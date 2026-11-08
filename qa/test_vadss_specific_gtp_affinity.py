"""Regression tests for the reversible VADSS-specific GTP affinity."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from equadiff_brodbar import BRODBAR_METABOLITE_MAP, equadiff_brodbar  # noqa: E402
from MM_calibration import DEFAULT_PARAM_BOUNDS, load_initial_conditions  # noqa: E402


class _Tracker:
    def __init__(self) -> None:
        self.fluxes: dict[str, float] = {}

    def add_timepoint(self, _time: float, fluxes: dict[str, float]) -> None:
        self.fluxes = dict(fluxes)


def test_default_vadss_affinity_is_exact_legacy_shared_gtp_affinity() -> None:
    state = np.asarray(load_initial_conditions(), dtype=float)
    default = equadiff_brodbar(1.0, state, custom_params={})
    explicit = equadiff_brodbar(
        1.0,
        state,
        custom_params={"km_GTP_VADSS": 0.5},
    )
    np.testing.assert_allclose(default, explicit, rtol=0.0, atol=0.0)


def test_lower_specific_km_changes_only_vadss_stoichiometric_states() -> None:
    state = np.asarray(load_initial_conditions(), dtype=float)
    legacy_tracker = _Tracker()
    specific_tracker = _Tracker()
    legacy = equadiff_brodbar(
        1.0,
        state,
        custom_params={"km_GTP_VADSS": 0.5},
        flux_tracker=legacy_tracker,
    )
    specific = equadiff_brodbar(
        1.0,
        state,
        custom_params={"km_GTP_VADSS": 0.2},
        flux_tracker=specific_tracker,
    )
    difference = np.asarray(specific) - np.asarray(legacy)
    changed = set(np.flatnonzero(np.abs(difference) > 1e-12).tolist())
    assert changed == {
        BRODBAR_METABOLITE_MAP[name]
        for name in ("IMP", "ADESUC", "GTP", "GDP", "ASP")
    }
    assert specific_tracker.fluxes["VADSS"] > legacy_tracker.fluxes["VADSS"]


def test_specific_km_has_declared_calibration_bounds() -> None:
    default, lower, upper = DEFAULT_PARAM_BOUNDS["km_GTP_VADSS"]
    assert lower < default < upper
    assert default == pytest.approx(0.5)
