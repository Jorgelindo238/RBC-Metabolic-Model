import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.optimize import minimize_scalar

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
sys.path.insert(0, str(ROOT/"scripts"))
from fla_broad_protected_calibration import POOLS, training_data, score, guard_contract, assess, best_feasible


def setup():
    design = json.loads((ROOT/"config/fla_broad_protected_joint.json").read_text())
    observations = {"time": [1., 4., 8., 11., 46.], "values": {p: [1.]*5 for p in POOLS}}
    times, target = training_data(observations, 10.)
    reference = target*.8
    return design, observations, times, target, reference, guard_contract(reference, target, design)


@pytest.mark.parametrize("pool", POOLS)
def test_each_of_eleven_pools_individually_vetoes_a_regression(pool):
    d, obs, t, y, p, contract = setup()
    candidate = y*.9
    candidate[POOLS.index(pool)] = .5
    result = assess(candidate, y, contract)
    assert not result["passed"] and "RMSE:"+pool in result["failed_constraints"]
    assert len(result["margins"]) == 13


@pytest.mark.parametrize("j", [0, 1])
def test_each_PEP_time_vetoes_compensated_RMSE_improvement(j):
    d, obs, t, y, p, _ = setup()
    p[POOLS.index("PEP")] = .6
    contract = guard_contract(p, y, d)
    candidate = y*.95
    candidate[POOLS.index("PEP")] = 1.
    candidate[POOLS.index("PEP"), j] = .5
    result = assess(candidate, y, contract)
    assert result["RMSE_mM"]["PEP"] < contract["reference_score"]["RMSE_mM"]["PEP"]
    assert result["failed_constraints"] == [f"absolute:PEP:J{t[j]:g}"]


def test_training_excludes_initial_and_future_observations():
    d, obs, t, y, p, contract = setup()
    for values in obs["values"].values():
        values[0], values[3], values[4] = -1e10, float("nan"), -100.
    t1, y1 = training_data(obs, 10.)
    np.testing.assert_array_equal(t1, t)
    np.testing.assert_array_equal(y1, y)


def test_fixed_allowance_reserves_replay_margin_and_supports_zero_reference_error():
    d, obs, t, y, reference, _ = setup()
    reference[POOLS.index("PEP")] = y[POOLS.index("PEP")]
    contract = guard_contract(reference, y, d)
    assert all(np.isfinite(contract["normalization_mM"]))
    candidate = reference.copy()
    candidate[POOLS.index("PEP")] += 5e-6
    assert not assess(candidate, y, contract)["passed"]
    assert assess(candidate, y, contract, phase="audit")["passed"]


def test_shared_profile_retains_full_density_normalizers():
    d, obs, t, y, p, _ = setup()
    prediction = p*np.linspace(.9, 1.1, p.size).reshape(p.shape)
    result = score(prediction, y)
    def cost(logv):
        variance = np.exp(logv)
        residual = np.log(y/prediction)+variance/2
        return np.sum(np.log(y)+.5*np.log(2*np.pi*variance)+residual**2/(2*variance))
    optimized = minimize_scalar(cost, bounds=(-20., 3.), method="bounded")
    assert result["negative_log_likelihood"] == pytest.approx(optimized.fun, abs=1e-9)
    assert result["count"] == 22 and not result["independent_teacher_likelihood"]


@pytest.mark.parametrize("kind", ["zero", "nan", "shape", "unordered", "empty"])
def test_invalid_training_values_not_imputed(kind):
    d, obs, *_ = setup()
    if kind == "zero": obs["values"]["B23PG"][1] = 0.
    if kind == "nan": obs["values"]["F6P"][2] = float("nan")
    if kind == "shape": obs["values"]["PEP"] = [1.]
    if kind == "unordered": obs["time"] = [1., 8., 4., 11., 46.]
    if kind == "empty": obs["time"] = [11., 12., 13., 14., 46.]
    with pytest.raises(ValueError): training_data(obs, 10.)


def test_alias_channels_not_admitted_and_low_infeasible_cost_does_not_win():
    d, obs, t, y, p, contract = setup()
    d["source_aliases_excluded"]["F6P"] = "other"
    with pytest.raises(ValueError): guard_contract(p, y, d)
    good = {"valid": True, "guards": {"passed": True}, "score": {"negative_log_likelihood": 100.}}
    bad = {"valid": True, "guards": {"passed": False}, "score": {"negative_log_likelihood": -100.}}
    assert best_feasible([good, bad]) is good


def toy_worker(monkeypatch, tmp_path):
    import run_broad_protected_joint as run
    from fla_joint_calibration import resolve_capacities
    d, obs, t, y, p, guards = setup()
    d["optimizer"].update(primary_actual_integrations=20, secondary_cumulative_actual_integrations=40)
    frozen = {"design": d, "parent_design": json.loads((ROOT/"config/fla_joint_glucose_energy.json").read_text()),
        "parameters": {"vmax_VHK": 5.}, "resolved_capacities": resolve_capacities({"vmax_VHK": 5.}),
        "candidate": {"glucose_kinetics": {"conductance": .027, "km_i": 3.49, "km_e": 23.5}},
        "initial": [*[1.]*113, 7.2], "starts": {"control": [0.]*6}, "guards": guards}
    run.write(tmp_path/"observations.json", obs)
    monkeypatch.setattr(run, "verify_inputs", lambda out: copy.deepcopy(frozen))
    def evaluate(x, f, times, target):
        prediction = y*.8+.001*x[0]
        g = assess(prediction, y, guards)
        return {"log_factors": x.tolist(), "valid": True, "predictions": prediction.tolist(),
                "score": g.pop("score"), "guards": g}
    def predict(initial, parameters, kinetics, end, times):
        x = np.log(kinetics["conductance"]/.027)
        sol = SimpleNamespace(t=np.array([1., end]), y=np.column_stack([initial, initial]))
        return y*.8+.001*x, sol, None
    monkeypatch.setattr(run, "evaluate", evaluate)
    monkeypatch.setattr(run, "predict_broad", predict)
    return run, frozen


def test_thirteen_constraint_jacobians_share_the_seven_ODE_evaluations(tmp_path, monkeypatch):
    run, _ = toy_worker(monkeypatch, tmp_path)
    def minimize(fun, x, **kw):
        fun(x)
        assert kw["constraints"][0]["fun"](x).shape == (13,)
        kw["jac"](x)
        assert kw["constraints"][0]["jac"](x).shape == (13, 6)
        return SimpleNamespace(x=x, success=True, message="toy", nfev=1, njev=1)
    monkeypatch.setattr(run, "minimize", minimize)
    result = run.fit_one(str(tmp_path), "control", False)
    assert result["actual_objective_integrations"] == 7 and result["training_guards"]["passed"]
    assert run.fit_one(str(tmp_path), "control", True) == result


def test_cumulative_budget_counts_actual_calls_across_restart(tmp_path, monkeypatch):
    run, frozen = toy_worker(monkeypatch, tmp_path)
    frozen["design"]["optimizer"].update(primary_actual_integrations=5, secondary_cumulative_actual_integrations=9)
    def minimize(fun, x, **kw):
        for i in range(100):
            other = x.copy()
            other[0] += i*.0001
            fun(other)
            kw["constraints"][0]["fun"](other)
        raise AssertionError("budget should stop objective")
    monkeypatch.setattr(run, "minimize", minimize)
    result = run.fit_one(str(tmp_path), "control", False)
    assert result["actual_objective_integrations"] == 9 and not result["optimizer_success"]
    assert result["training_guards"]["passed"]
