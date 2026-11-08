"""Evaluate the mapped VAMPD1 storage-decay point in the full ODE."""

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
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
DEFAULT_MAP = ROOT / "output" / "vampd1_storage_decay_map" / "summary.json"
DEFAULT_ANCHOR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "vmax_vampd1_vaprt_zero_screen_J1_J46"
    / "summary.json"
)
DEFAULT_OUT_DIR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "vampd1_storage_decay_full_ode_J1_J46"
)
BASELINE_LABEL = "VAMPD1_constant_anchor"
CANDIDATE_LABEL = "VAMPD1_storage_decay"
STRICT_LABEL = "VAMPD1_storage_decay_strict"
WINDOWS = ((1.0, 11.0), (11.0, 22.0), (22.0, 46.0))
for path in (str(SRC), str(SCRIPTS)):
    if path not in sys.path:
        sys.path.insert(0, path)

from equadiff_brodbar import MODEL_NETWORK_VERSION  # noqa: E402
from evaluate_brodbar_candidate_full_panel import _load_brodbar_panel  # noqa: E402
from fla_integrated_flux import build_integrated_flux_targets, integrated_flux_nrmse  # noqa: E402
from fla_validation_v2 import CandidateEvidence, evaluate_candidate  # noqa: E402
from screen_amp_nucleotidase_fixed_purine import (  # noqa: E402
    PURINE_STATES,
    _build_anchor,
    _simulate_candidate,
)


def _relative_degradation(candidate: float, baseline: float) -> float:
    return float((candidate - baseline) / max(abs(baseline), 1e-12))


def _vampd1_teachers(
    *,
    frame: pd.DataFrame,
    exp_time: np.ndarray,
    curves: Mapping[str, np.ndarray],
) -> dict[str, Any]:
    time = frame["time_day"].to_numpy(dtype=float)
    vampd1 = frame["VAMPD1"].to_numpy(dtype=float)
    imp_known = (
        frame["VHGPRT1"].to_numpy(dtype=float)
        - frame["VADSS"].to_numpy(dtype=float)
        - frame["VIMPH"].to_numpy(dtype=float)
        - frame["Vnucleo2"].to_numpy(dtype=float)
    )
    total_known = (
        frame["VAK2"].to_numpy(dtype=float)
        - frame["VSAM"].to_numpy(dtype=float)
        + frame["VADSL"].to_numpy(dtype=float)
        + frame["VAPRT"].to_numpy(dtype=float)
    )
    total_values = sum(
        np.asarray(curves[name], dtype=float) for name in ("ATP", "ADP", "AMP")
    )
    imp_targets = build_integrated_flux_targets(
        measurement_time=exp_time,
        measurement_values=np.asarray(curves["IMP"], dtype=float),
        dense_time=time,
        known_rate=imp_known,
        model_unknown_rate=vampd1,
        unknown_stoichiometric_coefficient=1.0,
        windows=WINDOWS,
    )
    total_targets = build_integrated_flux_targets(
        measurement_time=exp_time,
        measurement_values=total_values,
        dense_time=time,
        known_rate=total_known,
        model_unknown_rate=vampd1,
        unknown_stoichiometric_coefficient=-1.0,
        windows=WINDOWS,
    )
    imp_required = np.asarray(
        [target.required_unknown_flux_integral_mM for target in imp_targets]
    )
    total_required = np.asarray(
        [target.required_unknown_flux_integral_mM for target in total_targets]
    )
    compatibility_scale = max(
        float(np.mean(np.abs(np.concatenate([imp_required, total_required])))),
        0.05,
    )
    disagreement = float(
        np.sqrt(np.mean((imp_required - total_required) ** 2))
        / compatibility_scale
    )
    return {
        "IMP_nrmse": integrated_flux_nrmse(imp_targets),
        "adenylate_nrmse": integrated_flux_nrmse(total_targets),
        "combined_nrmse": float(
            np.sqrt(
                (
                    integrated_flux_nrmse(imp_targets) ** 2
                    + integrated_flux_nrmse(total_targets) ** 2
                )
                / 2.0
            )
        ),
        "teacher_disagreement_nrmse": disagreement,
        "teachers_sign_compatible": bool(
            np.all(imp_required >= 0.0) and np.all(total_required >= 0.0)
        ),
        "IMP_windows": [target.to_dict() for target in imp_targets],
        "adenylate_windows": [target.to_dict() for target in total_targets],
    }


