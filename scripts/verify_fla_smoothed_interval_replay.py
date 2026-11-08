"""Independent scope, lineage, raw-state, flux and metric checks for fixed replay."""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from fla_precalibration_readiness import evaluate_readiness
from fla_synthetic_recovery import executed_transport
from fla_working_reference import load_working_reference, reference_options
from run_fla_sparse_teacher_resolution import verify_archive_inputs
from run_fla_synthetic_recovery import write_json
from verify_fla_teacher_resolution import analytic_fit, independent_metrics, read_json, sha256

METHODS = ["raw_integrated", "smoothed_inputs_integrated"]
CASES = ["clean", "noise_2718", "noise_31415", "noise_1618", "noise_57721", "noise_104729"]
PARAMETERS = ("vmax_VEGLC", "vmax_VELAC")
REACTIONS = ("VEGLC", "VELAC")


def dense_anchor_matches(actual, initial):
    actual, initial = np.asarray(actual), np.asarray(initial)
    if actual.shape != initial.shape or not np.all(np.isfinite(actual)):
        return False
    # BDF dense polynomials may differ from their exact accepted anchor by roundoff.
    allowed = 8*np.finfo(float).eps*np.maximum(1., np.abs(initial))
    return bool(np.all(np.abs(actual-initial) <= allowed))


