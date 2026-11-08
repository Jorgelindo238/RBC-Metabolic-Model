"""Closed MCT/buffer toy for recovery design, never the biological RBC kernel."""

import copy
import math

import numpy as np
from scipy.integrate import solve_ivp

from fla_transport_access_ph import buffered_rates, finite
from rbc_distinct_volume_transport import mct_export

PARAMETERS = ("conductance", "access_i", "phi0", "beta_e")


def validate_config(config):
    if config.get("schema_version") != 1 or config.get("purpose") != "prepare_synthetic_carrier_buffer_recovery_not_biological_fitting":
        raise ValueError("isolated synthetic preparation required")
    for key in ("biological_fitting_allowed", "full_RBC_replay_allowed", "production_defaults_changed", "measured_initial_states_changed"):
        if config.get(key) is not False:
            raise ValueError("synthetic preparation cannot modify biological settings")
    if config["future_recovery"]["optimizer_executed_in_preparation"] is not False:
        raise ValueError("preparation does not execute recovery optimization")
    if tuple(config["sensitivity_parameters"]) != PARAMETERS or config["geometry"]["constant"] is not True:
        raise ValueError("explicit fixed geometry and parameter scope required")
    h = finite(config["geometry"]["hematocrit"], positive=True)
    if h >= 1:
        raise ValueError("nonzero external phase required")
    truth = config["truth"]
    for key in ("conductance", "access_i", "access_e", "km_i", "km_e", "beta_i", "beta_e", "ph_reference"):
        finite(truth[key], positive=True)
    for key in ("dense_training_count", "evaluation_count"):
        if type(config[key]) is not int or config[key] < 3:
            raise ValueError("point count must be an integer >=3")
    start, end = map(finite, config["horizon_day"])
    split = finite(config["training_end_day"])
    times = np.asarray(config["sparse_days"], dtype=float)
    if (not start < split < end or not np.all(np.isfinite(times)) or np.any(np.diff(times) <= 0)
            or times[0] != start or times[-1] != end or not np.any(times > split)):
        raise ValueError("explicit ordered training/holdout design required")
    for scenario in config["scenarios"]:
        initial = np.asarray(scenario["initial"], dtype=float)
        if (initial.shape != (5,) or not np.all(np.isfinite(initial)) or np.any(initial[:2] < 0)
                or np.any(initial[2:4] < 0) or np.any(initial[2:4] > 14) or initial[4] != 0):
            raise ValueError("five finite synthetic initial states required")
    if config["closure"] != {"sources_i_bag": 0.0, "sources_e_bag": 0.0, "metabolism": "none_in_closed_toy_only",
                             "buffer_representation": "constant_effective_capacity_no_explicit_CO2",
                             "gas_and_reservoirs": "none_in_closed_toy", "ATP_present": False}:
        raise ValueError("only the closed MCT-only toy is implemented")
    for profile in config["solver_profiles"].values():
        for value in profile.values():
            finite(value, positive=True)
    for step in config["finite_difference_steps"]:
        finite(step, positive=True)
    return config


def rhs(time, state, *, h, truth):
    if np.shape(state) != (5,) or not np.all(np.isfinite(state)):
        raise ValueError("finite toy state required")
    if np.any(np.asarray(state)[:2] < 0):
        raise ValueError("negative substrate state; no silent clipping")
    li, le, phi, phe, _ = state
    j = mct_export(truth["access_i"] * li, truth["access_e"] * le, phi=phi, phe=phe,
                   conductance=truth["conductance"], km_i=truth["km_i"], km_e=truth["km_e"], ph_reference=truth["ph_reference"])
    pi, pe = buffered_rates(h * j, hct=h, beta_i=truth["beta_i"], beta_e=truth["beta_e"], source_i_bag=0, source_e_bag=0)
    return np.array([-j, h / (1 - h) * j, pi, pe, j])


