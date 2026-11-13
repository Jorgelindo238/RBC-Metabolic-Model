from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from fla_ak_ratio import arm_capacities,arm_flags,arm_parameters,balance_ratio,check_plan,classify

PLAN=json.loads((ROOT/"config/fla_ak_ratio_2026_11_11.json").read_text())
CENTER,BASE,BOUNDS,RATIO=(2.135939034249409,0.1983945409860798),(1.9451888601553504,0.18067690362584296),[0.05,2.0],0.6669045865283045


def test_registered_plan_is_closed_and_counts_six_integrations():
    check_plan(PLAN)
    assert PLAN["maximum_new_integrations"]==6 and PLAN["hypothesis_arm"]=="balanced_forward_lowered"
    assert PLAN["changed_parameters"]==["vmax_VAK","vmax_VAK_rev"]


@pytest.mark.parametrize("key",["measured_J1_changed","initial_state_changed","km_changed","bounds_changed","optimization_executed",
                                "followup_calibration_allowed","production_promotion_allowed","J46_replayed"])
def test_any_scope_opening_flag_is_refused(key):
    p=deepcopy(PLAN);p[key]=True
    with pytest.raises(ValueError):
        check_plan(p)


def test_other_parameter_extra_arm_or_swapped_role_is_refused():
    for change in (lambda p:p.update(changed_parameters=["vmax_VAK","vmax_VAK_rev","vmax_VNDPK"]),
                   lambda p:p.update(bound_group="NDPK"),
                   lambda p:p["arms"].update(extra={"reverse":"center","ratio":"balance"}),
                   lambda p:p["arms"]["balanced_forward_lowered"].update(reverse="lower_bound"),
                   lambda p:p["arms"]["balanced_forward_lowered"].update(ratio="geometric_mean"),
                   lambda p:p.update(hypothesis_arm="balanced_reverse_upper_bound",capacity_arm="balanced_forward_lowered"),
                   lambda p:p.update(maximum_new_integrations=4)):
        p=deepcopy(PLAN);change(p)
        with pytest.raises(ValueError):
            check_plan(p)


def test_balance_ratio_is_read_from_the_supplied_law_and_zeroes_it():
    law=lambda vf,vr:vf*.7438633142574973-vr*.4960858560284705
    r=balance_ratio(law,*CENTER,1e-12)
    assert r==pytest.approx(RATIO,rel=1e-12) and abs(law(r*.2,.2))<1e-15


def test_a_law_that_is_not_linear_or_not_forward_minus_reverse_is_refused():
    for law in (lambda vf,vr:vf*vf*.7-vr*.5,lambda vf,vr:vf*.7-vr*.5+.1,lambda vf,vr:vf*.7+vr*.5,lambda vf,vr:-vf*.7-vr*.5):
        with pytest.raises(ValueError):
            balance_ratio(law,*CENTER,1e-12)


def test_registered_arms_reach_their_ratio_inside_the_unchanged_box():
    values={k:arm_capacities(PLAN["arms"][k],CENTER,BASE,RATIO,BOUNDS) for k in PLAN["arms"]}
    forward,reverse,factors=values["balanced_forward_lowered"]
    assert reverse==CENTER[1] and forward/reverse==pytest.approx(RATIO) and factors[0]==pytest.approx(.068019220157)
    forward,reverse,factors=values["balanced_reverse_upper_bound"]
    assert factors[1]==pytest.approx(2.) and forward/reverse==pytest.approx(RATIO) and factors[0]==pytest.approx(.123889518572)
    forward,reverse,factors=values["intermediate_ratio"]
    assert reverse==CENTER[1] and forward/reverse==pytest.approx((RATIO*CENTER[0]/CENTER[1])**.5)
    assert RATIO<forward/reverse<CENTER[0]/CENTER[1]


def test_an_arm_outside_the_registered_box_is_refused_instead_of_widening_it():
    with pytest.raises(ValueError):
        arm_capacities(PLAN["arms"]["balanced_forward_lowered"],CENTER,BASE,.3,BOUNDS)
    with pytest.raises(ValueError):
        arm_capacities(PLAN["arms"]["balanced_reverse_upper_bound"],CENTER,BASE,RATIO,[.2,2.])


