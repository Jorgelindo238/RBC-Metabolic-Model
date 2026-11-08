"""Training-only curve reconstruction and quadrature for the synthetic FLA screen."""

from __future__ import annotations

import numpy as np
from scipy.interpolate import PchipInterpolator, make_smoothing_spline

from equadiff_brodbar import (
    BRODBAR_METABOLITE_MAP, MIN_CONCENTRATION, _compute_veglc_flux, _compute_velac_flux,
)
from fla_synthetic_recovery import OBSERVED_POOLS, REACTIONS, SIGNS, validate_observations
from reaction_positivity import limit_signed_fluxes, rbc_reaction_matrix


def validate_design(config):
    if config.get("schema_version") != 1 or config.get("purpose") != "synthetic_teacher_resolution_and_smoothing_diagnostic":
        raise ValueError("only the isolated synthetic resolution screen is allowed")
    for flag in ("biological_calibration_allowed", "global_model_promotion_allowed", "change_scientific_readiness_contract"):
        if config.get(flag) is not False:
            raise ValueError("biological calibration and promotion must remain disabled")
    for key, minimum in (("uniform_grid_counts", 3), ("aligned_quadrature_orders", 2), ("integrated_quadrature_orders", 2)):
        values = config[key]
        if not values or any(type(v) is not int or v < minimum for v in values) or values != sorted(set(values)):
            raise ValueError("grids and orders must be increasing unique integers")
    if config["aligned_quadrature_orders"] != [4, 8] or config["integrated_quadrature_orders"] != [8, 16] or 401 not in config["uniform_grid_counts"]:
        raise ValueError("the legacy and convergence controls must be retained")
    seeds = config["noise_seeds"]
    replay_seeds = config["replay_noise_seeds"]
    if (len(seeds) < 5 or len(set(seeds)) != len(seeds) or any(type(v) is not int or v < 0 for v in seeds)
            or not replay_seeds or len(set(replay_seeds)) != len(replay_seeds) or not set(replay_seeds).issubset(seeds)):
        raise ValueError("paired noise seeds and fixed replay subset must be explicit")
    if config["replay_methods"] != ["legacy_raw401", "raw_aligned8", "smooth_aligned8", "raw_integrated"]:
        raise ValueError("replays cannot be selected using fitted performance")
    if config["include_clean_control"] is not True or config["replay_clean_control"] is not True:
        raise ValueError("clean bias control is required")
    if config["smoothing"] != "log_cubic_smoothing_spline_GCV_training_only_initial_anchor":
        raise ValueError("smoothing policy must be preregistered")
    if config["pointwise_weighting"] != "time_quadrature_except_labeled_legacy_401":
        raise ValueError("pointwise temporal weighting must be explicit")
    if (config.get("time_partition_policy") != "merge_machine_precision_duplicates_before_noise"
            or config.get("time_merge_absolute_tolerance_day") != 1e-10):
        raise ValueError("machine-precision time partition repair must be explicit")
    for key in ("noise_coefficient_of_variation", "capacity_quadrature_relative_tolerance", "kernel_parity_absolute_tolerance"):
        value = config[key]
        if isinstance(value, bool) or not np.isfinite(value) or not 0 < value < 1:
            raise ValueError("invalid finite numerical/noise design")
    return config


def method_names(config):
    names = [f"{mode}_uniform{count}" for mode in ("raw", "smooth") for count in config["uniform_grid_counts"]]
    names += [f"{mode}_aligned{order}" for mode in ("raw", "smooth") for order in config["aligned_quadrature_orders"]]
    return names + ["raw_integrated", "smoothed_inputs_integrated", "legacy_raw401"]


