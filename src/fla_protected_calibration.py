"""Nine-pool likelihood and explicit training-only non-regression constraints."""

import numpy as np

from fla_joint_calibration import predict, unpack
from fla_profiled_observation_noise import profile_lognormal_dispersion

POOLS = ("EGLC", "GLC", "LAC", "ELAC", "ATP", "ADP", "AMP", "PEP", "G6P")


def training_data(observations, end_day):
    times = np.asarray(observations["time"], dtype=float)
    if times.ndim != 1 or not np.all(np.isfinite(times)) or np.any(np.diff(times) <= 0):
        raise ValueError("finite ordered original source times required")
    values = np.array([observations["values"][p] for p in POOLS], dtype=float)
    if values.shape != (len(POOLS), len(times)):
        raise ValueError("aligned original source channels required")
    mask = (times > 1) & (times <= end_day)
    selected = values[:, mask]
    if not mask.any() or not np.all(np.isfinite(selected)) or np.any(selected <= 0):
        raise ValueError("positive actual postinitial training values required; no imputation")
    return times[mask], selected


def score(prediction, observed):
    p, y = np.asarray(prediction, float), np.asarray(observed, float)
    if p.shape != y.shape or p.ndim != 2 or p.shape[0] != len(POOLS) or p.shape[1] == 0:
        raise ValueError("nine aligned noninitial observation channels required")
    result = profile_lognormal_dispersion(p.ravel(), y.ravel())
    rmse = np.sqrt(np.mean((p-y)**2, axis=1))
    result.update({"pools": list(POOLS), "points_per_pool": p.shape[1],
                   "RMSE_mM": dict(zip(POOLS, rmse.tolist())),
                   "log_RMSE": float(np.sqrt(np.mean(np.log(y/p)**2))),
                   "covariance_assumption": "independent_common_total_log_variance_not_measured_assay_covariance",
                   "independent_teacher_likelihood": False})
    return result


def guard_contract(reference_prediction, observed, design):
    s = score(reference_prediction, observed)
    reference = np.array([s["RMSE_mM"][p] for p in POOLS])
    if np.any(reference <= 0):
        raise ValueError("this relative guard normalization requires nonzero reference errors")
    atol, rtol = design["guard_numerical_atol_mM"], design["guard_numerical_rtol"]
    fraction = design["fitting_allowance_fraction"]
    if not np.isfinite(atol+rtol+fraction) or atol < 0 or rtol < 0 or not 0 < fraction < 1:
        raise ValueError("predeclared numerical allowance and reserved replay margin required")
    allowance = atol+rtol*reference
    return {"pools": list(POOLS), "reference_RMSE_mM": reference.tolist(),
            "numerical_allowance_mM": allowance.tolist(),
            "fit_limit_RMSE_mM": (reference+fraction*allowance).tolist(),
            "audit_limit_RMSE_mM": (reference+allowance).tolist(),
            "reference_score": s, "interpretation": design["allowance_interpretation"],
            "training_only": True}


def assess(prediction, observed, contract, *, phase="fit"):
    if phase not in ("fit", "audit") or contract["pools"] != list(POOLS):
        raise ValueError("declared fit/audit limits and ordered nine-pool contract required")
    s = score(prediction, observed)
    errors = np.array([s["RMSE_mM"][p] for p in POOLS])
    reference = np.asarray(contract["reference_RMSE_mM"])
    limits = np.asarray(contract[phase+"_limit_RMSE_mM"])
    margins = (limits-errors)/reference
    return {"passed": bool(np.all(errors <= limits)), "phase": phase,
            "margins": margins.tolist(), "RMSE_mM": s["RMSE_mM"],
            "delta_RMSE_mM": dict(zip(POOLS, (errors-reference).tolist())),
            "failed_pools": [p for p, e, limit in zip(POOLS, errors, limits) if e > limit],
            "score": s}


def predict_nine(initial, parameters, kinetics, end_day, sample_time, *, profile=None):
    _, sol, rhs = predict(initial, parameters, kinetics, end_day, sample_time, profile=profile)
    return sol.sol(sample_time)[[rhs.names.index(p) for p in POOLS]], sol, rhs


def evaluate(x, frozen, times, target):
    p, k, factors = unpack(x, frozen["parameters"], frozen["candidate"]["glucose_kinetics"],
                           frozen["resolved_capacities"], frozen["parent_design"]["factor_bounds"])
    predicted, _, _ = predict_nine(np.array(frozen["initial"]), p, k,
                                  frozen["design"]["training_end_day"], times)
    result = assess(predicted, target, frozen["guards"])
    return {"log_factors": np.asarray(x).tolist(), "factors": factors, "valid": True,
            "predictions": predicted.tolist(), "score": result["score"],
            "guards": {name: value for name, value in result.items() if name != "score"}}


def best_feasible(trace):
    eligible = [r for r in trace if r["valid"] and r["guards"]["passed"]]
    if not eligible:
        raise ValueError("no feasible control; fail closed rather than relax guards")
    return min(eligible, key=lambda r: r["score"]["negative_log_likelihood"])
