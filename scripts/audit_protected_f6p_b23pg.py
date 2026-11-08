"""Read-only F6P/B23PG/PEP attribution on sealed J1-J10 executed fluxes."""

import argparse
import csv
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fla_executed_attribution import aggregate_windows, limiting_loss_attribution, signed_pool_contributions
from fla_joint_calibration import JointRHS, unpack
from run_glut_only_free_replay import sha, write, close
from verify_protected_joint import verify as verify_parent

CONFIG = ROOT / "config/fla_f6p_b23pg_executed_audit.json"
EXPECTED = {
    "F6P": {"VPGI": 1., "VPFK": -1., "VTKL2": 1., "VTAL": 1.},
    "B23PG": {"VDPGM": 1., "V23DPGP": -1.},
    "PEP": {"VENOPGM": 1., "VPK": -1., "VPEP_PASE": -1.},
    "B13PG": {"VGAPDH": 1., "VPGK": -1., "VDPGM": -1.},
}


def check_initialization(archive, initial, end_day):
    initial = np.asarray(initial)
    if (not np.array_equal(archive["initial"], initial)
            or not np.array_equal(archive["accepted_states"][:, 0], initial)
            or archive["accepted_time"][-1] != end_day):
        raise ValueError("changed actual initial state or truncated replay")
    # Dense BDF evaluation at the initial knot can differ by one rounding bit.
    tolerance = 4*np.spacing(np.maximum(np.abs(initial), 1.))
    if np.any(np.abs(archive["states"][:, 0]-initial) > tolerance):
        raise ValueError("initial dense evaluation differs beyond machine rounding")


def indices_exact(time, requested):
    time, requested = np.asarray(time), np.asarray(requested)
    if (time.ndim != 1 or not time.size or requested.ndim != 1 or not np.all(np.isfinite(requested)) or not np.all(np.isfinite(time))
            or np.any(np.diff(time) <= 0)):
        raise ValueError("finite increasing time grid required")
    indices = np.searchsorted(time, requested)
    if np.any(indices >= len(time)) or not np.array_equal(time[indices], requested):
        raise ValueError("exact archived endpoints required; no interpolation")
    return indices


def weighted_windows(values, archive, order, windows):
    values = np.asarray(values, float)
    weights, cells = archive[f"q{order}_weights"], archive[f"q{order}_intervals"]
    if (values.ndim != 2 or values.shape[1] != len(weights) or not np.all(np.isfinite(values))
            or np.any(weights <= 0) or not np.all(np.isfinite(weights))
            or cells.dtype.kind not in "iu" or np.any(cells < 0)
            or np.any(cells >= len(archive["boundaries"])-1)):
        raise ValueError("finite aligned values and positive exact quadrature weights required")
    daily = np.vstack([np.bincount(cells, weights=weights*row,
                                  minlength=len(archive["boundaries"])-1) for row in values])
    return aggregate_windows(daily, archive["boundaries"], windows)


def budgets(archive, pools, windows):
    names, reactions = archive["pool_names"].tolist(), archive["reactions"].tolist()
    pool_rows, reaction_rows = [], []
    for pool in pools:
        index = names.index(pool)
        columns = np.flatnonzero(archive["matrix"][index])
        coefficients = archive["matrix"][index, columns]
        raw = coefficients[:, None]*archive["q8_raw_rates"][columns]
        executed = signed_pool_contributions(coefficients, archive["q8_executed_rates"][columns])
        amounts = {key: weighted_windows(value, archive, 8, windows) for key, value in
                   {"raw": raw, "executed": executed["net"], "production": executed["production"],
                    "consumption": executed["consumption"], "modifier": executed["net"]-raw}.items()}
        for j, (window, start, end) in enumerate(windows):
            state = archive["states"][index, indices_exact(archive["time"], [start, end])]
            net = float(amounts["executed"][:, j].sum())
            pool_rows.append({"window": window, "start_day": start, "end_day": end, "pool": pool,
                "state_start_mM": float(state[0]), "state_end_mM": float(state[1]),
                "state_change_mM": float(state[1]-state[0]), "executed_net_mM": net,
                "raw_net_mM": float(amounts["raw"][:, j].sum()),
                "production_mM": float(amounts["production"][:, j].sum()),
                "consumption_mM": float(amounts["consumption"][:, j].sum()),
                "closure_residual_mM": float(state[1]-state[0]-net)})
            for i, column in enumerate(columns):
                reaction_rows.append({"window": window, "start_day": start, "end_day": end,
                    "pool": pool, "reaction": reactions[column], "coefficient": float(coefficients[i]),
                    **{key+"_mM": float(value[i, j]) for key, value in amounts.items()}})
    return pool_rows, reaction_rows


