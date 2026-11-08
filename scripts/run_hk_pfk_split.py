"""Reversible nested HK/PFK screen and fits under the existing13 constraints."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import copy
import json
from pathlib import Path
import sys
from time import perf_counter

import numpy as np
from scipy.optimize import minimize
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from fla_hk_pfk_split import (FREE, POOLS, seed_coordinates, coordinate_bounds, unpack, evaluate,
    inner_margins, training_data, predict_broad, assess, score, best_feasible, choose_nested)
from run_protected_joint import verify_inputs, seal, check_seal
from run_glut_only_free_replay import sha, write
from run_broad_protected_joint import audit
from restore_broad_interior import interior_step

CONFIG = ROOT/"config/fla_hk_pfk_split.json"


def prepare(out):
    from verify_broad_protected_joint import verify
    if out.exists(): raise ValueError("fresh dissociation archive required")
    design = json.loads(CONFIG.read_text())
    parent = ROOT/design["parent_archive"]
    with threadpool_limits(limits=1): evidence = verify(parent)
    prior = json.loads((parent/"execution_design.json").read_text())
    selected = json.loads((parent/"summary.json").read_text())["selected"]
    observations = json.loads((parent/"observations.json").read_text())
    times, target = training_data(observations, design["training_end_day"])
    if times.tolist() != design["training_times"]: raise ValueError("actual J4/J8 required")
    initial_log = selected["selected_log_factors"][1]
    frozen = {"design": design, "parent_design": prior["parent_design"], "initial": prior["initial"],
        "guards": copy.deepcopy(prior["guards"]), "parameters": selected["parameters"], "kinetics": selected["glucose_kinetics"],
        "primitive_capacities": {p: prior["resolved_capacities"][p] for p in FREE},
        "primitive_factor_bounds": prior["parent_design"]["factor_bounds"]["investment"],
        "seed_log_investment": initial_log, "parent_verification": evidence,
        "fit_cases": {"paired_seed": {"mode": "paired", "offset": [0.]},
            "paired_directed": {"mode": "paired", "offset": [float(np.log(design["directed_start_multiplier"]))]},
            "split_seed": {"mode": "split", "offset": [0., 0.]},
            "split_directed": {"mode": "split", "offset": [float(np.log(design["directed_start_multiplier"])), 0.]}}}
    for mode in ("paired", "split"):
        parameters, kinetics, _ = unpack(seed_coordinates(frozen, mode), frozen, mode)
        if parameters != selected["parameters"] or kinetics != selected["glucose_kinetics"]:
            raise ValueError("paired/split seed does not reproduce parent parameters exactly")
    paths = [CONFIG, Path(__file__), ROOT/"src/fla_hk_pfk_split.py", ROOT/"qa/test_hk_pfk_split.py",
        ROOT/"scripts/verify_hk_pfk_split.py", parent/"execution_design.json", parent/"observations.json",
        parent/"summary.json", parent/"manifest.json"]+[ROOT/p for p in prior["input_sha256"]]
    frozen["input_sha256"] = {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}
    out.mkdir(parents=True)
    write(out/"execution_design.json", frozen)
    write(out/"observations.json", observations)
    write(out/"source_seal.json", {p: sha(out/p) for p in ("execution_design.json", "observations.json")})
    return {"prepared": True, "guards": len(frozen["guards"]["constraint_names"]),
        "parent_checks": evidence["checks"], "observations": target.size,
        "absolute_capacity_bounds": {p: (np.array(frozen["primitive_factor_bounds"])*v).tolist() for p, v in frozen["primitive_capacities"].items()}}


def screen(out, frozen):
    folder = out/"screen"
    if (folder/"files_seal.json").exists():
        check_seal(folder)
        return json.loads((folder/"results.json").read_text())
    if folder.exists(): raise ValueError("partial screen preserved; fresh successor required")
    folder.mkdir()
    times, target = training_data(json.loads((out/"observations.json").read_text()), frozen["design"]["training_end_day"])
    rows = []
    for label, offset in frozen["design"]["screen_offsets"].items():
        x = seed_coordinates(frozen, "split")+np.array(offset)*frozen["design"]["screen_log_step"]
        try:
            row, sol = evaluate(x, frozen, "split", times, target)
        except (ValueError, RuntimeError, FloatingPointError) as error:
            if label == "baseline": raise
            row, sol = {"log_factors": x.tolist(), "mode": "split", "valid": False, "error": str(error)}, None
        row["label"] = label
        rows.append(row)
        if sol is not None:
            np.savez_compressed(folder/(label+".npz"), sample_time=times, observed=target,
                prediction=np.array(row["predictions"]), accepted_time=sol.t, accepted_states=sol.y)
        write(folder/"results.json", rows)
        print(f"screen {label}: "+(f"NLL={row['score']['negative_log_likelihood']:.8g} guards={row['guards']['passed']}" if row["valid"] else row["error"]), flush=True)
    seal(folder)
    return rows


def fit_one(out_string, label, resume):
    out = Path(out_string)
    f = verify_inputs(out)
    case = f["fit_cases"][label]
    mode = case["mode"]
    folder = out/"fits"/label
    if (folder/"files_seal.json").exists():
        if not resume: raise ValueError("completed fit; explicit resume required")
        check_seal(folder)
        return json.loads((folder/"result.json").read_text())
    if folder.exists() and not resume: raise ValueError("partial fit; explicit resume required")
    folder.mkdir(parents=True, exist_ok=True)
    times, target = training_data(json.loads((out/"observations.json").read_text()), f["design"]["training_end_day"])
    trace_path = folder/"trace.jsonl"
    trace = [json.loads(line) for line in trace_path.read_text().splitlines()] if trace_path.exists() else []
    cache = {tuple(r["log_factors"]): r for r in trace}
    bounds = coordinate_bounds(f, mode)
    options = f["design"]["optimizer"]
    limit = options["primary_actual_integrations"]
    best_nll, last_progress = float("inf"), 0
    for row in trace:
        if row["valid"] and row["guards"]["passed"] and row["score"]["negative_log_likelihood"] < best_nll-options["admissible_progress_NLL"]:
            best_nll, last_progress = row["score"]["negative_log_likelihood"], row["call"]
    begin = perf_counter()
    repair_active = False
    class BudgetStop(Exception): pass
    class StagnationStop(Exception): pass
    def get(x):
        nonlocal best_nll, last_progress
        key = tuple(float(v) for v in x)
        if key in cache: return cache[key]
        if len(trace) >= limit: raise BudgetStop
        if (not repair_active and len(trace) >= options["stagnation_minimum_calls"]
                and len(trace)-last_progress >= options["stagnation_patience_calls"]): raise StagnationStop
        try: row, _ = evaluate(np.array(x), f, mode, times, target)
        except (ValueError, RuntimeError, FloatingPointError) as error:
            row = {"log_factors": list(key), "mode": mode, "valid": False, "error": str(error)}
        row["call"] = len(trace)+1
        trace.append(row)
        cache[key] = row
        with trace_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, allow_nan=False)+"\n")
            stream.flush()
        if row["valid"] and row["guards"]["passed"] and row["score"]["negative_log_likelihood"] < best_nll-options["admissible_progress_NLL"]:
            best_nll, last_progress = row["score"]["negative_log_likelihood"], row["call"]
        if len(trace) % 10 == 0:
            best = best_feasible(trace)
            write(folder/"progress.json", {"calls": len(trace), "best_feasible_NLL": best["score"]["negative_log_likelihood"],
                "last_admissible_progress_call": last_progress, "elapsed_seconds": perf_counter()-begin})
            print(f"{label}: calls={len(trace)} feasibleNLL={best['score']['negative_log_likelihood']:.8g}", flush=True)
        return row
    def values(x):
        row = get(x)
        return (row["score"]["negative_log_likelihood"], inner_margins(row, f)) if row["valid"] else (1e12, np.full(13, -1e6))
    jac_cache = {}
    def derivatives(x):
        key = tuple(float(v) for v in x)
        if key not in jac_cache:
            value, margins = values(x)
            gradient, jacobian = np.zeros(len(x)), np.zeros((13, len(x)))
            for j in range(len(x)):
                h = options["difference_step"] if x[j]+options["difference_step"] <= bounds[j, 1] else -options["difference_step"]
                other = x.copy(); other[j] += h
                value1, margins1 = values(other)
                gradient[j], jacobian[:, j] = (value1-value)/h, (margins1-margins)/h
            jac_cache[key] = gradient, jacobian
        return jac_cache[key]
    seed = get(seed_coordinates(f, mode))
    if not seed["valid"] or not seed["guards"]["passed"]: raise ValueError("parent seed not feasible under unchanged caps")
    terminal = np.array(best_feasible(trace)["log_factors"] if resume and len(trace)>1 else seed_coordinates(f, mode)+case["offset"])
    stages_path = folder/"optimizer_stages.json"
    stages = json.loads(stages_path.read_text()) if stages_path.exists() else []
    for stage in stages:
        if stage.get("state") == "running": stage["state"] = "interrupted_without_convergence_claim"
    success = False
    for cap in (options["primary_actual_integrations"], options["secondary_cumulative_actual_integrations"]):
        if len(trace) >= cap: continue
        limit = cap
        stage = {"state": "running", "cumulative_actual_limit": cap, "calls_before": len(trace)}
        stages.append(stage); write(stages_path, stages)
        stopped = False
        try:
            sol = minimize(lambda x: values(x)[0], terminal, jac=lambda x: derivatives(x)[0], method="SLSQP", bounds=bounds,
                constraints=[{"type": "ineq", "fun": lambda x: values(x)[1], "jac": lambda x: derivatives(x)[1]}],
                options={"maxiter": options["maxiter"], "ftol": options["ftol"]})
            terminal, success = sol.x, bool(sol.success)
            stage.update(state="complete", success=success, message=str(sol.message), reported_nfev=int(sol.nfev), reported_njev=int(sol.njev))
        except BudgetStop:
            stage.update(state="complete", success=False, message="actual_integration_budget_exhausted")
        except StagnationStop:
            stage.update(state="complete", success=False, message="preregistered_no_admissible_progress_stop")
            stopped = True
        stage["actual_integrations"] = len(trace)-stage["calls_before"]
        write(stages_path, stages)
        if success or stopped: break
        terminal = np.array(best_feasible(trace)["log_factors"])
    # A single within-budget inward repair cannot change any non-HK/PFK value.
    if not success and options["one_optional_within_budget_interior_repair"]:
        best = best_feasible(trace)
        candidates = [r for r in trace if r["valid"] and max(0., -min(r["guards"]["margins"])) <= 1e-5
                      and r["score"]["negative_log_likelihood"] < best["score"]["negative_log_likelihood"]-f["design"]["minimum_NLL_gain"]]
        if candidates and len(trace)+len(bounds)+1 <= options["secondary_cumulative_actual_integrations"]:
            limit = options["secondary_cumulative_actual_integrations"]
            repair_active = True
            row = min(candidates, key=lambda r:r["score"]["negative_log_likelihood"])
            x = np.array(row["log_factors"])
            _, jac = derivatives(x)
            target_margins = np.array(row["guards"]["margins"])-inner_margins(row, f)
            correction = interior_step(np.array(row["guards"]["margins"]), jac, target_margins, x, bounds, options["repair_trust_radius"])
            repair = {"state": "complete", "method": "same_coordinate_interior_repair", "linear_success": bool(correction.success)}
            if correction.success:
                trial = get(x+correction.x[:len(x)])
                repair["actual_guard_pass"] = trial["valid"] and trial["guards"]["passed"]
            stages.append(repair); write(stages_path, stages)
    best = best_feasible(trace)
    parameters, kinetics, factors = unpack(best["log_factors"], f, mode)
    prediction, sol, _ = predict_broad(np.array(f["initial"]), parameters, kinetics, f["design"]["training_end_day"], times)
    guards = assess(prediction, target, f["guards"])
    if not guards["passed"]: raise ValueError("selected replay not feasible")
    np.savez_compressed(folder/"fit_replay.npz", sample_time=times, observed=target, prediction=prediction,
                        accepted_time=sol.t, accepted_states=sol.y)
    result = {"label": label, "mode": mode, "free_dimensions": len(bounds), "selected_log_factors": best["log_factors"],
        "terminal_log_factors": terminal.tolist(), "factors": factors, "parameters": parameters, "glucose_kinetics": kinetics,
        "actual_objective_integrations": len(trace), "feasible_evaluations": sum(r["valid"] and r["guards"]["passed"] for r in trace),
        "optimizer_success": success, "optimizer_stages": stages, "training_score": score(prediction, target),
        "training_guards": guards, "is_parent": parameters == f["parameters"], "production_promoted": False}
    write(folder/"result.json", result); seal(folder)
    print(f"{label} done: success={success} calls={len(trace)} NLL={result['training_score']['negative_log_likelihood']:.8g}", flush=True)
    return result


def run(out, workers, resume):
    if (out/"manifest.json").exists(): raise ValueError("completed immutable archive")
    f = verify_inputs(out)
    screens = screen(out, f)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        jobs = [pool.submit(fit_one, str(out), name, resume) for name in f["fit_cases"]]
        fits = [job.result() for job in as_completed(jobs)]
    fits.sort(key=lambda r:r["label"])
    paired = min((r for r in fits if r["mode"] == "paired"), key=lambda r:r["training_score"]["negative_log_likelihood"])
    split = min((r for r in fits if r["mode"] == "split"), key=lambda r:r["training_score"]["negative_log_likelihood"])
    seed = next(r for r in screens if r["label"] == "baseline")
    parent = {"label": "parent_control", "mode": "paired", "selected_log_factors": seed_coordinates(f, "paired").tolist(),
        "parameters": f["parameters"], "glucose_kinetics": f["kinetics"], "training_score": seed["score"], "is_parent": True}
    chosen, paired_reference, split_gain = choose_nested(parent, paired, split, f["design"]["minimum_NLL_gain"])
    audits, attempts = [], []
    parent_summary = json.loads((ROOT/f["design"]["parent_archive"]/"summary.json").read_text())
    # Validate a changed paired comparator on the same original-path early data.
    if not paired_reference["is_parent"]:
        r = audit(out, f, paired_reference, 10.)
        audits.append(r)
        if not r["numerical_pass"] or not r["guard_pass"]:
            paired_reference = parent
    queue = [chosen, paired_reference, parent]
    seen = set()
    for candidate in queue:
        signature = (candidate["parameters"][FREE[0]], candidate["parameters"][FREE[1]])
        if signature in seen: continue
        seen.add(signature)
        if candidate["is_parent"]:
            passed = bool(parent_summary["accepted_numeric_and_training_guards"])
            attempts.append({"label": candidate["label"], "accepted": passed, "reused_verified_parent_audits": True})
        else:
            current = []
            for end in f["design"]["audit_end_days"]:
                r = audit(out, f, candidate, end)
                if not any(a["label"] == r["label"] and a["end_day"] == end for a in audits): audits.append(r)
                current.append(r)
                if not r["numerical_pass"] or not r["guard_pass"]: break
            passed = all(r["numerical_pass"] and r["guard_pass"] for r in current) and current[-1]["end_day"] == 46
            attempts.append({"label": candidate["label"], "accepted": passed, "reused_verified_parent_audits": False})
        if passed: break
    summary = {"fits": fits, "selected": candidate, "selection_attempts": attempts, "audits": audits,
        "paired_reference": paired_reference, "best_paired": paired, "best_split": split, "split_training_NLL_gain_vs_best_paired_found": split_gain,
        "accepted_numeric_and_training_guards": passed, "selected_is_parent": candidate["is_parent"],
        "selected_is_split": candidate["mode"] == "split", "screen_objective_integrations": len(screens),
        "fit_objective_integrations": sum(r["actual_objective_integrations"] for r in fits),
        "all_other_parameters_changed": False, "primitive_bounds_expanded": False, "guard_caps_changed": False,
        "source_values_changed": False, "initial_states_changed": False, "late_data_used_in_selection": False,
        "production_promoted": False, "paired_global_optimality_proved": False}
    write(out/"summary.json", summary); verify_inputs(out)
    write(out/"manifest.json", {"output_sha256": {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob("*")) if p.is_file()}})
    return {k: summary[k] for k in ("accepted_numeric_and_training_guards", "selected_is_split", "screen_objective_integrations", "fit_objective_integrations", "split_training_NLL_gain_vs_best_paired_found", "production_promoted")}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prepare", type=Path); p.add_argument("--run", type=Path)
    p.add_argument("--workers", type=int, default=3); p.add_argument("--resume", action="store_true")
    args = p.parse_args()
    if bool(args.prepare) == bool(args.run) or not 1 <= args.workers <= 3: p.error("choose prepare/run and1-3 numerical workers")
    print(json.dumps(prepare(args.prepare.resolve()) if args.prepare else run(args.run.resolve(), args.workers, args.resume), indent=2))
