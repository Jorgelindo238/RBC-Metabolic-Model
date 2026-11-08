"""Directed fixed-point feasibility screen of V6PGD under corrected PPP initialization."""

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
    ROOT / "Simulations" / "brodbar" / "hermes" / "vmax_v6pgd_feasibility_46d"
)

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from equadiff_brodbar import BRODBAR_METABOLITE_MAP  # noqa: E402
from MM_calibration import load_initial_conditions  # noqa: E402
from profile_atp_consumption_sinks import _all_experimental_curves  # noqa: E402
from profile_glycolysis_flux_bottlenecks import (  # noqa: E402
    _jsonable,
    _load_params,
    _simulate_and_track,
    _time_mean,
)
from run_glucose_utilization_fla import _build_lactate_teacher_dataset  # noqa: E402
from screen_km_adp_atp_production import _teacher_flux_metrics  # noqa: E402
from audit_investment_phase_flux_matching import _time_grid  # noqa: E402
from audit_complete_ppp_fla import (  # noqa: E402
    CONTEXT_POOLS,
    MEASURED_PPP_POOLS,
    _build_net_flux_teachers,
    _build_timeseries,
    _context_metric_rows,
    _measured_metric_rows,
    _routing_rows,
    _teacher_window_rows,
    _window_and_attribution_rows,
)
from diagnose_ppp_initial_conditions import (  # noqa: E402
    CASE_CURRENT,
    CASE_HISTORICAL,
    TEACHER_FLUXES,
    _historical_latent_ppp_state,
    _historical_values,
)


SEED_VMAX_V6PGD = 10.0
SCREEN_SCALES = (0.60, 0.50, 0.43, 0.35)
MIN_TEACHER_IMPROVEMENT = 0.20
MIN_GO6P_CONCENTRATION_IMPROVEMENT = 0.05
NADP_INDEX = int(BRODBAR_METABOLITE_MAP["NADP"])
NADPH_INDEX = int(BRODBAR_METABOLITE_MAP["NADPH"])


def _candidate_label(scale: float) -> str:
    return f"vmax_V6PGD_{scale:.2f}x"


def _candidate_params(
    seed_params: Mapping[str, Any], scale: float
) -> tuple[dict[str, Any], list[str]]:
    params = dict(seed_params)
    params["vmax_V6PGD"] = SEED_VMAX_V6PGD * float(scale)
    changed = [
        name
        for name in sorted(set(seed_params) | set(params))
        if seed_params.get(name) != params.get(name)
    ]
    if changed != ["vmax_V6PGD"]:
        raise RuntimeError(f"V6PGD fixed-point contract failed: changed={changed}")
    return params, changed


def _rows_by_key(
    rows: Sequence[Mapping[str, Any]], *keys: str
) -> dict[tuple[str, ...], Mapping[str, Any]]:
    return {tuple(str(row[key]) for key in keys): row for row in rows}


def _redox_metrics(label: str, sol: Any) -> dict[str, Any]:
    time = np.asarray(sol.t, dtype=float)
    nadp = np.asarray(sol.y[NADP_INDEX, :], dtype=float)
    nadph = np.asarray(sol.y[NADPH_INDEX, :], dtype=float)
    total = nadp + nadph

    def metrics(values: np.ndarray) -> dict[str, float]:
        return {
            "initial": float(values[0]),
            "final": float(values[-1]),
            "minimum": float(np.min(values)),
            "maximum": float(np.max(values)),
            "time_mean": _time_mean(values, time),
            "integral": float(np.trapezoid(values, time)),
        }

    return {
        "candidate": label,
        "NADP": metrics(nadp),
        "NADPH": metrics(nadph),
        "NADP_NADPH_total": metrics(total),
        "max_total_drift": float(np.max(np.abs(total - total[0]))),
    }


def _relative_guard(
    candidate: float,
    reference: float,
    *,
    limit: float,
    tolerance: float = 0.01,
) -> bool:
    return float(candidate) > float(reference) * float(limit) + float(tolerance)


