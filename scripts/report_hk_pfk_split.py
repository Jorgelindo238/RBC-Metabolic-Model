"""Read-only nested-model comparison and full executed-ODE evaluation."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from fla_broad_protected_calibration import POOLS, training_data, assess, score
from fla_joint_calibration import JointRHS
from run_protected_joint import verify_inputs, check_seal
from run_glut_only_free_replay import sha, write
from report_joint_glucose_energy import signed_budget
from verify_broad_protected_joint import independently_score


def report(archive, out):
    if out.exists(): raise ValueError("fresh report directory required")
    f = verify_inputs(archive)
    s = json.loads((archive/"summary.json").read_text())
    obs = json.loads((archive/"observations.json").read_text())
    parent = ROOT/f["design"]["parent_archive"]
    prior = json.loads((parent/"summary.json").read_text())
    times, target = training_data(obs, 10.)
    source_times = np.array(obs["time"])
    post = source_times > 1
    early = source_times[post] <= 10
    hashes, checks = {}, 0
    def require(ok, reason):
        nonlocal checks
        checks += 1
        if not ok: raise ValueError(reason)
    def tracked(path):
        hashes[path.relative_to(ROOT).as_posix()] = sha(path)
        return path
    def verify_score(prediction, recorded):
        nll, errors = independently_score(prediction, target)
        require(abs(nll-recorded["negative_log_likelihood"]) < 1e-7, "independent training density")
        require(np.allclose(errors[:11], [recorded["RMSE_mM"][p] for p in POOLS], rtol=0, atol=1e-12), "independent RMSE")
    training, early_curves = [], {}
    with np.load(tracked(archive/"screen/baseline.npz")) as a:
        prediction = a["prediction"].copy()
        base_score = score(prediction, target)
        verify_score(prediction, base_score)
        training.append({"case": "parent", "score": base_score, "predictions_mM": prediction.tolist(),
                         "parameters": f["parameters"], "guards": assess(prediction, target, f["guards"]), "fitted": False})
        names = JointRHS(f["parameters"], f["kinetics"]).names
        ix = [names.index(p) for p in POOLS]
        early_curves["parent"] = (a["accepted_time"].copy(), a["accepted_states"][ix].copy())
    for name in ("best_paired", "best_split"):
        fit = s[name]
        path = archive/"fits"/fit["label"]
        check_seal(path)
        with np.load(tracked(path/"fit_replay.npz")) as a:
            prediction = a["prediction"].copy()
            verify_score(prediction, fit["training_score"])
            require(np.array_equal(a["accepted_states"][:, 0], f["initial"]), "fit initial changed")
            training.append({"case": name, "label": fit["label"], "mode": fit["mode"], "fitted": True,
                "parameters": fit["parameters"], "score": fit["training_score"], "guards": fit["training_guards"],
                "predictions_mM": prediction.tolist(), "optimizer_success": fit["optimizer_success"]})
            early_curves[name] = (a["accepted_time"].copy(), a["accepted_states"][ix].copy())
    parent_path = parent/"audits"/(prior["selected"]["label"]+"_J46")/"J1_J46/glut_real_candidate_ultrastrict/replay.npz"
    selected_path = parent_path if s["selected_is_parent"] else archive/"audits"/(s["selected"]["label"]+"_J46")/"J1_J46/glut_real_candidate_ultrastrict/replay.npz"
    full, full_curves, parent_metrics = [], {}, None
    for label, path in (("parent", parent_path), ("accepted_selection", selected_path)):
        check_seal(path.parents[2])
        with np.load(tracked(path)) as a:
            require(np.array_equal(a["accepted_states"][:, 0], f["initial"]), "full initial changed")
            names = a["pool_names"].tolist()
            metrics = {}
            for p, values in obs["values"].items():
                predicted = a["states"][names.index(p), np.searchsorted(a["time"], source_times[post])]
                actual = np.array(values)[post]
                metrics[p] = {"training_RMSE_mM": float(np.sqrt(np.mean((predicted[early]-actual[early])**2))),
                    "late_RMSE_mM": float(np.sqrt(np.mean((predicted[~early]-actual[~early])**2))),
                    "all_postinitial_RMSE_mM": float(np.sqrt(np.mean((predicted-actual)**2))),
                    "endpoint_mM": float(predicted[-1]), "nominal_endpoint_mM": float(actual[-1]),
                    "hard_guarded": p in POOLS, "known_alias": p in ("B13PG", "P2G"),
                    "assay_independence_established": False}
                require(np.isfinite(list(metrics[p].values())[:5]).all(), "nonfinite pool metrics")
            if parent_metrics is None: parent_metrics = metrics
            for p, m in metrics.items():
                m["early_delta_vs_parent_mM"] = m["training_RMSE_mM"]-parent_metrics[p]["training_RMSE_mM"]
                m["all_delta_vs_parent_mM"] = m["all_postinitial_RMSE_mM"]-parent_metrics[p]["all_postinitial_RMSE_mM"]
            budgets = {}
            for p in ("GLC", "ATP", "ADP", "AMP", "PEP", "G6P", "F6P", "B23PG", "B13PG", "RIB", "PRPP"):
                matrix_row = a["matrix"][names.index(p)]
                contributions = matrix_row*a["executed8"].sum(axis=1)
                signed = signed_budget(matrix_row, a["q8_executed_rates"], a["q8_weights"])
                require(abs(signed["production_mM"]-signed["consumption_mM"]-contributions.sum()) < 1e-9, "executed signed budget")
                budgets[p] = {**signed, "net_integrated_mM": float(contributions.sum()),
                    "endpoint_change_mM": float(a["states"][names.index(p), -1]-a["states"][names.index(p), 0]),
                    "signed_reaction_contributions_mM": {r: float(v) for r, v in zip(a["reactions"].tolist(), contributions) if v != 0}}
            period_budgets = {}
            for start, end in ((1., 4.), (4., 8.), (8., 10.), (10., 46.)):
                nodes = (a["q8_nodes"] > start) & (a["q8_nodes"] < end)
                cells = (a["boundaries"][:-1] >= start) & (a["boundaries"][1:] <= end)
                integrals = a["executed8"][:, cells].sum(axis=1)
                require(np.allclose(integrals, a["q8_executed_rates"][:, nodes]@a["q8_weights"][nodes], rtol=1e-10, atol=1e-10), "period executed rates")
                rows = {}
                for p in ("ATP", "ADP", "AMP", "GLC", "G6P", "F6P", "B23PG", "B13PG", "PEP"):
                    row = a["matrix"][names.index(p)]
                    signed = signed_budget(row, a["q8_executed_rates"][:, nodes], a["q8_weights"][nodes])
                    delta = a["states"][names.index(p), np.searchsorted(a["time"], end)]-a["states"][names.index(p), np.searchsorted(a["time"], start)]
                    net = float(row@integrals)
                    require(abs(signed["production_mM"]-signed["consumption_mM"]-net) < 1e-9, "period signed budget")
                    rows[p] = {**signed, "net_integrated_mM": net, "simulated_state_change_mM": float(delta),
                        "integration_balance_residual_mM": float(delta-net),
                        "signed_reaction_contributions_mM": {r: float(v) for r, v in zip(a["reactions"].tolist(), row*integrals) if v != 0}}
                period_budgets[f"J{start:g}_J{end:g}"] = {"pool_budgets": rows,
                    "executed_reaction_integrals_mM": dict(zip(a["reactions"].tolist(), integrals.tolist()))}
            prediction = a["states"][[names.index(p) for p in POOLS]][:, np.searchsorted(a["time"], times)]
            nll = score(prediction, target)
            verify_score(prediction, nll)
            guards = assess(prediction, target, f["guards"], phase="audit")
            require(guards["passed"], "full early guards")
            worse = [p for p, m in metrics.items() if p not in POOLS and m["early_delta_vs_parent_mM"] > 0]
            full.append({"case": label, "reused_parent_replay": path == parent_path, "score": nll, "guards": guards,
                "all55_metrics": metrics, "executed_budgets": budgets, "period_budgets": period_budgets,
                "other44_raw_early_increases_vs_parent": len(worse),
                "largest_other_early_increases_mM": {p: metrics[p]["early_delta_vs_parent_mM"] for p in sorted(worse, key=lambda p:metrics[p]["early_delta_vs_parent_mM"], reverse=True)[:10]},
                "late_data_used_in_selection": False})
            full_curves[label] = (a["time"].copy(), a["states"][[names.index(p) for p in POOLS]].copy())
    out.mkdir(parents=True)
    write(out/"comparison.json", {"training": training, "full_evaluation": full,
        "nested_gain_NLL": s["split_training_NLL_gain_vs_best_paired_found"],
        "nested_gain_reference": "retained_paired_or_parent_after_1e-4_numerical_tie_rule",
        "raw_gain_vs_lowest_paired_fit_NLL": s["best_paired"]["training_score"]["negative_log_likelihood"]-s["best_split"]["training_score"]["negative_log_likelihood"],
        "selection_attempts": s["selection_attempts"], "selected_is_split": s["selected_is_split"],
        "capacity_comparison": {r["case"]: {"vmax_VHK": r["parameters"]["vmax_VHK"],
            "vmax_VPFK": r["parameters"]["vmax_VPFK"],
            "PFK_to_HK_capacity_ratio": r["parameters"]["vmax_VPFK"]/r["parameters"]["vmax_VHK"]} for r in training},
        "fit_statuses": [{k: r[k] for k in ("label", "mode", "optimizer_success", "actual_objective_integrations", "feasible_evaluations")} for r in s["fits"]],
        "fixed_screen": json.loads(tracked(archive/"screen/results.json").read_text()),
        "all55_independent": False, "physiological_validation": False})
    write(out/"candidate.json", {"status": "conditional_numerically_guard_admissible_not_biologically_validated",
        "source_archive": archive.relative_to(ROOT).as_posix(), "full_parameter_overrides": s["selected"]["parameters"],
        "glucose_kinetics": s["selected"]["glucose_kinetics"], "only_parameters_reestimated": ["vmax_VHK", "vmax_VPFK"],
        "initial_state": f["initial"], "hematocrit": .58, "pH_policy": "clamped_diagnostic",
        "positivity_policy": "reaction_consistent", "availability_threshold_mM": .001,
        "selected_is_parent": s["selected_is_parent"], "production_promoted": False})
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    for name, curves, short in (("training_comparison", early_curves, True), ("concentration_comparison", full_curves, False)):
        fig, axes = plt.subplots(6, 2, figsize=(12, 15), constrained_layout=True)
        colors = ("#247888", "#947c30", "#b44468")
        for i, p in enumerate(POOLS):
            ax = axes.flat[i]
            for (label, (time, state)), color in zip(curves.items(), colors):
                ax.plot(time, state[i], color=color, label=label, linestyle="--" if label == "parent" else "-", linewidth=1.5)
            use = source_times <= 10 if short else np.ones(len(source_times), bool)
            ax.scatter(source_times[use], np.array(obs["values"][p])[use], color="#222222", marker="D", s=16, label="Nominal source", zorder=4)
            if not short: ax.axvline(10, color="#777777", linestyle=":", linewidth=.8)
            ax.set(title=p, xlabel="Model day", ylabel="Concentration (mM)", xlim=(1, 10 if short else 46))
        axes.flat[-1].axis("off")
        handles, labels = axes.flat[0].get_legend_handles_labels()
        axes.flat[-1].legend(handles, labels, loc="upper left", frameon=False)
        axes.flat[-1].text(.02, .45, "Only J4/J8 used in fitting.\nJ1 fixed, not a fitting residual.\nNo measured or latent IC change.\nLate residuals: exposed evaluation only.", transform=axes.flat[-1].transAxes, va="top")
        fig.suptitle("HK/PFK: paired vs split fitting ODE" if short else "HK/PFK: accepted original full-ODE evaluation", fontsize=14)
        fig.savefig(out/(name+".png"), dpi=150)
        plt.close(fig)
    for path in (Path(__file__), ROOT/"scripts/report_joint_glucose_energy.py", ROOT/"scripts/verify_broad_protected_joint.py",
                 archive/"execution_design.json", archive/"summary.json", archive/"observations.json", archive/"manifest.json"):
        tracked(path)
    write(out/"checks.json", {"passed": True, "checks": checks, "pool_rows": len(full)*55,
        "signed_budgets": len(full)*11, "physiological_validation": False})
    write(out/"manifest.json", {"input_sha256": hashes, "output_sha256": {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()}})
    return {"checks": checks, "training_comparators": len(training), "full_source_rows": len(full)*55, "production_promoted": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True); p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    with threadpool_limits(limits=1): result = report(a.archive.resolve(), a.out.resolve())
    print(json.dumps(result, indent=2))
