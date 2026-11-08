"""Source-specific, nonredundant Vmax pilot scoring and non-regression gates."""

import numpy as np

ADENYLATES = ("ATP", "ADP", "AMP")


def panel_from_observations(observations, days, design):
    names = tuple(observations["values"])
    time = list(observations["time"])
    if len(names) != 55 or len(time) != 14 or time[0] != 1 or any(b <= a for a, b in zip(time, time[1:])):
        raise ValueError("exact ordered source panel required")
    indices = [time.index(t) for t in days]
    fit = [0, *(time.index(t) for t in design["fit_days"])]
    values = np.array([observations["values"][p] for p in names], float)
    if not np.all(np.isfinite(values)) or np.min(values) < 0 or not all(i > 0 for i in indices):
        raise ValueError("finite nonnegative source concentrations required")
    target = values[:, indices]
    bands = .05*np.median(values[:, fit], axis=1)[:, None]+.2*target
    excluded = set(design["source_aliases"]) | set(design["ambiguous_nominal_guards_only"]) | set(ADENYLATES)
    return {"names": names, "days": list(days), "target": target, "bands": bands,
            "adenylates": np.array([names.index(p) for p in ADENYLATES]),
            "other": np.array([p not in excluded for p in names]),
            "guarded": np.array([p not in set(design["source_aliases"]) | set(ADENYLATES) for p in names])}


def measure(prediction, panel):
    y, b = panel["target"], panel["bands"]
    x = np.asarray(prediction, float)
    ai = panel["adenylates"]
    if x.shape != y.shape or not np.all(np.isfinite(x)) or np.any(x[ai] <= 0) or np.any(y[ai] <= 0):
        raise ValueError("invalid or nonpositive adenylate prediction, no pseudocount")
    absolute = np.abs(x-y)
    squared = np.zeros_like(x)
    np.divide(absolute, b, out=squared, where=b > 0)
    n = np.sum(b > 0, axis=1)
    mse = np.divide(np.sum(squared**2, axis=1), n, out=np.zeros(len(n)), where=n > 0)
    log = np.log(x[ai]/y[ai])
    other = panel["other"] & (n > 0)
    if not other.any():
        raise ValueError("empty nonadenylate scoring panel")
    return {"adenylate_loss_raw": float(np.mean(log**2)), "other_loss_raw": float(np.mean(mse[other])),
            "working_MSE": mse.tolist(), "scaled_sample_count": n.tolist(),
            "absolute_errors_mM": absolute.tolist(), "adenylate_log_errors": log.tolist(),
            "adenylate_log_MSE": np.mean(log**2, axis=1).tolist(), "RMSE_mM": np.sqrt(np.mean(absolute**2, axis=1)).tolist(),
            "prediction_mM": x.tolist(), "adenylate_total_mM": x[ai].sum(axis=0).tolist(),
            "energy_charge": ((x[ai[0]]+.5*x[ai[1]])/x[ai].sum(axis=0)).tolist()}


def compare_metrics(metrics, reference, panel, design):
    b = panel["bands"]
    fraction = design["working_allowance_fraction"]
    m0, m = (np.array(r["working_MSE"]) for r in (reference, metrics))
    off = (m-m0)/(1+m0)-fraction
    zero = (b == 0) & panel["guarded"][:, None]
    a = design["zero_band_absolute_allowance_mM"]
    d0, d1 = (np.array(r["absolute_errors_mM"]) for r in (reference, metrics))
    # Zero-only scales remain undefined; only a labeled numerical absolute guard applies.
    zero_excess = (d1-d0-a)/(1+d0)
    e0, e1 = (np.abs(r["adenylate_log_errors"]) for r in (reference, metrics))
    point = e1-e0-np.log1p(fraction)
    base_mse = np.array(reference["adenylate_log_MSE"])
    adeny = (np.array(metrics["adenylate_log_MSE"])-base_mse*(1+fraction)-1e-8)/(1+base_mse)
    g = panel["guarded"] & (b > 0).any(axis=1)
    maximum = max(float(np.max(off[g], initial=-fraction)), float(np.max(zero_excess[zero], initial=-fraction)),
                  float(np.max(point)), float(np.max(adeny)))
    base_aden, base_other = reference["adenylate_loss_raw"], reference["other_loss_raw"]
    gain = (base_aden-metrics["adenylate_loss_raw"])/max(base_aden, 1e-15)
    return {"valid": True, "adenylate_loss": metrics["adenylate_loss_raw"]/max(base_aden, 1e-15),
            "other_loss": metrics["other_loss_raw"]/max(base_other, 1e-15), "max_guard_excess": maximum,
            "relative_adenylate_gain": gain, "guards_pass": maximum <= 0,
            "sufficient_gain": gain >= design["minimum_relative_adenylate_gain"],
            "off_target_failures": [p for p, fail in zip(panel["names"], (g & (off > 0)) | np.any(zero & (zero_excess > 0), axis=1)) if fail],
            "adenylate_point_failures": [[ADENYLATES[i], panel["days"][j]] for i, j in np.argwhere(point > 0)],
            "adenylate_mean_failures": [p for p, fail in zip(ADENYLATES, adeny > 0) if fail]}
