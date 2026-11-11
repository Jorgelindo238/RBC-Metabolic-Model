"""Certify historical-threshold controls, then replay only archived rejects."""

import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import json

import numpy as np
import scipy
from threadpoolctl import threadpool_limits

from run_pgk_ndpk_profile import (ROOT,check_seal,measure,panel_from_observations,read,require,rhs_for,
    scored,seal,sha,verify_archive,verify_inputs,write,write_csv)
from fla_vmax_requalification import exact_parameters,within_original_box,rejected_registry,classify_candidate
from fla_stepper_diagnostics import record_stepper
from fla_bounded_jacobian import BoundedJacobian
from fla_reaction_threshold import compare_replays,threshold_context
from fla_integration_diagnostics import audit_recorded_solution,forensic_rates,require_concentration_contract,ConcentrationRejected

CONFIG=ROOT/"config/fla_vmax_requalification_2026_11_09.json"


def prepare(out):
    require(not out.exists(),"fresh requalification campaign required")
    plan=read(CONFIG)
    require(plan["threshold_mM"]==1e-3 and scipy.__version__==plan["scipy_version"],"historical threshold or tested runtime changed")
    require(not any(plan[k] for k in ("optimization_executed","production_promotion_allowed","J46_replayed")),"requalification cannot optimize or promote")
    parent=ROOT/plan["numerical_parent"]
    verify_archive(parent)
    f=verify_inputs(parent)
    obs=read(parent/"observations.json")
    f["requalification_plan"]=plan
    paths=[CONFIG,Path(__file__),ROOT/"scripts/verify_vmax_requalification.py",ROOT/"src/fla_vmax_requalification.py",
           ROOT/"qa/test_fla_vmax_requalification.py",ROOT/"tasks/fla_vmax_requalification_protocol_2026_11_09.md",
           parent/"manifest.json",parent/"execution_design.json",parent/"observations.json"]
    sources=[]
    for spec in plan["sources"]:
        archive=ROOT/spec["archive"]
        verify_archive(archive)
        source=verify_inputs(archive)
        for field in ("parameters","initial","kinetics","structure_modes","GEM_commit"):
            require(source[field]==f[field],f"source model mismatch: {spec['id']}/{field}")
        for field in ("groups","factor_bounds","source_aliases","working_allowance_fraction","zero_band_absolute_allowance_mM"):
            require(source["design"][field]==f["design"][field],"source parameter box or guard contract mismatch")
        require(source["temporal"]==f["temporal"] and read(archive/"observations.json")==obs,"source time/observation/guard mismatch")
        for field in ("hematocrit","availability_threshold_mM","negative_tolerance_mM"):
            require(source["numeric"][field]==f["numeric"][field],"source numerical/phase context mismatch")
        trace=archive/spec["trace"]
        sources.append((spec["id"],[json.loads(s) for s in trace.read_text().splitlines()]))
        paths.extend([archive/"manifest.json",archive/"execution_design.json",archive/"observations.json",trace])
    candidates=rejected_registry(f,sources,plan["maximum_candidates"])
    require(len(candidates)==16 and sum(len(c["occurrences"]) for c in candidates)==16,"expected sixteen literal recent rejects")
    controls=[{"id":"fixed_reference","role":"control","log_factors":[0.]*len(f["profile_center"])},
              {"id":"working_center","role":"control","log_factors":f["profile_center"]}]
    for c in controls:c["parameters"]=exact_parameters(f,c["log_factors"])
    history=ROOT/plan["historical_controls"]
    verify_archive(history);verify_inputs(history)
    old_center=read(history/"validation_summary.json")["selected_Vmax"]
    require(all(controls[1]["parameters"][k]==v for k,v in old_center.items()),"working center is not the historical admitted vector")
    f["requalification_historical_folders"]={"fixed_reference":str(history/"audits/corrected_reference"),
                                            "working_center":str(history/"audits/temporal_candidate")}
    for key,label in (("fixed_reference","corrected_reference"),("working_center","temporal_candidate")):
        for profile in plan["profiles"]:
            folder=history/"audits"/label/profile
            check_seal(folder)
            paths.extend(folder/p for p in ("replay.npz","result.json","files_seal.json"))
    paths.extend([history/"manifest.json",history/"execution_design.json"])
    f["input_sha256"].update({p.relative_to(ROOT).as_posix():sha(p) for p in paths})
    out.mkdir(parents=True)
    write(out/"execution_design.json",f);write(out/"observations.json",obs)
    write(out/"cases.json",{"controls":controls,"candidates":candidates})
    write(out/"source_seal.json",{p:sha(out/p) for p in ("execution_design.json","observations.json","cases.json")})
    return f,controls,candidates


def folder_for(out,case,backend,profile):
    return out/("controls" if case["role"]=="control" else "candidates")/case["id"]/backend/profile


