"""Independent receipt for the adenylate kinase ratio x PEP phosphatase diagnostic.

Does not import the diagnostic's decision modules. Arm capacities are
re-derived from the sealed evidence and the native rate law, replays are
re-verified, scores and executed integrals recomputed by separate code, and
the classification and flags re-derived.
"""

import argparse
from pathlib import Path

import numpy as np

from run_vmax_requalification import (ROOT,check_seal,compare_replays,exact_parameters,folder_for,historical_metrics,read,
    require,rhs_for,seal,sha,verify_archive,verify_inputs,write)
from verify_vmax_requalification import verify_replay
from verify_vmax_corrected_search import rescore
from fla_reaction_threshold import threshold_context

AK=("vmax_VAK","vmax_VAK_rev")
PEPASE="vmax_VPEP_PASE"


def measure(folder,f,panel,reference):
    """Score plus executed PK, PEP phosphatase and gross ATP turnover from quadrature rates."""
    with np.load(folder/"flux_evidence.npz") as a:
        names,reactions=a["pool_names"].tolist(),a["reactions"].tolist()
        x=a["states"][np.ix_([names.index(k) for k in panel["names"]],np.searchsorted(a["time"],panel["days"]))]
        level=lambda pool,day:float(a["states"][names.index(pool),np.searchsorted(a["time"],day)])
        extra={"ATP_J4":level("ATP",4),"ATP_J15":level("ATP",15),"ADP_J15":level("ADP",15)}
        w,cells,ex=a["q8_weights"],a["q8_intervals"],a["q8_executed_rates"]
        use=cells<3
        daily=lambda r:np.bincount(cells,weights=ex[reactions.index(r)]*w,minlength=14)
        pk,pepase=daily("VPK"),daily("VPEP_PASE")
        atp=a["matrix"][names.index("ATP")][:,None]*ex[:,use]
        ledger={"PK_J1_J4":float(pk[:3].sum()),"PEPASE_J1_J4":float(pepase[:3].sum()),"PK_J1_J15":float(pk.sum()),"PEPASE_J1_J15":float(pepase.sum()),
                "ATP_consumption":float(np.maximum(-atp,0).sum(axis=0)@w[use]),"ATP_production":float(np.maximum(atp,0).sum(axis=0)@w[use])}
    if np.any(x[panel["adenylates"]]<=0):return None,ledger
    s=rescore(x,reference,panel,f)
    return {**extra,"gap":s["gap"],"admitted":s["admitted"],"guards":len(s["guards"])},ledger


def gap(block):
    return None if any(s is None for s in block["scores"].values()) else max(s["gap"] for s in block["scores"].values())


def not_lower(arm,reference):
    return all(arm["scores"][p][k]>=reference["scores"][p][k] for p in arm["scores"] for k in ("ATP_J15","ADP_J15"))


def improves(arm,control):
    if not (all(arm["numerical"].values()) and arm["paired"]):return False
    if gap(arm) is None or not all(s["admitted"] for s in arm["scores"].values()):return False
    return bool(gap(arm)<gap(control) and not_lower(arm,control))


def share(ledger,window):
    total=ledger["PK_"+window]+ledger["PEPASE_"+window]
    return ledger["PK_"+window]/total if total>0 else None


