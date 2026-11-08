"""Execute a successor archive of bounded clean synthetic recovery only."""

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
from fla_transport_buffer_synthetic import quadrature, simulate
from fla_transport_buffer_recovery import (STAGES, multistart_agreement, prediction_metrics, recover,
                                           select_saved, training_times)
from prepare_transport_buffer_benchmark import close, sha, verify as verify_preparation, write_json

PREPARATION = ROOT / "output/transport_buffer_synthetic_preparation_2026_10_06"


def saved_reference(scenario):
    with np.load(PREPARATION / f"{scenario['name']}_ultrastrict.npz") as a:
        return {k: a[k].copy() for k in ("time", "states", "flux")}


def numerical_checks(config, strict, ultra):
    q4, q8 = [quadrature(ultra, config, order) for order in config["quadrature_orders"]]
    checks = {"strict_ultrastrict_states": close(strict["states"], ultra["states"], config),
              "strict_ultrastrict_flux": close(strict["flux"], ultra["flux"], config),
              "quadrature_orders": close(q4, q8, config),
              "integral_extent": close(q8, ultra["states"][4, -1], config)}
    for label, result in (("strict", strict), ("ultrastrict", ultra)):
        for key in ("amount_residual", "acid_residual", "extent_state_residual"):
            checks[label + "_" + key] = close(result[key], 0, config)
        checks[label + "_positive"] = bool(min(result["states"][:2].min(), result["accepted_states"][:2].min()) >= 0)
        checks[label + "_complete"] = bool(result["accepted_time"][-1] == config["horizon_day"][-1])
    return {"checks": checks, "numerical_pass": all(checks.values()), "quadrature4": q4, "quadrature8": q8}


def save_prediction(path, reference, strict, ultra):
    arrays = {"time": ultra["time"], "reference_states": reference["states"], "reference_flux": reference["flux"]}
    for label, result in (("strict", strict), ("ultrastrict", ultra)):
        for key in ("states", "flux", "initial", "accepted_time", "accepted_states"):
            arrays[label + "_" + key] = result[key]
    np.savez_compressed(path, **arrays)


def summarize(fits, groups, controls):
    counts = defaultdict(lambda: {"fits": 0, "numerics_pass": 0, "parameter_recovery_pass": 0,
                                  "holdout_prediction_pass": 0, "optimizer_success": 0, "recovery_pass": 0})
    for fit in fits:
        label = fit["stage"] + "/" + fit["schedule"] + "/" + fit["plan"]
        c = counts[label]
        c["fits"] += 1
        for name in tuple(c)[1:]:
            c[name] += int(fit["numerical_pass" if name == "numerics_pass" else name])
    return {"fits_executed": len(fits), "actual_objective_integrations": sum(f["actual_objective_evaluations"] for f in fits),
            "full_horizon_validation_integrations": 2 * len(fits), "equivalent_family_integrations": 2 * len(controls),
            "group_count": len(groups), "multistart_groups_pass": sum(g["multistart_agreement_pass"] for g in groups),
            "all_numerical_checks_pass": all(f["numerical_pass"] for f in fits),
            "all_parameter_recovery_pass": all(f["parameter_recovery_pass"] for f in fits),
            "all_holdout_prediction_pass": all(f["holdout_prediction_pass"] for f in fits),
            "all_recovery_pass": all(f["recovery_pass"] for f in fits),
            "max_actual_objective_evaluations": max(f["actual_objective_evaluations"] for f in fits),
            "by_scope": dict(counts), "equivalent_family_controls": controls,
            "noise_experiments_executed": 0, "biological_ODE_replays": 0, "biological_parameters_promoted": False,
            "measured_initial_conditions_changed": False,
            "interpretation": "conditional_clean_toy_recovery_not_biological_readiness_or_global_identifiability"}