def _primary_concentration_score(metrics: Mapping[str, Any]) -> float:
    return float(
        np.sqrt(
            (
                metrics["adenylate_total"]["nrmse"] ** 2
                + metrics["state_metrics"]["IMP"]["nrmse"] ** 2
            )
            / 2.0
        )
    )


def _strict_invariance(
    standard: pd.DataFrame,
    strict: pd.DataFrame,
    standard_metrics: Mapping[str, Any],
    strict_metrics: Mapping[str, Any],
) -> dict[str, Any]:
    comparisons = {}
    for name in ("ATP", "ADP", "AMP", "IMP", "VAMPD1"):
        reference = standard[name].to_numpy(dtype=float)
        candidate = strict[name].to_numpy(dtype=float)
        scale = max(float(np.mean(np.abs(reference))), 0.01)
        comparisons[name] = float(np.max(np.abs(reference - candidate)) / scale)
    maximum = max(comparisons.values())
    decision_metrics = {
        "adenylate_total_nrmse": (
            standard_metrics["adenylate_total"]["nrmse"],
            strict_metrics["adenylate_total"]["nrmse"],
        ),
        "IMP_nrmse": (
            standard_metrics["state_metrics"]["IMP"]["nrmse"],
            strict_metrics["state_metrics"]["IMP"]["nrmse"],
        ),
        "integrated_flux_combined_nrmse": (
            standard_metrics["VAMPD1_integrated_teachers"]["combined_nrmse"],
            strict_metrics["VAMPD1_integrated_teachers"]["combined_nrmse"],
        ),
        "adenylate_endpoint_error": (
            standard_metrics["adenylate_total"]["endpoint_error_mM"],
            strict_metrics["adenylate_total"]["endpoint_error_mM"],
        ),
        "IMP_endpoint_error": (
            standard_metrics["state_metrics"]["IMP"]["endpoint_error_mM"],
            strict_metrics["state_metrics"]["IMP"]["endpoint_error_mM"],
        ),
    }
    decision_differences = {
        name: float(abs(strict_value - standard_value) / max(abs(standard_value), 0.01))
        for name, (standard_value, strict_value) in decision_metrics.items()
    }
    decision_maximum = max(decision_differences.values())
    return {
        "per_target_max_normalized_difference": comparisons,
        "maximum_normalized_trajectory_difference": maximum,
        "decision_metric_relative_differences": decision_differences,
        "maximum_decision_metric_relative_difference": decision_maximum,
        "pass": bool(decision_maximum <= 0.01),
    }


