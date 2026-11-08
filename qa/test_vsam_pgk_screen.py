"""Focused guards and interaction tests for the fixed VSAM/PGK screen."""

from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from run_vsam_pgk_screen import CONFIG, contrast, guard, read, score, working_scales

DESIGN = read(CONFIG)
DAYS = [4, 8, 11, 15]
POOLS = ["ATP", "ADP", "AMP", *[f"pool{i}" for i in range(52)]]


def panel():
    y = np.ones((55, 4))
    x = y.copy()
    x[:3] = .5
    return x, y, working_scales(y, DESIGN)


def test_scales_use_only_provided_measurements_and_accept_observed_zeros():
    np.testing.assert_allclose(working_scales([[0., 0., 2., 4.]], DESIGN), [[.05, .05, .45, .85]], rtol=0, atol=1e-15)


def test_zero_only_channel_has_no_invented_detection_limit():
    with pytest.raises(ValueError, match="no implicit detection limit"):
        working_scales([[0., 0., 0., 0.]], DESIGN)


def test_zero_adenylate_prediction_is_not_floored():
    x, y, bands = panel()
    x[0, 0] = 0.
    with pytest.raises(ValueError, match="no pseudocount"):
        score(x, y, bands, POOLS)


def test_improving_adenylates_can_pass_without_other_changes():
    x, y, bands = panel()
    base = score(x, y, bands, POOLS)
    x[:3] *= 1.02
    assert guard(score(x, y, bands, POOLS), base, POOLS, DAYS, DESIGN)["pass"]


def test_off_target_at_end_of_55_channels_blocks_aggregate_improvement():
    x, y, bands = panel()
    base = score(x, y, bands, POOLS)
    x[:3] *= 1.02
    x[-1] += .1
    g = guard(score(x, y, bands, POOLS), base, POOLS, DAYS, DESIGN)
    assert g["gain"] > 0 and g["all55_failures"] == [POOLS[-1]] and not g["pass"]


def test_pointwise_atp_regression_is_not_hidden_by_other_dates():
    x, y, bands = panel()
    base = score(x, y, bands, POOLS)
    x[:3] *= 1.2
    x[0, -1] = .49
    g = guard(score(x, y, bands, POOLS), base, POOLS, DAYS, DESIGN)
    assert g["gain"] > 0 and g["adenylate_point_failures"] == [{"pool": "ATP", "day": 15}]
    assert not g["pass"]


def test_perfect_baseline_does_not_admit_a_tie():
    _, y, bands = panel()
    base = score(y, y, bands, POOLS)
    result = guard(base, base, POOLS, DAYS, DESIGN)
    assert result["gain_percent"] is None and not result["pass"]


def test_full_corner_interaction_is_zero_for_additive_effects():
    np.testing.assert_array_equal(contrast([10., 20.], [11., 22.], [12., 19.], [13., 21.]), [0., 0.])
    assert contrast(10., 11., 12., 14.) == 1.
