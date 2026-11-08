"""Run a small guarded full-ODE VADSS/GTP-affinity feasibility screen."""

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
DEFAULT_MAP = ROOT / "output" / "vadss_saturation_vampd1_decay" / "summary.json"
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
    / "vadss_specific_gtp_vampd1_decay_J1_J46"
)
BASELINE_LABEL = "VAMPD1_decay_VADSS_legacy"
STRICT_LABEL = "VADSS_selected_strict"
LOCAL_CROSS = (
    (1.0, 1.0),
    (0.85, 1.0),
    (1.15, 1.0),
    (1.0, 0.65),
    (1.0, 1.50),
)
for path in (str(SRC), str(SCRIPTS)):
    if path not in sys.path:
        sys.path.insert(0, path)

from audit_vadss_saturation_vampd1_decay import (  # noqa: E402
    build_joint_vadss_targets,
)
from equadiff_brodbar import MODEL_NETWORK_VERSION  # noqa: E402
from evaluate_brodbar_candidate_full_panel import _load_brodbar_panel  # noqa: E402
from evaluate_vampd1_storage_decay_candidate import (  # noqa: E402
    _strict_invariance,
    _vampd1_teachers,
)
from fla_integrated_flux import integrated_flux_nrmse  # noqa: E402
from fla_validation_v2 import CandidateEvidence, evaluate_candidate  # noqa: E402
from screen_amp_nucleotidase_fixed_purine import (  # noqa: E402
    PURINE_STATES,
    _build_anchor,
    _simulate_candidate,
)


def _relative_degradation(candidate: float, baseline: float) -> float:
    return float((candidate - baseline) / max(abs(baseline), 1e-12))


def _rms(values: Sequence[float]) -> float:
    array = np.asarray(values, dtype=float)
    return float(np.sqrt(np.mean(array**2)))


def _candidate_label(vmax_multiplier: float, km_multiplier: float) -> str:
    return f"VADSS_v{vmax_multiplier:.2f}_kg{km_multiplier:.2f}"


def _metric_row(
    *,
    label: str,
    params: Mapping[str, Any],
    frame: pd.DataFrame,
    metrics: dict[str, Any],
    exp_time: np.ndarray,
    curves: Mapping[str, np.ndarray],
) -> dict[str, Any]:
    targets = build_joint_vadss_targets(
        frame,
        exp_time,
        curves,
        frame["VADSS"].to_numpy(dtype=float),
    )
    vampd1 = _vampd1_teachers(frame=frame, exp_time=exp_time, curves=curves)
    metrics["VADSS_joint_integrated_teacher"] = {
        "nrmse": integrated_flux_nrmse(targets),
        "windows": [target.to_dict() for target in targets],
    }
    metrics["VAMPD1_integrated_teachers"] = vampd1
    asp_model = frame["ASP"].to_numpy(dtype=float)
    asp_teacher = frame["ASP_teacher"].to_numpy(dtype=float)
    metrics["ASP_endpoint_error_mM"] = float(asp_model[-1] - asp_teacher[-1])
    metrics["GTP_minimum_mM"] = float(frame["GTP"].min())
    return {
        "candidate": label,
        "vmax_VADSS": float(params["vmax_VADSS"]),
        "km_GTP_VADSS": float(params["km_GTP_VADSS"]),
        "IMP_nrmse": metrics["state_metrics"]["IMP"]["nrmse"],
        "IMP_endpoint_abs_mM": abs(metrics["state_metrics"]["IMP"]["endpoint_error_mM"]),
        "adenylate_nrmse": metrics["adenylate_total"]["nrmse"],
        "adenylate_endpoint_abs_mM": abs(metrics["adenylate_total"]["endpoint_error_mM"]),
        "ASP_nrmse": metrics["whole_panel_per_metabolite_nrmse"]["ASP"],
        "ASP_endpoint_abs_mM": abs(metrics["ASP_endpoint_error_mM"]),
        "VADSS_integrated_nrmse": metrics["VADSS_joint_integrated_teacher"]["nrmse"],
        "VAMPD1_adenylate_integrated_nrmse": vampd1["adenylate_nrmse"],
        "panel_mean_nrmse": metrics["whole_panel_mean_nrmse"],
        "panel_median_nrmse": metrics["whole_panel_median_nrmse"],
        "minimum_state_mM": metrics["minimum_state_mM"],
        "GTP_minimum_mM": metrics["GTP_minimum_mM"],
        "max_closure_error": metrics["closures"]["max_abs_closure_error"],
    }


