"""Same22-observation comparison, whole-source audit and unpromoted export."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from fla_joint_calibration import GROUPS
from fla_broad_protected_calibration import POOLS, training_data, score, assess
from run_glut_only_free_replay import sha, write
from report_joint_glucose_energy import signed_budget


def report(archive, out):
    if out.exists():
        raise ValueError("fresh report directory required")
    f = json.loads((archive/"execution_design.json").read_text())
    s = json.loads((archive/"summary.json").read_text())
    obs = json.loads((archive/"observations.json").read_text())
    parent = ROOT/f["design"]["parent_archive"]
    previous = json.loads((parent/"summary.json").read_text())["selected"]
    selected = s["selected"]
    base = ROOT/f["parent_design"]["source_archive"]
    cases = [("GLUT_control", base/"J1_J46/glut_real_candidate_ultrastrict/replay.npz"),
        ("previous_nine_pool_fit", parent/"audits"/(previous["label"]+"_J46")/"J1_J46/glut_real_candidate_ultrastrict/replay.npz"),
        ("broad_selection", archive/"audits"/(selected["label"]+"_J46")/"J1_J46/glut_real_candidate_ultrastrict/replay.npz")]
    times, target = training_data(obs, f["design"]["training_end_day"])
    all_times = np.array(obs["time"])
    post = all_times > 1
    early = all_times[post] <= f["design"]["training_end_day"]
    comparisons, trajectories, hashes = [], {}, {}
    control_metrics = None
    for label, path in cases:
        if not path.exists():
            continue
        hashes[path.relative_to(ROOT).as_posix()] = sha(path)
        with np.load(path) as a:
            names = a["pool_names"].tolist()
            metrics = {}
            for pool, values in obs["values"].items():
                actual = np.asarray(values)[post]
                prediction = a["states"][names.index(pool), np.searchsorted(a["time"], all_times[post])]
                metrics[pool] = {"training_RMSE_mM": float(np.sqrt(np.mean((prediction[early]-actual[early])**2))),
                    "all_postinitial_RMSE_mM": float(np.sqrt(np.mean((prediction-actual)**2))),
                    "late_J11_J46_RMSE_mM": float(np.sqrt(np.mean((prediction[~early]-actual[~early])**2))),
                    "endpoint_mM": float(prediction[-1]), "nominal_endpoint_mM": float(actual[-1]),
                    "hard_training_RMSE_guarded": pool in POOLS,
                    "pointwise_guarded": pool in f["design"]["pointwise_pools"],
                    "known_source_alias": pool in f["design"]["source_aliases_excluded"],
                    "assay_independence_established": False}
                if pool in POOLS:
                    metrics[pool].update(training_predictions_mM=prediction[early].tolist(), training_observations_mM=actual[early].tolist())
            if control_metrics is None:
                control_metrics = metrics
            for pool, values in metrics.items():
                values["training_RMSE_delta_vs_control_mM"] = values["training_RMSE_mM"]-control_metrics[pool]["training_RMSE_mM"]
                values["all_RMSE_delta_vs_control_mM"] = values["all_postinitial_RMSE_mM"]-control_metrics[pool]["all_postinitial_RMSE_mM"]
            prediction = a["states"][[names.index(p) for p in POOLS]][:, np.searchsorted(a["time"], times)]
            budgets = {}
            for pool in ("GLC", "ATP", "ADP", "AMP", "PEP", "G6P", "F6P", "B23PG", "B13PG", "RIB", "PRPP"):
                row = a["matrix"][names.index(pool)]
                contributions = row*a["executed8"].sum(axis=1)
                budgets[pool] = {**signed_budget(row, a["q8_executed_rates"], a["q8_weights"]),
                    "net_integrated_mM": float(contributions.sum()),
                    "endpoint_change_mM": float(a["states"][names.index(pool), -1]-a["states"][names.index(pool), 0]),
                    "signed_reaction_contributions_mM": {r: float(v) for r, v in zip(a["reactions"].tolist(), contributions) if v != 0}}
            worse = [p for p, m in metrics.items() if p not in POOLS and m["training_RMSE_delta_vs_control_mM"] > 0]
            comparisons.append({"case": label, "training_score": score(prediction, target),
                "training_guards": assess(prediction, target, f["guards"], phase="audit"),
                "all55_pool_metrics": metrics, "executed_budgets": budgets,
                "other44_raw_training_RMSE_increases": len(worse),
                "largest_other_training_increases_mM": {p: metrics[p]["training_RMSE_delta_vs_control_mM"]
                    for p in sorted(worse, key=lambda p: metrics[p]["training_RMSE_delta_vs_control_mM"], reverse=True)[:10]},
                "late_residuals_used_in_selection": False})
            trajectories[label] = (a["time"].copy(), a["states"][[names.index(p) for p in POOLS]].copy())
    candidate = {"status": "broad_guarded_training_candidate_not_physiologically_validated",
        "source_archive": archive.relative_to(ROOT).as_posix(), "source_summary_sha256": sha(archive/"summary.json"),
        "is_control_fallback": s["selected_is_control"], "initial_states_changed": False,
        "numerical_and_training_guards_pass": s["accepted_numeric_and_training_guards"],
        "parameter_overrides": {name: selected["parameters"][name] for group in GROUPS.values() for name in group},
        "glucose_kinetics": selected["glucose_kinetics"], "initial_context": f["parent_design"]["initial_context"],
        "hematocrit": .58, "pH_policy": "clamped_diagnostic", "positivity_policy": "reaction_consistent",
        "availability_threshold_mM": .001, "native_VELAC_changed": False, "production_promoted": False,
        "guarded_pools": list(POOLS), "pointwise_pools": ["PEP"]}
    out.mkdir(parents=True)
    write(out/"comparison.json", {"comparisons": comparisons, "selected_factors": selected["factors"],
        "fit_statuses": [{k: row[k] for k in ("label", "optimizer_success", "actual_objective_integrations", "feasible_evaluations")} for row in s["fits"]],
        "total_objective_integrations": s["total_objective_integrations"], "selection_attempts": s["selection_attempts"],
        "training_times": times.tolist(), "guard_contract": f["guards"], "biological_promotion": False,
        "same22_observations_rescored": True, "all55_source_channels_independent": False})
    write(out/"candidate.json", candidate)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(6, 2, figsize=(13, 16), constrained_layout=True)
    colors = {"GLUT_control": "#247888", "previous_nine_pool_fit": "#8c6b32", "broad_selection": "#b44468"}
    for i, pool in enumerate(POOLS):
        ax = axes.flat[i]
        for label, (time, state) in trajectories.items():
            ax.plot(time, state[i], color=colors[label], linestyle="-" if label == "broad_selection" else "--", label=label)
        ax.scatter(all_times, obs["values"][pool], color="#242424", marker="D", s=15, zorder=4, label="Nominal source")
        ax.axvline(10, color="#666666", linestyle=":", linewidth=.8)
        ax.set(title=pool, xlabel="Model day", ylabel="Concentration (mM)", xlim=(1, 46))
    axes.flat[-1].axis("off")
    handles, labels = axes.flat[0].get_legend_handles_labels()
    axes.flat[-1].legend(handles, labels, loc="upper left", frameon=False)
    axes.flat[-1].text(.02, .45, "Training: actual J4/J8 only.\nJ11-J46: exposed temporal evaluation.\nNo source or initial-state adjustment.", transform=axes.flat[-1].transAxes, va="top")
    fig.suptitle("Eleven-pool protected calibration: original full-ODE trajectories", fontsize=14)
    fig.savefig(out/"concentration_comparison.png", dpi=160)
    plt.close(fig)
    for path in (Path(__file__), ROOT/"src/fla_broad_protected_calibration.py", ROOT/"scripts/report_joint_glucose_energy.py",
                 archive/"execution_design.json", archive/"summary.json", archive/"observations.json"):
        hashes[path.relative_to(ROOT).as_posix()] = sha(path)
    write(out/"manifest.json", {"input_sha256": hashes,
        "output_sha256": {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()}})
    return {"comparisons": len(comparisons), "source_pool_rows": len(comparisons)*55, "production_promoted": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    with threadpool_limits(limits=1): result = report(args.archive.resolve(), args.out.resolve())
    print(json.dumps(result, indent=2))
