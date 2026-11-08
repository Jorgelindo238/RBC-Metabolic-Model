"""Fixed-parameter free RBC replays with a single optional GLUT override."""

import argparse
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
from rbc_distinct_volume_transport import phase_matrix
from rbc_glut_only_transport import equadiff_glut_only

CONFIG = ROOT / "config/fla_glut_only_free_replay.json"
OBSERVATIONS = ROOT / "output/fla_latent_inference_preparation_2026_10_06/local_observation_inventory.csv"


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False)+"\n", encoding="utf-8")


def close(a, b, design, kind):
    a, b = np.asarray(a), np.asarray(b)
    return np.abs(a-b) <= design[kind+"_atol_mM"]+design[kind+"_rtol"]*np.maximum(np.abs(a), np.abs(b))


def observations():
    with OBSERVATIONS.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    grouped = {}
    for r in rows:
        grouped.setdefault(r["pool"], []).append((float(r["model_day"]), float(r["nominal_mM"])))
    time = np.array([t for t, _ in next(iter(grouped.values()))])
    if len(grouped) != 55 or len(time) != 14:
        raise ValueError("full preserved55 source channels and14 source times required")
    return time, {p: np.array([v for _, v in pairs]) for p, pairs in grouped.items()}


def case_options(case, candidate, seed, design, params):
    if case not in design["cases"]:
        raise ValueError("undeclared replay case")
    kinetics = None if case == "phase_native_reference" else seed if case == "glut_seed_control" else candidate["glucose_kinetics"]
    return {"glucose_kinetics": kinetics, "hematocrit": design["hematocrit"], "custom_params": params,
            "ph_policy": "clamped_diagnostic", "positivity_policy": "reaction_consistent", "curve_fit_strength": 0.0,
            "reaction_availability_threshold": design["availability_threshold_mM"]}