def _score_and_guard(
    row: dict[str, Any],
    baseline_row: Mapping[str, Any],
    metrics: Mapping[str, Any],
    baseline_metrics: Mapping[str, Any],
) -> None:
    score_names = (
        "IMP_nrmse",
        "adenylate_nrmse",
        "ASP_nrmse",
        "VADSS_integrated_nrmse",
        "VAMPD1_adenylate_integrated_nrmse",
    )
    row["relative_composite_score"] = _rms(
        [row[name] / max(float(baseline_row[name]), 1e-12) for name in score_names]
    )
    protected = tuple(name for name in PURINE_STATES if name != "IMP")
    protected_degradation = max(
        _relative_degradation(
            metrics["state_metrics"][name]["nrmse"],
            baseline_metrics["state_metrics"][name]["nrmse"],
        )
        for name in protected
    )
    row["protected_purine_max_degradation"] = protected_degradation
    row["panel_mean_degradation"] = _relative_degradation(
        row["panel_mean_nrmse"], baseline_row["panel_mean_nrmse"]
    )
    row["panel_median_degradation"] = _relative_degradation(
        row["panel_median_nrmse"], baseline_row["panel_median_nrmse"]
    )
    row["VADSS_flux_improvement"] = 1.0 - (
        row["VADSS_integrated_nrmse"]
        / max(float(baseline_row["VADSS_integrated_nrmse"]), 1e-12)
    )
    row["passes_guard"] = bool(
        row["IMP_nrmse"] < baseline_row["IMP_nrmse"]
        and row["IMP_endpoint_abs_mM"] < baseline_row["IMP_endpoint_abs_mM"]
        and row["ASP_nrmse"] <= baseline_row["ASP_nrmse"]
        and row["adenylate_nrmse"] <= 1.10 * baseline_row["adenylate_nrmse"]
        and row["adenylate_endpoint_abs_mM"] <= 1.10 * baseline_row["adenylate_endpoint_abs_mM"]
        and row["VADSS_flux_improvement"] >= 0.15
        and row["VAMPD1_adenylate_integrated_nrmse"]
        <= 1.10 * baseline_row["VAMPD1_adenylate_integrated_nrmse"]
        and protected_degradation <= 0.10
        and row["panel_mean_degradation"] <= 0.05
        and row["panel_median_degradation"] <= 0.05
        and row["minimum_state_mM"] >= -1e-10
        and row["GTP_minimum_mM"] >= -1e-10
        and row["max_closure_error"] <= 1e-7
    )


