"""Independently verify archived synthetic fits, scope, noise and all-pool metrics."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from equadiff_brodbar import BRODBAR_METABOLITE_MAP


def verify(out):
    contract = json.loads((out / "preregistered_contract.json").read_text())
    summary = json.loads((out / "summary.json").read_text())
    design = contract["design"]
    parameters = tuple(design["parameters"])
    source = ROOT / contract["working_reference"]["fixed_context"]
    baseline = json.loads((source / "fixed_parameters.json").read_text())
    initial = np.load(out / "frozen_initial_state.npz")["states"]
    truth_params = json.loads((out / "synthetic_truth_parameters.json").read_text())
    truth = np.load(out / "truth/evaluation.npz")
    table = pd.read_csv(out / "trajectory_and_flux_metrics.csv", float_precision="round_trip")
    base = np.asarray([baseline[p] for p in parameters])
    low, high = base * design["search_multiplier_bounds"][0], base * design["search_multiplier_bounds"][1]
    truth_values = base * design["truth_multipliers"]
    checks, absolute_metrics = [], []

    def check(name, passed, detail=None):
        checks.append({"name": name, "passes": bool(passed), "detail": detail})

    check("synthetic_only", not summary["biological_calibration_allowed"] and not summary["global_model_promotion_allowed"]
          and not contract["real_concentrations_used_as_training_targets"])
    check("input_hashes", all(hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest for path, digest in contract["input_sha256"].items()))
    check("truth_scope", all(truth_params[key] == value for key, value in baseline.items() if key not in parameters)
          and all(truth_params[p] == truth_values[i] for i, p in enumerate(parameters)))
    check("full_pool_metric_coverage", len(table) == summary["fit_count"] * 2 * 115)
    clean_observations = {}
    noise_checks = []
    for directory in sorted((out / "datasets").iterdir()):
        frame = pd.read_csv(directory / "observations.csv", float_precision="round_trip")
        check(f"training_only:{directory.name}", frame.time_day.max() <= design["training_end_day"] and frame.time_day.min() == 1.)
        columns = ["EGLC", "ELAC", "GLC", "LAC"]
        if "clean" in directory.name:
            clean_observations[directory.name.split("_")[0]] = frame[columns].to_numpy().T
    for directory in sorted((out / "datasets").iterdir()):
        if "noisy" not in directory.name:
            continue
        frame = pd.read_csv(directory / "observations.csv", float_precision="round_trip")
        seed = int(directory.name.rsplit("_", 1)[1])
        clean = clean_observations[directory.name.split("_")[0]]
        logvar = np.log1p(design["noise_coefficient_of_variation"]**2)
        expected = clean.copy()
        expected[:, 1:] *= np.exp(np.random.default_rng(seed).normal(size=(4, clean.shape[1]-1))*np.sqrt(logvar)-.5*logvar)
        actual = frame[["EGLC", "ELAC", "GLC", "LAC"]].to_numpy().T
        passed = np.allclose(expected, actual, rtol=1e-13, atol=1e-14)
        check(f"noise_receipt:{directory.name}", passed)
        noise_checks.append(passed)
    maximum_fit_error, maximum_metric_error = 0., 0.
    for row in summary["results"]:
        label = row["label"]
        directory = out / label
        fitted = json.loads((directory / "learned_synthetic_parameters.json").read_text())
        check(f"kinetic_scope:{label}", all(fitted[key] == value for key, value in baseline.items() if key not in parameters))
        check(f"capacity_bounds:{label}", all(low[i] <= fitted[p] <= high[i] for i, p in enumerate(parameters)))
        if row["case"] != "oracle":
            reconstructed = np.load(out / "datasets" / row["case"] / "reconstructed_training.npz")
            basis = reconstructed["basis" if row["method"] == "pointwise" else "integrated_basis"]
            targets = reconstructed["targets" if row["method"] == "pointwise" else "integral_targets"]
            denominator = np.sum(basis**2, axis=1)
            if np.any(denominator <= 0):
                raise ValueError("closed-form verification needs excited capacities")
            analytic = np.clip(np.sum(basis*targets, axis=1)/denominator, low, high)
            error = float(np.max(np.abs(np.asarray(row["learned_capacities"]) - analytic)))
            maximum_fit_error = max(maximum_fit_error, error)
            check(f"independent_closed_form_fit:{label}", error < 1e-6, error)
        learned = np.load(directory / "evaluation.npz")
        check(f"aligned_evaluation:{label}", np.array_equal(learned["time"], truth["time"]))
        for solver in ("strict", "ultrastrict"):
            archive = np.load(directory / f"{solver}_accepted_states.npz")
            check(f"raw_replay:{label}:{solver}", np.array_equal(archive["states"][:, 0], initial)
                  and np.all(np.isfinite(archive["states"])) and np.min(archive["states"][:113]) >= 0.
                  and archive["time"][0] == 1. and archive["time"][-1] == 46. and np.all(np.diff(archive["time"]) > 0))
        for period in ("training", "holdout"):
            mask = truth["time"] <= design["training_end_day"] if period == "training" else truth["time"] > design["training_end_day"]
            values = truth["states"][:113, mask]
            errors = np.sqrt(np.mean((learned["states"][:113, mask]-values)**2, axis=1)) / np.maximum(np.ptp(values, axis=1), .001)
            expected = table[(table.label == label) & (table.period == period) & (table.kind == "concentration")]
            for pool, index in BRODBAR_METABOLITE_MAP.items():
                if index >= 113:
                    continue
                rows = expected[expected.name == pool]
                if len(rows) != 1:
                    raise ValueError(f"missing or duplicated pool metric: {label}:{period}:{pool}")
                maximum_metric_error = max(maximum_metric_error, abs(float(rows.normalized_rmse.iloc[0])-errors[index]))
                rmse = float(np.sqrt(np.mean((learned["states"][index, mask]-values[index])**2)))
                mean = float(np.mean(np.abs(values[index])))
                excursion = float(np.ptp(values[index]))
                absolute_metrics.append({"label": label, "period": period, "pool": pool,
                    "absolute_rmse_mM": rmse, "truth_mean_mM": mean, "truth_excursion_mM": excursion,
                    "excursion_scale_floor_active": excursion < .001,
                    "excursion_normalized_rmse": float(errors[index]), "mean_normalized_rmse": rmse / max(mean, .001),
                    "signed_last_evaluated_error_mM": float(learned["states"][index, mask][-1] - values[index, -1])})
            flux_truth = truth["effective"][:, mask]
            fluxerrors = np.sqrt(np.mean((learned["effective_flux"][:, mask]-flux_truth)**2, axis=1)) / np.maximum(np.sqrt(np.mean(flux_truth**2, axis=1)), 1e-6)
            for i, reaction in enumerate(("VEGLC", "VELAC")):
                rows = table[(table.label == label) & (table.period == period) & (table.kind == "executed_flux") & (table.name == reaction)]
                if len(rows) != 1:
                    raise ValueError("missing or duplicated flux metric")
                maximum_metric_error = max(maximum_metric_error, abs(float(rows.normalized_rmse.iloc[0])-fluxerrors[i]))
    check("independent_all_pool_and_flux_metrics", maximum_metric_error < 1e-12, float(maximum_metric_error))
    pd.DataFrame(absolute_metrics).to_csv(out / "absolute_and_relative_concentration_metrics.csv", index=False)
    report = {"independent_checks_pass": all(row["passes"] for row in checks), "check_count": len(checks),
              "max_closed_form_capacity_difference": maximum_fit_error, "max_metric_difference": float(maximum_metric_error),
              "absolute_metric_row_count": len(absolute_metrics),
              "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "checks": checks}
    (out / "independent_verification.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if not report["independent_checks_pass"]:
        raise ValueError("independent benchmark verification failed")
    qa = None
    if (out / "qa_results.xml").exists():
        suites = list(ET.parse(out / "qa_results.xml").getroot().iter("testsuite"))
        qa = {key: sum(int(suite.get(key, 0)) for suite in suites) for key in ("tests", "failures", "errors", "skipped")}
        qa["passes"] = bool(qa["tests"] > 0 and qa["failures"] == 0 and qa["errors"] == 0)
    final = json.loads((out / "final_verification.json").read_text())
    final.update(independently_verified_at=datetime.now(timezone.utc).isoformat(),
                 independent_archive_checks_pass=True, independent_archive_check_count=report["check_count"], qa=qa,
                 supporting_code_sha256={str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in (Path(__file__), ROOT / "qa/test_fla_synthetic_recovery.py")})
    (out / "final_verification.json").write_text(json.dumps(final, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "output/fla_synthetic_recovery_2026_10_05_v2")
    args = parser.parse_args()
    result = verify(args.out.resolve())
    print(json.dumps({key: value for key, value in result.items() if key != "checks"}))
