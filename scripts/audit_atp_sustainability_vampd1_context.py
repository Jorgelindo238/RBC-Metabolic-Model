"""Reconstruct interval ATP production and consumption after purine diagnostics."""

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
DEFAULT_SOURCE_DIR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "vampd1_storage_decay_full_ode_J1_J46"
)
DEFAULT_OUT_DIR = ROOT / "output" / "atp_sustainability_vampd1_context"
SOURCE_LABEL = "VAMPD1_storage_decay"
WINDOWS = ((1.0, 4.0), (4.0, 11.0), (11.0, 22.0), (22.0, 46.0))
ATP_PRODUCTION = ("VPGK", "VPK", "VAK")
ATP_CONSUMPTION = (
    "VHK",
    "VPFK",
    "VAK2",
    "VGLNS",
    "VGLUCYS",
    "VGSS",
    "VSAM",
    "VRKa",
    "VPRPPASe",
    "VGMPS",
    "VGMPK",
    "VNDPK",
    "VOPLAH",
)
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fla_integrated_flux import build_integrated_flux_targets  # noqa: E402


def aggregate_atp_rates(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    missing = set(ATP_PRODUCTION + ATP_CONSUMPTION) - set(frame.columns)
    if missing:
        raise ValueError(f"missing ATP flux columns: {sorted(missing)}")
    production = frame.loc[:, ATP_PRODUCTION].sum(axis=1).to_numpy(dtype=float)
    consumption = frame.loc[:, ATP_CONSUMPTION].sum(axis=1).to_numpy(dtype=float)
    return production, consumption


def _window_integral(time: np.ndarray, values: np.ndarray, start: float, end: float) -> float:
    mask = (time >= start - 1e-10) & (time <= end + 1e-10)
    return float(trapezoid(values[mask], time[mask]))


def run(source_dir: Path, out_dir: Path) -> dict[str, Any]:
    all_frame = pd.read_csv(source_dir / "J1_J46_timeseries.csv")
    frame = all_frame.loc[all_frame["candidate"] == SOURCE_LABEL].copy()
    if frame.empty:
        raise ValueError(f"candidate {SOURCE_LABEL!r} is absent")
    time = frame["time_day"].to_numpy(dtype=float)
    production, consumption = aggregate_atp_rates(frame)
    measurement_mask = frame["time_day"].isin(
        sorted({boundary for window in WINDOWS for boundary in window})
    )
    measurement_time = frame.loc[measurement_mask, "time_day"].to_numpy(dtype=float)
    measurement_atp = frame.loc[measurement_mask, "ATP_teacher"].to_numpy(dtype=float)
    production_targets = build_integrated_flux_targets(
        measurement_time=measurement_time,
        measurement_values=measurement_atp,
        dense_time=time,
        known_rate=-consumption,
        model_unknown_rate=production,
        unknown_stoichiometric_coefficient=1.0,
        windows=WINDOWS,
    )
    consumption_targets = build_integrated_flux_targets(
        measurement_time=measurement_time,
        measurement_values=measurement_atp,
        dense_time=time,
        known_rate=production,
        model_unknown_rate=consumption,
        unknown_stoichiometric_coefficient=-1.0,
        windows=WINDOWS,
    )
    rows = []
    sink_rows = []
    for production_target, consumption_target, (start, end) in zip(
        production_targets, consumption_targets, WINDOWS
    ):
        actual_production = production_target.model_unknown_flux_integral_mM
        required_production = production_target.required_unknown_flux_integral_mM
        actual_consumption = consumption_target.model_unknown_flux_integral_mM
        required_consumption = consumption_target.required_unknown_flux_integral_mM
        rows.append(
            {
                "start_day": start,
                "end_day": end,
                "teacher_ATP_change_mM": production_target.observed_state_change_mM,
                "actual_ATP_production_mM": actual_production,
                "required_ATP_production_at_model_consumption_mM": required_production,
                "required_to_actual_production_ratio": required_production
                / max(abs(actual_production), 1e-15),
                "actual_ATP_consumption_mM": actual_consumption,
                "required_ATP_consumption_at_model_production_mM": required_consumption,
                "required_to_actual_consumption_ratio": required_consumption
                / max(abs(actual_consumption), 1e-15),
                "production_group_teacher_nonnegative": required_production >= 0.0,
                "consumption_group_teacher_nonnegative": required_consumption >= 0.0,
            }
        )
        for reaction in ATP_CONSUMPTION:
            integral = _window_integral(
                time, frame[reaction].to_numpy(dtype=float), start, end
            )
            sink_rows.append(
                {
                    "start_day": start,
                    "end_day": end,
                    "reaction": reaction,
                    "integral_mM": integral,
                    "fraction_of_ATP_consumption": integral
                    / max(abs(actual_consumption), 1e-15),
                }
            )
    threshold = 0.01
    below = frame.loc[frame["ATP"] < threshold, "time_day"]
    crossing = float(below.iloc[0]) if not below.empty else None
    impossible_late = [
        row for row in rows if not row["production_group_teacher_nonnegative"]
    ]
    early_ratios = [row["required_to_actual_production_ratio"] for row in rows[:2]]
    summary = {
        "contract_type": "integrated_ATP_sustainability_audit",
        "contract_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "optimization_performed": False,
        "parameters_promoted": False,
        "source_replay": str(source_dir.resolve()),
        "source_candidate": SOURCE_LABEL,
        "ATP_production_terms": list(ATP_PRODUCTION),
        "ATP_consumption_terms": list(ATP_CONSUMPTION),
        "window_results": rows,
        "ATP_below_0.01_mM_day": crossing,
        "early_required_production_multiplier_range": [
            float(min(early_ratios)),
            float(max(early_ratios)),
        ],
        "late_negative_required_production_windows": len(impossible_late),
        "interpretation": (
            "Early model-state inversion requires a larger signed ATP production group at fixed "
            "model consumption. The late conditional group becomes negative. These groups contain "
            "reversible net VAK and VNDPK, so the group sign alone is NOT an irreversibility test. "
            "Separate gross forward/reverse contributions and numerical damping before attributing "
            "the mismatch to ATP production or consumption."
        ),
        "decision": (
            "freeze purine kinetics; quantify raw ATP/adenylate balance defects and evaluate "
            "short-horizon sensitivities before selecting a multiple-shooting training objective. "
            "Retain continuous unforced J1-J46 replay as a mandatory validation test."
        ),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out_dir / "atp_window_feasibility.csv", index=False)
    pd.DataFrame(sink_rows).to_csv(out_dir / "atp_sink_attribution.csv", index=False)
    pd.DataFrame(
        {
            "time_day": time,
            "ATP": frame["ATP"],
            "ATP_teacher": frame["ATP_teacher"],
            "ATP_production": production,
            "ATP_consumption": consumption,
            "ATP_net": production - consumption,
        }
    ).to_csv(out_dir / "atp_rate_trace.csv", index=False)
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.8), constrained_layout=True)
    axes[0].plot(time, frame["ATP"], label="model", color="#d1495b", lw=2)
    axes[0].plot(time, frame["ATP_teacher"], "k--", label="Brodbar", lw=2)
    axes[0].axhline(threshold, color="#777777", ls=":")
    axes[0].set_title("ATP trajectory")
    axes[0].set_ylabel("mM")
    axes[0].legend()
    axes[1].plot(time, production, label="production", color="#2a9d8f", lw=2)
    axes[1].plot(time, consumption, label="consumption", color="#d1495b", lw=2)
    axes[1].set_yscale("symlog", linthresh=1e-3)
    axes[1].set_title("Model ATP rates")
    axes[1].set_ylabel("mM/day")
    axes[1].legend()
    labels = [f"J{row['start_day']:g}-J{row['end_day']:g}" for row in rows]
    x = np.arange(len(rows))
    axes[2].bar(
        x - 0.2,
        [row["actual_ATP_production_mM"] for row in rows],
        width=0.4,
        label="actual production",
        color="#457b9d",
    )
    axes[2].bar(
        x + 0.2,
        [row["required_ATP_production_at_model_consumption_mM"] for row in rows],
        width=0.4,
        label="required production",
        color="#d1495b",
    )
    axes[2].axhline(0.0, color="#333333", lw=1)
    axes[2].set_xticks(x, labels, rotation=20)
    axes[2].set_title("Integrated production teacher")
    axes[2].set_ylabel("mM")
    axes[2].legend(fontsize=8)
    for axis in axes:
        axis.set_xlabel("Storage day" if axis is not axes[2] else "Window")
        axis.grid(alpha=0.2)
    fig.savefig(out_dir / "atp_sustainability_audit.png", dpi=180)
    plt.close(fig)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    report = (
        "# ATP sustainability audit in the VAMPD1 context\n\n"
        f"- ATP crosses below `0.01 mM` at day `{crossing:.4g}`.\n"
        f"- Required early production multipliers: `{min(early_ratios):.3f}` to "
        f"`{max(early_ratios):.3f}` at fixed model consumption.\n"
        f"- Late windows with a negative fixed-state production teacher: "
        f"`{len(impossible_late)}`.\n"
        "- Dominant early sinks are reported in `atp_sink_attribution.csv`.\n\n"
        f"{summary['decision']}\n"
    )
    (out_dir / "decision_report.md").write_text(report, encoding="utf-8")
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)
    print(json.dumps(run(args.source_dir, args.out_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
