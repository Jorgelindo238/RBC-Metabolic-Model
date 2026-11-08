from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from fla_balance_certificates import balance_certificates


def test_constant_pool_has_a_direct_initial_anchor_error_lower_bound():
    c = balance_certificates([[0.]], [[1., .5]], [1., 4.], [[.1, .1]], ["CITR"], [])
    assert c[0]["kind"] == "constant" and c[0]["minimum_working_multiplier_lower_bound"] == 5


def test_volume_weighted_pair_is_not_a_total_bag_concentration_sum():
    m = np.array([[-1.], [.58/.42]])
    c = balance_certificates(m, [[1., .5], [1., 1.]], [1., 4.], np.ones((2, 2))*.1, ["CIT", "ECIT"], [])
    assert c[0]["coefficients"]["ECIT"] == pytest.approx(.42/.58)
    assert max(abs(np.array(c[0]["matrix_combination"]))) < 1e-12


def test_glucose_forward_consumption_certificate_is_an_inequality_not_conservation():
    m = np.array([[-.58/.42, 0.], [1., -1.]])
    c = balance_certificates(m, [[10., 10.], [1., 2.]], [1., 4.], np.ones((2, 2))*.1, ["EGLC", "GLC"], [1])
    assert c[0]["kind"] == "nonincreasing" and c[0]["minimum_working_multiplier_lower_bound"] > 0


def test_signed_reaction_cannot_be_assumed_forward_from_catalog():
    c = balance_certificates([[1.]], [[1., 0.]], [1., 4.], [[.1, .1]], ["X"], [])
    assert c == []


def test_inequality_compares_both_uncertain_endpoints_not_only_initial():
    c = balance_certificates([[1.]], [[0., 1., 0.]], [1., 4., 8.], [[.1, .1, .1]], ["X"], [0])
    assert c[0]["kind"] == "nondecreasing" and c[0]["critical_days"] == [4., 8.]
    assert c[0]["minimum_working_multiplier_lower_bound"] == 5