def replay(out, case, profile, end, initial, params, candidate, seed, design, time_exp, observed):
    begin = perf_counter()
    names, reactions, matrix, volumes, rate_volumes = phase_matrix(design["hematocrit"], params.get("sam_adenylate_stoichiometry", "biochemical_transfer"))
    options = case_options(case, candidate, seed, design, params)
    def evaluate(t, x, audit=None):
        return equadiff_glut_only(t, x, numerical_audit=audit, **options)
    sol = solve_ivp(evaluate, (1.0, end), initial.copy(), method="BDF", dense_output=True, **design["numerical_profiles"][profile])
    if not sol.success or sol.t[-1] != end or not np.array_equal(sol.y[:, 0], initial):
        raise ValueError(f"incomplete or changed-initial-state replay: {case}/{profile}/{end}: {sol.message}")
    cuts = np.arange(1., end+1.)
    time = np.unique(np.r_[np.linspace(1., end, 301), cuts, time_exp[time_exp <= end]])
    states = sol.sol(time)
    minimum = float(min(states[:113].min(), sol.y[:113].min()))
    archive = {"time": time, "states": states, "initial": initial, "accepted_time": sol.t, "accepted_states": sol.y,
               "boundaries": cuts, "pool_names": np.array(names), "reactions": np.array(reactions), "matrix": matrix,
               "pool_volumes": volumes, "reaction_volumes": rate_volumes}
    integrals = {}
    closure, raw_closure, extensions = 0., 0., 0
    for order in design["quadrature_orders"]:
        grid = accepted_step_quadrature(sol.t, cuts, order=order)
        x = sol.sol(grid.nodes)
        minimum = min(minimum, float(x[:113].min()))
        raw, executed = [], []
        for t, point in zip(grid.nodes, x.T):
            audit = {}
            derivative = evaluate(t, point, audit)
            vr = np.array([audit["raw_fluxes"][r] for r in reactions])
            ve = np.array([audit["effective_fluxes"][r] for r in reactions])
            closure = max(closure, float(np.max(np.abs(derivative[:113]-matrix@ve))))
            raw_closure = max(raw_closure, float(np.max(np.abs(audit["raw_derivative"]-matrix@vr))))
            extensions += int(audit.get("GLUT_substrate_extension_used", False))
            raw.append(vr)
            executed.append(ve)
        raw, executed = np.array(raw).T, np.array(executed).T
        integrals[order] = {"raw": integrate_intervals(raw, grid), "executed": integrate_intervals(executed, grid)}
        archive.update({f"q{order}_nodes": grid.nodes, f"q{order}_weights": grid.weights,
            f"q{order}_intervals": grid.interval_indices, f"q{order}_states": x,
            f"q{order}_raw_rates": raw, f"q{order}_executed_rates": executed,
            f"raw{order}": integrals[order]["raw"], f"executed{order}": integrals[order]["executed"]})
    increments = np.diff(sol.sol(cuts)[:113], axis=1)
    tests = {"executed_integrated_balance": close(increments, matrix@integrals[8]["executed"], design, "quadrature"),
             "raw_quadrature": close(integrals[4]["raw"], integrals[8]["raw"], design, "quadrature"),
             "executed_quadrature": close(integrals[4]["executed"], integrals[8]["executed"], design, "quadrature")}
    endpoint = {p: float(states[names.index(p), -1]) for p in design["guard_pools"]}
    samples = (time_exp > 1) & (time_exp <= end)
    metrics = {}
    for pool in design["guard_pools"]:
        actual = observed[pool][samples]
        predicted = sol.sol(time_exp[samples])[names.index(pool)]
        metrics[pool] = {"n_noninitial_source_points": int(samples.sum()), "source_days": time_exp[samples].tolist(),
                        "nominal_RMSE_mM": float(np.sqrt(np.mean((predicted-actual)**2)))}
        if end == 46:
            late = time_exp > 25
            delta = sol.sol(time_exp[late])[names.index(pool)]-observed[pool][late]
            metrics[pool]["J29_J46_nominal_RMSE_mM"] = float(np.sqrt(np.mean(delta**2)))
    contributions = {}
    net_integrals = integrals[8]["executed"].sum(axis=1)
    for pool in design["guard_pools"]:
        row = matrix[names.index(pool)]*net_integrals
        contributions[pool] = {r: float(row[j]) for j, r in enumerate(reactions) if matrix[names.index(pool), j] != 0}
    total = endpoint["ATP"]+endpoint["ADP"]+endpoint["AMP"]
    result = {"case": case, "profile": profile, "end_day": end, "elapsed_seconds": perf_counter()-begin,
        "endpoint": endpoint, "adenylate_total_endpoint_mM": total,
        "energy_charge_endpoint": (endpoint["ATP"]+.5*endpoint["ADP"])/total,
        "minimum_checked_mM": minimum, "raw_closure_max": raw_closure, "executed_closure_max": closure,
        "GLUT_negative_substrate_extension_at_quadrature_nodes": extensions,
        "quadrature_checks": {k: {"passed": int(v.sum()), "total": int(v.size)} for k, v in tests.items()},
        "source_fit_metrics": metrics, "executed_pool_contributions_mM": contributions,
        "transport_integrals_cell_mM": {r: float(net_integrals[reactions.index(r)]) for r in ("VEGLC", "VELAC", "VHK")},
        "numerical_pass": bool(all(v.all() for v in tests.values()) and minimum >= design["negative_tolerance_mM"]
            and closure <= design["closure_atol_mM_per_day"] and raw_closure <= design["closure_atol_mM_per_day"]),
        "GLC_is_free_state": True, "ph_clamped_reference": float(initial[-1]), "native_VELAC_law_unchanged": True,
        "biological_validation_pass": False, "candidate_promoted": False}
    if case == "phase_native_reference" and end == 4:
        previous = ROOT / "output/distinct_phase_transport_2026_10_06/fixed_context_v2" / f"phase_native_D3_{profile}/replay.npz"
        with np.load(previous) as a:
            result["archived_reference_accepted_states_bitwise_equal"] = bool(np.array_equal(sol.t, a["accepted_time"])
                                                                          and np.array_equal(sol.y, a["accepted_states"]))
    folder = out / f"J1_J{int(end)}" / f"{case}_{profile}"
    folder.mkdir(parents=True)
    np.savez_compressed(folder / "replay.npz", **archive)
    write(folder / "result.json", result)
    print(f"J1-J{int(end)} {case} {profile}: numerics={result['numerical_pass']} "
          f"EGLC={endpoint['EGLC']:.6g} GLC={endpoint['GLC']:.6g} ATP={endpoint['ATP']:.6g}", flush=True)
    return result, (states[:113], integrals[8]["raw"], integrals[8]["executed"])


