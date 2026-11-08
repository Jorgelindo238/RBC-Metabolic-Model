"""Conditional transport recovery using the real FLA teacher and executed ODE rates."""

from __future__ import annotations

import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.optimize import least_squares

from equadiff_brodbar import BRODBAR_METABOLITE_MAP, equadiff_brodbar
from extracellular_teacher_flux import build_extracellular_teacher_flux_dataset

PARAMETERS = ("vmax_VEGLC", "vmax_VELAC")
REACTIONS = ("VEGLC", "VELAC")
OBSERVED_POOLS = ("EGLC", "ELAC", "GLC", "LAC")
SIGNS = np.array([-1., 1.])


def validate_config(config):
    if config.get("schema_version") != 1 or config.get("purpose") != "synthetic_software_benchmark_not_biological_calibration":
        raise ValueError("only a separate synthetic benchmark is authorized")
    for key in ("biological_calibration_allowed", "global_model_promotion_allowed", "change_scientific_readiness_contract"):
        if config.get(key) is not False:
            raise ValueError("synthetic recovery cannot enable biological calibration or promotion")
    if tuple(config.get("parameters", ())) != PARAMETERS:
        raise ValueError("this benchmark only learns the two transport capacities")
    start, end = np.asarray(config["horizon_day"], dtype=float)
    split = float(config["training_end_day"])
    if not np.all(np.isfinite([start, split, end])) or not start < split < end:
        raise ValueError("training and holdout must have distinct finite horizons")
    bounds = np.asarray(config["search_multiplier_bounds"], dtype=float)
    truth = np.asarray(config["truth_multipliers"], dtype=float)
    starts = np.asarray(config["start_multipliers"], dtype=float)
    if (bounds.shape != (2,) or truth.shape != (2,) or starts.ndim != 2 or starts.shape[1] != 2
            or not len(starts) or not np.all(np.isfinite(np.r_[bounds, truth, starts.ravel()]))
            or not 0 < bounds[0] < bounds[1] or np.any(truth <= bounds[0]) or np.any(truth >= bounds[1])
            or np.any(starts <= bounds[0]) or np.any(starts >= bounds[1])):
        raise ValueError("positive finite truth and starts must lie inside search bounds")
    for key in ("dense_observation_count", "dense_early_observation_count", "teacher_point_count", "evaluation_point_count"):
        if type(config[key]) is not int or config[key] < 3:
            raise ValueError("point counts must be integers >= 3")
    cv = config["noise_coefficient_of_variation"]
    if isinstance(cv, bool) or not np.isfinite(cv) or not 0 < cv <= 1:
        raise ValueError("noise design must be positive and finite, with CV <= 1")
    if config.get("noise_model") != "independent_mean_preserving_lognormal_known_IC":
        raise ValueError("synthetic noise model must be explicit")
    if (not config["noise_seeds"] or any(type(seed) is not int or seed < 0 for seed in config["noise_seeds"])
            or len(set(config["noise_seeds"])) != len(config["noise_seeds"])):
        raise ValueError("noise seeds must be unique nonnegative integers")
    orders = config["quadrature_orders"]
    if len(orders) != 2 or any(type(order) is not int or order < 2 for order in orders) or orders[0] >= orders[1]:
        raise ValueError("two increasing quadrature orders are required")
    for value in config["synthetic_recovery_checks"].values():
        if isinstance(value, bool) or not np.isfinite(value) or value <= 0:
            raise ValueError("synthetic checks must be finite and positive")
    return config


def validate_observations(time, values, *, training_end):
    time = np.asarray(time, dtype=float)
    values = np.asarray(values, dtype=float)
    if (time.ndim != 1 or len(time) < 2 or values.shape != (4, len(time))
            or not np.all(np.isfinite(time)) or not np.all(np.isfinite(values))
            or np.any(np.diff(time) <= 0) or np.any(values < 0) or time[-1] > training_end):
        raise ValueError("nonnegative finite observations must align and remain inside training")
    return time, values


def add_synthetic_noise(values, *, cv, seed):
    values = np.asarray(values, dtype=float)
    if (values.ndim != 2 or values.shape[0] != 4 or values.shape[1] < 2
            or not np.all(np.isfinite(values)) or np.any(values < 0)
            or not np.isfinite(cv) or not 0 < cv <= 1
            or type(seed) is not int or seed < 0):
        raise ValueError("invalid synthetic noise design")
    sigma = cv * values
    sigma[:, 0] = 0.
    log_variance = np.log1p(cv**2)
    noisy = values.copy()
    log_noise = np.random.default_rng(seed).normal(size=(4, values.shape[1] - 1)) * np.sqrt(log_variance)
    noisy[:, 1:] *= np.exp(log_noise - .5 * log_variance)
    if not np.all(np.isfinite(noisy)) or np.any(noisy[values > 0] <= 0):
        raise ValueError("invalid noisy data; do not silently clip or resample")
    return noisy, sigma


