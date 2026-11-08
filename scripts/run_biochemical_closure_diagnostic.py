"""Fixed-context structural replays plus separately labeled synthetic redox tests."""

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
from rbc_biochemical_extensions import (BRANCHES, NEW_POOLS, REDOX_GROUPS, biochemical_matrix,
                                       build_initial_state, equadiff_biochemical, extension_rates)
from reaction_positivity import limit_signed_fluxes

OUT = ROOT / "output/biochemical_closure_2026_10_06/fixed_context"
CONFIG = ROOT / "config/fla_biochemical_closure_diagnostic.json"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(folder, name, value):
    (folder / name).write_text(json.dumps(value, indent=2) + "\n")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    design = json.loads(CONFIG.read_text())
    for key in ("biological_calibration_allowed", "global_promotion_allowed", "forcing_allowed",
                "redox_kinetics_enabled_in_Bordbar_replays", "MTHFR_enabled_in_Bordbar_replays", "abc_exports"):
        require(design[key] is False, f"Forbidden change: {key}")
    parent = ROOT / design["initial_state_archive"]
    old_initial = np.load(parent / "frozen_initial_state.npz")["states"]
    parameters = json.loads((parent / "frozen_parameters.json").read_text())
    with (parent / "initialization_inventory.csv").open(newline="") as stream:
        inventory = list(csv.DictReader(stream))
    ref = load_working_reference(ROOT / design["working_reference"])
    controls = ref["validation_before_calibration"]
    inputs = [CONFIG, Path(__file__).resolve(), ROOT / "src/rbc_biochemical_extensions.py",
              ROOT / "src/rbc_gem_network.py", ROOT / "src/equadiff_brodbar.py",
              ROOT / "src/rbc_stoichiometry.py", ROOT / "src/reaction_positivity.py",
              ROOT / "src/fla_balance_audit.py", ROOT / "src/fla_working_reference.py",
              ROOT / design["working_reference"], ROOT / "src/Data_Bordbar_et_al_exp.xlsx",
              parent / "frozen_initial_state.npz", parent / "frozen_parameters.json",
              parent / "initialization_inventory.csv", OUT.parent / "source_audit.json"]
    hashes = {str(path): sha(path) for path in inputs}
    names, reactions, matrix = biochemical_matrix("vcse_folate")
    # Inventory classifications are explicit; do not infer measured pools from nonzero states.
    measured = [row["pool"] for row in inventory if row["source"] == "Sheet1_J1_exact"]
    require(len(measured) == 55, f"Expected 55 source-measured pools, found {len(measured)}")
    require("METTHF" not in measured, "Cannot split an observed pool without its observation operator")
    synthetic = []
    for index, group in enumerate(REDOX_GROUPS):
        kin = {r: {"vmax": 0.2, **{"km_" + s: 0.1 for s in BRANCHES[r]["substrates"]}} for r in group}
        states = np.zeros(len(names))
        for name in ("NADH", "NADPH", "CYB5OX", "HBFE3", "TXNOX", "PRDXOX", "H2O2"):
            states[names.index(name)] = 0.1
        synthetic.append({"name": "synthetic_" + ("metHb" if index == 0 else "PRDX_TXN"),
                          "purpose": "synthetic_software_budget_test_not_biological_prior",
                          "kinetics": kin, "initial": states.tolist(), "reactions": list(group)})
    OUT.mkdir(exist_ok=False)
    save(OUT, "preregistered_contract.json", {"design": design, "synthetic_cases": synthetic,
                                            "input_sha256": hashes, "measured_pools": measured})
    started = perf_counter()
    results, comparisons, endpoints = {}, [], []
    def close(left, right, kind="quadrature"):
        return np.abs(left-right) <= controls[kind + "_atol_mM"] + controls[kind + "_rtol"] * np.maximum(abs(left), abs(right))

    def execute(name, initial, pool_names, reaction_names, s, evaluate, horizon, boundaries, solver, tolerance, purpose):
        solution = solve_ivp(evaluate, tuple(horizon), initial.copy(), dense_output=True, **solver)
        require(solution.success and solution.t[-1] == horizon[-1], f"Integration failed: {name}")
        require(np.array_equal(solution.y[:, 0], initial), "Initial values modified")
        folder = OUT / name
        folder.mkdir()
        np.savez_compressed(folder / "accepted_states.npz", time=solution.t, states=solution.y)
        times = np.unique(np.r_[solution.t, np.linspace(*horizon, 601)])
        dense = solution.sol(times)
        minimum = float(dense[:len(pool_names)].min())
        closure, quadratures = 0.0, {}
        for order in (4, 8):
            grid = accepted_step_quadrature(solution.t, boundaries, order=order)
            points = solution.sol(grid.nodes)
            minimum = min(minimum, float(points[:len(pool_names)].min()))
            raw, effective = [], []
            for time, point in zip(grid.nodes, points.T):
                audit = {}
                derivative = evaluate(time, point, audit)
                vr = [audit["raw_fluxes"][r] for r in reaction_names]
                ve = [audit["effective_fluxes"][r] for r in reaction_names]
                closure = max(closure, float(np.max(np.abs(s @ ve - derivative[:len(pool_names)]))))
                raw.append(vr)
                effective.append(ve)
            quadratures[order] = {"raw": integrate_intervals(np.asarray(raw).T, grid),
                                  "effective": integrate_intervals(np.asarray(effective).T, grid)}
        increments = np.diff(solution.sol(boundaries)[:len(pool_names)], axis=1)
        budget = s @ quadratures[8]["effective"]
        checks = {"pool_budgets": close(increments, budget),
                  "raw_quadrature": close(quadratures[4]["raw"], quadratures[8]["raw"]),
                  "executed_quadrature": close(quadratures[4]["effective"], quadratures[8]["effective"])}
        result = {"name": name, "purpose": purpose, "tolerance": tolerance,
                  "minimum_checked_mM": minimum, "closure_max_mM_per_day": closure,
                  "checks": {k: {"passed": int(v.sum()), "total": int(v.size)} for k, v in checks.items()},
                  "numerical_pass": bool(all(v.all() for v in checks.values())
                      and minimum >= controls["negative_state_tolerance_mM"]
                      and closure <= controls["closure_tolerance_mM_per_day"]),
                  "ATP_endpoint": float(solution.y[pool_names.index("ATP"), -1]),
                  "ADP_endpoint": float(solution.y[pool_names.index("ADP"), -1]),
                  "AMP_endpoint": float(solution.y[pool_names.index("AMP"), -1])}
        np.savez_compressed(folder / "dense_and_integrals.npz", time=times, states=dense,
                            pool_names=np.asarray(pool_names), reactions=np.asarray(reaction_names), matrix=s,
                            boundaries=boundaries, raw_4=quadratures[4]["raw"], raw_8=quadratures[8]["raw"],
                            effective_4=quadratures[4]["effective"], effective_8=quadratures[8]["effective"])
        save(folder, "result.json", result)
        results[name] = {"solution": solution, "result": result, "quadrature": quadratures[8], "pools": len(pool_names)}
        for i, pool in enumerate(pool_names):
            endpoints.append({"case": name, "pool": pool, "initial": initial[i], "endpoint": solution.y[i, -1],
                              "integrated_executed_balance": float(budget[i].sum())})
        save(OUT, "execution_progress.json", {"completed": [r["result"] for r in results.values()],
                                             "elapsed_seconds": perf_counter()-started})
        print(json.dumps(result), flush=True)

    def compare(case_name):
        a, b = (results[case_name + "_" + t] for t in design["tolerances"])
        grid = np.unique(np.r_[a["solution"].t, b["solution"].t,
                               np.linspace(a["solution"].t[0], a["solution"].t[-1], 601)])
        n = a["pools"]
        for quantity, left, right in (("states", a["solution"].sol(grid)[:n], b["solution"].sol(grid)[:n]),
            ("raw_integrals", a["quadrature"]["raw"], b["quadrature"]["raw"]),
            ("executed_integrals", a["quadrature"]["effective"], b["quadrature"]["effective"])):
            checks = close(left, right, "comparison")
            comparisons.append({"case": case_name, "quantity": quantity, "passed": int(checks.sum()),
                                "total": int(checks.size), "all_pass": bool(checks.all())})

    for case in design["cases"]:
        mode = case["mode"]
        pool_names, reaction_names, s = biochemical_matrix(mode)
        fraction = case["methyl_fraction"]
        partition = None if fraction is None else {"MTHF": old_initial[47]*fraction,
                                                   "MLTHF": old_initial[47]*(1-fraction)}
        x0 = build_initial_state(old_initial, mode=mode, added_initial={n: 0.0 for n in NEW_POOLS if n != "MLTHF"},
                                 folate_partition=partition)
        for pool in measured:
            require(x0[pool_names.index(pool)] == old_initial[names.index(pool)], "Measured J1 changed")
        for tolerance in design["tolerances"]:
            options, solver = reference_options(ref, ultrastrict=tolerance == "ultrastrict")
            def evaluate(t, x, audit=None):
                return equadiff_biochemical(t, x, network_mode=mode, oplah_policy=case["oplah_policy"],
                                            custom_params=parameters, numerical_audit=audit, **options)
            execute(case["name"] + "_" + tolerance, x0, pool_names, reaction_names, s, evaluate,
                    design["horizon_day"], np.asarray(design["audit_boundaries_day"]), solver, tolerance,
                    "conditional_Bordbar_structure_no_new_kinetic_fit")
        compare(case["name"])
    for case in synthetic:
        group = case["reactions"]
        s = matrix[:, [reactions.index(r) for r in group]]
        for tolerance in design["tolerances"]:
            _, solver = reference_options(ref, ultrastrict=tolerance == "ultrastrict")
            def evaluate(t, x, audit=None):
                rates = extension_rates(x, names, case["kinetics"])
                raw = np.array([rates[r] for r in group])
                effective, _ = limit_signed_fluxes(x, raw, s, threshold=ref["profile"]["reaction_availability_threshold_mM"])
                if audit is not None:
                    audit.update({"raw_fluxes": dict(zip(group, raw.tolist())),
                                  "effective_fluxes": dict(zip(group, effective.tolist()))})
                return s @ effective
            execute(case["name"] + "_" + tolerance, np.asarray(case["initial"]), names, group, s, evaluate,
                    [0, 2], np.array([0, 1, 2]), solver, tolerance, case["purpose"])
        compare(case["name"])
    with (OUT / "pool_endpoints.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=endpoints[0].keys())
        writer.writeheader()
        writer.writerows(endpoints)
    summary = {"cases": [r["result"] for r in results.values()], "convergence": comparisons,
               "all_numerical_gates_pass": all(r["result"]["numerical_pass"] for r in results.values())
                  and all(c["all_pass"] for c in comparisons),
               "new_Bordbar_integrations": 10, "synthetic_integrations": 4,
               "measured_initial_values_preserved": 55, "redox_Bordbar_validation": False,
               "biological_calibration": False, "global_promotion": False,
               "elapsed_seconds": perf_counter()-started}
    save(OUT, "summary.json", summary)
    for path, expected in hashes.items():
        require(sha(Path(path)) == expected, f"Input changed during campaign: {path}")
    save(OUT, "manifest.json", {"input_sha256": hashes,
         "output_sha256": {p.relative_to(OUT).as_posix(): sha(p) for p in OUT.rglob("*") if p.is_file()
                            and p.name != "manifest.json"}})
    print(json.dumps({"completed": len(results), "all_numerical_gates_pass": summary["all_numerical_gates_pass"]}))


if __name__ == "__main__":
    main()
