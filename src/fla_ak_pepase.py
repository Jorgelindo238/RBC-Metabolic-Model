"""Fixed-kinetics adenylate kinase ratio x PEP phosphatase capacity diagnostic: pure decisions.

No model, integration or filesystem access. The balanced AK capacities are
taken from a sealed arm, not recomputed here; the PEP phosphatase capacity
follows a registered rule inside its unchanged box.
"""

import numpy as np

from fla_guanylate_partition import improves

FORWARD, REVERSE, PEPASE = "vmax_VAK", "vmax_VAK_rev", "vmax_VPEP_PASE"
CHANGED = [FORWARD, REVERSE, PEPASE]
REQUIRED_FALSE = ("measured_J1_changed", "initial_state_changed", "km_changed", "bounds_changed", "optimization_executed",
                  "followup_calibration_allowed", "production_promotion_allowed", "J46_replayed")
RULES = (("center", "lower_bound"), ("sealed_balanced", "lower_bound"), ("sealed_balanced", "geometric_mean"))


def check_plan(plan):
    if any(plan[k] for k in REQUIRED_FALSE):
        raise ValueError("diagnostic cannot change J1, Km or bounds, optimize, calibrate, promote or run J46")
    if plan["changed_parameters"] != CHANGED or plan["bound_groups"] != {"AK": [FORWARD, REVERSE], "PEPase": [PEPASE]}:
        raise ValueError("only the two adenylate kinase capacities and the PEP phosphatase capacity are registered")
    arms, roles = plan["arms"], [plan["single_factor_arm"], plan["hypothesis_arm"], plan["monotonicity_arm"]]
    if set(arms) != set(roles) or len(set(roles)) != 3:
        raise ValueError("exactly one single-factor, one hypothesis and one monotonicity arm required")
    if tuple((arms[r]["ak"], arms[r]["pepase"]) for r in roles) != RULES:
        raise ValueError("arm roles do not match their registered rules")
    if plan["maximum_new_integrations"] != len(arms)*len(plan["profiles"]) or plan["profiles"] != ["strict", "ultrastrict"]:
        raise ValueError("registered integration count or profiles changed")


def arm_values(spec, center, sealed_ak, base_pepase, bounds):
    """Forward AK, reverse AK and PEP phosphatase capacity of one arm.

    ``center`` is (forward, reverse, pepase) at the working center and
    ``sealed_ak`` the (forward, reverse) pair of the sealed balanced arm. The
    phosphatase factor against base must stay inside the registered box.
    """
    forward, reverse = center[:2] if spec["ak"] == "center" else sealed_ak
    floor = base_pepase*bounds[0]
    pepase = floor if spec["pepase"] == "lower_bound" else float(np.sqrt(center[2]*floor))
    factor = pepase/base_pepase
    if not (np.isfinite([forward, reverse, pepase]).all() and min(forward, reverse, pepase) > 0
            and bounds[0]-1e-12 <= factor <= bounds[1]+1e-12 and pepase <= center[2]):
        raise ValueError("arm leaves the registered capacity box or raises the phosphatase")
    return float(forward), float(reverse), float(pepase)


def arm_parameters(center, forward, reverse, pepase):
    """Copy of the working-center parameters with only the three registered capacities replaced."""
    if not (np.isfinite([forward, reverse, pepase]).all() and min(forward, reverse, pepase) > 0):
        raise ValueError("positive finite capacities required")
    p = {**center, FORWARD: forward, REVERSE: reverse, PEPASE: pepase}
    if set(p) != set(center) or not {k for k in p if p[k] != center[k]} <= set(CHANGED):
        raise ValueError("only the three registered capacities may change")
    return p


def pk_share(pk, pepase):
    """Share of direct PEP outflow carried by pyruvate kinase."""
    total = pk+pepase
    return float(pk/total) if total > 0 else None


def worst_gap(block):
    if any(s is None for s in block["scores"].values()):
        return None
    return max(s["gap"] for s in block["scores"].values())


def beyond(arm, reference):
    """Lower worst gap than the reference with J15 ATP and ADP not lower; guards are not required here."""
    gaps = worst_gap(arm), worst_gap(reference)
    if None in gaps or not gaps[0] < gaps[1]:
        return False
    return all(arm["scores"][p][k] >= reference["scores"][p][k] for p in arm["scores"] for k in ("ATP_J15", "ADP_J15"))


def arm_flags(arm, control, reference):
    """``reference`` is the trajectory with the same AK capacities and the working-center phosphatase."""
    scored = all(s is not None for s in arm["scores"].values())
    good = improves(arm, control)
    failed = sorted({g for s in arm["scores"].values() if s is not None for g in s["failed_guards"]})
    flags = {"improves": good,
             "early_only": bool(scored and not good and all(arm["scores"][p]["ATP_J4"] > control["scores"][p]["ATP_J4"] for p in arm["scores"])),
             "failed_guards": failed, "pep_guard_failed": any(g.split(":")[1] == "PEP" for g in failed),
             "absolute_J15_targets_reached": bool(scored and all(s["gap"] <= 0 for s in arm["scores"].values())),
             "beyond_reference": bool(scored and beyond(arm, reference)),
             "pk_share_J1_J4": None, "pk_share_J1_J15": None, "pk_share_raised": None, "net_ATP_change_mM": None}
    if arm.get("ledger") and reference.get("ledger") and control.get("ledger"):
        a, r, c = arm["ledger"], reference["ledger"], control["ledger"]
        flags["pk_share_J1_J4"] = pk_share(a["PK_J1_J4"], a["PEPASE_J1_J4"])
        flags["pk_share_J1_J15"] = pk_share(a["PK_J1_J15"], a["PEPASE_J1_J15"])
        before = pk_share(r["PK_J1_J15"], r["PEPASE_J1_J15"])
        flags["pk_share_raised"] = bool(flags["pk_share_J1_J15"] is not None and before is not None and flags["pk_share_J1_J15"] > before)
        flags["net_ATP_change_mM"] = (a["ATP_production"]-a["ATP_consumption"])-(c["ATP_production"]-c["ATP_consumption"])
    return flags


def classify(hypothesis, single, middle, control, ak_only):
    flags = {"hypothesis": arm_flags(hypothesis, control, ak_only), "single_factor": arm_flags(single, control, control),
             "monotonicity": arm_flags(middle, control, ak_only)}
    if not (all(hypothesis["numerical_pass"].values()) and hypothesis["paired_pass"]):
        category = "numerical_failure"
    elif flags["hypothesis"]["improves"]:
        category = "combined_effect_supported"
    elif flags["single_factor"]["improves"]:
        category = "pepase_alone_effect_only"
    else:
        category = "no_supported_effect"
    gaps = [worst_gap(b) for b in (ak_only, middle, hypothesis)]
    monotone = None if any(g is None for g in gaps) else bool(min(gaps[0], gaps[2]) <= gaps[1] <= max(gaps[0], gaps[2]))
    return {"category": category, "flags": flags, "monotone_response": monotone, "working_center_retained": True,
            "grouped_search_design_retained": True, "followup_calibration_launched": False, "production_promoted": False}
