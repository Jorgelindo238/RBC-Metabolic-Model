"""Independent absolute-target reconstruction after the original-rate replays."""

import argparse
import json
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

from verify_temporal_vmax import verify as verify_temporal
from run_temporal_vmax import (ROOT, check_seal, read, require, seal, sha, verify_inputs, write, write_csv)


def reconstruct(x, base, target, bands, names, days, d, temporal):
    absolute, baseline = np.abs(x-target), np.abs(base-target)
    squared, squared0 = np.zeros_like(x), np.zeros_like(x)
    np.divide(absolute,bands,out=squared,where=bands>0)
    np.divide(baseline,bands,out=squared0,where=bands>0)
    count = (bands>0).sum(axis=1)
    mse = np.divide((squared**2).sum(axis=1),count,out=np.zeros(len(names)),where=count>0)
    mse0 = np.divide((squared0**2).sum(axis=1),count,out=np.zeros(len(names)),where=count>0)
    fraction = d["working_allowance_fraction"]
    guards = {}
    for i,p in enumerate(names):
        if p in set(d["source_aliases"]) | {"ATP","ADP","AMP"}:
            continue
        if (bands[i]>0).any():
            guards["MSE:"+p] = (mse[i]-mse0[i])/(1+mse0[i])-fraction
        for j,t in enumerate(days):
            if bands[i,j] == 0:
                guards[f"zero:{p}:J{t}"] = (absolute[i,j]-baseline[i,j]-d["zero_band_absolute_allowance_mM"])/(1+baseline[i,j])
    aden = [names.index(p) for p in ("ATP","ADP","AMP")]
    log,log0 = np.log(x[aden]/target[aden]),np.log(base[aden]/target[aden])
    for i,p in enumerate(("ATP","ADP","AMP")):
        for j,t in enumerate(days):
            guards[f"log:{p}:J{t}"] = abs(log[i,j])-abs(log0[i,j])-np.log1p(fraction)
    for p in temporal["critical_pointwise_pools"]:
        i = names.index(p)
        for j,t in enumerate(days):
            cap = np.sqrt(baseline[i,j]**2+fraction*(bands[i,j]**2+baseline[i,j]**2)) if bands[i,j] else baseline[i,j]+d["zero_band_absolute_allowance_mM"]
            guards[f"point:{p}:J{t}"] = (absolute[i,j]-cap)/max(bands[i,j]+cap,1e-6)
    ratios = np.mean(log**2,axis=0)/np.mean(log0**2,axis=0)
    for t,ratio in zip(days,ratios):
        guards[f"date_gain:J{t}"] = ratio-1+temporal["minimum_each_day_relative_gain"]
    j = days.index(15)
    sides = {key: float(value) for p in ("ATP","ADP") for key,value in (
        (p+":lower",np.log((target[names.index(p),j]-bands[names.index(p),j])/x[names.index(p),j])),
        (p+":upper",np.log(x[names.index(p),j]/(target[names.index(p),j]+bands[names.index(p),j]))))}
    return guards,sides