def limiter_rows(archive, reactions_to_check, threshold, windows, order):
    names, reactions = archive["pool_names"].tolist(), archive["reactions"].tolist()
    rows = []
    for reaction in reactions_to_check:
        column = reactions.index(reaction)
        raw, executed = archive[f"q{order}_raw_rates"][column], archive[f"q{order}_executed_rates"][column]
        allocation = limiting_loss_attribution(archive[f"q{order}_states"][:len(names)], raw,
                                               archive["matrix"][:, column], threshold=threshold)
        if not np.allclose(raw*allocation["factors"], executed, rtol=1e-12, atol=1e-14):
            raise ValueError("saved executed rate differs from complete-reaction limiter")
        total = weighted_windows(np.abs(raw-executed)[None, :], archive, order, windows)[0]
        raw_abs = weighted_windows(np.abs(raw)[None, :], archive, order, windows)[0]
        executed_abs = weighted_windows(np.abs(executed)[None, :], archive, order, windows)[0]
        for pool in np.flatnonzero(archive["matrix"][:, column]):
            amounts = weighted_windows(allocation["loss_by_pool"][pool:pool+1], archive, order, windows)[0]
            active_time = weighted_windows(allocation["active"][pool:pool+1].astype(float), archive, order, windows)[0]
            for j, (window, start, end) in enumerate(windows):
                rows.append({"order": order, "window": window, "reaction": reaction,
                    "limiting_pool": names[pool], "loss_mM": float(amounts[j]),
                    "total_absolute_rate_loss_mM": float(total[j]),
                    "raw_absolute_integral_mM": float(raw_abs[j]),
                    "executed_absolute_integral_mM": float(executed_abs[j]),
                    "retained_fraction": float(executed_abs[j]/raw_abs[j]) if raw_abs[j] else None,
                    "loss_share": float(amounts[j]/total[j]) if total[j] else None,
                    "active_time_fraction": float(active_time[j]/(end-start))})
    return rows


def compare_budgets(control, candidate, keys, values):
    baseline = {tuple(row[k] for k in keys): row for row in control}
    if len(baseline) != len(control) or len(candidate) != len(control) or set(baseline) != {tuple(row[k] for k in keys) for row in candidate}:
        raise ValueError("unique matched budget identities required")
    return [{**{k: row[k] for k in keys}, **{v+"_delta": row[v]-baseline[tuple(row[k] for k in keys)][v]
                                        for v in values}} for row in candidate]


def capacity_decomposition(baseline, candidate, factor):
    if not np.isfinite(factor) or factor <= 0 or not np.isfinite(baseline+candidate):
        raise ValueError("finite integrals and a positive multiplicative factor required")
    return {"capacity_at_control_states_mM": (factor-1)*baseline,
            "state_response_remainder_mM": candidate-factor*baseline,
            "raw_integral_delta_mM": candidate-baseline,
            "interpretation": "ordered_fixed_state_accounting_not_a_new_ODE_or_causal_effect"}


