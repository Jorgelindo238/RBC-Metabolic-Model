"""Independent receipt for the latent guanylate partition diagnostic.

Does not import the diagnostic's decision module. Zeros are re-evaluated on
both right-hand sides, replays are re-verified, scores and executed integrals
are recomputed by separate code, and the classification is re-derived.
"""

import argparse
from pathlib import Path

import numpy as np

from run_vmax_requalification import (ROOT,check_seal,compare_replays,exact_parameters,folder_for,historical_metrics,read,
    require,rhs_for,seal,sha,verify_archive,verify_inputs,write)
from fla_reaction_threshold import threshold_context
from verify_vmax_requalification import verify_replay
from verify_vmax_corrected_search import rescore


def window_values(a,plan,label):
    lo,hi=(int(v)-1 for v in plan["windows"][label])
    names,reactions=a["pool_names"].tolist(),a["reactions"].tolist()
    w,cells,ex=a["q8_weights"],a["q8_intervals"],a["q8_executed_rates"]
    daily=np.array([np.bincount(cells,weights=v*w,minlength=14) for v in ex])
    use=(cells>=lo)&(cells<hi)
    atp=a["matrix"][names.index("ATP")][:,None]*ex[:,use]
    return daily[reactions.index("VNDPK"),lo:hi].sum(),float(np.maximum(-atp,0).sum(axis=0)@w[use])


def score_of(folder,f,panel,reference):
    with np.load(folder/"flux_evidence.npz") as a:
        names=a["pool_names"].tolist()
        x=a["states"][np.ix_([names.index(k) for k in panel["names"]],np.searchsorted(a["time"],panel["days"]))]
        level=lambda pool,day:float(a["states"][names.index(pool),np.searchsorted(a["time"],day)])
        extra={"ATP_J4":level("ATP",4),"ATP_J15":level("ATP",15),"ADP_J15":level("ADP",15)}
        ndpk,consumption=window_values(a,f["guanylate_plan"],"J1_J4")
    if np.any(x[panel["adenylates"]]<=0):return None,ndpk,consumption
    s=rescore(x,reference,panel,f)
    return {**extra,"gap":s["gap"],"admitted":s["admitted"],"guards":len(s["guards"])},ndpk,consumption


def improves(arm,control):
    if not (all(arm["numerical"].values()) and arm["paired"]):return False
    if any(s is None for s in arm["scores"].values()) or not all(s["admitted"] for s in arm["scores"].values()):return False
    if not max(s["gap"] for s in arm["scores"].values())<max(s["gap"] for s in control["scores"].values()):return False
    return all(arm["scores"][p][k]>=control["scores"][p][k] for p in arm["scores"] for k in ("ATP_J15","ADP_J15"))


