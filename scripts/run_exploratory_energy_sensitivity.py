"""Execute user-authorized conditional energy probes without changing biological guards."""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from audit_ppp_constraints_and_numerics import file_hash, write_json
from build_adenylate_redox_feasibility import audit_case, pool_rows
from equadiff_brodbar import equadiff_brodbar
from fla_adenylate_redox_contract import adenylate_metrics
from fla_coupled_energy_protocol import GROUPS, build_sensitivity_plan, resolved_parameters
from fla_executed_attribution import limiting_loss_attribution
from fla_precalibration_readiness import evaluate_readiness
from fla_working_reference import load_working_reference, reference_options
from reaction_positivity import rbc_reaction_matrix
from run_fla_sparse_teacher_resolution import verify_archive_inputs
from test_reaction_positivity_fixed_context import load_context, replay
from verify_fla_working_reference import compare_arrays

CONFIG = ROOT / "config/fla_exploratory_energy_sensitivity.json"
DEFAULT_OUT = ROOT / "output/exploratory_energy_sensitivity_J1_J4_2026_10_06"
REACTIONS = ("VHK", "VPFK", "VAK", "VGAPDH", "VPGK", "VPK", "VDPGM", "VLDH")
PARENT_ARCHIVES = ("fla_synthetic_recovery_2026_10_05_v2", "fla_teacher_resolution_2026_10_05_v2",
                   "fla_sparse_teacher_resolution_2026_10_05", "fla_smoothed_interval_replay_2026_10_05",
                   "bordbar_source_units_time_audit_2026_10_06")


def validate_design(design):
    expected = json.loads(CONFIG.read_text())
    if design != expected or type(design.get("schema_version")) is not int:
        raise ValueError("exact preregistered exploratory design required")
    for key in ("biological_optimization_allowed", "global_model_promotion_allowed", "historical_contract_changed",
                "initial_conditions_fitted", "teacher_forcing", "observation_reset", "output_clipping", "historical_initialization_enabled"):
        if design.get(key) is not False:
            raise ValueError(f"exploratory diagnostic cannot enable {key}")
    if design.get("user_authorized_exploratory_execution") is not True:
        raise ValueError("explicit exploratory execution authorization required")
    return design


def measured_initialization(frozen, names, frame):
    times = np.asarray(frame.columns[1:], dtype=float)
    if times[0] != 1. or times[1] != 4. or np.any(np.diff(times) <= 0):
        raise ValueError("unaltered J1/J4 observation support required")
    state = np.asarray(frozen, dtype=float).copy()
    rows, seen = [], set()
    for index, row in frame.iterrows():
        pool = str(row.iloc[0]).strip().upper()
        value = float(row.iloc[1])
        if pool in seen or pool not in names[:113] or not np.isfinite(value) or value < 0:
            raise ValueError("unique mapped nonnegative J1 observations required")
        seen.add(pool)
        position = names.index(pool)
        old = float(state[position])
        state[position] = value
        rows.append({"pool": pool, "source": "Sheet1_J1_exact", "source_cell": f"B{index+2}",
                     "prior_archived_value": old, "initial_value": value, "changed_from_archive": old != value,
                     "independent_observation": pool not in ("B13PG", "P2G")})
    for position, pool in enumerate(names):
        if pool not in seen:
            rows.append({"pool": pool, "source": "unchanged_frozen_unmeasured_pool", "source_cell": None,
                         "prior_archived_value": float(frozen[position]), "initial_value": float(state[position]),
                         "changed_from_archive": False, "independent_observation": False})
    return state, pd.DataFrame(rows)


def stencil_cases(plan, scales):
    return next(c["case_id"] for c in plan["cases"] if c["log_scales"] == scales)


def single_response(plan, values, group, step):
    if group == "investment":
        return (values["baseline"]-values[stencil_cases(plan, {group: -step})])/step
    return (values[stencil_cases(plan, {group: step})]-values[stencil_cases(plan, {group: -step})])/(2*step)


def mixed_response(plan, values, first, second):
    step = .05
    def terms(group):
        return ((0., 1/step), (-step, -1/step)) if group == "investment" else ((step, 1/(2*step)), (-step, -1/(2*step)))
    response = np.zeros_like(values["baseline"])
    for (a, wa), (b, wb) in itertools.product(terms(first), terms(second)):
        scales = {g: s for g, s in ((first, a), (second, b)) if s != 0}
        response += wa*wb*values[stencil_cases(plan, scales)]
    return response


