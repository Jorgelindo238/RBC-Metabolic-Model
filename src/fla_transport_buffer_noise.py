"""Frozen noise panels and descriptive diagnostics for the isolated MCT toy."""

from collections import defaultdict
import itertools

import numpy as np

from fla_transport_buffer_recovery import scales, select_saved, training_times


def validate_noise(config, design):
    future = config["future_recovery"]
    if (design.get("schema_version") != 1
            or design.get("purpose") != "preregistered_noisy_conditional_toy_recovery_not_biological_calibration"
            or design["noise_seeds"] != future["noise_seeds"]
            or design["concentration_CV"] != future["synthetic_concentration_CV"]
            or design["pH_SD"] != future["synthetic_pH_SD"]):
        raise ValueError("noise amplitudes and seeds must match the frozen preparation")
    for key in ("biological_fitting_allowed", "full_RBC_replay_allowed", "production_defaults_changed", "source_data_changed"):
        if design.get(key) is not False:
            raise ValueError("noisy toy cannot enable biological changes")
    if (design["concentration_noise"] != "independent_mean_preserving_lognormal"
            or design["pH_noise"] != "independent_additive_gaussian"
            or design["initial_concentrations"] != "known_exact_not_noised_not_estimated"
            or design["initial_pH_observations"] != "noised_including_time_zero_when_pH_is_observed"):
        raise ValueError("undeclared observation model")
    return design


def panel_times(config):
    return np.unique(np.r_[training_times(config, "sparse"), training_times(config, "dense"),
                           [t for t in config["sparse_days"] if t > config["training_end_day"]]])


def generate_panel(config, design, scenario_index, seed, reference):
    validate_noise(config, design)
    if (type(scenario_index) is not int or not 0 <= scenario_index < len(config["scenarios"])
            or type(seed) is not int or seed not in design["noise_seeds"]):
        raise ValueError("frozen scenario index and seed required")
    time = panel_times(config)
    clean = select_saved(reference["time"], reference["states"], time)[:4]
    generator = np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed, scenario_index])))
    draws = generator.normal(size=clean.shape)
    noisy = clean.copy()
    log_variance = np.log1p(design["concentration_CV"] ** 2)
    noisy[:2, 1:] *= np.exp(np.sqrt(log_variance) * draws[:2, 1:] - .5 * log_variance)
    noisy[2:] += design["pH_SD"] * draws[2:]
    if (not np.all(np.isfinite(noisy)) or np.any(noisy[:2] < 0)
            or np.any(noisy[2:] <= 0) or np.any(noisy[2:] >= 14)):
        raise ValueError("invalid noisy panel; no clipping or redraw")
    return {"time": time, "clean_states": clean, "observed_states": noisy, "normal_draws": draws}


def panel_values(panel, query):
    # The saved-query helper expects five states; the extent is never an observation.
    scaffold = np.vstack([panel["observed_states"], np.zeros(len(panel["time"]))])
    return select_saved(panel["time"], scaffold, query)[:4]


def observed_metrics(config, plan, panel, training_time, result):
    rows = config["observation_plans"][plan]
    metrics = {}
    for label, time in (("training", training_time),
                        ("holdout", np.array([t for t in config["sparse_days"] if t > config["training_end_day"]]))):
        prediction = select_saved(result["time"], result["states"], time)[rows]
        target = panel_values(panel, time)[rows]
        metrics[label + "_noisy_observed_plan_scaled_RMSE"] = float(
            np.sqrt(np.mean(((prediction - target) / scales(config, rows)[:, None]) ** 2)))
    return metrics


def bounds_hit(config, design, parameters):
    bounds = config["future_recovery"]["parameter_bounds"]
    hits = []
    for name, value in parameters.items():
        lo, hi = bounds[name]
        rounding = 1e-12 * max(1.0, abs(lo), abs(hi))
        if not np.isfinite(value) or value < lo-rounding or value > hi+rounding:
            raise ValueError("fitted parameter outside declared bounds")
        if min(value-lo, hi-value)/(hi-lo) <= design["bound_proximity_fraction"]:
            hits.append(name)
    return hits


