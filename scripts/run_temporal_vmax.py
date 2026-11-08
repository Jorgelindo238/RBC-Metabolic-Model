"""Multi-date constrained Vmax optimization and original-rate validation."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

from run_agentic_vmax_pilot import (ROOT, check_seal, integrate_free, measure, panel_from_observations,
                                    parameters_for, read, replay_evidence, require, rhs_for, seal, sha,
                                    verify_inputs, verify_manifest, within, write, write_csv)
from fla_temporal_vmax import evaluate_panel, lp_step

CONFIG = ROOT/"config/fla_temporal_vmax_2026_11_04.json"
PROTOCOL = ROOT/"tasks/fla_temporal_vmax_protocol_2026_11_04.md"


def prepare(out):
    require(not out.exists(), "fresh temporal successor required")
    plan = read(CONFIG)
    parent = ROOT/plan["parent_archive"]
    f = verify_inputs(parent)
    verify_manifest(parent)
    require(plan["fit_days"] == [4, 8, 11, 15] and plan["critical_pointwise_pools"] == ["PEP", "G6P", "F6P", "AMP"], "declared temporal targets changed")
    require(f["structure_modes"][plan["network"]] == "redox_gssg_abc", "expected verified RBC-GEM variant")
    diagnostic = parent/"search"/plan["network"]/"result.json"
    f["prior_direction"] = read(diagnostic)["finalist"]["log_factors"]
    f["temporal"] = plan
    f["design"]["fit_days"] = plan["fit_days"]
    paths = [CONFIG, PROTOCOL, Path(__file__), ROOT/"src/fla_temporal_vmax.py", ROOT/"qa/test_fla_temporal_vmax.py",
             parent/"execution_design.json", parent/"observations.json", parent/"manifest.json", diagnostic]
    f["input_sha256"].update({p.relative_to(ROOT).as_posix(): sha(p) for p in paths})
    out.mkdir(parents=True)
    write(out/"execution_design.json", f)
    write(out/"observations.json", read(parent/"observations.json"))
    write(out/"source_seal.json", {p: sha(out/p) for p in ("execution_design.json", "observations.json")})
    return f


def evaluate(f, names, vector):
    try:
        p = parameters_for(f, vector)
        rhs = rhs_for(f, p, f["temporal"]["network"])
        days = f["temporal"]["fit_days"]
        with threadpool_limits(1):
            sol, _, _, minimum = integrate_free(rhs, f["initial"], 15, days, f["design"]["fit_profile"], f["numeric"]["negative_tolerance_mM"])
        prediction = sol.sol(days)[[rhs.names.index(k) for k in names]]
        return {"valid": True, "prediction_mM": prediction.tolist(), "minimum_checked_mM": minimum}
    except (ValueError, RuntimeError, FloatingPointError, OverflowError) as error:
        return {"valid": False, "error": str(error)}


def search(out):
    f = prepare(out)
    plan, d = f["temporal"], f["design"]
    panel = panel_from_observations(read(out/"observations.json"), plan["fit_days"], d)
    lo, hi = np.log([d["factor_bounds"][k] for k in d["groups"]]).T
    origin = np.zeros(len(lo))
    anchor = evaluate(f, panel["names"], origin)
    require(anchor["valid"], "same-network reference did not integrate")
    reference = measure(anchor["prediction_mM"], panel)
    folder = out/"fit"
    folder.mkdir()
    trace, steps, cache = [], [], {}
    base = evaluate_panel(anchor["prediction_mM"], reference, panel, d, plan)
    reserve = -np.array(list(base["guards"].values()))*plan["reserve_fraction"]
    current = None
    radius = plan["initial_radius_log"]
    print("Frozen temporal pilot: J4/J8/J11/J15, 14 Vmax groups, four guarded trust rounds", flush=True)
    with ProcessPoolExecutor(max_workers=3) as pool, (folder/"trace.jsonl").open("x", encoding="utf-8") as stream:
        def record(vector, result, stage):
            row = {"attempt": len(trace)+1, "stage": stage, "log_factors": list(vector), **result}
            if result["valid"]:
                row.update(evaluate_panel(result["prediction_mM"], reference, panel, d, plan))
            trace.append(row)
            cache[tuple(vector)] = row
            stream.write(json.dumps(row, allow_nan=False)+"\n")
            stream.flush()
            return row

        def batch(vectors, stage):
            vectors = [tuple(np.clip(v, lo, hi)) for v in vectors]
            jobs = {v: pool.submit(evaluate, f, panel["names"], v) for v in dict.fromkeys(vectors) if v not in cache}
            for v, future in jobs.items():
                record(v, future.result(), stage)
            return [cache[v] for v in vectors]

        def fit_feasible(row):
            return row["valid"] and np.all(np.array(list(row["guards"].values())) <= -.5*reserve)

        current = record(origin, anchor, "corrected_fixed_reference")
        starts = batch([a*np.array(f["prior_direction"]) for a in plan["continuation_start_fractions"]], "prior_direction")
        for row in starts:
            if fit_feasible(row) and row["objective"] < current["objective"]:
                current = row
        for it in range(plan["number_of_rounds"]):
            x = np.array(current["log_factors"])
            h = np.where(x+plan["difference_step_log"] <= hi, plan["difference_step_log"], -plan["difference_step_log"])
            diffs = batch(x+np.diag(h), f"round{it+1}_sensitivity")
            good = [i for i, r in enumerate(diffs) if r["valid"] and r["log_factors"][i] != x[i]]
            if not good:
                steps.append({"round": it+1, "status": "no_valid_direction"})
                break
            r0, g0 = np.array(current["day_ratios"]), np.array(list(current["guards"].values()))
            jr, jg = np.zeros((len(r0), len(x))), np.zeros((len(g0), len(x)))
            for i in good:
                row = diffs[i]
                dx = row["log_factors"][i]-x[i]
                jr[:, i] = (np.array(row["day_ratios"])-r0)/dx
                jg[:, i] = (np.array(list(row["guards"].values()))-g0)/dx
            a, b = lo.copy(), hi.copy()
            missing = list(set(range(len(x)))-set(good))
            a[missing] = b[missing] = x[missing]
            proposed = lp_step(x, a, b, radius, r0, jr, g0, jg, reserve)
            step = {"round": it+1, "radius": radius, "anchor": current["attempt"],
                    "valid_derivatives": len(good), "linearized_proposal": proposed, "accepted": None}
            if proposed is not None and proposed["predicted_objective"] < current["objective"]:
                candidates = batch([x+alpha*np.array(proposed["delta"]) for alpha in plan["line_search_fractions"]], f"round{it+1}_backtrack")
                step["candidate_attempts"] = [r["attempt"] for r in candidates]
                passed = [r for r in candidates if fit_feasible(r) and r["objective"] <= current["objective"]-plan["minimum_step_objective_gain"]]
                if passed:
                    current = min(passed, key=lambda r: r["objective"])
                    step["accepted"] = current["attempt"]
            radius = min(plan["maximum_radius_log"], radius*1.25) if step["accepted"] else radius*.5
            steps.append(step)
            print(f"Round {it+1}: {len(trace)} actual attempts, accepted={step['accepted']}, worst dated ratio={current['objective']:.8g}", flush=True)
    maximum = 1+len(plan["continuation_start_fractions"])+plan["number_of_rounds"]*(len(lo)+len(plan["line_search_fractions"]))
    require(len(trace) <= maximum, "budget exceeded")
    result = {"actual_attempts": len(trace), "invalid_attempts": sum(not r["valid"] for r in trace),
              "maximum_attempts": maximum, "steps": steps, "selected": current,
              "corrected_fit_reference": reference, "global_optimality": False}
    write(folder/"result.json", result)
    seal(folder)
    verify_inputs(out)
    return {"attempts": len(trace), "selected_attempt": current["attempt"], "dated_gains": current["gain_by_day"]}


def original(out, f, label, profile, vector):
    plan, n = f["temporal"], f["numeric"]
    p = parameters_for(f, vector)
    full, fast = (rhs_for(f, p, plan["network"], backend) for backend in ("full", "joint"))
    folder = out/"audits"/label/profile
    folder.mkdir(parents=True)
    with threadpool_limits(1):
        arrays, stats = replay_evidence(full, f["initial"], 15, plan["fit_days"], n["numerical_profiles"][profile],
                                        n, lambda t,x: fast.rates(t,x)[:2])
    np.savez_compressed(folder/"replay.npz", **arrays)
    write(folder/"result.json", stats)
    seal(folder)
    print(f"{label} {profile}: original J15 numerical pass={stats['numerical_pass']}", flush=True)
    return stats


def audit(out):
    require(not (out/"audits").exists(), "preserve any interrupted audit; fresh successor required")
    f, obs = verify_inputs(out), read(out/"observations.json")
    check_seal(out/"fit")
    s = read(out/"fit/result.json")
    selected = s["selected"]["log_factors"]
    vectors = {"corrected_reference": [0.]*len(selected), "temporal_candidate": selected}
    with ProcessPoolExecutor(max_workers=3) as pool:
        jobs = [pool.submit(original, out, f, label, profile, x) for label, x in vectors.items() for profile in ("strict", "ultrastrict")]
        for future in as_completed(jobs):
            future.result()
    panel = panel_from_observations(obs, f["temporal"]["fit_days"], f["design"])
    checks, scored, rows = {}, {}, []
    for label in vectors:
        base = out/"audits"/label
        with np.load(base/"strict/replay.npz") as a, np.load(base/"ultrastrict/replay.npz") as b:
            require(np.array_equal(a["time"], b["time"]), "cross-tolerance support changed")
            values = [within(a[k], b[k], f["numeric"], "comparison") for k in ("states", "raw8", "executed8")]
        checks[label] = {"pass": all(v.all() for v in values) and all(read(base/profile/"result.json")["numerical_pass"]
                          for profile in ("strict", "ultrastrict")), "cross_checks_passed": sum(int(v.sum()) for v in values),
                         "cross_checks_total": sum(v.size for v in values)}
    for profile in ("strict", "ultrastrict"):
        prediction = {}
        for label in vectors:
            base = out/"audits"/label/profile
            check_seal(base)
            with np.load(base/"replay.npz") as a:
                names, time = a["pool_names"].tolist(), a["time"]
                ids = np.searchsorted(time, panel["days"])
                require(np.array_equal(time[ids], panel["days"]) and np.array_equal(a["accepted_states"][:, 0], f["initial"]), "exact J1 or actual sample time changed")
                prediction[label] = a["states"][np.ix_([names.index(p) for p in panel["names"]], ids)]
        ref = measure(prediction["corrected_reference"], panel)
        scored[profile] = evaluate_panel(prediction["temporal_candidate"], ref, panel, f["design"], f["temporal"])
        for i, p in enumerate(panel["names"]):
            for j, day in enumerate(panel["days"]):
                rows.append([profile, day, p, p in f["design"]["source_aliases"], panel["target"][i,j],
                             prediction["corrected_reference"][i,j], prediction["temporal_candidate"][i,j]])
    admitted = all(r["pass"] for r in checks.values()) and all(r["guards_pass"] and r["sufficient_every_day"] for r in scored.values())
    p = parameters_for(f, selected)
    result = {"original_checks": checks, "original_metrics": scored, "admitted_under_temporal_guards": admitted,
              "selected_attempt": s["selected"]["attempt"], "selected_Vmax": {k: p[k] for k in f["resolved_capacities"]},
              "same_network_corrected_reference": True, "Km_changed": False, "production_promoted": False,
              "biological_calibration": False, "J46_replayed": False}
    write(out/"validation_summary.json", result)
    write_csv(out/"all55_by_day.csv", ["profile", "day", "pool", "alias", "nominal_mM", "corrected_reference_mM", "temporal_candidate_mM"], rows)
    verify_inputs(out)
    write(out/"manifest.json", {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob("*")) if p.is_file()})
    return {"admitted": admitted, "numerical_checks": checks, "dated_gains": {k: v["gain_by_day"] for k,v in scored.items()}}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--audit", action="store_true")
    a = p.parse_args()
    with threadpool_limits(1):
        print(audit(a.out.resolve()) if a.audit else search(a.out.resolve()))
