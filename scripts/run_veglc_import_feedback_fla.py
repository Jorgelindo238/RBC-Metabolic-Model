"""Controlled VEGLC import-cap/feedback FLA pass for Brodbar.

This pass keeps the current ``transport_depletion_gate`` hypothesis reversible
and activates a strictly local family variant:

    transport_depletion_gate_import_feedback

Only VEGLC transport-shape parameters are opened.  The objective keeps direct
pressure on EGLC slope/endpoint and VEGLC teacher flux, while also asking for
lower intracellular GLC without sacrificing ELAC/LAC/PYR or VELAC/VLDH flux
guards.
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
DEFAULT_SEED_PARAMS = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "glucose_utilization_vhk_atp_46d_n16_upper5"
    / "candidate_params.json"
)
DEFAULT_GLOBAL_BASELINE_PARAMS = ROOT / "Simulations" / "brodbar" / "calibration" / "best_params.json"
DEFAULT_OUT_DIR = ROOT / "Simulations" / "brodbar" / "hermes" / "veglc_import_feedback_46d"

for path in (str(ROOT), str(SRC_DIR), str(Path(__file__).resolve().parent)):
    if path not in sys.path:
        sys.path.insert(0, path)

from MM_calibration import EXP_TO_MODEL, PHASE1_PARAMS, get_phase_params, load_initial_conditions, should_use_log_sampling  # noqa: E402
from run_lactate_focused_fla import (  # noqa: E402
    HAS_OPTUNA,
    TARGETS,
    _build_lactate_teacher_dataset,
    _extract_brodbar_targets,
    _flatten_trial_rows,
    _jsonable,
    _load_params,
    _nrmse,
    _sim_fluxes,
    _simulate,
    _slope_nrmse,
    optuna,
)


FLUX_TARGETS = ("VEGLC", "VELAC", "VLDH")
FIXED_VEGLC_FAMILY = {
    "kinetic_family_VEGLC": "transport_depletion_gate_import_feedback",
    "hybrid_blend_VEGLC": 1.0,
}
OPTIMIZED_PARAM_NAMES = (
    "vmax_VEGLC",
    "km_EGLC",
    "km_GLC_transport",
    "hybrid_import_hill_VEGLC",
    "hybrid_export_hill_VEGLC",
    "hybrid_reverse_scale_VEGLC",
    "transport_gate_km_VEGLC",
    "transport_gate_hill_VEGLC",
    "transport_gate_feedback_strength_VEGLC",
    "transport_gate_feedback_km_GLC_VEGLC",
    "transport_gate_feedback_hill_VEGLC",
    "transport_gate_import_cap_VEGLC",
)


def _local_bounds(
    seed_params: Mapping[str, Any],
    param_names: Sequence[str],
    scale: float,
) -> dict[str, tuple[float, float, float]]:
    phase_params = {**PHASE1_PARAMS, **get_phase_params(1, "glycolysis_terminal")}
    out: dict[str, tuple[float, float, float]] = {}
    for name in param_names:
        if name not in phase_params:
            raise KeyError(f"No phase bounds found for {name!r}")
        default, lo, hi = phase_params[name]
        center = float(seed_params.get(name, default))
        if name.startswith(("hybrid_", "transport_gate_")):
            local_lo = float(lo)
            local_hi = float(hi)
        else:
            local_lo = max(float(lo), center / max(float(scale), 1.0))
            local_hi = min(float(hi), center * max(float(scale), 1.0))
        if local_lo >= local_hi:
            local_lo, local_hi = float(lo), float(hi)
        out[name] = (center, local_lo, local_hi)
    return out


class VeglcImportFeedbackObjective:
    def __init__(
        self,
        *,
        x0: np.ndarray,
        seed_params: Mapping[str, Any],
        fixed_family_params: Mapping[str, Any],
        tracked_param_names: Sequence[str],
        exp_time: np.ndarray,
        exp_curves: Mapping[str, np.ndarray],
        teacher_dataset: Mapping[str, Any],
        method: str,
        rtol: float,
        atol: float,
        level_weight: float,
        endpoint_weight: float,
        slope_weight: float,
        flux_weight: float,
        guard_weight: float,
        regularization_weight: float,
    ) -> None:
        self.x0 = np.asarray(x0, dtype=float)
        self.seed_params = dict(seed_params)
        self.fixed_family_params = dict(fixed_family_params)
        self.tracked_param_names = tuple(tracked_param_names)
        self.exp_time = np.asarray(exp_time, dtype=float)
        self.exp_curves = {name: np.asarray(values, dtype=float) for name, values in exp_curves.items()}
        self.teacher_time = np.asarray(teacher_dataset["dense_timepoints"], dtype=float)
        self.teacher_flux = {
            reaction: np.asarray(teacher_dataset["reaction_flux_curves"][reaction]["dense_values"], dtype=float)
            for reaction in FLUX_TARGETS
        }
        self.method = str(method)
        self.rtol = float(rtol)
        self.atol = float(atol)
        self.level_weight = float(level_weight)
        self.endpoint_weight = float(endpoint_weight)
        self.slope_weight = float(slope_weight)
        self.flux_weight = float(flux_weight)
        self.guard_weight = float(guard_weight)
        self.regularization_weight = float(regularization_weight)
        self.t_eval = np.unique(np.concatenate([self.exp_time, self.teacher_time]))
        self.trials: list[dict[str, Any]] = []
        self.best_payload: dict[str, Any] | None = None
        self.seed_guard_reference: dict[str, Any] | None = None

    def _build_params(self, overrides: Mapping[str, Any], *, apply_fixed_family: bool) -> dict[str, Any]:
        params = dict(self.seed_params)
        if apply_fixed_family:
            params.update(self.fixed_family_params)
        for name, value in overrides.items():
            params[name] = float(value)
        return params

    def _param_regularization(self, params: Mapping[str, Any]) -> float:
        terms = []
        for name in self.tracked_param_names:
            default = PHASE1_PARAMS[name][0]
            value = max(float(params.get(name, default)), 1e-9)
            seed = max(float(self.seed_params.get(name, default)), 1e-9)
            if name == "transport_gate_feedback_strength_VEGLC":
                terms.append((value / max(PHASE1_PARAMS[name][2], 1e-9)) ** 2)
            else:
                terms.append(math.log(value / seed) ** 2)
        return float(np.mean(terms)) if terms else 0.0

    def evaluate(
        self,
        overrides: Mapping[str, Any],
        *,
        label: str,
        apply_fixed_family: bool,
        record: bool = True,
    ) -> dict[str, Any]:
        start = time.perf_counter()
        params = self._build_params(overrides, apply_fixed_family=apply_fixed_family)
        try:
            sol = _simulate(
                x0=self.x0,
                params=params,
                t_eval=self.t_eval,
                method=self.method,
                rtol=self.rtol,
                atol=self.atol,
            )
        except Exception as exc:
            payload = {
                "label": label,
                "params": {name: params.get(name) for name in self.tracked_param_names},
                "fixed_family_params": dict(self.fixed_family_params) if apply_fixed_family else {},
                "loss": float("inf"),
                "error": str(exc),
                "elapsed_sec": time.perf_counter() - start,
            }
            if record:
                self.trials.append(payload)
            return payload

        sim_exp = {
            name: np.interp(self.exp_time, sol.t, sol.y[EXP_TO_MODEL[name], :])
            for name in TARGETS
        }
        metrics = {name: _nrmse(sim_exp[name], self.exp_curves[name]) for name in TARGETS}
        slope_metrics = {
            name: _slope_nrmse(sim_exp[name], self.exp_curves[name], self.exp_time)
            for name in ("EGLC", "ELAC", "GLC", "LAC")
        }

        level_weights = {"EGLC": 5.0, "ELAC": 2.0, "GLC": 14.0, "LAC": 6.0, "PYR": 1.0}
        endpoint_weights = {"EGLC": 14.0, "ELAC": 3.0, "GLC": 16.0, "LAC": 6.0, "PYR": 1.0}
        slope_weights = {"EGLC": 8.0, "ELAC": 2.0, "GLC": 6.0, "LAC": 3.0}
        level_loss = float(
            sum(level_weights[name] * metrics[name]["nrmse"] for name in TARGETS)
            / sum(level_weights.values())
        )
        endpoint_loss = float(
            sum(endpoint_weights[name] * metrics[name]["endpoint_error"] for name in TARGETS)
            / sum(endpoint_weights.values())
        )
        slope_loss = float(
            sum(slope_weights[name] * slope_metrics[name] for name in slope_metrics)
            / sum(slope_weights.values())
        )

        sim_flux = _sim_fluxes(sol, params, self.teacher_time)
        flux_details = {}
        flux_loss_terms = []
        flux_weights = {"VEGLC": 8.0, "VELAC": 3.0, "VLDH": 3.0}
        for reaction in FLUX_TARGETS:
            target = self.teacher_flux[reaction]
            sim = sim_flux[reaction]
            rmse = float(np.sqrt(np.mean((sim - target) ** 2)))
            norm = float(max(np.mean(np.abs(target)), 1e-4))
            nrmse = rmse / norm
            flux_loss_terms.append(flux_weights[reaction] * nrmse)
            flux_details[reaction] = {"rmse": rmse, "nrmse": nrmse, "weight": flux_weights[reaction]}
        flux_loss = float(sum(flux_loss_terms) / sum(flux_weights.values()))

        regularization_loss = self._param_regularization(params)
        guard_loss = 0.0
        if self.seed_guard_reference is not None:
            seed_metrics = self.seed_guard_reference["metrics"]
            seed_slope = self.seed_guard_reference["slope_metrics"]
            seed_flux = self.seed_guard_reference["teacher_flux_details"]
            guard_loss += 40.0 * max(
                0.0,
                metrics["EGLC"]["endpoint_error"] - max(0.08, seed_metrics["EGLC"]["endpoint_error"] + 0.03),
            ) ** 2
            guard_loss += 8.0 * max(0.0, slope_metrics["EGLC"] - seed_slope["EGLC"] * 1.15) ** 2
            guard_loss += 8.0 * max(0.0, metrics["ELAC"]["nrmse"] - seed_metrics["ELAC"]["nrmse"] * 1.08) ** 2
            guard_loss += 12.0 * max(0.0, metrics["LAC"]["nrmse"] - seed_metrics["LAC"]["nrmse"] * 1.05) ** 2
            guard_loss += 3.0 * max(0.0, metrics["PYR"]["nrmse"] - seed_metrics["PYR"]["nrmse"] * 1.15) ** 2
            guard_loss += 6.0 * max(0.0, flux_details["VEGLC"]["nrmse"] - seed_flux["VEGLC"]["nrmse"] * 1.20) ** 2
            for reaction in ("VELAC", "VLDH"):
                guard_loss += 5.0 * max(
                    0.0,
                    flux_details[reaction]["nrmse"] - seed_flux[reaction]["nrmse"] * 1.10,
                ) ** 2

        loss = (
            self.level_weight * level_loss
            + self.endpoint_weight * endpoint_loss
            + self.slope_weight * slope_loss
            + self.flux_weight * flux_loss
            + self.guard_weight * guard_loss
            + self.regularization_weight * regularization_loss
        )

        payload = {
            "label": label,
            "params": {name: params.get(name) for name in self.tracked_param_names},
            "fixed_family_params": dict(self.fixed_family_params) if apply_fixed_family else {},
            "loss": float(loss),
            "level_loss": level_loss,
            "endpoint_loss": endpoint_loss,
            "slope_loss": slope_loss,
            "teacher_flux_loss": flux_loss,
            "guard_loss": float(guard_loss),
            "regularization_loss": regularization_loss,
            "metrics": metrics,
            "slope_metrics": slope_metrics,
            "teacher_flux_details": flux_details,
            "sim_final": {name: float(sim_exp[name][-1]) for name in TARGETS},
            "exp_final": {name: float(self.exp_curves[name][-1]) for name in TARGETS},
            "elapsed_sec": float(time.perf_counter() - start),
            "sol": sol,
            "sim_exp": sim_exp,
            "sim_flux": sim_flux,
        }
        for name in self.tracked_param_names:
            payload[name] = params.get(name)
        if record:
            self.trials.append({k: v for k, v in payload.items() if k not in {"sol", "sim_exp", "sim_flux"}})
        if apply_fixed_family and (self.best_payload is None or payload["loss"] < self.best_payload["loss"]):
            self.best_payload = payload
        return payload

    def __call__(self, overrides: Mapping[str, Any], *, label: str = "trial") -> float:
        return float(self.evaluate(overrides, label=label, apply_fixed_family=True)["loss"])


def _metrics_table(
    *,
    seed: Mapping[str, Any],
    best: Mapping[str, Any],
    global_baseline: Mapping[str, Any] | None,
    out_path: Path,
) -> list[dict[str, Any]]:
    rows = []
    for name in TARGETS:
        seed_metric = seed["metrics"][name]
        best_metric = best["metrics"][name]
        row = {
            "metabolite": name,
            "seed_nrmse": seed_metric["nrmse"],
            "candidate_nrmse": best_metric["nrmse"],
            "delta_nrmse": best_metric["nrmse"] - seed_metric["nrmse"],
            "seed_endpoint_error": seed_metric["endpoint_error"],
            "candidate_endpoint_error": best_metric["endpoint_error"],
            "delta_endpoint_error": best_metric["endpoint_error"] - seed_metric["endpoint_error"],
            "exp_final": best["exp_final"][name],
            "seed_final": seed["sim_final"][name],
            "candidate_final": best["sim_final"][name],
        }
        if global_baseline is not None and "metrics" in global_baseline:
            row["global_baseline_nrmse"] = global_baseline["metrics"][name]["nrmse"]
            row["global_baseline_final"] = global_baseline["sim_final"][name]
        rows.append(row)
    pd.DataFrame(rows).to_csv(out_path, index=False)
    return rows


def _write_trajectory(
    *,
    best: Mapping[str, Any],
    seed: Mapping[str, Any],
    exp_time: np.ndarray,
    exp_curves: Mapping[str, np.ndarray],
    out_path: Path,
) -> None:
    dense_time = np.asarray(best["sol"].t, dtype=float)
    rows: list[dict[str, Any]] = []
    for t in dense_time:
        row: dict[str, Any] = {"time_day": float(t)}
        for name in TARGETS:
            idx = EXP_TO_MODEL[name]
            row[f"seed_{name}"] = float(np.interp(t, seed["sol"].t, seed["sol"].y[idx, :]))
            row[f"candidate_{name}"] = float(np.interp(t, best["sol"].t, best["sol"].y[idx, :]))
            row[f"exp_{name}"] = float(np.interp(t, exp_time, exp_curves[name]))
        for reaction in FLUX_TARGETS:
            row[f"seed_{reaction}"] = float(np.interp(t, seed["sim_flux_time"], seed["sim_flux_dense"][reaction]))
            row[f"candidate_{reaction}"] = float(
                np.interp(t, best["sim_flux_time"], best["sim_flux_dense"][reaction])
            )
        rows.append(row)
    pd.DataFrame(rows).to_csv(out_path, index=False)


def _plot_result(
    *,
    seed: Mapping[str, Any],
    best: Mapping[str, Any],
    global_baseline: Mapping[str, Any] | None,
    objective: VeglcImportFeedbackObjective,
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(3, 3, figsize=(15, 11), constrained_layout=True)
    axes_flat = axes.flatten()
    for ax, name in zip(axes_flat[:5], TARGETS):
        idx = EXP_TO_MODEL[name]
        if global_baseline is not None and "sol" in global_baseline:
            ax.plot(
                global_baseline["sol"].t,
                global_baseline["sol"].y[idx, :],
                color="#94a3b8",
                linewidth=1.5,
                label="global baseline",
            )
        ax.plot(seed["sol"].t, seed["sol"].y[idx, :], color="#64748b", linewidth=2.0, label="seed")
        ax.plot(best["sol"].t, best["sol"].y[idx, :], color="#2563eb", linewidth=2.4, label="import feedback")
        ax.scatter(objective.exp_time, objective.exp_curves[name], color="#111827", s=24, label="Brodbar")
        delta = best["metrics"][name]["nrmse"] - seed["metrics"][name]["nrmse"]
        ax.set_title(f"{name}  {seed['metrics'][name]['nrmse']:.2f}->{best['metrics'][name]['nrmse']:.2f}  d={delta:+.2f}")
        ax.set_xlabel("Time (days)")
        ax.set_ylabel("mM")
        ax.grid(True, alpha=0.25)

    for ax, reaction in zip(axes_flat[5:8], FLUX_TARGETS):
        ax.plot(objective.teacher_time, objective.teacher_flux[reaction], color="#111827", linewidth=2.1, label="teacher")
        ax.plot(objective.teacher_time, seed["sim_flux"][reaction], color="#64748b", linewidth=1.9, label="seed")
        ax.plot(objective.teacher_time, best["sim_flux"][reaction], color="#2563eb", linewidth=2.3, label="candidate")
        ax.set_title(f"{reaction} flux")
        ax.set_xlabel("Time (days)")
        ax.set_ylabel("mM/day")
        ax.grid(True, alpha=0.25)

    ax = axes_flat[8]
    metabolites = list(TARGETS)
    deltas = [best["metrics"][name]["nrmse"] - seed["metrics"][name]["nrmse"] for name in metabolites]
    colors = ["#16a34a" if value < 0 else "#dc2626" for value in deltas]
    ax.barh(metabolites, deltas, color=colors)
    ax.axvline(0, color="#111827", linewidth=1.0)
    ax.set_title("Candidate minus seed nRMSE")
    ax.set_xlabel("delta nRMSE")
    ax.grid(True, axis="x", alpha=0.25)

    handles, labels = axes_flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False)
    fig.suptitle("Brodbar FLA: controlled VEGLC import cap/feedback")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _acceptance(seed: Mapping[str, Any], best: Mapping[str, Any]) -> tuple[bool, list[str]]:
    accepted = True
    reasons = []
    if not float(best["loss"]) < float(seed["loss"]):
        accepted = False
        reasons.append("candidate did not improve the focused VEGLC feedback loss")
    if best["metrics"]["GLC"]["nrmse"] >= seed["metrics"]["GLC"]["nrmse"] * 0.80:
        accepted = False
        reasons.append("internal GLC nRMSE did not improve by at least 20%")
    if best["metrics"]["EGLC"]["endpoint_error"] > max(0.08, seed["metrics"]["EGLC"]["endpoint_error"] + 0.03):
        accepted = False
        reasons.append("EGLC endpoint guard failed")
    if best["slope_metrics"]["EGLC"] > seed["slope_metrics"]["EGLC"] * 1.20:
        accepted = False
        reasons.append("EGLC slope guard failed")
    if best["metrics"]["ELAC"]["nrmse"] > seed["metrics"]["ELAC"]["nrmse"] * 1.08:
        accepted = False
        reasons.append("ELAC nRMSE regressed beyond the guard")
    if best["metrics"]["LAC"]["nrmse"] > seed["metrics"]["LAC"]["nrmse"] * 1.05:
        accepted = False
        reasons.append("internal LAC nRMSE regressed beyond the guard")
    for reaction, factor in {"VEGLC": 1.20, "VELAC": 1.10, "VLDH": 1.10}.items():
        if best["teacher_flux_details"][reaction]["nrmse"] > seed["teacher_flux_details"][reaction]["nrmse"] * factor:
            accepted = False
            reasons.append(f"{reaction} teacher-flux guard failed")
    if accepted:
        reasons.append("candidate improved GLC while preserving EGLC, ELAC, LAC, and flux guards")
    return accepted, reasons


def _attach_dense_flux(payload: dict[str, Any], params: Mapping[str, Any]) -> None:
    flux_dense = _sim_fluxes(payload["sol"], params, payload["sol"].t)
    payload["sim_flux_time"] = np.asarray(payload["sol"].t, dtype=float)
    payload["sim_flux_dense"] = flux_dense


def run_veglc_import_feedback_fla(
    *,
    out_dir: Path,
    seed_params_path: Path,
    global_baseline_params_path: Path | None,
    n_trials: int,
    global_trials: int,
    t_max: float,
    teacher_dense_points: int,
    local_bound_scale: float,
    seed: int,
    method: str,
    rtol: float,
    atol: float,
    level_weight: float,
    endpoint_weight: float,
    slope_weight: float,
    flux_weight: float,
    guard_weight: float,
    regularization_weight: float,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    seed_params = _load_params(Path(seed_params_path))
    global_baseline_params = _load_params(Path(global_baseline_params_path)) if global_baseline_params_path else None
    exp_time, exp_curves = _extract_brodbar_targets(t_max)
    teacher_path = out_dir / "teacher_flux_dataset_veglc_import_feedback.json"
    teacher_dataset = _build_lactate_teacher_dataset(
        exp_time=exp_time,
        exp_curves=exp_curves,
        dense_points=teacher_dense_points,
        out_path=teacher_path,
    )
    x0 = np.asarray(load_initial_conditions(), dtype=float)
    objective = VeglcImportFeedbackObjective(
        x0=x0,
        seed_params=seed_params,
        fixed_family_params=FIXED_VEGLC_FAMILY,
        tracked_param_names=OPTIMIZED_PARAM_NAMES,
        exp_time=exp_time,
        exp_curves=exp_curves,
        teacher_dataset=teacher_dataset,
        method=method,
        rtol=rtol,
        atol=atol,
        level_weight=level_weight,
        endpoint_weight=endpoint_weight,
        slope_weight=slope_weight,
        flux_weight=flux_weight,
        guard_weight=guard_weight,
        regularization_weight=regularization_weight,
    )
    bounds = _local_bounds(seed_params, OPTIMIZED_PARAM_NAMES, local_bound_scale)
    print("VEGLC import feedback FLA bounds:", flush=True)
    for name, (center, lo, hi) in bounds.items():
        print(f"  {name}: {lo:.6g} .. {hi:.6g} (center={center:.6g})", flush=True)

    global_baseline = None
    if global_baseline_params is not None:
        saved_seed = objective.seed_params
        objective.seed_params = global_baseline_params
        global_baseline = objective.evaluate({}, label="global_baseline", apply_fixed_family=False, record=False)
        objective.seed_params = saved_seed

    seed_eval = objective.evaluate({}, label="seed_transport_depletion_gate", apply_fixed_family=False)
    objective.seed_guard_reference = seed_eval
    print(
        f"Seed loss={seed_eval['loss']:.4f}, GLC nRMSE={seed_eval['metrics']['GLC']['nrmse']:.4f}, "
        f"EGLC endpoint={seed_eval['metrics']['EGLC']['endpoint_error']:.4f}, "
        f"VEGLC flux={seed_eval['teacher_flux_details']['VEGLC']['nrmse']:.4f}",
        flush=True,
    )
    family_center = {name: float(bounds[name][0]) for name in OPTIMIZED_PARAM_NAMES}
    family_seed = objective.evaluate(
        family_center,
        label="import_feedback_family_neutral_seed",
        apply_fixed_family=True,
    )
    objective.best_payload = family_seed
    print(
        f"Family neutral loss={family_seed['loss']:.4f}, GLC nRMSE={family_seed['metrics']['GLC']['nrmse']:.4f}, "
        f"EGLC endpoint={family_seed['metrics']['EGLC']['endpoint_error']:.4f}, "
        f"VEGLC flux={family_seed['teacher_flux_details']['VEGLC']['nrmse']:.4f}",
        flush=True,
    )

    if HAS_OPTUNA and int(n_trials) > 0:
        sampler = optuna.samplers.TPESampler(
            seed=int(seed),
            n_startup_trials=min(8, max(3, int(n_trials) // 3)),
            multivariate=True,
        )
        study = optuna.create_study(direction="minimize", sampler=sampler)
        study.enqueue_trial(family_center)
        for strength, feedback_km, hill, cap in (
            (0.5, 2.0, 1.0, 1.0),
            (1.5, 1.0, 1.5, 0.8),
            (3.0, 0.75, 2.0, 0.55),
            (0.0, 1.0, 1.0, 0.6),
        ):
            queued = dict(family_center)
            queued["transport_gate_feedback_strength_VEGLC"] = float(strength)
            queued["transport_gate_feedback_km_GLC_VEGLC"] = float(feedback_km)
            queued["transport_gate_feedback_hill_VEGLC"] = float(hill)
            queued["transport_gate_import_cap_VEGLC"] = float(cap)
            study.enqueue_trial(queued)

        def optuna_objective(trial: Any) -> float:
            overrides = {}
            for name, (_, lo, hi) in bounds.items():
                overrides[name] = trial.suggest_float(
                    name,
                    float(lo),
                    float(hi),
                    log=should_use_log_sampling(name, float(lo), float(hi)),
                )
            loss = objective(overrides, label=f"trial_{trial.number}")
            latest = objective.trials[-1] if objective.trials else {}
            metrics = latest.get("metrics", {}) if isinstance(latest.get("metrics"), Mapping) else {}
            flux = latest.get("teacher_flux_details", {}) if isinstance(latest.get("teacher_flux_details"), Mapping) else {}
            print(
                f"trial {trial.number:03d}: loss={latest.get('loss', loss):.4f}, "
                f"GLC={metrics.get('GLC', {}).get('nrmse', float('nan')):.4f}, "
                f"EGLC_ep={metrics.get('EGLC', {}).get('endpoint_error', float('nan')):.4f}, "
                f"LAC={metrics.get('LAC', {}).get('nrmse', float('nan')):.4f}, "
                f"VEGLC_flux={flux.get('VEGLC', {}).get('nrmse', float('nan')):.4f}, "
                f"cap={float(overrides['transport_gate_import_cap_VEGLC']):.4g}, "
                f"fb={float(overrides['transport_gate_feedback_strength_VEGLC']):.4g}, "
                f"fb_km={float(overrides['transport_gate_feedback_km_GLC_VEGLC']):.4g}, "
                f"elapsed={latest.get('elapsed_sec', float('nan')):.1f}s",
                flush=True,
            )
            return float(loss)

        study.optimize(optuna_objective, n_trials=int(n_trials), show_progress_bar=False)
    else:
        grid_caps = np.linspace(0.35, 1.2, max(2, int(n_trials)))
        for i, cap in enumerate(grid_caps):
            overrides = dict(family_center)
            overrides["transport_gate_import_cap_VEGLC"] = float(cap)
            overrides["transport_gate_feedback_strength_VEGLC"] = float(min(4.0, 0.5 + i * 0.25))
            objective(overrides, label=f"grid_{i}")

    if int(global_trials) > 0 and objective.best_payload is not None:
        center = dict(objective.best_payload["params"])
        for i in range(int(global_trials)):
            scale = 1.0 + (i + 1) * 0.10
            for cap_direction in (-1.0, 1.0):
                overrides = dict(center)
                overrides["transport_gate_import_cap_VEGLC"] = float(
                    np.clip(
                        center["transport_gate_import_cap_VEGLC"] * (1.0 + cap_direction * (scale - 1.0)),
                        bounds["transport_gate_import_cap_VEGLC"][1],
                        bounds["transport_gate_import_cap_VEGLC"][2],
                    )
                )
                objective(overrides, label=f"local_refine_cap_{i}_{cap_direction:+.0f}")

    best = objective.best_payload or family_seed
    best_final = objective.evaluate(best["params"], label="best_final", apply_fixed_family=True)
    seed_params_for_flux = dict(seed_params)
    best_params = dict(seed_params)
    best_params.update(FIXED_VEGLC_FAMILY)
    best_params.update(best_final["params"])
    _attach_dense_flux(seed_eval, seed_params_for_flux)
    _attach_dense_flux(best_final, best_params)

    accepted, acceptance_reasons = _acceptance(seed_eval, best_final)
    candidate_params = dict(seed_params)
    candidate_params.update(FIXED_VEGLC_FAMILY)
    candidate_params.update(best_final["params"])
    promoted_or_seed_params = candidate_params if accepted else dict(seed_params)

    (out_dir / "seed_params.json").write_text(json.dumps(_jsonable(seed_params), indent=2), encoding="utf-8")
    (out_dir / "candidate_params.json").write_text(json.dumps(_jsonable(candidate_params), indent=2), encoding="utf-8")
    (out_dir / "promoted_or_seed_params.json").write_text(
        json.dumps(_jsonable(promoted_or_seed_params), indent=2),
        encoding="utf-8",
    )
    if accepted:
        (out_dir / "best_params.json").write_text(json.dumps(_jsonable(candidate_params), indent=2), encoding="utf-8")

    trials_csv = out_dir / "optimization_trials.csv"
    pd.DataFrame(_flatten_trial_rows(objective.trials)).to_csv(trials_csv, index=False)
    metrics_csv = out_dir / "veglc_import_feedback_metrics.csv"
    metric_rows = _metrics_table(seed=seed_eval, best=best_final, global_baseline=global_baseline, out_path=metrics_csv)
    trajectory_csv = out_dir / "best_trajectory_veglc_import_feedback.csv"
    _write_trajectory(best=best_final, seed=seed_eval, exp_time=exp_time, exp_curves=exp_curves, out_path=trajectory_csv)
    plot_path = out_dir / "veglc_import_feedback_fla.png"
    _plot_result(seed=seed_eval, best=best_final, global_baseline=global_baseline, objective=objective, out_path=plot_path)

    summary = {
        "contract_type": "veglc_import_feedback_fla_result",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "out_dir": str(out_dir),
        "seed_params_path": str(seed_params_path),
        "global_baseline_params_path": str(global_baseline_params_path) if global_baseline_params_path else None,
        "teacher_dataset_path": str(teacher_path),
        "fixed_family_params": dict(FIXED_VEGLC_FAMILY),
        "optimized_params": list(OPTIMIZED_PARAM_NAMES),
        "targets": list(TARGETS),
        "flux_targets": list(FLUX_TARGETS),
        "t_max": float(t_max),
        "n_trials": int(n_trials),
        "global_trials": int(global_trials),
        "method": method,
        "rtol": float(rtol),
        "atol": float(atol),
        "local_bound_scale": float(local_bound_scale),
        "loss_weights": {
            "level_weight": float(level_weight),
            "endpoint_weight": float(endpoint_weight),
            "slope_weight": float(slope_weight),
            "flux_weight": float(flux_weight),
            "guard_weight": float(guard_weight),
            "regularization_weight": float(regularization_weight),
        },
        "global_baseline": (
            {k: v for k, v in global_baseline.items() if k not in {"sol", "sim_exp", "sim_flux"}}
            if global_baseline is not None
            else None
        ),
        "seed": {k: v for k, v in seed_eval.items() if k not in {"sol", "sim_exp", "sim_flux", "sim_flux_time", "sim_flux_dense"}},
        "family_neutral_seed": {
            k: v
            for k, v in family_seed.items()
            if k not in {"sol", "sim_exp", "sim_flux", "sim_flux_time", "sim_flux_dense"}
        },
        "best_candidate": {
            k: v
            for k, v in best_final.items()
            if k not in {"sol", "sim_exp", "sim_flux", "sim_flux_time", "sim_flux_dense"}
        },
        "metric_rows": metric_rows,
        "accepted": bool(accepted),
        "acceptance_reasons": acceptance_reasons,
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "teacher_dataset": str(teacher_path),
            "seed_params": str(out_dir / "seed_params.json"),
            "candidate_params": str(out_dir / "candidate_params.json"),
            "promoted_or_seed_params": str(out_dir / "promoted_or_seed_params.json"),
            "best_params": str(out_dir / "best_params.json") if accepted else None,
            "trials_csv": str(trials_csv),
            "metrics_csv": str(metrics_csv),
            "trajectory_csv": str(trajectory_csv),
            "plot": str(plot_path),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(_jsonable(summary), indent=2), encoding="utf-8")
    print(json.dumps(_jsonable(summary), indent=2), flush=True)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run controlled Brodbar VEGLC import-cap/feedback FLA")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--seed-params", type=Path, default=DEFAULT_SEED_PARAMS)
    parser.add_argument("--global-baseline-params", type=Path, default=DEFAULT_GLOBAL_BASELINE_PARAMS)
    parser.add_argument("--n-trials", type=int, default=28)
    parser.add_argument("--global-trials", type=int, default=4)
    parser.add_argument("--t-max", type=float, default=46.0)
    parser.add_argument("--teacher-dense-points", type=int, default=96)
    parser.add_argument("--local-bound-scale", type=float, default=3.0)
    parser.add_argument("--seed", type=int, default=628)
    parser.add_argument("--method", default="LSODA")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    parser.add_argument("--level-weight", type=float, default=1.2)
    parser.add_argument("--endpoint-weight", type=float, default=3.5)
    parser.add_argument("--slope-weight", type=float, default=2.5)
    parser.add_argument("--flux-weight", type=float, default=3.5)
    parser.add_argument("--guard-weight", type=float, default=8.0)
    parser.add_argument("--regularization-weight", type=float, default=0.20)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    run_veglc_import_feedback_fla(
        out_dir=args.out_dir,
        seed_params_path=args.seed_params,
        global_baseline_params_path=args.global_baseline_params,
        n_trials=args.n_trials,
        global_trials=args.global_trials,
        t_max=args.t_max,
        teacher_dense_points=args.teacher_dense_points,
        local_bound_scale=args.local_bound_scale,
        seed=args.seed,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
        level_weight=args.level_weight,
        endpoint_weight=args.endpoint_weight,
        slope_weight=args.slope_weight,
        flux_weight=args.flux_weight,
        guard_weight=args.guard_weight,
        regularization_weight=args.regularization_weight,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
