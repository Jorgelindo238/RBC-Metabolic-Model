"""Structural tests for explicit extracellular degradation reactions."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import rbc_stoichiometry as STOICH  # noqa: E402


def test_extracellular_glutathione_degradation_is_explicit() -> None:
    assert STOICH.STOICHIOMETRY["VEGSH_deg"] == {"EGSH": -1.0}
    assert STOICH.STOICHIOMETRY["VEGSSG_deg"] == {"EGSSG": -1.0}


def test_degradation_parameters_are_reachable_from_extracellular_pools() -> None:
    assert "k_EGSH_deg" in STOICH.REACTION_PARAMS["VEGSH_deg"]
    assert "k_EGSSG_deg" in STOICH.REACTION_PARAMS["VEGSSG_deg"]
    assert "VEGSH_deg" in STOICH.reactions_for_metabolites(["EGSH"])
    assert "VEGSSG_deg" in STOICH.reactions_for_metabolites(["EGSSG"])


def test_glutathione_transport_is_no_longer_a_singleton_balance() -> None:
    assert STOICH.reactions_for_metabolites(["EGSH"]) >= {
        "VEGSH_rate",
        "VEGSH_deg",
    }
    assert STOICH.reactions_for_metabolites(["EGSSG"]) >= {
        "VEGSSG",
        "VEGSSG_deg",
    }
