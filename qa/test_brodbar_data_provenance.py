"""Tests for the Brodbar curated-data provenance contract."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_brodbar_data_provenance.py"
SPEC = importlib.util.spec_from_file_location("audit_brodbar_data_provenance", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_provenance_quarantines_non_independent_rows() -> None:
    payload = AUDIT.build_provenance()
    assert payload["expected_duplicate_pairs_present"] is True
    assert payload["training_policy"]["independent_state_targets_excluded"] == [
        "B13PG",
        "P2G",
    ]
    assert set(payload["training_policy"]["reaction_level_teachers_excluded"]) == {
        "B13PG",
        "P2G",
        "P3G",
    }


def test_provenance_records_day_46_mismatch() -> None:
    payload = AUDIT.build_provenance()
    assert payload["timepoints_days"][-1] == 46.0
    assert "42" in payload["publication_evidence"]["unresolved_mismatch"]
