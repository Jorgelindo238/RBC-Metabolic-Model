"""Regression tests for the optional AMP-to-adenosine structural branch."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from equadiff_brodbar import BRODBAR_METABOLITE_MAP, equadiff_brodbar  # noqa: E402
from MM_calibration import load_initial_conditions  # noqa: E402


class _Tracker:
    def __init__(self) -> None:
        self.fluxes: dict[str, float] = {}

    def add_timepoint(self, _time: float, fluxes: dict[str, float]) -> None:
        self.fluxes = dict(fluxes)


def test_amp_nucleotidase_is_default_off() -> None:
    state = np.asarray(load_initial_conditions(), dtype=float)
    default = equadiff_brodbar(1.0, state, custom_params={})
    explicit = equadiff_brodbar(
        1.0,
        state,
        custom_params={"purine_structure_mode": "legacy", "vmax_VAMP_NT": 2.0},
    )
    np.testing.assert_allclose(default, explicit, rtol=0.0, atol=0.0)


def test_amp_nucleotidase_moves_amp_to_ado_with_exact_stoichiometry() -> None:
    state = np.asarray(load_initial_conditions(), dtype=float)
    legacy = equadiff_brodbar(
        1.0,
        state,
        custom_params={"purine_structure_mode": "legacy", "vmax_VAMP_NT": 0.2},
    )
    tracker = _Tracker()
    active = equadiff_brodbar(
        1.0,
        state,
        custom_params={
            "purine_structure_mode": "amp_nucleotidase",
            "vmax_VAMP_NT": 0.2,
            "km_AMP_NT": 0.3,
        },
        flux_tracker=tracker,
    )
    difference = np.asarray(active) - np.asarray(legacy)
    changed = set(np.flatnonzero(np.abs(difference) > 1e-12).tolist())
    amp_index = BRODBAR_METABOLITE_MAP["AMP"]
    ado_index = BRODBAR_METABOLITE_MAP["ADO"]
    assert changed == {amp_index, ado_index}
    assert tracker.fluxes["VAMP_NT"] > 0.0
    assert difference[ado_index] == pytest.approx(tracker.fluxes["VAMP_NT"])
    assert difference[amp_index] == pytest.approx(-tracker.fluxes["VAMP_NT"])


def test_unknown_purine_structure_mode_is_rejected() -> None:
    state = np.asarray(load_initial_conditions(), dtype=float)
    with pytest.raises(ValueError, match="purine_structure_mode"):
        equadiff_brodbar(
            1.0,
            state,
            custom_params={"purine_structure_mode": "unknown"},
        )
