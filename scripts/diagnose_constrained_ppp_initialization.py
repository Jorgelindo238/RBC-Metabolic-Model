"""Estimate and diagnose seven latent PPP initial states at fixed kinetics."""

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
from scipy.optimize import least_squares


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
    / "constrained_ppp_initialization_J1_J2"
)

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from equadiff_brodbar import BRODBAR_METABOLITE_MAP, equadiff_brodbar  # noqa: E402
from MM_calibration import load_initial_conditions  # noqa: E402
from profile_atp_consumption_sinks import _all_experimental_curves  # noqa: E402
from profile_glycolysis_flux_bottlenecks import (  # noqa: E402
    _jsonable,
    _load_params,
    _simulate_and_track,
)
from run_glucose_utilization_fla import _nrmse  # noqa: E402
from audit_complete_ppp_fla import (  # noqa: E402
    LATENT_PPP_POOLS,
    MEASURED_PPP_POOLS,
    _build_net_flux_teachers,
    _build_timeseries,
    _net_teacher_metric,
)
from diagnose_ppp_initial_conditions import (  # noqa: E402
    CASE_CURRENT,
    CASE_HISTORICAL,
    _historical_latent_ppp_state,
    _historical_values,
)
from screen_vmax_v6pgd_feasibility import NADPH_INDEX, NADP_INDEX  # noqa: E402


CASE_QSS = "constrained_latent_qss"
CASE_BALANCED = "constrained_balanced_teacher"
CASE_TEACHER = "constrained_teacher_priority"
CONSTRAINED_CASES = (CASE_QSS, CASE_BALANCED, CASE_TEACHER)
MODE_WEIGHTS = {
    CASE_QSS: (1.0, 0.0),
    CASE_BALANCED: (1.0, 1.0),
    CASE_TEACHER: (0.5, 3.0),
}
LATENT_INDICES = np.asarray(
    [int(BRODBAR_METABOLITE_MAP[pool]) for pool in LATENT_PPP_POOLS], dtype=int
)
MEASURED_INDICES = np.asarray(
    [int(BRODBAR_METABOLITE_MAP[pool]) for pool in MEASURED_PPP_POOLS], dtype=int
)


def _state_with_latent(base_state: np.ndarray, latent_values: Sequence[float]) -> np.ndarray:
    state = np.asarray(base_state, dtype=float).copy()
    values = np.asarray(latent_values, dtype=float)
    if values.shape != (len(LATENT_PPP_POOLS),):
        raise ValueError("latent_values must match the seven latent PPP pools")
    state[LATENT_INDICES] = values
    return state


def _initial_derivatives(state: np.ndarray, params: Mapping[str, Any]) -> np.ndarray:
    return np.asarray(
        equadiff_brodbar(
            1.0,
            np.asarray(state, dtype=float),
            custom_params=dict(params),
            curve_fit_strength=0.0,
        ),
        dtype=float,
    )


