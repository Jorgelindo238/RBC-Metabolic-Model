"""Paired synthetic grid/smoothing study, with a preregistered full-ODE replay subset."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT / "src", ROOT / "scripts"):
    sys.path.insert(0, str(directory))

from fla_synthetic_recovery import (
    OBSERVED_POOLS, PARAMETERS, REACTIONS, add_synthetic_noise, check_linear_capacity_domain,
    executed_transport, fit_capacities, unit_capacity_basis,
)
from fla_teacher_resolution import (
    TrainingCurves, canonical_partition, fast_transport_basis, integrated_problem, method_names, time_grid,
    validate_design, weighted_problem,
)
from fla_working_reference import load_working_reference, reference_options
from extracellular_teacher_flux import build_extracellular_teacher_flux_dataset
from run_fla_synthetic_recovery import audit_solutions, file_hash, simulate, write_json

DEFAULT_CONFIG = ROOT / "config/fla_teacher_resolution.json"
DEFAULT_OUT = ROOT / "output/fla_teacher_resolution_2026_10_05_v2"


def load_parent(parent):
    contract = json.loads((parent / "preregistered_contract.json").read_text())
    summary = json.loads((parent / "summary.json").read_text())
    final = json.loads((parent / "final_verification.json").read_text())
    if (contract["contract_type"] != "synthetic_software_benchmark_not_biological_calibration"
            or not summary["synthetic_checks"]["all_replays_numerically_pass"]
            or not final["independent_archive_checks_pass"] or final["biological_contract_changed"]
            or contract["working_reference"] != load_working_reference()):
        raise ValueError("parent must be a verified unchanged synthetic benchmark")
    for path, digest in contract["input_sha256"].items():
        if file_hash(Path(path)) != digest:
            raise ValueError(f"parent input changed: {path}")
    if contract["design"]["horizon_day"] != [1., 46.] or contract["design"]["training_end_day"] != 22.:
        raise ValueError("this paired study preserves J1-J22 training and J22-J46 holdout")
    frame = pd.read_csv(parent / "datasets/dense_clean/observations.csv", float_precision="round_trip")
    time, values = frame.time_day.to_numpy(), frame[list(OBSERVED_POOLS)].to_numpy().T
    source = ROOT / contract["working_reference"]["fixed_context"]
    params = json.loads((source / "fixed_parameters.json").read_text())
    archive = np.load(parent / "frozen_initial_state.npz")
    return contract, params, archive["states"], tuple(archive["names"]), time, values


def kernel_parity(curves, initial, params, ode, tolerance):
    query = np.linspace(curves.time[0], curves.time[-1], 13)
    states, _ = curves.proxy(query, initial)
    fast = fast_transport_basis(query, states, params, ode)
    direct = unit_capacity_basis(query, states, params, ode)
    error = float(np.max(np.abs(fast["basis"] - direct)))
    if error > tolerance:
        raise ValueError("fast transport disagrees with complete executed ODE")
    return {"compared_states": len(query), "maximum_executed_rate_difference": error, "passes": True}


def fit_method(case, name, basis, targets, weights, grid, base, parent_design, truth, out):
    scored_basis, scored_targets = weighted_problem(basis, targets, weights)
    fit = fit_capacities(scored_basis, scored_targets, base, parent_design["search_multiplier_bounds"], parent_design["start_multipliers"])
    label = f"{case}_{name}"
    directory = out / "fits" / label
    directory.mkdir(parents=True)
    np.savez_compressed(directory / "training_problem.npz", basis=basis, targets=targets, weights=weights, grid=grid)
    write_json(directory / "conditional_recovery.json", fit)
    return {"case": case, "method": name, "label": label, "capacities": fit["capacities"],
            "relative_parameter_error": np.abs(np.asarray(fit["capacities"])/truth-1).tolist(),
            "conditional_log_jacobian_rank": fit["conditional_log_jacobian_rank"],
            "at_bound": any(fit["at_bound"]), "multistart_max_capacity_spread": fit["multistart_max_capacity_spread"]}


def replay_metrics(states, parts, truth, label, names, split):
    rows = []
    for period, mask in (("training", truth["time"] <= split), ("holdout", truth["time"] > split)):
        actual = states[:113, mask]
        reference = truth["states"][:113, mask]
        rmse = np.sqrt(np.mean((actual-reference)**2, axis=1))
        excursion = np.ptp(reference, axis=1)
        mean = np.mean(np.abs(reference), axis=1)
        for i, pool in enumerate(names[:113]):
            rows.append({"label": label, "period": period, "kind": "concentration", "name": pool,
                         "absolute_rmse": float(rmse[i]), "unit": "mM", "truth_mean": float(mean[i]),
                         "excursion_nrmse": float(rmse[i]/max(excursion[i], .001)),
                         "mean_nrmse": float(rmse[i]/max(mean[i], .001)),
                         "last_error": float(actual[i, -1]-reference[i, -1])})
        rate = truth["effective"][:, mask]
        flux_rmse = np.sqrt(np.mean((parts["effective"][:, mask]-rate)**2, axis=1))
        for i, reaction in enumerate(REACTIONS):
            rows.append({"label": label, "period": period, "kind": "executed_flux", "name": reaction,
                         "absolute_rmse": float(flux_rmse[i]), "unit": "mM/day", "truth_mean": float(np.mean(np.abs(rate[i]))),
                         "excursion_nrmse": None, "mean_nrmse": float(flux_rmse[i]/max(np.sqrt(np.mean(rate[i]**2)), 1e-6)),
                         "last_error": float(parts["effective"][i, mask][-1]-rate[i, -1])})
    return rows


def plot_study(out, fits, metrics, design):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    frame = pd.DataFrame(fits)
    noisy = frame[frame.case != "clean"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    for i, (axis, parameter) in enumerate(zip(axes, PARAMETERS)):
        for mode, color in (("raw", "#b45446"), ("smooth", "#248779")):
            medians, maxima = [], []
            for count in design["uniform_grid_counts"]:
                values = np.asarray(noisy[noisy.method == f"{mode}_uniform{count}"].relative_parameter_error.tolist())[:, i] * 100
                medians.append(np.median(values))
                maxima.append(np.max(values))
            axis.plot(design["uniform_grid_counts"], medians, marker="o", color=color, label=f"{mode}: median of 5 seeds")
            axis.plot(design["uniform_grid_counts"], maxima, linestyle=":", color=color, label=f"{mode}: maximum of 5 seeds")
        for name, color in (("raw_aligned8", "#4d72b4"), ("smooth_aligned8", "#53565c"), ("raw_integrated", "#967c24")):
            values = np.asarray(noisy[noisy.method == name].relative_parameter_error.tolist())[:, i] * 100
            axis.axhline(np.median(values), linestyle="--", color=color, label=f"{name}: median")
        axis.set(xscale="log", yscale="symlog", title=parameter, xlabel="Uniform teacher grid points", ylabel="Absolute capacity error (%)")
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(alpha=.15)
    axes[1].legend(fontsize=7, loc="upper right", frameon=False)
    fig.suptitle("Paired synthetic FLA: teacher resolution and smoothing", fontsize=13)
    fig.savefig(out / "grid_smoothing_comparison.png", dpi=170)
    fig.savefig(out / "grid_smoothing_comparison.pdf")
    plt.close(fig)
    metric_frame = pd.DataFrame(metrics)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    colors = ("#b45446", "#4d72b4", "#248779", "#967c24")
    for axis, pool in zip(axes, ("EGLC", "ELAC")):
        for position, (method, color) in enumerate(zip(design["replay_methods"], colors)):
            labels = {row["label"] for row in fits if row["case"] != "clean" and row["method"] == method}
            values = metric_frame[(metric_frame.label.isin(labels)) & (metric_frame.period == "holdout") & (metric_frame.name == pool)].excursion_nrmse.to_numpy()
            axis.scatter(np.full(len(values), position), values*100, color=color, s=45)
        axis.set_xticks(range(len(colors)), design["replay_methods"], rotation=25, ha="right", fontsize=8)
        axis.set(ylabel="Holdout excursion nRMSE (%)", title=pool, yscale="symlog")
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(axis="y", alpha=.15)
    fig.suptitle("Free J22-J46 predictions: three preselected noise seeds", fontsize=13)
    fig.savefig(out / "holdout_method_comparison.png", dpi=170)
    fig.savefig(out / "holdout_method_comparison.pdf")
    plt.close(fig)


def run(config_path, out):
    if out.exists():
        raise FileExistsError("fresh output directory required")
    design = validate_design(json.loads(config_path.read_text()))
    parent = ROOT / design["parent_archive"]
    parent_contract, params, initial, names, time, clean = load_parent(parent)
    time, clean, partition = canonical_partition(time, clean, tolerance=design["time_merge_absolute_tolerance_day"])
    pdsgn, working = parent_contract["design"], parent_contract["working_reference"]
    if design["noise_coefficient_of_variation"] != pdsgn["noise_coefficient_of_variation"]:
        raise ValueError("paired screen keeps the parent noise amplitude")
    base = np.asarray([params[p] for p in PARAMETERS])
    truth_capacities = base * pdsgn["truth_multipliers"]
    check_linear_capacity_domain(params, base, pdsgn["search_multiplier_bounds"])
    ode, _ = reference_options(working)
    cases = ["clean"] + [f"noise_{seed}" for seed in design["noise_seeds"]]
    replay_cases = ["clean"] + [f"noise_{seed}" for seed in design["replay_noise_seeds"]]
    replay_labels = [f"{case}_{method}" for case in replay_cases for method in design["replay_methods"]]
    input_paths = [config_path, Path(__file__), ROOT / "src/fla_teacher_resolution.py",
                   parent / "preregistered_contract.json", parent / "summary.json", parent / "final_verification.json",
                   parent / "frozen_initial_state.npz", parent / "truth/evaluation.npz", parent / "datasets/dense_clean/observations.csv"]
    input_paths.extend(Path(path) for path in parent_contract["input_sha256"])
    hashes = {str(path.resolve()): file_hash(path) for path in input_paths}
    out.mkdir(parents=True)
    contract = {"contract_type": design["purpose"], "created_at": datetime.now(timezone.utc).isoformat(),
                "design": design, "parent_design": pdsgn, "working_reference": working,
                "input_sha256": hashes, "cases": cases, "methods": method_names(design), "replay_labels": replay_labels,
                "conditional_fit_count": len(cases)*len(method_names(design)), "planned_ODE_replay_count": 2*len(replay_labels),
                "full_ODE_replayed_methods_are_fixed_not_rank_selected": True,
                "truth_used_to_select_smoothing_or_grid": False, "frozen_initial_state": True,
                "biological_calibration_allowed": False, "global_model_promotion_allowed": False,
                "smoothing_reference": "https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.interpolate.make_smoothing_spline.html"}
    write_json(out / "preregistered_contract.json", contract)
    write_json(out / "time_partition_receipt.json", partition)
    pd.DataFrame({"time_day": time, **dict(zip(OBSERVED_POOLS, clean))}).to_csv(out / "canonical_clean_observations.csv", index=False)
    write_json(out / "frozen_parameters.json", params)
    np.savez_compressed(out / "frozen_initial_state.npz", states=initial, names=np.asarray(names))
    fits, parity, numerical_controls = [], [], []
    for case in cases:
        print(f"Reconstruction/conditional fits: {case}", flush=True)
        values = clean.copy() if case == "clean" else add_synthetic_noise(clean, cv=design["noise_coefficient_of_variation"], seed=int(case.split("_")[1]))[0]
        directory = out / "datasets" / case
        directory.mkdir(parents=True)
        pd.DataFrame({"time_day": time, **dict(zip(OBSERVED_POOLS, values))}).to_csv(directory / "observations.csv", index=False)
        curves = {mode: TrainingCurves(time, values, training_end=22., mode=mode,
                   noise_cv=0. if case == "clean" else design["noise_coefficient_of_variation"]) for mode in ("raw", "smooth")}
        for mode, curve in curves.items():
            write_json(directory / f"{mode}_curve_receipt.json", curve.receipt())
            parity.append({"case": case, "mode": mode, **kernel_parity(curve, initial, params, ode, design["kernel_parity_absolute_tolerance"])})
            for count in design["uniform_grid_counts"]:
                query, weights, _ = time_grid(time, count=count)
                states, target = curve.proxy(query, initial)
                basis = fast_transport_basis(query, states, params, ode)["basis"]
                name = f"{mode}_uniform{count}"
                fits.append(fit_method(case, name, basis, target, weights, query, base, pdsgn, truth_capacities, out))
                if mode == "raw" and count == 401:
                    teacher = build_extracellular_teacher_flux_dataset(dict(zip(OBSERVED_POOLS, values)), time,
                        metabolite_names=("EGLC", "ELAC"), dense_points=401, dataset_label="synthetic_resolution_legacy_control")
                    production = np.asarray([teacher["reaction_flux_curves"][r]["dense_values"] for r in REACTIONS])
                    if not np.array_equal(production, target):
                        raise ValueError("raw teacher differs from production PCHIP builder")
                    fits.append(fit_method(case, "legacy_raw401", basis, target, np.ones(len(query)), query, base, pdsgn, truth_capacities, out))
            for order in design["aligned_quadrature_orders"]:
                query, weights, _ = time_grid(time, order=order)
                states, target = curve.proxy(query, initial)
                basis = fast_transport_basis(query, states, params, ode)["basis"]
                fits.append(fit_method(case, f"{mode}_aligned{order}", basis, target, weights, query, base, pdsgn, truth_capacities, out))
            integrals = [integrated_problem(curve, initial, params, ode, order=order) for order in design["integrated_quadrature_orders"]]
            error = np.abs(integrals[0][0]-integrals[1][0])
            passes = bool(np.all(error <= 1e-7 + 1e-3*np.abs(integrals[1][0])))
            numerical_controls.append({"case": case, "mode": mode, "integral_order8_order16_pass": passes,
                                       "max_integral_basis_difference": float(np.max(error))})
            if not passes:
                raise ValueError("interval basis quadrature failed")
            name = "raw_integrated" if mode == "raw" else "smoothed_inputs_integrated"
            midpoint = (time[:-1]+time[1:])/2
            fits.append(fit_method(case, name, *integrals[1], np.ones(len(midpoint)), midpoint, base, pdsgn, truth_capacities, out))
        write_json(out / "partial_fit_results.json", fits)
    write_json(out / "kernel_parity.json", parity)
    write_json(out / "interval_quadrature_checks.json", numerical_controls)
    if len(fits) != contract["conditional_fit_count"] or {row["method"] for row in fits} != set(method_names(design)):
        raise ValueError("incomplete method design")
    comparisons = []
    for case in cases:
        for mode in ("raw", "smooth"):
            coarse = next(row for row in fits if row["case"] == case and row["method"] == f"{mode}_aligned4")
            fine = next(row for row in fits if row["case"] == case and row["method"] == f"{mode}_aligned8")
            delta = np.abs(np.asarray(coarse["capacities"])/fine["capacities"]-1)
            comparisons.append({"case": case, "mode": mode, "capacity_relative_difference": delta.tolist(),
                                "passes_numerical_resolution_check": bool(np.all(delta <= design["capacity_quadrature_relative_tolerance"]))})
    write_json(out / "aligned_capacity_convergence.json", comparisons)
    write_json(out / "conditional_results.json", fits)
    truth = np.load(parent / "truth/evaluation.npz")
    metrics, replay_rows = [], []
    for label in replay_labels:
        row = next(item for item in fits if item["label"] == label)
        candidate = dict(params)
        candidate.update(dict(zip(PARAMETERS, row["capacities"])))
        directory = out / "replays" / label
        directory.parent.mkdir(exist_ok=True)
        print(f"Free ODE replay {len(replay_rows)+1}/{len(replay_labels)}: {label}", flush=True)
        solutions = simulate(initial, candidate, working, [1., 46.], directory)
        states, parts, checks = audit_solutions(solutions, truth["time"], candidate, working, names, directory)
        write_json(directory / "learned_synthetic_parameters.json", candidate)
        np.savez_compressed(directory / "evaluation.npz", time=truth["time"], states=states,
                            effective_flux=parts["effective"], native_flux=parts["native"], availability_factors=parts["factors"])
        metrics.extend(replay_metrics(states, parts, truth, label, names, 22.))
        replay_rows.append({"label": label, "numerical_checks": checks})
        write_json(out / "partial_replay_results.json", replay_rows)
    unchanged = {path: file_hash(Path(path)) == digest for path, digest in hashes.items()}
    if not all(unchanged.values()):
        raise ValueError("inputs changed during the screen")
    aggregate = []
    for method in method_names(design):
        group = [row for row in fits if row["case"] != "clean" and row["method"] == method]
        errors = np.asarray([row["relative_parameter_error"] for row in group])
        aggregate.append({"method": method, "noise_seed_count": len(group), "median_relative_parameter_error": np.median(errors, axis=0).tolist(),
                          "maximum_relative_parameter_error": errors.max(axis=0).tolist(), "bound_case_count": sum(row["at_bound"] for row in group)})
    summary = {"status": "completed_synthetic_resolution_screen", "fit_count": len(fits), "replayed_pair_count": len(replay_rows),
               "new_ODE_replay_count": len(replay_rows)*2, "truth_reused_from_verified_parent": True,
               "all_replayed_numerical_checks_pass": all(row["numerical_checks"]["passes"] for row in replay_rows),
               "input_hashes_unchanged": all(unchanged.values()), "kernel_parity_checks_pass": all(row["passes"] for row in parity),
               "all_aligned_capacity_convergence_checks_pass": all(row["passes_numerical_resolution_check"] for row in comparisons),
               "aggregated_noise_results": aggregate, "fits": fits, "replays": replay_rows,
               "full_ODE_validation_applies_only_to_predeclared_subset": True,
               "biological_calibration_allowed": False, "global_model_promotion_allowed": False}
    write_json(out / "summary.json", summary)
    pd.DataFrame(metrics).to_csv(out / "full_pool_replay_metrics.csv", index=False)
    plot_study(out, fits, metrics, design)
    lines = ["# Synthetic FLA: teacher resolution and smoothing", "",
             "Only two transport capacities are learned; all initial states, affinities, other kinetics and numerical policy stay frozen.",
             "Training J1-J22; held-out free prediction through J46. Six dense regimes: clean and five paired 0.5% CV log-normal noise seeds.",
             f"{len(fits)} conditional fits; {len(replay_rows)} preselected parameter pairs receive {2*len(replay_rows)} new strict/ultrastrict ODE replays. No best-case replay selection.", "",
             "| Method | Median VEGLC error (%) | Maximum VEGLC error (%) | Median VELAC error (%) | Maximum VELAC error (%) |",
             "|---|---:|---:|---:|---:|"]
    for row in aggregate:
        med, maximum = np.asarray(row["median_relative_parameter_error"])*100, np.asarray(row["maximum_relative_parameter_error"])*100
        lines.append(f"| {row['method']} | {med[0]:.4g} | {maximum[0]:.4g} | {med[1]:.4g} | {maximum[1]:.4g} |")
    lines += ["", "## Boundaries", "",
              f"Clean training timestamps are canonicalized before noise: {partition['original_count']} to {partition['canonical_count']} points at 1e-10 day tolerance. Historical input files stay unchanged.",
              "Noise is paired across methods in this screen, not bit-identical to the earlier 689-point parent draws. Legacy 401 is an objective control, not exact reproduction of the parent fit.",
              "Temporal weights distinguish equal-point legacy loss from a time-integrated pointwise objective. Aligned Gauss cells resolve every observation interval.",
              "Raw PCHIP teachers are checked against the production builder. Fast transport uses actual rate helpers and signed limiter, checked against the full kernel.",
              "Log smoothing uses training-only GCV and a postfit log shift to preserve the known initial value; this is not an exact constrained-spline optimum.",
              "Raw observed increments remain the primary interval targets, including when only kinetic inputs are smoothed.",
              "Five synthetic noise seeds are descriptive, not biological replicates or statistical confidence intervals. Not all conditional grid variants have ODE replays.",
              "Full 113-pool absolute/mean/excursion errors are exported separately from executed-flux errors. No biological calibration or promotion.",
              "Smoothing reference: [SciPy make_smoothing_spline](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.interpolate.make_smoothing_spline.html)."]
    (out / "decision_report.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    write_json(out / "final_verification.json", {"verified_at": datetime.now(timezone.utc).isoformat(), "input_hash_checks": unchanged,
               "biological_contract_changed": False, "parameters_promoted": False, "new_ODE_replay_count": len(replay_rows)*2})
    print(json.dumps({key: summary[key] for key in ("fit_count", "new_ODE_replay_count", "all_replayed_numerical_checks_pass", "all_aligned_capacity_convergence_checks_pass")}), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    run(args.config.resolve(), args.out.resolve())
