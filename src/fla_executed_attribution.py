"""Signed stoichiometric budgets and descriptive availability-loss attribution."""

import numpy as np


def signed_pool_contributions(coefficients, fluxes):
    coefficients, fluxes = np.asarray(coefficients, dtype=float), np.asarray(fluxes, dtype=float)
    if (coefficients.ndim != 1 or fluxes.ndim != 2 or coefficients.size != fluxes.shape[0]
            or not coefficients.size or not fluxes.shape[1]
            or not np.all(np.isfinite(coefficients)) or not np.all(np.isfinite(fluxes))):
        raise ValueError("finite coefficients and fluxes must align")
    net = coefficients[:, None] * fluxes
    return {"net": net, "production": np.maximum(net, 0.0), "consumption": np.maximum(-net, 0.0)}


def limiting_loss_attribution(states, native_flux, coefficients, *, threshold):
    """Allocate |native-executed| to minimum-availability consumers; split ties.

    This is additive bookkeeping on one trajectory, not a causal intervention.
    Products cannot limit a positive rate, and consumers reverse for negative rates.
    """
    x, rate, column = (np.asarray(value, dtype=float) for value in (states, native_flux, coefficients))
    if (x.ndim != 2 or rate.ndim != 1 or column.ndim != 1 or x.shape != (column.size, rate.size)
            or not x.size or any(not np.all(np.isfinite(value)) for value in (x, rate, column))):
        raise ValueError("finite states, rates and reaction column must align")
    if isinstance(threshold, (bool, np.bool_)) or not np.isfinite(threshold) or threshold <= 0:
        raise ValueError("threshold must be finite and positive")
    availability = np.clip(x / threshold, 0.0, 1.0)
    consumers = ((column[:, None] < 0) & (rate > 0)) | ((column[:, None] > 0) & (rate < 0))
    factors = np.min(np.where(consumers, availability, 1.0), axis=0)
    active = consumers & (factors < 1.0) & (rate != 0.0) & np.isclose(
        availability, factors[None, :], rtol=1e-10, atol=1e-12)
    count = active.sum(axis=0)
    weights = np.divide(active.astype(float), count[None, :], out=np.zeros_like(availability), where=count[None, :] > 0)
    loss = np.abs(rate) * (1.0 - factors)
    return {"factors": factors, "loss": loss, "loss_by_pool": weights * loss, "active": active}


def aggregate_windows(values, boundaries, windows):
    values, boundaries = np.asarray(values, dtype=float), np.asarray(boundaries, dtype=float)
    if (values.ndim != 2 or boundaries.ndim != 1 or boundaries.size < 2
            or values.shape[1] != boundaries.size - 1 or not values.shape[0]
            or not np.all(np.isfinite(values)) or not np.all(np.isfinite(boundaries))
            or np.any(np.diff(boundaries) <= 0)):
        raise ValueError("finite interval integrals and increasing boundaries must align")
    result = []
    for _, start, end in windows:
        if not np.isfinite(start) or not np.isfinite(end) or start >= end:
            raise ValueError("windows must have finite increasing endpoints")
        left, right = np.flatnonzero(boundaries == start), np.flatnonzero(boundaries == end)
        if len(left) != 1 or len(right) != 1:
            raise ValueError("window endpoints must be exact audit boundaries")
        result.append(values[:, left[0]:right[0]].sum(axis=1))
    if not result:
        raise ValueError("at least one window is required")
    return np.column_stack(result)