def check_arms(f,plan,cases,obs):
    """Only the three registered capacities differ from the working center, at the registered rules and inside the box."""
    center=cases["parameters"]
    spec=plan["sealed_ak_arm"]
    sealed=read(ROOT/spec["archive"]/"cases.json")["arms"][spec["case"]]["parameters"]
    require({k for k in sealed if sealed[k]!=center[k]}=={AK[0]},"sealed AK arm differs from the working center elsewhere")
    context=threshold_context(f,f["numeric"]["availability_threshold_mM"])
    state=np.array(f["initial"],float)
    def raw(forward,reverse):
        rhs=rhs_for(context,{**center,AK[0]:forward,AK[1]:reverse},f["temporal"]["network"],"full")
        return float(rhs.rates(1.,state)[0][list(rhs.reactions).index("VAK")])
    both=raw(1.,1.)
    ratio=(both-raw(1.,2.))/(raw(2.,1.)-both)
    require(abs(ratio/plan["expected_balance_ratio"]-1)<=plan["expected_relative_tolerance"]
            and abs(sealed[AK[0]]/sealed[AK[1]]/ratio-1)<=plan["expected_relative_tolerance"],"sealed AK arm is not at the balancing ratio")
    low,high=f["design"]["factor_bounds"]["PEPase"]
    base=f["parameters"][PEPASE]
    checked=0
    for key,rule in plan["arms"].items():
        p=cases["arms"][key]["parameters"]
        require(set(p)==set(center) and {k for k in p if p[k]!=center[k]}<={*AK,PEPASE},"a parameter outside the three registered capacities changed")
        require(not any(k.startswith("km_") and p[k]!=center[k] for k in p),"an affinity changed")
        source=center if rule["ak"]=="center" else sealed
        require(p[AK[0]]==source[AK[0]] and p[AK[1]]==source[AK[1]],"AK capacities differ from their registered source")
        want=base*low if rule["pepase"]=="lower_bound" else float(np.sqrt(center[PEPASE]*base*low))
        require(np.isclose(p[PEPASE],want,rtol=1e-12,atol=0) and low-1e-12<=p[PEPASE]/base<=high+1e-12,"PEP phosphatase capacity differs from its registered rule or leaves the box")
        checked+=1
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
    plan=f["ak_pepase_plan"]
    require(plan==read(ROOT/"config/fla_ak_pepase_2026_11_11.json"),"registered plan changed")
    require(not any(plan[k] for k in ("measured_J1_changed","initial_state_changed","km_changed","bounds_changed","optimization_executed",
                                      "followup_calibration_allowed","production_promotion_allowed","J46_replayed")),"scope opened")
    cases,obs,summary=read(out/"cases.json"),read(out/"observations.json"),read(out/"summary.json")
    f["observations_for_verification"]=obs
    require(cases["log_factors"]==f["profile_center"] and cases["parameters"]==exact_parameters(f,f["profile_center"]),"not the retained working center")
    counts={"records":0,"quarantined":0,"daily_balances_passed":0,"daily_balances_total":0,"quadrature_values":0,"native_rate_checkpoints":0,
            "guard_values":0,"measured_J1_checked":0,"arm_vectors_checked":0}
    counts["arm_vectors_checked"],counts["measured_J1_checked"]=check_arms(f,plan,cases,obs)
    panel,historical=historical_metrics(f,obs)
    ak=plan["sealed_ak_arm"]
    folders={"control":{p:ROOT/plan["numerical_parent"]/"controls"/plan["control_case"]/plan["backend"]/p for p in plan["profiles"]},
             "ak_only":{p:folder_for(ROOT/ak["archive"],{"id":ak["case"],"role":"candidate"},plan["backend"],p) for p in plan["profiles"]}}
    sealed={}
    for name,by_profile in folders.items():
        block={"scores":{},"ledger":None}
        for p,folder in by_profile.items():
            check_seal(folder)
            block["scores"][p],ledger=measure(folder,f,panel,historical[p])
            require(abs(block["scores"][p]["gap"]-summary[name]["scores"][p]["gap"])<1e-12,"sealed reference score changed")
            if p=="ultrastrict":block["ledger"]=ledger
        sealed[name]=block
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
                led=recorded["details"][p]["ledger"]
                require(np.allclose([led["J1_J4"]["reactions"]["VPK"],led["J1_J4"]["reactions"]["VPEP_PASE"],
                                     sum(led[w]["reactions"]["VPK"] for w in led),sum(led[w]["reactions"]["VPEP_PASE"] for w in led),
                                     led["J1_J4"]["ATP_consumption_mM"],led["J1_J4"]["ATP_production_mM"]],
                                    [ledger[k] for k in ("PK_J1_J4","PEPASE_J1_J4","PK_J1_J15","PEPASE_J1_J15","ATP_consumption","ATP_production")],
                                    rtol=1e-9,atol=1e-12),"executed ledger changed")
                if p=="ultrastrict":arm["ledger"]=ledger
        arm["paired"]=len(data)==2 and bool(compare_replays(data["strict"],data["ultrastrict"],f["numeric"],f["threshold_plan"],panel["days"])["pass"])
        require(arm["paired"]==recorded["paired_pass"],"paired decision changed")
        arms[key]=arm
    hyp,single,mid=(arms[plan[k]] for k in ("hypothesis_arm","single_factor_arm","monotonicity_arm"))
    if not (all(hyp["numerical"].values()) and hyp["paired"]):category="numerical_failure"
    elif improves(hyp,sealed["control"]):category="combined_effect_supported"
    elif improves(single,sealed["control"]):category="pepase_alone_effect_only"
    else:category="no_supported_effect"
    c=summary["classification"]
    require(c["category"]==category and c["working_center_retained"] and c["grouped_search_design_retained"]
            and not c["followup_calibration_launched"] and not c["production_promoted"],"registered classification changed")
    gaps=[gap(b) for b in (sealed["ak_only"],mid,hyp)]
    monotone=None if any(g is None for g in gaps) else bool(min(gaps[0],gaps[2])<=gaps[1]<=max(gaps[0],gaps[2]))
    require(c["monotone_response"]==monotone,"monotonicity flag changed")
    flags={}
    for role,arm,reference in (("hypothesis",hyp,sealed["ak_only"]),("single_factor",single,sealed["control"]),("monotonicity",mid,sealed["ak_only"])):
        recorded=c["flags"][role]
        better=bool(gap(arm) is not None and gap(arm)<gap(reference) and not_lower(arm,reference))
        require(recorded["improves"]==improves(arm,sealed["control"]) and recorded["beyond_reference"]==better,"improvement flag changed")
        raised=None
        if arm["ledger"] is not None:
            now,before=share(arm["ledger"],"J1_J15"),share(reference["ledger"],"J1_J15")
            raised=bool(now is not None and before is not None and now>before)
            net=(arm["ledger"]["ATP_production"]-arm["ledger"]["ATP_consumption"])-(sealed["control"]["ledger"]["ATP_production"]-sealed["control"]["ledger"]["ATP_consumption"])
            require(recorded["pk_share_raised"]==raised and np.isclose(recorded["pk_share_J1_J15"],now,rtol=1e-9,atol=1e-12)
                    and np.isclose(recorded["pk_share_J1_J4"],share(arm["ledger"],"J1_J4"),rtol=1e-9,atol=1e-12)
                    and np.isclose(recorded["net_ATP_change_mM"],net,rtol=1e-9,atol=1e-12),"ledger flag changed")
        flags[role]={"improves":recorded["improves"],"beyond_reference":better,"pk_share_raised":raised}
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
