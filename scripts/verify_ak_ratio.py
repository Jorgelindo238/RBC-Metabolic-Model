"""Independent receipt for the adenylate kinase ratio diagnostic.

Does not import the diagnostic's decision module. The balancing ratio and arm
capacities are re-derived from the native rate law, replays are re-verified,
scores and executed integrals recomputed by separate code, and the
classification and flags re-derived.
"""

import argparse
from pathlib import Path

import numpy as np

from run_vmax_requalification import (ROOT,check_seal,compare_replays,exact_parameters,folder_for,historical_metrics,read,
    require,rhs_for,seal,sha,verify_archive,verify_inputs,write)
from verify_vmax_requalification import verify_replay
from verify_vmax_corrected_search import rescore
from fla_reaction_threshold import threshold_context

PAIR=("vmax_VAK","vmax_VAK_rev")


def measure(folder,f,panel,reference):
    """Score plus J1-J4 executed signed AK, gross ATP consumption and production from quadrature rates."""
    with np.load(folder/"flux_evidence.npz") as a:
        names,reactions=a["pool_names"].tolist(),a["reactions"].tolist()
        x=a["states"][np.ix_([names.index(k) for k in panel["names"]],np.searchsorted(a["time"],panel["days"]))]
        level=lambda pool,day:float(a["states"][names.index(pool),np.searchsorted(a["time"],day)])
        extra={"ATP_J4":level("ATP",4),"ATP_J15":level("ATP",15),"ADP_J15":level("ADP",15)}
        w,cells,ex=a["q8_weights"],a["q8_intervals"],a["q8_executed_rates"]
        use=cells<3
        daily=np.bincount(cells,weights=ex[reactions.index("VAK")]*w,minlength=14)
        atp=a["matrix"][names.index("ATP")][:,None]*ex[:,use]
        ledger=(float(daily[:3].sum()),float(np.maximum(-atp,0).sum(axis=0)@w[use]),float(np.maximum(atp,0).sum(axis=0)@w[use]))
    if np.any(x[panel["adenylates"]]<=0):return None,ledger
    s=rescore(x,reference,panel,f)
    return {**extra,"gap":s["gap"],"admitted":s["admitted"],"guards":len(s["guards"])},ledger


def improves(arm,control):
    if not (all(arm["numerical"].values()) and arm["paired"]):return False
    if any(s is None for s in arm["scores"].values()) or not all(s["admitted"] for s in arm["scores"].values()):return False
    if not max(s["gap"] for s in arm["scores"].values())<max(s["gap"] for s in control["scores"].values()):return False
    return all(arm["scores"][p][k]>=control["scores"][p][k] for p in arm["scores"] for k in ("ATP_J15","ADP_J15"))


def native_terms(f,center):
    """Forward and reverse saturation terms of the native AK law at frozen J1, from two unit evaluations."""
    context=threshold_context(f,f["numeric"]["availability_threshold_mM"])
    state=np.array(f["initial"],float)
    def raw(forward,reverse):
        rhs=rhs_for(context,{**center,PAIR[0]:forward,PAIR[1]:reverse},f["temporal"]["network"],"full")
        return float(rhs.rates(1.,state)[0][list(rhs.reactions).index("VAK")])
    both=raw(1.,1.)
    return raw(2.,1.)-both,both-raw(1.,2.),raw