def run(out):
    if out.exists():
        raise ValueError("use a fresh successor output directory")
    verify_preparation(PREPARATION)
    frozen = json.loads((PREPARATION / "preregistered_design.json").read_text())
    config = frozen["design"]
    protected = list(PREPARATION.iterdir()) + [ROOT / p for p in frozen["input_sha256"]]
    protected += [Path(__file__), ROOT / "src/fla_transport_buffer_recovery.py", ROOT / "qa/test_transport_buffer_recovery.py",
                  ROOT / "src/equadiff_brodbar.py", ROOT / "src/MM_calibration.py", ROOT / "src/Data_Bordbar_et_al_exp.xlsx",
                  ROOT / "RBC/Rxn_RBC.txt", ROOT / "config/fla_working_reference.json"]
    hashes = {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p) for p in protected if p.is_file()}
    out.mkdir(parents=True)
    write_json(out / "execution_design.json", {"source_preparation": str(PREPARATION.relative_to(ROOT)).replace("\\", "/"),
        "input_sha256": hashes, "stages": STAGES, "training_schedules": ["sparse", "dense"],
        "noise": "none_clean_recovery_only", "budget_counts_all_residual_calls_including_finite_difference": True,
        "software": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
        "full_RBC_replay_allowed": False, "biological_fitting_allowed": False})
    fits, grouped = [], defaultdict(list)
    for scenario in config["scenarios"]:
        reference = saved_reference(scenario)
        for schedule in ("sparse", "dense"):
            train_time = training_times(config, schedule)
            target = select_saved(reference["time"], reference["states"], train_time)
            for stage, (_, plans) in STAGES.items():
                for plan in plans:
                    rows = config["observation_plans"][plan]
                    for start in range(len(config["future_recovery"]["start_vectors"])):
                        begin = time.perf_counter()
                        fit = recover(config, scenario, stage, plan, train_time, target[rows], start)
                        fit["schedule"] = schedule
                        parameters = fit["parameters"]
                        kwargs = {"updates": {k: v for k, v in parameters.items() if k != "phi0"},
                                  "phi0": parameters.get("phi0"), "time": reference["time"]}
                        strict = simulate(config, scenario, profile="strict", **kwargs)
                        ultra = simulate(config, scenario, profile="ultrastrict", **kwargs)
                        fit.update(prediction_metrics(config, scenario, parameters, ultra, reference))
                        fit.update(numerical_checks(config, strict, ultra))
                        fit["recovery_pass"] = bool(fit["optimizer_success"] and fit["numerical_pass"]
                            and fit["parameter_recovery_pass"] and fit["holdout_prediction_pass"])
                        fit["seconds"] = time.perf_counter() - begin
                        key = f"{scenario['name']}_{schedule}_{stage}_{plan}_start{start}"
                        fit["prediction_file"] = key + ".npz"
                        save_prediction(out / fit["prediction_file"], reference, strict, ultra)
                        write_json(out / (key + ".json"), fit)
                        fits.append(fit)
                        grouped[(scenario["name"], schedule, stage, plan)].append(fit)
                        print(f"{len(fits):02d}/72 {key}: recovery={fit['recovery_pass']} calls={fit['actual_objective_evaluations']}", flush=True)
    groups = [{"scenario": key[0], "schedule": key[1], "stage": key[2], "plan": key[3],
               **multistart_agreement(config, group)} for key, group in grouped.items()]
    # No unknown-Km optimization can select a unique vector from this exact family.
    controls = []
    for scenario in config["scenarios"]:
        selected = next(f for f in fits if f["scenario"] == scenario["name"] and f["stage"] == "access_pHi"
                        and f["schedule"] == "sparse" and f["plan"] == "concentrations_plus_pHi_pHe" and f["start_index"] == 0)
        params = selected["parameters"]
        for factor in config["negative_control"]["scale_factors"]:
            base = simulate(config, scenario, updates={"access_i": params["access_i"]}, phi0=params["phi0"])
            shifted = simulate(config, scenario, updates={"access_i": factor * params["access_i"],
                "km_i": factor * config["truth"]["km_i"]}, phi0=params["phi0"] + np.log10(factor), time=base["time"])
            checks = {"concentrations": close(base["states"][:2], shifted["states"][:2], config),
                      "pHe": close(base["states"][3], shifted["states"][3], config),
                      "flux": close(base["flux"], shifted["flux"], config),
                      "pHi_shift": close(shifted["states"][2] - base["states"][2], np.log10(factor), config)}
            if not all(checks.values()):
                raise ValueError("unknown-Km equivalent-family control failed")
            file = f"{scenario['name']}_equivalent_family_{factor}.npz"
            np.savez_compressed(out / file, time=base["time"], base_states=base["states"], shifted_states=shifted["states"],
                                base_flux=base["flux"], shifted_flux=shifted["flux"])
            controls.append({"scenario": scenario["name"], "scale_factor": factor, "checks": checks, "file": file,
                             "interpretation": "equivalent_family_with_unknown_Km_not_unique_recovery"})
    summary = summarize(fits, groups, controls)
    write_json(out / "multistart_groups.json", groups)
    write_json(out / "summary.json", summary)
    verify_preparation(PREPARATION)
    if any(sha(ROOT / p) != digest for p, digest in hashes.items()):
        raise ValueError("protected input changed during recovery")
    write_json(out / "manifest.json", {"output_sha256": {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()}})
    return verify(out)


