import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from fla_atp_attribution import (cycle_accounts,first_below,gate_loss,pool_ledger,reading,shares,
    signed_integrals,window_mask)

PLAN=json.loads((ROOT/"config/fla_atp_attribution_2026_11_10.json").read_text())


def support(days=3,nodes=4):
    cells=np.repeat(np.arange(days),nodes)
    return np.full(days*nodes,1/nodes),cells


def test_registered_plan_is_read_only_and_uses_inherited_closure_tolerances():
    assert PLAN["new_integrations"]==0 and PLAN["primary_window"]=="J1_J4" and PLAN["gate_threshold_mM"]==1e-3
    assert not any(PLAN[k] for k in ("parameters_changed","optimization_executed","production_promotion_allowed","J46_replayed"))
    assert (PLAN["closure_atol_mM"],PLAN["closure_rtol"])==(1e-6,1e-3)


def test_window_uses_whole_day_intervals_and_rejects_empty_or_fractional_ones():
    _,cells=support()
    assert window_mask(cells,[1,3]).sum()==8 and window_mask(cells,[3,4]).sum()==4
    for bad in ([1.5,3],[3,3],[0,2],[9,10]):
        with pytest.raises(ValueError):
            window_mask(cells,bad)


def test_signed_integral_of_constant_rate_equals_rate_times_duration():
    w,cells=support()
    assert np.allclose(signed_integrals(np.array([[2.]*12,[-1.]*12]),w,cells,[1,4]),[6.,-3.])


def test_reversing_reaction_is_not_netted_away_in_gross_turnover():
    w,cells=support(days=2,nodes=2)
    rates=np.array([[1.,1.,-1.,-1.]])
    led=pool_ledger(np.array([1.]),rates,w,cells,[1,3])
    assert np.allclose([led["net"][0],led["production"][0],led["consumption"][0]],[0.,1.,1.])


def test_ledger_net_equals_production_minus_consumption_per_reaction():
    w,cells=support()
    rng=np.random.default_rng(3)
    rates=rng.normal(size=(5,12));c=np.array([1.,-1.,0.,2.,-2.])
    led=pool_ledger(c,rates,w,cells,[1,4])
    assert np.allclose(led["net"],led["production"]-led["consumption"]) and led["net"][2]==0


def test_shares_sum_to_one_and_are_zero_for_an_empty_total():
    assert np.isclose(shares([1.,3.]).sum(),1.) and np.array_equal(shares([0.,0.]),[0.,0.])


def gated():
    w,cells=support(days=1,nodes=2)
    matrix=np.array([[-1.],[1.]])
    states=np.array([[5e-4,2e-3],[1.,1.]])
    raw=np.array([[2.,2.]])
    return states,raw,matrix,w,cells


def test_gate_loss_is_raw_minus_executed_and_goes_to_the_limiting_substrate():
    states,raw,matrix,w,cells=gated()
    executed=raw*np.array([.5,1.])
    g=gate_loss(states,raw,executed,matrix,w,cells,[1,2],1e-3)
    assert np.isclose(g["lost"][0],.5) and np.isclose(g["raw"][0]-g["executed"][0],.5)
    assert np.isclose(g["lost_by_pool"][0,0],.5) and g["lost_by_pool"][1,0]==0


def test_gate_loss_refuses_executed_rates_that_are_not_the_gated_raw_rates():
    states,raw,matrix,w,cells=gated()
    with pytest.raises(ValueError,match="minimum consumer availability"):
        gate_loss(states,raw,raw*.9,matrix,w,cells,[1,2],1e-3)


def integrals(**values):
    reactions=["VAMPD1","VADSS","VADSL","VNDPK","VGMPK","VAK","VAK2","VPRPPASe","VHGPRT1","VHGPRT2","VAPRT",
               "VPGK","VPK","VHK","VPFK","VDPGM","V23DPGP"]
    return np.array([values.get(r,0.) for r in reactions]),reactions


def test_purine_cycle_throughput_is_the_minimum_leg_and_never_negative():
    v,r=integrals(VAMPD1=2.,VADSS=1.5,VADSL=1.8,VNDPK=1.9)
    c=cycle_accounts(v,r,PLAN["cycles"])
    assert c["purine_nucleotide_cycle"]["throughput_mM"]==1.5 and c["purine_nucleotide_cycle"]["GTP_cost_mM"]==1.5
    assert c["NDPK_coupling"]["net_ATP_to_GTP_mM"]==1.9 and c["NDPK_coupling"]["GTP_sinks_mM"]=={"VADSS":1.5}
    v,r=integrals(VAMPD1=2.,VADSS=-.1,VADSL=1.)
    assert cycle_accounts(v,r,PLAN["cycles"])["purine_nucleotide_cycle"]["throughput_mM"]==0.


def test_glycolytic_yield_and_bypass_share_are_undefined_without_flux():
    v,r=integrals(VPGK=3.,VPK=1.,VHK=1.,VPFK=1.,VDPGM=1.)
    c=cycle_accounts(v,r,PLAN["cycles"])
    assert c["glycolytic_yield"]["yield"]==2. and c["rapoport_luebering"]["bypass_share"]==.25
    c=cycle_accounts(*integrals(),PLAN["cycles"])
    assert c["glycolytic_yield"]["yield"] is None and c["rapoport_luebering"]["bypass_share"] is None


def test_first_below_is_support_based_and_strict():
    t=np.array([1.,2.,3.])
    assert first_below(t,np.array([1.,.5,.1]),.5)==3. and first_below(t,np.array([1.,1.,1.]),.5) is None
    with pytest.raises(ValueError):
        first_below(np.array([1.,1.]),np.array([1.,1.]),.5)


def primary(ndpk=.1,prpp=.1,y=2.,bypass=.2,lost=0.):
    gate={r:{"lost":lost,"executed":1.} for r in ("VPGK","VPK")}
    return {"ATP_consumption_share":{"VNDPK":ndpk,"VPRPPASe":prpp},"glycolytic_yield":y,"bypass_share":bypass,"gate":gate}


def test_reading_flags_can_hold_together_and_none_is_not_forced():
    th=PLAN["reading_thresholds"]
    assert reading(primary(),th)=={"NDPK_purine_cycle":False,"PRPPASe":False,"availability_gate_on_PGK_PK":False,
                                   "lower_glycolysis_supply":False,"none":True}
    r=reading(primary(ndpk=.25,prpp=.3,y=.9,lost=2.),th)
    assert all(r[k] for k in ("NDPK_purine_cycle","PRPPASe","availability_gate_on_PGK_PK","lower_glycolysis_supply")) and not r["none"]
    assert reading(primary(bypass=.6),th)["lower_glycolysis_supply"]
    assert not reading(primary(ndpk=.2499),th)["NDPK_purine_cycle"]