def proxy_states(time, values, query, initial_state, *, training_end):
    time, values = validate_observations(time, values, training_end=training_end)
    query = np.asarray(query, dtype=float)
    initial_state = np.asarray(initial_state, dtype=float)
    if (query.ndim != 1 or not np.all(np.isfinite(query)) or np.any(query < time[0]) or np.any(query > time[-1])
            or initial_state.shape != (114,) or not np.all(np.isfinite(initial_state)) or np.any(initial_state[:113] < 0)):
        raise ValueError("proxy interpolation cannot extrapolate or hide invalid initialization")
    # Only these four pools enter the two transport rates; all other entries are inert scaffolding.
    states = np.repeat(initial_state[:, None], len(query), axis=1)
    for pool, row in zip(OBSERVED_POOLS, values):
        states[BRODBAR_METABOLITE_MAP[pool]] = PchipInterpolator(time, row, extrapolate=False)(query)
    return states


def executed_transport(time, states, params, ode_options):
    """Replay the kernel, including native concentration floors and signed availability."""
    time, states = np.asarray(time, dtype=float), np.asarray(states, dtype=float)
    if time.ndim != 1 or states.shape != (114, len(time)) or not np.all(np.isfinite(states)) or not np.all(np.isfinite(time)):
        raise ValueError("transport replay inputs must be finite and aligned")
    if ode_options.get("positivity_policy") != "reaction_consistent" or ode_options.get("curve_fit_strength") != 0:
        raise ValueError("synthetic benchmark requires unforced reaction-consistent execution")
    if any(str(params.get("kinetic_family_" + r, "")).startswith("teacher") for r in REACTIONS):
        raise ValueError("teacher forcing is forbidden")
    native, effective, factors, closure = [], [], [], []
    for day, state in zip(time, states.T):
        audit = {}
        derivative = equadiff_brodbar(float(day), state.copy(), custom_params=dict(params), numerical_audit=audit, **ode_options)
        native.append([audit["raw_fluxes"][r] for r in REACTIONS])
        effective.append([audit["effective_fluxes"][r] for r in REACTIONS])
        factors.append([audit["availability_factors"][r] for r in REACTIONS])
        closure.append(float(np.max(np.abs(derivative[:113] - audit["effective_derivative"]))))
    result = {"native": np.asarray(native).T, "effective": np.asarray(effective).T,
              "factors": np.asarray(factors).T, "closure": np.asarray(closure)}
    if any(not np.all(np.isfinite(value)) for value in result.values()):
        raise ValueError("nonfinite executed transport replay")
    return result


def check_linear_capacity_domain(params, base, multiplier_bounds):
    """Reject a cap-active domain: a cached unit-capacity basis would no longer be exact."""
    base = np.asarray(base, dtype=float)
    bounds = np.asarray(multiplier_bounds, dtype=float)
    if base.shape != (2,) or bounds.shape != (2,) or not np.all(np.isfinite(np.r_[base, bounds])) or np.any(base <= 0) or not 0 < bounds[0] < bounds[1]:
        raise ValueError("invalid capacity domain")
    family = params.get("kinetic_family_VEGLC", "mm_bidirectional")
    if family == "transport_depletion_gate_import_feedback":
        feedback = float(params.get("transport_gate_feedback_strength_VEGLC", 0.))
        if not np.isfinite(feedback) or feedback < 0:
            raise ValueError("feedback must not amplify import before the cap")
        cap = float(params.get("transport_gate_import_cap_VEGLC", 1e9))
        if not np.isfinite(cap) or cap <= max(1., base[0] * bounds[1]):
            raise ValueError("import cap may be active; cannot use a linear capacity basis")
    if family not in {"mm_bidirectional", "hybrid_asymmetric_transport", "transport_depletion_gate", "transport_depletion_gate_import_feedback"}:
        raise ValueError("unsupported glucose transport family")
    if params.get("kinetic_family_VELAC", "mm_efflux") not in {"mm_efflux", "hybrid_reversible_transport"}:
        raise ValueError("unsupported lactate transport family")


def unit_capacity_basis(time, states, params, ode_options):
    unit = dict(params)
    unit.update(dict.fromkeys(PARAMETERS, 1.))
    return executed_transport(time, states, unit, ode_options)["effective"]


