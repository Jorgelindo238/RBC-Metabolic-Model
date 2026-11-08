"""Eleven-channel likelihood with explicit per-time PEP non-regression."""

import numpy as np

from fla_joint_calibration import predict, unpack
from fla_profiled_observation_noise import profile_lognormal_dispersion
from fla_protected_calibration import best_feasible

POOLS = ("EGLC", "GLC", "LAC", "ELAC", "ATP", "ADP", "AMP", "PEP", "G6P", "F6P", "B23PG")


def training_data(observations, end_day):
    time = np.asarray(observations["time"], float)
    values = np.array([observations["values"][p] for p in POOLS], float)
    if (time.ndim != 1 or not np.all(np.isfinite(time)) or np.any(np.diff(time) <= 0)
            or values.shape != (len(POOLS), len(time))):
        raise ValueError("ordered aligned original observation channels required")
    mask = (time > 1) & (time <= end_day)
    selected = values[:, mask]
    if not mask.any() or not np.all(np.isfinite(selected)) or np.any(selected <= 0):
        raise ValueError("positive original postinitial observations required; no imputation")
    return time[mask], selected


def score(prediction, observed):
    prediction, observed = np.asarray(prediction, float), np.asarray(observed, float)
    if prediction.shape != observed.shape or prediction.ndim != 2 or prediction.shape[0] != len(POOLS) or not prediction.shape[1]:
        raise ValueError("eleven aligned observation channels required")
    result = profile_lognormal_dispersion(prediction.ravel(), observed.ravel())
    result.update({"pools": list(POOLS), "points_per_pool": prediction.shape[1],
        "RMSE_mM": dict(zip(POOLS, np.sqrt(np.mean((prediction-observed)**2, axis=1)).tolist())),
        "independent_teacher_likelihood": False,
        "covariance_assumption": "independent_common_total_log_variance_not_measured_assay_covariance"})
    return result


def constraint_errors(prediction, observed, times, pointwise_pools):
    result = score(prediction, observed)
    times = np.asarray(times, float)
    if times.shape != (np.shape(prediction)[1],) or not np.all(np.isfinite(times)) or np.any(np.diff(times) <= 0):
        raise ValueError("exact ordered constraint times required")
    if len(set(pointwise_pools)) != len(pointwise_pools) or not set(pointwise_pools) <= set(POOLS):
        raise ValueError("unique declared pointwise pools required")
    labels = ["RMSE:"+p for p in POOLS]
    errors = [result["RMSE_mM"][p] for p in POOLS]
    for pool in pointwise_pools:
        labels.extend(f"absolute:{pool}:J{day:g}" for day in times)
        errors.extend(np.abs(np.asarray(prediction)[POOLS.index(pool)]-np.asarray(observed)[POOLS.index(pool)]).tolist())
    return labels, np.array(errors), result


def guard_contract(reference, observed, design):
    if design["pools"] != list(POOLS) or set(POOLS) & set(design["source_aliases_excluded"]):
        raise ValueError("canonical declared guard channels required")
    labels, errors, result = constraint_errors(reference, observed, design["training_times"], design["pointwise_pools"])
    atol, rtol, fraction = (design[k] for k in ("guard_numerical_atol_mM", "guard_numerical_rtol", "fitting_allowance_fraction"))
    if not np.isfinite(atol+rtol+fraction) or atol <= 0 or rtol < 0 or not 0 < fraction < 1:
        raise ValueError("fixed positive numerical allowance with reserved replay margin required")
    allowance = atol+rtol*errors
    return {"pools": list(POOLS), "times": design["training_times"], "pointwise_pools": design["pointwise_pools"],
        "constraint_names": labels, "reference_errors_mM": errors.tolist(),
        "normalization_mM": np.maximum(errors, atol).tolist(), "numerical_allowance_mM": allowance.tolist(),
        "fit_limits_mM": (errors+fraction*allowance).tolist(), "audit_limits_mM": (errors+allowance).tolist(),
        "reference_score": result, "training_only": True, "interpretation": design["allowance_interpretation"]}


def assess(prediction, observed, contract, *, phase="fit"):
    if phase not in ("fit", "audit") or contract["pools"] != list(POOLS):
        raise ValueError("declared broad guard contract and phase required")
    labels, errors, result = constraint_errors(prediction, observed, contract["times"], contract["pointwise_pools"])
    if labels != contract["constraint_names"]:
        raise ValueError("constraint identities changed")
    limits = np.array(contract[phase+"_limits_mM"])
    passed = errors <= limits
    return {"passed": bool(passed.all()), "phase": phase,
        "margins": ((limits-errors)/contract["normalization_mM"]).tolist(),
        "errors_mM": dict(zip(labels, errors.tolist())), "RMSE_mM": result["RMSE_mM"],
        "failed_constraints": [name for name, ok in zip(labels, passed) if not ok], "score": result}


def predict_broad(initial, parameters, kinetics, end_day, times, *, profile=None):
    _, solution, rhs = predict(initial, parameters, kinetics, end_day, times, profile=profile)
    return solution.sol(times)[[rhs.names.index(p) for p in POOLS]], solution, rhs


def evaluate(x, frozen, times, target):
    parameters, kinetics, factors = unpack(x, frozen["parameters"], frozen["candidate"]["glucose_kinetics"],
        frozen["resolved_capacities"], frozen["parent_design"]["factor_bounds"])
    prediction, _, _ = predict_broad(np.array(frozen["initial"]), parameters, kinetics,
                                     frozen["design"]["training_end_day"], times)
    guards = assess(prediction, target, frozen["guards"])
    return {"log_factors": np.asarray(x).tolist(), "factors": factors, "valid": True,
        "predictions": prediction.tolist(), "score": guards.pop("score"), "guards": guards}
