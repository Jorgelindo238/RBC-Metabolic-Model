"""Coupled Brodbar FLA pass for the competing PEP outlets.

This pass keeps the mild VEGLC feedback and the VHK/km_ATP_HK hypothesis
fixed. It moves ``vmax_VPEP_PASE`` only downward and ``vmax_VPK`` only upward,
with hard trajectory guards on PEP and G6P before full-panel review.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
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
DEFAULT_OUT_DIR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "vpep_pase_vpk_coupled_mild_feedback_46d_n24"
)

for path in (str(ROOT), str(SRC_DIR), str(Path(__file__).resolve().parent)):
    if path not in sys.path:
        sys.path.insert(0, path)

from MM_calibration import EXP_TO_MODEL, load_experimental_data, load_initial_conditions, should_use_log_sampling  # noqa: E402
from run_lactate_focused_fla import HAS_OPTUNA, _build_lactate_teacher_dataset, _flatten_trial_rows, _jsonable, _load_params, _nrmse, optuna  # noqa: E402
from run_vpep_pase_downward_fla import (  # noqa: E402
    CONCENTRATION_TARGETS,
    OPTIMIZED_PARAM,
    VpepPaseObjective,
    _clean_payload,
    _extract_targets,
    _fixed_mild_feedback,
    _focused_acceptance,
    _plot_result,
)


VPEP_PARAM = OPTIMIZED_PARAM
VPK_PARAM = "vmax_VPK"
TRACKED_PARAMS = (VPEP_PARAM, VPK_PARAM)


def _directional_bounds(
    seed_params: Mapping[str, Any],
    *,
    vpep_lower_ratio: float,
    vpep_upper_ratio: float,
    vpk_lower_ratio: float,
    vpk_upper_multiplier: float,
    vpk_global_upper: float = 50.0,
) -> dict[str, tuple[float, float, float]]:
    vpep_seed = float(seed_params[VPEP_PARAM])
    vpk_seed = float(seed_params[VPK_PARAM])
    if not 0.0 < vpep_lower_ratio < vpep_upper_ratio < 1.0:
        raise ValueError("VPEP_PASE ratios must satisfy 0 < lower < upper < 1")
    if not 1.0 < vpk_lower_ratio < vpk_upper_multiplier:
        raise ValueError("VPK ratios must satisfy 1 < lower < upper")
    vpep_lo = vpep_seed * float(vpep_lower_ratio)
    vpep_hi = vpep_seed * float(vpep_upper_ratio)
    vpk_lo = vpk_seed * float(vpk_lower_ratio)
    vpk_hi = min(float(vpk_global_upper), vpk_seed * float(vpk_upper_multiplier))
    if not vpk_lo < vpk_hi:
        raise ValueError("VPK bounds are empty after applying the global upper bound")
    return {
        VPEP_PARAM: (vpep_seed, vpep_lo, vpep_hi),
        VPK_PARAM: (vpk_seed, vpk_lo, vpk_hi),
    }


def _extract_g6p_curve(t_max: float) -> tuple[np.ndarray, np.ndarray]:
    time_exp, exp_values, name_to_row = load_experimental_data()
    if "G6P" not in name_to_row:
        raise KeyError("Brodbar experimental target 'G6P' is missing")
    mask = (time_exp >= 1.0 - 1e-9) & (time_exp <= float(t_max) + 1e-9)
    return (
        np.asarray(time_exp[mask], dtype=float),
        np.asarray(exp_values[name_to_row["G6P"], mask], dtype=float),
    )


class CoupledPepOutletObjective(VpepPaseObjective):
    def __init__(
        self,
        *,
        g6p_exp: np.ndarray,
        g6p_weight: float,
        energy_log_weight: float,
        **kwargs: Any,
    ) -> None:
        super().__init__(tracked_param_names=TRACKED_PARAMS, **kwargs)
        self.g6p_exp = np.asarray(g6p_exp, dtype=float)
        self.g6p_weight = float(g6p_weight)
        self.energy_log_weight = float(energy_log_weight)

    def evaluate(
        self,
        overrides: Mapping[str, Any],
        *,
        label: str,
        apply_feedback: bool = True,
        record: bool = True,
    ) -> dict[str, Any]:
        prior_best = self.best_payload
        self.best_payload = None
        payload = super().evaluate(
            overrides,
            label=label,
            apply_feedback=apply_feedback,
            record=False,
        )
        self.best_payload = prior_best
        if not math.isfinite(float(payload.get("loss", float("inf")))):
            if record:
                self.trials.append(payload)
            return payload

        g6p_sim = np.interp(self.exp_time, payload["sol"].t, payload["sol"].y[EXP_TO_MODEL["G6P"]])
        g6p_metric = _nrmse(g6p_sim, self.g6p_exp)
        payload["metrics"]["G6P"] = g6p_metric
        payload["sim_final"]["G6P"] = float(g6p_sim[-1])
        payload["exp_final"]["G6P"] = float(self.g6p_exp[-1])
        g6p_loss = float(g6p_metric["nrmse"] / 10.0)

        atp_final = max(float(payload["sim_final"]["ATP"]), 1e-9)
        atp_exp_final = max(float(payload["exp_final"]["ATP"]), 1e-9)
        atp_log_endpoint_error = abs(math.log10(atp_final / atp_exp_final))

        extra_guard_loss = 0.0
        if self.mild_reference is not None and "G6P" in self.mild_reference.get("metrics", {}):
            g6p_limit = self.mild_reference["metrics"]["G6P"]["nrmse"] * 1.02
            extra_guard_loss += 30.0 * max(0.0, g6p_metric["nrmse"] - g6p_limit) ** 2

        payload["g6p_loss"] = g6p_loss
        payload["ATP_log_endpoint_error"] = float(atp_log_endpoint_error)
        payload["guard_loss"] = float(payload["guard_loss"] + extra_guard_loss)
        payload["loss"] = float(
            payload["loss"]
            + self.g6p_weight * g6p_loss
            + self.energy_log_weight * atp_log_endpoint_error
            + self.guard_weight * extra_guard_loss
        )

        if record:
            self.trials.append(
                {k: v for k, v in payload.items() if k not in {"sol", "sim_exp", "sim_flux", "native_flux"}}
            )
        if apply_feedback and (prior_best is None or payload["loss"] < prior_best["loss"]):
            self.best_payload = payload
        return payload


def _coupled_acceptance(
    neutral: Mapping[str, Any],
    mild: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    vpk_seed: float,
) -> tuple[bool, list[str]]:
    base_accepted, base_reasons = _focused_acceptance(neutral, mild, candidate)
    success_text = "focused candidate passed concentration, energy-routing, and teacher-flux guards"
    reasons = [reason for reason in base_reasons if reason != success_text]
    accepted = bool(base_accepted)
    if candidate["metrics"]["G6P"]["nrmse"] > mild["metrics"]["G6P"]["nrmse"] * 1.02:
        accepted = False
        reasons.append("G6P trajectory guard failed")
    if float(candidate[VPK_PARAM]) < float(vpk_seed) * 1.05:
        accepted = False
        reasons.append("VPK capacity did not increase by at least 5%")
    if accepted:
        reasons.append("coupled candidate passed PEP, G6P, energy, extracellular, and teacher-flux guards")
    return accepted, reasons


def _write_guardrail_metrics(
    neutral: Mapping[str, Any],
    mild: Mapping[str, Any],
    candidate: Mapping[str, Any],
    out_path: Path,
) -> None:
    rows = []
    for name in (*CONCENTRATION_TARGETS, "G6P"):
        rows.append(
            {
                "metabolite": name,
                "neutral_nrmse": neutral["metrics"][name]["nrmse"],
                "mild_seed_nrmse": mild["metrics"][name]["nrmse"],
                "candidate_nrmse": candidate["metrics"][name]["nrmse"],
                "delta_vs_mild_nrmse": candidate["metrics"][name]["nrmse"]
                - mild["metrics"][name]["nrmse"],
                "experimental_final": candidate["exp_final"][name],
                "mild_seed_final": mild["sim_final"][name],
                "candidate_final": candidate["sim_final"][name],
            }
        )
    pd.DataFrame(rows).to_csv(out_path, index=False)


def _plot_coupled_diagnostics(
    objective: CoupledPepOutletObjective,
    mild: Mapping[str, Any],
    candidate: Mapping[str, Any],
    trial_rows: Sequence[Mapping[str, Any]],
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(15, 9), constrained_layout=True)
    for ax, name in zip(axes[0], ("G6P", "PEP", "ATP")):
        idx = EXP_TO_MODEL[name]
        exp_values = objective.g6p_exp if name == "G6P" else objective.exp_curves[name]
        ax.plot(mild["sol"].t, mild["sol"].y[idx], color="#64748b", linewidth=2.0, label="mild seed")
        ax.plot(candidate["sol"].t, candidate["sol"].y[idx], color="#2563eb", linewidth=2.4, label="candidate")
        ax.scatter(objective.exp_time, exp_values, color="#111827", s=22, label="Brodbar")
        ax.set_title(f"{name}: {mild['metrics'][name]['nrmse']:.2f} -> {candidate['metrics'][name]['nrmse']:.2f}")
        ax.set_xlabel("Time (days)")
        ax.set_ylabel("mM")
        ax.grid(True, alpha=0.25)

    frame = pd.DataFrame(trial_rows)
    valid = frame[np.isfinite(pd.to_numeric(frame.get("loss"), errors="coerce"))].copy()
    ax = axes[1, 0]
    scatter = ax.scatter(
        valid[VPEP_PARAM],
        valid[VPK_PARAM],
        c=valid["loss"],
        cmap="viridis_r",
        s=55,
        edgecolors="white",
        linewidths=0.5,
    )
    ax.scatter(candidate[VPEP_PARAM], candidate[VPK_PARAM], marker="*", s=220, color="#dc2626", label="best")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(VPEP_PARAM)
    ax.set_ylabel(VPK_PARAM)
    ax.set_title("Directional search")
    ax.legend(frameon=False)
    fig.colorbar(scatter, ax=ax, label="Focused loss")

    ax = axes[1, 1]
    labels = ["mild seed", "candidate"]
    vpk_share = [mild["routing_metrics"]["PEP_to_VPK_share"], candidate["routing_metrics"]["PEP_to_VPK_share"]]
    bypass_share = [1.0 - value for value in vpk_share]
    ax.bar(labels, vpk_share, color="#16a34a", label="VPK")
    ax.bar(labels, bypass_share, bottom=vpk_share, color="#dc2626", label="VPEP_PASE")
    ax.set_ylim(0.0, 1.0)
    ax.set_title("Direct PEP routing")
    ax.set_ylabel("Route share")
    ax.legend(frameon=False)

    ax = axes[1, 2]
    names = ["GLC", "G6P", "F6P", "PEP", "ATP", "LAC"]
    deltas = [candidate["metrics"][name]["nrmse"] - mild["metrics"][name]["nrmse"] for name in names]
    colors = ["#16a34a" if value <= 0.0 else "#dc2626" for value in deltas]
    ax.barh(names, deltas, color=colors)
    ax.axvline(0.0, color="#111827", linewidth=1.0)
    ax.set_title("Candidate minus mild seed")
    ax.set_xlabel("Delta nRMSE")
    ax.grid(True, axis="x", alpha=0.25)

    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False)
    fig.suptitle("Coupled PEP outlet FLA: VPEP_PASE down, VPK up", y=0.998)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def run_coupled_fla(
    *,
    out_dir: Path,
    seed_params_path: Path,
    n_trials: int,
    t_max: float,
    teacher_dense_points: int,
    random_seed: int,
    method: str,
    rtol: float,
    atol: float,
    vpep_lower_ratio: float,
    vpep_upper_ratio: float,
    vpk_lower_ratio: float,
    vpk_upper_multiplier: float,
    feedback_strength: float,
    feedback_km: float,
    feedback_hill: float,
    feedback_cap: float,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base_seed_params = _load_params(Path(seed_params_path))
    fixed_feedback = _fixed_mild_feedback(
        strength=feedback_strength,
        km_glc=feedback_km,
        hill=feedback_hill,
        import_cap=feedback_cap,
    )
    bounds = _directional_bounds(
        base_seed_params,
        vpep_lower_ratio=vpep_lower_ratio,
        vpep_upper_ratio=vpep_upper_ratio,
        vpk_lower_ratio=vpk_lower_ratio,
        vpk_upper_multiplier=vpk_upper_multiplier,
    )
    exp_time, exp_curves = _extract_targets(t_max)
    g6p_time, g6p_exp = _extract_g6p_curve(t_max)
    if not np.array_equal(exp_time, g6p_time):
        raise ValueError("G6P and focused Brodbar targets do not share a time grid")
    teacher_path = out_dir / "teacher_flux_dataset_vpep_vpk.json"
    teacher_dataset = _build_lactate_teacher_dataset(
        exp_time=exp_time,
        exp_curves=exp_curves,
        dense_points=teacher_dense_points,
        out_path=teacher_path,
    )
    objective = CoupledPepOutletObjective(
        x0=np.asarray(load_initial_conditions(), dtype=float),
        base_seed_params=base_seed_params,
        fixed_feedback_params=fixed_feedback,
        exp_time=exp_time,
        exp_curves=exp_curves,
        teacher_dataset=teacher_dataset,
        method=method,
        rtol=rtol,
        atol=atol,
        level_weight=1.5,
        endpoint_weight=3.5,
        slope_weight=2.0,
        flux_weight=3.0,
        routing_weight=2.5,
        guard_weight=12.0,
        regularization_weight=0.03,
        g6p_exp=g6p_exp,
        g6p_weight=2.0,
        energy_log_weight=0.75,
    )

    centers = {name: values[0] for name, values in bounds.items()}
    for name, (center, lo, hi) in bounds.items():
        print(f"{name}: {lo:.6g} .. {hi:.6g} (seed={center:.6g})", flush=True)
    neutral = objective.evaluate(centers, label="neutral_vhk_atp_seed", apply_feedback=False)
    mild = objective.evaluate(centers, label="fixed_mild_feedback_seed", apply_feedback=True)
    objective.neutral_reference = neutral
    objective.mild_reference = mild
    objective.best_payload = mild
    print(
        f"Mild seed: loss={mild['loss']:.4f}, GLC={mild['metrics']['GLC']['nrmse']:.3f}, "
        f"G6P={mild['metrics']['G6P']['nrmse']:.3f}, PEP={mild['metrics']['PEP']['nrmse']:.3f}, "
        f"ATP={mild['sim_final']['ATP']:.6g}, VPK_share={mild['routing_metrics']['PEP_to_VPK_share']:.3f}",
        flush=True,
    )

    if HAS_OPTUNA and int(n_trials) > 0:
        sampler = optuna.samplers.TPESampler(
            seed=int(random_seed),
            n_startup_trials=min(8, max(4, int(n_trials) // 3)),
            multivariate=True,
        )
        study = optuna.create_study(direction="minimize", sampler=sampler)
        vpep_seed, _, _ = bounds[VPEP_PARAM]
        vpk_seed, _, _ = bounds[VPK_PARAM]
        anchors = (
            (0.85, 1.5),
            (0.50, 2.0),
            (0.25, 4.0),
            (0.10, 8.0),
            (0.17, 6.0),
            (0.35, 5.0),
        )
        for vpep_ratio, vpk_multiplier in anchors:
            study.enqueue_trial(
                {
                    VPEP_PARAM: float(np.clip(vpep_seed * vpep_ratio, bounds[VPEP_PARAM][1], bounds[VPEP_PARAM][2])),
                    VPK_PARAM: float(np.clip(vpk_seed * vpk_multiplier, bounds[VPK_PARAM][1], bounds[VPK_PARAM][2])),
                }
            )

        def optuna_objective(trial: Any) -> float:
            overrides = {
                name: trial.suggest_float(
                    name,
                    lo,
                    hi,
                    log=should_use_log_sampling(name, lo, hi),
                )
                for name, (_, lo, hi) in bounds.items()
            }
            latest = objective.evaluate(overrides, label=f"trial_{trial.number}")
            loss = float(latest["loss"])
            print(
                f"trial {trial.number:03d}: loss={loss:.4f}, VPEP={overrides[VPEP_PARAM]:.5g}, "
                f"VPK={overrides[VPK_PARAM]:.5g}, GLC={latest['metrics']['GLC']['nrmse']:.3f}, "
                f"G6P={latest['metrics']['G6P']['nrmse']:.3f}, PEP={latest['metrics']['PEP']['nrmse']:.3f}, "
                f"ATP={latest['sim_final']['ATP']:.6g}, VPK_share={latest['routing_metrics']['PEP_to_VPK_share']:.3f}",
                flush=True,
            )
            return float(loss)

        study.optimize(optuna_objective, n_trials=int(n_trials), show_progress_bar=False)
    else:
        for i, ratio in enumerate(np.linspace(0.1, 0.9, max(2, abs(int(n_trials))))):
            overrides = {
                VPEP_PARAM: float(np.clip(centers[VPEP_PARAM] * ratio, bounds[VPEP_PARAM][1], bounds[VPEP_PARAM][2])),
                VPK_PARAM: float(np.clip(centers[VPK_PARAM] / ratio, bounds[VPK_PARAM][1], bounds[VPK_PARAM][2])),
            }
            objective.evaluate(overrides, label=f"grid_{i}")

    best = objective.best_payload or mild
    candidate = objective.evaluate(best["params"], label="best_final")
    focused_accepted, reasons = _coupled_acceptance(
        neutral,
        mild,
        candidate,
        vpk_seed=centers[VPK_PARAM],
    )
    neutral_params = objective.build_params(centers, apply_feedback=False)
    mild_params = objective.build_params(centers, apply_feedback=True)
    candidate_params = objective.build_params(candidate["params"], apply_feedback=True)
    for filename, params in (
        ("neutral_seed_params.json", neutral_params),
        ("seed_fixed_params.json", mild_params),
        ("candidate_params.json", candidate_params),
    ):
        (out_dir / filename).write_text(json.dumps(_jsonable(params), indent=2), encoding="utf-8")

    trials_path = out_dir / "optimization_trials.csv"
    metrics_path = out_dir / "coupled_guardrail_metrics.csv"
    main_plot_path = out_dir / "coupled_vpep_vpk_fla.png"
    diagnostic_plot_path = out_dir / "coupled_guardrail_diagnostics.png"
    pd.DataFrame(_flatten_trial_rows(objective.trials)).to_csv(trials_path, index=False)
    _write_guardrail_metrics(neutral, mild, candidate, metrics_path)
    _plot_result(objective, neutral, mild, candidate, main_plot_path)
    _plot_coupled_diagnostics(objective, mild, candidate, objective.trials, diagnostic_plot_path)

    summary = {
        "contract_type": "coupled_vpep_pase_vpk_fla_result",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "out_dir": str(out_dir),
        "seed_params_path": str(seed_params_path),
        "fixed_feedback_params": fixed_feedback,
        "optimized_params": list(TRACKED_PARAMS),
        "search_directions": {VPEP_PARAM: "decrease_only", VPK_PARAM: "increase_only"},
        "bounds": {
            name: {"seed": center, "lower": lo, "upper": hi}
            for name, (center, lo, hi) in bounds.items()
        },
        "t_max": float(t_max),
        "n_trials": int(n_trials),
        "neutral_seed": _clean_payload(neutral),
        "fixed_mild_feedback_seed": _clean_payload(mild),
        "best_candidate": _clean_payload(candidate),
        "focused_accepted": bool(focused_accepted),
        "acceptance_reasons": reasons,
        "parameters_promoted": False,
        "global_best_overwritten": False,
        "requires_full_panel_replay": True,
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "candidate_params": str(out_dir / "candidate_params.json"),
            "seed_fixed_params": str(out_dir / "seed_fixed_params.json"),
            "trials_csv": str(trials_path),
            "metrics_csv": str(metrics_path),
            "main_plot": str(main_plot_path),
            "diagnostic_plot": str(diagnostic_plot_path),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(_jsonable(summary), indent=2), encoding="utf-8")
    print(json.dumps(_jsonable(summary), indent=2), flush=True)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run coupled decrease-VPEP_PASE/increase-VPK Brodbar FLA")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--seed-params", type=Path, default=DEFAULT_SEED_PARAMS)
    parser.add_argument("--n-trials", type=int, default=24)
    parser.add_argument("--t-max", type=float, default=46.0)
    parser.add_argument("--teacher-dense-points", type=int, default=96)
    parser.add_argument("--random-seed", type=int, default=805)
    parser.add_argument("--method", default="LSODA")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    parser.add_argument("--vpep-lower-ratio", type=float, default=0.05)
    parser.add_argument("--vpep-upper-ratio", type=float, default=0.999)
    parser.add_argument("--vpk-lower-ratio", type=float, default=1.001)
    parser.add_argument("--vpk-upper-multiplier", type=float, default=10.0)
    parser.add_argument("--feedback-strength", type=float, default=0.10)
    parser.add_argument("--feedback-km", type=float, default=8.54922196746391)
    parser.add_argument("--feedback-hill", type=float, default=0.6928279794535482)
    parser.add_argument("--feedback-cap", type=float, default=5.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_coupled_fla(
        out_dir=args.out_dir,
        seed_params_path=args.seed_params,
        n_trials=args.n_trials,
        t_max=args.t_max,
        teacher_dense_points=args.teacher_dense_points,
        random_seed=args.random_seed,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
        vpep_lower_ratio=args.vpep_lower_ratio,
        vpep_upper_ratio=args.vpep_upper_ratio,
        vpk_lower_ratio=args.vpk_lower_ratio,
        vpk_upper_multiplier=args.vpk_upper_multiplier,
        feedback_strength=args.feedback_strength,
        feedback_km=args.feedback_km,
        feedback_hill=args.feedback_hill,
        feedback_cap=args.feedback_cap,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
