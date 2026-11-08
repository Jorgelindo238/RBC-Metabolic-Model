"""User-authorized, reversible joint free-ODE kinetic calibration campaign."""

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
from fla_joint_calibration import COORDINATES, POOLS, joint_score, predict, resolve_capacities, unpack
from run_glut_only_free_replay import sha, write, replay, close

CONFIG = ROOT / "config/fla_joint_glucose_energy.json"


def prepare(out):
    from openpyxl import load_workbook
    from rbc_distinct_volume_transport import phase_matrix
    if out.exists():
        raise ValueError("fresh joint campaign directory required")
    d = json.loads(CONFIG.read_text())
    source = ROOT / d["source_archive"]
    previous = json.loads((source / "execution_design.json").read_text())
    observations = json.loads((source / "observations.json").read_text())
    workbook = load_workbook(ROOT / d["source_workbook"], read_only=True, data_only=False)
    try:
        rows = list(workbook[d["source_sheet"]].iter_rows(values_only=True))
        if list(rows[0][1:15]) != observations["time"]:
            raise ValueError("source sampling changed")
        actual = {r[0]: list(r[1:15]) for r in rows[1:] if isinstance(r[0], str) and isinstance(r[1], (int,float))}
        if actual != observations["values"] or len(actual) != 55:
            raise ValueError("original workbook versus sealed770-cell inventory mismatch")
    finally:
        workbook.close()
    context = ROOT / d["initial_context"]
    initial = np.load(context / "frozen_initial_state.npz")["states"]
    names = phase_matrix(d["hematocrit"])[0]
    if any(initial[names.index(p)] != v[0] for p,v in actual.items()):
        raise ValueError("exact55 measured J1 states must remain unchanged")
    params = json.loads((context / "frozen_parameters.json").read_text())
    candidate = json.loads((ROOT / d["candidate"]).read_text())
    seed = previous["seed_kinetics"]["conductance"] / candidate["glucose_kinetics"]["conductance"]
    if seed != d["start_factors"]["seed_GLUT"][0]:
        raise ValueError("declared seed conductance ratio mismatch")
    files = [CONFIG, Path(__file__), ROOT / "scripts/verify_joint_glucose_energy.py",
        ROOT / "src/fla_joint_calibration.py", ROOT / "src/fla_profiled_observation_noise.py",
        ROOT / "qa/test_joint_glucose_energy.py", ROOT / d["source_workbook"],
        source / "execution_design.json", source / "observations.json", source / "manifest.json",
        ROOT / "scripts/run_glut_only_free_replay.py"]
    files += [ROOT / p for p in previous["input_sha256"]]
    hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in files}
    out.mkdir(parents=True)
    write(out / "execution_design.json", {"design": d, "input_sha256": hashes,
        "initial": initial.tolist(), "parameters": params, "candidate": candidate,
        "resolved_capacities": resolve_capacities(params),
        "source_cells_reconstructed": 770, "source_initial_entries_preserved": 55,
        "source_scope": "nominal_source_coordinates_and_borrowed_geometry_not_verified_physiological_pools",
        "joint_biological_promotion_allowed": False})
    write(out / "observations.json", observations)
    write(out / "source_seal.json", {p: sha(out/p) for p in ("execution_design.json", "observations.json")})
    return {"prepared": True, "source_cells_verified": 770, "starts": len(d["start_factors"]), "coordinates": list(COORDINATES)}


def verify_inputs(out):
    frozen = json.loads((out / "execution_design.json").read_text())
    for p, digest in json.loads((out / "source_seal.json").read_text()).items():
        if sha(out / p) != digest:
            raise ValueError("prepared campaign source changed")
    for p, digest in frozen["input_sha256"].items():
        if sha(ROOT / p) != digest:
            raise ValueError(f"protected campaign input changed: {p}")
    return frozen


