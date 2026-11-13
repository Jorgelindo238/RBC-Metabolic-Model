from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from fla_ak_arm_attribution import check_plan,contrast

PLAN=json.loads((ROOT/"config/fla_ak_arm_attribution_2026_11_11.json").read_text())
OLD=json.loads((ROOT/"config/fla_atp_attribution_2026_11_10.json").read_text())


def test_registered_plan_is_read_only_and_contrasts_the_hypothesis_arm_with_the_sealed_control():
    check_plan(PLAN)
    assert PLAN["new_integrations"]==0 and PLAN["primary_case"]=="balanced_forward_lowered" and PLAN["control_case"]=="control"
    assert PLAN["cases"]["control"]["folder"]=="output/vmax_requalification_2026_11_09/controls/working_center"
    assert {c["backend"] for c in PLAN["cases"].values()}=={"joint"} and len(PLAN["cases"])==4


def test_windows_thresholds_cycles_and_tolerances_are_inherited_unchanged_from_the_first_attribution():
    for key in ("windows","primary_window","profiles","primary_profile","gate_threshold_mM","gate_tabulated_reactions","cycles",
                "reading_thresholds","closure_atol_mM","closure_rtol","lumped_pools","daily_resolution"):
        assert PLAN[key]==OLD[key]
    assert set(OLD["ledger_pools"])<=set(PLAN["ledger_pools"])


@pytest.mark.parametrize("key",["parameters_changed","optimization_executed","production_promotion_allowed","J46_replayed"])
def test_any_scope_opening_flag_is_refused(key):
    p=deepcopy(PLAN);p[key]=True
    with pytest.raises(ValueError):
        check_plan(p)


def test_integration_unsealed_case_mixed_backend_or_unknown_contrast_pool_is_refused():
    for change in (lambda p:p.update(new_integrations=1),
                   lambda p:p.update(primary_case="control"),
                   lambda p:p.update(control_case="missing"),
                   lambda p:p["cases"]["control"].update(backend="full"),
                   lambda p:p["cases"]["control"].update(folder="output/somewhere_else/controls/working_center"),
                   lambda p:p.update(primary_window="J1_J2"),
                   lambda p:p.update(contrast_pools=["ATP","LAC"])):
        p=deepcopy(PLAN);change(p)
        with pytest.raises(ValueError):
            check_plan(p)


def entry(net,production,consumption):
    return {"net":net,"production":production,"consumption":consumption}


def test_contrast_is_arm_minus_control_sorted_by_absolute_net_change():
    control={"VAK":entry(1.1,1.1,0.),"VNDPK":entry(-1.9,0.,1.9),"VPGK":entry(2.7,2.7,0.)}
    arm={"VAK":entry(.1,.3,.2),"VNDPK":entry(-1.4,0.,1.4),"VPGK":entry(3.,3.,0.)}
    rows=contrast(arm,control)
    assert [r["reaction"] for r in rows]==["VAK","VNDPK","VPGK"]
    assert rows[0]["d_net"]==pytest.approx(-1.) and rows[0]["d_production"]==pytest.approx(-.8) and rows[0]["d_consumption"]==pytest.approx(.2)
    assert rows[1]["d_net"]==pytest.approx(.5) and rows[1]["control_consumption"]==1.9 and rows[1]["arm_consumption"]==1.4
    assert sum(r["d_net"] for r in rows)==pytest.approx(sum(v["net"] for v in arm.values())-sum(v["net"] for v in control.values()))


def test_contrast_refuses_ledgers_over_different_reactions():
    with pytest.raises(ValueError):
        contrast({"VAK":entry(0,0,0)},{"VAK":entry(0,0,0),"VPK":entry(0,0,0)})
