"""Execute predeclared J1-J4 structural cases, with explicit executed-flux budgets."""

import csv
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

import numpy as np
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fla_balance_audit import accepted_step_quadrature, integrate_intervals
from fla_working_reference import load_working_reference, reference_options
from rbc_gem_network import diagnostic_matrix, equadiff_rbc_gem
from reaction_positivity import rbc_reaction_matrix

OUT = ROOT / "output/rbc_gem_network_audit_2026_10_06/fixed_parameter_diagnostic"
CONFIG = ROOT / "config/fla_rbc_gem_structural_diagnostic.json"


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + "\n")


def main():
    design = json.loads(CONFIG.read_text())
    if any(design[key] is not False for key in ("initial_conditions_changed", "biological_optimization_allowed",
                                                "global_promotion_allowed", "forcing_allowed")):
        raise ValueError("fixed-context diagnostic cannot enable fitting or promotion")
    OUT.mkdir(exist_ok=False)
    parent = ROOT / design["initial_state_archive"]
    reference = load_working_reference(ROOT / design["working_reference"])
    initial = np.load(parent / "frozen_initial_state.npz")["states"]
    parameters = json.loads((parent / "frozen_parameters.json").read_text())
    boundaries = np.asarray(design["audit_boundaries_day"])
    inputs = [CONFIG, parent / "frozen_initial_state.npz", parent / "frozen_parameters.json",
              ROOT / "src/equadiff_brodbar.py", ROOT / "src/rbc_stoichiometry.py",
              ROOT / "src/reaction_positivity.py", ROOT / "src/rbc_gem_network.py",
              ROOT / design["working_reference"], ROOT / "src/Data_Bordbar_et_al_exp.xlsx",
              Path(__file__).resolve()]
    input_hashes = {str(path): file_hash(path) for path in inputs}
    save("preregistered_contract.json", {"design": design, "input_sha256": input_hashes})
    records, comparisons, results = [], [], {}
    started = perf_counter()
    for case in design["cases"]:
        for tolerance in design["tolerances"]:
            name = case["name"] + "_" + tolerance
            params = dict(parameters)
            if case["disable_oplah"]:
                params["vmax_VOPLAH"] = 0.0
            options, solver = reference_options(reference, ultrastrict=tolerance == "ultrastrict")
            mode = case["network_mode"]
            names, reactions, matrix = (rbc_reaction_matrix(params.get("sam_adenylate_stoichiometry", "biochemical_transfer"))
                                       if mode == "historical" else diagnostic_matrix(mode))
            def evaluate(time, states, audit=None):
                return equadiff_rbc_gem(time, states, network_mode=mode, custom_params=params,
                                       numerical_audit=audit, **options)
            solution = solve_ivp(evaluate, tuple(design["horizon_day"]), initial.copy(),
                                 dense_output=True, **solver)
            if not solution.success or solution.t[-1] != design["horizon_day"][-1]:
                raise RuntimeError(f"incomplete integration: {name}: {solution.message}")
            assert np.array_equal(solution.y[:, 0], initial)
            if case["name"] == "historical":
                old = np.load(parent / ("baseline_" + tolerance) / "accepted_solver_states.npz")
                assert np.array_equal(solution.t, old["time"]), "historical accepted times changed"
                assert np.array_equal(solution.y, old["states"]), "historical accepted states changed"
            folder = OUT / name
            folder.mkdir()
            np.savez_compressed(folder / "accepted_states.npz", time=solution.t, states=solution.y)
            sample_times = np.unique(np.r_[np.linspace(*design["horizon_day"], 601), solution.t])
            sample_states = solution.sol(sample_times)
            minimum = min(float(solution.y[:113].min()), float(sample_states[:113].min()))
            closure = 0.0
            quad = {}
            quad_minimum = minimum
            for order in (4, 8):
                grid = accepted_step_quadrature(solution.t, boundaries, order=order)
                states = solution.sol(grid.nodes)
                quad_minimum = min(quad_minimum, float(states[:113].min()))
                raw, effective = [], []
                for time, point in zip(grid.nodes, states.T):
                    audit = {}
                    derivative = evaluate(time, point, audit)
                    vr = [audit["raw_fluxes"][reaction] for reaction in reactions]
                    ve = [audit["effective_fluxes"][reaction] for reaction in reactions]
                    closure = max(closure, float(np.max(np.abs(matrix @ ve - derivative[:113]))))
                    raw.append(vr)
                    effective.append(ve)
                quad[order] = {"raw": integrate_intervals(np.asarray(raw).T, grid),
                               "effective": integrate_intervals(np.asarray(effective).T, grid)}
            controls = reference["validation_before_calibration"]
            def close(a, b):
                return np.abs(a-b) <= controls["quadrature_atol_mM"] + controls["quadrature_rtol"]*np.maximum(abs(a), abs(b))
            increments = np.diff(solution.sol(boundaries)[:113], axis=1)
            predicted = matrix @ quad[8]["effective"]
            checks = close(predicted, increments)
            checks_raw = close(quad[4]["raw"], quad[8]["raw"])
            checks_executed = close(quad[4]["effective"], quad[8]["effective"])
            valid = (quad_minimum >= controls["negative_state_tolerance_mM"]
                     and closure <= controls["closure_tolerance_mM_per_day"]
                     and bool(checks.all()) and bool(checks_raw.all()) and bool(checks_executed.all()))
            np.savez_compressed(folder / "dense_and_integrals.npz", time=sample_times, states=sample_states,
                                reactions=np.asarray(reactions), matrix=matrix, boundaries=boundaries,
                                raw_4=quad[4]["raw"], raw_8=quad[8]["raw"],
                                effective_4=quad[4]["effective"], effective_8=quad[8]["effective"])
            for index, pool in enumerate(names):
                records.append({"case": name, "pool": pool, "initial": initial[index],
                                "endpoint": solution.y[index, -1],
                                "integrated_balance": float(predicted[index].sum())})
            result = {"case": name, "network_mode": mode, "new_branches_enabled": [],
                      "minimum_checked_mM": quad_minimum, "closure_max_mM_per_day": closure,
                      "pool_interval_checks": int(checks.sum()), "pool_interval_checks_total": checks.size,
                      "raw_quadrature_checks": int(checks_raw.sum()),
                      "effective_quadrature_checks": int(checks_executed.sum()),
                      "rate_quadrature_checks_total_each": checks_raw.size,
                      "ATP_J4": float(solution.y[35, -1]), "ADP_J4": float(solution.y[36, -1]),
                      "AMP_J4": float(solution.y[37, -1]), "numerical_pass": valid,
                      "historical_bit_identical": case["name"] == "historical"}
            (folder / "result.json").write_text(json.dumps(result, indent=2) + "\n")
            results[name] = {"result": result, "solution": solution, "integrals": quad[8], "reactions": reactions}
            save("execution_progress.json", {"completed": [item["result"] for item in results.values()],
                                             "elapsed_seconds": perf_counter()-started})
            print(json.dumps(result), flush=True)
        a, b = (results[case["name"] + "_" + tolerance] for tolerance in design["tolerances"])
        times = np.unique(np.r_[a["solution"].t, b["solution"].t, np.linspace(1, 4, 601)])
        for quantity, left, right in (
            ("states", a["solution"].sol(times)[:113], b["solution"].sol(times)[:113]),
            ("raw_integrals", a["integrals"]["raw"], b["integrals"]["raw"]),
            ("effective_integrals", a["integrals"]["effective"], b["integrals"]["effective"]),
        ):
            acceptable = np.abs(left-right) <= controls["comparison_atol_mM"] + controls["comparison_rtol"]*np.maximum(abs(left), abs(right))
            comparisons.append({"case": case["name"], "quantity": quantity,
                                "passed": int(acceptable.sum()), "total": acceptable.size,
                                "all_pass": bool(acceptable.all()), "max_difference": float(abs(left-right).max())})
    with (OUT / "pool_endpoints.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)
    summary = {"cases": [item["result"] for item in results.values()], "convergence": comparisons,
               "all_numerical_gates_pass": all(item["result"]["numerical_pass"] for item in results.values())
                 and all(item["all_pass"] for item in comparisons),
               "biological_promotion": False, "calibration_executed": False,
               "elapsed_seconds": perf_counter()-started}
    save("summary.json", summary)
    for path, expected in input_hashes.items():
        assert file_hash(Path(path)) == expected, path
    save("manifest.json", {"input_sha256": input_hashes,
                           "output_sha256": {str(path.relative_to(OUT)): file_hash(path)
                                             for path in sorted(OUT.rglob("*")) if path.is_file()
                                             and path.name != "manifest.json"}})
    print(json.dumps({"completed": len(results), "all_numerical_gates_pass": summary["all_numerical_gates_pass"]}))


if __name__ == "__main__":
    main()
