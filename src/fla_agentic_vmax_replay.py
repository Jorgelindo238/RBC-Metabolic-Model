"""Free ODE integration and rate-based verification for paired network modes."""

import numpy as np
from scipy.integrate import solve_ivp

from fla_balance_audit import accepted_step_quadrature, integrate_intervals


def integrate_free(rhs, initial, end, times, profile, negative_tolerance):
    initial = np.asarray(initial, float)
    if initial.shape != (114,) or initial[-1] != 7.2:
        raise ValueError("frozen clamped-pH state required")
    sol = solve_ivp(rhs, (1., float(end)), initial.copy(), method="BDF", dense_output=True,
                    jac_sparsity=rhs.jacobian_sparsity, **profile)
    if not sol.success or sol.t[-1] != end or not np.array_equal(sol.y[:, 0], initial):
        raise ValueError("ODE incomplete or exact J1 changed")
    time = np.unique(np.r_[np.linspace(1., end, 301), np.arange(1., end+1.), times])
    states = sol.sol(time)
    minimum = float(min(states[:113].min(), sol.y[:113].min()))
    if not np.isfinite(states).all() or minimum < negative_tolerance:
        raise ValueError("negative or nonfinite checked concentration")
    return sol, time, states, minimum


def within(a, b, numeric, kind):
    a, b = np.asarray(a), np.asarray(b)
    return np.abs(a-b) <= numeric[kind+"_atol_mM"]+numeric[kind+"_rtol"]*np.maximum(np.abs(a), np.abs(b))


def replay_evidence(rhs, initial, end, sample_days, profile, numeric, native_rates):
    sol, time, states, minimum = integrate_free(rhs, initial, end, sample_days, profile, numeric["negative_tolerance_mM"])
    bounds = np.arange(1., end+1.)
    result = {"time": time, "states": states, "accepted_time": sol.t, "accepted_states": sol.y,
              "matrix": rhs.matrix, "pool_names": np.array(rhs.names), "reactions": np.array(rhs.reactions),
              "boundaries": bounds}
    live = 0
    for order in (4, 8):
        grid = accepted_step_quadrature(sol.t, bounds, order=order)
        x = sol.sol(grid.nodes)
        minimum = min(minimum, float(x[:113].min()))
        rates = [rhs.rates(t, y)[:2] for t, y in zip(grid.nodes, x.T)]
        raw, executed = (np.asarray([r[i] for r in rates]).T for i in range(2))
        for name, values in (("raw", raw), ("executed", executed)):
            result[f"{name}{order}"] = integrate_intervals(values, grid)
            result[f"q{order}_{name}_rates"] = values
        result.update({f"q{order}_weights": grid.weights, f"q{order}_intervals": grid.interval_indices})
        if order == 8:
            chosen = np.linspace(0, len(grid.nodes)-1, 9).astype(int)
            for j in chosen:
                v0, v1 = native_rates(grid.nodes[j], x[:, j])
                if not np.allclose(v0, raw[:, j], rtol=1e-12, atol=1e-12) or not np.allclose(v1, executed[:, j], rtol=1e-12, atol=1e-12):
                    raise ValueError("native source rate projection disagrees with fast replay")
                live += 1
            result.update(live_time=grid.nodes[chosen], live_states=x[:, chosen], live_raw=raw[:, chosen], live_executed=executed[:, chosen])
    increments = np.diff(sol.sol(bounds)[:113], axis=1)
    closure = rhs.matrix@result["executed8"]
    checks = {"daily_balance": within(increments, closure, numeric, "quadrature"),
              **{k+"_quadrature": within(result[k+"4"], result[k+"8"], numeric, "quadrature") for k in ("raw", "executed")}}
    return result, {"numerical_pass": all(v.all() for v in checks.values()) and minimum >= numeric["negative_tolerance_mM"],
                    "minimum_checked_mM": minimum, "live_native_rate_checks": live,
                    "checks": {k: {"passed": int(v.sum()), "total": v.size} for k, v in checks.items()},
                    "max_daily_balance_residual_mM": float(np.max(np.abs(increments-closure)))}