def reconstruction(time, values, initial_state, params, ode_options, *, training_end, point_count, order):
    time, values = validate_observations(time, values, training_end=training_end)
    teacher = build_extracellular_teacher_flux_dataset(
        {pool: row for pool, row in zip(OBSERVED_POOLS, values)}, time,
        metabolite_names=("EGLC", "ELAC"), dense_points=point_count,
        dataset_label="synthetic_transport_recovery_not_experimental", data_path="synthetic_observations",
    )
    query = np.asarray(teacher["dense_timepoints"])
    states = proxy_states(time, values, query, initial_state, training_end=training_end)
    basis = unit_capacity_basis(query, states, params, ode_options)
    targets = np.asarray([teacher["reaction_flux_curves"][r]["dense_values"] for r in REACTIONS])
    nodes, weights = np.polynomial.legendre.leggauss(order)
    widths, mid = np.diff(time) / 2, (time[:-1] + time[1:]) / 2
    qtime = (mid[:, None] + widths[:, None] * nodes).ravel()
    qstates = proxy_states(time, values, qtime, initial_state, training_end=training_end)
    qbasis = unit_capacity_basis(qtime, qstates, params, ode_options).reshape(2, len(widths), order)
    integrated_basis = np.sum(qbasis * weights[None, None, :] * widths[None, :, None], axis=2)
    integral_targets = SIGNS[:, None] * np.diff(values[:2], axis=1)
    return {"teacher": teacher, "time": query, "basis": basis, "targets": targets,
            "integrated_basis": integrated_basis, "integral_targets": integral_targets}


def fit_capacities(basis, targets, base, bounds, starts):
    """Deterministic positive log-capacity least squares; no hidden truth-dependent scale."""
    basis, targets, base = (np.asarray(value, dtype=float) for value in (basis, targets, base))
    bounds, starts = np.asarray(bounds, dtype=float), np.asarray(starts, dtype=float)
    if (basis.ndim != 2 or basis.shape != targets.shape or basis.shape[0] != 2 or not basis.shape[1]
            or base.shape != (2,) or not np.all(np.isfinite(np.r_[basis.ravel(), targets.ravel(), base]))
            or np.any(base <= 0) or bounds.shape != (2,) or not np.all(np.isfinite(bounds))
            or not 0 < bounds[0] < bounds[1] or starts.ndim != 2 or starts.shape[1] != 2
            or not len(starts) or not np.all(np.isfinite(starts)) or np.any(starts <= bounds[0]) or np.any(starts >= bounds[1])):
        raise ValueError("invalid finite aligned recovery problem")
    scale = np.maximum(np.sqrt(np.mean(targets**2, axis=1)), 1e-6)

    def residual(log_multiplier):
        return ((base[:, None] * np.exp(log_multiplier[:, None]) * basis - targets) / scale[:, None]).ravel()

    fits = []
    for start in starts:
        fit = least_squares(residual, np.log(start), bounds=np.log(bounds), xtol=1e-12, ftol=1e-12,
                            gtol=1e-12, max_nfev=200)
        if not fit.success or not np.all(np.isfinite(fit.x)):
            raise ValueError("synthetic recovery optimizer failed")
        fits.append({"start_multipliers": start.tolist(), "capacities": (base * np.exp(fit.x)).tolist(),
                     "loss": float(np.mean(fit.fun**2)), "nfev": int(fit.nfev)})
    best = min(fits, key=lambda result: result["loss"])
    fitted = np.asarray(best["capacities"])
    design = np.zeros((2 * basis.shape[1], 2))
    for i in range(2):
        design[i*basis.shape[1]:(i+1)*basis.shape[1], i] = fitted[i] * basis[i] / scale[i]
    singular = np.linalg.svd(design, compute_uv=False)
    rank = int(np.count_nonzero(singular > max(float(singular[0]) * 1e-10, 1e-12)))
    return {"capacities": best["capacities"], "loss": best["loss"], "starts": fits,
            "multistart_max_capacity_spread": float(np.max(np.ptp([fit["capacities"] for fit in fits], axis=0))),
            "conditional_log_jacobian_rank": rank, "conditional_log_jacobian_singular_values": singular.tolist(),
            "at_bound": [bool(np.isclose(value, bound, rtol=1e-5, atol=0))
                         for value in fitted / base for bound in bounds],
            "global_identifiability_established": False}


def excursion_metrics(predicted, truth, *, floor=0.001):
    predicted, truth = np.asarray(predicted, dtype=float), np.asarray(truth, dtype=float)
    if predicted.shape != truth.shape or truth.ndim != 2 or truth.shape[1] < 2 or not np.all(np.isfinite(np.r_[predicted.ravel(), truth.ravel()])):
        raise ValueError("finite trajectories must align")
    if not np.isfinite(floor) or floor <= 0:
        raise ValueError("metric scale floor must be positive")
    return np.sqrt(np.mean((predicted - truth)**2, axis=1)) / np.maximum(np.ptp(truth, axis=1), floor)
