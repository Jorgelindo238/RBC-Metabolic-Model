"""Same bounded-Jacobian executor with a separately registered finer step."""

import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import json

import numpy as np
from threadpoolctl import threadpool_limits

from run_bounded_jacobian_confirmation import (ROOT,parameters_for,read,require,run_one,seal,sha,verify_archive,verify_inputs,write)
from fla_reaction_threshold import compare_replays

CONFIG=ROOT/"config/fla_fine_jacobian_confirmation_2026_11_08.json"


def execute(out):
    require(not out.exists(),"fresh fine-step confirmation required")
    plan=read(CONFIG)
    parent=ROOT/plan["parent_archive"]
    verify_archive(parent)
    f=verify_inputs(parent)
    f["bounded_plan"]=plan
    cases=read(parent/"cases.json")
    require(len(cases)*len(plan["profiles"])==plan["maximum_new_original_integrations"]==6,"registered size changed")
    paths=[CONFIG,Path(__file__),ROOT/"scripts/run_bounded_jacobian_confirmation.py",ROOT/"src/fla_bounded_jacobian.py",
           ROOT/"qa/test_fla_bounded_jacobian.py",ROOT/"qa/test_fla_fine_jacobian.py",ROOT/"scripts/verify_recorded_integrations.py",
           ROOT/"tasks/fla_fine_jacobian_protocol_2026_11_08.md",parent/"manifest.json",parent/"execution_design.json",parent/"cases.json"]
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
            stream.write(json.dumps(r,allow_nan=False)+"\n");stream.flush()
    paired={}
    for case in cases:
        key=case["id"]
        if all(results[key][p]["numerical_pass"] for p in plan["profiles"]):
            with np.load(out/"bounded"/key/"strict/flux_evidence.npz") as a,np.load(out/"bounded"/key/"ultrastrict/flux_evidence.npz") as b:
                paired[key]=compare_replays(a,b,f["numeric"],f["threshold_plan"],f["temporal"]["fit_days"])
        else:paired[key]={"pass":False,"reason":"incomplete numerical pair"}
    write(out/"summary.json",{"results":results,"paired":paired,"new_integrations":6,"production_promoted":False,"optimization_executed":False,"J46_replayed":False})
    verify_inputs(out)
    write(out/"manifest.json",{p.relative_to(out).as_posix():sha(p) for p in out.rglob("*") if p.is_file()})
    return {"paired_pass":{k:r["pass"] for k,r in paired.items()},"new_integrations":6}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    with threadpool_limits(1):print(execute(a.out.resolve()))
