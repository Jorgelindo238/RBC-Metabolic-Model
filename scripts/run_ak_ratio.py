"""Fixed-kinetics adenylate kinase forward/reverse ratio diagnostic at the working center.

Six J1-J15 integrations (three arms, two profiles). Only vmax_VAK and
vmax_VAK_rev differ from the working center. The control is the sealed
requalification control and is never reintegrated. No retry, no calibration.
``--dry`` derives and prints the arms without creating an archive or
integrating anything.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import scipy

from run_vmax_requalification import (ROOT,check_seal,compare_files,exact_parameters,folder_for,historical_metrics,
    read,require,rhs_for,run_one,sha,verify_archive,verify_inputs,write,write_csv)
from run_pgk_ndpk_profile import reserve_for
from run_guanylate_partition import describe
from fla_reaction_threshold import threshold_context
from fla_ak_ratio import FORWARD,REVERSE,arm_capacities,arm_parameters,balance_ratio,check_plan,classify

CONFIG=ROOT/"config/fla_ak_ratio_2026_11_11.json"
PROTOCOL=ROOT/"tasks/fla_ak_ratio_protocol_2026_11_11.md"


def raw_rate_function(f,center,backend,reaction):
    """Raw coded rate of one reaction at the frozen J1 state as a function of the two AK capacities."""
    context=threshold_context(f,f["numeric"]["availability_threshold_mM"])
    state=np.array(f["initial"],float)
    def raw(forward,reverse):
        rhs=rhs_for(context,arm_parameters(center,forward,reverse),f["temporal"]["network"],backend)
        return float(rhs.rates(1.,state)[0][list(rhs.reactions).index(reaction)])
    return raw


def build_arms(f,plan,center):
    raw,compiled=(raw_rate_function(f,center,b,plan["balance_reaction"]) for b in ("full",plan["backend"]))
    middle=(center[FORWARD],center[REVERSE])
    base=(f["parameters"][FORWARD],f["parameters"][REVERSE])
    bounds=f["design"]["factor_bounds"][plan["bound_group"]]
    require(f["design"]["groups"][plan["bound_group"]]==plan["changed_parameters"] and set(plan["changed_parameters"])<=set(f["resolved_capacities"]),
            "registered capacity group changed")
    ratio=balance_ratio(raw,*middle,plan["linearity_abs_tolerance"])
    require(abs(ratio/plan["expected_balance_ratio"]-1)<=plan["expected_relative_tolerance"],"balancing ratio differs from the registered value")
    arms={"control":{FORWARD:middle[0],REVERSE:middle[1],"ratio":middle[0]/middle[1],"factors_vs_base":[middle[0]/base[0],middle[1]/base[1]],
                     "raw_balance_reaction_J1":raw(*middle)}}
    for key,spec in plan["arms"].items():
        forward,reverse,factors=arm_capacities(spec,middle,base,ratio,bounds)
        rates=(raw(forward,reverse),compiled(forward,reverse))
        if spec["ratio"]=="balance":
            require(max(map(abs,rates))<=plan["zero_flux_abs_tolerance"],"arm does not zero the coded law on both backends")
        arms[key]={FORWARD:forward,REVERSE:reverse,"ratio":forward/reverse,"factors_vs_base":list(factors),"raw_balance_reaction_J1":rates[0],
                   "rule":{k:spec[k] for k in ("reverse","ratio")},"parameters":arm_parameters(center,forward,reverse)}
    return {"balance_ratio":ratio,"registered_factor_bounds":bounds,"arms":arms}


def design():
    """Everything derived before launch. Reads sealed evidence only; writes nothing and integrates nothing."""
    plan=read(CONFIG)
    check_plan(plan)
    parent=ROOT/plan["numerical_parent"]
    verify_archive(parent)
    f=verify_inputs(parent)
    recipe=f["requalification_plan"]
    require(scipy.__version__==recipe["scipy_version"] and list(recipe["profiles"])==plan["profiles"]
            and recipe["candidate_backend"]==plan["backend"],"qualified recipe changed")
    center=next(c for c in read(parent/"cases.json")["controls"] if c["id"]==plan["control_case"])
    require(center["log_factors"]==f["profile_center"] and center["parameters"]==exact_parameters(f,f["profile_center"]),"control is not the retained working center")
    built=build_arms(f,plan,center["parameters"])
    for key in plan["arms"]:
        case=arm_case(f,key,built["arms"][key]["parameters"])
        require(exact_parameters(arm_context(f,case["parameters"]),case["log_factors"])==case["parameters"],"replay routine would not reproduce the arm vector")
    return f,plan,parent,center,built


def prepare(out):
    require(not out.exists(),"fresh adenylate kinase diagnostic archive required")
    f,plan,parent,center,built=design()
    obs=read(parent/"observations.json")
    paths=[CONFIG,PROTOCOL,Path(__file__),ROOT/"scripts/verify_ak_ratio.py",ROOT/"scripts/run_guanylate_partition.py",
           ROOT/"src/fla_ak_ratio.py",ROOT/"src/fla_guanylate_partition.py",ROOT/"src/fla_atp_attribution.py",
           ROOT/"qa/test_fla_ak_ratio.py",parent/"manifest.json",parent/"execution_design.json",parent/"observations.json",parent/"cases.json"]
    for profile in plan["profiles"]:
        folder=parent/"controls"/plan["control_case"]/plan["backend"]/profile
        check_seal(folder)
        paths.extend(folder/p for p in ("flux_evidence.npz","files_seal.json"))
    f["ak_ratio_plan"]=plan
    f["input_sha256"].update({p.relative_to(ROOT).as_posix():sha(p) for p in paths})
    out.mkdir(parents=True)
    write(out/"execution_design.json",f);write(out/"observations.json",obs)
    write(out/"cases.json",{"parameters":center["parameters"],"log_factors":center["log_factors"],**built})
    write(out/"source_seal.json",{p:sha(out/p) for p in ("execution_design.json","observations.json","cases.json")})
    return f,plan


def arm_context(f,parameters):
    """Frozen context whose base parameters are the arm's literal vector.

    The shared replay routine rebuilds parameters from grouped log factors and
    refuses an ungrouped AK pair. Each arm is therefore replayed with its own
    literal vector as base and all log factors at zero, which that routine
    reproduces exactly. J1, Km, network and recipe are the unchanged frozen ones.
    """
    return {**f,"parameters":parameters}


def arm_case(f,key,parameters):
    return {"id":key,"role":"candidate","log_factors":[0.]*len(f["design"]["groups"]),"parameters":parameters}


def flat(description):
    j=description["ledger"]["J1_J4"]
    return {"AK":j["reactions"]["VAK"],"ATP_consumption":j["ATP_consumption_mM"],"ATP_production":j["ATP_production_mM"]}


def run(out):
    f,plan=prepare(out)
    cases=read(out/"cases.json")
    arms={k:arm_case(f,k,cases["arms"][k]["parameters"]) for k in plan["arms"]}
    with ProcessPoolExecutor(max_workers=3) as pool:
        jobs={(k,p):pool.submit(run_one,out,arm_context(f,arms[k]["parameters"]),arms[k],plan["backend"],p) for k in arms for p in plan["profiles"]}
        statuses={key:j.result() for key,j in jobs.items()}
    require(len(statuses)==plan["maximum_new_integrations"],"registered integration count changed")
    panel,references=historical_metrics(f,read(out/"observations.json"))
    reserves={p:reserve_for(references[p],panel,f) for p in plan["profiles"]}
    parent=ROOT/plan["numerical_parent"]
    control={"numerical_pass":{},"paired_pass":True,"scores":{},"details":{}}
    for p in plan["profiles"]:
        folder=parent/"controls"/plan["control_case"]/plan["backend"]/p
        d=describe(folder,f,plan,panel,references[p],reserves[p])
        control["numerical_pass"][p]=read(folder/"result.json")["numerical_pass"];control["scores"][p]=d["score"];control["details"][p]=d
    control["ledger"]=flat(control["details"]["ultrastrict"])
    results={}
    for k in arms:
        folders={p:folder_for(out,arms[k],plan["backend"],p) for p in plan["profiles"]}
        paired=compare_files(folders["strict"]/"flux_evidence.npz",folders["ultrastrict"]/"flux_evidence.npz",f)
        r={"numerical_pass":{p:statuses[(k,p)]["numerical_pass"] for p in plan["profiles"]},"paired_pass":bool(paired["pass"]),
           "paired":paired,"scores":{},"details":{},"statuses":{p:statuses[(k,p)] for p in plan["profiles"]},"ledger":None}
        for p in plan["profiles"]:
            r["scores"][p]=None
            if (folders[p]/"flux_evidence.npz").exists():
                d=describe(folders[p],f,plan,panel,references[p],reserves[p])
                r["scores"][p]=d["score"];r["details"][p]=d
        if "ultrastrict" in r["details"]:r["ledger"]=flat(r["details"]["ultrastrict"])
        results[k]=r
    decision=classify(results[plan["hypothesis_arm"]],results[plan["capacity_arm"]],results[plan["monotonicity_arm"]],control,plan["compensation_fraction"])
    write(out/"summary.json",{"control":control,"arms":results,"classification":decision,"new_integrations":len(statuses),
          "balance_ratio":cases["balance_ratio"],"arm_capacities":{k:{x:v for x,v in a.items() if x!="parameters"} for k,a in cases["arms"].items()},
          "measured_J1_changed":False,"initial_state_changed":False,"km_changed":False,"bounds_changed":False,
          "optimization_executed":False,"production_promoted":False,"J46_replayed":False})
    levels,ledger=[],[]
    for name,block in (("control",control),*results.items()):
        for p,d in block["details"].items():
            for pool,values in {**d["levels_mM"],**d["phosphoryl_stocks_mM"]}.items():
                levels.extend([name,p,pool,day,v] for day,v in zip(plan["report_days"],values))
            for label,w in d["ledger"].items():
                ledger.extend([name,p,label,r,v] for r,v in {**w["reactions"],"ATP_production":w["ATP_production_mM"],"ATP_consumption":w["ATP_consumption_mM"]}.items())
    write_csv(out/"levels_by_day.csv",["arm","profile","pool_or_stock","day","mM"],levels)
    write_csv(out/"executed_ledger.csv",["arm","profile","window","reaction_or_total","executed_integral_mM"],ledger)
    verify_inputs(out)
    write(out/"manifest.json",{p.relative_to(out).as_posix():sha(p) for p in out.rglob("*") if p.is_file()})
    return {"new_integrations":len(statuses),"classification":decision["category"],"monotone_response":decision["monotone_response"],
            "flags":{k:{x:v for x,v in fl.items() if x!="failed_guards"} for k,fl in decision["flags"].items()}}


if __name__=="__main__":
    from threadpoolctl import threadpool_limits
    p=argparse.ArgumentParser(description=__doc__)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument("--out",type=Path);group.add_argument("--dry",action="store_true")
    a=p.parse_args()
    with threadpool_limits(1):
        if a.dry:
            built=design()[4]
            print({"balance_ratio":built["balance_ratio"],"registered_factor_bounds":built["registered_factor_bounds"],
                   "arms":{k:{x:v for x,v in arm.items() if x!="parameters"} for k,arm in built["arms"].items()}})
        else:print(run(a.out.resolve()))
