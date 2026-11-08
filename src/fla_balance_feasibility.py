"""Necessary integrated-balance relaxations, never an ODE existence proof."""

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import block_diag, coo_matrix, hstack, vstack


def integral_balance_screen(matrix, observed, time, errors, *, reaction_bounds):
    m, y, t, scales = (np.asarray(v, float) for v in (matrix, observed, time, errors))
    if (m.ndim != 2 or y.ndim != 2 or y.shape[0] != len(m) or t.shape != (y.shape[1],)
            or scales.shape != y.shape or len(t) < 2 or len(reaction_bounds) != m.shape[1]
            or any(not np.all(np.isfinite(a)) for a in (m, y, t, scales)) or np.any(y < 0)
            or np.any(scales < 0) or np.any(np.diff(t) <= 0)):
        raise ValueError("aligned finite measured mM concentrations, scales and direction bounds required")
    n, intervals, reactions = len(y), len(t)-1, m.shape[1]
    delta = np.diff(y, axis=1).T.ravel()
    flux = block_diag([m]*intervals, format="csr")
    flux_bounds = list(reaction_bounds)*intervals
    exact = linprog(np.zeros(reactions*intervals), A_eq=flux, b_eq=delta, bounds=flux_bounds, method="highs")
    if exact.status not in (0, 2): raise RuntimeError("exact feasibility LP unresolved: "+exact.message)
    # Shared measurement adjustments couple adjacent intervals; J1 is never adjusted.
    rows, cols, values = [], [], []
    for k in range(intervals):
        for i in range(n):
            row = k*n+i
            rows.append(row); cols.append((k+1)*n+i); values.append(-1.)
            if k: rows.append(row); cols.append(k*n+i); values.append(1.)
    adjustments = coo_matrix((values, (rows, cols)), shape=(n*intervals, n*len(t))).tocsr()
    eq = hstack([flux, adjustments, coo_matrix((n*intervals, 1))], format="csr")
    size = eq.shape[1]
    c = np.zeros(size); c[-1] = 1
    nr = n*len(t)
    indices = np.arange(nr)
    selector = coo_matrix((np.ones(nr), (indices, indices+flux.shape[1])), shape=(nr, size)).tocsr()
    scale_col = coo_matrix((-scales.T.ravel(), (indices, np.full(nr, size-1))), shape=(nr, size)).tocsr()
    ub = vstack([selector+scale_col, -selector+scale_col], format="csr")
    bounds = flux_bounds+[(0., 0.)]*n+[(-float(v), None) for v in y[:, 1:].T.ravel()]+[(0., None)]
    solved = linprog(c, A_eq=eq, b_eq=delta, A_ub=ub, b_ub=np.zeros(2*nr), bounds=bounds, method="highs")
    if not solved.success: raise RuntimeError("shared-error feasibility LP unresolved: "+solved.message)
    z = solved.x[:flux.shape[1]].reshape(intervals, reactions).T
    e = solved.x[flux.shape[1]:-1].reshape(len(t), n).T
    adjusted = y+e
    # Concentrations are nonnegative, including hypothetical adjusted observations.
    if adjusted.min() < -1e-7: raise ValueError("negative adjusted observations; nonnegative constraint missing")
    residual = m@z-np.diff(adjusted, axis=1)
    if np.max(np.abs(residual)) > 1e-6: raise ValueError("inaccurate balance LP")
    return {"exact_measured_balances_feasible": bool(exact.success), "minimum_working_error_multiplier": float(solved.x[-1]),
        "executed_extent_integrals": z.tolist(), "hypothetical_observation_adjustments_mM": e.tolist(),
        "initial_observations_adjusted": False, "max_balance_residual_mM": float(np.max(np.abs(residual))),
        "observations_changed": False, "kinetic_or_ODE_feasibility_proved": False,
        "uncertainty_is_assay_SD": False}
