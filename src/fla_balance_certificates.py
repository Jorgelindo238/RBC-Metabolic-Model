"""Simple exact-row certificates explaining necessary interval contradictions."""

import numpy as np


def balance_certificates(matrix, observed, time, errors, pools, forward_columns, *, tolerance=1e-11):
    m, y, t, sigma = (np.asarray(v, float) for v in (matrix, observed, time, errors))
    if (m.ndim != 2 or y.shape != sigma.shape or y.shape != (len(m), len(t)) or len(pools) != len(m)
            or not all(np.all(np.isfinite(v)) for v in (m, y, t, sigma)) or np.any(sigma < 0)):
        raise ValueError("aligned finite balance inputs required")
    forward = np.zeros(m.shape[1], bool); forward[list(forward_columns)] = True
    signed = ~forward
    candidates = [np.eye(len(m))[i] for i in range(len(m))]
    for i in range(len(m)):
        for j in range(i+1, len(m)):
            den = float(m[j, signed]@m[j, signed])
            if den == 0: continue
            ratio = -float(m[i, signed]@m[j, signed])/den
            if ratio <= 0: continue
            w = np.zeros(len(m)); w[i], w[j] = 1., ratio
            candidates.append(w/max(w))
    result = []
    for w in candidates:
        row = w@m
        if np.max(np.abs(row), initial=0) <= tolerance:
            kind, sign = "constant", 0
        elif np.max(np.abs(row[signed]), initial=0) <= tolerance and np.max(row[forward], initial=0) <= tolerance:
            kind, sign = "nonincreasing", 1
        elif np.max(np.abs(row[signed]), initial=0) <= tolerance and np.min(row[forward], initial=0) >= -tolerance:
            kind, sign = "nondecreasing", -1
        else: continue
        values, scales = w@y, np.abs(w)@sigma
        scales[0] = 0.  # Exact nominal J1 is not adjusted.
        lower, critical, change = 0., None, 0.
        for k in range(len(t)-1):
            for j in range(k+1, len(t)):
                d = values[j]-values[k]
                violation = abs(d) if sign == 0 else max(0., sign*d)
                denominator = scales[k]+scales[j]
                if denominator == 0:
                    if violation > tolerance: raise ValueError("exact-zero-error balance contradiction")
                    continue
                bound = violation/denominator
                if bound > lower: lower, critical, change = float(bound), [float(t[k]), float(t[j])], float(d)
        result.append({"kind": kind, "coefficients": {p: float(v) for p, v in zip(pools, w) if v != 0},
            "minimum_working_multiplier_lower_bound": lower, "critical_days": critical,
            "nominal_change": change, "source_combination": values.tolist(),
            "signed_columns_annihilated_max": float(np.max(np.abs(row[signed]), initial=0)),
            "matrix_combination": row.tolist(), "all_constraints_enumerated": False})
    return sorted(result, key=lambda r:r["minimum_working_multiplier_lower_bound"], reverse=True)
