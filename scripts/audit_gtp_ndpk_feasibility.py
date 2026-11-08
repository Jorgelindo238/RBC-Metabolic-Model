"""Audit the GTP supply and conditional NDPK demand behind VADSS failure."""

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
from scipy.integrate import trapezoid


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
DEFAULT_SOURCE_DIR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "vadss_specific_gtp_vampd1_decay_J1_J46"
)
DEFAULT_MAP = ROOT / "output" / "vadss_saturation_vampd1_decay" / "summary.json"
DEFAULT_ANCHOR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "vmax_vampd1_vaprt_zero_screen_J1_J46"
    / "summary.json"
)
DEFAULT_OUT_DIR = ROOT / "output" / "gtp_ndpk_feasibility"
SOURCE_LABEL = "VAMPD1_decay_VADSS_legacy"
WINDOWS = ((1.0, 11.0), (11.0, 22.0), (22.0, 46.0))
for path in (str(SRC), str(SCRIPTS)):
    if path not in sys.path:
        sys.path.insert(0, path)

from audit_vadss_saturation_vampd1_decay import (  # noqa: E402
    build_joint_vadss_targets,
    michaelis_fraction,
)
from evaluate_brodbar_candidate_full_panel import _load_brodbar_panel  # noqa: E402
from screen_amp_nucleotidase_fixed_purine import _build_anchor  # noqa: E402


