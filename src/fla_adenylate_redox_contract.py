"""Precalibration algebra and reversible, source-backed redox IC scenarios."""

import numpy as np

ADENYLATE_POOLS = ("ATP", "ADP", "AMP")
AK_COLUMN = np.array([1., -2., 1.])
TOTAL_ADENYLATE_TERMS = {"VADSL": 1., "VAK2": 1., "VAPRT": 1.,
                         "VSAM": -1., "VAMPD1": -1., "VAMP_NT": -1.}


def adenylate_metrics(states):
    x = np.asarray(states, dtype=float)
    if x.ndim != 2 or x.shape[0] != 3 or not x.shape[1] or not np.all(np.isfinite(x)) or np.any(x < 0):
        raise ValueError("ATP/ADP/AMP must be finite nonnegative aligned concentrations")
    total = x.sum(axis=0)
    if np.any(total <= 0):
        raise ValueError("energy charge is undefined for an empty adenylate pool")
    return {"total": total, "energy_charge": (x[0] + .5*x[1]) / total,
            "fractions": x / total}


def conditional_ak_requirements(reference_change, executed_change, executed_ak_integral):
    reference, actual = np.asarray(reference_change, dtype=float), np.asarray(executed_change, dtype=float)
    if (reference.shape != (3,) or actual.shape != (3,) or not np.all(np.isfinite(reference))
            or not np.all(np.isfinite(actual)) or not np.isfinite(executed_ak_integral)):
        raise ValueError("three finite adenylate interval changes and a finite AK integral are required")
    other_terms = actual - AK_COLUMN * executed_ak_integral
    requirements = (reference - other_terms) / AK_COLUMN
    return {"required_by_pool": requirements, "requirement_spread_mM": float(np.ptp(requirements)),
            "total_adenylate_discrepancy_mM": float((reference - actual).sum()),
            "individually_observed_AK": False, "other_executed_terms_held_fixed": True}


def redox_initializations(initial, indices, historical):
    x = np.asarray(initial, dtype=float)
    positions = np.asarray(indices)
    historical = np.asarray(historical, dtype=float)
    if (x.ndim != 1 or not np.all(np.isfinite(x)) or np.any(x < 0)
            or positions.shape != (2,) or not np.issubdtype(positions.dtype, np.integer)
            or len(set(positions.tolist())) != 2 or np.any(positions < 0) or np.any(positions >= x.size)
            or historical.shape != (2,) or not np.all(np.isfinite(historical)) or np.any(historical <= 0)
            or np.any(x[positions] <= 0)):
        raise ValueError("valid initial states, two indices and positive historical redox values are required")
    current_total, historical_total = x[positions].sum(), historical.sum()
    current_fraction, historical_fraction = x[positions] / current_total, historical / historical_total
    values = {"baseline": x[positions], "historical_total_only": historical_total * current_fraction,
              "historical_ratio_only": current_total * historical_fraction, "historical_pair": historical}
    result = {}
    for label, pair in values.items():
        state = x.copy()
        state[positions] = pair
        result[label] = state
    return result


def readiness_blockers(data_contract, redox_contract, absolute_limits):
    """Numerical success cannot fill absent experimental or prior evidence."""
    blockers = []
    for key in ("upstream_lineage_verified", "normalization_verified", "uncertainty_available", "time_origin_verified"):
        if data_contract.get(key) is not True:
            blockers.append(f"data:{key}")
    if redox_contract.get("biological_prior_verified") is not True:
        blockers.append("redox:biological_prior_verified")
    if not isinstance(absolute_limits, dict):
        blockers.append("accuracy:absolute_limits_unset")
    else:
        for pool in ADENYLATE_POOLS:
            limit = absolute_limits.get(pool)
            if isinstance(limit, bool) or not isinstance(limit, (int, float)) or not np.isfinite(limit) or limit <= 0:
                blockers.append(f"accuracy:{pool}_absolute_limit")
    return blockers
