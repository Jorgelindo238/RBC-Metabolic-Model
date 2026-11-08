"""Nested paired/split capacity models: only HK and PFK can change."""

import copy
import numpy as np

from fla_broad_protected_calibration import POOLS, training_data, predict_broad, assess, score, best_feasible

FREE = ("vmax_VHK", "vmax_VPFK")


def seed_coordinates(frozen, mode):
    if mode not in ("paired", "split"):
        raise ValueError("paired or split mode required")
    return np.full(1 if mode == "paired" else 2, frozen["seed_log_investment"])


def coordinate_bounds(frozen, mode):
    return np.tile(np.log(frozen["primitive_factor_bounds"]), (len(seed_coordinates(frozen, mode)), 1))


def unpack(x, frozen, mode):
    x = np.asarray(x, float)
    bounds = coordinate_bounds(frozen, mode)
    if x.shape != (len(bounds),) or not np.all(np.isfinite(x)):
        raise ValueError("finite declared HK/PFK coordinates required")
    if np.any(x < bounds[:, 0]-1e-12) or np.any(x > bounds[:, 1]+1e-12):
        raise ValueError("original primitive capacity bounds exceeded")
    factors = np.exp(np.repeat(x, 2) if mode == "paired" else x)
    parameters = copy.deepcopy(frozen["parameters"])
    for name, factor in zip(FREE, factors):
        parameters[name] = frozen["primitive_capacities"][name]*float(factor)
    if parameters["vmax_VHK"] > 5.+1e-12:
        raise ValueError("original HK5.0 ceiling exceeded")
    if any(parameters[k] != v for k, v in frozen["parameters"].items() if k not in FREE):
        raise ValueError("a frozen non-HK/PFK parameter changed")
    return parameters, dict(frozen["kinetics"]), dict(zip(FREE, factors.tolist()))


def evaluate(x, frozen, mode, times, target):
    parameters, kinetics, factors = unpack(x, frozen, mode)
    prediction, sol, rhs = predict_broad(np.array(frozen["initial"]), parameters, kinetics,
                                        frozen["design"]["training_end_day"], times)
    guards = assess(prediction, target, frozen["guards"])
    row = {"log_factors": np.asarray(x).tolist(), "mode": mode, "factors": factors,
        "valid": True, "predictions": prediction.tolist(), "score": guards.pop("score"), "guards": guards}
    return row, sol


def inner_margins(row, frozen):
    reserve = (frozen["design"]["optimizer"]["inner_reserve_fraction"]
               *np.array(frozen["guards"]["numerical_allowance_mM"])/frozen["guards"]["normalization_mM"])
    return np.array(row["guards"]["margins"])-reserve


def choose_nested(parent, paired, split, minimum_gain):
    paired_choice = paired if parent["training_score"]["negative_log_likelihood"]-paired["training_score"]["negative_log_likelihood"] >= minimum_gain else parent
    split_gain = paired_choice["training_score"]["negative_log_likelihood"]-split["training_score"]["negative_log_likelihood"]
    return (split if split_gain >= minimum_gain else paired_choice), paired_choice, split_gain
