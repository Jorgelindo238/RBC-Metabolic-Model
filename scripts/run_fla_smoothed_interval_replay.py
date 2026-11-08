"""Free-ODE validation of sealed interval capacities; no fitting or teacher forcing."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from fla_synthetic_recovery import PARAMETERS
from fla_working_reference import load_working_reference
from run_fla_sparse_teacher_resolution import verify_archive_inputs
from run_fla_synthetic_recovery import audit_solutions, file_hash, simulate, write_json
from run_fla_teacher_resolution import replay_metrics

DEFAULT_CONFIG = ROOT / "config/fla_smoothed_interval_replay.json"
DEFAULT_OUT = ROOT / "output/fla_smoothed_interval_replay_2026_10_05"
METHODS = ["raw_integrated", "smoothed_inputs_integrated"]
SEEDS = [2718, 31415, 1618, 57721, 104729]
REUSE = ["clean", "noise_2718", "noise_31415", "noise_1618"]
REPLAY_FILES = ["strict_accepted_states.npz", "ultrastrict_accepted_states.npz",
                "evaluation.npz", "learned_synthetic_parameters.json",
                "numerical_audit.json", "solver_convergence.csv"]


def validate_design(design):
    required = {"schema_version": 1,
                "purpose": "synthetic_fixed_capacity_smoothed_interval_free_ODE_validation",
                "parent_archive": "output/fla_sparse_teacher_resolution_2026_10_05",
                "methods": METHODS, "noise_seeds": SEEDS, "reused_raw_cases": REUSE,
                "horizon_day": [1., 46.], "training_end_day": 22., "new_fit_count": 0,
                "new_ODE_integration_count": 16, "reused_ODE_integration_count": 8,
                "biological_calibration_allowed": False, "global_model_promotion_allowed": False,
                "teacher_forcing": False, "observation_reset": False, "raw_state_output_clipping": False}
    if set(design) != set(required):
        raise ValueError("unexpected or missing fixed-replay control")
    for key, value in required.items():
        # JSON true compares equal to 1: enforce scalar and list-element types too.
        if design[key] != value or type(design[key]) is not type(value):
            raise ValueError(f"fixed-replay control changed: {key}")
        if isinstance(value, list) and any(type(a) is not type(b) for a, b in zip(design[key], value)):
            raise ValueError(f"fixed-replay list type changed: {key}")
    return design


def replay_plan(design, fits):
    cases = ["clean"] + [f"noise_{seed}" for seed in design["noise_seeds"]]
    rows = []
    for case in cases:
        for method in design["methods"]:
            matches = [row for row in fits if row["case"] == case and row["method"] == method]
            if len(matches) != 1:
                raise ValueError(f"exactly one sealed capacity pair required: {case}/{method}")
            fit = matches[0]
            if fit["label"] != f"{case}_{method}" or len(fit["capacities"]) != 2 or not np.all(np.isfinite(fit["capacities"])):
                raise ValueError("invalid sealed capacity pair")
            rows.append(dict(fit, replay_source="reused" if method == METHODS[0] and case in REUSE else "new"))
    return rows


def paired_comparison(metrics, plan):
    frame = pd.DataFrame(metrics).merge(pd.DataFrame(plan)[["label", "case", "method"]], on="label", validate="many_to_one")
    rows = []
    for (case, period, kind, name), group in frame.groupby(["case", "period", "kind", "name"], sort=False):
        raw = group[group.method == METHODS[0]].iloc[0]
        smooth = group[group.method == METHODS[1]].iloc[0]
        key = "mean_nrmse" if kind == "executed_flux" else "excursion_nrmse"
        rows.append({"case": case, "period": period, "kind": kind, "name": name,
                     "metric": key, "raw_error": float(raw[key]), "smoothed_error": float(smooth[key]),
                     "smoothed_minus_raw": float(smooth[key]-raw[key]),
                     "raw_mean_nrmse": float(raw.mean_nrmse), "smoothed_mean_nrmse": float(smooth.mean_nrmse),
                     "raw_endpoint_error": float(raw.last_error), "smoothed_endpoint_error": float(smooth.last_error)})
    paired = pd.DataFrame(rows)
    noisy = paired[paired.case != "clean"]
    aggregates = []
    for (period, kind, name), group in noisy.groupby(["period", "kind", "name"], sort=False):
        if len(group) != 5:
            raise ValueError("five matched seeds required for every metric")
        aggregates.append({"period": period, "kind": kind, "name": name, "noise_seed_count": 5,
                           "raw_median": float(group.raw_error.median()), "smoothed_median": float(group.smoothed_error.median()),
                           "raw_maximum": float(group.raw_error.max()), "smoothed_maximum": float(group.smoothed_error.max()),
                           "smoothed_better_seed_count": int((group.smoothed_minus_raw < 0).sum()),
                           "median_paired_difference": float(group.smoothed_minus_raw.median()),
                           "raw_mean_nrmse_maximum": float(group.raw_mean_nrmse.max()),
                           "smoothed_mean_nrmse_maximum": float(group.smoothed_mean_nrmse.max())})
    return paired, pd.DataFrame(aggregates)


def plot_results(out, truth, names, plan, paired):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = {METHODS[0]: "#b45446", METHODS[1]: "#168577"}
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    for i, pool in enumerate(("EGLC", "ELAC")):
        for j in (0, 1):
            axis = axes[i, j]
            reference = truth["states"][names.index(pool)] if j == 0 else truth["effective"][i]
            axis.plot(truth["time"], reference, color="black", linewidth=2, label="Synthetic truth")
            for row in plan:
                values = np.load(out / "replays" / row["label"] / "evaluation.npz")
                actual = values["states"][names.index(pool)] if j == 0 else values["effective_flux"][i]
                clean = row["case"] == "clean"
                axis.plot(truth["time"], actual, color=colors[row["method"]], alpha=1 if clean else .28,
                          linewidth=1.6 if clean else .8, linestyle="--" if clean else "-",
                          label=row["method"] + " (clean)" if clean else None)
            axis.axvspan(22, 46, color="#777777", alpha=.08)
            axis.axvline(22, color="#777777", linestyle=":")
            axis.set(xlabel="Model day", ylabel="mM" if j == 0 else "mM/day",
                     title=pool if j == 0 else ("VEGLC" if i == 0 else "VELAC"))
            axis.spines[["top", "right"]].set_visible(False)
            axis.grid(alpha=.15)
    axes[0, 0].legend(fontsize=8, frameon=False)
    fig.suptitle("Free ODE: fixed interval capacities | thin lines: five noise seeds | shaded: holdout", fontsize=12)
    for suffix in ("png", "pdf"):
        fig.savefig(out / f"free_ODE_predictions.{suffix}", dpi=170)
    plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), constrained_layout=True)
    for i, name in enumerate(("EGLC", "ELAC", "VEGLC", "VELAC")):
        axis = axes.flat[i]
        group = paired[(paired.period == "holdout") & (paired.name == name)]
        for position, case in enumerate(["clean"] + [f"noise_{seed}" for seed in SEEDS]):
            row = group[group.case == case].iloc[0]
            axis.plot([position-.13, position+.13], [row.raw_error*100, row.smoothed_error*100], color="#999999", linewidth=1)
            axis.scatter(position-.13, row.raw_error*100, color=colors[METHODS[0]], label="Raw inputs" if position == 0 else None)
            axis.scatter(position+.13, row.smoothed_error*100, color=colors[METHODS[1]], label="Smoothed inputs" if position == 0 else None)
        axis.set_xticks(range(6), ["Clean"] + [str(s) for s in SEEDS], rotation=25)
        axis.set(title=name, ylabel="Excursion nRMSE (%)" if i < 2 else "RMS-normalized flux error (%)", ylim=(0, None))
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(axis="y", alpha=.15)
    axes[0, 0].legend(frameon=False, fontsize=9)
    fig.suptitle("J22-J46 predictions: clean bias and paired five-seed errors", fontsize=13)
    for suffix in ("png", "pdf"):
        fig.savefig(out / f"paired_holdout_errors.{suffix}", dpi=170)
    plt.close(fig)


def run(config_path, out):
    if out.exists():
        raise FileExistsError("fresh output required; sealed evidence is never overwritten")
    design = validate_design(json.loads(config_path.read_text()))
    parent = ROOT / design["parent_archive"]
    parent_contract = verify_archive_inputs(parent)
    working = parent_contract["working_reference"]
    if working != load_working_reference():
        raise ValueError("working reference changed")
    truth_parent = ROOT / parent_contract["design"]["parent_archive"]
    verify_archive_inputs(truth_parent)
    truth = np.load(truth_parent / "truth/evaluation.npz")
    params = json.loads((parent / "frozen_parameters.json").read_text())
    initial_archive = np.load(parent / "frozen_initial_state.npz")
    initial, names = initial_archive["states"], tuple(initial_archive["names"])
    plan = replay_plan(design, json.loads((parent / "conditional_results.json").read_text()))
    final_parent = json.loads((parent / "final_verification.json").read_text())
    inputs = set(Path(path) for path in parent_contract["input_sha256"])
    inputs.update(Path(path) for path in final_parent["supporting_code_sha256"])
    inputs.update(parent / path for path in final_parent["output_sha256"])
    inputs.update([parent / "final_verification.json", parent / "independent_verification.json",
                   truth_parent / "truth/evaluation.npz", config_path, Path(__file__)])
    hashes = {str(p.resolve()): file_hash(p) for p in sorted(inputs)}
    out.mkdir(parents=True)
    contract = {"contract_type": design["purpose"], "created_at": datetime.now(timezone.utc).isoformat(),
                "design": design, "working_reference": working, "input_sha256": hashes,
                "replay_plan": plan, "planned_new_integrations": 16, "planned_reused_integrations": 8,
                "planned_total_integrations": 24, "new_fit_count": 0,
                "raw_signed_observation_increments_unchanged": True,
                "prediction_does_not_receive_smoothed_inputs": True,
                "all_other_kinetics_ICs_and_numerics_frozen": True,
                "synthetic_only": True, "truth_used_only_for_evaluation": True,
                "biological_calibration_allowed": False, "global_model_promotion_allowed": False}
    write_json(out / "preregistered_contract.json", contract)
    shutil.copy2(parent / "frozen_initial_state.npz", out / "frozen_initial_state.npz")
    shutil.copy2(parent / "frozen_parameters.json", out / "frozen_parameters.json")
    (out / "replays").mkdir()
    metrics, completed, reuse_receipts = [], [], []
    for row in plan:
        label = row["label"]
        candidate = dict(params, **dict(zip(PARAMETERS, row["capacities"])))
        directory = out / "replays" / label
        print(f"Fixed-capacity replay {len(completed)+1}/12: {label} [{row['replay_source']}]", flush=True)
        if row["replay_source"] == "reused":
            directory.mkdir()
            for filename in REPLAY_FILES:
                source = parent / "replays" / label / filename
                shutil.copy2(source, directory / filename)
                reuse_receipts.append({"label": label, "file": filename, "source": str(source), "sha256": file_hash(source)})
            if json.loads((directory / "learned_synthetic_parameters.json").read_text()) != candidate:
                raise ValueError("reused kinetic vector does not match sealed fit")
            evaluation = np.load(directory / "evaluation.npz")
            states, parts = evaluation["states"], {"effective": evaluation["effective_flux"]}
            checks = json.loads((directory / "numerical_audit.json").read_text())
        else:
            solutions = simulate(initial, candidate, working, design["horizon_day"], directory)
            states, parts, checks = audit_solutions(solutions, truth["time"], candidate, working, names, directory)
            write_json(directory / "learned_synthetic_parameters.json", candidate)
            np.savez_compressed(directory / "evaluation.npz", time=truth["time"], states=states,
                                effective_flux=parts["effective"], native_flux=parts["native"], availability_factors=parts["factors"])
        metrics.extend(replay_metrics(states, parts, truth, label, names, design["training_end_day"]))
        completed.append(dict(row, numerical_checks=checks))
        write_json(out / "partial_replay_results.json", completed)
    paired, aggregate = paired_comparison(metrics, plan)
    pd.DataFrame(metrics).to_csv(out / "full_pool_replay_metrics.csv", index=False)
    paired.to_csv(out / "paired_metrics.csv", index=False)
    aggregate.to_csv(out / "five_seed_summary.csv", index=False)
    write_json(out / "reuse_receipts.json", reuse_receipts)
    unchanged = {path: file_hash(Path(path)) == digest for path, digest in hashes.items()}
    if not all(unchanged.values()):
        raise ValueError("sealed inputs changed during replay")
    summary = {"status": "completed_fixed_capacity_free_ODE_validation", "replays": completed,
               "new_fit_count": 0, "new_ODE_integration_count": 16, "reused_ODE_integration_count": 8,
               "total_ODE_integration_count": 24, "replayed_pair_count": 12,
               "all_replayed_numerical_checks_pass": all(r["numerical_checks"]["passes"] for r in completed),
               "input_hashes_unchanged": True, "biological_calibration_allowed": False,
               "global_model_promotion_allowed": False, "five_seed_results": aggregate.to_dict("records")}
    write_json(out / "summary.json", summary)
    plot_results(out, truth, names, plan, paired)
    lines = ["# Fixed-capacity free-ODE validation: smoothed interval inputs", "",
             "Synthetic software validation only. No new fits, biological calibration or kinetic/default promotion.",
             "Twelve frozen capacity pairs: clean and five paired sparse noise seeds, raw versus smoothed kinetic inputs.",
             "16 new strict/ultrastrict integrations plus eight copied verified integrations; 24 total. J1-J46 unforced.",
             "Smoothing was used only to learn capacities on J1-J22. Prediction receives neither observed nor smoothed inputs.",
             "Raw signed concentration increments remain training targets; full ICs, affinities, other kinetics and threshold are fixed.", "",
             "## Five-seed held-out prediction", "",
             "| Quantity | Raw median (%) | Smoothed median (%) | Raw maximum (%) | Smoothed maximum (%) | Smoothed better seeds /5 |",
             "|---|---:|---:|---:|---:|---:|"]
    for name in ("EGLC", "ELAC", "GLC", "LAC", "VEGLC", "VELAC"):
        row = aggregate[(aggregate.period == "holdout") & (aggregate.name == name)].iloc[0]
        lines.append(f"| {name} | {100*row.raw_median:.6g} | {100*row.smoothed_median:.6g} | {100*row.raw_maximum:.6g} | {100*row.smoothed_maximum:.6g} | {int(row.smoothed_better_seed_count)} |")
    lines += ["", "Concentration errors use truth excursion (floor 0.001 mM); flux errors use truth RMS (floor 1e-6 mM/day).",
              "Absolute RMSE, mean-normalized errors and signed endpoints for all 113 pools and both executed fluxes are exported.", "",
              "## Clean control (not included in noisy medians)", "",
              "| Quantity | Raw holdout (%) | Smoothed holdout (%) | Raw signed J46 error | Smoothed signed J46 error |",
              "|---|---:|---:|---:|---:|"]
    for name in ("EGLC", "ELAC", "VEGLC", "VELAC"):
        row = paired[(paired.case == "clean") & (paired.period == "holdout") & (paired.name == name)].iloc[0]
        lines.append(f"| {name} | {100*row.raw_error:.6g} | {100*row.smoothed_error:.6g} | {row.raw_endpoint_error:.6g} | {row.smoothed_endpoint_error:.6g} |")
    lines += ["", "## Interpretation boundaries", "",
              "Five synthetic noise seeds are descriptive paired stress tests, not biological replicates or confidence intervals.",
              "Same-family truth, known full ICs, fixed affinities and only two capacities do not establish global identifiability.",
              "A favorable noisy median does not establish universal superiority: inspect clean bias, worst seed and all latent pools.",
              "Numerical positivity applies to raw accepted and archived dense samples, not a formal continuous-time proof.",
              "Numerical acceptance is not experimental accuracy: no new biological limits are invented.",
              "Biological readiness and the prepared, unauthorized 38 coupled energy replays remain unchanged."]
    (out / "decision_report.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    write_json(out / "final_verification.json", {"input_hash_checks": unchanged, "input_hashes_unchanged": True,
               "biological_contract_changed": False, "parameters_promoted": False,
               "new_ODE_integration_count": 16, "reused_ODE_integration_count": 8})
    print(json.dumps({k: v for k, v in summary.items() if k not in {"replays", "five_seed_results"}}), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    run(args.config.resolve(), args.out.resolve())
