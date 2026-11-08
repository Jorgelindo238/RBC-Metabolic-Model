"""Map a storage-activity decay law for VAMPD1 on fixed Brodbar replay states."""

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
DEFAULT_SOURCE_DIR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "imp_purine_transfer_vampd1_1p1_vaprt_zero_J1_J46"
)
DEFAULT_OUT_DIR = ROOT / "output" / "vampd1_storage_decay_map"
ANCHOR_LABEL = "vmax_VAMPD1_1.100x"
WINDOWS = ((1.0, 11.0), (11.0, 22.0), (22.0, 46.0))
VMAX0_GRID = (0.09, 0.10, 0.11, 0.12, 0.125, 0.13)
DECAY_GRID = (0.0, 0.005, 0.010, 0.0125, 0.015, 0.020)
for path in (str(SRC), str(SCRIPTS)):
    if path not in sys.path:
        sys.path.insert(0, path)

from evaluate_brodbar_candidate_full_panel import _load_brodbar_panel  # noqa: E402
from fla_integrated_flux import build_integrated_flux_targets, integrated_flux_nrmse  # noqa: E402
from fla_validation_v2 import pareto_front  # noqa: E402


def activity_decay_flux(
    *,
    saturation_trace: np.ndarray,
    time: np.ndarray,
    vmax_initial: float,
    decay_per_day: float,
) -> np.ndarray:
    if vmax_initial < 0.0 or decay_per_day < 0.0:
        raise ValueError("vmax_initial and decay_per_day must be nonnegative")
    elapsed = np.maximum(np.asarray(time, dtype=float) - float(time[0]), 0.0)
    return (
        float(vmax_initial)
        * np.exp(-float(decay_per_day) * elapsed)
        * np.asarray(saturation_trace, dtype=float)
    )


def _targets(
    *,
    exp_time: np.ndarray,
    values: np.ndarray,
    time: np.ndarray,
    known_rate: np.ndarray,
    candidate_rate: np.ndarray,
    coefficient: float,
) -> tuple:
    return build_integrated_flux_targets(
        measurement_time=exp_time,
        measurement_values=values,
        dense_time=time,
        known_rate=known_rate,
        model_unknown_rate=candidate_rate,
        unknown_stoichiometric_coefficient=coefficient,
        windows=WINDOWS,
    )


def _rate_window_integrals(
    time: np.ndarray, rate: np.ndarray
) -> np.ndarray:
    values = []
    for start, end in WINDOWS:
        mask = (time >= start - 1e-10) & (time <= end + 1e-10)
        values.append(float(np.trapezoid(rate[mask], time[mask])))
    return np.asarray(values, dtype=float)


def _sensitivity_diagnostics(
    *,
    saturation: np.ndarray,
    time: np.ndarray,
    vmax_initial: float,
    decay_per_day: float,
) -> dict[str, Any]:
    epsilon = 1e-4

    def outputs(vmax: float, decay: float) -> np.ndarray:
        return _rate_window_integrals(
            time,
            activity_decay_flux(
                saturation_trace=saturation,
                time=time,
                vmax_initial=vmax,
                decay_per_day=decay,
            ),
        )

    vmax_plus = outputs(vmax_initial * np.exp(epsilon), decay_per_day)
    vmax_minus = outputs(vmax_initial * np.exp(-epsilon), decay_per_day)
    decay_plus = outputs(vmax_initial, decay_per_day * np.exp(epsilon))
    decay_minus = outputs(vmax_initial, decay_per_day * np.exp(-epsilon))
    jacobian = np.column_stack(
        [
            (vmax_plus - vmax_minus) / (2.0 * epsilon),
            (decay_plus - decay_minus) / (2.0 * epsilon),
        ]
    )
    row_scale = np.maximum(np.abs(outputs(vmax_initial, decay_per_day)), 0.05)
    normalized = jacobian / row_scale[:, None]
    singular_values = np.linalg.svd(normalized, compute_uv=False)
    rank = int(np.sum(singular_values > singular_values[0] * 1e-8))
    condition = float(singular_values[0] / singular_values[-1])
    return {
        "parameterization": "log(vmax_initial), log(storage_decay)",
        "window_integral_jacobian": normalized.tolist(),
        "singular_values": singular_values.tolist(),
        "rank": rank,
        "condition_number": condition,
        "identifiable": bool(rank == 2 and condition < 100.0),
    }


