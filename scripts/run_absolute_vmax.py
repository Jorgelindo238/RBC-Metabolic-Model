"""Bounded absolute J15 ATP/ADP screen with unchanged dated guards."""

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

from run_temporal_vmax import (ROOT, audit, check_seal, evaluate, lp_step, measure,
    panel_from_observations, read, require, seal, sha, verify_inputs, write)
from fla_absolute_vmax import evaluate_screen, target_spec

CONFIG = ROOT/"config/fla_absolute_vmax_2026_11_07.json"


def prepare(out):
    require(not out.exists(), "fresh absolute successor required")
    plan = read(CONFIG)
    parent = ROOT/plan["parent_archive"]
    f = verify_inputs(parent)
    actual = {p.relative_to(parent).as_posix(): sha(p) for p in parent.rglob("*")
              if p.is_file() and p != parent/"manifest.json"}
    require(actual == read(parent/"manifest.json"), "parent manifest changed")
    check_seal(parent/"fit")
    prior = read(parent/"validation_summary.json")
    require(prior["admitted_under_temporal_guards"] and not prior["Km_changed"], "admitted temporal start required")
    require(f["temporal"]["fit_days"] == [4,8,11,15] and not plan["production_promotion_allowed"], "scope changed")
    f["absolute"] = plan
    f["absolute_start"] = read(parent/"fit/result.json")["selected"]["log_factors"]
    obs = read(parent/"observations.json")
    panel = panel_from_observations(obs, f["temporal"]["fit_days"], f["design"])
    f["absolute_targets"] = target_spec(panel, plan)
    paths = [CONFIG, Path(__file__), ROOT/"src/fla_absolute_vmax.py", ROOT/"qa/test_fla_absolute_vmax.py",
             ROOT/"scripts/verify_absolute_vmax.py", ROOT/"scripts/verify_temporal_vmax.py",
             ROOT/"tasks/fla_absolute_vmax_protocol_2026_11_07.md",
             parent/"manifest.json", parent/"execution_design.json", parent/"observations.json",
             parent/"fit/result.json", parent/"validation_summary.json"]
    f["input_sha256"].update({p.relative_to(ROOT).as_posix(): sha(p) for p in paths})
    out.mkdir(parents=True)
    write(out/"execution_design.json", f)
    write(out/"observations.json", obs)
    write(out/"source_seal.json", {p: sha(out/p) for p in ("execution_design.json", "observations.json")})
    return f, panel


