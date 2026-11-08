"""Tests for the ATP sustainability audit."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from audit_atp_sustainability_vampd1_context import (  # noqa: E402
    ATP_CONSUMPTION,
    ATP_PRODUCTION,
    aggregate_atp_rates,
)


def test_atp_aggregation_matches_declared_stoichiometric_signs() -> None:
    data = {name: [1.0, 2.0] for name in ATP_PRODUCTION + ATP_CONSUMPTION}
    production, consumption = aggregate_atp_rates(pd.DataFrame(data))
    np.testing.assert_allclose(production, [3.0, 6.0])
    np.testing.assert_allclose(consumption, [13.0, 26.0])


def test_missing_flux_is_rejected() -> None:
    with pytest.raises(ValueError, match="missing ATP flux"):
        aggregate_atp_rates(pd.DataFrame({"VPGK": [1.0]}))


def test_audit_contains_no_optimizer_or_ode_replay() -> None:
    source = (SCRIPTS / "audit_atp_sustainability_vampd1_context.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "optimize" not in called_names
    assert "solve_ivp" not in source
