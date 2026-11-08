"""Independent weighted-fit, reconstruction, scope and metric archive checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
from scipy.interpolate import BSpline, PPoly, PchipInterpolator, make_smoothing_spline

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from equadiff_brodbar import BRODBAR_METABOLITE_MAP
from fla_synthetic_recovery import unit_capacity_basis, executed_transport
from fla_working_reference import reference_options
from fla_precalibration_readiness import evaluate_readiness

POOLS = ("EGLC", "ELAC", "GLC", "LAC")
PARAMETERS = ("vmax_VEGLC", "vmax_VELAC")
REACTIONS = ("VEGLC", "VELAC")


def read_json(path):
    return json.loads(path.read_text())


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analytic_fit(basis, targets, weights, low, high):
    basis, targets, weights = map(np.asarray, (basis, targets, weights))
    if (basis.ndim != 2 or basis.shape[0] != 2 or basis.shape != targets.shape
            or weights.shape != (basis.shape[1],) or not basis.shape[1]
            or not np.all(np.isfinite(np.r_[basis.ravel(), targets.ravel(), weights])) or np.any(weights <= 0)):
        raise ValueError("invalid independent weighted fit")
    denominator = np.sum(weights[None, :]*basis**2, axis=1)
    if np.any(denominator <= 0):
        raise ValueError("unexcited capacity")
    return np.clip(np.sum(weights[None, :]*basis*targets, axis=1)/denominator, low, high)


def independent_metrics(actual, reference, *, flux=False):
    if actual.shape != reference.shape or not np.all(np.isfinite(np.r_[actual.ravel(), reference.ravel()])):
        raise ValueError("nonfinite or unaligned predictions")
    rmse = np.sqrt(np.mean((actual-reference)**2, axis=1))
    mean = np.mean(np.abs(reference), axis=1)
    scale = np.maximum(np.sqrt(np.mean(reference**2, axis=1)), 1e-6) if flux else np.maximum(mean, .001)
    return {"absolute_rmse": rmse, "truth_mean": mean, "mean_nrmse": rmse/scale,
            "last_error": actual[:, -1]-reference[:, -1],
            "excursion_nrmse": None if flux else rmse/np.maximum(np.ptp(reference, axis=1), .001)}


def verify(out):
    contract, summary = read_json(out / "preregistered_contract.json"), read_json(out / "summary.json")
    design, parent_design = contract["design"], contract["parent_design"]
    parent = ROOT / design["parent_archive"]
    initial_archive = np.load(out / "frozen_initial_state.npz")
    initial, names = initial_archive["states"], initial_archive["names"]
    baseline = read_json(ROOT / contract["working_reference"]["fixed_context"] / "fixed_parameters.json")
    base = np.asarray([baseline[p] for p in PARAMETERS])
    low, high = base*parent_design["search_multiplier_bounds"][0], base*parent_design["search_multiplier_bounds"][1]
    truth_capacity = base*parent_design["truth_multipliers"]
    truth = np.load(parent / "truth/evaluation.npz")
    table = pd.read_csv(out / "full_pool_replay_metrics.csv", float_precision="round_trip")
    ode, _ = reference_options(contract["working_reference"])
    checks = []

    def check(name, condition, detail=None):
        checks.append({"name": name, "passes": bool(condition), "detail": detail})

    check("synthetic_scope", contract["biological_calibration_allowed"] is False
          and contract["global_model_promotion_allowed"] is False
          and summary["biological_calibration_allowed"] is False and summary["global_model_promotion_allowed"] is False
          and contract["truth_used_to_select_smoothing_or_grid"] is False)
    check("input_hashes", all(sha256(Path(path)) == digest for path, digest in contract["input_sha256"].items()))
    check("initial_and_parameters_frozen", np.array_equal(initial, np.load(parent / "frozen_initial_state.npz")["states"])
          and np.array_equal(names, np.load(parent / "frozen_initial_state.npz")["names"])
          and read_json(out / "frozen_parameters.json") == baseline)
    readiness = evaluate_readiness(read_json(ROOT / "config/fla_adenylate_redox_readiness.json"), root=ROOT,
                                  frozen_initial_redox=[initial[list(names).index(p)] for p in ("NAD", "NADH")])
    protocol = read_json(ROOT / "output/adenylate_redox_readiness_2026_10_05_v2/coupled_sensitivity_protocol.json")
    check("biological_gate_still_blocked", readiness["scientific_contract_complete"] is False
          and readiness["optimization_allowed"] is False and len(readiness["blockers"]) == 13
          and protocol["execution_authorized"] is False)
    expected_methods = [f"{mode}_uniform{count}" for mode in ("raw", "smooth") for count in design["uniform_grid_counts"]]
    expected_methods += [f"{mode}_aligned{order}" for mode in ("raw", "smooth") for order in (4, 8)]
    expected_methods += ["raw_integrated", "smoothed_inputs_integrated", "legacy_raw401"]
    expected_cases = ["clean"] + [f"noise_{seed}" for seed in design["noise_seeds"]]
    expected_labels = {f"{case}_{method}" for case in expected_cases for method in expected_methods}
    check("complete_conditional_design", set(contract["methods"]) == set(expected_methods)
          and contract["cases"] == expected_cases and len(summary["fits"]) == len(expected_labels)
          and {row["label"] for row in summary["fits"]} == expected_labels)
    expected_replays = [f"{case}_{method}" for case in ["clean"]+[f"noise_{s}" for s in design["replay_noise_seeds"]]
                        for method in design["replay_methods"]]
    check("fixed_replay_subset", contract["replay_labels"] == expected_replays
          and [row["label"] for row in summary["replays"]] == expected_replays
          and contract["full_ODE_replayed_methods_are_fixed_not_rank_selected"] is True
          and summary["new_ODE_replay_count"] == 2*len(expected_replays))
    for aggregate in summary["aggregated_noise_results"]:
        group = [row for row in summary["fits"] if row["case"] != "clean" and row["method"] == aggregate["method"]]
        errors = np.asarray([row["relative_parameter_error"] for row in group])
        check(f"noise_aggregate:{aggregate['method']}", aggregate["noise_seed_count"] == len(design["noise_seeds"])
              and np.array_equal(np.median(errors, axis=0), aggregate["median_relative_parameter_error"])
              and np.array_equal(errors.max(axis=0), aggregate["maximum_relative_parameter_error"])
              and aggregate["bound_case_count"] == sum(row["at_bound"] for row in group))
    convergence_checks = read_json(out / "aligned_capacity_convergence.json")
    for row in convergence_checks:
        coarse = next(f for f in summary["fits"] if f["case"] == row["case"] and f["method"] == f"{row['mode']}_aligned4")
        fine = next(f for f in summary["fits"] if f["case"] == row["case"] and f["method"] == f"{row['mode']}_aligned8")
        difference = np.abs(np.asarray(coarse["capacities"])/fine["capacities"]-1)
        check(f"aligned_convergence_receipt:{row['case']}:{row['mode']}",
              np.array_equal(difference, row["capacity_relative_difference"])
              and bool(np.all(difference <= design["capacity_quadrature_relative_tolerance"])) == row["passes_numerical_resolution_check"])
    check("full_metric_coverage", len(table) == len(expected_replays)*2*115
          and not table.duplicated(["label", "period", "kind", "name"]).any())
    source = pd.read_csv(parent / "datasets/dense_clean/observations.csv", float_precision="round_trip")
    receipt = read_json(out / "time_partition_receipt.json")
    groups = receipt["source_index_groups"]
    source_time, source_values = source.time_day.to_numpy(), source[list(POOLS)].to_numpy().T
    rebuilt_groups = []
    for i, day in enumerate(source_time):
        if not rebuilt_groups or day-source_time[rebuilt_groups[-1][0]] > 1e-10:
            rebuilt_groups.append([i])
        else:
            rebuilt_groups[-1].append(i)
    time = np.asarray([source_time[g[0]] for g in groups])
    clean = np.column_stack([source_values[:, g].mean(axis=1) for g in groups])
    canonical = pd.read_csv(out / "canonical_clean_observations.csv", float_precision="round_trip")
    check("canonical_partition_before_noise", groups == rebuilt_groups and receipt["before_noise"] is True
          and receipt["original_count"] == 689 and receipt["canonical_count"] == 687
          and np.array_equal(canonical.time_day, time) and np.array_equal(canonical[list(POOLS)].to_numpy().T, clean)
          and np.min(np.diff(time)) > 1e-10)
    curves_by_case = {}
    for case in expected_cases:
        frame = pd.read_csv(out / "datasets" / case / "observations.csv", float_precision="round_trip")
        expected = clean.copy()
        variance = np.log1p(design["noise_coefficient_of_variation"]**2)
        if case != "clean":
            expected[:, 1:] *= np.exp(np.random.default_rng(int(case.split("_")[1])).normal(size=(4, len(time)-1))*np.sqrt(variance)-.5*variance)
        values = frame[list(POOLS)].to_numpy().T
        check(f"paired_training_data:{case}", np.array_equal(frame.time_day, time)
              and time[0] == 1. and time[-1] == 22. and np.all(values > 0)
              and np.allclose(values, expected, rtol=1e-13, atol=1e-14) and np.array_equal(values[:, 0], clean[:, 0]))
        curves_by_case[case] = {}
        for mode in ("raw", "smooth"):
            saved = read_json(out / "datasets" / case / f"{mode}_curve_receipt.json")
            curves = []
            for i, item in enumerate(saved["coefficient_receipts"]):
                if mode == "raw":
                    curve = PPoly(np.asarray(item["coefficients"]), np.asarray(item["breaks"]), extrapolate=False)
                    regenerated = PchipInterpolator(time, values[i], extrapolate=False)
                    check(f"raw_coefficients:{case}:{POOLS[i]}", np.array_equal(curve.c, regenerated.c))
                else:
                    curve = BSpline(np.asarray(item["knots"]), np.asarray(item["coefficients"]), item["degree"], extrapolate=False)
                    logs = np.log(values[i])
                    if case != "clean":
                        logs[1:] += .5*variance
                    regenerated = make_smoothing_spline(time, logs, lam=None)
                    shift = np.log(values[i, 0])-regenerated(time[0])
                    check(f"training_only_GCV:{case}:{POOLS[i]}", np.array_equal(curve.t, regenerated.t)
                          and np.allclose(curve.c, regenerated.c, rtol=1e-12, atol=1e-12)
                          and abs(shift-saved["log_anchor_shifts"][i]) < 1e-12)
                curves.append(curve)
            curves_by_case[case][mode] = (curves, saved["log_anchor_shifts"], values)
    max_fit_error, max_metric_error = 0., 0.
    original_query = np.linspace(1., 22., 401)
    original_curves = [PchipInterpolator(source_time, row, extrapolate=False) for row in source_values]
    original_states = np.repeat(initial[:, None], len(original_query), axis=1)
    for pool, curve in zip(POOLS, original_curves):
        original_states[BRODBAR_METABOLITE_MAP[pool]] = curve(original_query)
    original_targets = np.asarray([-1., 1.])[:, None]*np.asarray([c.derivative()(original_query) for c in original_curves[:2]])
    original_basis = unit_capacity_basis(original_query, original_states, baseline, ode)
    original_capacities = analytic_fit(original_basis, original_targets, np.ones(401), low, high)
    parent_fitted = read_json(parent / "dense_clean_pointwise/learned_synthetic_parameters.json")
    check("original_clean_parent_reconstruction", np.max(np.abs(original_capacities-[parent_fitted[p] for p in PARAMETERS])) < 1e-6)
    canonical_fit = next(row for row in summary["fits"] if row["label"] == "clean_legacy_raw401")
    timestamp_impact = {"classification": "posthoc_numerical_partition_diagnostic_not_candidate_selection",
        "new_ODE_replay_count": 0, "original_count": len(source_time), "canonical_count": len(time),
        "pointwise_teacher_grid_count": 401, "equal_point_objective_in_both": True,
        "original_relative_capacity_error": np.abs(original_capacities/truth_capacity-1).tolist(),
        "canonical_relative_capacity_error": canonical_fit["relative_parameter_error"],
        "noise_draws_changed_between_parent_and_successor": True}
    (out / "timestamp_impact.json").write_text(json.dumps(timestamp_impact, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    for row in summary["fits"]:
        label, method = row["label"], row["method"]
        problem = np.load(out / "fits" / label / "training_problem.npz")
        basis, targets, weights, grid = (problem[key] for key in ("basis", "targets", "weights", "grid"))
        analytic = analytic_fit(basis, targets, weights, low, high)
        difference = float(np.max(np.abs(analytic-row["capacities"])))
        max_fit_error = max(max_fit_error, difference)
        fit = read_json(out / "fits" / label / "conditional_recovery.json")
        check(f"closed_form_fit:{label}", difference < 1e-6 and fit["capacities"] == row["capacities"]
              and np.allclose(row["relative_parameter_error"], np.abs(analytic/truth_capacity-1), rtol=1e-5, atol=1e-6)
              and len(fit["starts"]) == 3 and fit["global_identifiability_established"] is False, difference)
        mode = "smooth" if method.startswith("smooth") else "raw"
        curves, shifts, values = curves_by_case[row["case"]][mode]
        is_integral = method in {"raw_integrated", "smoothed_inputs_integrated"}
        if is_integral:
            check(f"raw_interval_teacher:{label}", np.array_equal(targets, np.asarray([-1., 1.])[:, None]*np.diff(values[:2], axis=1))
                  and np.array_equal(weights, np.ones(len(time)-1)) and np.array_equal(grid, (time[:-1]+time[1:])/2))
            # Reconstruct integrals using the complete kernel on three prespecified intervals.
            nodes, local_weights = np.polynomial.legendre.leggauss(16)
            selected = np.asarray([0, len(time)//2, len(time)-2])
            half = (time[selected+1]-time[selected])/2
            query = (((time[selected+1]+time[selected])/2)[:, None]+half[:, None]*nodes).ravel()
        else:
            if "uniform" in method or method == "legacy_raw401":
                count = 401 if method == "legacy_raw401" else int(method.split("uniform")[1])
                expected_grid = np.linspace(1., 22., count)
                expected_weights = np.full(count, 21./(count-1))
                expected_weights[[0, -1]] *= .5
                if method == "legacy_raw401":
                    expected_weights[:] = 1.
            else:
                order = int(method.split("aligned")[1])
                nodes, local_weights = np.polynomial.legendre.leggauss(order)
                half = np.diff(time)/2
                expected_grid = (((time[:-1]+time[1:])/2)[:, None]+half[:, None]*nodes).ravel()
                expected_weights = (half[:, None]*local_weights).ravel()
            check(f"temporal_grid_weights:{label}", np.array_equal(grid, expected_grid) and np.array_equal(weights, expected_weights))
            selected = np.asarray([0, len(grid)//2, len(grid)-1])
            query = grid[selected]
        pool_values = np.asarray([curve(query) for curve in curves])
        pool_derivatives = np.asarray([curve.derivative()(query) for curve in curves])
        if mode == "smooth":
            pool_values = np.exp(pool_values+np.asarray(shifts)[:, None])
            pool_derivatives *= pool_values
        states = np.repeat(initial[:, None], len(query), axis=1)
        for pool, value in zip(POOLS, pool_values):
            states[BRODBAR_METABOLITE_MAP[pool]] = value
        executed = unit_capacity_basis(query, states, baseline, ode)
        if is_integral:
            integrated = np.sum(executed.reshape(2, 3, 16)*local_weights[None, None, :]*half[None, :, None], axis=2)
            parity = np.allclose(integrated, basis[:, selected], rtol=1e-12, atol=1e-12)
        else:
            parity = np.allclose(executed, basis[:, selected], rtol=1e-12, atol=1e-12)
            parity = parity and np.allclose(targets[:, selected], np.asarray([-1., 1.])[:, None]*pool_derivatives[:2], rtol=1e-12, atol=1e-12)
        check(f"complete_kernel_problem_parity:{label}", parity)
    min_checked = float("inf")
    for label in expected_replays:
        directory = out / "replays" / label
        candidate = read_json(directory / "learned_synthetic_parameters.json")
        fitted = next(row for row in summary["fits"] if row["label"] == label)
        check(f"kinetic_scope:{label}", candidate.keys() == baseline.keys()
              and all(candidate[key] == value for key, value in baseline.items() if key not in PARAMETERS)
              and all(candidate[p] == fitted["capacities"][i] for i, p in enumerate(PARAMETERS)))
        learned = np.load(directory / "evaluation.npz")
        min_checked = min(min_checked, float(np.min(learned["states"][:113])))
        check(f"evaluation_alignment:{label}", np.array_equal(learned["time"], truth["time"])
              and np.all(np.isfinite(learned["states"])) and np.min(learned["states"][:113]) >= 0)
        numerical = read_json(directory / "numerical_audit.json")
        convergence = pd.read_csv(directory / "solver_convergence.csv")
        check(f"numerical_audit:{label}", numerical["passes"] and numerical["negative_accepted_count"] == 0
              and numerical["minimum_raw_checked_concentration_mM"] >= 0
              and numerical["max_executed_balance_closure_mM_per_day"] <= 1e-10
              and len(convergence) == 114 and convergence.strict_ultrastrict_pass.all())
        for solver in ("strict", "ultrastrict"):
            archive = np.load(directory / f"{solver}_accepted_states.npz")
            min_checked = min(min_checked, float(np.min(archive["states"][:113])))
            check(f"raw_replay:{label}:{solver}", np.array_equal(archive["states"][:, 0], initial)
                  and np.all(np.isfinite(archive["states"])) and np.min(archive["states"][:113]) >= 0
                  and archive["time"][0] == 1. and archive["time"][-1] == 46. and np.all(np.diff(archive["time"]) > 0))
        selected = np.asarray([0, len(truth["time"])//2, len(truth["time"])-1])
        full = executed_transport(truth["time"][selected], learned["states"][:, selected], candidate, ode)
        check(f"replayed_executed_flux:{label}", np.allclose(full["effective"], learned["effective_flux"][:, selected], rtol=1e-12, atol=1e-12)
              and np.allclose(full["native"], learned["native_flux"][:, selected], rtol=1e-12, atol=1e-12)
              and np.allclose(full["factors"], learned["availability_factors"][:, selected], rtol=1e-12, atol=1e-12))
        for period in ("training", "holdout"):
            mask = truth["time"] <= 22. if period == "training" else truth["time"] > 22.
            for flux, kind, pool_names in ((False, "concentration", names[:113]), (True, "executed_flux", REACTIONS)):
                actual = learned["effective_flux"][:, mask] if flux else learned["states"][:113, mask]
                reference = truth["effective"][:, mask] if flux else truth["states"][:113, mask]
                expected = independent_metrics(actual, reference, flux=flux)
                for i, pool in enumerate(pool_names):
                    saved = table[(table.label == label) & (table.period == period) & (table.kind == kind) & (table.name == pool)]
                    if len(saved) != 1:
                        raise ValueError(f"missing or duplicated metric {label}:{period}:{pool}")
                    for key, values in expected.items():
                        if values is not None:
                            max_metric_error = max(max_metric_error, abs(float(saved[key].iloc[0])-values[i]))
    check("independent_all_metrics", max_metric_error < 1e-12, float(max_metric_error))
    qa = None
    if (out / "qa_results.xml").exists():
        suites = list(ET.parse(out / "qa_results.xml").getroot().iter("testsuite"))
        qa = {key: sum(int(s.get(key, 0)) for s in suites) for key in ("tests", "failures", "errors", "skipped")}
        qa["passes"] = qa["tests"] > 0 and qa["failures"] == 0 and qa["errors"] == 0
        check("qa_suite", qa["passes"])
    report = {"independent_checks_pass": all(c["passes"] for c in checks), "check_count": len(checks),
              "max_closed_form_capacity_difference": max_fit_error, "max_metric_difference": float(max_metric_error),
              "minimum_independently_checked_concentration_mM": min_checked, "checks": checks,
              "scope": "conditional_fit_and_sampled_problem_parity; full archived metric recomputation; raw accepted state checks",
              "current_environment": {"python": platform.python_version(), "numpy": np.__version__,
                                      "scipy": scipy.__version__, "pandas": pd.__version__},
              "biological_readiness_status": readiness["status"],
              "verifier_sha256": sha256(Path(__file__))}
    (out / "independent_verification.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    if not report["independent_checks_pass"]:
        raise ValueError("independent screen verification failed")
    final = read_json(out / "final_verification.json")
    final.update(independently_verified_at=datetime.now(timezone.utc).isoformat(), independent_archive_checks_pass=True,
                 independent_archive_check_count=len(checks), qa=qa,
                 supporting_code_sha256={str(p): sha256(p) for p in (Path(__file__), ROOT / "qa/test_fla_teacher_resolution.py",
                                                                  ROOT / "scripts/finalize_fla_teacher_resolution_figures.py")},
                 output_sha256={str(p.relative_to(out)): sha256(p) for p in out.rglob("*") if p.is_file()
                                and p.name not in {"final_verification.json", "independent_verification.json"}})
    (out / "final_verification.json").write_text(json.dumps(final, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "output/fla_teacher_resolution_2026_10_05_v2")
    args = parser.parse_args()
    result = verify(args.out.resolve())
    print(json.dumps({key: value for key, value in result.items() if key != "checks"}))