def sample_evidence(solution, params, ode, directory, names, reactions, matrix):
    grid = np.unique(np.r_[solution.t, np.linspace(1., 4., 601)])
    states = solution.sol(grid)
    parts = replay(grid, states, params, "reaction_consistent", reactions, matrix,
                   threshold=ode["reaction_availability_threshold"])
    np.savez_compressed(directory / "dense_full_states_fluxes.npz", time=grid, names=names, states=states,
        reactions=reactions, native_flux=parts["native_flux"], effective_flux=parts["effective_flux"],
        availability_factors=parts["availability_factors"], executed_rhs=parts["executed"])
    rows = []
    for reaction in REACTIONS:
        j = reactions.index(reaction)
        attribution = limiting_loss_attribution(states[:113], parts["native_flux"][j], matrix[:, j],
                                                threshold=ode["reaction_availability_threshold"])
        if not np.allclose(attribution["factors"], parts["availability_factors"][j], rtol=1e-12, atol=1e-12):
            raise ValueError("sampled limiter attribution disagrees with executable kernel")
        pool_losses = np.trapezoid(attribution["loss_by_pool"], grid, axis=1)
        total_loss = float(np.trapezoid(attribution["loss"], grid))
        for i in np.flatnonzero(pool_losses):
            rows.append({"reaction": reaction, "limiting_pool": names[i], "sampled_absolute_loss_mM": float(pool_losses[i]),
                         "sampled_total_absolute_loss_mM": total_loss,
                         "sampled_loss_share": float(pool_losses[i]/total_loss),
                         "integration_method": "trapezoid_accepted_plus_dense_nodes_not_independent_quadrature",
                         "interpretation": "minimum_consumer_bookkeeping_not_biological_control_coefficient"})
    pd.DataFrame(rows, columns=["reaction", "limiting_pool", "sampled_absolute_loss_mM", "sampled_total_absolute_loss_mM",
        "sampled_loss_share", "integration_method", "interpretation"]).to_csv(directory / "sampled_limiter_participation.csv", index=False)
    return grid, states, parts


def response_tables(plan, features, feature_names, feature_kinds):
    singles, interactions = [], []
    for solver in ("strict", "ultrastrict"):
        values = {case["case_id"]: features[(case["case_id"], solver)] for case in plan["cases"]}
        for group in GROUPS:
            for step in (.05, .10):
                vector = single_response(plan, values, group, step)
                singles.extend({"solver": solver, "group": group, "log_step": step, "kind": kind,
                                "name": name, "response_per_log_capacity": float(value)}
                               for name, kind, value in zip(feature_names, feature_kinds, vector))
        for first, second in itertools.combinations(GROUPS, 2):
            vector = mixed_response(plan, values, first, second)
            interactions.extend({"solver": solver, "first_group": first, "second_group": second,
                "kind": kind, "name": name, "mixed_response_per_log_capacity_squared": float(value)}
                for name, kind, value in zip(feature_names, feature_kinds, vector))
    return pd.DataFrame(singles), pd.DataFrame(interactions)


