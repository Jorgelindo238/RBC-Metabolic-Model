"""Coverage decisions, conditional sensitivity selection and executed budgets."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from fla_broad_protected_calibration import POOLS
from fla_joint_calibration import JointRHS
from run_protected_joint import verify_inputs, check_seal
from run_glut_only_free_replay import write, sha
from report_joint_glucose_energy import signed_budget


def report(archive, followup, out):
    if out.exists(): raise ValueError("fresh report directory required")
    f = verify_inputs(archive); s = json.loads((archive/"summary.json").read_text())
    coverage = json.loads((archive/"coverage/summary.json").read_text())
    extra = json.loads((followup/"summary.json").read_text())
    obs = json.loads((archive/"observations.json").read_text())
    rhs = JointRHS(f["parameters"], f["kinetics"])
    hashes = {}
    def track(path): hashes[path.relative_to(ROOT).as_posix()] = sha(path); return path
    parent = ROOT/f["design"]["parent_archive"]
    base_path = parent/"audits"/(f["design"]["baseline_label"]+"_J15")/"J1_J15/glut_real_candidate_ultrastrict/replay.npz"
    files = [("baseline", base_path)]
    files += [(a["label"], archive/"audits"/(a["label"]+"_J15")/"J1_J15/glut_real_candidate_ultrastrict/replay.npz") for a in s["audits"]]
    rows, trajectories = [], {}
    source_t = np.array(obs["time"]); use = (source_t > 1)&(source_t <= 15)
    baseline_metrics = None
    for label, path in files:
        check_seal(path.parents[2])
        with np.load(track(path)) as a:
            names = a["pool_names"].tolist(); metrics = {}
            for p, values in obs["values"].items():
                predicted = a["states"][names.index(p), np.searchsorted(a["time"], source_t[use])]
                target = np.array(values)[use]
                metrics[p] = {"RMSE_mM": float(np.sqrt(np.mean((predicted-target)**2))),
                    "J15_mM": float(predicted[-1]), "nominal_J15_mM": float(target[-1]),
                    "predictions": predicted.tolist(), "known_alias": p in ("B13PG", "P2G")}
            if baseline_metrics is None: baseline_metrics = metrics
            for p, m in metrics.items(): m["RMSE_change_vs_baseline_mM"] = m["RMSE_mM"]-baseline_metrics[p]["RMSE_mM"]
            budgets = {}
            raw_rates, executed_rates, weights = a["q8_raw_rates"], a["q8_executed_rates"], a["q8_weights"]
            for p in ("ATP", "ADP", "AMP", "GLC", "PEP", "G6P", "F6P", "MET", "ADOMET", "SAH", "RIB", "GTP", "B13PG", "B23PG"):
                row = a["matrix"][names.index(p)]
                terms = row*a["executed8"].sum(axis=1)
                budgets[p] = {"executed": signed_budget(row, executed_rates, weights),
                    "raw_on_executed_trajectory": signed_budget(row, raw_rates, weights),
                    "net_executed_integral_mM": float(terms.sum()),
                    "state_change_mM": float(a["states"][names.index(p), -1]-a["states"][names.index(p), 0]),
                    "reaction_contributions_mM": {r: float(v) for r, v in zip(a["reactions"].tolist(), terms) if v != 0}}
            other_increases = [p for p, m in metrics.items() if p not in POOLS and m["RMSE_change_vs_baseline_mM"] > 0]
            rows.append({"label": label, "all55_metrics": metrics, "budgets": budgets,
                "other44_raw_error_increases": len(other_increases),
                "largest_other_increases_mM": {p: metrics[p]["RMSE_change_vs_baseline_mM"] for p in sorted(other_increases, key=lambda p:metrics[p]["RMSE_change_vs_baseline_mM"], reverse=True)[:8]},
                "error_changes_are_not_significance_tests": True})
            trajectories[label] = (a["time"].copy(), a["states"][[names.index(p) for p in POOLS]].copy())
    fixed_effects = {}
    for p in f["design"]["parameters"]:
        paths = [archive/"probes"/(p+"__"+direction)/"trajectory.npz" for direction in ("plus", "minus")]
        if not all(path.exists() for path in paths): continue
        with np.load(paths[0]) as plus, np.load(paths[1]) as minus:
            raw = (plus["fixed_state_raw_rates"]-minus["fixed_state_raw_rates"])/(2*f["design"]["log_step"])
            executed = (plus["fixed_state_executed_rates"]-minus["fixed_state_executed_rates"])/(2*f["design"]["log_step"])
        fixed_effects[p] = {"raw_ATP_balance_derivative_at_fixed_states": (rhs.matrix[rhs.names.index("ATP")]@raw).tolist(),
            "executed_ATP_balance_derivative_at_fixed_states": (rhs.matrix[rhs.names.index("ATP")]@executed).tolist(),
            "reaction_scope": f["parameter_scopes"][p], "same_state_effect_not_trajectory_causal_attribution": True}
    with np.load(archive/"sensitivity.npz") as a:
        cosine, names, jac = a["cosine"].copy(), a["parameter_names"].tolist(), a["adenylate_log_jacobian"].copy()
    pairs = sorted([{"a": names[i], "b": names[j], "absolute_cosine": abs(float(cosine[i, j]))}
        for i in range(len(names)) for j in range(i+1, len(names)) if abs(cosine[i, j]) >= .95], key=lambda r:r["absolute_cosine"], reverse=True)
    out.mkdir(parents=True)
    write(out/"comparison.json", {"ranking": s["ranking"], "proposed_single_levers": s["proposed_subset"],
        "original_validated_single_levers": s["validated_single_levers"], "original_admissibility": s["original_admissibility"],
        "baseline_log_error": s["baseline"]["diagnostics"]["adenylate_log_mean"], "probe_count": s["actual_fast_integrations"],
        "original_comparisons": rows, "fixed_state_effects": fixed_effects, "highly_correlated_effect_pairs": pairs,
        "singular_values": s["singular_values"], "local_rank": s["local_rank_at_relative_threshold_1e-6"],
        "local_nullity_lower_bound": len(names)-s["local_rank_at_relative_threshold_1e-6"],
        "network_context": "historical_no_active_coverage_branches", "joint_subset_tested": False,
        "confidence_intervals_or_global_identifiability_proved": False, "production_promoted": False})
    write(out/"coverage_decision.json", {"original_coverage": coverage, "separate_ARGSL_followup": extra,
        "new_ODE_options": {"VACLY": "implemented_off_requires_explicit_CIT_ATP_COA_kinetics",
                            "VARGN": "implemented_off_requires_explicit_ARG_kinetics"},
        "ARGSL_status": "source_supported_stoichiometric_only_followup_no_ODE_rate_added",
        "CITR_status": "static_model_exact_dynamics_blocked_not_proof_of_activity_above_assay_noise",
        "ASS1_status": "detected_in_Deep_Red_not_in_pinned_GEM_requires_separate_curation_not_a_CITR_production_solution",
        "no_source_values_or_initial_conditions_changed": True, "full_network_calibrated": False})
    write(out/"next_single_levers.json", {"status": "conditional_small_levers_for_next_feasibility_screen_not_fitted_constants",
        "levers": [{"parameter": r["parameter"], "direction": r["direction"],
            "baseline_value": f["resolved_parameters"][r["parameter"]]["value"],
            "tested_value": f["resolved_parameters"][r["parameter"]]["value"]*float(np.exp(r["direction"]*f["design"]["log_step"])),
            "source_probe": r["probe_label"]} for r in s["validated_single_levers"]],
        "activation_with_new_coverage_branches_tested": False, "combined_activation_tested": False,
        "new_optimization_run": False, "production_promoted": False})
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rank = s["ranking"][:12]
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), constrained_layout=True)
    pos = np.arange(len(rank))
    gains = [100*r["actual_adenylate_log_gain"]/s["baseline"]["diagnostics"]["adenylate_log_mean"] for r in rank]
    color = ["#247888" if r["eligible_for_subset"] else "#969696" for r in rank]
    axes[0].barh(pos, gains, color=color)
    axes[0].set_yticks(pos, [r["parameter"]+(" +" if r["direction"] > 0 else " -") for r in rank])
    axes[0].invert_yaxis(); axes[0].set(xlabel="Reduction in mean log-adenylate error (%)", title="Full-step effects; grey fails an admission screen")
    selected_names = [r["parameter"] for r in rank]
    heat = np.array([s["columns"][p]["log_adenylate_derivative"] for p in selected_names]).reshape(len(rank), 3, 4).mean(axis=2).T
    maximum = float(np.max(np.abs(heat)))
    show = axes[1].imshow(heat, aspect="auto", cmap="RdBu_r", vmin=-maximum, vmax=maximum)
    axes[1].set_xticks(pos, selected_names, rotation=70, ha="right"); axes[1].set_yticks([0, 1, 2], ["ATP", "ADP", "AMP"])
    axes[1].set_title("Mean log-concentration elasticity (all four source times)")
    fig.colorbar(show, ax=axes[1], shrink=.6)
    fig.savefig(out/"adenylate_sensitivity.png", dpi=160); plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, 4), constrained_layout=True)
    labels, values15, values46 = [], [], []
    for key in ("historical", "citrate_only", "arginase_only", "both_candidates"):
        labels.append(key)
        values15.append(next(r for r in coverage["balance_relaxations"] if r["label"] == key and r["end_day"] == 15)["minimum_working_error_multiplier"])
        values46.append(next(r for r in coverage["balance_relaxations"] if r["label"] == key and r["end_day"] == 46)["minimum_working_error_multiplier"])
    labels.append("both + ARGSL\n(structural only)")
    values15.append(extra["results"][0]["minimum_working_error_multiplier"]); values46.append(extra["results"][1]["minimum_working_error_multiplier"])
    x = np.arange(len(labels)); ax.bar(x-.18, values15, width=.36, color="#247888", label="J1-J15")
    ax.bar(x+.18, values46, width=.36, color="#b44468", label="J1-J46")
    ax.set_xticks(x, labels); ax.set(ylabel="Minimum multiplier of engineering error bands", title="Necessary stoichiometric relaxations, not kinetic calibration")
    ax.legend(frameon=False); fig.savefig(out/"coverage_relaxations.png", dpi=160); plt.close(fig)
    fig, axes = plt.subplots(3, 3, figsize=(13, 10), constrained_layout=True)
    panels = ("ATP", "ADP", "AMP", "energy_charge", "G6P", "F6P", "GLC", "PEP", "EGLC")
    colors = ("#707070", "#247888", "#b44468", "#9a7c2e")
    for ax, p in zip(axes.flat, panels):
        for (label, (time, states)), color in zip(trajectories.items(), colors):
            if p == "energy_charge":
                a, b, c = [states[POOLS.index(q)] for q in ("ATP", "ADP", "AMP")]; values = (a+.5*b)/(a+b+c)
            else: values = states[POOLS.index(p)]
            ax.plot(time, values, color=color, label=label, linestyle="--" if label == "baseline" else "-")
        use = source_t <= 15
        if p == "energy_charge":
            a, b, c = [np.array(obs["values"][q])[use] for q in ("ATP", "ADP", "AMP")]; y = (a+.5*b)/(a+b+c)
        else: y = np.array(obs["values"][p])[use]
        ax.scatter(source_t[use], y, color="#222222", marker="D", s=18, label="Nominal source", zorder=4)
        ax.set(title=p, xlabel="Model day", ylabel="Energy charge" if p == "energy_charge" else "Concentration (mM)", xlim=(1, 15))
        if p in ("ATP", "ADP"): ax.set_yscale("log")
    handles, legend = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, legend, loc="outside lower center", ncols=2, frameon=False)
    fig.suptitle("Original ODE: independently tested single-parameter effects, not a combined fit", fontsize=13)
    fig.savefig(out/"single_lever_original_replays.png", dpi=150); plt.close(fig)
    paths = [Path(__file__), ROOT/"scripts/report_joint_glucose_energy.py", archive/"execution_design.json",
        archive/"summary.json", archive/"manifest.json", archive/"coverage/summary.json", followup/"summary.json", followup/"manifest.json"]
    for p in paths: track(p)
    write(out/"manifest.json", {"input_sha256": hashes, "output_sha256": {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()}})
    return {"original_comparisons": len(rows), "source_metric_rows": len(rows)*55, "validated_single_levers": len(s["validated_single_levers"]), "production_promoted": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True); p.add_argument("--followup", type=Path, required=True); p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    with threadpool_limits(1): result = report(a.archive.resolve(), a.followup.resolve(), a.out.resolve())
    print(json.dumps(result, indent=2))