def run(out):
    if out.exists():
        raise ValueError("new free-network replay archive required")
    design = json.loads(CONFIG.read_text())
    candidate = json.loads((ROOT / design["candidate"]).read_text())
    prior = json.loads((ROOT / design["phase_reference"]).read_text())
    params = json.loads((ROOT / design["initial_context"] / "frozen_parameters.json").read_text())
    initial = np.load(ROOT / design["initial_context"] / "frozen_initial_state.npz")["states"]
    obs_time, observed = observations()
    names = phase_matrix(design["hematocrit"])[0]
    if candidate["working_hematocrit"] != design["hematocrit"] or any(initial[names.index(p)] != v[0] for p, v in observed.items()):
        raise ValueError("candidate geometry or exact55 initial source values changed")
    files = [CONFIG, Path(__file__), ROOT / design["candidate"], ROOT / design["phase_reference"],
        ROOT / design["initial_context"] / "frozen_parameters.json", ROOT / design["initial_context"] / "frozen_initial_state.npz",
        ROOT / design["source_observations"], OBSERVATIONS, ROOT / "src/rbc_glut_only_transport.py",
        ROOT / "qa/test_glut_only_free_network.py", ROOT / "scripts/verify_glut_only_free_replay.py",
        ROOT / "src/fla_balance_audit.py"]
    files += [ROOT / p for p in prior["input_sha256"]]
    hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in files}
    out.mkdir(parents=True)
    write(out / "execution_design.json", {"design": design, "candidate": candidate, "seed_kinetics": prior["kinetics"]["glucose"],
        "initial_state": initial.tolist(), "input_sha256": hashes, "source_meaning": "nominal_concentrations_under_user_selected_phase_coordinates"})
    write(out / "observations.json", {"time": obs_time.tolist(), "values": {p: v.tolist() for p, v in observed.items()}})
    results, comparisons = [], []
    for end in design["horizons_end_day"]:
        stage_results, stage_comparisons = [], []
        for case in design["cases"]:
            pair = []
            for profile in design["numerical_profiles"]:
                result, arrays = replay(out, case, profile, end, initial, params, candidate, prior["kinetics"]["glucose"],
                                        design, obs_time, observed)
                results.append(result)
                stage_results.append(result)
                pair.append(arrays)
                write(out / "progress.json", {"results": results, "completed_replays": len(results)})
            tests = [close(pair[0][j], pair[1][j], design, "comparison") for j in range(3)]
            comparison = {"case": case, "end_day": end, "passed": bool(all(v.all() for v in tests)),
                          "checks_passed": sum(int(v.sum()) for v in tests), "checks_total": sum(v.size for v in tests)}
            stage_comparisons.append(comparison)
            comparisons.append(comparison)
        if not all(r["numerical_pass"] for r in stage_results) or not all(c["passed"] for c in stage_comparisons):
            print(f"Numerical extension gate failed at J{int(end)}; no longer replay launched.", flush=True)
            break
    summary = {"results": results, "convergence": comparisons, "replays_completed": len(results),
        "last_end_day": results[-1]["end_day"], "planned_replays": len(design["cases"])*len(design["numerical_profiles"])*len(design["horizons_end_day"]),
        "all_numerical_pass": all(r["numerical_pass"] for r in results) and all(c["passed"] for c in comparisons),
        "GLC_input_forcing": False, "native_VELAC_law_changed": False, "production_promoted": False,
        "optimization_run": False, "biological_validation_pass": False}
    write(out / "summary.json", summary)
    if any(sha(ROOT / p) != digest for p, digest in hashes.items()):
        raise ValueError("protected source/model input changed")
    write(out / "manifest.json", {"output_sha256": {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob("*")) if p.is_file()}})
    return {k: summary[k] for k in ("replays_completed", "planned_replays", "last_end_day", "all_numerical_pass", "production_promoted")}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(run(args.out.resolve()), indent=2))
