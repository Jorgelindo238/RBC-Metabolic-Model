"""Verify rejected-state evidence and the fixed tighter BDF experiment."""

import argparse
import json
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

from run_integration_failure_audit import (check_seal,instrumentation_gate,parameters_for,read,require,rhs_for,seal,sha,
    verify_archive,verify_inputs,write,write_csv)
from fla_reaction_threshold import compare_replays,plateau_decision,threshold_context
from fla_integration_diagnostics import inspect_support


def verify(out,report):
    require(not report.exists() and not report.is_relative_to(out),"fresh external failure-audit decision required")
    verify_archive(out)
    f=verify_inputs(out)
    cases,summary,obs=read(out/"cases.json"),read(out/"summary.json"),read(out/"observations.json")
    trace=[json.loads(s) for s in (out/"execution_trace.jsonl").read_text().splitlines()]
    require(len(trace)==summary["new_integrations"]<=f["failure_audit_plan"]["maximum_new_original_integrations"] and
            len({(r["stage"],r["case"],r["profile"]) for r in trace})==len(trace),"attempt count changed")
    require(instrumentation_gate(out,f,cases,summary["legacy"])==summary["instrumentation_gate"],"instrumentation reproduction changed")
    minima,failures,witnesses,observed=[],[],[],[]
    data={stage:{} for stage in ("legacy","stabilized")}
    counts={"physical_support_values":0,"per_species_minima":0,"quarantined_integrations":0,"daily_balance_passed":0,
            "daily_balance_total":0,"quadrature_values":0,"native_rate_checkpoints":0}
    for stage in ("legacy","stabilized"):
        if summary[stage] is None:
            continue
        for case in cases:
            key=case["id"]
            data[stage][key]={}
            local=threshold_context(f,case["threshold_mM"])
            parameters=parameters_for(local,f["profile_center"])
            require(parameters==f["threshold_parameters"],"biological parameters changed")
            rhs=rhs_for(local,parameters,f["temporal"]["network"],"full")
            for profile in f["failure_audit_plan"]["profiles"]:
                folder=out/stage/key/profile
                check_seal(folder)
                result,diagnostic=read(folder/"result.json"),read(folder/"diagnostics.json")
                require(result==summary[stage][key][profile],"case result changed")
                expected=dict(f["numeric"]["numerical_profiles"][profile])
                if stage=="stabilized":
                    expected.update(atol=f["failure_audit_plan"]["stabilized_atol_mM"][profile],max_step=f["failure_audit_plan"]["stabilized_max_step_days"])
                require(result["solver_settings"]==expected and diagnostic["negative_tolerance_mM"]==f["numeric"]["negative_tolerance_mM"],"numerical policy changed")
                with np.load(folder/"trajectory_evidence.npz") as a:
                    require(np.array_equal(a["initial"],f["initial"]),"initial state changed")
                    supports={"accepted":("accepted_time","accepted_states"),"dense":("time","states"),
                              "quadrature4":("q4_time","q4_states"),"quadrature8":("q8_time","q8_states")}
                    recomputed={}
                    for support,(tk,xk) in supports.items():
                        if support not in diagnostic["supports"]:
                            continue
                        x,t=a[xk][:113],a[tk]
                        actual=inspect_support(t,x,a["pool_names"].tolist(),f["numeric"]["negative_tolerance_mM"])
                        require(actual==diagnostic["supports"][support],"support minima or gate changed")
                        counts["physical_support_values"]+=x.size
                        for i,row in enumerate(actual["per_species"]):
                            finite=np.isfinite(x[i])
                            require(row["nonfinite_count"]==int((~finite).sum()) and row["below_policy_count"]==int((finite & (x[i]<f["numeric"]["negative_tolerance_mM"])).sum()),"finite/negative classification changed")
                            if finite.any():
                                require(row["minimum_mM"]==float(x[i,finite].min()),"per-species minimum changed")
                            minima.append([stage,key,profile,case["threshold_mM"],support,row["pool"],row["minimum_mM"],row["minimum_day"],
                                row["negative_count"],row["below_policy_count"],row["nonfinite_count"],row["first_policy_violation_day"]])
                            counts["per_species_minima"]+=1
                        recomputed[support]=actual
                        witness=diagnostic["forensic_rates"].get(support)
                        if witness and witness["available"]:
                            worst=actual["worst_finite"]
                            state=a[xk][:,worst["minimum_index"]]
                            raw,executed,_=rhs.rates(worst["minimum_day"],state)
                            contribution=rhs.matrix[rhs.names.index(worst["pool"])]*executed
                            require(np.isclose(contribution.sum(),witness["executed_derivative"],rtol=1e-12,atol=1e-12),"forensic derivative changed")
                            witnesses.append([stage,key,profile,support,witness["pool"],witness["day"],witness["concentration_mM"],witness["raw_derivative"],witness["executed_derivative"],witness["executed_consumption"]])
                    ph_fixed=all(np.array_equal(a[xk][-1],np.full(a[xk].shape[1],f["initial"][-1])) for support,(tk,xk) in supports.items() if support in recomputed)
                    gate=bool(diagnostic.get("complete_exact_J1",False) and ph_fixed and len(recomputed)==4 and all(s["pass"] for s in recomputed.values()))
                    require(gate==diagnostic["concentration_gate_pass"]==result["concentration_pass"],"rejected integration admitted")
                    if not gate:
                        require(not (folder/"flux_evidence.npz").exists(),"rejected state evidence leaked into rate validation")
                        counts["quarantined_integrations"]+=1
                        candidates=[(s,d["worst_finite"]) for s,d in recomputed.items() if d["worst_finite"] is not None]
                        source,worst=min(candidates,key=lambda item:item[1]["minimum_mM"]) if candidates else (None,None)
                        first=[d["first_sampled_policy_violation"] for d in recomputed.values() if d["first_sampled_policy_violation"]]
                        first=min(first,key=lambda r:r["day"]) if first else None
                        failures.append([stage,key,profile,source,worst["pool"] if worst else None,worst["minimum_mM"] if worst else None,
                            worst["minimum_day"] if worst else None,first["pool"] if first else None,first["day"] if first else None])
                    for p,values in obs["values"].items():
                        for day in f["temporal"]["fit_days"]:
                            index=np.searchsorted(a["time"],day)
                            if index<len(a["time"]) and a["time"][index]==day:
                                observed.append([stage,key,profile,result["numerical_pass"],p,day,values[obs["time"].index(day)],float(a["states"][a["pool_names"].tolist().index(p),index])])
                if not result["concentration_pass"] or not (folder/"flux_evidence.npz").exists():
                    require(not result["numerical_pass"],"missing flux proof marked numerically valid")
                    continue
                stats=read(folder/"flux_checks.json")
                with np.load(folder/"flux_evidence.npz") as a:
                    require(np.array_equal(a["matrix"],rhs.matrix),"executed matrix changed")
                    for order in (4,8):
                        for kind in ("raw","executed"):
                            integral=np.array([np.bincount(a[f"q{order}_intervals"],weights=v*a[f"q{order}_weights"],minlength=14) for v in a[f"q{order}_{kind}_rates"]])
                            require(np.allclose(integral,a[kind+str(order)],rtol=1e-12,atol=1e-12),"quadrature reconstruction failed")
                            counts["quadrature_values"]+=integral.size
                    ids=np.searchsorted(a["time"],a["boundaries"])
                    delta=np.diff(a["states"][:113,ids],axis=1)
                    balance=rhs.matrix@a["executed8"]
                    ok=np.abs(delta-balance)<=f["numeric"]["quadrature_atol_mM"]+f["numeric"]["quadrature_rtol"]*np.maximum(np.abs(delta),np.abs(balance))
                    require(int(ok.sum())==stats["checks"]["daily_balance"]["passed"],"daily closure changed")
                    counts["daily_balance_passed"]+=int(ok.sum())
                    counts["daily_balance_total"]+=ok.size
                    qchecks=[]
                    for kind in ("raw","executed"):
                        aa,bb=a[kind+"4"],a[kind+"8"]
                        q=np.abs(aa-bb)<=f["numeric"]["quadrature_atol_mM"]+f["numeric"]["quadrature_rtol"]*np.maximum(np.abs(aa),np.abs(bb))
                        require(int(q.sum())==stats["checks"][kind+"_quadrature"]["passed"],"quadrature agreement changed")
                        qchecks.append(q)
                    require(bool(ok.all() and all(q.all() for q in qchecks))==result["numerical_pass"]==stats["numerical_pass"],"numerical gate changed")
                    for j,(t,state) in enumerate(zip(a["live_time"],a["live_states"].T)):
                        raw,executed,_=rhs.rates(t,state)
                        require(np.allclose(raw,a["live_raw"][:,j],rtol=1e-12,atol=1e-12) and np.allclose(executed,a["live_executed"][:,j],rtol=1e-12,atol=1e-12),"native rate checkpoint failed")
                        counts["native_rate_checkpoints"]+=1
                    data[stage][key][profile]={k:a[k].copy() for k in ("time","states","pool_names","raw8","executed8")}
    solver_checks={}
    adjacent={}
    if summary["stabilized"]:
        for case in cases:
            key=case["id"]
            complete=all(summary["stabilized"][key][p]["numerical_pass"] for p in f["failure_audit_plan"]["profiles"])
            comparison=compare_replays(data["stabilized"][key]["strict"],data["stabilized"][key]["ultrastrict"],f["numeric"],f["threshold_plan"],f["temporal"]["fit_days"]) if complete else {"pass":False,"reason":"at least one numerical gate failed"}
            require(comparison==summary["paired_stabilized"][key],"paired solver decision changed")
            solver_checks[key]={"numerical_pass":complete,"comparison":comparison}
        for a,b in zip(cases,cases[1:]):
            adjacent[a["id"]+"__"+b["id"]]={p:compare_replays(data["stabilized"][a["id"]][p],data["stabilized"][b["id"]][p],f["numeric"],f["threshold_plan"],f["temporal"]["fit_days"])
                if p in data["stabilized"][a["id"]] and p in data["stabilized"][b["id"]] else {"pass":False,"reason":"incomplete numerical pair"} for p in f["failure_audit_plan"]["profiles"]}
        plateau=plateau_decision([c["id"] for c in cases],solver_checks,adjacent,2)
    else:
        plateau={"registered_plateau":False,"reason":"instrumentation did not reproduce parent"}
    report.mkdir(parents=True)
    write_csv(report/"minima_by_species.csv",["stage","case","profile","threshold_mM","support","pool","minimum_mM","minimum_day","negative_count","below_policy_count","nonfinite_count","first_sampled_violation_day"],minima)
    write_csv(report/"rejected_concentrations.csv",["stage","case","profile","worst_support","worst_pool","worst_minimum_mM","worst_day","first_sampled_violation_pool","first_sampled_violation_day"],failures)
    write_csv(report/"forensic_rates.csv",["stage","case","profile","support","pool","day","concentration_mM","raw_derivative","executed_derivative","executed_consumption"],witnesses)
    write_csv(report/"all55_by_day.csv",["stage","case","profile","numerical_gate_pass","pool","day","nominal_mM","prediction_mM"],observed)
    result={"verified":True,"new_integrations":len(trace),"instrumentation_gate":summary["instrumentation_gate"],
            "checks":counts,"stabilized_solver_checks":solver_checks,"adjacent_thresholds":adjacent,"threshold_plateau":plateau,
            "all_Vmax_Km_initials_fixed":True,"negative_policy_unchanged":True,"production_promoted":False,
            "optimization_executed":False,"J46_replayed":False,"verifier_sha256":sha(Path(__file__)),"archive_manifest_sha256":sha(out/"manifest.json")}
    write(report/"verification.json",result)
    seal(report)
    check_seal(report)
    return {"verified":True,"checks":counts,"paired_stabilized":{k:v["comparison"]["pass"] for k,v in solver_checks.items()},"threshold_plateau":plateau}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    args=p.parse_args()
    with threadpool_limits(1):
        print(verify(args.out.resolve(),args.report.resolve()))
