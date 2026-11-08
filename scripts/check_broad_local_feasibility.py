"""Three predeclared local linearized directions, checked by actual ODE solves.

This is separate from the sealed SLSQP campaign. It neither relaxes a guard nor
establishes a globally calibrated parameter vector.
"""

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from scipy.optimize import linprog

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from fla_broad_protected_calibration import training_data, evaluate
from fla_joint_calibration import COORDINATES
from run_protected_joint import verify_inputs
from run_glut_only_free_replay import sha, write


def check(parent, out):
    if out.exists(): raise ValueError("fresh local-check directory required")
    frozen = verify_inputs(parent)
    trace = [json.loads(line) for line in (parent/"fits/control/trace.jsonl").read_text().splitlines()]
    base = trace[0]
    if base["log_factors"] != [0.]*6 or not base["guards"]["passed"]:
        raise ValueError("real feasible control required")
    gradient, jacobian = np.zeros(6), np.zeros((13, 6))
    stencil = [base]
    for j in range(6):
        row = next(r for r in trace[1:] if r["valid"] and np.count_nonzero(r["log_factors"]) == 1 and r["log_factors"][j] != 0)
        step = row["log_factors"][j]
        gradient[j] = (row["score"]["negative_log_likelihood"]-base["score"]["negative_log_likelihood"])/step
        jacobian[:, j] = (np.array(row["guards"]["margins"])-base["guards"]["margins"])/step
        stencil.append(row)
    out.mkdir(parents=True)
    write(out/"stencil.json", stencil)
    protocol = {"parent": parent.relative_to(ROOT).as_posix(), "radii": [.01, .002, .0005],
        "maximum_new_objective_ODE_calls": 3, "same_six_coordinates": True, "guard_limits_changed": False,
        "late_data_used": False, "production_promoted": False,
        "interpretation": "local_linearized_descent_is_not_global_feasibility_or_identifiability"}
    write(out/"protocol.json", protocol)
    times, target = training_data(json.loads((parent/"observations.json").read_text()), frozen["design"]["training_end_day"])
    box = np.log([frozen["parent_design"]["factor_bounds"][name] for name in COORDINATES])
    rows = []
    for radius in protocol["radii"]:
        bounds = [(max(-radius, lo), min(radius, hi)) for lo, hi in box]
        lp = linprog(gradient, A_ub=-jacobian, b_ub=base["guards"]["margins"], bounds=bounds, method="highs")
        result = {"radius": radius, "linear_program_success": bool(lp.success)}
        if lp.success:
            result.update(predicted_NLL_change=float(lp.fun), direction=lp.x.tolist())
            try:
                result["actual_evaluation"] = evaluate(lp.x, frozen, times, target)
            except (ValueError, RuntimeError, FloatingPointError) as error:
                result["actual_evaluation"] = {"valid": False, "error": str(error)}
        rows.append(result)
        write(out/"results.json", rows)
    valid = [r["actual_evaluation"] for r in rows if r.get("actual_evaluation", {}).get("valid")]
    feasible = [r for r in valid if r["guards"]["passed"]]
    result = {"actual_new_objective_ODE_calls": sum(r["linear_program_success"] for r in rows),
        "feasible_points": len(feasible), "control_NLL": base["score"]["negative_log_likelihood"],
        "best_feasible_NLL": min((r["score"]["negative_log_likelihood"] for r in feasible), default=None),
        "best_feasible_point": min(feasible, key=lambda r:r["score"]["negative_log_likelihood"]) if feasible else None,
        "physiological_validation": False, "selected_into_parent_campaign": False}
    write(out/"summary.json", result)
    sources = [Path(__file__), parent/"execution_design.json", parent/"observations.json"]
    hashes = {**frozen["input_sha256"], **{p.relative_to(ROOT).as_posix(): sha(p) for p in sources}}
    write(out/"manifest.json", {"input_sha256": hashes,
        "output_sha256": {p.name: sha(p) for p in out.iterdir() if p.is_file()}})
    return {k:v for k,v in result.items() if k != "best_feasible_point"}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--parent", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(check(args.parent.resolve(), args.out.resolve()), indent=2))