def verify(out):
    design = json.loads((out / "execution_design.json").read_text())
    for name, digest in design["input_sha256"].items():
        if sha(ROOT / name) != digest:
            raise ValueError("recovery input changed: " + name)
    for name, digest in json.loads((out / "manifest.json").read_text())["output_sha256"].items():
        if sha(out / name) != digest:
            raise ValueError("recovery output changed: " + name)
    verify_preparation(PREPARATION)
    config = json.loads((PREPARATION / "preregistered_design.json").read_text())["design"]
    fits, grouped = [], defaultdict(list)
    for scenario in config["scenarios"]:
        reference = saved_reference(scenario)
        for schedule in ("sparse", "dense"):
            for stage, (_, plans) in STAGES.items():
                for plan in plans:
                    for start in range(len(config["future_recovery"]["start_vectors"])):
                        key = f"{scenario['name']}_{schedule}_{stage}_{plan}_start{start}"
                        fit = json.loads((out / (key + ".json")).read_text())
                        if (fit["training_days"] != training_times(config, schedule).tolist()
                                or not 0 < len(fit["trace"]) == fit["actual_objective_evaluations"] <= config["future_recovery"]["optimizer_budget_max_nfev"]
                                or any(t["integration_end"] != config["training_end_day"] for t in fit["trace"])):
                            raise ValueError("training separation or actual-call budget violated")
                        with np.load(out / fit["prediction_file"]) as a:
                            if not np.array_equal(a["reference_states"], reference["states"]):
                                raise ValueError("reference changed")
                            metrics = prediction_metrics(config, scenario, fit["parameters"],
                                {"time": a["time"], "states": a["ultrastrict_states"]}, reference)
                            if any(metrics[k] != fit[k] for k in metrics):
                                raise ValueError("prediction/parameter metric reconstruction failed")
                            for profile in config["solver_profiles"]:
                                x, initial = a[profile + "_states"], a[profile + "_initial"]
                                h = config["geometry"]["hematocrit"]
                                beta_e = fit["parameters"].get("beta_e", config["truth"]["beta_e"])
                                expected_phi = fit["parameters"].get("phi0", scenario["initial"][2])
                                if (initial[2] != expected_phi or min(x[:2].min(), a[profile + "_accepted_states"][:2].min()) < 0
                                        or not close(h*x[0]+(1-h)*x[1], h*initial[0]+(1-h)*initial[1], config)
                                        or not close(-h*config["truth"]["beta_i"]*(x[2]-initial[2])
                                                     -(1-h)*beta_e*(x[3]-initial[3]), 0, config)
                                        or a[profile + "_accepted_time"][-1] != config["horizon_day"][-1]):
                                    raise ValueError("stored prediction invariants failed")
                        fits.append(fit)
                        grouped[(scenario["name"], schedule, stage, plan)].append(fit)
    groups = [{"scenario": key[0], "schedule": key[1], "stage": key[2], "plan": key[3],
               **multistart_agreement(config, group)} for key, group in grouped.items()]
    if groups != json.loads((out / "multistart_groups.json").read_text()):
        raise ValueError("multistart reconstruction failed")
    summary = json.loads((out / "summary.json").read_text())
    for control in summary["equivalent_family_controls"]:
        with np.load(out / control["file"]) as a:
            if (not close(a["base_states"][:2], a["shifted_states"][:2], config)
                    or not close(a["base_states"][3], a["shifted_states"][3], config)
                    or not close(a["base_flux"], a["shifted_flux"], config)
                    or not close(a["shifted_states"][2]-a["base_states"][2], np.log10(control["scale_factor"]), config)):
                raise ValueError("stored equivalent-family check failed")
    if summary != summarize(fits, groups, summary["equivalent_family_controls"]):
        raise ValueError("summary reconstruction failed")
    return {"verified": True, "fits": len(fits), "groups": len(groups), "actual_objective_integrations": summary["actual_objective_integrations"],
            "recovery_pass": sum(f["recovery_pass"] for f in fits), "numerics_pass": sum(f["numerical_pass"] for f in fits),
            "holdout_pass": sum(f["holdout_prediction_pass"] for f in fits), "biological_ODE_replays": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if bool(args.out) == bool(args.verify):
        parser.error("choose exactly one of --out or --verify")
    print(json.dumps(run(args.out.resolve()) if args.out else verify(args.verify.resolve()), indent=2))
