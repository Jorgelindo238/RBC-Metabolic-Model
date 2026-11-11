"""Fixed-kinetics latent ribose stock diagnostic: pure decisions.

No model, integration or filesystem access. Registered values are declared
conventions, never physiological bounds.
"""

import numpy as np

from fla_guanylate_partition import improves

REQUIRED_FALSE = ("measured_J1_changed", "parameters_changed", "optimization_executed",
                  "followup_calibration_allowed", "production_promotion_allowed", "J46_replayed")


def check_plan(plan):
    if any(plan[k] for k in REQUIRED_FALSE):
        raise ValueError("diagnostic cannot change measured J1 or parameters, optimize, calibrate, promote or run J46")
    if plan["changed_pool"] != "RIB" or plan["control_value_mM"] != 1.0:
        raise ValueError("only the latent ribose stock is registered")
    arms = plan["arms"]
    if set(arms) != {plan["hypothesis_arm"], plan["monotonicity_arm"]} or plan["hypothesis_arm"] == plan["monotonicity_arm"]:
        raise ValueError("exactly one hypothesis arm and one monotonicity arm required")
    values = [a["RIB_mM"] for a in arms.values()]
    if any(not np.isfinite(v) or not 0 < v < plan["control_value_mM"] for v in values) or len(set(values)) != len(values):
        raise ValueError("distinct positive ribose stocks below the control required")
    if not arms[plan["hypothesis_arm"]]["RIB_mM"] < arms[plan["monotonicity_arm"]]["RIB_mM"]:
        raise ValueError("monotonicity arm must lie between the hypothesis arm and the control")
    if plan["maximum_new_integrations"] != len(arms)*len(plan["profiles"]) or plan["profiles"] != ["strict", "ultrastrict"]:
        raise ValueError("registered integration count or profiles changed")


def arm_initial(initial, names, pool, value):
    """Copy of the frozen J1 vector with one latent pool replaced."""
    x = np.array(initial, float)
    if x.ndim != 1 or len(names) > x.size or not np.isfinite(value) or value <= 0:
        raise ValueError("aligned frozen state and positive finite stock required")
    x[names.index(pool)] = value
    base = np.asarray(initial, float)
    if [names[i] for i in np.flatnonzero(x[:len(names)] != base[:len(names)])] != [pool] or not np.array_equal(x[len(names):], base[len(names):]):
        raise ValueError("exactly the registered pool must change")
    return x


def inventory(value, control):
    return {"RIB_mM": value, "pentose_inventory_change_mM": value-control, "phosphoryl_inventory_change_mM": 0.}


def arm_flags(arm, control, fraction):
    scored = all(s is not None for s in arm["scores"].values())
    good = improves(arm, control)
    flags = {"improves": good,
             "early_only": bool(scored and not good and all(arm["scores"][p]["ATP_J4"] > control["scores"][p]["ATP_J4"] for p in arm["scores"])),
             "failed_guards": sorted({g for s in arm["scores"].values() if s is not None for g in s["failed_guards"]}),
             "absolute_J15_targets_reached": bool(scored and all(s["gap"] <= 0 for s in arm["scores"].values())),
             "reductions_mM": None, "demand_compensation": None, "production_compensation": None}
    if arm.get("ledger") and control.get("ledger"):
        d = {k: control["ledger"][k]-arm["ledger"][k] for k in ("RKa", "ATP_consumption", "ATP_production")}
        flags["reductions_mM"] = d
        flags["demand_compensation"] = bool(d["RKa"] > 0 and d["ATP_consumption"] < fraction*d["RKa"])
        flags["production_compensation"] = bool(d["ATP_consumption"] > 0 and d["ATP_production"] >= fraction*d["ATP_consumption"])
    return flags


def worst_gap(block):
    if any(s is None for s in block["scores"].values()):
        return None
    return max(s["gap"] for s in block["scores"].values())


def classify(hypothesis, middle, control, fraction):
    flags = {"hypothesis": arm_flags(hypothesis, control, fraction), "monotonicity": arm_flags(middle, control, fraction)}
    if not (all(hypothesis["numerical_pass"].values()) and hypothesis["paired_pass"]):
        category = "numerical_failure"
    elif flags["hypothesis"]["improves"]:
        category = "ribose_stock_effect_supported"
    else:
        category = "no_supported_effect"
    gaps = [worst_gap(b) for b in (control, middle, hypothesis)]
    monotone = None if any(g is None for g in gaps) else bool(min(gaps[0], gaps[2]) <= gaps[1] <= max(gaps[0], gaps[2]))
    return {"category": category, "flags": flags, "monotone_response": monotone, "working_center_retained": True,
            "J1_convention_retained": True, "followup_calibration_launched": False, "production_promoted": False}
