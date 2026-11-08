"""Profile the PGK/NDPK limits with all other capacities frozen."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import json

import numpy as np
from threadpoolctl import threadpool_limits

from run_temporal_vmax import (ROOT,check_seal,integrate_free,measure,original,
    panel_from_observations,parameters_for,read,require,rhs_for,seal,sha,verify_inputs,within,write,write_csv)
from fla_absolute_vmax import evaluate_screen
from fla_pgk_ndpk_profile import audit_roles,ndpk_column,profile_cases

CONFIG=ROOT/"config/fla_pgk_ndpk_profile_2026_11_07.json"


def verify_archive(folder):
    actual={p.relative_to(folder).as_posix():sha(p) for p in folder.rglob("*") if p.is_file() and p!=folder/"manifest.json"}
    require(actual==read(folder/"manifest.json"),"archive manifest mismatch")


def reserve_for(reference,panel,f):
    base=evaluate_screen(reference["prediction_mM"],reference,panel,f["design"],f["temporal"],f["absolute_targets"])
    return np.array([0 if k.startswith("date_gain:") else -v*f["temporal"]["reserve_fraction"]
                     for k,v in base["feasibility_guards"].items()])


def scored(prediction,reference,panel,f):
    r=evaluate_screen(prediction,reference,panel,f["design"],f["temporal"],f["absolute_targets"])
    r["reserved_guards_pass"]=bool(np.all(np.array(list(r["feasibility_guards"].values()))<=-.5*reserve_for(reference,panel,f)))
    return r


def prepare(out):
    require(not out.exists(),"fresh profile successor required")
    plan=read(CONFIG)
    parent=ROOT/plan["parent_archive"]
    verify_archive(parent)
    f=verify_inputs(parent)
    check_seal(parent/"fit")
    require(not any(plan[k] for k in ("production_promotion_allowed","optimization_executed","J46_replayed")),"diagnostic-only contract changed")
    f["pgk_ndpk"]=plan
    f["profile_center"]=read(parent/"fit/result.json")["selected"]["log_factors"]
    cases=profile_cases(f)
    require(len(cases)==26,"registered grid must have 25 points plus control")
    require(f["design"]["groups"]["NDPK"]==["vmax_VNDPK","vmax_VNDPK_rev"],"shared forward/reverse capacity group changed")
    obs=read(parent/"observations.json")
    require("GDP" not in obs["values"] and "GTP" not in obs["values"] and "GMP" in obs["values"],"revisit nucleotide observation status")
    for label in ("corrected_reference","temporal_candidate"):
        for profile in ("strict","ultrastrict"):
            check_seal(parent/"audits"/label/profile)
    paths=[CONFIG,Path(__file__),ROOT/"src/fla_pgk_ndpk_profile.py",ROOT/"qa/test_fla_pgk_ndpk_profile.py",
           ROOT/"scripts/verify_pgk_ndpk_profile.py",ROOT/"tasks/fla_pgk_ndpk_profile_protocol_2026_11_07.md",
           parent/"manifest.json",parent/"fit/result.json",parent/"execution_design.json",parent/"validation_summary.json"]
    f["input_sha256"].update({p.relative_to(ROOT).as_posix():sha(p) for p in paths})
    out.mkdir(parents=True)
    write(out/"execution_design.json",f)
    write(out/"observations.json",obs)
    write(out/"cases.json",cases)
    write(out/"source_seal.json",{p:sha(out/p) for p in ("execution_design.json","observations.json","cases.json")})
    return f


def evaluate_point(f,case,names):
    try:
        rhs=rhs_for(f,parameters_for(f,case["log_factors"]),f["temporal"]["network"])
        ndpk_column(rhs.matrix,list(rhs.names),list(rhs.reactions))
        days=f["temporal"]["fit_days"]
        with threadpool_limits(1):
            sol,_,_,minimum=integrate_free(rhs,f["initial"],15,days,f["design"]["fit_profile"],f["numeric"]["negative_tolerance_mM"])
        x=sol.sol(days)
        sample=[rhs.rates(t,state)[:2] for t,state in zip(days,x.T)]
        reaction_ids=[rhs.reactions.index(r) for r in f["pgk_ndpk"]["sampled_reactions"]]
        return {"valid":True,"prediction_mM":x[[rhs.names.index(k) for k in names]].tolist(),
                "minimum_checked_mM":minimum,"diagnostic_states_mM":{p:x[rhs.names.index(p)].tolist() for p in f["pgk_ndpk"]["diagnostic_pools"]},
                "sampled_raw_rates":np.array([s[0][reaction_ids] for s in sample]).T.tolist(),
                "sampled_executed_rates":np.array([s[1][reaction_ids] for s in sample]).T.tolist()}
    except (ValueError,RuntimeError,FloatingPointError,OverflowError) as error:
        return {"valid":False,"error":str(error)}


def screen(out):
    f=prepare(out)
    cases=read(out/"cases.json")
    panel=panel_from_observations(read(out/"observations.json"),f["temporal"]["fit_days"],f["design"])
    anchor=evaluate_point(f,cases[0],panel["names"])
    require(anchor["valid"],"same-network reference failed")
    reference=measure(anchor["prediction_mM"],panel)
    folder=out/"screen"
    folder.mkdir()
    rows=[]
    with ProcessPoolExecutor(max_workers=3) as pool,(folder/"trace.jsonl").open("x",encoding="utf-8") as stream:
        def record(case,result):
            row={"attempt":len(rows)+1,**case,**result}
            if row["valid"]:
                try:
                    row.update(scored(result["prediction_mM"],reference,panel,f))
                except ValueError as error:
                    row.update(valid=False,error=str(error))
            rows.append(row)
            stream.write(json.dumps(row,allow_nan=False)+"\n")
            stream.flush()
            if len(rows)%5==0:
                print(f"Profile: {len(rows)}/26 ODE points recorded",flush=True)
        record(cases[0],anchor)
        jobs={c["id"]:pool.submit(evaluate_point,f,c,panel["names"]) for c in cases[1:]}
        for case in cases[1:]:
            record(case,jobs[case["id"]].result())
    roles=audit_roles(rows,f)
    center=next(c["id"] for c in cases if c["log_factors"]==f["profile_center"])
    write(folder/"result.json",{"attempts":len(rows),"valid":sum(r["valid"] for r in rows),"roles":roles,
          "center_id":center,"same_reference":reference,"optimization_executed":False,"production_promoted":False})
    seal(folder)
    verify_inputs(out)
    return {"attempts":len(rows),"valid":sum(r["valid"] for r in rows),"roles":roles}


def original_safe(out,f,case,profile):
    try:
        result=original(out,f,case["id"],profile,case["log_factors"])
        return {"completed":True,"stats":result}
    except (ValueError,RuntimeError,FloatingPointError,OverflowError) as error:
        folder=out/"audits"/case["id"]/profile
        folder.mkdir(parents=True,exist_ok=True)
        result={"completed":False,"error":str(error)}
        write(folder/"failure.json",result)
        seal(folder)
        return result


def audit(out):
    require(not (out/"audit_summary.json").exists() and not (out/"audits").exists(),"preserve interrupted audit; use successor")
    f=verify_inputs(out)
    check_seal(out/"screen")
    screen=read(out/"screen/result.json")
    rows=[json.loads(s) for s in (out/"screen/trace.jsonl").read_text().splitlines()]
    by_id={r["id"]:r for r in rows}
    parent=ROOT/f["pgk_ndpk"]["parent_archive"]
    locations={"fixed_reference":{"reused":True,"folder":str(parent/"audits/corrected_reference")},
               screen["center_id"]:{"reused":True,"folder":str(parent/"audits/temporal_candidate")}}
    selected=list(dict.fromkeys(r for r in screen["roles"].values() if r is not None and by_id[r]["valid"] and r not in locations))
    require(len(selected)<=f["pgk_ndpk"]["maximum_new_audit_profiles"],"registered audit-role cap exceeded")
    statuses={}
    with ProcessPoolExecutor(max_workers=3) as pool:
        jobs={pool.submit(original_safe,out,f,by_id[key],profile):(key,profile) for key in selected for profile in ("strict","ultrastrict")}
        for future in as_completed(jobs):
            key,profile=jobs[future]
            statuses.setdefault(key,{})[profile]=future.result()
    locations.update({key:{"reused":False,"folder":str(out/"audits"/key)} for key in selected})
    panel=panel_from_observations(read(out/"observations.json"),f["temporal"]["fit_days"],f["design"])
    def prediction(folder,profile):
        check_seal(folder/profile)
        with np.load(folder/profile/"replay.npz") as a:
            ids=np.searchsorted(a["time"],panel["days"])
            require(np.array_equal(a["time"][ids],panel["days"]) and np.array_equal(a["accepted_states"][:,0],f["initial"]),"J1 or sample dates changed")
            return a["states"][np.ix_([a["pool_names"].tolist().index(p) for p in panel["names"]],ids)]
    references={p:measure(prediction(Path(locations["fixed_reference"]["folder"]),p),panel) for p in ("strict","ultrastrict")}
    results={}
    for key,location in locations.items():
        folder=Path(location["folder"])
        result={"reused":location["reused"],"inside_previous_box":by_id[key]["inside_previous_box"],"profiles":{}}
        for profile in ("strict","ultrastrict"):
            status=statuses.get(key,{}).get(profile,{"completed":True})
            result["profiles"][profile]=status
            if status["completed"]:
                status["stats"]=read(folder/profile/"result.json")
                status["score"]=scored(prediction(folder,profile),references[profile],panel,f)
        complete=all(r["completed"] for r in result["profiles"].values())
        checks=[]
        if complete:
            with np.load(folder/"strict/replay.npz") as a,np.load(folder/"ultrastrict/replay.npz") as b:
                require(np.array_equal(a["time"],b["time"]),"cross-tolerance support changed")
                checks=[within(a[k],b[k],f["numeric"],"comparison") for k in ("states","raw8","executed8")]
        result["numerical_pass"]=bool(complete and all(v.all() for v in checks) and all(r["stats"]["numerical_pass"] for r in result["profiles"].values()))
        result["cross_passed"]=sum(int(v.sum()) for v in checks)
        result["cross_total"]=sum(v.size for v in checks)
        result["within_old_box_and_guard_contract"]=bool(result["numerical_pass"] and result["inside_previous_box"] and all(r["score"]["reserved_guards_pass"] for r in result["profiles"].values()))
        result["absolute_target_admissible"]=bool(result["within_old_box_and_guard_contract"] and all(r["score"]["absolute"]["target_pass"] for r in result["profiles"].values()))
        results[key]=result
    write(out/"audit_summary.json",{"locations":locations,"results":results,"new_original_replays_attempted":2*len(selected),
          "reused_original_replays":4,"production_promoted":False,"optimization_executed":False,"J46_replayed":False})
    verify_inputs(out)
    write(out/"manifest.json",{p.relative_to(out).as_posix():sha(p) for p in out.rglob("*") if p.is_file()})
    return {"new_replays":2*len(selected),"audited_points":len(results),"absolute_target_admissible":{k:r["absolute_target_admissible"] for k,r in results.items()}}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--audit",action="store_true")
    args=parser.parse_args()
    with threadpool_limits(1):
        print(audit(args.out.resolve()) if args.audit else screen(args.out.resolve()))
