import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import fla_integration_diagnostics as diagnostic


def test_support_retains_negative_species_time_and_minimum():
    x=np.array([[1.,2.,3.],[0.,-2e-10,-3e-10]])
    r=diagnostic.inspect_support([1.,2.,3.],x,["ATP","O2"],-1e-10)
    assert not r["pass"] and r["worst_finite"]["pool"]=="O2"
    assert r["worst_finite"]["minimum_day"]==3.
    assert r["first_sampled_policy_violation"]=={"day":2.,"pool":"O2"}
    assert r["per_species"][1]["below_policy_count"]==2
    assert np.array_equal(x[1],[0.,-2e-10,-3e-10])
    json.dumps(r,allow_nan=False)


def test_nonfinite_evidence_is_not_imputed_or_serialized_as_nan():
    r=diagnostic.inspect_support([1.,2.],[[np.nan,np.inf],[1.,0.]],["ATP","O2"],-1e-10)
    assert not r["pass"] and r["nonfinite_count"]==2
    assert r["per_species"][0]["minimum_mM"] is None
    assert r["per_species"][0]["first_nonfinite_day"]==1.
    json.dumps(r,allow_nan=False)


def test_tolerated_tiny_negative_is_reported_not_called_exact_nonnegativity():
    r=diagnostic.inspect_support([1.,2.],[[0.,-1e-11]],["O2"],-1e-10)
    assert r["pass"] and r["per_species"][0]["negative_count"]==1
    assert r["worst_finite"]["minimum_mM"]==-1e-11


def test_concentration_gate_is_fail_closed_before_rate_audit():
    report={"concentration_gate_pass":False,"supports":{"dense":{"pass":False}}}
    with pytest.raises(diagnostic.ConcentrationRejected) as error:
        diagnostic.audit_recorded_solution(None,{},report,{},lambda t,x:pytest.fail("rate audit on rejected states"))
    assert error.value.diagnostics is report


class ExchangeRHS:
    names=tuple(["ATP","ADP","O2"]+[f"P{i}" for i in range(110)])
    jacobian_sparsity=np.eye(114,dtype=bool)
    jacobian_sparsity[1,0]=True

    def __call__(self,t,x):
        d=np.zeros(114)
        d[0],d[1]=-x[0],x[0]
        return d


def test_recording_solves_existing_bdf_without_changing_initial_state():
    initial=np.ones(114)
    initial[-1]=7.2
    sol,arrays,r=diagnostic.record_integration(ExchangeRHS(),initial,2.,[1.5,2.],
        {"rtol":1e-8,"atol":1e-12,"max_step":.05},-1e-10)
    assert r["concentration_gate_pass"] and sol.success
    assert np.array_equal(arrays["accepted_states"][:,0],initial)
    assert set(r["supports"])=={"accepted","dense","quadrature4","quadrature8"}
    assert arrays["states"][0,-1]==pytest.approx(np.exp(-1),rel=1e-6)
    assert initial[0]==1.


def test_dense_negative_cannot_hide_behind_positive_accepted_states(monkeypatch):
    initial=np.ones(114)
    initial[-1]=7.2
    def fake(probe,span,y0,**kwargs):
        internal=y0.copy()
        internal[2]=-1.
        probe(1.,internal)
        def dense(t):
            x=np.tile(y0[:,None],(1,len(np.atleast_1d(t))))
            t=np.atleast_1d(t)
            x[2]=1-8*(t-1)*(2-t)
            return x
        return SimpleNamespace(t=np.array([1.,2.]),y=np.tile(y0[:,None],(1,2)),sol=dense,
            success=True,status=0,message="test",nfev=1,njev=0,nlu=0)
    monkeypatch.setattr(diagnostic,"solve_ivp",fake)
    _,arrays,r=diagnostic.record_integration(ExchangeRHS(),initial,2.,[1.5],{"rtol":1e-7,"atol":1e-9},-1e-10)
    assert r["supports"]["accepted"]["pass"] and not r["supports"]["dense"]["pass"]
    assert not r["concentration_gate_pass"] and arrays["states"][2].min()<0
    with pytest.raises(diagnostic.ConcentrationRejected):
        diagnostic.require_concentration_contract(r)


def test_internal_newton_proposals_are_not_an_admission_gate(monkeypatch):
    initial=np.ones(114)
    initial[-1]=7.2
    def fake(probe,span,y0,**kwargs):
        proposal=y0.copy()
        proposal[2]=-1.
        probe(1.,proposal)
        return SimpleNamespace(t=np.array([1.,2.]),y=np.tile(y0[:,None],(1,2)),
            sol=lambda t:np.tile(y0[:,None],(1,len(np.atleast_1d(t)))),
            success=True,status=0,message="test",nfev=1,njev=0,nlu=0)
    monkeypatch.setattr(diagnostic,"solve_ivp",fake)
    _,_,r=diagnostic.record_integration(ExchangeRHS(),initial,2.,[1.5],{"rtol":1e-7,"atol":1e-9},-1e-10)
    assert r["internal_RHS"]["worst_finite_proposal"]["value_mM"]==-1
    assert r["concentration_gate_pass"]
