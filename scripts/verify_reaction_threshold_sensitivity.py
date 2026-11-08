"""Reconstruct numerical decisions for the fixed-parameter threshold audit."""

import argparse
import csv
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

from run_reaction_threshold_sensitivity import (check_seal,parameters_for,read,require,rhs_for,seal,sha,
    verify_archive,verify_inputs,write,write_csv)
from fla_reaction_threshold import compare_replays,plateau_decision,threshold_context
from fla_pgk_ndpk_profile import executed_ledger
from verify_absolute_vmax import reconstruct
from audit_pgk_ndpk_availability import rate_explanation


def verify(out,report):
    require(not report.exists() and not report.is_relative_to(out),"fresh external numerical decision receipt required")
    verify_archive(out)
    f,obs=verify_inputs(out),read(out/"observations.json")
    plan=f["threshold_plan"]
    cases,summary=read(out/"cases.json"),read(out/"summary.json")
    require([c["threshold_mM"] for c in cases]==plan["thresholds_mM"],"registered threshold levels changed")
    require(parameters_for(f,f["profile_center"])==f["threshold_parameters"],"locked kinetics changed")
    require(not summary["guard_or_target_scores_used_for_threshold_choice"] and not summary["production_promoted"] and not summary["optimization_executed"],"threshold fitted or promoted")
    require("GDP" not in obs["values"] and "GTP" not in obs["values"],"latent pools silently became observations")
    names,days=list(obs["values"]),f["temporal"]["fit_days"]
    target=np.array([[obs["values"][p][obs["time"].index(t)] for t in days] for p in names])
    early=np.column_stack(([obs["values"][p][0] for p in names],target))
    bands=.05*np.median(early,axis=1)[:,None]+.2*target
    reference={}
    for profile in plan["profiles"]:
        folder=Path(f["threshold_guard_reference_folder"])/profile
        check_seal(folder)
        with np.load(folder/"replay.npz") as a:
            reference[profile]=a["states"][np.ix_([a["pool_names"].tolist().index(p) for p in names],np.searchsorted(a["time"],days))]
    ledgers=read(out/"nucleotide_ledgers.json")
    with (out/"all55_by_day.csv").open(newline="") as stream:
        csv_rows=list(csv.DictReader(stream))
    indexed={(r["case"],r["profile"],r["pool"],int(r["day"])):r for r in csv_rows}
    with (out/"sampled_availability.csv").open(newline="") as stream:
        avail={(r["case"],r["profile"],int(r["day"]),r["reaction"]):r for r in csv.DictReader(stream)}
    data,checks={},{}
    counters={"complete_replays":0,"quadrature_values":0,"daily_balance_passed":0,"daily_balance_total":0,
              "native_rate_checkpoints":0,"guard_values":0,"source_predictions":0,"availability_rows":0}
    budgets=[]
    for case in cases:
        key=case["id"]
        data[key]={}
        local=threshold_context(f,case["threshold_mM"])
        require(local["parameters"]==f["parameters"] and local["initial"]==f["initial"] and local["kinetics"]==f["kinetics"],"nonthreshold input changed")
        require({k for k in local["numeric"] if local["numeric"][k]!=f["numeric"][k]}<={"availability_threshold_mM"},"another numerical setting changed")
        rhs=rhs_for(local,f["threshold_parameters"],f["temporal"]["network"],"full")
        require(rhs.threshold==case["threshold_mM"] and rhs.parameters==f["threshold_parameters"],"runtime parameters differ")
        individual=[]
        for profile in plan["profiles"]:
            status=summary["levels"][key]["profiles"][profile]
            folder=Path(case["folder"])/profile
            check_seal(folder)
            if not status["completed"]:
                require(read(folder/"failure.json")==status,"failed simulation was changed or omitted")
                individual.append(False)
                continue
            stats=read(folder/"result.json")
            require(stats==status["stats"],"replay status changed")
            with np.load(folder/"replay.npz") as a:
                require(np.array_equal(a["accepted_states"][:,0],f["initial"]) and np.array_equal(a["matrix"],rhs.matrix),"exact J1 or network changed")
                for order in (4,8):
                    for kind in ("raw","executed"):
                        integral=np.array([np.bincount(a[f"q{order}_intervals"],weights=v*a[f"q{order}_weights"],minlength=14) for v in a[f"q{order}_{kind}_rates"]])
                        require(np.allclose(integral,a[f"{kind}{order}"],rtol=1e-12,atol=1e-12),"quadrature reconstruction changed")
                        counters["quadrature_values"]+=integral.size
                bound=np.searchsorted(a["time"],a["boundaries"])
                delta=np.diff(a["states"][:113,bound],axis=1)
                closure=a["matrix"]@a["executed8"]
                daily=np.abs(delta-closure)<=f["numeric"]["quadrature_atol_mM"]+f["numeric"]["quadrature_rtol"]*np.maximum(np.abs(delta),np.abs(closure))
                require(int(daily.sum())==stats["checks"]["daily_balance"]["passed"],"daily balance count changed")
                counters["daily_balance_passed"]+=int(daily.sum())
                counters["daily_balance_total"]+=daily.size
                qchecks=[]
                for kind in ("raw","executed"):
                    aa,bb=a[kind+"4"],a[kind+"8"]
                    q=np.abs(aa-bb)<=f["numeric"]["quadrature_atol_mM"]+f["numeric"]["quadrature_rtol"]*np.maximum(np.abs(aa),np.abs(bb))
                    require(int(q.sum())==stats["checks"][kind+"_quadrature"]["passed"],"quadrature agreement count changed")
                    qchecks.append(q)
                positive=stats["minimum_checked_mM"]>=f["numeric"]["negative_tolerance_mM"]
                require(bool(daily.all() and all(q.all() for q in qchecks) and positive)==stats["numerical_pass"],"numerical validity flag changed")
                individual.append(stats["numerical_pass"])
                for j,(t,x) in enumerate(zip(a["live_time"],a["live_states"].T)):
                    raw,executed,_=rhs.rates(t,x)
                    require(np.allclose(raw,a["live_raw"][:,j],rtol=1e-12,atol=1e-12) and np.allclose(executed,a["live_executed"][:,j],rtol=1e-12,atol=1e-12),"native rate mismatch at actual threshold")
                    counters["native_rate_checkpoints"]+=1
                ids=np.searchsorted(a["time"],days)
                require(np.array_equal(a["time"][ids],days),"observation time changed")
                ix=[a["pool_names"].tolist().index(p) for p in names]
                x=a["states"][np.ix_(ix,ids)]
                for i,p in enumerate(names):
                    for j,day in enumerate(days):
                        row=indexed[(key,profile,p,day)]
                        require(float(row["prediction_mM"])==x[i,j] and float(row["nominal_mM"])==target[i,j],"source or prediction export changed")
                        counters["source_predictions"]+=1
                if status["guard_diagnostic"] is not None:
                    guards,sides=reconstruct(x,reference[profile],target,bands,names,days,f["design"],f["temporal"])
                    require(np.allclose(list(guards.values()),list(status["guard_diagnostic"]["feasibility_guards"].values()),rtol=1e-12,atol=1e-12),"guard diagnostic changed")
                    require(abs(max(sides.values())-status["guard_diagnostic"]["absolute"]["objective"])<1e-12,"absolute target diagnostic changed")
                    counters["guard_values"]+=len(guards)
                else:
                    require(np.any(x[[names.index(p) for p in ("ATP","ADP","AMP")]]<=0),"undefined log diagnostic without nonpositive adenylate")
                ledger=executed_ledger(a)
                require(ledger==ledgers[key][profile],"executed nucleotide ledger changed")
                for period,entry in ledger["periods"].items():
                    budgets.append([key,case["threshold_mM"],profile,period,entry["ATP_production_mM"],entry["ATP_consumption_mM"],
                        entry["ATP_production_mM"]-entry["ATP_consumption_mM"],entry["NDPK_net_positive_direction_mM"],entry["NDPK_net_negative_direction_mM"]])
                for day in (1,4,8,11,15):
                    state=a["states"][:,np.searchsorted(a["time"],day)]
                    raw,executed,_=rhs.rates(day,state)
                    infos=rate_explanation(state,raw,executed,a["matrix"],a["pool_names"].tolist(),a["reactions"].tolist(),case["threshold_mM"])
                    for info in infos:
                        row=avail[(key,profile,day,info["reaction"])]
                        require(float(row["availability_factor"])==info["availability_factor"] and float(row["executed_rate"])==info["executed_rate"] and float(row["same_state_raw_rate"])==info["raw_rate"],"availability diagnostic changed")
                        require(row["limiting_pools"]==";".join(info["limiting_pools"]),"limiting pool changed")
                        counters["availability_rows"]+=1
                data[key][profile]={k:a[k].copy() for k in ("time","pool_names","states","raw8","executed8")}
                counters["complete_replays"]+=1
        comparison=compare_replays(data[key]["strict"],data[key]["ultrastrict"],f["numeric"],plan,days) if len(data[key])==2 else {"pass":False,"reason":"incomplete replay pair"}
        require(comparison==summary["levels"][key]["comparison"],"solver comparison changed")
        numerical=bool(all(individual))
        require(numerical==summary["levels"][key]["numerical_pass"],"solver numerical validity changed")
        checks[key]={"numerical_pass":numerical,"comparison":comparison}
    require(counters["source_predictions"]==len(csv_rows),"unexpected or missing exported observation rows")
    adjacent={}
    comparison_rows=[]
    for a,b in zip(cases,cases[1:]):
        key=a["id"]+"__"+b["id"]
        adjacent[key]={}
        for profile in plan["profiles"]:
            c=compare_replays(data[a["id"]][profile],data[b["id"]][profile],f["numeric"],plan,days) if profile in data[a["id"]] and profile in data[b["id"]] else {"pass":False,"reason":"incomplete replay pair"}
            require(c==summary["adjacent_thresholds"][key][profile],"threshold comparison changed")
            adjacent[key][profile]=c
            comparison_rows.append([a["id"],b["id"],profile,c["pass"],c.get("focused_nucleotides",{}).get("max_tolerance_ratio"),c.get("focused_executed_integrals",{}).get("max_tolerance_ratio")])
    plateau=plateau_decision([c["id"] for c in cases],checks,adjacent,plan["required_final_adjacent_pairs"])
    require(plateau==summary["plateau"],"threshold decision changed")
    report.mkdir(parents=True)
    write_csv(report/"ATP_budgets.csv",["case","threshold_mM","profile","period","production_mM","consumption_mM","net_mM","NDPK_net_positive_direction_mM","NDPK_net_negative_direction_mM"],budgets)
    write_csv(report/"adjacent_threshold_comparisons.csv",["larger_threshold_case","smaller_threshold_case","profile","all_checks_pass","max_focus_tolerance_ratio","max_executed_integral_tolerance_ratio"],comparison_rows)
    result={"verified":True,"checks":counters,"numerical_pass":{k:v["numerical_pass"] for k,v in checks.items()},
            "solver_comparison_pass":{k:v["comparison"]["pass"] for k,v in checks.items()},"plateau":plateau,
            "new_original_replays":6,"reused_center_replays":2,"historical_guard_reference_replays":2,
            "all_Vmax_Km_initials_fixed":True,"threshold_fitted_to_data":False,"threshold_promoted":False,
            "optimization_executed":False,"J46_replayed":False,"verifier_sha256":sha(Path(__file__)),
            "archive_manifest_sha256":sha(out/"manifest.json")}
    write(report/"verification.json",result)
    seal(report)
    check_seal(report)
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    args=p.parse_args()
    with threadpool_limits(1):
        print(verify(args.out.resolve(),args.report.resolve()))
