"""Independently check the sparse FLA comparison and its sealed numerical evidence."""

from __future__ import annotations

import argparse
import json
import platform
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
from scipy.interpolate import BSpline, PchipInterpolator

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from equadiff_brodbar import BRODBAR_METABOLITE_MAP
from fla_synthetic_recovery import unit_capacity_basis, executed_transport
from fla_working_reference import reference_options
from fla_precalibration_readiness import evaluate_readiness
from run_fla_sparse_teacher_resolution import verify_archive_inputs
from verify_fla_teacher_resolution import analytic_fit, independent_metrics, read_json, sha256

POOLS = ("EGLC", "ELAC", "GLC", "LAC")
PARAMETERS = ("vmax_VEGLC", "vmax_VELAC")
REACTIONS = ("VEGLC", "VELAC")
TIMES = np.asarray([1., 4., 8., 11., 15., 18., 22.])


def verify(out):
    contract, summary = read_json(out / "preregistered_contract.json"), read_json(out / "summary.json")
    design, parent_design = contract["design"], contract["parent_design"]
    parent, dense = ROOT / design["parent_archive"], ROOT / design["dense_comparison_archive"]
    initial_archive = np.load(out / "frozen_initial_state.npz")
    initial, names = initial_archive["states"], initial_archive["names"]
    baseline = read_json(ROOT / contract["working_reference"]["fixed_context"] / "fixed_parameters.json")
    base = np.asarray([baseline[p] for p in PARAMETERS])
    low, high = base*parent_design["search_multiplier_bounds"][0], base*parent_design["search_multiplier_bounds"][1]
    truth_capacities = base*parent_design["truth_multipliers"]
    truth = np.load(parent / "truth/evaluation.npz")
    ode, _ = reference_options(contract["working_reference"])
    table = pd.read_csv(out / "full_pool_replay_metrics.csv", float_precision="round_trip")
    checks = []

    def check(name, passed, detail=None):
        checks.append({"name": name, "passes": bool(passed), "detail": detail})

    check("synthetic_scope", contract["contract_type"] == "synthetic_sparse_teacher_resolution_diagnostic"
          and not contract["biological_calibration_allowed"] and not contract["global_model_promotion_allowed"]
          and not contract["real_concentrations_used_as_training_targets"] and not contract["teacher_forcing"]
          and not contract["observation_reset"] and not contract["truth_used_to_select_smoothing_or_grid"]
          and not summary["biological_calibration_allowed"] and not summary["global_model_promotion_allowed"])
    check("input_hashes", all(sha256(Path(p)) == h for p, h in contract["input_sha256"].items()))
    dense_contract = verify_archive_inputs(dense)
    check("dense_comparison_unchanged", dense_contract["working_reference"] == contract["working_reference"]
          and dense_contract["parent_design"] == parent_design)
    check("frozen_context", read_json(out / "frozen_parameters.json") == baseline
          and np.array_equal(initial, np.load(parent / "frozen_initial_state.npz")["states"])
          and np.array_equal(names, np.load(parent / "frozen_initial_state.npz")["names"]))
    readiness = evaluate_readiness(read_json(ROOT / "config/fla_adenylate_redox_readiness.json"), root=ROOT,
        frozen_initial_redox=[initial[list(names).index(p)] for p in ("NAD", "NADH")])
    protocol = read_json(ROOT / "output/adenylate_redox_readiness_2026_10_05_v2/coupled_sensitivity_protocol.json")
    check("scientific_guard_unchanged", len(readiness["blockers"]) == 13 and not readiness["scientific_contract_complete"]
          and not readiness["optimization_allowed"] and not protocol["execution_authorized"])
    source = pd.read_csv(parent / "datasets/sparse_clean/observations.csv", float_precision="round_trip")
    clean = source[list(POOLS)].to_numpy().T
    partition = read_json(out / "time_partition_receipt.json")
    check("exact_seven_time_partition", np.array_equal(source.time_day, TIMES) and design["training_times_day"] == TIMES.tolist()
          and partition["original_count"] == partition["canonical_count"] == 7
          and partition["source_index_groups"] == [[i] for i in range(7)]
          and read_json(parent / "preregistered_contract.json")["sparse_training_times"] == TIMES.tolist())
    methods = [f"{mode}_uniform{n}" for mode in ("raw", "smooth") for n in design["uniform_grid_counts"]]
    methods += [f"{mode}_aligned{n}" for mode in ("raw", "smooth") for n in (4, 8)]
    methods += ["raw_integrated", "smoothed_inputs_integrated", "legacy_raw401"]
    cases = ["clean"]+[f"noise_{seed}" for seed in design["noise_seeds"]]
    labels = {f"{case}_{method}" for case in cases for method in methods}
    replays = [f"{case}_{method}" for case in ["clean"]+[f"noise_{s}" for s in design["replay_noise_seeds"]] for method in design["replay_methods"]]
    check("complete_conditional_design", len(summary["fits"]) == len(labels) and {r["label"] for r in summary["fits"]} == labels
          and contract["methods"] == methods and contract["cases"] == cases and contract["conditional_fit_count"] == len(labels))
    check("fixed_replay_design", contract["replay_labels"] == replays and [r["label"] for r in summary["replays"]] == replays
          and contract["full_ODE_replayed_methods_are_fixed_not_rank_selected"] and summary["new_ODE_replay_count"] == 2*len(replays))
    check("metric_coverage", len(table) == len(replays)*2*115 and not table.duplicated(["label", "period", "kind", "name"]).any())
    curves_by_case = {}
    noise_lineage = {"paired_within_sparse_methods": True, "dense_sparse_draws_are_matched": False,
        "known_synthetic_CV": design["noise_coefficient_of_variation"], "shared_parent_sparse_seeds": [],
        "new_sparse_seeds": [57721, 104729],
        "partition_receipt_noise_flag_is_inherited_helper_metadata_not_final_lineage": True}
    variance = np.log1p(design["noise_coefficient_of_variation"]**2)
    for case in cases:
        frame = pd.read_csv(out / "datasets" / case / "observations.csv", float_precision="round_trip")
        values = frame[list(POOLS)].to_numpy().T
        expected = clean.copy()
        if case != "clean":
            seed = int(case.split("_")[1])
            expected[:, 1:] *= np.exp(np.random.default_rng(seed).normal(size=(4, 6))*np.sqrt(variance)-.5*variance)
        check(f"paired_training_data:{case}", np.array_equal(frame.time_day, TIMES) and np.array_equal(values, expected)
              and np.array_equal(values[:, 0], clean[:, 0]) and np.all(values > 0))
        if case in {"noise_2718", "noise_31415", "noise_1618"}:
            old = pd.read_csv(parent / "datasets" / case.replace("noise_", "sparse_noisy_") / "observations.csv", float_precision="round_trip")
            check(f"parent_sparse_noise_reproduction:{case}", np.array_equal(values, old[list(POOLS)].to_numpy().T))
            noise_lineage["shared_parent_sparse_seeds"].append({"seed": seed,
                "regenerated_values_identical_to_parent": bool(np.array_equal(values, old[list(POOLS)].to_numpy().T))})
        curves_by_case[case] = {}
        for mode in ("raw", "smooth"):
            receipt = read_json(out / "datasets" / case / f"{mode}_curve_receipt.json")
            check(f"curve_scope:{case}:{mode}", receipt["training_interval"] == [1., 22.]
                  and receipt["initial_anchor_is_exact_constrained_spline_optimum"] is False
                  and receipt["smoothing_selection"] == ("GCV_training_only" if mode == "smooth" else "none"))
            curves = []
            for i, item in enumerate(receipt["coefficient_receipts"]):
                if mode == "raw":
                    curve = PchipInterpolator(TIMES, values[i], extrapolate=False)
                    good = np.array_equal(curve.x, item["breaks"]) and np.array_equal(curve.c, item["coefficients"])
                else:
                    logs = np.log(values[i])
                    if case != "clean":
                        logs[1:] += .5*variance
                    curve = scipy.interpolate.make_smoothing_spline(TIMES, logs, lam=None)
                    shift = float(np.log(values[i, 0])-curve(TIMES[0]))
                    good = np.array_equal(curve.t, item["knots"]) and np.array_equal(curve.c, item["coefficients"])
                    good = good and abs(shift-receipt["log_anchor_shifts"][i]) < 1e-12 and item["degree"] == curve.k
                check(f"curve_coefficients:{case}:{mode}:{POOLS[i]}", good)
                curves.append(curve)
            curves_by_case[case][mode] = (curves, receipt["log_anchor_shifts"], values)
    (out / "verified_noise_lineage.json").write_text(json.dumps(noise_lineage, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    maximum_fit, maximum_metric = 0., 0.
    for row in summary["fits"]:
        label, method = row["label"], row["method"]
        data = np.load(out / "fits" / label / "training_problem.npz")
        basis, targets, weights, grid = [data[key] for key in ("basis", "targets", "weights", "grid")]
        estimate = analytic_fit(basis, targets, weights, low, high)
        error = float(np.max(np.abs(estimate-row["capacities"])))
        maximum_fit = max(maximum_fit, error)
        fit = read_json(out / "fits" / label / "conditional_recovery.json")
        check(f"analytic_fit:{label}", error < 1e-6 and row["capacities"] == fit["capacities"]
              and fit["global_identifiability_established"] is False and len(fit["starts"]) == 3
              and np.allclose(row["relative_parameter_error"], np.abs(np.asarray(row["capacities"])/truth_capacities-1), atol=1e-14), error)
        mode = "smooth" if method.startswith("smooth") else "raw"
        curves, shifts, observations = curves_by_case[row["case"]][mode]
        integral = method in {"raw_integrated", "smoothed_inputs_integrated"}
        if integral:
            nodes, local_weights = np.polynomial.legendre.leggauss(16)
            half = np.diff(TIMES)/2
            query = (((TIMES[:-1]+TIMES[1:])/2)[:, None]+half[:, None]*nodes).ravel()
            check(f"raw_interval_targets:{label}", np.array_equal(targets, np.asarray([-1., 1.])[:, None]*np.diff(observations[:2], axis=1))
                  and np.array_equal(weights, np.ones(6)) and np.array_equal(grid, (TIMES[:-1]+TIMES[1:])/2))
        else:
            if "uniform" in method or method == "legacy_raw401":
                count = 401 if method == "legacy_raw401" else int(method.split("uniform")[1])
                expected_grid = np.linspace(1., 22., count)
                expected_weights = np.full(count, 21./(count-1))
                expected_weights[[0, -1]] *= .5
                if method == "legacy_raw401":
                    expected_weights[:] = 1.
                selected = np.asarray([0, count//2, count-1])
            else:
                order = int(method.split("aligned")[1])
                nodes, local_weights = np.polynomial.legendre.leggauss(order)
                half = np.diff(TIMES)/2
                expected_grid = (((TIMES[:-1]+TIMES[1:])/2)[:, None]+half[:, None]*nodes).ravel()
                expected_weights = (half[:, None]*local_weights).ravel()
                selected = np.arange(len(grid))
            check(f"grid_weights:{label}", np.array_equal(grid, expected_grid) and np.array_equal(weights, expected_weights))
            query = grid[selected]
        values = np.asarray([c(query) for c in curves])
        derivatives = np.asarray([c.derivative()(query) for c in curves])
        if mode == "smooth":
            values = np.exp(values+np.asarray(shifts)[:, None])
            derivatives *= values
        states = np.repeat(initial[:, None], len(query), axis=1)
        for pool, values_row in zip(POOLS, values):
            states[BRODBAR_METABOLITE_MAP[pool]] = values_row
        full_basis = unit_capacity_basis(query, states, baseline, ode)
        if integral:
            expected_basis = np.sum(full_basis.reshape(2, 6, 16)*local_weights[None, None, :]*half[None, :, None], axis=2)
            parity = np.allclose(basis, expected_basis, rtol=1e-12, atol=1e-12)
        else:
            parity = np.allclose(basis[:, selected], full_basis, rtol=1e-12, atol=1e-12)
            parity = parity and np.allclose(targets[:, selected], np.asarray([-1., 1.])[:, None]*derivatives[:2], rtol=1e-12, atol=1e-12)
        check(f"executed_problem_parity:{label}", parity)
        if method == "legacy_raw401" and row["case"] in {"clean", "noise_2718", "noise_31415", "noise_1618"}:
            old_label = "sparse_clean_pointwise" if row["case"] == "clean" else row["case"].replace("noise_", "sparse_noisy_")+"_pointwise"
            old = read_json(parent / old_label / "learned_synthetic_parameters.json")
            check(f"parent_legacy_fit:{label}", np.max(np.abs(np.asarray(row["capacities"])-[old[p] for p in PARAMETERS])) < 1e-6)
    for row in summary["aggregated_noise_results"]:
        group = [r for r in summary["fits"] if r["case"] != "clean" and r["method"] == row["method"]]
        errors = np.asarray([r["relative_parameter_error"] for r in group])
        check(f"noise_aggregate:{row['method']}", row["noise_seed_count"] == 5
              and np.array_equal(row["median_relative_parameter_error"], np.median(errors, axis=0))
              and np.array_equal(row["maximum_relative_parameter_error"], errors.max(axis=0))
              and row["bound_case_count"] == sum(r["at_bound"] for r in group))
    for row in read_json(out / "aligned_capacity_convergence.json"):
        pair = [next(r for r in summary["fits"] if r["case"] == row["case"] and r["method"] == f"{row['mode']}_aligned{order}") for order in (4, 8)]
        delta = np.abs(np.asarray(pair[0]["capacities"])/pair[1]["capacities"]-1)
        check(f"capacity_quadrature:{row['case']}:{row['mode']}", np.array_equal(delta, row["capacity_relative_difference"])
              and bool(np.all(delta <= design["capacity_quadrature_relative_tolerance"])) == row["passes_numerical_resolution_check"])
    minimum = float("inf")
    for label in replays:
        directory = out / "replays" / label
        candidate = read_json(directory / "learned_synthetic_parameters.json")
        fit = next(r for r in summary["fits"] if r["label"] == label)
        check(f"kinetic_scope:{label}", candidate.keys() == baseline.keys()
              and all(candidate[key] == value for key, value in baseline.items() if key not in PARAMETERS)
              and all(candidate[p] == fit["capacities"][i] for i, p in enumerate(PARAMETERS)))
        evaluation = np.load(directory / "evaluation.npz")
        minimum = min(minimum, float(np.min(evaluation["states"][:113])))
        check(f"evaluation_scope:{label}", np.array_equal(evaluation["time"], truth["time"])
              and np.all(np.isfinite(evaluation["states"])) and np.min(evaluation["states"][:113]) >= 0)
        audit = read_json(directory / "numerical_audit.json")
        convergence = pd.read_csv(directory / "solver_convergence.csv")
        check(f"numerical_audit:{label}", audit["passes"] and audit["negative_accepted_count"] == 0
              and audit["minimum_raw_checked_concentration_mM"] >= 0 and audit["max_executed_balance_closure_mM_per_day"] <= 1e-10
              and len(convergence) == 114 and convergence.strict_ultrastrict_pass.all())
        for solver in ("strict", "ultrastrict"):
            raw = np.load(directory / f"{solver}_accepted_states.npz")
            minimum = min(minimum, float(np.min(raw["states"][:113])))
            check(f"raw_ODE:{label}:{solver}", np.array_equal(raw["states"][:, 0], initial)
                  and np.all(np.isfinite(raw["states"])) and np.min(raw["states"][:113]) >= 0
                  and raw["time"][0] == 1. and raw["time"][-1] == 46. and np.all(np.diff(raw["time"]) > 0))
        sample = np.asarray([0, len(truth["time"])//2, len(truth["time"])-1])
        rates = executed_transport(truth["time"][sample], evaluation["states"][:, sample], candidate, ode)
        check(f"executed_replay_rates:{label}", all(np.allclose(rates[key], evaluation[saved][:, sample], rtol=1e-12, atol=1e-12)
              for key, saved in (("native", "native_flux"), ("effective", "effective_flux"), ("factors", "availability_factors"))))
        for period in ("training", "holdout"):
            mask = truth["time"] <= 22. if period == "training" else truth["time"] > 22.
            for flux, kind, pool_names in ((False, "concentration", names[:113]), (True, "executed_flux", REACTIONS)):
                actual = evaluation["effective_flux"][:, mask] if flux else evaluation["states"][:113, mask]
                reference = truth["effective"][:, mask] if flux else truth["states"][:113, mask]
                expected = independent_metrics(actual, reference, flux=flux)
                for i, pool in enumerate(pool_names):
                    saved = table[(table.label == label) & (table.period == period) & (table.kind == kind) & (table.name == pool)]
                    if len(saved) != 1:
                        raise ValueError(f"missing or duplicated metric {label}:{period}:{pool}")
                    for key, values in expected.items():
                        if values is not None:
                            maximum_metric = max(maximum_metric, abs(float(saved[key].iloc[0])-values[i]))
    check("independent_metrics", maximum_metric < 1e-12, float(maximum_metric))
    qa = None
    if (out / "qa_results.xml").exists():
        suites = list(ET.parse(out / "qa_results.xml").getroot().iter("testsuite"))
        qa = {key: sum(int(s.get(key, 0)) for s in suites) for key in ("tests", "failures", "errors", "skipped")}
        qa["passes"] = qa["tests"] > 0 and qa["failures"] == qa["errors"] == 0
        check("QA", qa["passes"])
    report = {"independent_checks_pass": all(r["passes"] for r in checks), "check_count": len(checks), "checks": checks,
        "max_closed_form_capacity_difference": maximum_fit, "max_metric_difference": float(maximum_metric),
        "minimum_independently_checked_concentration_mM": minimum, "biological_readiness_status": readiness["status"],
        "current_environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__, "pandas": pd.__version__},
        "scope": "all sparse aligned/interval training nodes; sampled uniform nodes; all archived metrics and raw accepted concentrations"}
    (out / "independent_verification.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    if not report["independent_checks_pass"]:
        raise ValueError("independent sparse comparison checks failed")
    final = read_json(out / "final_verification.json")
    final.update(independently_verified_at=datetime.now(timezone.utc).isoformat(), independent_archive_checks_pass=True,
        independent_archive_check_count=len(checks), qa=qa,
        supporting_code_sha256={str(p): sha256(p) for p in (Path(__file__), ROOT / "scripts/verify_fla_teacher_resolution.py",
            ROOT / "qa/test_fla_sparse_teacher_resolution.py", ROOT / "scripts/plot_fla_sparse_teacher_diagnostics.py")},
        output_sha256={str(p.relative_to(out)): sha256(p) for p in out.rglob("*") if p.is_file()
            and p.name not in {"final_verification.json", "independent_verification.json"}})
    (out / "final_verification.json").write_text(json.dumps(final, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "output/fla_sparse_teacher_resolution_2026_10_05")
    result = verify(parser.parse_args().out.resolve())
    print(json.dumps({key: value for key, value in result.items() if key != "checks"}))
