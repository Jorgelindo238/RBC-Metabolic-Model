"""Conditional glucose-carrier fit; GLC is an input, not a predicted RBC pool."""

import numpy as np
from scipy.integrate import solve_ivp
from scipy.interpolate import PchipInterpolator

from fla_profiled_observation_noise import profile_lognormal_dispersion
from rbc_distinct_volume_transport import glut_import


def glucose_driver(time, values, training_end):
    time, values = np.asarray(time, dtype=float), np.asarray(values, dtype=float)
    if (time.ndim != 1 or values.shape != time.shape or len(time) < 4 or not np.all(np.isfinite(time))
            or not np.all(np.isfinite(values)) or np.any(np.diff(time) <= 0) or np.any(values < 0)):
        raise ValueError("finite ordered nominal glucose observations required")
    mask = time <= training_end
    if mask.sum() < 4 or not np.any(~mask):
        raise ValueError("training and later-time comparison required")
    t, x = time[mask], values[mask]
    spline = PchipInterpolator(t, x, extrapolate=False)

    def driver(day):
        if day < t[0]:
            raise ValueError("no pre-initial extrapolation")
        return float(spline(day)) if day <= t[-1] else float(x[-1])
    return driver


def predict_glucose(data, design, clearance, km_e, *, profile="ultrastrict", method="BDF"):
    if not np.all(np.isfinite([clearance, km_e])) or min(clearance, km_e) <= 0:
        raise ValueError("positive finite candidate kinetics required")
    time = np.asarray(data["time"], dtype=float)
    driver = glucose_driver(time, data["GLC"], design["training_end_day"])
    initial = data["EGLC"][0]
    tolerances = design["solver_profiles"][profile]
    def rate(day, state):
        if state[0] < 0:
            raise ValueError("negative extracellular glucose; no clipping")
        return [-glut_import(driver(day), state[0], conductance=clearance, km_i=data["kinetics"]["km_i"], km_e=km_e)]
    solution = solve_ivp(rate, (time[0], time[-1]), [initial], method=method, dense_output=True, **tolerances)
    if not solution.success or solution.t[-1] != time[-1] or solution.y.min() < 0:
        raise ValueError("invalid conditional carrier integration")
    predicted = solution.sol(time)[0]
    return {"time": time, "predicted_EGLC": predicted, "accepted_time": solution.t, "accepted_EGLC": solution.y[0],
            "driver_at_samples": np.array([driver(t) for t in time]), "solution": solution}


def training_score(data, design, prediction):
    time = np.asarray(data["time"], dtype=float)
    mask = (time > time[0]) & (time <= design["training_end_day"])
    return profile_lognormal_dispersion(prediction["predicted_EGLC"][mask], np.asarray(data["EGLC"])[mask])
