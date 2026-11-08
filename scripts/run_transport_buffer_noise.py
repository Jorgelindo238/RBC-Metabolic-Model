"""Freeze then execute the three-seed noise challenge without editing old archives."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fla_transport_buffer_synthetic import simulate
from fla_transport_buffer_recovery import STAGES, prediction_metrics, recover, training_times
from fla_transport_buffer_noise import (bounds_hit, generate_panel, group_diagnostics, observed_metrics,
    panel_values, summarize_noisy, validate_noise)
from prepare_transport_buffer_benchmark import close, sha, write_json
from run_transport_buffer_recovery import (numerical_checks, save_prediction, saved_reference, verify as verify_clean)

CONFIG = ROOT / "config/fla_transport_buffer_noise.json"
CLEAN = ROOT / "output/transport_buffer_clean_recovery_2026_10_23"
PREPARATION = ROOT / "output/transport_buffer_synthetic_preparation_2026_10_06"


def configuration():
    config = json.loads((PREPARATION / "preregistered_design.json").read_text())["design"]
    design = json.loads(CONFIG.read_text())
    validate_noise(config, design)
    return config, design


def panel_name(scenario, seed):
    return f"{scenario['name']}_seed{seed}_noise_panel.npz"


def load_panel(path):
    with np.load(path) as a:
        return {k: a[k].copy() for k in a.files}


def fit_key(scenario, seed, schedule, stage, plan, start):
    return f"{scenario['name']}_seed{seed}_{schedule}_{stage}_{plan}_start{start}"


def prepare(out):
    if out.exists():
        raise ValueError("new noise archive required")
    verify_clean(CLEAN)
    config, design = configuration()
    upstream = json.loads((CLEAN / "execution_design.json").read_text())["input_sha256"]
    protected = [ROOT / p for p in upstream] + list(CLEAN.iterdir())
    protected += [CONFIG, Path(__file__), ROOT / "src/fla_transport_buffer_noise.py",
                  ROOT / "qa/test_transport_buffer_noise.py", ROOT / "scripts/audit_transport_buffer_noise.py"]
    hashes = {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p) for p in protected if p.is_file()}
    out.mkdir(parents=True)
    write_json(out / "execution_design.json", {"design": design, "input_sha256": hashes,
        "phase": "noise_frozen_before_recovery", "stages": STAGES, "schedules": ["sparse", "dense"],
        "python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
        "optimizer_and_thresholds": "unchanged_from_sealed_clean_recovery",
        "known_initial_concentration_and_pHe_context": True,
        "noise_is_not_a_measured_biological_error_model": True})
    for i, scenario in enumerate(config["scenarios"]):
        reference = saved_reference(scenario)
        for seed in design["noise_seeds"]:
            panel = generate_panel(config, design, i, seed, reference)
            np.savez_compressed(out / panel_name(scenario, seed), **panel)
    write_json(out / "noise_manifest.json", {"output_sha256": {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()}})
    return verify_frozen(out)


def verify_frozen(out):
    config, design = configuration()
    frozen = json.loads((out / "execution_design.json").read_text())
    if frozen["design"] != design:
        raise ValueError("noise protocol changed after freezing")
    for name, expected in frozen["input_sha256"].items():
        if sha(ROOT / name) != expected:
            raise ValueError("protected noise input changed: " + name)
    for name, expected in json.loads((out / "noise_manifest.json").read_text())["output_sha256"].items():
        if sha(out / name) != expected:
            raise ValueError("frozen noise output changed: " + name)
    count = 0
    for i, scenario in enumerate(config["scenarios"]):
        for seed in design["noise_seeds"]:
            panel = load_panel(out / panel_name(scenario, seed))
            expected = generate_panel(config, design, i, seed, saved_reference(scenario))
            if set(panel) != set(expected) or any(not np.array_equal(panel[k], expected[k]) for k in expected):
                raise ValueError("noise reconstruction failed")
            count += 1
    return {"noise_frozen_verified": True, "panels": count, "recovery_fits_executed": 0}


def equivalent_controls(config, out, fits, design):
    controls = []
    for scenario in config["scenarios"]:
        for seed in design["noise_seeds"]:
            fit = next(f for f in fits if f["scenario"] == scenario["name"] and f["noise_seed"] == seed
                       and f["stage"] == "access_pHi" and f["schedule"] == "sparse"
                       and f["plan"] == "concentrations_plus_pHi_pHe" and f["start_index"] == 0)
            p = fit["parameters"]
            for factor in config["negative_control"]["scale_factors"]:
                base = simulate(config, scenario, updates={"access_i": p["access_i"]}, phi0=p["phi0"])
                shifted = simulate(config, scenario, updates={"access_i": factor*p["access_i"],
                    "km_i": factor*config["truth"]["km_i"]}, phi0=p["phi0"]+np.log10(factor), time=base["time"])
                checks = {"concentrations": close(base["states"][:2], shifted["states"][:2], config),
                    "pHe": close(base["states"][3], shifted["states"][3], config),
                    "flux": close(base["flux"], shifted["flux"], config),
                    "pHi_shift": close(shifted["states"][2]-base["states"][2], np.log10(factor), config)}
                if not all(checks.values()):
                    raise ValueError("equivalent family failed; noise cannot repair exact observation symmetry")
                name = f"{scenario['name']}_seed{seed}_equivalent_{factor}.npz"
                np.savez_compressed(out / name, time=base["time"], base_states=base["states"],
                    shifted_states=shifted["states"], base_flux=base["flux"], shifted_flux=shifted["flux"])
                controls.append({"scenario": scenario["name"], "noise_seed": seed, "factor": factor,
                    "checks": checks, "file": name, "source_start": 0,
                    "interpretation": "same_unknown_Km_family_even_with_noisy_concentration_and_pHe_observations"})
    return controls


def run(out):
    if (out / "manifest.json").exists() or list(out.glob("*_start*.json")):
        raise ValueError("do not overwrite/restart a recovery campaign; use a fresh archive")
    verify_frozen(out)
    config, design = configuration()
    fits, grouped = [], defaultdict(list)
    for scenario in config["scenarios"]:
        reference = saved_reference(scenario)
        for seed in design["noise_seeds"]:
            panel = load_panel(out / panel_name(scenario, seed))
            for schedule in ("sparse", "dense"):
                time_train = training_times(config, schedule)
                values = panel_values(panel, time_train)
                for stage, (_, plans) in STAGES.items():
                    for plan in plans:
                        rows = config["observation_plans"][plan]
                        for start in range(len(config["future_recovery"]["start_vectors"])):
                            begin = time.perf_counter()
                            fit = recover(config, scenario, stage, plan, time_train, values[rows], start)
                            fit.update({"noise_seed": seed, "schedule": schedule,
                                        "noise_panel_file": panel_name(scenario, seed)})
                            p = fit["parameters"]
                            kwargs = {"updates": {k: v for k, v in p.items() if k != "phi0"},
                                      "phi0": p.get("phi0"), "time": reference["time"]}
                            strict = simulate(config, scenario, profile="strict", **kwargs)
                            ultra = simulate(config, scenario, profile="ultrastrict", **kwargs)
                            fit.update(prediction_metrics(config, scenario, p, ultra, reference))
                            fit.update(observed_metrics(config, plan, panel, time_train, ultra))
                            fit.update(numerical_checks(config, strict, ultra))
                            fit["bound_hits"] = bounds_hit(config, design, p)
                            fit["recovery_pass"] = bool(fit["optimizer_success"] and fit["numerical_pass"]
                                and fit["parameter_recovery_pass"] and fit["holdout_prediction_pass"])
                            fit["seconds"] = time.perf_counter()-begin
                            key = fit_key(scenario, seed, schedule, stage, plan, start)
                            fit["prediction_file"] = key+".npz"
                            save_prediction(out / fit["prediction_file"], reference, strict, ultra)
                            write_json(out / (key+".json"), fit)
                            fits.append(fit)
                            grouped[(scenario["name"], seed, schedule, stage, plan)].append(fit)
                            print(f"{len(fits):03d}/216 {key}: params={fit['parameter_recovery_pass']} "
                                  f"holdout={fit['holdout_prediction_pass']} optimizer={fit['optimizer_success']} "
                                  f"calls={fit['actual_objective_evaluations']}", flush=True)
    groups = [group_diagnostics(config, members) for members in grouped.values()]
    controls = equivalent_controls(config, out, fits, design)
    summary = summarize_noisy(config, fits, groups, controls)
    write_json(out / "multistart_groups.json", groups)
    write_json(out / "summary.json", summary)
    verify_frozen(out)
    write_json(out / "manifest.json", {"output_sha256": {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()}})
    return verify(out)


def verify(out):
    verify_frozen(out)
    config, design = configuration()
    for name, expected in json.loads((out / "manifest.json").read_text())["output_sha256"].items():
        if sha(out / name) != expected:
            raise ValueError("noise recovery output changed: " + name)
    fits, grouped = [], defaultdict(list)
    for scenario in config["scenarios"]:
        reference = saved_reference(scenario)
        for seed in design["noise_seeds"]:
            panel = load_panel(out / panel_name(scenario, seed))
            for schedule in ("sparse", "dense"):
                for stage, (_, plans) in STAGES.items():
                    for plan in plans:
                        for start in range(len(config["future_recovery"]["start_vectors"])):
                            key = fit_key(scenario, seed, schedule, stage, plan, start)
                            fit = json.loads((out / (key+".json")).read_text())
                            time_train = training_times(config, schedule)
                            if (fit["training_days"] != time_train.tolist() or not 0 < len(fit["trace"])
                                    == fit["actual_objective_evaluations"] <= config["future_recovery"]["optimizer_budget_max_nfev"]
                                    or any(t["integration_end"] != config["training_end_day"] for t in fit["trace"])):
                                raise ValueError("invalid objective budget or training separation")
                            with np.load(out / fit["prediction_file"]) as a:
                                if not np.array_equal(a["reference_states"], reference["states"]):
                                    raise ValueError("truth reference changed")
                                result = {"time": a["time"], "states": a["ultrastrict_states"]}
                                metrics = {**prediction_metrics(config, scenario, fit["parameters"], result, reference),
                                           **observed_metrics(config, plan, panel, time_train, result)}
                                if any(fit[k] != v for k, v in metrics.items()):
                                    raise ValueError("noisy prediction metric reconstruction failed")
                                for profile in config["solver_profiles"]:
                                    x, initial = a[profile+"_states"], a[profile+"_initial"]
                                    h = config["geometry"]["hematocrit"]
                                    p = fit["parameters"]
                                    extent_expected = np.vstack([initial[0]-x[4], initial[1]+h/(1-h)*x[4],
                                        initial[2]+x[4]/config["truth"]["beta_i"],
                                        initial[3]-h/(1-h)*x[4]/p.get("beta_e", config["truth"]["beta_e"])])
                                    if (initial[2] != p.get("phi0", scenario["initial"][2])
                                            or min(x[:2].min(), a[profile+"_accepted_states"][:2].min()) < 0
                                            or not close(x[:4], extent_expected, config)
                                            or a[profile+"_accepted_time"][-1] != config["horizon_day"][-1]):
                                        raise ValueError("stored toy invariants failed")
                                if not close(a["strict_states"], a["ultrastrict_states"], config):
                                    raise ValueError("strict/ultrastrict state mismatch")
                            if (fit["numerical_pass"] != all(fit["checks"].values())
                                    or fit["bound_hits"] != bounds_hit(config, design, fit["parameters"])
                                    or fit["recovery_pass"] != bool(fit["optimizer_success"] and fit["numerical_pass"]
                                        and fit["parameter_recovery_pass"] and fit["holdout_prediction_pass"])):
                                raise ValueError("success indicators changed")
                            fits.append(fit)
                            grouped[(scenario["name"], seed, schedule, stage, plan)].append(fit)
    groups = [group_diagnostics(config, members) for members in grouped.values()]
    if groups != json.loads((out / "multistart_groups.json").read_text()):
        raise ValueError("group reconstruction failed")
    summary = json.loads((out / "summary.json").read_text())
    controls = summary["equivalent_family_controls"]
    if len(controls) != 12:
        raise ValueError("incomplete negative controls")
    for control in controls:
        with np.load(out / control["file"]) as a:
            if (not close(a["base_states"][:2], a["shifted_states"][:2], config)
                    or not close(a["base_states"][3], a["shifted_states"][3], config)
                    or not close(a["base_flux"], a["shifted_flux"], config)
                    or not close(a["shifted_states"][2]-a["base_states"][2], np.log10(control["factor"]), config)):
                raise ValueError("stored equivalent-family control failed")
    if (len(fits) != design["fits_expected"] or len(groups) != design["multistart_groups_expected"]
            or summary != summarize_noisy(config, fits, groups, controls)):
        raise ValueError("summary/coverage reconstruction failed")
    return {"verified": True, **{k: summary[k] for k in ("fits_executed", "independent_noise_panels", "optimizer_success",
        "parameter_recovery_pass", "holdout_prediction_pass", "recovery_pass", "numerical_pass", "budget_exhausted_fits")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", type=Path)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if sum(bool(x) for x in (args.prepare, args.run, args.verify)) != 1:
        parser.error("choose exactly one phase: --prepare, --run or --verify")
    print(json.dumps(prepare(args.prepare.resolve()) if args.prepare else
                     run(args.run.resolve()) if args.run else verify(args.verify.resolve()), indent=2))