def fit_one(out_string, end, label, start):
    out = Path(out_string)
    frozen = verify_inputs(out)
    d = frozen["design"]
    observed = json.loads((out / "observations.json").read_text())
    time = np.asarray(observed["time"])
    mask = (time > 1) & (time <= end)
    sample_time = time[mask]
    target = np.array([observed["values"][p] for p in POOLS])[:,mask]
    initial = np.array(frozen["initial"])
    params, kinetics = frozen["parameters"], frozen["candidate"]["glucose_kinetics"]
    capacities = frozen["resolved_capacities"]
    bounds = np.log([d["factor_bounds"][n] for n in COORDINATES])
    folder = out / f"fit_J{int(end)}" / label
    folder.mkdir(parents=True, exist_ok=False)
    trace, cache = [], {}
    begin = perf_counter()
    integration_limit = d["optimizer"]["maxfun"]

    class BudgetExhausted(Exception):
        pass

    def cost(x):
        key = tuple(float(v) for v in x)
        if key in cache:
            return cache[key]
        if len(trace) >= integration_limit:
            raise BudgetExhausted
        p, k, factors = unpack(x, params, kinetics, capacities, d["factor_bounds"])
        try:
            predicted, _, _ = predict(initial, p, k, end, sample_time)
            score = joint_score(predicted, target)
            value = score["negative_log_likelihood"]
            row = {"call": len(trace)+1, "log_factors": list(key), "factors": factors, "valid": True,
                   "score": score, "predictions": predicted.tolist()}
        except (ValueError, FloatingPointError, RuntimeError) as error:
            value = 1e12
            row = {"call": len(trace)+1, "log_factors": list(key), "factors": factors, "valid": False,
                   "error": str(error), "objective_penalty": value}
        trace.append(row)
        cache[key] = value
        if len(trace) % 10 == 0:
            write(folder / "progress.json", {"calls": len(trace), "best_nll": min(cache.values()),
                "elapsed_seconds": perf_counter()-begin, "last": row})
            print(f"J{int(end)} {label}: calls={len(trace)} bestNLL={min(cache.values()):.5g}", flush=True)
        return value

    def gradient(x):
        result = np.zeros(len(x))
        h = d["optimizer"]["finite_difference_relative_step"]
        for j in range(len(x)):
            step = h if x[j]+h <= bounds[j,1] else -h
            other = x.copy()
            other[j] = min(bounds[j,1],max(bounds[j,0],x[j]+step))
            result[j] = (cost(other)-cost(x))/(other[j]-x[j])
        return result

    options = {k:d["optimizer"][k] for k in ("maxfun", "maxiter", "ftol", "gtol")}
    solutions, terminal, optimizer_success = [], np.array(start), False
    # Both caps count actual integrations including finite-difference perturbations.
    for limit in (d["optimizer"]["maxfun"], d["optimizer"]["secondary_maxfun"]):
        integration_limit = limit
        calls_before = len(trace)
        try:
            solution = minimize(cost, terminal, method="L-BFGS-B", jac=gradient, bounds=bounds, options=options)
            terminal, optimizer_success = solution.x, bool(solution.success)
            status = {"success": optimizer_success, "message": str(solution.message),
                "reported_nfev": int(solution.nfev), "reported_njev": int(solution.njev), "nll": float(solution.fun)}
        except BudgetExhausted:
            best_valid = min((r for r in trace if r["valid"]), key=lambda r:r["score"]["negative_log_likelihood"])
            terminal = np.array(best_valid["log_factors"])
            status = {"success": False, "message": "actual_integration_budget_exhausted_including_jacobian_calls"}
        status.update({"actual_integration_cap_cumulative": limit, "actual_integrations": len(trace)-calls_before})
        solutions.append(status)
        if optimizer_success:
            break
    valid = [r for r in trace if r["valid"]]
    if not valid:
        raise ValueError("no valid full-network likelihood evaluation")
    # Preserve terminal solution separately: line-search failures cannot promote a last iterate.
    best = min(valid, key=lambda r:r["score"]["negative_log_likelihood"])
    p, k, factors = unpack(best["log_factors"], params, kinetics, capacities, d["factor_bounds"])
    prediction, sol, rhs = predict(initial, p, k, end, sample_time)
    np.savez_compressed(folder / "fit_replay.npz", sample_time=sample_time, prediction=prediction, observed=target,
                        accepted_time=sol.t, accepted_states=sol.y, jacobian_sparsity=rhs.jacobian_sparsity)
    result = {"label": label, "training_end_day": end, "source_times": sample_time.tolist(),
        "actual_objective_integrations": len(trace), "elapsed_seconds": perf_counter()-begin,
        "optimizer_stages": solutions, "optimizer_success": optimizer_success,
        "terminal_log_factors": terminal.tolist(), "selected_log_factors": best["log_factors"],
        "selected_from": "lowest_valid_training_nll_among_all_evaluations_including_finite_difference_probes",
        "factors": factors, "parameters": p, "glucose_kinetics": k, "training_score": joint_score(prediction,target),
        "bound_hits": [n for i,n in enumerate(COORDINATES) if min(abs(best["log_factors"][i]-bounds[i])) < .002],
        "independent_constants_identified": False, "biological_promotion": False}
    write(folder / "trace.json", trace)
    write(folder / "result.json", result)
    print(f"J{int(end)} {label} finished: NLL={result['training_score']['negative_log_likelihood']:.5g} calls={len(trace)}", flush=True)
    return result


