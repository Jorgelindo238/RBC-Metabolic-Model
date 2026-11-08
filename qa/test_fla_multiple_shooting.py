"""Tests for observation-anchored FLA multiple-shooting contracts."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fla_multiple_shooting import (  # noqa: E402
    endpoint_nrmse,
    forward_chaining_splits,
    reset_observed_states,
)


def test_reset_changes_only_declared_observed_states_and_records_jump() -> None:
    reset, evidence = reset_observed_states(
        [1.0, 2.0, 3.0],
        observations={"B": 4.0},
        state_indices={"B": 1},
        scales={"B": 2.0},
        time_day=4.0,
    )
    np.testing.assert_allclose(reset, [1.0, 4.0, 3.0])
    assert evidence.jump_values == (2.0,)
    assert evidence.normalized_jump_loss == pytest.approx(1.0)


def test_invalid_observation_is_rejected() -> None:
    with pytest.raises(ValueError):
        reset_observed_states(
            [1.0],
            observations={"A": -1.0},
            state_indices={"A": 0},
            time_day=1.0,
        )


def test_endpoint_nrmse_uses_declared_scale() -> None:
    assert endpoint_nrmse([1.0, 3.0], [1.0, 1.0], scale=2.0) == pytest.approx(
        np.sqrt(2.0) / 2.0
    )


def test_forward_chaining_never_uses_future_interval_for_training() -> None:
    splits = forward_chaining_splits([1.0, 4.0, 8.0, 11.0, 15.0])
    assert splits == (((1.0, 11.0), (11.0, 15.0)),)
