import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src")); sys.path.insert(0, str(ROOT/"scripts"))
from fla_hk_pfk_split import (FREE, unpack, seed_coordinates, coordinate_bounds, inner_margins,
                            choose_nested, assess, score, training_data)
from fla_broad_protected_calibration import POOLS, guard_contract


def context():
    design = json.loads((ROOT/"config/fla_hk_pfk_split.json").read_text())
    seed = -.9
    primitive = {"vmax_VHK": 5., "vmax_VPFK": 2.5494306472194306}
    parameters = {k: v*float(np.exp(seed)) for k, v in primitive.items()}
    parameters.update(vmax_VAK=.5, km_ATP_HK=.2, custom_family="unchanged")
    observations = {"time": [1., 4., 8., 11., 46.], "values": {p: [1.]*5 for p in POOLS}}
    times, y = training_data(observations, 10.)
    guard_design = json.loads((ROOT/"config/fla_broad_protected_joint.json").read_text())
    f = {"design": design, "parameters": parameters, "kinetics": {"conductance": .026, "km_i": 3.49, "km_e": 23.5},
         "primitive_capacities": primitive, "primitive_factor_bounds": [.02, 1.], "seed_log_investment": seed,
         "guards": guard_contract(y*.8, y, guard_design), "initial": [*[1.]*113, 7.2]}
    return f, observations, times, y


@pytest.mark.parametrize("mode", ["paired", "split"])
def test_both_seed_parameterizations_exactly_reproduce_the_parent(mode):
    f, *_ = context()
    parameters, kinetics, _ = unpack(seed_coordinates(f, mode), f, mode)
    assert parameters == f["parameters"] and kinetics == f["kinetics"]


def test_split_changes_only_the_two_declared_capacity_parameters():
    f, *_ = context()
    before = copy.deepcopy(f)
    parameters, kinetics, _ = unpack(seed_coordinates(f, "split")+[-.1, .05], f, "split")
    assert {k for k in parameters if parameters[k] != f["parameters"][k]} == set(FREE)
    assert kinetics == f["kinetics"] and f == before


def test_paired_and_split_have_identical_primitive_envelopes_not_seed_relative_bounds():
    f, *_ = context()
    for mode in ("paired", "split"):
        for factor in (.02, 1.):
            parameters, _, _ = unpack(np.full(len(seed_coordinates(f, mode)), np.log(factor)), f, mode)
            assert parameters["vmax_VHK"] == pytest.approx(5.*factor)
            assert parameters["vmax_VPFK"] == pytest.approx(f["primitive_capacities"]["vmax_VPFK"]*factor)


@pytest.mark.parametrize("x,mode", [([.01, 0.], "split"), ([np.log(.019), -.9], "split"),
                                  ([np.nan], "paired"), ([-.9, -.9], "paired"), ([-.9], "unknown")])
def test_invalid_coordinates_or_bound_expansion_fail(x, mode):
    f, *_ = context()
    with pytest.raises(ValueError): unpack(x, f, mode)


def test_inner_solver_target_tightens_only_margins_not_acceptance_caps():
    f, _, _, y = context()
    guards = copy.deepcopy(f["guards"])
    g = assess(y*.8, y, guards)
    row = {"guards": g}
    assert np.all(inner_margins(row, f) < g["margins"])
    assert f["guards"] == guards and g["passed"]


def test_simpler_paired_fit_wins_numerical_ties_and_parent_is_real_fallback():
    def result(label, value): return {"label": label, "training_score": {"negative_log_likelihood": value}}
    parent, paired = result("parent", 100.), result("paired", 90.)
    chosen, _, _ = choose_nested(parent, paired, result("split", 89.99995), .0001)
    assert chosen is paired
    chosen, _, gain = choose_nested(parent, paired, result("split", 89.), .0001)
    assert chosen["label"] == "split" and gain == 1.
    chosen, _, _ = choose_nested(parent, result("paired", 100.1), result("split", 100.2), .0001)
    assert chosen is parent


