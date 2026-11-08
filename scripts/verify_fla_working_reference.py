"""Adopt the explicit working profile and test convergence/threshold sensitivity."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "scripts"):
    sys.path.insert(0, str(path))

from audit_ppp_constraints_and_numerics import file_hash, write_json
from equadiff_brodbar import BRODBAR_METABOLITE_MAP, equadiff_brodbar
from fla_working_reference import DEFAULT_WORKING_REFERENCE, load_working_reference, reference_options
from reaction_positivity import REACTION_POSITIVITY_VERSION, rbc_reaction_matrix
from test_reaction_positivity_fixed_context import (
    POLICY, audit_case, boundary_checks, check_legacy_parity, load_context,
)

DEFAULT_OUT = ROOT / "output/fla_working_reference_verification_2026_10_05"


def compare_arrays(left, right, *, atol, rtol):
    a, b = np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    if a.shape != b.shape or a.ndim != 2 or not a.size or not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
        raise ValueError("comparison arrays must be aligned, finite and nonempty")
    if not np.isfinite(atol) or not np.isfinite(rtol) or atol <= 0.0 or rtol <= 0.0:
        raise ValueError("comparison tolerances must be finite and positive")
    difference = np.abs(a - b)
    allowance = atol + rtol * np.abs(b)
    return np.max(difference, axis=1), np.all(difference <= allowance, axis=1)


def compare_cases(left, right, config, names, reactions):
    controls = config["validation_before_calibration"]
    kwargs = {"atol": controls["comparison_atol_mM"], "rtol": controls["comparison_rtol"]}
    first, second = left["solution"], right["solution"]
    common = np.unique(np.r_[first.t, second.t, np.linspace(1.0, 46.0, 901)])
    rows = []

    def add(kind, quantity, labels, a, b):
        maximum, passed = compare_arrays(a, b, **kwargs)
        rows.extend({"kind": kind, "quantity": quantity, "name": name,
                     "max_absolute_difference_mM": float(maximum[index]), "passes_declared_tolerance": bool(passed[index])}
                    for index, name in enumerate(labels))

    add("state", "concentration", names[:113], first.sol(common)[:113], second.sol(common)[:113])
    with np.load(left["directory"] / "quadrature_integrals.npz") as a, np.load(right["directory"] / "quadrature_integrals.npz") as b:
        if not np.array_equal(a["boundaries"], b["boundaries"]):
            raise ValueError("strict/ultrastrict audit intervals must coincide")
        boundaries = a["boundaries"]
        add("interval_state", "state_change", names[:113], np.diff(first.sol(boundaries)[:113]), np.diff(second.sol(boundaries)[:113]))
        for quantity in ("native_flux", "effective_flux", "absolute_reaction_flux_change"):
            add("interval_reaction", quantity, reactions, a[quantity], b[quantity])
        for quantity in ("effective_balance", "executed", "nonreaction_residual", "reaction_consistent_rate_change"):
            add("interval_pool", quantity, names[:113], a[quantity], b[quantity])
    return pd.DataFrame(rows)


def verify_cached_reference(baseline, params, x0, config):
    contract = json.loads((baseline / "preregistered_contract.json").read_text())
    directory = baseline / "J46_reaction_consistent_strict"
    summary = json.loads((directory / "summary.json").read_text())
    profile = config["profile"]
    if (summary["rtol"] != profile["solver_rtol"] or summary["atol"] != profile["solver_atol"]
            or contract["numerical_policy"]["availability_threshold_mM"] != profile["reaction_availability_threshold_mM"]):
        raise ValueError("cached reference does not match the active numerical profile")
    for filename, key in (("fixed_parameters.json", "fixed_parameter_sha256"), ("fixed_initial_state.csv", "initial_state_sha256")):
        if file_hash(baseline / filename) != contract[key]:
            raise ValueError("cached reference snapshot hash changed")
    if json.loads((baseline / "fixed_parameters.json").read_text()) != params:
        raise ValueError("cached reference kinetics differ from frozen context")
    saved = np.load(directory / "accepted_solver_states.npz")
    if not np.array_equal(saved["states"][:, 0], x0):
        raise ValueError("cached reference initial state differs")
    frame = pd.read_csv(directory / "accepted_solution_replay.csv", float_precision="round_trip")
    ode, _ = reference_options(config)
    errors = []
    for index in np.linspace(0, saved["time"].size - 1, 24, dtype=int):
        day = float(saved["time"][index])
        row = frame.loc[frame.time_day.sub(day).abs() < 1e-12]
        if len(row) != 1:
            raise ValueError("cached reference accepted node missing")
        derivative = equadiff_brodbar(day, saved["states"][:, index].copy(), custom_params=params, **ode)
        for pool in ("B13PG", "ATP", "ADP", "GO6P", "G6P", "F6P"):
            errors.append(abs(float(derivative[BRODBAR_METABOLITE_MAP[pool]]) - float(row.iloc[0][f"{pool}_executed"])))
    maximum = float(max(errors))
    if maximum > 1e-10:
        raise ValueError("explicit threshold changed the saved working-reference RHS")
    return {"maximum_saved_rhs_difference_mM_per_day": maximum, "accepted_probe_count": 24, "passes": True}


def run(profile_path, out_dir, *, historical=False):
    if (out_dir / "summary.json").exists():
        raise FileExistsError("completed verification exists; use a new --out-dir")
    config = load_working_reference(profile_path)
    source, baseline = ROOT / config["fixed_context"], ROOT / config["baseline_audit"]
    x0, params, names, times, curves, data_path = load_context(source)
    _, reactions, matrix = rbc_reaction_matrix(params.get("sam_adenylate_stoichiometry", "biochemical_transfer"))
    u, singular, _ = np.linalg.svd(matrix, full_matrices=True)
    rank = np.count_nonzero(singular > singular[0] * 1e-10)
    invariants = u[:, rank:].T
    controls = config["validation_before_calibration"]
    if (controls["quadrature_atol_mM"] != POLICY["quadrature_absolute_tolerance_mM"]
            or controls["quadrature_rtol"] != POLICY["quadrature_relative_tolerance"]
            or controls["negative_state_tolerance_mM"] != POLICY["minimum_raw_state_mM"]
            or controls["closure_tolerance_mM_per_day"] != POLICY["closure_tolerance_mM_per_day"]):
        raise ValueError("working controls must match the executable audit thresholds")
    out_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("fixed_parameters.json", "fixed_initial_state.csv"):
        shutil.copyfile(source / filename, out_dir / filename)
    input_paths = [profile_path, data_path, source / "preregistered_contract.json",
                   source / "strict/accepted_solver_states.npz", baseline / "preregistered_contract.json",
                   baseline / "J46_reaction_consistent_strict/accepted_solver_states.npz",
                   baseline / "J46_reaction_consistent_strict/accepted_solution_replay.csv",
                   ROOT / "src/equadiff_brodbar.py", ROOT / "src/reaction_positivity.py",
                   ROOT / "src/rbc_stoichiometry.py", ROOT / "src/fla_working_reference.py",
                   ROOT / "src/fla_balance_audit.py", ROOT / "scripts/test_reaction_positivity_fixed_context.py",
                   ROOT / "scripts/audit_ppp_constraints_and_numerics.py", Path(__file__)]
    reference_threshold = config["profile"]["reaction_availability_threshold_mM"]
    thresholds = [reference_threshold, *[value for value in controls["availability_thresholds_mM"] if value != reference_threshold]]
    write_json(out_dir / "preregistered_contract.json", {
        "working_reference": config, "historical_replay_requested": historical,
        "numerical_policy_version": REACTION_POSITIVITY_VERSION,
        "input_sha256": {str(path.resolve()): file_hash(path) for path in input_paths},
        "fixed_parameter_sha256": file_hash(out_dir / "fixed_parameters.json"),
        "initial_state_sha256": file_hash(out_dir / "fixed_initial_state.csv"),
        "threshold_execution_order_mM": thresholds, "optimization_performed": False,
        "observation_resets": False, "kinetic_parameters_promoted": False,
        "calibration_allowed": False, "threshold_selection_by_prediction_error": False,
        "sensitivity_is_observational_even_if_convergence_fails": True,
    })
    compatibility = {"legacy": check_legacy_parity(source, params),
                     "working_reference": verify_cached_reference(baseline, params, x0, config)}
    write_json(out_dir / "profile_compatibility.json", compatibility)
    if not historical:
        probes = []
        for threshold in thresholds:
            probe = boundary_checks(source, x0, params, threshold=threshold)
            probe["threshold_mM"] = threshold
            probes.append(probe)
        pd.concat(probes, ignore_index=True).to_csv(out_dir / "zero_boundary_checks.csv", index=False)
        print(f"1017 boundary checks passed; working and historical RHS parity verified", flush=True)
    cases, runs, all_metrics = {}, {}, []
    plan = [(None, "historical")] if historical else [(threshold, solver) for threshold in thresholds for solver in ("strict", "ultrastrict")]
    for threshold, solver in plan:
        label = "legacy_historical" if historical else f"tau_{threshold:.0e}_{solver}"
        ode, integration = reference_options(config, historical=historical, threshold=threshold, ultrastrict=solver == "ultrastrict")
        directory = out_dir / label
        directory.mkdir(exist_ok=True)
        print(f"[{label}] J1-J46 with frozen kinetics/initialization", flush=True)
        start = perf_counter()
        try:
            solution = solve_ivp(lambda day, values: equadiff_brodbar(float(day), values, custom_params=params, **ode),
                                 (1.0, 46.0), x0.copy(), dense_output=True, **integration)
            if not solution.success or not np.all(np.isfinite(solution.y)):
                raise RuntimeError(f"solver failure: {solution.message}")
            result, _, metrics = audit_case(solution, params, ode["positivity_policy"], 46.0, directory,
                times, curves, names, reactions, matrix, invariants, threshold=threshold, include_reaction_quadrature=True)
            result.update(status="completed", threshold_mM=threshold, solver=solver,
                          integration_options=integration, elapsed_seconds=perf_counter() - start)
            runs[label] = {"solution": solution, "directory": directory, "summary": result}
            metrics = metrics.copy()
            metrics["case"], metrics["threshold_mM"], metrics["solver"] = label, threshold, solver
            all_metrics.append(metrics)
            print(f"[{label}] complete; min={result['minimum_raw_dense_state_mM']:.3g}; pool/reaction quadrature failures={result['failed_pool_quantity_quadrature_checks']}/{result['failed_reaction_quantity_quadrature_checks']}", flush=True)
        except Exception as error:
            result = {"status": "failed", "threshold_mM": threshold, "solver": solver,
                      "error_type": type(error).__name__, "error": str(error), "numerical_integrity_pass": False,
                      "elapsed_seconds": perf_counter() - start, "kinetic_parameters_promoted": False}
            print(f"[{label}] failed: {error}", flush=True)
        cases[label] = result
        write_json(directory / "summary.json", result)
    convergence = {}
    if not historical:
        for threshold in thresholds:
            prefix = f"tau_{threshold:.0e}"
            if not all(f"{prefix}_{solver}" in runs for solver in ("strict", "ultrastrict")):
                convergence[str(threshold)] = {"passes": False, "reason": "missing or failed replay"}
                continue
            comparison = compare_cases(runs[f"{prefix}_strict"], runs[f"{prefix}_ultrastrict"], config, names, reactions)
            comparison.to_csv(out_dir / f"{prefix}_strict_ultrastrict_comparison.csv", index=False)
            failures = comparison.loc[~comparison.passes_declared_tolerance]
            passes = (not len(failures) and all(runs[f"{prefix}_{solver}"]["summary"]["numerical_integrity_pass"] for solver in ("strict", "ultrastrict")))
            convergence[str(threshold)] = {"passes": bool(passes), "failed_quantity_count": len(failures),
                "failed_by_kind": failures.groupby("kind").size().to_dict(), "check_count": len(comparison)}
        sensitivity = []
        reference_label = f"tau_{reference_threshold:.0e}_ultrastrict"
        if reference_label in runs:
            for threshold in thresholds:
                label = f"tau_{threshold:.0e}_ultrastrict"
                if label == reference_label or label not in runs:
                    continue
                comparison = compare_cases(runs[label], runs[reference_label], config, names, reactions)
                comparison["threshold_mM"], comparison["reference_threshold_mM"] = threshold, reference_threshold
                sensitivity.append(comparison)
        if sensitivity:
            pd.concat(sensitivity, ignore_index=True).to_csv(out_dir / "threshold_sensitivity.csv", index=False)
    if all_metrics:
        pd.concat(all_metrics, ignore_index=True).to_csv(out_dir / "all_predictive_metrics.csv", index=False)
    reference_passes = not historical and convergence.get(str(reference_threshold), {}).get("passes", False)
    result = {"working_reference_adopted": True, "working_reference_status": config["status"],
              "kernel_default": "legacy", "historical_replay_requested": historical,
              "cases": cases, "strict_ultrastrict_convergence": convergence,
              "reference_numerical_convergence_passes": bool(reference_passes),
              "optimization_performed": False, "kinetic_parameters_promoted": False,
              "calibration_allowed": False, "threshold_mM_selected": reference_threshold,
              "threshold_selection_by_prediction_error": False,
              "next_execution": "review threshold influence and B13PG/ATP executed flux attribution; freeze data and absolute accuracy contracts before calibration"}
    write_json(out_dir / "summary.json", result)
    lines = ["# Provisional FLA working reference", "",
             "The active work profile is reaction_consistent + strict BDF (rtol=1e-7, atol=1e-9), threshold 1e-3 mM. Legacy remains the historical kernel default and is explicitly available through --historical. This is not promotion of kinetic constants or biological validity.", "",
             "One explicit historical legacy replay is requested; the working profile is not changed." if historical else
             "Six fixed-kinetic J1-J46 cases are predeclared: three numerical availability thresholds, each strict/ultrastrict. No threshold is selected by prediction error. Failed cases remain failed evidence; guards are not relaxed.", "",
             "| Case | Status | Minimum raw concentration (mM) | Pool/reaction quadrature failures | Numerical integrity |",
             "|---|---|---:|---|---|"]
    for label, value in cases.items():
        lines.append(f"| {label} | {value['status']} | {value.get('minimum_raw_dense_state_mM', float('nan')):.6g} | {value.get('failed_pool_quantity_quadrature_checks', 'NA')}/{value.get('failed_reaction_quantity_quadrature_checks', 'NA')} | {value['numerical_integrity_pass']} |")
    lines += ["", "## Strict/ultrastrict convergence", "", "| Threshold (mM) | Passes | Failed comparisons |", "|---|---|---:|"]
    for threshold, value in convergence.items():
        lines.append(f"| {threshold} | {value['passes']} | {value.get('failed_quantity_count', 'NA')} |")
    lines += ["", "Convergence comparisons cover dense concentrations, experimental-interval state changes, individual native/executed reaction flux integrals, and numerical budgets. Quadrature order4/order8 also checks individual reaction integrals. Threshold sensitivity is a different experiment: differences between thresholds are not solver failures or evidence to optimize the threshold.", "",
              "Kinetic constants and initialization remain fixed; source and parameter hashes are recorded. Output states are not clipped, observation resets are off, absolute biological accuracy limits and source-data provenance remain unresolved. Calibration is still blocked.", "",
              "Use the JSON working-reference profile and reference_options() for new work; old runners/API defaults do not silently migrate. --historical explicitly selects the legacy profile without changing this work reference."]
    (out_dir / "decision_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(out_dir / "decision_report.md"), "reference_convergence_passes": bool(reference_passes)}), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=DEFAULT_WORKING_REFERENCE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--historical", action="store_true", help="Replay legacy explicitly, retaining the provisional work profile")
    args = parser.parse_args()
    run(args.profile, args.out_dir, historical=args.historical)
