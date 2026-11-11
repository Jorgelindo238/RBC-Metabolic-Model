from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from fla_ribose_stock import arm_flags,arm_initial,check_plan,classify,inventory

PLAN=json.loads((ROOT/"config/fla_ribose_stock_2026_11_10.json").read_text())


def test_registered_plan_is_closed_and_counts_four_integrations():
    check_plan(PLAN)
    assert PLAN["maximum_new_integrations"]==4 and PLAN["hypothesis_arm"]=="JA_historical"
    assert PLAN["arms"]["JA_historical"]["RIB_mM"]==0.0023


@pytest.mark.parametrize("key",["measured_J1_changed","parameters_changed","optimization_executed","followup_calibration_allowed",
                                "production_promotion_allowed","J46_replayed"])
def test_any_scope_opening_flag_is_refused(key):
    p=deepcopy(PLAN);p[key]=True
    with pytest.raises(ValueError):
        check_plan(p)


def test_other_pool_extra_arm_or_out_of_range_stock_is_refused():
    for change in (lambda p:p.update(changed_pool="R5P"),
                   lambda p:p["arms"].update(C={"RIB_mM":.5,"provenance":"x"}),
                   lambda p:p["arms"]["JA_historical"].update(RIB_mM=0.),
                   lambda p:p["arms"]["JA_historical"].update(RIB_mM=2.),
                   lambda p:p["arms"]["intermediate_diagnostic"].update(RIB_mM=.001)):
        p=deepcopy(PLAN);change(p)
        with pytest.raises(ValueError):
            check_plan(p)


def test_only_the_registered_pool_changes_and_ph_is_kept():
    names=["ATP","RIB","R5P"]
    assert arm_initial([.9,1.,1.6,7.2],names,"RIB",.0023).tolist()==[.9,.0023,1.6,7.2]
    with pytest.raises(ValueError):
        arm_initial([.9,1.,1.6,7.2],names,"RIB",1.)
    with pytest.raises(ValueError):
        arm_initial([.9,1.,1.6,7.2],names,"RIB",-.1)


def test_ribose_change_removes_pentose_and_adds_no_phosphoryl_inventory():
    i=inventory(.0023,1.)
    assert i["pentose_inventory_change_mM"]==pytest.approx(-.9977) and i["phosphoryl_inventory_change_mM"]==0.


def scores(gap,atp15,adp15,atp4,passed,failed):
    return {p:{"gap":gap,"reserved_guards_pass":passed,"ATP_J15":atp15,"ADP_J15":adp15,"ATP_J4":atp4,"failed_guards":list(failed)}
            for p in ("strict","ultrastrict")}


def arm(gap,atp15=9e-5,adp15=1.8e-6,atp4=.02,passed=True,failed=(),rka=0.,cons=4.7,prod=4.7,numerical=None,paired=True):
    return {"numerical_pass":numerical or {"strict":True,"ultrastrict":True},"paired_pass":paired,
            "scores":scores(gap,atp15,adp15,atp4,passed,failed),"ledger":{"RKa":rka,"ATP_consumption":cons,"ATP_production":prod}}


CONTROL=arm(12.089,atp15=8.98e-5,adp15=1.77e-6,rka=1.,cons=5.656,prod=4.747)


def test_supported_only_when_the_hypothesis_arm_improves_under_all_guards():
    assert classify(arm(11.),arm(11.5),CONTROL,.5)["category"]=="ribose_stock_effect_supported"
    assert classify(arm(11.,passed=False,failed=["point:PEP:J4"]),arm(11.5),CONTROL,.5)["category"]=="no_supported_effect"
    assert classify(arm(12.3),arm(11.5),CONTROL,.5)["category"]=="no_supported_effect"
    assert classify(arm(11.,adp15=1e-6),arm(11.5),CONTROL,.5)["category"]=="no_supported_effect"
    assert classify(arm(11.,paired=False),arm(11.5),CONTROL,.5)["category"]=="numerical_failure"


def test_an_improving_intermediate_arm_cannot_rescue_the_hypothesis():
    assert classify(arm(12.3),arm(11.),CONTROL,.5)["category"]=="no_supported_effect"


def test_monotone_response_requires_the_intermediate_gap_between_the_other_two():
    assert classify(arm(11.),arm(11.5),CONTROL,.5)["monotone_response"]
    assert not classify(arm(11.),arm(12.5),CONTROL,.5)["monotone_response"]
    assert classify(arm(12.5),arm(12.2),CONTROL,.5)["monotone_response"]
    broken=arm(11.5);broken["scores"]["strict"]=None
    assert classify(arm(11.),broken,CONTROL,.5)["monotone_response"] is None


def test_demand_compensation_when_other_consumers_take_over():
    f=arm_flags(arm(12.,rka=0.,cons=5.4,prod=4.5),CONTROL,.5)
    assert f["demand_compensation"] and f["reductions_mM"]["RKa"]==1.
    assert not arm_flags(arm(12.,rka=0.,cons=4.7,prod=4.7),CONTROL,.5)["demand_compensation"]


def test_production_compensation_when_supply_falls_with_demand():
    assert arm_flags(arm(12.,rka=0.,cons=4.656,prod=4.0),CONTROL,.5)["production_compensation"]
    assert not arm_flags(arm(12.,rka=0.,cons=4.656,prod=4.6),CONTROL,.5)["production_compensation"]
    assert not arm_flags(arm(12.,rka=0.,cons=5.9,prod=4.0),CONTROL,.5)["production_compensation"]


def test_early_atp_rise_alone_is_flagged_and_is_not_an_improvement():
    f=arm_flags(arm(12.3,atp4=.3),CONTROL,.5)
    assert f["early_only"] and not f["improves"] and not f["absolute_J15_targets_reached"]


def test_no_class_promotes_changes_the_convention_or_launches_calibration():
    for hyp in (arm(11.),arm(12.3),arm(-1.)):
        r=classify(hyp,arm(12.),CONTROL,.5)
        assert r["working_center_retained"] and r["J1_convention_retained"]
        assert not r["production_promoted"] and not r["followup_calibration_launched"]
