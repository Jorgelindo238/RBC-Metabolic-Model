"""Tests for compartment-aware model initialization policies."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from equadiff_brodbar import BRODBAR_METABOLITE_MAP, NUM_BASE_METABOLITES  # noqa: E402
from MM_calibration import load_initial_conditions  # noqa: E402
from parse_initial_conditions import build_initial_conditions  # noqa: E402


def _metabolites() -> list[str]:
    names = [""] * (NUM_BASE_METABOLITES + 1)
    for name, index in BRODBAR_METABOLITE_MAP.items():
        if index < len(names):
            names[index] = name
    return names


def test_legacy_policy_is_backward_compatible_default() -> None:
    default = load_initial_conditions()
    legacy = load_initial_conditions("legacy_experimental_alias")
    assert np.allclose(default, legacy, rtol=0.0, atol=0.0)


def test_strict_generic_policy_never_crosses_compartments() -> None:
    values, provenance = build_initial_conditions(
        _metabolites(),
        ROOT / "src" / "Initial_conditions_JA_Final.xls",
        initialization_policy="compartment_strict_generic",
    )
    assert values[BRODBAR_METABOLITE_MAP["CYS"]] == 1.0
    assert values[BRODBAR_METABOLITE_MAP["EASP"]] == 1.0
    assert provenance["CYS"] == "generic_1mM"
    assert provenance["EASP"] == "generic_1mM"
    assert not any("alias" in source for source in provenance.values())


def test_strict_historical_policy_uses_exact_compartment_priors() -> None:
    values, provenance = build_initial_conditions(
        _metabolites(),
        ROOT / "src" / "Initial_conditions_JA_Final.xls",
        initialization_policy="compartment_strict_historical",
    )
    assert np.isclose(values[BRODBAR_METABOLITE_MAP["CYS"]], 0.212)
    assert np.isclose(values[BRODBAR_METABOLITE_MAP["EASP"]], 0.021)
    assert provenance["CYS"] == "historical_exact"
    assert provenance["EASP"] == "historical_exact"
    assert not any("alias" in source for source in provenance.values())


def test_brodbar_exact_measurements_override_historical_priors() -> None:
    values = load_initial_conditions("compartment_strict_historical")
    raw = pd.read_excel(
        ROOT / "src" / "Data_Bordbar_et_al_exp.xlsx",
        engine="openpyxl",
    )
    names = raw.iloc[:, 0].astype(str).str.strip().str.upper()
    atp = float(raw.loc[names == "ATP"].iloc[0, 1])
    assert np.isclose(values[BRODBAR_METABOLITE_MAP["ATP"]], atp)


def test_unknown_initialization_policy_is_rejected() -> None:
    try:
        load_initial_conditions("unknown")
    except ValueError as exc:
        assert "initialization policy" in str(exc)
    else:
        raise AssertionError("Unknown initialization policy was accepted")