def _window_teacher(
    teachers: Mapping[str, Any], pool: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    time = np.asarray(teachers["dense_timepoints"], dtype=float)
    mask = (time >= 1.0) & (time <= 2.0)
    curve = teachers["curves"][pool]
    return (
        time[mask],
        np.asarray(curve["dense_concentration"], dtype=float)[mask],
        np.asarray(curve["dense_net_flux"], dtype=float)[mask],
    )


def _reference_scales(
    *,
    current_state: np.ndarray,
    historical_state: np.ndarray,
    params: Mapping[str, Any],
    measured_teacher_initial: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    current_dx = _initial_derivatives(current_state, params)
    historical_dx = _initial_derivatives(historical_state, params)
    latent_scales = np.maximum.reduce(
        (
            np.abs(current_dx[LATENT_INDICES]),
            np.abs(historical_dx[LATENT_INDICES]),
            np.full(len(LATENT_PPP_POOLS), 0.05),
        )
    )
    teacher_scales = np.maximum(np.abs(measured_teacher_initial), 0.01)
    return latent_scales, teacher_scales


def _residual_vector(
    *,
    log_values: np.ndarray,
    base_state: np.ndarray,
    params: Mapping[str, Any],
    teacher_initial: np.ndarray,
    latent_scales: np.ndarray,
    teacher_scales: np.ndarray,
    latent_weight: float,
    teacher_weight: float,
    regularization_center: np.ndarray,
    regularization_weight: float = 0.01,
) -> np.ndarray:
    values = np.exp(np.asarray(log_values, dtype=float))
    state = _state_with_latent(base_state, values)
    derivatives = _initial_derivatives(state, params)
    parts: list[np.ndarray] = []
    if latent_weight > 0.0:
        parts.append(
            float(latent_weight)
            * derivatives[LATENT_INDICES]
            / np.asarray(latent_scales, dtype=float)
        )
    if teacher_weight > 0.0:
        parts.append(
            float(teacher_weight)
            * (derivatives[MEASURED_INDICES] - teacher_initial)
            / np.asarray(teacher_scales, dtype=float)
        )
    if regularization_weight > 0.0:
        parts.append(
            float(regularization_weight)
            * (np.asarray(log_values, dtype=float) - regularization_center)
        )
    return np.concatenate(parts)


def _solve_mode(
    *,
    mode: str,
    current_state: np.ndarray,
    historical_state: np.ndarray,
    params: Mapping[str, Any],
    teacher_initial: np.ndarray,
    latent_scales: np.ndarray,
    teacher_scales: np.ndarray,
    max_nfev: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    latent_weight, teacher_weight = MODE_WEIGHTS[mode]
    historical_values = np.maximum(historical_state[LATENT_INDICES], 1e-9)
    current_values = np.maximum(current_state[LATENT_INDICES], 1e-9)
    lower = np.full(len(LATENT_PPP_POOLS), 1e-9, dtype=float)
    upper = np.maximum(current_values, historical_values) * 2.0
    regularization_center = np.log(historical_values)
    seeds = {
        "historical": historical_values,
        "generic": current_values,
        "geometric_mean": np.sqrt(historical_values * current_values),
        "low_millimolar": np.full(len(LATENT_PPP_POOLS), 1e-3),
    }
    results: list[tuple[str, Any]] = []
    for seed_name, seed in seeds.items():
        clipped = np.clip(seed, lower * 1.001, upper / 1.001)
        result = least_squares(
            lambda z: _residual_vector(
                log_values=z,
                base_state=current_state,
                params=params,
                teacher_initial=teacher_initial,
                latent_scales=latent_scales,
                teacher_scales=teacher_scales,
                latent_weight=latent_weight,
                teacher_weight=teacher_weight,
                regularization_center=regularization_center,
            ),
            np.log(clipped),
            bounds=(np.log(lower), np.log(upper)),
            method="trf",
            x_scale="jac",
            max_nfev=int(max_nfev),
            ftol=1e-11,
            xtol=1e-11,
            gtol=1e-11,
        )
        results.append((seed_name, result))
    seed_name, best = min(results, key=lambda item: float(item[1].cost))
    values = np.exp(np.asarray(best.x, dtype=float))
    state = _state_with_latent(current_state, values)
    derivatives = _initial_derivatives(state, params)
    diagnostics = {
        "mode": mode,
        "latent_weight": latent_weight,
        "teacher_weight": teacher_weight,
        "selected_start": seed_name,
        "success": bool(best.success),
        "status": int(best.status),
        "message": str(best.message),
        "cost": float(best.cost),
        "optimality": float(best.optimality),
        "nfev": int(best.nfev),
        "active_mask": np.asarray(best.active_mask, dtype=int).tolist(),
        "latent_values": {
            pool: float(value) for pool, value in zip(LATENT_PPP_POOLS, values)
        },
        "latent_derivatives": {
            pool: float(derivatives[index])
            for pool, index in zip(LATENT_PPP_POOLS, LATENT_INDICES)
        },
        "measured_teacher_residuals": {
            pool: float(derivatives[index] - teacher)
            for pool, index, teacher in zip(
                MEASURED_PPP_POOLS, MEASURED_INDICES, teacher_initial
            )
        },
        "all_start_costs": {
            name: float(result.cost) for name, result in results
        },
    }
    return state, diagnostics


def _teacher_sensitivity(
    *,
    state: np.ndarray,
    params: Mapping[str, Any],
    relative_step: float = 1e-4,
) -> tuple[np.ndarray, int]:
    baseline = _initial_derivatives(state, params)[MEASURED_INDICES]
    jacobian = np.empty(
        (len(MEASURED_PPP_POOLS), len(LATENT_PPP_POOLS)), dtype=float
    )
    for column, index in enumerate(LATENT_INDICES):
        perturbed = np.asarray(state, dtype=float).copy()
        step = max(abs(float(state[index])) * relative_step, 1e-9)
        perturbed[index] += step
        shifted = _initial_derivatives(perturbed, params)[MEASURED_INDICES]
        jacobian[:, column] = (shifted - baseline) / step
    threshold = max(float(np.linalg.norm(jacobian, ord=2)) * 1e-10, 1e-12)
    return jacobian, int(np.linalg.matrix_rank(jacobian, tol=threshold))


def _go6p_fixed_kinetic_feasibility(
    *,
    state: np.ndarray,
    params: Mapping[str, Any],
    teacher_flux: float,
    bounded_gl6p_max: float,
) -> dict[str, Any]:
    zero_state = np.asarray(state, dtype=float).copy()
    bounded_state = np.asarray(state, dtype=float).copy()
    saturated_state = np.asarray(state, dtype=float).copy()
    zero_state[int(BRODBAR_METABOLITE_MAP["GL6P"])] = 0.0
    bounded_state[int(BRODBAR_METABOLITE_MAP["GL6P"])] = float(bounded_gl6p_max)
    saturated_state[int(BRODBAR_METABOLITE_MAP["GL6P"])] = 1e12
    go6p_index = int(BRODBAR_METABOLITE_MAP["GO6P"])
    minimum = float(_initial_derivatives(zero_state, params)[go6p_index])
    bounded_maximum = float(_initial_derivatives(bounded_state, params)[go6p_index])
    theoretical_maximum = float(
        _initial_derivatives(saturated_state, params)[go6p_index]
    )
    teacher = float(teacher_flux)
    return {
        "teacher_dGO6P_initial": teacher,
        "dGO6P_at_GL6P_zero": minimum,
        "dGO6P_at_bounded_GL6P_max": bounded_maximum,
        "bounded_GL6P_max": float(bounded_gl6p_max),
        "dGO6P_at_GL6P_saturation": theoretical_maximum,
        "bounded_feasible": bool(minimum <= teacher <= bounded_maximum),
        "theoretically_feasible": bool(minimum <= teacher <= theoretical_maximum),
        "best_theoretical_residual": theoretical_maximum - teacher,
    }


def _case_metrics(
    *,
    label: str,
    frame: pd.DataFrame,
    teachers: Mapping[str, Any],
) -> dict[str, Any]:
    model_time = frame["time_day"].to_numpy(dtype=float)
    metrics: dict[str, Any] = {
        "candidate": label,
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
    for pool in MEASURED_PPP_POOLS:
        teacher_time, teacher_concentration, teacher_flux = _window_teacher(
            teachers, pool
        )
        model_concentration = np.interp(
            teacher_time, model_time, frame[pool].to_numpy(dtype=float)
        )
        model_flux = np.interp(
            teacher_time,
            model_time,
            frame[f"d{pool}_dt_effective_flux"].to_numpy(dtype=float),
        )
        concentration = _nrmse(model_concentration, teacher_concentration)
        flux = _net_teacher_metric(model_flux, teacher_flux)
        metrics[f"{pool}_concentration_nrmse"] = float(concentration["nrmse"])
        metrics[f"{pool}_teacher_nrmse"] = float(flux["nrmse"])
        metrics[f"{pool}_teacher_sign_agreement"] = float(flux["sign_agreement"])
        metrics[f"{pool}_final"] = float(frame[pool].iloc[-1])
    metrics["redox_valid"] = bool(
        metrics["NADP_minimum"] >= -1e-10
        and metrics["NADPH_minimum"] >= -1e-10
        and metrics["NADP_NADPH_max_drift"] <= 1e-9
    )
    metrics["joint_concentration_score"] = float(
        sum(metrics[f"{pool}_concentration_nrmse"] for pool in MEASURED_PPP_POOLS)
    )
    metrics["joint_teacher_score"] = float(
        sum(metrics[f"{pool}_teacher_nrmse"] for pool in MEASURED_PPP_POOLS)
    )
    return metrics


def _assess_candidates(
    metrics: Sequence[Mapping[str, Any]],
    go6p_feasibility: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], str, str, str | None]:
    by_label = {str(row["candidate"]): row for row in metrics}
    generic = by_label[CASE_CURRENT]
    assessments: list[dict[str, Any]] = []
    for label in CONSTRAINED_CASES:
        row = by_label[label]
        concentration_improvements = {
            pool: 1.0
            - float(row[f"{pool}_concentration_nrmse"])
            / max(float(generic[f"{pool}_concentration_nrmse"]), 1e-30)
            for pool in MEASURED_PPP_POOLS
        }
        teacher_improvements = {
            pool: 1.0
            - float(row[f"{pool}_teacher_nrmse"])
            / max(float(generic[f"{pool}_teacher_nrmse"]), 1e-30)
            for pool in MEASURED_PPP_POOLS
        }
        joint_pass = bool(
            all(value >= 0.05 for value in concentration_improvements.values())
            and all(value >= 0.05 for value in teacher_improvements.values())
            and bool(row["redox_valid"])
        )
        assessments.append(
            {
                "candidate": label,
                "concentration_relative_improvements": concentration_improvements,
                "teacher_relative_improvements": teacher_improvements,
                "joint_measured_pool_pass": joint_pass,
                "redox_valid": bool(row["redox_valid"]),
                "joint_concentration_score": float(row["joint_concentration_score"]),
                "joint_teacher_score": float(row["joint_teacher_score"]),
            }
        )
    if not bool(go6p_feasibility["theoretically_feasible"]):
        return (
            assessments,
            "do not extend the constrained initialization to 46 days",
            "At fixed production kinetics, the J1 GO6P teacher lies above the maximum dGO6P/dt attainable even with saturating nonnegative GL6P. No initialization-only solution exists; retain all paths as diagnostic and revisit the fixed VPGLS/V6PGD capacity relation before kinetic learning.",
            None,
        )
    eligible = [row for row in assessments if row["joint_measured_pool_pass"]]
    if eligible:
        selected = min(
            eligible,
            key=lambda row: float(row["joint_concentration_score"])
            + 0.1 * float(row["joint_teacher_score"]),
        )
        return (
            assessments,
            "advance one constrained initialization to a guarded 46-day replay",
            "A fixed-kinetic constrained initialization improves concentrations and teachers for G6P, GO6P, and F6P by at least 5% while preserving redox.",
            str(selected["candidate"]),
        )
    return (
        assessments,
        "do not extend the constrained initialization to 46 days",
        "No constrained initialization jointly improves all three measured PPP concentrations and teachers by 5%. Keep all initialization paths diagnostic and revise the initialization constraints before kinetic learning.",
        None,
    )


def _plot_replays(
    *,
    frames: Mapping[str, pd.DataFrame],
    teachers: Mapping[str, Any],
    out_path: Path,
) -> None:
    colors = {
        CASE_CURRENT: "#64748b",
        CASE_HISTORICAL: "#0f766e",
        CASE_QSS: "#2563eb",
        CASE_BALANCED: "#7c3aed",
        CASE_TEACHER: "#dc2626",
    }
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.5), constrained_layout=True)
    for column, pool in enumerate(MEASURED_PPP_POOLS):
        teacher_time, teacher_concentration, teacher_flux = _window_teacher(
            teachers, pool
        )
        for label, frame in frames.items():
            axes[0, column].plot(
                frame["time_day"], frame[pool], color=colors[label], linewidth=1.8, label=label
            )
            axes[1, column].plot(
                frame["time_day"],
                frame[f"d{pool}_dt_effective_flux"],
                color=colors[label],
                linewidth=1.8,
                label=label,
            )
        axes[0, column].plot(
            teacher_time,
            teacher_concentration,
            color="#111827",
            linestyle="--",
            linewidth=2.2,
            label="Brodbar PCHIP",
        )
        axes[1, column].plot(
            teacher_time,
            teacher_flux,
            color="#111827",
            linestyle="--",
            linewidth=2.2,
            label="Brodbar teacher",
        )
        axes[0, column].set_title(f"{pool} concentration")
        axes[1, column].set_title(f"{pool} net flux")
        axes[0, column].set_ylabel("mM")
        axes[1, column].set_ylabel("mM/day")
        axes[1, column].set_xlabel("Time (day)")
        for axis in (axes[0, column], axes[1, column]):
            axis.grid(alpha=0.22)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=3, frameon=False)
    fig.suptitle("Constrained latent PPP initialization at fixed kinetics")
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _plot_initial_states(
    *,
    states: Mapping[str, np.ndarray],
    params: Mapping[str, Any],
    teacher_initial: np.ndarray,
    out_path: Path,
) -> None:
    labels = list(states)
    x = np.arange(len(LATENT_PPP_POOLS), dtype=float)
    width = 0.16
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.4), constrained_layout=True)
    for offset, label in enumerate(labels):
        state = states[label]
        axes[0].bar(
            x + (offset - (len(labels) - 1) / 2.0) * width,
            state[LATENT_INDICES],
            width,
            label=label,
        )
        derivatives = _initial_derivatives(state, params)
        axes[1].plot(
            LATENT_PPP_POOLS,
            derivatives[LATENT_INDICES],
            marker="o",
            linewidth=1.5,
            label=label,
        )
    axes[0].set_yscale("log")
    axes[0].set_xticks(x, LATENT_PPP_POOLS, rotation=35, ha="right")
    axes[0].set_ylabel("Initial concentration (mM)")
    axes[0].set_title("Seven latent PPP initial states")
    axes[1].axhline(0.0, color="#111827", linewidth=0.8)
    axes[1].tick_params(axis="x", rotation=35)
    axes[1].set_ylabel("Initial ODE derivative (mM/day)")
    axes[1].set_title("Latent quasi-steady residuals")
    for axis in axes:
        axis.grid(alpha=0.22)
    handles, legend_labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, legend_labels, loc="outside lower center", ncol=3, frameon=False)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    lines = [
        "# Constrained latent PPP initialization",
        "",
        "## Contract",
        "",
        "- Production kinetics fixed; measured J1 states locked.",
        "- Only GL6P, RU5P, R5P, X5P, E4P, S7P, and GA3P may change.",
        "- Positive bounded multistart least-squares in log concentration space.",
        "- Generic and historical initializations preserved as revert paths.",
        "- Diagnostic only; no initial condition or kinetic parameter promoted.",
        f"- Measured-teacher sensitivity rank: `{summary['measured_teacher_sensitivity_rank']}` of 3.",
        f"- GO6P teacher feasible at fixed kinetics: `{summary['go6p_fixed_kinetic_feasibility']['theoretically_feasible']}`.",
        f"- Saturating-GL6P maximum dGO6P/dt: `{summary['go6p_fixed_kinetic_feasibility']['dGO6P_at_GL6P_saturation']:.6g}` versus teacher `{summary['go6p_fixed_kinetic_feasibility']['teacher_dGO6P_initial']:.6g}` mM/day.",
        f"- Maximum ten-pool replay closure error: `{summary['max_pointwise_closure_error']:.3e}` mM/day.",
        "",
        "## J1-J2 metrics",
        "",
        "| Case | G6P conc. | GO6P conc. | F6P conc. | G6P teacher | GO6P teacher | F6P teacher |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary["replay_metrics"]:
        lines.append(
            f"| `{row['candidate']}` | {row['G6P_concentration_nrmse']:.4f} | "
            f"{row['GO6P_concentration_nrmse']:.4f} | {row['F6P_concentration_nrmse']:.4f} | "
            f"{row['G6P_teacher_nrmse']:.4f} | {row['GO6P_teacher_nrmse']:.4f} | "
            f"{row['F6P_teacher_nrmse']:.4f} |"
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
            f"Selected case: `{summary['selected_case']}`.",
            "",
            "No production initialization or kinetic artifact was generated.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_diagnostic(
    *,
    out_dir: Path,
    seed_params_path: Path,
    timepoints: int,
    teacher_dense_points: int,
    max_nfev: int,
    method: str,
    rtol: float,
    atol: float,
    closure_tolerance: float,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    params = _load_params(seed_params_path)
    current_state = np.asarray(load_initial_conditions(), dtype=float)
    historical_state, historical_changes = _historical_latent_ppp_state(
        current_state, _historical_values()
    )
    exp_time, exp_curves = _all_experimental_curves(46.0)
    teachers = _build_net_flux_teachers(
        exp_time, exp_curves, dense_points=teacher_dense_points
    )
    teacher_initial = np.asarray(
        [
            _window_teacher(teachers, pool)[2][0]
            for pool in MEASURED_PPP_POOLS
        ],
        dtype=float,
    )
    latent_scales, teacher_scales = _reference_scales(
        current_state=current_state,
        historical_state=historical_state,
        params=params,
        measured_teacher_initial=teacher_initial,
    )
    bounded_gl6p_max = float(
        max(
            current_state[int(BRODBAR_METABOLITE_MAP["GL6P"])],
            historical_state[int(BRODBAR_METABOLITE_MAP["GL6P"])],
        )
        * 2.0
    )
    go6p_feasibility = _go6p_fixed_kinetic_feasibility(
        state=current_state,
        params=params,
        teacher_flux=float(teacher_initial[list(MEASURED_PPP_POOLS).index("GO6P")]),
        bounded_gl6p_max=bounded_gl6p_max,
    )
    constrained_states: dict[str, np.ndarray] = {}
    solver_diagnostics: list[dict[str, Any]] = []
    for mode in CONSTRAINED_CASES:
        print(f"[constrained-ppp-init] solving {mode}", flush=True)
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
        constrained_states[mode] = state
        solver_diagnostics.append(diagnostics)

    sensitivity, sensitivity_rank = _teacher_sensitivity(
        state=historical_state, params=params
    )
    states: dict[str, np.ndarray] = {
        CASE_CURRENT: current_state,
        CASE_HISTORICAL: historical_state,
        **constrained_states,
    }
    t_eval = np.linspace(1.0, 2.0, int(timepoints))
    frames: dict[str, pd.DataFrame] = {}
    replay_metrics: list[dict[str, Any]] = []
    closure_by_case: dict[str, dict[str, float]] = {}
    case_contracts: list[dict[str, Any]] = []
    for label, state in states.items():
        print(f"[constrained-ppp-init] simulating {label}", flush=True)
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
        frames[label] = frame
        closure_by_case[label] = closure
        replay_metrics.append(
            _case_metrics(label=label, frame=frame, teachers=teachers)
        )
        changed = [
            pool
            for pool, index in zip(LATENT_PPP_POOLS, LATENT_INDICES)
            if not np.isclose(float(state[index]), float(current_state[index]), rtol=0.0, atol=1e-15)
        ]
        measured_changed = [
            pool
            for pool, index in zip(MEASURED_PPP_POOLS, MEASURED_INDICES)
            if not np.isclose(float(state[index]), float(current_state[index]), rtol=0.0, atol=1e-15)
        ]
        case_contracts.append(
            {
                "candidate": label,
                "changed_initial_states": changed,
                "changed_measured_states": measured_changed,
                "changed_kinetic_constants": [],
            }
        )
    assessments, decision, rationale, selected = _assess_candidates(
        replay_metrics, go6p_feasibility
    )
    max_closure = max(
        value for case in closure_by_case.values() for value in case.values()
    )
    initialization_payload = {
        "contract_type": "diagnostic_constrained_latent_ppp_initializations",
        "diagnostic_only": True,
        "promoted": False,
        "measured_states_locked": True,
        "kinetics_fixed": True,
        "revert_cases": [CASE_CURRENT, CASE_HISTORICAL],
        "candidates": {
            label: {
                pool: float(state[index])
                for pool, index in zip(LATENT_PPP_POOLS, LATENT_INDICES)
            }
            for label, state in constrained_states.items()
        },
    }
    initializations_path = out_dir / "constrained_initializations.json"
    solver_path = out_dir / "solver_diagnostics.json"
    metrics_path = out_dir / "replay_metrics.csv"
    timeseries_path = out_dir / "replay_timeseries.csv"
    replay_plot_path = out_dir / "constrained_initialization_replays.png"
    initial_plot_path = out_dir / "constrained_initial_states.png"
    initializations_path.write_text(
        json.dumps(_jsonable(initialization_payload), indent=2), encoding="utf-8"
    )
    solver_path.write_text(
        json.dumps(_jsonable(solver_diagnostics), indent=2), encoding="utf-8"
    )
    pd.DataFrame(replay_metrics).to_csv(metrics_path, index=False)
    pd.concat(frames.values(), ignore_index=True).to_csv(timeseries_path, index=False)
    _plot_replays(frames=frames, teachers=teachers, out_path=replay_plot_path)
    _plot_initial_states(
        states=states,
        params=params,
        teacher_initial=teacher_initial,
        out_path=initial_plot_path,
    )
    summary = {
        "contract_type": "constrained_latent_ppp_initialization_diagnostic",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "optimization_type": "initial_state_estimation_only",
        "kinetic_optimization_performed": False,
        "parameters_promoted": False,
        "initial_conditions_promoted": False,
        "seed_params_path": str(seed_params_path),
        "latent_pools": list(LATENT_PPP_POOLS),
        "measured_pools_locked": list(MEASURED_PPP_POOLS),
        "historical_changes": historical_changes,
        "teacher_initial": {
            pool: float(value) for pool, value in zip(MEASURED_PPP_POOLS, teacher_initial)
        },
        "latent_residual_scales": {
            pool: float(value) for pool, value in zip(LATENT_PPP_POOLS, latent_scales)
        },
        "teacher_residual_scales": {
            pool: float(value) for pool, value in zip(MEASURED_PPP_POOLS, teacher_scales)
        },
        "measured_teacher_sensitivity_jacobian": sensitivity.tolist(),
        "measured_teacher_sensitivity_rank": sensitivity_rank,
        "go6p_fixed_kinetic_feasibility": go6p_feasibility,
        "solver_diagnostics": solver_diagnostics,
        "case_contracts": case_contracts,
        "closure_by_case": closure_by_case,
        "max_pointwise_closure_error": max_closure,
        "replay_metrics": replay_metrics,
        "assessments": assessments,
        "decision": decision,
        "decision_rationale": rationale,
        "selected_case": selected,
        "extend_to_46_days": selected is not None,
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "report": str(out_dir / "decision_report.md"),
            "diagnostic_initializations": str(initializations_path),
            "solver_diagnostics": str(solver_path),
            "replay_metrics": str(metrics_path),
            "replay_timeseries": str(timeseries_path),
            "replay_plot": str(replay_plot_path),
            "initial_state_plot": str(initial_plot_path),
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
                "selected_case": selected,
                "extend_to_46_days": summary["extend_to_46_days"],
                "sensitivity_rank": sensitivity_rank,
                "max_closure": max_closure,
            },
            indent=2,
        ),
        flush=True,
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Diagnose constrained PPP initial states")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--seed-params", type=Path, default=DEFAULT_SEED_PARAMS)
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
    run_diagnostic(
        out_dir=args.out_dir,
        seed_params_path=args.seed_params,
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
