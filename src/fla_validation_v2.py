"""Cumulative validation gates for Flux Learning Analysis candidates.

This module contains no optimizer or ODE dependency. It turns already-computed
evidence into an auditable candidate status and keeps training, temporal
validation, and external validation logically separate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

import numpy as np


class CandidateStatus(str, Enum):
    REJECTED = "rejected"
    DIAGNOSTIC = "diagnostic"
    RETAINED = "retained_for_external_validation"
    PROMOTED = "promoted"


@dataclass(frozen=True)
class ValidationThresholds:
    max_balance_error_mM_per_day: float = 1e-7
    min_state_mM: float = -1e-10
    min_primary_trajectory_improvement: float = 0.20
    min_primary_flux_improvement: float = 0.15
    max_protected_nrmse_degradation: float = 0.10
    max_panel_mean_nrmse_degradation: float = 0.05
    max_panel_median_nrmse_degradation: float = 0.05
    # These limits must be specified before fitting, in the declared nRMSE units.
    max_absolute_target_nrmse: Mapping[str, float] | None = None
    required_absolute_targets: tuple[str, ...] = (
        "EGLC", "ELAC", "LAC", "ATP", "ADP", "AMP", "B23PG",
    )


@dataclass(frozen=True)
class TargetDataContract:
    target: str
    dataset: str
    compartment: str
    quantity_basis: str
    normalization: str
    time_unit: str
    volume_factor_source: str
    interpolation_policy: str
    uncertainty_status: str
    replicate_count: int | None
    role: str


@dataclass(frozen=True)
class CandidateEvidence:
    candidate_id: str
    training_datasets: tuple[str, ...]
    temporal_validation_datasets: tuple[str, ...]
    external_validation_datasets: tuple[str, ...]
    data_contract_complete: bool
    exact_balance_max_error_mM_per_day: float
    minimum_state_mM: float
    independent_teachers_compatible: bool | None
    sensitivity_block_identifiable: bool
    primary_trajectory_baseline: float
    primary_trajectory_candidate: float
    primary_flux_baseline: float
    primary_flux_candidate: float
    all_primary_endpoints_improve: bool
    all_primary_slopes_improve: bool
    max_protected_nrmse_degradation: float
    panel_mean_nrmse_degradation: float
    panel_median_nrmse_degradation: float
    strict_solver_invariant: bool
    temporal_holdout_improves: bool | None
    external_holdout_improves: bool | None
    complexity_supported_by_prediction: bool | None
    minimum_state_measured_before_clipping: bool | None = None
    continuous_unforced_replay: bool | None = None
    absolute_target_nrmse: Mapping[str, float] | None = None
    raw_balance_max_error_mM_per_day: float | None = None


@dataclass(frozen=True)
class GateCheck:
    gate: str
    name: str
    passed: bool | None
    measured: Any
    requirement: str


@dataclass(frozen=True)
class ValidationDecision:
    candidate_id: str
    status: CandidateStatus
    checks: tuple[GateCheck, ...]
    first_blocking_gate: str | None
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


def _relative_improvement(baseline: float, candidate: float) -> float:
    if (not np.isfinite(baseline) or not np.isfinite(candidate)
            or baseline <= 0.0 or candidate < 0.0):
        return float("nan")
    return float((baseline - candidate) / baseline)


def _datasets_are_disjoint(evidence: CandidateEvidence) -> bool:
    training = set(evidence.training_datasets)
    temporal = set(evidence.temporal_validation_datasets)
    external = set(evidence.external_validation_datasets)
    if not training or any(
        not isinstance(name, str) or not name.strip()
        for name in training | temporal | external
    ):
        return False
    return not bool(training & temporal or training & external or temporal & external)


def _absolute_target_guard(
    evidence: CandidateEvidence, thresholds: ValidationThresholds,
) -> bool | None:
    errors = evidence.absolute_target_nrmse
    limits = thresholds.max_absolute_target_nrmse
    if errors is None or limits is None:
        return None
    if not limits or not set(thresholds.required_absolute_targets).issubset(limits):
        return False
    return all(
        name in errors
        and np.isfinite(limit) and limit > 0.0
        and np.isfinite(errors[name]) and 0.0 <= errors[name] <= limit
        for name, limit in limits.items()
    )


def _gate_passes(checks: Sequence[GateCheck], gate: str) -> bool | None:
    selected = [check.passed for check in checks if check.gate == gate]
    if any(value is not None and value is not True for value in selected):
        return False
    if not selected or any(value is None for value in selected):
        return None
    return all(selected)


def evaluate_candidate(
    evidence: CandidateEvidence,
    thresholds: ValidationThresholds = ValidationThresholds(),
) -> ValidationDecision:
    """Evaluate cumulative Gates 0-5 and return a non-ambiguous status."""
    trajectory_improvement = _relative_improvement(
        evidence.primary_trajectory_baseline,
        evidence.primary_trajectory_candidate,
    )
    flux_improvement = _relative_improvement(
        evidence.primary_flux_baseline,
        evidence.primary_flux_candidate,
    )
    checks = (
        GateCheck(
            "G0_data",
            "target_data_contracts_complete",
            evidence.data_contract_complete,
            evidence.data_contract_complete,
            "all target unit, compartment, normalization, interpolation, and uncertainty fields declared",
        ),
        GateCheck(
            "G0_data",
            "training_validation_dataset_disjointness",
            _datasets_are_disjoint(evidence),
            {
                "training": evidence.training_datasets,
                "temporal": evidence.temporal_validation_datasets,
                "external": evidence.external_validation_datasets,
            },
            "no dataset identifier appears in both training and validation",
        ),
        GateCheck(
            "G1_structure",
            "exact_balance_closure",
            bool(
                np.isfinite(evidence.exact_balance_max_error_mM_per_day)
                and evidence.exact_balance_max_error_mM_per_day >= 0.0
                and evidence.exact_balance_max_error_mM_per_day
                <= thresholds.max_balance_error_mM_per_day
            ),
            evidence.exact_balance_max_error_mM_per_day,
            f"<= {thresholds.max_balance_error_mM_per_day:g} mM/day",
        ),
        GateCheck(
            "G1_structure",
            "raw_balance_closure_without_numerical_damping",
            (None if evidence.raw_balance_max_error_mM_per_day is None else bool(
                np.isfinite(evidence.raw_balance_max_error_mM_per_day)
                and 0.0 <= evidence.raw_balance_max_error_mM_per_day
                <= thresholds.max_balance_error_mM_per_day
            )),
            evidence.raw_balance_max_error_mM_per_day,
            "S v plus declared physical sources matches the derivative without numerical repair terms",
        ),
        GateCheck(
            "G1_structure",
            "nonnegative_states",
            bool(
                np.isfinite(evidence.minimum_state_mM)
                and evidence.minimum_state_mM >= thresholds.min_state_mM
            ),
            evidence.minimum_state_mM,
            f">= {thresholds.min_state_mM:g} mM before declared floor handling",
        ),
        GateCheck(
            "G1_structure",
            "positivity_evidence_before_clipping",
            evidence.minimum_state_measured_before_clipping,
            evidence.minimum_state_measured_before_clipping,
            "minimum reported on raw solver output, before clipping or display floors",
        ),
        GateCheck(
            "G1_structure",
            "independent_teacher_compatibility",
            evidence.independent_teachers_compatible,
            evidence.independent_teachers_compatible,
            "independent teachers have compatible signs and integrated magnitudes",
        ),
        GateCheck(
            "G2_identifiability",
            "active_sensitivity_block_identifiable",
            evidence.sensitivity_block_identifiable,
            evidence.sensitivity_block_identifiable,
            "active parameter combination has adequate sensitivity rank and bounded profile",
        ),
        GateCheck(
            "G3_calibration",
            "primary_trajectory_improvement",
            bool(
                np.isfinite(trajectory_improvement)
                and trajectory_improvement
                >= thresholds.min_primary_trajectory_improvement
            ),
            trajectory_improvement,
            f">= {thresholds.min_primary_trajectory_improvement:.0%}",
        ),
        GateCheck(
            "G3_calibration",
            "primary_flux_improvement",
            bool(
                np.isfinite(flux_improvement)
                and flux_improvement >= thresholds.min_primary_flux_improvement
            ),
            flux_improvement,
            f">= {thresholds.min_primary_flux_improvement:.0%}",
        ),
        GateCheck(
            "G3_calibration",
            "primary_endpoints_improve",
            evidence.all_primary_endpoints_improve,
            evidence.all_primary_endpoints_improve,
            "all declared primary endpoint errors improve",
        ),
        GateCheck(
            "G3_calibration",
            "primary_slopes_improve",
            evidence.all_primary_slopes_improve,
            evidence.all_primary_slopes_improve,
            "all declared primary slope errors improve",
        ),
        GateCheck(
            "G4_internal_validation",
            "absolute_protected_target_accuracy",
            _absolute_target_guard(evidence, thresholds),
            {"errors": evidence.absolute_target_nrmse,
             "limits": thresholds.max_absolute_target_nrmse},
            "all protected targets meet predeclared absolute nRMSE limits",
        ),
        GateCheck(
            "G4_internal_validation",
            "continuous_unforced_replay",
            evidence.continuous_unforced_replay,
            evidence.continuous_unforced_replay,
            "continuous ODE replay without observation resets or curve forcing",
        ),
        GateCheck(
            "G4_internal_validation",
            "protected_target_guard",
            bool(
                np.isfinite(evidence.max_protected_nrmse_degradation)
                and evidence.max_protected_nrmse_degradation
                <= thresholds.max_protected_nrmse_degradation
            ),
            evidence.max_protected_nrmse_degradation,
            f"<= {thresholds.max_protected_nrmse_degradation:.0%} relative nRMSE degradation",
        ),
        GateCheck(
            "G4_internal_validation",
            "panel_mean_guard",
            bool(
                np.isfinite(evidence.panel_mean_nrmse_degradation)
                and evidence.panel_mean_nrmse_degradation
                <= thresholds.max_panel_mean_nrmse_degradation
            ),
            evidence.panel_mean_nrmse_degradation,
            f"<= {thresholds.max_panel_mean_nrmse_degradation:.0%} relative nRMSE degradation",
        ),
        GateCheck(
            "G4_internal_validation",
            "panel_median_guard",
            bool(
                np.isfinite(evidence.panel_median_nrmse_degradation)
                and evidence.panel_median_nrmse_degradation
                <= thresholds.max_panel_median_nrmse_degradation
            ),
            evidence.panel_median_nrmse_degradation,
            f"<= {thresholds.max_panel_median_nrmse_degradation:.0%} relative nRMSE degradation",
        ),
        GateCheck(
            "G4_internal_validation",
            "strict_solver_invariance",
            evidence.strict_solver_invariant,
            evidence.strict_solver_invariant,
            "selection and scientific conclusion survive strict-solver replay",
        ),
        GateCheck(
            "G4_internal_validation",
            "forward_temporal_holdout",
            (evidence.temporal_holdout_improves
             if evidence.temporal_validation_datasets else None),
            evidence.temporal_holdout_improves,
            "later temporal block improves without refitting",
        ),
        GateCheck(
            "G5_external_validation",
            "external_dataset_or_intervention",
            (evidence.external_holdout_improves
             if evidence.external_validation_datasets else None),
            evidence.external_holdout_improves,
            "at least one frozen external dataset or intervention improves",
        ),
        GateCheck(
            "G5_external_validation",
            "complexity_supported_by_prediction",
            evidence.complexity_supported_by_prediction,
            evidence.complexity_supported_by_prediction,
            "added parameter or reaction complexity improves held-out prediction",
        ),
    )

    prerequisite_gates = ("G0_data", "G1_structure", "G2_identifiability")
    calibration_gates = prerequisite_gates + ("G3_calibration",)
    internal_gates = calibration_gates + ("G4_internal_validation",)
    for gate in prerequisite_gates:
        if _gate_passes(checks, gate) is not True:
            return ValidationDecision(
                evidence.candidate_id,
                CandidateStatus.REJECTED,
                checks,
                gate,
                f"{gate} failed or is incomplete; kinetic promotion is blocked.",
            )
    for gate in calibration_gates[len(prerequisite_gates) :]:
        if _gate_passes(checks, gate) is not True:
            return ValidationDecision(
                evidence.candidate_id,
                CandidateStatus.DIAGNOSTIC,
                checks,
                gate,
                f"{gate} did not pass; retain only as a diagnostic hypothesis.",
            )
    for gate in internal_gates[len(calibration_gates) :]:
        if _gate_passes(checks, gate) is not True:
            return ValidationDecision(
                evidence.candidate_id,
                CandidateStatus.DIAGNOSTIC,
                checks,
                gate,
                f"{gate} did not pass; the training gain does not transfer through time.",
            )
    if _gate_passes(checks, "G5_external_validation") is not True:
        return ValidationDecision(
            evidence.candidate_id,
            CandidateStatus.RETAINED,
            checks,
            "G5_external_validation",
            "Internal evidence passed; external predictive evidence is absent or insufficient.",
        )
    return ValidationDecision(
        evidence.candidate_id,
        CandidateStatus.PROMOTED,
        checks,
        None,
        "All cumulative FLA validation gates passed.",
    )


def validate_target_contracts(
    contracts: Sequence[TargetDataContract],
) -> tuple[bool, tuple[str, ...]]:
    """Check completeness and uniqueness of target/dataset/role declarations."""
    failures: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    required_text = (
        "target",
        "dataset",
        "compartment",
        "quantity_basis",
        "normalization",
        "time_unit",
        "volume_factor_source",
        "interpolation_policy",
        "uncertainty_status",
        "role",
    )
    for index, contract in enumerate(contracts):
        for field in required_text:
            value = getattr(contract, field)
            if not isinstance(value, str) or not value.strip():
                failures.append(f"row {index}: missing {field}")
        if contract.replicate_count is not None and (
            type(contract.replicate_count) is not int or contract.replicate_count < 1
        ):
            failures.append(f"row {index}: replicate_count must be positive or unknown")
        key = (contract.target, contract.dataset, contract.role)
        if key in seen:
            failures.append(f"row {index}: duplicate target/dataset/role {key}")
        seen.add(key)
    if not contracts:
        failures.append("no target data contracts declared")
    return not failures, tuple(failures)


def pareto_front(
    rows: Sequence[Mapping[str, float]],
    objectives: Mapping[str, str],
) -> tuple[int, ...]:
    """Return non-dominated row indices for declared min/max objectives."""
    if not rows:
        return ()
    if not objectives:
        raise ValueError("at least one Pareto objective is required")
    keys = tuple(objectives)
    directions = []
    for key in keys:
        direction = objectives[key]
        if direction not in {"min", "max"}:
            raise ValueError(f"unsupported Pareto direction for {key}: {direction}")
        directions.append(1.0 if direction == "min" else -1.0)
    values = np.asarray(
        [[float(row[key]) for key in keys] for row in rows],
        dtype=float,
    ) * np.asarray(directions, dtype=float)
    if not np.all(np.isfinite(values)):
        raise ValueError("Pareto objectives must be finite")
    retained: list[int] = []
    for index, candidate in enumerate(values):
        dominated = any(
            other_index != index
            and np.all(other <= candidate)
            and np.any(other < candidate)
            for other_index, other in enumerate(values)
        )
        if not dominated:
            retained.append(index)
    return tuple(retained)
