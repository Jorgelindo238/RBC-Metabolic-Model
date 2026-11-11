"""Partial-safe successor verifier for BDF and Radau recorded evidence."""

import argparse
import json
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

from run_integration_failure_audit import (check_seal,parameters_for,read,require,rhs_for,seal,sha,
    verify_archive,verify_inputs,write,write_csv)
from fla_integration_diagnostics import inspect_support
from fla_reaction_threshold import compare_replays,plateau_decision,threshold_context

SUPPORTS={"accepted":("accepted_time","accepted_states"),"dense":("time","states"),
          "quadrature4":("q4_time","q4_states"),"quadrature8":("q8_time","q8_states")}


def check_saved_supports(a,d,names,tolerance):
    summaries={}
    for label,(tk,xk) in SUPPORTS.items():
        if label not in d["supports"]:continue
        require(tk in a and xk in a,"declared support missing")
        summaries[label]=inspect_support(a[tk],a[xk][:len(names)],names,tolerance)
        require(summaries[label]==d["supports"][label],"support evidence changed")
    ph=all(np.array_equal(a[xk][-1],np.full(a[xk].shape[1],a["initial"][-1])) for k,(tk,xk) in SUPPORTS.items() if k in summaries)
    gate=bool(d.get("complete_exact_J1",False) and len(summaries)==4 and ph and all(s["pass"] for s in summaries.values()))
    return summaries,gate


