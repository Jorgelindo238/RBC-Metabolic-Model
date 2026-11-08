"""Fixed-parameter free J1-J4 replays under declared phase-volume assumptions."""

import argparse
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
from rbc_distinct_volume_transport import equadiff_distinct_volume, phase_matrix
from reaction_positivity import rbc_reaction_matrix

CONFIG = ROOT / "config/fla_distinct_volume_transport.json"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def run(out, data):
    out, data = out.resolve(), data.resolve()
    design = json.loads(CONFIG.read_text())
    for key in ("ufba_normalization_applied", "optimization_allowed", "biological_promotion_allowed",
                "production_default_changed", "measured_initial_state_changed"):
        if design[key] is not False:
            raise ValueError("fixed diagnostics cannot authorize normalization/fitting/promotion")
    parent = ROOT / design["initial_state_archive"]
    initial = np.load(parent / "frozen_initial_state.npz")["states"]
    params = json.loads((parent / "frozen_parameters.json").read_text())
    reference = json.loads((ROOT / design["working_reference"]).read_text())
    controls = reference["validation_before_calibration"]
    geometry = json.loads((data / "hematocrit_scenarios.json").read_text())
    kinetics = {"glucose": {"conductance": params["vmax_VEGLC"] / params["km_EGLC"],
                           "km_i": params["km_GLC_transport"], "km_e": params["km_EGLC"]},
                "lactate": {"conductance": params["vmax_VELAC"] / params["km_LAC"],
                            "km_i": params["km_LAC"], "km_e": params["km_LAC"]},
                "ph_reference": design["reversible_kinetics"]["pH_reference"]}
    cases = [{"name": "common_volume_native_clamped", "mode": "historical", "h": None}]
    for g in geometry:
        for mode in ("phase_native", "phase_glut_mct"):
            cases.append({"name": mode + "_" + g["source_cell"], "mode": mode, "h": g["hematocrit"]})
    inputs = [CONFIG, Path(__file__), ROOT / "src/rbc_distinct_volume_transport.py",
              ROOT / "src/equadiff_brodbar.py", ROOT / "src/reaction_positivity.py",
              ROOT / "src/rbc_stoichiometry.py", ROOT / "src/rbc_gem_audit.py", ROOT / "RBC/Rxn_RBC.txt",
              ROOT / "src/Data_Bordbar_et_al_exp.xlsx", ROOT / design["working_reference"],
              parent / "frozen_parameters.json", parent / "frozen_initial_state.npz",
              data / "hematocrit_scenarios.json", ROOT / design["jbc_workbook"]]
    hashes = {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p) for p in inputs}
    out.mkdir(parents=True, exist_ok=False)
    save(out / "preregistered_contract.json", {"design": design, "cases": cases,
         "kinetics": kinetics, "input_sha256": hashes, "initial_state": initial.tolist(),
         "pHi_clamped": float(initial[-1]), "not_a_biological_parameter_prior": True})
    names, reactions, common_s = rbc_reaction_matrix(params.get("sam_adenylate_stoichiometry", "biochemical_transfer"))
    boundaries = np.array([1., 2., 3., 4.])
    results, solutions = [], {}
    started = perf_counter()
    def close(a, b, kind):
        return np.abs(a - b) <= controls[kind + "_atol_mM"] + controls[kind + "_rtol"] * np.maximum(abs(a), abs(b))
    for case in cases:
        for tolerance in design["tolerances"]:
            name = case["name"] + "_" + tolerance
            options = {"mode": case["mode"], "custom_params": params,
                       "positivity_policy": "reaction_consistent", "reaction_availability_threshold": .001,
                       "ph_policy": "clamped_diagnostic"}
            if case["h"] is not None:
                options["hematocrit"] = case["h"]
            if case["mode"] == "phase_glut_mct":
                options.update(transport_kinetics=kinetics, phe=design["reversible_kinetics"]["pHe_diagnostic"])
            def evaluate(t, x, audit=None):
                return equadiff_distinct_volume(t, x, numerical_audit=audit, **options)
            rtol, atol = ((1e-7, 1e-9) if tolerance == "strict" else (1e-8, 1e-10))
            solution = solve_ivp(evaluate, (1, 4), initial.copy(), method="BDF", rtol=rtol, atol=atol, dense_output=True)
            if not solution.success or solution.t[-1] != 4 or not np.array_equal(solution.y[:, 0], initial):
                raise ValueError("uninterrupted fixed-IC replay failed " + name)
            matrix = common_s if case["h"] is None else phase_matrix(case["h"])[2]
            dense_time = np.linspace(1, 4, 301)
            dense = solution.sol(dense_time)
            minimum = float(min(dense[:113].min(), solution.y[:113].min()))
            quad = {}
            closure = 0.
            for order in (4, 8):
                grid = accepted_step_quadrature(solution.t, boundaries, order=order)
                points = solution.sol(grid.nodes)
                minimum = min(minimum, float(points[:113].min()))
                raw, effective = [], []
                for t, x in zip(grid.nodes, points.T):
                    audit = {}
                    d = evaluate(t, x, audit)
                    vr = np.array([audit["raw_fluxes"][r] for r in reactions])
                    ve = np.array([audit["effective_fluxes"][r] for r in reactions])
                    closure = max(closure, float(np.abs(d[:113] - matrix @ ve).max()))
                    raw.append(vr)
                    effective.append(ve)
                quad[order] = {"raw": integrate_intervals(np.array(raw).T, grid),
                               "executed": integrate_intervals(np.array(effective).T, grid)}
            increments = np.diff(solution.sol(boundaries)[:113], axis=1)
            checks = [close(increments, matrix @ quad[8]["executed"], "quadrature"),
                      close(quad[4]["raw"], quad[8]["raw"], "quadrature"),
                      close(quad[4]["executed"], quad[8]["executed"], "quadrature")]
            result = {"case": case["name"], "tolerance": tolerance, "hematocrit": case["h"],
                      "minimum_checked_mM": minimum, "closure_max_mM_per_day": closure,
                      "quadrature_checks_passed": sum(int(c.sum()) for c in checks),
                      "quadrature_checks_total": sum(int(c.size) for c in checks),
                      "numerical_pass": bool(all(c.all() for c in checks) and minimum >= -1e-10 and closure <= 1e-7),
                      "endpoint": {p: float(solution.y[names.index(p), -1]) for p in ("ATP", "ADP", "AMP", "GLC", "EGLC", "LAC", "ELAC")},
                      "executed_transport_integrals_cell_mM": {p: float(quad[8]["executed"][reactions.index(p)].sum()) for p in ("VEGLC", "VELAC")},
                      "free_pH_prediction": False, "biological_pass": False}
            if case["mode"] == "phase_glut_mct":
                result["MCT_proton_export_amount_per_L_bag"] = case["h"] * result["executed_transport_integrals_cell_mM"]["VELAC"]
            folder = out / name
            folder.mkdir()
            np.savez_compressed(folder / "replay.npz", accepted_time=solution.t, accepted_states=solution.y,
                time=dense_time, states=dense, pool_names=np.array(names), reactions=np.array(reactions),
                matrix=matrix, boundaries=boundaries, raw4=quad[4]["raw"], raw8=quad[8]["raw"],
                executed4=quad[4]["executed"], executed8=quad[8]["executed"], initial=initial)
            save(folder / "result.json", result)
            solutions[name] = (dense, quad[8]["executed"])
            results.append(result)
            save(out / "execution_progress.json", {"completed": results, "elapsed_seconds": perf_counter() - started})
            print(name + " ATP=" + str(result["endpoint"]["ATP"]) + " numerical=" + str(result["numerical_pass"]), flush=True)
    comparisons = []
    for case in cases:
        strict, ultra = (solutions[case["name"] + "_" + t] for t in ("strict", "ultrastrict"))
        tests = [close(strict[0][:113], ultra[0][:113], "comparison"), close(strict[1], ultra[1], "comparison")]
        comparisons.append({"case": case["name"], "passed": all(c.all() for c in tests),
                            "checks_passed": sum(int(c.sum()) for c in tests), "checks_total": sum(int(c.size) for c in tests)})
    comparisons = [{**r, "passed": bool(r["passed"])} for r in comparisons]
    save(out / "summary.json", {"results": results, "convergence": comparisons,
         "numerical_pass": all(r["numerical_pass"] for r in results) and all(r["passed"] for r in comparisons),
         "elapsed_seconds": perf_counter() - started, "optimization_run": False,
         "ufba_applied": False, "biological_promotion": False, "free_pH_prediction": False})
    for p, expected in hashes.items():
        if sha(ROOT / p) != expected:
            raise ValueError("protected input changed " + p)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    args = parser.parse_args()
    run(args.out, args.data)
