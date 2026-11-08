"""Latent observation helpers never change measured states or fabricate anchors."""

import ast
import copy
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from fla_latent_inference import (balance_identifiability, paired_log_residual, reconstruct_log_variance,
                                 reconstruct_relative, redox_initial_state, relative_log_residual)
from prepare_fla_latent_inference import CONFIG, kernel_audit, parse_reference_rows, run, validate_design


@pytest.fixture
def relative_contract():
    return {"ratio_kind": "within_metabolite_time_course", "anchor_context": "same_donor",
            **{key: True for key in ("linear_response_verified", "normalization_factors_resolved", "same_pool_definition",
                                    "same_volume_basis", "same_metabolite", "exact_anchor_day_verified")}}


def test_reconstruction_keeps_estimate_classification(relative_contract):
    result = reconstruct_relative([10., 7.5], 10., 1.2, contract=relative_contract)
    np.testing.assert_allclose(result["estimated_concentration_mM"], [1.2, .9])
    assert result["measurement_type"] == "anchored_estimate_not_absolute_measurement"
    assert result["uncertainty_propagated"] is False


@pytest.mark.parametrize("key", ["linear_response_verified", "normalization_factors_resolved", "same_pool_definition",
                                 "same_volume_basis", "same_metabolite", "exact_anchor_day_verified"])
def test_unknown_contract_never_silently_converts(relative_contract, key):
    relative_contract[key] = False
    with pytest.raises(ValueError):
        reconstruct_relative([10., 7.5], 10., 1.2, contract=relative_contract)


def test_contemporaneous_control_ratio_not_a_time_course(relative_contract):
    relative_contract["ratio_kind"] = "same_day_treatment_control"
    with pytest.raises(ValueError):
        reconstruct_relative([1., 2.], 1., 1., contract=relative_contract)


def test_external_anchor_remains_a_prior(relative_contract):
    relative_contract["anchor_context"] = "external_prior"
    result = reconstruct_relative([1., 2.], 1., 1., contract=relative_contract)
    assert result["anchor_context"] == "external_prior"
    assert "not_absolute_measurement" in result["measurement_type"]


@pytest.mark.parametrize("signal,reference,anchor", [([1., -1.], 1., 1.), ([1., np.nan], 1., 1.),
    ([1., 2.], 0., 1.), ([1., 2.], 1., 0.), ([True, False], 1., 1.), ([1., True], 1., 1.), ([1., 2.], [1., 2.], 1.)])
def test_invalid_inputs_not_repaired(relative_contract, signal, reference, anchor):
    with pytest.raises(ValueError):
        reconstruct_relative(signal, reference, anchor, contract=relative_contract)


def test_relative_likelihood_cancels_constant_scale():
    np.testing.assert_allclose(relative_log_residual([1., 2., 3.], [20., 40., 60.], reference_index=0), 0., atol=1e-15)


def test_pair_likelihood_uses_same_day_control():
    np.testing.assert_allclose(paired_log_residual([2., 6.], [1., 2.], [2., 3.]), 0., atol=1e-15)


@pytest.mark.parametrize("function,args", [(relative_log_residual, ([0., 1.], [1., 2.])),
                                           (paired_log_residual, ([1.], [0.], [1.]))])
def test_nonpositive_log_observations_require_censoring_not_epsilon(function, args):
    with pytest.raises(ValueError):
        function(*args, **({"reference_index": 0} if function == relative_log_residual else {}))


def test_anchor_shared_reference_covariance_is_retained():
    covariance = np.array([[.01, 0., 0.], [0., .04, .04], [0., .04, .04]])
    assert reconstruct_log_variance(covariance) == pytest.approx(.01)
    assert reconstruct_log_variance(np.diag([.01, .04, .04])) == pytest.approx(.09)


@pytest.mark.parametrize("covariance", [np.ones((2, 2)), [[1., 2., 0.], [2., 1., 0.], [0., 0., 1.]],
                                       [[1., 0., 0.], [1., 1., 0.], [0., 0., 1.]]])
def test_invalid_covariance_not_made_independent(covariance):
    with pytest.raises(ValueError):
        reconstruct_log_variance(covariance)