def check_arms(f,plan,cases,obs):
    """Only the two AK capacities differ from the working center, at the registered rules and inside the box."""
    center=cases["parameters"]
    a,b,raw=native_terms(f,center)
    require(a>0 and b>0,"native law lost its forward-minus-reverse form")
    ratio=b/a
    require(abs(ratio/plan["expected_balance_ratio"]-1)<=plan["expected_relative_tolerance"] and abs(ratio/cases["balance_ratio"]-1)<=1e-12,
            "balancing ratio changed")
    low,high=f["design"]["factor_bounds"][plan["bound_group"]]
    base=[f["parameters"][k] for k in PAIR]
    checked=0
    for key,spec in plan["arms"].items():
        p=cases["arms"][key]["parameters"]
        require(set(p)==set(center) and {k for k in p if p[k]!=center[k]}<=set(PAIR),"a parameter other than the two AK capacities changed")
        require(not any(k.startswith("km_") and p[k]!=center[k] for k in p),"an affinity changed")
        forward,reverse=p[PAIR[0]],p[PAIR[1]]
        want_reverse=center[PAIR[1]] if spec["reverse"]=="center" else base[1]*high
        want_ratio=ratio if spec["ratio"]=="balance" else float(np.sqrt(ratio*center[PAIR[0]]/center[PAIR[1]]))
        require(np.isclose(reverse,want_reverse,rtol=1e-12,atol=0) and np.isclose(forward/reverse,want_ratio,rtol=1e-12,atol=0),"arm differs from its registered rule")
        require(all(low-1e-12<=v/b0<=high+1e-12 for v,b0 in zip((forward,reverse),base)),"arm leaves the registered capacity box")
        if spec["ratio"]=="balance":
            require(abs(raw(forward,reverse))<=plan["zero_flux_abs_tolerance"],"balanced arm does not zero the native law at frozen J1")
        checked+=1
    names=None
    with np.load(ROOT/plan["numerical_parent"]/"controls"/plan["control_case"]/plan["backend"]/"strict"/"flux_evidence.npz") as archive:
        names=archive["pool_names"].tolist()
    measured=0
    for pool,values in obs["values"].items():
        require(f["initial"][names.index(pool)]==values[0],"measured J1 value changed")
        measured+=1
    return checked,measured


