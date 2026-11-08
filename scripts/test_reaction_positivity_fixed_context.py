"""Compare legacy and opt-in reaction positivity without changing kinetics."""

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
from equadiff_brodbar import (
    BRODBAR_METABOLITE_MAP, MODEL_NETWORK_VERSION, NONEG_THRESHOLD,
    NUM_BASE_METABOLITES, equadiff_brodbar,
)
from fla_balance_audit import accepted_step_quadrature, integrate_intervals
from flux_visualization import FluxTracker
from reaction_positivity import REACTION_POSITIVITY_VERSION, rbc_reaction_matrix

DEFAULT_SOURCE = ROOT / "output/ppp_numerical_audit_2026_10_05"
DEFAULT_OUT = ROOT / "output/reaction_positivity_fixed_2026_10_05_roundtrip"
HORIZONS = (3.0, 10.0, 46.0)
SOLVERS = {"standard": (3e-4, 1e-6), "strict": (1e-7, 1e-9)}
GROUPS = {"ATP_ADP_AMP": ("ATP", "ADP", "AMP"), "NAD_NADH": ("NAD", "NADH"),
          "NADP_NADPH": ("NADP", "NADPH")}
POLICY = {
    "minimum_raw_state_mM": -1e-10,
    "closure_tolerance_mM_per_day": 1e-7,
    "quadrature_orders": [4, 8],
    "quadrature_absolute_tolerance_mM": 1e-6,
    "quadrature_relative_tolerance": 1e-3,
    "solver_absolute_tolerance_mM": 1e-5,
    "solver_relative_tolerance": 0.01,
    "maximum_quadrature_nodes": 150000,
    "availability_threshold_mM": NONEG_THRESHOLD,
}


def read_exact_initial_snapshot(initial_path, accepted_path):
    initial = pd.read_csv(initial_path, float_precision="round_trip")
    accepted = np.load(accepted_path)
    if accepted["time"][0] != 1.0 or not np.array_equal(
        initial.initial_value.to_numpy(dtype=float), accepted["states"][:, 0]
    ):
        raise ValueError("serialized initialization must exactly match the archived binary day-1 state")
    return initial


def load_context(source):
    contract = json.loads((source / "preregistered_contract.json").read_text())
    for name, key in (("fixed_parameters.json", "fixed_parameter_sha256"),
                      ("fixed_initial_state.csv", "initial_state_sha256")):
        if file_hash(source / name) != contract[key]:
            raise ValueError(f"frozen snapshot hash mismatch: {name}")
    params = json.loads((source / "fixed_parameters.json").read_text())
    initial = read_exact_initial_snapshot(source / "fixed_initial_state.csv",
                                         source / "strict/accepted_solver_states.npz")
    x0 = initial.initial_value.to_numpy(dtype=float)
    names = tuple(initial.pool)
    if (len(x0) != 114 or not np.all(np.isfinite(x0)) or np.any(x0[:113] < 0.0)
            or names[:113] != rbc_reaction_matrix()[0]):
        raise ValueError("frozen initialization is not the expected nonnegative context")
    data_path = Path(contract["source_data"])
    if file_hash(data_path) != contract["input_sha256"][str(data_path)]:
        raise ValueError("reference table changed since the frozen audit")
    frame = pd.read_excel(data_path, engine="openpyxl")
    times = np.asarray(frame.columns[1:], dtype=float)
    if not np.all(np.isfinite(times)) or np.any(np.diff(times) <= 0) or (times[0], times[-1]) != (1.0, 46.0):
        raise ValueError("reference times must span J1-J46 without duplicates")
    curves = {}
    for row in frame.itertuples(index=False, name=None):
        name, values = str(row[0]).strip().upper(), np.asarray(row[1:], dtype=float)
        if name in BRODBAR_METABOLITE_MAP and BRODBAR_METABOLITE_MAP[name] < 113:
            if name in curves or not np.all(np.isfinite(values)):
                raise ValueError(f"invalid reference row: {name}")
            curves[name] = values
    for name in ("ATP", "ADP", "AMP", "GLC", "LAC", "EGLC", "ELAC", "G6P", "GO6P", "B23PG"):
        if name not in curves:
            raise ValueError(f"missing protected reference: {name}")
    return x0, params, names, times, curves, data_path


