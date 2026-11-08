"""Profile total lognormal residual dispersion, not isolated assay precision."""

import numpy as np


def profile_lognormal_dispersion(predicted, observed):
    pred, obs = np.asarray(predicted, dtype=float), np.asarray(observed, dtype=float)
    if (pred.ndim != 1 or pred.shape != obs.shape or len(pred) < 3 or not np.all(np.isfinite(pred))
            or not np.all(np.isfinite(obs)) or np.any(pred <= 0) or np.any(obs <= 0)):
        raise ValueError("at least three aligned positive finite training concentrations required")
    d = np.log(obs)-np.log(pred)
    m2 = float(np.mean(d*d))
    if m2 == 0:
        raise ValueError("zero-dispersion boundary; do not invent a variance floor")
    # Exact positive root of v^2 + 4v - 4 mean(d^2) = 0, without cancellation.
    v = 2*m2/(np.sqrt(1+m2)+1)
    residuals = (d+.5*v)/np.sqrt(v)
    nll = float(.5*np.dot(residuals, residuals)+np.sum(np.log(obs))+.5*len(obs)*np.log(2*np.pi*v))
    return {"log_variance": float(v), "CV": float(np.sqrt(np.expm1(v))), "negative_log_likelihood": nll,
            "count": len(obs), "interpretation": "total_residual_dispersion_includes_model_input_and_assay_error"}
