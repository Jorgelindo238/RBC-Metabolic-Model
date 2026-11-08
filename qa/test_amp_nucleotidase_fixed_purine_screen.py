"""Tests for the deterministic AMP 5'-nucleotidase screen."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import screen_amp_nucleotidase_fixed_purine as SCREEN  # noqa: E402


def test_screen_is_narrow_and_includes_zero_control() -> None:
    assert SCREEN.VMAX_GRID[0] == 0.0
    assert all(left < right for left, right in zip(SCREEN.VMAX_GRID, SCREEN.VMAX_GRID[1:]))
    assert SCREEN.VMAX_GRID[-1] == 0.05
    assert SCREEN.INTEGRATED_WINDOWS == ((1.0, 11.0), (11.0, 22.0), (22.0, 46.0))


def test_raw_amp_and_ado_balances_include_optional_branch() -> None:
    points = 3
    fluxes = {
        reaction: np.ones(points)
        for reaction in SCREEN.STOICH.REVERSE_INDEX["AMP"]
        | SCREEN.STOICH.REVERSE_INDEX["ADO"]
    }
    amp = SCREEN._raw_state_balance("AMP", fluxes)
    ado = SCREEN._raw_state_balance("ADO", fluxes)
    fluxes_without = dict(fluxes)
    fluxes_without["VAMP_NT"] = np.zeros(points)
    amp_without = SCREEN._raw_state_balance("AMP", fluxes_without)
    ado_without = SCREEN._raw_state_balance("ADO", fluxes_without)
    np.testing.assert_allclose(amp - amp_without, -1.0)
    np.testing.assert_allclose(ado - ado_without, 1.0)


def test_screen_contains_no_optimizer() -> None:
    source = (SCRIPTS / "screen_amp_nucleotidase_fixed_purine.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "optimize" not in called_names
    assert "minimize" not in called_names
    assert "create_study" not in source
