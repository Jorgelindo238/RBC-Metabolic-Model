"""Fixed 46-day diagnostic of reversible VTKL2/VTAL directionality.

The current one-way non-oxidative PPP rates remain the model default. This
runner activates the optional reversible saturation-difference family for
VTKL2 alone, VTAL alone, and both reactions together. All kinetic constants
remain fixed at the mild-feedback seed; no optimization or promotion occurs.
"""

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
    / "reversible_ppp_directionality_diagnostic_46d"
)

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from MM_calibration import EXP_TO_MODEL  # noqa: E402
from audit_investment_phase_flux_matching import (  # noqa: E402
    AUDITED_FLUXES,
    _time_grid,
    _timeseries_frame,
)
from profile_atp_consumption_sinks import (  # noqa: E402
    _all_experimental_curves,
    _changed_parameters,
)
from profile_glycolysis_flux_bottlenecks import (  # noqa: E402
    _jsonable,
    _load_params,
    _simulate_and_track,
    _time_mean,
)
from run_glucose_utilization_fla import _build_lactate_teacher_dataset, _nrmse  # noqa: E402
from screen_km_adp_atp_production import _teacher_flux_metrics  # noqa: E402


REVERSIBLE_FAMILY = "reversible_saturation_difference"
METABOLITE_TARGETS = (
    "EGLC",
    "ELAC",
    "GLC",
    "G6P",
    "F6P",
    "F16BP",
    "LAC",
    "PEP",
    "ATP",
)
TEACHER_TARGETS = ("VEGLC", "VELAC", "VLDH")
WINDOWS = (
    ("early_1_2d", 1.0, 2.0),
    ("mid_10_20d", 10.0, 20.0),
    ("late_40_46d", 40.0, 46.0),
)


def _fixed_reversible_toggles(*reactions: str) -> dict[str, Any]:
    toggles: dict[str, Any] = {}
    for reaction in reactions:
        if reaction not in {"VTKL2", "VTAL"}:
            raise ValueError(f"Unsupported reversible PPP reaction: {reaction}")
        toggles[f"kinetic_family_{reaction}"] = REVERSIBLE_FAMILY
        toggles[f"hybrid_blend_{reaction}"] = 1.0
        toggles[f"hybrid_reverse_scale_{reaction}"] = 1.0
    return toggles


CASE_TOGGLES: dict[str, dict[str, Any]] = {
    "seed_irreversible": {},
    "reversible_VTKL2": _fixed_reversible_toggles("VTKL2"),
    "reversible_VTAL": _fixed_reversible_toggles("VTAL"),
    "reversible_both": _fixed_reversible_toggles("VTKL2", "VTAL"),
}


