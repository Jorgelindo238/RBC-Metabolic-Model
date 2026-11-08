"""Explicit provisional numerical profile; historical kernel defaults stay intact."""

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKING_REFERENCE = ROOT / "config/fla_working_reference.json"


def _positive_number(value):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and np.isfinite(value) and value > 0.0)


def load_working_reference(path=DEFAULT_WORKING_REFERENCE):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if config.get("schema_version") != 1 or config.get("status") != "provisional_numerical_working_reference":
        raise ValueError("unsupported provisional working-reference contract")
    if any(config.get(key) is not False for key in (
        "kinetic_parameters_changed", "kinetic_parameters_promoted", "calibration_allowed",
        "threshold_selection_by_prediction_error",
    )):
        raise ValueError("working reference cannot enable kinetic calibration or promotion")
    for key, policy in (("profile", "reaction_consistent"), ("historical_profile", "legacy")):
        profile = config[key]
        if profile["positivity_policy"] != policy or profile["solver_method"] != "BDF":
            raise ValueError("working and historical policies must be explicit")
        if not all(_positive_number(profile[key]) for key in ("solver_rtol", "solver_atol")):
            raise ValueError("invalid reference solver tolerances")
        threshold = profile["reaction_availability_threshold_mM"]
        if (policy == "legacy" and threshold is not None) or (policy != "legacy" and not _positive_number(threshold)):
            raise ValueError("invalid numerical availability threshold")
    controls = config["validation_before_calibration"]
    thresholds = controls["availability_thresholds_mM"]
    if (not thresholds or not all(_positive_number(value) for value in thresholds)
            or len(set(thresholds)) != len(thresholds)
            or config["profile"]["reaction_availability_threshold_mM"] not in thresholds):
        raise ValueError("threshold screen must be finite, unique and contain the reference")
    for key in ("ultrastrict_rtol", "ultrastrict_atol", "comparison_atol_mM", "comparison_rtol",
                "closure_tolerance_mM_per_day", "quadrature_atol_mM", "quadrature_rtol"):
        if not _positive_number(controls[key]):
            raise ValueError(f"invalid numerical control: {key}")
    if (controls["ultrastrict_rtol"] >= config["profile"]["solver_rtol"]
            or controls["ultrastrict_atol"] >= config["profile"]["solver_atol"]):
        raise ValueError("ultrastrict tolerances must be tighter than the working reference")
    minimum = controls["negative_state_tolerance_mM"]
    if isinstance(minimum, bool) or not isinstance(minimum, (int, float)) or not np.isfinite(minimum) or minimum > 0:
        raise ValueError("invalid raw-state negativity tolerance")
    if controls["horizon_day"] != [1.0, 46.0] or controls["quadrature_orders"] != [4, 8]:
        raise ValueError("this diagnostic contract requires J1-J46 and quadrature orders 4/8")
    return config


def reference_options(config, *, historical=False, ultrastrict=False, threshold=None):
    profile = config["historical_profile" if historical else "profile"]
    if historical and (threshold is not None or ultrastrict):
        raise ValueError("historical replay cannot override the numerical threshold or tolerances")
    ode = {"positivity_policy": profile["positivity_policy"], "curve_fit_strength": 0.0}
    if not historical:
        value = profile["reaction_availability_threshold_mM"] if threshold is None else threshold
        if not _positive_number(value):
            raise ValueError("invalid numerical threshold override")
        ode["reaction_availability_threshold"] = float(value)
    controls = config["validation_before_calibration"]
    solver = {"method": profile["solver_method"],
              "rtol": controls["ultrastrict_rtol"] if ultrastrict else profile["solver_rtol"],
              "atol": controls["ultrastrict_atol"] if ultrastrict else profile["solver_atol"]}
    return ode, solver
