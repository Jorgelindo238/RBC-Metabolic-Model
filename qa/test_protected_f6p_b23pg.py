import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from audit_protected_f6p_b23pg import (indices_exact, weighted_windows, budgets, limiter_rows,
    compare_budgets, capacity_decomposition, proposed_guards, check_initialization)


def example_archive():
    return {"pool_names": np.array(["A", "B"]), "reactions": np.array(["R"]),
        "matrix": np.array([[-1.], [1.]]), "time": np.array([1., 2., 3.]),
        "states": np.array([[5., 4.5, 5.5], [0., .5, -.5]]), "boundaries": np.array([1., 2., 3.]),
        "q8_nodes": np.array([1.5, 2.5]), "q8_weights": np.ones(2), "q8_intervals": np.array([0, 1]),
        "q8_raw_rates": np.array([[2., -2.]]), "q8_executed_rates": np.array([[.5, -1.]]),
        "q8_states": np.array([[.25, 1.], [1., .5]])}


def test_exact_actual_initial_state_is_distinct_from_dense_rounding():
    a = {"initial": np.array([1.]), "accepted_states": np.array([[1., .5]]),
         "accepted_time": np.array([1., 10.]), "states": np.array([[np.nextafter(1., 2.), .5]])}
    check_initialization(a, [1.], 10.)
    a["accepted_states"][0, 0] = np.nextafter(1., 2.)
    with pytest.raises(ValueError, match="actual initial"):
        check_initialization(a, [1.], 10.)
    a["accepted_states"][0, 0] = 1.
    a["states"][0, 0] = 1.+1e-10
    with pytest.raises(ValueError, match="dense evaluation"):
        check_initialization(a, [1.], 10.)


def test_signed_budgets_do_not_net_reversals_before_production_and_consumption():
    pools, reactions = budgets(example_archive(), ["A"], [("all", 1., 3.)])
    row = pools[0]
    assert row["production_mM"] == 1.
    assert row["consumption_mM"] == .5
    assert row["executed_net_mM"] == .5
    assert row["closure_residual_mM"] == 0.
    assert reactions[0]["modifier_mM"] == .5


@pytest.mark.parametrize("grid,requested", [([], [1.]), ([1., 1.], [1.]), ([1., 3.], [2.]),
                                               ([1., 2.], [4.]), ([1., 2.], [np.nan])])
def test_missing_or_ambiguous_times_fail_without_interpolation(grid, requested):
    with pytest.raises(ValueError):
        indices_exact(grid, requested)


def test_window_ownership_uses_cells_not_nodes_nearest_an_observation():
    a = example_archive()
    result = weighted_windows(a["q8_raw_rates"], a, 8, [("first", 1., 2.), ("all", 1., 3.)])
    np.testing.assert_array_equal(result, [[2., 0.]])
    with pytest.raises(ValueError):
        weighted_windows(a["q8_raw_rates"], a, 8, [("invented", 1., 2.5)])


def test_nonpositive_quadrature_weights_are_rejected():
    a = example_archive()
    a["q8_weights"][0] = -1
    with pytest.raises(ValueError):
        weighted_windows(a["q8_raw_rates"], a, 8, [("all", 1., 3.)])


def test_limiter_allocates_reverse_flux_to_reversed_consumer_only():
    rows = limiter_rows(example_archive(), ["R"], 1., [("all", 1., 3.)], 8)
    assert next(r for r in rows if r["limiting_pool"] == "A")["loss_mM"] == 1.5
    assert next(r for r in rows if r["limiting_pool"] == "B")["loss_mM"] == 1.
    assert sum(r["loss_mM"] for r in rows) == rows[0]["total_absolute_rate_loss_mM"]


def test_saved_flux_must_match_reaction_consistent_execution():
    a = example_archive()
    a["q8_executed_rates"][0, 0] = 7.
    with pytest.raises(ValueError, match="saved executed"):
        limiter_rows(a, ["R"], 1., [("all", 1., 3.)], 8)


def test_capacity_accounting_closes_but_does_not_claim_causality():
    d = capacity_decomposition(10., 4., .2)
    assert d["capacity_at_control_states_mM"] == -8.
    assert d["state_response_remainder_mM"] == 2.
    assert sum(d[k] for k in ("capacity_at_control_states_mM", "state_response_remainder_mM")) == d["raw_integral_delta_mM"]
    assert "not_a_new_ODE_or_causal" in d["interpretation"]


def test_sampled_rate_checks_use_parameter_mappings_and_both_fixed_contexts(monkeypatch):
    import audit_protected_f6p_b23pg as audit
    received = []
    class FixedRates:
        reactions = ["VPFK"]
        def __init__(self, parameters, kinetics):
            assert isinstance(parameters, dict)
            self.capacity = parameters["capacity"]
            received.append(parameters)
        def rates(self, time, state):
            rate = np.array([self.capacity])
            return rate, rate, np.ones(1)
    monkeypatch.setattr(audit, "JointRHS", FixedRates)
    archives = {case: {"q8_nodes": np.array([1.5]), "q8_states": np.ones((1, 1)),
                      "q8_raw_rates": np.array([[v]]), "q8_executed_rates": np.array([[v]])}
                for case, v in (("control", 10.), ("protected", 2.))}
    selected = {"parameters": {"capacity": 2.}, "glucose_kinetics": {}, "factors": {"investment": .2}}
    assert audit.sampled_rate_checks(archives, {"capacity": 10.}, {}, selected) == 2
    assert received == [{"capacity": 10.}, {"capacity": 2.}]


def test_comparison_rejects_duplicate_or_unmatched_identities():
    base = [{"pool": "A", "amount": 1.}]
    for other in ([{"pool": "B", "amount": 2.}], base*2):
        with pytest.raises(ValueError):
            compare_budgets(base, other, ("pool",), ("amount",))


def test_guard_proposal_detects_pointwise_regression_even_when_RMSE_improves():
    obs = {"time": [1., 4., 8., 11.], "values": {"PEP": [1., 1., 1., 999.]}}
    frozen = {"design": {"pools": ["PEP"], "training_times": [4., 8.],
        "guard_numerical_atol_mM": 1e-5, "guard_numerical_rtol": 1e-4, "fitting_allowance_fraction": .25}}
    config = {"proposed_added_RMSE_guards": [], "proposed_pointwise_guards": ["PEP"], "source_aliases": {}}
    base = {"pool_names": np.array(["PEP"]), "time": np.array([1., 4., 8.]), "states": np.array([[1., 0., .9]])}
    candidate = {**base, "states": np.array([[1., .9, 1.2]])}
    result = proposed_guards(base, candidate, obs, frozen, config)
    assert result["RMSE_guards"][0]["candidate_pass"]
    assert not result["pointwise_guards"][1]["candidate_pass"]
    obs["values"]["PEP"][-1] = -999.
    assert result == proposed_guards(base, candidate, obs, frozen, config)
    config["source_aliases"] = {"PEP": "other"}
    with pytest.raises(ValueError, match="nonduplicated"):
        proposed_guards(base, candidate, obs, frozen, config)
