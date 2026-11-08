"""Early-window boundary screen for fixed V6PGD capacity under historical PPP initialization."""

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
    / "vmax_v6pgd_initial_rate_boundary_J1_J2"
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
from run_glucose_utilization_fla import _nrmse  # noqa: E402
from audit_complete_ppp_fla import (  # noqa: E402
    _build_net_flux_teachers,
    _build_timeseries,
    _net_teacher_metric,
)
from diagnose_ppp_initial_conditions import (  # noqa: E402
    CASE_HISTORICAL,
    _historical_latent_ppp_state,
    _historical_values,
)
from screen_vmax_v6pgd_feasibility import (  # noqa: E402
    NADPH_INDEX,
    NADP_INDEX,
    SEED_VMAX_V6PGD,
    _candidate_params,
)


TEACHER_MATCHED_SCALE = 0.00265384504390937
BOUNDARY_SCALES = (0.010, 0.005, TEACHER_MATCHED_SCALE, 0.001)
TRACKED_POOLS = ("GO6P", "G6P", "F6P", "RU5P")


def _boundary_label(scale: float) -> str:
    return f"vmax_V6PGD_{scale:.6f}x"


def _window_teacher(
    teachers: Mapping[str, Any], pool: str, start: float, end: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    time = np.asarray(teachers["dense_timepoints"], dtype=float)
    mask = (time >= float(start)) & (time <= float(end))
    curve = teachers["curves"][pool]
    return (
        time[mask],
        np.asarray(curve["dense_concentration"], dtype=float)[mask],
        np.asarray(curve["dense_net_flux"], dtype=float)[mask],
    )


def _case_metrics(
    label: str,
    frame: pd.DataFrame,
    teachers: Mapping[str, Any],
) -> dict[str, Any]:
    teacher_time, teacher_concentration, teacher_flux = _window_teacher(
        teachers, "GO6P", 1.0, 2.0
    )
    model_time = frame["time_day"].to_numpy(dtype=float)
    model_concentration = np.interp(
        teacher_time, model_time, frame["GO6P"].to_numpy(dtype=float)
    )
    model_flux = np.interp(
        teacher_time,
        model_time,
        frame["dGO6P_dt_effective_flux"].to_numpy(dtype=float),
    )
    concentration = _nrmse(model_concentration, teacher_concentration)
    result: dict[str, Any] = {
        "candidate": label,
        "GO6P_concentration_nrmse": float(concentration["nrmse"]),
        "GO6P_teacher": _net_teacher_metric(model_flux, teacher_flux),
        "GO6P_initial": float(frame["GO6P"].iloc[0]),
        "GO6P_final": float(frame["GO6P"].iloc[-1]),
        "GO6P_minimum": float(frame["GO6P"].min()),
        "VPGLS_initial": float(frame["VPGLS"].iloc[0]),
        "V6PGD_initial": float(frame["V6PGD"].iloc[0]),
        "dGO6P_initial": float(frame["dGO6P_dt_effective_flux"].iloc[0]),
        "teacher_dGO6P_initial": float(teacher_flux[0]),
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
    for pool in TRACKED_POOLS:
        result[f"{pool}_final"] = float(frame[pool].iloc[-1])
        result[f"{pool}_minimum"] = float(frame[pool].min())
    return result


def _assess(
    metrics: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], str, str | None]:
    reference = next(row for row in metrics if row["candidate"] == CASE_HISTORICAL)
    reference_teacher = float(reference["GO6P_teacher"]["nrmse"])
    reference_concentration = float(reference["GO6P_concentration_nrmse"])
    assessments: list[dict[str, Any]] = []
    for row in metrics:
        if row["candidate"] == CASE_HISTORICAL:
            continue
        teacher_improvement = 1.0 - float(row["GO6P_teacher"]["nrmse"]) / max(
            reference_teacher, 1e-30
        )
        concentration_improvement = 1.0 - float(
            row["GO6P_concentration_nrmse"]
        ) / max(reference_concentration, 1e-30)
        sign_agreement = float(row["GO6P_teacher"]["sign_agreement"])
        pool_retained = float(row["GO6P_minimum"]) > 0.0
        redox_valid = (
            float(row["NADP_minimum"]) >= -1e-10
            and float(row["NADPH_minimum"]) >= -1e-10
            and float(row["NADP_NADPH_max_drift"]) <= 1e-9
        )
        locally_feasible = (
            teacher_improvement >= 0.50
            and concentration_improvement >= 0.20
            and sign_agreement >= 0.80
            and pool_retained
            and redox_valid
        )
        assessments.append(
            {
                "candidate": row["candidate"],
                "GO6P_teacher_relative_improvement": teacher_improvement,
                "GO6P_concentration_relative_improvement": concentration_improvement,
                "GO6P_teacher_sign_agreement": sign_agreement,
                "GO6P_final": float(row["GO6P_final"]),
                "dGO6P_initial": float(row["dGO6P_initial"]),
                "pool_retained": pool_retained,
                "redox_valid": redox_valid,
                "locally_feasible": locally_feasible,
            }
        )
    feasible = [row for row in assessments if row["locally_feasible"]]
    if not feasible:
        return assessments, "reject fixed-capacity V6PGD locally", None
    selected = min(
        feasible,
        key=lambda row: abs(
            float(row["dGO6P_initial"])
            - float(reference["teacher_dGO6P_initial"])
        ),
    )
    return assessments, "advance one fixed point to the 46-day transfer replay", str(
        selected["candidate"]
    )


def _plot(
    frames: Mapping[str, pd.DataFrame],
    teachers: Mapping[str, Any],
    out_path: Path,
) -> None:
    teacher_time, teacher_concentration, teacher_flux = _window_teacher(
        teachers, "GO6P", 1.0, 2.0
    )
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True)
    for label, frame in frames.items():
        width = 2.5 if label == CASE_HISTORICAL else 1.8
        axes[0].plot(frame["time_day"], frame["GO6P"], label=label, linewidth=width)
        axes[1].plot(
            frame["time_day"],
            frame["dGO6P_dt_effective_flux"],
            label=label,
            linewidth=width,
        )
    axes[0].plot(teacher_time, teacher_concentration, "k--", linewidth=2.2, label="Brodbar PCHIP")
    axes[1].plot(teacher_time, teacher_flux, "k--", linewidth=2.2, label="Brodbar teacher")
    axes[0].set(title="GO6P concentration", xlabel="Time (day)", ylabel="mM")
    axes[1].set(title="GO6P net flux", xlabel="Time (day)", ylabel="mM/day")
    for axis in axes:
        axis.grid(alpha=0.25)
    handles, labels = axes[1].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=3, fontsize=8)
    fig.suptitle("V6PGD initial-rate boundary screen (J1-J2)")
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    lines = [
        "# V6PGD initial-rate boundary screen",
        "",
        f"- Horizon: J1-J2 (`{summary['timepoints']}` points).",
        f"- Maximum ten-pool closure error: `{summary['max_pointwise_closure_error']:.3e}` mM/day.",
        "- Historical latent-PPP initialization; only `vmax_V6PGD` changes.",
        "- Diagnostic only; no optimization or promotion.",
        "",
        "| Candidate | Teacher improvement | Concentration improvement | Sign agreement | GO6P final | Initial dGO6P | Locally feasible |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary["assessments"]:
        lines.append(
            f"| `{row['candidate']}` | {100 * row['GO6P_teacher_relative_improvement']:.1f}% | "
            f"{100 * row['GO6P_concentration_relative_improvement']:.1f}% | "
            f"{100 * row['GO6P_teacher_sign_agreement']:.1f}% | {row['GO6P_final']:.6g} | "
            f"{row['dGO6P_initial']:.6g} | `{row['locally_feasible']}` |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"**`{summary['decision']}`**",
            "",
            f"Selected fixed case: `{summary['selected_fixed_case']}`.",
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
    method: str,
    rtol: float,
    atol: float,
    closure_tolerance: float,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    seed_params = _load_params(seed_params_path)
    current_x0 = np.asarray(load_initial_conditions(), dtype=float)
    historical_x0, initial_changes = _historical_latent_ppp_state(
        current_x0, _historical_values()
    )
    exp_time, exp_curves = _all_experimental_curves(46.0)
    teachers = _build_net_flux_teachers(
        exp_time, exp_curves, dense_points=teacher_dense_points
    )
    t_eval = np.linspace(1.0, 2.0, int(timepoints))
    specs: list[tuple[str, dict[str, Any], list[str]]] = [
        (CASE_HISTORICAL, dict(seed_params), [])
    ]
    for scale in scales:
        params, changed = _candidate_params(seed_params, scale)
        specs.append((_boundary_label(scale), params, changed))

    frames: dict[str, pd.DataFrame] = {}
    metrics: list[dict[str, Any]] = []
    contracts: list[dict[str, Any]] = []
    closure_by_case: dict[str, dict[str, float]] = {}
    for label, params, changed in specs:
        print(f"[v6pgd-boundary] simulating {label}", flush=True)
        sol, fluxes, derivatives = _simulate_and_track(
            params=params,
            t_eval=t_eval,
            method=method,
            rtol=rtol,
            atol=atol,
            x0_override=historical_x0,
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
        metrics.append(_case_metrics(label, frame, teachers))
        contracts.append(
            {
                "candidate": label,
                "changed_kinetic_constants": changed,
                "vmax_V6PGD": float(params.get("vmax_V6PGD", SEED_VMAX_V6PGD)),
            }
        )

    assessments, decision, selected = _assess(metrics)
    max_closure = max(
        value for case_values in closure_by_case.values() for value in case_values.values()
    )
    timeseries_path = out_dir / "vmax_v6pgd_boundary_timeseries.csv"
    metrics_path = out_dir / "vmax_v6pgd_boundary_metrics.json"
    assessments_path = out_dir / "vmax_v6pgd_boundary_assessments.csv"
    plot_path = out_dir / "vmax_v6pgd_boundary.png"
    pd.concat(frames.values(), ignore_index=True).to_csv(timeseries_path, index=False)
    metrics_path.write_text(json.dumps(_jsonable(metrics), indent=2), encoding="utf-8")
    pd.DataFrame(assessments).to_csv(assessments_path, index=False)
    _plot(frames, teachers, plot_path)
    summary = {
        "contract_type": "vmax_v6pgd_initial_rate_boundary_screen",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "optimization_performed": False,
        "parameters_promoted": False,
        "default_initialization_preserved": True,
        "seed_params_path": str(seed_params_path),
        "historical_initial_condition_changes": initial_changes,
        "screen_scales": [float(scale) for scale in scales],
        "teacher_matched_scale": TEACHER_MATCHED_SCALE,
        "timepoints": int(timepoints),
        "case_contracts": contracts,
        "closure_by_case": closure_by_case,
        "max_pointwise_closure_error": max_closure,
        "metrics": metrics,
        "assessments": assessments,
        "decision": decision,
        "selected_fixed_case": selected,
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "report": str(out_dir / "decision_report.md"),
            "plot": str(plot_path),
            "timeseries": str(timeseries_path),
            "metrics": str(metrics_path),
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
                "decision": decision,
                "selected_fixed_case": selected,
                "max_closure": max_closure,
                "assessments": assessments,
            },
            indent=2,
        ),
        flush=True,
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Screen the J1-J2 V6PGD capacity boundary")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--seed-params", type=Path, default=DEFAULT_SEED_PARAMS)
    parser.add_argument("--scales", type=float, nargs="+", default=BOUNDARY_SCALES)
    parser.add_argument("--timepoints", type=int, default=241)
    parser.add_argument("--teacher-dense-points", type=int, default=9001)
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
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
        closure_tolerance=args.closure_tolerance,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