def verify(out,report):
    require(not report.exists() and not report.is_relative_to(out),"fresh partial-safe decision receipt required")
    verify_archive(out)
    f=verify_inputs(out)
    trace=[json.loads(s) for s in (out/"execution_trace.jsonl").read_text().splitlines()]
    require(len(trace)==read(out/"summary.json")["new_integrations"],"attempt count changed")
    records=sorted(out.rglob("result.json"))
    require(len(records)==len(trace),"missing case records")
    rows,failures,observed,witnesses=[],[],[],[]
    data={}
    counts={"records":0,"quarantined":0,"partial_exceptions":0,"per_species_minima":0,"daily_balances_passed":0,
            "daily_balances_total":0,"quadrature_values":0,"native_rate_checkpoints":0}
    obs=read(out/"observations.json")
    for file in records:
        folder=file.parent
        check_seal(folder)
        result,d=read(file),read(folder/"diagnostics.json")
        require(result in trace,"result not an actual attempted integration")
        stage,key,profile=result["stage"],result["case"],result["profile"]
        local=threshold_context(f,result["threshold_mM"])
        parameters=parameters_for(local,f["profile_center"])
        require(parameters==f["threshold_parameters"],"kinetics changed")
        rhs=rhs_for(local,parameters,f["temporal"]["network"],"full")
        require(d["negative_tolerance_mM"]==f["numeric"]["negative_tolerance_mM"],"negative policy changed")
        data.setdefault(stage,{}).setdefault(key,{})
        with np.load(folder/"trajectory_evidence.npz") as a:
            require(np.array_equal(a["initial"],f["initial"]),"exact J1 changed")
            s,gate=check_saved_supports(a,d,a["pool_names"].tolist(),f["numeric"]["negative_tolerance_mM"])
            require(gate==d["concentration_gate_pass"]==result["concentration_pass"],"concentration gate changed")
            for label,summary in s.items():
                for entry in summary["per_species"]:
                    rows.append([stage,key,profile,label,entry["pool"],entry["minimum_mM"],entry["minimum_day"],entry["negative_count"],entry["below_policy_count"],entry["nonfinite_count"],entry["first_policy_violation_day"]])
                    counts["per_species_minima"]+=1
                w=d.get("forensic_rates",{}).get(label)
                if w and w["available"]:
                    tk,xk=SUPPORTS[label]
                    minimum=summary["worst_finite"]
                    state=a[xk][:,minimum["minimum_index"]]
                    raw,executed,_=rhs.rates(minimum["minimum_day"],state)
                    v=rhs.matrix[rhs.names.index(w["pool"])]*executed
                    require(np.isclose(v.sum(),w["executed_derivative"],rtol=1e-12,atol=1e-12),"forensic rate changed")
                    witnesses.append([stage,key,profile,label,w["pool"],w["day"],w["concentration_mM"],w["executed_derivative"],w["executed_consumption"]])
            if not gate:
                require(not (folder/"flux_evidence.npz").exists() and not result["numerical_pass"],"rejected evidence admitted")
                candidates=[(k,v["worst_finite"]) for k,v in s.items() if v["worst_finite"] is not None]
                label,worst=min(candidates,key=lambda z:z[1]["minimum_mM"]) if candidates else (None,None)
                first=[v["first_sampled_policy_violation"] for v in s.values() if v["first_sampled_policy_violation"]]
                first=min(first,key=lambda z:z["day"]) if first else None
                nonfinite=[a["pool_names"].tolist()[i] for i in range(113) if "internal_last_state" in a and not np.isfinite(a["internal_last_state"][i])]
                failures.append([stage,key,profile,label,worst["pool"] if worst else None,worst["minimum_mM"] if worst else None,
                    worst["minimum_day"] if worst else None,first["day"] if first else None,
                    d.get("internal_RHS",{}).get("last_day"),";".join(nonfinite),d.get("exception",{}).get("message") if d.get("exception") else None])
                counts["quarantined"]+=1
            if d.get("exception"):counts["partial_exceptions"]+=1
            if "time" in a and "states" in a:
                names=a["pool_names"].tolist()
                for p,y in obs["values"].items():
                    for day in f["temporal"]["fit_days"]:
                        j=np.searchsorted(a["time"],day)
                        if j<len(a["time"]) and a["time"][j]==day:
                            observed.append([stage,key,profile,result["numerical_pass"],p,day,y[obs["time"].index(day)],float(a["states"][names.index(p),j])])
        if (folder/"flux_evidence.npz").exists():
            require(gate,"rate audit on rejected states")
            stats=read(folder/"flux_checks.json")
            with np.load(folder/"flux_evidence.npz") as a:
                require(np.array_equal(a["matrix"],rhs.matrix),"matrix changed")
                for order in (4,8):
                    for kind in ("raw","executed"):
                        integral=np.array([np.bincount(a[f"q{order}_intervals"],weights=v*a[f"q{order}_weights"],minlength=14) for v in a[f"q{order}_{kind}_rates"]])
                        require(np.allclose(integral,a[kind+str(order)],rtol=1e-12,atol=1e-12),"quadrature reconstruction failed")
                        counts["quadrature_values"]+=integral.size
                ids=np.searchsorted(a["time"],a["boundaries"])
                delta=np.diff(a["states"][:113,ids],axis=1)
                b=rhs.matrix@a["executed8"]
                ok=np.abs(delta-b)<=f["numeric"]["quadrature_atol_mM"]+f["numeric"]["quadrature_rtol"]*np.maximum(np.abs(delta),np.abs(b))
                counts["daily_balances_passed"]+=int(ok.sum())
                counts["daily_balances_total"]+=ok.size
                valid=bool(ok.all())
                for kind in ("raw","executed"):
                    aa,bb=a[kind+"4"],a[kind+"8"]
                    q=np.abs(aa-bb)<=f["numeric"]["quadrature_atol_mM"]+f["numeric"]["quadrature_rtol"]*np.maximum(np.abs(aa),np.abs(bb))
                    require(int(q.sum())==stats["checks"][kind+"_quadrature"]["passed"],"quadrature agreement changed")
                    valid &= bool(q.all())
                require(valid==result["numerical_pass"]==stats["numerical_pass"],"numerical validity changed")
                for j,(t,state) in enumerate(zip(a["live_time"],a["live_states"].T)):
                    raw,executed,_=rhs.rates(t,state)
                    require(np.allclose(raw,a["live_raw"][:,j],rtol=1e-12,atol=1e-12) and np.allclose(executed,a["live_executed"][:,j],rtol=1e-12,atol=1e-12),"native rate mismatch")
                    counts["native_rate_checkpoints"]+=1
                if valid:data[stage][key][profile]={k:a[k].copy() for k in ("time","states","pool_names","raw8","executed8")}
        counts["records"]+=1
    stages={}
    for stage,levels in data.items():
        solver={}
        for key,profiles in levels.items():
            complete=all(p in profiles for p in ("strict","ultrastrict"))
            c=compare_replays(profiles["strict"],profiles["ultrastrict"],f["numeric"],f["threshold_plan"],f["temporal"]["fit_days"]) if complete else {"pass":False}
            solver[key]={"numerical_pass":complete,"comparison":c}
        keys=sorted(levels)
        adjacent={a+"__"+b:{p:compare_replays(levels[a][p],levels[b][p],f["numeric"],f["threshold_plan"],f["temporal"]["fit_days"]) if p in levels[a] and p in levels[b] else {"pass":False} for p in ("strict","ultrastrict")} for a,b in zip(keys,keys[1:])}
        stages[stage]={"solver_checks":solver,"adjacent_thresholds":adjacent,"threshold_plateau":plateau_decision(keys,solver,adjacent,2)}
    report.mkdir(parents=True)
    write_csv(report/"minima_by_species.csv",["stage","case","profile","support","pool","minimum_mM","minimum_day","negative_count","below_policy_count","nonfinite_count","first_sampled_violation_day"],rows)
    write_csv(report/"rejected_concentrations.csv",["stage","case","profile","worst_support","worst_pool","worst_minimum_mM","worst_day","first_sampled_violation_day","last_RHS_day","last_RHS_nonfinite_pools","exception"],failures)
    write_csv(report/"all55_by_day.csv",["stage","case","profile","numerical_gate_pass","pool","day","nominal_mM","prediction_mM"],observed)
    write_csv(report/"forensic_rates.csv",["stage","case","profile","support","pool","day","concentration_mM","executed_derivative","executed_consumption"],witnesses)
    result={"verified":True,"counts":counts,"stages":stages,"all_Vmax_Km_initials_fixed":True,"negative_policy_unchanged":True,
            "production_promoted":False,"optimization_executed":False,"J46_replayed":False,
            "verifier_sha256":sha(Path(__file__)),"archive_manifest_sha256":sha(out/"manifest.json")}
    write(report/"verification.json",result)
    seal(report)
    check_seal(report)
    return {"verified":True,"counts":counts,"paired_pass":{s:{k:r["comparison"]["pass"] for k,r in v["solver_checks"].items()} for s,v in stages.items()}}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    a=p.parse_args()
    with threadpool_limits(1):print(verify(a.out.resolve(),a.report.resolve()))
