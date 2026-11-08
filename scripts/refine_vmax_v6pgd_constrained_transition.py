"""Refine the finite-bound V6PGD transition with balanced PPP initialization."""

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
    / "v6pgd_constrained_transition_refinement_46d"
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
from audit_complete_ppp_fla import (  # noqa: E402
    LATENT_PPP_POOLS,
    MEASURED_PPP_POOLS,
    PPP_POOLS,
    _build_net_flux_teachers,
    _build_timeseries,
)
from diagnose_ppp_initial_conditions import (  # noqa: E402
    _historical_latent_ppp_state,
    _historical_values,
)
from diagnose_constrained_ppp_initialization import (  # noqa: E402
    CASE_BALANCED,
    LATENT_INDICES,
    NADPH_INDEX,
    NADP_INDEX,
    _case_metrics,
    _go6p_fixed_kinetic_feasibility,
    _reference_scales,
    _solve_mode,
    _window_teacher,
)
from screen_vmax_v6pgd_constrained_initialization import (  # noqa: E402
    G6P_NONINFERIORITY_TOLERANCE,
    LONG_GUARD_POOLS,
    SEED_VMAX_V6PGD,
    _assess_candidate,
    _augment_metrics,
    _candidate_params,
    _long_replay_metrics,
)


REFINEMENT_SCALES = (0.895, 0.900, 0.9025, 0.905, 0.9075)
BASELINE_SCALE = 1.0
CONTEXT_NONINFERIORITY_TOLERANCE = 0.10
PPP_NONINFERIORITY_TOLERANCE = 0.05


def _label(scale: float) -> str:
    if np.isclose(float(scale), BASELINE_SCALE):
        return "constrained_balanced_teacher__seed"
    return f"constrained_balanced_teacher__v6pgd_{float(scale):.4f}x"


def _full_horizon_guards(
    *,
    candidate: Mapping[str, Any],
    baseline: Mapping[str, Any],
    early_pass: bool,
    finite_bound_feasible: bool,
    closure_tolerance: float,
) -> dict[str, bool]:
    guards = {
        f"{pool}_noninferior_10pct": float(candidate[f"{pool}_nrmse"])
        <= (1.0 + CONTEXT_NONINFERIORITY_TOLERANCE)
        * max(float(baseline[f"{pool}_nrmse"]), 1e-30)
        for pool in LONG_GUARD_POOLS
    }
    for pool in MEASURED_PPP_POOLS:
        guards[f"{pool}_concentration_noninferior_5pct"] = float(
            candidate[f"{pool}_concentration_nrmse"]
        ) <= (1.0 + PPP_NONINFERIORITY_TOLERANCE) * max(
            float(baseline[f"{pool}_concentration_nrmse"]), 1e-30
        )
        guards[f"{pool}_teacher_noninferior_5pct"] = float(
            candidate[f"{pool}_teacher_nrmse"]
        ) <= (1.0 + PPP_NONINFERIORITY_TOLERANCE) * max(
            float(baseline[f"{pool}_teacher_nrmse"]), 1e-30
        )
    guards.update(
        {
            "early_J1_J2_pass": bool(early_pass),
            "finite_bound_GO6P_feasible": bool(finite_bound_feasible),
            "GO6P_F6P_joint_full_improves": float(
                candidate["GO6P_F6P_joint_score"]
            )
            < float(baseline["GO6P_F6P_joint_score"]),
            "PPP_positive": float(candidate["PPP_minimum"]) >= -1e-10,
            "redox_positive": float(candidate["NADP_minimum"]) >= -1e-10
            and float(candidate["NADPH_minimum"]) >= -1e-10,
            "redox_conserved": float(candidate["NADP_NADPH_max_drift"]) <= 1e-9,
            "exact_ten_pool_closure": float(
                candidate["max_pointwise_closure_error"]
            )
            <= float(closure_tolerance),
        }
    )
    return guards


