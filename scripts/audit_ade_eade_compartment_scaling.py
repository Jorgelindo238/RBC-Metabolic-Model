"""Test whether compartment-volume scaling can reconcile independent APRT teachers."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "imp_purine_transfer_vampd1_1p1_vaprt_zero_J1_J46"
)
DEFAULT_OUT_DIR = ROOT / "output" / "ade_eade_compartment_scaling"
ANCHOR_LABEL = "vmax_VAMPD1_1.100x"
HEMATOCRIT_GRID = (0.50, 0.55, 0.60, 0.65, 0.70, 0.75)
SIGN_EPSILON = 1e-12


def external_scale_from_hematocrit(hematocrit: float) -> float:
    """Return the extracellular-to-intracellular volume ratio Ve/Vi."""
    if not 0.0 < hematocrit < 1.0:
        raise ValueError("hematocrit must lie strictly between zero and one")
    return (1.0 - hematocrit) / hematocrit


def amount_consistent_aprt_teacher(
    dade_dt: np.ndarray,
    deade_dt: np.ndarray,
    external_scale: float,
) -> np.ndarray:
    """Infer APRT from -d(ADE + (Ve/Vi) EADE)/dt."""
    if external_scale < 0.0:
        raise ValueError("external_scale must be nonnegative")
    return -(
        np.asarray(dade_dt, dtype=float)
        + external_scale * np.asarray(deade_dt, dtype=float)
    )


def analytical_external_scale(
    *,
    ade_loss: float,
    eade_loss: float,
    target_integral: float,
) -> float | None:
    """Solve ade_loss + scale*eade_loss = target_integral."""
    if np.isclose(eade_loss, 0.0):
        return None
    return (target_integral - ade_loss) / eade_loss


def _integral(values: np.ndarray, time: np.ndarray) -> float:
    return float(np.trapezoid(np.asarray(values, dtype=float), np.asarray(time, dtype=float)))


def _sign_agreement(left: np.ndarray, right: np.ndarray) -> float:
    left_sign = np.where(left > SIGN_EPSILON, 1, np.where(left < -SIGN_EPSILON, -1, 0))
    right_sign = np.where(right > SIGN_EPSILON, 1, np.where(right < -SIGN_EPSILON, -1, 0))
    active = (left_sign != 0) | (right_sign != 0)
    if not np.any(active):
        return 1.0
    return float(np.mean(left_sign[active] == right_sign[active]))


def _normalized_rmse(candidate: np.ndarray, reference: np.ndarray) -> float:
    scale = max(float(np.mean(np.abs(reference))), 0.01)
    return float(np.sqrt(np.mean((candidate - reference) ** 2)) / scale)


def _build_rows(frame: pd.DataFrame) -> tuple[list[dict[str, float]], dict[str, float | None]]:
    time = frame["time_day"].to_numpy(dtype=float)
    dade = frame["dADE_teacher_dt"].to_numpy(dtype=float)
    deade = frame["dEADE_teacher_dt"].to_numpy(dtype=float)
    total_teacher = frame["VAPRT_teacher_from_total_adenylate"].to_numpy(dtype=float)
    ade_loss = float(frame["ADE_teacher"].iloc[0] - frame["ADE_teacher"].iloc[-1])
    eade_loss = float(frame["EADE_teacher"].iloc[0] - frame["EADE_teacher"].iloc[-1])
    total_integral = _integral(total_teacher, time)

    rows: list[dict[str, float]] = []
    for hematocrit in HEMATOCRIT_GRID:
        external_scale = external_scale_from_hematocrit(hematocrit)
        pair_teacher = amount_consistent_aprt_teacher(dade, deade, external_scale)
        pair_integral = _integral(pair_teacher, time)
        endpoint_integral = ade_loss + external_scale * eade_loss
        rows.append(
            {
                "hematocrit_fraction": hematocrit,
                "external_to_intracellular_volume_ratio": external_scale,
                "ADE_loss_mM": ade_loss,
                "scaled_EADE_loss_mM": external_scale * eade_loss,
                "pair_APRT_integral_trapezoid_mM": pair_integral,
                "pair_APRT_integral_endpoint_mM": endpoint_integral,
                "total_adenylate_APRT_integral_mM": total_integral,
                "integrated_disagreement_mM": pair_integral - total_integral,
                "mean_absolute_disagreement_mM_per_day": float(
                    np.mean(np.abs(pair_teacher - total_teacher))
                ),
                "teacher_nrmse": _normalized_rmse(pair_teacher, total_teacher),
                "teacher_sign_agreement_fraction": _sign_agreement(
                    pair_teacher, total_teacher
                ),
                "pair_positive_time_fraction": float(
                    np.mean(pair_teacher > SIGN_EPSILON)
                ),
                "total_positive_time_fraction": float(
                    np.mean(total_teacher > SIGN_EPSILON)
                ),
            }
        )

    analytical = {
        "ADE_loss_mM": ade_loss,
        "EADE_loss_mM": eade_loss,
        "total_adenylate_APRT_integral_mM": total_integral,
        "external_scale_required_for_integral_match": analytical_external_scale(
            ade_loss=ade_loss,
            eade_loss=eade_loss,
            target_integral=total_integral,
        ),
        "external_scale_required_for_zero_pair_APRT": analytical_external_scale(
            ade_loss=ade_loss,
            eade_loss=eade_loss,
            target_integral=0.0,
        ),
    }
    return rows, analytical


def _classify(rows: Sequence[Mapping[str, float]], analytical: Mapping[str, float | None]) -> str:
    all_pair_positive = all(row["pair_APRT_integral_trapezoid_mM"] > 0.0 for row in rows)
    total_negative = float(analytical["total_adenylate_APRT_integral_mM"] or 0.0) < 0.0
    required_scale = analytical["external_scale_required_for_integral_match"]
    if all_pair_positive and total_negative and required_scale is not None and required_scale < 0.0:
        return "reject_volume_scaling_as_resolution_of_APRT_teacher_sign_conflict"
    if any(abs(row["integrated_disagreement_mM"]) <= 0.10 for row in rows):
        return "retain_declared_volume_scaling_as_a_plausible_resolution"
    return "volume_scaling_does_not_resolve_APRT_teacher_magnitude_conflict"


def _plot(frame: pd.DataFrame, rows: Sequence[Mapping[str, float]], out_path: Path) -> None:
    time = frame["time_day"].to_numpy(dtype=float)
    dade = frame["dADE_teacher_dt"].to_numpy(dtype=float)
    deade = frame["dEADE_teacher_dt"].to_numpy(dtype=float)
    total = frame["VAPRT_teacher_from_total_adenylate"].to_numpy(dtype=float)
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2), constrained_layout=True)
    colors = ("#2a9d8f", "#457b9d", "#6a4c93", "#bc6c25", "#d1495b", "#5c677d")
    for color, row in zip(colors, rows):
        teacher = amount_consistent_aprt_teacher(
            dade,
            deade,
            row["external_to_intracellular_volume_ratio"],
        )
        axes[0].plot(
            time,
            teacher,
            color=color,
            lw=1.6,
            label=f"H={row['hematocrit_fraction']:.2f}",
        )
    axes[0].plot(time, total, color="black", lw=2.4, linestyle="--", label="Total adenylate")
    axes[0].axhline(0.0, color="0.55", lw=1)
    axes[0].set_title("Independent APRT teacher trajectories")
    axes[0].set_xlabel("Storage day")
    axes[0].set_ylabel("Required APRT flux (mM/day)")
    axes[0].grid(alpha=0.2)
    axes[0].legend(fontsize=8, ncol=2)

    hematocrit = [row["hematocrit_fraction"] for row in rows]
    pair_integral = [row["pair_APRT_integral_trapezoid_mM"] for row in rows]
    total_integral = rows[0]["total_adenylate_APRT_integral_mM"]
    axes[1].plot(hematocrit, pair_integral, "o-", color="#d1495b", lw=2, label="ADE + scaled EADE")
    axes[1].axhline(total_integral, color="black", lw=2, linestyle="--", label="Total adenylate")
    axes[1].axhline(0.0, color="0.55", lw=1)
    axes[1].set_title("J1-J46 integrated APRT requirement")
    axes[1].set_xlabel("Hematocrit fraction")
    axes[1].set_ylabel("Required APRT amount (mM equivalent)")
    axes[1].grid(alpha=0.2)
    axes[1].legend(fontsize=8)
    fig.suptitle("ADE/EADE compartment-scaling feasibility audit", fontsize=14)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    analytical = summary["analytical_requirements"]
    best = summary["least_disagreeing_grid_point"]
    lines = [
        "# ADE/EADE compartment-scaling audit",
        "",
        "## Contract",
        "",
        "- Fixed VAMPD1 1.1x / VAPRT=0 replay; no ODE simulation or parameter optimization.",
        "- External EADE was converted to an intracellular-equivalent amount with `Ve/Vi = (1-H)/H`.",
        "- Hematocrit was evaluated on a declared grid and was not fitted to ADE/EADE.",
        "",
        "## J1-J46 result",
        "",
        f"- Measured ADE loss: `{analytical['ADE_loss_mM']:.6g} mM`.",
        f"- Measured EADE loss: `{analytical['EADE_loss_mM']:.6g} mM` before volume conversion.",
        f"- Total-adenylate APRT requirement: `{analytical['total_adenylate_APRT_integral_mM']:.6g} mM`.",
        f"- Least-disagreeing physiological grid point: `H={best['hematocrit_fraction']:.2f}`, pair requirement `{best['pair_APRT_integral_trapezoid_mM']:.6g} mM`.",
        f"- Exact external scale required to match the total-pool integral: `{analytical['external_scale_required_for_integral_match']:.6g}`.",
        "",
        "## Decision",
        "",
        summary["decision"],
        "",
        summary["rationale"],
        "",
        f"Next: {summary['next_step']}.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_audit(*, source_dir: Path, out_dir: Path) -> dict[str, Any]:
    source_path = source_dir / "J1_J46_purine_audit_timeseries.csv"
    frame = pd.read_csv(source_path)
    frame = frame.loc[frame["candidate"] == ANCHOR_LABEL].reset_index(drop=True)
    if frame.empty:
        raise RuntimeError(f"Missing fixed anchor {ANCHOR_LABEL}")
    required = {
        "time_day",
        "ADE_teacher",
        "EADE_teacher",
        "dADE_teacher_dt",
        "dEADE_teacher_dt",
        "VAPRT_teacher_from_total_adenylate",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise RuntimeError(f"Source audit is missing columns: {missing}")

    rows, analytical = _build_rows(frame)
    classification = _classify(rows, analytical)
    best = min(rows, key=lambda row: abs(row["integrated_disagreement_mM"]))
    if classification == "reject_volume_scaling_as_resolution_of_APRT_teacher_sign_conflict":
        decision = "reject H1: physiological ADE/EADE volume scaling cannot resolve the APRT teacher conflict"
        rationale = (
            "ADE and EADE both decrease, so every nonnegative compartment-volume factor requires "
            "positive adenine-pool removal. The independent total-adenylate balance instead requires "
            "a negative net APRT contribution. Integral agreement would require a negative external "
            "volume, which is physically inadmissible."
        )
        next_step = (
            "test an optional extracellular EADE loss and a separate adenylate exit as fixed-kinetic "
            "structural hypotheses before reopening kinetic calibration"
        )
    else:
        decision = "retain compartment scaling for a metadata-resolved follow-up"
        rationale = "At least one declared volume conversion reduces the independent APRT discrepancy."
        next_step = "obtain compartment-volume metadata and validate the conversion outside ADE/EADE"

    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out_dir / "hematocrit_aprt_teacher_grid.csv", index=False)
    _plot(frame, rows, out_dir / "ade_eade_compartment_scaling.png")
    summary = {
        "contract_type": "fixed_kinetic_ADE_EADE_compartment_scaling_feasibility",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_timeseries": str(source_path.resolve()),
        "anchor_candidate": ANCHOR_LABEL,
        "optimization_performed": False,
        "parameters_promoted": False,
        "hematocrit_fitted": False,
        "amount_balance": "APRT_pair_T = -d(ADE_T + (Ve/Vi)*EADE_T)/dt",
        "volume_contract": "Ve/Vi = (1-H)/H",
        "hematocrit_grid": list(HEMATOCRIT_GRID),
        "analytical_requirements": analytical,
        "grid_rows": rows,
        "least_disagreeing_grid_point": best,
        "classification": classification,
        "decision": decision,
        "rationale": rationale,
        "next_step": next_step,
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "report": str(out_dir / "decision_report.md"),
            "grid": str(out_dir / "hematocrit_aprt_teacher_grid.csv"),
            "plot": str(out_dir / "ade_eade_compartment_scaling.png"),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _write_report(out_dir / "decision_report.md", summary)
    print(
        json.dumps(
            {
                "classification": classification,
                "required_external_scale": analytical[
                    "external_scale_required_for_integral_match"
                ],
                "best_grid_hematocrit": best["hematocrit_fraction"],
                "best_grid_pair_integral_mM": best[
                    "pair_APRT_integral_trapezoid_mM"
                ],
                "total_teacher_integral_mM": analytical[
                    "total_adenylate_APRT_integral_mM"
                ],
                "report": str(out_dir / "decision_report.md"),
            },
            indent=2,
        )
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_audit(source_dir=args.source_dir, out_dir=args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