def verify(out,report):
    require(not report.exists() and not report.is_relative_to(out),"fresh external receipt required")
    verify_archive(out)
    f=verify_inputs(out)
    plan=f["ak_ratio_plan"]
    require(plan==read(ROOT/"config/fla_ak_ratio_2026_11_11.json"),"registered plan changed")
    require(not any(plan[k] for k in ("measured_J1_changed","initial_state_changed","km_changed","bounds_changed","optimization_executed",
                                      "followup_calibration_allowed","production_promotion_allowed","J46_replayed")),"scope opened")
    cases,obs,summary=read(out/"cases.json"),read(out/"observations.json"),read(out/"summary.json")
    f["observations_for_verification"]=obs
    require(cases["log_factors"]==f["profile_center"] and cases["parameters"]==exact_parameters(f,f["profile_center"]),"not the retained working center")
    counts={"records":0,"quarantined":0,"daily_balances_passed":0,"daily_balances_total":0,"quadrature_values":0,"native_rate_checkpoints":0,
            "guard_values":0,"measured_J1_checked":0,"arm_vectors_checked":0}
    counts["arm_vectors_checked"],counts["measured_J1_checked"]=check_arms(f,plan,cases,obs)
    panel,historical=historical_metrics(f,obs)
    parent=ROOT/plan["numerical_parent"]
    control={"scores":{},"ledger":None}
    for p in plan["profiles"]:
        folder=parent/"controls"/plan["control_case"]/plan["backend"]/p
        check_seal(folder)
        control["scores"][p],ledger=measure(folder,f,panel,historical[p])
        require(abs(control["scores"][p]["gap"]-summary["control"]["scores"][p]["gap"])<1e-12,"control score changed")
        if p=="ultrastrict":control["ledger"]=ledger
    minima,observed,budgets,arms=[],[],[],{}
    for key in plan["arms"]:
        case={"id":key,"role":"candidate","log_factors":[0.]*len(f["design"]["groups"]),"parameters":cases["arms"][key]["parameters"]}
        recorded=summary["arms"][key]
        arm={"numerical":{},"scores":{},"ledger":None}
        data={}
        for p in plan["profiles"]:
            folder=folder_for(out,case,plan["backend"],p)
            r,a=verify_replay(folder,f,case,plan["backend"],p,counts,minima,observed,budgets)
            require(r==recorded["statuses"][p],"replay status changed")
            arm["numerical"][p]=r["numerical_pass"];arm["scores"][p]=None
            if a is not None:
                data[p]=a
                s,ledger=measure(folder,f,panel,historical[p])
                arm["scores"][p]=s
                rec=recorded["scores"][p]
                require((s is None)==(rec is None),"observation-domain status changed")
                if s is not None:
                    require(abs(s["gap"]-rec["gap"])<1e-12 and s["admitted"]==rec["reserved_guards_pass"]
                            and s["ATP_J15"]==rec["ATP_J15"] and s["ADP_J15"]==rec["ADP_J15"],"arm score changed")
                    counts["guard_values"]+=s["guards"]
                led=recorded["details"][p]["ledger"]["J1_J4"]
                require(np.allclose([led["reactions"]["VAK"],led["ATP_consumption_mM"],led["ATP_production_mM"]],ledger,rtol=1e-9,atol=1e-12),
                        "executed ledger changed")
                if p=="ultrastrict":arm["ledger"]=ledger
        arm["paired"]=len(data)==2 and bool(compare_replays(data["strict"],data["ultrastrict"],f["numeric"],f["threshold_plan"],panel["days"])["pass"])
        require(arm["paired"]==recorded["paired_pass"],"paired decision changed")
        arms[key]=arm
    hyp,cap,mid=(arms[plan[k]] for k in ("hypothesis_arm","capacity_arm","monotonicity_arm"))
    if not (all(hyp["numerical"].values()) and hyp["paired"]):category="numerical_failure"
    elif improves(hyp,control):category="ak_ratio_effect_supported"
    elif improves(cap,control):category="capacity_dependent_effect_only"
    else:category="no_supported_effect"
    c=summary["classification"]
    require(c["category"]==category and c["working_center_retained"] and c["grouped_search_design_retained"]
            and not c["followup_calibration_launched"] and not c["production_promoted"],"registered classification changed")
    gaps=[None if any(s is None for s in b["scores"].values()) else max(s["gap"] for s in b["scores"].values()) for b in (control,mid,hyp)]
    monotone=None if any(g is None for g in gaps) else bool(min(gaps[0],gaps[2])<=gaps[1]<=max(gaps[0],gaps[2]))
    require(c["monotone_response"]==monotone,"monotonicity flag changed")
    flags={}
    for role,arm in (("hypothesis",hyp),("capacity",cap),("monotonicity",mid)):
        recorded=c["flags"][role]
        require(recorded["improves"]==improves(arm,control),"improvement flag changed")
        reduced=compensation=None
        if arm["ledger"] is not None:
            d_ak,d_c,d_p=(control["ledger"][i]-arm["ledger"][i] for i in range(3))
            reduced,compensation=bool(d_ak>0),bool(d_ak>0 and d_c>=plan["compensation_fraction"]*d_ak)
            require(recorded["ak_flux_reduced"]==reduced and recorded["consumption_compensation"]==compensation
                    and np.isclose(recorded["net_ATP_change_mM"],d_c-d_p,rtol=1e-9,atol=1e-12),"ledger flag changed")
        flags[role]={"improves":recorded["improves"],"ak_flux_reduced":reduced,"consumption_compensation":compensation}
    require(summary["new_integrations"]==counts["records"]==plan["maximum_new_integrations"],"integration count changed")
    report.mkdir(parents=True)
    receipt={"verified":True,"category":category,"monotone_response":monotone,"flags":flags,"counts":counts,
             "measured_J1_changed":False,"initial_state_changed":False,"km_changed":False,"bounds_changed":False,"production_promoted":False,
             "followup_calibration_launched":False,"J46_replayed":False,"archive_manifest_sha256":sha(out/"manifest.json"),
             "verifier_sha256":sha(Path(__file__))}
    write(report/"verification.json",receipt);seal(report);check_seal(report)
    return receipt


if __name__=="__main__":
    from threadpoolctl import threadpool_limits
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--out",type=Path,required=True);p.add_argument("--report",type=Path,required=True)
    a=p.parse_args()
    with threadpool_limits(1):print(verify(a.out.resolve(),a.report.resolve()))