def _candidate_guards(
    *,
    label: str,
    measured: Mapping[tuple[str, ...], Mapping[str, Any]],
    context: Mapping[tuple[str, ...], Mapping[str, Any]],
    teacher_flux: Mapping[tuple[str, ...], Mapping[str, Any]],
    redox: Mapping[str, Mapping[str, Any]],
    reference_label: str,
    production_reference: bool,
) -> list[str]:
    reasons: list[str] = []
    for pool in MEASURED_PPP_POOLS:
        if pool == "GO6P":
            continue
        candidate = measured[(label, pool)]
        reference = measured[(reference_label, pool)]
        if _relative_guard(
            candidate["concentration_nrmse"],
            reference["concentration_nrmse"],
            limit=1.05,
        ):
            reasons.append(f"{pool} concentration nRMSE guard")
        if abs(float(candidate["concentration_endpoint_error"])) > abs(
            float(reference["concentration_endpoint_error"])
        ) * 1.10 + 0.02:
            reasons.append(f"{pool} endpoint guard")

    limits = {
        "EGLC": 1.03,
        "ELAC": 1.05,
        "GLC": 1.05,
        "F16BP": 1.10,
        "LAC": 1.05,
        "PEP": 1.05,
        "ATP": 1.10,
    }
    for pool, limit in limits.items():
        candidate = context[(label, pool)]
        reference = context[(reference_label, pool)]
        if _relative_guard(candidate["nrmse"], reference["nrmse"], limit=limit):
            reasons.append(f"{pool} nRMSE guard")
        if abs(float(candidate["endpoint_error"])) > abs(
            float(reference["endpoint_error"])
        ) * 1.10 + 0.02:
            reasons.append(f"{pool} endpoint guard")
    if float(context[(label, "ATP")]["simulated_final"]) < float(
        context[(reference_label, "ATP")]["simulated_final"]
    ) * 0.95:
        reasons.append("ATP endpoint below 95% of reference")

    for reaction in TEACHER_FLUXES:
        candidate = teacher_flux[(label, reaction)]
        reference = teacher_flux[(reference_label, reaction)]
        if _relative_guard(candidate["nrmse"], reference["nrmse"], limit=1.08):
            reasons.append(f"{reaction} teacher-flux guard")

    reference_redox = redox[reference_label]
    candidate_redox = redox[label]
    for pool in ("NADP", "NADPH"):
        reference_final = max(abs(float(reference_redox[pool]["final"])), 1e-12)
        final_ratio = float(candidate_redox[pool]["final"]) / reference_final
        if final_ratio < 0.80 or final_ratio > 1.25:
            reasons.append(f"{pool} endpoint ratio guard")
        reference_mean = max(abs(float(reference_redox[pool]["time_mean"])), 1e-12)
        mean_ratio = float(candidate_redox[pool]["time_mean"]) / reference_mean
        if mean_ratio < 0.80 or mean_ratio > 1.25:
            reasons.append(f"{pool} time-mean ratio guard")
    if float(candidate_redox["max_total_drift"]) > 1e-8:
        reasons.append("NADP+NADPH conservation guard")
    prefix = "production" if production_reference else "incremental"
    return [f"{prefix}: {reason}" for reason in sorted(set(reasons))]


