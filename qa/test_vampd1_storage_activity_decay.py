"""Regression tests for optional storage-dependent VAMPD1 activity."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from equadiff_brodbar import (  # noqa: E402
    BRODBAR_METABOLITE_MAP,
    _compute_vampd1_flux,
    equadiff_brodbar,
)
from MM_calibration import load_initial_conditions  # noqa: E402


def test_storage_decay_matches_mm_at_day_one_and_declines_afterward() -> None:
    params = {
        "kinetic_family_VAMPD1": "storage_activity_decay",
        "storage_decay_VAMPD1": np.log(2.0),
    }
    day_one = _compute_vampd1_flux(1.0, 1.0, params, 0.2, 1.0)
    day_two = _compute_vampd1_flux(2.0, 1.0, params, 0.2, 1.0)
    assert day_one == pytest.approx(0.1)
    assert day_two == pytest.approx(0.05)


def test_default_vampd1_family_is_exact_historical_mm() -> None:
    state = np.asarray(load_initial_conditions(), dtype=float)
    default = equadiff_brodbar(10.0, state, custom_params={})
    explicit = equadiff_brodbar(
        10.0,
        state,
        custom_params={"kinetic_family_VAMPD1": "mm"},
    )
    np.testing.assert_allclose(default, explicit, rtol=0.0, atol=0.0)


def test_storage_decay_changes_only_vampd1_stoichiometric_states_at_fixed_state() -> None:
    state = np.asarray(load_initial_conditions(), dtype=float)
    legacy = equadiff_brodbar(
        20.0,
        state,
        custom_params={"vmax_VAMPD1": 0.125, "kinetic_family_VAMPD1": "mm"},
    )
    decay = equadiff_brodbar(
        20.0,
        state,
        custom_params={
            "vmax_VAMPD1": 0.125,
            "kinetic_family_VAMPD1": "storage_activity_decay",
            "storage_decay_VAMPD1": 0.0125,
        },
    )
    changed = set(np.flatnonzero(np.abs(np.asarray(decay) - np.asarray(legacy)) > 1e-12))
    assert changed == {
        BRODBAR_METABOLITE_MAP["AMP"],
        BRODBAR_METABOLITE_MAP["IMP"],
        BRODBAR_METABOLITE_MAP["NH4"],
    }


def test_unknown_vampd1_family_is_rejected() -> None:
    with pytest.raises(ValueError, match="kinetic_family_VAMPD1"):
        _compute_vampd1_flux(
            1.0,
            1.0,
            {"kinetic_family_VAMPD1": "unknown"},
            0.1,
            0.1,
        )