def run(config_path=CONFIG, out=DEFAULT_OUT):
    if out.exists():
        raise FileExistsError("fresh directory required; previous evidence cannot be overwritten")
    design = validate_design(json.loads(config_path.read_text()))
    working = load_working_reference(ROOT / design["working_reference"])
    context = ROOT / design["fixed_context"]
    frozen, params, names, times, curves, workbook = load_context(context)
    frame = pd.read_excel(workbook, sheet_name="Sheet1")
    initial, initialization = measured_initialization(frozen, names, frame)
    resolved, provenance = resolved_parameters(params, ROOT / "src/equadiff_brodbar.py")
    plan = build_sensitivity_plan(resolved)
    if len(plan["cases"]) != 19:
        raise ValueError("complete 19-case diagnostic stencil required")
    for archive in PARENT_ARCHIVES:
        verify_archive_inputs(ROOT / "output" / archive)
    readiness = evaluate_readiness(json.loads((ROOT / "config/fla_adenylate_redox_readiness.json").read_text()), root=ROOT,
        frozen_initial_redox=[float(initial[names.index(p)]) for p in ("NAD", "NADH")])
    historical_path = ROOT / design["historical_prepared_protocol"]
    historical = json.loads(historical_path.read_text())
    if historical["execution_authorized"] is not False:
        raise ValueError("historical protocol must stay unexecuted")
    dependencies = [config_path, Path(__file__), ROOT / "src/fla_coupled_energy_protocol.py",
        ROOT / "src/fla_working_reference.py", ROOT / "src/fla_executed_attribution.py",
        ROOT / "src/fla_balance_audit.py", ROOT / "src/reaction_positivity.py",
        ROOT / "src/fla_adenylate_redox_contract.py", ROOT / "scripts/build_adenylate_redox_feasibility.py",
        ROOT / "scripts/test_reaction_positivity_fixed_context.py", ROOT / "scripts/verify_fla_working_reference.py",
        ROOT / "config/fla_adenylate_redox_readiness.json", ROOT / design["working_reference"],
        ROOT / "src/equadiff_brodbar.py", ROOT / "src/rbc_stoichiometry.py", workbook,
        context / "fixed_parameters.json", context / "fixed_initial_state.csv", historical_path,
        ROOT / "src/Initial_conditions_JA_Final.xls", ROOT / "src/parse_initial_conditions.py", ROOT / "src/MM_calibration.py"]
    hashes = {str(p.resolve()): file_hash(p) for p in dependencies}
    out.mkdir(parents=True)
    contract = {"created_at": datetime.now(timezone.utc).isoformat(), "design": design, "input_sha256": hashes,
        "working_reference": working, "resolved_capacities": resolved, "capacity_provenance": provenance,
        "initialization_changes": initialization[initialization.changed_from_archive].to_dict("records"),
        "historical_prepared_protocol_execution_authorized": False, "biological_contract_changed": False,
        "scientific_contract_complete": readiness["scientific_contract_complete"], "blockers": readiness["blockers"],
        "optimization_performed": False, "parameters_promoted": False,
        "conditional_exploratory_execution_authorized": True}
    write_json(out / "preregistered_contract.json", contract)
    write_json(out / "exploratory_probe_plan.json", {"scope": design["purpose"], "execution_authorized": True,
        "historical_protocol_execution_authorized": False, "cases": plan["cases"],
        "planned_case_count": 19, "planned_integrations": 38, "initial_conditions_fitted": False})
    write_json(out / "readiness_assessment.json", readiness)
    write_json(out / "frozen_parameters.json", params)
    initialization.to_csv(out / "initialization_inventory.csv", index=False)
    np.savez_compressed(out / "frozen_initial_state.npz", names=names, states=initial)
    _, reactions, matrix = rbc_reaction_matrix(params.get("sam_adenylate_stoichiometry", "biochemical_transfer"))
    labels, indices, rows = pool_rows(names, matrix, reactions)
    results, endpoints, comparisons, flux_rows, features = {}, [], [], [], {}
    feature_names = list(names[:113])+["energy_charge", "NADH_fraction"]+list(reactions)
    feature_kinds = ["J4_concentration"]*113+["J4_energy_charge", "J4_NADH_fraction"]+["J1_J4_executed_flux_integral"]*len(reactions)
    started = perf_counter()
    for case in plan["cases"]:
        candidate = {**params, **case["parameter_overrides"]}
        for solver_name in ("strict", "ultrastrict"):
            label = f"{case['case_id']}_{solver_name}"
            print(f"[{label}] J1-J4 exact observed J1; conditional sensitivity only", flush=True)
            ode, solver = reference_options(working, ultrastrict=solver_name == "ultrastrict")
            solution = solve_ivp(lambda day, state: equadiff_brodbar(float(day), state, custom_params=candidate, **ode),
                (1., 4.), initial.copy(), dense_output=True, **solver)
            if not solution.success or not np.all(np.isfinite(solution.y)) or not np.array_equal(solution.y[:, 0], initial):
                raise RuntimeError(f"{label}: integration/initialization failure: {solution.message}")
            directory = out / label
            result = audit_case(solution, candidate, ode, directory, names, reactions, matrix, labels, indices, rows)
            grid, states, parts = sample_evidence(solution, candidate, ode, directory, names, reactions, matrix)
            write_json(directory / "parameters.json", candidate)
            write_json(directory / "numerical_audit.json", result["summary"])
            results[label] = result
            final = solution.y[:, -1]
            metrics = adenylate_metrics(final[[names.index(p) for p in ("ATP", "ADP", "AMP")], None])
            pair_total = float(final[names.index("NAD")]+final[names.index("NADH")])
            features[(case["case_id"], solver_name)] = np.r_[final[:113], metrics["energy_charge"][0],
                final[names.index("NADH")]/pair_total, result["integrals"]["effective_flux"].sum(axis=1)]
            for pool, values in curves.items():
                value = float(final[names.index(pool)])
                endpoints.append({"case": case["case_id"], "solver": solver_name, "pool": pool,
                    "model_J4_mM": value, "reference_J4_mM": float(values[1]), "signed_endpoint_error_mM": value-float(values[1]),
                    "independent_observation": pool not in ("B13PG", "P2G"), "biological_accuracy_pass": None})
            for j, reaction in enumerate(reactions):
                flux_rows.append({"case": case["case_id"], "solver": solver_name, "reaction": reaction,
                    "executed_J1_J4_integral_mM": float(result["integrals"]["effective_flux"][j].sum()),
                    "observed_individual_flux": False})
            write_json(out / "execution_progress.json", {"completed_integrations": len(results), "planned_integrations": 38,
                "last_case": label, "elapsed_seconds": perf_counter()-started,
                "numerical_failures": [key for key, value in results.items() if not value["summary"]["numerical_integrity_pass"]]})
            print(f"[{label}] steps={len(solution.t)} numerical_pass={result['summary']['numerical_integrity_pass']}", flush=True)
        a, b = results[f"{case['case_id']}_strict"], results[f"{case['case_id']}_ultrastrict"]
        common = np.unique(np.r_[a["solution"].t, b["solution"].t, np.linspace(1., 4., 601)])
        difference, passed = compare_arrays(a["solution"].sol(common)[:113], b["solution"].sol(common)[:113], atol=1e-5, rtol=.01)
        comparisons.extend({"case": case["case_id"], "quantity": "concentration", "name": name,
            "passes": bool(passed[i]), "maximum_difference_mM": float(difference[i])} for i, name in enumerate(names[:113]))
        for key in a["integrals"]:
            difference, passed = compare_arrays(a["integrals"][key], b["integrals"][key], atol=1e-5, rtol=.01)
            comparisons.extend({"case": case["case_id"], "quantity": key, "name": name,
                "passes": bool(passed[i]), "maximum_difference_mM": float(difference[i])} for i, name in enumerate(a["quantity_labels"][key]))
    endpoint_frame = pd.DataFrame(endpoints)
    endpoint_frame.to_csv(out / "J4_endpoint_diagnostics.csv", index=False)
    pd.DataFrame(flux_rows).to_csv(out / "executed_flux_integrals.csv", index=False)
    comparison_frame = pd.DataFrame(comparisons)
    comparison_frame.to_csv(out / "strict_ultrastrict_convergence.csv", index=False)
    singles, interactions = response_tables(plan, features, feature_names, feature_kinds)
    singles.to_csv(out / "single_group_responses.csv", index=False)
    interactions.to_csv(out / "paired_group_interactions.csv", index=False)
    stability = singles.pivot(index=["solver", "group", "kind", "name"], columns="log_step", values="response_per_log_capacity").reset_index()
    stability["response_step_difference"] = stability[.10]-stability[.05]
    stability.to_csv(out / "probe_size_stability.csv", index=False)
    unchanged = {p: file_hash(Path(p)) == h for p, h in hashes.items()}
    if not all(unchanged.values()):
        raise ValueError("frozen input modified during diagnostic")
    for archive in PARENT_ARCHIVES:
        verify_archive_inputs(ROOT / "output" / archive)
    summary = {"status": "completed_conditional_exploratory_sensitivity", "case_count": 19, "integrations_completed": len(results),
        "optimization_performed": False, "biological_contract_changed": False, "kinetic_parameters_promoted": False,
        "initial_conditions_promoted": False, "measured_J1_exact": True, "unmeasured_initialization_changed": False,
        "initialization_changes": contract["initialization_changes"], "scientific_blocker_count": len(readiness["blockers"]),
        "historical_coupled_protocol_authorized": False, "biological_calibration_allowed": False,
        "minimum_raw_checked_concentration_mM": min(r["summary"]["min_raw_checked_concentration_mM"] for r in results.values()),
        "quadrature_check_count": sum(r["summary"]["quadrature_check_count"] for r in results.values()),
        "failed_quadrature_checks": sum(r["summary"]["failed_quadrature_checks"] for r in results.values()),
        "convergence_check_count": len(comparisons), "failed_convergence_checks": int((~comparison_frame.passes).sum()),
        "numerical_diagnostic_passes": bool(comparison_frame.passes.all() and all(r["summary"]["numerical_integrity_pass"] for r in results.values())),
        "cases": {key: r["summary"] for key, r in results.items()}, "elapsed_seconds": perf_counter()-started,
        "input_hash_checks": unchanged, "sealed_prior_archives_unchanged": list(PARENT_ARCHIVES)}
    write_json(out / "summary.json", summary)
    write_json(out / "final_verification.json", {"input_hash_checks": unchanged, "biological_contract_changed": False,
        "independent_archive_checks_pass": False,
        "output_sha256": {str(p.relative_to(out)): file_hash(p) for p in out.rglob("*") if p.is_file() and p.name != "final_verification.json"}})
    print(json.dumps({k: v for k, v in summary.items() if k not in ("cases", "input_hash_checks")}, indent=2), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    run(args.config.resolve(), args.out.resolve())
