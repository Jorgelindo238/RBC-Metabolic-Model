"""Fixed-kinetics latent guanylate partition diagnostic: pure decisions.

No model, integration or filesystem access. The zero of the coded NDPK law
is solved on a caller-supplied raw-rate function, never from a transcribed
formula, and is not asserted to be a thermodynamic equilibrium.
"""

import numpy as np
from scipy.optimize import brentq

CONVENTIONS = {"GDP_plus_GTP": lambda value, gdp: value-gdp,
               "GDP_plus_2GTP": lambda value, gdp: (value-gdp)/2.}
REQUIRED_FALSE = ("measured_J1_changed", "parameters_changed", "optimization_executed",
                  "followup_calibration_allowed", "production_promotion_allowed", "J46_replayed")


def check_plan(plan):
    if any(plan[k] for k in REQUIRED_FALSE):
        raise ValueError("diagnostic cannot change measured J1 or parameters, optimize, calibrate, promote or run J46")
    if plan["changed_pools"] != ["GDP", "GTP"] or plan["zero_flux_reaction"] != "VNDPK":
        raise ValueError("only latent GDP/GTP and the NDPK zero are registered")
    if set(plan["arms"]) != {plan["hypothesis_arm"], plan["inventory_arm"]} or plan["hypothesis_arm"] == plan["inventory_arm"]:
        raise ValueError("exactly one hypothesis arm and one inventory arm required")
    if plan["maximum_new_integrations"] != len(plan["arms"])*len(plan["profiles"]) or plan["profiles"] != ["strict", "ultrastrict"]:
        raise ValueError("registered integration count or profiles changed")
    if any(a["convention"] not in CONVENTIONS for a in plan["arms"].values()):
        raise ValueError("unregistered second convention")


def solve_partition(raw_rate, convention, value, tolerance):
    """GDP, GTP with raw_rate(GDP, GTP) = 0 under one declared second convention."""
    if convention not in CONVENTIONS or not np.isfinite(value) or value <= 0:
        raise ValueError("registered convention and positive finite total required")
    gtp_of = lambda gdp: CONVENTIONS[convention](value, gdp)
    f = lambda gdp: raw_rate(gdp, gtp_of(gdp))
    lo, hi = 1e-12, value*(1-1e-12)
    if not f(lo) < 0 < f(hi):
        raise ValueError("zero-flux partition is not bracketed inside the positive declared pool")
    gdp = brentq(f, lo, hi, xtol=1e-15, rtol=1e-15)
    gtp = gtp_of(gdp)
    if not (gdp > 0 and gtp > 0) or abs(raw_rate(gdp, gtp)) > tolerance:
        raise ValueError("no positive zero-flux partition within tolerance")
    return float(gdp), float(gtp)


def inventory(gdp, gtp, reference=(1., 1.)):
    return {"GDP_mM": gdp, "GTP_mM": gtp, "total_mM": gdp+gtp, "E_G_mM": gdp+2*gtp,
            "delta_E_G_mM": gdp+2*gtp-(reference[0]+2*reference[1]),
            "delta_total_mM": gdp+gtp-sum(reference)}


def arm_initial(initial, names, gdp, gtp):
    """Copy of the frozen J1 vector with only GDP and GTP replaced."""
    x = np.array(initial, float)
    if x.ndim != 1 or len(names) > x.size:
        raise ValueError("frozen state and names must align")
    x[names.index("GDP")], x[names.index("GTP")] = gdp, gtp
    changed = [names[i] for i in np.flatnonzero(x[:len(names)] != np.asarray(initial, float)[:len(names)])]
    if not set(changed) <= {"GDP", "GTP"} or not np.array_equal(x[len(names):], np.asarray(initial, float)[len(names):]):
        raise ValueError("only GDP and GTP may change")
    return x


def improves(arm, control):
    """Registered meaning: valid, paired, guards with reserve, lower worst gap, ATP and ADP not lower."""
    if not (all(arm["numerical_pass"].values()) and arm["paired_pass"]):
        return False
    if any(s is None for s in arm["scores"].values()) or not all(s["reserved_guards_pass"] for s in arm["scores"].values()):
        return False
    gap = max(s["gap"] for s in arm["scores"].values())
    if not gap < max(s["gap"] for s in control["scores"].values()):
        return False
    return all(arm["scores"][p][k] >= control["scores"][p][k] for p in arm["scores"] for k in ("ATP_J15", "ADP_J15"))


def arm_flags(arm, control, fraction):
    scored = all(s is not None for s in arm["scores"].values())
    failed = sorted({g for s in arm["scores"].values() if s is not None for g in s["failed_guards"]})
    good = improves(arm, control)
    early = bool(scored and not good and all(arm["scores"][p]["ATP_J4"] > control["scores"][p]["ATP_J4"] for p in arm["scores"]))
    compensation = None
    if arm.get("ledger") and control.get("ledger"):
        d_ndpk = control["ledger"]["NDPK_J1_J4"]-arm["ledger"]["NDPK_J1_J4"]
        d_cons = control["ledger"]["ATP_consumption_J1_J4"]-arm["ledger"]["ATP_consumption_J1_J4"]
        compensation = {"NDPK_reduction_mM": d_ndpk, "ATP_consumption_reduction_mM": d_cons,
                        "flag": bool(d_ndpk > 0 and d_cons < fraction*d_ndpk)}
    return {"improves": good, "early_only": early, "failed_guards": failed, "compensation": compensation,
            "absolute_J15_targets_reached": bool(scored and all(s["gap"] <= 0 for s in arm["scores"].values()))}


def classify(hypothesis, inventory_arm, control, fraction):
    flags = {"hypothesis": arm_flags(hypothesis, control, fraction), "inventory": arm_flags(inventory_arm, control, fraction)}
    if not (all(hypothesis["numerical_pass"].values()) and hypothesis["paired_pass"]):
        category = "numerical_failure"
    elif flags["hypothesis"]["improves"]:
        category = "partition_effect_supported"
    elif flags["inventory"]["improves"]:
        category = "inventory_effect_only"
    else:
        category = "no_supported_effect"
    return {"category": category, "flags": flags, "working_center_retained": True, "J1_convention_retained": True,
            "followup_calibration_launched": False, "production_promoted": False}
