"""Readiness is fail-closed and joint uncertainty is not independent by default."""

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fla_precalibration_readiness import (
    OBSERVATION_ORDER, covariance_matrix, endpoint_checks, evaluate_readiness,
    propagate_adenylate_uncertainty, require_scientific_contract,
)
from fla_coupled_energy_protocol import GROUPS, build_sensitivity_plan, resolved_parameters


@pytest.fixture
def complete_contract(tmp_path):
    path = tmp_path / "source.txt"
    path.write_text("synthetic test evidence, not biological evidence", encoding="ascii")
    evidence = [{"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]
    config = json.loads((ROOT / "config/fla_adenylate_redox_readiness.json").read_text())
    for name in ("lineage", "normalization", "time_origin", "uncertainty", "accuracy", "redox_prior"):
        config[name].update(verified=True, evidence_files=copy.deepcopy(evidence))
    config["lineage"].update(source_table_id="fixture", row_mapping={pool: f"fixture:{pool}" for pool in ("ATP", "ADP", "AMP")})
    config["normalization"].update(source_quantity_basis="mmol/L intracellular water", model_volume_basis="intracellular water",
                                   transformation="documented identity", scale_to_model_mM_by_pool={pool: 1. for pool in ("ATP", "ADP", "AMP")})
    config["time_origin"].update(source_days=[0., 3.], source_to_model_offset_day=1., biological_origin="collection")
    config["uncertainty"].update(covariance_mM2=(np.eye(6) * .01).tolist(), estimator="paired sample covariance", estimand="mean of biological units",
                                  estimator_type="paired_biological_replicates", biological_unit_count=3, technical_replicate_count=1)
    config["accuracy"].update(absolute_endpoint_error_mM={pool: .1 for pool in ("ATP", "ADP", "AMP")},
                              basis="predeclared_prediction_requirement", justification="test fixture policy only", independent_of_model_fit=True,
                              frozen_at="2020-01-01T00:00:00Z")
    config["redox_prior"].update(NAD_total_bounds_mM=[1., 3.], NADH_fraction_bounds=[.1, .9],
                                 sample_context="fixture context", volume_basis="intracellular water",
                                 source_pool_definition="free_reaction_available", model_pool_definition="free_reaction_available")
    return config


def assess(config):
    return evaluate_readiness(config, root=ROOT, frozen_initial_redox=[1., 1.])


def test_actual_readiness_is_blocked_without_invented_accuracy_or_priors():
    config = json.loads((ROOT / "config/fla_adenylate_redox_readiness.json").read_text())
    result = assess(config)
    assert not result["scientific_contract_complete"]
    assert result["optimization_allowed"] is False
    assert result["global_model_promotion_allowed"] is False
    assert len(result["blockers"]) == 13
    with pytest.raises(ValueError, match="readiness blocked"):
        require_scientific_contract(config, root=ROOT, frozen_initial_redox=[1., 1.])
    assert all(row["passed"] is None for row in endpoint_checks([1, 1, 1], [1, 1, 1], config, root=ROOT, frozen_initial_redox=[1., 1.]))


def test_complete_fixture_can_assess_endpoints_but_not_authorize_optimization(complete_contract):
    result = assess(complete_contract)
    assert result["scientific_contract_complete"]
    require_scientific_contract(complete_contract, root=ROOT, frozen_initial_redox=[1., 1.])
    assert result["optimization_allowed"] is False
    assert [row["passed"] for row in endpoint_checks([1, 1, 1], [1.01, 1.5, .5], complete_contract, root=ROOT, frozen_initial_redox=[1., 1.])] == [True, False, False]


@pytest.mark.parametrize("section", ["lineage", "normalization", "time_origin", "uncertainty", "accuracy", "redox_prior"])
def test_boolean_only_verification_cannot_satisfy_claims(section):
    config = json.loads((ROOT / "config/fla_adenylate_redox_readiness.json").read_text())
    config[section]["verified"] = True
    assert f"{section}:verified_evidence" in assess(config)["blockers"]


@pytest.mark.parametrize("section,key,value", [
    ("lineage", "row_mapping", {}), ("normalization", "scale_to_model_mM_by_pool", {"ATP": True, "ADP": 1, "AMP": 1}),
    ("normalization", "model_volume_basis", None), ("time_origin", "source_to_model_offset_day", 0),
    ("uncertainty", "covariance_mM2", None), ("uncertainty", "observation_order", list(reversed(OBSERVATION_ORDER))),
    ("accuracy", "absolute_endpoint_error_mM", {"ATP": .1, "ADP": .1}), ("accuracy", "independent_of_model_fit", False),
    ("accuracy", "frozen_at", "2999-01-01T00:00:00Z"), ("accuracy", "frozen_at", "2020-01-01"),
    ("redox_prior", "NAD_total_bounds_mM", [0, 3]), ("redox_prior", "NAD_total_bounds_mM", [3, 1]),
    ("redox_prior", "NADH_fraction_bounds", [0, 2]), ("redox_prior", "NAD_total_bounds_mM", [.01, .02]),
    ("redox_prior", "volume_basis", "whole blood volume"),
    ("uncertainty", "biological_unit_count", None), ("uncertainty", "technical_replicate_count", True),
    ("uncertainty", "cross_pool_and_cross_day_independence_assumed", True),
    ("redox_prior", "source_pool_definition", "total_extractable"), ("redox_prior", "model_pool_definition", None),
])
def test_missing_malformed_or_inapplicable_evidence_blocks(complete_contract, section, key, value):
    complete_contract[section][key] = value
    assert not assess(complete_contract)["scientific_contract_complete"]


def test_changed_supporting_file_invalidates_readiness(complete_contract):
    Path(complete_contract["lineage"]["evidence_files"][0]["path"]).write_text("changed fixture", encoding="ascii")
    assert not assess(complete_contract)["scientific_contract_complete"]


def test_uncertainty_keeps_cross_day_correlations_and_exact_total_variance():
    same_day = np.eye(3) * .01
    covariance = np.block([[same_day, same_day], [same_day, same_day]])
    result = propagate_adenylate_uncertainty([1, 1, 1, 2, 2, 2], covariance)
    np.testing.assert_allclose(result["total_variance_mM2"], [.03, .03])
    np.testing.assert_allclose(result["pool_change_covariance_mM2"], 0, atol=1e-15)
    assert result["total_change_variance_mM2"] == 0
    assert result["independence_assumed"] is False
    assert result["accuracy_limits_inferred"] is False


def test_cross_pool_covariance_changes_total_uncertainty():
    covariance = np.eye(6) * .01
    covariance[0, 1] = covariance[1, 0] = .005
    result = propagate_adenylate_uncertainty([1] * 6, covariance)
    assert result["total_variance_mM2"][0] == pytest.approx(.04)
    assert result["total_variance_mM2"][1] == pytest.approx(.03)
    gradient = np.array([1/6, 0, -1/6])
    assert result["energy_charge_variance_delta_method"][0] == pytest.approx(gradient @ covariance[:3, :3] @ gradient)


@pytest.mark.parametrize("covariance", [np.eye(3), np.full((6, 6), np.nan), -np.eye(6), np.eye(6) + np.triu(np.ones((6, 6)), 1), np.ones((6, 6)) - 2*np.eye(6), np.eye(6, dtype=bool), np.eye(6).astype(str)])
def test_invalid_covariance_is_not_repaired_or_replaced(covariance):
    with pytest.raises(ValueError):
        covariance_matrix(covariance)


@pytest.mark.parametrize("means", [[1] * 3, [-1] + [1] * 5, [0] * 6, [np.nan] + [1] * 5])
def test_invalid_mean_evidence_fails(means):
    with pytest.raises(ValueError):
        propagate_adenylate_uncertainty(means, np.eye(6))


def test_plan_is_reversible_bounded_and_not_executed():
    parameters = json.loads((ROOT / "output/ppp_numerical_audit_2026_10_05/fixed_parameters.json").read_text())
    values, provenance = resolved_parameters(parameters, ROOT / "src/equadiff_brodbar.py")
    assert provenance["vmax_VGAPDH"]["source"] == "hashed_kernel_default"
    plan = build_sensitivity_plan(values)
    assert plan["status"] == "prepared_not_executed"
    assert plan["single_group_case_count"] == 11 and plan["paired_group_case_count"] == 8
    assert plan["planned_replays_with_strict_ultrastrict"] == 38
    assert len({case["case_id"] for case in plan["cases"]}) == 19
    assert plan["cases"][0]["parameter_overrides"] == {}
    for case in plan["cases"]:
        assert case["parameter_overrides"].get("vmax_VHK", values["vmax_VHK"]) <= 5.0
        for group, scale in case["log_scales"].items():
            ratios = [case["parameter_overrides"][name] / values[name] for name in GROUPS[group]]
            np.testing.assert_allclose(ratios, np.exp(scale))
    assert "vmax_VGAPDH" not in parameters


def test_hk_seed_above_ceiling_fails_before_any_diagnostic():
    values = {name: 1. for members in GROUPS.values() for name in members}
    values["vmax_VHK"] = 5.01
    with pytest.raises(ValueError, match="ceiling"):
        build_sensitivity_plan(values)


def load_runner():
    spec = importlib.util.spec_from_file_location("prepare_readiness_test", ROOT / "scripts/prepare_adenylate_redox_readiness.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_require_ready_returns_two_and_never_runs_simulations(tmp_path):
    runner = load_runner()
    out_dir = tmp_path / "evidence"
    assert runner.main(["--out-dir", str(out_dir), "--require-ready"]) == 2
    manifest = json.loads((out_dir / "readiness_contract.json").read_text())
    assert manifest["simulations_executed"] == 0 and manifest["optimization_performed"] is False
    assert not (out_dir / "propagated_uncertainty.json").exists()
    rows = json.loads((out_dir / "joint_endpoint_checks.json").read_text())
    assert len(rows) == 24 and all(row["passed"] is None for row in rows)
    for path, digest in manifest["input_sha256"].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest
    with pytest.raises(FileExistsError):
        runner.main(["--out-dir", str(out_dir)])


def test_source_receipt_certifies_only_local_cells_and_preserves_external_lead():
    runner = load_runner()
    receipt = runner.source_receipt(ROOT / "src/Data_Bordbar_et_al_exp.xlsx", ROOT / "src/Initial_conditions_JA_Final.xls")
    assert receipt["adenylate_cells"]["ATP"]["J1_cell"] == "B9"
    assert receipt["adenylate_cells"]["AMP"]["J4_cell"] == "C5"
    assert receipt["historical_redox_cells"]["NAD"]["row_1_based"] == 84
    assert receipt["external_connection_followed"] is False
    assert receipt["literature_uncertainty_imported"] is False
    assert receipt["prior_bounds_inferred_from_historical_point"] is False


def test_result_booleans_cannot_replace_the_contract():
    with pytest.raises(ValueError):
        require_scientific_contract({"scientific_contract_complete": True}, root=ROOT, frozen_initial_redox=[1., 1.])


def test_tampered_limits_are_rechecked_not_authorized_by_old_assessment(complete_contract):
    assert assess(complete_contract)["scientific_contract_complete"]
    complete_contract["accuracy"]["absolute_endpoint_error_mM"] = {pool: float("inf") for pool in ("ATP", "ADP", "AMP")}
    rows = endpoint_checks([1, 1, 1], [999, 999, 999], complete_contract, root=ROOT, frozen_initial_redox=[1., 1.])
    assert all(row["passed"] is None and row["limit_mM"] is None for row in rows)
    with pytest.raises(ValueError):
        require_scientific_contract(complete_contract, root=ROOT, frozen_initial_redox=[1., 1.])


@pytest.mark.parametrize("scale", [1., 1e-15, 1e15])
def test_impossible_correlation_rejected_independently_of_covariance_scale(scale):
    covariance = np.eye(6) * scale
    covariance[0, 1] = covariance[1, 0] = 2 * scale
    with pytest.raises(ValueError):
        covariance_matrix(covariance)


def test_protocol_rejects_capacity_overflow_before_execution():
    values = {name: 1. for members in GROUPS.values() for name in members}
    values["vmax_VAK"] = 1.7e308
    with pytest.raises(ValueError, match="finite"):
        build_sensitivity_plan(values)