def canonical_partition(time, values, *, tolerance=1e-10):
    """Merge roundoff-only duplicates in clean synthetic truth before drawing noise."""
    time, values = validate_observations(time, values, training_end=22.)
    groups = []
    for index, day in enumerate(time):
        if not groups or day-time[groups[-1][0]] > tolerance:
            groups.append([index])
        else:
            groups[-1].append(index)
    for group in groups:
        if len(group) > 1 and not np.allclose(values[:, group], values[:, group[:1]], rtol=1e-9, atol=1e-12):
            raise ValueError("duplicate clean timestamps have inconsistent concentrations")
    repaired_time = np.asarray([time[group[0]] for group in groups])
    repaired_values = np.column_stack([np.mean(values[:, group], axis=1) for group in groups])
    return repaired_time, repaired_values, {"original_count": len(time), "canonical_count": len(groups),
        "tolerance_day": tolerance, "source_index_groups": groups, "before_noise": True,
        "clean_value_aggregation": "arithmetic_mean", "representative_time": "first_source_time",
        "parent_noise_draws_reused_bit_for_bit": False}


class TrainingCurves:
    def __init__(self, time, values, *, training_end, mode, noise_cv):
        self.time, self.observations = validate_observations(time, values, training_end=training_end)
        if len(self.time) < 5 or mode not in {"raw", "smooth"} or not np.isfinite(noise_cv) or not 0 <= noise_cv <= 1:
            raise ValueError("invalid training-only curve design")
        self.mode = mode
        self.curves, self.anchor_shifts = [], []
        if mode == "smooth" and np.any(self.observations <= 0):
            raise ValueError("log smoothing requires positive data; do not insert floors")
        for row in self.observations:
            if mode == "raw":
                curve = PchipInterpolator(self.time, row, extrapolate=False)
                shift = 0.
            else:
                log_values = np.log(row)
                # The log-normal mean correction is known by synthetic design, not estimated from truth.
                log_values[1:] += .5 * np.log1p(noise_cv**2)
                curve = make_smoothing_spline(self.time, log_values, lam=None)
                shift = float(np.log(row[0]) - curve(self.time[0]))
            self.curves.append(curve)
            self.anchor_shifts.append(shift)

    def evaluate(self, query):
        query = np.asarray(query, dtype=float)
        if (query.ndim != 1 or not np.all(np.isfinite(query)) or np.any(query < self.time[0])
                or np.any(query > self.time[-1])):
            raise ValueError("no holdout extrapolation in training reconstruction")
        values, derivatives = [], []
        for curve, shift in zip(self.curves, self.anchor_shifts):
            local = curve(query)
            derivative = curve.derivative()(query)
            if self.mode == "smooth":
                local = np.exp(local + shift)
                derivative *= local
            values.append(local)
            derivatives.append(derivative)
        values, derivatives = np.asarray(values), np.asarray(derivatives)
        if not np.all(np.isfinite(np.r_[values.ravel(), derivatives.ravel()])) or np.any(values < 0):
            raise ValueError("nonfinite or negative reconstructed curves; no clipping")
        return values, derivatives

    def proxy(self, query, initial):
        initial = np.asarray(initial, dtype=float)
        if initial.shape != (114,) or not np.all(np.isfinite(initial)) or np.any(initial[:113] < 0):
            raise ValueError("invalid frozen initial state")
        values, derivatives = self.evaluate(query)
        states = np.repeat(initial[:, None], len(query), axis=1)
        for pool, row in zip(OBSERVED_POOLS, values):
            states[BRODBAR_METABOLITE_MAP[pool]] = row
        return states, SIGNS[:, None] * derivatives[:2]

    def receipt(self):
        receipt = {"mode": self.mode, "training_interval": [float(self.time[0]), float(self.time[-1])],
                   "smoothing_selection": "GCV_training_only" if self.mode == "smooth" else "none",
                   "log_anchor_shifts": self.anchor_shifts, "initial_anchor_is_postfit_log_shift": self.mode == "smooth",
                   "initial_anchor_is_exact_constrained_spline_optimum": False,
                   "coefficient_receipts": []}
        for curve in self.curves:
            if self.mode == "smooth":
                receipt["coefficient_receipts"].append({"knots": curve.t.tolist(), "coefficients": curve.c.tolist(), "degree": curve.k})
            else:
                receipt["coefficient_receipts"].append({"breaks": curve.x.tolist(), "coefficients": curve.c.tolist()})
        return receipt


