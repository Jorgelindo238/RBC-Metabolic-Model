from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from fla_ak_pepase import arm_flags,arm_parameters,arm_values,beyond,check_plan,classify,pk_share

PLAN=json.loads((ROOT/"config/fla_ak_pepase_2026_11_11.json").read_text())
AK_PLAN=json.loads((ROOT/"config/fla_ak_ratio_2026_11_11.json").read_text())
CENTER=(2.135939034249409,0.1983945409860798,7.659773742905662)
SEALED=(0.1323102293257943,0.1983945409860798)
BASE,BOUNDS=8.35624219380441,[0.1,3.0]


def test_registered_plan_is_closed_counts_six_integrations_and_reuses_the_sealed_ak_arm():
    check_plan(PLAN)
    assert PLAN["maximum_new_integrations"]==6 and PLAN["hypothesis_arm"]=="ak_balanced_pepase_floor"
    assert PLAN["sealed_ak_arm"]=={"archive":"output/ak_ratio_2026_11_11","case":AK_PLAN["hypothesis_arm"]}
    assert PLAN["expected_balance_ratio"]==AK_PLAN["expected_balance_ratio"]
    for key in ("numerical_parent","control_case","backend","profiles","windows","report_days","phosphoryl_stocks"):
        assert PLAN[key]==AK_PLAN[key]
    assert set(AK_PLAN["ledger_reactions"])<=set(PLAN["ledger_reactions"]) and {"VPK","VPEP_PASE"}<=set(PLAN["ledger_reactions"])


@pytest.mark.parametrize("key",["measured_J1_changed","initial_state_changed","km_changed","bounds_changed","optimization_executed",
                                "followup_calibration_allowed","production_promotion_allowed","J46_replayed"])
def test_any_scope_opening_flag_is_refused(key):
    p=deepcopy(PLAN);p[key]=True
    with pytest.raises(ValueError):
        check_plan(p)


def test_other_parameter_extra_arm_or_swapped_role_is_refused():
    for change in (lambda p:p.update(changed_parameters=["vmax_VAK","vmax_VAK_rev","vmax_VPEP_PASE","vmax_VPK"]),
                   lambda p:p["bound_groups"].update(PK=["vmax_VPK"]),
                   lambda p:p["arms"].update(extra={"ak":"center","pepase":"lower_bound"}),
                   lambda p:p["arms"]["ak_balanced_pepase_floor"].update(pepase="upper_bound"),
                   lambda p:p["arms"]["pepase_floor_only"].update(ak="sealed_balanced"),
                   lambda p:p.update(hypothesis_arm="pepase_floor_only",single_factor_arm="ak_balanced_pepase_floor"),
                   lambda p:p.update(maximum_new_integrations=4)):
        p=deepcopy(PLAN);change(p)
        with pytest.raises(ValueError):
            check_plan(p)


def test_registered_arms_follow_their_rules_inside_the_unchanged_box():
    v={k:arm_values(PLAN["arms"][k],CENTER,SEALED,BASE,BOUNDS) for k in PLAN["arms"]}
    assert v["pepase_floor_only"]==(CENTER[0],CENTER[1],pytest.approx(.835624219380441))
    assert v["ak_balanced_pepase_floor"][:2]==SEALED and v["ak_balanced_pepase_floor"][2]==pytest.approx(.835624219380441)
    forward,reverse,middle=v["ak_balanced_pepase_intermediate"]
    assert (forward,reverse)==SEALED and middle==pytest.approx((CENTER[2]*.835624219380441)**.5)
    assert .835624219380441<middle<CENTER[2]


def test_an_arm_outside_the_box_or_raising_the_phosphatase_is_refused():
    with pytest.raises(ValueError):
        arm_values(PLAN["arms"]["pepase_floor_only"],CENTER,SEALED,BASE,[float("nan"),3.])
    with pytest.raises(ValueError):
        arm_values(PLAN["arms"]["pepase_floor_only"],(CENTER[0],CENTER[1],.5),SEALED,BASE,BOUNDS)
    with pytest.raises(ValueError):
        arm_values(PLAN["arms"]["ak_balanced_pepase_floor"],CENTER,(0.,.2),BASE,BOUNDS)


def test_only_the_three_registered_capacities_change_and_affinities_are_kept():
    center={"vmax_VAK":2.1,"vmax_VAK_rev":.2,"vmax_VPEP_PASE":7.7,"vmax_VPK":.66,"km_PEP":1.04}
    p=arm_parameters(center,.13,.2,.84)
    assert p=={"vmax_VAK":.13,"vmax_VAK_rev":.2,"vmax_VPEP_PASE":.84,"vmax_VPK":.66,"km_PEP":1.04} and center["vmax_VPEP_PASE"]==7.7
    for bad in ((0.,.2,.84),(.13,.2,-1.),(.13,float("nan"),.84)):
        with pytest.raises(ValueError):
            arm_parameters(center,*bad)
    with pytest.raises(ValueError):
        arm_parameters({"vmax_VAK":2.1,"vmax_VAK_rev":.2},.13,.2,.84)


