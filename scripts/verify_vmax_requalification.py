"""Independent stage certificates and classifications for literal Vmax replays."""

import argparse
from collections import Counter
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

from run_vmax_requalification import (check_seal,control_decision,exact_parameters,folder_for,historical_metrics,
    read,require,rhs_for,seal,sha,verify_archive,verify_inputs,write,write_csv)
from fla_reaction_threshold import compare_replays,threshold_context
from fla_vmax_requalification import rejected_registry,within_original_box,classify_candidate
from verify_recorded_integrations import check_saved_supports
from verify_absolute_vmax import reconstruct
from fla_pgk_ndpk_profile import executed_ledger


def verify_registry(out,f,cases):
    plan=f["requalification_plan"]
    sources=[]
    for spec in plan["sources"]:
        # Source paths are rooted in the same repository, not in the output folder.
        from run_pgk_ndpk_profile import ROOT
        archive=ROOT/spec["archive"]
        verify_archive(archive);verify_inputs(archive)
        import json
        sources.append((spec["id"],[json.loads(s) for s in (archive/spec["trace"]).read_text().splitlines()]))
    require(rejected_registry(f,sources,plan["maximum_candidates"])==cases["candidates"],"registry did not preserve the literal rejected rows")
    for case in cases["controls"]+cases["candidates"]:
        require(exact_parameters(f,case["log_factors"])==case["parameters"],"exported vector or kinetic constants changed")
        require(within_original_box(f,case["log_factors"]),"out-of-box proposal introduced")


def verify_replay(folder,f,case,backend,profile,counts,minima,observed,budgets):
    check_seal(folder)
    r,d=read(folder/"result.json"),read(folder/"diagnostics.json")
    plan=f["requalification_plan"]
    require(r["case"]==case["id"] and r["backend"]==backend and r["profile"]==profile and r["threshold_mM"]==plan["threshold_mM"],"case/profile/threshold mismatch")
    require(r["solver_settings"]==plan["profiles"][profile] and d["method"]==plan["method"] and d["scipy_version"]==plan["scipy_version"],"uncertified numerical recipe")
    require(d["negative_tolerance_mM"]==f["numeric"]["negative_tolerance_mM"],"negative tolerance relaxed")
    jac=d["bounded_jacobian"]
    require(jac["minimum_step_mM"]==plan["jacobian_minimum_step_mM"][profile] and jac["largest_requested_step_mM"]<=jac["maximum_step_mM"] and not jac["states_clipped"],"finite-difference recipe changed")
    local=threshold_context(f,plan["threshold_mM"])
    native=rhs_for(local,case["parameters"],f["temporal"]["network"],"full")
    compiled=rhs_for(local,case["parameters"],f["temporal"]["network"],"joint")
    with np.load(folder/"trajectory_evidence.npz") as a:
        require(np.array_equal(a["initial"],f["initial"]),"J1 changed")
        summaries,gate=check_saved_supports(a,d,a["pool_names"].tolist(),f["numeric"]["negative_tolerance_mM"])
        require(gate==r["concentration_pass"]==d["concentration_gate_pass"],"concentration gate changed")
        for support,s in summaries.items():
            for p in s["per_species"]:
                minima.append([case["id"],backend,profile,support,p["pool"],p["minimum_mM"],p["minimum_day"],p["below_policy_count"],p["nonfinite_count"]])
        if "time" in a and "states" in a:
            names=a["pool_names"].tolist()
            for pool,values in f["observations_for_verification"]["values"].items():
                for day in f["temporal"]["fit_days"]:
                    j=np.searchsorted(a["time"],day)
                    if j<len(a["time"]) and a["time"][j]==day:
                        observed.append([case["id"],backend,profile,r["numerical_pass"],pool,day,values[f["observations_for_verification"]["time"].index(day)],float(a["states"][names.index(pool),j])])
    counts["records"]+=1
    if not gate:
        require(not (folder/"flux_evidence.npz").exists() and not r["numerical_pass"],"rejected states admitted")
        counts["quarantined"]+=1
        return r,None
    if not (folder/"flux_evidence.npz").exists():
        require(not r["numerical_pass"] and (folder/"failure.json").exists(),"missing flux audit unexplained")
        return r,None
    stats=read(folder/"flux_checks.json")
    with np.load(folder/"flux_evidence.npz") as a:
        require(np.array_equal(a["matrix"],native.matrix) and np.array_equal(a["accepted_states"][:,0],f["initial"]),"matrix or J1 changed")
        for order in (4,8):
            for kind in ("raw","executed"):
                integral=np.array([np.bincount(a[f"q{order}_intervals"],weights=v*a[f"q{order}_weights"],minlength=14) for v in a[f"q{order}_{kind}_rates"]])
                require(np.allclose(integral,a[kind+str(order)],rtol=1e-12,atol=1e-12),"quadrature reconstruction failed")
                counts["quadrature_values"]+=integral.size
        ids=np.searchsorted(a["time"],a["boundaries"])
        delta=np.diff(a["states"][:113,ids],axis=1)
        executed=native.matrix@a["executed8"]
        balance=np.abs(delta-executed)<=f["numeric"]["quadrature_atol_mM"]+f["numeric"]["quadrature_rtol"]*np.maximum(np.abs(delta),np.abs(executed))
        require(int(balance.sum())==stats["checks"]["daily_balance"]["passed"],"balance flag changed")
        valid=bool(balance.all())
        counts["daily_balances_passed"]+=int(balance.sum());counts["daily_balances_total"]+=balance.size
        for kind in ("raw","executed"):
            aa,bb=a[kind+"4"],a[kind+"8"]
            q=np.abs(aa-bb)<=f["numeric"]["quadrature_atol_mM"]+f["numeric"]["quadrature_rtol"]*np.maximum(np.abs(aa),np.abs(bb))
            require(int(q.sum())==stats["checks"][kind+"_quadrature"]["passed"],"quadrature agreement changed")
            valid &= bool(q.all())
        require(valid==r["numerical_pass"]==stats["numerical_pass"],"numerical validity flag changed")
        for j,(time,state) in enumerate(zip(a["live_time"],a["live_states"].T)):
            for rhs in (native,compiled):
                raw,v,_=rhs.rates(time,state)
                require(np.allclose(raw,a["live_raw"][:,j],rtol=1e-12,atol=1e-12) and np.allclose(v,a["live_executed"][:,j],rtol=1e-12,atol=1e-12),"native/compiled projection mismatch")
            counts["native_rate_checkpoints"]+=1
        for period,p in executed_ledger(a)["periods"].items():
            budgets.append([case["id"],backend,profile,period,p["ATP_production_mM"],p["ATP_consumption_mM"],p["ATP_production_mM"]-p["ATP_consumption_mM"],p["NDPK_net_positive_direction_mM"],p["NDPK_net_negative_direction_mM"]])
        small={k:a[k].copy() for k in ("time","pool_names","states","raw8","executed8")}
    return r,small