def run_one(out,f,case,backend,profile):
    folder=folder_for(out,case,backend,profile)
    folder.mkdir(parents=True)
    plan=f["requalification_plan"]
    p=exact_parameters(f,case["log_factors"])
    require(p==case["parameters"],"literal source parameter vector changed")
    local=threshold_context(f,plan["threshold_mM"])
    rhs,other=(rhs_for(local,p,f["temporal"]["network"],b) for b in (backend,"full" if backend=="joint" else "joint"))
    jac=BoundedJacobian(rhs,minimum_step=plan["jacobian_minimum_step_mM"][profile])
    settings=plan["profiles"][profile]
    with threadpool_limits(1):
        a,d=record_stepper(rhs,f["initial"],15,f["temporal"]["fit_days"],{**settings,"jac":jac},f["numeric"]["negative_tolerance_mM"],plan["method"])
        d["bounded_jacobian"]=jac.diagnostics();d["runtime_backend"]=backend
        d["forensic_rates"]=forensic_rates(rhs,a,d)
        np.savez_compressed(folder/"trajectory_evidence.npz",**a);write(folder/"diagnostics.json",d)
        stats,failure=None,None
        try:
            require_concentration_contract(d)
            evidence,stats=audit_recorded_solution(rhs,a,d,f["numeric"],lambda t,x:other.rates(t,x)[:2])
            np.savez_compressed(folder/"flux_evidence.npz",**evidence);write(folder/"flux_checks.json",stats)
        except ConcentrationRejected:failure={"stage":"concentration_gate","reason":"unchanged physical-support contract failed"}
        except (ValueError,RuntimeError,FloatingPointError,OverflowError) as error:failure={"stage":"flux_audit","reason":str(error)}
        if failure:write(folder/"failure.json",failure)
        result={"case":case["id"],"role":case["role"],"backend":backend,"profile":profile,"threshold_mM":plan["threshold_mM"],
                "concentration_pass":d["concentration_gate_pass"],"numerical_pass":bool(stats and stats["numerical_pass"]),
                "solver_settings":settings,"failure":failure}
        write(folder/"result.json",result)
    seal(folder)
    print(f"{case['id']} {backend}/{profile}: numerical={result['numerical_pass']}",flush=True)
    return result


def run_batch(out,f,cases,backends,trace_path):
    results=[]
    with ProcessPoolExecutor(max_workers=3) as pool,trace_path.open("x",encoding="utf-8") as stream:
        jobs=[pool.submit(run_one,out,f,c,b,p) for c in cases for b in backends for p in f["requalification_plan"]["profiles"]]
        for future in as_completed(jobs):
            r=future.result();results.append(r)
            stream.write(json.dumps(r,allow_nan=False)+"\n");stream.flush()
    return results


def compare_files(a_path,b_path,f):
    if not a_path.exists() or not b_path.exists():return {"pass":False,"reason":"missing validated flux evidence"}
    with np.load(a_path) as a,np.load(b_path) as b:
        return compare_replays(a,b,f["numeric"],f["threshold_plan"],f["temporal"]["fit_days"])


def historical_metrics(f,obs):
    panel=panel_from_observations(obs,f["temporal"]["fit_days"],f["design"])
    reference={}
    for profile in f["requalification_plan"]["profiles"]:
        folder=Path(f["requalification_historical_folders"]["fixed_reference"])/profile
        check_seal(folder)
        with np.load(folder/"replay.npz") as a:
            i=np.searchsorted(a["time"],panel["days"])
            require(np.array_equal(a["time"][i],panel["days"]),"historical support changed")
            reference[profile]=measure(a["states"][np.ix_([a["pool_names"].tolist().index(p) for p in panel["names"]],i)],panel)
    return panel,reference


def score_file(folder,f,panel,reference):
    if not (folder/"flux_evidence.npz").exists():return None
    with np.load(folder/"flux_evidence.npz") as a:
        ids=np.searchsorted(a["time"],panel["days"])
        x=a["states"][np.ix_([a["pool_names"].tolist().index(p) for p in panel["names"]],ids)]
    try:return scored(x,reference,panel,f)
    except ValueError:return None


