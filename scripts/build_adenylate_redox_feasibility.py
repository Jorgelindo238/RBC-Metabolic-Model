"""Build the fixed-kinetic J1-J4 adenylate/redox precalibration contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "scripts"):
    sys.path.insert(0, str(path))

from audit_ppp_constraints_and_numerics import file_hash, write_json
from equadiff_brodbar import equadiff_brodbar
from fla_adenylate_redox_contract import (
    ADENYLATE_POOLS, TOTAL_ADENYLATE_TERMS, adenylate_metrics, conditional_ak_requirements,
    readiness_blockers, redox_initializations,
)
from fla_balance_audit import accepted_step_quadrature, integrate_intervals
from fla_executed_attribution import aggregate_windows
from fla_working_reference import DEFAULT_WORKING_REFERENCE, load_working_reference, reference_options
from reaction_positivity import rbc_reaction_matrix
from test_reaction_positivity_fixed_context import POLICY, load_context, replay
from verify_fla_working_reference import compare_arrays

DEFAULT_SOURCE = ROOT / "output/b13pg_atp_executed_audit_2026_10_05"
DEFAULT_OUT = ROOT / "output/adenylate_redox_feasibility_2026_10_05"
HISTORICAL = ROOT / "src/Initial_conditions_JA_Final.xls"
PROVENANCE = ROOT / "output/brodbar_data_provenance_2026_08_11/provenance.json"
POOLS = ("ATP", "ADP", "AMP", "NAD", "NADH", "NADP", "NADPH")
GROUPS = {"ATP_ADP_AMP": ("ATP", "ADP", "AMP"), "NAD_NADH": ("NAD", "NADH"), "NADP_NADPH": ("NADP", "NADPH")}
WINDOWS = (("J1_J1.1", 1., 1.1), ("J1.1_J1.3", 1.1, 1.3), ("J1.3_J1.6", 1.3, 1.6),
           ("J1.6_J2", 1.6, 2.), ("J2_J3", 2., 3.), ("J3_J4", 3., 4.), ("J1_J4", 1., 4.))


def historical_redox_values(path):
    frame = pd.read_excel(path, header=None)
    labels = frame.iloc[:, 0].astype(str).str.strip().str.upper()
    result = {}
    for pool in ("NAD", "NADH", "NADP", "NADPH"):
        values = frame.loc[labels.eq(pool)].iloc[:, 1].to_numpy(dtype=float)
        if values.shape != (1,) or not np.isfinite(values[0]) or values[0] <= 0:
            raise ValueError(f"historical redox row must be unique, finite and positive: {pool}")
        result[pool] = float(values[0])
    return result


def pool_rows(names, matrix, reactions):
    labels = list(POOLS) + list(GROUPS)
    indices = [[names.index(pool)] for pool in POOLS] + [[names.index(pool) for pool in members] for members in GROUPS.values()]
    rows = np.asarray([matrix[members].sum(axis=0) for members in indices])
    total = {reactions[j]: float(rows[labels.index("ATP_ADP_AMP"), j]) for j in np.flatnonzero(rows[labels.index("ATP_ADP_AMP")])}
    if total != TOTAL_ADENYLATE_TERMS:
        raise ValueError("joint adenylate equation differs from the explicit corrected network")
    if np.any(rows[labels.index("NAD_NADH")]) or np.any(rows[labels.index("NADP_NADPH")]):
        raise ValueError("encoded redox pair is not conserved")
    return labels, indices, rows


def audit_case(solution, params, ode, out_dir, names, reactions, matrix, labels, indices, rows):
    out_dir.mkdir()
    cuts = np.unique([point for _, start, end in WINDOWS for point in (start, end)])
    meta = [(i, j) for i in range(len(labels)) for j in np.flatnonzero(rows[i])]

    def quantities(time):
        states = solution.sol(time)
        parts = replay(time, states, params, "reaction_consistent", reactions, matrix,
                       threshold=ode["reaction_availability_threshold"])
        contributions = np.asarray([rows[i, j] * parts["effective_flux"][j] for i, j in meta])
        production, consumption = np.zeros((len(labels), len(time))), np.zeros((len(labels), len(time)))
        for k, (i, _) in enumerate(meta):
            production[i] += np.maximum(contributions[k], 0)
            consumption[i] += np.maximum(-contributions[k], 0)
        rhs = np.asarray([parts["executed"][members].sum(axis=0) for members in indices])
        net = rows @ parts["effective_flux"]
        values = {"reaction_contribution": contributions, "net": net, "native_net": rows @ parts["native_flux"],
                  "production": production, "consumption": consumption, "rhs": rhs, "nonreaction_residual": rhs - net,
                  "effective_flux": parts["effective_flux"]}
        return states, parts, values

    sample_time = np.unique(np.r_[solution.t, cuts, np.linspace(1, 4, 601)])
    sample_states, sample_parts, _ = quantities(sample_time)
    frame = {"time_day": sample_time, **{pool: sample_states[names.index(pool)] for pool in POOLS}}
    metrics = adenylate_metrics(sample_states[[names.index(pool) for pool in ADENYLATE_POOLS]])
    frame["ATP_ADP_AMP"], frame["energy_charge"] = metrics["total"], metrics["energy_charge"]
    frame["NAD_NADH"] = frame["NAD"] + frame["NADH"]
    frame["NADH_fraction"] = frame["NADH"] / frame["NAD_NADH"]
    for reaction in ("VAK", "VAK2", "VADSL", "VAMPD1", "VAMP_NT", "VAPRT", "VSAM", "VGAPDH", "VLDH", "VIMPH", "VMLD", "VPHGDH"):
        j = reactions.index(reaction)
        frame[f"{reaction}_executed"] = sample_parts["effective_flux"][j]
        frame[f"{reaction}_native"] = sample_parts["native_flux"][j]
    pd.DataFrame(frame).to_csv(out_dir / "executed_timeseries.csv", index=False)
    np.savez_compressed(out_dir / "accepted_solver_states.npz", time=solution.t, states=solution.y)
    integral, minimum = {}, float(np.min(sample_states[:113]))
    closure = float(np.max(np.abs(sample_parts["nonreaction_residual"])))
    for order in (4, 8):
        grid = accepted_step_quadrature(solution.t, cuts, order=order)
        if len(grid.nodes) > POLICY["maximum_quadrature_nodes"]:
            raise ValueError("quadrature node budget exceeded")
        states, parts, values = quantities(grid.nodes)
        integral[order] = {key: integrate_intervals(value, grid) for key, value in values.items()}
        minimum = min(minimum, float(np.min(states[:113])))
        closure = max(closure, float(np.max(np.abs(parts["nonreaction_residual"]))))
    quantity_labels = {key: labels for key in ("net", "native_net", "production", "consumption", "rhs", "nonreaction_residual")}
    quantity_labels.update(reaction_contribution=[f"{labels[i]}:{reactions[j]}" for i, j in meta], effective_flux=list(reactions))
    checks = []
    for key in integral[8]:
        differences, passed = compare_arrays(integral[4][key], integral[8][key], atol=1e-6, rtol=1e-3)
        checks.extend({"quantity": key, "name": name, "passes": bool(passed[i]), "maximum_difference_mM": float(differences[i])}
                      for i, name in enumerate(quantity_labels[key]))
    checks = pd.DataFrame(checks)
    checks.to_csv(out_dir / "quadrature_checks.csv", index=False)
    fine = integral[8]
    np.savez_compressed(out_dir / "interval_integrals.npz", boundaries=cuts, **fine)
    window_integrals = {key: aggregate_windows(value, cuts, WINDOWS) for key, value in fine.items()}
    budget, terms = [], []
    for window_index, (window, start, end) in enumerate(WINDOWS):
        for i, (pool, members) in enumerate(zip(labels, indices)):
            delta = float((solution.sol(end)[members] - solution.sol(start)[members]).sum())
            budget.append({"window": window, "pool": pool, "state_change_mM": delta,
                **{f"{key}_mM": float(window_integrals[key][i, window_index]) for key in
                   ("net", "native_net", "production", "consumption", "rhs", "nonreaction_residual")},
                "solver_integral_residual_mM": delta - float(window_integrals["rhs"][i, window_index])})
        for k, (i, j) in enumerate(meta):
            terms.append({"window": window, "pool": labels[i], "reaction": reactions[j],
                          "coefficient": float(rows[i, j]), "executed_contribution_mM": float(window_integrals["reaction_contribution"][k, window_index])})
    budgets = pd.DataFrame(budget)
    budgets.to_csv(out_dir / "window_pool_budgets.csv", index=False)
    pd.DataFrame(terms).to_csv(out_dir / "window_reaction_contributions.csv", index=False)
    pair_drift = float(np.max(np.abs(frame["NAD_NADH"] - frame["NAD_NADH"][0])))
    nadp_total = frame["NADP"] + frame["NADPH"]
    nadp_drift = float(np.max(np.abs(nadp_total - nadp_total[0])))
    state_delta = budgets.state_change_mM.to_numpy()
    rhs_integral = budgets.rhs_mM.to_numpy()
    state_integral_pass = bool(np.all(np.abs(state_delta - rhs_integral) <= 1e-6 + 1e-3 * np.maximum(np.abs(state_delta), np.abs(rhs_integral))))
    summary = {"min_raw_checked_concentration_mM": minimum, "negative_accepted_count": int(np.count_nonzero(solution.y[:113] < 0)),
        "max_executed_closure_mM_per_day": closure, "max_NAD_pair_drift_mM": pair_drift,
        "max_NADP_pair_drift_mM": nadp_drift, "state_integral_balance_pass": state_integral_pass,
        "quadrature_check_count": len(checks), "failed_quadrature_checks": int((~checks.passes).sum()),
        "max_window_solver_integral_residual_mM": float(budgets.solver_integral_residual_mM.abs().max()),
        "numerical_integrity_pass": bool(minimum >= -1e-10 and closure <= 1e-7 and pair_drift <= 1e-7 and nadp_drift <= 1e-7 and state_integral_pass and checks.passes.all())}
    return {"summary": summary, "solution": solution, "frame": pd.DataFrame(frame), "integrals": fine,
            "quantity_labels": quantity_labels, "window_integrals": window_integrals, "budgets": budgets}


def plot_cases(out_dir, results, observed):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 2, figsize=(12, 10), constrained_layout=True)
    panels = ("ATP", "ADP", "AMP", "energy_charge", "NAD_NADH", "NADH_fraction")
    cases = ("baseline", "historical_total_only", "historical_ratio_only", "historical_pair")
    for axis, pool in zip(axes.flat, panels):
        for case, color, style in zip(cases, ("#333333", "#25857b", "#4863b0", "#b85665"), ("-", "--", "-.", ":")):
            frame = results[f"{case}_strict"]["frame"]
            axis.plot(frame.time_day, frame[pool], color=color, linestyle=style, label=case.replace("_", " "))
        if pool in observed:
            axis.scatter([1, 4], observed[pool], color="#111111", marker="o", zorder=3, label="Local tabulated endpoints")
        axis.set(title=pool, xlabel="Model day", ylabel="Dimensionless" if pool in {"energy_charge", "NADH_fraction"} else "Nominal mM")
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(alpha=.15)
    handles, legend = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, legend, loc="outside lower center", ncol=3, fontsize=9, frameon=False)
    fig.suptitle("J1-J4 fixed kinetics: redox IC diagnostics are not calibration", fontsize=14)
    fig.savefig(out_dir / "adenylate_redox_contract.png", dpi=180)
    fig.savefig(out_dir / "adenylate_redox_contract.pdf")
    plt.close(fig)


def run(source, out_dir):
    if out_dir.exists():
        raise FileExistsError("use a fresh output directory")
    config = load_working_reference()
    prior_contract = json.loads((source / "preregistered_contract.json").read_text())
    prior_summary = json.loads((source / "summary.json").read_text())
    if prior_contract["working_reference"] != config or not prior_summary["numerical_audit_passes"]:
        raise ValueError("source audit must use the unchanged, numerically verified working reference")
    for path, digest in prior_contract["input_sha256"].items():
        if file_hash(Path(path)) != digest:
            raise ValueError(f"source audit input changed: {path}")
    x0, params, names, times, curves, data_path = load_context(ROOT / config["fixed_context"])
    if times[0] != 1 or times[1] != 4:
        raise ValueError("J1 and J4 must be the first two tabulated endpoints")
    historical = historical_redox_values(HISTORICAL)
    pair_indices = [names.index("NAD"), names.index("NADH")]
    scenarios = redox_initializations(x0, pair_indices, [historical["NAD"], historical["NADH"]])
    adenylate_indices = [names.index(pool) for pool in ADENYLATE_POOLS]
    reference = np.asarray([curves[pool][:2] for pool in ADENYLATE_POOLS])
    if not np.allclose(x0[adenylate_indices], reference[:, 0], rtol=0, atol=1e-12):
        raise ValueError("measured initial adenylates differ from the frozen context")
    _, reactions, matrix = rbc_reaction_matrix(params.get("sam_adenylate_stoichiometry", "biochemical_transfer"))
    labels, indices, rows = pool_rows(names, matrix, reactions)
    reference_metrics = adenylate_metrics(reference)
    observed = {pool: reference[i] for i, pool in enumerate(ADENYLATE_POOLS)}
    observed.update(ATP_ADP_AMP=reference_metrics["total"], energy_charge=reference_metrics["energy_charge"])
    data_contract = {"source_classification": "curated_model_input_not_traceable_raw_measurements",
        "observed_days": [1., 4.], "time_unit": "day", "time_origin": "J1 first tabulated endpoint; not reindexed as J0",
        "nominal_quantity_unit": "mM", "upstream_lineage_verified": False, "normalization_verified": None,
        "uncertainty_available": False, "time_origin_verified": None, "replicate_count": None,
        "compartment_volume_basis": None, "measurement_uncertainty": None,
        "intermediate_values": "simulation only; no independent measured J2/J3 teacher", "role": "precalibration diagnostic"}
    redox_contract = {"observed_redox_rows": [pool for pool in ("NAD", "NADH", "NADP", "NADPH") if pool in curves],
        "biological_prior_verified": False, "historical_input_unit_verified": None,
        "historical_values_nominal_mM": historical, "historical_source": str(HISTORICAL.resolve()),
        "current_NAD_total_mM": float(x0[pair_indices].sum()), "current_NADH_fraction": float(x0[pair_indices[1]] / x0[pair_indices].sum()),
        "prior_total_bounds_mM": None, "prior_NADH_fraction_bounds": None,
        "admissibility": "NAD,NADH nonnegative; total positive; fraction in [0,1]; conservation is numerical, not a measured total",
        "diagnostic_scenarios_not_fitted": list(scenarios), "NADP_NADPH_changed": False}
    blockers = readiness_blockers(data_contract, redox_contract, None)
    out_dir.mkdir(parents=True)
    inputs = [DEFAULT_WORKING_REFERENCE, HISTORICAL, PROVENANCE, data_path, source / "preregistered_contract.json", source / "summary.json",
              ROOT / "src/fla_adenylate_redox_contract.py", Path(__file__)]
    inputs.extend(source / solver / "accepted_solver_states.npz" for solver in ("strict", "ultrastrict"))
    inputs.extend(Path(path) for path in prior_contract["input_sha256"])
    contract = {"contract_type": "fla_fixed_kinetic_adenylate_redox_J1_J4", "schema_version": 1,
        "working_reference": config, "input_sha256": {str(path.resolve()): file_hash(path) for path in inputs},
        "data_contract": data_contract, "redox_contract": redox_contract, "absolute_accuracy_limits": None,
        "reference_endpoints": {pool: list(map(float, reference[i])) for i, pool in enumerate(ADENYLATE_POOLS)},
        "windows": WINDOWS, "numerical_policy": POLICY, "scenario_order": list(scenarios),
        "scenario_initial_states": {case: {pool: float(state[names.index(pool)]) for pool in ("NAD", "NADH")} for case, state in scenarios.items()},
        "kinetic_parameters_changed": False, "initial_conditions_promoted": False,
        "optimization_performed": False, "calibration_allowed": False, "blockers": blockers,
        "interpretation": "historical ICs are model inputs, not independently measured redox priors; no best scenario is selected"}
    write_json(out_dir / "preregistered_contract.json", contract)
    pd.DataFrame({"day": [1., 4.], **observed}).to_csv(out_dir / "reference_endpoints.csv", index=False)
    pd.DataFrame([{"pool": pool, "baseline_nominal_mM": float(x0[names.index(pool)]), "historical_nominal_mM": historical[pool],
                   "observed_in_reference": pool in curves, "changed_in_scenarios": pool in ("NAD", "NADH")}
                  for pool in historical]).to_csv(out_dir / "redox_initialization_inventory.csv", index=False)
    results, endpoints, inversions, comparisons = {}, [], [], []
    for case, state in scenarios.items():
        mask = np.ones(len(x0), dtype=bool)
        mask[pair_indices] = False
        if not np.array_equal(state[mask], x0[mask]):
            raise ValueError("redox scenario changed unrelated or measured initial states")
        for solver_name in ("strict", "ultrastrict"):
            label = f"{case}_{solver_name}"
            ode, solver = reference_options(config, ultrastrict=solver_name == "ultrastrict")
            print(f"[{label}] J1-J4 fixed kinetics, no fitting", flush=True)
            solution = solve_ivp(lambda day, values: equadiff_brodbar(float(day), values, custom_params=params, **ode),
                                 (1., 4.), state.copy(), dense_output=True, **solver)
            if not solution.success or not np.all(np.isfinite(solution.y)):
                raise RuntimeError(f"{label}: {solution.message}")
            result = audit_case(solution, params, ode, out_dir / label, names, reactions, matrix, labels, indices, rows)
            if case == "baseline":
                with np.load(source / solver_name / "accepted_solver_states.npz") as saved:
                    selected = saved["time"] <= 4
                    differences, passed = compare_arrays(solution.sol(saved["time"][selected])[:113], saved["states"][:113, selected], atol=1e-5, rtol=.01)
                    result["summary"]["baseline_prefix_matches_verified_replay_within_tolerance"] = bool(passed.all())
                    result["summary"]["baseline_prefix_max_difference_mM"] = float(differences.max())
                    result["summary"]["numerical_integrity_pass"] &= bool(passed.all())
            write_json(out_dir / label / "summary.json", result["summary"])
            results[label] = result
            final = solution.sol(4)[adenylate_indices]
            metrics = adenylate_metrics(final[:, None])
            for i, pool in enumerate(ADENYLATE_POOLS):
                endpoints.append({"case": case, "solver": solver_name, "pool": pool, "model_J4_mM": float(final[i]),
                    "reference_J4_mM": float(reference[i, 1]), "signed_endpoint_error_mM": float(final[i] - reference[i, 1]),
                    "biological_accuracy_pass": None})
            endpoint_total = float(metrics["total"][0])
            endpoints.append({"case": case, "solver": solver_name, "pool": "ATP_ADP_AMP", "model_J4_mM": endpoint_total,
                "reference_J4_mM": float(reference_metrics["total"][1]), "signed_endpoint_error_mM": endpoint_total - float(reference_metrics["total"][1]), "biological_accuracy_pass": None})
            net = result["window_integrals"]["net"][:3, -1]
            vak = float(result["window_integrals"]["effective_flux"][reactions.index("VAK"), -1])
            inversion = conditional_ak_requirements(reference[:, 1] - reference[:, 0], net, vak)
            inversions.append({"case": case, "solver": solver_name, "executed_VAK_integral_mM": vak,
                **{f"required_VAK_from_{pool}_mM": float(inversion["required_by_pool"][i]) for i, pool in enumerate(ADENYLATE_POOLS)},
                "requirement_spread_mM": inversion["requirement_spread_mM"], "total_adenylate_discrepancy_mM": inversion["total_adenylate_discrepancy_mM"],
                "individually_observed_AK": False, "statistical_compatibility": None,
                "energy_charge_J4": float(metrics["energy_charge"][0])})
            print(f"[{label}] quad failures={result['summary']['failed_quadrature_checks']}", flush=True)
        a, b = results[f"{case}_strict"], results[f"{case}_ultrastrict"]
        common = np.unique(np.r_[a["solution"].t, b["solution"].t, np.linspace(1, 4, 601)])
        difference, passed = compare_arrays(a["solution"].sol(common)[:113], b["solution"].sol(common)[:113], atol=1e-5, rtol=.01)
        comparisons.extend({"case": case, "quantity": "concentration", "name": pool, "passes": bool(passed[i]), "maximum_difference_mM": float(difference[i])} for i, pool in enumerate(names[:113]))
        for key in a["integrals"]:
            difference, passed = compare_arrays(a["integrals"][key], b["integrals"][key], atol=1e-5, rtol=.01)
            comparisons.extend({"case": case, "quantity": key, "name": name, "passes": bool(passed[i]), "maximum_difference_mM": float(difference[i])} for i, name in enumerate(a["quantity_labels"][key]))
    pd.DataFrame(endpoints).to_csv(out_dir / "J4_endpoint_diagnostics.csv", index=False)
    pd.DataFrame(inversions).to_csv(out_dir / "conditional_joint_AK_requirements.csv", index=False)
    comparison_frame = pd.DataFrame(comparisons)
    comparison_frame.to_csv(out_dir / "strict_ultrastrict_convergence.csv", index=False)
    summary = {"contract_created": True, "cases": {label: result["summary"] for label, result in results.items()},
        "comparison_count": len(comparisons), "failed_convergence_checks": int((~comparison_frame.passes).sum()),
        "numerical_diagnostic_passes": bool(comparison_frame.passes.all() and all(result["summary"]["numerical_integrity_pass"] for result in results.values())),
        "contract_readiness": "blocked_pending_data_accuracy_and_redox_prior", "blockers": blockers,
        "absolute_accuracy_limits": None, "calibration_allowed": False, "optimization_performed": False,
        "kinetic_parameters_promoted": False, "initial_conditions_promoted": False, "best_redox_scenario_selected": False}
    write_json(out_dir / "summary.json", summary)
    write_json(out_dir / "feasibility_contract.json", {**contract, "numerical_diagnostic_passes": summary["numerical_diagnostic_passes"],
                                                     "contract_readiness": summary["contract_readiness"]})
    plot_cases(out_dir, results, observed)
    lines = ["# ATP-ADP-AMP and redox feasibility contract: J1-J4", "",
        "Fixed unpromoted kinetics and strict reaction_consistent profile, threshold 1e-3 mM. Four IC scenarios are predeclared, each strict/ultrastrict: baseline, historical NAD total only, historical NAD ratio only, historical NAD pair. Only NAD/NADH may differ; every measured initial state and NADP/NADPH remain unchanged. No fitting, best-scenario selection, observation reset, output clipping or promotion.", "",
        "Historical values are traceable model inputs, not independently measured biological priors. Nominal workbook mM/day units do not verify normalization, upstream measurement lineage, uncertainty or biological time origin. Only J1/J4 are observed endpoints; intermediate trajectories are simulations, not additional teachers.", "",
        "## Structural constraints", "",
        "T_A=ATP+ADP+AMP; dT_A/dt=VADSL+VAK2+VAPRT-VSAM-VAMPD1-VAMP_NT (executed rates). VAK redistributes with (1,-2,1), so it cannot directly change T_A. NAD+NADH and NADP+NADPH are encoded invariants; conservation does not identify their initial totals. Energy charge=(ATP+0.5 ADP)/T_A is computed only for nonnegative states and a positive pool.", "",
        "## J4 endpoint diagnostics (strict)", "", "| Scenario | ATP | ADP | AMP | Total |", "|---|---:|---:|---:|---:|"]
    endpoint_frame = pd.DataFrame(endpoints)
    for case in scenarios:
        selected = endpoint_frame.loc[endpoint_frame.case.eq(case) & endpoint_frame.solver.eq("strict")].set_index("pool")
        lines.append(f"| {case} | " + " | ".join(f"{selected.loc[pool, 'model_J4_mM']:.8g}" for pool in (*ADENYLATE_POOLS, "ATP_ADP_AMP")) + " |")
    lines.append("| Local reference | " + " | ".join(f"{observed[pool][1]:.8g}" for pool in (*ADENYLATE_POOLS, "ATP_ADP_AMP")) + " |")
    lines += ["", "## Readiness", "", f"Numerical diagnostic gate passes: {summary['numerical_diagnostic_passes']}. Failed cross-tolerance checks: {summary['failed_convergence_checks']}/{summary['comparison_count']}.", "",
        "Absolute biological accuracy limits and supported redox total/fraction bounds remain unset, not replaced with numerical tolerances. Calibration remains blocked. Blockers: " + ", ".join(blockers) + ".", "",
        "Conditional VAK requirements hold every other simulated contribution fixed. Different ATP/ADP/AMP demands reject that exact fixed-neighbor explanation, not the full coupled network. They are not observed VAK fluxes or evidence that changing VAK alone will work. Statistical compatibility remains unknown without uncertainty.", "",
        "Inspect the full AMP/purine and total-pool window budgets, initialization inventory, source hashes and conditional_joint_AK_requirements.csv. Scenario differences are diagnostics only; they cannot establish a calibrated initialization or external biological validation."]
    (out_dir / "decision_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(out_dir / "decision_report.md"), "numerical_diagnostic_passes": summary["numerical_diagnostic_passes"], "calibration_allowed": False}), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    run(args.source, args.out_dir)
