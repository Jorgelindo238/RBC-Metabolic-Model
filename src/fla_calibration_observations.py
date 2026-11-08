"""Explicit observation operators for reusable, cohort-specific FLA fitting."""

import copy
import numpy as np


def _numbers(value, *, positive=False):
    raw = np.asarray(value)
    if raw.dtype.kind not in "fiu" or any(isinstance(v, (bool, np.bool_)) for v in np.asarray(value, object).flat):
        raise ValueError("finite numeric observations required")
    a = np.asarray(value, float)
    if not np.all(np.isfinite(a)) or np.any(a <= 0 if positive else a < 0):
        raise ValueError("positive values required" if positive else "nonnegative values required")
    return a


def validate_series(series):
    s = copy.deepcopy(series)
    for key in ("channel_id", "metabolite", "trajectory_id", "cohort_id", "source_id", "unit", "volume_basis"):
        if not isinstance(s.get(key), str) or not s[key].strip(): raise ValueError("explicit "+key+" required")
    if s.get("compartment") not in ("intracellular", "extracellular"): raise ValueError("explicit compartment required")
    if s["volume_basis"] != {"intracellular": "cell_phase", "extracellular": "supernatant_phase"}[s["compartment"]]:
        raise ValueError("observation denominator must match its compartment")
    if not (isinstance(s.get("donor_id"), str) and s["donor_id"].strip()) and s.get("donor_identity_status") != "unresolved":
        raise ValueError("explicit donor identity or unresolved status required")
    time, values = _numbers(s["time"]), _numbers(s["values"])
    if time.ndim != 1 or time.size < 2 or values.shape != time.shape or np.any(np.diff(time) <= 0):
        raise ValueError("ordered aligned observations required; missing values need a mask upstream")
    kind = s.get("measurement_type")
    if kind not in ("absolute_concentration", "relative_signal", "temporal_ratio"):
        raise ValueError("unsupported measurement type; no silent absolute conversion")
    if s.get("normalization_status") != "resolved": raise ValueError("normalization unresolved")
    if kind == "absolute_concentration":
        if s["unit"] != "mM": raise ValueError("absolute adapter requires explicit conversion to mM")
    else:
        if s["unit"] != {"relative_signal": "relative_signal", "temporal_ratio": "fold_change"}[kind]:
            raise ValueError("relative values require the matching signal/ratio unit, never mM")
        if s.get("linear_response_verified") is not True: raise ValueError("relative response must be verified linear")
        if s.get("ratio_kind") != "within_metabolite_time_course": raise ValueError("relative cohort/control ratios need a separate operator")
        if kind == "temporal_ratio":
            ref = s.get("reference_index")
            if type(ref) is not int or not 0 <= ref < len(time) or values[ref] != 1:
                raise ValueError("temporal ratio requires a declared unit reference")
    return s


def validate_collection(series):
    if not isinstance(series, list) or not series: raise ValueError("nonempty observation-series list required")
    validated = [validate_series(s) for s in series]
    keys, groups = set(), {}
    for s in validated:
        key = (s["source_id"], s["cohort_id"], s["trajectory_id"], s["channel_id"])
        if key in keys: raise ValueError("duplicate observation series; do not double-count source channels")
        keys.add(key)
        group = (s["source_id"], s["cohort_id"], s["trajectory_id"], s.get("donor_id"))
        groups.setdefault(group, []).append(s["channel_id"])
    return {"series": validated, "groups": [{"source_id": k[0], "cohort_id": k[1], "trajectory_id": k[2],
        "donor_id": k[3], "channels": v} for k, v in groups.items()], "auto_merge_cohorts": False,
        "absolute_units_inferred_from_relative": False, "ODE_initialization_complete": False,
        "status": "observation_contract_validated_not_a_completed_ODE_calibration"}


def fixed_error_scales(values, *, absolute_fraction, relative_fraction, interpretation):
    y = _numbers(values)
    if y.ndim != 2 or not y.shape[1]: raise ValueError("channel x training-observation array required")
    a, b = _numbers([absolute_fraction, relative_fraction], positive=True)
    if interpretation not in ("engineering_normalization_not_assay_SD", "verified_assay_error_model"):
        raise ValueError("declare scale interpretation")
    medians = np.median(y, axis=1)
    if np.any(medians <= 0): raise ValueError("zero-only channels require explicit assay/censoring scales")
    return {"absolute": (a*medians).tolist(), "relative": float(b), "training_medians": medians.tolist(),
            "interpretation": interpretation, "estimated_from_model_residuals": False}


def residuals(predicted, series, *, mask, absolute_scale, relative_scale, nuisance_scale=None):
    s = validate_series(series)
    pred, y = _numbers(predicted), np.asarray(s["values"], float)
    use = np.asarray(mask)
    if pred.shape != y.shape or use.shape != y.shape or use.dtype != bool or not use.any():
        raise ValueError("aligned prediction and explicit nonempty boolean training mask required")
    a = float(_numbers(absolute_scale, positive=True))
    b = float(_numbers(relative_scale))
    sigma = a+b*np.abs(y)
    kind = s["measurement_type"]
    scale = None
    if kind == "relative_signal":
        if nuisance_scale is None:
            den = float(np.sum((pred[use]/sigma[use])**2))
            if den == 0: raise ValueError("relative nuisance scale is unidentifiable at zero prediction")
            scale = float(np.sum(pred[use]*y[use]/sigma[use]**2)/den)
        else: scale = float(_numbers(nuisance_scale, positive=True))
        if scale <= 0: raise ValueError("positive relative scale cannot be identified")
        pred = scale*pred
    elif kind == "temporal_ratio":
        ref = s["reference_index"]
        if pred[ref] <= 0: raise ValueError("positive reference prediction required")
        pred = pred/pred[ref]
        use = use.copy(); use[ref] = False
        if not use.any(): raise ValueError("ratio reference is not an independent fitting observation")
    r = (pred[use]-y[use])/sigma[use]
    return {"residuals": r, "observation_predictions": pred, "nuisance_scale": scale,
        "absolute_scale_identified_by_this_channel": kind == "absolute_concentration",
        "measurement_type": kind, "reference_covariance_modelled": False,
        "independent_assay_likelihood_claimed": False}


def objective_metrics(prediction, target, scales):
    p, y = _numbers(prediction), _numbers(target)
    if p.shape != y.shape or p.ndim != 2: raise ValueError("aligned channel matrices required")
    a = np.asarray(scales["absolute"], float)
    b = float(scales["relative"])
    if a.shape != (len(y),) or not np.all(np.isfinite(a)) or np.any(a <= 0) or not np.isfinite(b) or b < 0:
        raise ValueError("fixed positive absolute and nonnegative relative scales required")
    r = (p-y)/(a[:, None]+b*np.abs(y))
    per = np.mean(r*r, axis=1)
    return {"channel_MSE": per.tolist(), "balanced_MSE": float(np.mean(per)), "worst_channel_MSE": float(np.max(per)),
        "worst_channel_index": int(np.argmax(per)), "residuals": r.tolist(),
        "all_within_working_unit_MSE": bool(np.all(per <= 1)), "assay_accuracy_established": False}
