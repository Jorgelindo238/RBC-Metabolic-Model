"""Run the sealed FLA teacher comparison on the seven synthetic Bordbar times."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from fla_synthetic_recovery import OBSERVED_POOLS, PARAMETERS, REACTIONS, add_synthetic_noise, check_linear_capacity_domain
from fla_teacher_resolution import TrainingCurves, canonical_partition, fast_transport_basis, integrated_problem, method_names, time_grid, validate_design
from fla_working_reference import reference_options
from extracellular_teacher_flux import build_extracellular_teacher_flux_dataset
from run_fla_synthetic_recovery import audit_solutions, file_hash, simulate, write_json
from run_fla_teacher_resolution import fit_method, kernel_parity, load_parent, plot_study, replay_metrics
from finalize_fla_teacher_resolution_figures import run as finalize_figures

DEFAULT_CONFIG = ROOT / "config/fla_sparse_teacher_resolution.json"
DEFAULT_OUT = ROOT / "output/fla_sparse_teacher_resolution_2026_10_05"
SCHEDULE = [1., 4., 8., 11., 15., 18., 22.]


def validate_sparse_design(config):
    if (config.get("purpose") != "synthetic_sparse_teacher_resolution_diagnostic"
            or config.get("sampling_scope") != "seven_Bordbar_training_times_synthetic_concentrations_only"
            or config.get("training_times_day") != SCHEDULE
            or any(isinstance(day, bool) for day in config["training_times_day"])):
        raise ValueError("only the fixed seven-time synthetic schedule is allowed")
    validate_design(dict(config, purpose="synthetic_teacher_resolution_and_smoothing_diagnostic"))
    if any(type(seed) is not int or seed < 0 for seed in config["replay_noise_seeds"]):
        raise ValueError("replay seeds must be integers, not booleans or rounded values")
    return config


def verify_archive_inputs(archive):
    final = json.loads((archive / "final_verification.json").read_text())
    contract = json.loads((archive / "preregistered_contract.json").read_text())
    if not final.get("independent_archive_checks_pass") or final.get("biological_contract_changed") is not False:
        raise ValueError("verified unchanged comparison archive required")
    for path, digest in {**contract["input_sha256"], **final.get("supporting_code_sha256", {})}.items():
        if file_hash(Path(path)) != digest:
            raise ValueError(f"comparison input changed: {path}")
    for relative, digest in final.get("output_sha256", {}).items():
        if file_hash(archive / relative) != digest:
            raise ValueError(f"comparison output changed: {relative}")
    return contract


def load_sparse_context(design):
    parent = ROOT / design["parent_archive"]
    contract, params, initial, names, _, _ = load_parent(parent)
    dense = ROOT / design["dense_comparison_archive"]
    dense_contract = verify_archive_inputs(dense)
    if dense_contract["working_reference"] != contract["working_reference"] or dense_contract["parent_design"] != contract["design"]:
        raise ValueError("dense and sparse controls must share the same truth and context")
    for key in ("noise_seeds", "replay_noise_seeds", "replay_methods", "uniform_grid_counts", "noise_coefficient_of_variation",
                "smoothing", "pointwise_weighting", "aligned_quadrature_orders", "integrated_quadrature_orders"):
        if design[key] != dense_contract["design"][key]:
            raise ValueError(f"sparse continuation changed paired control: {key}")
    frame = pd.read_csv(parent / "datasets/sparse_clean/observations.csv", float_precision="round_trip")
    time, values = frame.time_day.to_numpy(), frame[list(OBSERVED_POOLS)].to_numpy().T
    if not np.array_equal(time, SCHEDULE) or contract["sparse_training_times"] != SCHEDULE:
        raise ValueError("sparse schedule must match the archived source schedule exactly")
    time, values, partition = canonical_partition(time, values)
    if partition["original_count"] != 7 or partition["canonical_count"] != 7:
        raise ValueError("this sparse schedule must not require timestamp aggregation")
    return contract, params, initial, names, time, values, partition


def conditional_case(case, time, values, initial, params, ode, design, parent_design, truth_capacities, out):
    base = np.asarray([params[p] for p in PARAMETERS])
    fits, parity, quadrature = [], [], []
    directory = out / "datasets" / case
    directory.mkdir(parents=True)
    pd.DataFrame({"time_day": time, **dict(zip(OBSERVED_POOLS, values))}).to_csv(directory / "observations.csv", index=False)
    for mode in ("raw", "smooth"):
        curve = TrainingCurves(time, values, training_end=22., mode=mode,
                               noise_cv=0. if case == "clean" else design["noise_coefficient_of_variation"])
        write_json(directory / f"{mode}_curve_receipt.json", curve.receipt())
        parity.append({"case": case, "mode": mode, **kernel_parity(curve, initial, params, ode, design["kernel_parity_absolute_tolerance"])})
        for count in design["uniform_grid_counts"]:
            query, weights, _ = time_grid(time, count=count)
            states, targets = curve.proxy(query, initial)
            basis = fast_transport_basis(query, states, params, ode)["basis"]
            fits.append(fit_method(case, f"{mode}_uniform{count}", basis, targets, weights, query, base, parent_design, truth_capacities, out))
            if mode == "raw" and count == 401:
                teacher = build_extracellular_teacher_flux_dataset(dict(zip(OBSERVED_POOLS, values)), time,
                    metabolite_names=("EGLC", "ELAC"), dense_points=401, dataset_label="sparse_synthetic_legacy_control")
                production = np.asarray([teacher["reaction_flux_curves"][r]["dense_values"] for r in REACTIONS])
                if not np.array_equal(production, targets):
                    raise ValueError("sparse raw teacher differs from production builder")
                fits.append(fit_method(case, "legacy_raw401", basis, targets, np.ones(len(query)), query, base, parent_design, truth_capacities, out))
        for order in design["aligned_quadrature_orders"]:
            query, weights, _ = time_grid(time, order=order)
            states, targets = curve.proxy(query, initial)
            basis = fast_transport_basis(query, states, params, ode)["basis"]
            fits.append(fit_method(case, f"{mode}_aligned{order}", basis, targets, weights, query, base, parent_design, truth_capacities, out))
        coarse, fine = [integrated_problem(curve, initial, params, ode, order=order) for order in design["integrated_quadrature_orders"]]
        error = np.abs(coarse[0]-fine[0])
        passes = bool(np.all(error <= 1e-7+1e-3*np.abs(fine[0])))
        quadrature.append({"case": case, "mode": mode, "integral_order8_order16_pass": passes,
                           "max_integral_basis_difference": float(np.max(error))})
        if not passes:
            raise ValueError("sparse interval quadrature failed; no replay is authorized")
        midpoint = (time[:-1]+time[1:])/2
        name = "raw_integrated" if mode == "raw" else "smoothed_inputs_integrated"
        fits.append(fit_method(case, name, *fine, np.ones(len(midpoint)), midpoint, base, parent_design, truth_capacities, out))
    return fits, parity, quadrature


def run(config_path, out):
    if out.exists():
        raise FileExistsError("fresh output directory required; sealed archives are never overwritten")
    design = validate_sparse_design(json.loads(config_path.read_text()))
    parent_contract, params, initial, names, time, clean, partition = load_sparse_context(design)
    working, parent_design = parent_contract["working_reference"], parent_contract["design"]
    base = np.asarray([params[p] for p in PARAMETERS])
    truth_capacities = base*parent_design["truth_multipliers"]
    check_linear_capacity_domain(params, base, parent_design["search_multiplier_bounds"])
    ode, _ = reference_options(working)
    parent, dense = ROOT / design["parent_archive"], ROOT / design["dense_comparison_archive"]
    cases = ["clean"]+[f"noise_{seed}" for seed in design["noise_seeds"]]
    replay_cases = ["clean"]+[f"noise_{seed}" for seed in design["replay_noise_seeds"]]
    replay_labels = [f"{case}_{method}" for case in replay_cases for method in design["replay_methods"]]
    paths = [config_path, Path(__file__), ROOT / "src/fla_teacher_resolution.py",
             ROOT / "scripts/run_fla_teacher_resolution.py", ROOT / "scripts/finalize_fla_teacher_resolution_figures.py",
             parent / "preregistered_contract.json", parent / "summary.json", parent / "final_verification.json",
             parent / "frozen_initial_state.npz", parent / "truth/evaluation.npz", parent / "datasets/sparse_clean/observations.csv",
             dense / "preregistered_contract.json", dense / "summary.json", dense / "final_verification.json"]
    paths.extend(Path(p) for p in parent_contract["input_sha256"])
    hashes = {str(p.resolve()): file_hash(p) for p in paths}
    contract = {"contract_type": design["purpose"], "created_at": datetime.now(timezone.utc).isoformat(),
        "design": design, "parent_design": parent_design, "working_reference": working, "input_sha256": hashes,
        "cases": cases, "methods": method_names(design), "replay_labels": replay_labels,
        "conditional_fit_count": len(cases)*len(method_names(design)), "planned_ODE_replay_count": 2*len(replay_labels),
        "full_ODE_replayed_methods_are_fixed_not_rank_selected": True, "truth_used_to_select_smoothing_or_grid": False,
        "real_concentrations_used_as_training_targets": False, "teacher_forcing": False, "observation_reset": False,
        "biological_calibration_allowed": False, "global_model_promotion_allowed": False,
        "dense_sparse_noise_draws_are_matched": False, "sparse_parent_noise_draws_reused_bit_for_bit": True}
    out.mkdir(parents=True)
    write_json(out / "preregistered_contract.json", contract)
    write_json(out / "time_partition_receipt.json", partition)
    write_json(out / "frozen_parameters.json", params)
    np.savez_compressed(out / "frozen_initial_state.npz", states=initial, names=np.asarray(names))
    fits, parity, quadrature = [], [], []
    for case in cases:
        print(f"Sparse reconstruction/conditional fits: {case}", flush=True)
        values = clean.copy() if case == "clean" else add_synthetic_noise(clean, cv=design["noise_coefficient_of_variation"], seed=int(case.split("_")[1]))[0]
        result = conditional_case(case, time, values, initial, params, ode, design, parent_design, truth_capacities, out)
        for target, additions in zip((fits, parity, quadrature), result):
            target.extend(additions)
        write_json(out / "partial_fit_results.json", fits)
    if len(fits) != contract["conditional_fit_count"] or len({row["label"] for row in fits}) != len(fits):
        raise ValueError("incomplete sparse method design")
    comparisons = []
    for case in cases:
        for mode in ("raw", "smooth"):
            coarse = next(row for row in fits if row["case"] == case and row["method"] == f"{mode}_aligned4")
            fine = next(row for row in fits if row["case"] == case and row["method"] == f"{mode}_aligned8")
            delta = np.abs(np.asarray(coarse["capacities"])/fine["capacities"]-1)
            comparisons.append({"case": case, "mode": mode, "capacity_relative_difference": delta.tolist(),
                "passes_numerical_resolution_check": bool(np.all(delta <= design["capacity_quadrature_relative_tolerance"]))})
    for filename, data in (("conditional_results.json", fits), ("kernel_parity.json", parity),
                           ("interval_quadrature_checks.json", quadrature), ("aligned_capacity_convergence.json", comparisons)):
        write_json(out / filename, data)
    truth = np.load(parent / "truth/evaluation.npz")
    metrics, replays = [], []
    for number, label in enumerate(replay_labels, 1):
        row = next(row for row in fits if row["label"] == label)
        candidate = dict(params)
        candidate.update(dict(zip(PARAMETERS, row["capacities"])))
        directory = out / "replays" / label
        directory.parent.mkdir(exist_ok=True)
        print(f"Free sparse ODE replay {number}/{len(replay_labels)}: {label}", flush=True)
        solutions = simulate(initial, candidate, working, [1., 46.], directory)
        states, parts, checks = audit_solutions(solutions, truth["time"], candidate, working, names, directory)
        write_json(directory / "learned_synthetic_parameters.json", candidate)
        np.savez_compressed(directory / "evaluation.npz", time=truth["time"], states=states,
            effective_flux=parts["effective"], native_flux=parts["native"], availability_factors=parts["factors"])
        metrics.extend(replay_metrics(states, parts, truth, label, names, 22.))
        replays.append({"label": label, "numerical_checks": checks})
        write_json(out / "partial_replay_results.json", replays)
    unchanged = {path: file_hash(Path(path)) == value for path, value in hashes.items()}
    if not all(unchanged.values()):
        raise ValueError("sparse screen inputs changed during execution")
    aggregates = []
    for method in method_names(design):
        group = [row for row in fits if row["case"] != "clean" and row["method"] == method]
        errors = np.asarray([row["relative_parameter_error"] for row in group])
        aggregates.append({"method": method, "noise_seed_count": len(group), "median_relative_parameter_error": np.median(errors, axis=0).tolist(),
            "maximum_relative_parameter_error": errors.max(axis=0).tolist(), "bound_case_count": sum(row["at_bound"] for row in group)})
    summary = {"status": "completed_synthetic_sparse_resolution_screen", "fit_count": len(fits), "replayed_pair_count": len(replays),
        "new_ODE_replay_count": 2*len(replays), "truth_reused_from_verified_parent": True,
        "all_replayed_numerical_checks_pass": all(row["numerical_checks"]["passes"] for row in replays),
        "input_hashes_unchanged": all(unchanged.values()), "kernel_parity_checks_pass": all(row["passes"] for row in parity),
        "all_aligned_capacity_convergence_checks_pass": all(row["passes_numerical_resolution_check"] for row in comparisons),
        "full_ODE_validation_applies_only_to_predeclared_subset": True, "aggregated_noise_results": aggregates,
        "fits": fits, "replays": replays, "biological_calibration_allowed": False, "global_model_promotion_allowed": False}
    write_json(out / "summary.json", summary)
    pd.DataFrame(metrics).to_csv(out / "full_pool_replay_metrics.csv", index=False)
    plot_study(out, fits, metrics, design)
    finalize_figures(out)
    lines = ["# Synthetic FLA: seven-time sparse teacher comparison", "",
        "Synthetic concentrations only; the local Bordbar schedule supplies times, not experimental training targets.",
        "Training J1/J4/J8/J11/J15/J18/J22; complete unforced prediction through J46. Same frozen truth, ICs, affinities, bounds, starts, numerical profile and threshold as the dense screen.",
        f"{len(fits)} conditional fits, {2*len(replays)} predeclared strict/ultrastrict full ODE replays. Five paired noise seeds at 0.5% CV; no truth-selected smoothing or replays.", "",
        "| Method | Median VEGLC error (%) | Maximum VEGLC error (%) | Median VELAC error (%) | Maximum VELAC error (%) |",
        "|---|---:|---:|---:|---:|"]
    for row in aggregates:
        med, maximum = 100*np.asarray(row["median_relative_parameter_error"]), 100*np.asarray(row["maximum_relative_parameter_error"])
        lines.append(f"| {row['method']} | {med[0]:.4g} | {maximum[0]:.4g} | {med[1]:.4g} | {maximum[1]:.4g} |")
    lines += ["", "Sparse noises reproduce the earlier sparse parent draws for the shared seeds, but are not matched dense-sparse draws.",
        "GCV uses seven training observations per pool and an explicit postfit initial anchor, not an exactly constrained spline. All interval targets retain raw signed increments.",
        "Full ODE validation applies only to the predeclared subset; all 113 pools and executed transport metrics are exported with absolute and relative errors.",
        "These are descriptive same-family fixed-affinity synthetic checks, not confidence intervals, biological calibration or global identifiability. All readiness guards and platform defaults remain unchanged."]
    (out / "decision_report.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    write_json(out / "final_verification.json", {"verified_at": datetime.now(timezone.utc).isoformat(), "input_hash_checks": unchanged,
        "biological_contract_changed": False, "parameters_promoted": False, "new_ODE_replay_count": 2*len(replays)})
    print(json.dumps({key: summary[key] for key in ("fit_count", "new_ODE_replay_count", "all_replayed_numerical_checks_pass", "all_aligned_capacity_convergence_checks_pass")}), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    run(args.config.resolve(), args.out.resolve())
