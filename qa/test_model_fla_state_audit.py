"""Tests for the reproducible AIRBC model and FLA state audit."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "src"), str(ROOT / "scripts")):
    if path not in sys.path:
        sys.path.insert(0, path)

SCRIPT = ROOT / "scripts" / "audit_model_fla_state.py"
SPEC = importlib.util.spec_from_file_location("audit_model_fla_state", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_case_contract_separates_network_and_initialization_effects() -> None:
    assert AUDIT.CASE_LEGACY != AUDIT.CASE_SAM != AUDIT.CASE_STRICT
    seed = {"vmax_VHK": 1.0}
    legacy = AUDIT._case_params(seed, "legacy_amp_coproduct")
    corrected = AUDIT._case_params(seed, "biochemical_transfer")
    assert legacy["vmax_VHK"] == corrected["vmax_VHK"]
    assert legacy["sam_adenylate_stoichiometry"] != corrected["sam_adenylate_stoichiometry"]


def test_duplicate_detector_finds_quarantined_non_independent_rows() -> None:
    pairs = {(row["left"], row["right"]) for row in AUDIT._duplicate_experimental_rows()}
    assert ("B13PG", "B23PG") in pairs
    assert ("P3G", "P2G") in pairs or ("P2G", "P3G") in pairs
    assert AUDIT.NON_INDEPENDENT_OBSERVATIONS == {"B13PG", "P2G"}


def test_model_inventory_reports_corrected_network_reactions() -> None:
    inventory = AUDIT._model_inventory()
    assert inventory["sam_stoichiometry"] == {
        "ATP": -1.0,
        "MET": -1.0,
        "ADOMET": 1.0,
    }
    assert inventory["explicit_degradation_reactions"]["VEGSH_deg"] == {"EGSH": -1.0}
    assert inventory["stoichiometry_consistency_errors"] == []


def test_initialization_inventory_exposes_legacy_aliases_only() -> None:
    inventory = AUDIT._initialization_inventory()
    assert len(inventory["legacy_experimental_alias"]["compartment_aliases"]) == 5
    assert inventory["compartment_strict_generic"]["compartment_aliases"] == {}
    assert inventory["compartment_strict_historical"]["compartment_aliases"] == {}


def test_jsonable_converts_numpy_scalars() -> None:
    assert AUDIT._jsonable({"value": np.float64(1.5)}) == {"value": 1.5}