def test_only_the_two_ak_capacities_change_and_affinities_are_kept():
    center={"vmax_VAK":2.1,"vmax_VAK_rev":.2,"vmax_VNDPK":17.6,"km_ADP":.3}
    p=arm_parameters(center,.13,.2)
    assert p=={"vmax_VAK":.13,"vmax_VAK_rev":.2,"vmax_VNDPK":17.6,"km_ADP":.3} and center["vmax_VAK"]==2.1
    for bad in ((0.,.2),(.13,-1.),(float("nan"),.2)):
        with pytest.raises(ValueError):
            arm_parameters(center,*bad)
    with pytest.raises(ValueError):
        arm_parameters({"vmax_VAK":2.1},.13,.2)


def scores(gap,atp15,adp15,atp4,passed,failed):
    return {p:{"gap":gap,"reserved_guards_pass":passed,"ATP_J15":atp15,"ADP_J15":adp15,"ATP_J4":atp4,"failed_guards":list(failed)}
            for p in ("strict","ultrastrict")}


def arm(gap,atp15=9e-5,adp15=1.8e-6,atp4=.02,passed=True,failed=(),ak=0.,cons=5.6,prod=4.7,paired=True):
    return {"numerical_pass":{"strict":True,"ultrastrict":True},"paired_pass":paired,
            "scores":scores(gap,atp15,adp15,atp4,passed,failed),"ledger":{"AK":ak,"ATP_consumption":cons,"ATP_production":prod}}


CONTROL=arm(12.089,atp15=8.98e-5,adp15=1.77e-6,ak=1.1208,cons=5.656,prod=4.747)
run=lambda hyp,cap=None,mid=None:classify(hyp,cap or arm(12.3),mid or arm(12.2),CONTROL,.5)


def test_supported_only_when_the_hypothesis_arm_improves_under_all_guards():
    assert run(arm(11.))["category"]=="ak_ratio_effect_supported"
    assert run(arm(11.,passed=False,failed=["point:PEP:J4"]))["category"]=="no_supported_effect"
    assert run(arm(12.3))["category"]=="no_supported_effect"
    assert run(arm(11.,adp15=1e-6))["category"]=="no_supported_effect"
    assert run(arm(11.,paired=False))["category"]=="numerical_failure"


def test_capacity_arm_alone_gives_its_own_class_and_the_intermediate_arm_rescues_nothing():
    assert run(arm(12.3),cap=arm(11.))["category"]=="capacity_dependent_effect_only"
    assert run(arm(12.3),mid=arm(11.))["category"]=="no_supported_effect"
    assert run(arm(11.),cap=arm(11.))["category"]=="ak_ratio_effect_supported"


def test_monotone_response_requires_the_intermediate_gap_between_the_other_two():
    assert run(arm(11.),mid=arm(11.5))["monotone_response"]
    assert not run(arm(11.),mid=arm(12.5))["monotone_response"]
    broken=arm(11.5);broken["scores"]["strict"]=None
    assert run(arm(11.),mid=broken)["monotone_response"] is None


def test_consumption_compensation_when_demand_falls_with_the_removed_ak_production():
    f=arm_flags(arm(12.,ak=0.,cons=4.6,prod=3.7),CONTROL,.5)
    assert f["ak_flux_reduced"] and f["consumption_compensation"] and f["net_ATP_change_mM"]==pytest.approx(.009)
    f=arm_flags(arm(12.,ak=0.,cons=5.5,prod=3.7),CONTROL,.5)
    assert f["ak_flux_reduced"] and not f["consumption_compensation"] and f["net_ATP_change_mM"]<0
    f=arm_flags(arm(12.,ak=1.5,cons=4.6,prod=4.7),CONTROL,.5)
    assert not f["ak_flux_reduced"] and not f["consumption_compensation"]


def test_early_atp_rise_alone_is_flagged_and_is_not_an_improvement():
    f=arm_flags(arm(12.3,atp4=.3),CONTROL,.5)
    assert f["early_only"] and not f["improves"] and not f["absolute_J15_targets_reached"]


def test_no_class_promotes_ungroups_the_search_or_launches_calibration():
    for hyp in (arm(11.),arm(12.3),arm(-1.)):
        r=run(hyp)
        assert r["working_center_retained"] and r["grouped_search_design_retained"]
        assert not r["production_promoted"] and not r["followup_calibration_launched"]
