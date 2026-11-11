"""Independent receipt for the latent ribose stock diagnostic.

Does not import the diagnostic's decision module. Replays are re-verified,
scores and executed integrals recomputed by separate code, and the
classification and flags re-derived.
"""

import argparse
from pathlib import Path

import numpy as np

from run_vmax_requalification import (ROOT,check_seal,compare_replays,exact_parameters,folder_for,historical_metrics,read,
    require,seal,sha,verify_archive,verify_inputs,write)
from verify_vmax_requalification import verify_replay
from verify_vmax_corrected_search import rescore


def measure(folder,f,panel,reference):
    """Score plus J1-J4 executed RKa, gross ATP consumption and production from quadrature rates."""
    with np.load(folder/"flux_evidence.npz") as a:
        names,reactions=a["pool_names"].tolist(),a["reactions"].tolist()
        x=a["states"][np.ix_([names.index(k) for k in panel["names"]],np.searchsorted(a["time"],panel["days"]))]
        level=lambda pool,day:float(a["states"][names.index(pool),np.searchsorted(a["time"],day)])
        extra={"ATP_J4":level("ATP",4),"ATP_J15":level("ATP",15),"ADP_J15":level("ADP",15)}
        w,cells,ex=a["q8_weights"],a["q8_intervals"],a["q8_executed_rates"]
        use=cells<3
        daily=np.bincount(cells,weights=ex[reactions.index("VRKa")]*w,minlength=14)
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


