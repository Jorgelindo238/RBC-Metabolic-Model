"""Regression checks for observability, numerical sources and accepted-step quadrature."""

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fla_balance_audit import (
    accepted_step_quadrature, balance_matrix, constraint_observability,
    integrate_intervals, numerical_components,
)


def test_missing_sink_creates_false_individual_flux_identifiability():
    corrected = np.array([[1.0, -1.0]])
    old = np.array([[1.0, 0.0]])
    assert constraint_observability(old)["individually_identifiable_columns"] == [0]
    result = constraint_observability(corrected)
    assert result["rank"] == 1
    assert result["nullity"] == 1
    assert result["individually_identifiable_columns"] == []
    np.testing.assert_allclose(corrected @ result["null_basis"], 0.0, atol=1e-14)


def test_corrected_ppp_and_shunt_cannot_identify_individual_fluxes_from_four_pools():
    import rbc_stoichiometry as stoich
    pools = ("G6P", "GO6P", "F6P", "B23PG")
    reactions = sorted(stoich.reactions_for_metabolites(pools))
    result = constraint_observability(balance_matrix(pools, reactions, stoich.STOICHIOMETRY))
    assert result["rank"] == 4
    assert result["nullity"] > 0
    assert result["individually_identifiable_columns"] == []


def test_poolwise_damping_breaks_a_shared_reaction_invariant():
    # A -> B: only depleted A's derivative is attenuated, creating A+B.
    matrix = np.array([[-1.0], [1.0]])
    states = np.array([[5e-4], [0.2]])
    expected = np.array([[-0.5], [1.0]])
    parts = numerical_components(states=states, fluxes=np.array([[1.0]]), executed=expected,
        matrix=matrix, minimum_concentration=1e-6, damping_threshold=1e-3, maximum_derivative=1000)
    assert parts["raw"].sum() == 0.0
    assert parts["total_correction"].sum() == pytest.approx(0.5)
    np.testing.assert_allclose(parts["unexplained"], 0.0)


def test_input_floor_is_displacement_and_clipping_is_a_distinct_rate():
    parts = numerical_components(states=np.array([[-1e-5], [0.2]]), fluxes=np.array([[2000.0]]),
        executed=np.array([[-2.0], [1000.0]]), matrix=np.array([[-1.0], [1.0]]),
        minimum_concentration=1e-6, damping_threshold=1e-3, maximum_derivative=1000)
    assert parts["input_floor_displacement"][0, 0] == pytest.approx(1.1e-5)
    assert parts["damping"][0, 0] == pytest.approx(1998.0)
    assert parts["clipping"][1, 0] == -1000.0
    np.testing.assert_allclose(parts["unexplained"], 0.0)


def test_quadrature_splits_at_observed_endpoints_and_integrates_polynomials():
    grid = accepted_step_quadrature([1.0, 2.5, 6.0], [1.0, 4.0, 6.0], order=4)
    values = np.vstack([np.ones_like(grid.nodes), grid.nodes**3])
    actual = integrate_intervals(values, grid)
    np.testing.assert_allclose(actual, [[3.0, 2.0], [(4**4 - 1) / 4, (6**4 - 4**4) / 4]])
    assert np.all((grid.nodes > 1.0) & (grid.nodes < 6.0))
    assert grid.weights.sum() == pytest.approx(5.0)


@pytest.mark.parametrize("accepted,boundaries", [
    ([1, 3, 2, 4], [1, 4]),
    ([1, 2, 4], [1, 4, 4]),
    ([1, 2, 4], [0, 4]),
    ([1, np.nan, 4], [1, 4]),
])
def test_rejected_step_logs_or_missing_support_cannot_be_quadrature(accepted, boundaries):
    with pytest.raises(ValueError):
        accepted_step_quadrature(accepted, boundaries, order=4)


def test_nonfinite_flux_is_not_sanitized_into_valid_audit_evidence():
    with pytest.raises(ValueError, match="finite"):
        numerical_components(states=np.array([[0.2]]), fluxes=np.array([[np.nan]]),
            executed=np.array([[0.0]]), matrix=np.array([[1.0]]),
            minimum_concentration=1e-6, damping_threshold=1e-3, maximum_derivative=1000)
