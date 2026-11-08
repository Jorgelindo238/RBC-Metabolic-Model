"""Diagnose observation-anchored multiple shooting on the Brodbar record."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.integrate import trapezoid


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
DEFAULT_ANCHOR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "vmax_vampd1_vaprt_zero_screen_J1_J46"
    / "summary.json"
)
DEFAULT_FREE_RUN = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "vampd1_storage_decay_full_ode_J1_J46"
    / "J1_J46_timeseries.csv"
)
DEFAULT_OUT_DIR = ROOT / "output" / "brodbar_multiple_shooting_diagnostic"
FREE_LABEL = "VAMPD1_storage_decay"
EXCLUDED_RESETS = {"B13PG", "P2G", "P3G"}
ENERGY_TARGETS = ("ATP", "ADP", "AMP", "GLC", "G6P", "F6P", "B23PG", "PEP", "PYR", "LAC")
ENERGY_FLUXES = (
    "VHK",
    "VPFK",
    "VPGK",
    "VPK",
    "VAK",
    "VNDPK",
    "VADSS",
)
for path in (str(SRC), str(SCRIPTS)):
    if path not in sys.path:
        sys.path.insert(0, path)

from evaluate_brodbar_candidate_full_panel import _load_brodbar_panel  # noqa: E402
from fla_multiple_shooting import duration_above_threshold, endpoint_nrmse, reset_observed_states  # noqa: E402
from profile_glycolysis_flux_bottlenecks import _simulate_and_track  # noqa: E402
from screen_amp_nucleotidase_fixed_purine import _build_anchor  # noqa: E402


def _simulation_params(anchor: Path) -> tuple[np.ndarray, dict[str, Any], Path]:
    state, params, seed_path, _anchor_vampd1 = _build_anchor(anchor)
    params = dict(params)
    params.update(
        {
            "purine_structure_mode": "legacy",
            "vmax_VAMP_NT": 0.0,
            "vmax_VAMPD1": 0.125,
            "kinetic_family_VAMPD1": "storage_activity_decay",
            "storage_decay_VAMPD1": 0.0125,
        }
    )
    return state, params, seed_path


def run(anchor: Path, free_run: Path, out_dir: Path, points_per_segment: int) -> dict[str, Any]:
    state, params, seed_path = _simulation_params(anchor)
    exp_time, curves, order, state_indices, unmapped = _load_brodbar_panel()
    reset_names = tuple(
        name for name in order if name not in EXCLUDED_RESETS and name in state_indices
    )
    scales = {
        name: max(float(np.mean(np.abs(curves[name]))), 0.01) for name in reset_names
    }
    endpoint_rows = []
    reset_rows = []
    segment_rows = []
    trace_frames = []
    current_state = np.asarray(state, dtype=float)
    for interval_index, (start, end) in enumerate(zip(exp_time[:-1], exp_time[1:])):
        observations = {
            name: float(curves[name][interval_index]) for name in reset_names
        }
        current_state, reset = reset_observed_states(
            current_state,
            observations=observations,
            state_indices=state_indices,
            scales=scales,
            time_day=float(start),
        )
        reset_rows.append(reset.to_dict())
        local_time = np.linspace(float(start), float(end), points_per_segment)
        solution, fluxes, _derivatives = _simulate_and_track(
            params=params,
            t_eval=local_time,
            method="BDF",
            rtol=3e-4,
            atol=1e-6,
            x0_override=current_state,
        )
        current_state = np.asarray(solution.y[:, -1], dtype=float)
        for name in reset_names:
            prediction = float(current_state[state_indices[name]])
            observation = float(curves[name][interval_index + 1])
            endpoint_rows.append(
                {
                    "start_day": float(start),
                    "end_day": float(end),
                    "metabolite": name,
                    "prediction_mM": prediction,
                    "observation_mM": observation,
                    "error_mM": prediction - observation,
                }
            )
        segment = {
            "start_day": float(start),
            "end_day": float(end),
            "minimum_ATP_mM": float(np.min(solution.y[state_indices["ATP"], :])),
            "ATP_endpoint_mM": float(current_state[state_indices["ATP"]]),
            "ATP_teacher_endpoint_mM": float(curves["ATP"][interval_index + 1]),
        }
        for reaction in ENERGY_FLUXES:
            segment[f"{reaction}_integral_mM"] = float(
                trapezoid(fluxes[reaction], local_time)
            )
        segment_rows.append(segment)
        local_frame = pd.DataFrame(
            {
                "segment": interval_index,
                "time_day": local_time,
                **{
                    name: solution.y[state_indices[name], :]
                    for name in ENERGY_TARGETS
                },
                **{reaction: fluxes[reaction] for reaction in ENERGY_FLUXES},
            }
        )
        trace_frames.append(local_frame)

    endpoint_frame = pd.DataFrame(endpoint_rows)
    free = pd.read_csv(free_run)
    free = free.loc[free["candidate"] == FREE_LABEL].copy()
    metric_rows = []
    for name in reset_names:
        local = endpoint_frame.loc[endpoint_frame["metabolite"] == name]
        multiple_score = endpoint_nrmse(
            local["prediction_mM"],
            local["observation_mM"],
            scale=scales[name],
        )
        free_prediction = np.interp(
            exp_time[1:], free["time_day"], free[name]
        )
        free_score = endpoint_nrmse(
            free_prediction,
            curves[name][1:],
            scale=scales[name],
        )
        metric_rows.append(
            {
                "metabolite": name,
                "free_run_endpoint_nrmse": free_score,
                "multiple_shooting_endpoint_nrmse": multiple_score,
                "relative_change": (multiple_score - free_score)
                / max(abs(free_score), 1e-12),
            }
        )
    metrics = pd.DataFrame(metric_rows)
    trace = pd.concat(trace_frames, ignore_index=True)
    free_atp_informative = duration_above_threshold(
        free["time_day"], free["ATP"], threshold=0.01,
    ) / float(free["time_day"].iloc[-1] - free["time_day"].iloc[0])
    shooting_atp_informative = sum(
        duration_above_threshold(frame["time_day"], frame["ATP"], threshold=0.01)
        for frame in trace_frames
    ) / float(exp_time[-1] - exp_time[0])
    reset_loss = float(
        np.mean([row["normalized_jump_loss"] for row in reset_rows[1:]])
    )
    energy_metrics = metrics.loc[metrics["metabolite"].isin(ENERGY_TARGETS)]
    summary = {
        "contract_type": "Brodbar_observation_anchored_multiple_shooting_diagnostic",
        "contract_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "optimization_performed": False,
        "parameters_promoted": False,
        "source_anchor": str(anchor.resolve()),
        "source_free_run": str(free_run.resolve()),
        "seed_params_path": str(seed_path.resolve()),
        "reset_policy": {
            "observed_states_reset_only_at_measured_times": True,
            "latent_states_carried_between_segments": True,
            "excluded_ambiguous_observations": sorted(EXCLUDED_RESETS),
            "reset_state_count": len(reset_names),
            "continuity_jump_is_penalized": False,
            "continuity_jump_is_reported": True,
            "shooting_nodes_or_kinetics_optimized": False,
            "curve_fit_forcing_inside_segments": False,
        },
        "segment_count": len(segment_rows),
        "mean_normalized_continuity_jump_loss": reset_loss,
        "ATP_above_threshold_time_fraction": {
            "threshold_mM": 0.01,
            "method": "piecewise_linear_duration_per_segment_excluding_reset_jumps",
            "free_run": free_atp_informative,
            "multiple_shooting": shooting_atp_informative,
        },
        "energy_panel_mean_endpoint_nrmse": {
            "free_run": float(energy_metrics["free_run_endpoint_nrmse"].mean()),
            "multiple_shooting": float(
                energy_metrics["multiple_shooting_endpoint_nrmse"].mean()
            ),
        },
        "unmapped_states": unmapped,
        "decision": (
            "diagnostic only: observation resets change ATP availability but do not establish "
            "identifiability or predictive calibration. Test kinetic sensitivities and an explicit "
            "continuity objective before choosing multiple shooting; continuous unforced J1-J46 "
            "and held-out replay remain mandatory validation gates."
        ),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    endpoint_frame.to_csv(out_dir / "segment_endpoint_predictions.csv", index=False)
    metrics.to_csv(out_dir / "endpoint_metrics.csv", index=False)
    pd.DataFrame(segment_rows).to_csv(out_dir / "segment_flux_integrals.csv", index=False)
    pd.DataFrame(reset_rows).to_json(
        out_dir / "shooting_resets.json", orient="records", indent=2
    )
    trace.to_csv(out_dir / "multiple_shooting_timeseries.csv", index=False)
    fig, axes = plt.subplots(2, 2, figsize=(13.5, 8.5), constrained_layout=True)
    for name, axis in zip(("ATP", "ADP", "GLC", "B23PG"), axes.flat):
        axis.plot(free["time_day"], free[name], color="#457b9d", lw=2, label="free run")
        for segment_id, local in trace.groupby("segment"):
            axis.plot(
                local["time_day"],
                local[name],
                color="#d1495b",
                lw=1.3,
                label="multiple shooting" if segment_id == 0 else None,
            )
        axis.scatter(exp_time, curves[name], color="#111111", s=18, zorder=3, label="Brodbar" if name == "ATP" else None)
        axis.set_title(name)
        axis.set_xlabel("Storage day")
        axis.set_ylabel("mM")
        axis.grid(alpha=0.2)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle("Brodbar observation-anchored multiple-shooting diagnostic", fontsize=15)
    fig.savefig(out_dir / "multiple_shooting_diagnostic.png", dpi=180)
    plt.close(fig)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    report = (
        "# Brodbar multiple-shooting diagnostic\n\n"
        f"- Segments: `{len(segment_rows)}`; observed resets per node: `{len(reset_names)}`.\n"
        f"- Elapsed time with ATP >= 0.01 mM: `{free_atp_informative:.1%}` free run versus "
        f"`{shooting_atp_informative:.1%}` multiple shooting.\n"
        f"- Mean normalized continuity-jump loss: `{reset_loss:.5g}`.\n"
        f"- Energy-panel endpoint nRMSE: "
        f"`{summary['energy_panel_mean_endpoint_nrmse']['free_run']:.5g}` free run versus "
        f"`{summary['energy_panel_mean_endpoint_nrmse']['multiple_shooting']:.5g}` multiple shooting.\n\n"
        f"{summary['decision']}\n"
    )
    (out_dir / "decision_report.md").write_text(report, encoding="utf-8")
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchor", type=Path, default=DEFAULT_ANCHOR)
    parser.add_argument("--free-run", type=Path, default=DEFAULT_FREE_RUN)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--points-per-segment", type=int, default=61)
    args = parser.parse_args(argv)
    summary = run(args.anchor, args.free_run, args.out_dir, args.points_per_segment)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
