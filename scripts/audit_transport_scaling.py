"""Audit compartment-volume and time-unit assumptions of transport fluxes."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
DEFAULT_OUT_DIR = ROOT / "output" / "transport_scaling_audit_2026_08_11"
PHASE_A_SUMMARY = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "extracellular_flux_phase_ab"
    / "phase_ab_summary.json"
)
UNIT_LABEL_COMMIT = "44cca13e7ea522a883bb745ab6c0ea297bf1d5d2"
HEMATOCRIT_GRID = (0.50, 0.55, 0.60, 0.65, 0.70, 0.75)

for path in (str(ROOT), str(SRC_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import rbc_stoichiometry as STOICH  # noqa: E402
from equadiff_brodbar import (  # noqa: E402
    MODEL_NETWORK_VERSION,
    MODEL_TIME_UNIT,
    TRANSPORT_VOLUME_SCALING_MODE,
)


def _paired_transport_inventory() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    paired: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for reaction, coefficients in STOICH.STOICHIOMETRY.items():
        if not reaction.startswith("VE"):
            continue
        external = {name: value for name, value in coefficients.items() if name.startswith("E")}
        internal = {name: value for name, value in coefficients.items() if not name.startswith("E")}
        if not external:
            continue
        if (
            len(external) == 1
            and len(internal) == 1
            and np.isclose(sum(external.values()) + sum(internal.values()), 0.0)
        ):
            paired.append(
                {
                    "reaction": reaction,
                    "internal_metabolite": next(iter(internal)),
                    "external_metabolite": next(iter(external)),
                    "internal_coefficient": float(next(iter(internal.values()))),
                    "external_coefficient": float(next(iter(external.values()))),
                    "current_concentration_derivative_ratio": 1.0,
                }
            )
        elif reaction not in {"VEGSH_deg", "VEGSSG_deg"}:
            unresolved.append({"reaction": reaction, "stoichiometry": coefficients})
    return paired, unresolved


def _teacher_diagnostics() -> Mapping[str, Any]:
    payload = json.loads(PHASE_A_SUMMARY.read_text(encoding="utf-8"))
    return payload["phase_a"]["dataset_summary"]["diagnostics"]


def _scaling_rows(diagnostics: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for hematocrit in HEMATOCRIT_GRID:
        ratio = hematocrit / (1.0 - hematocrit)
        multiplier = 1.0 / ratio
        for reaction, values in diagnostics.items():
            mean_abs = float(values["mean_abs_flux"])
            rows.append(
                {
                    "hematocrit_fraction": hematocrit,
                    "intracellular_to_extracellular_volume_ratio": ratio,
                    "external_derivative_to_intracellular_flux_multiplier": multiplier,
                    "reaction": reaction,
                    "legacy_teacher_mean_abs_mM_per_day": mean_abs,
                    "volume_corrected_intracellular_mean_abs_mM_per_day": mean_abs * multiplier,
                }
            )
    return rows


def _time_unit_evidence() -> dict[str, Any]:
    initial_source = subprocess.check_output(
        [
            "git",
            "show",
            "7cfcadcc18c7886fad55f83d39234aed4bc545b6:src/equadiff_brodbar.py",
        ],
        cwd=ROOT,
        text=True,
        errors="replace",
    )
    change_stat = subprocess.check_output(
        ["git", "show", "--stat", "--oneline", UNIT_LABEL_COMMIT],
        cwd=ROOT,
        text=True,
        errors="replace",
    )
    return {
        "initial_ode_documented_time_unit": "hour",
        "initial_source_contains_current_time_hours": "Current time point (hours)" in initial_source,
        "unit_label_commit": UNIT_LABEL_COMMIT,
        "ode_source_changed_in_unit_label_commit": "src/equadiff_brodbar.py" in change_stat,
        "current_declared_time_unit": MODEL_TIME_UNIT,
        "finding": (
            "The unit-label commit changed presentation files and the workbook but did not change "
            "the ODE source. Absolute rate constants therefore lack a demonstrated hour-to-day "
            "conversion lineage. Current fitted constants are empirical per-model-day values."
        ),
    }


def build_audit() -> dict[str, Any]:
    paired, unresolved = _paired_transport_inventory()
    diagnostics = _teacher_diagnostics()
    rows = _scaling_rows(diagnostics)
    at_h60 = {
        row["reaction"]: row
        for row in rows
        if np.isclose(row["hematocrit_fraction"], 0.60)
    }
    return {
        "model_network_version": MODEL_NETWORK_VERSION,
        "current_transport_scaling_mode": TRANSPORT_VOLUME_SCALING_MODE,
        "paired_transport_count": len(paired),
        "paired_transports": paired,
        "unresolved_external_reactions": unresolved,
        "current_assumption": "equal-and-opposite intracellular and extracellular concentration derivatives",
        "implied_volume_ratio": 1.0,
        "amount_balance_equation": "V_i*dC_i/dt + V_e*dC_e/dt = 0",
        "required_external_derivative": "dC_e/dt = -(V_i/V_e)*dC_i/dt",
        "hematocrit_metadata_present": False,
        "scaling_grid": rows,
        "example_at_hematocrit_0.60": {
            reaction: {
                "legacy_mean_abs": float(at_h60[reaction]["legacy_teacher_mean_abs_mM_per_day"]),
                "intracellular_equivalent_mean_abs": float(
                    at_h60[reaction]["volume_corrected_intracellular_mean_abs_mM_per_day"]
                ),
            }
            for reaction in ("VEGLC", "VELAC")
        },
        "time_unit_evidence": _time_unit_evidence(),
        "decision": (
            "Do not refit transport constants until hematocrit/extracellular-volume metadata and "
            "the historical hour-to-day rate conversion are resolved. Keep the equal-volume mode "
            "for exact replay only."
        ),
        "implementation_decision": "no numerical scaling promoted because required experimental metadata are absent",
    }


def run_audit(*, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_audit()
    payload.update(
        {
            "contract_type": "transport_volume_time_scaling_audit",
            "contract_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    pd.DataFrame(payload["paired_transports"]).to_csv(
        out_dir / "paired_transport_inventory.csv", index=False
    )
    pd.DataFrame(payload["scaling_grid"]).to_csv(
        out_dir / "hematocrit_scaling_grid.csv", index=False
    )
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    example = payload["example_at_hematocrit_0.60"]
    report = [
        "# Transport volume and time-unit audit",
        "",
        f"The executable network contains `{payload['paired_transport_count']}` paired compartment transports.",
        "All currently impose equal-and-opposite concentration derivatives, which is amount-conserving only when effective intracellular and extracellular volumes are equal.",
        "",
        "## Volume sensitivity",
        "",
        "At a diagnostic hematocrit of 0.60, the intracellular-equivalent teacher is 2/3 of the legacy extracellular derivative teacher:",
        "",
        f"- VEGLC: `{example['VEGLC']['legacy_mean_abs']:.6g}` to `{example['VEGLC']['intracellular_equivalent_mean_abs']:.6g} mM/day`.",
        f"- VELAC: `{example['VELAC']['legacy_mean_abs']:.6g}` to `{example['VELAC']['intracellular_equivalent_mean_abs']:.6g} mM/day`.",
        "",
        "This is a sensitivity calculation, not a promoted correction; the dataset contains no hematocrit or compartment-volume metadata.",
        "",
        "## Time-unit lineage",
        "",
        payload["time_unit_evidence"]["finding"],
        "",
        "## Decision",
        "",
        payload["decision"],
    ]
    (out_dir / "decision_report.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"decision": payload["decision"], "report": str(out_dir / "decision_report.md")}, indent=2))
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_audit(out_dir=args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