def check_legacy_parity(source, params):
    cached = pd.read_csv(source / "strict/accepted_solution_replay.csv")
    errors = []
    pools = [name for name in BRODBAR_METABOLITE_MAP if f"{name}_executed" in cached]
    accepted = np.load(source / "strict/accepted_solver_states.npz")
    for index in np.linspace(0, accepted["time"].size - 1, 24, dtype=int):
        day = float(accepted["time"][index])
        row = cached.loc[cached.time_day.sub(day).abs() < 1e-12]
        if len(row) != 1:
            raise ValueError("previous accepted solver node absent or ambiguous in replay")
        derivative = equadiff_brodbar(day, accepted["states"][:, index].copy(), custom_params=params)
        errors += [abs(float(derivative[BRODBAR_METABOLITE_MAP[pool]]) - float(row.iloc[0][f"{pool}_executed"]))
                   for pool in pools]
    maximum = float(max(errors))
    if maximum > 1e-10:
        raise ValueError("default legacy RHS changed on archived accepted states")
    return {"maximum_saved_state_rhs_difference_mM_per_day": maximum, "state_count": 24,
            "compared_pool_count": len(pools), "passes": True}


def boundary_checks(source, x0, params, *, threshold=None):
    archive = np.load(source / "strict/accepted_solver_states.npz")
    tests = [("initial", 1.0, x0.copy())]
    for name in ("B13PG", "ADP"):
        index = BRODBAR_METABOLITE_MAP[name]
        worst = int(np.argmin(archive["states"][index]))
        # Construct a nonnegative boundary probe; never clip integrated outputs.
        probe = archive["states"][:, worst].copy()
        probe[:113] = np.maximum(probe[:113], 0.0)
        tests.append((f"archived_{name}_depleted_nonnegative_probe", float(archive["time"][worst]), probe))
    rows = []
    for label, day, base in tests:
        for pool, index in sorted(BRODBAR_METABOLITE_MAP.items(), key=lambda item: item[1]):
            if index >= 113:
                continue
            x = base.copy()
            x[index] = 0.0
            audit = {}
            legacy = equadiff_brodbar(day, x.copy(), custom_params=params)
            limited = equadiff_brodbar(day, x.copy(), custom_params=params,
                                      positivity_policy="reaction_consistent", numerical_audit=audit,
                                      reaction_availability_threshold=threshold)
            rows.append({"probe": label, "pool": pool, "time_day": day,
                         "legacy_boundary_derivative_mM_per_day": float(legacy[index]),
                         "consistent_boundary_derivative_mM_per_day": float(limited[index]),
                         "passes_boundary_invariance": bool(limited[index] >= -1e-12)})
    if not all(row["passes_boundary_invariance"] for row in rows):
        raise ValueError("reaction-consistent boundary invariance failed; no replay launched")
    return pd.DataFrame(rows)


def replay(time, states, params, policy, reactions, matrix, *, threshold=None):
    tracker, native, factors, executed = FluxTracker(), [], [], []
    for day, x in zip(time, states.T):
        audit = {}
        derivative = equadiff_brodbar(float(day), x.copy(), custom_params=params,
                                     positivity_policy=policy, numerical_audit=audit, flux_tracker=tracker,
                                     reaction_availability_threshold=threshold)
        executed.append(derivative[:113])
        if policy == "reaction_consistent":
            native.append([audit["raw_fluxes"][name] for name in reactions])
            factors.append([audit["availability_factors"][name] for name in reactions])
    missing = set(reactions).difference(tracker.fluxes)
    if missing:
        raise ValueError(f"missing replay fluxes: {sorted(missing)}")
    effective = np.asarray([tracker.fluxes[name] for name in reactions])
    native = np.asarray(native).T if native else effective.copy()
    factors = np.asarray(factors).T if factors else np.ones_like(effective)
    executed = np.asarray(executed).T
    if not all(np.all(np.isfinite(value)) for value in (native, effective, executed, factors)):
        raise ValueError("nonfinite accepted-state replay")
    return {
        "native_flux": native, "effective_flux": effective,
        "reaction_flux_change": effective - native, "absolute_reaction_flux_change": np.abs(effective - native),
        "native_balance": matrix @ native, "effective_balance": matrix @ effective,
        "reaction_consistent_rate_change": matrix @ (effective - native),
        "executed": executed, "nonreaction_residual": executed - matrix @ effective,
        "absolute_nonreaction_residual": np.abs(executed - matrix @ effective),
        "availability_factors": factors,
    }


