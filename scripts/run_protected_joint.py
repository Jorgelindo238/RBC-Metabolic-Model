"""Fixed-source constrained successor; no old source or kinetic box is changed."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path
import sys
from time import perf_counter

import numpy as np
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fla_joint_calibration import COORDINATES, unpack
from fla_protected_calibration import POOLS, training_data, score, guard_contract, assess, evaluate, best_feasible, predict_nine
from run_glut_only_free_replay import sha, write, replay, close

CONFIG = ROOT / "config/fla_protected_joint.json"


def seal(folder):
    write(folder / "files_seal.json", {p.relative_to(folder).as_posix(): sha(p)
        for p in sorted(folder.rglob("*")) if p.is_file() and p.name != "files_seal.json"})


def check_seal(folder):
    for p, digest in json.loads((folder / "files_seal.json").read_text()).items():
        if sha(folder / p) != digest:
            raise ValueError(f"changed completed artifact:{folder/p}")


def prepare(out):
    from openpyxl import load_workbook
    if out.exists():
        raise ValueError("fresh protected campaign directory required")
    design = json.loads(CONFIG.read_text())
    parent = ROOT / design["parent_archive"]
    prior = json.loads((parent / "execution_design.json").read_text())
    parent_design = json.loads((ROOT / design["parent_config"]).read_text())
    for p, digest in prior["input_sha256"].items():
        if sha(ROOT / p) != digest:
            raise ValueError(f"parent input changed:{p}; do not reuse its reference silently")
    for p, digest in json.loads((parent / "manifest.json").read_text())["output_sha256"].items():
        if sha(parent / p) != digest:
            raise ValueError(f"parent output changed:{p}")
    observations = json.loads((parent / "observations.json").read_text())
    book = load_workbook(ROOT / parent_design["source_workbook"], read_only=True, data_only=False)
    try:
        rows = list(book[parent_design["source_sheet"]].iter_rows(values_only=True))
        original = {r[0]: list(r[1:15]) for r in rows[1:] if isinstance(r[0], str) and isinstance(r[1], (int, float))}
        if original != observations["values"] or list(rows[0][1:15]) != observations["time"] or len(original) != 55:
            raise ValueError("original770 source values or sample times changed")
    finally:
        book.close()
    times, target = training_data(observations, design["training_end_day"])
    if times.tolist() != design["training_times"]:
        raise ValueError("actual original training samples required")
    baseline_path = ROOT / parent_design["source_archive"] / "J1_J10" / design["reference_case"] / "replay.npz"
    with np.load(baseline_path) as a:
        names = a["pool_names"].tolist()
        indices = np.searchsorted(a["time"], times)
        if not np.array_equal(a["time"][indices], times) or not np.array_equal(a["initial"], prior["initial"]):
            raise ValueError("baseline time/initialization mismatch")
        reference = a["states"][[names.index(p) for p in POOLS]][:, indices]
    if any(prior["initial"][names.index(p)] != values[0] for p, values in original.items()):
        raise ValueError("all55 measured initial states must remain exact")
    previous_fit = json.loads((parent / "summary.json").read_text())["selected"]
    rejected = np.array(previous_fit["selected_log_factors"])
    starts = {"control": [0.]*6, "rejected_joint": rejected.tolist(), "midpoint": (rejected/2).tolist()}
    paths = [CONFIG, ROOT / design["parent_config"], Path(__file__), ROOT / "src/fla_protected_calibration.py",
        ROOT / "scripts/verify_protected_joint.py", ROOT / "qa/test_protected_joint.py",
        parent / "execution_design.json", parent / "manifest.json", parent / "observations.json",
        parent / "summary.json", baseline_path]
    paths += [ROOT / p for p in prior["input_sha256"]]
    frozen = {"design": design, "parent_design": parent_design, "parent_design_path": str(parent),
        "initial": prior["initial"], "parameters": prior["parameters"], "candidate": prior["candidate"],
        "resolved_capacities": prior["resolved_capacities"], "starts": starts,
        "guards": guard_contract(reference, target, design), "reference_predictions": reference.tolist(),
        "input_sha256": {p.relative_to(ROOT).as_posix(): sha(p) for p in paths},
        "source_cells_verified": 770, "exact_J1_entries": 55, "new_kinetic_coordinates": False,
        "source_normalization_verified": False, "biological_promotion": False}
    out.mkdir(parents=True)
    write(out / "execution_design.json", frozen)
    write(out / "observations.json", observations)
    write(out / "source_seal.json", {p: sha(out/p) for p in ("execution_design.json", "observations.json")})
    return {"prepared": True, "training_times": times.tolist(), "pools": list(POOLS),
            "baseline_training_RMSE_mM": frozen["guards"]["reference_RMSE_mM"]}


def verify_inputs(out):
    for p, h in json.loads((out / "source_seal.json").read_text()).items():
        if sha(out/p) != h:
            raise ValueError("prepared observations/design changed")
    frozen = json.loads((out / "execution_design.json").read_text())
    for p, h in frozen["input_sha256"].items():
        if sha(ROOT/p) != h:
            raise ValueError(f"protected source input changed:{p}")
    return frozen


def fit_one(out_string, label, resume):
    out = Path(out_string)
    frozen = verify_inputs(out)
    d = frozen["design"]
    folder = out / "fits" / label
    if (folder / "files_seal.json").exists():
        if not resume:
            raise ValueError("completed fit exists; use resume or a new archive")
        check_seal(folder)
        return json.loads((folder / "result.json").read_text())
    if folder.exists() and not resume:
        raise ValueError("partial fit exists; explicit resume required")
    folder.mkdir(parents=True, exist_ok=True)
    times, target = training_data(json.loads((out / "observations.json").read_text()), d["training_end_day"])
    trace = []
    trace_path = folder / "trace.jsonl"
    if trace_path.exists():
        trace = [json.loads(line) for line in trace_path.read_text().splitlines()]
    cache = {tuple(r["log_factors"]): r for r in trace}
    bounds = np.log([frozen["parent_design"]["factor_bounds"][n] for n in COORDINATES])
    options = d["optimizer"]
    begin = perf_counter()
    integration_limit = options["primary_actual_integrations"]

    class BudgetExhausted(Exception):
        pass

    def get(x):
        key = tuple(float(v) for v in x)
        if key in cache:
            return cache[key]
        if len(trace) >= integration_limit:
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
            write(folder / "progress.json", {"calls": len(trace), "best_feasible_NLL": best["score"]["negative_log_likelihood"],
                "feasible_evaluations": sum(r["valid"] and r["guards"]["passed"] for r in trace),
                "best_feasible_log_factors": best["log_factors"], "elapsed_this_attempt_seconds": perf_counter()-begin})
            print(f"{label}: calls={len(trace)} feasibleNLL={best['score']['negative_log_likelihood']:.6g}", flush=True)
        return row

    def values(x):
        r = get(x)
        if not r["valid"]:
            return 1e12, np.full(len(POOLS), -1e6)
        return r["score"]["negative_log_likelihood"], np.array(r["guards"]["margins"])

    jac_cache = {}
    def derivatives(x):
        key = tuple(float(v) for v in x)
        if key in jac_cache:
            return jac_cache[key]
        f, c = values(x)
        gradient, jacobian = np.zeros(6), np.zeros((len(POOLS),6))
        for j in range(6):
            h = options["log_factor_difference_step"]
            step = h if x[j]+h <= bounds[j,1] else -h
            other = x.copy()
            other[j] = min(bounds[j,1], max(bounds[j,0], x[j]+step))
            fy, cy = values(other)
            gradient[j] = (fy-f)/(other[j]-x[j])
            jacobian[:,j] = (cy-c)/(other[j]-x[j])
        jac_cache[key] = gradient, jacobian
        return gradient, jacobian

    # The same admissible control is always available, even from infeasible starts.
    control = get(np.zeros(6))
    if not control["valid"] or not control["guards"]["passed"]:
        raise ValueError("control not feasible within reserved numerical margin; fail closed")
    terminal = np.array(best_feasible(trace)["log_factors"] if resume and len(trace)>1 else frozen["starts"][label])
    stages_path = folder / "optimizer_stages.json"
    stages = json.loads(stages_path.read_text()) if stages_path.exists() else []
    for old in stages:
        if old["state"] == "running":
            old.update({"state": "interrupted_without_convergence_claim", "actual_integrations": len(trace)-old["calls_before"]})
    success = False
    for limit in (options["primary_actual_integrations"], options["secondary_cumulative_actual_integrations"]):
        if len(trace) >= limit:
            continue
        integration_limit = limit
        before = len(trace)
        status = {"state": "running", "cumulative_actual_limit": limit, "resumed": bool(resume), "calls_before": before}
        stages.append(status)
        write(stages_path, stages)
        try:
            sol = minimize(lambda x: values(x)[0], terminal, method="SLSQP",
                jac=lambda x: derivatives(x)[0], bounds=bounds,
                constraints=[{"type": "ineq", "fun": lambda x: values(x)[1], "jac": lambda x: derivatives(x)[1]}],
                options={"maxiter": options["maxiter"], "ftol": options["ftol"]})
            terminal, success = sol.x, bool(sol.success)
            status.update({"state": "complete", "success": success, "message": str(sol.message),
                           "reported_nfev": int(sol.nfev), "reported_njev": int(sol.njev)})
        except BudgetExhausted:
            terminal = np.array(best_feasible(trace)["log_factors"])
            status.update({"state": "complete", "success": False, "message": "actual_integration_budget_exhausted"})
        status["actual_integrations"] = len(trace)-before
        write(stages_path, stages)
        if success:
            break
    best = best_feasible(trace)
    p, k, factors = unpack(best["log_factors"], frozen["parameters"], frozen["candidate"]["glucose_kinetics"],
                          frozen["resolved_capacities"], frozen["parent_design"]["factor_bounds"])
    pred, sol, rhs = predict_nine(np.array(frozen["initial"]), p, k, d["training_end_day"], times)
    agreement = assess(pred, target, frozen["guards"])
    if not agreement["passed"]:
        raise ValueError("selected fitting replay violates fixed fitting guards")
    np.savez_compressed(folder / "fit_replay.npz", sample_time=times, prediction=pred, observed=target,
                        accepted_time=sol.t, accepted_states=sol.y)
    result = {"label": label, "training_end_day": d["training_end_day"], "source_times": times.tolist(),
        "actual_objective_integrations": len(trace), "feasible_evaluations": sum(r["valid"] and r["guards"]["passed"] for r in trace),
        "optimizer_success": success, "optimizer_stages": stages, "terminal_log_factors": terminal.tolist(),
        "selected_log_factors": best["log_factors"], "factors": factors, "parameters": p, "glucose_kinetics": k,
        "training_score": score(pred, target), "training_guards": agreement,
        "selected_from": "lowest_training_NLL_among_guard_feasible_valid_evaluations_including_control",
        "is_control": best["log_factors"] == [0.]*6, "production_promoted": False}
    write(folder / "result.json", result)
    seal(folder)
    print(f"{label} done: converged={success} calls={len(trace)} feasibleNLL={result['training_score']['negative_log_likelihood']:.6g}", flush=True)
    return result


def audit(out, frozen, selected, end):
    folder = out / "audits" / (selected["label"]+f"_J{int(end)}")
    if (folder / "files_seal.json").exists():
        check_seal(folder)
        existing = json.loads((folder / "audit_summary.json").read_text())
        if existing["log_factors"] != selected["selected_log_factors"]:
            raise ValueError("completed audit belongs to another candidate")
        return existing
    if folder.exists():
        raise ValueError("partial full audit preserved; use a successor archive, do not overwrite")
    d = frozen["design"]
    original = ROOT / frozen["parent_design"]["source_archive"] / "execution_design.json"
    numerical = json.loads(original.read_text())["design"]
    design = {**numerical, "cases": ["glut_real_candidate"], "guard_pools": list(POOLS)}
    observed = json.loads((out / "observations.json").read_text())
    times = np.array(observed["time"])
    source = {p: np.array(v) for p,v in observed["values"].items()}
    candidate = {"glucose_kinetics": selected["glucose_kinetics"]}
    results, arrays, guards = [], [], []
    for profile in frozen["parent_design"]["numerical_profiles"]:
        r, a = replay(folder, "glut_real_candidate", profile, end, np.array(frozen["initial"]), selected["parameters"],
                      candidate, candidate["glucose_kinetics"], design, times, source)
        results.append(r)
        arrays.append(a)
        if end >= d["training_end_day"]:
            t, target = training_data(observed, d["training_end_day"])
            path = folder / f"J1_J{int(end)}" / f"glut_real_candidate_{profile}/replay.npz"
            with np.load(path) as archive:
                names = archive["pool_names"].tolist()
                prediction = archive["states"][[names.index(p) for p in POOLS]][:,np.searchsorted(archive["time"],t)]
            guards.append({"profile": profile, **assess(prediction, target, frozen["guards"], phase="audit")})
    comparisons = [close(arrays[0][i], arrays[1][i], numerical, "comparison") for i in range(3)]
    t, target = training_data(observed, min(end, d["training_end_day"]))
    fast_pred, fast_sol, rhs = predict_nine(np.array(frozen["initial"]), selected["parameters"], selected["glucose_kinetics"],
                                           end, t, profile=frozen["parent_design"]["numerical_profiles"]["ultrastrict"])
    with np.load(folder / f"J1_J{int(end)}/glut_real_candidate_ultrastrict/replay.npz") as archive:
        native = archive["states"][[rhs.names.index(p) for p in POOLS]][:,np.searchsorted(archive["time"],t)]
        fast_states = fast_sol.sol(archive["time"])
        parity = bool(np.allclose(fast_pred, native, rtol=1e-5, atol=1e-7)
                      and np.allclose(fast_states[:113], archive["states"][:113], rtol=.01, atol=1e-5))
        np.savez_compressed(folder / "fast_parity.npz", time=archive["time"], states=fast_states,
                            sample_time=t, prediction=fast_pred)
    report = {"label": selected["label"], "log_factors": selected["selected_log_factors"], "end_day": end,
        "numerical_pass": bool(all(r["numerical_pass"] for r in results) and all(c.all() for c in comparisons) and parity),
        "guard_pass": all(g["passed"] for g in guards), "training_guards": guards,
        "fast_full_parity": parity, "convergence_checks_passed": sum(int(c.sum()) for c in comparisons),
        "convergence_checks_total": sum(c.size for c in comparisons), "results": results}
    write(folder / "audit_summary.json", report)
    seal(folder)
    return report


def run(out, workers, resume):
    if (out / "manifest.json").exists():
        raise ValueError("campaign already completed; immutable archive")
    frozen = verify_inputs(out)
    fits = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        jobs = [pool.submit(fit_one, str(out), label, resume) for label in frozen["starts"]]
        for job in as_completed(jobs):
            fits.append(job.result())
            write(out / "progress.json", {"completed_fits": len(fits)})
    fits.sort(key=lambda r:r["label"])
    selected = min(fits, key=lambda r:r["training_score"]["negative_log_likelihood"])
    # A real control replay, not an assumed feasibility claim, is present in every trace.
    base_trace = [json.loads(line) for line in (out / "fits/control/trace.jsonl").read_text().splitlines()]
    control_row = next(r for r in base_trace if r["log_factors"] == [0.]*6)
    gain = control_row["score"]["negative_log_likelihood"]-selected["training_score"]["negative_log_likelihood"]
    p, k, factors = unpack(np.zeros(6), frozen["parameters"], frozen["candidate"]["glucose_kinetics"],
                          frozen["resolved_capacities"], frozen["parent_design"]["factor_bounds"])
    fallback = {"label": "control_fallback", "training_end_day": 10., "selected_log_factors": [0.]*6,
                "parameters": p, "glucose_kinetics": k, "factors": factors, "is_control": True,
                "training_score": control_row["score"]}
    if gain < frozen["design"]["minimum_training_NLL_gain"]:
        selected = fallback
    selection_attempts, audits = [], []
    for attempt in range(2):
        current = []
        for end in frozen["design"]["audit_end_days"]:
            r = audit(out, frozen, selected, end)
            current.append(r)
            if not r["numerical_pass"] or not r["guard_pass"]:
                break
        audits += current
        passed = all(r["numerical_pass"] and r["guard_pass"] for r in current) and current[-1]["end_day"] == 46
        selection_attempts.append({"label": selected["label"], "log_factors": selected["selected_log_factors"], "accepted": passed})
        if passed or selected["is_control"]:
            break
        selected = fallback
    summary = {"fits": fits, "selected": selected, "selection_attempts": selection_attempts, "audits": audits,
        "accepted_numeric_and_training_guards": selection_attempts[-1]["accepted"],
        "selected_is_control": selected["is_control"], "total_objective_integrations": sum(r["actual_objective_integrations"] for r in fits),
        "kinetic_box_expanded": False, "initial_states_changed": False, "source_values_changed": False,
        "late_observations_used_in_selection": False, "production_promoted": False,
        "all_observed_pools_hard_guarded": False, "guarded_pools": list(POOLS)}
    write(out / "summary.json", summary)
    verify_inputs(out)
    write(out / "manifest.json", {"output_sha256": {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob("*")) if p.is_file()}})
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
