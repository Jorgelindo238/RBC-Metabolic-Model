"""Map the non-identifiable purine flux continuum implied by Brodbar teachers."""

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
DEFAULT_SOURCE = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "imp_purine_transfer_vampd1_1p1_vaprt_zero_J1_J46"
    / "summary.json"
)
DEFAULT_OUT_DIR = ROOT / "output" / "purine_structure_feasibility"
ANCHOR_LABEL = "vmax_VAMPD1_1.100x"


def structural_fluxes(
    *,
    aprt_integral: float,
    ade_loss: float,
    eade_loss: float,
    total_aprt_equivalent: float,
) -> dict[str, float]:
    """Solve integrated ADE, EADE, and adenylate balances for one APRT choice.

    Positive VEADE denotes ADE efflux, EADE_loss removes extracellular adenine,
    and AMP_NT denotes an AMP-to-adenosine adenylate exit.
    """
    pair_loss = ade_loss + eade_loss
    return {
        "APRT_integral_mM": aprt_integral,
        "VEADE_integral_mM": ade_loss - aprt_integral,
        "EADE_loss_integral_mM": pair_loss - aprt_integral,
        "AMP_NT_integral_mM": aprt_integral - total_aprt_equivalent,
    }


def _anchor(summary: Mapping[str, Any]) -> Mapping[str, Any]:
    return summary["metrics"]["J1_J46"][ANCHOR_LABEL]


def _build_rows(anchor: Mapping[str, Any], points: int = 101) -> tuple[list[dict[str, float]], dict[str, float]]:
    states = anchor["state_metrics"]
    ade_loss = -float(states["ADE"]["teacher_change_mM"])
    eade_loss = -float(states["EADE"]["teacher_change_mM"])
    pair_loss = ade_loss + eade_loss
    total_equivalent = float(
        anchor["VAPRT_teacher_from_total_adenylate"]["integral_mM"]
    )
    prpp = anchor["PRPP_contributions_mM"]
    current_prpp_headroom = float(
        1.0
        + prpp["VPRPPASe"]
        + prpp["VAPRT"]
        + prpp["VHGPRT1"]
        + prpp["VHGPRT2"]
        - anchor["PRPP_endpoint_mM"]
    )
    recoverable_hgprt = -float(prpp["VHGPRT1"] + prpp["VHGPRT2"])

    rows: list[dict[str, float]] = []
    for aprt in np.linspace(0.0, pair_loss, points):
        row = structural_fluxes(
            aprt_integral=float(aprt),
            ade_loss=ade_loss,
            eade_loss=eade_loss,
            total_aprt_equivalent=total_equivalent,
        )
        required_release = max(0.0, float(aprt) - current_prpp_headroom)
        row.update(
            {
                "fraction_of_pair_loss_assigned_to_APRT": float(aprt / pair_loss),
                "additional_PRPP_requirement_mM": float(aprt),
                "required_HGPRT_release_mM_at_fixed_PRPP_production": required_release,
                "required_fraction_of_current_HGPRT_consumption": (
                    required_release / recoverable_hgprt
                    if recoverable_hgprt > 0.0
                    else float("inf")
                ),
            }
        )
        rows.append(row)

    hypx_teacher_change = float(states["HYPX"]["teacher_change_mM"]) + float(
        states["EHYPX"]["teacher_change_mM"]
    )
    hypx_model_change = float(states["HYPX"]["model_change_mM"]) + float(
        states["EHYPX"]["model_change_mM"]
    )
    facts = {
        "ADE_teacher_loss_mM": ade_loss,
        "EADE_teacher_loss_mM": eade_loss,
        "ADE_EADE_pair_loss_mM": pair_loss,
        "total_adenylate_APRT_equivalent_mM": total_equivalent,
        "minimum_required_AMP_NT_integral_mM": -total_equivalent,
        "maximum_required_AMP_NT_integral_mM": pair_loss - total_equivalent,
        "current_PRPP_headroom_mM": current_prpp_headroom,
        "current_HGPRT_consumption_mM": recoverable_hgprt,
        "HYPX_EHYPX_teacher_change_mM": hypx_teacher_change,
        "HYPX_EHYPX_model_change_mM": hypx_model_change,
        "HYPX_EHYPX_change_deficit_mM": hypx_teacher_change - hypx_model_change,
    }
    return rows, facts