def control_decision(out,f,controls):
    checks={}
    numerical={}
    panel,ref=historical_metrics(f,read(out/"observations.json"))
    center_scores={}
    for c in controls:
        key=c["id"]
        for b in f["requalification_plan"]["control_backends"]:
            for p in f["requalification_plan"]["profiles"]:
                numerical[key+"/"+b+"/"+p]=read(folder_for(out,c,b,p)/"result.json")["numerical_pass"]
            checks[key+"/"+b+"/paired"]=compare_files(folder_for(out,c,b,"strict")/"flux_evidence.npz",folder_for(out,c,b,"ultrastrict")/"flux_evidence.npz",f)
        for p in f["requalification_plan"]["profiles"]:
            new=folder_for(out,c,"full",p)/"flux_evidence.npz"
            checks[key+"/"+p+"/historical"]=compare_files(new,Path(f["requalification_historical_folders"][key])/p/"replay.npz",f)
            checks[key+"/"+p+"/backend"]=compare_files(new,folder_for(out,c,"joint",p)/"flux_evidence.npz",f)
            if key=="working_center":
                for b in f["requalification_plan"]["control_backends"]:
                    center_scores[b+"/"+p]=score_file(folder_for(out,c,b,p),f,panel,ref[p])
    guards=all(s is not None and s["reserved_guards_pass"] for s in center_scores.values())
    return {"pass":bool(all(numerical.values()) and all(c["pass"] for c in checks.values()) and guards),
            "numerical":numerical,"comparisons":checks,"working_center_scores":center_scores,
            "working_center_original_guards_pass":guards,"threshold_mM":f["requalification_plan"]["threshold_mM"]}


def run_controls(out):
    f,controls,_=prepare(out)
    run_batch(out,f,controls,f["requalification_plan"]["control_backends"],out/"control_trace.jsonl")
    gate=control_decision(out,f,controls)
    write(out/"control_gate.json",gate);seal(out/"controls")
    write(out/"control_certificate.json",{"control_gate_sha256":sha(out/"control_gate.json"),"controls_seal_sha256":sha(out/"controls/files_seal.json")})
    verify_inputs(out)
    return {"step1_control_gate_pass":gate["pass"],"new_integrations":8}


def run_candidates(out,receipt):
    f=verify_inputs(out)
    require(not (out/"candidates").exists(),"preserve any partial requalification; use successor")
    check_seal(out/"controls");check_seal(receipt)
    proof=read(receipt/"verification.json")
    cert=read(out/"control_certificate.json")
    require(proof["verified"] and proof["control_gate_pass"] and proof["control_certificate_sha256"]==sha(out/"control_certificate.json"),"independent control certificate required")
    require(cert["control_gate_sha256"]==sha(out/"control_gate.json") and cert["controls_seal_sha256"]==sha(out/"controls/files_seal.json"),"control certificate changed")
    cases=read(out/"cases.json")["candidates"]
    write(out/"candidate_authorization.json",{"receipt":str(receipt),"receipt_seal_sha256":sha(receipt/"files_seal.json"),"control_certificate_sha256":sha(out/"control_certificate.json")})
    run_batch(out,f,cases,[f["requalification_plan"]["candidate_backend"]],out/"candidate_trace.jsonl")
    panel,reference=historical_metrics(f,read(out/"observations.json"))
    result={}
    for case in cases:
        backend=f["requalification_plan"]["candidate_backend"]
        statuses={p:read(folder_for(out,case,backend,p)/"result.json") for p in f["requalification_plan"]["profiles"]}
        paired=compare_files(folder_for(out,case,backend,"strict")/"flux_evidence.npz",folder_for(out,case,backend,"ultrastrict")/"flux_evidence.npz",f)
        scores={p:score_file(folder_for(out,case,backend,p),f,panel,reference[p]) for p in f["requalification_plan"]["profiles"]}
        classification=classify_candidate({p:s["numerical_pass"] for p,s in statuses.items()},paired["pass"],scores,within_original_box(f,case["log_factors"]))
        result[case["id"]]={"statuses":statuses,"paired":paired,"scores":scores,"classification":classification}
    ranking=sorted([key for key,r in result.items() if r["classification"]["rankable"]],key=lambda key:(
        max(s["absolute"]["objective"] for s in result[key]["scores"].values()),max(s["objective"] for s in result[key]["scores"].values())))
    write(out/"summary.json",{"new_integrations":8+2*len(cases),"controls_pass":True,"candidates":result,"admissible_ranking":ranking,
          "historical_guard_caps_recomputed":False,"optimization_executed":False,"production_promoted":False,"J46_replayed":False})
    verify_inputs(out)
    write(out/"manifest.json",{p.relative_to(out).as_posix():sha(p) for p in out.rglob("*") if p.is_file()})
    return {"step2_candidates":len(cases),"categories":{k:r["classification"]["category"] for k,r in result.items()},"admissible_ranking":ranking}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--out",type=Path,required=True)
    p.add_argument("--candidates",action="store_true");p.add_argument("--control-receipt",type=Path)
    a=p.parse_args()
    with threadpool_limits(1):
        if a.candidates:
            require(a.control_receipt is not None,"independent control receipt path required")
            print(run_candidates(a.out.resolve(),a.control_receipt.resolve()))
        else:print(run_controls(a.out.resolve()))
