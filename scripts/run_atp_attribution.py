"""Executed ATP/adenylate attribution on sealed trajectories. No integration."""

import argparse
from pathlib import Path

import numpy as np

from run_vmax_requalification import ROOT,check_seal,read,require,seal,sha,verify_archive,write,write_csv
from fla_atp_attribution import cycle_accounts,first_below,gate_loss,pool_ledger,reading,shares,signed_integrals

CONFIG=ROOT/"config/fla_atp_attribution_2026_11_10.json"
PROTOCOL=ROOT/"tasks/fla_atp_attribution_protocol_2026_11_10.md"
ARCHIVES=("output/vmax_requalification_2026_11_09","output/vmax_corrected_search_2026_11_10")
WINDOWS_J15={"ATP":[0.75707361,1.27058099],"ADP":[0.31579781215841685,0.5854817010799304]}


def evidence_folder(plan,case,profile):
    spec=plan["cases"][case]
    return ROOT/spec["folder"]/spec["backend"]/profile


def prepare(out):
    require(not out.exists(),"fresh attribution archive required")
    plan=read(CONFIG)
    require(plan["new_integrations"]==0 and not any(plan[k] for k in ("parameters_changed","optimization_executed","production_promotion_allowed","J46_replayed")),
            "attribution is read-only bookkeeping")
    for archive in ARCHIVES:
        verify_archive(ROOT/archive)
    paths=[CONFIG,PROTOCOL,Path(__file__),ROOT/"scripts/verify_atp_attribution.py",ROOT/"src/fla_atp_attribution.py",
           ROOT/"src/fla_executed_attribution.py",ROOT/"qa/test_fla_atp_attribution.py",ROOT/plan["published_budgets"],
           *(ROOT/a/"manifest.json" for a in ARCHIVES)]
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