def simulate(config, scenario, *, profile="ultrastrict", updates=None, phi0=None, time=None):
    validate_config(config)
    truth = copy.deepcopy(config["truth"])
    if updates:
        if not set(updates) <= set(truth):
            raise ValueError("unknown synthetic parameter")
        truth.update(updates)
        for value in truth.values():
            finite(value, positive=True)
    initial = np.array(scenario["initial"], dtype=float)
    if phi0 is not None:
        phi0 = finite(phi0)
        if not 0 < phi0 < 14:
            raise ValueError("synthetic pHi outside domain")
        initial[2] = phi0
    start, end = config["horizon_day"]
    if time is None:
        time = np.unique(np.r_[np.linspace(start, end, config["evaluation_count"]), config["sparse_days"],
                               np.linspace(start, config["training_end_day"], config["dense_training_count"])])
    time = np.asarray(time, dtype=float)
    if (time.ndim != 1 or not len(time) or not np.all(np.isfinite(time)) or np.any(np.diff(time) <= 0)
            or time[0] < start or time[-1] > end):
        raise ValueError("ordered in-horizon query times required")
    h = config["geometry"]["hematocrit"]
    sol = solve_ivp(lambda t, x: rhs(t, x, h=h, truth=truth), (start, end), initial,
                    method="BDF", dense_output=True, **config["solver_profiles"][profile])
    if not sol.success or sol.t[-1] != end:
        raise ValueError("incomplete synthetic integration: " + sol.message)
    states = sol.sol(time)
    if not np.all(np.isfinite(states)) or min(states[:2].min(), sol.y[:2].min()) < 0:
        raise ValueError("invalid synthetic concentrations")
    flux = np.array([rhs(t, x, h=h, truth=truth)[4] for t, x in zip(time, states.T)])
    amounts = h * states[0] + (1 - h) * states[1]
    acid = -h * truth["beta_i"] * (states[2] - initial[2]) - (1 - h) * truth["beta_e"] * (states[3] - initial[3])
    extent = states[4]
    expected = np.vstack([initial[0] - extent, initial[1] + h / (1 - h) * extent,
                          initial[2] + extent / truth["beta_i"], initial[3] - h / (1 - h) * extent / truth["beta_e"]])
    return {"time": time, "states": states, "accepted_time": sol.t, "accepted_states": sol.y,
            "initial": initial, "flux": flux, "amount_residual": amounts - (h * initial[0] + (1 - h) * initial[1]),
            "acid_residual": acid, "extent_state_residual": states[:4] - expected, "solution": sol, "truth": truth}


def quadrature(result, config, order):
    nodes, weights = np.polynomial.legendre.leggauss(order)
    sol = result["solution"]
    h = config["geometry"]["hematocrit"]
    total = 0.0
    for left, right in zip(sol.t[:-1], sol.t[1:]):
        time = .5 * (left + right) + .5 * (right - left) * nodes
        states = sol.sol(time)
        values = [rhs(t, x, h=h, truth=result["truth"])[4] for t, x in zip(time, states.T)]
        total += .5 * (right - left) * np.dot(weights, values)
    return float(total)


def sensitivity(config, scenario, time, *, step):
    time = np.asarray(time, dtype=float)
    if np.any(time > config["training_end_day"]):
        raise ValueError("holdout cannot enter training sensitivities")
    jac = []
    for name in PARAMETERS:
        if name == "phi0":
            center = scenario["initial"][2]
            plus = simulate(config, scenario, phi0=center + step, time=time)
            minus = simulate(config, scenario, phi0=center - step, time=time)
        else:
            center = config["truth"][name]
            plus = simulate(config, scenario, updates={name: center * math.exp(step)}, time=time)
            minus = simulate(config, scenario, updates={name: center * math.exp(-step)}, time=time)
        jac.append((plus["states"][:4] - minus["states"][:4]) / (2 * step))
    return np.stack(jac, axis=-1)


def symmetry_inputs(config, scenario, c):
    c = finite(c, positive=True)
    return {"updates": {"access_i": config["truth"]["access_i"] * c,
                         "km_i": config["truth"]["km_i"] * c},
            "phi0": scenario["initial"][2] + math.log10(c)}