def search(out):
    f, panel = prepare(out)
    plan, temporal, d = f["absolute"], f["temporal"], f["design"]
    lo, hi = np.log([d["factor_bounds"][k] for k in d["groups"]]).T
    origin = np.zeros(len(lo))
    anchor = evaluate(f, panel["names"], origin)
    require(anchor["valid"], "fixed reference did not integrate")
    reference = measure(anchor["prediction_mM"], panel)
    folder = out/"fit"
    folder.mkdir()
    trace, cache, steps = [], {}, []
    base = evaluate_screen(anchor["prediction_mM"], reference, panel, d, temporal, f["absolute_targets"])
    reserve = np.r_[-np.array(list(base["guards"].values()))*temporal["reserve_fraction"], np.zeros(len(panel["days"]))]

    def feasible(row):
        return row["valid"] and bool(np.all(np.array(list(row["feasibility_guards"].values())) <= -.5*reserve))

    radius = temporal["initial_radius_log"]
    with ProcessPoolExecutor(max_workers=3) as pool, (folder/"trace.jsonl").open("x", encoding="utf-8") as stream:
        def record(vector, result, stage):
            require(len(trace) < plan["maximum_attempts"], "registered budget exhausted")
            row = {"attempt": len(trace)+1, "stage": stage, "log_factors": list(vector), **result}
            if row["valid"]:
                try:
                    row.update(evaluate_screen(result["prediction_mM"], reference, panel, d, temporal, f["absolute_targets"]))
                except ValueError as error:
                    row.update(valid=False, error=str(error))
            trace.append(row)
            cache[tuple(vector)] = row
            stream.write(json.dumps(row, allow_nan=False)+"\n")
            stream.flush()
            return row

        def batch(vectors, stage):
            vectors = [tuple(np.clip(v, lo, hi)) for v in vectors]
            new = [v for v in dict.fromkeys(vectors) if v not in cache]
            require(len(trace)+len(new) <= plan["maximum_attempts"], "registered budget exceeded")
            jobs = {v: pool.submit(evaluate, f, panel["names"], v) for v in new}
            for v, future in jobs.items():
                record(v, future.result(), stage)
            return [cache[v] for v in vectors]

        record(origin, anchor, "corrected_fixed_reference")
        current = batch([f["absolute_start"]], "previous_temporal_candidate")[0]
        require(feasible(current), "previous candidate no longer satisfies the fixed guard reserve")
        start = np.array(f["absolute_start"])
        probes = batch([start+a*(np.array(f["prior_direction"])-start) for a in plan["exploratory_fractions"]], "prior_J4_direction")
        current = min([current, *[r for r in probes if feasible(r)]], key=lambda r: r["absolute"]["objective"])
        for it in range(plan["number_of_rounds"]):
            x = np.array(current["log_factors"])
            h = np.where(x+temporal["difference_step_log"] <= hi, temporal["difference_step_log"], -temporal["difference_step_log"])
            diffs = batch(x+np.diag(h), f"round{it+1}_sensitivity")
            good = [i for i,r in enumerate(diffs) if r["valid"] and r["log_factors"][i] != x[i]]
            if not good:
                steps.append({"round": it+1, "status": "no_valid_direction"})
                break
            r0 = np.array(list(current["absolute"]["sides"].values()))
            g0 = np.array(list(current["feasibility_guards"].values()))
            jr, jg = np.zeros((len(r0),len(x))), np.zeros((len(g0),len(x)))
            for i in good:
                row = diffs[i]
                dx = row["log_factors"][i]-x[i]
                jr[:,i] = (np.array(list(row["absolute"]["sides"].values()))-r0)/dx
                jg[:,i] = (np.array(list(row["feasibility_guards"].values()))-g0)/dx
            a,b = lo.copy(),hi.copy()
            missing = list(set(range(len(x)))-set(good))
            a[missing] = b[missing] = x[missing]
            proposal = lp_step(x,a,b,radius,r0,jr,g0,jg,reserve)
            step = {"round": it+1, "radius": radius, "anchor": current["attempt"],
                    "valid_derivatives": len(good), "linearized_proposal": proposal, "accepted": None}
            if proposal is not None and proposal["predicted_objective"] < current["absolute"]["objective"]:
                candidates = batch([x+alpha*np.array(proposal["delta"]) for alpha in temporal["line_search_fractions"]], f"round{it+1}_backtrack")
                step["candidate_attempts"] = [r["attempt"] for r in candidates]
                passed = [r for r in candidates if feasible(r) and r["absolute"]["objective"] <= current["absolute"]["objective"]-temporal["minimum_step_objective_gain"]]
                if passed:
                    current = min(passed, key=lambda r:r["absolute"]["objective"])
                    step["accepted"] = current["attempt"]
            radius = min(temporal["maximum_radius_log"],radius*1.25) if step["accepted"] else radius*.5
            steps.append(step)
            print(f"Round {it+1}: {len(trace)} attempts, accepted={step['accepted']}, absolute log gap={current['absolute']['objective']:.8g}", flush=True)
        selected = min([r for r in trace if feasible(r)], key=lambda r:r["absolute"]["objective"])
    write(folder/"result.json", {"actual_attempts":len(trace), "invalid_attempts":sum(not r["valid"] for r in trace),
          "maximum_attempts":plan["maximum_attempts"], "steps":steps, "selected":selected,
          "corrected_fit_reference":reference, "global_optimality":False,
          "absolute_target_attained_in_fit":selected["absolute"]["target_pass"]})
    seal(folder)
    verify_inputs(out)
    return {"attempts":len(trace), "selected_attempt":selected["attempt"], "absolute":selected["absolute"]}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--audit",action="store_true")
    args = p.parse_args()
    with threadpool_limits(1):
        print(audit(args.out.resolve()) if args.audit else search(args.out.resolve()))
