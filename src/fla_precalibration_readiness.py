"""Evidence-backed readiness checks, separate from archived diagnostic algebra."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

POOLS = ("ATP", "ADP", "AMP")
OBSERVATION_ORDER = tuple(f"{pool}_J{day}" for day in (1, 4) for pool in POOLS)


def positive_number(value):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and np.isfinite(value) and value > 0)


def covariance_matrix(values):
    raw = np.asarray(values)
    if raw.dtype.kind not in "fiu" or any(isinstance(value, (bool, np.bool_)) for value in np.asarray(values, dtype=object).flat):
        raise ValueError("covariance entries must be numeric, not booleans or numeric strings")
    covariance = np.asarray(values, dtype=float)
    if (covariance.shape != (6, 6) or not np.all(np.isfinite(covariance)) or np.any(np.diag(covariance) < 0)):
        raise ValueError("a finite symmetric 6x6 covariance in declared observation order is required")
    scale = float(np.max(np.abs(covariance)))
    normalized = covariance / scale if scale else covariance
    if not np.allclose(normalized, normalized.T, rtol=0, atol=1e-12):
        raise ValueError("covariance must be symmetric relative to its own scale")
    variances = np.diag(normalized)
    bounds = np.sqrt(variances[:, None] * variances[None, :])
    if np.any(np.abs(normalized) > bounds * (1 + 1e-12)):
        raise ValueError("covariance implies an impossible correlation")
    if np.linalg.eigvalsh(normalized).min() < -1e-12:
        raise ValueError("observation covariance must be positive semidefinite")
    return covariance


def propagate_adenylate_uncertainty(means, covariance):
    """First-order energy-charge propagation; total/change variances are exact."""
    means = np.asarray(means, dtype=float)
    if means.shape != (6,) or not np.all(np.isfinite(means)) or np.any(means < 0):
        raise ValueError("six finite nonnegative means in J1/J4 ATP/ADP/AMP order are required")
    covariance = covariance_matrix(covariance)
    totals, charges, total_vectors, charge_vectors = [], [], [], []
    for day_index in (0, 1):
        start = 3 * day_index
        values = means[start:start + 3]
        total = float(values.sum())
        if total <= 0:
            raise ValueError("energy charge requires a positive adenylate total")
        numerator = float(values[0] + .5 * values[1])
        total_vector, charge_vector = np.zeros(6), np.zeros(6)
        total_vector[start:start + 3] = 1
        charge_vector[start:start + 3] = (np.array([1., .5, 0.]) * total - numerator) / total**2
        totals.append(total)
        charges.append(numerator / total)
        total_vectors.append(total_vector)
        charge_vectors.append(charge_vector)
    change_vectors = np.c_[-np.eye(3), np.eye(3)]
    def variance(vector):
        return max(0., float(vector @ covariance @ vector))
    return {"observation_order": list(OBSERVATION_ORDER), "total_mM": totals,
            "energy_charge": charges, "total_variance_mM2": [variance(v) for v in total_vectors],
            "energy_charge_variance_delta_method": [variance(v) for v in charge_vectors],
            "pool_change_covariance_mM2": (change_vectors @ covariance @ change_vectors.T).tolist(),
            "total_change_variance_mM2": variance(total_vectors[1] - total_vectors[0]),
            "independence_assumed": False, "accuracy_limits_inferred": False}


def evidence_files_valid(section, root):
    evidence = section.get("evidence_files")
    if not isinstance(evidence, list) or not evidence:
        return False
    for item in evidence:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not item["path"].strip():
            return False
        digest = item.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            return False
        path = Path(item["path"])
        path = path if path.is_absolute() else Path(root) / path
        try:
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                return False
        except OSError:
            return False
    return True


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _timestamp(value):
    if not _text(value):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.tzinfo is not None and parsed <= datetime.now(timezone.utc)
    except ValueError:
        return False


def evaluate_readiness(contract, *, root, frozen_initial_redox):
    """Unknowns fail closed; a ready local contract never promotes the full model."""
    if contract.get("schema_version") != 1 or contract.get("horizon_day") != [1., 4.]:
        raise ValueError("this readiness contract requires schema 1 and J1-J4")
    sections = {key: contract.get(key, {}) for key in
                ("lineage", "normalization", "time_origin", "uncertainty", "accuracy", "redox_prior")}
    if any(not isinstance(section, dict) for section in sections.values()):
        raise ValueError("readiness sections must be mappings")
    checks = []
    def add(name, condition, requirement):
        checks.append({"name": name, "passed": bool(condition), "requirement": requirement})
    for key, section in sections.items():
        add(f"{key}:verified_evidence", section.get("verified") is True and evidence_files_valid(section, root),
            "Explicit verified claim plus existing evidence files with unchanged SHA256; a publication lead alone is insufficient")
    lineage = sections["lineage"]
    row_mapping = lineage.get("row_mapping")
    add("lineage:raw_table_mapping", _text(lineage.get("source_table_id")) and isinstance(row_mapping, dict)
        and all(_text(row_mapping.get(pool)) for pool in POOLS), "Exact upstream table/row mapping for ATP, ADP and AMP")
    normalization = sections["normalization"]
    factors = normalization.get("scale_to_model_mM_by_pool")
    add("normalization:quantity_basis", normalization.get("model_unit") == "mM"
        and normalization.get("compartment") == "intracellular" and _text(normalization.get("source_quantity_basis"))
        and _text(normalization.get("model_volume_basis")) and _text(normalization.get("transformation"))
        and isinstance(factors, dict) and all(positive_number(factors.get(pool)) for pool in POOLS),
        "Traceable pool-wise conversion, source quantity basis and intracellular model volume basis")
    time = sections["time_origin"]
    source_days, offset = time.get("source_days"), time.get("source_to_model_offset_day")
    valid_time = (isinstance(source_days, list) and len(source_days) == 2
                  and all(not isinstance(v, bool) and isinstance(v, (int, float)) and np.isfinite(v) for v in source_days)
                  and not isinstance(offset, bool) and isinstance(offset, (int, float)) and np.isfinite(offset))
    add("time_origin:explicit_mapping", valid_time and np.allclose(np.asarray(source_days) + offset, [1., 4.], rtol=0, atol=1e-12)
        and _text(time.get("biological_origin")), "Measured source days, biological origin and exact source-to-model offset; no implicit J0")
    uncertainty = sections["uncertainty"]
    valid_covariance = False
    try:
        covariance = covariance_matrix(uncertainty.get("covariance_mM2"))
        valid_covariance = bool(np.all(np.diag(covariance) > 0))
    except (TypeError, ValueError):
        pass
    biological, technical = uncertainty.get("biological_unit_count"), uncertainty.get("technical_replicate_count")
    valid_counts = (isinstance(biological, int) and not isinstance(biological, bool)
                    and isinstance(technical, int) and not isinstance(technical, bool))
    estimator_type = uncertainty.get("estimator_type")
    valid_estimator = valid_counts and (
        (estimator_type == "paired_biological_replicates" and biological >= 2 and technical >= 1)
        or (estimator_type == "validated_assay_covariance" and biological >= 1 and technical >= 2))
    add("uncertainty:joint_endpoint_covariance", valid_covariance and valid_estimator
        and uncertainty.get("observation_order") == list(OBSERVATION_ORDER)
        and _text(uncertainty.get("estimator")) and _text(uncertainty.get("estimand"))
        and uncertainty.get("cross_pool_and_cross_day_independence_assumed") is False,
        "Documented uncertainty estimand/estimator and full J1/J4 covariance, including cross-pool and cross-day terms")
    accuracy = sections["accuracy"]
    limits = accuracy.get("absolute_endpoint_error_mM")
    add("accuracy:independent_frozen_limits", isinstance(limits, dict) and all(positive_number(limits.get(pool)) for pool in POOLS)
        and accuracy.get("metric") == "absolute_endpoint_error_mM" and accuracy.get("independent_of_model_fit") is True
        and accuracy.get("basis") in ("measurement_supported_tolerance", "predeclared_prediction_requirement")
        and _text(accuracy.get("justification")) and _timestamp(accuracy.get("frozen_at")),
        "Three separately justified endpoint limits, frozen before fitting; not solver tolerances or undocumented literature variability")
    redox = sections["redox_prior"]
    total_bounds, fraction_bounds = redox.get("NAD_total_bounds_mM"), redox.get("NADH_fraction_bounds")
    valid_bounds = (isinstance(total_bounds, list) and len(total_bounds) == 2 and all(positive_number(v) for v in total_bounds)
                    and total_bounds[0] <= total_bounds[1]
                    and isinstance(fraction_bounds, list) and len(fraction_bounds) == 2
                    and all(not isinstance(v, bool) and isinstance(v, (int, float)) and np.isfinite(v) for v in fraction_bounds)
                    and 0 <= fraction_bounds[0] <= fraction_bounds[1] <= 1)
    add("redox_prior:supported_domain", valid_bounds and redox.get("quantity_unit") == "mM"
        and _text(redox.get("sample_context")) and _text(redox.get("volume_basis"))
        and redox.get("volume_basis") == normalization.get("model_volume_basis")
        and redox.get("source_pool_definition") in ("free_reaction_available", "total_extractable")
        and redox.get("source_pool_definition") == redox.get("model_pool_definition"),
        "Applicable stored-RBC prior support with matching volume and free-available/total-extractable pool definitions; historical inputs alone do not qualify")
    pair = np.asarray(frozen_initial_redox, dtype=float)
    if pair.shape != (2,) or not np.all(np.isfinite(pair)) or np.any(pair < 0) or pair.sum() <= 0:
        raise ValueError("frozen NAD/NADH initialization is invalid")
    total, fraction = float(pair.sum()), float(pair[1] / pair.sum())
    add("redox_prior:frozen_initialization_supported", valid_bounds and total_bounds[0] <= total <= total_bounds[1]
        and fraction_bounds[0] <= fraction <= fraction_bounds[1], "Frozen diagnostic initialization must fall in the supported prior domain")
    blockers = [check["name"] for check in checks if not check["passed"]]
    ready = not blockers
    return {"scientific_contract_complete": ready, "checks": checks, "blockers": blockers,
            "endpoint_accuracy_assessable": ready, "optimization_allowed": False,
            "global_model_promotion_allowed": False,
            "status": "ready_for_separate_calibration_protocol" if ready else "blocked_pending_scientific_evidence"}


def require_scientific_contract(contract, *, root, frozen_initial_redox):
    assessment = evaluate_readiness(contract, root=root, frozen_initial_redox=frozen_initial_redox)
    if assessment.get("scientific_contract_complete") is not True:
        raise ValueError("scientific readiness blocked: " + ", ".join(assessment.get("blockers", [])))
    return assessment


def endpoint_checks(reference, predicted, contract, *, root, frozen_initial_redox):
    reference, predicted = np.asarray(reference, dtype=float), np.asarray(predicted, dtype=float)
    if reference.shape != (3,) or predicted.shape != (3,) or not np.all(np.isfinite(np.r_[reference, predicted])):
        raise ValueError("three finite aligned adenylate endpoints are required")
    assessment = evaluate_readiness(contract, root=root, frozen_initial_redox=frozen_initial_redox)
    ready = assessment.get("endpoint_accuracy_assessable") is True
    limits = contract["accuracy"]["absolute_endpoint_error_mM"]
    limits = limits if isinstance(limits, dict) else {}
    return [{"pool": pool, "nominal_absolute_endpoint_error_mM": float(abs(predicted[i] - reference[i])),
             "limit_mM": limits.get(pool) if positive_number(limits.get(pool)) else None,
             "passed": bool(abs(predicted[i] - reference[i]) <= limits[pool]) if ready else None}
            for i, pool in enumerate(POOLS)]
