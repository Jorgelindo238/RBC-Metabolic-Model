"""Likelihood density, unknown-pHi isolation and controlled budget expansion."""

import copy
import json
from pathlib import Path
import sys

import numpy as np
import pytest
from scipy.stats import lognorm, norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fla_observation_likelihood import mixed_assay_likelihood
from fla_transport_buffer_recovery import encode, training_times
from fla_transport_buffer_synthetic import simulate
from fla_transport_likelihood import MatchedObjective, recover_objective


@pytest.fixture
def config():
    return json.loads((ROOT / "config/fla_transport_buffer_synthetic.json").read_text())


def test_nll_matches_independent_library_densities():
    pred = np.array([[2, 3], [6.9, 7.0]])
    obs = np.array([[2.02, 2.99], [6.903, 6.998]])
    cv, sd = .005, .005
    lv = np.log1p(cv**2)
    expected = -sum(lognorm.logpdf(obs[0], s=np.sqrt(lv), scale=pred[0]*np.exp(-.5*lv)))
    expected -= sum(norm.logpdf(obs[1], loc=pred[1], scale=sd))
    result = mixed_assay_likelihood(pred, obs, [0, 2], concentration_cv=cv, ph_sd=sd)
    assert result["negative_log_likelihood"] == pytest.approx(expected, abs=1e-11)


def test_normalizers_are_present_when_sigma_changes():
    pred = obs = np.array([[7.0]])
    a, b = [mixed_assay_likelihood(pred, obs, [2], concentration_cv=.005, ph_sd=sd) for sd in (.005, .01)]
    assert a["negative_log_likelihood"] < b["negative_log_likelihood"]


@pytest.mark.parametrize("cv,sd", [(None, .005), (.005, None), (0, .005), (.005, 0), (True, .005), (.005, np.nan)])
def test_no_implicit_or_invalid_noise(cv, sd):
    with pytest.raises(ValueError):
        mixed_assay_likelihood([[2]], [[2]], [0], concentration_cv=cv, ph_sd=sd)


@pytest.mark.parametrize("value", [0, -1, np.nan, np.inf])
def test_no_zero_imputation_or_nonfinite_log_observation(value):
    with pytest.raises(ValueError):
        mixed_assay_likelihood([[2]], [[value]], [0], concentration_cv=.005, ph_sd=.005)


def test_exact_initial_zero_can_be_explicitly_excluded():
    result = mixed_assay_likelihood([[0, 2]], [[0, 2]], [0], concentration_cv=.005, ph_sd=.005,
                                   mask=np.array([[False, True]]))
    assert result["terms"] == 1


def test_exact_log_residual_reconstructs_noise_draw():
    p, z, cv = np.array([[2., 3.]]), np.array([[1.2, -.5]]), .005
    lv = np.log1p(cv**2)
    obs = p*np.exp(np.sqrt(lv)*z-.5*lv)
    result = mixed_assay_likelihood(p, obs, [0], concentration_cv=cv, ph_sd=.005)
    np.testing.assert_allclose(result["residuals"], z.ravel(), atol=1e-12)


def test_unknown_initial_pHi_does_not_leak(config):
    time = training_times(config, "sparse")
    scenario = config["scenarios"][0]
    data = simulate(config, scenario, time=time)["states"][:2]
    other = copy.deepcopy(scenario)
    other["initial"][2] = 8
    objectives = [MatchedObjective(config, s, "access_pHi", "concentrations", time, data) for s in (scenario, other)]
    x = encode(objectives[0].names, {"access_i": 1.2, "phi0": 7.0})
    np.testing.assert_array_equal(*[o.evaluate(x) for o in objectives])
    assert objectives[0].trace[0]["stochastic_terms"] == 6
    assert objectives[0].trace[0]["integration_end"] == config["training_end_day"]


def test_best_point_uses_matched_not_parent_objective(config):
    time = training_times(config, "sparse")
    scenario = config["scenarios"][0]
    data = simulate(config, scenario, time=time)["states"][[0, 1, 3]]
    data[2] += .003
    objective = MatchedObjective(config, scenario, "conductance_buffer", "concentrations_plus_pHe", time, data)
    for p in ({"conductance": .2, "beta_e": 9}, {"conductance": .4, "beta_e": 12}):
        objective.evaluate(encode(objective.names, p))
    best = min(objective.trace, key=lambda t: t["sum_squared_scaled_residual"])
    assert objective.best == (best["sum_squared_scaled_residual"], best["parameters"])


def test_budget_override_does_not_mutate_frozen_config(config):
    before = copy.deepcopy(config)
    scenario = config["scenarios"][0]
    time = training_times(config, "sparse")
    data = simulate(config, scenario, time=time)["states"][:2]
    fit = recover_objective(config, scenario, "oracle_conductance", "concentrations", time, data, 0,
                            kind="matched_likelihood", budget=1)
    assert not fit["optimizer_success"] and fit["actual_objective_evaluations"] == 1
    assert fit["evaluation_budget"] == 1 and config == before
