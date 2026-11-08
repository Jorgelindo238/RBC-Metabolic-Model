"""Controlled replay of historical latent PPP initial conditions.

The current Brodbar initialization uses measured day-one concentrations when
available and a generic 1 mM fallback otherwise. This diagnostic replaces
only the seven unmeasured PPP pools with values from
Initial_conditions_JA_Final.xls. Kinetics and all measured initial states are
held fixed.
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
    ROOT / "Simulations" / "brodbar" / "hermes" / "ppp_initial_condition_diagnostic_46d"
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
)
from run_glucose_utilization_fla import _build_lactate_teacher_dataset  # noqa: E402
from screen_km_adp_atp_production import _teacher_flux_metrics  # noqa: E402
from audit_investment_phase_flux_matching import _time_grid  # noqa: E402
from audit_complete_ppp_fla import (  # noqa: E402
    CONTEXT_POOLS,
    HISTORICAL_INITIAL_CONDITIONS,
    LATENT_PPP_POOLS,
    MEASURED_PPP_POOLS,
    _build_net_flux_teachers,
    _build_timeseries,
    _context_metric_rows,
    _measured_metric_rows,
    _routing_rows,
    _teacher_window_rows,
    _window_and_attribution_rows,
)


CASE_CURRENT = "current_generic_latent_ppp"
CASE_HISTORICAL = "historical_JA_latent_ppp"
TEACHER_FLUXES = ("VEGLC", "VELAC", "VLDH")


def _historical_values(path: Path = HISTORICAL_INITIAL_CONDITIONS) -> dict[str, float]:
    frame = pd.read_excel(path, sheet_name=0, header=None)
    return {
        str(name).strip().upper(): float(value)
        for name, value in zip(frame.iloc[:, 0], frame.iloc[:, 1])
        if pd.notna(name) and pd.notna(value) and str(name).strip().upper() != "METABOLITE"
    }


def _historical_latent_ppp_state(
    current: np.ndarray,
    historical: Mapping[str, float],
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    current = np.asarray(current, dtype=float)
    corrected = current.copy()
    changes: list[dict[str, Any]] = []
    for pool in LATENT_PPP_POOLS:
        if pool not in historical:
            raise KeyError(f"Historical initial conditions are missing {pool}")
        index = int(BRODBAR_METABOLITE_MAP[pool])
        before = float(corrected[index])
        after = float(historical[pool])
        corrected[index] = after
        changes.append(
            {
                "pool": pool,
                "state_index": index,
                "current_initial_mM": before,
                "historical_initial_mM": after,
                "fold_change": after / max(abs(before), 1e-30),
            }
        )
    expected = {int(BRODBAR_METABOLITE_MAP[pool]) for pool in LATENT_PPP_POOLS}
    actual = set(np.flatnonzero(np.abs(corrected - current) > 1e-15).tolist())
    if actual != expected:
        raise RuntimeError(f"Initial-condition contract failed: changed={actual}, expected={expected}")
    return corrected, changes


def _rows_by_key(
    rows: Sequence[Mapping[str, Any]], *keys: str
) -> dict[tuple[str, ...], Mapping[str, Any]]:
    return {tuple(str(row[key]) for key in keys): row for row in rows}


def _guard_reasons(
    measured_rows: Sequence[Mapping[str, Any]],
    context_rows: Sequence[Mapping[str, Any]],
    teacher_flux_rows: Sequence[Mapping[str, Any]],
) -> list[str]:
    measured = _rows_by_key(measured_rows, "candidate", "pool")
    context = _rows_by_key(context_rows, "candidate", "pool")
    teacher = _rows_by_key(teacher_flux_rows, "candidate", "reaction")
    reasons: list[str] = []
    for pool in MEASURED_PPP_POOLS:
        seed = measured[(CASE_CURRENT, pool)]
        candidate = measured[(CASE_HISTORICAL, pool)]
        if float(candidate["concentration_nrmse"]) > float(seed["concentration_nrmse"]) * 1.05 + 0.01:
            reasons.append(f"{pool} concentration nRMSE guard")
        if abs(float(candidate["concentration_endpoint_error"])) > abs(
            float(seed["concentration_endpoint_error"])
        ) * 1.10 + 0.02:
            reasons.append(f"{pool} endpoint guard")
    relative_limits = {
        "EGLC": 1.03,
        "ELAC": 1.05,
        "GLC": 1.05,
        "F16BP": 1.10,
        "LAC": 1.05,
        "PEP": 1.05,
        "ATP": 1.10,
    }
    for pool, limit in relative_limits.items():
        seed = context[(CASE_CURRENT, pool)]
        candidate = context[(CASE_HISTORICAL, pool)]
        if float(candidate["nrmse"]) > float(seed["nrmse"]) * limit + 0.01:
            reasons.append(f"{pool} nRMSE guard")
        if abs(float(candidate["endpoint_error"])) > abs(float(seed["endpoint_error"])) * 1.10 + 0.02:
            reasons.append(f"{pool} endpoint guard")
    if float(context[(CASE_HISTORICAL, "ATP")]["simulated_final"]) < float(
        context[(CASE_CURRENT, "ATP")]["simulated_final"]
    ) * 0.95:
        reasons.append("ATP endpoint below 95% of current initialization")
    for reaction in TEACHER_FLUXES:
        seed = teacher[(CASE_CURRENT, reaction)]
        candidate = teacher[(CASE_HISTORICAL, reaction)]
        if float(candidate["nrmse"]) > float(seed["nrmse"]) * 1.08 + 0.01:
            reasons.append(f"{reaction} teacher-flux guard")
    return sorted(set(reasons))


def _decision(
    measured_rows: Sequence[Mapping[str, Any]],
    guard_reasons: Sequence[str],
) -> tuple[str, str, dict[str, Any]]:
    measured = _rows_by_key(measured_rows, "candidate", "pool")
    improvements = {
        pool: 1.0
        - float(measured[(CASE_HISTORICAL, pool)]["concentration_nrmse"])
        / max(float(measured[(CASE_CURRENT, pool)]["concentration_nrmse"]), 1e-30)
        for pool in MEASURED_PPP_POOLS
    }
    teacher_improvements = {
        pool: 1.0
        - float(measured[(CASE_HISTORICAL, pool)]["net_teacher_nrmse"])
        / max(float(measured[(CASE_CURRENT, pool)]["net_teacher_nrmse"]), 1e-30)
        for pool in MEASURED_PPP_POOLS
    }
    evidence = {
        "concentration_nrmse_relative_improvements": improvements,
        "net_teacher_nrmse_relative_improvements": teacher_improvements,
        "guard_reasons": list(guard_reasons),
    }
    useful = max((*improvements.values(), *teacher_improvements.values())) >= 0.05
    if not guard_reasons and useful:
        return (
            "retain historical latent PPP initialization as a candidate baseline and repeat the kinetic audit",
            "Replacing only unsupported 1 mM latent PPP defaults improves at least one measured PPP concentration or net-flux teacher by 5% while preserving every transfer guard. This establishes a better initialization candidate but does not yet promote it globally.",
            evidence,
        )
    if (
        improvements["F6P"] >= 0.10
        and teacher_improvements["F6P"] >= 0.10
        and teacher_improvements["GO6P"] <= -0.50
    ):
        return (
            "reject historical initialization alone and screen vmax_V6PGD under the historical latent-PPP context",
            "The historical latent pools substantially reduce the false F6P return transient, but expose excessive early GO6P drainage and transfer error to energy and lactate safeguards. Before testing VTAL feedback, run a directed fixed-point screen of vmax_V6PGD alone with the historical latent initialization held fixed; keep the current initialization as the default revert path.",
            evidence,
        )
    return (
        "reject historical latent PPP initialization as a standalone correction",
        "The controlled initial-condition replay does not produce a guarded >=5% PPP improvement. Keep the current initialization for continuity and return to the conditional forward-only VTAL feedback hypothesis.",
        evidence,
    )


def _plot_diagnostic(
    *,
    frames: Mapping[str, pd.DataFrame],
    exp_time: np.ndarray,
    exp_curves: Mapping[str, np.ndarray],
    net_teachers: Mapping[str, Any],
    out_path: Path,
) -> None:
    colors = {CASE_CURRENT: "#64748b", CASE_HISTORICAL: "#0f766e"}
    fig, axes = plt.subplots(3, 4, figsize=(17, 12), constrained_layout=True)
    for axis, pool in zip(axes.flat[:3], MEASURED_PPP_POOLS):
        for label, frame in frames.items():
            axis.plot(frame["time_day"], frame[pool], color=colors[label], linewidth=2.2, label=label)
        axis.scatter(exp_time, exp_curves[pool], color="#111827", s=28, zorder=5, label="Brodbar")
        axis.set_title(f"{pool} concentration")
        axis.set_xlabel("Time (days)")
        axis.set_ylabel("mM")
        axis.grid(True, alpha=0.22)
        if pool in {"G6P", "F6P"}:
            axis.set_yscale("log")
    axes.flat[3].axis("off")

    teacher_time = np.asarray(net_teachers["dense_timepoints"], dtype=float)
    for axis, pool in zip(axes.flat[4:7], MEASURED_PPP_POOLS):
        axis.plot(
            teacher_time,
            net_teachers["curves"][pool]["dense_net_flux"],
            color="#111827",
            linewidth=2.2,
            linestyle=":",
            label="Brodbar net teacher",
        )
        for label, frame in frames.items():
            axis.plot(
                frame["time_day"],
                frame[f"d{pool}_dt_effective_flux"],
                color=colors[label],
                linewidth=1.9,
                label=label,
            )
        axis.axhline(0.0, color="#111827", linewidth=0.8)
        axis.set_title(f"d{pool}/dt net flux")
        axis.set_xlabel("Time (days)")
        axis.set_ylabel("mM/day")
        axis.set_yscale("symlog", linthresh=1e-3)
        axis.grid(True, alpha=0.22)
    axes.flat[7].axis("off")

    latent_panels = ("GL6P", "RU5P", "R5P", "X5P")
    for axis, pool in zip(axes.flat[8:], latent_panels):
        for label, frame in frames.items():
            axis.plot(frame["time_day"], frame[pool], color=colors[label], linewidth=2.0, label=label)
        axis.set_title(f"{pool} latent pool")
        axis.set_xlabel("Time (days)")
        axis.set_ylabel("mM")
        axis.grid(True, alpha=0.22)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False)
    fig.suptitle("Controlled latent PPP initial-condition replay", fontsize=15)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    measured = _rows_by_key(summary["measured_pool_metrics"], "candidate", "pool")
    lines = [
        "# Historical latent PPP initial-condition diagnostic",
        "",
        "## Contract",
        "",
        f"- Generated: {summary['generated_at']}",
        f"- Horizon: `{summary['t_max']:.0f}` days.",
        "- Seed kinetic constants and irreversible PPP rate laws held fixed.",
        "- Only GL6P, RU5P, R5P, X5P, E4P, S7P, and GA3P initial concentrations changed.",
        "- G6P, GO6P, F6P, and every other measured initial concentration remained unchanged.",
        f"- Maximum pointwise closure error: `{summary['max_pointwise_closure_error']:.3e}` mM/day.",
        "",
        "## Initial-condition changes",
        "",
        "| Pool | Current (mM) | Historical JA (mM) | Fold |",
        "|---|---:|---:|---:|",
    ]
    for row in summary["initial_condition_changes"]:
        lines.append(
            f"| `{row['pool']}` | {row['current_initial_mM']:.6g} | "
            f"{row['historical_initial_mM']:.6g} | {row['fold_change']:.6g} |"
        )
    lines.extend(
        [
            "",
            "## Measured PPP outcomes",
            "",
            "| Pool | Current nRMSE | Historical nRMSE | Current net-teacher nRMSE | Historical net-teacher nRMSE | Current final | Historical final | Experiment |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for pool in MEASURED_PPP_POOLS:
        seed = measured[(CASE_CURRENT, pool)]
        candidate = measured[(CASE_HISTORICAL, pool)]
        lines.append(
            f"| `{pool}` | {seed['concentration_nrmse']:.6g} | {candidate['concentration_nrmse']:.6g} | "
            f"{seed['net_teacher_nrmse']:.6g} | {candidate['net_teacher_nrmse']:.6g} | "
            f"{seed['simulated_final']:.6g} | {candidate['simulated_final']:.6g} | "
            f"{seed['experimental_final']:.6g} |"
        )
    lines.extend(
        [
            "",
            "## Guards",
            "",
            f"- Failed guards: `{'; '.join(summary['guard_reasons']) or 'none'}`.",
            "",
            "## Decision",
            "",
            f"**`{summary['decision']}`**",
            "",
            summary["decision_rationale"],
            "",
            "No kinetic or promoted parameter file was generated.",
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
    params = _load_params(seed_params_path)
    current_x0 = np.asarray(load_initial_conditions(), dtype=float)
    corrected_x0, changes = _historical_latent_ppp_state(
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

    frames: dict[str, pd.DataFrame] = {}
    measured_rows: list[dict[str, Any]] = []
    context_rows: list[dict[str, Any]] = []
    teacher_flux_rows: list[dict[str, Any]] = []
    window_rows: list[dict[str, Any]] = []
    attribution_rows: list[dict[str, Any]] = []
    routing_rows: list[dict[str, Any]] = []
    teacher_window_rows: list[dict[str, Any]] = []
    closure_by_case: dict[str, dict[str, float]] = {}
    for label, x0 in ((CASE_CURRENT, current_x0), (CASE_HISTORICAL, corrected_x0)):
        print(f"[ppp-initialization] simulating {label}", flush=True)
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
        frames[label] = frame
        closure_by_case[label] = closure
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
        teacher_metrics = _teacher_flux_metrics(
            sol=sol,
            fluxes=fluxes,
            teacher_dataset=transport_teacher,
        )
        teacher_flux_rows.extend(
            {"candidate": label, "reaction": reaction, **metric}
            for reaction, metric in teacher_metrics.items()
            if reaction in TEACHER_FLUXES
        )
        case_windows, case_attributions = _window_and_attribution_rows(frame)
        window_rows.extend(case_windows)
        attribution_rows.extend(case_attributions)
        routing_rows.extend(_routing_rows(frame))
        teacher_window_rows.extend(
            _teacher_window_rows(label=label, frame=frame, teachers=net_teachers)
        )

    max_closure = max(error for case in closure_by_case.values() for error in case.values())
    guards = _guard_reasons(measured_rows, context_rows, teacher_flux_rows)
    decision, rationale, evidence = _decision(measured_rows, guards)

    timeseries_path = out_dir / "ppp_initial_condition_timeseries.csv"
    measured_path = out_dir / "ppp_initial_condition_measured_metrics.csv"
    context_path = out_dir / "ppp_initial_condition_context_metrics.csv"
    flux_path = out_dir / "ppp_initial_condition_teacher_flux_metrics.csv"
    windows_path = out_dir / "ppp_initial_condition_pool_windows.csv"
    attribution_path = out_dir / "ppp_initial_condition_attribution.csv"
    routing_path = out_dir / "ppp_initial_condition_routing.csv"
    teacher_windows_path = out_dir / "ppp_initial_condition_net_teacher_windows.csv"
    changes_path = out_dir / "ppp_initial_condition_changes.csv"
    plot_path = out_dir / "ppp_initial_condition_diagnostic.png"
    pd.concat(frames.values(), ignore_index=True).to_csv(timeseries_path, index=False)
    pd.DataFrame(measured_rows).to_csv(measured_path, index=False)
    pd.DataFrame(context_rows).to_csv(context_path, index=False)
    pd.DataFrame(teacher_flux_rows).to_csv(flux_path, index=False)
    pd.DataFrame(window_rows).to_csv(windows_path, index=False)
    pd.DataFrame(attribution_rows).to_csv(attribution_path, index=False)
    pd.DataFrame(routing_rows).to_csv(routing_path, index=False)
    pd.DataFrame(teacher_window_rows).to_csv(teacher_windows_path, index=False)
    pd.DataFrame(changes).to_csv(changes_path, index=False)
    _plot_diagnostic(
        frames=frames,
        exp_time=exp_time,
        exp_curves=exp_curves,
        net_teachers=net_teachers,
        out_path=plot_path,
    )

    summary = {
        "contract_type": "fixed_latent_ppp_initial_condition_diagnostic",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "optimization_performed": False,
        "kinetic_constants_changed": [],
        "parameters_promoted": False,
        "parameter_artifacts_generated": False,
        "default_initialization_preserved": True,
        "seed_params_path": str(seed_params_path),
        "historical_initial_conditions_path": str(HISTORICAL_INITIAL_CONDITIONS),
        "t_max": float(t_max),
        "timepoints": int(t_eval.size),
        "solver": {"method": method, "rtol": float(rtol), "atol": float(atol)},
        "initial_condition_changes": changes,
        "closure_by_case": closure_by_case,
        "max_pointwise_closure_error": max_closure,
        "measured_pool_metrics": measured_rows,
        "context_metrics": context_rows,
        "teacher_flux_metrics": teacher_flux_rows,
        "pool_windows": window_rows,
        "reaction_attribution": attribution_rows,
        "routing_windows": routing_rows,
        "net_teacher_windows": teacher_window_rows,
        "guard_reasons": guards,
        "decision": decision,
        "decision_rationale": rationale,
        "decision_evidence": evidence,
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "report": str(out_dir / "decision_report.md"),
            "plot": str(plot_path),
            "timeseries": str(timeseries_path),
            "measured_metrics": str(measured_path),
            "context_metrics": str(context_path),
            "teacher_flux_metrics": str(flux_path),
            "pool_windows": str(windows_path),
            "reaction_attribution": str(attribution_path),
            "routing": str(routing_path),
            "net_teacher_windows": str(teacher_windows_path),
            "changes": str(changes_path),
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
                "guards": guards,
                "decision": decision,
                "evidence": evidence,
            },
            indent=2,
        ),
        flush=True,
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay historical latent PPP initial conditions")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--seed-params", type=Path, default=DEFAULT_SEED_PARAMS)
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
