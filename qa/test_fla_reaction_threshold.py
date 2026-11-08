from copy import deepcopy
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from fla_reaction_threshold import compare_replays,element_comparison,plateau_decision,threshold_context


def test_threshold_change_never_mutates_frozen_parameters_or_numeric_contract():
    f={"parameters":{"vmax":2.,"km":3.},"initial":[1.,2.],"numeric":{"availability_threshold_mM":.001,"negative_tolerance_mM":-1e-10}}
    old=deepcopy(f)
    local=threshold_context(f,1e-6)
    assert f==old and local["numeric"]=={**f["numeric"],"availability_threshold_mM":1e-6}
    assert local["parameters"] is f["parameters"] and local["initial"] is f["initial"]


@pytest.mark.parametrize("value",[0.,-1.,np.nan,np.inf])
def test_nonpositive_or_nonfinite_thresholds_rejected(value):
    with pytest.raises(ValueError):
        threshold_context({"numeric":{}},value)


def example():
    pools=np.array(["ATP","ADP","AMP","GDP","GTP","GMP"])
    a={"time":np.array([1,4,8,11,15]),"pool_names":pools,"states":np.full((6,5),1e-6),
       "raw8":np.full((2,14),1e-6),"executed8":np.full((2,14),1e-6)}
    n={"comparison_atol_mM":1e-5,"comparison_rtol":.01}
    p={"focus_pools":pools.tolist(),"focus_atol_mM":1e-10,"focus_rtol":.01,
       "executed_integral_atol_mM":1e-8,"executed_integral_rtol":.01}
    return a,n,p


def test_small_adenylate_change_cannot_hide_under_old_absolute_tolerance():
    a,n,p=example()
    b=deepcopy(a)
    b["states"][1,-1]=2e-6
    r=compare_replays(a,b,n,p,[4,8,11,15])
    assert all(v["pass"] for v in r["inherited"].values())
    assert not r["focused_nucleotides"]["pass"] and not r["pass"]


def test_small_executed_flux_change_has_its_own_guard():
    a,n,p=example()
    b=deepcopy(a)
    b["executed8"][0,10]=2e-6
    r=compare_replays(a,b,n,p,[4,8,11,15])
    assert r["inherited"]["executed8"]["pass"] and not r["focused_executed_integrals"]["pass"]


def test_no_average_can_hide_one_failed_date():
    a,n,p=example()
    b=deepcopy(a)
    b["states"][0,3]*=1.1
    assert not compare_replays(a,b,n,p,[4,8,11,15])["pass"]


def test_exact_zero_is_not_replaced_by_a_pseudocount():
    assert element_comparison([0.],[0.],1e-10,.01)["pass"]
    assert not element_comparison([0.],[1e-8],1e-10,.01)["pass"]


def test_plateau_requires_two_final_pairs_and_both_solver_profiles():
    levels=["e3","e4","e5","e6"]
    sol={k:{"numerical_pass":True,"comparison":{"pass":True}} for k in levels}
    adjacent={a+"__"+b:{p:{"pass":True} for p in ("strict","ultrastrict")} for a,b in zip(levels,levels[1:])}
    adjacent["e3__e4"]["strict"]["pass"]=False
    assert plateau_decision(levels,sol,adjacent,2)["registered_plateau"]
    adjacent["e4__e5"]["strict"]["pass"]=False
    assert not plateau_decision(levels,sol,adjacent,2)["registered_plateau"]
    adjacent["e4__e5"]["strict"]["pass"]=True
    sol["e5"]["numerical_pass"]=False
    assert not plateau_decision(levels,sol,adjacent,2)["registered_plateau"]
