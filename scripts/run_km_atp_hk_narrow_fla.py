"""Run a narrow, guarded Brodbar FLA pass for ``km_ATP_HK`` only.

The mild-feedback VEGLC/VHK/VPEP/VPK seed is kept fixed except for the single
ATP-affinity parameter. The focused objective includes the native teacher
fluxes plus ATP, PEP, and G6P, and the candidate is replayed automatically on
the full Brodbar panel before it can be considered for promotion.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
SCRIPT_DIR = ROOT / "scripts"
DEFAULT_SEED_PARAMS = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "vpep_vpk_coupled_mild_feedback_46d_n20"
    / "seed_fixed_params.json"
)
DEFAULT_OUT_DIR = ROOT / "Simulations" / "brodbar" / "hermes" / "km_atp_hk_narrow_mild_feedback_46d"

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from MM_calibration import EXP_TO_MODEL, PHASE1_PARAMS, load_experimental_data, load_initial_conditions, should_use_log_sampling  # noqa: E402
from evaluate_brodbar_candidate_full_panel import run_evaluation as run_full_panel  # noqa: E402
from run_glucose_utilization_fla import (  # noqa: E402
    FLUX_TARGETS,
    GlucoseUtilizationObjective,
    HAS_OPTUNA,
    _build_lactate_teacher_dataset,
    _extract_brodbar_targets,
    _flatten_trial_rows,
    _jsonable,
    _local_bounds,
    _nrmse,
    _slope_nrmse,
    optuna,
)


EXTRA_TARGETS = ("ATP", "PEP", "G6P")
GUARD_CONCENTRATIONS = ("ATP", "PEP", "G6P", "GLC", "LAC", "EGLC", "ELAC")
GUARD_FLUXES = ("VEGLC", "VELAC", "VLDH")
TARGET_WEIGHTS = {"ATP": 8.0, "PEP": 5.0, "G6P": 5.0}
DEFAULTS = {"km_ATP_HK": PHASE1_PARAMS["km_ATP_HK"][0]}


def _full_experimental_curves(t_max: float) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    time_exp, exp_values, name_to_row = load_experimental_data()
    mask = (time_exp >= 1.0 - 1e-9) & (time_exp <= float(t_max) + 1e-9)
    curves: dict[str, np.ndarray] = {}
    for name in (*GUARD_CONCENTRATIONS, "PYR"):
        if name not in name_to_row:
            raise KeyError(f"Brodbar experimental guard target {name!r} is missing")
        curves[name] = np.asarray(exp_values[name_to_row[name], mask], dtype=float)
    return np.asarray(time_exp[mask], dtype=float), curves


def _state_curve(sol: Any, name: str, time_exp: np.ndarray) -> np.ndarray:
    idx = int(EXP_TO_MODEL[name])
    return np.interp(time_exp, np.asarray(sol.t, dtype=float), sol.y[idx, :])


def _flux_details(
    *,
    sim_flux: Mapping[str, np.ndarray],
    teacher_dataset: Mapping[str, Any],
) -> dict[str, dict[str, float]]:
    teacher_curves = teacher_dataset["reaction_flux_curves"]
    details: dict[str, dict[str, float]] = {}
    for reaction in GUARD_FLUXES:
        target = np.asarray(teacher_curves[reaction]["dense_values"], dtype=float)
        simulated = np.asarray(sim_flux[reaction], dtype=float)
        rmse = float(np.sqrt(np.mean((simulated - target) ** 2)))
        norm = float(max(np.mean(np.abs(target)), 1e-4))
        details[reaction] = {
            "rmse": rmse,
            "nrmse": rmse / norm,
            "target_mean_abs": norm,
        }
    return details


class GuardedKmAtpHkObjective:
    """Thin wrapper adding energy targets and hard-guard diagnostics."""

    def __init__(
        self,
        *,
        x0: np.ndarray,
        seed_params: Mapping[str, Any],
        exp_time: np.ndarray,
        exp_curves: Mapping[str, np.ndarray],
        teacher_dataset: Mapping[str, Any],
        method: str,
        rtol: float,
        atol: float,
        energy_weight: float,
        energy_endpoint_weight: float,
        guard_weight: float,
    ) -> None:
        self.base = GlucoseUtilizationObjective(
            x0=x0,
            seed_params=seed_params,
            tracked_param_names=("km_ATP_HK",),
            exp_time=exp_time,
            exp_curves={name: exp_curves[name] for name in ("EGLC", "ELAC", "GLC", "LAC", "PYR")},
            teacher_dataset=teacher_dataset,
            method=method,
            rtol=rtol,
            atol=atol,
            level_weight=1.2,
            endpoint_weight=3.0,
            slope_weight=2.0,
            flux_weight=2.5,
            guard_weight=5.0,
            regularization_weight=0.35,
        )
        self.seed_params = dict(seed_params)
        self.exp_time = np.asarray(exp_time, dtype=float)
        self.exp_curves = {name: np.asarray(values, dtype=float) for name, values in exp_curves.items()}
        self.teacher_dataset = teacher_dataset
        self.energy_weight = float(energy_weight)
        self.energy_endpoint_weight = float(energy_endpoint_weight)
        self.guard_weight = float(guard_weight)
        self.seed_reference: dict[str, Any] | None = None
        self.trials: list[dict[str, Any]] = []
        self.best_payload: dict[str, Any] | None = None

    def _energy_metrics(self, sol: Any) -> dict[str, dict[str, float]]:
        metrics: dict[str, dict[str, float]] = {}
        for name in EXTRA_TARGETS:
            simulated = _state_curve(sol, name, self.exp_time)
            metrics[name] = _nrmse(simulated, self.exp_curves[name])
            metrics[name]["slope_nrmse"] = _slope_nrmse(simulated, self.exp_curves[name], self.exp_time)
        return metrics

    def _trajectory_guard_rows(self, sol: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for name in GUARD_CONCENTRATIONS:
            simulated = _state_curve(sol, name, self.exp_time)
            experimental = self.exp_curves[name]
            scale = max(float(np.mean(np.abs(experimental))), 0.01)
            rows.append(
                {
                    "metabolite": name,
                    "max_abs_error": float(np.max(np.abs(simulated - experimental)) / scale),
                    "endpoint_error": float(abs(simulated[-1] - experimental[-1]) / max(abs(float(experimental[-1])), 0.01)),
                    "final_value": float(simulated[-1]),
                }
            )
        return rows

    def _guard_loss(
        self,
        payload: Mapping[str, Any],
        energy_metrics: Mapping[str, Mapping[str, float]],
        flux_details: Mapping[str, Mapping[str, float]],
    ) -> tuple[float, list[str]]:
        if self.seed_reference is None:
            return 0.0, []
        seed = self.seed_reference
        violations: list[str] = []
        penalty = 0.0
        all_metrics = {**seed["metrics"], **seed["energy_metrics"]}
        candidate_metrics = {**payload["metrics"], **energy_metrics}

        for name in GUARD_CONCENTRATIONS:
            seed_metric = all_metrics[name]
            candidate_metric = candidate_metrics[name]
            limit = float(seed_metric["nrmse"]) * 1.05 + 0.01
            violation = max(0.0, float(candidate_metric["nrmse"]) - limit)
            penalty += violation * violation
            if violation > 0.0:
                violations.append(f"{name} nRMSE guard")
            endpoint_limit = float(seed_metric["endpoint_error"]) * 1.10 + 0.01
            endpoint_violation = max(0.0, float(candidate_metric["endpoint_error"]) - endpoint_limit)
            penalty += endpoint_violation * endpoint_violation
            if endpoint_violation > 0.0:
                violations.append(f"{name} endpoint guard")

        seed_atp = float(seed["sim_final"]["ATP"])
        candidate_atp = float(payload["sim_final"]["ATP"])
        atp_floor = max(seed_atp * 0.95, 1e-8)
        atp_violation = max(0.0, (atp_floor - candidate_atp) / max(seed_atp, 1e-8))
        penalty += atp_violation * atp_violation
        if atp_violation > 0.0:
            violations.append("ATP endpoint floor")

        for reaction in GUARD_FLUXES:
            seed_flux = seed["teacher_flux_details"][reaction]
            candidate_flux = flux_details[reaction]
            limit = float(seed_flux["nrmse"]) * 1.08 + 0.01
            violation = max(0.0, float(candidate_flux["nrmse"]) - limit)
            penalty += violation * violation
            if violation > 0.0:
                violations.append(f"{reaction} teacher-flux guard")
        return float(penalty), sorted(set(violations))

    def evaluate(self, overrides: Mapping[str, Any], *, label: str, record: bool = True) -> dict[str, Any]:
        start = time.perf_counter()
        payload = self.base.evaluate(overrides, label=label, record=False)
        if "sol" not in payload:
            return payload
        energy_metrics = self._energy_metrics(payload["sol"])
        payload["sim_final"].update(
            {
                name: float(_state_curve(payload["sol"], name, self.exp_time)[-1])
                for name in EXTRA_TARGETS
            }
        )
        flux_details = _flux_details(sim_flux=payload["sim_flux"], teacher_dataset=self.teacher_dataset)
        extra_level = float(
            sum(TARGET_WEIGHTS[name] * energy_metrics[name]["nrmse"] for name in EXTRA_TARGETS)
            / sum(TARGET_WEIGHTS.values())
        )
        extra_endpoint = float(
            sum(TARGET_WEIGHTS[name] * energy_metrics[name]["endpoint_error"] for name in EXTRA_TARGETS)
            / sum(TARGET_WEIGHTS.values())
        )
        guard_loss, guard_violations = self._guard_loss(payload, energy_metrics, flux_details)
        payload["energy_metrics"] = energy_metrics
        payload["teacher_flux_details"] = flux_details
        payload["energy_level_loss"] = extra_level
        payload["energy_endpoint_loss"] = extra_endpoint
        payload["guard_loss"] = float(payload.get("guard_loss", 0.0)) + guard_loss
        payload["guard_violations"] = guard_violations
        payload["trajectory_guard"] = self._trajectory_guard_rows(payload["sol"])
        payload["loss"] = float(
            payload["loss"]
            + self.energy_weight * extra_level
            + self.energy_endpoint_weight * extra_endpoint
            + self.guard_weight * guard_loss
        )
        payload["elapsed_sec"] = float(time.perf_counter() - start)
        if record:
            self.trials.append({key: value for key, value in payload.items() if key not in {"sol", "sim_exp", "sim_flux"}})
        if self.best_payload is None or float(payload["loss"]) < float(self.best_payload["loss"]):
            self.best_payload = payload
        return payload

    def __call__(self, overrides: Mapping[str, Any], *, label: str = "trial") -> float:
        return float(self.evaluate(overrides, label=label)["loss"])


def _acceptance(seed: Mapping[str, Any], candidate: Mapping[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not float(candidate["loss"]) < float(seed["loss"]):
        reasons.append("focused guarded loss did not improve")
    if float(candidate["metrics"]["GLC"]["nrmse"]) >= float(seed["metrics"]["GLC"]["nrmse"]) * 0.98:
        reasons.append("GLC nRMSE improvement below 2%")
    if float(candidate["sim_final"]["ATP"]) < float(seed["sim_final"]["ATP"]) * 0.95:
        reasons.append("ATP endpoint floor failed")
    if candidate.get("guard_violations"):
        reasons.extend(candidate["guard_violations"])
    return not reasons, reasons or ["candidate passed focused km_ATP_HK guards"]


def _final_value(payload: Mapping[str, Any], name: str) -> float:
    if name in payload.get("sim_final", {}):
        return float(payload["sim_final"][name])
    for row in payload.get("trajectory_guard", []):
        if row.get("metabolite") == name:
            return float(row["final_value"])
    raise KeyError(f"No final value available for {name!r}")


def _panel_acceptance(manifest: Mapping[str, Any]) -> tuple[bool, list[str]]:
    decision = manifest["decision"]
    reasons: list[str] = []
    mean = decision["mean_nrmse"]
    median = decision["median_nrmse"]
    if float(mean["candidate"]) > float(mean["baseline"]) * 1.05:
        reasons.append("full-panel mean nRMSE regressed")
    if float(median["candidate"]) > float(median["baseline"]) * 1.05:
        reasons.append("full-panel median nRMSE regressed")
    metrics_path = Path(str(manifest["metrics_csv"]))
    if metrics_path.exists():
        panel_metrics = pd.read_csv(metrics_path)
        for name in ("EGLC", "G6P", "PEP", "ATP"):
            rows = panel_metrics[panel_metrics["metabolite"] == name]
            if not rows.empty:
                row = rows.iloc[0]
                if float(row["candidate_nrmse"]) > float(row["baseline_nrmse"]) * 1.10 + 0.01:
                    reasons.append(f"full-panel {name} guard failed")
    return not reasons, reasons or ["candidate passed full-panel non-inferiority gate"]


def _plot_result(
    *,
    seed: Mapping[str, Any],
    candidate: Mapping[str, Any],
    objective: GuardedKmAtpHkObjective,
    out_path: Path,
) -> None:
    names = ("EGLC", "ELAC", "GLC", "LAC", "PYR", "ATP", "PEP", "G6P")
    fig, axes = plt.subplots(3, 4, figsize=(15, 11))
    for ax, name in zip(axes.flat[:8], names):
        idx = int(EXP_TO_MODEL[name])
        ax.plot(seed["sol"].t, seed["sol"].y[idx, :], color="#64748b", linewidth=1.8, label="seed")
        ax.plot(candidate["sol"].t, candidate["sol"].y[idx, :], color="#2563eb", linewidth=2.2, label="km_ATP_HK candidate")
        ax.scatter(objective.exp_time, objective.exp_curves[name], color="#111827", s=18, label="Brodbar")
        metric = candidate["metrics"].get(name, candidate["energy_metrics"].get(name, {}))
        ax.set_title(f"{name} nRMSE {metric.get('nrmse', float('nan')):.2f}")
        ax.set_xlabel("Time (days)")
        ax.set_ylabel("mM")
        ax.grid(True, alpha=0.22)
    for ax, reaction in zip(axes.flat[8:11], GUARD_FLUXES):
        target = objective.teacher_dataset["reaction_flux_curves"][reaction]
        ax.plot(objective.base.teacher_time, target["dense_values"], color="#111827", linewidth=2.0, label="teacher")
        ax.plot(objective.base.teacher_time, seed["sim_flux"][reaction], color="#64748b", linewidth=1.8, label="seed")
        ax.plot(objective.base.teacher_time, candidate["sim_flux"][reaction], color="#2563eb", linewidth=2.2, label="candidate")
        ax.set_title(f"{reaction} flux")
        ax.set_xlabel("Time (days)")
        ax.set_ylabel("mM/day")
        ax.grid(True, alpha=0.22)
    ax = axes.flat[11]
    labels = ["GLC", "ATP", "PEP", "G6P", "LAC", "ELAC"]
    deltas = []
    for name in labels:
        cand_metric = candidate["metrics"].get(name, candidate["energy_metrics"].get(name, {}))
        seed_metric = seed["metrics"].get(name, seed["energy_metrics"].get(name, {}))
        deltas.append(float(cand_metric["nrmse"]) - float(seed_metric["nrmse"]))
    ax.barh(labels, deltas, color=["#16a34a" if value < 0 else "#dc2626" for value in deltas])
    ax.axvline(0.0, color="#111827", linewidth=0.9)
    ax.set_title("Candidate minus seed nRMSE")
    ax.grid(True, axis="x", alpha=0.22)
    handles, labels_legend = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels_legend, loc="upper center", bbox_to_anchor=(0.5, 0.965), ncol=3, frameon=False)
    fig.suptitle("Brodbar narrow FLA: km_ATP_HK only", fontsize=15, y=0.995)
    fig.subplots_adjust(top=0.89, hspace=0.34, wspace=0.28)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _write_report(path: Path, *, summary: Mapping[str, Any], panel_manifest: Mapping[str, Any]) -> None:
    seed = summary["seed"]
    candidate = summary["best_candidate"]
    lines = [
        "# Narrow `km_ATP_HK` FLA decision",
        "",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        "- Horizon: 46 days",
        "- Open parameter: `km_ATP_HK` only",
        "- Fixed hypothesis: mild-feedback VEGLC seed, `vmax_VHK`, `VPEP_PASE`, `VPK`, `km_ATP_PFK`, `ki_ATP_PK`, and `km_NADH_NAD`.",
        "",
        "## Focused result",
        "",
        f"- Seed `km_ATP_HK`: `{seed['params']['km_ATP_HK']:.8g}`.",
        f"- Candidate `km_ATP_HK`: `{candidate['params']['km_ATP_HK']:.8g}`.",
        f"- Focused loss: `{seed['loss']:.6g} -> {candidate['loss']:.6g}`.",
        f"- Focused acceptance: `{summary['focused_accepted']}`.",
        f"- Focused reasons: {', '.join(summary['focused_reasons'])}.",
        "",
        "Guarded targets: `ATP`, `PEP`, `G6P`, `GLC`, `LAC`, `EGLC`, `ELAC`, `VEGLC`, `VELAC`, and `VLDH`.",
        "",
        "## Full Brodbar panel",
        "",
        f"- Mapped metabolites: `{len(panel_manifest['mapped_metabolites'])}`.",
        f"- Mean nRMSE: `{panel_manifest['decision']['mean_nrmse']['baseline']:.6g} -> {panel_manifest['decision']['mean_nrmse']['candidate']:.6g}`.",
        f"- Median nRMSE: `{panel_manifest['decision']['median_nrmse']['baseline']:.6g} -> {panel_manifest['decision']['median_nrmse']['candidate']:.6g}`.",
        f"- Full-panel acceptance: `{summary['full_panel_accepted']}`.",
        f"- Full-panel reasons: {', '.join(summary['full_panel_reasons'])}.",
        "",
        "## Decision",
        "",
        f"**Final promotion decision: `{summary['accepted']}`.** No parameter file outside this run directory was overwritten.",
        "",
        "A candidate is promotable only when both the focused guards and the full-panel non-inferiority gate pass. The next separate hypothesis remains `km_NADH_NAD`, but it stays closed in this experiment.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_pass(
    *,
    out_dir: Path,
    seed_params_path: Path,
    n_trials: int,
    global_trials: int,
    t_max: float,
    teacher_dense_points: int,
    local_bound_scale: float,
    seed: int,
    method: str,
    rtol: float,
    atol: float,
    energy_weight: float,
    energy_endpoint_weight: float,
    guard_weight: float,
    resume_candidate_path: Path | None = None,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    seed_params = json.loads(Path(seed_params_path).read_text(encoding="utf-8"))
    seed_params = {key: value for key, value in seed_params.items() if not isinstance(value, bool) and isinstance(value, (int, float, str))}
    exp_time, base_curves = _extract_brodbar_targets(t_max)
    full_time, full_curves = _full_experimental_curves(t_max)
    if not np.allclose(exp_time, full_time):
        raise RuntimeError("Brodbar target time grids are inconsistent")
    teacher_path = out_dir / "teacher_flux_dataset_km_atp_hk.json"
    teacher_dataset = _build_lactate_teacher_dataset(
        exp_time=exp_time,
        exp_curves=base_curves,
        dense_points=teacher_dense_points,
        out_path=teacher_path,
    )
    x0 = np.asarray(load_initial_conditions(), dtype=float)
    objective = GuardedKmAtpHkObjective(
        x0=x0,
        seed_params=seed_params,
        exp_time=exp_time,
        exp_curves=full_curves,
        teacher_dataset=teacher_dataset,
        method=method,
        rtol=rtol,
        atol=atol,
        energy_weight=energy_weight,
        energy_endpoint_weight=energy_endpoint_weight,
        guard_weight=guard_weight,
    )
    bounds = _local_bounds(seed_params, ("km_ATP_HK",), local_bound_scale)
    center, lower, upper = bounds["km_ATP_HK"]
    print(f"km_ATP_HK narrow bounds: {lower:.8g} .. {upper:.8g} (center={center:.8g})", flush=True)

    seed_eval = objective.evaluate({"km_ATP_HK": center}, label="mild_feedback_seed")
    objective.seed_reference = seed_eval
    objective.base.seed_guard_reference = seed_eval
    objective.best_payload = seed_eval
    resumed_payload: dict[str, Any] | None = None
    if resume_candidate_path is not None:
        resumed_payload_params = json.loads(Path(resume_candidate_path).read_text(encoding="utf-8"))
        resumed_value = float(resumed_payload_params["km_ATP_HK"])
        resumed_payload = objective.evaluate({"km_ATP_HK": resumed_value}, label="resumed_best_candidate")
        objective.best_payload = resumed_payload
    elif HAS_OPTUNA and int(n_trials) > 0:
        sampler = optuna.samplers.TPESampler(seed=int(seed), n_startup_trials=min(6, max(2, int(n_trials) // 3)))
        study = optuna.create_study(direction="minimize", sampler=sampler)
        study.enqueue_trial({"km_ATP_HK": center})
        for multiplier in (0.5, 0.75, 1.5, 2.0):
            study.enqueue_trial({"km_ATP_HK": float(np.clip(center * multiplier, lower, upper))})

        def optuna_objective(trial: Any) -> float:
            value = trial.suggest_float(
                "km_ATP_HK",
                float(lower),
                float(upper),
                log=should_use_log_sampling("km_ATP_HK", float(lower), float(upper)),
            )
            payload = objective.evaluate({"km_ATP_HK": value}, label=f"trial_{trial.number}")
            print(
                f"trial {trial.number:03d}: loss={payload['loss']:.5f}, GLC={payload['metrics']['GLC']['nrmse']:.4f}, "
                f"ATP={payload['sim_final']['ATP']:.6g}, PEP={payload['energy_metrics']['PEP']['nrmse']:.4f}, "
                f"G6P={payload['energy_metrics']['G6P']['nrmse']:.4f}, km_ATP_HK={value:.7g}, "
                f"guards={','.join(payload['guard_violations']) or 'none'}",
                flush=True,
            )
            return float(payload["loss"])

        study.optimize(optuna_objective, n_trials=int(n_trials), show_progress_bar=False)
    else:
        multipliers = np.linspace(1.0 / local_bound_scale, local_bound_scale, max(2, int(n_trials)))
        for index, multiplier in enumerate(multipliers):
            objective.evaluate(
                {"km_ATP_HK": float(np.clip(center * multiplier, lower, upper))},
                label=f"grid_{index}",
            )

    if resume_candidate_path is None and int(global_trials) > 0 and objective.best_payload is not None:
        best_value = float(objective.best_payload["params"]["km_ATP_HK"])
        for index in range(int(global_trials)):
            scale = 1.0 + 0.10 * (index + 1)
            for direction in (-1.0, 1.0):
                objective.evaluate(
                    {"km_ATP_HK": float(np.clip(best_value * (1.0 + direction * (scale - 1.0)), lower, upper))},
                    label=f"local_refine_{index}_{direction:+.0f}",
                )

    best = resumed_payload or objective.best_payload or seed_eval
    best_final = objective.evaluate(best["params"], label="best_final")
    candidate_params = dict(seed_params)
    candidate_params.update(best_final["params"])
    focused_accepted, focused_reasons = _acceptance(seed_eval, best_final)

    seed_path = out_dir / "seed_params.json"
    candidate_path = out_dir / "candidate_params.json"
    promoted_path = out_dir / "promoted_or_seed_params.json"
    seed_path.write_text(json.dumps(_jsonable(seed_params), indent=2), encoding="utf-8")
    candidate_path.write_text(json.dumps(_jsonable(candidate_params), indent=2), encoding="utf-8")

    existing_panel_manifest = out_dir / "full_panel" / "manifest.json"
    if resume_candidate_path is not None and existing_panel_manifest.exists():
        panel_manifest = json.loads(existing_panel_manifest.read_text(encoding="utf-8"))
    else:
        panel_manifest = run_full_panel(
            baseline_params_path=seed_path,
            candidate_params_path=candidate_path,
            out_dir=out_dir / "full_panel",
            dense_points=240,
            method=method,
            rtol=rtol,
            atol=atol,
        )
    full_panel_accepted, full_panel_reasons = _panel_acceptance(panel_manifest)
    accepted = bool(focused_accepted and full_panel_accepted)
    promoted_params = candidate_params if accepted else dict(seed_params)
    promoted_path.write_text(json.dumps(_jsonable(promoted_params), indent=2), encoding="utf-8")
    if accepted:
        (out_dir / "best_params.json").write_text(json.dumps(_jsonable(candidate_params), indent=2), encoding="utf-8")

    trials_csv = out_dir / "optimization_trials.csv"
    if not (resume_candidate_path is not None and trials_csv.exists()):
        pd.DataFrame(_flatten_trial_rows(objective.trials)).to_csv(trials_csv, index=False)
    metrics_csv = out_dir / "km_atp_hk_metrics.csv"
    metric_rows = []
    for name in (*("EGLC", "ELAC", "GLC", "LAC", "PYR"), *EXTRA_TARGETS):
        seed_metric = seed_eval["metrics"].get(name, seed_eval["energy_metrics"].get(name, {}))
        candidate_metric = best_final["metrics"].get(name, best_final["energy_metrics"].get(name, {}))
        metric_rows.append(
            {
                "metabolite": name,
                "seed_nrmse": seed_metric["nrmse"],
                "candidate_nrmse": candidate_metric["nrmse"],
                "delta_nrmse": candidate_metric["nrmse"] - seed_metric["nrmse"],
                "seed_endpoint_error": seed_metric["endpoint_error"],
                "candidate_endpoint_error": candidate_metric["endpoint_error"],
                "delta_endpoint_error": candidate_metric["endpoint_error"] - seed_metric["endpoint_error"],
                "seed_final": _final_value(seed_eval, name),
                "candidate_final": _final_value(best_final, name),
                "experimental_final": full_curves[name][-1],
            }
        )
    pd.DataFrame(metric_rows).to_csv(metrics_csv, index=False)
    trajectory_csv = out_dir / "km_atp_hk_trajectory.csv"
    trajectory_rows = []
    for t in best_final["sol"].t:
        row = {"time_day": float(t)}
        for name in (*("EGLC", "ELAC", "GLC", "LAC", "PYR"), *EXTRA_TARGETS):
            idx = int(EXP_TO_MODEL[name])
            row[f"seed_{name}"] = float(np.interp(t, seed_eval["sol"].t, seed_eval["sol"].y[idx, :]))
            row[f"candidate_{name}"] = float(np.interp(t, best_final["sol"].t, best_final["sol"].y[idx, :]))
            row[f"experimental_{name}"] = float(np.interp(t, exp_time, full_curves[name]))
        trajectory_rows.append(row)
    pd.DataFrame(trajectory_rows).to_csv(trajectory_csv, index=False)
    plot_path = out_dir / "km_atp_hk_narrow_fla.png"
    _plot_result(seed=seed_eval, candidate=best_final, objective=objective, out_path=plot_path)

    summary = {
        "contract_type": "km_atp_hk_narrow_fla_result",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed_params_path": str(seed_params_path),
        "optimized_params": ["km_ATP_HK"],
        "fixed_params": ["vmax_VHK", "vmax_VPEP_PASE", "vmax_VPK", "km_ATP_PFK", "ki_ATP_PK", "km_NADH_NAD"],
        "bounds": {"km_ATP_HK": [center, lower, upper]},
        "t_max": float(t_max),
        "n_trials": int(n_trials),
        "global_trials": int(global_trials),
        "teacher_dense_points": int(teacher_dense_points),
        "solver": {"method": method, "rtol": float(rtol), "atol": float(atol)},
        "guarded_targets": list(GUARD_CONCENTRATIONS),
        "guarded_fluxes": list(GUARD_FLUXES),
        "energy_weights": TARGET_WEIGHTS,
        "seed": {key: value for key, value in seed_eval.items() if key not in {"sol", "sim_exp", "sim_flux"}},
        "best_candidate": {key: value for key, value in best_final.items() if key not in {"sol", "sim_exp", "sim_flux"}},
        "focused_accepted": bool(focused_accepted),
        "focused_reasons": focused_reasons,
        "full_panel_accepted": bool(full_panel_accepted),
        "full_panel_reasons": full_panel_reasons,
        "accepted": accepted,
        "parameters_promoted": accepted,
        "full_panel": {
            "manifest": panel_manifest["manifest_path"],
            "decision": panel_manifest["decision"],
        },
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "decision_report": str(out_dir / "decision_report.md"),
            "seed_params": str(seed_path),
            "candidate_params": str(candidate_path),
            "promoted_or_seed_params": str(promoted_path),
            "best_params": str(out_dir / "best_params.json") if accepted else None,
            "teacher_dataset": str(teacher_path),
            "trials_csv": str(trials_csv),
            "metrics_csv": str(metrics_csv),
            "trajectory_csv": str(trajectory_csv),
            "plot": str(plot_path),
            "full_panel_manifest": panel_manifest["manifest_path"],
            "full_panel_delta_summary": panel_manifest["delta_summary_png"],
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(_jsonable(summary), indent=2), encoding="utf-8")
    _write_report(out_dir / "decision_report.md", summary=summary, panel_manifest=panel_manifest)
    print(json.dumps(_jsonable(summary), indent=2), flush=True)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a narrow guarded FLA pass for km_ATP_HK only")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--seed-params", type=Path, default=DEFAULT_SEED_PARAMS)
    parser.add_argument("--n-trials", type=int, default=24)
    parser.add_argument("--global-trials", type=int, default=3)
    parser.add_argument("--t-max", type=float, default=46.0)
    parser.add_argument("--teacher-dense-points", type=int, default=96)
    parser.add_argument("--local-bound-scale", type=float, default=2.0)
    parser.add_argument("--seed", type=int, default=421)
    parser.add_argument("--method", default="LSODA")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    parser.add_argument("--energy-weight", type=float, default=3.0)
    parser.add_argument("--energy-endpoint-weight", type=float, default=4.0)
    parser.add_argument("--guard-weight", type=float, default=20.0)
    parser.add_argument("--resume-candidate", type=Path, default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    run_pass(
        out_dir=args.out_dir,
        seed_params_path=args.seed_params,
        n_trials=args.n_trials,
        global_trials=args.global_trials,
        t_max=args.t_max,
        teacher_dense_points=args.teacher_dense_points,
        local_bound_scale=args.local_bound_scale,
        seed=args.seed,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
        energy_weight=args.energy_weight,
        energy_endpoint_weight=args.energy_endpoint_weight,
        guard_weight=args.guard_weight,
        resume_candidate_path=args.resume_candidate,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
