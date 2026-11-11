from copy import deepcopy
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from fla_vmax_corrected_search import (check_plan,classify,controls_agree,difference_points,feasible,
    finite_differences,near_active,select)

CONFIG=ROOT/"config/fla_vmax_corrected_search_2026_11_10.json"


def plan():
    return json.loads(CONFIG.read_text())


def frozen():
    p=plan()
    temporal={k:p[k] for k in ("fit_days","critical_pointwise_pools","minimum_each_day_relative_gain","number_of_rounds",
        "difference_step_log","initial_radius_log","maximum_radius_log","reserve_fraction","line_search_fractions",
        "minimum_step_objective_gain")}
    parent={k:p[k] for k in ("threshold_mM","scipy_version","method","profiles","jacobian_minimum_step_mM")}
    parent["candidate_backend"]="joint"
    return {"temporal":temporal,"requalification_plan":parent,"numeric":{"availability_threshold_mM":1e-3},
            "design":{"groups":{f"g{i}":[f"vmax_V{i}"] for i in range(14)}}}


def row(attempt,gap,passed=True,valid=True,ratio=.9):
    return {"attempt":attempt,"valid":valid,"reserved_guards_pass":passed,"objective":ratio,
            "absolute":{"objective":gap,"target_pass":gap<=0}}


def test_registered_config_matches_the_frozen_contract_and_fits_the_budget():
    assert check_plan(plan(),frozen())==78


@pytest.mark.parametrize("key",["bounds_expanded","Km_changed","fit_based_retries","production_promotion_allowed","J46_replayed"])
def test_any_scope_opening_flag_is_refused(key):
    p=plan();p[key]=True
    with pytest.raises(ValueError,match="cannot expand"):
        check_plan(p,frozen())


@pytest.mark.parametrize("key,value",[("threshold_mM",1e-4),("scipy_version","1.16.3"),("method","BDF"),
                                       ("difference_step_log",.01),("maximum_radius_log",.5),("number_of_rounds",5)])
def test_changed_recipe_or_search_constant_is_refused(key,value):
    p=plan();p[key]=value
    with pytest.raises(ValueError):
        check_plan(p,frozen())


def test_budget_cannot_be_raised_by_adding_rounds_inside_the_same_cap():
    p,f=plan(),frozen()
    p["number_of_rounds"]=f["temporal"]["number_of_rounds"]=5
    with pytest.raises(ValueError,match="budget"):
        check_plan(p,f)


def test_futility_threshold_is_exactly_one_log_unit_below_the_center():
    p=plan();p["futility_gap_threshold"]=10.
    with pytest.raises(ValueError,match="futility"):
        check_plan(p,frozen())


def test_difference_is_reversed_only_at_the_upper_bound_and_never_leaves_the_box():
    lo,hi=np.log([.5,.1]),np.log([1.5,2.])
    x=np.array([np.log(.5),np.log(2.)])
    points=difference_points(x,lo,hi,.006)
    assert np.allclose(points-x,[[.006,0],[0,-.006]])
    assert np.all(points>=lo-1e-15) and np.all(points<=hi+1e-15)
    with pytest.raises(ValueError):
        difference_points(x+1,lo,hi,.006)


def evaluation(x,sides,guards,valid=True):
    return {"valid":valid,"log_factors":list(x),"absolute":{"sides":sides},"feasibility_guards":guards}


def test_jacobians_come_only_from_valid_actual_rows_and_freeze_missing_coordinates():
    x=np.zeros(3)
    s0,g0={"ATP:lower":9.,"ADP:lower":12.},{"point:PEP:J4":-.2}
    rows=[evaluation([.006,0,0],{"ATP:lower":9.006,"ADP:lower":11.994},{"point:PEP:J4":-.194}),
          evaluation([0,.006,0],s0,g0,valid=False),
          evaluation([0,0,-.006],{"ATP:lower":9.,"ADP:lower":12.012},{"point:PEP:J4":-.2})]
    jr,jg,good=finite_differences(x,s0,g0,rows)
    assert good==[0,2]
    assert np.allclose(jr,[[1,0,0],[-1,0,-2]]) and np.allclose(jg,[[1,0,0]])


