from copy import deepcopy
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from fla_guanylate_partition import arm_flags,arm_initial,check_plan,classify,improves,inventory,solve_partition

PLAN=json.loads((ROOT/"config/fla_guanylate_partition_2026_11_10.json").read_text())


def mm(s,k):
    return s/(k+s)


def coded_like(gdp,gtp,atp=0.9329923,adp=1.1693999742386922):
    """Same functional form as the executable NDPK law, with illustrative constants."""
    return 17.6*mm(gdp,.3)*mm(atp,.59)-3.35*mm(gtp,.5)*mm(adp,.4)


def test_registered_plan_is_closed_and_counts_four_integrations():
    check_plan(PLAN)
    assert PLAN["maximum_new_integrations"]==4 and PLAN["hypothesis_arm"]=="B_fixed_phosphoryl"


@pytest.mark.parametrize("key",["measured_J1_changed","parameters_changed","optimization_executed","followup_calibration_allowed",
                                "production_promotion_allowed","J46_replayed"])
def test_any_scope_opening_flag_is_refused(key):
    p=deepcopy(PLAN);p[key]=True
    with pytest.raises(ValueError):
        check_plan(p)


def test_other_pools_or_extra_arms_are_refused():
    p=deepcopy(PLAN);p["changed_pools"]=["GDP","GTP","RIB"]
    with pytest.raises(ValueError):
        check_plan(p)
    p=deepcopy(PLAN);p["arms"]["C"]={"convention":"GDP_plus_GTP","value_mM":1.}
    with pytest.raises(ValueError):
        check_plan(p)


@pytest.mark.parametrize("convention,value",[("GDP_plus_GTP",2.),("GDP_plus_2GTP",3.)])
def test_partition_zeroes_the_supplied_law_and_satisfies_the_declared_convention(convention,value):
    gdp,gtp=solve_partition(coded_like,convention,value,1e-12)
    assert gdp>0 and gtp>0 and abs(coded_like(gdp,gtp))<1e-12
    assert np.isclose(gdp+gtp if convention=="GDP_plus_GTP" else gdp+2*gtp,value,rtol=0,atol=1e-12)


def test_zero_of_the_saturating_law_is_not_the_adenylate_ratio():
    gdp,gtp=solve_partition(coded_like,"GDP_plus_GTP",2.,1e-12)
    assert not np.isclose(gtp/gdp,0.9329923/1.1693999742386922,rtol=.5)


def test_one_condition_does_not_fix_the_pair_without_a_second_convention():
    a=solve_partition(coded_like,"GDP_plus_GTP",2.,1e-12)
    b=solve_partition(coded_like,"GDP_plus_2GTP",3.,1e-12)
    assert not np.allclose(a,b) and abs(coded_like(*a))<1e-12 and abs(coded_like(*b))<1e-12


def test_unbracketed_or_unregistered_partition_is_refused():
    with pytest.raises(ValueError):
        solve_partition(lambda gdp,gtp:1.,"GDP_plus_GTP",2.,1e-12)
    with pytest.raises(ValueError):
        solve_partition(coded_like,"GTP_only",2.,1e-12)


def test_fixed_total_adds_phosphoryl_inventory_and_fixed_phosphoryl_does_not():
    a=inventory(*solve_partition(coded_like,"GDP_plus_GTP",2.,1e-12))
    b=inventory(*solve_partition(coded_like,"GDP_plus_2GTP",3.,1e-12))
    assert np.isclose(a["delta_total_mM"],0.,atol=1e-12) and a["delta_E_G_mM"]>0
    assert np.isclose(a["delta_E_G_mM"],a["GTP_mM"]-1.,atol=1e-12)
    assert np.isclose(b["delta_E_G_mM"],0.,atol=1e-12) and b["delta_total_mM"]<0


