"""Paired observation likelihood and controlled larger-budget follow-up."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fla_observation_likelihood import mixed_assay_likelihood
from fla_transport_buffer_synthetic import simulate
from fla_transport_buffer_recovery import prediction_metrics, select_saved, training_times
from fla_transport_buffer_noise import bounds_hit, group_diagnostics, observed_metrics, panel_values, summarize_noisy
from fla_transport_likelihood import recover_objective
from prepare_transport_buffer_benchmark import close, sha, write_json
from run_transport_buffer_recovery import numerical_checks, save_prediction, saved_reference
from run_transport_buffer_noise import configuration, load_panel, panel_name, verify as verify_noise

CONFIG = ROOT / "config/fla_transport_likelihood_comparison.json"
NOISE = ROOT / "output/transport_buffer_noisy_recovery_2026_10_23"


def grouped_summary(config, fits):
    grouped = defaultdict(list)
    for f in fits:
        grouped[(f["scenario"], f["noise_seed"], f["schedule"], f["stage"], f["plan"])].append(f)
    groups = [group_diagnostics(config, members) for members in grouped.values()]
    return summarize_noisy(config, fits, groups, []), groups


def refit(config, noise_design, old, kind, budget, folder):
    scenario = next(s for s in config["scenarios"] if s["name"] == old["scenario"])
    reference = saved_reference(scenario)
    panel = load_panel(NOISE / panel_name(scenario, old["noise_seed"]))
    train_time = training_times(config, old["schedule"])
    rows = config["observation_plans"][old["plan"]]
    fit = recover_objective(config, scenario, old["stage"], old["plan"], train_time,
        panel_values(panel, train_time)[rows], old["start_index"], kind=kind, budget=budget)
    fit.update({k: old[k] for k in ("noise_seed", "schedule", "noise_panel_file")})
    kwargs = {"updates": {k: v for k, v in fit["parameters"].items() if k != "phi0"},
              "phi0": fit["parameters"].get("phi0"), "time": reference["time"]}
    strict, ultra = [simulate(config, scenario, profile=p, **kwargs) for p in ("strict", "ultrastrict")]
    fit.update(prediction_metrics(config, scenario, fit["parameters"], ultra, reference))
    fit.update(observed_metrics(config, old["plan"], panel, train_time, ultra))
    fit.update(numerical_checks(config, strict, ultra))
    fit["bound_hits"] = bounds_hit(config, noise_design, fit["parameters"])
    fit["recovery_pass"] = bool(fit["optimizer_success"] and fit["numerical_pass"]
        and fit["parameter_recovery_pass"] and fit["holdout_prediction_pass"])
    source = old["source_fit"]
    key = source.removesuffix(".json")
    fit["source_fit"] = source
    fit["prediction_file"] = key+".npz"
    folder.mkdir(parents=True, exist_ok=True)
    save_prediction(folder / fit["prediction_file"], reference, strict, ultra)
    write_json(folder / source, fit)
    return fit


def paired_metrics(baseline, matched):
    result = {}
    for name in ("optimizer_success", "parameter_recovery_pass", "holdout_prediction_pass", "recovery_pass"):
        result[name] = {"baseline": sum(f[name] for f in baseline), "matched": sum(f[name] for f in matched),
            "gained_pairs": sum(not a[name] and b[name] for a, b in zip(baseline, matched)),
            "lost_pairs": sum(a[name] and not b[name] for a, b in zip(baseline, matched))}
    return result


def control_checks(config):
    summary = json.loads((NOISE / "summary.json").read_text())
    checks = []
    for c in summary["equivalent_family_controls"]:
        scenario = next(s for s in config["scenarios"] if s["name"] == c["scenario"])
        panel = load_panel(NOISE / panel_name(scenario, c["noise_seed"]))
        with np.load(NOISE / c["file"]) as a:
            rows = [0, 1, 3]
            states = [select_saved(a["time"], a[k], panel["time"])[rows] for k in ("base_states", "shifted_states")]
            mask = np.ones(states[0].shape, dtype=bool)
            mask[:2, 0] = False
            nll = [mixed_assay_likelihood(x, panel["observed_states"][rows], rows, concentration_cv=.005,
                                          ph_sd=.005, mask=mask)["negative_log_likelihood"] for x in states]
            if not close(nll[0], nll[1], config):
                raise ValueError("likelihood falsely breaks the unknown-Km family")
            checks.append({"source_control": c["file"], "matched_NLL_difference": nll[1]-nll[0], "equivalent": True})
    return checks


def run(out):
    if out.exists():
        raise ValueError("fresh likelihood comparison archive required")
    verify_noise(NOISE)
    config, noise_design = configuration()
    design = json.loads(CONFIG.read_text())
    if design["primary_budget"] != 100 or design["secondary_budgets"] != [500, 2000]:
        raise ValueError("explicit primary/secondary protocol required")
    old_inputs = json.loads((NOISE / "execution_design.json").read_text())["input_sha256"]
    files = [ROOT / p for p in old_inputs]+list(NOISE.iterdir())+[CONFIG, Path(__file__),
        ROOT / "src/fla_observation_likelihood.py", ROOT / "src/fla_transport_likelihood.py",
        ROOT / "qa/test_fla_observation_likelihood.py"]
    hashes = {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p) for p in files if p.is_file()}
    out.mkdir(parents=True)
    write_json(out / "execution_design.json", {"design": design, "input_sha256": hashes,
        "primary": "216 archived current-cost fits paired with 216 new matched-likelihood fits",
        "secondary": "only optimizer failures, same original starts, no truth-based selection",
        "biological_calibration": "not_executed_by_this_synthetic_runner"})
    baseline, matched = [], []
    for i, file in enumerate(sorted(NOISE.glob("*_start*.json")), 1):
        old = json.loads(file.read_text())
        old["source_fit"] = file.name
        baseline.append(old)
        fit = refit(config, noise_design, old, "matched_likelihood", 100, out / "primary")
        matched.append(fit)
        print(f"{i:03d}/216 {file.stem}: params={fit['parameter_recovery_pass']} pred={fit['holdout_prediction_pass']} "
              f"optimizer={fit['optimizer_success']} calls={fit['actual_objective_evaluations']}", flush=True)
    base_summary, base_groups = grouped_summary(config, baseline)
    matched_summary, groups = grouped_summary(config, matched)
    extensions = []
    for kind, fits in (("current_cost", baseline), ("matched_likelihood", matched)):
        for old in fits:
            if old["optimizer_success"]:
                continue
            for budget in design["secondary_budgets"]:
                folder = out / "secondary" / kind / f"budget{budget}"
                fit = refit(config, noise_design, old, kind, budget, folder)
                extensions.append({"objective": kind, "budget": budget, "source_fit": old["source_fit"],
                    "record": str((folder/old["source_fit"]).relative_to(out)).replace("\\", "/"),
                    **{k: fit[k] for k in ("optimizer_success", "numerical_pass", "parameter_recovery_pass", "holdout_prediction_pass",
                                          "recovery_pass", "actual_objective_evaluations")}})
                print(f"secondary {kind} {budget}: {old['source_fit']} optimizer={fit['optimizer_success']}", flush=True)
                if fit["optimizer_success"]:
                    break
    controls = control_checks(config)
    summary = {"paired_fits": len(matched), "independent_noise_panels": 6, "primary_pairs": paired_metrics(baseline, matched),
        "baseline_summary": base_summary, "matched_summary": matched_summary,
        "matched_all_starts_recovery_groups": sum(g["all_starts_recovery_pass"] for g in groups),
        "matched_all_starts_parameter_groups": sum(g["all_starts_parameter_pass"] for g in groups),
        "matched_all_starts_holdout_groups": sum(g["all_starts_holdout_pass"] for g in groups),
        "secondary": extensions, "negative_control_checks": controls,
        "primary_results_replaced_by_secondary": False, "biological_kinetic_parameters_changed": False}
    write_json(out / "multistart_groups.json", groups)
    write_json(out / "summary.json", summary)
    if any(sha(ROOT / name) != digest for name, digest in hashes.items()):
        raise ValueError("comparison input changed")
    write_json(out / "manifest.json", {"output_sha256": {str(p.relative_to(out)).replace("\\", "/"): sha(p)
        for p in sorted(out.rglob("*")) if p.is_file()}})
    return verify(out)


def verify_fit(config, fit, folder):
    scenario = next(s for s in config["scenarios"] if s["name"] == fit["scenario"])
    reference = saved_reference(scenario)
    panel = load_panel(NOISE / panel_name(scenario, fit["noise_seed"]))
    if (not 0 < len(fit["trace"]) == fit["actual_objective_evaluations"] <= fit["evaluation_budget"]
            or any(t["integration_end"] != config["training_end_day"] for t in fit["trace"])):
        raise ValueError("invalid budget or temporal separation")
    with np.load(folder / fit["prediction_file"]) as a:
        metrics = prediction_metrics(config, scenario, fit["parameters"], {"time": a["time"], "states": a["ultrastrict_states"]}, reference)
        if any(fit[k] != value for k, value in metrics.items()):
            raise ValueError("metric reconstruction failed")
        if not close(a["strict_states"], a["ultrastrict_states"], config) or min(a["ultrastrict_states"][:2].min(),
                                                                                 a["ultrastrict_accepted_states"][:2].min()) < 0:
            raise ValueError("stored positivity/convergence check failed")
    if fit["recovery_pass"] != bool(fit["optimizer_success"] and fit["numerical_pass"] and fit["parameter_recovery_pass"] and fit["holdout_prediction_pass"]):
        raise ValueError("recovery flag changed")


def verify(out):
    frozen = json.loads((out / "execution_design.json").read_text())
    for name, digest in frozen["input_sha256"].items():
        if sha(ROOT / name) != digest:
            raise ValueError("protected comparison input changed: "+name)
    for name, digest in json.loads((out / "manifest.json").read_text())["output_sha256"].items():
        if sha(out / name) != digest:
            raise ValueError("comparison output changed: "+name)
    config, _ = configuration()
    baseline, fits = [], []
    for file in sorted((out / "primary").glob("*_start*.json")):
        f = json.loads(file.read_text())
        verify_fit(config, f, file.parent)
        old = json.loads((NOISE / f["source_fit"]).read_text())
        baseline.append(old)
        fits.append(f)
    if len(fits) != 216:
        raise ValueError("incomplete paired comparison")
    summary = json.loads((out / "summary.json").read_text())
    matched_summary, groups = grouped_summary(config, fits)
    if (summary["primary_pairs"] != paired_metrics(baseline, fits) or summary["matched_summary"] != matched_summary
            or groups != json.loads((out / "multistart_groups.json").read_text())
            or summary["negative_control_checks"] != control_checks(config)):
        raise ValueError("paired/group/control reconstruction failed")
    for extension in summary["secondary"]:
        file = out / extension["record"]
        fit = json.loads(file.read_text())
        verify_fit(config, fit, file.parent)
        original = json.loads((NOISE / extension["source_fit"]).read_text()) if extension["objective"] == "current_cost" else next(
            f for f in fits if f["source_fit"] == extension["source_fit"])
        if original["optimizer_success"]:
            raise ValueError("secondary budget selected by truth error instead of optimizer failure")
    return {"verified": True, "pairs": len(fits), "primary": summary["primary_pairs"],
            "secondary_fits": len(summary["secondary"]), "biological_ODE_replays": 0}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path)
    p.add_argument("--verify", type=Path)
    args = p.parse_args()
    if bool(args.out) == bool(args.verify):
        p.error("choose --out or --verify")
    print(json.dumps(run(args.out.resolve()) if args.out else verify(args.verify.resolve()), indent=2))
