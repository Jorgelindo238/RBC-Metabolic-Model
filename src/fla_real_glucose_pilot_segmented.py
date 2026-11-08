"""Successor real pilot with explicit experimental-input integration boundaries."""

from types import SimpleNamespace

import numpy as np
from scipy.integrate import solve_ivp

from fla_real_glucose_pilot import glucose_driver, training_score
from rbc_distinct_volume_transport import glut_import


def predict_glucose(data, design, clearance, km_e, *, profile="ultrastrict", method="BDF"):
    if not np.all(np.isfinite([clearance, km_e])) or min(clearance, km_e) <= 0:
        raise ValueError("positive finite candidate kinetics required")
    time = np.asarray(data["time"], dtype=float)
    driver = glucose_driver(time, data["GLC"], design["training_end_day"])
    initial = float(data["EGLC"][0])
    breaks = np.r_[time[time <= design["training_end_day"]], time[-1]]
    segments, accepted_time, accepted_states = [], [], []

    def rate(day, state):
        if state[0] < 0:
            raise ValueError("negative extracellular glucose; no clipping")
        return [-glut_import(driver(day), state[0], conductance=clearance, km_i=data["kinetics"]["km_i"], km_e=km_e)]

    state = [initial]
    for i, (start, end) in enumerate(zip(breaks[:-1], breaks[1:])):
        sol = solve_ivp(rate, (start, end), state, method=method, dense_output=True, **design["solver_profiles"][profile])
        if not sol.success or sol.t[-1] != end or sol.y.min() < 0:
            raise ValueError("incomplete segmented carrier integration")
        segments.append(sol)
        accepted_time.extend(sol.t[1 if i else 0:])
        accepted_states.extend(sol.y[0, 1 if i else 0:])
        state = sol.y[:, -1]

    def dense(query):
        scalar = np.ndim(query) == 0
        query = np.atleast_1d(query).astype(float)
        if np.any(query < time[0]) or np.any(query > time[-1]):
            raise ValueError("query outside the source horizon")
        indices = np.minimum(np.searchsorted(breaks, query, side="right")-1, len(segments)-1)
        values = np.array([segments[j].sol(t)[0] for t, j in zip(query, indices)])
        return values[:1] if scalar else values[None, :]

    return {"time": time, "predicted_EGLC": dense(time)[0], "accepted_time": np.array(accepted_time),
        "accepted_EGLC": np.array(accepted_states), "driver_at_samples": np.array([driver(t) for t in time]),
        "solution": SimpleNamespace(t=np.array(accepted_time), sol=dense)}
