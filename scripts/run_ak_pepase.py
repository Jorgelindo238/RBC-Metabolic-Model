"""Fixed-kinetics adenylate kinase ratio x PEP phosphatase capacity diagnostic at the working center.

Six J1-J15 integrations (three arms, two profiles). Only vmax_VAK,
vmax_VAK_rev and vmax_VPEP_PASE differ from the working center. The control
and the balanced-AK-only arm are sealed and never reintegrated. No retry, no
calibration. ``--dry`` derives and prints the arms without creating an
archive or integrating anything.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import scipy

from run_vmax_requalification import (ROOT,check_seal,compare_files,exact_parameters,folder_for,historical_metrics,
    read,require,run_one,sha,verify_archive,verify_inputs,write,write_csv)
from run_pgk_ndpk_profile import reserve_for
from run_guanylate_partition import describe
from run_ak_ratio import arm_case,arm_context,raw_rate_function
from fla_ak_ratio import balance_ratio
from fla_ak_pepase import FORWARD,PEPASE,REVERSE,arm_parameters,arm_values,check_plan,classify

CONFIG=ROOT/"config/fla_ak_pepase_2026_11_11.json"
PROTOCOL=ROOT/"tasks/fla_ak_pepase_protocol_2026_11_11.md"


def sealed_ak(plan,center):
    """AK capacities of the sealed balanced arm; everything else in that arm must be the working center."""
    spec=plan["sealed_ak_arm"]
    cases=read(ROOT/spec["archive"]/"cases.json")
    p=cases["arms"][spec["case"]]["parameters"]
    require(cases["parameters"]==center and set(p)==set(center) and {k for k in p if p[k]!=center[k]}=={FORWARD},
            "sealed AK arm is not the working center with only the forward AK capacity lowered")
    return p[FORWARD],p[REVERSE]


def build_arms(f,plan,center):
    for group,members in plan["bound_groups"].items():
        require(f["design"]["groups"][group]==members and set(members)<=set(f["resolved_capacities"]),"registered capacity group changed")
    pair=sealed_ak(plan,center)
    ratio=balance_ratio(raw_rate_function(f,center,"full","VAK"),center[FORWARD],center[REVERSE],plan["linearity_abs_tolerance"])
    require(abs(ratio/plan["expected_balance_ratio"]-1)<=plan["expected_relative_tolerance"]
            and abs(pair[0]/pair[1]/ratio-1)<=plan["expected_relative_tolerance"],"sealed AK arm is not at the registered balancing ratio")
    middle=(center[FORWARD],center[REVERSE],center[PEPASE])
    base,bounds=f["parameters"][PEPASE],f["design"]["factor_bounds"]["PEPase"]
    arms={}
    for key,spec in plan["arms"].items():
        forward,reverse,pepase=arm_values(spec,middle,pair,base,bounds)
        arms[key]={FORWARD:forward,REVERSE:reverse,PEPASE:pepase,"AK_ratio":forward/reverse,"PEPase_factor_vs_base":pepase/base,
                   "PEPase_over_center":pepase/middle[2],"rule":{k:spec[k] for k in ("ak","pepase")},
                   "parameters":arm_parameters(center,forward,reverse,pepase)}
    return {"balance_ratio":ratio,"sealed_AK_pair":list(pair),"registered_PEPase_bounds":bounds,"PEPase_base":base,
            "center":dict(zip((FORWARD,REVERSE,PEPASE),middle)),"arms":arms}


def design():
    """Everything derived before launch. Reads sealed evidence only; writes nothing and integrates nothing."""
    plan=read(CONFIG)
    check_plan(plan)
    parent=ROOT/plan["numerical_parent"]
    verify_archive(parent);verify_archive(ROOT/plan["sealed_ak_arm"]["archive"])
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


def sealed_folders(plan,parent):
    """Sealed control and sealed balanced-AK-only folders per profile."""
    ak=plan["sealed_ak_arm"]
    case={"id":ak["case"],"role":"candidate"}
    return {"control":{p:parent/"controls"/plan["control_case"]/plan["backend"]/p for p in plan["profiles"]},
            "ak_only":{p:folder_for(ROOT/ak["archive"],case,plan["backend"],p) for p in plan["profiles"]}}


def prepare(out):
    require(not out.exists(),"fresh diagnostic archive required")
    f,plan,parent,center,built=design()
    obs=read(parent/"observations.json")
    ak=ROOT/plan["sealed_ak_arm"]["archive"]
    paths=[CONFIG,PROTOCOL,Path(__file__),ROOT/"scripts/verify_ak_pepase.py",ROOT/"scripts/run_ak_ratio.py",ROOT/"scripts/run_guanylate_partition.py",
           ROOT/"src/fla_ak_pepase.py",ROOT/"src/fla_ak_ratio.py",ROOT/"src/fla_guanylate_partition.py",ROOT/"src/fla_atp_attribution.py",
           ROOT/"qa/test_fla_ak_pepase.py",parent/"manifest.json",parent/"execution_design.json",parent/"observations.json",parent/"cases.json",
           ak/"manifest.json",ak/"cases.json",ak/"summary.json"]
    for folders in sealed_folders(plan,parent).values():
        for folder in folders.values():
            check_seal(folder)
            require(read(folder/"result.json")["numerical_pass"],"sealed reference is not numerically admitted")
            paths.extend(folder/p for p in ("flux_evidence.npz","files_seal.json"))
    f["ak_pepase_plan"]=plan
    f["input_sha256"].update({p.relative_to(ROOT).as_posix():sha(p) for p in paths})
    out.mkdir(parents=True)
    write(out/"execution_design.json",f);write(out/"observations.json",obs)
    write(out/"cases.json",{"parameters":center["parameters"],"log_factors":center["log_factors"],**built})
    write(out/"source_seal.json",{p:sha(out/p) for p in ("execution_design.json","observations.json","cases.json")})
    return f,plan


def flat(description):
    w=description["ledger"]
    total=lambda r:sum(w[label]["reactions"][r] for label in w)
    return {"PK_J1_J4":w["J1_J4"]["reactions"]["VPK"],"PEPASE_J1_J4":w["J1_J4"]["reactions"]["VPEP_PASE"],
            "PK_J1_J15":total("VPK"),"PEPASE_J1_J15":total("VPEP_PASE"),
            "ATP_consumption":w["J1_J4"]["ATP_consumption_mM"],"ATP_production":w["J1_J4"]["ATP_production_mM"]}


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
    sealed={}
    for name,folders in sealed_folders(plan,ROOT/plan["numerical_parent"]).items():
        block={"numerical_pass":{},"paired_pass":True,"scores":{},"details":{}}
        for p,folder in folders.items():
            d=describe(folder,f,plan,panel,references[p],reserves[p])
            block["numerical_pass"][p]=read(folder/"result.json")["numerical_pass"];block["scores"][p]=d["score"];block["details"][p]=d
        block["ledger"]=flat(block["details"]["ultrastrict"])
        sealed[name]=block
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
    decision=classify(results[plan["hypothesis_arm"]],results[plan["single_factor_arm"]],results[plan["monotonicity_arm"]],sealed["control"],sealed["ak_only"])
    write(out/"summary.json",{"control":sealed["control"],"ak_only":sealed["ak_only"],"arms":results,"classification":decision,"new_integrations":len(statuses),
          "arm_capacities":{k:{x:v for x,v in a.items() if x!="parameters"} for k,a in cases["arms"].items()},
          "measured_J1_changed":False,"initial_state_changed":False,"km_changed":False,"bounds_changed":False,
          "optimization_executed":False,"production_promoted":False,"J46_replayed":False})
    levels,ledger=[],[]
    for name,block in (*sealed.items(),*results.items()):
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
            print({k:(v if k!="arms" else {n:{x:y for x,y in arm.items() if x!="parameters"} for n,arm in v.items()}) for k,v in built.items()})
        else:print(run(a.out.resolve()))