def analyse(plan,case,profile):
    folder=evidence_folder(plan,case,profile)
    with np.load(folder/"flux_evidence.npz") as a,np.load(folder/"trajectory_evidence.npz") as t:
        names,reactions,matrix=a["pool_names"].tolist(),a["reactions"].tolist(),a["matrix"]
        raw,executed,weights,cells=a["q8_raw_rates"],a["q8_executed_rates"],a["q8_weights"],a["q8_intervals"]
        require(np.array_equal(weights,t["q8_weights"]) and np.array_equal(cells,t["q8_intervals"]),"quadrature supports differ")
        nodes=t["q8_states"][:len(names)]
        time,states,bounds=a["time"],a["states"],a["boundaries"]
    require(np.array_equal(bounds,np.arange(1.,16.)),"exact daily J1-J15 boundaries required")
    ids=np.searchsorted(time,bounds)
    rows={k:matrix[names.index(k)] for k in plan["ledger_pools"]}
    rows.update({k:sum(c*matrix[names.index(p)] for p,c in spec.items()) for k,spec in plan["lumped_pools"].items()})
    level=lambda k,j:(states[names.index(k),j] if k in names else sum(c*states[names.index(p),j] for p,c in plan["lumped_pools"][k].items()))
    windows={**plan["windows"],**({f"day_{d}_{d+1}":[d,d+1] for d in range(1,15)} if plan["daily_resolution"] else {})}
    result={"case":case,"profile":profile,"reactions":reactions,"windows":{}}
    ledger_rows,gate_rows,closure_ok=[],[],True
    for label,window in windows.items():
        lo,hi=int(window[0])-1,int(window[1])-1
        entry={"pools":{},"gate":{},"cycles":None}
        for pool,coefficients in rows.items():
            led=pool_ledger(coefficients,executed,weights,cells,window)
            delta=float(level(pool,ids[hi])-level(pool,ids[lo]))
            net=float(led["net"].sum())
            closed=abs(delta-net)<=plan["closure_atol_mM"]+plan["closure_rtol"]*max(abs(delta),abs(net))
            closure_ok&=bool(closed)
            entry["pools"][pool]={"delta_state_mM":delta,"executed_net_mM":net,"closure_residual_mM":delta-net,"closed":bool(closed),
                "production_mM":float(led["production"].sum()),"consumption_mM":float(led["consumption"].sum()),
                "production_share":dict(zip(reactions,shares(led["production"]).tolist())),
                "consumption_share":dict(zip(reactions,shares(led["consumption"]).tolist()))}
            for j in np.flatnonzero(coefficients):
                ledger_rows.append([case,profile,label,pool,reactions[j],float(coefficients[j]),float(led["net"][j]),
                                    float(led["production"][j]),float(led["consumption"][j])])
        if label in plan["windows"]:
            gate=gate_loss(nodes,raw,executed,matrix,weights,cells,window,plan["gate_threshold_mM"])
            for j,r in enumerate(reactions):
                if matrix[names.index("ATP"),j]==0 and matrix[names.index("ADP"),j]==0:continue
                limiting={names[i]:float(gate["lost_by_pool"][i,j]) for i in np.flatnonzero(gate["lost_by_pool"][:,j])}
                top=max(limiting,key=limiting.get) if limiting else None
                entry["gate"][r]={"raw":float(gate["raw"][j]),"executed":float(gate["executed"][j]),"lost":float(gate["lost"][j]),
                                  "limiting_pools":limiting}
                gate_rows.append([case,profile,label,r,float(gate["raw"][j]),float(gate["executed"][j]),float(gate["lost"][j]),top,
                                  limiting.get(top) if top else None])
            entry["cycles"]=cycle_accounts(signed_integrals(executed,weights,cells,window),reactions,plan["cycles"])
        result["windows"][label]=entry
    timing={}
    for pool in ("ATP","ADP"):
        x=states[names.index(pool)]
        timing[pool]={"J1_mM":float(x[0]),"first_day_below_J15_window_lower":first_below(time,x,WINDOWS_J15[pool][0]),
                      "first_day_below_gate":first_below(time,x,plan["gate_threshold_mM"]),
                      "daily_mM":x[ids].tolist()}
    atp=rows["ATP"]
    timing["cumulative_executed_ATP_net_mM"]=np.cumsum([float(pool_ledger(atp,executed,weights,cells,[d,d+1])["net"].sum()) for d in range(1,15)]).tolist()
    result["timing"]=timing
    result["closure_pass"]=closure_ok
    return result,ledger_rows,gate_rows


def primary_reading(plan,result):
    w=result["windows"][plan["primary_window"]]
    return reading({"ATP_consumption_share":w["pools"]["ATP"]["consumption_share"],
                    "glycolytic_yield":w["cycles"]["glycolytic_yield"]["yield"],
                    "bypass_share":w["cycles"]["rapoport_luebering"]["bypass_share"],"gate":w["gate"]},plan["reading_thresholds"])


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
    write_csv(out/"ledger_by_reaction.csv",["case","profile","window","pool","reaction","coefficient","net_mM","production_mM","consumption_mM"],ledgers)
    write_csv(out/"gate_loss.csv",["case","profile","window","reaction","raw_abs_integral_mM","executed_abs_integral_mM","lost_mM","top_limiting_pool","lost_to_top_pool_mM"],gates)
    key=plan["primary_case"]+"/"+plan["primary_profile"]
    write(out/"summary.json",{"cases":summary,"primary":key,"primary_reading":summary[key]["reading"],
          "all_closures_pass":all(s["closure_pass"] for s in summary.values()),"new_integrations":0,
          "descriptive_not_causal":True,"parameters_changed":False,"production_promoted":False})
    seal(out/"cases")
    write(out/"manifest.json",{p.relative_to(out).as_posix():sha(p) for p in out.rglob("*") if p.is_file()})
    return {"primary":key,"primary_reading":summary[key]["reading"],"all_closures_pass":all(s["closure_pass"] for s in summary.values())}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--out",type=Path,required=True)
    print(run(p.parse_args().out.resolve()))