def scores(gap,atp15,adp15,atp4,passed,failed):
    return {p:{"gap":gap,"reserved_guards_pass":passed,"ATP_J15":atp15,"ADP_J15":adp15,"ATP_J4":atp4,"failed_guards":list(failed)}
            for p in ("strict","ultrastrict")}


def arm(gap,atp15=9e-5,adp15=1.8e-6,atp4=.02,passed=True,failed=(),pk=(.9,1.1),pepase=(2.7,9.1),cons=5.6,prod=4.7,paired=True):
    return {"numerical_pass":{"strict":True,"ultrastrict":True},"paired_pass":paired,"scores":scores(gap,atp15,adp15,atp4,passed,failed),
            "ledger":{"PK_J1_J4":pk[0],"PK_J1_J15":pk[1],"PEPASE_J1_J4":pepase[0],"PEPASE_J1_J15":pepase[1],
                      "ATP_consumption":cons,"ATP_production":prod}}


CONTROL=arm(12.089,atp15=8.98e-5,adp15=1.77e-6,cons=5.656,prod=4.747)
AK_ONLY=arm(7.5,atp15=4.4e-3,adp15=1.7e-4,atp4=.113,passed=False,failed=["point:PEP:J4","MSE:G6P"],pk=(1.32,2.92),pepase=(2.34,8.),cons=5.233,prod=4.414)
run=lambda hyp,single=None,mid=None:classify(hyp,single or arm(12.3),mid or arm(7.2,atp15=5e-3,adp15=2e-4),CONTROL,AK_ONLY)


def test_supported_only_when_the_combined_arm_improves_on_the_control_under_all_guards():
    assert run(arm(6.,atp15=.01,adp15=.001))["category"]=="combined_effect_supported"
    assert run(arm(6.,atp15=.01,adp15=.001,passed=False,failed=["point:PEP:J8"]))["category"]=="no_supported_effect"
    assert run(arm(12.3))["category"]=="no_supported_effect"
    assert run(arm(6.,atp15=.01,adp15=1e-6))["category"]=="no_supported_effect"
    assert run(arm(6.,atp15=.01,adp15=.001,paired=False))["category"]=="numerical_failure"


def test_single_factor_arm_alone_gives_its_own_class_and_the_intermediate_arm_rescues_nothing():
    assert run(arm(12.3),single=arm(11.))["category"]=="pepase_alone_effect_only"
    assert run(arm(12.3),mid=arm(6.,atp15=.01,adp15=.001))["category"]=="no_supported_effect"
    assert run(arm(6.,atp15=.01,adp15=.001),single=arm(11.))["category"]=="combined_effect_supported"


def test_beyond_reference_compares_with_the_sealed_ak_only_arm_without_requiring_guards():
    better=arm(6.,atp15=.01,adp15=.001,atp4=.3,passed=False,failed=["point:PEP:J4"])
    assert beyond(better,AK_ONLY) and not beyond(arm(8.,atp15=.01,adp15=.001),AK_ONLY)
    assert not beyond(arm(6.,atp15=1e-3,adp15=.001),AK_ONLY)
    f=run(better)["flags"]["hypothesis"]
    assert f["beyond_reference"] and not f["improves"] and f["pep_guard_failed"] and f["early_only"]
    broken=arm(6.);broken["scores"]["strict"]=None
    assert not beyond(broken,AK_ONLY)


def test_pk_share_flags_use_the_reference_with_the_same_ak_capacities():
    assert pk_share(1.,3.)==.25 and pk_share(0.,0.) is None
    f=arm_flags(arm(7.,pk=(1.6,4.),pepase=(1.,3.)),CONTROL,AK_ONLY)
    assert f["pk_share_J1_J4"]==pytest.approx(1.6/2.6) and f["pk_share_J1_J15"]==pytest.approx(4/7) and f["pk_share_raised"]
    assert not arm_flags(arm(7.,pk=(1.,1.),pepase=(2.,8.)),CONTROL,AK_ONLY)["pk_share_raised"]
    f=arm_flags(arm(12.,cons=5.5,prod=4.8),CONTROL,CONTROL)
    assert f["net_ATP_change_mM"]==pytest.approx((4.8-5.5)-(4.747-5.656)) and not f["pep_guard_failed"]


def test_monotone_response_requires_the_intermediate_gap_between_ak_only_and_combined():
    hyp=arm(6.,atp15=.01,adp15=.001)
    assert run(hyp,mid=arm(6.8))["monotone_response"] and not run(hyp,mid=arm(9.))["monotone_response"]
    broken=arm(6.8);broken["scores"]["strict"]=None
    assert run(hyp,mid=broken)["monotone_response"] is None


def test_no_class_promotes_ungroups_the_search_or_launches_calibration():
    for hyp in (arm(6.,atp15=.01,adp15=.001),arm(12.3),arm(-1.,atp15=1.,adp15=.4)):
        r=run(hyp)
        assert r["working_center_retained"] and r["grouped_search_design_retained"]
        assert not r["production_promoted"] and not r["followup_calibration_launched"]
