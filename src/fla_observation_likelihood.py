"""Explicit assay likelihoods; no default experimental noise or zero imputation."""

import numpy as np


def mixed_assay_likelihood(predicted, observed, rows, *, concentration_cv, ph_sd, mask=None):
    """Mean-preserving lognormal concentration and additive normal pH assays.

    Rows identify LAC/ELAC/pHi/pHe in the synthetic adapter, not extra flux
    observations. The returned NLL includes normalizers for noise estimation.
    """
    predicted, observed = np.asarray(predicted, dtype=float), np.asarray(observed, dtype=float)
    rows = tuple(rows)
    if (predicted.ndim != 2 or predicted.shape != observed.shape or predicted.shape[0] != len(rows)
            or not predicted.size or len(set(rows)) != len(rows) or any(r not in (0, 1, 2, 3) for r in rows)
            or not np.all(np.isfinite(predicted)) or not np.all(np.isfinite(observed))):
        raise ValueError("finite aligned distinct assay channels required")
    if concentration_cv is None or ph_sd is None:
        raise ValueError("noise must be supplied explicitly, never borrowed from synthetic defaults")
    cv, sd = np.asarray(concentration_cv, dtype=float), np.asarray(ph_sd, dtype=float)
    if (cv.shape or sd.shape or not np.isfinite(cv) or not np.isfinite(sd)
            or cv <= 0 or sd <= 0 or isinstance(concentration_cv, bool) or isinstance(ph_sd, bool)):
        raise ValueError("explicit positive finite scalar assay noise required")
    if mask is None:
        mask = np.ones(predicted.shape, dtype=bool)
    else:
        mask = np.asarray(mask)
        if mask.shape != predicted.shape or mask.dtype != bool:
            raise ValueError("explicit boolean observation mask required")
    if not mask.any():
        raise ValueError("at least one stochastic observation is required")
    log_variance = np.log1p(float(cv)**2)
    sigma_log = np.sqrt(log_variance)
    residuals, normalizers = [], []
    for i, row in enumerate(rows):
        pred, obs = predicted[i, mask[i]], observed[i, mask[i]]
        if row < 2:
            if np.any(pred <= 0) or np.any(obs <= 0):
                raise ValueError("positive concentrations required; zeros need an explicit censoring or zero model")
            residuals.extend((np.log(obs)-np.log(pred)+.5*log_variance)/sigma_log)
            normalizers.extend(np.log(obs)+np.log(sigma_log)+.5*np.log(2*np.pi))
        else:
            residuals.extend((obs-pred)/float(sd))
            normalizers.extend(np.full(len(obs), np.log(float(sd))+.5*np.log(2*np.pi)))
    residuals = np.asarray(residuals)
    nll = float(.5*np.dot(residuals, residuals)+np.sum(normalizers))
    return {"residuals": residuals, "negative_log_likelihood": nll, "terms": len(residuals)}
