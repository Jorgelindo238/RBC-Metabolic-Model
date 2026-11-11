"""Fixed-kinetics latent guanylate partition diagnostic at the working center.

Four J1-J15 integrations (two arms, two profiles). The control is the sealed
requalification control and is never reintegrated. No retry, no calibration.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import scipy

from run_vmax_requalification import (ROOT,check_seal,compare_files,exact_parameters,folder_for,historical_metrics,
    read,require,rhs_for,run_one,score_file,sha,verify_archive,verify_inputs,write,write_csv)
from run_pgk_ndpk_profile import reserve_for
from fla_reaction_threshold import threshold_context
from fla_atp_attribution import pool_ledger,signed_integrals
from fla_guanylate_partition import arm_initial,check_plan,classify,inventory,solve_partition

CONFIG=ROOT/"config/fla_guanylate_partition_2026_11_10.json"
PROTOCOL=ROOT/"tasks/fla_guanylate_partition_protocol_2026_11_10.md"


def raw_rate_function(f,parameters,backend,reaction):
    rhs=rhs_for(threshold_context(f,f["numeric"]["availability_threshold_mM"]),parameters,f["temporal"]["network"],backend)
    names,j=list(rhs.names),list(rhs.reactions).index(reaction)
    base=np.array(f["initial"],float)
    def raw(gdp,gtp):
        x=base.copy();x[names.index("GDP")],x[names.index("GTP")]=gdp,gtp
        return float(rhs.rates(1.,x)[0][j])
    return raw,names


def build_arms(f,plan,parameters):
    raw,names=raw_rate_function(f,parameters,"full",plan["zero_flux_reaction"])
    compiled,_=raw_rate_function(f,parameters,plan["backend"],plan["zero_flux_reaction"])
    reference=(f["initial"][names.index("GDP")],f["initial"][names.index("GTP")])
    require(reference==(1.,1.),"frozen latent guanylate convention is not 1 mM each")
    arms={"control":{**inventory(*reference,reference),"raw_zero_flux_reaction_J1":raw(*reference)}}
    for key,spec in plan["arms"].items():
        gdp,gtp=solve_partition(raw,spec["convention"],spec["value_mM"],plan["zero_flux_abs_tolerance"])
        require(abs(gdp-spec["expected_GDP_mM"])<=plan["expected_tolerance_mM"] and abs(gtp-spec["expected_GTP_mM"])<=plan["expected_tolerance_mM"],
                "solved partition differs from the registered values")
        require(abs(compiled(gdp,gtp))<=plan["zero_flux_abs_tolerance"],"compiled backend disagrees on the zero")
        arms[key]={**inventory(gdp,gtp,reference),"convention":spec["convention"],"convention_value_mM":spec["value_mM"],
                   "raw_zero_flux_reaction_J1":raw(gdp,gtp),"initial":arm_initial(f["initial"],names,gdp,gtp).tolist()}
    return arms


def prepare(out):
    require(not out.exists(),"fresh guanylate diagnostic archive required")
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
    require(not any(p in obs["values"] for p in plan["changed_pools"]),"changed pools must be unobserved")
    arms=build_arms(f,plan,center["parameters"])
    paths=[CONFIG,PROTOCOL,Path(__file__),ROOT/"scripts/verify_guanylate_partition.py",ROOT/"src/fla_guanylate_partition.py",
           ROOT/"src/fla_atp_attribution.py",ROOT/"qa/test_fla_guanylate_partition.py",parent/"manifest.json",
           parent/"execution_design.json",parent/"observations.json",parent/"cases.json"]
    for profile in plan["profiles"]:
        folder=parent/"controls"/plan["control_case"]/plan["backend"]/profile
        check_seal(folder)
        paths.extend(folder/p for p in ("flux_evidence.npz","files_seal.json"))
    f["guanylate_plan"]=plan
    f["input_sha256"].update({p.relative_to(ROOT).as_posix():sha(p) for p in paths})
    out.mkdir(parents=True)
    write(out/"execution_design.json",f);write(out/"observations.json",obs)
    write(out/"cases.json",{"parameters":center["parameters"],"log_factors":center["log_factors"],"arms":arms})
    write(out/"source_seal.json",{p:sha(out/p) for p in ("execution_design.json","observations.json","cases.json")})
    return f,plan


def arm_context(f,arm):
    return {**f,"initial":arm["initial"]}


def describe(folder,f,plan,panel,reference,reserve_cache):
    """Scores, dated concentrations, phosphoryl stocks and executed integrals of one replay."""
    score=score_file(folder,f,panel,reference)
    with np.load(folder/"flux_evidence.npz") as a:
        names,reactions,matrix=a["pool_names"].tolist(),a["reactions"].tolist(),a["matrix"]
        ids=np.searchsorted(a["time"],plan["report_days"])
        require(np.array_equal(a["time"][ids],plan["report_days"]),"report dates missing")
        levels={p:a["states"][names.index(p),ids].tolist() for p in plan["report_pools"]}
        stocks={k:sum(c*a["states"][names.index(p),ids] for p,c in spec.items()).tolist() for k,spec in plan["phosphoryl_stocks"].items()}
        ex,w,cells=a["q8_executed_rates"],a["q8_weights"],a["q8_intervals"]
        ledger={}
        for label,window in plan["windows"].items():
            total=signed_integrals(ex,w,cells,window)
            atp=pool_ledger(matrix[names.index("ATP")],ex,w,cells,window)
            ledger[label]={"reactions":{r:float(total[reactions.index(r)]) for r in plan["ledger_reactions"]},
                           "ATP_production_mM":float(atp["production"].sum()),"ATP_consumption_mM":float(atp["consumption"].sum())}
    summary=None
    if score is not None:
        reserve=reserve_cache
        guards=score["feasibility_guards"]
        failed=[k for (k,v),r in zip(guards.items(),reserve) if v>-.5*r]
        j4,j15=plan["report_days"].index(4),plan["report_days"].index(15)
        summary={"gap":score["absolute"]["objective"],"sides":score["absolute"]["sides"],"reserved_guards_pass":score["reserved_guards_pass"],
                 "failed_guards":failed,"worst_dated_ratio":score["objective"],"ATP_J4":levels["ATP"][j4],"ATP_J15":levels["ATP"][j15],
                 "ADP_J15":levels["ADP"][j15],"guard_values":guards}
    stocks["E_A_plus_E_G"]=(np.array(stocks["E_A"])+np.array(stocks["E_G"])).tolist()
    return {"score":summary,"levels_mM":levels,"phosphoryl_stocks_mM":stocks,"ledger":ledger}


def flat(description):
    j=description["ledger"]["J1_J4"]
    return {"NDPK_J1_J4":j["reactions"]["VNDPK"],"ATP_consumption_J1_J4":j["ATP_consumption_mM"]}


def run(out):
    f,plan=prepare(out)
    cases=read(out/"cases.json")
    arms={k:{"id":k,"role":"candidate","log_factors":cases["log_factors"],"parameters":cases["parameters"]} for k in plan["arms"]}
    with ProcessPoolExecutor(max_workers=3) as pool:
        jobs={(k,p):pool.submit(run_one,out,arm_context(f,cases["arms"][k]),arms[k],plan["backend"],p) for k in arms for p in plan["profiles"]}
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
            if (folders[p]/"flux_evidence.npz").exists():
                d=describe(folders[p],arm_context(f,cases["arms"][k]),plan,panel,references[p],reserves[p])
                r["scores"][p]=d["score"];r["details"][p]=d
            else:
                r["scores"][p]=None
        if "ultrastrict" in r["details"]:r["ledger"]=flat(r["details"]["ultrastrict"])
        results[k]=r
    decision=classify(results[plan["hypothesis_arm"]],results[plan["inventory_arm"]],control,plan["compensation_fraction"])
    write(out/"summary.json",{"control":control,"arms":results,"classification":decision,"new_integrations":len(statuses),
          "arm_inventories":{k:{x:v for x,v in a.items() if x!="initial"} for k,a in cases["arms"].items()},
          "measured_J1_changed":False,"parameters_changed":False,"optimization_executed":False,"production_promoted":False,"J46_replayed":False})
    rows=[]
    for name,block in (("control",control),*results.items()):
        for p,d in block["details"].items():
            for pool,values in {**d["levels_mM"],**d["phosphoryl_stocks_mM"]}.items():
                rows.extend([name,p,pool,day,v] for day,v in zip(plan["report_days"],values))
    write_csv(out/"levels_by_day.csv",["arm","profile","pool_or_stock","day","mM"],rows)
    rows=[]
    for name,block in (("control",control),*results.items()):
        for p,d in block["details"].items():
            for label,w in d["ledger"].items():
                rows.extend([name,p,label,r,v] for r,v in {**w["reactions"],"ATP_production":w["ATP_production_mM"],"ATP_consumption":w["ATP_consumption_mM"]}.items())
    write_csv(out/"executed_ledger.csv",["arm","profile","window","reaction_or_total","executed_integral_mM"],rows)
    verify_inputs(out)
    write(out/"manifest.json",{p.relative_to(out).as_posix():sha(p) for p in out.rglob("*") if p.is_file()})
    return {"new_integrations":len(statuses),"classification":decision["category"],
            "flags":{k:{x:v for x,v in fl.items() if x!="compensation"} for k,fl in decision["flags"].items()}}


if __name__=="__main__":
    from threadpoolctl import threadpool_limits
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--out",type=Path,required=True)
    with threadpool_limits(1):print(run(p.parse_args().out.resolve()))
