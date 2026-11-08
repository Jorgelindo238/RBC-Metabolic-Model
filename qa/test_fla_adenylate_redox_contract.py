"""Adenylate conservation, latent IC separation and fail-closed data contracts."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fla_adenylate_redox_contract import (
    AK_COLUMN, TOTAL_ADENYLATE_TERMS, adenylate_metrics, conditional_ak_requirements,
    readiness_blockers, redox_initializations,
)
from reaction_positivity import rbc_reaction_matrix


def test_ak_redistributes_but_does_not_change_total_adenylates():
    names, reactions, matrix = rbc_reaction_matrix()
    rows = matrix[[names.index(name) for name in ("ATP", "ADP", "AMP")]]
    np.testing.assert_array_equal(rows[:, reactions.index("VAK")], AK_COLUMN)
    actual = {reactions[i]: coefficient for i, coefficient in enumerate(rows.sum(axis=0)) if coefficient}
    assert actual == TOTAL_ADENYLATE_TERMS


def test_nad_pair_is_an_encoded_invariant():
    names, _, matrix = rbc_reaction_matrix()
    np.testing.assert_array_equal(matrix[names.index("NAD")] + matrix[names.index("NADH")], 0)


def test_energy_charge_distinguishes_same_total_with_wrong_partition():
    a = adenylate_metrics([[1], [1], [1]])
    b = adenylate_metrics([[0], [0], [3]])
    np.testing.assert_array_equal(a["total"], b["total"])
    assert a["energy_charge"][0] == .5 and b["energy_charge"][0] == 0


@pytest.mark.parametrize("states", [[[0], [0], [0]], [[-1], [1], [1]], [[np.nan], [1], [1]], [[1], [2]]])
def test_invalid_energy_charge_evidence_fails(states):
    with pytest.raises(ValueError):
        adenylate_metrics(states)


def test_conditional_ak_requirements_agree_only_under_fixed_neighbor_feasibility():
    actual = AK_COLUMN * 2 + [1, 2, 3]
    reference = actual + AK_COLUMN * .5
    result = conditional_ak_requirements(reference, actual, 2)
    np.testing.assert_allclose(result["required_by_pool"], 2.5)
    assert result["requirement_spread_mM"] == 0
    assert result["individually_observed_AK"] is False
    contradictory = conditional_ak_requirements(actual + [1, 1, -2], actual, 2)
    assert contradictory["requirement_spread_mM"] > 0
    assert contradictory["total_adenylate_discrepancy_mM"] == 0


@pytest.mark.parametrize("reference,rate", [([1, 2], 1), ([1, np.inf, 2], 1), ([1, 2, 3], np.nan)])
def test_nonfinite_or_truncated_inverse_constraints_fail(reference, rate):
    with pytest.raises(ValueError):
        conditional_ak_requirements(reference, [1, 2, 3], rate)


def test_redox_total_and_fraction_are_separated_without_changing_measured_states():
    original = np.array([3., 1., 1., 7.])
    scenarios = redox_initializations(original, [1, 2], [.09, .01])
    np.testing.assert_array_equal(scenarios["baseline"], original)
    np.testing.assert_allclose(scenarios["historical_total_only"][[1, 2]], [.05, .05])
    np.testing.assert_allclose(scenarios["historical_ratio_only"][[1, 2]], [1.8, .2])
    np.testing.assert_allclose(scenarios["historical_pair"][[1, 2]], [.09, .01])
    for state in scenarios.values():
        np.testing.assert_array_equal(state[[0, 3]], original[[0, 3]])
    np.testing.assert_array_equal(original, [3, 1, 1, 7])


@pytest.mark.parametrize("indices,historical", [([1, 1], [.1, .2]), ([1, 4], [.1, .2]), ([1, 2], [0, .1]), ([1, 2], [np.nan, 1])])
def test_invalid_or_untraceable_redox_scenario_values_fail(indices, historical):
    with pytest.raises(ValueError):
        redox_initializations([1, 1, 1], indices, historical)


def test_missing_accuracy_or_redox_prior_cannot_be_certified_by_numerics():
    known_data = {key: True for key in ("upstream_lineage_verified", "normalization_verified", "uncertainty_available", "time_origin_verified")}
    assert readiness_blockers(known_data, {}, None) == ["redox:biological_prior_verified", "accuracy:absolute_limits_unset"]
    assert not readiness_blockers(known_data, {"biological_prior_verified": True}, {"ATP": .1, "ADP": .1, "AMP": .1})
    assert "accuracy:AMP_absolute_limit" in readiness_blockers(known_data, {"biological_prior_verified": True}, {"ATP": .1, "ADP": .1})


def test_unknown_source_normalization_stays_blocking():
    blockers = readiness_blockers({}, {}, None)
    assert len(blockers) == 6
    assert "data:normalization_verified" in blockers