def predictive_metrics(solution, times, curves):
    mask = (times > 1.0) & (times <= solution.t[-1])
    rows = []
    for name, values in curves.items():
        if name in {"B13PG", "P2G"} or not np.any(mask):
            continue
        actual = solution.sol(times[mask])[BRODBAR_METABOLITE_MAP[name]]
        reference = values[mask]
        scale = max(float(np.mean(np.abs(reference))), 0.01)
        rows.append({"pool": name, "nrmse_postinitial": float(np.sqrt(np.mean((actual - reference)**2)) / scale),
                     "observation_count": int(np.count_nonzero(mask)),
                     "last_observed_day": float(times[mask][-1]), "model_at_last_observed_mM": float(actual[-1]),
                     "reference_at_last_observed_mM": float(reference[-1]),
                     "absolute_last_observed_error_mM": float(abs(actual[-1] - reference[-1]))})
    return pd.DataFrame(rows, columns=["pool", "nrmse_postinitial", "observation_count", "last_observed_day",
        "model_at_last_observed_mM", "reference_at_last_observed_mM", "absolute_last_observed_error_mM"])


def audit_case(solution, params, policy, end, out_dir, times, curves, names, reactions, matrix, invariants, *,
               threshold=None, include_reaction_quadrature=False):
    boundaries = np.unique(np.r_[times[(times >= 1.0) & (times <= end)], [1.0, end],
                                 [day for day in HORIZONS if day <= end]])
    sample = np.unique(np.r_[solution.t, boundaries, np.linspace(1.0, end, 501),
                             1.0 + np.geomspace(1e-9, min(2.0, end - 1.0), 101)])
    states = solution.sol(sample)
    parts = replay(sample, states, params, policy, reactions, matrix, threshold=threshold)
    frame = {"time_day": sample, **{name: states[index] for index, name in enumerate(names)}}
    for pool in ("B13PG", "ATP", "ADP", "GO6P", "G6P", "F6P"):
        index = BRODBAR_METABOLITE_MAP[pool]
        for key in ("native_balance", "effective_balance", "executed", "nonreaction_residual"):
            frame[f"{pool}_{key}"] = parts[key][index]
    pd.DataFrame(frame).to_csv(out_dir / "accepted_solution_replay.csv", index=False)
    np.savez_compressed(out_dir / "accepted_solver_states.npz", time=solution.t, states=solution.y)
    keys = ("native_flux", "effective_flux", "reaction_flux_change", "absolute_reaction_flux_change",
            "native_balance", "effective_balance", "reaction_consistent_rate_change", "executed",
            "nonreaction_residual", "absolute_nonreaction_residual")
    integrals, stats = {}, {}
    for order in (4, 8):
        grid = accepted_step_quadrature(solution.t, boundaries, order=order)
        if grid.nodes.size > POLICY["maximum_quadrature_nodes"]:
            raise ValueError("predeclared quadrature node budget exceeded")
        values = replay(grid.nodes, solution.sol(grid.nodes), params, policy, reactions, matrix, threshold=threshold)
        integrals[order] = {key: integrate_intervals(values[key], grid) for key in keys}
        stats[order] = {"node_count": grid.nodes.size,
                       "max_effective_closure_error_mM_per_day": float(np.max(np.abs(values["nonreaction_residual"]))),
                       "minimum_dense_state_mM": float(np.min(solution.sol(grid.nodes)[:113]))}
    fine, coarse = integrals[8], integrals[4]
    convergence = []
    for key in ("effective_balance", "executed", "nonreaction_residual", "reaction_consistent_rate_change"):
        differences = np.abs(fine[key] - coarse[key])
        allowance = 1e-6 + 1e-3 * np.abs(fine[key])
        for index, pool in enumerate(names[:113]):
            convergence.append({"pool": pool, "quantity": key, "passes": bool(np.all(differences[index] <= allowance[index])),
                                "maximum_order4_order8_difference_mM": float(np.max(differences[index]))})
    pd.DataFrame(convergence).to_csv(out_dir / "quadrature_convergence.csv", index=False)
    reaction_convergence = []
    if include_reaction_quadrature:
        for key in ("native_flux", "effective_flux", "absolute_reaction_flux_change"):
            differences = np.abs(fine[key] - coarse[key])
            allowance = POLICY["quadrature_absolute_tolerance_mM"] + POLICY["quadrature_relative_tolerance"] * np.abs(fine[key])
            for index, reaction in enumerate(reactions):
                reaction_convergence.append({"reaction": reaction, "quantity": key,
                    "passes": bool(np.all(differences[index] <= allowance[index])),
                    "maximum_order4_order8_difference_mM": float(np.max(differences[index]))})
        pd.DataFrame(reaction_convergence).to_csv(out_dir / "reaction_quadrature_convergence.csv", index=False)
    np.savez_compressed(out_dir / "quadrature_integrals.npz", boundaries=boundaries,
                        pool_names=names[:113], reaction_names=reactions, **fine)
    delta = solution.sol(end)[:113] - solution.sol(1.0)[:113]
    sums = {key: value.sum(axis=1) for key, value in fine.items()}
    budgets = []
    for pool, indices in [*[(name, [index]) for index, name in enumerate(names[:113])],
                          *[(group, [BRODBAR_METABOLITE_MAP[name] for name in members]) for group, members in GROUPS.items()]]:
        row = {"pool": pool, "state_change_mM": float(delta[indices].sum())}
        row.update({f"{key}_integral_mM": float(sums[key][indices].sum()) for key in keys if "flux" not in key})
        row["solver_integral_residual_mM"] = row["state_change_mM"] - row["executed_integral_mM"]
        budgets.append(row)
    budgets = pd.DataFrame(budgets)
    budgets.to_csv(out_dir / "numerical_budgets.csv", index=False)
    pd.DataFrame({"reaction": reactions, **{f"{key}_integral_mM": sums[key] for key in keys if "flux" in key},
                  "minimum_report_grid_availability_factor": parts["availability_factors"].min(axis=1)}).to_csv(
                      out_dir / "reaction_budgets.csv", index=False)
    metrics = predictive_metrics(solution, times, curves)
    metrics.to_csv(out_dir / "predictive_metrics.csv", index=False)
    minimum = min(float(np.min(solution.y[:113])), float(np.min(states[:113])),
                  *(value["minimum_dense_state_mM"] for value in stats.values()))
    closure = max(float(np.max(np.abs(parts["nonreaction_residual"]))),
                  *(value["max_effective_closure_error_mM_per_day"] for value in stats.values()))
    result = {
        "positivity_policy": policy, "end_day": end, "accepted_step_count": len(solution.t) - 1,
        "nfev": solution.nfev, "njev": solution.njev, "nlu": solution.nlu,
        "minimum_raw_accepted_state_mM": float(np.min(solution.y[:113])),
        "minimum_raw_dense_state_mM": minimum,
        "negative_accepted_sample_count": int(np.count_nonzero(solution.y[:113] < 0)),
        "negativity_beyond_tolerance": bool(minimum < POLICY["minimum_raw_state_mM"]),
        "max_effective_closure_error_mM_per_day": closure,
        "max_executed_left_nullspace_residual_mM_per_day": float(np.max(np.abs(invariants @ parts["executed"]))),
        "max_integrated_solver_residual_mM": float(budgets.solver_integral_residual_mM.abs().max()),
        "quadrature": {str(order): stat for order, stat in stats.items()},
        "failed_pool_quantity_quadrature_checks": sum(not row["passes"] for row in convergence),
        "reaction_quadrature_checked": include_reaction_quadrature,
        "failed_reaction_quantity_quadrature_checks": sum(not row["passes"] for row in reaction_convergence)
            if include_reaction_quadrature else None,
        "panel_metric": "postinitial reference points only; scale=max(mean(abs(reference)),0.01 mM)",
        "postinitial_panel_count": len(metrics),
        "postinitial_panel_mean_nrmse": float(metrics.nrmse_postinitial.mean()) if len(metrics) else None,
        "postinitial_panel_median_nrmse": float(metrics.nrmse_postinitial.median()) if len(metrics) else None,
        "boundary_and_closure_pass": bool(minimum >= POLICY["minimum_raw_state_mM"] and closure <= POLICY["closure_tolerance_mM_per_day"]),
        "numerical_integrity_pass": bool(minimum >= POLICY["minimum_raw_state_mM"] and closure <= POLICY["closure_tolerance_mM_per_day"]
                                         and all(row["passes"] for row in convergence)
                                         and all(row["passes"] for row in reaction_convergence)),
        "parameters_promoted": False,
    }
    return result, budgets, metrics


