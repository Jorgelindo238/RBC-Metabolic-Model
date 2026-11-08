"""Tests for the fixed-state VAMPD1 storage-decay map."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from map_vampd1_storage_decay import (  # noqa: E402
    _sensitivity_diagnostics,
    activity_decay_flux,
)


def test_activity_decay_preserves_saturation_and_decays_from_first_day() -> None:
    flux = activity_decay_flux(
        saturation_trace=np.ones(3),
        time=np.asarray([1.0, 2.0, 3.0]),
        vmax_initial=0.2,
        decay_per_day=np.log(2.0),
    )
    np.testing.assert_allclose(flux, [0.2, 0.1, 0.05])


def test_negative_decay_is_rejected() -> None:
    with pytest.raises(ValueError):
        activity_decay_flux(
            saturation_trace=np.ones(2),
            time=np.asarray([1.0, 2.0]),
            vmax_initial=0.1,
            decay_per_day=-0.1,
        )


def test_window_integrals_identify_capacity_and_decay_directions() -> None:
    time = np.linspace(1.0, 46.0, 451)
    diagnostics = _sensitivity_diagnostics(
        saturation=np.ones_like(time),
        time=time,
        vmax_initial=0.125,
        decay_per_day=0.0125,
    )
    assert diagnostics["rank"] == 2
    assert diagnostics["identifiable"] is True


def test_map_contains_no_optimizer_or_ode_execution() -> None:
    source = (SCRIPTS / "map_vampd1_storage_decay.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "optimize" not in called_names
    assert "solve_ivp" not in source