def _select_full_horizon_candidate(
    assessments: Sequence[Mapping[str, Any]],
) -> str | None:
    eligible = [
        row for row in assessments if bool(row["fully_guarded_full_horizon_pass"])
    ]
    if not eligible:
        return None
    return str(
        min(
            eligible,
            key=lambda row: (
                float(row["GO6P_F6P_joint_score"]),
                abs(float(row["scale"]) - 0.90),
            ),
        )["candidate"]
    )


def _plot_refinement(
    *,
    metrics: Sequence[Mapping[str, Any]],
    assessments: Sequence[Mapping[str, Any]],
    frames: Mapping[str, pd.DataFrame],
    experimental_time: np.ndarray,
    experimental_curves: Mapping[str, np.ndarray],
    selected: str | None,
    out_path: Path,
) -> None:
    candidate_metrics = sorted(
        (row for row in metrics if float(row["scale"]) < 1.0),
        key=lambda row: float(row["scale"]),
    )
    assessment_by_label = {str(row["candidate"]): row for row in assessments}
    scales = np.asarray([row["scale"] for row in candidate_metrics], dtype=float)
    colors = [
        "#15803d"
        if assessment_by_label[str(row["candidate"])][
            "fully_guarded_full_horizon_pass"
        ]
        else "#b91c1c"
        for row in candidate_metrics
    ]
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.5), constrained_layout=True)
    axes[0, 0].plot(
        scales,
        [row["GO6P_F6P_joint_score"] for row in candidate_metrics],
        color="#111827",
        marker="o",
    )
    axes[0, 0].scatter(
        scales,
        [row["GO6P_F6P_joint_score"] for row in candidate_metrics],
        c=colors,
        s=55,
        zorder=3,
    )
    axes[0, 0].set_title("Full-horizon GO6P/F6P joint score")
    axes[0, 1].plot(
        scales,
        [row["GL6P_initial"] for row in candidate_metrics],
        color="#2563eb",
        marker="o",
    )
    axes[0, 1].axhline(2.0, color="#111827", linestyle="--")
    axes[0, 1].set_title("Constrained GL6P initial state")
    baseline = next(row for row in metrics if np.isclose(float(row["scale"]), 1.0))
    for pool, color in zip(LONG_GUARD_POOLS, ("#2563eb", "#7c3aed", "#dc2626", "#ea580c", "#0f766e", "#4d7c0f")):
        axes[0, 2].plot(
            scales,
            [
                float(row[f"{pool}_nrmse"])
                / max(float(baseline[f"{pool}_nrmse"]), 1e-30)
                for row in candidate_metrics
            ],
            marker="o",
            label=pool,
            color=color,
        )
    axes[0, 2].axhline(1.10, color="#111827", linestyle="--")
    axes[0, 2].set_title("Transfer nRMSE ratios")
    axes[0, 2].legend(frameon=False, ncol=2, fontsize=8)

    labels_to_plot = [_label(1.0)]
    if selected is not None:
        labels_to_plot.append(selected)
    else:
        labels_to_plot.append(
            str(min(candidate_metrics, key=lambda row: row["GO6P_F6P_joint_score"])["candidate"])
        )
    line_colors = ("#64748b", "#b91c1c")
    for column, pool in enumerate(("GO6P", "F6P")):
        for label, color in zip(labels_to_plot, line_colors):
            frame = frames[label]
            axes[1, column].plot(
                frame["time_day"],
                frame[pool],
                color=color,
                linewidth=1.8,
                label=label,
            )
        axes[1, column].plot(
            experimental_time,
            np.asarray(experimental_curves[pool], dtype=float),
            color="#111827",
            linestyle="--",
            linewidth=2.0,
            label="Brodbar",
        )
        axes[1, column].set_title(f"{pool} concentration, 46 days")
        axes[1, column].set_xlabel("Time (day)")
        axes[1, column].set_ylabel("mM")
        axes[1, column].legend(frameon=False, fontsize=8)
    axes[1, 2].axis("off")
    lines = [
        "Green: all local and 46-day guards pass",
        "Red: at least one guard fails",
        "",
        f"Selected: {selected}",
        "",
        "Diagnostic only",
        "No kinetic or initialization promotion",
    ]
    axes[1, 2].text(0.02, 0.95, "\n".join(lines), va="top", fontsize=11)
    for axis in axes.flat[:5]:
        axis.grid(alpha=0.22)
    for axis in axes[0, :2]:
        axis.set_xlabel("V6PGD scale")
    fig.suptitle("V6PGD finite-bound transition refinement")
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    lines = [
        "# V6PGD constrained-transition refinement",
        "",
        "## Contract",
        "",
        "- Balanced constrained initialization only; seven latent PPP states re-solved independently.",
        "- Fixed deterministic V6PGD grid; every other kinetic constant unchanged.",
        "- All candidates replayed over 46 days and ranked by the full GO6P/F6P concentration-plus-teacher score.",
        "- Diagnostic only; no parameter or initial-state promotion.",
        "",
        "## Results",
        "",
        "| Scale | GL6P(0) | GO6P conc. | GO6P teacher | F6P conc. | F6P teacher | Joint score | Full pass |",
        "|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary["ranked_candidates"]:
        lines.append(
            f"| {row['scale']:.4f} | {row['GL6P_initial']:.6g} | "
            f"{row['GO6P_concentration_nrmse']:.4f} | {row['GO6P_teacher_nrmse']:.4f} | "
            f"{row['F6P_concentration_nrmse']:.4f} | {row['F6P_teacher_nrmse']:.4f} | "
            f"{row['GO6P_F6P_joint_score']:.4f} | `{row['fully_guarded_full_horizon_pass']}` |"
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
            f"Selected diagnostic point: `{summary['selected_candidate']}`.",
            "",
            "The production seed and production initialization remain unchanged.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_refinement(
    *,
    out_dir: Path,
    seed_params_path: Path,
    scales: Sequence[float],
    early_timepoints: int,
    long_timepoints: int,
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
    experimental_time, experimental_curves = _all_experimental_curves(46.0)
    teachers = _build_net_flux_teachers(
        experimental_time,
        experimental_curves,
        dense_points=teacher_dense_points,
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
    all_scales = (BASELINE_SCALE, *tuple(float(scale) for scale in scales))
    early_metrics: list[dict[str, Any]] = []
    long_metrics: list[dict[str, Any]] = []
    solver_diagnostics: list[dict[str, Any]] = []
    early_frames: dict[str, pd.DataFrame] = {}
    long_frames: dict[str, pd.DataFrame] = {}
    states: dict[str, np.ndarray] = {}
    params_by_label: dict[str, dict[str, Any]] = {}
    feasibility: dict[str, dict[str, Any]] = {}

    for scale in all_scales:
        label = _label(scale)
        params = seed_params if np.isclose(scale, 1.0) else _candidate_params(seed_params, scale)[0]
        print(f"[v6pgd-refinement] solving {label}", flush=True)
        state, diagnostics = _solve_mode(
            mode=CASE_BALANCED,
            current_state=current_state,
            historical_state=historical_state,
            params=params,
            teacher_initial=teacher_initial,
            latent_scales=latent_scales,
            teacher_scales=teacher_scales,
            max_nfev=max_nfev,
        )
        states[label] = state
        params_by_label[label] = dict(params)
        diagnostics = {
            **diagnostics,
            "candidate": label,
            "scale": float(scale),
            "vmax_V6PGD": float(params.get("vmax_V6PGD", SEED_VMAX_V6PGD)),
        }
        solver_diagnostics.append(diagnostics)
        feasibility[label] = _go6p_fixed_kinetic_feasibility(
            state=current_state,
            params=params,
            teacher_flux=float(
                teacher_initial[list(MEASURED_PPP_POOLS).index("GO6P")]
            ),
            bounded_gl6p_max=bounded_gl6p_max,
        )
        sol, fluxes, derivatives = _simulate_and_track(
            params=params,
            t_eval=np.linspace(1.0, 2.0, int(early_timepoints)),
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
                "scale": float(scale),
                "vmax_V6PGD": float(params.get("vmax_V6PGD", SEED_VMAX_V6PGD)),
            }
        )
        early_metrics.append(row)
        early_frames[label] = frame

    early_by_label = {str(row["candidate"]): row for row in early_metrics}
    baseline_early = early_by_label[_label(1.0)]
    early_assessments: dict[str, dict[str, Any]] = {}
    for scale in scales:
        label = _label(float(scale))
        early_assessments[label] = _assess_candidate(
            row={**early_by_label[label], "mode": CASE_BALANCED},
            baseline=baseline_early,
            feasibility=feasibility[label],
            bounded_gl6p_max=bounded_gl6p_max,
            closure_tolerance=closure_tolerance,
        )

    for scale in all_scales:
        label = _label(scale)
        print(f"[v6pgd-refinement] 46-day replay {label}", flush=True)
        sol, fluxes, derivatives = _simulate_and_track(
            params=params_by_label[label],
            t_eval=np.linspace(1.0, 46.0, int(long_timepoints)),
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
        row = _long_replay_metrics(
            label=label,
            frame=frame,
            experimental_time=experimental_time,
            experimental_curves=experimental_curves,
            teachers=teachers,
        )
        row.update(
            {
                "scale": float(scale),
                "vmax_V6PGD": float(
                    params_by_label[label].get("vmax_V6PGD", SEED_VMAX_V6PGD)
                ),
                "GL6P_initial": float(states[label][LATENT_INDICES[0]]),
                "max_pointwise_closure_error": float(max(closure.values())),
            }
        )
        long_metrics.append(row)
        long_frames[label] = frame

    long_by_label = {str(row["candidate"]): row for row in long_metrics}
    baseline_long = long_by_label[_label(1.0)]
    assessments: list[dict[str, Any]] = []
    for scale in scales:
        label = _label(float(scale))
        guards = _full_horizon_guards(
            candidate=long_by_label[label],
            baseline=baseline_long,
            early_pass=bool(
                early_assessments[label]["fully_guarded_early_pass"]
            ),
            finite_bound_feasible=bool(feasibility[label]["bounded_feasible"]),
            closure_tolerance=closure_tolerance,
        )
        assessments.append(
            {
                "candidate": label,
                "scale": float(scale),
                "vmax_V6PGD": float(long_by_label[label]["vmax_V6PGD"]),
                "GO6P_F6P_joint_score": float(
                    long_by_label[label]["GO6P_F6P_joint_score"]
                ),
                "joint_score_relative_improvement": 1.0
                - float(long_by_label[label]["GO6P_F6P_joint_score"])
                / max(float(baseline_long["GO6P_F6P_joint_score"]), 1e-30),
                "early_assessment": early_assessments[label],
                "full_horizon_guards": guards,
                "fully_guarded_full_horizon_pass": bool(all(guards.values())),
            }
        )
    selected = _select_full_horizon_candidate(assessments)
    assessment_by_label = {str(row["candidate"]): row for row in assessments}
    ranked_candidates = sorted(
        (
            {
                **long_by_label[_label(float(scale))],
                "fully_guarded_full_horizon_pass": assessment_by_label[
                    _label(float(scale))
                ]["fully_guarded_full_horizon_pass"],
            }
            for scale in scales
        ),
        key=lambda row: float(row["GO6P_F6P_joint_score"]),
    )
    if selected is None:
        decision = "do not retain a refined V6PGD operating point"
        rationale = (
            "No refined point improved the full-horizon GO6P/F6P score while passing "
            "every local PPP and global transfer guard. Keep the production seed and "
            "the prior 0.90x point as diagnostic history only."
        )
    else:
        selected_row = long_by_label[selected]
        improvement = 1.0 - float(selected_row["GO6P_F6P_joint_score"]) / max(
            float(baseline_long["GO6P_F6P_joint_score"]), 1e-30
        )
        decision = "retain one refined diagnostic V6PGD operating point"
        rationale = (
            f"{selected} minimized the guarded full-horizon GO6P/F6P score and "
            f"improved it by {100.0 * improvement:.3f}% relative to the balanced seed. "
            "The point remains diagnostic because absolute G6P/F6P errors are high."
        )

    pd.DataFrame(early_metrics).to_csv(out_dir / "early_metrics.csv", index=False)
    pd.DataFrame(long_metrics).to_csv(out_dir / "full_horizon_metrics.csv", index=False)
    pd.concat(long_frames.values(), ignore_index=True).to_csv(
        out_dir / "full_horizon_timeseries.csv", index=False
    )
    (out_dir / "solver_diagnostics.json").write_text(
        json.dumps(_jsonable(solver_diagnostics), indent=2), encoding="utf-8"
    )
    (out_dir / "candidate_assessments.json").write_text(
        json.dumps(_jsonable(assessments), indent=2), encoding="utf-8"
    )
    diagnostic_candidates = {
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
                    "candidates": diagnostic_candidates,
                }
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    _plot_refinement(
        metrics=long_metrics,
        assessments=assessments,
        frames=long_frames,
        experimental_time=experimental_time,
        experimental_curves=experimental_curves,
        selected=selected,
        out_path=out_dir / "v6pgd_transition_refinement.png",
    )
    summary = {
        "contract_type": "v6pgd_constrained_transition_refinement",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "kinetic_optimization_performed": False,
        "parameters_promoted": False,
        "initial_conditions_promoted": False,
        "initialization_mode": CASE_BALANCED,
        "seed_params_path": str(seed_params_path),
        "seed_vmax_V6PGD": SEED_VMAX_V6PGD,
        "refinement_scales": [float(scale) for scale in scales],
        "changed_kinetic_constants": ["vmax_V6PGD"],
        "latent_pools_resolved": list(LATENT_PPP_POOLS),
        "measured_pools_locked": list(MEASURED_PPP_POOLS),
        "g6p_role": "noninferiority_guard_only",
        "g6p_noninferiority_tolerance": G6P_NONINFERIORITY_TOLERANCE,
        "context_noninferiority_tolerance": CONTEXT_NONINFERIORITY_TOLERANCE,
        "ppp_noninferiority_tolerance": PPP_NONINFERIORITY_TOLERANCE,
        "feasibility": feasibility,
        "solver_diagnostics": solver_diagnostics,
        "early_metrics": early_metrics,
        "long_metrics": long_metrics,
        "assessments": assessments,
        "ranked_candidates": ranked_candidates,
        "selected_candidate": selected,
        "decision": decision,
        "decision_rationale": rationale,
        "next_step": (
            "audit the residual full-horizon F6P accumulation before any PPP promotion"
            if selected is not None
            else "retain the production seed and revisit VPGLS/V6PGD structural coupling"
        ),
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "report": str(out_dir / "decision_report.md"),
            "early_metrics": str(out_dir / "early_metrics.csv"),
            "full_metrics": str(out_dir / "full_horizon_metrics.csv"),
            "timeseries": str(out_dir / "full_horizon_timeseries.csv"),
            "assessments": str(out_dir / "candidate_assessments.json"),
            "diagnostic_candidates": str(out_dir / "diagnostic_candidates.json"),
            "plot": str(out_dir / "v6pgd_transition_refinement.png"),
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
                "selected_candidate": selected,
            },
            indent=2,
        ),
        flush=True,
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Refine V6PGD near the finite constrained-GL6P boundary"
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--seed-params", type=Path, default=DEFAULT_SEED_PARAMS)
    parser.add_argument("--scales", type=float, nargs="+", default=REFINEMENT_SCALES)
    parser.add_argument("--early-timepoints", type=int, default=241)
    parser.add_argument("--long-timepoints", type=int, default=901)
    parser.add_argument("--teacher-dense-points", type=int, default=9001)
    parser.add_argument("--max-nfev", type=int, default=1500)
    parser.add_argument("--method", default="LSODA")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    parser.add_argument("--closure-tolerance", type=float, default=1e-12)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_refinement(
        out_dir=args.out_dir,
        seed_params_path=args.seed_params,
        scales=args.scales,
        early_timepoints=args.early_timepoints,
        long_timepoints=args.long_timepoints,
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