def _plot(
    baseline: pd.DataFrame,
    candidate: pd.DataFrame,
    strict: pd.DataFrame,
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(15.5, 8.5), constrained_layout=True)
    series = (
        (baseline, "constant anchor", "#457b9d", "-"),
        (candidate, "storage decay", "#d1495b", "-"),
        (strict, "storage decay strict", "#2a9d8f", ":"),
    )
    for frame, label, color, style in series:
        total = frame["ATP"] + frame["ADP"] + frame["AMP"]
        axes[0, 0].plot(frame["time_day"], total, color=color, ls=style, lw=2, label=label)
        axes[0, 1].plot(frame["time_day"], frame["IMP"], color=color, ls=style, lw=2, label=label)
        axes[0, 2].plot(frame["time_day"], frame["VAMPD1"], color=color, ls=style, lw=2, label=label)
        axes[1, 0].plot(frame["time_day"], frame["AMP"], color=color, ls=style, lw=2, label=label)
        axes[1, 1].plot(frame["time_day"], frame["HYPX"] + frame["EHYPX"], color=color, ls=style, lw=2, label=label)
        axes[1, 2].plot(frame["time_day"], frame["PRPP"], color=color, ls=style, lw=2, label=label)
    axes[0, 0].plot(baseline["time_day"], baseline["adenylate_total_teacher"], "k--", lw=2, label="Brodbar")
    axes[0, 1].plot(baseline["time_day"], baseline["IMP_teacher"], "k--", lw=2)
    axes[1, 0].plot(baseline["time_day"], baseline["AMP_teacher"], "k--", lw=2)
    axes[1, 1].plot(baseline["time_day"], baseline["HYPX_teacher"] + baseline["EHYPX_teacher"], "k--", lw=2)
    titles = ("ATP + ADP + AMP", "IMP", "VAMPD1", "AMP", "HYPX + EHYPX", "PRPP")
    for axis, title in zip(axes.flat, titles):
        axis.set_title(title)
        axis.set_xlabel("Storage day")
        axis.grid(alpha=0.2)
    axes[0, 0].legend(fontsize=8)
    axes[0, 1].set_ylabel("Concentration (mM)")
    axes[0, 2].set_ylabel("Flux (mM/day)")
    for axis in axes[1, :]:
        axis.set_ylabel("Concentration (mM)")
    fig.suptitle("Full ODE evaluation of VAMPD1 storage-activity decay", fontsize=15)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def run(
    *,
    map_summary: Path,
    anchor_summary: Path,
    out_dir: Path,
    points: int,
) -> dict[str, Any]:
    mapping = json.loads(map_summary.read_text(encoding="utf-8"))
    selected = mapping["selected_fixed_state_row"]
    state, anchor_params, seed_path, anchor_vampd1 = _build_anchor(anchor_summary)
    anchor_params = dict(anchor_params)
    anchor_params["purine_structure_mode"] = "legacy"
    anchor_params["vmax_VAMP_NT"] = 0.0
    anchor_params["kinetic_family_VAMPD1"] = "mm"
    candidate_params = dict(anchor_params)
    candidate_params.update(
        {
            "vmax_VAMPD1": float(selected["vmax_VAMPD1_initial"]),
            "kinetic_family_VAMPD1": "storage_activity_decay",
            "storage_decay_VAMPD1": float(selected["storage_decay_VAMPD1_per_day"]),
        }
    )
    exp_time, curves, _order, _indices, unmapped = _load_brodbar_panel()
    time = np.unique(np.concatenate([np.linspace(1.0, 46.0, points), exp_time]))
    frames: dict[str, pd.DataFrame] = {}
    metrics: dict[str, dict[str, Any]] = {}
    specifications = (
        (BASELINE_LABEL, anchor_params, "BDF", 3e-4, 1e-6),
        (CANDIDATE_LABEL, candidate_params, "BDF", 3e-4, 1e-6),
        (STRICT_LABEL, candidate_params, "BDF", 1e-7, 1e-9),
    )
    for label, params, method, rtol, atol in specifications:
        print(f"[VAMPD1-decay] replay {label}", flush=True)
        frames[label], metrics[label] = _simulate_candidate(
            label=label,
            state=state,
            params=params,
            time=time,
            exp_time=exp_time,
            curves=curves,
            method=method,
            rtol=rtol,
            atol=atol,
            closure_tolerance=1e-7,
        )
        metrics[label]["VAMPD1_integrated_teachers"] = _vampd1_teachers(
            frame=frames[label], exp_time=exp_time, curves=curves
        )

    baseline = metrics[BASELINE_LABEL]
    candidate = metrics[CANDIDATE_LABEL]
    strict_check = _strict_invariance(
        frames[CANDIDATE_LABEL],
        frames[STRICT_LABEL],
        metrics[CANDIDATE_LABEL],
        metrics[STRICT_LABEL],
    )
    primary_baseline = _primary_concentration_score(baseline)
    primary_candidate = _primary_concentration_score(candidate)
    flux_baseline = baseline["VAMPD1_integrated_teachers"]["combined_nrmse"]
    flux_candidate = candidate["VAMPD1_integrated_teachers"]["combined_nrmse"]
    protected = tuple(name for name in PURINE_STATES if name not in {"IMP"})
    protected_degradation = max(
        _relative_degradation(
            candidate["state_metrics"][name]["nrmse"],
            baseline["state_metrics"][name]["nrmse"],
        )
        for name in protected
    )
    panel_mean_degradation = _relative_degradation(
        candidate["whole_panel_mean_nrmse"], baseline["whole_panel_mean_nrmse"]
    )
    panel_median_degradation = _relative_degradation(
        candidate["whole_panel_median_nrmse"], baseline["whole_panel_median_nrmse"]
    )
    teachers = candidate["VAMPD1_integrated_teachers"]
    teacher_compatible = bool(
        teachers["teachers_sign_compatible"]
        and teachers["teacher_disagreement_nrmse"] <= 0.25
    )
    endpoints_improve = bool(
        abs(candidate["adenylate_total"]["endpoint_error_mM"])
        < abs(baseline["adenylate_total"]["endpoint_error_mM"])
        and abs(candidate["state_metrics"]["IMP"]["endpoint_error_mM"])
        < abs(baseline["state_metrics"]["IMP"]["endpoint_error_mM"])
    )
    flux_channels_improve = bool(
        candidate["VAMPD1_integrated_teachers"]["IMP_nrmse"]
        < baseline["VAMPD1_integrated_teachers"]["IMP_nrmse"]
        and candidate["VAMPD1_integrated_teachers"]["adenylate_nrmse"]
        < baseline["VAMPD1_integrated_teachers"]["adenylate_nrmse"]
    )
    evidence = CandidateEvidence(
        candidate_id=CANDIDATE_LABEL,
        training_datasets=("brodbar_J1_J46",),
        temporal_validation_datasets=(),
        external_validation_datasets=(),
        data_contract_complete=False,  # Raw endpoint provenance and units remain unresolved.
        exact_balance_max_error_mM_per_day=candidate["closures"]["max_abs_closure_error"],
        minimum_state_mM=candidate["minimum_state_mM"],
        minimum_state_measured_before_clipping=candidate.get("minimum_state_measured_before_clipping"),
        continuous_unforced_replay=True,
        absolute_target_nrmse=candidate["whole_panel_per_metabolite_nrmse"],
        independent_teachers_compatible=teacher_compatible,
        sensitivity_block_identifiable=bool(
            mapping["sensitivity_diagnostics"]["identifiable"]
        ),
        primary_trajectory_baseline=primary_baseline,
        primary_trajectory_candidate=primary_candidate,
        primary_flux_baseline=flux_baseline,
        primary_flux_candidate=flux_candidate,
        all_primary_endpoints_improve=endpoints_improve,
        all_primary_slopes_improve=flux_channels_improve,
        max_protected_nrmse_degradation=protected_degradation,
        panel_mean_nrmse_degradation=panel_mean_degradation,
        panel_median_nrmse_degradation=panel_median_degradation,
        strict_solver_invariant=bool(strict_check["pass"]),
        temporal_holdout_improves=None,
        external_holdout_improves=None,
        complexity_supported_by_prediction=None,
    )
    validation = evaluate_candidate(evidence).to_dict()
    local_pass = bool(
        teacher_compatible
        and mapping["sensitivity_diagnostics"]["identifiable"]
        and (primary_baseline - primary_candidate) / primary_baseline >= 0.20
        and (flux_baseline - flux_candidate) / flux_baseline >= 0.15
        and endpoints_improve
        and flux_channels_improve
        and protected_degradation <= 0.10
        and panel_mean_degradation <= 0.05
        and panel_median_degradation <= 0.05
        and strict_check["pass"]
    )
    if local_pass:
        decision = "retain VAMPD1 storage decay as an internally guarded diagnostic"
        rationale = (
            "The full ODE preserves the mapped gains, independent IMP and adenylate teachers are "
            "compatible, and numerical/panel guards pass. Promotion remains blocked until a true "
            "temporal holdout and Bardyn/Michel validation are completed."
        )
    else:
        decision = "reject VAMPD1 storage decay after full-state feedback"
        rationale = "At least one predeclared teacher, concentration, purine, panel, or strict-solver guard failed."

    out_dir.mkdir(parents=True, exist_ok=True)
    pd.concat(frames.values(), ignore_index=True).to_csv(out_dir / "J1_J46_timeseries.csv", index=False)
    _plot(
        frames[BASELINE_LABEL],
        frames[CANDIDATE_LABEL],
        frames[STRICT_LABEL],
        out_dir / "vampd1_storage_decay_full_ode.png",
    )
    summary = {
        "contract_type": "full_ODE_VAMPD1_storage_activity_decay_evaluation",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_network_version": MODEL_NETWORK_VERSION,
        "optimization_performed": False,
        "parameters_promoted": False,
        "source_map": str(map_summary.resolve()),
        "source_anchor": str(anchor_summary.resolve()),
        "seed_params_path": str(seed_path),
        "baseline_vmax_VAMPD1": anchor_vampd1,
        "candidate_params": {
            "vmax_VAMPD1": candidate_params["vmax_VAMPD1"],
            "kinetic_family_VAMPD1": candidate_params["kinetic_family_VAMPD1"],
            "storage_decay_VAMPD1": candidate_params["storage_decay_VAMPD1"],
            "vmax_VAPRT": 0.0,
        },
        "windows": [list(window) for window in WINDOWS],
        "metrics": metrics,
        "primary_concentration_score": {
            "baseline": primary_baseline,
            "candidate": primary_candidate,
            "improvement": (primary_baseline - primary_candidate) / primary_baseline,
        },
        "primary_integrated_flux_score": {
            "baseline": flux_baseline,
            "candidate": flux_candidate,
            "improvement": (flux_baseline - flux_candidate) / flux_baseline,
        },
        "teacher_compatible": teacher_compatible,
        "protected_nrmse_max_degradation": protected_degradation,
        "panel_mean_degradation": panel_mean_degradation,
        "panel_median_degradation": panel_median_degradation,
        "strict_solver": strict_check,
        "validation_v2": validation,
        "local_diagnostic_pass": local_pass,
        "unmapped_panel_states": unmapped,
        "decision": decision,
        "decision_rationale": rationale,
        "next_step": (
            "run forward-chaining temporal refits without J22-J46 leakage, then freeze the candidate "
            "for Bardyn control and Michel ATP/ADP/AMP/HYPX validation"
            if local_pass
            else "inspect the first failed validation-v2 check before opening another purine parameter"
        ),
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "report": str(out_dir / "decision_report.md"),
            "timeseries": str(out_dir / "J1_J46_timeseries.csv"),
            "plot": str(out_dir / "vampd1_storage_decay_full_ode.png"),
        },
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    report = [
        "# Full-ODE VAMPD1 storage-decay evaluation",
        "",
        f"- Candidate: `vmax0={candidate_params['vmax_VAMPD1']:.6g}`, `k={candidate_params['storage_decay_VAMPD1']:.6g} day^-1`.",
        f"- Primary concentration improvement: `{summary['primary_concentration_score']['improvement']:.1%}`.",
        f"- Integrated teacher-flux improvement: `{summary['primary_integrated_flux_score']['improvement']:.1%}`.",
        f"- IMP/adenylate teacher disagreement nRMSE: `{teachers['teacher_disagreement_nrmse']:.5g}`.",
        f"- Protected/panel mean/panel median degradation: `{protected_degradation:.1%}` / `{panel_mean_degradation:.1%}` / `{panel_median_degradation:.1%}`.",
        f"- Strict-solver decision-metric difference: `{strict_check['maximum_decision_metric_relative_difference']:.5g}`; maximum transient difference `{strict_check['maximum_normalized_trajectory_difference']:.5g}`.",
        f"- Validation-v2 status: `{validation['status']}`.",
        "",
        decision,
        "",
        rationale,
    ]
    (out_dir / "decision_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "local_diagnostic_pass": local_pass,
                "validation_v2_status": validation["status"],
                "concentration_improvement": summary["primary_concentration_score"]["improvement"],
                "flux_improvement": summary["primary_integrated_flux_score"]["improvement"],
                "decision": decision,
                "report": str(out_dir / "decision_report.md"),
            },
            indent=2,
        )
    )
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map-summary", type=Path, default=DEFAULT_MAP)
    parser.add_argument("--anchor-summary", type=Path, default=DEFAULT_ANCHOR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--points", type=int, default=901)
    args = parser.parse_args(argv)
    run(
        map_summary=args.map_summary,
        anchor_summary=args.anchor_summary,
        out_dir=args.out_dir,
        points=args.points,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