def test_only_gdp_and_gtp_change_in_the_arm_state_and_ph_is_kept():
    names=["ATP","GDP","GTP","RIB"]
    x=arm_initial([.9,1.,1.,1.,7.2],names,.07,1.93)
    assert x.tolist()==[.9,.07,1.93,1.,7.2]
    with pytest.raises(ValueError):
        arm_initial([.9,1.,1.,1.,7.2],["ATP","GDP","GTP","RIB","PH","X"],.07,1.93)


def scores(gap,atp15,adp15,atp4=.02,passed=True,failed=()):
    return {p:{"gap":gap,"reserved_guards_pass":passed,"ATP_J15":atp15,"ADP_J15":adp15,"ATP_J4":atp4,"failed_guards":list(failed)}
            for p in ("strict","ultrastrict")}


def arm(gap,atp15=9e-5,adp15=1.8e-6,ndpk=1.9,cons=5.6,**kw):
    numerical=kw.pop("numerical",{"strict":True,"ultrastrict":True})
    paired=kw.pop("paired",True)
    return {"numerical_pass":numerical,"paired_pass":paired,"scores":scores(gap,atp15,adp15,**kw),
            "ledger":{"NDPK_J1_J4":ndpk,"ATP_consumption_J1_J4":cons}}


CONTROL=arm(12.089,atp15=8.98e-5,adp15=1.77e-6,ndpk=1.916,cons=5.656)


def test_improvement_needs_guards_lower_gap_and_no_adenylate_regression():
    assert improves(arm(12.0),CONTROL)
    assert not improves(arm(12.0,passed=False,failed=["point:PEP:J4"]),CONTROL)
    assert not improves(arm(12.089),CONTROL)
    assert not improves(arm(12.0,adp15=1.7e-6),CONTROL)
    assert not improves(arm(12.0,atp15=8.9e-5),CONTROL)
    assert not improves(arm(12.0,paired=False),CONTROL)


def test_worst_profile_gap_decides():
    a=arm(12.0);a["scores"]["ultrastrict"]["gap"]=12.2
    assert not improves(a,CONTROL)


def test_early_atp_rise_alone_is_flagged_and_is_not_an_improvement():
    f=arm_flags(arm(12.3,atp4=.2),CONTROL,.5)
    assert f["early_only"] and not f["improves"] and not f["absolute_J15_targets_reached"]


def test_compensation_is_flagged_when_consumption_falls_by_less_than_half_the_ndpk_reduction():
    assert arm_flags(arm(12.0,ndpk=.9,cons=5.5),CONTROL,.5)["compensation"]["flag"]
    assert not arm_flags(arm(12.0,ndpk=.9,cons=4.8),CONTROL,.5)["compensation"]["flag"]
    assert not arm_flags(arm(12.0,ndpk=2.1,cons=5.9),CONTROL,.5)["compensation"]["flag"]


def test_classification_order_and_inventory_confound():
    good,bad=arm(12.0),arm(12.3)
    assert classify(good,good,CONTROL,.5)["category"]=="partition_effect_supported"
    assert classify(bad,good,CONTROL,.5)["category"]=="inventory_effect_only"
    assert classify(bad,bad,CONTROL,.5)["category"]=="no_supported_effect"
    failed=arm(12.0,numerical={"strict":True,"ultrastrict":False})
    assert classify(failed,good,CONTROL,.5)["category"]=="numerical_failure"


def test_no_class_promotes_changes_the_convention_or_launches_calibration():
    for hyp in (arm(12.0),arm(12.3),arm(-1.)):
        r=classify(hyp,arm(12.0),CONTROL,.5)
        assert r["working_center_retained"] and r["J1_convention_retained"]
        assert not r["production_promoted"] and not r["followup_calibration_launched"]


def test_log_domain_failure_cannot_improve():
    a=arm(12.0);a["scores"]={"strict":None,"ultrastrict":None}
    assert not improves(a,CONTROL) and classify(a,a,CONTROL,.5)["category"]=="no_supported_effect"