def plot_full_horizon(out_dir, times, curves):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 3, figsize=(12, 7), constrained_layout=True)
    panels = ("ATP", "ADP", "B13PG", "GO6P", "GLC", "ELAC")
    frames = {policy: pd.read_csv(out_dir / f"J46_{policy}_strict/accepted_solution_replay.csv")
              for policy in ("legacy", "reaction_consistent")}
    for ax, pool in zip(axes.flat, panels):
        for policy, color, label in (("legacy", "#b54d62", "Legacy pool damping"),
                                     ("reaction_consistent", "#16847b", "Reaction-consistent (diagnostic)")):
            frame = frames[policy]
            ax.plot(frame.time_day, frame[pool], color=color, label=label, linewidth=1.7)
        if pool != "B13PG":
            ax.scatter(times, curves[pool], color="#222222", s=22, label="Local reference table", zorder=3)
        ax.axhline(0, color="#888888", linewidth=0.6)
        ax.set(title=pool, xlabel="Model day", ylabel="Concentration (mM)")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=0.15)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=3, frameon=False)
    fig.suptitle("Fixed kinetics and initialization: numerical positivity is not calibration", fontsize=14)
    fig.savefig(out_dir / "fixed_context_comparison.png", dpi=180)
    fig.savefig(out_dir / "fixed_context_comparison.pdf")
    plt.close(fig)