def ndpk_components(
    *,
    gdp: Sequence[float],
    atp: Sequence[float],
    gtp: Sequence[float],
    adp: Sequence[float],
    vmax_forward: float,
    vmax_reverse: float,
    km_gdp: float,
    km_atp: float,
    km_gtp: float,
    km_adp: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    forward = (
        float(vmax_forward)
        * michaelis_fraction(gdp, km_gdp)
        * michaelis_fraction(np.maximum(np.asarray(atp, dtype=float), 1e-6), km_atp)
    )
    reverse = (
        float(vmax_reverse)
        * michaelis_fraction(gtp, km_gtp)
        * michaelis_fraction(np.maximum(np.asarray(adp, dtype=float), 1e-6), km_adp)
    )
    return forward, reverse, forward - reverse


def _window_integral(time: np.ndarray, values: np.ndarray, start: float, end: float) -> float:
    mask = (time >= start - 1e-10) & (time <= end + 1e-10)
    return float(trapezoid(values[mask], time[mask]))


def conditional_ndpk_windows(
    *,
    frame: pd.DataFrame,
    vadss_targets: Sequence[Any],
    forward_drive: np.ndarray,
    reverse_rate: np.ndarray,
) -> list[dict[str, float]]:
    time = frame["time_day"].to_numpy(dtype=float)
    rows = []
    for target, (start, end) in zip(vadss_targets, WINDOWS):
        mask = (time >= start - 1e-10) & (time <= end + 1e-10)
        delta_gtp = float(frame.loc[mask, "GTP"].iloc[-1] - frame.loc[mask, "GTP"].iloc[0])
        actual_ndpk = _window_integral(
            time, frame["VNDPK"].to_numpy(dtype=float), start, end
        )
        required_vadss = float(target.required_unknown_flux_integral_mM)
        required_ndpk = required_vadss + delta_gtp
        drive_integral = _window_integral(time, forward_drive, start, end)
        reverse_integral = _window_integral(time, reverse_rate, start, end)
        required_vmax = (required_ndpk + reverse_integral) / max(drive_integral, 1e-15)
        rows.append(
            {
                "start_day": start,
                "end_day": end,
                "actual_VADSS_integral_mM": float(target.model_unknown_flux_integral_mM),
                "required_VADSS_integral_mM": required_vadss,
                "model_delta_GTP_mM": delta_gtp,
                "actual_VNDPK_integral_mM": actual_ndpk,
                "conditional_required_VNDPK_integral_mM": required_ndpk,
                "additional_VNDPK_integral_mM": required_ndpk - actual_ndpk,
                "required_vmax_VNDPK_at_fixed_states": required_vmax,
            }
        )
    return rows


def _plot(
    frame: pd.DataFrame,
    forward: np.ndarray,
    reverse: np.ndarray,
    teacher_atp_net: np.ndarray,
    rows: Sequence[Mapping[str, float]],
    out_path: Path,
) -> None:
    time = frame["time_day"].to_numpy(dtype=float)
    fig, axes = plt.subplots(2, 2, figsize=(13.2, 8.8), constrained_layout=True)
    axes[0, 0].plot(time, frame["ATP"], label="model ATP", color="#d1495b", lw=2)
    axes[0, 0].plot(time, frame["ATP_teacher"], "k--", label="Brodbar ATP", lw=2)
    axes[0, 0].set_title("ATP availability")
    axes[0, 0].set_ylabel("mM")
    axes[0, 0].legend()

    axes[0, 1].plot(time, forward, label="NDPK forward", color="#457b9d", lw=2)
    axes[0, 1].plot(time, reverse, label="NDPK reverse", color="#2a9d8f", lw=2)
    axes[0, 1].plot(time, frame["VNDPK"], label="NDPK net", color="#333333", lw=2)
    axes[0, 1].set_title("Native NDPK components")
    axes[0, 1].set_ylabel("mM/day")
    axes[0, 1].legend()

    axes[1, 0].plot(time, frame["VNDPK"], label="model ATP", color="#457b9d", lw=2)
    axes[1, 0].plot(
        time,
        teacher_atp_net,
        label="counterfactual Brodbar ATP and ADP",
        color="#d1495b",
        lw=2,
    )
    axes[1, 0].set_yscale("symlog", linthresh=1e-3)
    axes[1, 0].set_title("NDPK response to conditional ATP/ADP replacement")
    axes[1, 0].set_ylabel("mM/day")
    axes[1, 0].legend()

    labels = [f"J{row['start_day']:g}-J{row['end_day']:g}" for row in rows]
    x = np.arange(len(labels))
    axes[1, 1].bar(
        x - 0.18,
        [row["actual_VNDPK_integral_mM"] for row in rows],
        width=0.36,
        label="actual",
        color="#457b9d",
    )
    axes[1, 1].bar(
        x + 0.18,
        [row["conditional_required_VNDPK_integral_mM"] for row in rows],
        width=0.36,
        label="conditional required",
        color="#d1495b",
    )
    axes[1, 1].set_xticks(x, labels)
    axes[1, 1].set_title("NDPK window integrals")
    axes[1, 1].set_ylabel("mM")
    axes[1, 1].legend()
    for axis in axes.flat:
        axis.set_xlabel("Storage day" if axis is not axes[1, 1] else "Window")
        axis.grid(alpha=0.2)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def run(source_dir: Path, map_summary: Path, anchor: Path, out_dir: Path) -> dict[str, Any]:
    all_frame = pd.read_csv(source_dir / "J1_J46_timeseries.csv")
    frame = all_frame.loc[all_frame["candidate"] == SOURCE_LABEL].copy()
    if frame.empty:
        raise ValueError(f"candidate {SOURCE_LABEL!r} is absent")
    exp_time, curves, *_ = _load_brodbar_panel()
    _state, params, seed_path, _vampd1 = _build_anchor(anchor)
    defaults = {
        "km_GDP": 0.3,
        "km_GTP": 0.5,
        "km_ADP": 0.402663,
    }
    values = {
        "vmax_VNDPK": float(params["vmax_VNDPK"]),
        "vmax_VNDPK_rev": float(params["vmax_VNDPK_rev"]),
        "km_GDP": float(params.get("km_GDP", defaults["km_GDP"])),
        "km_ATP": float(params["km_ATP"]),
        "km_GTP": float(params.get("km_GTP", defaults["km_GTP"])),
        "km_ADP": float(params.get("km_ADP", defaults["km_ADP"])),
    }
    forward, reverse, net = ndpk_components(
        gdp=frame["GDP"],
        atp=frame["ATP"],
        gtp=frame["GTP"],
        adp=frame["ADP"],
        vmax_forward=values["vmax_VNDPK"],
        vmax_reverse=values["vmax_VNDPK_rev"],
        km_gdp=values["km_GDP"],
        km_atp=values["km_ATP"],
        km_gtp=values["km_GTP"],
        km_adp=values["km_ADP"],
    )
    reconstruction_error = float(
        np.max(np.abs(net - frame["VNDPK"].to_numpy(dtype=float)))
    )
    vadss_targets = build_joint_vadss_targets(
        frame,
        exp_time,
        curves,
        frame["VADSS"].to_numpy(dtype=float),
    )
    forward_drive = forward / values["vmax_VNDPK"]
    window_rows = conditional_ndpk_windows(
        frame=frame,
        vadss_targets=vadss_targets,
        forward_drive=forward_drive,
        reverse_rate=reverse,
    )
    teacher_forward, _teacher_reverse, teacher_net = ndpk_components(
        gdp=frame["GDP"],
        atp=frame["ATP_teacher"],
        gtp=frame["GTP"],
        adp=frame["ADP_teacher"],
        vmax_forward=values["vmax_VNDPK"],
        vmax_reverse=values["vmax_VNDPK_rev"],
        km_gdp=values["km_GDP"],
        km_atp=values["km_ATP"],
        km_gtp=values["km_GTP"],
        km_adp=values["km_ADP"],
    )
    actual_total = sum(row["actual_VNDPK_integral_mM"] for row in window_rows)
    required_total = sum(
        row["conditional_required_VNDPK_integral_mM"] for row in window_rows
    )
    required_capacities = np.asarray(
        [row["required_vmax_VNDPK_at_fixed_states"] for row in window_rows]
    )
    capacity_ratio = float(required_capacities.max() / required_capacities.min())
    initial_gtp = float(frame["GTP"].iloc[0])
    required_vadss_total = sum(
        target.required_unknown_flux_integral_mM for target in vadss_targets
    )
    minimum_ndpk_for_nonnegative_gtp = max(required_vadss_total - initial_gtp, 0.0)
    model_atp_saturation = michaelis_fraction(frame["ATP"], values["km_ATP"])
    teacher_atp_saturation = michaelis_fraction(
        frame["ATP_teacher"], values["km_ATP"]
    )

    summary = {
        "contract_type": "conditional_GTP_NDPK_feasibility_audit",
        "contract_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "optimization_performed": False,
        "parameters_promoted": False,
        "source_screen": str(source_dir.resolve()),
        "source_map": str(map_summary.resolve()),
        "source_anchor": str(anchor.resolve()),
        "seed_params_path": str(seed_path.resolve()),
        "parameters": values,
        "maximum_VNDPK_reconstruction_error": reconstruction_error,
        "window_results": window_rows,
        "actual_VNDPK_total_mM": actual_total,
        "conditional_required_VNDPK_total_mM": required_total,
        "additional_total_VNDPK_mM": required_total - actual_total,
        "required_VADSS_total_mM": required_vadss_total,
        "minimum_VNDPK_for_nonnegative_terminal_GTP_mM": minimum_ndpk_for_nonnegative_gtp,
        "required_fixed_state_capacity_ratio_across_windows": capacity_ratio,
        "ATP": {
            "model_day1_mM": float(frame["ATP"].iloc[0]),
            "model_day46_mM": float(frame["ATP"].iloc[-1]),
            "teacher_day46_mM": float(frame["ATP_teacher"].iloc[-1]),
            "model_saturation_day46": float(model_atp_saturation[-1]),
            "teacher_saturation_day46": float(teacher_atp_saturation[-1]),
            "counterfactual_teacher_ATP_ADP_NDPK_day46_mM_per_day": float(teacher_net[-1]),
        },
        "interpretation": (
            "Conditional capacity demand changes strongly by window, while native NDPK falls "
            "with simulated ATP. Replacing BOTH ATP and ADP by their reference trajectories at "
            "fixed guanylate states strongly increases net NDPK. This conditional counterfactual "
            "suggests energy/guanylate coupling; it neither isolates ATP nor proves parameter "
            "compensation or failed transfer to an energy-corrected model."
        ),
        "decision": (
            "do not calibrate VNDPK or VADSS further; freeze the purine branch and repair ATP "
            "sustainability with a joint energy/guanylate validation contract"
        ),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(window_rows).to_csv(out_dir / "ndpk_window_feasibility.csv", index=False)
    pd.DataFrame(
        {
            "time_day": frame["time_day"],
            "ATP": frame["ATP"],
            "ATP_teacher": frame["ATP_teacher"],
            "GTP": frame["GTP"],
            "GDP": frame["GDP"],
            "VNDPK_forward": forward,
            "VNDPK_reverse": reverse,
            "VNDPK_net": net,
            "VNDPK_counterfactual_teacher_ATP_ADP": teacher_net,
            "VADSS": frame["VADSS"],
        }
    ).to_csv(out_dir / "ndpk_trace.csv", index=False)
    _plot(
        frame,
        forward,
        reverse,
        teacher_net,
        window_rows,
        out_dir / "gtp_ndpk_feasibility.png",
    )
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    report = (
        "# Conditional GTP/NDPK feasibility audit\n\n"
        f"- Native NDPK total: `{actual_total:.5f} mM`.\n"
        f"- Conditional NDPK total required: `{required_total:.5f} mM`.\n"
        f"- Additional NDPK supply: `{required_total - actual_total:.5f} mM`.\n"
        f"- Required fixed-state capacity range: "
        f"`{required_capacities.min():.5g}` to `{required_capacities.max():.5g}` "
        f"(`{capacity_ratio:.1f}x`).\n"
        f"- ATP model/teacher at J46: `{frame['ATP'].iloc[-1]:.5g}` / "
        f"`{frame['ATP_teacher'].iloc[-1]:.5g} mM`.\n"
        f"- ATP saturation model/teacher at J46: `{model_atp_saturation[-1]:.5g}` / "
        f"`{teacher_atp_saturation[-1]:.5g}`.\n\n"
        f"{summary['decision']}\n"
    )
    (out_dir / "decision_report.md").write_text(report, encoding="utf-8")
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--map-summary", type=Path, default=DEFAULT_MAP)
    parser.add_argument("--anchor", type=Path, default=DEFAULT_ANCHOR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)
    summary = run(args.source_dir, args.map_summary, args.anchor, args.out_dir)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
