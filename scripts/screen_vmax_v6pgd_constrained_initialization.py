"""Narrow fixed V6PGD screen coupled to constrained PPP initialization."""

from __future__ import annotations

import argparse
import json
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
SCRIPT_DIR = ROOT / "scripts"
DEFAULT_SEED_PARAMS = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "vpep_vpk_coupled_mild_feedback_46d_n20"
    / "seed_fixed_params.json"
)
DEFAULT_OUT_DIR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "v6pgd_constrained_initialization_screen_J1_J2"
)

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from MM_calibration import load_initial_conditions  # noqa: E402
from profile_atp_consumption_sinks import _all_experimental_curves  # noqa: E402
from profile_glycolysis_flux_bottlenecks import (  # noqa: E402
    _jsonable,
    _load_params,
    _simulate_and_track,
)
from run_glucose_utilization_fla import _nrmse  # noqa: E402
from audit_complete_ppp_fla import (  # noqa: E402
    CONTEXT_POOLS,
    LATENT_PPP_POOLS,
    MEASURED_PPP_POOLS,
    PPP_POOLS,
    _build_net_flux_teachers,
    _build_timeseries,
    _net_teacher_metric,
)
from diagnose_ppp_initial_conditions import (  # noqa: E402
    _historical_latent_ppp_state,
    _historical_values,
)
from diagnose_constrained_ppp_initialization import (  # noqa: E402
    CONSTRAINED_CASES,
    LATENT_INDICES,
    NADPH_INDEX,
    NADP_INDEX,
    _case_metrics,
    _go6p_fixed_kinetic_feasibility,
    _reference_scales,
    _solve_mode,
    _window_teacher,
)


SEED_VMAX_V6PGD = 10.0
SCREEN_SCALES = (0.97, 0.9532, 0.93, 0.91, 0.90)
GO6P_BOUNDARY_VMAX = 9.5316549
EARLY_IMPROVEMENT_FLOOR = 0.05
G6P_NONINFERIORITY_TOLERANCE = 0.02
LATENT_RESIDUAL_REDUCTION_FLOOR = 0.01
LONG_GUARD_POOLS = ("ATP", "PEP", "GLC", "LAC", "EGLC", "ELAC")


def _candidate_params(
    seed_params: Mapping[str, Any], scale: float
) -> tuple[dict[str, Any], list[str]]:
    params = dict(seed_params)
    params["vmax_V6PGD"] = SEED_VMAX_V6PGD * float(scale)
    changed = sorted(
        key
        for key in set(seed_params) | set(params)
        if seed_params.get(key) != params.get(key)
    )
    if changed != ["vmax_V6PGD"]:
        raise RuntimeError(f"Narrow V6PGD contract failed: changed={changed}")
    return params, changed


def _candidate_label(mode: str, scale: float) -> str:
    return f"{mode}__v6pgd_{scale:.4f}x"


def _normalized_latent_residual(
    diagnostics: Mapping[str, Any], latent_scales: np.ndarray
) -> float:
    values = np.asarray(
        [diagnostics["latent_derivatives"][pool] for pool in LATENT_PPP_POOLS],
        dtype=float,
    )
    scaled = values / np.asarray(latent_scales, dtype=float)
    return float(np.sqrt(np.mean(scaled**2)))


def _augment_metrics(
    *,
    metrics: Mapping[str, Any],
    frame: pd.DataFrame,
    closure: Mapping[str, float],
    diagnostics: Mapping[str, Any],
    latent_scales: np.ndarray,
) -> dict[str, Any]:
    row = dict(metrics)
    row["PPP_minimum"] = float(frame[list(PPP_POOLS)].min().min())
    row["latent_PPP_minimum"] = float(frame[list(LATENT_PPP_POOLS)].min().min())
    row["max_pointwise_closure_error"] = float(max(closure.values()))
    row["latent_residual_nRMS"] = _normalized_latent_residual(
        diagnostics, latent_scales
    )
    row["GL6P_initial"] = float(frame["GL6P"].iloc[0])
    row["solver_cost"] = float(diagnostics["cost"])
    row["solver_success"] = bool(diagnostics["success"])
    return row


def _relative_improvement(candidate: float, baseline: float) -> float:
    return 1.0 - float(candidate) / max(float(baseline), 1e-30)


