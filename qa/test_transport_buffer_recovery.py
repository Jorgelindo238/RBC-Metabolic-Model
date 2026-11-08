"""Clean toy recovery, training/holdout separation and real evaluation budgets."""

import copy
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fla_transport_buffer_synthetic import simulate
from fla_transport_buffer_recovery import (EvaluationBudgetReached, TrainingObjective, decode, encode,
    multistart_agreement, parameter_errors, prediction_metrics, recover, select_saved, training_times)


@pytest.fixture
def config():
    return json.loads((ROOT / "config/fla_transport_buffer_synthetic.json").read_text())


def observations(config, scenario, plan="concentrations"):
    time = training_times(config, "sparse")
    values = simulate(config, scenario, time=time)["states"][config["observation_plans"][plan]]
    return time, values


@pytest.mark.parametrize("schedule", ["sparse", "dense"])
def test_training_schedule_excludes_holdout(config, schedule):
    time = training_times(config, schedule)
    assert time[0] == 0 and time[-1] == config["training_end_day"]
    assert len(time) == (4 if schedule == "sparse" else 81)


def test_exact_saved_queries_reject_interpolation():
    with pytest.raises(ValueError, match="exact saved"):
        select_saved([0, 1, 2], np.ones((5, 3)), [0, 1.01])
    np.testing.assert_array_equal(select_saved([0, 1, 2], np.ones((5, 3)), [0, 2]), np.ones((5, 2)))


def test_parameter_coordinate_roundtrip():
    values = {"conductance": .2, "phi0": 6.8, "beta_e": 20}
    actual = decode(tuple(values), encode(tuple(values), values))
    for key in values:
        assert actual[key] == pytest.approx(values[key])


@pytest.mark.parametrize("bad", ["unknown", "holdout"])
def test_undeclared_stage_rejected(config, bad):
    with pytest.raises(ValueError, match="scope"):
        TrainingObjective(config, config["scenarios"][0], bad, "concentrations", [0, 1], np.ones((2, 2)))


@pytest.mark.parametrize("time,values", [([0, 10], np.ones((2, 2))), ([0, 1], np.full((2, 2), np.nan)),
    ([0, 1], -np.ones((2, 2))), ([0, 1], np.ones((3, 2))), ([1, 2], np.ones((2, 2)))])
def test_bad_training_data_rejected(config, time, values):
    with pytest.raises(ValueError, match="training"):
        TrainingObjective(config, config["scenarios"][0], "access_pHi", "concentrations", time, values)


def test_unknown_initial_pHi_never_leaks_from_scenario(config):
    scenario = config["scenarios"][0]
    time, values = observations(config, scenario)
    other = copy.deepcopy(scenario)
    other["initial"][2] = 8.0
    a = TrainingObjective(config, scenario, "access_pHi", "concentrations", time, values)
    b = TrainingObjective(config, other, "access_pHi", "concentrations", time, values)
    x = encode(a.names, {"access_i": 1.2, "phi0": 7.0})
    np.testing.assert_array_equal(a.evaluate(x), b.evaluate(x))
    assert a.trace[-1]["integration_end"] == config["training_end_day"]


def test_budget_counts_every_residual_call(config):
    scenario = config["scenarios"][0]
    time, values = observations(config, scenario)
    config["future_recovery"]["optimizer_budget_max_nfev"] = 1
    objective = TrainingObjective(config, scenario, "oracle_conductance", "concentrations", time, values)
    x = encode(objective.names, {"conductance": .2})
    objective.evaluate(x)
    with pytest.raises(EvaluationBudgetReached):
        objective.evaluate(x)
    assert len(objective.trace) == 1
    fit = recover(config, scenario, "oracle_conductance", "concentrations", time, values, 0)
    assert fit["actual_objective_evaluations"] == 1 and fit["optimizer_success"] is False


@pytest.mark.parametrize("which", [0, 1])
def test_oracle_recovers_clean_conductance(config, which):
    before = copy.deepcopy(config)
    scenario = config["scenarios"][which]
    time, values = observations(config, scenario)
    fit = recover(config, scenario, "oracle_conductance", "concentrations", time, values, 0)
    assert fit["optimizer_success"]
    assert fit["parameters"]["conductance"] == pytest.approx(.3, rel=.001)
    assert fit["actual_objective_evaluations"] <= 100
    assert config == before


def test_parameter_accuracy_is_not_replaced_by_fit_accuracy(config):
    scenario = config["scenarios"][0]
    _, passed = parameter_errors(config, scenario, {"access_i": .7, "phi0": 6.9})
    assert passed is False
    ref = simulate(config, scenario)
    metrics = prediction_metrics(config, scenario, {"access_i": .7, "phi0": 6.9}, ref, ref)
    assert metrics["holdout_prediction_pass"] and not metrics["parameter_recovery_pass"]


def test_multistart_requires_complete_unique_starts(config):
    fits = [{"parameters": {"conductance": v}, "start_index": i} for i, v in enumerate([.3, .301, .299])]
    assert multistart_agreement(config, fits)["multistart_agreement_pass"]
    fits[2]["parameters"]["conductance"] = .7
    assert not multistart_agreement(config, fits)["multistart_agreement_pass"]
    with pytest.raises(ValueError):
        multistart_agreement(config, fits[:2])
    fits[2]["start_index"] = 1
    with pytest.raises(ValueError):
        multistart_agreement(config, fits)
