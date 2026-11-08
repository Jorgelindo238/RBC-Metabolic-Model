"""Independently verify raw replays, signed budgets and conditional response stencils."""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from audit_ppp_constraints_and_numerics import file_hash, write_json
from equadiff_brodbar import equadiff_brodbar
from reaction_positivity import rbc_reaction_matrix
from run_fla_sparse_teacher_resolution import verify_archive_inputs

DEFAULT_OUT = ROOT / "output/exploratory_energy_sensitivity_J1_J4_2026_10_06"
GROUPS = ("investment", "AK_capacity", "GAPDH_PGK_capacity")
TOTAL_TERMS = {"VADSL": 1., "VAK2": 1., "VAPRT": 1., "VSAM": -1., "VAMPD1": -1., "VAMP_NT": -1.}


def read(path):
    return json.loads(path.read_text())


def verify(out):
    checks = []
    def check(name, passes):
        checks.append({"name": name, "passes": bool(passes)})
    contract, final, summary = [read(out / name) for name in ("preregistered_contract.json", "final_verification.json", "summary.json")]
    for path, digest in contract["input_sha256"].items():
        check(f"input:{path}", file_hash(Path(path)) == digest)
    for path, digest in final["output_sha256"].items():
        check(f"output:{path}", file_hash(out / path) == digest)
    for archive in summary["sealed_prior_archives_unchanged"]:
        verify_archive_inputs(ROOT / "output" / archive)
        check(f"parent:{archive}", True)
    historical = read(ROOT / contract["design"]["historical_prepared_protocol"])
    readiness = read(out / "readiness_assessment.json")
    check("scientific_guard_unchanged", historical["execution_authorized"] is False and historical["simulations_executed"] == 0
          and len(readiness["blockers"]) == 13 and not summary["biological_calibration_allowed"]
          and not summary["biological_contract_changed"] and not summary["kinetic_parameters_promoted"]
          and not summary["optimization_performed"])
    initial = np.load(out / "frozen_initial_state.npz")
    names, state = list(initial["names"]), initial["states"]
    frame = pd.read_excel(ROOT / "src/Data_Bordbar_et_al_exp.xlsx", sheet_name="Sheet1")
    measured = frame.iloc[:, 0].astype(str).str.strip().str.upper().tolist()
    check("all_55_measured_J1_exact", np.array_equal(state[[names.index(p) for p in measured]], frame.iloc[:, 1].to_numpy(dtype=float)))
    prior = pd.read_csv(ROOT / contract["design"]["fixed_context"] / "fixed_initial_state.csv", float_precision="round_trip")
    latent = [i for i, name in enumerate(names) if name not in measured]
    check("unmeasured_initialization_exact", np.array_equal(state[latent], prior.initial_value.to_numpy()[latent]))
    check("no_historical_redox_migration", state[names.index("NAD")] == state[names.index("NADH")] == 1.)
    plan = read(out / "exploratory_probe_plan.json")
    params = read(out / "frozen_parameters.json")
    _, reactions, matrix = rbc_reaction_matrix(params.get("sam_adenylate_stoichiometry", "biochemical_transfer"))
    check("coverage", len(plan["cases"]) == summary["case_count"] == 19 and summary["integrations_completed"] == 38)
    endpoint = pd.read_csv(out / "J4_endpoint_diagnostics.csv", float_precision="round_trip")
    flux_table = pd.read_csv(out / "executed_flux_integrals.csv", float_precision="round_trip")
    single = pd.read_csv(out / "single_group_responses.csv", float_precision="round_trip")
    mixed = pd.read_csv(out / "paired_group_interactions.csv", float_precision="round_trip")
    check("complete_table_sizes", len(endpoint) == 55*38 and len(flux_table) == len(reactions)*38
          and len(single) == (115+len(reactions))*12 and len(mixed) == (115+len(reactions))*6)
    features, trajectories, integrals, minimum, negative = {}, {}, {}, np.inf, 0
    feature_names = names[:113]+["energy_charge", "NADH_fraction"]+list(reactions)
    feature_kinds = ["J4_concentration"]*113+["J4_energy_charge", "J4_NADH_fraction"]+["J1_J4_executed_flux_integral"]*len(reactions)
    for case in plan["cases"]:
        for solver in ("strict", "ultrastrict"):
            label = f"{case['case_id']}_{solver}"
            directory = out / label
            accepted = np.load(directory / "accepted_solver_states.npz")
            dense = np.load(directory / "dense_full_states_fluxes.npz")
            x, v, native, factors = [dense[key] for key in ("states", "effective_flux", "native_flux", "availability_factors")]
            minimum = min(minimum, float(np.min(x[:113])), float(np.min(accepted["states"][:113])))
            negative += int(np.count_nonzero(x[:113] < 0))+int(np.count_nonzero(accepted["states"][:113] < 0))
            check(f"raw_initialization:{label}", np.array_equal(accepted["states"][:, 0], state)
                  and accepted["time"][[0, -1]].tolist() == [1., 4.] and np.isfinite(x).all()
                  and np.isfinite(accepted["states"]).all() and np.min(x[:113]) >= -1e-10)
            for pair in (("NAD", "NADH"), ("NADP", "NADPH")):
                total = x[[names.index(p) for p in pair]].sum(axis=0)
                check(f"redox_pair_conservation:{label}:{pair[0]}", np.max(np.abs(total-state[[names.index(p) for p in pair]].sum())) <= 1e-7)
            energy = pd.read_csv(directory / "executed_timeseries.csv", float_precision="round_trip")
            total = energy[["ATP", "ADP", "AMP"]].to_numpy().sum(axis=1)
            check(f"energy_charge_timeseries:{label}", np.allclose(total, energy.ATP_ADP_AMP, rtol=1e-12, atol=1e-12)
                  and np.allclose((energy.ATP+.5*energy.ADP)/total, energy.energy_charge, rtol=1e-12, atol=1e-12))
            actual_params = read(directory / "parameters.json")
            check(f"restricted_parameters:{label}", actual_params == {**params, **case["parameter_overrides"]}
                  and actual_params.get("vmax_VHK", 5.) <= 5.)
            check(f"rate_and_balance_closure:{label}", np.allclose(v, native*factors, rtol=1e-12, atol=1e-12)
                  and np.max(np.abs(matrix@v-dense["executed_rhs"])) <= 1e-7
                  and np.all((factors >= 0)&(factors <= 1)))
            # Reconstruct signed-consumer factors without using the limiter helper.
            availability = np.clip(x[:113]/1e-3, 0., 1.)
            for j, reaction in enumerate(reactions):
                consumers = ((matrix[:, j, None] < 0)&(native[j] > 0))|((matrix[:, j, None] > 0)&(native[j] < 0))
                expected = np.min(np.where(consumers, availability, 1.), axis=0)
                check(f"signed_consumer_factor:{label}:{reaction}", np.allclose(expected, factors[j], rtol=1e-12, atol=1e-12))
            sample = np.unique(np.linspace(0, len(dense["time"])-1, 9, dtype=int))
            maximum = 0.
            for position in sample:
                audit = {}
                derivative = equadiff_brodbar(float(dense["time"][position]), x[:, position].copy(), custom_params=actual_params,
                    positivity_policy="reaction_consistent", reaction_availability_threshold=1e-3, curve_fit_strength=0., numerical_audit=audit)
                expected = np.array([audit["effective_fluxes"][r] for r in reactions])
                maximum = max(maximum, float(np.max(np.abs(expected-v[:, position]))),
                              float(np.max(np.abs(derivative[:113]-dense["executed_rhs"][:, position]))))
            check(f"executable_kernel_nodes:{label}", maximum <= 1e-12)
            values = accepted["states"][:, -1]
            a, d, m = [float(values[names.index(p)]) for p in ("ATP", "ADP", "AMP")]
            integral = np.load(directory / "interval_integrals.npz")
            integrals[(case["case_id"], solver)] = {key: integral[key] for key in integral.files if key != "boundaries"}
            flux = integral["effective_flux"].sum(axis=1)
            features[(case["case_id"], solver)] = np.r_[values[:113], (a+.5*d)/(a+d+m),
                values[names.index("NADH")]/(values[names.index("NAD")]+values[names.index("NADH")]), flux]
            selected = endpoint[(endpoint.case == case["case_id"])&(endpoint.solver == solver)].set_index("pool")
            check(f"all_endpoints:{label}", np.array_equal(selected.loc[measured, "model_J4_mM"], values[[names.index(p) for p in measured]])
                  and np.array_equal(selected.loc[measured, "reference_J4_mM"], frame.iloc[:, 2].to_numpy(dtype=float))
                  and selected.biological_accuracy_pass.isna().all() and not selected.loc[["B13PG", "P2G"], "independent_observation"].any())
            saved = flux_table[(flux_table.case == case["case_id"])&(flux_table.solver == solver)].set_index("reaction")
            check(f"all_integral_features:{label}", np.array_equal(saved.loc[list(reactions), "executed_J1_J4_integral_mM"], flux))
            budgets = pd.read_csv(directory / "window_pool_budgets.csv", float_precision="round_trip")
            contributions = pd.read_csv(directory / "window_reaction_contributions.csv", float_precision="round_trip")
            for window in budgets.window.unique():
                group = budgets[budgets.window == window].set_index("pool")
                terms = contributions[contributions.window == window]
                for pool in ("ATP", "ADP", "AMP", "ATP_ADP_AMP"):
                    net = terms[terms.pool == pool].executed_contribution_mM.sum()
                    check(f"signed_budget:{label}:{window}:{pool}", abs(net-group.loc[pool, "net_mM"]) <= 1e-12
                          and abs(group.loc[pool, "state_change_mM"]-net) <= 1e-6+1e-3*max(abs(net), abs(group.loc[pool, "state_change_mM"])))
                total = terms[terms.pool == "ATP_ADP_AMP"].set_index("reaction")
                check(f"total_pool_stoichiometry:{label}:{window}", total.coefficient.to_dict() == TOTAL_TERMS)
            limiter = pd.read_csv(directory / "sampled_limiter_participation.csv", float_precision="round_trip")
            for reaction, group in limiter.groupby("reaction"):
                check(f"sampled_limiter_sum:{label}:{reaction}", np.isclose(group.sampled_loss_share.sum(), 1., rtol=1e-12, atol=1e-12)
                      and np.isclose(group.sampled_absolute_loss_mM.sum(), group.sampled_total_absolute_loss_mM.iloc[0], rtol=1e-12, atol=1e-12))
            numerical = read(directory / "numerical_audit.json")
            quadrature = pd.read_csv(directory / "quadrature_checks.csv")
            check(f"numerical_receipts:{label}", numerical == summary["cases"][label]
                  and numerical["numerical_integrity_pass"] and len(quadrature) == 223 and quadrature.passes.all())
            trajectories[(case["case_id"], solver)] = (dense["time"], x)
    for case in plan["cases"]:
        key = case["case_id"]
        a_time, a_state = trajectories[(key, "strict")]
        b_time, b_state = trajectories[(key, "ultrastrict")]
        uniform = np.linspace(1., 4., 601)
        ia, ib = np.searchsorted(a_time, uniform), np.searchsorted(b_time, uniform)
        check(f"common_uniform_nodes:{key}", np.array_equal(a_time[ia], uniform) and np.array_equal(b_time[ib], uniform))
        difference = np.abs(a_state[:113, ia]-b_state[:113, ib])
        check(f"independent_uniform_state_convergence:{key}", np.all(difference <= 1e-5+.01*np.abs(b_state[:113, ib])))
        for quantity, a in integrals[(key, "strict")].items():
            b = integrals[(key, "ultrastrict")][quantity]
            check(f"independent_integral_convergence:{key}:{quantity}", np.all(np.abs(a-b) <= 1e-5+.01*np.abs(b)))
    # Reconstruct finite differences directly from case coordinates and verified features.
    for solver in ("strict", "ultrastrict"):
        values = {tuple(c["log_scales"].get(g, 0.) for g in GROUPS): features[(c["case_id"], solver)] for c in plan["cases"]}
        origin = (0., 0., 0.)
        for i, group in enumerate(GROUPS):
            for step in (.05, .10):
                lo, hi = list(origin), list(origin)
                lo[i], hi[i] = -step, step
                expected = (values[origin]-values[tuple(lo)])/step if i == 0 else (values[tuple(hi)]-values[tuple(lo)])/(2*step)
                selected = single[(single.solver == solver)&(single.group == group)&(single.log_step == step)]
                for kind in dict.fromkeys(feature_kinds):
                    positions = [j for j, k in enumerate(feature_kinds) if k == kind]
                    saved = selected[selected.kind == kind].set_index("name").loc[[feature_names[j] for j in positions]]
                    check(f"single_response:{solver}:{group}:{step}:{kind}", np.allclose(saved.response_per_log_capacity, expected[positions], rtol=1e-12, atol=1e-12))
        for i, j in itertools.combinations(range(3), 2):
            h = .05
            expected = np.zeros_like(values[origin])
            coords = ((0., 1/h), (-h, -1/h)) if i == 0 else ((h, 1/(2*h)), (-h, -1/(2*h)))
            for (a, wa), (b, wb) in itertools.product(coords, ((h, 1/(2*h)), (-h, -1/(2*h)))):
                point = list(origin)
                point[i], point[j] = a, b
                expected += wa*wb*values[tuple(point)]
            selected = mixed[(mixed.solver == solver)&(mixed.first_group == GROUPS[i])&(mixed.second_group == GROUPS[j])]
            for kind in dict.fromkeys(feature_kinds):
                positions = [k for k, label in enumerate(feature_kinds) if label == kind]
                saved = selected[selected.kind == kind].set_index("name").loc[[feature_names[k] for k in positions]]
                check(f"mixed_response:{solver}:{GROUPS[i]}:{GROUPS[j]}:{kind}", np.allclose(saved.mixed_response_per_log_capacity_squared, expected[positions], rtol=1e-12, atol=1e-12))
    convergence = pd.read_csv(out / "strict_ultrastrict_convergence.csv")
    check("convergence_coverage", len(convergence) == 19*336 and convergence.passes.all()
          and summary["numerical_diagnostic_passes"] and summary["quadrature_check_count"] == 38*223)
    suites = list(ET.parse(out / "qa_results.xml").getroot().iter("testsuite"))
    qa = {key: sum(int(s.get(key, 0)) for s in suites) for key in ("tests", "failures", "errors", "skipped")}
    check("QA", qa["tests"] > 0 and qa["errors"] == qa["failures"] == qa["skipped"] == 0)
    resolution = []
    for table, keys, value in ((single, ["group", "log_step", "kind", "name"], "response_per_log_capacity"),
                               (mixed, ["first_group", "second_group", "kind", "name"], "mixed_response_per_log_capacity_squared")):
        paired = table.pivot(index=keys, columns="solver", values=value).reset_index()
        paired["strict_ultrastrict_absolute_difference"] = (paired.strict-paired.ultrastrict).abs()
        paired["same_nonzero_sign"] = np.sign(paired.strict) == np.sign(paired.ultrastrict)
        paired["relative_difference_to_ultrastrict"] = paired.strict_ultrastrict_absolute_difference/paired.ultrastrict.abs().replace(0., np.nan)
        paired["response_type"] = value
        resolution.extend(paired.to_dict("records"))
    pd.DataFrame(resolution).to_csv(out / "response_solver_differences.csv", index=False)
    report = {"independent_checks_pass": all(c["passes"] for c in checks), "check_count": len(checks), "checks": checks,
        "minimum_independently_checked_raw_concentration_mM": minimum, "negative_stored_values_count": negative,
        "qa": qa, "scope": "all accepted/dense stored concentrations and factors, sampled executable kernel parity, signed window budgets, all endpoint and response features; no new ODE integrations"}
    write_json(out / "independent_verification.json", report)
    if not report["independent_checks_pass"]:
        raise ValueError([c["name"] for c in checks if not c["passes"]])
    final.update(independently_verified_at=datetime.now(timezone.utc).isoformat(), independent_archive_checks_pass=True,
        independent_archive_check_count=len(checks), qa=qa,
        supporting_code_sha256={str(p): file_hash(p) for p in (Path(__file__), ROOT / "scripts/finalize_exploratory_energy_sensitivity.py",
            ROOT / "qa/test_exploratory_energy_sensitivity.py")},
        output_sha256={str(p.relative_to(out)): file_hash(p) for p in out.rglob("*") if p.is_file() and p.name != "final_verification.json"})
    write_json(out / "final_verification.json", final)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    result = verify(parser.parse_args().out.resolve())
    print({k: v for k, v in result.items() if k != "checks"})