def verify(out):
    contract, summary = read_json(out / "preregistered_contract.json"), read_json(out / "summary.json")
    parent = ROOT / contract["design"]["parent_archive"]
    parent_contract = verify_archive_inputs(parent)
    truth_parent = ROOT / parent_contract["design"]["parent_archive"]
    truth = np.load(truth_parent / "truth/evaluation.npz")
    frozen = np.load(out / "frozen_initial_state.npz")
    initial, names = frozen["states"], list(frozen["names"])
    baseline = read_json(parent / "frozen_parameters.json")
    table = pd.read_csv(out / "full_pool_replay_metrics.csv", float_precision="round_trip")
    paired = pd.read_csv(out / "paired_metrics.csv", float_precision="round_trip")
    aggregate = pd.read_csv(out / "five_seed_summary.csv", float_precision="round_trip")
    working = contract["working_reference"]
    ode, _ = reference_options(working)
    checks = []

    def check(name, passed, detail=None):
        checks.append({"name": name, "passes": bool(passed), "detail": detail})

    for path, digest in contract["input_sha256"].items():
        check(f"input_sha256:{path}", sha256(Path(path)) == digest)
    check("reference_frozen", working == parent_contract["working_reference"] == load_working_reference())
    check("synthetic_scope", contract["contract_type"] == "synthetic_fixed_capacity_smoothed_interval_free_ODE_validation"
          and contract["synthetic_only"] is True and contract["truth_used_only_for_evaluation"] is True
          and contract["prediction_does_not_receive_smoothed_inputs"] is True
          and contract["raw_signed_observation_increments_unchanged"] is True
          and contract["biological_calibration_allowed"] is False and contract["global_model_promotion_allowed"] is False
          and all(contract["design"][key] is False for key in ("teacher_forcing", "observation_reset", "raw_state_output_clipping"))
          and summary["biological_calibration_allowed"] is False and summary["global_model_promotion_allowed"] is False)
    check("frozen_context", sha256(out / "frozen_initial_state.npz") == sha256(parent / "frozen_initial_state.npz")
          and read_json(out / "frozen_parameters.json") == baseline and len(names) == 114 and initial.shape == (114,))
    labels = [f"{case}_{method}" for case in CASES for method in METHODS]
    check("complete_predeclared_design", [r["label"] for r in contract["replay_plan"]] == labels
          and [r["label"] for r in summary["replays"]] == labels and summary["replayed_pair_count"] == 12
          and summary["new_fit_count"] == contract["new_fit_count"] == 0
          and contract["planned_new_integrations"] == summary["new_ODE_integration_count"] == 16
          and contract["planned_reused_integrations"] == summary["reused_ODE_integration_count"] == 8
          and contract["planned_total_integrations"] == summary["total_ODE_integration_count"] == 24)
    readiness = evaluate_readiness(read_json(ROOT / "config/fla_adenylate_redox_readiness.json"), root=ROOT,
        frozen_initial_redox=[initial[names.index(pool)] for pool in ("NAD", "NADH")])
    protocol = read_json(ROOT / "output/adenylate_redox_readiness_2026_10_05_v2/coupled_sensitivity_protocol.json")
    check("biological_guard_unchanged", len(readiness["blockers"]) == 13 and not readiness["scientific_contract_complete"]
          and not readiness["optimization_allowed"] and protocol["execution_authorized"] is False)
    receipts = read_json(out / "reuse_receipts.json")
    check("reuse_coverage", len(receipts) == 24 and {r["label"] for r in receipts} == {f"{case}_raw_integrated" for case in CASES[:4]}
          and len({(r["label"], r["file"]) for r in receipts}) == 24)
    for receipt in receipts:
        check(f"copied_replay:{receipt['label']}:{receipt['file']}", sha256(Path(receipt["source"])) == receipt["sha256"]
              == sha256(out / "replays" / receipt["label"] / receipt["file"]))
    check("full_metric_coverage", len(table) == 2760 and set(table.label) == set(labels)
          and not table.duplicated(["label", "period", "kind", "name"]).any())
    check("paired_coverage", len(paired) == 1380 and not paired.duplicated(["case", "period", "kind", "name"]).any()
          and len(aggregate) == 230 and not aggregate.duplicated(["period", "kind", "name"]).any())
    sealed_fits = {row["label"]: row for row in read_json(parent / "conditional_results.json")}
    source_design = parent_contract["parent_design"]
    base = np.asarray([baseline[p] for p in PARAMETERS])
    low, high = base*source_design["search_multiplier_bounds"][0], base*source_design["search_multiplier_bounds"][1]
    maximum_metric, minimum, maximum_fit = 0., float("inf"), 0.
    integrated_rows = []
    for row in summary["replays"]:
        label = row["label"]
        sealed = sealed_fits[label]
        check(f"sealed_capacities:{label}", all(row[key] == sealed[key] for key in sealed)
              and row["replay_source"] == ("reused" if row["case"] in CASES[:4] and row["method"] == METHODS[0] else "new"))
        data = pd.read_csv(parent / "datasets" / row["case"] / "observations.csv", float_precision="round_trip")
        problem = np.load(parent / "fits" / label / "training_problem.npz")
        expected_targets = np.asarray([-1., 1.])[:, None]*np.diff(data[["EGLC", "ELAC"]].to_numpy().T, axis=1)
        check(f"raw_increment_targets:{label}", np.array_equal(data.time_day, [1, 4, 8, 11, 15, 18, 22])
              and np.array_equal(expected_targets, problem["targets"]) and problem["basis"].shape == (2, 6))
        expected_fit = analytic_fit(problem["basis"], problem["targets"], problem["weights"], low, high)
        difference = float(np.max(np.abs(expected_fit-row["capacities"])))
        maximum_fit = max(maximum_fit, difference)
        check(f"closed_form_capacity:{label}", difference < 1e-8)
        directory = out / "replays" / label
        candidate = read_json(directory / "learned_synthetic_parameters.json")
        check(f"kinetic_scope:{label}", candidate.keys() == baseline.keys()
              and all(candidate[key] == value for key, value in baseline.items() if key not in PARAMETERS)
              and all(candidate[p] == row["capacities"][i] for i, p in enumerate(PARAMETERS)))
        evaluation = np.load(directory / "evaluation.npz")
        minimum = min(minimum, float(np.min(evaluation["states"][:113])))
        check(f"evaluation_scope:{label}", np.array_equal(evaluation["time"], truth["time"])
              and evaluation["states"].shape == truth["states"].shape
              and dense_anchor_matches(evaluation["states"][:, 0], initial)
              and np.all(np.isfinite(evaluation["states"])) and np.min(evaluation["states"][:113]) >= 0)
        raw_solvers = {}
        for solver in ("strict", "ultrastrict"):
            raw = np.load(directory / f"{solver}_accepted_states.npz")
            raw_solvers[solver] = raw
            minimum = min(minimum, float(np.min(raw["states"][:113])))
            check(f"raw_ODE:{label}:{solver}", np.array_equal(raw["states"][:, 0], initial)
                  and np.all(np.isfinite(raw["states"])) and np.min(raw["states"][:113]) >= 0
                  and raw["time"][0] == 1. and raw["time"][-1] == 46. and np.all(np.diff(raw["time"]) > 0))
        strict, ultra = [raw_solvers[s]["states"][:, -1] for s in ("strict", "ultrastrict")]
        controls = working["validation_before_calibration"]
        allowed = controls["comparison_atol_mM"] + controls["comparison_rtol"]*np.maximum(np.abs(strict), np.abs(ultra))
        check(f"independent_endpoint_convergence:{label}", np.all(np.abs(strict-ultra) <= allowed)
              and np.allclose(ultra, evaluation["states"][:, -1], rtol=1e-12, atol=1e-12))
        audit = read_json(directory / "numerical_audit.json")
        convergence = pd.read_csv(directory / "solver_convergence.csv")
        check(f"numerical_receipt:{label}", audit == row["numerical_checks"] and audit["passes"]
              and audit["negative_accepted_count"] == 0 and audit["minimum_raw_checked_concentration_mM"] >= 0
              and audit["max_executed_balance_closure_mM_per_day"] <= controls["closure_tolerance_mM_per_day"]
              and len(convergence) == 114 and convergence.pool.tolist() == names and convergence.strict_ultrastrict_pass.all())
        sample = np.unique(np.r_[0, np.linspace(0, len(truth["time"])-1, 13, dtype=int), len(truth["time"])-1])
        rates = executed_transport(truth["time"][sample], evaluation["states"][:, sample], candidate, ode)
        check(f"actual_kernel_fluxes:{label}", all(np.allclose(rates[key], evaluation[saved][:, sample], rtol=1e-12, atol=1e-12)
              for key, saved in (("native", "native_flux"), ("effective", "effective_flux"), ("factors", "availability_factors")))
              and np.max(rates["closure"]) <= controls["closure_tolerance_mM_per_day"])
        # Executed extracellular balances identify the net transport integrals exactly.
        # This endpoint identity is not an independent quadrature of the stored rate grid.
        cuts = np.asarray([1., 4., 8., 11., 15., 18., 22., 46.])
        positions = [np.flatnonzero(truth["time"] == day) for day in cuts]
        check(f"exact_integral_boundaries:{label}", all(len(position) == 1 for position in positions))
        positions = np.asarray([position[0] for position in positions])
        for i, (reaction, pool, sign) in enumerate(zip(REACTIONS, ("EGLC", "ELAC"), (-1., 1.))):
            predicted = sign*np.diff(evaluation["states"][names.index(pool), positions])
            reference = sign*np.diff(truth["states"][names.index(pool), positions])
            for j in range(7):
                integrated_rows.append({"label": label, "case": row["case"], "method": row["method"],
                    "reaction": reaction, "start_day": cuts[j], "end_day": cuts[j+1],
                    "period": "training" if j < 6 else "holdout", "predicted_integral_mM": predicted[j],
                    "truth_integral_mM": reference[j], "signed_integral_error_mM": predicted[j]-reference[j],
                    "raw_observed_teacher_integral_mM": float(expected_targets[i, j]) if j < 6 else None,
                    "integral_source": "executed_balance_identity_not_independent_quadrature"})
        for period in ("training", "holdout"):
            mask = truth["time"] <= 22. if period == "training" else truth["time"] > 22.
            for flux, kind, pool_names in ((False, "concentration", names[:113]), (True, "executed_flux", REACTIONS)):
                actual = evaluation["effective_flux"][:, mask] if flux else evaluation["states"][:113, mask]
                reference = truth["effective"][:, mask] if flux else truth["states"][:113, mask]
                expected = independent_metrics(actual, reference, flux=flux)
                saved = table[(table.label == label) & (table.period == period) & (table.kind == kind)].set_index("name").loc[list(pool_names)]
                for key, values in expected.items():
                    if values is not None:
                        maximum_metric = max(maximum_metric, float(np.max(np.abs(saved[key].to_numpy()-values))))
                check(f"independent_metrics:{label}:{period}:{kind}", maximum_metric < 1e-12)
    # Recompute paired and five-seed summaries from the independently checked metric table.
    for case in CASES:
        for period in ("training", "holdout"):
            subset = paired[(paired.case == case) & (paired.period == period)]
            for _, pair in subset.iterrows():
                group = table[(table.period == period) & (table.kind == pair.kind) & (table.name == pair["name"])]
                raw = group[group.label == f"{case}_{METHODS[0]}"].iloc[0]
                smooth = group[group.label == f"{case}_{METHODS[1]}"].iloc[0]
                key = "mean_nrmse" if pair.kind == "executed_flux" else "excursion_nrmse"
                expected = [raw[key], smooth[key], smooth[key]-raw[key], raw.mean_nrmse, smooth.mean_nrmse, raw.last_error, smooth.last_error]
                saved = [pair.raw_error, pair.smoothed_error, pair.smoothed_minus_raw, pair.raw_mean_nrmse,
                         pair.smoothed_mean_nrmse, pair.raw_endpoint_error, pair.smoothed_endpoint_error]
                maximum_metric = max(maximum_metric, float(np.max(np.abs(np.asarray(expected)-saved))))
            check(f"independent_paired_metrics:{case}:{period}", len(subset) == 115 and maximum_metric < 1e-12)
    for _, row in aggregate.iterrows():
        group = paired[(paired.case != "clean") & (paired.period == row.period) & (paired.kind == row.kind) & (paired.name == row["name"])]
        expected = [group.raw_error.median(), group.smoothed_error.median(), group.raw_error.max(), group.smoothed_error.max(),
                    group.smoothed_minus_raw.median(), group.raw_mean_nrmse.max(), group.smoothed_mean_nrmse.max()]
        saved = [row.raw_median, row.smoothed_median, row.raw_maximum, row.smoothed_maximum,
                 row.median_paired_difference, row.raw_mean_nrmse_maximum, row.smoothed_mean_nrmse_maximum]
        check(f"five_seed_aggregate:{row.period}:{row.kind}:{row['name']}", len(group) == row.noise_seed_count == 5
              and row.smoothed_better_seed_count == int((group.smoothed_minus_raw < 0).sum())
              and np.max(np.abs(np.asarray(expected)-saved)) < 1e-12)
    suites = list(ET.parse(out / "qa_results.xml").getroot().iter("testsuite"))
    qa = {key: sum(int(s.get(key, 0)) for s in suites) for key in ("tests", "failures", "errors", "skipped")}
    check("QA", qa["tests"] > 0 and qa["failures"] == qa["errors"] == qa["skipped"] == 0)
    pd.DataFrame(integrated_rows).to_csv(out / "executed_balance_integrals.csv", index=False)
    check("integrated_transport_coverage", len(integrated_rows) == 168)
    report = {"independent_checks_pass": all(r["passes"] for r in checks), "check_count": len(checks), "checks": checks,
              "max_metric_difference": maximum_metric, "max_closed_form_capacity_difference": maximum_fit,
              "minimum_independently_checked_concentration_mM": minimum, "biological_readiness_status": readiness["status"],
              "scope": "all raw accepted and archived dense concentrations; all metrics; endpoints independently cross-checked; 13 full-kernel flux nodes per pair",
              "dense_convergence_scope": "114-pool dense strict/ultrastrict audit receipts; independent endpoint checks (not a new dense interpolant reconstruction)"}
    write_json(out / "independent_verification.json", report)
    if not report["independent_checks_pass"]:
        raise ValueError("independent fixed-replay validation failed")
    final = read_json(out / "final_verification.json")
    final.update(independently_verified_at=datetime.now(timezone.utc).isoformat(), independent_archive_checks_pass=True,
        independent_archive_check_count=len(checks), qa=qa,
        supporting_code_sha256={str(p): sha256(p) for p in (Path(__file__), ROOT / "qa/test_fla_smoothed_interval_replay.py",
            ROOT / "scripts/verify_fla_teacher_resolution.py")},
        output_sha256={str(p.relative_to(out)): sha256(p) for p in out.rglob("*") if p.is_file()
            and p.name not in {"final_verification.json", "independent_verification.json"}})
    write_json(out / "final_verification.json", final)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "output/fla_smoothed_interval_replay_2026_10_05")
    result = verify(parser.parse_args().out.resolve())
    print({key: value for key, value in result.items() if key != "checks"})
