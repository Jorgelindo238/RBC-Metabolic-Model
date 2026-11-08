"""Tests for cumulative Flux Learning Analysis validation gates."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fla_validation_v2 import (  # noqa: E402
    CandidateEvidence,
    CandidateStatus,
    TargetDataContract,
    ValidationThresholds,
    evaluate_candidate as _evaluate_candidate,
    pareto_front,
    validate_target_contracts,
)


LIMITS = {name: 0.5 for name in ("EGLC", "ELAC", "LAC", "ATP", "ADP", "AMP", "B23PG")}


def evaluate_candidate(evidence):
    return _evaluate_candidate(evidence, ValidationThresholds(max_absolute_target_nrmse=LIMITS))


def _passing_evidence() -> CandidateEvidence:
    return CandidateEvidence(
        candidate_id="candidate",
        training_datasets=("brodbar_train_J1_J10",),
        temporal_validation_datasets=("brodbar_holdout_J10_J46",),
        external_validation_datasets=("michel_control",),
        data_contract_complete=True,
        exact_balance_max_error_mM_per_day=1e-10,
        minimum_state_mM=0.0,
        independent_teachers_compatible=True,
        sensitivity_block_identifiable=True,
        primary_trajectory_baseline=1.0,
        primary_trajectory_candidate=0.75,
        primary_flux_baseline=1.0,
        primary_flux_candidate=0.80,
        all_primary_endpoints_improve=True,
        all_primary_slopes_improve=True,
        max_protected_nrmse_degradation=0.05,
        panel_mean_nrmse_degradation=0.02,
        panel_median_nrmse_degradation=0.01,
        strict_solver_invariant=True,
        temporal_holdout_improves=True,
        external_holdout_improves=True,
        complexity_supported_by_prediction=True,
        minimum_state_measured_before_clipping=True,
        continuous_unforced_replay=True,
        absolute_target_nrmse={name: 0.2 for name in LIMITS},
        raw_balance_max_error_mM_per_day=1e-10,
    )


def test_candidate_is_promoted_only_after_every_gate_passes() -> None:
    decision = evaluate_candidate(_passing_evidence())
    assert decision.status is CandidateStatus.PROMOTED
    assert decision.first_blocking_gate is None


def test_incompatible_teachers_reject_before_calibration_score() -> None:
    evidence = replace(_passing_evidence(), independent_teachers_compatible=False)
    decision = evaluate_candidate(evidence)
    assert decision.status is CandidateStatus.REJECTED
    assert decision.first_blocking_gate == "G1_structure"


def test_training_validation_leakage_is_a_hard_failure() -> None:
    evidence = replace(
        _passing_evidence(),
        temporal_validation_datasets=("brodbar_train_J1_J10",),
    )
    decision = evaluate_candidate(evidence)
    assert decision.status is CandidateStatus.REJECTED
    assert decision.first_blocking_gate == "G0_data"


def test_training_gain_without_temporal_transfer_stays_diagnostic() -> None:
    evidence = replace(_passing_evidence(), temporal_holdout_improves=False)
    decision = evaluate_candidate(evidence)
    assert decision.status is CandidateStatus.DIAGNOSTIC
    assert decision.first_blocking_gate == "G4_internal_validation"


def test_missing_external_evidence_retains_but_does_not_promote() -> None:
    evidence = replace(
        _passing_evidence(),
        external_validation_datasets=(),
        external_holdout_improves=None,
        complexity_supported_by_prediction=None,
    )
    decision = evaluate_candidate(evidence)
    assert decision.status is CandidateStatus.RETAINED
    assert decision.first_blocking_gate == "G5_external_validation"


@pytest.mark.parametrize("field,value", [
    ("minimum_state_measured_before_clipping", None),
    ("minimum_state_measured_before_clipping", False),
    ("raw_balance_max_error_mM_per_day", None),
    ("raw_balance_max_error_mM_per_day", 1e-3),
    ("exact_balance_max_error_mM_per_day", -1.0),
    ("data_contract_complete", "False"),
    ("training_datasets", ()),
    ("external_validation_datasets", ("brodbar_holdout_J10_J46",)),
])
def test_invalid_prerequisite_evidence_cannot_pass(field, value):
    assert evaluate_candidate(replace(_passing_evidence(), **{field: value})).status is CandidateStatus.REJECTED


@pytest.mark.parametrize("field,value", [
    ("absolute_target_nrmse", {**{name: 0.2 for name in LIMITS}, "ATP": 0.99}),
    ("absolute_target_nrmse", {}),
    ("absolute_target_nrmse", None),
    ("continuous_unforced_replay", False),
    ("continuous_unforced_replay", None),
    ("primary_trajectory_candidate", -0.5),
    ("temporal_validation_datasets", ()),
])
def test_relative_gain_alone_is_not_validation(field, value):
    assert evaluate_candidate(replace(_passing_evidence(), **{field: value})).status is CandidateStatus.DIAGNOSTIC


def test_missing_external_dataset_cannot_be_replaced_by_true_flag():
    result = evaluate_candidate(replace(_passing_evidence(), external_validation_datasets=()))
    assert result.status is CandidateStatus.RETAINED


def test_absolute_limits_must_be_declared_explicitly():
    assert _evaluate_candidate(_passing_evidence()).status is CandidateStatus.DIAGNOSTIC


def test_target_contract_requires_complete_unique_rows() -> None:
    contract = TargetDataContract(
        target="EGLC",
        dataset="brodbar",
        compartment="extracellular",
        quantity_basis="concentration",
        normalization="reported standardized mM",
        time_unit="day",
        volume_factor_source="unknown_not_applied",
        interpolation_policy="PCHIP",
        uncertainty_status="not reported",
        replicate_count=None,
        role="training",
    )
    assert validate_target_contracts([contract]) == (True, ())
    ok, failures = validate_target_contracts([contract, contract])
    assert ok is False
    assert any("duplicate" in failure for failure in failures)
    assert not validate_target_contracts([replace(contract, normalization=None)])[0]
    assert not validate_target_contracts([replace(contract, replicate_count=1.5)])[0]


def test_pareto_front_supports_min_and_max_objectives() -> None:
    rows = (
        {"loss": 1.0, "transfer": 0.8},
        {"loss": 1.2, "transfer": 0.7},
        {"loss": 0.9, "transfer": 0.6},
    )
    assert pareto_front(rows, {"loss": "min", "transfer": "max"}) == (0, 2)
    with pytest.raises(ValueError):
        pareto_front(rows, {"loss": "sideways"})
