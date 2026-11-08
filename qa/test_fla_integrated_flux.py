"""Tests for interpolation-free interval-integrated flux teachers."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fla_integrated_flux import (  # noqa: E402
    build_integrated_flux_targets,
    integrated_flux_nrmse,
    irreversible_teacher_is_feasible,
)


def test_integrated_teacher_closes_declared_balance_without_derivatives() -> None:
    targets = build_integrated_flux_targets(
        measurement_time=[1.0, 2.0, 3.0],
        measurement_values=[5.0, 4.0, 3.5],
        dense_time=[1.0, 2.0, 3.0],
        known_rate=[0.5, 0.5, 0.5],
        model_unknown_rate=[1.0, 1.0, 1.0],
        unknown_stoichiometric_coefficient=-1.0,
        windows=[(1.0, 2.0), (2.0, 3.0)],
    )
    assert targets[0].observed_state_change_mM == pytest.approx(-1.0)
    assert targets[0].required_unknown_flux_integral_mM == pytest.approx(1.5)
    assert targets[1].required_unknown_flux_integral_mM == pytest.approx(1.0)


def test_window_boundaries_must_be_actual_measurements() -> None:
    with pytest.raises(ValueError, match="not a unique measured time"):
        build_integrated_flux_targets(
            measurement_time=[1.0, 3.0],
            measurement_values=[2.0, 1.0],
            dense_time=[1.0, 2.0, 3.0],
            known_rate=[0.0, 0.0, 0.0],
            model_unknown_rate=[0.0, 0.0, 0.0],
            unknown_stoichiometric_coefficient=-1.0,
            windows=[(1.0, 2.0)],
        )


def test_integrated_score_and_irreversible_feasibility_are_separate() -> None:
    targets = build_integrated_flux_targets(
        measurement_time=[1.0, 2.0, 3.0],
        measurement_values=[2.0, 1.0, 1.5],
        dense_time=[1.0, 2.0, 3.0],
        known_rate=[0.0, 0.0, 0.0],
        model_unknown_rate=[1.0, 0.0, 0.0],
        unknown_stoichiometric_coefficient=-1.0,
        windows=[(1.0, 2.0), (2.0, 3.0)],
    )
    assert np.isfinite(integrated_flux_nrmse(targets))
    assert irreversible_teacher_is_feasible(targets) is False
