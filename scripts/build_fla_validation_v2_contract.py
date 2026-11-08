"""Write the frozen FLA validation-v2 policy as a reviewable artifact."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DEFAULT_OUT_DIR = ROOT / "output" / "fla_validation_v2_contract"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fla_validation_v2 import CandidateStatus, ValidationThresholds  # noqa: E402


def run(*, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    thresholds = asdict(ValidationThresholds())
    payload = {
        "contract_type": "fla_cumulative_validation_policy",
        "contract_version": 3,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "thresholds": thresholds,
        "gate_order": [
            "G0_data",
            "G1_structure",
            "G2_identifiability",
            "G3_calibration",
            "G4_internal_validation",
            "G5_external_validation",
        ],
        "statuses": [status.value for status in CandidateStatus],
        "rules": [
            "G0-G2 failure rejects kinetic promotion before objective ranking.",
            "G1 requires both raw and damping-adjusted closure, and pre-clipping state minima.",
            "G3 failure retains a candidate only as a diagnostic hypothesis.",
            "G4 requires strict-solver and forward temporal transfer without refitting.",
            "G4 requires continuous unforced replay and predeclared absolute protected-target limits.",
            "Absolute limits are unset: internal validation is blocked until they are frozen before fitting.",
            "G5 is mandatory for global promotion and must remain disjoint from training.",
            "Pareto objectives remain separate; no hidden scalarization is authorized.",
        ],
    }
    contract_path = out_dir / "contract.json"
    report_path = out_dir / "decision_report.md"
    contract_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    report = [
        "# FLA validation policy revision 3",
        "",
        "Candidates now pass six cumulative gates: data contract, structural feasibility, identifiability, calibration, internal temporal validation, and external validation.",
        "",
        "A candidate cannot be promoted from training loss alone. Independent teacher incompatibility is a structural rejection; absent external evidence yields `retained_for_external_validation`, not `promoted`.",
        "",
        "## Frozen thresholds",
        "",
        f"- Exact balance error: `<= {thresholds['max_balance_error_mM_per_day']:g} mM/day`.",
        f"- Minimum unfloored state: `>= {thresholds['min_state_mM']:g} mM`.",
        f"- Primary trajectory improvement: `>= {thresholds['min_primary_trajectory_improvement']:.0%}`.",
        f"- Primary teacher-flux improvement: `>= {thresholds['min_primary_flux_improvement']:.0%}`.",
        f"- Maximum protected-target degradation: `<= {thresholds['max_protected_nrmse_degradation']:.0%}`.",
        f"- Whole-panel mean and median degradation: `<= {thresholds['max_panel_mean_nrmse_degradation']:.0%}`.",
        "- Absolute target nRMSE limits: NOT YET DECLARED. Promotion is blocked, even if all relative gains pass.",
        "- Raw balance closure must also pass; numerical damping is not a physical source term.",
        "- State minima must be measured before clipping; resets cannot count as unforced validation.",
    ]
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps({"contract": str(contract_path), "report": str(report_path)}, indent=2))
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)
    run(out_dir=args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
