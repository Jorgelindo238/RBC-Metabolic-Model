"""Observation primitives for a future fixed-kinetic latent-pool protocol."""

from __future__ import annotations

import numpy as np


def _array(value, *, positive=False):
    raw = np.asarray(value)
    if raw.dtype.kind not in "fiu" or any(isinstance(v, (bool, np.bool_)) for v in np.asarray(value, dtype=object).flat):
        raise ValueError("finite numeric values required")
    array = np.asarray(value, dtype=float)
    if not np.all(np.isfinite(array)) or np.any(array <= 0 if positive else array < 0):
        raise ValueError("positive values required" if positive else "nonnegative finite values required")
    return array


def reconstruct_relative(signal, reference_signal, anchor_mM, *, contract):
    """Return anchored estimates, never relabel them as measured concentrations."""
    if contract.get("ratio_kind") != "within_metabolite_time_course":
        raise ValueError("a same-day treatment/control ratio is not a temporal series")
    for key in ("linear_response_verified", "normalization_factors_resolved", "same_pool_definition",
                "same_volume_basis", "same_metabolite", "exact_anchor_day_verified"):
        if contract.get(key) is not True:
            raise ValueError(f"relative reconstruction requires {key}")
    if contract.get("anchor_context") not in {"same_donor", "same_cohort", "external_prior"}:
        raise ValueError("explicit anchor context required")
    values = _array(signal)
    reference, anchor = _array(reference_signal, positive=True), _array(anchor_mM, positive=True)
    if reference.ndim != 0 or anchor.ndim != 0:
        raise ValueError("one reference signal and anchor per metabolite required")
    result = anchor * (values / reference)
    if not np.all(np.isfinite(result)):
        raise ValueError("relative reconstruction overflow")
    return {"estimated_concentration_mM": result, "measurement_type": "anchored_estimate_not_absolute_measurement",
            "anchor_context": contract["anchor_context"], "uncertainty_propagated": False}


def relative_log_residual(prediction, observed_signal, *, reference_index):
    predicted, observed = _array(prediction, positive=True), _array(observed_signal, positive=True)
    if predicted.ndim != 1 or predicted.shape != observed.shape:
        raise ValueError("aligned one-dimensional positive series required")
    if type(reference_index) is not int or not 0 <= reference_index < len(predicted):
        raise ValueError("valid reference index required")
    return (np.log(predicted) - np.log(predicted[reference_index])
            - np.log(observed) + np.log(observed[reference_index]))


def paired_log_residual(treatment, control, observed_ratio):
    treatment, control, ratio = [_array(v, positive=True) for v in (treatment, control, observed_ratio)]
    if treatment.shape != control.shape or treatment.shape != ratio.shape:
        raise ValueError("same-day paired arrays must align")
    return np.log(treatment) - np.log(control) - np.log(ratio)


def reconstruct_log_variance(joint_covariance):
    """Delta-method variance of log(anchor*signal/reference), including covariance."""
    raw = np.asarray(joint_covariance)
    if raw.dtype.kind not in "fiu" or any(isinstance(v, (bool, np.bool_)) for v in np.asarray(joint_covariance, dtype=object).flat):
        raise ValueError("numeric covariance required")
    covariance = np.asarray(raw, dtype=float)
    if covariance.shape != (3, 3) or not np.all(np.isfinite(covariance)):
        raise ValueError("finite 3x3 log covariance in anchor/signal/reference order required")
    scale = float(np.max(np.abs(covariance)))
    normalized = covariance / scale if scale else covariance
    if not np.allclose(normalized, normalized.T, rtol=0, atol=1e-12):
        raise ValueError("symmetric covariance required")
    if np.linalg.eigvalsh(normalized).min() < -1e-12:
        raise ValueError("positive semidefinite covariance required")
    vector = np.array([1., 1., -1.])
    return max(0., float(vector @ covariance @ vector))


def redox_initial_state(initial, names, *, NAD_total, NADH_fraction, NADP_total, NADPH_fraction,
                        measured_pools):
    state = _array(initial).copy()
    if state.ndim != 1 or len(names) != len(state) or len(set(names)) != len(names):
        raise ValueError("unique aligned state registry required")
    totals = _array([NAD_total, NADP_total], positive=True)
    fractions = _array([NADH_fraction, NADPH_fraction])
    if np.any(fractions > 1):
        raise ValueError("redox fractions must lie in [0,1]")
    for a, b, total, fraction in zip(("NAD", "NADP"), ("NADH", "NADPH"), totals, fractions):
        if a in measured_pools or b in measured_pools:
            raise ValueError("measured J1 entries cannot be inferred or overwritten")
        state[names.index(a)], state[names.index(b)] = total * (1-fraction), total * fraction
    return state


def balance_identifiability(matrix, measured_indices):
    """Structural flux ambiguity only; not dynamic latent-state identifiability."""
    matrix = np.asarray(matrix, dtype=float)
    if matrix.ndim != 2 or not np.all(np.isfinite(matrix)):
        raise ValueError("finite stoichiometric matrix required")
    indices = np.asarray(measured_indices)
    if indices.ndim != 1 or indices.dtype.kind not in "iu" or len(set(indices.tolist())) != len(indices):
        raise ValueError("unique integer observation indices required")
    if np.any(indices < 0) or np.any(indices >= len(matrix)) or not len(indices):
        raise ValueError("observation index outside matrix")
    rows = matrix[indices]
    _, singular, right = np.linalg.svd(rows, full_matrices=True)
    threshold = np.finfo(float).eps * max(rows.shape) * (singular[0] if len(singular) else 0.)
    rank = int(np.count_nonzero(singular > threshold))
    null = right[rank:].T
    unique = np.linalg.norm(null, axis=1) <= 1e-10
    return {"measured_balance_count": len(indices), "rank": rank, "reaction_count": matrix.shape[1],
            "flux_nullity": matrix.shape[1]-rank, "individually_identifiable_columns": np.flatnonzero(unique).tolist(),
            "singular_values": singular.tolist(), "dynamic_latent_identifiability_established": False}
