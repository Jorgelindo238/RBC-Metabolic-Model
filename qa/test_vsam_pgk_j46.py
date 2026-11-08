from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from replay_vsam_pgk_j46 import periods

DAYS = np.array([1, 4, 8, 11, 15, 18, 22, 25, 29, 32, 36, 38, 43, 46])


def test_replay_periods_do_not_score_j1_or_mix_late_with_early():
    masks = periods(DAYS)
    np.testing.assert_array_equal(DAYS[masks["J4_J15"]], [4, 8, 11, 15])
    np.testing.assert_array_equal(DAYS[masks["J18_J46"]], DAYS[5:])
    np.testing.assert_array_equal(DAYS[masks["J4_J46"]], DAYS[1:])


@pytest.mark.parametrize("days", [DAYS[:-1], DAYS[::-1], np.r_[DAYS[:-1], 45]])
def test_missing_or_unsorted_horizon_rejected(days):
    with pytest.raises(ValueError, match="complete original time support"):
        periods(days)