def verify(out,report):
    require(not report.exists() and not report.is_relative_to(out),"fresh external receipt required")
    verify_archive(out)
    f=verify_inputs(out)
    plan=f["ribose_plan"]
    require(plan==read(ROOT/"config/fla_ribose_stock_2026_11_10.json"),"registered plan changed")
    require(not any(plan[k] for k in ("measured_J1_changed","parameters_changed","optimization_executed","followup_calibration_allowed",
                                      "production_promotion_allowed","J46_replayed")),"scope opened")
    cases,obs,summary=read(out/"cases.json"),read(out/"observations.json"),read(out/"summary.json")
    f["observations_for_verification"]=obs
    require(cases["log_factors"]==f["profile_center"] and cases["parameters"]==exact_parameters(f,f["profile_center"]),"not the retained working center")
    counts={"records":0,"quarantined":0,"daily_balances_passed":0,"daily_balances_total":0,"quadrature_values":0,"native_rate_checkpoints":0,
            "guard_values":0,"measured_J1_checked":0}
    panel,historical=historical_metrics(f,obs)
    parent=ROOT/plan["numerical_parent"]
    with np.load(parent/"controls"/plan["control_case"]/plan["backend"]/"strict"/"flux_evidence.npz") as a:
        names=a["pool_names"].tolist()
    base=np.array(f["initial"],float)
    for key,spec in plan["arms"].items():
        x=np.array(cases["arms"][key]["initial"],float)
        require([names[i] for i in np.flatnonzero(x[:len(names)]!=base[:len(names)])]==[plan["changed_pool"]]
                and np.array_equal(x[len(names):],base[len(names):]) and x[names.index(plan["changed_pool"])]==spec["RIB_mM"],
                "an initial state other than the registered ribose stock changed")
        for pool,values in obs["values"].items():
            require(x[names.index(pool)]==values[0],"measured J1 value changed")
            counts["measured_J1_checked"]+=1
    control={"scores":{},"ledger":None}
    for p in plan["profiles"]:
        folder=parent/"controls"/plan["control_case"]/plan["backend"]/p
        check_seal(folder)
        control["scores"][p],ledger=measure(folder,f,panel,historical[p])
        require(abs(control["scores"][p]["gap"]-summary["control"]["scores"][p]["gap"])<1e-12,"control score changed")
        if p=="ultrastrict":control["ledger"]=ledger
    minima,observed,budgets,arms=[],[],[],{}
    for key in plan["arms"]:
        context={**f,"initial":cases["arms"][key]["initial"]}
        case={"id":key,"role":"candidate","log_factors":cases["log_factors"],"parameters":cases["parameters"]}
        recorded=summary["arms"][key]
        arm={"numerical":{},"scores":{},"ledger":None}
        data={}
        for p in plan["profiles"]:
            folder=folder_for(out,case,plan["backend"],p)
            r,a=verify_replay(folder,context,case,plan["backend"],p,counts,minima,observed,budgets)
            require(r==recorded["statuses"][p],"replay status changed")
            arm["numerical"][p]=r["numerical_pass"];arm["scores"][p]=None
            if a is not None:
                data[p]=a
                s,ledger=measure(folder,context,panel,historical[p])
                arm["scores"][p]=s
                rec=recorded["scores"][p]
                require((s is None)==(rec is None),"observation-domain status changed")
                if s is not None:
                    require(abs(s["gap"]-rec["gap"])<1e-12 and s["admitted"]==rec["reserved_guards_pass"]
                            and s["ATP_J15"]==rec["ATP_J15"] and s["ADP_J15"]==rec["ADP_J15"],"arm score changed")
                    counts["guard_values"]+=s["guards"]
                led=recorded["details"][p]["ledger"]["J1_J4"]
                require(np.allclose([led["reactions"]["VRKa"],led["ATP_consumption_mM"],led["ATP_production_mM"]],ledger,rtol=1e-9,atol=1e-12),
                        "executed ledger changed")
                if p=="ultrastrict":arm["ledger"]=ledger
        arm["paired"]=len(data)==2 and bool(compare_replays(data["strict"],data["ultrastrict"],f["numeric"],f["threshold_plan"],panel["days"])["pass"])
        require(arm["paired"]==recorded["paired_pass"],"paired decision changed")
        arms[key]=arm
    hyp,mid=arms[plan["hypothesis_arm"]],arms[plan["monotonicity_arm"]]
    if not (all(hyp["numerical"].values()) and hyp["paired"]):category="numerical_failure"
    elif improves(hyp,control):category="ribose_stock_effect_supported"
    else:category="no_supported_effect"
    c=summary["classification"]
    require(c["category"]==category and c["working_center_retained"] and c["J1_convention_retained"]
            and not c["followup_calibration_launched"] and not c["production_promoted"],"registered classification changed")
    gaps=[None if any(s is None for s in b["scores"].values()) else max(s["gap"] for s in b["scores"].values()) for b in (control,mid,hyp)]
    monotone=None if any(g is None for g in gaps) else bool(min(gaps[0],gaps[2])<=gaps[1]<=max(gaps[0],gaps[2]))
    require(c["monotone_response"]==monotone,"monotonicity flag changed")
    flags={}
    for role,arm in (("hypothesis",hyp),("monotonicity",mid)):
        recorded=c["flags"][role]
        require(recorded["improves"]==improves(arm,control),"improvement flag changed")
        demand=production=None
        if arm["ledger"] is not None:
            d_r,d_c,d_p=(control["ledger"][i]-arm["ledger"][i] for i in range(3))
            fraction=plan["compensation_fraction"]
            demand,production=bool(d_r>0 and d_c<fraction*d_r),bool(d_c>0 and d_p>=fraction*d_c)
            require(recorded["demand_compensation"]==demand and recorded["production_compensation"]==production,"compensation flag changed")
        flags[role]={"improves":recorded["improves"],"demand_compensation":demand,"production_compensation":production}
    require(summary["new_integrations"]==counts["records"]==plan["maximum_new_integrations"],"integration count changed")
    report.mkdir(parents=True)
    receipt={"verified":True,"category":category,"monotone_response":monotone,"flags":flags,"counts":counts,
             "measured_J1_changed":False,"parameters_changed":False,"production_promoted":False,"followup_calibration_launched":False,
             "J46_replayed":False,"archive_manifest_sha256":sha(out/"manifest.json"),"verifier_sha256":sha(Path(__file__))}
    write(report/"verification.json",receipt);seal(report);check_seal(report)
    return receipt


if __name__=="__main__":
    from threadpoolctl import threadpool_limits
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--out",type=Path,required=True);p.add_argument("--report",type=Path,required=True)
    a=p.parse_args()
    with threadpool_limits(1):print(verify(a.out.resolve(),a.report.resolve()))
