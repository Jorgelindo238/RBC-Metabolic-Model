"""Cheap workflow controls: held-out observations and true objective-call caps."""

import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import run_joint_glucose_energy as campaign
from report_joint_glucose_energy import signed_budget


def setup(monkeypatch, directory, *, future_multiplier=1.):
    parameters={"vmax_VHK":5.}
    frozen={"design":json.loads((ROOT/"config/fla_joint_glucose_energy.json").read_text()),
        "initial":[*[1.]*113,7.2],"parameters":parameters,
        "candidate":{"glucose_kinetics":{"conductance":.027,"km_i":3.49,"km_e":23.5}},
        "resolved_capacities":campaign.resolve_capacities(parameters)}
    frozen["design"]["optimizer"]["maxfun"]=3
    frozen["design"]["optimizer"]["secondary_maxfun"]=5
    data={"time":[1.,4.,8.,11.,46.],"values":{p:[1.,1.1,1.2,1.3,1.4] for p in campaign.POOLS}}
    for values in data["values"].values():
        for i,t in enumerate(data["time"]):
            if t>10:
                values[i]*=future_multiplier
    directory.mkdir()
    campaign.write(directory/"observations.json",data)
    monkeypatch.setattr(campaign,"verify_inputs",lambda out:copy.deepcopy(frozen))

    def predict(initial,parameters,kinetics,end,samples):
        # Deliberately observation-independent stub; temporal masking is the target.
        factor=parameters["vmax_VHK"]/5
        value=np.full((7,len(samples)),.5+factor*.1)
        sol=SimpleNamespace(t=np.array([1.,end]),y=np.column_stack([initial,initial]))
        rhs=SimpleNamespace(jacobian_sparsity=np.eye(114,dtype=bool))
        return value,sol,rhs

    def minimize(cost,x,**kwargs):
        for i in range(50):
            point=x.copy()
            point[0]+=i*.0001
            cost(point)
        raise AssertionError("actual integration cap should interrupt the optimizer")

    monkeypatch.setattr(campaign,"predict",predict)
    monkeypatch.setattr(campaign,"minimize",minimize)


def run(directory):
    return campaign.fit_one(str(directory),10.,"controlled",np.log([1.,.5,.5,1.,1.,.5]))


def test_actual_integrations_are_capped_across_secondary_restart(tmp_path,monkeypatch):
    directory=tmp_path/"budget"
    setup(monkeypatch,directory)
    result=run(directory)
    assert result["actual_objective_integrations"]==5
    assert [s["actual_integrations"] for s in result["optimizer_stages"]]==[3,2]
    assert not result["optimizer_success"]
    assert result["source_times"]==[4.,8.]


def test_late_source_changes_do_not_enter_training_or_selection(tmp_path,monkeypatch):
    a,b=tmp_path/"original",tmp_path/"future_changed"
    setup(monkeypatch,a)
    first=run(a)
    setup(monkeypatch,b,future_multiplier=100.)
    second=run(b)
    for key in ("training_score","selected_log_factors","factors","parameters","glucose_kinetics"):
        assert first[key]==second[key]


def test_budget_integrates_positive_and_negative_rates_before_netting():
    # A reversible reaction has zero net contribution but nonzero turnover.
    result=signed_budget([2.,-1.],np.array([[3.,-3.],[1.,1.]]),[.5,.5])
    assert result["production_mM"]==3.
    assert result["consumption_mM"]==4.
