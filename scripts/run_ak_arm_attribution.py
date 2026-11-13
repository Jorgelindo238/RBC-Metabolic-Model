"""Executed ATP/adenylate attribution of the sealed adenylate kinase ratio arms. No integration.

Reuses the registered 2026-11-10 attribution analysis unchanged on the four
sealed trajectories of the AK ratio diagnostic and adds arm-minus-control
contrasts per reaction.
"""

import argparse
from pathlib import Path

from run_vmax_requalification import ROOT,check_seal,read,require,seal,sha,verify_archive,write,write_csv
from run_atp_attribution import WINDOWS_J15,analyse,evidence_folder,primary_reading
from fla_ak_arm_attribution import FIELDS,check_plan,contrast

CONFIG=ROOT/"config/fla_ak_arm_attribution_2026_11_11.json"
PROTOCOL=ROOT/"tasks/fla_ak_arm_attribution_protocol_2026_11_11.md"


def prepare(out):
    require(not out.exists(),"fresh attribution archive required")
    plan=read(CONFIG)
    check_plan(plan)
    for archive in plan["archives"]:
        verify_archive(ROOT/archive)
    paths=[CONFIG,PROTOCOL,Path(__file__),ROOT/"scripts/verify_ak_arm_attribution.py",ROOT/"scripts/run_atp_attribution.py",
           ROOT/"src/fla_ak_arm_attribution.py",ROOT/"src/fla_atp_attribution.py",ROOT/"src/fla_executed_attribution.py",
           ROOT/"qa/test_fla_ak_arm_attribution.py",ROOT/plan["published_summary"],*(ROOT/a/"manifest.json" for a in plan["archives"])]
    for case in plan["cases"]:
        for profile in plan["profiles"]:
            folder=evidence_folder(plan,case,profile)
            check_seal(folder)
            require(read(folder/"result.json")["numerical_pass"],"only numerically admitted evidence is attributed")
            paths.extend(folder/p for p in ("flux_evidence.npz","trajectory_evidence.npz","files_seal.json"))
    out.mkdir(parents=True)
    write(out/"execution_design.json",{"plan":plan,"absolute_windows_J15_mM":WINDOWS_J15,
          "input_sha256":{p.relative_to(ROOT).as_posix():sha(p) for p in paths}})
    return plan


def run(out):
    plan=prepare(out)
    ledgers,gates,summary=[],[],{}
    for case in plan["cases"]:
        for profile in plan["profiles"]:
            result,l,g=analyse(plan,case,profile)
            folder=out/"cases"/case;folder.mkdir(parents=True,exist_ok=True)
            write(folder/f"{profile}.json",result)
            ledgers+=l;gates+=g
            summary[case+"/"+profile]={"closure_pass":result["closure_pass"],"reading":primary_reading(plan,result)}
            print(f"{case}/{profile}: closure={result['closure_pass']}",flush=True)
    table={}
    for case,profile,window,pool,reaction,_,net,production,consumption in ledgers:
        table.setdefault((case,profile,window,pool),{})[reaction]=dict(zip(FIELDS,(net,production,consumption)))
    rows=[]
    for (case,profile,window,pool),arm in table.items():
        if case==plan["control_case"] or pool not in plan["contrast_pools"] or window not in plan["windows"]:continue
        for r in contrast(arm,table[(plan["control_case"],profile,window,pool)]):
            rows.append([case,profile,window,pool,r["reaction"],*(r[p+k] for p in ("control_","arm_","d_") for k in FIELDS)])
    write_csv(out/"ledger_by_reaction.csv",["case","profile","window","pool","reaction","coefficient","net_mM","production_mM","consumption_mM"],ledgers)
    write_csv(out/"gate_loss.csv",["case","profile","window","reaction","raw_abs_integral_mM","executed_abs_integral_mM","lost_mM","top_limiting_pool","lost_to_top_pool_mM"],gates)
    write_csv(out/"contrast_vs_control.csv",["case","profile","window","pool","reaction",*(p+k+"_mM" for p in ("control_","arm_","d_") for k in FIELDS)],rows)
    key=plan["primary_case"]+"/"+plan["primary_profile"]
    control=plan["control_case"]+"/"+plan["primary_profile"]
    write(out/"summary.json",{"cases":summary,"primary":key,"primary_reading":summary[key]["reading"],"control_reading":summary[control]["reading"],
          "all_closures_pass":all(s["closure_pass"] for s in summary.values()),"contrast_rows":len(rows),"new_integrations":0,
          "descriptive_not_causal":True,"parameters_changed":False,"production_promoted":False})
    seal(out/"cases")
    write(out/"manifest.json",{p.relative_to(out).as_posix():sha(p) for p in out.rglob("*") if p.is_file()})
    return {"primary":key,"primary_reading":summary[key]["reading"],"control_reading":summary[control]["reading"],
            "all_closures_pass":all(s["closure_pass"] for s in summary.values()),"contrast_rows":len(rows)}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--out",type=Path,required=True)
    print(run(p.parse_args().out.resolve()))