def sampled_rate_checks(archives, control_parameters, control_kinetics, selected):
    rhs = {"control": JointRHS(control_parameters, control_kinetics),
           "protected": JointRHS(selected["parameters"], selected["glucose_kinetics"])}
    checked = 0
    for case, archive in archives.items():
        for node in np.unique(np.linspace(0, len(archive["q8_nodes"])-1, 7).astype(int)):
            time, state = archive["q8_nodes"][node], archive["q8_states"][:, node]
            raw, executed, _ = rhs[case].rates(time, state)
            if not np.array_equal(raw, archive["q8_raw_rates"][:, node]) or not np.array_equal(executed, archive["q8_executed_rates"][:, node]):
                raise ValueError("live/saved rate sampling mismatch")
            raw0, exe0, _ = rhs["control"].rates(time, state)
            raw1, exe1, _ = rhs["protected"].rates(time, state)
            j = rhs[case].reactions.index("VPFK")
            if not np.allclose([raw1[j], exe1[j]], selected["factors"]["investment"]*np.array([raw0[j], exe0[j]]), rtol=1e-12, atol=1e-14):
                raise ValueError("PFK law is not multiplicative at shared fixed states")
            checked += 1
    return checked


def proposed_guards(control, candidate, observations, frozen, config):
    pools = frozen["design"]["pools"]+config["proposed_added_RMSE_guards"]
    if len(set(pools)) != len(pools) or set(pools) & set(config["source_aliases"]):
        raise ValueError("canonical nonduplicated proposed channels required")
    times = frozen["design"]["training_times"]
    caps, pointwise = [], []
    design = frozen["design"]
    for pool in pools:
        target = np.array(observations["values"][pool])[indices_exact(observations["time"], times)]
        errors = []
        for archive in (control, candidate):
            i = archive["pool_names"].tolist().index(pool)
            errors.append(archive["states"][i, indices_exact(archive["time"], times)]-target)
        reference, current = (float(np.sqrt(np.mean(e**2))) for e in errors)
        allowance = design["guard_numerical_atol_mM"]+design["guard_numerical_rtol"]*reference
        caps.append({"pool": pool, "reference_RMSE_mM": reference, "candidate_RMSE_mM": current,
            "fit_limit_mM": reference+design["fitting_allowance_fraction"]*allowance,
            "audit_limit_mM": reference+allowance, "candidate_pass": current <= reference+allowance})
        if pool in config["proposed_pointwise_guards"]:
            for day, base, current in zip(times, np.abs(errors[0]), np.abs(errors[1])):
                allowance = design["guard_numerical_atol_mM"]+design["guard_numerical_rtol"]*base
                pointwise.append({"pool": pool, "day": day, "reference_absolute_error_mM": float(base),
                    "candidate_absolute_error_mM": float(current),
                    "fit_limit_mM": float(base+design["fitting_allowance_fraction"]*allowance),
                    "audit_limit_mM": float(base+allowance), "candidate_pass": bool(current <= base+allowance)})
    return {"status": "proposal_only_not_activated_or_used_to_reselect_parent", "RMSE_guards": caps,
        "pointwise_guards": pointwise, "source_aliases_excluded": config["source_aliases"],
        "future_likelihood_channels": pools, "observation_days": times, "initial_or_late_residuals": False,
        "remaining_source_representations_not_hard_guarded": 55-len(pools),
        "allowance_is_assay_noise": False, "biological_accuracy_established": False}


def save_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot(out, archives, observations, reaction_deltas):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 3, figsize=(15, 10), constrained_layout=True)
    colors = {"control": "#247888", "protected": "#b44468"}
    for row, pool in enumerate(("F6P", "B23PG", "PEP")):
        ax = axes[row, 0]
        for case, archive in archives.items():
            i = archive["pool_names"].tolist().index(pool)
            ax.plot(archive["time"], archive["states"][i], color=colors[case],
                    linestyle="-" if case == "protected" else "--", label=case)
        times = np.array([1., 4., 8.])
        target = np.array(observations["values"][pool])[indices_exact(observations["time"], times)]
        ax.scatter(times, target, color="#242424", marker="D", s=26, zorder=4, label="Nominal source")
        ax.set(title=pool, xlabel="Model day", ylabel="Concentration (mM)", xlim=(1, 10))
        ax.legend(fontsize=8)
        for col, window in enumerate(("J1_J4", "J4_J8"), 1):
            selected = [r for r in reaction_deltas if r["pool"] == pool and r["window"] == window]
            vals = [r["executed_mM_delta"] for r in selected]
            ax = axes[row, col]
            ax.barh([r["reaction"] for r in selected], vals, color=["#b44468" if v > 0 else "#247888" for v in vals])
            ax.axvline(0, color="#222222", linewidth=.7)
            for i, v in enumerate(vals):
                ax.annotate(f"{v:+.4f}", (v, i), xytext=(4 if v >= 0 else -4, 0),
                            textcoords="offset points", ha="left" if v >= 0 else "right", va="center", fontsize=8)
            ax.margins(x=.35)
            ax.set(title=pool+" "+window.replace("_", "-"), xlabel="Change in signed executed contribution (mM)")
    fig.suptitle("Fixed-parameter trajectory accounting: protected minus GLUT-only control", fontsize=14)
    fig.savefig(out / "f6p_b23pg_pep_attribution.png", dpi=170)
    plt.close(fig)


