"""Tests for the conditional GTP/NDPK feasibility audit."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from audit_gtp_ndpk_feasibility import ndpk_components  # noqa: E402


def test_ndpk_components_follow_forward_minus_reverse_contract() -> None:
    forward, reverse, net = ndpk_components(
        gdp=[1.0],
        atp=[1.0],
        gtp=[1.0],
        adp=[1.0],
        vmax_forward=2.0,
        vmax_reverse=1.0,
        km_gdp=1.0,
        km_atp=1.0,
        km_gtp=1.0,
        km_adp=1.0,
    )
    np.testing.assert_allclose(forward, [0.5])
    np.testing.assert_allclose(reverse, [0.25])
    np.testing.assert_allclose(net, [0.25])


def test_audit_contains_no_optimizer_or_ode_replay() -> None:
    source = (SCRIPTS / "audit_gtp_ndpk_feasibility.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "optimize" not in called_names
    assert "solve_ivp" not in source
