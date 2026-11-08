"""Original-rate availability-threshold sensitivity without calibration."""

import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import json

import numpy as np
from threadpoolctl import threadpool_limits

from run_pgk_ndpk_profile import (ROOT,check_seal,measure,original,panel_from_observations,
    parameters_for,read,require,rhs_for,scored,seal,sha,verify_archive,verify_inputs,write,write_csv)
from fla_reaction_threshold import compare_replays,plateau_decision,threshold_context
from fla_pgk_ndpk_profile import executed_ledger
from audit_pgk_ndpk_availability import rate_explanation

CONFIG=ROOT/"config/fla_reaction_threshold_2026_11_07.json"


def prepare(out):
    require(not out.exists(),"fresh threshold successor required")
    plan=read(CONFIG)
    require(plan["thresholds_mM"]==[1e-3,1e-4,1e-5,1e-6] and plan["profiles"]==["strict","ultrastrict"],"registered levels or tolerances changed")
    require(not any(plan[k] for k in ("production_promotion_allowed","optimization_executed","J46_replayed")),"no fitting or promotion allowed")
    parent=ROOT/plan["parent_archive"]
    verify_archive(parent)
    f=verify_inputs(parent)
    summary=read(parent/"audit_summary.json")
    center=read(parent/"screen/result.json")["center_id"]
    cached=Path(summary["locations"][center]["folder"])
    reference=Path(summary["locations"]["fixed_reference"]["folder"])
    require(f["numeric"]["availability_threshold_mM"]==plan["thresholds_mM"][0],"cached threshold mismatch")
    cases=[]
    for i,value in enumerate(plan["thresholds_mM"]):
        key=f"tau_e{i+3}"
        cases.append({"id":key,"threshold_mM":value,"reused":i==0,
                      "folder":str(cached if i==0 else out/"audits"/key)})
    require(sum(not c["reused"] for c in cases)*len(plan["profiles"])==plan["maximum_new_original_replays"],"replay budget changed")
    f["threshold_plan"]=plan
    f["threshold_parameters"]=parameters_for(f,f["profile_center"])
    f["threshold_guard_reference_folder"]=str(reference)
    paths=[CONFIG,Path(__file__),ROOT/"scripts/verify_reaction_threshold_sensitivity.py",
           ROOT/"src/fla_reaction_threshold.py",ROOT/"qa/test_fla_reaction_threshold.py",
           ROOT/"tasks/fla_reaction_threshold_protocol_2026_11_07.md",ROOT/"scripts/audit_pgk_ndpk_availability.py",
           parent/"manifest.json",parent/"execution_design.json",parent/"audit_summary.json",parent/"screen/result.json"]
    for folder in (cached,reference):
        for profile in plan["profiles"]:
            check_seal(folder/profile)
            paths.extend(folder/profile/name for name in ("replay.npz","result.json","files_seal.json"))
    f["input_sha256"].update({p.relative_to(ROOT).as_posix():sha(p) for p in paths})
    out.mkdir(parents=True)
    write(out/"execution_design.json",f)
    write(out/"observations.json",read(parent/"observations.json"))
    write(out/"cases.json",cases)
    write(out/"source_seal.json",{p:sha(out/p) for p in ("execution_design.json","observations.json","cases.json")})
    return f,cases


def original_threshold(out,f,case,profile):
    local=threshold_context(f,case["threshold_mM"])
    require(parameters_for(local,local["profile_center"])==f["threshold_parameters"],"fixed kinetic parameters changed")
    try:
        stats=original(out,local,case["id"],profile,f["profile_center"])
        return {"completed":True,"stats":stats}
    except (ValueError,RuntimeError,FloatingPointError,OverflowError) as error:
        folder=Path(case["folder"])/profile
        folder.mkdir(parents=True,exist_ok=True)
        result={"completed":False,"error":str(error)}
        write(folder/"failure.json",result)
        seal(folder)
        print(f"{case['id']} {profile}: preserved numerical failure: {error}",flush=True)
        return result


def prediction(a,panel):
    ids=np.searchsorted(a["time"],panel["days"])
    require(np.array_equal(a["time"][ids],panel["days"]),"actual sample dates changed")
    return a["states"][np.ix_([a["pool_names"].tolist().index(p) for p in panel["names"]],ids)]


