"""Fixed-kinetics adenylate kinase forward/reverse ratio diagnostic: pure decisions.

No model, integration or filesystem access. The zero of the coded AK law is
derived from a caller-supplied raw-rate function, never from a transcribed
formula, and is not asserted to be a thermodynamic equilibrium.
"""

import numpy as np

from fla_guanylate_partition import improves

FORWARD, REVERSE = "vmax_VAK", "vmax_VAK_rev"
REQUIRED_FALSE = ("measured_J1_changed", "initial_state_changed", "km_changed", "bounds_changed", "optimization_executed",
                  "followup_calibration_allowed", "production_promotion_allowed", "J46_replayed")
REVERSE_RULES = ("center", "upper_bound")
RATIO_RULES = ("balance", "geometric_mean")


def check_plan(plan):
    if any(plan[k] for k in REQUIRED_FALSE):
        raise ValueError("diagnostic cannot change J1, Km or bounds, optimize, calibrate, promote or run J46")
    if plan["changed_parameters"] != [FORWARD, REVERSE] or plan["balance_reaction"] != "VAK" or plan["bound_group"] != "AK":
        raise ValueError("only the two adenylate kinase capacities are registered")
    arms, roles = plan["arms"], [plan["hypothesis_arm"], plan["capacity_arm"], plan["monotonicity_arm"]]
    if set(arms) != set(roles) or len(set(roles)) != 3:
        raise ValueError("exactly one hypothesis, one capacity and one monotonicity arm required")
    if any(a["reverse"] not in REVERSE_RULES or a["ratio"] not in RATIO_RULES for a in arms.values()):
        raise ValueError("unregistered arm rule")
    rules = lambda key: (arms[key]["reverse"], arms[key]["ratio"])
    if (rules(plan["hypothesis_arm"]), rules(plan["capacity_arm"]), rules(plan["monotonicity_arm"])) != (
            ("center", "balance"), ("upper_bound", "balance"), ("center", "geometric_mean")):
        raise ValueError("arm roles do not match their registered rules")
    if plan["maximum_new_integrations"] != len(arms)*len(plan["profiles"]) or plan["profiles"] != ["strict", "ultrastrict"]:
        raise ValueError("registered integration count or profiles changed")


def balance_ratio(rate, forward, reverse, tolerance):
    """Vf/Vr that zeroes a law of the form Vf*a - Vr*b at one fixed state.

    ``rate(Vf, Vr)`` is the raw coded rate. Linearity in both capacities is
    checked, not assumed.
    """
    r0, r_forward, r_reverse = rate(forward, reverse), rate(2*forward, reverse), rate(forward, 2*reverse)
    a, b = (r_forward-r0)/forward, (r0-r_reverse)/reverse
    if not (np.isfinite([a, b]).all() and a > 0 and b > 0):
        raise ValueError("coded law is not a positive forward term minus a positive reverse term at this state")
    if abs(forward*a-reverse*b-r0) > tolerance or abs(rate(3*forward, 3*reverse)-3*r0) > tolerance:
        raise ValueError("coded law is not linear in the two capacities")
    return float(b/a)


def arm_capacities(spec, center, base, ratio, bounds):
    """Forward and reverse capacity of one arm; each factor against base must stay inside the registered box."""
    center_forward, center_reverse = center
    reverse = center_reverse if spec["reverse"] == "center" else base[1]*bounds[1]
    target = ratio if spec["ratio"] == "balance" else float(np.sqrt(ratio*center_forward/center_reverse))
    forward = target*reverse
    factors = (forward/base[0], reverse/base[1])
    if not all(np.isfinite(v) and bounds[0]-1e-12 <= v <= bounds[1]+1e-12 for v in factors):
        raise ValueError("arm leaves the registered capacity box")
    return float(forward), float(reverse), tuple(map(float, factors))


def arm_parameters(center, forward, reverse):
    """Copy of the working-center parameters with only the two AK capacities replaced."""
    if not (np.isfinite([forward, reverse]).all() and forward > 0 and reverse > 0):
        raise ValueError("positive finite capacities required")
    p = {**center, FORWARD: forward, REVERSE: reverse}
    if set(p) != set(center) or not {k for k in p if p[k] != center[k]} <= {FORWARD, REVERSE}:
        raise ValueError("only the two adenylate kinase capacities may change")
    return p


def arm_flags(arm, control, fraction):
    scored = all(s is not None for s in arm["scores"].values())
    good = improves(arm, control)
    flags = {"improves": good,
             "early_only": bool(scored and not good and all(arm["scores"][p]["ATP_J4"] > control["scores"][p]["ATP_J4"] for p in arm["scores"])),
             "failed_guards": sorted({g for s in arm["scores"].values() if s is not None for g in s["failed_guards"]}),
             "absolute_J15_targets_reached": bool(scored and all(s["gap"] <= 0 for s in arm["scores"].values())),
             "reductions_mM": None, "ak_flux_reduced": None, "consumption_compensation": None, "net_ATP_change_mM": None}
    if arm.get("ledger") and control.get("ledger"):
        d = {k: control["ledger"][k]-arm["ledger"][k] for k in ("AK", "ATP_consumption", "ATP_production")}
        flags["reductions_mM"] = d
        flags["ak_flux_reduced"] = bool(d["AK"] > 0)
        flags["consumption_compensation"] = bool(d["AK"] > 0 and d["ATP_consumption"] >= fraction*d["AK"])
        flags["net_ATP_change_mM"] = d["ATP_consumption"]-d["ATP_production"]
    return flags


def worst_gap(block):
    if any(s is None for s in block["scores"].values()):
        return None
    return max(s["gap"] for s in block["scores"].values())


def classify(hypothesis, capacity, middle, control, fraction):
    flags = {"hypothesis": arm_flags(hypothesis, control, fraction), "capacity": arm_flags(capacity, control, fraction),
             "monotonicity": arm_flags(middle, control, fraction)}
    if not (all(hypothesis["numerical_pass"].values()) and hypothesis["paired_pass"]):
        category = "numerical_failure"
    elif flags["hypothesis"]["improves"]:
        category = "ak_ratio_effect_supported"
    elif flags["capacity"]["improves"]:
        category = "capacity_dependent_effect_only"
    else:
        category = "no_supported_effect"
    gaps = [worst_gap(b) for b in (control, middle, hypothesis)]
    monotone = None if any(g is None for g in gaps) else bool(min(gaps[0], gaps[2]) <= gaps[1] <= max(gaps[0], gaps[2]))
    return {"category": category, "flags": flags, "monotone_response": monotone, "working_center_retained": True,
            "grouped_search_design_retained": True, "followup_calibration_launched": False, "production_promoted": False}
