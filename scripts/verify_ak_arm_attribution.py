"""Independent receipt for the attribution of the adenylate kinase ratio arms.

Recomputes ledgers, closures, gate identities, contrasts and the registered
reading from quadrature rates with a separate code path (daily bincount
integrals), without importing either attribution module.
"""

import argparse
import csv
from pathlib import Path

import numpy as np

from run_vmax_requalification import ROOT,check_seal,read,require,seal,sha,verify_archive,write


def daily(values,weights,cells):
    return np.array([np.bincount(cells,weights=v*weights,minlength=14) for v in values])


def rows_of(path,key):
    with path.open(newline="",encoding="utf-8") as s:
        return {tuple(r[k] for k in key):r for r in csv.DictReader(s)}


def verify(out,report):
    require(not report.exists() and not report.is_relative_to(out),"fresh external receipt required")
    verify_archive(out);check_seal(out/"cases")
    design=read(out/"execution_design.json")
    plan=design["plan"]
    require(plan==read(ROOT/"config/fla_ak_arm_attribution_2026_11_11.json") and plan["new_integrations"]==0,"registered plan changed")
    for p,h in design["input_sha256"].items():
        require(sha(ROOT/p)==h,f"protected input changed:{p}")
    require(not any(p.suffix==".npz" for p in out.rglob("*")),"attribution archive must not contain trajectories")
    ledger=rows_of(out/"ledger_by_reaction.csv",("case","profile","window","pool","reaction"))
    contrasts=rows_of(out/"contrast_vs_control.csv",("case","profile","window","pool","reaction"))
    published=read(ROOT/plan["published_summary"])
    summary=read(out/"summary.json")
    counts={"ledger_values":0,"closures_passed":0,"closures_total":0,"published_budget_rows":0,"gate_identities":0,
            "profile_comparisons":0,"contrast_values":0}
    th=plan["reading_thresholds"]
    readings,parts={},{}
    for case,spec in plan["cases"].items():
        nets={}
        source=published["control"] if case==plan["control_case"] else published["arms"][case]
        for profile in plan["profiles"]:
            folder=ROOT/spec["folder"]/spec["backend"]/profile
            recorded=read(out/"cases"/case/f"{profile}.json")
            with np.load(folder/"flux_evidence.npz") as a,np.load(folder/"trajectory_evidence.npz") as t:
                names,reactions,matrix=a["pool_names"].tolist(),a["reactions"].tolist(),a["matrix"]
                w,cells=a["q8_weights"],a["q8_intervals"]
                ex,raw=a["q8_executed_rates"],a["q8_raw_rates"]
                integral=daily(ex,w,cells)
                require(np.allclose(integral,a["executed8"],rtol=1e-12,atol=1e-12),"executed quadrature does not reproduce the sealed integrals")
                states,ids=a["states"],np.searchsorted(a["time"],a["boundaries"])
                x=t["q8_states"][:len(names)]
            coefficient={pool:matrix[names.index(pool)] for pool in plan["ledger_pools"]}
            level={pool:states[names.index(pool)] for pool in plan["ledger_pools"]}
            for pool,mix in plan["lumped_pools"].items():
                coefficient[pool]=sum(c*matrix[names.index(k)] for k,c in mix.items())
                level[pool]=sum(c*states[names.index(k)] for k,c in mix.items())
            closure=True
            for label,(lo,hi) in plan["windows"].items():
                lo,hi=int(lo)-1,int(hi)-1
                total=integral[:,lo:hi].sum(axis=1)
                use=(cells>=lo)&(cells<hi)
                for pool,row in coefficient.items():
                    contribution=row*total
                    part=row[:,None]*ex[:,use]
                    gross=(np.maximum(part,0)@w[use],np.maximum(-part,0)@w[use])
                    for j in np.flatnonzero(row):
                        r=ledger[(case,profile,label,pool,reactions[j])]
                        require(np.isclose(float(r["net_mM"]),contribution[j],rtol=1e-9,atol=1e-12)
                                and np.isclose(float(r["production_mM"]),gross[0][j],rtol=1e-9,atol=1e-12)
                                and np.isclose(float(r["consumption_mM"]),gross[1][j],rtol=1e-9,atol=1e-12),"ledger entry changed")
                        counts["ledger_values"]+=3
                    delta=level[pool][ids[hi]]-level[pool][ids[lo]]
                    ok=abs(delta-contribution.sum())<=plan["closure_atol_mM"]+plan["closure_rtol"]*max(abs(delta),abs(contribution.sum()))
                    require(bool(ok)==recorded["windows"][label]["pools"][pool]["closed"],"closure flag changed")
                    closure&=bool(ok);counts["closures_total"]+=1;counts["closures_passed"]+=int(ok)
                    nets[(profile,label,pool)]=contribution
                    if pool in plan["contrast_pools"]:
                        parts[(case,profile,label,pool)]={reactions[j]:(contribution[j],gross[0][j],gross[1][j]) for j in np.flatnonzero(row)}
                atp=coefficient["ATP"][:,None]*ex[:,use]
                production,consumption=np.maximum(atp,0).sum(axis=0)@w[use],np.maximum(-atp,0).sum(axis=0)@w[use]
                budget=source["details"][profile]["ledger"][label]
                require(np.isclose(budget["ATP_production_mM"],production,rtol=1e-9,atol=1e-12)
                        and np.isclose(budget["ATP_consumption_mM"],consumption,rtol=1e-9,atol=1e-12),"disagrees with the sealed AK diagnostic budget")
                counts["published_budget_rows"]+=1
                entry=recorded["windows"][label]
                require(abs(entry["pools"]["ATP"]["production_mM"]-production)<1e-9 and abs(entry["pools"]["ATP"]["consumption_mM"]-consumption)<1e-9,"gross ATP turnover changed")
                for r,g in entry["gate"].items():
                    j=reactions.index(r)
                    consumers=((matrix[:,j,None]<0)&(raw[j]>0))|((matrix[:,j,None]>0)&(raw[j]<0))
                    factor=np.min(np.where(consumers,np.clip(x/plan["gate_threshold_mM"],0,1),1.),axis=0)
                    require(np.allclose(raw[j]*factor,ex[j],rtol=1e-9,atol=1e-14),"executed rate is not the gated raw rate")
                    lost=(np.abs(raw[j])*(1-factor))[use]@w[use]
                    require(np.isclose(g["lost"],lost,rtol=1e-9,atol=1e-12) and np.isclose(g["raw"]-g["executed"],lost,rtol=1e-8,atol=1e-10)
                            and np.isclose(sum(g["limiting_pools"].values()),lost,rtol=1e-8,atol=1e-10),"gate loss changed")
                    counts["gate_identities"]+=1
            require(closure==recorded["closure_pass"]==summary["cases"][case+"/"+profile]["closure_pass"],"closure summary changed")
            e=recorded["windows"][plan["primary_window"]]
            lo,hi=(int(v)-1 for v in plan["windows"][plan["primary_window"]])
            use=(cells>=lo)&(cells<hi)
            cons=np.maximum(-coefficient["ATP"][:,None]*ex[:,use],0)@w[use]
            share=dict(zip(reactions,cons/cons.sum()))
            total=integral[:,lo:hi].sum(axis=1);v=lambda r:total[reactions.index(r)]
            flags={"NDPK_purine_cycle":bool(share["VNDPK"]>=th["dominant_consumer_share"]),
                   "PRPPASe":bool(share["VPRPPASe"]>=th["dominant_consumer_share"]),
                   "availability_gate_on_PGK_PK":bool(e["gate"]["VPGK"]["lost"]+e["gate"]["VPK"]["lost"]>e["gate"]["VPGK"]["executed"]+e["gate"]["VPK"]["executed"]),
                   "lower_glycolysis_supply":bool((v("VPGK")+v("VPK"))/(v("VHK")+v("VPFK"))<th["glycolytic_yield_below"]
                                                  or v("VDPGM")/(v("VDPGM")+v("VPGK"))>th["bypass_share_above"])}
            flags["none"]=not any(flags.values())
            require(flags==summary["cases"][case+"/"+profile]["reading"],"registered reading changed")
            if profile==plan["primary_profile"]:
                readings[case]={"flags":flags,"NDPK_share":float(share["VNDPK"]),"PRPPASe_share":float(share["VPRPPASe"]),
                                "glycolytic_yield":float((v("VPGK")+v("VPK"))/(v("VHK")+v("VPFK"))),
                                "bypass_share":float(v("VDPGM")/(v("VDPGM")+v("VPGK")))}
        agree=True
        for (profile,label,pool),value in nets.items():
            if profile!="strict":continue
            other=nets[("ultrastrict",label,pool)]
            agree&=bool(np.all(np.abs(value-other)<=1e-5+.01*np.maximum(np.abs(value),np.abs(other))))
            counts["profile_comparisons"]+=value.size
        require(agree,f"strict and ultrastrict ledgers disagree: {case}")
    expected=0
    for (case,profile,label,pool),arm in parts.items():
        if case==plan["control_case"]:continue
        control=parts[(plan["control_case"],profile,label,pool)]
        require(set(arm)==set(control),"contrast reactions differ")
        for reaction,values in arm.items():
            r=contrasts[(case,profile,label,pool,reaction)]
            for k,a,c in zip(("net","production","consumption"),values,control[reaction]):
                require(np.isclose(float(r["d_"+k+"_mM"]),a-c,rtol=1e-9,atol=1e-12) and np.isclose(float(r["arm_"+k+"_mM"]),a,rtol=1e-9,atol=1e-12)
                        and np.isclose(float(r["control_"+k+"_mM"]),c,rtol=1e-9,atol=1e-12),"contrast entry changed")
                counts["contrast_values"]+=3
            expected+=1
    require(expected==len(contrasts)==summary["contrast_rows"],"contrast table has unexpected rows")
    require(readings[plan["primary_case"]]["flags"]==summary["primary_reading"] and readings[plan["control_case"]]["flags"]==summary["control_reading"],
            "summary reading changed")
    report.mkdir(parents=True)
    receipt={"verified":True,"counts":counts,"all_closures_pass":counts["closures_passed"]==counts["closures_total"],
             "summary_all_closures_pass":summary["all_closures_pass"],"readings":readings,"new_integrations":0,"parameters_changed":False,
             "descriptive_not_causal":True,"archive_manifest_sha256":sha(out/"manifest.json"),"verifier_sha256":sha(Path(__file__))}
    write(report/"verification.json",receipt);seal(report);check_seal(report)
    return receipt


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--out",type=Path,required=True);p.add_argument("--report",type=Path,required=True)
    a=p.parse_args();print(verify(a.out.resolve(),a.report.resolve()))