def summarise(out,f,cases,statuses):
    plan=f["threshold_plan"]
    obs=read(out/"observations.json")
    panel=panel_from_observations(obs,f["temporal"]["fit_days"],f["design"])
    references={}
    for profile in plan["profiles"]:
        folder=Path(f["threshold_guard_reference_folder"])/profile
        check_seal(folder)
        with np.load(folder/"replay.npz") as a:
            references[profile]=measure(prediction(a,panel),panel)
    data,results,ledgers={}, {}, {}
    rows,nucleotides,availability,integrated=[],[],[],[]
    for case in cases:
        key=case["id"]
        data[key],ledgers[key]={},{}
        result={"threshold_mM":case["threshold_mM"],"reused":case["reused"],"profiles":{}}
        local=threshold_context(f,case["threshold_mM"])
        rhs=rhs_for(local,f["threshold_parameters"],f["temporal"]["network"],"full")
        require(rhs.threshold==case["threshold_mM"] and rhs.parameters==f["threshold_parameters"],"runtime threshold or kinetics changed")
        for profile in plan["profiles"]:
            folder=Path(case["folder"])/profile
            check_seal(folder)
            status=statuses.get(key,{}).get(profile,{"completed":True})
            result["profiles"][profile]=status
            if not status["completed"]:
                continue
            status["stats"]=read(folder/"result.json")
            with np.load(folder/"replay.npz") as a:
                require(np.array_equal(a["accepted_states"][:,0],f["initial"]),"J1 changed")
                x=prediction(a,panel)
                try:
                    status["guard_diagnostic"]=scored(x,references[profile],panel,f)
                except ValueError as error:
                    status["guard_diagnostic"]=None
                    status["guard_error"]=str(error)
                data[key][profile]={k:a[k].copy() for k in ("time","pool_names","states","raw8","executed8")}
                ledgers[key][profile]=executed_ledger(a)
                for i,p in enumerate(panel["names"]):
                    for j,day in enumerate(panel["days"]):
                        rows.append([key,case["threshold_mM"],profile,day,p,panel["target"][i,j],x[i,j]])
                for p in plan["focus_pools"]:
                    value=float(a["states"][a["pool_names"].tolist().index(p),np.searchsorted(a["time"],15)])
                    t=f["absolute_targets"].get(p)
                    nucleotides.append([key,case["threshold_mM"],profile,p,p in panel["names"],value,
                        t["nominal_mM"] if t else None,t["lower_mM"] if t else None,t["upper_mM"] if t else None,
                        bool(t["lower_mM"]<=value<=t["upper_mM"]) if t else None])
                for day in (1,4,8,11,15):
                    state=a["states"][:,np.searchsorted(a["time"],day)]
                    raw,executed,_=rhs.rates(day,state)
                    for info in rate_explanation(state,raw,executed,a["matrix"],a["pool_names"].tolist(),a["reactions"].tolist(),case["threshold_mM"]):
                        availability.append([key,profile,day,info["reaction"],info["raw_rate"],info["executed_rate"],info["availability_factor"],";".join(info["limiting_pools"])])
                for label,lo,hi in (("J1_J4",0,3),("J4_J8",3,7),("J8_J15",7,14)):
                    use=(a["q8_intervals"]>=lo)&(a["q8_intervals"]<hi)
                    w=a["q8_weights"][use]
                    for reaction in ("VPGK","VPK","VNDPK"):
                        j=a["reactions"].tolist().index(reaction)
                        raw,executed=a["q8_raw_rates"][j,use],a["q8_executed_rates"][j,use]
                        raw_abs=float(np.abs(raw)@w)
                        executed_abs=float(np.abs(executed)@w)
                        integrated.append([key,profile,label,reaction,float(raw@w),float(executed@w),raw_abs,executed_abs,
                                           executed_abs/raw_abs if raw_abs else None])
        result["numerical_pass"]=bool(all(s["completed"] and s["stats"]["numerical_pass"] for s in result["profiles"].values()))
        result["comparison"]=compare_replays(data[key]["strict"],data[key]["ultrastrict"],f["numeric"],plan,panel["days"]) if len(data[key])==2 else {"pass":False,"reason":"incomplete replay pair"}
        results[key]=result
    adjacent={}
    for a,b in zip(cases,cases[1:]):
        key=a["id"]+"__"+b["id"]
        adjacent[key]={}
        for profile in plan["profiles"]:
            adjacent[key][profile]=compare_replays(data[a["id"]][profile],data[b["id"]][profile],f["numeric"],plan,panel["days"]) if profile in data[a["id"]] and profile in data[b["id"]] else {"pass":False,"reason":"incomplete replay pair"}
    plateau=plateau_decision([c["id"] for c in cases],results,adjacent,plan["required_final_adjacent_pairs"])
    write(out/"summary.json",{"levels":results,"adjacent_thresholds":adjacent,"plateau":plateau,
          "new_original_replays_attempted":6,"reused_center_replays":2,"historical_guard_reference_replays":2,
          "guard_or_target_scores_used_for_threshold_choice":False,"optimization_executed":False,
          "production_promoted":False,"J46_replayed":False})
    write(out/"nucleotide_ledgers.json",ledgers)
    write_csv(out/"all55_by_day.csv",["case","threshold_mM","profile","day","pool","nominal_mM","prediction_mM"],rows)
    write_csv(out/"J15_nucleotides.csv",["case","threshold_mM","profile","pool","observed_in_source","prediction_mM","nominal_target_mM","lower_target_mM","upper_target_mM","target_pass"],nucleotides)
    write_csv(out/"sampled_availability.csv",["case","profile","day","reaction","same_state_raw_rate","executed_rate","availability_factor","limiting_pools"],availability)
    write_csv(out/"integrated_availability.csv",["case","profile","period","reaction","same_state_raw_net_mM","executed_net_mM","raw_abs_integral_mM","executed_abs_integral_mM","executed_fraction_of_raw_abs"],integrated)
    verify_inputs(out)
    write(out/"manifest.json",{p.relative_to(out).as_posix():sha(p) for p in out.rglob("*") if p.is_file()})
    return {"numerical_pass":{k:r["numerical_pass"] for k,r in results.items()},"solver_comparison_pass":{k:r["comparison"]["pass"] for k,r in results.items()},"plateau":plateau}


def execute(out):
    f,cases=prepare(out)
    statuses={}
    with ProcessPoolExecutor(max_workers=3) as pool,(out/"execution_trace.jsonl").open("x",encoding="utf-8") as stream:
        jobs={pool.submit(original_threshold,out,f,c,p):(c["id"],p) for c in cases if not c["reused"] for p in f["threshold_plan"]["profiles"]}
        for future in as_completed(jobs):
            key,profile=jobs[future]
            result=future.result()
            statuses.setdefault(key,{})[profile]=result
            stream.write(json.dumps({"case":key,"profile":profile,**result},allow_nan=False)+"\n")
            stream.flush()
    return summarise(out,f,cases,statuses)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    with threadpool_limits(1):
        print(execute(args.out.resolve()))