def audit(out):
    if out.exists():
        raise ValueError("fresh audit directory required; do not overwrite scientific evidence")
    config = json.loads(CONFIG.read_text())
    parent = ROOT / config["parent_archive"]
    parent_check = verify_parent(parent)
    frozen = json.loads((parent / "execution_design.json").read_text())
    selected = json.loads((parent / "summary.json").read_text())["selected"]
    observations = json.loads((parent / "observations.json").read_text())
    for alias, canonical in config["source_aliases"].items():
        if observations["values"][alias] != observations["values"][canonical]:
            raise ValueError("declared source alias no longer matches; resolve observation contract")
    base = ROOT / frozen["parent_design"]["source_archive"]
    for key, directory in (("input_sha256", ROOT), ("output_sha256", base)):
        for path, digest in json.loads((base / "manifest.json").read_text()).get(key, {}).items():
            if sha(directory/path) != digest:
                raise ValueError("changed baseline archive or its source:"+path)
    numerical = json.loads((base / "execution_design.json").read_text())["design"]
    threshold = frozen["parent_design"]["reaction_availability_threshold_mM"]
    if threshold != .001:
        raise ValueError("this audit preserves the parent0.001mM threshold")
    control_parameters, control_kinetics, _ = unpack(np.zeros(6), frozen["parameters"], frozen["candidate"]["glucose_kinetics"],
                     frozen["resolved_capacities"], frozen["parent_design"]["factor_bounds"])
    out.mkdir(parents=True)
    contract = {"config": config, "parent_verification": parent_check, "new_ODE_integrations": 0,
        "new_optimizer_calls": 0, "parent_selected_label": selected["label"],
        "capacity_parameters": {"control": control_parameters, "protected": selected["parameters"]},
        "glucose_kinetics": {"control": control_kinetics, "protected": selected["glucose_kinetics"]},
        "initial_sha256": sha(ROOT/frozen["parent_design"]["initial_context"]/"frozen_initial_state.npz")}
    write(out / "execution_contract.json", contract)
    inputs = {str(p): h for p, h in frozen["input_sha256"].items()}
    for p in (CONFIG, Path(__file__), ROOT/"qa/test_protected_f6p_b23pg.py",
              ROOT/"scripts/verify_protected_f6p_b23pg.py", ROOT/"src/fla_executed_attribution.py",
              parent/"execution_design.json", parent/"summary.json", parent/"observations.json", parent/"manifest.json",
              base/"manifest.json"):
        inputs[p.relative_to(ROOT).as_posix()] = sha(p)
    all_pools, all_reactions, all_limiters, checks, archives, sample_rows = [], [], [], [], {}, []
    for case in ("control", "protected"):
        for profile in config["profiles"]:
            path = (base/"J1_J10"/f"glut_real_candidate_{profile}"/"replay.npz" if case == "control" else
                    parent/"audits"/(selected["label"]+"_J10")/"J1_J10"/f"glut_real_candidate_{profile}"/"replay.npz")
            inputs[path.relative_to(ROOT).as_posix()] = sha(path)
            with np.load(path) as z:
                archive = {k: z[k] for k in z.files}
            names, reactions = archive["pool_names"].tolist(), archive["reactions"].tolist()
            check_initialization(archive, frozen["initial"], config["end_day"])
            minimum = min(archive["states"][:113].min(), archive["accepted_states"][:113].min(),
                          archive["q4_states"][:113].min(), archive["q8_states"][:113].min())
            if minimum < numerical["negative_tolerance_mM"]:
                raise ValueError("negative saved concentration outside the parent contract")
            for pool, expected in EXPECTED.items():
                row = archive["matrix"][names.index(pool)]
                if {reactions[j]: float(row[j]) for j in np.flatnonzero(row)} != expected:
                    raise ValueError("unexpected exact balance:"+pool)
            for order in (4, 8):
                for kind in ("raw", "executed"):
                    windows = [(str(i), l, r) for i, (l, r) in enumerate(zip(archive["boundaries"][:-1], archive["boundaries"][1:]))]
                    reconstructed = weighted_windows(archive[f"q{order}_{kind}_rates"], archive, order, windows)
                    passed = close(reconstructed, archive[f"{kind}{order}"], numerical, "quadrature")
                    checks.append({"case": case, "profile": profile, "quantity": kind+str(order)+"_reconstruction", "passed": bool(passed.all())})
            for kind in ("raw", "executed"):
                checks.append({"case": case, "profile": profile, "quantity": kind+"_gauss4_8",
                    "passed": bool(close(archive[kind+"4"], archive[kind+"8"], numerical, "quadrature").all())})
            pool_rows, reaction_rows = budgets(archive, config["pools"], config["windows"])
            for row in pool_rows:
                passed = close(row["state_change_mM"], row["executed_net_mM"], numerical, "quadrature")
                checks.append({"case": case, "profile": profile, "quantity": row["pool"]+":"+row["window"]+"_closure", "passed": bool(passed)})
            for order in (4, 8):
                rows = limiter_rows(archive, config["limiter_reactions"], threshold, config["windows"], order)
                all_limiters.extend({"case": case, "profile": profile, **r} for r in rows)
            all_pools.extend({"case": case, "profile": profile, **r} for r in pool_rows)
            all_reactions.extend({"case": case, "profile": profile, **r} for r in reaction_rows)
            for pool in config["pools"]:
                if pool not in observations["values"]:
                    continue
                for day in config["observation_days"]:
                    value = float(archive["states"][names.index(pool), indices_exact(archive["time"], [day])[0]])
                    source = observations["values"][pool][indices_exact(observations["time"], [day])[0]]
                    sample_rows.append({"case": case, "profile": profile, "pool": pool, "day": day,
                        "prediction_mM": value, "nominal_source_mM": source, "residual_mM": value-source,
                        "source_alias_not_independent": pool in config["source_aliases"],
                        "used_in_this_audit_for_calibration": False})
            if profile == "ultrastrict":
                archives[case] = archive
    allocations = {(r["case"], r["profile"], r["order"], r["window"], r["reaction"], r["limiting_pool"]): r
                   for r in all_limiters}
    allocation_checks = []
    for row in all_limiters:
        if row["order"] != 8:
            continue
        key = (row["case"], row["profile"], 4, row["window"], row["reaction"], row["limiting_pool"])
        other = allocations[key]
        allocation_checks.append({"case": row["case"], "profile": row["profile"],
            "quantity": row["reaction"]+":"+row["limiting_pool"]+":"+row["window"]+"_loss_gauss4_8",
            "passed": bool(close(row["loss_mM"], other["loss_mM"], numerical, "quadrature")),
            "difference_mM": abs(row["loss_mM"]-other["loss_mM"])})
    # Min-consumer labels can switch inside a quadrature segment. Resolution of
    # each allocation is reported separately from additive total-rate closure.
    for case in ("control", "protected"):
        coarse = [r for r in all_pools if r["case"] == case and r["profile"] == "strict"]
        fine = [r for r in all_pools if r["case"] == case and r["profile"] == "ultrastrict"]
        for row0, row1 in zip(coarse, fine):
            checks.append({"case": case, "profile": "strict_vs_ultrastrict",
                "quantity": row0["pool"]+":"+row0["window"]+"_state_and_budget",
                "passed": bool(close([row0["state_end_mM"], row0["executed_net_mM"]],
                                     [row1["state_end_mM"], row1["executed_net_mM"]], numerical, "comparison").all())})
    pool_delta = compare_budgets([r for r in all_pools if r["case"] == "control" and r["profile"] == "ultrastrict"],
        [r for r in all_pools if r["case"] == "protected" and r["profile"] == "ultrastrict"],
        ("pool", "window"), ("state_change_mM", "executed_net_mM", "raw_net_mM"))
    reaction_delta = compare_budgets([r for r in all_reactions if r["case"] == "control" and r["profile"] == "ultrastrict"],
        [r for r in all_reactions if r["case"] == "protected" and r["profile"] == "ultrastrict"],
        ("pool", "reaction", "window"), ("raw_mM", "executed_mM", "modifier_mM"))
    rate_decompositions = []
    for window, _, _ in config["windows"]:
        values = []
        for case in ("control", "protected"):
            row = next(r for r in all_reactions if r["case"] == case and r["profile"] == "ultrastrict"
                       and r["pool"] == "F6P" and r["reaction"] == "VPFK" and r["window"] == window)
            values.append(-row["raw_mM"])
        rate_decompositions.append({"reaction": "VPFK", "window": window,
            **capacity_decomposition(*values, selected["factors"]["investment"])})
    # Same-state rate checks establish the multiplicative PFK comparison without new integration.
    sampled_nodes = sampled_rate_checks(archives, control_parameters, control_kinetics, selected)
    proposal = proposed_guards(archives["control"], archives["protected"], observations, frozen, config)
    if not all(r["passed"] for r in checks):
        raise ValueError("original numerical closure contract failed; preserve partial audit")
    for name, rows in (("pool_budgets", all_pools), ("reaction_budgets", all_reactions), ("limiter_attribution", all_limiters),
                       ("pool_deltas", pool_delta), ("reaction_deltas", reaction_delta), ("PFK_capacity_state_split", rate_decompositions),
                       ("numerical_checks", checks), ("limiter_resolution_checks", allocation_checks),
                       ("source_time_predictions", sample_rows)):
        save_csv(out/(name+".csv"), rows)
    write(out/"proposed_guard_contract.json", proposal)
    plot(out, archives, observations, reaction_delta)
    summary = {"numerical_checks_passed": len(checks), "all_numerical_checks_pass": True,
        "parent_verification_checks": parent_check["checks"], "source_aliases_confirmed": config["source_aliases"],
        "new_ODE_integrations": 0, "new_optimizer_calls": 0, "parameters_changed": False,
        "initial_states_changed": False, "source_values_changed": False, "production_promoted": False,
        "full_input_hashes": len(inputs), "pool_rows": len(all_pools), "reaction_rows": len(all_reactions),
        "sampled_live_rate_and_same_state_PFK_checks": sampled_nodes,
        "limiter_rows": len(all_limiters), "maximum_pool_closure_residual_mM": max(abs(r["closure_residual_mM"]) for r in all_pools),
        "limiter_allocation_resolution_passes": sum(r["passed"] for r in allocation_checks),
        "limiter_allocation_resolution_checks": len(allocation_checks),
        "unresolved_limiter_allocations_must_not_be_reported_as_precise_shares": True,
        "proposed_failed_RMSE_pools": [r["pool"] for r in proposal["RMSE_guards"] if not r["candidate_pass"]],
        "proposed_failed_pointwise": [{"pool": r["pool"], "day": r["day"]} for r in proposal["pointwise_guards"] if not r["candidate_pass"]],
        "limiter_attribution_interpretation": config["attribution_interpretation"]}
    write(out/"summary.json", summary)
    for name, digest in inputs.items():
        if sha(ROOT/name) != digest:
            raise ValueError("input changed during audit:"+name)
    write(out/"manifest.json", {"input_sha256": inputs,
        "output_sha256": {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob("*")) if p.is_file()}})
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.out.resolve()), indent=2))