def audit_case(out, frozen, result, end):
    d = frozen["design"]
    base = json.loads((ROOT / d["source_archive"] / "execution_design.json").read_text())["design"]
    design = {**base, "cases": ["glut_real_candidate"], "horizons_end_day": [end]}
    observed = json.loads((out / "observations.json").read_text())
    time = np.asarray(observed["time"])
    data = {p:np.asarray(v) for p,v in observed["values"].items()}
    candidate = {"glucose_kinetics": result["glucose_kinetics"]}
    case_out = out / "audits" / f"selected_training_J{int(result['training_end_day'])}_replay_J{int(end)}"
    arrays, results = [], []
    for profile in d["numerical_profiles"]:
        r, a = replay(case_out, "glut_real_candidate", profile, end, np.array(frozen["initial"]), result["parameters"],
                      candidate, candidate["glucose_kinetics"], design, time, data)
        results.append(r)
        arrays.append(a)
    comparisons = [close(arrays[0][i], arrays[1][i], design, "comparison") for i in range(3)]
    passed = all(r["numerical_pass"] for r in results) and all(a.all() for a in comparisons)
    mask = (time > 1) & (time <= result["training_end_day"])
    pred, sol, rhs = predict(np.array(frozen["initial"]), result["parameters"], result["glucose_kinetics"], end, time[mask],
                             profile=d["numerical_profiles"]["ultrastrict"])
    full = case_out / f"J1_J{int(end)}" / "glut_real_candidate_ultrastrict/replay.npz"
    with np.load(full) as a:
        idx = np.searchsorted(a["time"], time[mask])
        expected = a["states"][[rhs.names.index(p) for p in POOLS]][:,idx]
        equivalence = bool(np.allclose(pred, expected, rtol=1e-5, atol=1e-7))
        states_equal = bool(np.allclose(sol.sol(a["time"])[:113], a["states"][:113], rtol=.01, atol=1e-5))
    report = {"training_end_day": result["training_end_day"], "replay_end_day": end,
        "numerical_pass": bool(passed and equivalence and states_equal),
        "strict_ultrastrict_checks_passed": sum(int(a.sum()) for a in comparisons),
        "strict_ultrastrict_checks_total": sum(a.size for a in comparisons),
        "fast_full_source_predictions_agree": equivalence, "fast_full_all_pool_samples_agree": states_equal,
        "results": results, "GLC_free": True, "initial_state_changed": False}
    write(case_out / "audit_summary.json", report)
    return report


def run(out, workers):
    if (out / "manifest.json").exists():
        raise ValueError("joint campaign already sealed")
    frozen = verify_inputs(out)
    d = frozen["design"]
    results, audits = [], []
    starts = {k:np.log(v).tolist() for k,v in d["start_factors"].items()}
    for end in d["fit_end_days"]:
        stage = []
        with ProcessPoolExecutor(max_workers=workers) as pool:
            jobs = [pool.submit(fit_one, str(out), end, label, start) for label,start in starts.items()]
            for job in as_completed(jobs):
                stage.append(job.result())
                write(out / "progress.json", {"completed_fits": len(results)+len(stage), "stage": end})
        stage.sort(key=lambda r:r["label"])
        results += stage
        selected = min(stage, key=lambda r:r["training_score"]["negative_log_likelihood"])
        audit = audit_case(out, frozen, selected, end)
        audits.append(audit)
        write(out / "checkpoint.json", {"fits": results, "audits": audits, "latest_selected": selected})
        if not audit["numerical_pass"]:
            break
        starts = {r["label"]:r["selected_log_factors"] for r in stage}
    if audits[-1]["numerical_pass"] and selected["training_end_day"] == d["fit_end_days"][-1]:
        audits.append(audit_case(out, frozen, selected, d["prediction_end_day"]))
    summary = {"fits": results, "audits": audits, "selected": selected,
        "all_numerical_pass": all(a["numerical_pass"] for a in audits),
        "total_objective_integrations": sum(r["actual_objective_integrations"] for r in results),
        "source_values_changed": False, "initial_state_changed": False, "production_promoted": False,
        "assay_precision_identified": False, "full_physiological_validation": False,
        "temporal_evaluation": "exposed_internal_J11_J46_not_independent_external_validation"}
    write(out / "summary.json", summary)
    verify_inputs(out)
    write(out / "manifest.json", {"output_sha256": {p.relative_to(out).as_posix():sha(p) for p in sorted(out.rglob('*')) if p.is_file()}})
    return {k:summary[k] for k in ("all_numerical_pass", "total_objective_integrations", "production_promoted")}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prepare", type=Path)
    p.add_argument("--run", type=Path)
    p.add_argument("--workers", type=int, default=3)
    args = p.parse_args()
    if bool(args.prepare) == bool(args.run) or not 1 <= args.workers <= 3:
        p.error("choose prepare/run and1-3 numerical workers")
    print(json.dumps(prepare(args.prepare.resolve()) if args.prepare else run(args.run.resolve(),args.workers),indent=2))
