"""Boundary invariance, signed stoichiometry and reversible diagnostic activation."""

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from equadiff_brodbar import NUM_BASE_METABOLITES, NONEG_THRESHOLD, equadiff_brodbar
from flux_visualization import FluxTracker
from reaction_positivity import limit_signed_fluxes, rbc_reaction_matrix


def state():
    return np.r_[np.full(NUM_BASE_METABOLITES, 0.2), 7.2]


def test_one_factor_limits_every_member_of_a_multisubstrate_reaction():
    matrix = np.array([[-2.0], [-1.0], [1.0]])
    rates, factors = limit_signed_fluxes([5e-4, 0.2, 0.3], [4.0], matrix, threshold=1e-3)
    np.testing.assert_allclose(rates, [2.0])
    np.testing.assert_allclose(factors, [0.5])
    np.testing.assert_allclose(matrix @ rates, [-4.0, -2.0, 2.0])
    assert np.array([1.0, 0.0, 2.0]) @ matrix @ rates == 0.0


@pytest.mark.parametrize("rate,values,expected", [
    (2.0, [0.0, 0.2], 0.0),
    (-2.0, [0.2, 0.0], 0.0),
    (-2.0, [0.0, 5e-4], -1.0),
    (2.0, [0.2, 0.0], 2.0),
    (2.0, [-1e-5, 0.2], 0.0),
])
def test_signed_consumers_not_products_determine_availability(rate, values, expected):
    limited, _ = limit_signed_fluxes(values, [rate], [[-1.0], [1.0]], threshold=1e-3)
    assert limited[0] == expected


def test_adenylate_kinase_preserves_total_pool_in_both_directions():
    matrix = np.array([[1.0], [-2.0], [1.0]])
    for rate in (-2.0, 2.0):
        limited, _ = limit_signed_fluxes([5e-4, 2e-4, 0.2], [rate], matrix, threshold=1e-3)
        assert (matrix @ limited).sum() == 0.0
        assert np.sign(limited[0]) == np.sign(rate)


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_nonfinite_fluxes_fail_instead_of_being_sanitized(bad):
    with pytest.raises(ValueError, match="finite"):
        limit_signed_fluxes([0.1], [bad], [[-1]], threshold=1e-3)


def test_legacy_is_default_and_can_be_restored_without_mutating_inputs():
    x = state()
    x[13] = -1e-5
    initial = x.copy()
    params = {"vmax_VHK": 0.5}
    default = equadiff_brodbar(1.0, x, custom_params=params)
    limited = equadiff_brodbar(1.0, x, custom_params=params, positivity_policy="reaction_consistent")
    legacy = equadiff_brodbar(1.0, x, custom_params=params, positivity_policy="legacy")
    np.testing.assert_array_equal(default, legacy)
    np.testing.assert_array_equal(x, initial)
    assert params == {"vmax_VHK": 0.5}
    assert limited[13] >= 0.0


@pytest.mark.parametrize("sam_mode", ["biochemical_transfer", "legacy_amp_coproduct"])
def test_effective_tracker_matches_rhs_and_native_fluxes_remain_available(sam_mode):
    tracker = FluxTracker()
    audit = {}
    x = state()
    x[13], x[36] = 2e-5, 3e-5
    derivative = equadiff_brodbar(1.0, x, custom_params={"sam_adenylate_stoichiometry": sam_mode},
        positivity_policy="reaction_consistent", numerical_audit=audit, flux_tracker=tracker)
    names, reactions, matrix = rbc_reaction_matrix(sam_mode)
    rates = [tracker.fluxes[reaction][0] for reaction in reactions]
    np.testing.assert_allclose(matrix @ rates, derivative[:len(names)], atol=1e-12)
    assert len(audit["raw_fluxes"]) == len(reactions)
    assert audit["availability_factors"]["VPGK"] < 1.0


def test_rbc_zero_boundaries_have_no_outgoing_derivative_for_every_pool():
    for index in range(NUM_BASE_METABOLITES):
        x = state()
        x[index] = 0.0
        derivative = equadiff_brodbar(1.0, x, positivity_policy="reaction_consistent")
        assert derivative[index] >= -1e-12, index


def test_redox_pairs_are_conserved_even_if_a_consumer_is_depleted():
    x = state()
    x[75], x[78] = 0.0, 2e-5
    derivative = equadiff_brodbar(1.0, x, positivity_policy="reaction_consistent")
    assert derivative[75] + derivative[76] == pytest.approx(0.0, abs=1e-12)
    assert derivative[77] + derivative[78] == pytest.approx(0.0, abs=1e-12)


def test_pH_uses_effective_glycolytic_and_ppp_rates():
    x, audit = state(), {}
    x[36] = 1e-5
    derivative = equadiff_brodbar(1.0, x, positivity_policy="reaction_consistent", numerical_audit=audit)
    v = audit["effective_fluxes"]
    expected = 0.01 * (0.1 * (v["VPK"] + v["VLDH"]) - 0.05 * (v["VG6PDH"] + v["V6PGD"]))
    assert derivative[113] == pytest.approx(expected, abs=1e-12)


@pytest.mark.parametrize("kwargs", [
    {"positivity_policy": "unknown"},
    {"positivity_policy": "reaction_consistent", "curve_fit_strength": 0.5},
])
def test_unknown_policy_and_observation_forcing_are_rejected(kwargs):
    with pytest.raises(ValueError):
        equadiff_brodbar(1.0, state(), **kwargs)


def test_no_independent_derivative_clipping_in_consistent_mode():
    with pytest.raises(ValueError, match="clip"):
        equadiff_brodbar(1.0, state(), custom_params={"vmax_VHK": 1e8},
                         positivity_policy="reaction_consistent")


def test_above_threshold_all_fluxes_are_unchanged():
    x, audit = state(), {}
    legacy = equadiff_brodbar(1.0, x)
    consistent = equadiff_brodbar(1.0, x, positivity_policy="reaction_consistent", numerical_audit=audit)
    np.testing.assert_allclose(legacy, consistent, atol=1e-12)
    assert all(value == 1.0 for value in audit["availability_factors"].values())
    assert NONEG_THRESHOLD == 1e-3


def test_initial_snapshot_roundtrip_preserves_binary_values(tmp_path):
    import pandas as pd
    from test_reaction_positivity_fixed_context import read_exact_initial_snapshot

    values = np.array([0.12818022534212347, 1.1694000033445567, 7.2])
    pd.DataFrame({"pool": ["A", "B", "PHI"], "initial_value": values}).to_csv(tmp_path / "initial.csv", index=False)
    np.savez(tmp_path / "accepted.npz", time=[1.0], states=values[:, None])
    restored = read_exact_initial_snapshot(tmp_path / "initial.csv", tmp_path / "accepted.npz")
    np.testing.assert_array_equal(restored.initial_value.to_numpy(), values)


def test_initial_snapshot_rejects_a_changed_initial_value(tmp_path):
    import pandas as pd
    from test_reaction_positivity_fixed_context import read_exact_initial_snapshot

    pd.DataFrame({"pool": ["A"], "initial_value": [0.1]}).to_csv(tmp_path / "initial.csv", index=False)
    np.savez(tmp_path / "accepted.npz", time=[1.0], states=np.array([[0.2]]))
    with pytest.raises(ValueError, match="exactly"):
        read_exact_initial_snapshot(tmp_path / "initial.csv", tmp_path / "accepted.npz")
