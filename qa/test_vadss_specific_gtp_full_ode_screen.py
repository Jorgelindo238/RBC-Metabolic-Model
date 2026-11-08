"""Tests for the guarded VADSS-specific GTP-affinity ODE screen."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from screen_vadss_specific_gtp_full_ode import (  # noqa: E402
    LOCAL_CROSS,
    _candidate_label,
    _relative_degradation,
    _rms,
)


def test_local_cross_contains_map_and_one_factor_neighbors() -> None:
    assert (1.0, 1.0) in LOCAL_CROSS
    assert all(vmax == 1.0 or km == 1.0 for vmax, km in LOCAL_CROSS)


def test_candidate_label_is_stable() -> None:
    assert _candidate_label(1.0, 0.65) == "VADSS_v1.00_kg0.65"


def test_relative_helpers_have_declared_direction() -> None:
    assert _relative_degradation(1.1, 1.0) == pytest.approx(0.1)
    assert _rms([3.0, 4.0]) == pytest.approx((12.5) ** 0.5)


def test_screen_contains_no_optimizer() -> None:
    source = (SCRIPTS / "screen_vadss_specific_gtp_full_ode.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "optimize" not in called_names
    assert "create_study" not in source
