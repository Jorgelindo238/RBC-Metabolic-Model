from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from build_fla_identifiability_mask import (  # noqa: E402
    _candidate_parameters,
    _numeric_parameter_value,
    _practical_rank,
)


def test_practical_rank_uses_relative_singular_value_threshold():
    matrix = np.diag([10.0, 0.02, 0.0001])
    rank, singular_values = _practical_rank(matrix, 1e-3)
    assert rank == 2
    assert np.allclose(singular_values, [10.0, 0.02, 0.0001])


def test_numeric_reaction_names_are_present_in_parameter_candidates():
    params = {
        "vmax_V23DPGP": 1.0,
        "km_B23PG": 1.0,
        "vmax_V6PGD": 1.0,
        "km_GO6P": 1.0,
        "km_NADP_NADPH": 1.0,
    }
    assert set(_candidate_parameters(["V23DPGP"], params)) == {
        "vmax_V23DPGP",
        "km_B23PG",
    }
    assert set(_candidate_parameters(["V6PGD"], params)) == {
        "vmax_V6PGD",
        "km_GO6P",
        "km_NADP_NADPH",
    }


def test_literal_ode_default_fills_calibration_default_gap():
    assert np.isclose(_numeric_parameter_value({}, "km_B23PG"), 1.013344)
    assert "km_B23PG" in _candidate_parameters(["V23DPGP"], {})