def group_diagnostics(config, fits):
    if len(fits) != 3 or sorted(f["start_index"] for f in fits) != [0, 1, 2]:
        raise ValueError("three complete unique starts required")
    keys = ("scenario", "noise_seed", "schedule", "stage", "plan")
    if any(any(f[k] != fits[0][k] for k in keys) for f in fits):
        raise ValueError("one shared noisy panel and scope required")
    spreads = {}
    for name in fits[0]["parameters"]:
        values = [f["parameters"][name] for f in fits]
        spreads[name] = max(abs(a-b) if name == "phi0" else abs(a-b)/max(abs(a), abs(b))
                            for a, b in itertools.combinations(values, 2))
    future = config["future_recovery"]
    return {**{k: fits[0][k] for k in keys}, "parameter_spreads": spreads,
            "multistart_agreement_pass": all(v <= future["clean_phi0_absolute_error_limit" if n == "phi0"
                                                                       else "clean_parameter_relative_error_limit"] for n, v in spreads.items()),
            "median_parameters_over_starts": {n: float(np.median([f["parameters"][n] for f in fits])) for n in spreads},
            "all_starts_parameter_pass": all(f["parameter_recovery_pass"] for f in fits),
            "all_starts_holdout_pass": all(f["holdout_prediction_pass"] for f in fits),
            "all_starts_recovery_pass": all(f["recovery_pass"] for f in fits),
            "any_optimizer_failure": any(not f["optimizer_success"] for f in fits),
            "any_bound_hit": any(f["bound_hits"] for f in fits)}


def summarize_noisy(config, fits, groups, controls):
    scopes = defaultdict(list)
    for fit in fits:
        scopes[(fit["stage"], fit["schedule"], fit["plan"])].append(fit)
    counts = []
    for (stage, schedule, plan), members in scopes.items():
        matched = [g for g in groups if (g["stage"], g["schedule"], g["plan"]) == (stage, schedule, plan)]
        counts.append({"stage": stage, "schedule": schedule, "plan": plan, "fits": len(members), "groups": len(matched),
            **{name: sum(bool(f[name]) for f in members) for name in ("optimizer_success", "numerical_pass",
                "parameter_recovery_pass", "holdout_prediction_pass", "recovery_pass")},
            "all_starts_parameter_groups": sum(g["all_starts_parameter_pass"] for g in matched),
            "all_starts_holdout_groups": sum(g["all_starts_holdout_pass"] for g in matched),
            "multistart_agreement_groups": sum(g["multistart_agreement_pass"] for g in matched),
            "bound_hit_fits": sum(bool(f["bound_hits"]) for f in members),
            "max_latent_holdout_scaled_RMSE": max(f["holdout_scaled_RMSE_all_states"] for f in members)})
    dispersions = []
    contexts = defaultdict(list)
    for group in groups:
        contexts[(group["scenario"], group["stage"], group["schedule"], group["plan"])].append(group)
    for (scenario, stage, schedule, plan), members in contexts.items():
        if sorted(g["noise_seed"] for g in members) != sorted(config["future_recovery"]["noise_seeds"]):
            raise ValueError("all preregistered seeds required")
        estimates = {}
        for name in members[0]["median_parameters_over_starts"]:
            values = [g["median_parameters_over_starts"][name] for g in members]
            estimates[name] = {"min": min(values), "median": float(np.median(values)), "max": max(values)}
        dispersions.append({"scenario": scenario, "stage": stage, "schedule": schedule, "plan": plan,
                            "seed_count": len(members), "median_start_estimates_across_seeds": estimates})
    return {"fits_executed": len(fits), "independent_noise_panels": len({(f["scenario"], f["noise_seed"]) for f in fits}),
        "multistart_groups": len(groups), "multistart_agreement_groups": sum(g["multistart_agreement_pass"] for g in groups),
        "actual_objective_integrations": sum(f["actual_objective_evaluations"] for f in fits),
        "max_actual_objective_evaluations": max(f["actual_objective_evaluations"] for f in fits),
        "full_horizon_validation_integrations": 2*len(fits), "equivalent_family_integrations": 2*len(controls),
        **{name: sum(bool(f[name]) for f in fits) for name in ("optimizer_success", "numerical_pass", "parameter_recovery_pass",
                                                            "holdout_prediction_pass", "recovery_pass")},
        "budget_exhausted_fits": sum(f["optimizer_message"] == "actual objective evaluations exhausted" for f in fits),
        "bound_hit_fits": sum(bool(f["bound_hits"]) for f in fits), "scopes": counts,
        "seed_dispersion": dispersions, "equivalent_family_controls": controls,
        "confidence_intervals_established": False, "biological_ODE_replays": 0, "biological_parameters_promoted": False,
        "interpretation": "descriptive_three_seed_robustness_of_conditional_toy_not_independent_216_datasets"}
