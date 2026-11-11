from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from fla_stepper_diagnostics import record_stepper
from fla_integration_diagnostics import record_integration
from test_fla_integration_diagnostics import ExchangeRHS


def test_public_bdf_stepper_matches_solve_ivp_control():
    initial=np.ones(114)
    initial[-1]=7.2
    p={"rtol":1e-8,"atol":1e-12,"max_step":.05}
    _,old,report=record_integration(ExchangeRHS(),initial,2.,[1.5,2.],p,-1e-10)
    new,record=record_stepper(ExchangeRHS(),initial,2.,[1.5,2.],p,-1e-10,"BDF")
    assert report["concentration_gate_pass"] and record["concentration_gate_pass"]
    for key in ("accepted_time","accepted_states","time","states","q4_states","q8_states"):
        assert np.array_equal(old[key],new[key])


def test_public_radau_preserves_exchange_without_repair():
    initial=np.ones(114)
    initial[-1]=7.2
    a,r=record_stepper(ExchangeRHS(),initial,2.,[1.5,2.],{"rtol":1e-8,"atol":1e-12,"max_step":.05},-1e-10,"Radau")
    assert r["concentration_gate_pass"]
    assert a["states"][0,-1]==pytest.approx(np.exp(-1),rel=1e-7)
    assert np.allclose(a["states"][0]+a["states"][1],2.,atol=1e-14)


def test_partial_accepted_states_survive_rhs_failure():
    class Broken(ExchangeRHS):
        def __call__(self,t,x):
            if t>1.5:
                raise ValueError("test RHS failure")
            return super().__call__(t,x)
    initial=np.ones(114)
    initial[-1]=7.2
    a,r=record_stepper(Broken(),initial,2.,[1.5,2.],{"rtol":1e-8,"atol":1e-12,"max_step":.05},-1e-10,"Radau")
    assert not r["concentration_gate_pass"] and r["exception"]["message"]=="test RHS failure"
    assert len(a["accepted_time"])>1 and a["accepted_time"][-1]<1.5
    assert "states" in a and "accepted" in r["supports"]
    assert a["accepted_states"][0,0]==1. and initial[0]==1.


def test_successor_verifier_handles_old_partial_evidence_without_dense_array():
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
    from verify_recorded_integrations import check_saved_supports
    a={"initial":np.r_[np.ones(113),7.2],"pool_names":np.array(ExchangeRHS.names),
       "internal_last_state":np.full(114,np.nan)}
    summary,gate=check_saved_supports(a,{"supports":{},"complete_exact_J1":False},list(ExchangeRHS.names),-1e-10)
    assert summary=={} and not gate