def _assess_candidate(
    *,
    row: Mapping[str, Any],
    baseline: Mapping[str, Any],
    feasibility: Mapping[str, Any],
    bounded_gl6p_max: float,
    closure_tolerance: float,
) -> dict[str, Any]:
    improvements: dict[str, float] = {}
    for pool in ("GO6P", "F6P"):
        for metric in ("concentration_nrmse", "teacher_nrmse"):
            key = f"{pool}_{metric}"
            improvements[key] = _relative_improvement(row[key], baseline[key])
    latent_reduction = _relative_improvement(
        row["latent_residual_nRMS"], baseline["latent_residual_nRMS"]
    )
    g6p_ratios = {
        "concentration_nrmse_ratio": float(row["G6P_concentration_nrmse"])
        / max(float(baseline["G6P_concentration_nrmse"]), 1e-30),
        "teacher_nrmse_ratio": float(row["G6P_teacher_nrmse"])
        / max(float(baseline["G6P_teacher_nrmse"]), 1e-30),
    }
    gl6p_interior = bool(
        float(row["GL6P_initial"]) < float(bounded_gl6p_max) * (1.0 - 1e-6)
    )
    gates = {
        "go6p_f6p_each_metric_improves_5pct": all(
            value >= EARLY_IMPROVEMENT_FLOOR for value in improvements.values()
        ),
        "latent_residual_reduces_1pct": latent_reduction
        >= LATENT_RESIDUAL_REDUCTION_FLOOR,
        "g6p_noninferior_within_2pct": all(
            value <= 1.0 + G6P_NONINFERIORITY_TOLERANCE
            for value in g6p_ratios.values()
        ),
        "bounded_go6p_teacher_feasible": bool(feasibility["bounded_feasible"]),
        "finite_interior_gl6p_solution": gl6p_interior,
        "solver_success": bool(row["solver_success"]),
        "ppp_positive": float(row["PPP_minimum"]) >= -1e-10,
        "redox_valid": bool(row["redox_valid"]),
        "exact_ten_pool_closure": float(row["max_pointwise_closure_error"])
        <= float(closure_tolerance),
    }
    return {
        "candidate": str(row["candidate"]),
        "mode": str(row["mode"]),
        "scale": float(row["scale"]),
        "vmax_V6PGD": float(row["vmax_V6PGD"]),
        "relative_improvements": improvements,
        "latent_residual_relative_reduction": latent_reduction,
        "g6p_noninferiority_ratios": g6p_ratios,
        "gates": gates,
        "fully_guarded_early_pass": bool(all(gates.values())),
    }


def _select_candidate(
    assessments: Sequence[Mapping[str, Any]], metrics: Sequence[Mapping[str, Any]]
) -> str | None:
    eligible = {
        str(row["candidate"])
        for row in assessments
        if bool(row["fully_guarded_early_pass"])
    }
    if not eligible:
        return None
    rows = [row for row in metrics if str(row["candidate"]) in eligible]
    return str(
        min(
            rows,
            key=lambda row: sum(
                float(row[f"{pool}_{metric}"])
                for pool in ("GO6P", "F6P")
                for metric in ("concentration_nrmse", "teacher_nrmse")
            ),
        )["candidate"]
    )