def verify(out,report):
    require(not report.exists() and not report.is_relative_to(out),"fresh external receipt required")
    verify_archive(out)
    f=verify_inputs(out)
    plan=f["guanylate_plan"]
    require(plan==read(ROOT/"config/fla_guanylate_partition_2026_11_10.json"),"registered plan changed")
    require(not any(plan[k] for k in ("measured_J1_changed","parameters_changed","optimization_executed","followup_calibration_allowed",
                                      "production_promotion_allowed","J46_replayed")),"scope opened")
    cases,obs,summary=read(out/"cases.json"),read(out/"observations.json"),read(out/"summary.json")
    f["observations_for_verification"]=obs
    require(cases["log_factors"]==f["profile_center"] and cases["parameters"]==exact_parameters(f,f["profile_center"]),"not the retained working center")
    local=threshold_context(f,f["numeric"]["availability_threshold_mM"])
    base=np.array(f["initial"],float)
    counts={"records":0,"quarantined":0,"daily_balances_passed":0,"daily_balances_total":0,"quadrature_values":0,"native_rate_checkpoints":0,
            "zero_flux_checks":0,"guard_values":0,"measured_J1_checked":0}
    for backend in ("full",plan["backend"]):
        rhs=rhs_for(local,cases["parameters"],f["temporal"]["network"],backend)
        names,j=list(rhs.names),list(rhs.reactions).index(plan["zero_flux_reaction"])
        for key,spec in plan["arms"].items():
            arm=cases["arms"][key]
            x=np.array(arm["initial"],float)
            changed={names[i] for i in np.flatnonzero(x[:len(names)]!=base[:len(names)])}
            require(changed=={"GDP","GTP"} and np.array_equal(x[len(names):],base[len(names):]),"an initial state other than GDP/GTP changed")
            gdp,gtp=x[names.index("GDP")],x[names.index("GTP")]
            value=gdp+gtp if spec["convention"]=="GDP_plus_GTP" else gdp+2*gtp
            require(gdp>0 and gtp>0 and abs(value-spec["value_mM"])<1e-12,"declared second convention not satisfied")
            require(abs(rhs.rates(1.,x)[0][j])<=plan["zero_flux_abs_tolerance"],"registered zero is not a zero of the executable law")
            require(abs(arm["delta_E_G_mM"]-(gdp+2*gtp-3.))<1e-12 and abs(arm["total_mM"]-(gdp+gtp))<1e-12,"declared inventory changed")
            counts["zero_flux_checks"]+=1
        for pool,values in obs["values"].items():
            for arm in cases["arms"].values():
                if "initial" in arm:
                    require(arm["initial"][names.index(pool)]==values[0],"measured J1 value changed")
                    counts["measured_J1_checked"]+=1
    panel,historical=historical_metrics(f,obs)
    parent=ROOT/plan["numerical_parent"]
    control={"scores":{},"ledger":None}
    for p in plan["profiles"]:
        folder=parent/"controls"/plan["control_case"]/plan["backend"]/p
        check_seal(folder)
        control["scores"][p],ndpk,consumption=score_of(folder,f,panel,historical[p])
        require(abs(control["scores"][p]["gap"]-summary["control"]["scores"][p]["gap"])<1e-12,"control score changed")
        if p=="ultrastrict":control["ledger"]=(ndpk,consumption)
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
            arm["numerical"][p]=r["numerical_pass"]
            arm["scores"][p]=None
            if a is not None:
                data[p]=a
                s,ndpk,consumption=score_of(folder,context,panel,historical[p])
                arm["scores"][p]=s
                rec=recorded["scores"][p]
                require((s is None)==(rec is None),"observation-domain status changed")
                if s is not None:
                    require(abs(s["gap"]-rec["gap"])<1e-12 and s["admitted"]==rec["reserved_guards_pass"]
                            and s["ATP_J15"]==rec["ATP_J15"] and s["ADP_J15"]==rec["ADP_J15"],"arm score changed")
                    counts["guard_values"]+=s["guards"]
                led=recorded["details"][p]["ledger"]["J1_J4"]
                require(np.isclose(led["reactions"]["VNDPK"],ndpk,rtol=1e-9,atol=1e-12) and np.isclose(led["ATP_consumption_mM"],consumption,rtol=1e-9,atol=1e-12),
                        "executed ledger changed")
                if p=="ultrastrict":arm["ledger"]=(ndpk,consumption)
        arm["paired"]=len(data)==2 and bool(compare_replays(data["strict"],data["ultrastrict"],f["numeric"],f["threshold_plan"],panel["days"])["pass"])
        require(arm["paired"]==recorded["paired_pass"],"paired decision changed")
        arms[key]=arm
    hyp,inv=arms[plan["hypothesis_arm"]],arms[plan["inventory_arm"]]
    if not (all(hyp["numerical"].values()) and hyp["paired"]):category="numerical_failure"
    elif improves(hyp,control):category="partition_effect_supported"
    elif improves(inv,control):category="inventory_effect_only"
    else:category="no_supported_effect"
    c=summary["classification"]
    require(c["category"]==category and c["working_center_retained"] and c["J1_convention_retained"]
            and not c["followup_calibration_launched"] and not c["production_promoted"],"registered classification changed")
    flags={}
    for role,arm in (("hypothesis",hyp),("inventory",inv)):
        recorded=c["flags"][role]
        good=improves(arm,control)
        require(recorded["improves"]==good,"improvement flag changed")
        comp=None
        if arm["ledger"] is not None:
            d_ndpk,d_cons=control["ledger"][0]-arm["ledger"][0],control["ledger"][1]-arm["ledger"][1]
            comp=bool(d_ndpk>0 and d_cons<plan["compensation_fraction"]*d_ndpk)
            require(recorded["compensation"]["flag"]==comp,"compensation flag changed")
        flags[role]={"improves":good,"compensation":comp}
    require(summary["new_integrations"]==counts["records"]==plan["maximum_new_integrations"],"integration count changed")
    report.mkdir(parents=True)
    receipt={"verified":True,"category":category,"flags":flags,"counts":counts,"measured_J1_changed":False,"parameters_changed":False,
             "production_promoted":False,"followup_calibration_launched":False,"J46_replayed":False,
             "archive_manifest_sha256":sha(out/"manifest.json"),"verifier_sha256":sha(Path(__file__))}
    write(report/"verification.json",receipt);seal(report);check_seal(report)
    return receipt


if __name__=="__main__":
    from threadpoolctl import threadpool_limits
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--out",type=Path,required=True);p.add_argument("--report",type=Path,required=True)
    a=p.parse_args()
    with threadpool_limits(1):print(verify(a.out.resolve(),a.report.resolve()))
