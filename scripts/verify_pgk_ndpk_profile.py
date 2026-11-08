"""Reconstruct profile guards and original-rate nucleotide-transfer ledgers."""

import argparse
import json
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

from run_pgk_ndpk_profile import ROOT,check_seal,parameters_for,read,require,rhs_for,seal,sha,verify_archive,verify_inputs,within,write,write_csv
from verify_absolute_vmax import reconstruct
from fla_pgk_ndpk_profile import POOLS,audit_roles,executed_ledger,profile_cases


def verify(out,report):
    require(not report.exists() and not report.is_relative_to(out),"fresh external profile receipt required")
    verify_archive(out)
    f=verify_inputs(out)
    check_seal(out/"screen")
    obs=read(out/"observations.json")
    names,days=list(obs["values"]),f["temporal"]["fit_days"]
    target=np.array([[obs["values"][p][obs["time"].index(t)] for t in days] for p in names])
    early=np.column_stack(([obs["values"][p][0] for p in names],target))
    bands=.05*np.median(early,axis=1)[:,None]+.2*target
    trace=[json.loads(s) for s in (out/"screen/trace.jsonl").read_text().splitlines()]
    cases=profile_cases(f)
    require(len(trace)==len(cases)==26,"profile coverage changed")
    require(read(out/"cases.json")==cases,"registered cases changed")
    result=read(out/"screen/result.json")
    require(audit_roles(trace,f)==result["roles"],"audited role selection changed")
    baseline=np.array(trace[0]["prediction_mM"])
    groups=list(f["design"]["groups"])
    center=parameters_for(f,f["profile_center"])
    allowed=set(f["design"]["groups"]["PGK"]+f["design"]["groups"]["NDPK"])
    counts={"fit_guard_values":0,"fit_absolute_scores":0,"daily_balances":0,
            "quadrature_values":0,"live_rate_checkpoints":0,"cross_tolerance_values":0}

    def check_score(x,base,record):
        guards,sides=reconstruct(x,base,target,bands,names,days,f["design"],f["temporal"])
        g0,_=reconstruct(base,base,target,bands,names,days,f["design"],f["temporal"])
        reserve=np.array([0 if k.startswith("date_gain:") else -v*f["temporal"]["reserve_fraction"] for k,v in g0.items()])
        require(list(guards)==list(record["feasibility_guards"]),"guard names changed")
        require(np.allclose(list(guards.values()),list(record["feasibility_guards"].values()),rtol=1e-12,atol=1e-12),"guard values changed")
        require(np.allclose(list(sides.values()),list(record["absolute"]["sides"].values()),rtol=1e-12,atol=1e-12),"absolute target sides changed")
        require(abs(max(sides.values())-record["absolute"]["objective"])<1e-12 and record["absolute"]["target_pass"]==(max(sides.values())<=0),"absolute target decision changed")
        require(record["reserved_guards_pass"]==bool(np.all(np.array(list(guards.values()))<=-.5*reserve)),"guard reserve changed")
        return guards

    screen_csv=[]
    for case,row in zip(cases,trace):
        require(all(row[k]==v for k,v in case.items()),"evaluated case vector or branch changed")
        parameters=parameters_for(f,row["log_factors"])
        if not row["control"]:
            require({k for k in parameters if parameters[k]!=center[k]}<=allowed,"non-profile capacity changed")
        require(all(parameters[k]==v for k,v in f["parameters"].items() if not k.startswith("vmax_") or v==0),"Km, closed branch or noncapacity changed")
        if row["valid"]:
            guards=check_score(np.array(row["prediction_mM"]),baseline,row)
            counts["fit_guard_values"]+=len(guards)
            counts["fit_absolute_scores"]+=1
        diag=row.get("diagnostic_states_mM",{})
        screen_csv.append([row["id"],row.get("PGK_factor"),row.get("NDPK_factor"),row["inside_previous_box"],row["valid"],
            row.get("reserved_guards_pass",False),row.get("absolute",{}).get("objective"),row.get("absolute",{}).get("target_pass",False),
            *[diag.get(p,[None]*4)[-1] for p in POOLS],";".join(k for k,v in row.get("feasibility_guards",{}).items() if v>0)])
    summary=read(out/"audit_summary.json")
    by_id={r["id"]:r for r in trace}
    target_rows,balance_rows,transfer_rows,atp_rows,ledgers=[],[],[],[],{}
    data={}
    for case_id,location in summary["locations"].items():
        folder=Path(location["folder"])
        case_result=summary["results"][case_id]
        data[case_id]={}
        numeric_profiles=[]
        ledgers[case_id]={}
        parameters=parameters_for(f,by_id[case_id]["log_factors"])
        rhs=rhs_for(f,parameters,f["temporal"]["network"],"full")
        for profile in ("strict","ultrastrict"):
            check_seal(folder/profile)
            status=case_result["profiles"][profile]
            if not status["completed"]:
                require(read(folder/profile/"failure.json")["completed"] is False,"failure record missing")
                continue
            stats=read(folder/profile/"result.json")
            require(stats==status["stats"],"original replay stats changed")
            with np.load(folder/profile/"replay.npz") as a:
                require(np.array_equal(a["accepted_states"][:,0],f["initial"]) and np.array_equal(a["matrix"],rhs.matrix),"original J1 or network changed")
                for order in (4,8):
                    for kind in ("raw","executed"):
                        integral=np.array([np.bincount(a[f"q{order}_intervals"],weights=v*a[f"q{order}_weights"],minlength=14) for v in a[f"q{order}_{kind}_rates"]])
                        require(within(integral,a[f"{kind}{order}"],f["numeric"],"quadrature").all(),"quadrature reconstruction failed")
                        counts["quadrature_values"]+=integral.size
                bound=np.searchsorted(a["time"],a["boundaries"])
                daily=within(np.diff(a["states"][:113,bound]),a["matrix"]@a["executed8"],f["numeric"],"quadrature")
                require(int(daily.sum())==stats["checks"]["daily_balance"]["passed"],"daily closure changed")
                counts["daily_balances"]+=int(daily.sum())
                quadratures=[]
                for kind in ("raw","executed"):
                    q=within(a[kind+"4"],a[kind+"8"],f["numeric"],"quadrature")
                    require(int(q.sum())==stats["checks"][kind+"_quadrature"]["passed"],"quadrature convergence flag changed")
                    quadratures.append(q)
                numerical=bool(daily.all() and all(q.all() for q in quadratures) and stats["minimum_checked_mM"]>=f["numeric"]["negative_tolerance_mM"])
                require(numerical==stats["numerical_pass"],"numerical admission flag changed")
                numeric_profiles.append(numerical)
                for j,(t,x) in enumerate(zip(a["live_time"],a["live_states"].T)):
                    raw,executed,_=rhs.rates(t,x)
                    require(np.allclose(raw,a["live_raw"][:,j],rtol=1e-12,atol=1e-12) and np.allclose(executed,a["live_executed"][:,j],rtol=1e-12,atol=1e-12),"native live rates changed")
                    counts["live_rate_checkpoints"]+=1
                ids=np.searchsorted(a["time"],days)
                require(np.array_equal(a["time"][ids],days),"original sample dates changed")
                replay_names=a["pool_names"].tolist()
                x=a["states"][np.ix_([replay_names.index(p) for p in names],ids)]
                data[case_id][profile]={k:a[k].copy() for k in ("time","states","raw8","executed8")}
                if case_id=="fixed_reference":
                    base=x
                else:
                    ref_folder=Path(summary["locations"]["fixed_reference"]["folder"])
                    with np.load(ref_folder/profile/"replay.npz") as b:
                        base=b["states"][np.ix_([b["pool_names"].tolist().index(p) for p in names],np.searchsorted(b["time"],days))]
                check_score(x,base,status["score"])
                ledger=executed_ledger(a)
                ledgers[case_id][profile]=ledger
                for pool in POOLS:
                    value=float(a["states"][replay_names.index(pool),ids[-1]])
                    t=f["absolute_targets"].get(pool)
                    target_rows.append([case_id,profile,pool,pool in names,t["nominal_mM"] if t else None,
                        t["lower_mM"] if t else None,t["upper_mM"] if t else None,value,
                        bool(t["lower_mM"]<=value<=t["upper_mM"]) if t else None])
                for period,payload in ledger["periods"].items():
                    atp_rows.append([case_id,profile,period,payload["ATP_production_mM"],payload["ATP_consumption_mM"],
                        payload["ATP_production_mM"]-payload["ATP_consumption_mM"],
                        payload["NDPK_net_positive_direction_mM"],payload["NDPK_net_negative_direction_mM"]])
                    for pool,payload0 in payload["pools"].items():
                        balance_rows.append([case_id,profile,period,pool,payload0["delta_state_mM"],payload0["executed_delta_mM"],payload0["balance_residual_mM"]])
                        transfer_rows.extend([case_id,profile,period,pool,r,v] for r,v in payload0["signed_reactions_mM"].items())
        cross=False
        if len(data[case_id])==2:
            a,b=data[case_id]["strict"],data[case_id]["ultrastrict"]
            require(np.array_equal(a["time"],b["time"]),"cross-tolerance grid changed")
            tests=[within(a[k],b[k],f["numeric"],"comparison") for k in ("states","raw8","executed8")]
            require(sum(int(v.sum()) for v in tests)==case_result["cross_passed"] and sum(v.size for v in tests)==case_result["cross_total"],"cross checks changed")
            counts["cross_tolerance_values"]+=sum(v.size for v in tests)
            cross=bool(all(v.all() for v in tests))
        require(case_result["numerical_pass"]==bool(len(numeric_profiles)==2 and all(numeric_profiles) and cross),"paired numerical flag changed")
        expected=bool(case_result["numerical_pass"] and by_id[case_id]["inside_previous_box"] and all(s["completed"] and s["score"]["reserved_guards_pass"] for s in case_result["profiles"].values()))
        require(expected==case_result["within_old_box_and_guard_contract"],"outside-box diagnostic admitted or guard failure ignored")
        require(case_result["absolute_target_admissible"]==bool(expected and all(s["score"]["absolute"]["target_pass"] for s in case_result["profiles"].values())),"absolute admission flag changed")
    report.mkdir(parents=True)
    write(report/"nucleotide_ledgers.json",ledgers)
    write_csv(report/"screen_profile.csv",["case","PGK_factor","NDPK_factor","inside_previous_box","valid","reserved_guards_pass","absolute_gap","absolute_target_pass",*['J15_'+p+'_mM' for p in POOLS],"failed_guards"],screen_csv)
    write_csv(report/"original_J15_nucleotides.csv",["case","profile","pool","observed_in_source","nominal_target_mM","lower_target_mM","upper_target_mM","simulated_mM","absolute_target_pass"],target_rows)
    write_csv(report/"six_pool_balances.csv",["case","profile","period","pool","delta_state_mM","executed_delta_mM","residual_mM"],balance_rows)
    write_csv(report/"executed_reaction_ledger.csv",["case","profile","period","pool","reaction","signed_contribution_mM"],transfer_rows)
    write_csv(report/"ATP_budgets.csv",["case","profile","period","production_mM","consumption_mM","net_mM","NDPK_net_positive_direction_mM","NDPK_net_negative_direction_mM"],atp_rows)
    result={"verified":True,"screen_attempts":len(trace),"valid_screen_points":sum(r["valid"] for r in trace),
            "new_replays_attempted":summary["new_original_replays_attempted"],"reused_replays":summary["reused_original_replays"],
            "checks":counts,"audit_roles":read(out/"screen/result.json")["roles"],
            "absolute_target_admissible":{k:r["absolute_target_admissible"] for k,r in summary["results"].items()},
            "GDP_GTP_are_latent":True,"all_Km_fixed":True,"optimization_executed":False,
            "outside_box_points_are_diagnostic_only":True,"production_promoted":False,"J46_replayed":False,
            "archive_manifest_sha256":sha(out/"manifest.json"),"verifier_sha256":sha(Path(__file__))}
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