def _plot(
    baseline: pd.DataFrame,
    selected: pd.DataFrame,
    strict: pd.DataFrame,
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(15.5, 8.5), constrained_layout=True)
    for frame, label, color, style in (
        (baseline, "VADSS legacy", "#457b9d", "-"),
        (selected, "VADSS selected", "#d1495b", "-"),
        (strict, "selected strict", "#2a9d8f", ":"),
    ):
        time = frame["time_day"]
        axes[0, 0].plot(time, frame["IMP"], color=color, ls=style, lw=2, label=label)
        axes[0, 1].plot(
            time,
            frame["ATP"] + frame["ADP"] + frame["AMP"],
            color=color,
            ls=style,
            lw=2,
            label=label,
        )
        axes[0, 2].plot(time, frame["ASP"], color=color, ls=style, lw=2, label=label)
        axes[1, 0].plot(time, frame["GTP"], color=color, ls=style, lw=2, label=label)
        axes[1, 1].plot(time, frame["VADSS"], color=color, ls=style, lw=2, label=label)
        axes[1, 2].plot(time, frame["VNDPK"], color=color, ls=style, lw=2, label=label)
    axes[0, 0].plot(baseline["time_day"], baseline["IMP_teacher"], "k--", lw=2)
    axes[0, 1].plot(
        baseline["time_day"], baseline["adenylate_total_teacher"], "k--", lw=2
    )
    axes[0, 2].plot(baseline["time_day"], baseline["ASP_teacher"], "k--", lw=2)
    for axis, title in zip(
        axes.flat,
        ("IMP", "ATP + ADP + AMP", "ASP", "GTP", "VADSS", "VNDPK"),
    ):
        axis.set_title(title)
        axis.set_xlabel("Storage day")
        axis.grid(alpha=0.2)
    axes[0, 0].legend(fontsize=8)
    for axis in axes[0, :]:
        axis.set_ylabel("Concentration (mM)")
    for axis in axes[1, 1:]:
        axis.set_ylabel("Flux (mM/day)")
    axes[1, 0].set_ylabel("Concentration (mM)")
    fig.suptitle("Guarded full-ODE VADSS/GTP-affinity screen", fontsize=15)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def run(
    *, map_summary: Path, anchor_summary: Path, out_dir: Path, points: int
) -> dict[str, Any]:
    mapping = json.loads(map_summary.read_text(encoding="utf-8"))
    mapped = mapping["best_fixed_state_candidate"]
    state, params, seed_path, _anchor_vampd1 = _build_anchor(anchor_summary)
    base_params = dict(params)
    base_params.update(
        {
            "purine_structure_mode": "legacy",
            "vmax_VAMP_NT": 0.0,
            "vmax_VAMPD1": 0.125,
            "kinetic_family_VAMPD1": "storage_activity_decay",
            "storage_decay_VAMPD1": 0.0125,
            "km_GTP_VADSS": 0.5,
        }
    )
    exp_time, curves, _order, _indices, unmapped = _load_brodbar_panel()
    time = np.unique(np.concatenate([np.linspace(1.0, 46.0, points), exp_time]))
    frames: dict[str, pd.DataFrame] = {}
    metrics: dict[str, dict[str, Any]] = {}
    params_by_label: dict[str, dict[str, Any]] = {BASELINE_LABEL: base_params}
    for vmax_multiplier, km_multiplier in LOCAL_CROSS:
        label = _candidate_label(vmax_multiplier, km_multiplier)
        candidate = dict(base_params)
        candidate.update(
            {
                "vmax_VADSS": float(mapped["vmax_VADSS"]) * vmax_multiplier,
                "km_GTP_VADSS": float(mapped["km_value"]) * km_multiplier,
            }
        )
        params_by_label[label] = candidate

    rows: list[dict[str, Any]] = []
    for label, local_params in params_by_label.items():
        print(f"[VADSS] replay {label}", flush=True)
        frames[label], metrics[label] = _simulate_candidate(
            label=label,
            state=state,
            params=local_params,
            time=time,
            exp_time=exp_time,
            curves=curves,
            method="BDF",
            rtol=3e-4,
            atol=1e-6,
            closure_tolerance=1e-7,
        )
        rows.append(
            _metric_row(
                label=label,
                params=local_params,
                frame=frames[label],
                metrics=metrics[label],
                exp_time=exp_time,
                curves=curves,
            )
        )

    row_by_label = {row["candidate"]: row for row in rows}
    baseline_row = row_by_label[BASELINE_LABEL]
    baseline_metrics = metrics[BASELINE_LABEL]
    for row in rows:
        if row["candidate"] == BASELINE_LABEL:
            row.update(
                {
                    "relative_composite_score": 1.0,
                    "protected_purine_max_degradation": 0.0,
                    "panel_mean_degradation": 0.0,
                    "panel_median_degradation": 0.0,
                    "VADSS_flux_improvement": 0.0,
                    "passes_guard": False,
                }
            )
        else:
            _score_and_guard(
                row,
                baseline_row,
                metrics[row["candidate"]],
                baseline_metrics,
            )
    candidates = [row for row in rows if row["candidate"] != BASELINE_LABEL]
    guarded = [row for row in candidates if row["passes_guard"]]
    selected_row = min(
        guarded or candidates, key=lambda row: row["relative_composite_score"]
    )
    selected_label = str(selected_row["candidate"])

    print(f"[VADSS] strict replay {selected_label}", flush=True)
    frames[STRICT_LABEL], metrics[STRICT_LABEL] = _simulate_candidate(
        label=STRICT_LABEL,
        state=state,
        params=params_by_label[selected_label],
        time=time,
        exp_time=exp_time,
        curves=curves,
        method="BDF",
        rtol=1e-7,
        atol=1e-9,
        closure_tolerance=1e-7,
    )
    strict_row = _metric_row(
        label=STRICT_LABEL,
        params=params_by_label[selected_label],
        frame=frames[STRICT_LABEL],
        metrics=metrics[STRICT_LABEL],
        exp_time=exp_time,
        curves=curves,
    )
    strict_check = _strict_invariance(
        frames[selected_label],
        frames[STRICT_LABEL],
        metrics[selected_label],
        metrics[STRICT_LABEL],
    )
    extra_strict_differences = {
        name: abs(strict_row[name] - selected_row[name])
        / max(abs(float(selected_row[name])), 0.01)
        for name in ("ASP_nrmse", "VADSS_integrated_nrmse")
    }
    strict_check["VADSS_screen_metric_relative_differences"] = extra_strict_differences
    strict_check["pass"] = bool(
        strict_check["pass"] and max(extra_strict_differences.values()) <= 0.01
    )

    trajectory_baseline = _rms(
        [baseline_row[name] for name in ("IMP_nrmse", "adenylate_nrmse", "ASP_nrmse")]
    )
    trajectory_candidate = _rms(
        [selected_row[name] for name in ("IMP_nrmse", "adenylate_nrmse", "ASP_nrmse")]
    )
    endpoints_improve = bool(
        all(
            selected_row[name] < baseline_row[name]
            for name in (
                "IMP_endpoint_abs_mM",
                "adenylate_endpoint_abs_mM",
                "ASP_endpoint_abs_mM",
            )
        )
    )
    evidence = CandidateEvidence(
        candidate_id=selected_label,
        training_datasets=("brodbar_J1_J46",),
        temporal_validation_datasets=(),
        external_validation_datasets=(),
        data_contract_complete=False,  # Raw endpoint provenance and units remain unresolved.
        exact_balance_max_error_mM_per_day=selected_row["max_closure_error"],
        minimum_state_mM=selected_row["minimum_state_mM"],
        continuous_unforced_replay=True,
        independent_teachers_compatible=None,  # Joint teacher is conditional, not independent evidence.
        sensitivity_block_identifiable=bool(
            mapped["identifiability"]["identifiable"]
        ),
        primary_trajectory_baseline=trajectory_baseline,
        primary_trajectory_candidate=trajectory_candidate,
        primary_flux_baseline=baseline_row["VADSS_integrated_nrmse"],
        primary_flux_candidate=selected_row["VADSS_integrated_nrmse"],
        all_primary_endpoints_improve=endpoints_improve,
        all_primary_slopes_improve=bool(
            selected_row["VADSS_integrated_nrmse"]
            < baseline_row["VADSS_integrated_nrmse"]
        ),
        max_protected_nrmse_degradation=selected_row[
            "protected_purine_max_degradation"
        ],
        panel_mean_nrmse_degradation=selected_row["panel_mean_degradation"],
        panel_median_nrmse_degradation=selected_row["panel_median_degradation"],
        strict_solver_invariant=bool(strict_check["pass"]),
        temporal_holdout_improves=None,
        external_holdout_improves=None,
        complexity_supported_by_prediction=None,
    )
    validation = evaluate_candidate(evidence).to_dict()
    retained = bool(guarded and selected_row["passes_guard"] and strict_check["pass"])
    decision = (
        "retain the enzyme-specific VADSS/GTP-affinity pair as a diagnostic candidate"
        if retained
        else "reject the local VADSS/GTP-affinity screen under full-state feedback"
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out_dir / "candidate_metrics.csv", index=False)
    pd.concat(frames.values(), ignore_index=True).to_csv(
        out_dir / "J1_J46_timeseries.csv", index=False
    )
    _plot(
        frames[BASELINE_LABEL],
        frames[selected_label],
        frames[STRICT_LABEL],
        out_dir / "vadss_specific_gtp_full_ode.png",
    )
    summary = {
        "contract_type": "guarded_full_ODE_VADSS_specific_GTP_affinity_screen",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_network_version": MODEL_NETWORK_VERSION,
        "optimization_performed": False,
        "parameters_promoted": False,
        "source_map": str(map_summary.resolve()),
        "source_anchor": str(anchor_summary.resolve()),
        "seed_params_path": str(seed_path),
        "fixed_context": {
            "vmax_VAMPD1": 0.125,
            "kinetic_family_VAMPD1": "storage_activity_decay",
            "storage_decay_VAMPD1": 0.0125,
            "vmax_VAPRT": 0.0,
        },
        "candidate_rows": rows,
        "selected_candidate": selected_row,
        "selected_full_metrics": metrics[selected_label],
        "strict_metrics": strict_row,
        "strict_solver": strict_check,
        "validation_v2": validation,
        "retained_diagnostic": retained,
        "unmapped_panel_states": unmapped,
        "decision": decision,
        "next_step": (
            "run forward-chaining temporal validation before any external replay"
            if retained
            else "audit GTP regeneration through VNDPK and the unmeasured guanylate pool before opening another VADSS parameter"
        ),
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "report": str(out_dir / "decision_report.md"),
            "metrics": str(out_dir / "candidate_metrics.csv"),
            "timeseries": str(out_dir / "J1_J46_timeseries.csv"),
            "plot": str(out_dir / "vadss_specific_gtp_full_ode.png"),
        },
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    report = (
        "# Full-ODE VADSS-specific GTP-affinity screen\n\n"
        f"- Selected diagnostic point: `{selected_label}` with "
        f"`vmax_VADSS={selected_row['vmax_VADSS']:.6g}` and "
        f"`km_GTP_VADSS={selected_row['km_GTP_VADSS']:.6g}`.\n"
        f"- Relative composite score: `{selected_row['relative_composite_score']:.5f}`.\n"
        f"- IMP nRMSE: `{baseline_row['IMP_nrmse']:.5f} -> {selected_row['IMP_nrmse']:.5f}`.\n"
        f"- ASP nRMSE: `{baseline_row['ASP_nrmse']:.5f} -> {selected_row['ASP_nrmse']:.5f}`.\n"
        f"- Joint VADSS teacher nRMSE: `{baseline_row['VADSS_integrated_nrmse']:.5f} -> {selected_row['VADSS_integrated_nrmse']:.5f}`.\n"
        f"- Protected/panel mean/panel median degradation: "
        f"`{selected_row['protected_purine_max_degradation']:.1%}` / "
        f"`{selected_row['panel_mean_degradation']:.1%}` / "
        f"`{selected_row['panel_median_degradation']:.1%}`.\n"
        f"- Strict-solver invariant: `{strict_check['pass']}`.\n"
        f"- Validation-v2 status: `{validation['status']}`.\n\n"
        f"{decision}\n"
    )
    (out_dir / "decision_report.md").write_text(report, encoding="utf-8")
    print(
        json.dumps(
            {
                "selected": selected_label,
                "retained_diagnostic": retained,
                "validation_v2_status": validation["status"],
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
    parser.add_argument("--points", type=int, default=601)
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
