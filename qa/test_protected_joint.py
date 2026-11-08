"""Regression guards, temporal isolation, constraint caching and honest fallback."""

import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.optimize import minimize_scalar

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fla_protected_calibration import POOLS, training_data, score, guard_contract, assess, best_feasible


def design():
    return json.loads((ROOT / "config/fla_protected_joint.json").read_text())


def observations():
    return {"time": [1.,4.,8.,11.,46.], "values": {p:[1.,1.1,1.2,1.3,1.4] for p in POOLS}}


def setup():
    t,y = training_data(observations(),10.)
    pred = y*.8
    return t,y,pred,guard_contract(pred,y,design())


def test_all_nine_pools_have_fixed_component_limits_and_reserved_margin():
    _,y,p,c = setup()
    assert c["pools"] == list(POOLS) and c["training_only"]
    assert np.all(np.array(c["fit_limit_RMSE_mM"]) < c["audit_limit_RMSE_mM"])
    assert assess(p,y,c)["passed"]


@pytest.mark.parametrize("pool", POOLS)
def test_any_pool_regression_is_rejected_even_if_the_other_eight_improve(pool):
    _,y,p,c = setup()
    candidate = y*.99
    candidate[POOLS.index(pool)] = y[POOLS.index(pool)]*.5
    r = assess(candidate,y,c)
    assert not r["passed"] and r["failed_pools"] == [pool]


def test_audit_allowance_does_not_become_free_fitting_tolerance():
    _,y,p,c = setup()
    reference=np.array(c["reference_RMSE_mM"])
    allowance=np.array(c["numerical_allowance_mM"])
    # Constant positive residuals produce the desired exact per-channel RMS.
    candidate = y+(reference+.5*allowance)[:,None]
    assert not assess(candidate,y,c,phase="fit")["passed"]
    assert assess(candidate,y,c,phase="audit")["passed"]


def test_future_values_do_not_change_training_targets_limits_or_likelihood():
    original=observations()
    other=copy.deepcopy(original)
    for v in other["values"].values():
        v[0]=9999
        v[3:]=[1e8,1e9]
    t,y=training_data(original,10.)
    tt,yy=training_data(other,10.)
    np.testing.assert_array_equal(t,tt)
    np.testing.assert_array_equal(y,yy)
    assert t.tolist()==[4.,8.]
    assert guard_contract(y*.8,y,design())==guard_contract(yy*.8,yy,design())


def test_shared_profile_retains_all_density_normalizers():
    _,y,p,_=setup()
    p=p*np.linspace(.8,1.2,p.size).reshape(p.shape)
    value=score(p,y)
    def nll(logv):
        v=np.exp(logv)
        r=np.log(y/p)+v/2
        return float(np.sum(r*r/(2*v)+np.log(y)+.5*np.log(2*np.pi*v)))
    result=minimize_scalar(nll,bounds=(-20.,3.),method="bounded")
    assert value["negative_log_likelihood"]==pytest.approx(result.fun,abs=1e-9)
    assert value["count"]==18 and not value["independent_teacher_likelihood"]


def test_infeasible_low_cost_never_displaces_the_control():
    _,y,p,c=setup()
    good=assess(p,y,c)
    bad=assess(y*.5,y,c)
    trace=[{"valid":True,"guards":good,"score":{"negative_log_likelihood":100.},"tag":"control"},
           {"valid":True,"guards":bad,"score":{"negative_log_likelihood":-100.},"tag":"rejected"}]
    assert best_feasible(trace)["tag"]=="control"
    with pytest.raises(ValueError): best_feasible(trace[1:])


@pytest.mark.parametrize("kind", ["zero", "nonfinite", "shape", "empty", "unordered"])
def test_invalid_data_not_sanitized(kind):
    obs=observations()
    if kind=="zero": obs["values"]["PEP"][1]=0
    if kind=="nonfinite": obs["values"]["G6P"][2]=float("nan")
    if kind=="shape": obs["values"]["ATP"]=[1.]
    if kind=="empty": obs["time"]=[11.,12.,13.,14.,15.]
    if kind=="unordered": obs["time"]=[1.,8.,4.,11.,46.]
    with pytest.raises(ValueError): training_data(obs,10.)


def toy_worker(monkeypatch,tmp_path):
    sys.path.insert(0,str(ROOT/"scripts"))
    import run_protected_joint as run
    from fla_joint_calibration import resolve_capacities
    d=design()
    d["optimizer"]["primary_actual_integrations"]=20
    d["optimizer"]["secondary_cumulative_actual_integrations"]=40
    parent=json.loads((ROOT/"config/fla_joint_glucose_energy.json").read_text())
    data=observations()
    times,target=training_data(data,10.)
    frozen={"design":d,"parent_design":parent,"parameters":{"vmax_VHK":5.},
        "resolved_capacities":resolve_capacities({"vmax_VHK":5.}),
        "candidate":{"glucose_kinetics":{"conductance":.027,"km_i":3.49,"km_e":23.5}},
        "initial":[*[1.]*113,7.2],"starts":{"control":[0.]*6},
        "guards":guard_contract(target*.8,target,d)}
    run.write(tmp_path/"observations.json",data)
    monkeypatch.setattr(run,"verify_inputs",lambda out:copy.deepcopy(frozen))

    def evaluate(x,f,t,y):
        pred=y*.8+.001*x[0]
        g=assess(pred,y,f["guards"])
        return {"log_factors":x.tolist(),"valid":True,"predictions":pred.tolist(),
                "score":g["score"],"guards":{k:v for k,v in g.items() if k!="score"}}

    def predict(initial,params,kinetics,end,t):
        x=np.log(kinetics["conductance"]/.027)
        pred=target*.8+.001*x
        sol=SimpleNamespace(t=np.array([1.,end]),y=np.column_stack([initial,initial]))
        return pred,sol,None

    monkeypatch.setattr(run,"evaluate",evaluate)
    monkeypatch.setattr(run,"predict_nine",predict)
    return run,frozen


def test_objective_constraint_and_jacobians_share_each_ODE_evaluation(tmp_path,monkeypatch):
    run,_=toy_worker(monkeypatch,tmp_path)
    def minimize(fun,x,**kw):
        fun(x)
        kw["constraints"][0]["fun"](x)
        kw["jac"](x)
        kw["constraints"][0]["jac"](x)
        return SimpleNamespace(x=x,success=True,message="toy",nfev=1,njev=1)
    monkeypatch.setattr(run,"minimize",minimize)
    result=run.fit_one(str(tmp_path),"control",False)
    assert result["actual_objective_integrations"]==7
    assert result["training_guards"]["passed"]
    assert run.fit_one(str(tmp_path),"control",True)==result


def test_actual_budget_counts_cached_constraint_calls_and_secondary_restart(tmp_path,monkeypatch):
    run,f=toy_worker(monkeypatch,tmp_path)
    f["design"]["optimizer"]["primary_actual_integrations"]=5
    f["design"]["optimizer"]["secondary_cumulative_actual_integrations"]=9
    def minimize(fun,x,**kw):
        for i in range(100):
            point=x.copy()
            point[0]+=i*.0001
            fun(point)
            kw["constraints"][0]["fun"](point)
        raise AssertionError("actual integration budget should stop this toy")
    monkeypatch.setattr(run,"minimize",minimize)
    result=run.fit_one(str(tmp_path),"control",False)
    assert result["actual_objective_integrations"]==9
    assert not result["optimizer_success"]
    assert result["training_guards"]["passed"]
