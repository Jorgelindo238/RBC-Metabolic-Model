"""Reproduce failed concentrations, then test a fixed tighter BDF policy."""

import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import json

import numpy as np
from threadpoolctl import threadpool_limits

from run_reaction_threshold_sensitivity import (ROOT,check_seal,parameters_for,read,require,rhs_for,seal,sha,verify_archive,verify_inputs,write,write_csv)
from fla_reaction_threshold import compare_replays,threshold_context
from fla_integration_diagnostics import (audit_recorded_solution,forensic_rates,record_integration,require_concentration_contract,ConcentrationRejected)

CONFIG=ROOT/"config/fla_integration_failure_audit_2026_11_08.json"


def prepare(out):
    require(not out.exists(),"fresh integration diagnostic successor required")
    plan=read(CONFIG)
    parent=ROOT/plan["parent_archive"]
    verify_archive(parent)
    f=verify_inputs(parent)
    require(plan["thresholds_mM"]==[1e-4,1e-5,1e-6] and plan["maximum_new_original_integrations"]==12,"registered forensic matrix changed")
    require(not any(plan[k] for k in ("negative_tolerance_changed","optimization_executed","production_promotion_allowed","J46_replayed")),"audit cannot alter biology or acceptance policy")
    f["failure_audit_plan"]=plan
    parent_cases={c["threshold_mM"]:c for c in read(parent/"cases.json")}
    previous=read(parent/"summary.json")
    cases=[]
    for tau in plan["thresholds_mM"]:
        original=parent_cases[tau]
        cases.append({"id":original["id"],"threshold_mM":tau,"parent_folder":original["folder"],
            "expected_concentration_pass":{p:previous["levels"][original["id"]]["profiles"][p]["completed"] for p in plan["profiles"]}})
    f["input_sha256"].update({p.relative_to(ROOT).as_posix():sha(p) for p in (
        CONFIG,Path(__file__),ROOT/"src/fla_integration_diagnostics.py",ROOT/"qa/test_fla_integration_diagnostics.py",
        ROOT/"scripts/verify_integration_failure_audit.py",ROOT/"tasks/fla_integration_failure_protocol_2026_11_08.md",
        parent/"manifest.json",parent/"execution_design.json",parent/"summary.json",parent/"cases.json")})
    out.mkdir(parents=True)
    write(out/"execution_design.json",f)
    write(out/"observations.json",read(parent/"observations.json"))
    write(out/"cases.json",cases)
    write(out/"source_seal.json",{p:sha(out/p) for p in ("execution_design.json","observations.json","cases.json")})
    return f,cases


def run_one(out,f,case,profile,stage):
    folder=out/stage/case["id"]/profile
    folder.mkdir(parents=True)
    settings=dict(f["numeric"]["numerical_profiles"][profile])
    if stage=="stabilized":
        settings.update(atol=f["failure_audit_plan"]["stabilized_atol_mM"][profile],max_step=f["failure_audit_plan"]["stabilized_max_step_days"])
    local=threshold_context(f,case["threshold_mM"])
    parameters=parameters_for(local,f["profile_center"])
    require(parameters==f["threshold_parameters"],"fixed kinetic vector changed")
    full,fast=(rhs_for(local,parameters,f["temporal"]["network"],backend) for backend in ("full","joint"))
    with threadpool_limits(1):
        _,arrays,diagnostic=record_integration(full,f["initial"],15,f["temporal"]["fit_days"],settings,f["numeric"]["negative_tolerance_mM"])
        diagnostic["forensic_rates"]=forensic_rates(full,arrays,diagnostic)
        np.savez_compressed(folder/"trajectory_evidence.npz",**arrays)
        write(folder/"diagnostics.json",diagnostic)
        stats=None
        failure=None
        try:
            require_concentration_contract(diagnostic)
            evidence,stats=audit_recorded_solution(full,arrays,diagnostic,f["numeric"],lambda t,x:fast.rates(t,x)[:2])
            np.savez_compressed(folder/"flux_evidence.npz",**evidence)
            write(folder/"flux_checks.json",stats)
        except ConcentrationRejected:
            failure={"stage":"concentration_gate","reason":"recorded physical supports violate the fixed policy"}
        except (ValueError,RuntimeError,FloatingPointError,OverflowError) as error:
            failure={"stage":"flux_audit","reason":str(error)}
        if failure:
            write(folder/"failure.json",failure)
        result={"stage":stage,"case":case["id"],"profile":profile,"threshold_mM":case["threshold_mM"],
                "concentration_pass":diagnostic["concentration_gate_pass"],
                "numerical_pass":bool(stats and stats["numerical_pass"]),"failure":failure,"solver_settings":settings}
        write(folder/"result.json",result)
    seal(folder)
    print(f"{stage} {case['id']} {profile}: concentrations={result['concentration_pass']}, numerical={result['numerical_pass']}",flush=True)
    return result


