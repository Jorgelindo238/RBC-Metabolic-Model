"""Explicit dated guards and a trust-region LP proposal for Vmax calibration."""

import numpy as np
from scipy.optimize import linprog

from fla_agentic_vmax_panel import ADENYLATES, measure


def evaluate_panel(prediction, reference, panel, design, plan):
    m = measure(prediction, panel)
    r0, r = (np.array(z["adenylate_log_errors"]) for z in (reference, m))
    e0, e = np.mean(r0**2, axis=0), np.mean(r**2, axis=0)
    if np.any(e0 <= 0):
        raise ValueError("nonzero dated reference error required for relative minimax")
    ratios = e/e0
    fraction = design["working_allowance_fraction"]
    absolute = np.array(m["absolute_errors_mM"])
    base_absolute = np.array(reference["absolute_errors_mM"])
    b = panel["bands"]
    guarded = panel["guarded"]
    m0, m1 = (np.array(z["working_MSE"]) for z in (reference, m))
    rows = {}
    for i, p in enumerate(panel["names"]):
        if not guarded[i]:
            continue
        if (b[i] > 0).any():
            rows["MSE:"+p] = (m1[i]-m0[i])/(1+m0[i])-fraction
        for j, t in enumerate(panel["days"]):
            if b[i, j] == 0:
                rows[f"zero:{p}:J{t}"] = (absolute[i,j]-base_absolute[i,j]-design["zero_band_absolute_allowance_mM"])/(1+base_absolute[i,j])
    for i, p in enumerate(ADENYLATES):
        for j, t in enumerate(panel["days"]):
            rows[f"log:{p}:J{t}"] = abs(r[i,j])-abs(r0[i,j])-np.log1p(fraction)
    for p in plan["critical_pointwise_pools"]:
        i = panel["names"].index(p)
        for j, t in enumerate(panel["days"]):
            band = b[i,j]
            cap = np.sqrt(base_absolute[i,j]**2+fraction*(band**2+base_absolute[i,j]**2))
            if band == 0:
                cap = base_absolute[i,j]+design["zero_band_absolute_allowance_mM"]
            rows[f"point:{p}:J{t}"] = (absolute[i,j]-cap)/max(band+cap, 1e-6)
    values = list(rows.values())
    return {"objective": float(ratios.max()), "day_ratios": ratios.tolist(),
            "gain_by_day": (1-ratios).tolist(), "mean_log_error": float(e.mean()),
            "guards": {k: float(v) for k, v in rows.items()}, "guards_pass": bool(max(values) <= 0),
            "sufficient_every_day": bool(np.all(1-ratios >= plan["minimum_each_day_relative_gain"])),
            "metrics": m}


def lp_step(x, lower, upper, radius, ratios, jac_ratio, guards, jac_guard, reserve):
    """Propose a local step only; the caller must re-evaluate the nonlinear ODE."""
    dimension = len(x)
    a = np.vstack((np.column_stack((jac_ratio, -np.ones(len(ratios)))),
                   np.column_stack((jac_guard, np.zeros(len(guards))))))
    b = np.r_[-np.asarray(ratios), -np.asarray(guards)-reserve]
    lo, hi = np.maximum(lower-x, -radius), np.minimum(upper-x, radius)
    solution = linprog(np.r_[np.zeros(dimension), 1.], A_ub=a, b_ub=b,
                       bounds=list(zip(lo, hi))+[(None, None)], method="highs")
    if solution.status not in (0, 2):
        raise RuntimeError(f"unresolved trust-region LP: {solution.message}")
    if not solution.success:
        return None
    if np.max(a@solution.x-b) > 1e-7:
        raise RuntimeError("LP witness violates linearized constraints")
    return {"delta": solution.x[:-1].tolist(), "predicted_objective": float(solution.x[-1])}