def _build_rows(
    frame: pd.DataFrame,
    exp_time: np.ndarray,
    curves: Mapping[str, np.ndarray],
    anchor_vmax: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    time = frame["time_day"].to_numpy(dtype=float)
    saturation = frame["VAMPD1"].to_numpy(dtype=float) / float(anchor_vmax)
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
    total_curve = sum(
        np.asarray(curves[name], dtype=float) for name in ("ATP", "ADP", "AMP")
    )
    rows: list[dict[str, Any]] = []
    for vmax_initial in VMAX0_GRID:
        for decay in DECAY_GRID:
            candidate = activity_decay_flux(
                saturation_trace=saturation,
                time=time,
                vmax_initial=vmax_initial,
                decay_per_day=decay,
            )
            imp_targets = _targets(
                exp_time=exp_time,
                values=np.asarray(curves["IMP"], dtype=float),
                time=time,
                known_rate=imp_known,
                candidate_rate=candidate,
                coefficient=1.0,
            )
            total_targets = _targets(
                exp_time=exp_time,
                values=total_curve,
                time=time,
                known_rate=total_known,
                candidate_rate=candidate,
                coefficient=-1.0,
            )
            imp_score = integrated_flux_nrmse(imp_targets)
            total_score = integrated_flux_nrmse(total_targets)
            rows.append(
                {
                    "vmax_VAMPD1_initial": vmax_initial,
                    "storage_decay_VAMPD1_per_day": decay,
                    "IMP_integrated_flux_nrmse": imp_score,
                    "adenylate_integrated_flux_nrmse": total_score,
                    "combined_score": float(np.sqrt((imp_score**2 + total_score**2) / 2.0)),
                    "predicted_VAMPD1_integral_mM": float(np.trapezoid(candidate, time)),
                    "IMP_windows": [target.to_dict() for target in imp_targets],
                    "adenylate_windows": [target.to_dict() for target in total_targets],
                }
            )
    indices = pareto_front(
        rows,
        {
            "IMP_integrated_flux_nrmse": "min",
            "adenylate_integrated_flux_nrmse": "min",
        },
    )
    for index, row in enumerate(rows):
        row["pareto_nondominated"] = index in indices
    selected = min(rows, key=lambda row: row["combined_score"])
    return rows, selected


def _plot(rows: Sequence[Mapping[str, Any]], selected: Mapping[str, Any], out_path: Path) -> None:
    frame = pd.DataFrame(rows)
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.2), constrained_layout=True)
    for vmax, local in frame.groupby("vmax_VAMPD1_initial"):
        local = local.sort_values("storage_decay_VAMPD1_per_day")
        axes[0].plot(
            local["storage_decay_VAMPD1_per_day"],
            local["IMP_integrated_flux_nrmse"],
            marker="o",
            label=f"vmax0={vmax:.3f}",
        )
        axes[1].plot(
            local["storage_decay_VAMPD1_per_day"],
            local["adenylate_integrated_flux_nrmse"],
            marker="o",
            label=f"vmax0={vmax:.3f}",
        )
    for axis, title in zip(axes, ("IMP balance teacher", "ATP+ADP+AMP balance teacher")):
        axis.scatter(
            [selected["storage_decay_VAMPD1_per_day"]],
            [
                selected[
                    "IMP_integrated_flux_nrmse"
                    if axis is axes[0]
                    else "adenylate_integrated_flux_nrmse"
                ]
            ],
            marker="*",
            s=180,
            color="black",
            zorder=5,
        )
        axis.set_title(title)
        axis.set_xlabel("VAMPD1 activity decay (day^-1)")
        axis.set_ylabel("Integrated-flux nRMSE")
        axis.grid(alpha=0.2)
    axes[0].legend(fontsize=7, ncol=2)
    fig.suptitle("Fixed-state VAMPD1 storage-decay feasibility map", fontsize=14)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def run(*, source_dir: Path, out_dir: Path) -> dict[str, Any]:
    source_summary = json.loads((source_dir / "summary.json").read_text(encoding="utf-8"))
    anchor_vmax = float(source_summary["anchor_vmax_VAMPD1"])
    frame = pd.read_csv(source_dir / "J1_J46_purine_audit_timeseries.csv")
    frame = frame.loc[frame["candidate"] == ANCHOR_LABEL].reset_index(drop=True)
    exp_time, curves, _order, _indices, _unmapped = _load_brodbar_panel()
    rows, selected = _build_rows(frame, exp_time, curves, anchor_vmax)
    time = frame["time_day"].to_numpy(dtype=float)
    saturation = frame["VAMPD1"].to_numpy(dtype=float) / anchor_vmax
    sensitivity = _sensitivity_diagnostics(
        saturation=saturation,
        time=time,
        vmax_initial=float(selected["vmax_VAMPD1_initial"]),
        decay_per_day=float(selected["storage_decay_VAMPD1_per_day"]),
    )
    baseline = next(
        row
        for row in rows
        if np.isclose(row["vmax_VAMPD1_initial"], anchor_vmax, atol=0.002)
        and np.isclose(row["storage_decay_VAMPD1_per_day"], 0.0)
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    flat = pd.DataFrame(
        [
            {key: value for key, value in row.items() if not isinstance(value, list)}
            for row in rows
        ]
    )
    flat.to_csv(out_dir / "vampd1_storage_decay_grid.csv", index=False)
    _plot(rows, selected, out_dir / "vampd1_storage_decay_map.png")
    improvement = float(
        (baseline["combined_score"] - selected["combined_score"])
        / baseline["combined_score"]
    )
    summary = {
        "contract_type": "fixed_state_VAMPD1_storage_activity_decay_map",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_dir": str(source_dir.resolve()),
        "optimization_performed": False,
        "parameters_promoted": False,
        "windows": [list(window) for window in WINDOWS],
        "vmax_initial_grid": list(VMAX0_GRID),
        "decay_grid": list(DECAY_GRID),
        "anchor_vmax_VAMPD1": anchor_vmax,
        "baseline_grid_row": baseline,
        "selected_fixed_state_row": selected,
        "sensitivity_diagnostics": sensitivity,
        "combined_score_improvement": improvement,
        "decision": (
            "advance the selected VAMPD1 storage-decay point to a full ODE replay only; "
            "fixed-state mapping is not parameter promotion"
        ),
        "next_step": (
            "enable the decay law behind an option and test the selected point against full-state "
            "IMP, ATP/ADP/AMP, purine-panel, numerical, and external-validation guards"
        ),
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "report": str(out_dir / "decision_report.md"),
            "grid": str(out_dir / "vampd1_storage_decay_grid.csv"),
            "plot": str(out_dir / "vampd1_storage_decay_map.png"),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    report = [
        "# VAMPD1 storage-decay feasibility map",
        "",
        "The map reweights the fixed anchor flux by `vmax0 * exp(-k*(t-1))` and scores measured-endpoint integrated balances. It does not rerun or fit the ODE.",
        "",
        f"- Selected map point: `vmax0={selected['vmax_VAMPD1_initial']:.6g}`, `k={selected['storage_decay_VAMPD1_per_day']:.6g} day^-1`.",
        f"- IMP integrated-flux nRMSE: `{baseline['IMP_integrated_flux_nrmse']:.5g} -> {selected['IMP_integrated_flux_nrmse']:.5g}`.",
        f"- Adenylate integrated-flux nRMSE: `{baseline['adenylate_integrated_flux_nrmse']:.5g} -> {selected['adenylate_integrated_flux_nrmse']:.5g}`.",
        f"- Combined improvement: `{improvement:.1%}`.",
        f"- Local window-integral sensitivity rank/condition: `{sensitivity['rank']}` / `{sensitivity['condition_number']:.5g}`.",
        "",
        summary["decision"],
    ]
    (out_dir / "decision_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "selected": {
                    "vmax0": selected["vmax_VAMPD1_initial"],
                    "decay": selected["storage_decay_VAMPD1_per_day"],
                    "IMP_nrmse": selected["IMP_integrated_flux_nrmse"],
                    "adenylate_nrmse": selected["adenylate_integrated_flux_nrmse"],
                },
                "combined_improvement": improvement,
                "report": str(out_dir / "decision_report.md"),
            },
            indent=2,
        )
    )
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)
    run(source_dir=args.source_dir, out_dir=args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