def verify(out,report,controls_only):
    require(not report.exists() and not report.is_relative_to(out),"fresh external requalification receipt required")
    if not controls_only:verify_archive(out)
    f=verify_inputs(out);cases=read(out/"cases.json")
    verify_registry(out,f,cases)
    obs=read(out/"observations.json");f["observations_for_verification"]=obs
    counts={"records":0,"quarantined":0,"daily_balances_passed":0,"daily_balances_total":0,"quadrature_values":0,"native_rate_checkpoints":0,"guard_values":0}
    minima,observed,budgets=[],[],[]
    for case in cases["controls"]:
        for backend in f["requalification_plan"]["control_backends"]:
            for p in f["requalification_plan"]["profiles"]:
                verify_replay(folder_for(out,case,backend,p),f,case,backend,p,counts,minima,observed,budgets)
    gate=control_decision(out,f,cases["controls"])
    require(gate==read(out/"control_gate.json"),"control decision changed")
    check_seal(out/"controls")
    classes={};rank=[];table=[]
    if not controls_only:
        summary=read(out/"summary.json")
        panel,historical=historical_metrics(f,obs)
        names,days=list(obs["values"]),panel["days"]
        target=panel["target"];bands=panel["bands"]
        reference={p:np.array(historical[p]["prediction_mM"]) for p in f["requalification_plan"]["profiles"]}
        rank_keys={}
        for case in cases["candidates"]:
            key=case["id"];backend=f["requalification_plan"]["candidate_backend"]
            recorded=summary["candidates"][key];data={};numeric={}
            for p in f["requalification_plan"]["profiles"]:
                r,a=verify_replay(folder_for(out,case,backend,p),f,case,backend,p,counts,minima,observed,budgets)
                require(r==recorded["statuses"][p],"candidate status changed")
                numeric[p]=r["numerical_pass"]
                if a is not None:data[p]=a
                score=recorded["scores"][p]
                if a is None:
                    require(score is None,"score emitted without retained flux evidence")
                if a is not None:
                    x=a["states"][np.ix_([a["pool_names"].tolist().index(k) for k in names],np.searchsorted(a["time"],days))]
                    if score is None:
                        require(np.any(x[[names.index(k) for k in ("ATP","ADP","AMP")]]<=0),"unexplained log-domain failure")
                    else:
                        guards,sides=reconstruct(x,reference[p],target,bands,names,days,f["design"],f["temporal"])
                        require(list(guards)==list(score["feasibility_guards"]) and np.allclose(list(guards.values()),list(score["feasibility_guards"].values()),rtol=1e-12,atol=1e-12),"original guard caps changed")
                        g0,_=reconstruct(reference[p],reference[p],target,bands,names,days,f["design"],f["temporal"])
                        reserve=np.array([0 if k.startswith("date_gain:") else -v*f["temporal"]["reserve_fraction"] for k,v in g0.items()])
                        require(score["reserved_guards_pass"]==bool(np.all(np.array(list(guards.values()))<=-.5*reserve)),"original reserve changed")
                        require(abs(max(sides.values())-score["absolute"]["objective"])<1e-12 and score["absolute"]["target_pass"]==(max(sides.values())<=0),"absolute target diagnostic changed")
                        counts["guard_values"]+=len(guards)
            paired=compare_replays(data["strict"],data["ultrastrict"],f["numeric"],f["threshold_plan"],days) if len(data)==2 else {"pass":False,"reason":"missing validated flux evidence"}
            require(paired==recorded["paired"],"paired numerical decision changed")
            classification=classify_candidate(numeric,paired["pass"],recorded["scores"],within_original_box(f,case["log_factors"]))
            require(classification==recorded["classification"],"candidate classification changed")
            classes[key]=classification
            scores=recorded["scores"]
            defined=all(s is not None for s in scores.values())
            abs_gap=max(s["absolute"]["objective"] for s in scores.values()) if defined else None
            worst_day=max(s["objective"] for s in scores.values()) if defined else None
            if classification["rankable"]:rank_keys[key]=(abs_gap,worst_day)
            s=scores["ultrastrict"]
            late=s["absolute"]["concentrations_mM"] if s is not None else {}
            failed=sorted({g for v in scores.values() if v is not None for g,value in v["feasibility_guards"].items() if value>0})
            table.append([key,";".join(f"{o['source']}:{o['attempt']}" for o in case["occurrences"]),classification["category"],paired["pass"],
                numeric["strict"],numeric["ultrastrict"],classification["absolute_J15_targets_reached"],abs_gap,worst_day,late.get("ATP"),late.get("ADP"),";".join(failed)])
        rank=sorted(rank_keys,key=lambda k:rank_keys[k])
        require(rank==summary["admissible_ranking"] and not summary["historical_guard_caps_recomputed"],"admissible ranking or guard source changed")
    report.mkdir(parents=True)
    write_csv(report/"minima_by_species.csv",["case","backend","profile","support","pool","minimum_mM","minimum_day","below_policy_count","nonfinite_count"],minima)
    write_csv(report/"all55_by_day.csv",["case","backend","profile","numerical_gate_pass","pool","day","nominal_mM","prediction_mM"],observed)
    write_csv(report/"ATP_budgets.csv",["case","backend","profile","period","production_mM","consumption_mM","net_mM","NDPK_net_positive_mM","NDPK_net_negative_mM"],budgets)
    if table:write_csv(report/"requalification.csv",["case","original_occurrences","category","paired_pass","strict_numerical_pass","ultrastrict_numerical_pass","absolute_J15_targets_reached","worst_absolute_gap","worst_day_ratio","ATP_J15_mM","ADP_J15_mM","failed_guards"],table)
    params=[]
    for case in cases["controls"]+([] if controls_only else cases["candidates"]):
        params.extend([case["id"],k,f["parameters"][k],case["parameters"][k],False] for k in f["resolved_capacities"])
    write_csv(report/"replayed_Vmax.csv",["case","parameter","fixed_reference_Vmax","replayed_Vmax","production_promoted"],params)
    result={"verified":True,"phase":"controls" if controls_only else "complete","control_gate_pass":gate["pass"],
        "control_certificate_sha256":sha(out/"control_certificate.json"),"counts":counts,"classifications":classes,
        "category_counts":dict(Counter(r["category"] for r in classes.values())),"admissible_ranking":rank,
        "absolute_target_candidates":[k for k,r in classes.items() if r["rankable"] and r["absolute_J15_targets_reached"]],
        "threshold_changed":False,"Km_initials_changed":False,"optimization_executed":False,"production_promoted":False,"J46_replayed":False,
        "source_seal_sha256":sha(out/"source_seal.json"),"verifier_sha256":sha(Path(__file__))}
    if not controls_only:result["archive_manifest_sha256"]=sha(out/"manifest.json")
    write(report/"verification.json",result);seal(report);check_seal(report)
    return {"verified":True,"control_gate":gate["pass"],"counts":counts,"category_counts":result["category_counts"],"admissible_ranking":rank}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--out",type=Path,required=True);p.add_argument("--report",type=Path,required=True)
    p.add_argument("--controls-only",action="store_true")
    a=p.parse_args()
    with threadpool_limits(1):print(verify(a.out.resolve(),a.report.resolve(),a.controls_only))