def _corner_rows(rows: Sequence[Mapping[str, float]]) -> list[Mapping[str, float]]:
    indices = (0, len(rows) // 2, len(rows) - 1)
    return [rows[index] for index in indices]


def _plot(rows: Sequence[Mapping[str, float]], out_path: Path) -> None:
    frame = pd.DataFrame(rows)
    x = frame["APRT_integral_mM"]
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2), constrained_layout=True)
    axes[0].plot(x, frame["VEADE_integral_mM"], color="#457b9d", lw=2, label="VEADE")
    axes[0].plot(x, frame["EADE_loss_integral_mM"], color="#d1495b", lw=2, label="EADE loss")
    axes[0].plot(x, frame["AMP_NT_integral_mM"], color="#2a9d8f", lw=2, label="AMP -> ADO")
    axes[0].axhline(0.0, color="0.55", lw=1)
    axes[0].set_title("Balance-compatible structural continuum")
    axes[0].set_xlabel("Integrated APRT flux (mM)")
    axes[0].set_ylabel("Required integrated flux (mM)")
    axes[0].grid(alpha=0.2)
    axes[0].legend()

    axes[1].plot(
        x,
        frame["required_fraction_of_current_HGPRT_consumption"],
        color="#6a4c93",
        lw=2,
    )
    axes[1].axhline(1.0, color="#d1495b", lw=1.5, linestyle="--", label="all current HGPRT")
    axes[1].set_title("PRPP coupling at fixed production")
    axes[1].set_xlabel("Integrated APRT flux (mM)")
    axes[1].set_ylabel("Fraction of current HGPRT flux to release")
    axes[1].grid(alpha=0.2)
    axes[1].legend()
    fig.suptitle("Purine structural feasibility before kinetic calibration", fontsize=14)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    facts = summary["facts"]
    corners = summary["representative_hypotheses"]
    lines = [
        "# Purine structural-feasibility audit",
        "",
        "## Exact integrated constraints",
        "",
        "For nonnegative APRT `P`, adenine efflux `T`, extracellular adenine loss `L`, and AMP-to-adenosine exit `N`:",
        "",
        "- `T + P = ADE loss`",
        "- `-T + L = EADE loss`",
        "- `P - N = total-adenylate APRT-equivalent requirement`",
        "",
        f"Brodbar therefore permits a continuum `0 <= P <= {facts['ADE_EADE_pair_loss_mM']:.6g} mM`, not one identified mechanism.",
        f"Every feasible point requires `N >= {facts['minimum_required_AMP_NT_integral_mM']:.6g} mM`; the current network has no AMP-to-ADO reaction.",
        "",
        "## Representative corners",
        "",
    ]
    for row in corners:
        lines.append(
            "- "
            f"P=`{row['APRT_integral_mM']:.4g}`, T=`{row['VEADE_integral_mM']:.4g}`, "
            f"L=`{row['EADE_loss_integral_mM']:.4g}`, N=`{row['AMP_NT_integral_mM']:.4g} mM`."
        )
    lines.extend(
        [
            "",
            "## Coupled evidence",
            "",
            f"- Current PRPP headroom is `{facts['current_PRPP_headroom_mM']:.6g} mM`; positive APRT therefore requires reduced HGPRT use or increased PRPP supply.",
            f"- HYPX+EHYPX rises `{facts['HYPX_EHYPX_change_deficit_mM']:.6g} mM` more in the teacher than in the model, independently supporting an audit of excessive HGPRT salvage and/or missing upstream purine degradation.",
            "- ADO and EADO are not measured in the Brodbar panel, so AMP-to-ADO activity must be judged through IMP/INO/EINO/HYPX/EHYPX transfer and external validation.",
            "",
            "## Decision",
            "",
            summary["decision"],
            "",
            f"Next: {summary['next_step']}.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_audit(*, source: Path, out_dir: Path) -> dict[str, Any]:
    payload = json.loads(source.read_text(encoding="utf-8"))
    anchor = _anchor(payload)
    rows, facts = _build_rows(anchor)
    corners = _corner_rows(rows)
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out_dir / "purine_structural_continuum.csv", index=False)
    _plot(rows, out_dir / "purine_structural_continuum.png")
    summary = {
        "contract_type": "fixed_kinetic_purine_structural_feasibility",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_summary": str(source.resolve()),
        "optimization_performed": False,
        "parameters_promoted": False,
        "facts": facts,
        "representative_hypotheses": corners,
        "classification": "structurally_feasible_but_non_identifiable_flux_continuum",
        "decision": (
            "add no fitted sink yet; implement AMP-to-ADO 5'-nucleotidase as an optional, "
            "default-off structural branch and test it at fixed kinetics"
        ),
        "next_step": (
            "screen AMP-to-ADO activity against ATP/ADP/AMP, IMP, INO/EINO, HYPX/EHYPX, "
            "then compare APRT/EADE-loss corners under the FLA validation-v2 gates"
        ),
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "report": str(out_dir / "decision_report.md"),
            "continuum": str(out_dir / "purine_structural_continuum.csv"),
            "plot": str(out_dir / "purine_structural_continuum.png"),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _write_report(out_dir / "decision_report.md", summary)
    print(
        json.dumps(
            {
                "classification": summary["classification"],
                "minimum_AMP_NT_mM": facts["minimum_required_AMP_NT_integral_mM"],
                "maximum_AMP_NT_mM": facts["maximum_required_AMP_NT_integral_mM"],
                "PRPP_headroom_mM": facts["current_PRPP_headroom_mM"],
                "report": str(out_dir / "decision_report.md"),
            },
            indent=2,
        )
    )
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)
    run_audit(source=args.source, out_dir=args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
