"""Explicit reduced-model coverage and counterfactual volume checks."""

import numpy as np


def volume_conservation_diagnostic(cell, extra, time, hematocrit):
    c, e, t = (np.asarray(v, float) for v in (cell, extra, time))
    if (c.ndim != 1 or c.shape != e.shape or c.shape != t.shape or len(c) < 2
            or not all(np.all(np.isfinite(a)) for a in (c, e, t)) or np.any(c < 0) or np.any(e < 0)
            or np.any(np.diff(t) <= 0) or not 0 < hematocrit < 1): raise ValueError("aligned nonnegative phase concentrations required")
    rows = []
    for i, (dc, de) in enumerate(zip(np.diff(c), np.diff(e))):
        denominator = dc-de
        if denominator == 0:
            h, possible = None, bool(dc == 0)
        else:
            h = float(-de/denominator); possible = bool(0 < h < 1)
        rows.append({"start_day": float(t[i]), "end_day": float(t[i+1]), "delta_cell_mM": float(dc),
            "delta_extra_mM": float(de), "exact_constant_H_implied": h, "physical_H_exists_for_this_interval": possible})
    amount = hematocrit*c+(1-hematocrit)*e
    variable = []
    for ci, ei in zip(c, e):
        variable.append(None if ci == ei else float((amount[0]-ei)/(ci-ei)))
    return {"declared_H": hematocrit, "amount_per_L_bag": amount.tolist(), "intervals": rows,
        "counterfactual_time_varying_H": variable, "H_fitted_or_measured": False,
        "any_interval_has_no_physical_constant_H": any(not r["physical_H_exists_for_this_interval"] for r in rows),
        "binding_normalization_or_cohort_effects_excluded": False}


def channel_coverage(matrix, model_names, observations, time, *, actively_fitted):
    m = np.asarray(matrix, float)
    if m.shape[0] != len(model_names) or not np.all(np.isfinite(m)): raise ValueError("aligned model matrix required")
    rows = []
    for name, values in observations.items():
        if name not in model_names: raise ValueError("explicit metabolite mapping required:"+name)
        y = np.asarray(values, float)
        if y.shape != (len(time),) or not np.all(np.isfinite(y)): raise ValueError("aligned source series required")
        static = not np.any(m[model_names.index(name)])
        varies = bool(np.any(y != y[0]))
        alias = name in ("B13PG", "P2G")
        rows.append({"pool": name, "source_retained": True, "known_source_alias": alias,
            "model_row_is_static": static, "nominal_observations_vary": varies,
            "status": "source_alias_not_independent" if alias else "blocked_static_dynamics" if static and varies
                      else "conditional_fitting_scope" if name in actively_fitted else "audit_only",
            "absolute_initial_state_changed": False, "structural_and_source_accuracy_verified": False})
    return rows