def toy_worker(monkeypatch, tmp_path, mode):
    import run_hk_pfk_split as run
    f, obs, times, target = context()
    f["fit_cases"] = {"toy": {"mode": mode, "offset": [0.]*len(seed_coordinates(f, mode))}}
    run.write(tmp_path/"observations.json", obs)
    monkeypatch.setattr(run, "verify_inputs", lambda out: copy.deepcopy(f))
    def prediction(parameters):
        change = sum(np.log(parameters[k]/f["primitive_capacities"][k])-f["seed_log_investment"] for k in FREE)
        return target*.8+.001*change
    def evaluate(x, frozen, mode0, t, y):
        parameters, _, factors = unpack(x, frozen, mode0)
        p = prediction(parameters)
        g = assess(p, y, frozen["guards"])
        return {"log_factors": x.tolist(), "mode": mode0, "valid": True, "factors": factors,
                "predictions": p.tolist(), "score": g.pop("score"), "guards": g}, None
    def predict(initial, parameters, kinetics, end, t):
        return prediction(parameters), SimpleNamespace(t=np.array([1., end]), y=np.column_stack([initial, initial])), None
    monkeypatch.setattr(run, "evaluate", evaluate)
    monkeypatch.setattr(run, "predict_broad", predict)
    return run, f


@pytest.mark.parametrize("mode,expected", [("paired", 2), ("split", 3)])
def test_cost_constraints_and_jacobians_share_actual_integrations(tmp_path, monkeypatch, mode, expected):
    run, _ = toy_worker(monkeypatch, tmp_path, mode)
    def minimize(fun, x, **kwargs):
        fun(x)
        assert kwargs["constraints"][0]["fun"](x).shape == (13,)
        kwargs["jac"](x)
        assert kwargs["constraints"][0]["jac"](x).shape == (13, len(x))
        return SimpleNamespace(x=x, success=True, message="toy", nfev=1, njev=1)
    monkeypatch.setattr(run, "minimize", minimize)
    result = run.fit_one(str(tmp_path), "toy", False)
    assert result["actual_objective_integrations"] == expected and result["training_guards"]["passed"]
    assert run.fit_one(str(tmp_path), "toy", True) == result


def test_preregistered_stagnation_stops_before_an_unlogged_evaluation(tmp_path, monkeypatch):
    run, f = toy_worker(monkeypatch, tmp_path, "split")
    f["design"]["optimizer"].update(stagnation_minimum_calls=4, stagnation_patience_calls=2)
    def minimize(fun, x, **kwargs):
        for i in range(100):
            other = x.copy(); other[0] -= i*.0001
            fun(other)
        raise AssertionError("stagnation guard should stop")
    monkeypatch.setattr(run, "minimize", minimize)
    result = run.fit_one(str(tmp_path), "toy", False)
    assert result["actual_objective_integrations"] == 4 and not result["optimizer_success"]
    assert result["optimizer_stages"][0]["message"] == "preregistered_no_admissible_progress_stop"


def test_actual_integration_budget_includes_probes_and_both_stages(tmp_path, monkeypatch):
    run, f = toy_worker(monkeypatch, tmp_path, "split")
    f["design"]["optimizer"].update(primary_actual_integrations=4, secondary_cumulative_actual_integrations=7)
    sequence = iter(range(1, 100))
    def minimize(fun, x, **kwargs):
        for i in sequence:
            other = x.copy(); other[0] -= i*.0001
            fun(other)
        raise AssertionError("actual budget should stop")
    monkeypatch.setattr(run, "minimize", minimize)
    result = run.fit_one(str(tmp_path), "toy", False)
    assert result["actual_objective_integrations"] == 7 and not result["optimizer_success"]
    assert [s["message"] for s in result["optimizer_stages"]] == ["actual_integration_budget_exhausted"]*2
    assert sum(s["actual_integrations"] for s in result["optimizer_stages"]) == 6


def test_paired_seed_raw_and_executed_rates_match_unchanged_kernel():
    from fla_joint_calibration import JointRHS
    f, *_ = context()
    p, k, _ = unpack(seed_coordinates(f, "paired"), f, "paired")
    before, after = JointRHS(f["parameters"], f["kinetics"]), JointRHS(p, k)
    state = np.ones(114); state[-1] = 7.2
    for values0, values1 in zip(before.rates(1., state), after.rates(1., state)):
        np.testing.assert_array_equal(values0, values1)