def test_difference_row_that_moves_another_coordinate_is_refused():
    s0,g0={"ADP:lower":12.},{"g":-1.}
    with pytest.raises(ValueError,match="more than its own"):
        finite_differences(np.zeros(2),s0,g0,[evaluation([.006,.001],s0,g0),evaluation([0,.006],s0,g0)])


def test_guards_inside_the_reserve_are_reported_before_any_proposal():
    assert near_active({"a":-.5,"b":-.01,"c":.0},np.array([.1,.1,.1]))==["b","c"]


def test_control_agreement_uses_inherited_tolerances_and_reports_identity():
    a=np.array([[1.,2.],[3e-6,4.]])
    assert controls_agree(a,a,1e-5,.01)=={"pass":True,"max_difference_mM":0.,"max_tolerance_ratio":0.,"bitwise_identical":True}
    assert not controls_agree(a,a*1.05,1e-5,.01)["pass"]
    with pytest.raises(ValueError):
        controls_agree(a,np.full_like(a,np.nan),1e-5,.01)


def test_selection_ignores_better_scoring_guard_violations_and_invalid_rows():
    rows=[row(2,12.09),row(5,11.5,passed=False),row(7,11.9),row(8,11.0,valid=False),row(9,11.9)]
    assert select(rows)["attempt"]==7 and not feasible(rows[1]) and not feasible(rows[3])
    with pytest.raises(ValueError):
        select([row(1,12.,passed=False)])


def scores(gap,ratio,passed=True):
    return {p:{"reserved_guards_pass":passed,"objective":ratio,"absolute":{"objective":gap,"target_pass":gap<=0}}
            for p in ("strict","ultrastrict")}


OK={"strict":True,"ultrastrict":True}


def test_selected_center_is_no_improvement_and_triggers_the_futility_rule():
    r=classify({},False,{},True,plan(),True)
    assert r["category"]=="no_improvement" and r["working_center_retained"] and r["original_box_local_search_exhausted"]
    assert not r["production_promoted"] and not r["global_infeasibility"]


def test_small_admissible_gain_improves_the_center_but_remains_futile():
    r=classify(OK,True,scores(12.0,.93),True,plan(),False)
    assert r["category"]=="improved_center" and not r["working_center_retained"]
    assert r["original_box_local_search_exhausted"] and not r["absolute_J15_targets_reached"]


def test_more_than_one_log_unit_gain_is_not_classified_as_exhausted():
    r=classify(OK,True,scores(11.0,.9),True,plan(),False)
    assert r["category"]=="improved_center" and not r["original_box_local_search_exhausted"]


def test_worst_profile_decides_and_a_worse_dated_ratio_blocks_a_new_center():
    s=scores(12.0,.93);s["ultrastrict"]["absolute"]["objective"]=12.2
    assert classify(OK,True,s,True,plan(),False)["category"]=="no_improvement"
    assert classify(OK,True,scores(12.0,.95),True,plan(),False)["category"]=="no_improvement"


def test_absolute_target_cannot_override_guards_numerics_or_the_box():
    assert classify(OK,True,scores(-.1,.5,passed=False),True,plan(),False)["category"]=="metabolic_guard_failure"
    assert classify(OK,True,scores(-.1,.5),False,plan(),False)["category"]=="metabolic_guard_failure"
    assert classify({"strict":True,"ultrastrict":False},True,scores(-.1,.5),True,plan(),False)["category"]=="numerical_failure"
    assert classify(OK,False,scores(-.1,.5),True,plan(),False)["category"]=="numerical_failure"
    r=classify(OK,True,scores(-.1,.5),True,plan(),False)
    assert r["category"]=="absolute_target_attained" and not r["production_promoted"]


def test_log_domain_failure_is_a_metabolic_failure_that_retains_the_center():
    r=classify(OK,True,{"strict":None,"ultrastrict":None},True,plan(),False)
    assert r["category"]=="metabolic_guard_failure" and r["working_center_retained"]
    assert r["final_working_gap"]==plan()["center_worst_profile_absolute_gap"]


def test_decisions_do_not_mutate_the_registered_plan():
    p=plan();before=deepcopy(p)
    classify(OK,True,scores(12.0,.93),True,p,False);check_plan(p,frozen())
    assert p==before