def run(source, out_dir):
    if (out_dir / "summary.json").exists():
        raise FileExistsError("completed diagnostic exists; use a new --out-dir")
    out_dir.mkdir(parents=True, exist_ok=True)
    x0, params, names, times, curves, data_path = load_context(source)
    sam_mode = params.get("sam_adenylate_stoichiometry", "biochemical_transfer")
    _, reactions, matrix = rbc_reaction_matrix(sam_mode)
    u, singular, _ = np.linalg.svd(matrix, full_matrices=True)
    rank = int(np.count_nonzero(singular > singular[0] * 1e-10))
    invariants = u[:, rank:].T
    for file in ("fixed_parameters.json", "fixed_initial_state.csv"):
        shutil.copyfile(source / file, out_dir / file)
    inputs = [source / "preregistered_contract.json", source / "strict/accepted_solver_states.npz",
              source / "strict/accepted_solution_replay.csv", data_path, ROOT / "src/equadiff_brodbar.py",
              ROOT / "src/reaction_positivity.py", ROOT / "src/rbc_stoichiometry.py",
              ROOT / "src/fla_balance_audit.py", ROOT / "scripts/audit_ppp_constraints_and_numerics.py", Path(__file__)]
    write_json(out_dir / "preregistered_contract.json", {
        "source_context": str(source.resolve()), "context_is_unpromoted": True,
        "model_network_version": MODEL_NETWORK_VERSION, "numerical_policy_version": REACTION_POSITIVITY_VERSION,
        "input_sha256": {str(path.resolve()): file_hash(path) for path in inputs},
        "fixed_parameter_sha256": file_hash(out_dir / "fixed_parameters.json"),
        "initial_state_sha256": file_hash(out_dir / "fixed_initial_state.csv"),
        "initial_state_matches_archived_binary_exactly": True,
        "csv_float_precision": "round_trip",
        "horizons_day": HORIZONS, "solvers": SOLVERS, "numerical_policy": POLICY,
        "optimization_performed": False, "observation_resets": False, "curve_fit_strength": 0.0,
        "output_clipping": False, "parameters_promoted": False,
        "kinetic_law_change": "net flux multiplied by minimum signed-consumer availability; not gross reversible exchange",
        "numerical_vs_predictive_contract": "numerical integrity does not imply predictive calibration; absolute accuracy limits unresolved",
    })
    parity = check_legacy_parity(source, params)
    boundaries = boundary_checks(source, x0, params)
    boundaries.to_csv(out_dir / "zero_boundary_checks.csv", index=False)
    write_json(out_dir / "legacy_compatibility.json", parity)
    print(f"Legacy parity verified; {len(boundaries)} zero-boundary checks passed", flush=True)
    cases, all_budgets, all_metrics = {}, [], []
    for end in HORIZONS:
        for policy in ("legacy", "reaction_consistent"):
            for solver, (rtol, atol) in SOLVERS.items():
                label = f"J{int(end)}_{policy}_{solver}"
                begin = perf_counter()
                print(f"[{label}] fixed-context BDF replay", flush=True)
                solution = solve_ivp(lambda day, values: equadiff_brodbar(float(day), values, custom_params=params,
                    positivity_policy=policy), (1.0, end), x0.copy(), method="BDF", rtol=rtol, atol=atol, dense_output=True)
                if not solution.success or not np.all(np.isfinite(solution.y)):
                    raise ValueError(f"{label} solver failed: {solution.message}")
                case_dir = out_dir / label
                case_dir.mkdir(exist_ok=True)
                result, budgets, metrics = audit_case(solution, params, policy, end, case_dir, times, curves,
                                                      names, reactions, matrix, invariants)
                result.update(solver=solver, rtol=rtol, atol=atol, elapsed_seconds=perf_counter() - begin)
                write_json(case_dir / "summary.json", result)
                cases[label] = result
                for frame, destination in ((budgets, all_budgets), (metrics, all_metrics)):
                    frame = frame.copy()
                    frame["case"], frame["end_day"], frame["policy"], frame["solver"] = label, end, policy, solver
                    destination.append(frame)
                print(f"[{label}] complete in {perf_counter()-begin:.1f}s; min={result['minimum_raw_dense_state_mM']:.3g}; quadrature failures={result['failed_pool_quantity_quadrature_checks']}", flush=True)
    budgets = pd.concat(all_budgets, ignore_index=True)
    metrics = pd.concat(all_metrics, ignore_index=True)
    budgets.to_csv(out_dir / "all_numerical_budgets.csv", index=False)
    metrics.to_csv(out_dir / "all_predictive_metrics.csv", index=False)
    comparison = budgets.loc[budgets.solver == "standard"].merge(budgets.loc[budgets.solver == "strict"],
        on=["pool", "end_day", "policy"], suffixes=("_standard", "_strict"))
    for key in ("state_change_mM", "effective_balance_integral_mM", "nonreaction_residual_integral_mM",
                "reaction_consistent_rate_change_integral_mM"):
        difference = np.abs(comparison[f"{key}_standard"] - comparison[f"{key}_strict"])
        comparison[f"{key}_solver_invariant"] = difference <= (1e-5 + 0.01 * np.abs(comparison[f"{key}_strict"]))
        comparison[f"{key}_solver_difference_mM"] = difference
    comparison.to_csv(out_dir / "standard_strict_comparison.csv", index=False)
    consistent = [value for value in cases.values() if value["positivity_policy"] == "reaction_consistent"]
    result = {"cases": cases, "legacy_parity": parity, "zero_boundary_checks_passed": len(boundaries),
              "matrix_rank": rank, "left_nullspace_dimension": len(invariants),
              "consistent_all_numerical_integrity_pass": all(value["numerical_integrity_pass"] for value in consistent),
              "optimization_performed": False, "parameters_promoted": False,
              "classification": "fixed_context_numerical_policy_diagnostic",
              "next_execution": "review positivity/convergence and predictive changes before selecting an energy-block method"}
    write_json(out_dir / "summary.json", result)
    plot_full_horizon(out_dir, times, curves)
    lines = ["# Reaction-consistent positivity at frozen kinetics", "",
             "This is an opt-in numerical/kinetic-rate diagnostic. The default legacy policy is unchanged. No optimization, observation resets or promotion.", "",
             f"Archived legacy RHS parity: maximum difference {parity['maximum_saved_state_rhs_difference_mM_per_day']:.3g} mM/day; {len(boundaries)} zero-boundary tests passed.", "",
             "One factor multiplies every stoichiometric contribution of a signed net reaction. Consumers are selected from the sign of the net rate; the factor is min(clip(x_raw/0.001 mM,0,1)) over consumers. Native kinetic floors remain, but positive floored values do not determine availability. Forward/reverse gross fluxes are not reconstructed.", "",
             "Tracked rates in reaction-consistent mode are executed limited rates. Native rates and their changes are exported separately; S(v_limited-v_native) is not an independent numerical source.", "",
             "| Case | Raw minimum, accepted/dense (mM) | Nonreaction RHS residual (mM/day) | Quadrature failures | Numerical integrity passes |",
             "|---|---:|---:|---:|---|"]
    for label, value in cases.items():
        lines.append(f"| {label} | {value['minimum_raw_dense_state_mM']:.6g} | {value['max_effective_closure_error_mM_per_day']:.6g} | {value['failed_pool_quantity_quadrature_checks']} | {value['numerical_integrity_pass']} |")
    lines += ["", "All measured-panel metrics exclude initial observations, B13PG and P2G duplicate aliases. J1-J3 has no postinitial reference point; no predictive nRMSE is invented for that horizon.", "",
              "Absolute predictive thresholds and measurement provenance are still unresolved. A numerical pass does not promote the context or demonstrate successful FLA calibration.", "",
              "See full parameters/state hashes, raw accepted arrays, native/effective reaction budgets, quadrature convergence, solver comparisons and postinitial predictive metrics. Historical outputs are preserved."]
    (out_dir / "decision_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(out_dir / "decision_report.md"), "numerical_integrity": result["consistent_all_numerical_integrity_pass"]}), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-audit", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    run(args.source_audit, args.out_dir)
