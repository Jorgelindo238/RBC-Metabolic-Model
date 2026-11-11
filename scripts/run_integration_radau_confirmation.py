"""Separate registered Radau confirmation; no biological parameter changes."""

import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import json

import numpy as np
from threadpoolctl import threadpool_limits

from run_integration_failure_audit import (ROOT,check_seal,parameters_for,read,require,rhs_for,seal,sha,verify_archive,verify_inputs,write)
from fla_reaction_threshold import compare_replays,threshold_context
from fla_stepper_diagnostics import record_stepper
from fla_integration_diagnostics import audit_recorded_solution,forensic_rates,require_concentration_contract,ConcentrationRejected

CONFIG=ROOT/"config/fla_integration_radau_confirmation_2026_11_08.json"


def run_one(out,f,case,profile):
    folder=out/"radau"/case["id"]/profile
    folder.mkdir(parents=True)
    settings=f["radau_plan"]["profiles"][profile]
    local=threshold_context(f,case["threshold_mM"])
    p=parameters_for(local,f["profile_center"])
    require(p==f["threshold_parameters"],"kinetic parameters changed")
    full,fast=(rhs_for(local,p,f["temporal"]["network"],backend) for backend in ("full","joint"))
    with threadpool_limits(1):
        arrays,d=record_stepper(full,f["initial"],15,f["temporal"]["fit_days"],settings,
                                f["numeric"]["negative_tolerance_mM"],"Radau")
        d["forensic_rates"]=forensic_rates(full,arrays,d)
        np.savez_compressed(folder/"trajectory_evidence.npz",**arrays)
        write(folder/"diagnostics.json",d)
        failure=None
        stats=None
        try:
            require_concentration_contract(d)
            evidence,stats=audit_recorded_solution(full,arrays,d,f["numeric"],lambda t,x:fast.rates(t,x)[:2])
            np.savez_compressed(folder/"flux_evidence.npz",**evidence)
            write(folder/"flux_checks.json",stats)
        except ConcentrationRejected:
            failure={"stage":"concentration_gate","reason":"recorded supports violate the unchanged contract"}
        except (ValueError,RuntimeError,FloatingPointError,OverflowError) as error:
            failure={"stage":"flux_audit","reason":str(error)}
        if failure:write(folder/"failure.json",failure)
        result={"stage":"radau","case":case["id"],"profile":profile,"threshold_mM":case["threshold_mM"],
            "concentration_pass":d["concentration_gate_pass"],"numerical_pass":bool(stats and stats["numerical_pass"]),
            "solver_settings":settings,"failure":failure}
        write(folder/"result.json",result)
    seal(folder)
    print(f"Radau {case['id']} {profile}: concentrations={result['concentration_pass']}, numerical={result['numerical_pass']}",flush=True)
    return result


def execute(out):
    require(not out.exists(),"fresh Radau confirmation required")
    plan=read(CONFIG)
    parent=ROOT/plan["parent_archive"]
    verify_archive(parent)
    f=verify_inputs(parent)
    require(read(parent/"summary.json")["instrumentation_gate"]["pass"],"uninstrumented baseline")
    require(not any(plan[k] for k in ("production_promotion_allowed","optimization_executed","J46_replayed")),"diagnostic-only confirmation")
    f["radau_plan"]=plan
    cases=read(parent/"cases.json")
    require(len(cases)*len(plan["profiles"])==plan["maximum_new_original_integrations"]==6,"registered confirmation size changed")
    paths=[CONFIG,Path(__file__),ROOT/"src/fla_stepper_diagnostics.py",ROOT/"qa/test_fla_stepper_diagnostics.py",
           ROOT/"scripts/verify_recorded_integrations.py",ROOT/"tasks/fla_integration_radau_protocol_2026_11_08.md",
           parent/"manifest.json",parent/"summary.json",parent/"execution_design.json",parent/"cases.json"]
    f["input_sha256"].update({p.relative_to(ROOT).as_posix():sha(p) for p in paths})
    out.mkdir(parents=True)
    write(out/"execution_design.json",f)
    write(out/"observations.json",read(parent/"observations.json"))
    write(out/"cases.json",cases)
    write(out/"source_seal.json",{p:sha(out/p) for p in ("execution_design.json","observations.json","cases.json")})
    results={c["id"]:{} for c in cases}
    with ProcessPoolExecutor(max_workers=3) as pool,(out/"execution_trace.jsonl").open("x",encoding="utf-8") as stream:
        jobs={pool.submit(run_one,out,f,c,p):(c["id"],p) for c in cases for p in plan["profiles"]}
        for future in as_completed(jobs):
            key,p=jobs[future]
            r=future.result()
            results[key][p]=r
            stream.write(json.dumps(r,allow_nan=False)+"\n")
            stream.flush()
    paired={}
    for case in cases:
        key=case["id"]
        if all(results[key][p]["numerical_pass"] for p in plan["profiles"]):
            with np.load(out/"radau"/key/"strict/flux_evidence.npz") as a,np.load(out/"radau"/key/"ultrastrict/flux_evidence.npz") as b:
                paired[key]=compare_replays(a,b,f["numeric"],f["threshold_plan"],f["temporal"]["fit_days"])
        else:paired[key]={"pass":False,"reason":"incomplete numerical pair"}
    write(out/"summary.json",{"results":results,"paired":paired,"new_integrations":6,"production_promoted":False,
                              "optimization_executed":False,"J46_replayed":False})
    verify_inputs(out)
    write(out/"manifest.json",{p.relative_to(out).as_posix():sha(p) for p in out.rglob("*") if p.is_file()})
    return {"paired_pass":{k:r["pass"] for k,r in paired.items()},"new_integrations":6}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    with threadpool_limits(1):
        print(execute(a.out.resolve()))
