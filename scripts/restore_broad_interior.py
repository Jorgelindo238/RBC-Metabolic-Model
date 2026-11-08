"""Bounded numerical feasibility restoration, never relaxed scientific caps."""

import argparse
import copy
import json
from pathlib import Path
import sys

import numpy as np
from scipy.optimize import linprog

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from fla_broad_protected_calibration import training_data, evaluate, best_feasible
from fla_joint_calibration import COORDINATES, unpack
from run_protected_joint import verify_inputs, seal
from run_glut_only_free_replay import sha, write
from run_broad_protected_joint import run


def interior_step(margins, jacobian, target, x, bounds, radius):
    """Minimum L1 correction toward an inner target in the same six coordinates."""
    n = len(x)
    lower = np.maximum(-radius, bounds[:, 0]-x)
    upper = np.minimum(radius, bounds[:, 1]-x)
    matrix = np.vstack([np.c_[-jacobian, np.zeros_like(jacobian)],
                        np.c_[np.eye(n), -np.eye(n)], np.c_[-np.eye(n), -np.eye(n)]])
    rhs = np.r_[margins-target, np.zeros(2*n)]
    result = linprog(np.r_[np.zeros(n), np.ones(n)], A_ub=matrix, b_ub=rhs,
                     bounds=[*zip(lower, upper), *[(0., radius)]*n], method="highs")
    return result


def restore(parent, out):
    if out.exists(): raise ValueError("fresh restoration archive required")
    source = verify_inputs(parent)
    trace = [json.loads(line) for line in (parent/"fits/control/trace.jsonl").read_text().splitlines()]
    control_nll = trace[0]["score"]["negative_log_likelihood"]
    eligible = [r for r in trace if r["valid"] and max(0., -min(r["guards"]["margins"])) <= 1e-5
                and r["score"]["negative_log_likelihood"] < control_nll-1e-4]
    if not eligible: raise ValueError("no near-boundary starting point; no change to feasibility rule")
    seed = min(eligible, key=lambda r:r["score"]["negative_log_likelihood"])
    protocol = {"purpose": "numerical_restoration_not_a_new_biological_lever",
        "maximum_actual_objective_integrations": 17, "maximum_linearizations": 2,
        "difference_step": 1e-4, "trust_radius": .005, "inner_reserve_fraction_of_allowance": .05,
        "seed_screen_max_normalized_violation": 1e-5, "seed_screen_is_acceptance_rule": False,
        "same_six_coordinates": True, "guard_limits_relaxed": False, "late_data_used": False,
        "optimizer_parent_archive": parent.relative_to(ROOT).as_posix()}
    f = copy.deepcopy(source)
    f["restoration_protocol"] = protocol
    f["starts"] = {"restoration": seed["log_factors"]}
    f["design"]["optimizer"] = {**f["design"]["optimizer"], "method": "minimum_L1_inner_feasibility_restoration",
        "primary_actual_integrations": 17, "secondary_cumulative_actual_integrations": 17}
    f["input_sha256"].update({p.relative_to(ROOT).as_posix(): sha(p) for p in
        (Path(__file__), ROOT/"qa/test_broad_interior_restoration.py", parent/"execution_design.json", parent/"observations.json")})
    out.mkdir(parents=True)
    write(out/"seed_snapshot.json", {"parent_row": seed, "parent_trace_file": "fits/control/trace.jsonl"})
    write(out/"restoration_protocol.json", protocol)
    write(out/"execution_design.json", f)
    write(out/"observations.json", json.loads((parent/"observations.json").read_text()))
    write(out/"source_seal.json", {p: sha(out/p) for p in ("execution_design.json", "observations.json", "seed_snapshot.json", "restoration_protocol.json")})
    times, target = training_data(json.loads((out/"observations.json").read_text()), f["design"]["training_end_day"])
    folder = out/"fits/restoration"
    folder.mkdir(parents=True)
    rows, cache, iterations = [], {}, []
    def get(x):
        key = tuple(float(v) for v in x)
        if key not in cache:
            if len(rows) >= protocol["maximum_actual_objective_integrations"]:
                raise ValueError("restoration integration cap reached")
            row = evaluate(np.array(x), f, times, target)
            row["call"] = len(rows)+1
            rows.append(row)
            cache[key] = row
            with (folder/"trace.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, allow_nan=False)+"\n")
                stream.flush()
        return cache[key]
    get(np.zeros(6))
    x = np.array(seed["log_factors"])
    bounds = np.log([f["parent_design"]["factor_bounds"][name] for name in COORDINATES])
    reserve = (protocol["inner_reserve_fraction_of_allowance"]*np.array(f["guards"]["numerical_allowance_mM"])
               /f["guards"]["normalization_mM"])
    for iteration in range(protocol["maximum_linearizations"]):
        base = get(x)
        margins = np.array(base["guards"]["margins"])
        jacobian = np.zeros((len(margins), 6))
        for j in range(6):
            h = protocol["difference_step"]
            h = h if x[j]+h <= bounds[j, 1] else -h
            other = x.copy()
            other[j] += h
            jacobian[:, j] = (np.array(get(other)["guards"]["margins"])-margins)/h
        lp = interior_step(margins, jacobian, reserve, x, bounds, protocol["trust_radius"])
        row = {"iteration": iteration, "linear_program_success": bool(lp.success), "message": lp.message}
        if lp.success:
            x = x+lp.x[:6]
            actual = get(x)
            row.update(actual_NLL=actual["score"]["negative_log_likelihood"],
                actual_guard_pass=actual["guards"]["passed"], actual_failed=actual["guards"]["failed_constraints"], step=lp.x[:6].tolist())
        iterations.append(row)
        write(out/"restoration_iterations.json", iterations)
        if not lp.success or row["actual_guard_pass"]:
            break
    best = best_feasible(rows)
    parameters, kinetics, factors = unpack(best["log_factors"], f["parameters"], f["candidate"]["glucose_kinetics"],
        f["resolved_capacities"], f["parent_design"]["factor_bounds"])
    # A final fit replay is evidence, not an objective evaluation in the call cap.
    from fla_broad_protected_calibration import predict_broad, assess, score
    prediction, sol, _ = predict_broad(np.array(f["initial"]), parameters, kinetics, f["design"]["training_end_day"], times)
    guards = assess(prediction, target, f["guards"])
    if not guards["passed"]: raise ValueError("restoration replay violates unchanged guards")
    np.savez_compressed(folder/"fit_replay.npz", sample_time=times, prediction=prediction, observed=target,
                        accepted_time=sol.t, accepted_states=sol.y)
    result = {"label": "restoration", "training_end_day": f["design"]["training_end_day"], "source_times": times.tolist(),
        "actual_objective_integrations": len(rows), "feasible_evaluations": sum(r["guards"]["passed"] for r in rows),
        "optimizer_success": False, "optimizer_status_meaning": "feasibility_restoration_not_NLL_optimum_convergence",
        "optimizer_stages": iterations, "terminal_log_factors": x.tolist(), "selected_log_factors": best["log_factors"],
        "parameters": parameters, "glucose_kinetics": kinetics, "factors": factors,
        "training_score": score(prediction, target), "training_guards": guards,
        "is_control": best["log_factors"] == [0.]*6, "production_promoted": False}
    write(folder/"result.json", result)
    seal(folder)
    return run(out, 1, True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--parent", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(restore(args.parent.resolve(), args.out.resolve()), indent=2))