def _long_replay_metrics(
    *,
    label: str,
    frame: pd.DataFrame,
    experimental_time: np.ndarray,
    experimental_curves: Mapping[str, np.ndarray],
    teachers: Mapping[str, Any],
) -> dict[str, Any]:
    time = frame["time_day"].to_numpy(dtype=float)
    row: dict[str, Any] = {
        "candidate": label,
        "PPP_minimum": float(frame[list(PPP_POOLS)].min().min()),
        "NADP_minimum": float(frame["NADP"].min()),
        "NADPH_minimum": float(frame["NADPH"].min()),
        "NADP_NADPH_max_drift": float(
            np.max(
                np.abs(
                    frame["NADP"].to_numpy(dtype=float)
                    + frame["NADPH"].to_numpy(dtype=float)
                    - float(frame["NADP"].iloc[0] + frame["NADPH"].iloc[0])
                )
            )
        ),
    }
    for pool in LONG_GUARD_POOLS:
        simulated = np.interp(
            experimental_time,
            time,
            frame[pool].to_numpy(dtype=float),
        )
        metric = _nrmse(simulated, np.asarray(experimental_curves[pool], dtype=float))
        row[f"{pool}_nrmse"] = float(metric["nrmse"])
        row[f"{pool}_endpoint_error"] = float(metric["endpoint_error"])
    teacher_time = np.asarray(teachers["dense_timepoints"], dtype=float)
    for pool in MEASURED_PPP_POOLS:
        simulated = np.interp(
            experimental_time,
            time,
            frame[pool].to_numpy(dtype=float),
        )
        concentration = _nrmse(
            simulated, np.asarray(experimental_curves[pool], dtype=float)
        )
        model_flux = np.interp(
            teacher_time,
            time,
            frame[f"d{pool}_dt_effective_flux"].to_numpy(dtype=float),
        )
        teacher_flux = np.asarray(
            teachers["curves"][pool]["dense_net_flux"], dtype=float
        )
        flux = _net_teacher_metric(model_flux, teacher_flux)
        row[f"{pool}_concentration_nrmse"] = float(concentration["nrmse"])
        row[f"{pool}_teacher_nrmse"] = float(flux["nrmse"])
        row[f"{pool}_teacher_sign_agreement"] = float(flux["sign_agreement"])
    row["GO6P_F6P_joint_score"] = float(
        sum(
            row[f"{pool}_{metric}"]
            for pool in ("GO6P", "F6P")
            for metric in ("concentration_nrmse", "teacher_nrmse")
        )
    )
    return row