def redox_arguments():
    return dict(NAD_total=.06534, NADH_fraction=.00024/.06534, NADP_total=.0653647,
                NADPH_fraction=.0653/.0653647, measured_pools={"ATP"})


def test_redox_parameterization_changes_only_unobserved_redox():
    names = ["ATP", "NAD", "NADH", "NADP", "NADPH", "pHi"]
    initial = np.array([.93, 1., 1., 1., 1., 6.95])
    candidate = redox_initial_state(initial, names, **redox_arguments())
    np.testing.assert_array_equal(initial, [.93, 1., 1., 1., 1., 6.95])
    np.testing.assert_array_equal(candidate[[0, 5]], initial[[0, 5]])
    np.testing.assert_allclose(candidate[1:5], [.0651, .00024, .0000647, .0653])


@pytest.mark.parametrize("key,value", [("NAD_total", 0.), ("NADH_fraction", -1.), ("NADPH_fraction", 1.1),
                                       ("measured_pools", {"ATP", "NAD"})])
def test_redox_invalid_or_measured_pool_changes_rejected(key, value):
    arguments = redox_arguments()
    arguments[key] = value
    with pytest.raises(ValueError):
        redox_initial_state(np.ones(5), ["ATP", "NAD", "NADH", "NADP", "NADPH"], **arguments)


def test_balance_nullspace_not_a_latent_identifiability_claim():
    result = balance_identifiability([[1., 1., 0.], [0., 0., 1.]], [0, 1])
    assert result["rank"] == 2 and result["flux_nullity"] == 1
    assert result["individually_identifiable_columns"] == [2]
    assert result["dynamic_latent_identifiability_established"] is False


def test_preparation_design_exact_and_no_ode_or_optimizer():
    design = json.loads(CONFIG.read_text())
    assert validate_design(design) is design
    assert design["supported_bounds"] is None and design["observation_covariance"] is None
    tree = ast.parse((ROOT / "scripts/prepare_fla_latent_inference.py").read_text())
    calls = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert not {"solve_ivp", "minimize", "least_squares", "simulate"} & calls


@pytest.mark.parametrize("key,value", [("schema_version", True), ("ode_execution_allowed", True),
    ("latent_estimation_allowed", True), ("measured_J1_changes_allowed", True),
    ("kinetic_optimization_allowed", True), ("supported_bounds", {"NAD_total": [.01, 1.]})])
def test_scope_expansion_requires_new_protocol(key, value):
    design = copy.deepcopy(json.loads(CONFIG.read_text()))
    design[key] = value
    with pytest.raises(ValueError):
        validate_design(design)


def test_output_preservation_guard(tmp_path):
    with pytest.raises(FileExistsError):
        run(tmp_path)


def test_kernel_has_no_explicit_free_total_ATP_operator():
    audit = kernel_audit(ROOT / "src/equadiff_brodbar.py")
    assert audit["state_registry"]["ATP"] == 35
    assert audit["transport_volume_scaling_mode"] == "legacy_equal_concentration"
    assert audit["explicit_ATP_binding_states"] == []
    assert audit["ATP_free_total_observation_mapping_implemented"] is False
    assert audit["explicit_Pi_state"] is False and audit["explicit_Mg_state"] is False


def test_local_nishino_table_reference_units_and_free_total_distinction():
    path = Path(json.loads(CONFIG.read_text())["nishino_supplement"])
    if not path.exists():
        pytest.skip("user-provided PDF is local evidence, not a repository fixture")
    rows = parse_reference_rows(path)
    by_label = {row["canonical_label"]: row for row in rows}
    for label, value in {"ATP(free)": .0551, "ATP(total)": 1.91, "NAD": .0651,
                         "NADH": .00024, "NADP": .0000647, "NADPH": .0653,
                         "1,3-BPG": .000215}.items():
        assert by_label[label]["value_mM_dimensional_only"] == pytest.approx(value)
        assert by_label[label]["role"] == "model_reference_point_not_measured_anchor"
        assert by_label[label]["applied_to_model"] is False
