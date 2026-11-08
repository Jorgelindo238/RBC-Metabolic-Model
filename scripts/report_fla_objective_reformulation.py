"""Common-metric comparisons and explanatory certificates, without reselection."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from fla_balance_certificates import balance_certificates
from fla_calibration_observations import fixed_error_scales, objective_metrics
from fla_broad_protected_calibration import POOLS, training_data
from fla_joint_calibration import JointRHS
from fla_profiled_observation_noise import profile_lognormal_dispersion
from run_protected_joint import verify_inputs, check_seal
from run_glut_only_free_replay import write, sha
from report_joint_glucose_energy import signed_budget


def report(archive, out):
    if out.exists(): raise ValueError("fresh report directory required")
    f = verify_inputs(archive); s = json.loads((archive/"summary.json").read_text())
    obs = json.loads((archive/"observations.json").read_text())
    rhs = JointRHS(f["parameters"], f["kinetics"])
    hashes, certificates, fitting, full, historical = {}, [], [], [], []
    early_curves, late_curves = {}, {}
    def tracked(path):
        hashes[path.relative_to(ROOT).as_posix()] = sha(path)
        return path
    parent = ROOT/f["design"]["parent_archive"]
    previous = json.loads((parent/"summary.json").read_text())["selected"]
    for label, path in (("restored_guarded_historical", parent/"screen/baseline.npz"),
        ("split_guarded_historical", parent/"fits"/previous["label"]/"fit_replay.npz")):
        with np.load(tracked(path)) as a:
            historical.append({"case": label, "refitted_in_this_comparison": False,
                "metrics": objective_metrics(a["prediction"], a["observed"], f["phases"]["10"]["scales"]),
                "NLL": profile_lognormal_dispersion(a["prediction"].ravel(), a["observed"].ravel())["negative_log_likelihood"]})
    for row in json.loads((archive/"balances/results.json").read_text()):
        path = archive/"balances"/f"{row['scope']}_J{int(row['end_day'])}.npz"
        with np.load(tracked(path)) as a:
            forward = [row["reaction_names"].index(r) for r in row["forward_direction_subset"]]
            cert = balance_certificates(a["matrix"], a["observed"], a["time"], a["scales"], row["pools"], forward)
        gap = row["minimum_working_error_multiplier"]-max(c["minimum_working_multiplier_lower_bound"] for c in cert)
        certificates.append({"scope": row["scope"], "end_day": row["end_day"],
            "exact_feasible": row["exact_measured_balances_feasible"],
            "LP_multiplier": row["minimum_working_error_multiplier"], "certificates": cert,
            "primal_analytic_lower_bound_gap": gap, "relaxation_optimum_certified": abs(gap) < 1e-7,
            "shared_adjustment_witness_is_unique": False, "ODE_feasibility_proved": False})
    selected = s["selected_J10"]+s["selected_J15"]
    for fit in selected:
        folder = archive/"fits"/fit["label"]; check_seal(folder)
        with np.load(tracked(folder/"fit_replay.npz")) as a:
            prediction, y = a["prediction"], a["observed"]
            rescored = []
            for pair in f["design"]["sensitivity_scale_pairs"]:
                scale = fixed_error_scales(y, absolute_fraction=pair[0], relative_fraction=pair[1],
                    interpretation="engineering_normalization_not_assay_SD")
                rescored.append({"absolute_fraction": pair[0], "relative_fraction": pair[1],
                    "metrics": objective_metrics(prediction, y, scale), "new_fit_or_selection": False})
            fitting.append({k: fit[k] for k in ("label", "loss", "end_day", "objective_value", "metrics", "legacy13",
                "optimizer_success", "actual_objective_integrations", "factors")}|{
                "vmax_VHK": fit["parameters"]["vmax_VHK"], "vmax_VPFK": fit["parameters"]["vmax_VPFK"],
                "ATP_predictions_mM": prediction[POOLS.index("ATP")].tolist(), "times": a["sample_time"].tolist(),
                "scale_rescoring_not_parameter_robustness_proof": rescored})
            if fit["end_day"] == 10:
                early_curves[fit["loss"]] = (a["accepted_time"].copy(), a["accepted_states"][[rhs.names.index(p) for p in POOLS]].copy())
    for fit in selected:
        candidates = [a for a in s["audits"] if a["label"] == fit["label"]]
        last = max(candidates, key=lambda a:a["end_day"])
        folder = archive/"audits"/(fit["label"]+f"_J{int(last['end_day'])}")
        check_seal(folder)
        path = folder/f"J1_J{int(last['end_day'])}/glut_real_candidate_ultrastrict/replay.npz"
        with np.load(tracked(path)) as a:
            time = np.array(obs["time"])
            post = (time > 1)&(time <= last["end_day"])
            names = a["pool_names"].tolist()
            metrics = {}
            for p, values in obs["values"].items():
                predicted = a["states"][names.index(p), np.searchsorted(a["time"], time[post])]
                actual = np.array(values)[post]
                early = time[post] <= 10
                trained = time[post] <= fit["end_day"]
                m = {"J4_J8_RMSE_mM": float(np.sqrt(np.mean((predicted[early]-actual[early])**2))),
                    "training_RMSE_mM": float(np.sqrt(np.mean((predicted[trained]-actual[trained])**2))),
                    "available_postinitial_RMSE_mM": float(np.sqrt(np.mean((predicted-actual)**2))),
                    "endpoint_mM": float(predicted[-1]), "nominal_endpoint_mM": float(actual[-1]),
                    "evaluation_end_day": last["end_day"], "source_points": int(post.sum()),
                    "known_alias_not_an_independent_assay": p in ("B13PG", "P2G")}
                if np.any(~trained): m["exposed_later_RMSE_mM"] = float(np.sqrt(np.mean((predicted[~trained]-actual[~trained])**2)))
                metrics[p] = m
            budgets = {}
            for p in ("ATP", "ADP", "AMP", "GLC", "G6P", "F6P", "B23PG"):
                row = a["matrix"][names.index(p)]
                contribution = row*a["executed8"].sum(axis=1)
                signed = signed_budget(row, a["q8_executed_rates"], a["q8_weights"])
                budgets[p] = {**signed, "net_integrated_mM": float(contribution.sum()),
                    "state_change_mM": float(a["states"][names.index(p), -1]-a["states"][names.index(p), 0]),
                    "reaction_contributions_mM": {r: float(v) for r, v in zip(a["reactions"].tolist(), contribution) if v != 0}}
            full.append({"label": fit["label"], "loss": fit["loss"], "training_end_day": fit["end_day"],
                "evaluation_end_day": last["end_day"], "numerical_pass": last["numerical_pass"],
                "old_early_guards_pass": last["guard_pass"], "all55_metrics": metrics, "executed_budgets": budgets,
                "late_residuals_used_in_selection": False, "physiological_validation": False})
            if last["end_day"] == 46:
                late_curves[fit["label"]] = (a["time"].copy(), a["states"][[names.index(p) for p in POOLS]].copy())
    out.mkdir(parents=True)
    bounds = np.log(f["primitive_factor_bounds"])
    bound_hits = {fit["label"]: [name for name, value in zip(("vmax_VHK", "vmax_VPFK"), fit["selected_log_factors"])
        if min(abs(value-bounds[0]), abs(value-bounds[1])) <= 1e-8] for fit in selected}
    working_fit_pass = all(r["metrics"]["all_within_working_unit_MSE"] for r in fitting)
    write(out/"readiness.json", {"status": "numerically_checked_experiment_not_biologically_calibrated",
        "all_original_numerical_checks_pass": s["all_original_numerical_checks_passed"],
        "all_selected_working_MSE_targets_met": working_fit_pass, "working_targets_are_not_assay_accuracy": True,
        "parameter_search_bound_hits": bound_hits,
        "canonical_source_invariant_conflicts": [c for c in certificates if c["scope"] == "canonical53" and c["LP_multiplier"] > 1],
        "source_normalization_author_verified": False, "relative_experimental_calibration_demonstrated": False,
        "generic_raw_file_ingestion_complete": False, "production_promotion_allowed": False,
        "next_required_work": ["resolve_model_observation_coverage_for_CIT_ECIT_ARG_EARG_CITR_without_artificial_sinks",
            "diagnose_adenylate_parameter_sensitivity_before_new_kinetic_freedom",
            "add_source_specific_raw_import_and_relative_anchor_uncertainty_before_generic_ODE_fitting"]})
    write(out/"comparison.json", {"fits": fitting, "historical_controls": historical, "full_evaluation": full, "balance_certificates": certificates,
        "working_scales_are_not_assay_SD": True, "raw_objective_numbers_are_not_comparable_across_loss_types": True,
        "relative_contract_is_not_yet_generic_relative_ODE_fit": True, "production_promoted": False})
    for fit in selected:
        write(out/(fit["label"]+"_candidate.json"), {"status": "experimental_override_not_biologically_validated",
            "parameters": fit["parameters"], "glucose_kinetics": fit["glucose_kinetics"], "initial": f["initial"],
            "hematocrit": .58, "threshold_mM": .001, "pH_policy": "clamped_diagnostic", "source_archive": archive.relative_to(ROOT).as_posix(),
            "source_summary_sha256": sha(archive/"summary.json"), "production_promoted": False})
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = ("#247888", "#b44468", "#967b26")
    for name, curves, end in (("matched_J10", early_curves, 10), ("exposed_J46", late_curves, 46)):
        if not curves: continue
        fig, axes = plt.subplots(6, 2, figsize=(12, 15), constrained_layout=True)
        source_t = np.array(obs["time"]); use = source_t <= end
        for i, p in enumerate(POOLS):
            ax = axes.flat[i]
            for (label, (t, x)), color in zip(curves.items(), colors): ax.plot(t, x[i], color=color, label=label)
            ax.scatter(source_t[use], np.array(obs["values"][p])[use], color="#222222", s=16, marker="D", label="Nominal source", zorder=4)
            if end == 46: ax.axvline(15, color="#777777", linestyle=":", linewidth=.8)
            ax.set(title=p, xlabel="Model day", ylabel="Concentration (mM)", xlim=(1, end))
        axes.flat[-1].axis("off")
        axes.flat[-1].legend(*axes.flat[0].get_legend_handles_labels(), frameon=False, loc="upper left")
        axes.flat[-1].text(.02, .45, "Same HK/PFK bounds and fixed J1.\nOld guards: diagnostic only.\nWorking scales are not assay precision.\nLate residuals do not select constants.", transform=axes.flat[-1].transAxes, va="top")
        fig.suptitle("Matched objectives: original training data" if end == 10 else "Progressive training: original full-ODE exposed evaluation", fontsize=14)
        fig.savefig(out/(name+".png"), dpi=150); plt.close(fig)
    r = next(r for r in certificates if r["scope"] == "canonical53" and r["end_day"] == 46)
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.5), constrained_layout=True)
    constants = [c for c in r["certificates"] if c["kind"] == "constant"]
    for ax, c in zip(axes, constants):
        ax.plot(obs["time"], c["source_combination"], "D-", color="#247888", markersize=4, label="Nominal data combination")
        ax.axhline(c["source_combination"][0], color="#b44468", linestyle="--", label="Model requires constant")
        label = " + ".join((p if abs(v-1) < 1e-10 else f"{v:.3f} {p}") for p, v in c["coefficients"].items())
        ax.set(title=label, xlabel="Model day", ylabel="Cell-reference concentration (mM)")
    axes[0].legend(frameon=False, fontsize=8)
    fig.savefig(out/"structural_balance_certificates.png", dpi=160); plt.close(fig)
    paths = [Path(__file__), ROOT/"src/fla_balance_certificates.py", ROOT/"qa/test_fla_balance_certificates.py",
        ROOT/"config/examples/fla_relative_observation_contract.json",
        ROOT/"scripts/validate_fla_observation_manifest.py", ROOT/"scripts/report_joint_glucose_energy.py",
        archive/"execution_design.json", archive/"summary.json", archive/"observations.json", archive/"manifest.json"]
    for path in paths: tracked(path)
    write(out/"manifest.json", {"input_sha256": hashes, "output_sha256": {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()}})
    return {"selected_comparisons": len(fitting), "source_pool_rows": len(full)*55,
        "six_relaxation_optima_certified": all(c["relaxation_optimum_certified"] for c in certificates), "production_promoted": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True); p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    with threadpool_limits(1): result = report(a.archive.resolve(), a.out.resolve())
    print(json.dumps(result, indent=2))
