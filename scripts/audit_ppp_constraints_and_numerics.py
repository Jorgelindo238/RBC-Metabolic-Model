"""Rebuild PPP/shunt constraints and audit numerical corrections at fixed kinetics."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp
from scipy.interpolate import PchipInterpolator

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "scripts"):
    sys.path.insert(0, str(path))

import rbc_stoichiometry as stoich
from equadiff_brodbar import (
    BRODBAR_METABOLITE_MAP, MAX_DERIVATIVE, MIN_CONCENTRATION,
    MODEL_NETWORK_VERSION, NONEG_THRESHOLD, NUM_BASE_METABOLITES,
    equadiff_brodbar,
)
from fla_balance_audit import (
    accepted_step_quadrature, balance_matrix, constraint_observability,
    integrate_intervals, numerical_components,
)
from flux_visualization import FluxTracker

DEFAULT_REFERENCE = ROOT / "Simulations/brodbar/hermes/vampd1_storage_decay_full_ode_J1_J46/summary.json"
DEFAULT_OUT = ROOT / "output/ppp_numerical_audit_2026_10_05"
PPP_POOLS = ("G6P", "GL6P", "GO6P", "RU5P", "R5P", "X5P", "E4P", "S7P", "GA3P", "F6P")
SHUNT_POOLS = ("B13PG", "B23PG", "P3G")
MEASURED_POOLS = ("G6P", "GO6P", "F6P", "B23PG")
AUDIT_POOLS = PPP_POOLS + SHUNT_POOLS + ("ATP", "ADP", "AMP", "NAD", "NADH", "NADP", "NADPH", "GTP", "GDP")
GROUPS = {
    "ATP_ADP_AMP": ("ATP", "ADP", "AMP"),
    "NAD_NADH": ("NAD", "NADH"),
    "NADP_NADPH": ("NADP", "NADPH"),
    "GTP_GDP": ("GTP", "GDP"),
}
REMOVED_BY_LEGACY_PARSER = frozenset({"V6PGD", "V23DPGP"})
POLICY = {
    "pointwise_effective_closure_tolerance_mM_per_day": 1e-7,
    "raw_closure_tolerance_mM_per_day": 1e-7,
    "minimum_raw_state_mM": -1e-10,
    "quadrature_orders": [4, 8],
    "quadrature_absolute_tolerance_mM": 1e-6,
    "quadrature_relative_tolerance": 1e-3,
    "solver_budget_absolute_tolerance_mM": 1e-5,
    "solver_budget_relative_tolerance": 0.01,
}


def write_json(path, payload):
    Path(path).write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_panel():
    path = ROOT / "src/Data_Bordbar_et_al_exp.xlsx"
    frame = pd.read_excel(path, engine="openpyxl")
    times = np.asarray(frame.columns[1:], dtype=float)
    names = frame.iloc[:, 0].astype(str).str.strip().str.upper()
    curves = {}
    for pool in (*MEASURED_POOLS, "ATP", "ADP", "AMP"):
        rows = frame.loc[names == pool].iloc[:, 1:].to_numpy(dtype=float)
        if rows.shape != (1, times.size) or not np.all(np.isfinite(rows)):
            raise ValueError(f"invalid or duplicated reference row for {pool}")
        curves[pool] = rows[0]
    if times[0] != 1.0 or times[-1] != 46.0 or np.any(np.diff(times) <= 0.0):
        raise ValueError("reference must cover J1-J46 at strictly increasing times")
    return times, curves, path


def _fixed_context(reference):
    from screen_amp_nucleotidase_fixed_purine import _build_anchor

    summary = json.loads(reference.read_text(encoding="utf-8"))
    anchor_path = Path(summary["source_anchor"])
    state, params, seed_path, _ = _build_anchor(anchor_path)
    params.update(summary["candidate_params"])
    params.update({"purine_structure_mode": "legacy", "vmax_VAMP_NT": 0.0})
    cached_path = reference.parent / "J1_J46_timeseries.csv"
    cached = pd.read_csv(cached_path)
    first = cached.loc[(cached.candidate == "VAMPD1_storage_decay") & (cached.time_day == 1.0)]
    if len(first) != 1:
        raise ValueError("cached diagnostic context must contain one initial row")
    cached_initial = np.asarray([
        first.iloc[0][name]
        for name, _ in sorted(BRODBAR_METABOLITE_MAP.items(), key=lambda item: item[1])
        if BRODBAR_METABOLITE_MAP[name] < state.size
    ], dtype=float)
    if state.shape != cached_initial.shape or not np.allclose(state, cached_initial, rtol=0.0, atol=1e-12):
        raise ValueError("reconstructed initialization does not match the archived context")
    input_paths = [
        reference, anchor_path, seed_path, cached_path,
        ROOT / "src/Data_Bordbar_et_al_exp.xlsx", ROOT / "src/Initial_conditions_JA_Final.xls",
        ROOT / "Simulations/brodbar/hermes/v6pgd_constrained_transition_refinement_46d/summary.json",
        ROOT / "Simulations/brodbar/hermes/v6pgd_constrained_transition_refinement_46d/diagnostic_candidates.json",
        ROOT / "Simulations/brodbar/hermes/b13pg_constrained_initialization_screen_J1_J10/diagnostic_initializations.json",
        ROOT / "src/equadiff_brodbar.py", ROOT / "src/rbc_stoichiometry.py",
        ROOT / "src/fla_balance_audit.py", Path(__file__),
    ]
    return state, params, {str(path.resolve()): file_hash(path) for path in input_paths}


def rebuild_constraints(out_dir, times, curves):
    pools = PPP_POOLS + SHUNT_POOLS
    reactions = tuple(sorted(stoich.reactions_for_metabolites(pools)))
    full = balance_matrix(pools, reactions, stoich.STOICHIOMETRY)
    legacy = full.copy()
    for reaction in REMOVED_BY_LEGACY_PARSER:
        legacy[:, reactions.index(reaction)] = 0.0
    summaries = {}
    for label, selected_pools in (
        ("PPP_measured_only", MEASURED_POOLS[:3]),
        ("PPP_and_shunt_measured_only", MEASURED_POOLS),
        ("PPP_all_pools_including_latent", PPP_POOLS),
        ("PPP_and_shunt_all_pools_including_latent", pools),
    ):
        indices = [pools.index(pool) for pool in selected_pools]
        summaries[label] = {"pools": selected_pools, "reactions": reactions, "versions": {}}
        for version, matrix in (("legacy_omission_reconstruction", legacy), ("schema_2", full)):
            local = matrix[indices]
            diagnostic = constraint_observability(local)
            null_basis = diagnostic.pop("null_basis")
            columns = diagnostic.pop("individually_identifiable_columns")
            diagnostic["individually_identifiable_reactions"] = [reactions[index] for index in columns]
            diagnostic["represented_reactions"] = [
                reaction for reaction, column in zip(reactions, local.T) if np.any(column != 0.0)
            ]
            diagnostic["interpretation"] = (
                "concentration-balance observability without fixed model fluxes; "
                "latent-row ranks are hypothetical, not measured-data evidence"
            )
            summaries[label]["versions"][version] = diagnostic
            pd.DataFrame(local, index=selected_pools, columns=reactions).rename_axis("pool").to_csv(
                out_dir / f"{label}__{version}__matrix.csv"
            )
            pd.DataFrame(null_basis, index=reactions).rename_axis("reaction").to_csv(
                out_dir / f"{label}__{version}__nullspace.csv"
            )
    pd.DataFrame([
        {
            "pool": pool, "direct_reference_target": pool in MEASURED_POOLS,
            "schema_2_reactions": ",".join(sorted(stoich.reactions_for_metabolites([pool]))),
            "schema_2_reachable_parameter_names": ",".join(sorted(stoich.params_for_metabolites([pool]))),
            "parameters_opened": "",
        }
        for pool in pools
    ]).to_csv(out_dir / "parameter_reachability.csv", index=False)
    dense = np.unique(np.concatenate([times, np.linspace(1.0, 46.0, 901)]))
    pd.DataFrame({
        "time_day": dense,
        **{f"d{pool}_reference_dt_mM_per_day": PchipInterpolator(times, curves[pool]).derivative()(dense)
           for pool in MEASURED_POOLS},
    }).to_csv(out_dir / "measured_net_flux_teachers.csv", index=False)
    pd.DataFrame([
        {"pool": pool, "start_day": float(start), "end_day": float(end),
         "reference_change_mM": float(curves[pool][index + 1] - curves[pool][index]),
         "quantity": "measured_row_net_change_not_individual_reaction", "source_provenance_status": "local_table_unresolved"}
        for pool in MEASURED_POOLS for index, (start, end) in enumerate(zip(times[:-1], times[1:]))
    ]).to_csv(out_dir / "measured_interval_constraints.csv", index=False)
    write_json(out_dir / "structural_constraints.json", summaries)
    return summaries


def _replay(time, states, params, global_matrix, reactions):
    tracker = FluxTracker()
    executed = np.asarray([
        equadiff_brodbar(float(day), state.copy(), custom_params=params,
                         curve_fit_strength=0.0, flux_tracker=tracker)
        for day, state in zip(time, states.T)
    ], dtype=float).T[:NUM_BASE_METABOLITES]
    missing = set(reactions) - set(tracker.fluxes)
    if missing:
        raise ValueError(f"missing tracked reaction fluxes: {sorted(missing)}")
    fluxes = np.asarray([tracker.fluxes[reaction] for reaction in reactions], dtype=float)
    parts = numerical_components(
        states=states[:NUM_BASE_METABOLITES], fluxes=fluxes, executed=executed,
        matrix=global_matrix, minimum_concentration=MIN_CONCENTRATION,
        damping_threshold=NONEG_THRESHOLD, maximum_derivative=MAX_DERIVATIVE,
    )
    parts["executed"] = executed
    return fluxes, parts


def _integrate_replay(solution, boundaries, order, params, matrix, reactions):
    grid = accepted_step_quadrature(solution.t, boundaries, order=order)
    if grid.nodes.size > 150000:
        raise RuntimeError("accepted-step quadrature exceeds the declared 150000-node budget")
    print(f"  quadrature order {order}: {grid.nodes.size} dense-solution nodes", flush=True)
    states = solution.sol(grid.nodes)
    fluxes, parts = _replay(grid.nodes, states, params, matrix, reactions)
    integrals = {name: integrate_intervals(parts[name], grid) for name in (
        "raw", "damping", "clipping", "executed", "total_correction", "unexplained",
    )}
    integrals["absolute_correction"] = integrate_intervals(np.abs(parts["total_correction"]), grid)
    integrals["reaction_flux"] = integrate_intervals(fluxes, grid)
    integrals["correction_L1_by_state"] = integrals["absolute_correction"]
    return integrals, {
        "node_count": grid.nodes.size,
        "max_effective_closure_error_mM_per_day": float(np.max(np.abs(parts["unexplained"]))),
        "max_raw_closure_error_mM_per_day": float(np.max(np.abs(parts["total_correction"]))),
        "minimum_dense_solution_state_mM": float(np.min(states[:NUM_BASE_METABOLITES])),
        "max_clipping_rate_mM_per_day": float(np.max(np.abs(parts["clipping"]))),
    }


def _window_sum(values, boundaries, start, end):
    selected = (boundaries[:-1] >= start) & (boundaries[1:] <= end)
    if not np.any(selected) or boundaries[:-1][selected][0] != start or boundaries[1:][selected][-1] != end:
        raise ValueError("window boundaries must be present in the quadrature partition")
    return np.sum(values[:, selected], axis=1)


def _observed_change(times, values, start, end):
    left, right = np.flatnonzero(times == start), np.flatnonzero(times == end)
    if left.size != 1 or right.size != 1:
        return None
    return float(values[right[0]] - values[left[0]])


def _windows(times):
    return tuple(dict.fromkeys([
        *zip(times[:-1], times[1:]), (1.0, 3.0), (3.0, 10.0), (10.0, 46.0),
        (1.0, 11.0), (11.0, 22.0), (22.0, 46.0), (1.0, 46.0),
    ]))


def run_case(label, solution, params, times, curves, out_dir, matrix, reactions, pool_names):
    boundaries = np.unique(np.concatenate([times, [3.0, 10.0]]))
    inverse = {name: index for index, name in enumerate(pool_names)}
    sample_time = np.unique(np.concatenate([
        solution.t, times, boundaries, np.linspace(1.0, 46.0, 901),
        1.0 + np.geomspace(1e-8, 2.0, 301),
    ]))
    states = solution.sol(sample_time)
    fluxes, parts = _replay(sample_time, states, params, matrix, reactions)
    frame = {"time_day": sample_time}
    for pool in AUDIT_POOLS:
        index = inverse[pool]
        frame[pool] = states[index]
        for key in ("raw", "executed", "damping", "clipping", "unexplained", "input_floor_displacement"):
            frame[f"{pool}_{key}"] = parts[key][index]
    for group, names in GROUPS.items():
        indices = [inverse[name] for name in names]
        frame[group] = np.sum(states[indices], axis=0)
        frame[f"{group}_raw"] = np.sum(parts["raw"][indices], axis=0)
        frame[f"{group}_numerical_correction"] = np.sum(parts["total_correction"][indices], axis=0)
    case_dir = out_dir / label
    case_dir.mkdir(exist_ok=True)
    pd.DataFrame(frame).to_csv(case_dir / "accepted_solution_replay.csv", index=False)
    np.savez_compressed(case_dir / "accepted_solver_states.npz", time=solution.t, states=solution.y)
    coarse, coarse_stats = _integrate_replay(solution, boundaries, 4, params, matrix, reactions)
    fine, fine_stats = _integrate_replay(solution, boundaries, 8, params, matrix, reactions)
    np.savez_compressed(case_dir / "quadrature_integrals.npz", boundaries=boundaries,
                        pool_names=pool_names, reaction_names=reactions, **fine)
    endpoint_states = solution.sol(boundaries)[:NUM_BASE_METABOLITES]
    delta = np.diff(endpoint_states)
    quadrature_rows = []
    for key in ("raw", "damping", "clipping", "total_correction", "executed"):
        error = np.abs(fine[key] - coarse[key])
        allowance = POLICY["quadrature_absolute_tolerance_mM"] + POLICY["quadrature_relative_tolerance"] * np.abs(fine[key])
        for index, pool in enumerate(pool_names):
            quadrature_rows.append({
                "case": label, "pool": pool, "quantity": key,
                "max_order4_order8_difference_mM": float(np.max(error[index])),
                "passes_declared_quadrature_tolerance": bool(np.all(error[index] <= allowance[index])),
            })
    pd.DataFrame(quadrature_rows).to_csv(case_dir / "quadrature_convergence.csv", index=False)
    budget_rows = []
    for start, end in _windows(times):
        selected = (boundaries[:-1] >= start) & (boundaries[1:] <= end)
        budget = {key: _window_sum(values, boundaries, start, end)
                  for key, values in fine.items() if key != "reaction_flux"}
        state_change = np.sum(delta[:, selected], axis=1)
        for pool, indices in [
            *[(pool, [index]) for index, pool in enumerate(pool_names)],
            *[(group, [inverse[name] for name in names]) for group, names in GROUPS.items()],
        ]:
            raw_change = float(np.sum(state_change[indices]))
            values = {key: float(np.sum(value[indices])) for key, value in budget.items()}
            observed = (
                _observed_change(times, curves[pool], start, end) if pool in curves else
                _observed_change(times, sum(curves[name] for name in GROUPS[pool]), start, end)
                if pool == "ATP_ADP_AMP" else None
            )
            budget_rows.append({
                "case": label, "pool": pool, "start_day": float(start), "end_day": float(end),
                "state_change_mM": raw_change, "raw_flux_integral_mM": values["raw"],
                "damping_integral_mM": values["damping"], "clipping_integral_mM": values["clipping"],
                "numerical_correction_integral_mM": values["total_correction"],
                "absolute_member_correction_integral_mM": values["absolute_correction"],
                "executed_derivative_integral_mM": values["executed"],
                "unexplained_integral_mM": values["unexplained"],
                "solver_integral_residual_mM": raw_change - values["executed"],
                "raw_mass_residual_mM": raw_change - values["raw"],
                "reference_change_mM": observed,
                "physical_reference_residual_mM": None if observed is None else observed - values["raw"],
                "implemented_reference_residual_mM": None if observed is None else observed - values["executed"],
            })
    budgets = pd.DataFrame(budget_rows)
    budgets.to_csv(case_dir / "numerical_budgets.csv", index=False)
    conditional_rows = []
    specifications = (
        ("GO6P", ("V6PGD",), "conditional_V6PGD_given_model_VPGLS"),
        ("G6P", ("VG6PDH",), "conditional_VG6PDH_given_model_VHK_VPGI"),
        ("B23PG", ("VDPGM",), "conditional_VDPGM_given_model_V23DPGP"),
        ("F6P", ("VTKL2", "VTAL"), "conditional_sum_VTKL2_VTAL_given_model_VPGI_VPFK"),
    )
    for start, end in _windows(times):
        for pool, unknown_reactions, teacher_name in specifications:
            observed = _observed_change(times, curves[pool], start, end)
            if observed is None:
                continue
            pool_index = inverse[pool]
            coefficients = [stoich.STOICHIOMETRY[reaction][pool] for reaction in unknown_reactions]
            if not np.all(np.asarray(coefficients) == coefficients[0]):
                raise ValueError("conditional sum must have one common stoichiometric coefficient")
            integrated = _window_sum(fine["reaction_flux"], boundaries, start, end)
            unknown = sum(integrated[reactions.index(reaction)] for reaction in unknown_reactions)
            raw_integral = _window_sum(fine["raw"], boundaries, start, end)[pool_index]
            correction = _window_sum(fine["total_correction"], boundaries, start, end)[pool_index]
            known = raw_integral - coefficients[0] * unknown
            required = (observed - known) / coefficients[0]
            conditional_rows.append({
                "case": label, "pool": pool, "teacher": teacher_name,
                "start_day": float(start), "end_day": float(end),
                "reference_change_mM": observed, "known_model_flux_integral_mM": float(known),
                "required_unknown_integral_mM": float(required), "model_unknown_integral_mM": float(unknown),
                "unknown_stoichiometric_coefficient": float(coefficients[0]),
                "model_minus_required_mM": float(unknown - required),
                "numerical_state_correction_mM": float(correction),
                "numerically_explainable_unknown_residual_mM": float(-correction / coefficients[0]),
                "independent_experimental_reaction_teacher": False,
            })
    pd.DataFrame(conditional_rows).to_csv(case_dir / "conditional_integrated_teachers.csv", index=False)
    summary = {
        "solver_rtol": float(solution.audit_rtol), "solver_atol": float(solution.audit_atol),
        "accepted_step_count": len(solution.t) - 1, "nfev": solution.nfev,
        "njev": solution.njev, "nlu": solution.nlu,
        "minimum_accepted_state_mM_before_clipping": float(np.min(solution.y[:NUM_BASE_METABOLITES])),
        "negative_accepted_state_sample_count": int(np.count_nonzero(solution.y[:NUM_BASE_METABOLITES] < 0.0)),
        "report_grid_count": len(sample_time),
        "max_report_grid_effective_closure_error_mM_per_day": float(np.max(np.abs(parts["unexplained"]))),
        "max_report_grid_raw_balance_defect_mM_per_day": float(np.max(np.abs(parts["total_correction"]))),
        "quadrature": {"order4": coarse_stats, "order8": fine_stats,
                       "failed_pool_quantity_count": sum(not row["passes_declared_quadrature_tolerance"] for row in quadrature_rows)},
        "full_horizon_audited_pool_budgets": budgets.loc[
            (budgets.start_day == 1.0) & (budgets.end_day == 46.0) & budgets.pool.isin((*AUDIT_POOLS, *GROUPS))
        ].drop(columns=["reference_change_mM", "physical_reference_residual_mM", "implemented_reference_residual_mM"]).to_dict(orient="records"),
        "raw_balance_gate_passes": bool(max(fine_stats["max_raw_closure_error_mM_per_day"],
            float(np.max(np.abs(parts["total_correction"])))) <= POLICY["raw_closure_tolerance_mM_per_day"]),
    }
    write_json(case_dir / "summary.json", summary)
    return summary, budgets


def run(reference, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    if (out_dir / "summary.json").exists():
        raise FileExistsError("completed audit exists; choose a new --out-dir to preserve it")
    times, curves, data_path = _load_panel()
    state, params, input_hashes = _fixed_context(reference)
    pool_names = tuple(name for name, index in sorted(BRODBAR_METABOLITE_MAP.items(), key=lambda item: item[1]) if index < NUM_BASE_METABOLITES)
    reactions = tuple(sorted(stoich.STOICHIOMETRY))
    matrix = balance_matrix(pool_names, reactions, stoich.STOICHIOMETRY)
    write_json(out_dir / "fixed_parameters.json", params)
    pd.DataFrame({"pool": list(name for name, index in sorted(BRODBAR_METABOLITE_MAP.items(), key=lambda item: item[1]) if index < state.size),
                  "initial_value": state}).to_csv(out_dir / "fixed_initial_state.csv", index=False)
    write_json(out_dir / "preregistered_contract.json", {
        "model_network_version": MODEL_NETWORK_VERSION,
        "stoichiometry_schema_version": stoich.STOICHIOMETRY_SCHEMA_VERSION,
        "fixed_reference_context": "VAMPD1_storage_decay_diagnostic_unpromoted",
        "source_reference": str(reference.resolve()), "input_sha256": input_hashes,
        "fixed_parameter_sha256": file_hash(out_dir / "fixed_parameters.json"),
        "initial_state_sha256": file_hash(out_dir / "fixed_initial_state.csv"),
        "numerical_policy": POLICY, "time_support_day": [1.0, 46.0],
        "curve_fit_strength": 0.0, "observation_resets": False,
        "optimization_performed": False, "parameters_promoted": False,
        "source_provenance_status": "local_reference_table_units_and_primary_endpoints_unresolved",
        "source_data": str(data_path.resolve()),
    })
    structural = rebuild_constraints(out_dir, times, curves)
    summaries, budgets = {}, {}
    for label, rtol, atol in (("standard", 3e-4, 1e-6), ("strict", 1e-7, 1e-9)):
        print(f"[{label}] fixed-context BDF replay J1-J46", flush=True)
        begin = perf_counter()
        solution = solve_ivp(
            lambda day, values: equadiff_brodbar(float(day), values, custom_params=params, curve_fit_strength=0.0),
            (1.0, 46.0), state.copy(), method="BDF", rtol=rtol, atol=atol, dense_output=True,
        )
        if not solution.success or not np.all(np.isfinite(solution.y)):
            raise RuntimeError(f"{label} replay failed: {solution.message}")
        solution.audit_rtol, solution.audit_atol = rtol, atol
        summaries[label], budgets[label] = run_case(
            label, solution, params, times, curves, out_dir, matrix, reactions, pool_names,
        )
        summaries[label]["solve_and_audit_elapsed_seconds"] = perf_counter() - begin
        print(f"[{label}] complete in {perf_counter() - begin:.1f} s", flush=True)
    comparison_keys = ["pool", "start_day", "end_day"]
    comparison = budgets["standard"].merge(budgets["strict"], on=comparison_keys, suffixes=("_standard", "_strict"))
    for quantity in ("numerical_correction_integral_mM", "raw_flux_integral_mM", "state_change_mM"):
        difference = np.abs(comparison[f"{quantity}_standard"] - comparison[f"{quantity}_strict"])
        allowance = POLICY["solver_budget_absolute_tolerance_mM"] + POLICY["solver_budget_relative_tolerance"] * np.abs(comparison[f"{quantity}_strict"])
        comparison[f"{quantity}_absolute_solver_difference"] = difference
        comparison[f"{quantity}_solver_invariant"] = difference <= allowance
    comparison.to_csv(out_dir / "standard_strict_comparison.csv", index=False)
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "optimization_performed": False, "parameters_promoted": False,
        "model_network_version": MODEL_NETWORK_VERSION,
        "stoichiometry_schema_version": stoich.STOICHIOMETRY_SCHEMA_VERSION,
        "cases": summaries, "structural_constraints": structural,
        "numerical_policy": POLICY,
        "classification": "fixed_parameter_diagnostic",
        "limitations": [
            "Derivative and interval targets reuse the same reference observations.",
            "Individual reaction teachers conditioned on simulated fluxes are not independent measurements.",
            "Input-floor displacement is recorded in mM, not integrated as a material source.",
            "Audit covers accepted states and their dense interpolant, not every rejected solver trial.",
            "Numerical budget differences and biological prediction errors are reported separately.",
        ],
        "next_execution": "test a reversible reaction-consistent positivity policy with kinetics frozen, after reviewing solver/quadrature convergence",
    }
    write_json(out_dir / "summary.json", result)
    measured = structural["PPP_and_shunt_measured_only"]["versions"]
    lines = [
        "# PPP and numerical balance audit at fixed kinetics", "",
        "The frozen context is the unpromoted VAMPD1 storage-decay diagnostic. Both runs use identical kinetics and initialization.", "",
        f"Measured PPP/shunt rank: {measured['schema_2']['rank']} of {measured['schema_2']['reaction_count']} reaction columns; nullity {measured['schema_2']['nullity']}.",
        f"Legacy individually identifiable fluxes: {measured['legacy_omission_reconstruction']['individually_identifiable_reactions']}.",
        f"Corrected individually identifiable fluxes: {measured['schema_2']['individually_identifiable_reactions']}.", "",
        "| Case | Max effective RHS error (mM/day) | Max raw defect (mM/day) | Raw accepted-state minimum (mM) | Failed quadrature pool/quantity checks |",
        "|---|---:|---:|---:|---:|",
    ]
    for label, summary in summaries.items():
        lines.append(f"| {label} | {summary['max_report_grid_effective_closure_error_mM_per_day']:.6g} | {summary['max_report_grid_raw_balance_defect_mM_per_day']:.6g} | {summary['minimum_accepted_state_mM_before_clipping']:.6g} | {summary['quadrature']['failed_pool_quantity_count']} |")
    lines += ["", "Full J1-J46 signed numerical corrections:", "", "| Pool/group | Standard (mM) | Strict (mM) | Solver invariant under declared tolerance |", "|---|---:|---:|---|"]
    focus = comparison.loc[(comparison.start_day == 1.0) & (comparison.end_day == 46.0) & comparison.pool.isin((*GROUPS, "G6P", "GO6P", "F6P", "B23PG", "ATP"))]
    for row in focus.itertuples():
        lines.append(f"| {row.pool} | {row.numerical_correction_integral_mM_standard:.7g} | {row.numerical_correction_integral_mM_strict:.7g} | {row.numerical_correction_integral_mM_solver_invariant} |")
    lines += ["", "The effective reconstruction includes numerical repair terms. Raw closure and unforced predictive accuracy remain separate requirements.", "",
              "No reaction flux is independently inferred where the measured matrix has null directions. Conditional teachers preserve their model dependencies explicitly.", "",
              "See `preregistered_contract.json`, `structural_constraints.json`, each case's numerical budgets and `standard_strict_comparison.csv`. No kinetic optimization or promotion occurred."]
    (out_dir / "decision_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"summary": str(out_dir / "summary.json"), "report": str(out_dir / "decision_report.md")}, indent=2), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-summary", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    run(args.reference_summary, args.out_dir)
