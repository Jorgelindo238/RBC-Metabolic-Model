"""Fixed-kinetics latent ribose stock RIB(0) diagnostic at the working center.

Four J1-J15 integrations (two arms, two profiles). The control is the sealed
requalification control and is never reintegrated. No retry, no calibration.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import scipy

from run_vmax_requalification import (ROOT,check_seal,compare_files,exact_parameters,folder_for,historical_metrics,
    read,require,rhs_for,run_one,sha,verify_archive,verify_inputs,write,write_csv)
from run_pgk_ndpk_profile import reserve_for
from run_guanylate_partition import describe
from fla_reaction_threshold import threshold_context
from fla_ribose_stock import arm_initial,check_plan,classify,inventory

CONFIG=ROOT/"config/fla_ribose_stock_2026_11_10.json"
PROTOCOL=ROOT/"tasks/fla_ribose_stock_protocol_2026_11_10.md"


def historical_value(plan):
    frame=pd.read_excel(ROOT/plan["historical_workbook"],sheet_name=0,header=None)
    values={str(n).strip().upper():v for n,v in zip(frame.iloc[:,0],frame.iloc[:,1])}
    return float(values[plan["changed_pool"]])


def prepare(out):
    require(not out.exists(),"fresh ribose diagnostic archive required")
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
    obs=read(parent/"observations.json")
    require(plan["changed_pool"] not in obs["values"],"changed pool must be unobserved")
    rhs=rhs_for(threshold_context(f,f["numeric"]["availability_threshold_mM"]),center["parameters"],f["temporal"]["network"],"full")
    names,reactions=list(rhs.names),list(rhs.reactions)
    i=names.index(plan["changed_pool"])
    require(f["initial"][i]==plan["control_value_mM"],"frozen ribose convention is not the registered control")
    require([reactions[j] for j in np.flatnonzero(rhs.matrix[i])]==["VRKa"] and rhs.matrix[i,reactions.index("VRKa")]==-1,
            "ribose is no longer a source-free stock consumed by ribokinase only")
    require(historical_value(plan)==plan["arms"][plan["hypothesis_arm"]]["RIB_mM"],"historical workbook value differs from the registered arm")
    arms={"control":inventory(plan["control_value_mM"],plan["control_value_mM"])}
    for key,spec in plan["arms"].items():
        arms[key]={**inventory(spec["RIB_mM"],plan["control_value_mM"]),"provenance":spec["provenance"],
                   "initial":arm_initial(f["initial"],names,plan["changed_pool"],spec["RIB_mM"]).tolist()}
    paths=[CONFIG,PROTOCOL,Path(__file__),ROOT/"scripts/verify_ribose_stock.py",ROOT/"scripts/run_guanylate_partition.py",
           ROOT/"src/fla_ribose_stock.py",ROOT/"src/fla_guanylate_partition.py",ROOT/"src/fla_atp_attribution.py",
           ROOT/"qa/test_fla_ribose_stock.py",ROOT/plan["historical_workbook"],parent/"manifest.json",
           parent/"execution_design.json",parent/"observations.json",parent/"cases.json"]
    for profile in plan["profiles"]:
        folder=parent/"controls"/plan["control_case"]/plan["backend"]/profile
        check_seal(folder)
        paths.extend(folder/p for p in ("flux_evidence.npz","files_seal.json"))
    f["ribose_plan"]=plan
    f["input_sha256"].update({p.relative_to(ROOT).as_posix():sha(p) for p in paths})
    out.mkdir(parents=True)
    write(out/"execution_design.json",f);write(out/"observations.json",obs)
    write(out/"cases.json",{"parameters":center["parameters"],"log_factors":center["log_factors"],"arms":arms})
    write(out/"source_seal.json",{p:sha(out/p) for p in ("execution_design.json","observations.json","cases.json")})
    return f,plan


def flat(description):
    j=description["ledger"]["J1_J4"]
    return {"RKa":j["reactions"]["VRKa"],"ATP_consumption":j["ATP_consumption_mM"],"ATP_production":j["ATP_production_mM"]}


def run(out):
    f,plan=prepare(out)
    cases=read(out/"cases.json")
    context=lambda k:{**f,"initial":cases["arms"][k]["initial"]}
    arms={k:{"id":k,"role":"candidate","log_factors":cases["log_factors"],"parameters":cases["parameters"]} for k in plan["arms"]}
    with ProcessPoolExecutor(max_workers=3) as pool:
        jobs={(k,p):pool.submit(run_one,out,context(k),arms[k],plan["backend"],p) for k in arms for p in plan["profiles"]}
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
                d=describe(folders[p],context(k),plan,panel,references[p],reserves[p])
                r["scores"][p]=d["score"];r["details"][p]=d
        if "ultrastrict" in r["details"]:r["ledger"]=flat(r["details"]["ultrastrict"])
        results[k]=r
    decision=classify(results[plan["hypothesis_arm"]],results[plan["monotonicity_arm"]],control,plan["compensation_fraction"])
    write(out/"summary.json",{"control":control,"arms":results,"classification":decision,"new_integrations":len(statuses),
          "arm_inventories":{k:{x:v for x,v in a.items() if x!="initial"} for k,a in cases["arms"].items()},
          "measured_J1_changed":False,"parameters_changed":False,"optimization_executed":False,"production_promoted":False,"J46_replayed":False})
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
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--out",type=Path,required=True)
    with threadpool_limits(1):print(run(p.parse_args().out.resolve()))
