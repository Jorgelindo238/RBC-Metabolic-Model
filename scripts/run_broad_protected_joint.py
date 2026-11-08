"""Separate frozen eleven-pool successor; historical campaigns stay immutable."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path
import sys
from time import perf_counter

import numpy as np
from scipy.optimize import minimize
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from fla_joint_calibration import COORDINATES, unpack
from fla_broad_protected_calibration import POOLS, training_data, score, guard_contract, assess, evaluate, best_feasible, predict_broad
from run_protected_joint import seal, check_seal, verify_inputs
from run_glut_only_free_replay import sha, write, replay, close

CONFIG = ROOT/"config/fla_broad_protected_joint.json"


def prepare(out):
    from verify_protected_joint import verify as verify_parent
    from verify_protected_f6p_b23pg import verify as verify_guard_audit
    if out.exists():
        raise ValueError("fresh campaign directory required")
    design = json.loads(CONFIG.read_text())
    parent, guard_audit = (ROOT/design[k] for k in ("parent_archive", "guard_audit_archive"))
    with threadpool_limits(limits=1):
        evidence = {"parent": verify_parent(parent), "guard_audit": verify_guard_audit(guard_audit)}
    prior = json.loads((parent/"execution_design.json").read_text())
    observations = json.loads((parent/"observations.json").read_text())
    for alias, canonical in design["source_aliases_excluded"].items():
        if observations["values"][alias] != observations["values"][canonical]:
            raise ValueError("unresolved source alias")
    times, target = training_data(observations, design["training_end_day"])
    if times.tolist() != design["training_times"]:
        raise ValueError("actual original training days required")
    baseline = ROOT/prior["parent_design"]["source_archive"]/"J1_J10/glut_real_candidate_ultrastrict/replay.npz"
    with np.load(baseline) as a:
        names = a["pool_names"].tolist()
        indices = np.searchsorted(a["time"], times)
        if not np.array_equal(a["time"][indices], times) or not np.array_equal(a["initial"], prior["initial"]):
            raise ValueError("baseline initialization/time mismatch")
        reference = a["states"][[names.index(p) for p in POOLS]][:, indices]
    if any(prior["initial"][names.index(p)] != values[0] for p, values in observations["values"].items()):
        raise ValueError("exact55 measured J1 required")
    guards = guard_contract(reference, target, design)
    proposal = json.loads((guard_audit/"proposed_guard_contract.json").read_text())
    proposed_reference = [r["reference_RMSE_mM"] for r in proposal["RMSE_guards"]]
    proposed_reference += [r["reference_absolute_error_mM"] for r in proposal["pointwise_guards"]]
    if not np.array_equal(guards["reference_errors_mM"], proposed_reference):
        raise ValueError("predeclared guard reference changed")
    previous = np.array(json.loads((parent/"summary.json").read_text())["selected"]["selected_log_factors"])
    paths = [CONFIG, Path(__file__), ROOT/"src/fla_broad_protected_calibration.py",
        ROOT/"scripts/verify_broad_protected_joint.py", ROOT/"qa/test_broad_protected_joint.py",
        parent/"execution_design.json", parent/"observations.json", parent/"summary.json", parent/"manifest.json",
        guard_audit/"manifest.json", guard_audit/"proposed_guard_contract.json", baseline]
    paths += [ROOT/name for name in prior["input_sha256"]]
    frozen = {"design": design, "parent_design": prior["parent_design"],
        **{k: prior[k] for k in ("initial", "parameters", "candidate", "resolved_capacities")},
        "guards": guards, "reference_predictions": reference.tolist(), "evidence_verification": evidence,
        "starts": {"control": [0.]*6, "previous_nine": previous.tolist(), "midpoint": (previous/2).tolist()},
        "input_sha256": {p.relative_to(ROOT).as_posix(): sha(p) for p in paths},
        "source_cells_verified": 770, "exact_J1_entries": 55, "source_normalization_verified": False,
        "new_kinetic_coordinates": False, "biological_promotion": False}
    out.mkdir(parents=True)
    write(out/"execution_design.json", frozen)
    write(out/"observations.json", observations)
    write(out/"source_seal.json", {p: sha(out/p) for p in ("execution_design.json", "observations.json")})
    return {"prepared": True, "constraints": len(guards["constraint_names"]), "observations": target.size,
            "evidence_checks": {k: v["checks"] for k, v in evidence.items()}}


def fit_one(out_string, label, resume):
    out = Path(out_string)
    frozen = verify_inputs(out)
    design = frozen["design"]
    folder = out/"fits"/label
    if (folder/"files_seal.json").exists():
        if not resume:
            raise ValueError("completed fit; explicit resume or successor required")
        check_seal(folder)
        return json.loads((folder/"result.json").read_text())
    if folder.exists() and not resume:
        raise ValueError("partial fit; explicit resume required")
    folder.mkdir(parents=True, exist_ok=True)
    times, target = training_data(json.loads((out/"observations.json").read_text()), design["training_end_day"])
    trace_path = folder/"trace.jsonl"
    trace = [json.loads(line) for line in trace_path.read_text().splitlines()] if trace_path.exists() else []
    cache = {tuple(row["log_factors"]): row for row in trace}
    bounds = np.log([frozen["parent_design"]["factor_bounds"][name] for name in COORDINATES])
    options = design["optimizer"]
    limit = options["primary_actual_integrations"]
    begin = perf_counter()

    class BudgetExhausted(Exception):
        pass

    def get(x):
        key = tuple(float(v) for v in x)
        if key in cache:
            return cache[key]
        if len(trace) >= limit:
            raise BudgetExhausted
        try:
            row = evaluate(np.array(x), frozen, times, target)
        except (ValueError, RuntimeError, FloatingPointError) as error:
            row = {"log_factors": list(key), "valid": False, "error": str(error), "objective_penalty": 1e12}
        row["call"] = len(trace)+1
        trace.append(row)
        cache[key] = row
        with trace_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, allow_nan=False)+"\n")
            stream.flush()
        if len(trace) % 10 == 0:
            best = best_feasible(trace)
            progress = {"calls": len(trace), "best_feasible_NLL": best["score"]["negative_log_likelihood"],
                "feasible_evaluations": sum(r["valid"] and r["guards"]["passed"] for r in trace),
                "best_feasible_log_factors": best["log_factors"], "elapsed_this_attempt_seconds": perf_counter()-begin}
            write(folder/"progress.json", progress)
            print(f"{label}: calls={len(trace)} feasibleNLL={progress['best_feasible_NLL']:.8g}", flush=True)
        return row

    def values(x):
        row = get(x)
        if not row["valid"]:
            return 1e12, np.full(len(frozen["guards"]["constraint_names"]), -1e6)
        return row["score"]["negative_log_likelihood"], np.array(row["guards"]["margins"])

    jac_cache = {}
    def derivatives(x):
        key = tuple(float(v) for v in x)
        if key not in jac_cache:
            cost, constraints = values(x)
            gradient, jacobian = np.zeros(6), np.zeros((len(constraints), 6))
            for j in range(6):
                step = options["log_factor_difference_step"]
                step = step if x[j]+step <= bounds[j, 1] else -step
                other = x.copy()
                other[j] = np.clip(x[j]+step, bounds[j, 0], bounds[j, 1])
                cost1, constraints1 = values(other)
                gradient[j] = (cost1-cost)/(other[j]-x[j])
                jacobian[:, j] = (constraints1-constraints)/(other[j]-x[j])
            jac_cache[key] = gradient, jacobian
        return jac_cache[key]

    control = get(np.zeros(6))
    if not control["valid"] or not control["guards"]["passed"]:
        raise ValueError("control violates frozen guards; fail closed")
    terminal = np.array(best_feasible(trace)["log_factors"] if resume and len(trace) > 1 else frozen["starts"][label])
    stages_path = folder/"optimizer_stages.json"
    stages = json.loads(stages_path.read_text()) if stages_path.exists() else []
    for stage in stages:
        if stage["state"] == "running":
            stage.update(state="interrupted_without_convergence_claim", actual_integrations=len(trace)-stage["calls_before"])
    success = False
    for cap in (options["primary_actual_integrations"], options["secondary_cumulative_actual_integrations"]):
        if len(trace) >= cap:
            continue
        limit, before = cap, len(trace)
        stage = {"state": "running", "cumulative_actual_limit": cap, "calls_before": before, "resumed": bool(resume)}
        stages.append(stage)
        write(stages_path, stages)
        try:
            sol = minimize(lambda x: values(x)[0], terminal, method="SLSQP", jac=lambda x: derivatives(x)[0],
                bounds=bounds, constraints=[{"type": "ineq", "fun": lambda x: values(x)[1], "jac": lambda x: derivatives(x)[1]}],
                options={"maxiter": options["maxiter"], "ftol": options["ftol"]})
            terminal, success = sol.x, bool(sol.success)
            stage.update(state="complete", success=success, message=str(sol.message),
                         reported_nfev=int(sol.nfev), reported_njev=int(sol.njev))
        except BudgetExhausted:
            terminal = np.array(best_feasible(trace)["log_factors"])
            stage.update(state="complete", success=False, message="actual_integration_budget_exhausted")
        stage["actual_integrations"] = len(trace)-before
        write(stages_path, stages)
        if success:
            break
    best = best_feasible(trace)
    parameters, kinetics, factors = unpack(best["log_factors"], frozen["parameters"], frozen["candidate"]["glucose_kinetics"],
        frozen["resolved_capacities"], frozen["parent_design"]["factor_bounds"])
    prediction, sol, _ = predict_broad(np.array(frozen["initial"]), parameters, kinetics, design["training_end_day"], times)
    guards = assess(prediction, target, frozen["guards"])
    if not guards["passed"]:
        raise ValueError("selected fitting replay violates frozen guards")
    np.savez_compressed(folder/"fit_replay.npz", sample_time=times, prediction=prediction, observed=target,
                        accepted_time=sol.t, accepted_states=sol.y)
    result = {"label": label, "training_end_day": design["training_end_day"], "source_times": times.tolist(),
        "actual_objective_integrations": len(trace), "feasible_evaluations": sum(r["valid"] and r["guards"]["passed"] for r in trace),
        "optimizer_success": success, "optimizer_stages": stages, "terminal_log_factors": terminal.tolist(),
        "selected_log_factors": best["log_factors"], "factors": factors, "parameters": parameters, "glucose_kinetics": kinetics,
        "training_score": score(prediction, target), "training_guards": guards,
        "is_control": best["log_factors"] == [0.]*6, "production_promoted": False}
    write(folder/"result.json", result)
    seal(folder)
    print(f"{label} done: converged={success} calls={len(trace)} feasibleNLL={result['training_score']['negative_log_likelihood']:.8g}", flush=True)
    return result


def audit(out, frozen, selected, end):
    folder = out/"audits"/(selected["label"]+f"_J{int(end)}")
    if (folder/"files_seal.json").exists():
        check_seal(folder)
        result = json.loads((folder/"audit_summary.json").read_text())
        if result["log_factors"] != selected["selected_log_factors"]:
            raise ValueError("completed audit belongs to different parameters")
        return result
    if folder.exists():
        raise ValueError("partial original-path audit preserved; successor required")
    base = ROOT/frozen["parent_design"]["source_archive"]
    numerical = json.loads((base/"execution_design.json").read_text())["design"]
    design = {**numerical, "cases": ["glut_real_candidate"], "guard_pools": list(POOLS)}
    observations = json.loads((out/"observations.json").read_text())
    candidate = {"glucose_kinetics": selected["glucose_kinetics"]}
    results, arrays, guards = [], [], []
    for profile in frozen["parent_design"]["numerical_profiles"]:
        result, values = replay(folder, "glut_real_candidate", profile, end, np.array(frozen["initial"]), selected["parameters"],
            candidate, candidate["glucose_kinetics"], design, np.array(observations["time"]),
            {p: np.array(v) for p, v in observations["values"].items()})
        results.append(result)
        arrays.append(values)
        if end >= frozen["design"]["training_end_day"]:
            times, target = training_data(observations, frozen["design"]["training_end_day"])
            with np.load(folder/f"J1_J{int(end)}"/f"glut_real_candidate_{profile}/replay.npz") as a:
                prediction = a["states"][[a["pool_names"].tolist().index(p) for p in POOLS]][:, np.searchsorted(a["time"], times)]
            guards.append({"profile": profile, **assess(prediction, target, frozen["guards"], phase="audit")})
    comparisons = [close(arrays[0][i], arrays[1][i], numerical, "comparison") for i in range(3)]
    times, _ = training_data(observations, min(end, frozen["design"]["training_end_day"]))
    prediction, fast, rhs = predict_broad(np.array(frozen["initial"]), selected["parameters"], selected["glucose_kinetics"],
        end, times, profile=frozen["parent_design"]["numerical_profiles"]["ultrastrict"])
    with np.load(folder/f"J1_J{int(end)}/glut_real_candidate_ultrastrict/replay.npz") as a:
        native = a["states"][[rhs.names.index(p) for p in POOLS]][:, np.searchsorted(a["time"], times)]
        fast_states = fast.sol(a["time"])
        parity = bool(np.allclose(prediction, native, rtol=1e-5, atol=1e-7)
                      and np.allclose(fast_states[:113], a["states"][:113], rtol=.01, atol=1e-5))
        np.savez_compressed(folder/"fast_parity.npz", time=a["time"], states=fast_states, sample_time=times, prediction=prediction)
    result = {"label": selected["label"], "log_factors": selected["selected_log_factors"], "end_day": end,
        "numerical_pass": bool(all(r["numerical_pass"] for r in results) and all(c.all() for c in comparisons) and parity),
        "guard_pass": all(g["passed"] for g in guards), "training_guards": guards, "fast_full_parity": parity,
        "convergence_checks_passed": sum(int(c.sum()) for c in comparisons), "convergence_checks_total": sum(c.size for c in comparisons),
        "results": results}
    write(folder/"audit_summary.json", result)
    seal(folder)
    return result


def run(out, workers, resume):
    if (out/"manifest.json").exists():
        raise ValueError("completed immutable campaign")
    frozen = verify_inputs(out)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        jobs = [pool.submit(fit_one, str(out), label, resume) for label in frozen["starts"]]
        fits = []
        for job in as_completed(jobs):
            fits.append(job.result())
            write(out/"progress.json", {"completed_fits": len(fits)})
    fits.sort(key=lambda r: r["label"])
    selected = min(fits, key=lambda r: r["training_score"]["negative_log_likelihood"])
    trace = [json.loads(line) for line in (out/"fits/control/trace.jsonl").read_text().splitlines()]
    control = next(r for r in trace if r["log_factors"] == [0.]*6)
    parameters, kinetics, factors = unpack(np.zeros(6), frozen["parameters"], frozen["candidate"]["glucose_kinetics"],
        frozen["resolved_capacities"], frozen["parent_design"]["factor_bounds"])
    fallback = {"label": "control_fallback", "selected_log_factors": [0.]*6, "is_control": True,
        "parameters": parameters, "glucose_kinetics": kinetics, "factors": factors, "training_score": control["score"]}
    if control["score"]["negative_log_likelihood"]-selected["training_score"]["negative_log_likelihood"] < frozen["design"]["minimum_training_NLL_gain"]:
        selected = fallback
    attempts, audits = [], []
    for attempt in range(2):
        current = []
        for end in frozen["design"]["audit_end_days"]:
            result = audit(out, frozen, selected, end)
            current.append(result)
            if not result["numerical_pass"] or not result["guard_pass"]:
                break
        audits += current
        accepted = all(r["numerical_pass"] and r["guard_pass"] for r in current) and current[-1]["end_day"] == 46
        attempts.append({"label": selected["label"], "log_factors": selected["selected_log_factors"], "accepted": accepted})
        if accepted or selected["is_control"]:
            break
        selected = fallback
    summary = {"fits": fits, "selected": selected, "selection_attempts": attempts, "audits": audits,
        "accepted_numeric_and_training_guards": attempts[-1]["accepted"], "selected_is_control": selected["is_control"],
        "total_objective_integrations": sum(r["actual_objective_integrations"] for r in fits),
        "kinetic_box_expanded": False, "initial_states_changed": False, "source_values_changed": False,
        "late_observations_used_in_selection": False, "production_promoted": False,
        "all_observed_pools_hard_guarded": False, "guarded_pools": list(POOLS), "pointwise_guarded_pools": ["PEP"]}
    write(out/"summary.json", summary)
    verify_inputs(out)
    write(out/"manifest.json", {"output_sha256": {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob("*")) if p.is_file()}})
    return {k: summary[k] for k in ("accepted_numeric_and_training_guards", "selected_is_control", "total_objective_integrations", "production_promoted")}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prepare", type=Path)
    p.add_argument("--run", type=Path)
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--resume", action="store_true")
    args = p.parse_args()
    if bool(args.prepare) == bool(args.run) or not 1 <= args.workers <= 3:
        p.error("choose prepare/run and1-3 numerical workers")
    print(json.dumps(prepare(args.prepare.resolve()) if args.prepare else run(args.run.resolve(), args.workers, args.resume), indent=2))
