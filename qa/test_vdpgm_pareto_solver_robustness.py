from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_vdpgm_pareto_solver_robustness as AUDIT  # noqa: E402


def _payload(selected: str, shift: float = 0.0):
    rows = []
    for multiplier in (2.0, 3.0, 4.0):
        row = {"multiplier": multiplier}
        row.update({metric: multiplier + shift for metric in AUDIT.METRICS})
        rows.append(row)
    return {
        "pareto_rows": rows,
        "selection": {
            "selected_candidate": selected,
            "interior_improvement_fraction": 0.2 + shift,
        },
    }


def test_compare_reports_invariant_selection():
    rows, summary = AUDIT._compare(_payload("p3"), _payload("p3", 0.01))
    assert summary["selection_invariant"] is True
    assert len(rows) == 3 * len(AUDIT.METRICS)


def test_compare_reports_changed_selection():
    _, summary = AUDIT._compare(_payload("p3"), _payload("p4"))
    assert summary["selection_invariant"] is False
