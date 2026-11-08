"""Direction, stoichiometry, ties and interval ownership in executed budgets."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fla_executed_attribution import aggregate_windows, limiting_loss_attribution, signed_pool_contributions
from reaction_positivity import limit_signed_fluxes, rbc_reaction_matrix


def test_reverse_ak_and_ndpk_are_not_misclassified_by_static_reaction_names():
    result = signed_pool_contributions([1, -1], [[2, -3], [4, -5]])
    np.testing.assert_array_equal(result["production"], [[2, 0], [0, 5]])
    np.testing.assert_array_equal(result["consumption"], [[0, 3], [4, 0]])
    np.testing.assert_array_equal(result["net"], result["production"] - result["consumption"])


def test_ak_adp_coefficient_is_two_not_one():
    names, reactions, matrix = rbc_reaction_matrix()
    assert matrix[names.index("ADP"), reactions.index("VAK")] == -2
    result = signed_pool_contributions([-2], [[3, -4]])
    np.testing.assert_array_equal(result["net"], [[-6, 8]])


def test_tied_consumers_share_loss_and_products_do_not_limit():
    result = limiting_loss_attribution([[0.2], [0.2], [0]], [10], [-1, -1, 1], threshold=1)
    np.testing.assert_allclose(result["factors"], [0.2])
    np.testing.assert_allclose(result["loss_by_pool"], [[4], [4], [0]])
    np.testing.assert_allclose(result["loss_by_pool"].sum(axis=0), result["loss"])


def test_reverse_flux_changes_limiting_consumers_and_zero_rate_has_no_loss():
    result = limiting_loss_attribution([[0, 0], [0.1, 0.1]], [-2, 0], [-1, 1], threshold=1)
    np.testing.assert_allclose(result["factors"], [0.1, 1])
    np.testing.assert_allclose(result["loss_by_pool"], [[0, 0], [1.8, 0]])


def test_attribution_matches_the_executed_limiter_for_signed_random_rates():
    rng = np.random.default_rng(20261005)
    states, matrix = rng.uniform(-0.1, 2, (4, 30)), rng.integers(-2, 3, (4, 6))
    rates = rng.normal(size=(6, 30))
    for index in range(6):
        result = limiting_loss_attribution(states, rates[index], matrix[:, index], threshold=1)
        for node in range(30):
            actual, factor = limit_signed_fluxes(states[:, node], rates[index:index+1, node], matrix[:, index:index+1], threshold=1)
            assert result["factors"][node] == factor[0]
            assert result["loss"][node] == pytest.approx(abs(rates[index, node] - actual[0]))
        np.testing.assert_allclose(result["loss_by_pool"].sum(axis=0), result["loss"])


def test_window_sum_respects_exact_boundaries_and_overlapping_windows_are_separate():
    result = aggregate_windows([[1, 2, 3]], [1, 2, 3, 4], [("early", 1, 3), ("all", 1, 4)])
    np.testing.assert_array_equal(result, [[3, 6]])


@pytest.mark.parametrize("boundaries,windows", [
    ([1, 2, 2], [("bad", 1, 2)]), ([1, 2, 3], [("missing", 1, 2.5)]),
    ([1, 2, 3], [("reverse", 3, 1)]), ([1, 2, 3], []),
])
def test_ambiguous_or_missing_window_evidence_fails(boundaries, windows):
    with pytest.raises(ValueError):
        aggregate_windows([[1, 2]], boundaries, windows)


@pytest.mark.parametrize("coefficients,fluxes", [([1], [[np.nan]]), ([1, 2], [[1]]), ([], [[]])])
def test_invalid_flux_evidence_is_not_replaced_with_zero(coefficients, fluxes):
    with pytest.raises(ValueError):
        signed_pool_contributions(coefficients, fluxes)


@pytest.mark.parametrize("threshold", [0, -1, np.nan, np.inf, True])
def test_invalid_availability_threshold_is_rejected(threshold):
    with pytest.raises(ValueError):
        limiting_loss_attribution([[1]], [1], [-1], threshold=threshold)


def test_full_focus_contributions_close_against_the_executed_ode():
    from audit_b13pg_atp_executed_fluxes import integrands, POOLS
    from test_reaction_positivity_fixed_context import replay
    names, reactions, matrix = rbc_reaction_matrix()
    states = np.full((114, 2), 0.2)
    states[113] = 7.2
    states[names.index("B13PG")] = [2e-4, 3e-4]
    states[names.index("ADP")] = [1e-4, 2e-4]
    parts = replay([1., 2.], states, {}, "reaction_consistent", reactions, matrix, threshold=1e-3)
    values, meta, loss_meta, labels = integrands(parts, states, names, reactions, matrix, 1e-3)
    assert sum(pool == "ATP" for pool, _ in meta) == 16
    assert set(reaction for pool, reaction in meta if pool == "B13PG") == {"VGAPDH", "VPGK", "VDPGM"}
    np.testing.assert_allclose(values["production"] - values["consumption"], values["executed_contribution"])
    for index, pool in enumerate(POOLS):
        members = [j for j, (name, _) in enumerate(meta) if name == pool]
        np.testing.assert_allclose(values["executed_contribution"][members].sum(axis=0), values["rhs"][index], atol=1e-14)
    for reaction in set(name for name, _ in loss_meta):
        members = [j for j, (name, _) in enumerate(loss_meta) if name == reaction]
        total_index = labels["limiter_loss"].index(reaction)
        np.testing.assert_allclose(values["limiter_loss_by_pool"][members].sum(axis=0), values["limiter_loss"][total_index])


def test_conditional_atp_requirement_is_labeled_and_b13pg_teacher_is_excluded():
    from audit_b13pg_atp_executed_fluxes import experimental_intervals
    meta = [("ATP", "VPGK"), ("ATP", "VHK"), ("ADP", "VAK"), ("B23PG", "VDPGM")]
    values = {"executed_contribution": np.array([[2], [-1], [-4], [0.3]])}
    curves = {"ATP": np.array([1., 3.]), "ADP": np.array([2., 1.]),
              "B23PG": np.array([4., 5.]), "B13PG": np.array([4., 5.])}
    frame = experimental_intervals(values, [1., 4.], None, meta, np.array([1., 4.]), curves)
    assert set(frame.pool) == {"ATP", "ADP", "B23PG"}
    assert not frame.individual_flux_identified.any()
    atp = frame.loc[frame.pool.eq("ATP")].iloc[0]
    assert atp.reference_minus_executed_mM == 1.
    assert atp.conditional_required_VPGK_mM == 3.
