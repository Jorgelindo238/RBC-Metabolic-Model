"""Vmax-only absolute J15 ATP/ADP search with the qualified engine inside the search.

Stages: default = prepare, two controls, recomputed sensitivities and guarded
trust-region rounds; ``--audit`` = strict/ultrastrict evidence for the selected
point and the registered classification. Never run against an existing folder.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path

import numpy as np
import scipy
from threadpoolctl import threadpool_limits

from run_vmax_requalification import (ROOT,check_seal,compare_files,exact_parameters,folder_for,historical_metrics,
    panel_from_observations,read,require,rhs_for,run_one,score_file,scored,seal,sha,verify_archive,verify_inputs,
    within_original_box,write)
from run_pgk_ndpk_profile import reserve_for
from fla_temporal_vmax import lp_step
from fla_stepper_diagnostics import record_stepper
from fla_bounded_jacobian import BoundedJacobian
from fla_reaction_threshold import threshold_context
from fla_vmax_corrected_search import (check_plan,classify,controls_agree,difference_points,feasible,
    finite_differences,near_active,select)

CONFIG=ROOT/"config/fla_vmax_corrected_search_2026_11_10.json"
PROTOCOL=ROOT/"tasks/fla_vmax_corrected_search_protocol_2026_11_10.md"
CENTER_RECEIPT=ROOT/"output/vmax_requalification_validation_2026_11_09"
CONTROLS=("fixed_reference","working_center")
REJECTED="negative or nonfinite checked concentration"


def sealed_control(parent,key,profile):
    return parent/"controls"/key/"joint"/profile


def prepare(out):
    require(not out.exists(),"fresh corrected-search campaign required")
    plan=read(CONFIG)
    require(scipy.__version__==plan["scipy_version"],"tested SciPy runtime required")
    parent=ROOT/plan["numerical_parent"]
    verify_archive(parent)
    f=verify_inputs(parent)
    check_plan(plan,f)
    require(f["requalification_historical_folders"]["fixed_reference"]==str(ROOT/plan["historical_controls"]/"audits/corrected_reference"),
            "guard reference is not the historical full control")
    check_seal(CENTER_RECEIPT)
    center=read(CENTER_RECEIPT/"center_comparison.json")
    require(center["center_worst_absolute_gap"]==plan["center_worst_profile_absolute_gap"]
            and center["center_worst_day_ratio"]==plan["center_worst_dated_ratio"],"registered center comparator changed")
    lo,hi=np.log([f["design"]["factor_bounds"][k] for k in f["design"]["groups"]]).T
    x=np.array(f["profile_center"])
    require(x.shape==lo.shape and np.all(x>=lo-1e-12) and np.all(x<=hi+1e-12),"working center left the original box")
    f["corrected_search_plan"]=plan
    obs=read(parent/"observations.json")
    paths=[CONFIG,PROTOCOL,Path(__file__),ROOT/"scripts/verify_vmax_corrected_search.py",ROOT/"src/fla_vmax_corrected_search.py",
           ROOT/"qa/test_fla_vmax_corrected_search.py",parent/"manifest.json",parent/"execution_design.json",
           parent/"observations.json",CENTER_RECEIPT/"center_comparison.json",CENTER_RECEIPT/"files_seal.json"]
    for key in CONTROLS:
        folder=sealed_control(parent,key,plan["search_profile"])
        check_seal(folder)
        require(read(folder/"result.json")["numerical_pass"],"sealed control was not numerically admitted")
        paths.extend([folder/"flux_evidence.npz",folder/"files_seal.json"])
    f["input_sha256"].update({p.relative_to(ROOT).as_posix():sha(p) for p in paths})
    out.mkdir(parents=True)
    write(out/"execution_design.json",f);write(out/"observations.json",obs)
    write(out/"source_seal.json",{p:sha(out/p) for p in ("execution_design.json","observations.json")})
    return f


def attempt_folder(out,attempt):
    return out/"search"/f"attempt_{attempt:03d}"


def evaluate(out,f,attempt,vector):
    """One actual strict integration. Valid rows keep the fit-date states and the full
    per-species support diagnostics; rejected rows keep the whole recorded trajectory."""
    out=Path(out)
    plan=f["corrected_search_plan"]
    profile=plan["search_profile"]
    folder=attempt_folder(out,attempt)
    folder.mkdir(parents=True)
    p=exact_parameters(f,vector)
    rhs=rhs_for(threshold_context(f,plan["threshold_mM"]),p,f["temporal"]["network"],plan["search_backend"])
    jac=BoundedJacobian(rhs,minimum_step=plan["jacobian_minimum_step_mM"][profile])
    days=plan["fit_days"]
    with threadpool_limits(1):
        a,d=record_stepper(rhs,f["initial"],plan["target_day"],days,{**plan["profiles"][profile],"jac":jac},
                           f["numeric"]["negative_tolerance_mM"],plan["method"])
    d["bounded_jacobian"]=jac.diagnostics();d["runtime_backend"]=plan["search_backend"]
    write(folder/"diagnostics.json",d)
    minimum=min((s["worst_finite"]["minimum_mM"] for s in d["supports"].values() if s["worst_finite"] is not None),default=None)
    if d["concentration_gate_pass"]:
        ids=np.searchsorted(a["time"],days)
        require(np.array_equal(a["time"][ids],days),"registered fit dates missing from dense support")
        states=a["states"][:,ids]
        np.savez_compressed(folder/"fit_states.npz",time=np.array(days,float),states=states,pool_names=a["pool_names"],initial=a["initial"])
        result={"valid":True,"minimum_checked_mM":minimum,"states":states,"pool_names":a["pool_names"].tolist()}
    else:
        np.savez_compressed(folder/"trajectory_evidence.npz",**a)
        result={"valid":False,"error":REJECTED,"minimum_checked_mM":minimum,
                "first_violation":{k:s["first_sampled_policy_violation"] for k,s in d["supports"].items()},
                "solver_exception":d["exception"]}
    seal(folder)
    return result


def control_gate(out,f,rows,panel,reference):
    plan=f["corrected_search_plan"]
    parent=ROOT/plan["numerical_parent"]
    checks={}
    for key,row in zip(CONTROLS,rows):
        if not row["valid"]:
            checks[key]={"pass":False,"reason":row["error"]}
            continue
        with np.load(sealed_control(parent,key,plan["search_profile"])/"flux_evidence.npz") as a:
            ids=np.searchsorted(a["time"],panel["days"])
            require(np.array_equal(a["time"][ids],panel["days"]),"sealed control support changed")
            old=a["states"][np.ix_([a["pool_names"].tolist().index(p) for p in panel["names"]],ids)]
        checks[key]=controls_agree(row["prediction_mM"],old,f["numeric"]["comparison_atol_mM"],f["numeric"]["comparison_rtol"])
    center=rows[1]
    guards=bool(feasible(center))
    return {"pass":bool(all(c["pass"] for c in checks.values()) and guards),"comparisons":checks,
            "working_center_original_reserved_guards_pass":guards,"integrations":len(rows)}


def search(out):
    f=prepare(out)
    plan,d=f["corrected_search_plan"],f["design"]
    obs=read(out/"observations.json")
    panel,references=historical_metrics(f,obs)
    require(list(panel["days"])==plan["fit_days"],"fit dates changed")
    reference=references[plan["search_profile"]]
    reserve=reserve_for(reference,panel,f)
    lo,hi=np.log([d["factor_bounds"][k] for k in d["groups"]]).T
    folder=out/"fit";folder.mkdir()
    trace,cache,steps=[],{},[]
    with ProcessPoolExecutor(max_workers=3) as pool,(folder/"trace.jsonl").open("x",encoding="utf-8") as stream:
        def batch(vectors,stage):
            vectors=[tuple(float(v) for v in np.clip(x,lo,hi)) for x in vectors]
            new=[v for v in dict.fromkeys(vectors) if v not in cache]
            require(len(trace)+len(new)<=plan["maximum_search_attempts"],"registered search budget exceeded")
            jobs=[(v,len(trace)+1+i,pool.submit(evaluate,str(out),f,len(trace)+1+i,v)) for i,v in enumerate(new)]
            for v,attempt,future in jobs:
                raw=future.result()
                row={"attempt":attempt,"stage":stage,"log_factors":list(v),"valid":raw["valid"],
                     "minimum_checked_mM":raw["minimum_checked_mM"],"inside_original_box":within_original_box(f,v)}
                if raw["valid"]:
                    x=raw["states"][[raw["pool_names"].index(p) for p in panel["names"]]]
                    row["prediction_mM"]=x.tolist()
                    try:
                        row.update(scored(x,reference,panel,f))
                    except ValueError as error:
                        row.update(valid=False,error="observation domain: "+str(error))
                else:
                    row.update({k:raw[k] for k in ("error","first_violation","solver_exception")})
                trace.append(row);cache[v]=row
                stream.write(json.dumps(row,allow_nan=False)+"\n");stream.flush()
            return [cache[v] for v in vectors]

        controls=batch([np.zeros(len(lo)),np.array(f["profile_center"])],"controls")
        gate=control_gate(out,f,controls,panel,reference)
        write(out/"control_gate.json",gate)
        print(f"Step 1 controls: pass={gate['pass']}",flush=True)
        if gate["pass"]:
            current=controls[1]
            radius=plan["initial_radius_log"]
            for it in range(plan["number_of_rounds"]):
                x=np.array(current["log_factors"])
                diffs=batch(difference_points(x,lo,hi,plan["difference_step_log"]),f"round{it+1}_sensitivity")
                r0,g0=current["absolute"]["sides"],current["feasibility_guards"]
                jr,jg,good=finite_differences(x,r0,g0,diffs)
                write(folder/f"sensitivity_round{it+1}.json",{"round":it+1,"anchor":current["attempt"],
                      "difference_attempts":[r["attempt"] for r in diffs],"groups":list(d["groups"]),
                      "sides":list(r0),"guards":list(g0),"valid_derivatives":len(good),"valid_coordinates":good,
                      "side_jacobian":jr.tolist(),"guard_jacobian":jg.tolist(),
                      "guards_within_reserve":near_active(g0,reserve),"local_finite_difference_only":True})
                if not good:
                    steps.append({"round":it+1,"status":"no_valid_direction"})
                    break
                a,b=lo.copy(),hi.copy()
                missing=sorted(set(range(len(x)))-set(good))
                a[missing]=b[missing]=x[missing]
                proposal=lp_step(x,a,b,radius,np.array(list(r0.values())),jr,np.array(list(g0.values())),jg,reserve)
                step={"round":it+1,"radius":radius,"anchor":current["attempt"],"valid_derivatives":len(good),
                      "frozen_coordinates":missing,"linearized_proposal":proposal,"accepted":None}
                if proposal is not None and proposal["predicted_objective"]<current["absolute"]["objective"]:
                    tried=batch([x+alpha*np.array(proposal["delta"]) for alpha in plan["line_search_fractions"]],f"round{it+1}_backtrack")
                    step["candidate_attempts"]=[r["attempt"] for r in tried]
                    passed=[r for r in tried if feasible(r) and r["absolute"]["objective"]<=current["absolute"]["objective"]-plan["minimum_step_objective_gain"]]
                    if passed:
                        current=min(passed,key=lambda r:(r["absolute"]["objective"],r["attempt"]))
                        step["accepted"]=current["attempt"]
                radius=min(plan["maximum_radius_log"],radius*1.25) if step["accepted"] else radius*.5
                steps.append(step)
                print(f"Round {it+1}: {len(trace)} attempts, accepted={step['accepted']}, gap={current['absolute']['objective']:.8g}",flush=True)
    result={"actual_attempts":len(trace),"invalid_attempts":sum(not r["valid"] for r in trace),
            "maximum_attempts":plan["maximum_search_attempts"],"control_gate_pass":gate["pass"],
            "control_attempts":{"fixed_reference":1,"working_center":2},"steps":steps,
            "guard_reference_recomputed":False,"global_optimality":False}
    if gate["pass"]:
        selected=select(trace)
        result.update(selected=selected,selected_is_working_center=selected["attempt"]==2,
                      absolute_target_attained_in_search=selected["absolute"]["target_pass"])
    write(folder/"result.json",result)
    seal(folder)
    verify_inputs(out)
    if not gate["pass"]:
        write(out/"manifest.json",{p.relative_to(out).as_posix():sha(p) for p in out.rglob("*") if p.is_file()})
        return {"control_gate_pass":False,"attempts":len(trace),"stopped":"controls failed; no search executed"}
    return {"control_gate_pass":True,"attempts":len(trace),"selected_attempt":selected["attempt"],
            "search_gap":selected["absolute"]["objective"],"concentrations_mM":selected["absolute"]["concentrations_mM"]}


def audit(out):
    f=verify_inputs(out)
    plan=f["corrected_search_plan"]
    require(not (out/"candidates").exists() and not (out/"summary.json").exists() and not (out/"manifest.json").exists(),
            "preserve any partial or closed audit; use a successor")
    check_seal(out/"fit")
    result=read(out/"fit/result.json")
    require(result["control_gate_pass"],"controls failed; nothing to audit")
    selected=result["selected"]
    center=result["selected_is_working_center"]
    case={"id":"selected","role":"candidate","log_factors":selected["log_factors"],
          "parameters":exact_parameters(f,selected["log_factors"]),"search_attempt":selected["attempt"]}
    inside=within_original_box(f,case["log_factors"])
    statuses,scores,paired={}, {}, None
    if not center:
        write(out/"cases.json",{"candidates":[case]})
        with ProcessPoolExecutor(max_workers=2) as pool:
            jobs={p:pool.submit(run_one,out,f,case,plan["search_backend"],p) for p in plan["audit_profiles"]}
            statuses={p:j.result() for p,j in jobs.items()}
        panel,reference=historical_metrics(f,read(out/"observations.json"))
        folders={p:folder_for(out,case,plan["search_backend"],p) for p in plan["audit_profiles"]}
        paired=compare_files(folders["strict"]/"flux_evidence.npz",folders["ultrastrict"]/"flux_evidence.npz",f)
        scores={p:score_file(folders[p],f,panel,reference[p]) for p in plan["audit_profiles"]}
    decision=classify({p:s["numerical_pass"] for p,s in statuses.items()},bool(paired and paired["pass"]),scores,inside,plan,center)
    write(out/"summary.json",{"selected_attempt":selected["attempt"],"selected_is_working_center":center,
          "new_audit_integrations":len(statuses),"statuses":statuses,"paired":paired,"scores":scores,
          "inside_original_box":inside,"classification":decision,"selected_Vmax":{k:case["parameters"][k] for k in f["resolved_capacities"]},
          "center_worst_profile_absolute_gap":plan["center_worst_profile_absolute_gap"],
          "center_worst_dated_ratio":plan["center_worst_dated_ratio"],"guard_reference_recomputed":False,
          "bounds_expanded":False,"Km_changed":False,"production_promoted":False,"J46_replayed":False})
    verify_inputs(out)
    write(out/"manifest.json",{p.relative_to(out).as_posix():sha(p) for p in out.rglob("*") if p.is_file()})
    return {"audit_integrations":len(statuses),"classification":decision}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True);p.add_argument("--audit",action="store_true")
    a=p.parse_args()
    with threadpool_limits(1):
        print(audit(a.out.resolve()) if a.audit else search(a.out.resolve()))