def run_stage(out,f,cases,stage,stream):
    results={c["id"]:{} for c in cases}
    with ProcessPoolExecutor(max_workers=3) as pool:
        jobs={pool.submit(run_one,out,f,c,p,stage):(c["id"],p) for c in cases for p in f["failure_audit_plan"]["profiles"]}
        for future in as_completed(jobs):
            key,p=jobs[future]
            r=future.result()
            results[key][p]=r
            stream.write(json.dumps(r,allow_nan=False)+"\n")
            stream.flush()
    return results


def instrumentation_gate(out,f,cases,results):
    checks=[]
    for case in cases:
        for profile in f["failure_audit_plan"]["profiles"]:
            r=results[case["id"]][profile]
            expected=case["expected_concentration_pass"][profile]
            parity=None
            if expected and r["concentration_pass"]:
                previous=Path(case["parent_folder"])/profile
                check_seal(previous)
                with np.load(previous/"replay.npz") as old,np.load(out/"legacy"/case["id"]/profile/"trajectory_evidence.npz") as new:
                    parity={k:{"exact":bool(np.array_equal(old[k],new[k])),"pass":bool(np.allclose(old[k],new[k],
                        atol=f["failure_audit_plan"]["control_parity_atol"],rtol=f["failure_audit_plan"]["control_parity_rtol"]))}
                        for k in ("time","states","accepted_time","accepted_states")}
            checks.append({"case":case["id"],"profile":profile,"expected_concentration_pass":expected,
                           "reproduced":r["concentration_pass"]==expected,"control_parity":parity})
    passed=all(r["reproduced"] and (r["control_parity"] is None or all(v["pass"] for v in r["control_parity"].values())) for r in checks)
    return {"pass":passed,"checks":checks}


def execute(out):
    f,cases=prepare(out)
    with (out/"execution_trace.jsonl").open("x",encoding="utf-8") as stream:
        legacy=run_stage(out,f,cases,"legacy",stream)
        gate=instrumentation_gate(out,f,cases,legacy)
        write(out/"instrumentation_gate.json",gate)
        stabilized=run_stage(out,f,cases,"stabilized",stream) if gate["pass"] else None
    paired={}
    if stabilized:
        for case in cases:
            key=case["id"]
            if all(stabilized[key][p]["numerical_pass"] for p in f["failure_audit_plan"]["profiles"]):
                with np.load(out/"stabilized"/key/"strict/flux_evidence.npz") as a,np.load(out/"stabilized"/key/"ultrastrict/flux_evidence.npz") as b:
                    paired[key]=compare_replays(a,b,f["numeric"],f["threshold_plan"],f["temporal"]["fit_days"])
            else:
                paired[key]={"pass":False,"reason":"at least one numerical gate failed"}
    summary={"legacy":legacy,"instrumentation_gate":gate,"stabilized":stabilized,"paired_stabilized":paired,
             "new_integrations":6+(6 if stabilized else 0),"all_Vmax_Km_initials_fixed":True,
             "negative_policy_unchanged":True,"production_promoted":False,"optimization_executed":False,"J46_replayed":False}
    write(out/"summary.json",summary)
    verify_inputs(out)
    write(out/"manifest.json",{p.relative_to(out).as_posix():sha(p) for p in out.rglob("*") if p.is_file()})
    return {"instrumentation_inert":gate["pass"],"integrations":summary["new_integrations"],"paired_stabilized_pass":{k:r["pass"] for k,r in paired.items()}}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    with threadpool_limits(1):
        print(execute(args.out.resolve()))
