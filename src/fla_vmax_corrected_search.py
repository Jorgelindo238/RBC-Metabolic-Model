"""Pure decisions for the corrected-engine Vmax-only absolute search.

No model, data or filesystem access. The trust-region LP itself stays in
``fla_temporal_vmax.lp_step``; scoring stays in ``fla_absolute_vmax``.
"""

import numpy as np

REQUIRED_FALSE = ("bounds_expanded", "Km_changed", "fit_based_retries",
                  "production_promotion_allowed", "J46_replayed")
INHERITED_TEMPORAL = ("fit_days", "critical_pointwise_pools", "minimum_each_day_relative_gain",
                      "number_of_rounds", "difference_step_log", "initial_radius_log",
                      "maximum_radius_log", "reserve_fraction", "line_search_fractions",
                      "minimum_step_objective_gain")


def check_plan(plan, frozen):
    """Fail closed if the registered search differs from the frozen parent contract."""
    if any(plan[k] for k in REQUIRED_FALSE):
        raise ValueError("search cannot expand bounds, change Km, retry by fit, promote or run J46")
    for key in INHERITED_TEMPORAL:
        if plan[key] != frozen["temporal"][key]:
            raise ValueError(f"inherited search constant changed: {key}")
    parent = frozen["requalification_plan"]
    for key in ("threshold_mM", "scipy_version", "method", "profiles", "jacobian_minimum_step_mM"):
        if plan[key] != parent[key]:
            raise ValueError(f"qualified numerical recipe changed: {key}")
    if plan["threshold_mM"] != frozen["numeric"]["availability_threshold_mM"]:
        raise ValueError("availability threshold changed")
    if plan["search_profile"] != "strict" or plan["audit_profiles"] != ["strict", "ultrastrict"]:
        raise ValueError("registered search/audit profiles changed")
    if plan["search_backend"] != parent["candidate_backend"] or plan["start"] != "working_center":
        raise ValueError("certified backend or registered start changed")
    if (plan["target_day"], plan["target_pools"], plan["target_band"]) != (15, ["ATP", "ADP"], "inherited_working_scale"):
        raise ValueError("registered absolute target changed")
    groups = len(frozen["design"]["groups"])
    needed = plan["maximum_control_integrations"]+plan["number_of_rounds"]*(groups+len(plan["line_search_fractions"]))
    if plan["maximum_control_integrations"] != 2 or needed > plan["maximum_search_attempts"]:
        raise ValueError("registered integration budget cannot cover the registered rounds")
    if plan["maximum_audit_integrations"] != 2:
        raise ValueError("registered audit budget changed")
    if not np.isclose(plan["center_worst_profile_absolute_gap"]-plan["futility_gap_threshold"], 1., rtol=0, atol=1e-12):
        raise ValueError("registered futility rule is one log unit below the center gap")
    return needed


def difference_points(x, lower, upper, step):
    """One forward log difference per coordinate, reversed only to stay inside the box."""
    x, lower, upper = (np.asarray(v, float) for v in (x, lower, upper))
    if not step > 0 or np.any(x < lower-1e-12) or np.any(x > upper+1e-12):
        raise ValueError("positive step and in-box anchor required")
    h = np.where(x+step <= upper, step, -step)
    if np.any(x+h < lower):
        raise ValueError("difference step leaves a degenerate box")
    return x+np.diag(h)


def finite_differences(x, sides0, guards0, rows):
    """Jacobians of absolute sides and guards from actual evaluations only.

    A coordinate whose evaluation is invalid, or clipped back onto the anchor,
    gets a zero column and is reported as missing so the caller can freeze it.
    """
    x = np.asarray(x, float)
    r0, g0 = np.array(list(sides0.values())), np.array(list(guards0.values()))
    jr, jg, good = np.zeros((len(r0), len(x))), np.zeros((len(g0), len(x))), []
    if len(rows) != len(x):
        raise ValueError("one difference row per coordinate required")
    for i, row in enumerate(rows):
        if not row["valid"]:
            continue
        moved = np.asarray(row["log_factors"], float)-x
        if moved[i] == 0 or np.any(np.delete(moved, i) != 0):
            if moved[i] == 0:
                continue
            raise ValueError("difference row moved more than its own coordinate")
        if list(row["absolute"]["sides"]) != list(sides0) or list(row["feasibility_guards"]) != list(guards0):
            raise ValueError("side or guard order changed between evaluations")
        jr[:, i] = (np.array(list(row["absolute"]["sides"].values()))-r0)/moved[i]
        jg[:, i] = (np.array(list(row["feasibility_guards"].values()))-g0)/moved[i]
        good.append(i)
    return jr, jg, good


def near_active(guards, reserve):
    """Guards whose slack at the anchor is inside the registered LP reserve."""
    return [k for (k, v), r in zip(guards.items(), reserve) if v > -r]


def controls_agree(new, sealed, atol, rtol):
    a, b = np.asarray(new, float), np.asarray(sealed, float)
    if a.shape != b.shape or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("aligned finite control panels required")
    delta = np.abs(a-b)
    limit = atol+rtol*np.maximum(np.abs(a), np.abs(b))
    return {"pass": bool(np.all(delta <= limit)), "max_difference_mM": float(delta.max()),
            "max_tolerance_ratio": float((delta/limit).max()), "bitwise_identical": bool(np.array_equal(a, b))}


def feasible(row):
    return bool(row["valid"] and row.get("reserved_guards_pass", False))


def select(rows):
    """Lowest worst-side gap among actually evaluated reserve-feasible rows; earliest wins ties."""
    admitted = [r for r in rows if feasible(r)]
    if not admitted:
        raise ValueError("no reserve-feasible evaluated row; the center itself must qualify")
    return min(admitted, key=lambda r: (r["absolute"]["objective"], r["attempt"]))


def classify(numerical_pass, paired_pass, scores, inside_box, plan, selected_is_center):
    """Registered decision rules, evaluated on the worst audited profile."""
    center_gap, center_ratio = plan["center_worst_profile_absolute_gap"], plan["center_worst_dated_ratio"]
    if selected_is_center:
        gap, ratio, category = center_gap, center_ratio, "no_improvement"
    else:
        gap = ratio = None
        if not all(numerical_pass.values()) or not paired_pass:
            category = "numerical_failure"
        else:
            defined = all(s is not None for s in scores.values())
            guards_pass = bool(defined and inside_box and all(s["reserved_guards_pass"] for s in scores.values()))
            if not guards_pass:
                category = "metabolic_guard_failure"
            else:
                gap = max(s["absolute"]["objective"] for s in scores.values())
                ratio = max(s["objective"] for s in scores.values())
                if gap <= 0:
                    category = "absolute_target_attained"
                elif gap < center_gap and ratio <= center_ratio:
                    category = "improved_center"
                else:
                    category = "no_improvement"
    retained = category not in ("absolute_target_attained", "improved_center")
    final_gap = center_gap if retained else gap
    return {"category": category, "working_center_retained": retained,
            "audited_worst_profile_gap": gap, "audited_worst_dated_ratio": ratio,
            "final_working_gap": final_gap,
            "original_box_local_search_exhausted": bool(final_gap > plan["futility_gap_threshold"]),
            "absolute_J15_targets_reached": category == "absolute_target_attained",
            "production_promoted": False, "global_optimality": False, "global_infeasibility": False}