def _assess_candidates(
    *,
    labels: Sequence[str],
    reference_label: str,
    measured_rows: Sequence[Mapping[str, Any]],
    context_rows: Sequence[Mapping[str, Any]],
    teacher_flux_rows: Sequence[Mapping[str, Any]],
    teacher_window_rows: Sequence[Mapping[str, Any]],
    redox_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    measured = _rows_by_key(measured_rows, "candidate", "pool")
    context = _rows_by_key(context_rows, "candidate", "pool")
    teacher_flux = _rows_by_key(teacher_flux_rows, "candidate", "reaction")
    teacher_windows = _rows_by_key(teacher_window_rows, "candidate", "window", "pool")
    redox = {str(row["candidate"]): row for row in redox_rows}
    assessments: list[dict[str, Any]] = []
    reference_early = teacher_windows[(reference_label, "early_1_2d", "GO6P")]
    reference_full = measured[(reference_label, "GO6P")]
    for label in labels:
        early = teacher_windows[(label, "early_1_2d", "GO6P")]
        full = measured[(label, "GO6P")]
        incremental = _candidate_guards(
            label=label,
            measured=measured,
            context=context,
            teacher_flux=teacher_flux,
            redox=redox,
            reference_label=reference_label,
            production_reference=False,
        )
        production = _candidate_guards(
            label=label,
            measured=measured,
            context=context,
            teacher_flux=teacher_flux,
            redox=redox,
            reference_label=CASE_CURRENT,
            production_reference=True,
        )
        early_improvement = 1.0 - float(early["nrmse"]) / max(
            float(reference_early["nrmse"]), 1e-30
        )
        full_improvement = 1.0 - float(full["net_teacher_nrmse"]) / max(
            float(reference_full["net_teacher_nrmse"]), 1e-30
        )
        concentration_improvement = 1.0 - float(full["concentration_nrmse"]) / max(
            float(reference_full["concentration_nrmse"]), 1e-30
        )
        target_pass = (
            early_improvement >= MIN_TEACHER_IMPROVEMENT
            and full_improvement >= MIN_TEACHER_IMPROVEMENT
            and concentration_improvement >= MIN_GO6P_CONCENTRATION_IMPROVEMENT
        )
        assessments.append(
            {
                "candidate": label,
                "early_GO6P_teacher_relative_improvement": early_improvement,
                "full_GO6P_teacher_relative_improvement": full_improvement,
                "early_GO6P_model_mean_flux": float(early["mean_model_flux"]),
                "early_GO6P_teacher_mean_flux": float(early["mean_teacher_flux"]),
                "GO6P_concentration_nrmse": float(full["concentration_nrmse"]),
                "GO6P_concentration_relative_improvement": concentration_improvement,
                "incremental_guard_reasons": incremental,
                "production_guard_reasons": production,
                "passes_primary_target": target_pass,
                "passes_incremental_guards": not incremental,
                "passes_production_guards": not production,
                "fixed_point_feasible": target_pass and not incremental and not production,
            }
        )
    return assessments


def _decision(
    assessments: Sequence[Mapping[str, Any]],
    candidate_initialization: str = "historical",
) -> tuple[str, str, str | None]:
    feasible = [row for row in assessments if bool(row["fixed_point_feasible"])]
    if feasible:
        best = max(
            feasible,
            key=lambda row: float(row["early_GO6P_teacher_relative_improvement"])
            + float(row["full_GO6P_teacher_relative_improvement"]),
        )
        label = str(best["candidate"])
        context = (
            "current-initialization"
            if candidate_initialization == "current"
            else "historical-initialization"
        )
        return (
            f"advance {label} as a guarded {context} candidate for a repeated PPP audit",
            "The fixed V6PGD point improves both early and full GO6P teachers by at least 20% and passes incremental, production, redox, extracellular, and lactate guards. It remains diagnostic and is not globally promoted.",
            label,
        )
    target_passes = [row for row in assessments if bool(row["passes_primary_target"])]
    if target_passes:
        best = max(
            target_passes,
            key=lambda row: float(row["early_GO6P_teacher_relative_improvement"])
            + float(row["full_GO6P_teacher_relative_improvement"]),
        )
        return (
            "reject V6PGD promotion despite GO6P target improvement",
            f"{best['candidate']} best corrects GO6P, but at least one incremental or production transfer guard remains. Do not run Optuna; inspect the failed guards before selecting another PPP lever.",
            None,
        )
    return (
        "reject the isolated V6PGD hypothesis",
        "No fixed downward V6PGD point jointly improves both GO6P teacher errors by 20% and the GO6P concentration nRMSE by 5%. Return to a coupled VPGLS/V6PGD, initial-rate, or GO6P-affinity structural diagnosis without optimization.",
        None,
    )


def _plot_screen(
    *,
    frames: Mapping[str, pd.DataFrame],
    screen_scales: Sequence[float],
    reference_label: str,
    exp_time: np.ndarray,
    exp_curves: Mapping[str, np.ndarray],
    net_teachers: Mapping[str, Any],
    redox_rows: Sequence[Mapping[str, Any]],
    out_path: Path,
) -> None:
    labels = list(frames)
    palette = ["#64748b", "#0f766e", "#2563eb", "#7c3aed", "#b45309", "#dc2626"]
    colors = dict(zip(labels, palette))
    fig, axes = plt.subplots(2, 4, figsize=(17, 9), constrained_layout=True)
    for axis, pool in zip(axes.flat[:3], ("GO6P", "G6P", "F6P")):
        for label, frame in frames.items():
            axis.plot(frame["time_day"], frame[pool], color=colors[label], linewidth=1.8, label=label)
        axis.scatter(exp_time, exp_curves[pool], color="#111827", s=24, zorder=5, label="Brodbar")
        axis.set_title(f"{pool} concentration")
        axis.set_xlabel("Time (days)")
        axis.set_ylabel("mM")
        axis.grid(True, alpha=0.22)
        if pool in {"G6P", "F6P"}:
            axis.set_yscale("log")

    axis = axes.flat[3]
    teacher_time = np.asarray(net_teachers["dense_timepoints"], dtype=float)
    axis.plot(
        teacher_time,
        net_teachers["curves"]["GO6P"]["dense_net_flux"],
        color="#111827",
        linewidth=2.4,
        linestyle=":",
        label="Brodbar net teacher",
    )
    for label, frame in frames.items():
        axis.plot(
            frame["time_day"],
            frame["dGO6P_dt_effective_flux"],
            color=colors[label],
            linewidth=1.7,
            label=label,
        )
    axis.axhline(0.0, color="#111827", linewidth=0.8)
    axis.set_title("GO6P net-flux teacher")
    axis.set_xlabel("Time (days)")
    axis.set_ylabel("mM/day")
    axis.set_yscale("symlog", linthresh=1e-3)
    axis.grid(True, alpha=0.22)

    axis = axes.flat[4]
    for label, frame in frames.items():
        axis.plot(frame["time_day"], frame["VPGLS"], color=colors[label], linewidth=1.7, label=f"{label} VPGLS")
        axis.plot(frame["time_day"], frame["V6PGD"], color=colors[label], linewidth=1.4, linestyle="--")
    axis.set_title("VPGLS input and V6PGD output")
    axis.set_xlabel("Time (days)")
    axis.set_ylabel("mM/day")
    axis.set_yscale("symlog", linthresh=1e-3)
    axis.grid(True, alpha=0.22)

    for axis, pool in zip(axes.flat[5:7], ("NADP", "NADPH")):
        index = int(BRODBAR_METABOLITE_MAP[pool])
        for label, frame in frames.items():
            axis.plot(frame["time_day"], frame[pool], color=colors[label], linewidth=1.8, label=label)
        axis.set_title(pool)
        axis.set_xlabel("Time (days)")
        axis.set_ylabel("mM")
        axis.grid(True, alpha=0.22)

    axis = axes.flat[7]
    scales = [1.0, *screen_scales]
    selected_labels = [reference_label, *[_candidate_label(scale) for scale in screen_scales]]
    early_values = []
    late_values = []
    for label in selected_labels:
        frame = frames[label]
        time = frame["time_day"].to_numpy(dtype=float)
        early = (time >= 1.0) & (time <= 2.0)
        late = (time >= 40.0) & (time <= 46.0)
        early_values.append(_time_mean(frame.loc[early, "dGO6P_dt_effective_flux"].to_numpy(dtype=float), time[early]))
        late_values.append(_time_mean(frame.loc[late, "dGO6P_dt_effective_flux"].to_numpy(dtype=float), time[late]))
    x = np.arange(len(scales), dtype=float)
    axis.bar(x - 0.18, early_values, 0.36, color="#2563eb", label="J1-J2")
    axis.bar(x + 0.18, late_values, 0.36, color="#b45309", label="J40-J46")
    axis.axhline(0.0, color="#111827", linewidth=0.8)
    axis.set_xticks(x, [f"{scale:.6g}x" for scale in scales])
    axis.set_title("Mean GO6P net flux")
    axis.set_ylabel("mM/day")
    axis.grid(True, axis="y", alpha=0.22)
    axis.legend(frameon=False, fontsize=8)

    handles, legend_labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(
        handles,
        legend_labels,
        loc="outside lower center",
        ncol=4,
        frameon=False,
    )
    initialization_context = (
        "current" if reference_label == CASE_CURRENT else "historical"
    )
    fig.suptitle(
        f"Directed V6PGD feasibility screen under {initialization_context} PPP initialization",
        fontsize=15,
    )
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    candidate_initialization = str(summary["candidate_initialization"])
    reference_label = str(summary["assessment_reference_label"])
    lines = [
        "# Directed V6PGD feasibility screen",
        "",
        "## Contract",
        "",
        f"- Generated: {summary['generated_at']}",
        f"- Horizon: `{summary['t_max']:.0f}` days.",
        f"- Candidate initialization: `{candidate_initialization}`; assessment reference: `{reference_label}`.",
        "- Candidate points change only `vmax_V6PGD`; no other kinetic constant or initial state changes within the selected initialization context.",
        f"- Fixed scales: `{', '.join(f'{scale:.6g}x' for scale in summary['screen_scales'])}` of native `vmax_V6PGD = {SEED_VMAX_V6PGD:g}`.",
        "- No optimization or promotion.",
        f"- Maximum ten-pool closure error: `{summary['max_pointwise_closure_error']:.3e}` mM/day.",
        "",
        "## Candidate assessment",
        "",
        "| Candidate | Early teacher improvement | Full teacher improvement | GO6P concentration improvement | Early model flux | Teacher flux | Incremental guards | Production guards | Feasible |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary["assessments"]:
        lines.append(
            f"| `{row['candidate']}` | {100.0 * row['early_GO6P_teacher_relative_improvement']:.1f}% | "
            f"{100.0 * row['full_GO6P_teacher_relative_improvement']:.1f}% | "
            f"{100.0 * row['GO6P_concentration_relative_improvement']:.1f}% | "
            f"{row['early_GO6P_model_mean_flux']:.6g} | {row['early_GO6P_teacher_mean_flux']:.6g} | "
            f"{len(row['incremental_guard_reasons'])} | {len(row['production_guard_reasons'])} | "
            f"`{row['fixed_point_feasible']}` |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"**`{summary['decision']}`**",
            "",
            summary["decision_rationale"],
            "",
            f"Selected fixed case: `{summary['selected_fixed_case']}`.",
            "",
            "No Optuna study or promoted parameter file was generated.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_screen(
    *,
    out_dir: Path,
    seed_params_path: Path,
    scales: Sequence[float],
    candidate_initialization: str,
    t_max: float,
    timepoints: int,
    early_timepoints: int,
    teacher_dense_points: int,
    method: str,
    rtol: float,
    atol: float,
    closure_tolerance: float,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    seed_params = _load_params(seed_params_path)
    if "vmax_V6PGD" in seed_params and not np.isclose(
        float(seed_params["vmax_V6PGD"]), SEED_VMAX_V6PGD
    ):
        raise RuntimeError("Saved seed overrides the expected native vmax_V6PGD")
    current_x0 = np.asarray(load_initial_conditions(), dtype=float)
    historical_x0, initial_changes = _historical_latent_ppp_state(
        current_x0,
        _historical_values(),
    )
    t_eval = _time_grid(t_max, timepoints, early_timepoints)
    exp_time, exp_curves = _all_experimental_curves(t_max)
    net_teachers = _build_net_flux_teachers(
        exp_time,
        exp_curves,
        dense_points=teacher_dense_points,
    )
    transport_teacher_path = out_dir / "transport_lactate_teacher_dataset.json"
    transport_teacher = _build_lactate_teacher_dataset(
        exp_time=exp_time,
        exp_curves=exp_curves,
        dense_points=teacher_dense_points,
        out_path=transport_teacher_path,
    )

    if candidate_initialization not in {"current", "historical"}:
        raise ValueError("candidate_initialization must be 'current' or 'historical'")
    reference_label = (
        CASE_CURRENT if candidate_initialization == "current" else CASE_HISTORICAL
    )
    candidate_x0 = (
        current_x0 if candidate_initialization == "current" else historical_x0
    )
    replay_specs: list[tuple[str, np.ndarray, dict[str, Any], list[str]]] = [
        (CASE_CURRENT, current_x0, dict(seed_params), []),
    ]
    if candidate_initialization == "historical":
        replay_specs.append((CASE_HISTORICAL, historical_x0, dict(seed_params), []))
    for scale in scales:
        params, changed = _candidate_params(seed_params, scale)
        replay_specs.append((_candidate_label(scale), candidate_x0, params, changed))

    frames: dict[str, pd.DataFrame] = {}
    case_contracts: list[dict[str, Any]] = []
    closure_by_case: dict[str, dict[str, float]] = {}
    measured_rows: list[dict[str, Any]] = []
    context_rows: list[dict[str, Any]] = []
    teacher_flux_rows: list[dict[str, Any]] = []
    teacher_window_rows: list[dict[str, Any]] = []
    pool_window_rows: list[dict[str, Any]] = []
    attribution_rows: list[dict[str, Any]] = []
    routing_rows: list[dict[str, Any]] = []
    redox_rows: list[dict[str, Any]] = []
    for label, x0, params, changed in replay_specs:
        print(f"[v6pgd-screen] simulating {label}", flush=True)
        sol, fluxes, derivatives = _simulate_and_track(
            params=params,
            t_eval=t_eval,
            method=method,
            rtol=rtol,
            atol=atol,
            x0_override=x0,
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
        case_contracts.append(
            {
                "candidate": label,
                "changed_kinetic_constants": changed,
                "uses_historical_latent_ppp_initialization": (
                    label == CASE_HISTORICAL
                    or (label not in {CASE_CURRENT, CASE_HISTORICAL} and candidate_initialization == "historical")
                ),
                "vmax_V6PGD": float(params.get("vmax_V6PGD", SEED_VMAX_V6PGD)),
            }
        )
        measured_rows.extend(
            _measured_metric_rows(
                label=label,
                sol=sol,
                frame=frame,
                exp_time=exp_time,
                exp_curves=exp_curves,
                teachers=net_teachers,
            )
        )
        context_rows.extend(
            _context_metric_rows(
                label=label,
                sol=sol,
                exp_time=exp_time,
                exp_curves=exp_curves,
            )
        )
        flux_metrics = _teacher_flux_metrics(
            sol=sol,
            fluxes=fluxes,
            teacher_dataset=transport_teacher,
        )
        teacher_flux_rows.extend(
            {"candidate": label, "reaction": reaction, **metric}
            for reaction, metric in flux_metrics.items()
            if reaction in TEACHER_FLUXES
        )
        teacher_window_rows.extend(
            _teacher_window_rows(label=label, frame=frame, teachers=net_teachers)
        )
        windows, attributions = _window_and_attribution_rows(frame)
        pool_window_rows.extend(windows)
        attribution_rows.extend(attributions)
        routing_rows.extend(_routing_rows(frame))
        redox_rows.append(_redox_metrics(label, sol))

    candidate_labels = [_candidate_label(scale) for scale in scales]
    assessments = _assess_candidates(
        labels=candidate_labels,
        reference_label=reference_label,
        measured_rows=measured_rows,
        context_rows=context_rows,
        teacher_flux_rows=teacher_flux_rows,
        teacher_window_rows=teacher_window_rows,
        redox_rows=redox_rows,
    )
    decision, rationale, selected = _decision(
        assessments, candidate_initialization=candidate_initialization
    )
    max_closure = max(error for case in closure_by_case.values() for error in case.values())

    timeseries_path = out_dir / "vmax_v6pgd_timeseries.csv"
    metrics_path = out_dir / "vmax_v6pgd_measured_metrics.csv"
    context_path = out_dir / "vmax_v6pgd_context_metrics.csv"
    teacher_flux_path = out_dir / "vmax_v6pgd_teacher_flux_metrics.csv"
    teacher_windows_path = out_dir / "vmax_v6pgd_net_teacher_windows.csv"
    pool_windows_path = out_dir / "vmax_v6pgd_pool_windows.csv"
    attribution_path = out_dir / "vmax_v6pgd_attribution.csv"
    routing_path = out_dir / "vmax_v6pgd_routing.csv"
    redox_path = out_dir / "vmax_v6pgd_redox_metrics.json"
    assessments_path = out_dir / "vmax_v6pgd_assessments.csv"
    plot_path = out_dir / "vmax_v6pgd_feasibility.png"
    pd.concat(frames.values(), ignore_index=True).to_csv(timeseries_path, index=False)
    pd.DataFrame(measured_rows).to_csv(metrics_path, index=False)
    pd.DataFrame(context_rows).to_csv(context_path, index=False)
    pd.DataFrame(teacher_flux_rows).to_csv(teacher_flux_path, index=False)
    pd.DataFrame(teacher_window_rows).to_csv(teacher_windows_path, index=False)
    pd.DataFrame(pool_window_rows).to_csv(pool_windows_path, index=False)
    pd.DataFrame(attribution_rows).to_csv(attribution_path, index=False)
    pd.DataFrame(routing_rows).to_csv(routing_path, index=False)
    redox_path.write_text(json.dumps(_jsonable(redox_rows), indent=2), encoding="utf-8")
    pd.DataFrame(assessments).to_csv(assessments_path, index=False)
    _plot_screen(
        frames=frames,
        screen_scales=scales,
        reference_label=reference_label,
        exp_time=exp_time,
        exp_curves=exp_curves,
        net_teachers=net_teachers,
        redox_rows=redox_rows,
        out_path=plot_path,
    )

    summary = {
        "contract_type": "directed_vmax_v6pgd_feasibility_screen",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "optimization_performed": False,
        "parameters_promoted": False,
        "parameter_artifacts_generated": False,
        "default_initialization_preserved": True,
        "seed_params_path": str(seed_params_path),
        "seed_vmax_V6PGD": SEED_VMAX_V6PGD,
        "screen_scales": [float(scale) for scale in scales],
        "candidate_initialization": candidate_initialization,
        "assessment_reference_label": reference_label,
        "candidate_initial_condition_changes": (
            [] if candidate_initialization == "current" else initial_changes
        ),
        "initial_condition_changes": initial_changes,
        "case_contracts": case_contracts,
        "t_max": float(t_max),
        "timepoints": int(t_eval.size),
        "solver": {"method": method, "rtol": float(rtol), "atol": float(atol)},
        "closure_by_case": closure_by_case,
        "max_pointwise_closure_error": max_closure,
        "measured_pool_metrics": measured_rows,
        "context_metrics": context_rows,
        "teacher_flux_metrics": teacher_flux_rows,
        "net_teacher_windows": teacher_window_rows,
        "pool_windows": pool_window_rows,
        "reaction_attribution": attribution_rows,
        "routing_windows": routing_rows,
        "redox_metrics": redox_rows,
        "assessments": assessments,
        "decision": decision,
        "decision_rationale": rationale,
        "selected_fixed_case": selected,
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "report": str(out_dir / "decision_report.md"),
            "plot": str(plot_path),
            "timeseries": str(timeseries_path),
            "measured_metrics": str(metrics_path),
            "context_metrics": str(context_path),
            "teacher_flux_metrics": str(teacher_flux_path),
            "net_teacher_windows": str(teacher_windows_path),
            "pool_windows": str(pool_windows_path),
            "reaction_attribution": str(attribution_path),
            "routing": str(routing_path),
            "redox_metrics": str(redox_path),
            "assessments": str(assessments_path),
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
                "max_closure": max_closure,
                "decision": decision,
                "selected_fixed_case": selected,
                "assessments": assessments,
            },
            indent=2,
        ),
        flush=True,
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Screen fixed downward V6PGD points")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--seed-params", type=Path, default=DEFAULT_SEED_PARAMS)
    parser.add_argument("--scales", type=float, nargs="+", default=SCREEN_SCALES)
    parser.add_argument(
        "--candidate-initialization",
        choices=("current", "historical"),
        default="historical",
    )
    parser.add_argument("--t-max", type=float, default=46.0)
    parser.add_argument("--timepoints", type=int, default=361)
    parser.add_argument("--early-timepoints", type=int, default=100)
    parser.add_argument("--teacher-dense-points", type=int, default=181)
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
        candidate_initialization=args.candidate_initialization,
        t_max=args.t_max,
        timepoints=args.timepoints,
        early_timepoints=args.early_timepoints,
        teacher_dense_points=args.teacher_dense_points,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
        closure_tolerance=args.closure_tolerance,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