def _case_params(
    seed_params: Mapping[str, Any], toggles: Mapping[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    params = dict(seed_params)
    params.update(toggles)
    changed = _changed_parameters(seed_params, params)
    if changed != sorted(toggles):
        raise RuntimeError(
            f"Fixed-case contract failed: changed={changed}, expected={sorted(toggles)}"
        )
    return params, changed


def _concentration_metrics(
    sol: Any,
    exp_time: np.ndarray,
    exp_curves: Mapping[str, np.ndarray],
) -> dict[str, dict[str, float]]:
    metrics: dict[str, dict[str, float]] = {}
    for name in METABOLITE_TARGETS:
        simulated = np.interp(exp_time, sol.t, sol.y[int(EXP_TO_MODEL[name]), :])
        metric = _nrmse(simulated, np.asarray(exp_curves[name], dtype=float))
        metric["final_value"] = float(simulated[-1])
        metric["experimental_final"] = float(exp_curves[name][-1])
        metrics[name] = metric
    return metrics


def _gross_balance_columns(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["G6P_gross_inflow"] = np.maximum(frame["VHK"], 0.0)
    frame["G6P_gross_outflow"] = (
        np.maximum(-frame["VHK"], 0.0)
        + np.maximum(frame["VPGI"], 0.0)
        + np.maximum(frame["VG6PDH"], 0.0)
    )
    frame["F6P_gross_inflow"] = (
        np.maximum(frame["VPGI"], 0.0)
        + np.maximum(frame["VTKL2"], 0.0)
        + np.maximum(frame["VTAL"], 0.0)
        + np.maximum(-frame["VPFK"], 0.0)
    )
    frame["F6P_gross_outflow"] = (
        np.maximum(-frame["VPGI"], 0.0)
        + np.maximum(-frame["VTKL2"], 0.0)
        + np.maximum(-frame["VTAL"], 0.0)
        + np.maximum(frame["VPFK"], 0.0)
    )
    frame["PPP_positive_F6P_return"] = np.maximum(frame["VTKL2"], 0.0) + np.maximum(
        frame["VTAL"], 0.0
    )
    frame["PPP_reverse_F6P_drain"] = np.maximum(-frame["VTKL2"], 0.0) + np.maximum(
        -frame["VTAL"], 0.0
    )
    frame["PPP_net_F6P_return"] = frame["VTKL2"] + frame["VTAL"]
    return frame


def _window_diagnostics(frame: pd.DataFrame) -> list[dict[str, Any]]:
    label = str(frame["candidate"].iloc[0])
    time = frame["time_day"].to_numpy(dtype=float)
    rows: list[dict[str, Any]] = []
    for window, start, end in WINDOWS:
        mask = (time >= start - 1e-12) & (time <= min(end, time[-1]) + 1e-12)
        if np.count_nonzero(mask) < 2:
            continue
        window_time = time[mask]
        row: dict[str, Any] = {
            "candidate": label,
            "window": window,
            "start_day": float(window_time[0]),
            "end_day": float(window_time[-1]),
            "n_timepoints": int(window_time.size),
        }
        for pool in ("G6P", "F6P"):
            inflow = frame.loc[mask, f"{pool}_gross_inflow"].to_numpy(dtype=float)
            outflow = frame.loc[mask, f"{pool}_gross_outflow"].to_numpy(dtype=float)
            concentration = frame.loc[mask, pool].to_numpy(dtype=float)
            mean_inflow = _time_mean(inflow, window_time)
            mean_outflow = _time_mean(outflow, window_time)
            row[f"{pool}_mean_gross_inflow"] = mean_inflow
            row[f"{pool}_mean_gross_outflow"] = mean_outflow
            row[f"{pool}_gross_output_input_ratio"] = mean_outflow / max(
                abs(mean_inflow), 1e-30
            )
            row[f"{pool}_mean_net_flux"] = _time_mean(
                frame.loc[mask, f"d{pool}_dt_flux"].to_numpy(dtype=float), window_time
            )
            row[f"{pool}_concentration_change"] = float(concentration[-1] - concentration[0])
            row[f"{pool}_max_abs_closure_error"] = float(
                np.max(
                    np.abs(
                        frame.loc[
                            mask, f"{pool}_pointwise_closure_error"
                        ].to_numpy(dtype=float)
                    )
                )
            )
        for reaction in AUDITED_FLUXES:
            row[f"mean_{reaction}"] = _time_mean(
                frame.loc[mask, reaction].to_numpy(dtype=float), window_time
            )
        for column in (
            "PPP_positive_F6P_return",
            "PPP_reverse_F6P_drain",
            "PPP_net_F6P_return",
        ):
            row[f"mean_{column}"] = _time_mean(
                frame.loc[mask, column].to_numpy(dtype=float), window_time
            )
        row["PPP_positive_share_of_F6P_inflow"] = row[
            "mean_PPP_positive_F6P_return"
        ] / max(abs(row["F6P_mean_gross_inflow"]), 1e-30)
        rows.append(row)
    return rows


def _directionality_summary(
    fluxes: Mapping[str, np.ndarray], time: np.ndarray
) -> dict[str, dict[str, float]]:
    time = np.asarray(time, dtype=float)
    summary: dict[str, dict[str, float]] = {}
    for reaction in ("VTKL2", "VTAL"):
        values = np.asarray(fluxes[reaction], dtype=float)
        summary[reaction] = {
            "mean_flux": _time_mean(values, time),
            "min_flux": float(np.min(values)),
            "max_flux": float(np.max(values)),
            "fraction_time_negative": float(np.mean(values < 0.0)),
            "integrated_forward_flux": float(np.trapezoid(np.maximum(values, 0.0), time)),
            "integrated_reverse_flux": float(np.trapezoid(np.maximum(-values, 0.0), time)),
        }
    return summary


def _damping_summary(frame: pd.DataFrame) -> dict[str, dict[str, float]]:
    summary: dict[str, dict[str, float]] = {}
    for pool in ("G6P", "F6P"):
        adjustment = frame[f"{pool}_nonnegative_damping_adjustment"].to_numpy(dtype=float)
        summary[pool] = {
            "max_abs_adjustment": float(np.max(np.abs(adjustment))),
            "fraction_time_active": float(np.mean(np.abs(adjustment) > 1e-15)),
        }
    return summary


def _guard_reasons(
    seed: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    closure_tolerance: float,
) -> list[str]:
    reasons: list[str] = []
    relative_nrmse_limits = {
        "EGLC": 1.03,
        "ELAC": 1.05,
        "GLC": 1.05,
        "G6P": 1.05,
        "F16BP": 1.10,
        "LAC": 1.05,
        "PEP": 1.05,
        "ATP": 1.10,
    }
    for name, limit in relative_nrmse_limits.items():
        seed_metric = seed["concentration_metrics"][name]
        candidate_metric = candidate["concentration_metrics"][name]
        if float(candidate_metric["nrmse"]) > float(seed_metric["nrmse"]) * limit + 0.01:
            reasons.append(f"{name} nRMSE guard")
        if float(candidate_metric["endpoint_error"]) > float(seed_metric["endpoint_error"]) * 1.10 + 0.02:
            reasons.append(f"{name} endpoint guard")
    if float(candidate["concentration_metrics"]["ATP"]["final_value"]) < float(
        seed["concentration_metrics"]["ATP"]["final_value"]
    ) * 0.95:
        reasons.append("ATP endpoint below 95% of seed")
    for reaction in TEACHER_TARGETS:
        seed_metric = seed["teacher_flux_metrics"][reaction]
        candidate_metric = candidate["teacher_flux_metrics"][reaction]
        if float(candidate_metric["nrmse"]) > float(seed_metric["nrmse"]) * 1.08 + 0.01:
            reasons.append(f"{reaction} teacher-flux guard")
    if float(candidate["max_pointwise_closure_error"]) > float(closure_tolerance):
        reasons.append("G6P/F6P pointwise closure guard")
    return sorted(set(reasons))


def _case_assessment(seed: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    seed_f6p = float(seed["concentration_metrics"]["F6P"]["nrmse"])
    candidate_f6p = float(candidate["concentration_metrics"]["F6P"]["nrmse"])
    f6p_improvement = 1.0 - candidate_f6p / max(seed_f6p, 1e-30)
    guards = list(candidate.get("guard_reasons", []))
    feasible = (
        not guards
        and f6p_improvement >= 0.05
        and float(candidate["concentration_metrics"]["F6P"]["endpoint_error"])
        <= float(seed["concentration_metrics"]["F6P"]["endpoint_error"])
    )
    return {
        "candidate": candidate["label"],
        "f6p_relative_nrmse_improvement": f6p_improvement,
        "guard_reasons": guards,
        "passes_all_guards": not guards,
        "fixed_hypothesis_feasible": feasible,
    }


def _decision(assessments: Sequence[Mapping[str, Any]]) -> tuple[str, str, str | None]:
    feasible = [row for row in assessments if row["fixed_hypothesis_feasible"]]
    if feasible:
        best = max(feasible, key=lambda row: float(row["f6p_relative_nrmse_improvement"]))
        label = str(best["candidate"])
        return (
            f"advance {label} to a bounded fixed-blend sensitivity screen before optimization",
            f"{label} improves F6P by {100.0 * float(best['f6p_relative_nrmse_improvement']):.1f}% while passing every transfer and closure guard. The formulation remains diagnostic and is not promoted.",
            label,
        )
    best = max(assessments, key=lambda row: float(row["f6p_relative_nrmse_improvement"]))
    label = str(best["candidate"])
    return (
        "reject the fixed reversible PPP hypothesis and retain the irreversible seed",
        f"The best fixed case was {label}, but it did not combine a >=5% F6P improvement with all transfer guards. No reversible directionality setting is promoted or optimized.",
        None,
    )


def _clean_case(payload: Mapping[str, Any]) -> dict[str, Any]:
    excluded = {"sol", "fluxes", "timeseries"}
    return {key: value for key, value in payload.items() if key not in excluded}


def _metric_rows(cases: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        for name, metric in case["concentration_metrics"].items():
            rows.append(
                {
                    "candidate": case["label"],
                    "metric_type": "concentration",
                    "target": name,
                    **metric,
                }
            )
        for name, metric in case["teacher_flux_metrics"].items():
            rows.append(
                {
                    "candidate": case["label"],
                    "metric_type": "teacher_flux",
                    "target": name,
                    **metric,
                }
            )
    return rows


def _plot_diagnostic(
    *,
    cases: Sequence[Mapping[str, Any]],
    exp_time: np.ndarray,
    exp_curves: Mapping[str, np.ndarray],
    out_path: Path,
) -> None:
    colors = {
        "seed_irreversible": "#64748b",
        "reversible_VTKL2": "#2563eb",
        "reversible_VTAL": "#b45309",
        "reversible_both": "#dc2626",
    }
    fig, axes = plt.subplots(3, 4, figsize=(17, 12), constrained_layout=True)
    concentration_panels = ("GLC", "G6P", "F6P", "F16BP", "ATP", "PEP")
    for axis, name in zip(axes.flat[:6], concentration_panels):
        idx = int(EXP_TO_MODEL[name])
        for case in cases:
            axis.plot(
                case["sol"].t,
                case["sol"].y[idx, :],
                color=colors[case["label"]],
                linewidth=2.0,
                label=case["label"],
            )
        axis.scatter(exp_time, exp_curves[name], color="#111827", s=22, zorder=4, label="Brodbar")
        axis.set_title(f"{name} concentration")
        axis.set_xlabel("Time (days)")
        axis.set_ylabel("mM")
        axis.grid(True, alpha=0.22)
        if name in {"G6P", "F6P"}:
            axis.set_yscale("log")

    for axis, reaction in zip(axes.flat[6:8], ("VTKL2", "VTAL")):
        for case in cases:
            axis.plot(
                case["sol"].t,
                case["fluxes"][reaction],
                color=colors[case["label"]],
                linewidth=2.0,
                label=case["label"],
            )
        axis.axhline(0.0, color="#111827", linewidth=0.8)
        axis.set_title(f"Signed {reaction} flux")
        axis.set_xlabel("Time (days)")
        axis.set_ylabel("mM/day")
        axis.set_yscale("symlog", linthresh=1e-3)
        axis.grid(True, alpha=0.22)

    for axis, pool in zip(axes.flat[8:10], ("G6P", "F6P")):
        for case in cases:
            frame = case["timeseries"]
            axis.plot(
                frame["time_day"],
                frame[f"{pool}_gross_inflow"],
                color=colors[case["label"]],
                linewidth=1.8,
                label=f"{case['label']} in",
            )
            axis.plot(
                frame["time_day"],
                frame[f"{pool}_gross_outflow"],
                color=colors[case["label"]],
                linewidth=1.4,
                linestyle="--",
            )
        axis.set_title(f"{pool} gross inflow/output")
        axis.set_xlabel("Time (days)")
        axis.set_ylabel("mM/day")
        axis.set_yscale("symlog", linthresh=1e-3)
        axis.grid(True, alpha=0.22)

    axis = axes.flat[10]
    targets = ("GLC", "G6P", "F6P", "F16BP", "ATP", "PEP")
    candidate_cases = list(cases[1:])
    x = np.arange(len(targets), dtype=float)
    width = 0.24
    seed = cases[0]
    for index, case in enumerate(candidate_cases):
        deltas = [
            float(case["concentration_metrics"][name]["nrmse"])
            - float(seed["concentration_metrics"][name]["nrmse"])
            for name in targets
        ]
        axis.bar(
            x + (index - 1) * width,
            deltas,
            width=width,
            color=colors[case["label"]],
            label=case["label"],
        )
    axis.axhline(0.0, color="#111827", linewidth=0.8)
    axis.set_xticks(x, targets, rotation=30, ha="right")
    axis.set_title("Candidate minus seed nRMSE")
    axis.set_ylabel("Delta nRMSE")
    axis.grid(True, axis="y", alpha=0.22)

    axis = axes.flat[11]
    selected_rows: dict[str, Mapping[str, Any]] = {}
    selected_window = ""
    for case in cases:
        rows = list(case["window_diagnostics"])
        if not rows:
            raise RuntimeError(f"No window diagnostics available for {case['label']}")
        selected = next(
            (row for row in rows if row["window"] == "late_40_46d"),
            rows[-1],
        )
        selected_rows[str(case["label"])] = selected
        selected_window = str(selected["window"])
    labels = [case["label"] for case in cases]
    ratios = [float(selected_rows[label]["F6P_gross_output_input_ratio"]) for label in labels]
    reverse = [float(selected_rows[label]["mean_PPP_reverse_F6P_drain"]) for label in labels]
    x = np.arange(len(labels), dtype=float)
    axis.bar(x - 0.18, ratios, 0.36, color="#0f766e", label="F6P output/input")
    axis.bar(x + 0.18, reverse, 0.36, color="#b45309", label="PPP reverse drain")
    axis.axhline(1.0, color="#111827", linewidth=0.8, linestyle=":")
    axis.set_xticks(x, [label.replace("reversible_", "rev ") for label in labels], rotation=28, ha="right")
    axis.set_title(f"F6P directionality: {selected_window}")
    axis.grid(True, axis="y", alpha=0.22)
    axis.legend(frameon=False, fontsize=8)

    handles, labels_legend = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels_legend, loc="upper center", ncol=5, frameon=False)
    fig.suptitle("Brodbar fixed reversible VTKL2/VTAL directionality diagnostic", fontsize=15)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    cases = {case["label"]: case for case in summary["cases"]}
    lines = [
        "# Fixed reversible VTKL2/VTAL directionality diagnostic",
        "",
        "## Contract",
        "",
        f"- Generated: {summary['generated_at']}",
        f"- Horizon: `{summary['t_max']:.0f}` days.",
        "- Seed kinetic constants held exactly fixed.",
        "- Fixed probes: VTKL2 reversible, VTAL reversible, and both reversible.",
        "- Reverse scale: `1.0`; hybrid blend: `1.0`; no fitted equilibrium constant.",
        "- Diagnostic only: no optimization or parameter promotion.",
        "",
        "## Candidate rate laws",
        "",
        "```text",
        "VTKL2 = vmax * [sat(E4P) sat(X5P) - sat(F6P) sat(GA3P)]",
        "VTAL  = vmax * [sat(GA3P) sat(S7P) - sat(F6P) sat(E4P)]",
        "```",
        "",
        "These are reversible saturation-difference probes, not Haldane-consistent thermodynamic rate laws.",
        "",
        "## Brodbar metrics",
        "",
        "| Case | GLC nRMSE | G6P nRMSE | F6P nRMSE | F16BP nRMSE | ATP nRMSE | PEP nRMSE | Max closure |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in CASE_TOGGLES:
        case = cases[label]
        metrics = case["concentration_metrics"]
        lines.append(
            f"| `{label}` | {metrics['GLC']['nrmse']:.6g} | {metrics['G6P']['nrmse']:.6g} | "
            f"{metrics['F6P']['nrmse']:.6g} | {metrics['F16BP']['nrmse']:.6g} | "
            f"{metrics['ATP']['nrmse']:.6g} | {metrics['PEP']['nrmse']:.6g} | "
            f"{case['max_pointwise_closure_error']:.3e} |"
        )
    lines.extend(
        [
            "",
            "## Directionality and guards",
            "",
        ]
    )
    for assessment in summary["assessments"]:
        case = cases[assessment["candidate"]]
        vtkl2 = case["directionality_summary"]["VTKL2"]
        vtal = case["directionality_summary"]["VTAL"]
        lines.append(
            f"- `{assessment['candidate']}`: F6P nRMSE change "
            f"`{100.0 * assessment['f6p_relative_nrmse_improvement']:+.1f}%` improvement; "
            f"VTKL2/VTAL negative-time fractions `{100.0 * vtkl2['fraction_time_negative']:.1f}%` / "
            f"`{100.0 * vtal['fraction_time_negative']:.1f}%`; guards "
            f"`{'; '.join(assessment['guard_reasons']) or 'none'}`."
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
            "The irreversible seed remains the default and can be restored by omitting the kinetic-family toggles or setting both hybrid blends to zero.",
            "",
            "No kinetic parameter file was created by this diagnostic.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_diagnostic(
    *,
    out_dir: Path,
    seed_params_path: Path,
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
    t_eval = _time_grid(t_max, timepoints, early_timepoints)
    exp_time, exp_curves = _all_experimental_curves(t_max)
    teacher_path = out_dir / "teacher_flux_dataset.json"
    teacher_dataset = _build_lactate_teacher_dataset(
        exp_time=exp_time,
        exp_curves=exp_curves,
        dense_points=teacher_dense_points,
        out_path=teacher_path,
    )

    cases: list[dict[str, Any]] = []
    timeseries_frames: list[pd.DataFrame] = []
    window_rows: list[dict[str, Any]] = []
    for label, toggles in CASE_TOGGLES.items():
        params, changed = _case_params(seed_params, toggles)
        print(f"[reversible-ppp] simulating {label}", flush=True)
        sol, fluxes, derivatives = _simulate_and_track(
            params=params,
            t_eval=t_eval,
            method=method,
            rtol=rtol,
            atol=atol,
        )
        frame, closure = _timeseries_frame(
            label=label,
            sol=sol,
            fluxes=fluxes,
            derivatives=derivatives,
            closure_tolerance=closure_tolerance,
            account_for_nonnegative_damping=True,
        )
        frame = _gross_balance_columns(frame)
        windows = _window_diagnostics(frame)
        case = {
            "label": label,
            "fixed_toggles": dict(toggles),
            "changed_configuration_keys": changed,
            "concentration_metrics": _concentration_metrics(sol, exp_time, exp_curves),
            "teacher_flux_metrics": _teacher_flux_metrics(
                sol=sol,
                fluxes=fluxes,
                teacher_dataset=teacher_dataset,
            ),
            "pointwise_closure": closure,
            "max_pointwise_closure_error": max(closure.values()),
            "directionality_summary": _directionality_summary(fluxes, np.asarray(sol.t)),
            "nonnegative_damping_summary": _damping_summary(frame),
            "window_diagnostics": windows,
            "sol": sol,
            "fluxes": fluxes,
            "timeseries": frame,
        }
        cases.append(case)
        timeseries_frames.append(frame)
        window_rows.extend(windows)

    seed = cases[0]
    for case in cases[1:]:
        case["guard_reasons"] = _guard_reasons(
            seed,
            case,
            closure_tolerance=closure_tolerance,
        )
    seed["guard_reasons"] = []
    assessments = [_case_assessment(seed, case) for case in cases[1:]]
    decision, rationale, selected_case = _decision(assessments)

    timeseries_path = out_dir / "reversible_ppp_timeseries.csv"
    windows_path = out_dir / "reversible_ppp_window_summary.csv"
    metrics_path = out_dir / "reversible_ppp_metrics.csv"
    cases_path = out_dir / "reversible_ppp_case_decisions.csv"
    plot_path = out_dir / "reversible_ppp_directionality.png"
    pd.concat(timeseries_frames, ignore_index=True).to_csv(timeseries_path, index=False)
    pd.DataFrame(window_rows).to_csv(windows_path, index=False)
    pd.DataFrame(_metric_rows(cases)).to_csv(metrics_path, index=False)
    pd.DataFrame(assessments).to_csv(cases_path, index=False)
    _plot_diagnostic(
        cases=cases,
        exp_time=exp_time,
        exp_curves=exp_curves,
        out_path=plot_path,
    )

    summary = {
        "contract_type": "fixed_reversible_ppp_directionality_diagnostic",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "optimization_performed": False,
        "kinetic_constants_changed": [],
        "parameters_promoted": False,
        "parameter_artifacts_generated": False,
        "default_model_family_preserved": True,
        "seed_params_path": str(seed_params_path),
        "t_max": float(t_max),
        "timepoints": int(t_eval.size),
        "teacher_dense_points": int(teacher_dense_points),
        "solver": {"method": method, "rtol": float(rtol), "atol": float(atol)},
        "closure_tolerance": float(closure_tolerance),
        "reversible_family": REVERSIBLE_FAMILY,
        "case_toggles": CASE_TOGGLES,
        "cases": [_clean_case(case) for case in cases],
        "assessments": assessments,
        "decision": decision,
        "decision_rationale": rationale,
        "selected_fixed_case": selected_case,
        "limitations": [
            "The reversible saturation-difference law is not Haldane-consistent.",
            "Reverse scales and blends are fixed diagnostic values, not calibrated constants.",
            "Experimental concentrations constrain net balances but do not identify unique VTKL2/VTAL fluxes.",
        ],
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "decision_report": str(out_dir / "decision_report.md"),
            "teacher_dataset": str(teacher_path),
            "timeseries_csv": str(timeseries_path),
            "window_summary_csv": str(windows_path),
            "metrics_csv": str(metrics_path),
            "case_decisions_csv": str(cases_path),
            "plot": str(plot_path),
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
                "selected_fixed_case": selected_case,
                "assessments": assessments,
                "max_closure": max(
                    float(case["max_pointwise_closure_error"]) for case in cases
                ),
            },
            indent=2,
        ),
        flush=True,
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run fixed reversible VTKL2/VTAL directionality probes"
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--seed-params", type=Path, default=DEFAULT_SEED_PARAMS)
    parser.add_argument("--t-max", type=float, default=46.0)
    parser.add_argument("--timepoints", type=int, default=361)
    parser.add_argument("--early-timepoints", type=int, default=100)
    parser.add_argument("--teacher-dense-points", type=int, default=96)
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