def _plot_early(
    *,
    frames: Mapping[str, pd.DataFrame],
    teachers: Mapping[str, Any],
    assessments: Sequence[Mapping[str, Any]],
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.5), constrained_layout=True)
    cmap = plt.get_cmap("viridis")
    labels = list(frames)
    for column, pool in enumerate(("GO6P", "F6P")):
        teacher_time, teacher_concentration, teacher_flux = _window_teacher(
            teachers, pool
        )
        for index, label in enumerate(labels):
            frame = frames[label]
            color = cmap(index / max(len(labels) - 1, 1))
            axes[0, column].plot(
                frame["time_day"], frame[pool], color=color, linewidth=1.25, alpha=0.8
            )
            axes[1, column].plot(
                frame["time_day"],
                frame[f"d{pool}_dt_effective_flux"],
                color=color,
                linewidth=1.25,
                alpha=0.8,
            )
        axes[0, column].plot(
            teacher_time, teacher_concentration, "k--", linewidth=2.2
        )
        axes[1, column].plot(teacher_time, teacher_flux, "k--", linewidth=2.2)
        axes[0, column].set_title(f"{pool} concentration")
        axes[1, column].set_title(f"{pool} net flux teacher")
        axes[1, column].set_xlabel("Time (day)")
        axes[0, column].set_ylabel("mM")
        axes[1, column].set_ylabel("mM/day")
    assessment_frame = pd.DataFrame(
        {
            "scale": [row["scale"] for row in assessments],
            "latent": [row["latent_residual_relative_reduction"] for row in assessments],
            "minimum_teacher": [
                min(
                    row["relative_improvements"]["GO6P_teacher_nrmse"],
                    row["relative_improvements"]["F6P_teacher_nrmse"],
                )
                for row in assessments
            ],
            "pass": [row["fully_guarded_early_pass"] for row in assessments],
        }
    )
    colors = np.where(assessment_frame["pass"], "#15803d", "#b91c1c")
    axes[0, 2].scatter(
        assessment_frame["scale"], assessment_frame["minimum_teacher"], c=colors
    )
    axes[1, 2].scatter(
        assessment_frame["scale"], assessment_frame["latent"], c=colors
    )
    axes[0, 2].axhline(EARLY_IMPROVEMENT_FLOOR, color="#111827", linestyle="--")
    axes[1, 2].axhline(
        LATENT_RESIDUAL_REDUCTION_FLOOR, color="#111827", linestyle="--"
    )
    axes[0, 2].set_title("Worst GO6P/F6P teacher improvement")
    axes[1, 2].set_title("Latent residual reduction")
    axes[1, 2].set_xlabel("V6PGD scale")
    for axis in axes.flat:
        axis.grid(alpha=0.22)
    fig.suptitle("Fixed V6PGD screen with independently constrained PPP states")
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    lines = [
        "# Fixed V6PGD screen coupled to constrained PPP initialization",
        "",
        "## Contract",
        "",
        "- Every kinetic constant except `vmax_V6PGD` remained fixed.",
        "- The same seven latent PPP initial states were re-solved independently at every fixed capacity.",
        "- G6P was used only as a 2% non-inferiority guard.",
        "- No Optuna search, kinetic promotion, or initial-state promotion was performed.",
        f"- Analytical saturation boundary: `{summary['analytical_boundary_vmax_V6PGD']:.7g}`.",
        "",
        "## Best point per capacity",
        "",
        "| Scale | Mode | GL6P(0) | GO6P conc. | GO6P teacher | F6P conc. | F6P teacher | Latent nRMS | Pass |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary["best_by_scale"]:
        lines.append(
            f"| {row['scale']:.4f} | `{row['mode']}` | {row['GL6P_initial']:.6g} | "
            f"{row['GO6P_concentration_nrmse']:.4f} | {row['GO6P_teacher_nrmse']:.4f} | "
            f"{row['F6P_concentration_nrmse']:.4f} | {row['F6P_teacher_nrmse']:.4f} | "
            f"{row['latent_residual_nRMS']:.4f} | `{row['fully_guarded_early_pass']}` |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"**`{summary['decision']}`**",
            "",
            str(summary["decision_rationale"]),
            "",
            f"Selected early candidate: `{summary['selected_early_candidate']}`.",
            f"46-day replay executed: `{summary['long_replay_executed']}`.",
            "",
            "All generated parameter and initialization records are diagnostic only.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_screen(
    *,
    out_dir: Path,
    seed_params_path: Path,
    scales: Sequence[float],
    timepoints: int,
    teacher_dense_points: int,
    max_nfev: int,
    method: str,
    rtol: float,
    atol: float,
    closure_tolerance: float,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    seed_params = _load_params(seed_params_path)
    if not np.isclose(
        float(seed_params.get("vmax_V6PGD", SEED_VMAX_V6PGD)),
        SEED_VMAX_V6PGD,
    ):
        raise RuntimeError("Seed overrides native vmax_V6PGD=10.0")
    current_state = np.asarray(load_initial_conditions(), dtype=float)
    historical_state, _ = _historical_latent_ppp_state(
        current_state, _historical_values()
    )
    exp_time, exp_curves = _all_experimental_curves(46.0)
    teachers = _build_net_flux_teachers(
        exp_time, exp_curves, dense_points=teacher_dense_points
    )
    teacher_initial = np.asarray(
        [_window_teacher(teachers, pool)[2][0] for pool in MEASURED_PPP_POOLS],
        dtype=float,
    )
    latent_scales, teacher_scales = _reference_scales(
        current_state=current_state,
        historical_state=historical_state,
        params=seed_params,
        measured_teacher_initial=teacher_initial,
    )
    bounded_gl6p_max = float(
        max(current_state[LATENT_INDICES[0]], historical_state[LATENT_INDICES[0]])
        * 2.0
    )
    t_eval = np.linspace(1.0, 2.0, int(timepoints))
    solver_rows: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []
    frames: dict[str, pd.DataFrame] = {}
    states: dict[str, np.ndarray] = {}
    params_by_label: dict[str, dict[str, Any]] = {}
    feasibility_by_scale: dict[str, dict[str, Any]] = {}

    def solve_and_replay(
        *, label: str, mode: str, scale: float, params: Mapping[str, Any]
    ) -> None:
        print(f"[v6pgd-constrained] solving {label}", flush=True)
        state, diagnostics = _solve_mode(
            mode=mode,
            current_state=current_state,
            historical_state=historical_state,
            params=params,
            teacher_initial=teacher_initial,
            latent_scales=latent_scales,
            teacher_scales=teacher_scales,
            max_nfev=max_nfev,
        )
        sol, fluxes, derivatives = _simulate_and_track(
            params=params,
            t_eval=t_eval,
            method=method,
            rtol=rtol,
            atol=atol,
            x0_override=state,
        )
        frame, closure = _build_timeseries(
            label=label,
            sol=sol,
            fluxes=fluxes,
            derivatives=derivatives,
            closure_tolerance=closure_tolerance,
        )
        frame["NADP"] = np.asarray(sol.y[NADP_INDEX, :], dtype=float)
        frame["NADPH"] = np.asarray(sol.y[NADPH_INDEX, :], dtype=float)
        row = _augment_metrics(
            metrics=_case_metrics(label=label, frame=frame, teachers=teachers),
            frame=frame,
            closure=closure,
            diagnostics=diagnostics,
            latent_scales=latent_scales,
        )
        row.update(
            {
                "mode": mode,
                "scale": float(scale),
                "vmax_V6PGD": float(params.get("vmax_V6PGD", SEED_VMAX_V6PGD)),
            }
        )
        diagnostics = {
            **diagnostics,
            "candidate": label,
            "scale": float(scale),
            "vmax_V6PGD": row["vmax_V6PGD"],
            "latent_residual_nRMS": row["latent_residual_nRMS"],
        }
        solver_rows.append(diagnostics)
        metrics.append(row)
        frames[label] = frame
        states[label] = state
        params_by_label[label] = dict(params)

    for mode in CONSTRAINED_CASES:
        solve_and_replay(
            label=f"{mode}__seed", mode=mode, scale=1.0, params=seed_params
        )
    for scale in scales:
        params, _ = _candidate_params(seed_params, float(scale))
        feasibility_by_scale[f"{float(scale):.4f}"] = _go6p_fixed_kinetic_feasibility(
            state=current_state,
            params=params,
            teacher_flux=float(teacher_initial[list(MEASURED_PPP_POOLS).index("GO6P")]),
            bounded_gl6p_max=bounded_gl6p_max,
        )
        for mode in CONSTRAINED_CASES:
            solve_and_replay(
                label=_candidate_label(mode, float(scale)),
                mode=mode,
                scale=float(scale),
                params=params,
            )

    metric_by_label = {str(row["candidate"]): row for row in metrics}
    assessments: list[dict[str, Any]] = []
    for scale in scales:
        feasibility = feasibility_by_scale[f"{float(scale):.4f}"]
        for mode in CONSTRAINED_CASES:
            label = _candidate_label(mode, float(scale))
            assessment = _assess_candidate(
                row=metric_by_label[label],
                baseline=metric_by_label[f"{mode}__seed"],
                feasibility=feasibility,
                bounded_gl6p_max=bounded_gl6p_max,
                closure_tolerance=closure_tolerance,
            )
            assessments.append(assessment)
    selected = _select_candidate(assessments, metrics)
    assessment_by_label = {str(row["candidate"]): row for row in assessments}
    best_by_scale: list[dict[str, Any]] = []
    for scale in scales:
        scale_rows = [
            row for row in metrics if np.isclose(float(row["scale"]), float(scale))
        ]
        guarded_rows = [
            row
            for row in scale_rows
            if assessment_by_label[str(row["candidate"])][
                "fully_guarded_early_pass"
            ]
        ]
        best = min(
            guarded_rows or scale_rows,
            key=lambda row: sum(
                float(row[f"{pool}_{metric}"])
                for pool in ("GO6P", "F6P")
                for metric in ("concentration_nrmse", "teacher_nrmse")
            ),
        )
        best_by_scale.append(
            {
                **best,
                "fully_guarded_early_pass": assessment_by_label[
                    str(best["candidate"])
                ]["fully_guarded_early_pass"],
            }
        )

    long_replay: dict[str, Any] | None = None
    if selected is not None:
        selected_mode = str(metric_by_label[selected]["mode"])
        baseline_label = f"{selected_mode}__seed"
        long_frames: dict[str, pd.DataFrame] = {}
        long_metrics: list[dict[str, Any]] = []
        for label in (baseline_label, selected):
            print(f"[v6pgd-constrained] 46-day replay {label}", flush=True)
            sol, fluxes, derivatives = _simulate_and_track(
                params=params_by_label[label],
                t_eval=np.linspace(1.0, 46.0, 901),
                method=method,
                rtol=rtol,
                atol=atol,
                x0_override=states[label],
            )
            frame, closure = _build_timeseries(
                label=label,
                sol=sol,
                fluxes=fluxes,
                derivatives=derivatives,
                closure_tolerance=closure_tolerance,
            )
            frame["NADP"] = np.asarray(sol.y[NADP_INDEX, :], dtype=float)
            frame["NADPH"] = np.asarray(sol.y[NADPH_INDEX, :], dtype=float)
            long_frames[label] = frame
            row = _long_replay_metrics(
                label=label,
                frame=frame,
                experimental_time=exp_time,
                experimental_curves=exp_curves,
                teachers=teachers,
            )
            row["max_pointwise_closure_error"] = float(max(closure.values()))
            long_metrics.append(row)
        baseline_long, candidate_long = long_metrics
        guards = {
            pool: float(candidate_long[f"{pool}_nrmse"])
            <= 1.10 * max(float(baseline_long[f"{pool}_nrmse"]), 1e-30)
            for pool in LONG_GUARD_POOLS
        }
        guards.update(
            {
                "G6P_full_noninferior": float(
                    candidate_long["G6P_concentration_nrmse"]
                )
                <= 1.05 * max(
                    float(baseline_long["G6P_concentration_nrmse"]), 1e-30
                )
                and float(candidate_long["G6P_teacher_nrmse"])
                <= 1.05 * max(float(baseline_long["G6P_teacher_nrmse"]), 1e-30),
                "GO6P_full_noninferior": float(
                    candidate_long["GO6P_concentration_nrmse"]
                )
                <= 1.05 * max(
                    float(baseline_long["GO6P_concentration_nrmse"]), 1e-30
                )
                and float(candidate_long["GO6P_teacher_nrmse"])
                <= 1.05 * max(float(baseline_long["GO6P_teacher_nrmse"]), 1e-30),
                "F6P_full_noninferior": float(
                    candidate_long["F6P_concentration_nrmse"]
                )
                <= 1.05 * max(
                    float(baseline_long["F6P_concentration_nrmse"]), 1e-30
                )
                and float(candidate_long["F6P_teacher_nrmse"])
                <= 1.05 * max(float(baseline_long["F6P_teacher_nrmse"]), 1e-30),
                "GO6P_F6P_joint_full_improves": float(
                    candidate_long["GO6P_F6P_joint_score"]
                )
                < float(baseline_long["GO6P_F6P_joint_score"]),
                "PPP_positive": float(candidate_long["PPP_minimum"]) >= -1e-10,
                "redox_positive": float(candidate_long["NADP_minimum"]) >= -1e-10
                and float(candidate_long["NADPH_minimum"]) >= -1e-10,
                "redox_conserved": float(candidate_long["NADP_NADPH_max_drift"])
                <= 1e-9,
                "exact_ten_pool_closure": float(
                    candidate_long["max_pointwise_closure_error"]
                )
                <= closure_tolerance,
            }
        )
        long_replay = {
            "metrics": long_metrics,
            "guards": guards,
            "all_guards_pass": bool(all(guards.values())),
        }
        pd.concat(long_frames.values(), ignore_index=True).to_csv(
            out_dir / "long_replay_timeseries.csv", index=False
        )

    if selected is None:
        decision = "reject the narrow V6PGD-plus-initialization hypothesis"
        rationale = (
            "No fixed V6PGD point jointly improved GO6P and F6P concentration and "
            "teacher errors, reduced latent residuals, and passed the G6P, finite-GL6P, "
            "positivity, redox, and exact-closure guards. Proceed to the minimal "
            "alternative VPGLS capacity screen around +4.93%."
        )
    elif long_replay is not None and bool(long_replay["all_guards_pass"]):
        decision = "retain one diagnostic V6PGD-plus-initialization candidate"
        rationale = (
            "One early candidate passed every J1-J2 gate and its 46-day replay passed "
            "the full-horizon PPP, ATP, PEP, glucose, lactate, extracellular, "
            "positivity, redox, and closure guards. It remains diagnostic and is not "
            "promoted."
        )
    else:
        decision = "reject candidate after guarded 46-day transfer"
        rationale = (
            "An early candidate passed the PPP gates but failed at least one 46-day "
            "production transfer guard. Retain the production seed."
        )

    pd.DataFrame(metrics).to_csv(out_dir / "early_replay_metrics.csv", index=False)
    pd.concat(frames.values(), ignore_index=True).to_csv(
        out_dir / "early_replay_timeseries.csv", index=False
    )
    (out_dir / "solver_diagnostics.json").write_text(
        json.dumps(_jsonable(solver_rows), indent=2), encoding="utf-8"
    )
    (out_dir / "candidate_assessments.json").write_text(
        json.dumps(_jsonable(assessments), indent=2), encoding="utf-8"
    )
    diagnostic_states = {
        label: {
            "vmax_V6PGD": float(params_by_label[label].get("vmax_V6PGD", 10.0)),
            "latent_initial_states": {
                pool: float(states[label][index])
                for pool, index in zip(LATENT_PPP_POOLS, LATENT_INDICES)
            },
        }
        for label in states
    }
    (out_dir / "diagnostic_candidates.json").write_text(
        json.dumps(
            _jsonable(
                {
                    "diagnostic_only": True,
                    "promoted": False,
                    "kinetic_optimization_performed": False,
                    "candidates": diagnostic_states,
                }
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    _plot_early(
        frames=frames,
        teachers=teachers,
        assessments=assessments,
        out_path=out_dir / "v6pgd_constrained_screen.png",
    )
    summary = {
        "contract_type": "fixed_v6pgd_constrained_ppp_initialization_screen",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "kinetic_optimization_performed": False,
        "parameters_promoted": False,
        "initial_conditions_promoted": False,
        "seed_params_path": str(seed_params_path),
        "seed_vmax_V6PGD": SEED_VMAX_V6PGD,
        "screen_scales": [float(scale) for scale in scales],
        "analytical_boundary_vmax_V6PGD": GO6P_BOUNDARY_VMAX,
        "bounded_GL6P_max": bounded_gl6p_max,
        "latent_pools_resolved": list(LATENT_PPP_POOLS),
        "measured_pools_locked": list(MEASURED_PPP_POOLS),
        "changed_kinetic_constants": ["vmax_V6PGD"],
        "g6p_role": "noninferiority_guard_only",
        "solver_diagnostics": solver_rows,
        "early_replay_metrics": metrics,
        "go6p_feasibility_by_scale": feasibility_by_scale,
        "assessments": assessments,
        "best_by_scale": best_by_scale,
        "selected_early_candidate": selected,
        "long_replay_executed": selected is not None,
        "long_replay": long_replay,
        "decision": decision,
        "decision_rationale": rationale,
        "next_step": (
            "test vmax_VPGLS upward around +4.93% with the same constrained initialization contract"
            if selected is None
            else "review the guarded 46-day transfer before any promotion"
        ),
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "report": str(out_dir / "decision_report.md"),
            "metrics": str(out_dir / "early_replay_metrics.csv"),
            "timeseries": str(out_dir / "early_replay_timeseries.csv"),
            "assessments": str(out_dir / "candidate_assessments.json"),
            "solver_diagnostics": str(out_dir / "solver_diagnostics.json"),
            "diagnostic_candidates": str(out_dir / "diagnostic_candidates.json"),
            "plot": str(out_dir / "v6pgd_constrained_screen.png"),
        },
    }
    (out_dir / "summary.json").write_text(
        json.dumps(_jsonable(summary), indent=2), encoding="utf-8"
    )
    _write_report(out_dir / "decision_report.md", summary)
    print(
        json.dumps(
            {
                "summary": summary["artifact_paths"]["summary"],
                "decision": decision,
                "selected_early_candidate": selected,
                "long_replay_executed": selected is not None,
            },
            indent=2,
        ),
        flush=True,
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Screen fixed V6PGD capacities with constrained PPP states"
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--seed-params", type=Path, default=DEFAULT_SEED_PARAMS)
    parser.add_argument("--scales", type=float, nargs="+", default=SCREEN_SCALES)
    parser.add_argument("--timepoints", type=int, default=241)
    parser.add_argument("--teacher-dense-points", type=int, default=9001)
    parser.add_argument("--max-nfev", type=int, default=1500)
    parser.add_argument("--method", default="LSODA")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    parser.add_argument("--closure-tolerance", type=float, default=1e-12)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_screen(
        out_dir=args.out_dir,
        seed_params_path=args.seed_params,
        scales=args.scales,
        timepoints=args.timepoints,
        teacher_dense_points=args.teacher_dense_points,
        max_nfev=args.max_nfev,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
        closure_tolerance=args.closure_tolerance,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