def fast_transport_basis(time, states, params, ode):
    """Use production rate helpers and signed limiter, not a reimplemented rate law."""
    time, states = np.asarray(time, dtype=float), np.asarray(states, dtype=float)
    if time.ndim != 1 or states.shape != (114, len(time)) or not np.all(np.isfinite(np.r_[time, states.ravel()])):
        raise ValueError("finite aligned state/rate inputs are required")
    if ode.get("positivity_policy") != "reaction_consistent" or ode.get("curve_fit_strength") != 0:
        raise ValueError("only unforced reaction-consistent transport is supported")
    for key in ("km_EGLC", "km_GLC_transport", "km_LAC"):
        if key not in params or not np.isfinite(params[key]) or params[key] <= 0:
            raise ValueError("explicit positive frozen transport affinities are required")
    if any(str(params.get("kinetic_family_"+r, "")).startswith("teacher") for r in REACTIONS):
        raise ValueError("teacher forcing is forbidden")
    threshold = ode["reaction_availability_threshold"]
    _, reactions, matrix = rbc_reaction_matrix(params.get("sam_adenylate_stoichiometry", "biochemical_transfer"))
    columns = matrix[:, [reactions.index(r) for r in REACTIONS]]
    native, effective, factors = [], [], []
    for day, state in zip(time, states.T):
        floored = np.maximum(state, MIN_CONCENTRATION)
        rates = np.asarray([_compute_veglc_flux(float(day), floored, params, 1., params["km_EGLC"], params["km_GLC_transport"]),
                            _compute_velac_flux(float(day), floored, params, 1., params["km_LAC"])])
        limited, availability = limit_signed_fluxes(state[:113], rates, columns, threshold=threshold)
        native.append(rates)
        effective.append(limited)
        factors.append(availability)
    return {"basis": np.asarray(effective).T, "native": np.asarray(native).T, "factors": np.asarray(factors).T}


def time_grid(observation_time, *, count=None, order=None):
    time = np.asarray(observation_time, dtype=float)
    if time.ndim != 1 or len(time) < 2 or not np.all(np.isfinite(time)) or np.any(np.diff(time) <= 0):
        raise ValueError("invalid observation partition")
    if (count is None) == (order is None):
        raise ValueError("choose exactly one uniform or interval-aligned grid")
    if count is not None:
        if type(count) is not int or count < 3:
            raise ValueError("uniform grid count must be >= 3")
        query = np.linspace(time[0], time[-1], count)
        weights = np.full(count, (time[-1]-time[0])/(count-1))
        weights[[0, -1]] *= .5
        interval = np.minimum(np.searchsorted(time, query, side="right")-1, len(time)-2)
    else:
        if type(order) is not int or order < 2:
            raise ValueError("aligned quadrature order must be >= 2")
        nodes, local_weights = np.polynomial.legendre.leggauss(order)
        half = np.diff(time)/2
        query = (((time[:-1]+time[1:])/2)[:, None]+half[:, None]*nodes).ravel()
        weights = (half[:, None]*local_weights).ravel()
        interval = np.repeat(np.arange(len(time)-1), order)
    return query, weights, interval


def weighted_problem(basis, targets, weights):
    basis, targets, weights = (np.asarray(value, dtype=float) for value in (basis, targets, weights))
    if (basis.ndim != 2 or basis.shape != targets.shape or basis.shape[0] != 2 or basis.shape[1] == 0 or weights.shape != (basis.shape[1],)
            or not np.all(np.isfinite(np.r_[basis.ravel(), targets.ravel(), weights])) or np.any(weights <= 0)):
        raise ValueError("finite positive temporal weights must align with the residuals")
    normalized = weights / np.mean(weights)
    return basis * np.sqrt(normalized)[None, :], targets * np.sqrt(normalized)[None, :]


def integrated_problem(curves, initial, params, ode, *, order):
    query, weights, intervals = time_grid(curves.time, order=order)
    states, _ = curves.proxy(query, initial)
    basis = fast_transport_basis(query, states, params, ode)["basis"]
    integral = np.column_stack([basis[:, intervals == i] @ weights[intervals == i] for i in range(len(curves.time)-1)])
    # Primary interval teachers always retain actual signed observation increments, even with smoothed inputs.
    targets = SIGNS[:, None] * np.diff(curves.observations[:2], axis=1)
    return integral, targets
