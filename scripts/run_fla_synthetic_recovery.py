"""Run an isolated transport FLA recovery benchmark with synthetic observations only."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
import scipy
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT / "src", ROOT / "scripts"):
    sys.path.insert(0, str(directory))

from equadiff_brodbar import equadiff_brodbar
from fla_balance_audit import accepted_step_quadrature, integrate_intervals
from fla_synthetic_recovery import (
    OBSERVED_POOLS, PARAMETERS, REACTIONS, SIGNS, add_synthetic_noise, check_linear_capacity_domain,
    executed_transport, excursion_metrics, fit_capacities, reconstruction, unit_capacity_basis, validate_config,
)
from fla_working_reference import load_working_reference, reference_options
from test_reaction_positivity_fixed_context import load_context

DEFAULT_CONFIG = ROOT / "config/fla_synthetic_recovery.json"
DEFAULT_OUT = ROOT / "output/fla_synthetic_recovery_2026_10_05_v2"


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def simulate(x0, params, working, horizon, out):
    out.mkdir()
    result = {}
    for name in ("strict", "ultrastrict"):
        ode, solver = reference_options(working, ultrastrict=name == "ultrastrict")
        started = perf_counter()
        solution = solve_ivp(lambda t, y: equadiff_brodbar(t, y, custom_params=params, **ode),
                             tuple(horizon), x0.copy(), dense_output=True, **solver)
        if not solution.success or solution.t[-1] != horizon[-1] or not np.all(np.isfinite(solution.y)):
            raise ValueError(f"incomplete or nonfinite {name} replay: {solution.message}")
        np.savez_compressed(out / f"{name}_accepted_states.npz", time=solution.t, states=solution.y)
        result[name] = solution
        print(f"  {out.name}/{name}: {len(solution.t)} accepted nodes, {perf_counter()-started:.1f}s", flush=True)
    return result


def audit_solutions(solutions, time, params, working, names, out):
    ode, _ = reference_options(working)
    states = {key: sol.sol(time) for key, sol in solutions.items()}
    strict, ultra = states["strict"], states["ultrastrict"]
    controls = working["validation_before_calibration"]
    difference = np.abs(strict - ultra)
    allowed = controls["comparison_atol_mM"] + controls["comparison_rtol"] * np.maximum(np.abs(strict), np.abs(ultra))
    rows = [{"pool": pool, "maximum_absolute_difference": float(np.max(difference[i])),
             "strict_ultrastrict_pass": bool(np.all(difference[i] <= allowed[i]))} for i, pool in enumerate(names)]
    pd.DataFrame(rows).to_csv(out / "solver_convergence.csv", index=False)
    parts = {key: executed_transport(time, value, params, ode) for key, value in states.items()}
    fluxdiff = np.abs(parts["strict"]["effective"] - parts["ultrastrict"]["effective"])
    fluxallow = 1e-6 + .01 * np.maximum(np.abs(parts["strict"]["effective"]), np.abs(parts["ultrastrict"]["effective"]))
    minimum = min(float(np.min(value[:113])) for value in states.values())
    minimum = min(minimum, *(float(np.min(sol.y[:113])) for sol in solutions.values()))
    negative = sum(int(np.count_nonzero(sol.y[:113] < 0)) for sol in solutions.values())
    closure = max(float(np.max(value["closure"])) for value in parts.values())
    numerical = {"minimum_raw_checked_concentration_mM": minimum, "negative_accepted_count": negative,
                 "max_executed_balance_closure_mM_per_day": closure,
                 "state_convergence_pass": all(row["strict_ultrastrict_pass"] for row in rows),
                 "executed_transport_convergence_pass": bool(np.all(fluxdiff <= fluxallow))}
    numerical["passes"] = bool(minimum >= controls["negative_state_tolerance_mM"] and negative == 0
        and closure <= controls["closure_tolerance_mM_per_day"] and numerical["state_convergence_pass"]
        and numerical["executed_transport_convergence_pass"])
    write_json(out / "numerical_audit.json", numerical)
    return states["ultrastrict"], parts["ultrastrict"], numerical


def truth_integral_audit(solution, observation_time, params, working, out):
    ode, _ = reference_options(working)
    cuts = np.unique(np.r_[observation_time, solution.t[-1]])
    integrals = {}
    for order in (4, 8):
        grid = accepted_step_quadrature(solution.t, cuts, order=order)
        parts = executed_transport(grid.nodes, solution.sol(grid.nodes), params, ode)
        integrals[order] = integrate_intervals(parts["effective"], grid)
    indices = [OBSERVED_POOLS.index(pool) for pool in ("EGLC", "ELAC")]
    from equadiff_brodbar import BRODBAR_METABOLITE_MAP
    state_indices = [BRODBAR_METABOLITE_MAP[OBSERVED_POOLS[i]] for i in indices]
    expected = SIGNS[:, None] * np.diff(solution.sol(cuts)[state_indices], axis=1)
    error = np.abs(integrals[8] - expected)
    qerror = np.abs(integrals[8] - integrals[4])
    checks = {"max_executed_integral_vs_state_change_mM": float(np.max(error)),
              "max_order4_order8_difference_mM": float(np.max(qerror)),
              "passes": bool(np.all(error <= 1e-6 + 1e-3*np.abs(expected))
                             and np.all(qerror <= 1e-6 + 1e-3*np.abs(integrals[8])))}
    pd.DataFrame([{"reaction": reaction, "start_day": float(cuts[j]), "end_day": float(cuts[j+1]),
                   "required_integral_mM": float(expected[i, j]), "executed_integral_mM": float(integrals[8][i, j]),
                   "order4_order8_difference_mM": float(qerror[i, j])}
                  for i, reaction in enumerate(REACTIONS) for j in range(len(cuts)-1)]).to_csv(out / "truth_interval_fluxes.csv", index=False)
    write_json(out / "truth_integral_audit.json", checks)
    return checks


def verify_capacity_basis(time, states, params, base, bounds, ode):
    check_linear_capacity_domain(params, base, bounds)
    basis = unit_capacity_basis(time, states, params, ode)
    maximum = 0.
    for multiplier in (bounds[0], 1., bounds[1]):
        candidate = dict(params)
        candidate.update(dict(zip(PARAMETERS, base * multiplier)))
        direct = executed_transport(time, states, candidate, ode)["effective"]
        maximum = max(maximum, float(np.max(np.abs(direct - base[:, None] * multiplier * basis))))
    if maximum > 1e-10:
        raise ValueError("cached capacity basis disagrees with real executed rates")
    return {"maximum_kernel_difference_mM_per_day": maximum, "passes": True}


def plot_results(out, results, metrics, time, truth, truth_parts, names, split):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    colors = {"oracle": "#30343b", "dense_clean": "#15847b", "sparse_clean": "#b65b43", "sparse_noisy_2718": "#486fbe"}
    from equadiff_brodbar import BRODBAR_METABOLITE_MAP
    for row, pool in enumerate(("EGLC", "ELAC")):
        index = BRODBAR_METABOLITE_MAP[pool]
        axes[row, 0].plot(time, truth[index], color="black", linewidth=2.2, label="Known synthetic truth")
        axes[row, 1].plot(time, truth_parts["effective"][row], color="black", linewidth=2.2, label="Executed truth")
        for result in results:
            case = result["case"]
            if case not in colors or (case != "oracle" and result["method"] != "integrated"):
                continue
            arrays = np.load(out / result["label"] / "evaluation.npz")
            axes[row, 0].plot(time, arrays["states"][index], color=colors[case], linestyle="--", label=result["label"])
            axes[row, 1].plot(time, arrays["effective_flux"][row], color=colors[case], linestyle="--", label=result["label"])
        for axis in axes[row]:
            axis.axvline(split, color="#777777", linestyle=":", linewidth=1)
            axis.axvspan(split, time[-1], color="#777777", alpha=.07)
            axis.set(xlabel="Model day", ylabel="mM" if axis is axes[row, 0] else "mM/day",
                     title=pool if axis is axes[row, 0] else REACTIONS[row])
            axis.spines[["top", "right"]].set_visible(False)
            axis.grid(alpha=.15)
    axes[0, 0].legend(fontsize=7, frameon=False)
    fig.suptitle("Synthetic FLA transport recovery - shaded interval is held out", fontsize=13)
    fig.savefig(out / "synthetic_recovery.png", dpi=170)
    fig.savefig(out / "synthetic_recovery.pdf")
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(12, 5), constrained_layout=True)
    positions = np.arange(len(results))
    for i, (parameter, color) in enumerate(zip(PARAMETERS, ("#15847b", "#b65b43"))):
        ax.bar(positions + (i-.5)*.36, [100*row["relative_parameter_error"][i] for row in results], .36, label=parameter, color=color)
    ax.set_xticks(positions, [row["label"] for row in results], rotation=55, ha="right", fontsize=8)
    ax.set(ylabel="Absolute parameter error (%)", title="Recovery of known transport capacities")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=9)
    fig.savefig(out / "parameter_recovery.png", dpi=170)
    plt.close(fig)


def run(config_path, out):
    if out.exists():
        raise FileExistsError("use a fresh output directory; historical evidence is never overwritten")
    design = validate_config(json.loads(config_path.read_text(encoding="utf-8")))
    working = load_working_reference()
    context = ROOT / working["fixed_context"]
    x0, params, names, table_times, _unused_measured_curves, data_path = load_context(context)
    base = np.asarray([params[p] for p in PARAMETERS])
    check_linear_capacity_domain(params, base, design["search_multiplier_bounds"])
    truth_params = dict(params)
    truth_capacities = base * design["truth_multipliers"]
    truth_params.update(dict(zip(PARAMETERS, truth_capacities)))
    split = design["training_end_day"]
    sparse = table_times[table_times <= split]
    if sparse[-1] != split:
        raise ValueError("split must be an actual local table time, not an invented sparse observation")
    dense = np.unique(np.r_[np.linspace(design["horizon_day"][0], split, design["dense_observation_count"]),
                             np.linspace(design["horizon_day"][0], design["horizon_day"][0]+1, design["dense_early_observation_count"])])
    evaluation_time = np.unique(np.r_[np.linspace(*design["horizon_day"], design["evaluation_point_count"]),
                                      table_times, split, 1. + np.geomspace(1e-7, 1., 101)])
    input_paths = [config_path, ROOT / "config/fla_working_reference.json", ROOT / "config/fla_adenylate_redox_readiness.json",
                   ROOT / "output/adenylate_redox_readiness_2026_10_05_v2/coupled_sensitivity_protocol.json", data_path,
                   context / "fixed_parameters.json", context / "fixed_initial_state.csv", context / "preregistered_contract.json",
                   context / "strict/accepted_solver_states.npz", Path(__file__)]
    input_paths.extend(ROOT / "src" / name for name in ("fla_synthetic_recovery.py", "fla_working_reference.py", "fla_balance_audit.py",
                       "extracellular_teacher_flux.py", "equadiff_brodbar.py", "reaction_positivity.py", "rbc_stoichiometry.py"))
    input_paths.append(ROOT / "scripts/test_reaction_positivity_fixed_context.py")
    hashes = {str(path.resolve()): file_hash(path) for path in input_paths}
    contract = {"contract_type": design["purpose"], "created_at": datetime.now(timezone.utc).isoformat(),
                "design": design, "working_reference": working, "input_sha256": hashes,
                "truth_capacities": dict(zip(PARAMETERS, truth_capacities.tolist())),
                "all_other_kinetics_and_ICs_frozen": True, "real_concentrations_used_as_training_targets": False,
                "local_workbook_role": "frozen legacy initial context and sampling times only, not biological truth",
                "teacher_forcing": False, "observation_reset": False, "raw_state_output_clipping": False,
                "learned_state_information": list(OBSERVED_POOLS),
                "oracle_role": "exact synthetic full states and executed fluxes; diagnostic control, not deployable observations",
                "nonoracle_state_information": "PCHIP of four synthetic observed pools only; latent truth never supplied to learner",
                "fitted_scope": "conditional two-capacity recovery, not full MM_calibration/Optuna or Phase C ML validation",
                "methods": ["pointwise", "integrated"], "solver_crosscheck_for_each_replay": ["strict", "ultrastrict"],
                "sparse_training_times": sparse.tolist(), "dense_training_times": dense.tolist(),
                "holdout_times": table_times[table_times > split].tolist(),
                "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
                "biological_calibration_allowed": False, "global_model_promotion_allowed": False}
    out.mkdir(parents=True)
    write_json(out / "preregistered_contract.json", contract)
    write_json(out / "synthetic_truth_parameters.json", truth_params)
    np.savez_compressed(out / "frozen_initial_state.npz", states=x0, names=np.asarray(names))
    print("Synthetic truth: fixed network/ICs, two perturbed transport capacities only", flush=True)
    truth_solutions = simulate(x0, truth_params, working, design["horizon_day"], out / "truth")
    truth, truth_parts, truth_numerical = audit_solutions(truth_solutions, evaluation_time, truth_params, working, names, out / "truth")
    write_json(out / "truth" / "capacity_basis_check.json", verify_capacity_basis(
        evaluation_time[::40], truth[:, ::40], params, base, design["search_multiplier_bounds"], reference_options(working)[0]))
    quadrature = truth_integral_audit(truth_solutions["ultrastrict"], sparse, truth_params, working, out / "truth")
    if not truth_numerical["passes"] or not quadrature["passes"]:
        raise ValueError("synthetic truth failed numerical checks; fitting is forbidden")
    np.savez_compressed(out / "truth" / "evaluation.npz", time=evaluation_time, states=truth, **truth_parts)
    from equadiff_brodbar import BRODBAR_METABOLITE_MAP
    indices = [BRODBAR_METABOLITE_MAP[p] for p in OBSERVED_POOLS]
    datasets = []
    for case, time in (("dense_clean", dense), ("sparse_clean", sparse)):
        clean = truth_solutions["ultrastrict"].sol(time)[indices]
        datasets.append((case, time, clean, None))
        seeds = design["noise_seeds"][:1] if case == "dense_clean" else design["noise_seeds"]
        for seed in seeds:
            noisy, sigma = add_synthetic_noise(clean, cv=design["noise_coefficient_of_variation"], seed=seed)
            datasets.append((case.replace("clean", "noisy")+f"_{seed}", time, noisy, sigma))
    ode, _ = reference_options(working)
    oracle_time = np.unique(np.r_[np.linspace(1., split, design["teacher_point_count"]), np.linspace(1., 2., 101)])
    oracle_states = truth_solutions["ultrastrict"].sol(oracle_time)
    oracle_targets = executed_transport(oracle_time, oracle_states, truth_params, ode)["effective"]
    fit_specs = [("oracle", "exact_executed", unit_capacity_basis(oracle_time, oracle_states, params, ode), oracle_targets, {})]
    teachers = []
    for case, time, values, sigma in datasets:
        dataset_out = out / "datasets" / case
        dataset_out.mkdir(parents=True)
        pd.DataFrame({"time_day": time, **dict(zip(OBSERVED_POOLS, values))}).to_csv(dataset_out / "observations.csv", index=False)
        write_json(dataset_out / "noise_design.json", {"synthetic_only": True, "noise_model": design["noise_model"],
                   "coefficient_of_variation": design["noise_coefficient_of_variation"] if sigma is not None else 0.,
                   "sigma_mM_by_pool_and_time": None if sigma is None else dict(zip(OBSERVED_POOLS, sigma.tolist())),
                   "initial_observation_noise": 0., "biological_measurement_uncertainty_established": False})
        coarse, fine = [reconstruction(time, values, x0, params, ode, training_end=split,
                         point_count=design["teacher_point_count"], order=order) for order in design["quadrature_orders"]]
        integral_error = np.abs(coarse["integrated_basis"] - fine["integrated_basis"])
        integral_pass = bool(np.all(integral_error <= 1e-7 + 1e-3 * np.abs(fine["integrated_basis"])))
        if not integral_pass:
            raise ValueError(f"reconstructed-basis quadrature did not converge: {case}")
        write_json(dataset_out / "teacher_flux_dataset.json", fine["teacher"])
        np.savez_compressed(dataset_out / "reconstructed_training.npz", time=fine["time"], basis=fine["basis"],
                              targets=fine["targets"], integrated_basis=fine["integrated_basis"], integral_targets=fine["integral_targets"])
        executed_truth = executed_transport(fine["time"], truth_solutions["ultrastrict"].sol(fine["time"]), truth_params, ode)["effective"]
        teacher_error = np.sqrt(np.mean((fine["targets"] - executed_truth)**2, axis=1)) / np.maximum(np.sqrt(np.mean(executed_truth**2, axis=1)), 1e-6)
        meta = {"quadrature_pass": integral_pass, "max_order8_order16_basis_integral_difference": float(np.max(integral_error)),
                "pointwise_teacher_rms_normalized_error": dict(zip(REACTIONS, teacher_error.tolist()))}
        teachers.append({"case": case, **meta})
        for method, bkey, tkey in (("pointwise", "basis", "targets"), ("integrated", "integrated_basis", "integral_targets")):
            fit_specs.append((case, method, fine[bkey], fine[tkey], meta))
    results, metric_rows = [], []
    trainmask, holdmask = evaluation_time <= split, evaluation_time > split
    for case, method, basis, targets, meta in fit_specs:
        label = f"{case}_{method}"
        print(f"Recovery {len(results)+1}/{len(fit_specs)}: {label}", flush=True)
        fit = fit_capacities(basis, targets, base, design["search_multiplier_bounds"], design["start_multipliers"])
        learned = dict(params)
        learned.update(dict(zip(PARAMETERS, fit["capacities"])))
        solutions = simulate(x0, learned, working, design["horizon_day"], out / label)
        states, parts, numerical = audit_solutions(solutions, evaluation_time, learned, working, names, out / label)
        write_json(out / label / "learned_synthetic_parameters.json", learned)
        write_json(out / label / "conditional_recovery.json", fit)
        np.savez_compressed(out / label / "evaluation.npz", time=evaluation_time, states=states, effective_flux=parts["effective"],
                              native_flux=parts["native"], availability_factors=parts["factors"])
        errors = np.abs(np.asarray(fit["capacities"]) / truth_capacities - 1.)
        transport_holdout = excursion_metrics(states[indices[:2]][:, holdmask], truth[indices[:2]][:, holdmask])
        result = {"case": case, "method": method, "label": label, "learned_capacities": fit["capacities"],
                  "relative_parameter_error": errors.tolist(), "conditional_log_jacobian_rank": fit["conditional_log_jacobian_rank"],
                  "multistart_max_capacity_spread": fit["multistart_max_capacity_spread"], "at_bound": any(fit["at_bound"]),
                  "transport_holdout_excursion_nrmse": dict(zip(OBSERVED_POOLS[:2], transport_holdout.tolist())),
                  "numerical_checks": numerical, "reconstruction_checks": meta}
        results.append(result)
        for period, mask in (("training", trainmask), ("holdout", holdmask)):
            state_errors = excursion_metrics(states[:113, mask], truth[:113, mask])
            flux_errors = np.sqrt(np.mean((parts["effective"][:, mask] - truth_parts["effective"][:, mask])**2, axis=1)) / np.maximum(np.sqrt(np.mean(truth_parts["effective"][:, mask]**2, axis=1)), 1e-6)
            metric_rows.extend({"label": label, "period": period, "kind": "concentration", "name": pool, "normalized_rmse": float(state_errors[i])}
                                for i, pool in enumerate(names[:113]))
            metric_rows.extend({"label": label, "period": period, "kind": "executed_flux", "name": r, "normalized_rmse": float(flux_errors[i])}
                                for i, r in enumerate(REACTIONS))
        write_json(out / "partial_results.json", results)
    unchanged = {path: file_hash(path) == digest for path, digest in hashes.items()}
    if not all(unchanged.values()):
        raise ValueError("inputs changed during the benchmark")
    limits = design["synthetic_recovery_checks"]
    oracle = results[0]
    dense_results = [row for row in results if row["case"] == "dense_clean"]
    checks = {"all_replays_numerically_pass": truth_numerical["passes"] and all(row["numerical_checks"]["passes"] for row in results),
              "oracle_parameter_recovery_pass": max(oracle["relative_parameter_error"]) <= limits["oracle_max_relative_parameter_error"],
              "dense_clean_parameter_recovery_by_method": {row["method"]: max(row["relative_parameter_error"]) <= limits["dense_clean_max_relative_parameter_error"] for row in dense_results},
              "dense_clean_holdout_by_method": {row["method"]: max(row["transport_holdout_excursion_nrmse"].values()) <= limits["dense_clean_max_transport_holdout_excursion_nrmse"] for row in dense_results}}
    summary = {"status": "completed_synthetic_benchmark", "input_hashes_unchanged": all(unchanged.values()),
               "learned_parameter_names": list(PARAMETERS), "truth_capacities": truth_capacities.tolist(),
               "fit_count": len(results), "continuous_ODE_replay_count": 2*(1+len(results)), "synthetic_checks": checks,
               "results": results, "teacher_diagnostics": teachers, "biological_calibration_allowed": False,
               "global_model_promotion_allowed": False, "global_kinetic_identifiability_established": False,
               "noise_replicates_are_biological_replicates": False,
               "limitations": ["same-family synthetic truth", "only two capacities with fixed affinities and full known ICs",
                               "four concentration pools needed to reconstruct kinetic inputs", "conditional Jacobian rank is not global identifiability",
                               "dense noise one realization and sparse noise three realizations, not uncertainty intervals",
                               "does not test every historical optimizer or the ML warm-start"]}
    pd.DataFrame(metric_rows).to_csv(out / "trajectory_and_flux_metrics.csv", index=False)
    write_json(out / "summary.json", summary)
    plot_results(out, results, metric_rows, evaluation_time, truth, truth_parts, names, split)
    report = ["# Synthetic FLA recovery benchmark", "", "This is software validation, not biological calibration or kinetic promotion.", "",
              f"Training J1-J{split:g}; continuous held-out prediction J{split:g}-J46. Only synthetic concentrations are targets.",
              "Other kinetics, full initial state, network and reaction-consistent availability threshold are fixed.", "",
              "The learner uses four observed pools (EGLC, ELAC, GLC, LAC). Only the oracle receives exact synthetic states/fluxes.",
              "PCHIP teachers and executed kernel rates are production components; the positive least-squares recovery adapter is benchmark-specific.", "",
              "| Case | Method | VEGLC error (%) | VELAC error (%) | EGLC holdout nRMSE | ELAC holdout nRMSE | Numerical pass |",
              "|---|---|---:|---:|---:|---:|---|"]
    for row in results:
        report.append(f"| {row['case']} | {row['method']} | {100*row['relative_parameter_error'][0]:.4g} | {100*row['relative_parameter_error'][1]:.4g} | {row['transport_holdout_excursion_nrmse']['EGLC']:.4g} | {row['transport_holdout_excursion_nrmse']['ELAC']:.4g} | {row['numerical_checks']['passes']} |")
    report += ["", "## Interpretation boundaries", "", "Recovery criteria are predeclared synthetic engineering checks, not experimental acceptance limits.",
               "The two methods reuse the same observations; their errors are correlated and must not be treated as independent evidence.",
               "Integrated targets avoid concentration differentiation, but their kinetic basis still interpolates GLC/LAC/EGLC/ELAC.",
               "Do not interpret a sparse/noisy failure as whole-model infeasibility or a dense pass as biological validity.",
               "The biological readiness contract and the prepared 38 coupled energy replays remain unchanged and blocked.", "",
               "Synthetic checks: `summary.json`. All 113 concentration metrics: `trajectory_and_flux_metrics.csv`.",
               "Raw accepted solver states, native/executed rates and availability factors are preserved; no output clipping or reset."]
    (out / "decision_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    write_json(out / "final_verification.json", {"verified_at": datetime.now(timezone.utc).isoformat(), "input_hash_checks": unchanged,
               "input_hashes_unchanged": all(unchanged.values()), "completed_fit_count": len(results),
               "continuous_ODE_replay_count": 2*(len(results)+1), "biological_contract_changed": False,
               "experimental_calibration_performed": False, "parameters_promoted": False})
    print(json.dumps({"output": str(out), "synthetic_checks": checks}), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    run(args.config.resolve(), args.out.resolve())


if __name__ == "__main__":
    main()