def verify(out, report):
    require(not report.exists() and not report.is_relative_to(out), "fresh external decision required")
    f = verify_inputs(out)
    obs,fit = read(out/"observations.json"),read(out/"fit/result.json")
    names,days = list(obs["values"]),f["temporal"]["fit_days"]
    target = np.array([[obs["values"][p][obs["time"].index(t)] for t in days] for p in names])
    early = np.column_stack(([obs["values"][p][0] for p in names],target))
    bands = .05*np.median(early,axis=1)[:,None]+.2*target
    for p,t in f["absolute_targets"].items():
        i,j = names.index(p),days.index(15)
        require(t == {"day":15,"nominal_mM":float(target[i,j]),"band_mM":float(bands[i,j]),
                      "lower_mM":float(target[i,j]-bands[i,j]),"upper_mM":float(target[i,j]+bands[i,j])}, "absolute interval changed")
    trace = [json.loads(line) for line in (out/"fit/trace.jsonl").read_text().splitlines()]
    base = np.array(trace[0]["prediction_mM"])
    g0,_ = reconstruct(base,base,target,bands,names,days,f["design"],f["temporal"])
    reserve = np.array([0 if k.startswith("date_gain:") else -v*f["temporal"]["reserve_fraction"] for k,v in g0.items()])
    feasible,scored,guard_rows = [],0,0
    for row in trace:
        if not row["valid"]:
            continue
        guards,sides = reconstruct(np.array(row["prediction_mM"]),base,target,bands,names,days,f["design"],f["temporal"])
        require(list(guards) == list(row["feasibility_guards"]) and np.allclose(list(guards.values()),list(row["feasibility_guards"].values()),rtol=1e-12,atol=1e-12), "dated constraint reconstruction changed")
        require(np.allclose(list(sides.values()),list(row["absolute"]["sides"].values()),rtol=1e-12,atol=1e-12)
                and abs(max(sides.values())-row["absolute"]["objective"])<1e-12, "absolute score changed")
        require(row["absolute"]["target_pass"] == (max(sides.values())<=0), "target pass changed")
        if np.all(np.array(list(guards.values())) <= -.5*reserve):
            feasible.append(row)
        scored += 1
        guard_rows += len(guards)
    best = min(feasible,key=lambda r:r["absolute"]["objective"])
    require(best["attempt"] == fit["selected"]["attempt"], "selected candidate not best sampled feasible absolute score")
    checks = verify_temporal(out, report/"temporal_reconstruction")
    summary = read(out/"validation_summary.json")
    rows,original,allguards = [],{},True
    for profile in ("strict","ultrastrict"):
        predictions = {}
        for label in ("corrected_reference","temporal_candidate"):
            with np.load(out/"audits"/label/profile/"replay.npz") as a:
                ids = np.searchsorted(a["time"],days)
                predictions[label] = a["states"][np.ix_([a["pool_names"].tolist().index(p) for p in names],ids)]
        candidate,reference = predictions["temporal_candidate"],predictions["corrected_reference"]
        guards,sides = reconstruct(candidate,reference,target,bands,names,days,f["design"],f["temporal"])
        combined = {**summary["original_metrics"][profile]["guards"],
                    **{f"date_gain:J{t}":r-1+f["temporal"]["minimum_each_day_relative_gain"] for t,r in zip(days,summary["original_metrics"][profile]["day_ratios"])}}
        require(np.allclose(list(guards.values()),list(combined.values()),rtol=1e-12,atol=1e-12), "original constraint mismatch")
        passed = bool(max(guards.values())<=0)
        allguards &= passed
        original[profile] = {"absolute_objective":max(sides.values()), "absolute_target_pass":bool(max(sides.values())<=0), "guards_pass":passed}
        for p,t in f["absolute_targets"].items():
            i,j = names.index(p),days.index(15)
            value = candidate[i,j]
            rows.append([profile,p,t["nominal_mM"],t["lower_mM"],t["upper_mM"],reference[i,j],value,bool(t["lower_mM"]<=value<=t["upper_mM"])])
    numerical = all(r["pass"] for r in summary["original_checks"].values())
    write_csv(report/"absolute_J15_targets.csv",["profile","pool","nominal_mM","lower_mM","upper_mM","reference_mM","candidate_mM","target_pass"],rows)
    result = {"verified":True, "attempts":len(trace), "fit_scores_reconstructed":scored,
              "fit_guard_rows_reconstructed":guard_rows,"sampled_guard_feasible_attempts":len(feasible),
              "selected_attempt":best["attempt"],"original_metrics":original,"numerical_pass":numerical,
              "same_temporal_guards_pass":bool(allguards),
              "absolute_target_attained":bool(numerical and allguards and all(r["absolute_target_pass"] for r in original.values())),
              "local_screen_only":True,"global_infeasibility_proven":False,"production_promoted":False,
              "all_Km_fixed":True,"J46_replayed":False,"temporal_checks":checks,
              "verifier_sha256":sha(Path(__file__)),"archive_manifest_sha256":sha(out/"manifest.json")}
    write(report/"absolute_decision.json",result)
    seal(report)
    check_seal(report)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--report",type=Path,required=True)
    args = parser.parse_args()
    with threadpool_limits(1):
        print(verify(args.out.resolve(),args.report.resolve()))
