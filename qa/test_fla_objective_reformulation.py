import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src")); sys.path.insert(0, str(ROOT/"scripts"))
from fla_calibration_observations import validate_series, validate_collection, residuals, fixed_error_scales, objective_metrics
from fla_balance_feasibility import integral_balance_screen


def series(kind="absolute_concentration"):
    return {"channel_id": "a", "metabolite": "GLC", "trajectory_id": "bag1", "cohort_id": "study1",
        "source_id": "raw.csv:GLC", "unit": "mM" if kind == "absolute_concentration" else "relative_signal",
        "volume_basis": "cell_phase", "compartment": "intracellular", "donor_id": None,
        "donor_identity_status": "unresolved", "measurement_type": kind, "normalization_status": "resolved",
        "linear_response_verified": True, "ratio_kind": "within_metabolite_time_course",
        "reference_index": 0, "time": [1., 4., 8.], "values": [1., 2., 3.]}


def test_observation_contract_preserves_unknown_identity_and_source_values():
    s = series(); before = copy.deepcopy(s)
    assert validate_series(s) == before and s == before


@pytest.mark.parametrize("field,value", [("unit", "mmol_per_bag"), ("volume_basis", "total_bag"),
    ("donor_identity_status", None), ("normalization_status", "unknown"), ("values", [1., None, 2.]),
    ("time", [1., 1., 8.]), ("compartment", "unknown")])
def test_unresolved_or_invalid_absolute_contract_fails(field, value):
    s = series(); s[field] = value
    with pytest.raises((ValueError, TypeError)): validate_series(s)


def test_relative_scale_uses_training_only_and_does_not_identify_absolute_scale():
    s = series("relative_signal"); s["values"] = [10., 20., 9999.]
    result = residuals([1., 2., 3.], s, mask=np.array([True, True, False]), absolute_scale=1., relative_scale=0.)
    assert result["nuisance_scale"] == 10 and np.all(result["residuals"] == 0)
    assert not result["absolute_scale_identified_by_this_channel"]
    scaled = residuals([2., 4., 6.], s, mask=np.array([True, True, False]), absolute_scale=1., relative_scale=0.)
    assert scaled["nuisance_scale"] == 5 and np.all(scaled["residuals"] == 0)
    held = residuals([1., 2., 3.], s, mask=np.array([False, False, True]), absolute_scale=1., relative_scale=0., nuisance_scale=10.)
    assert held["nuisance_scale"] == 10 and held["residuals"].tolist() == [-9969.]


@pytest.mark.parametrize("field,value", [("linear_response_verified", False), ("ratio_kind", "treatment_control"),
                                       ("unit", "mM"), ("normalization_status", "unresolved")])
def test_relative_observations_cannot_be_silently_promoted(field, value):
    s = series("relative_signal"); s[field] = value
    with pytest.raises(ValueError): validate_series(s)


def test_temporal_ratio_reference_is_not_an_independent_training_point():
    s = series("temporal_ratio"); s["unit"] = "fold_change"
    result = residuals([5., 10., 15.], s, mask=np.ones(3, bool), absolute_scale=.1, relative_scale=.2)
    assert result["residuals"].shape == (2,) and np.all(result["residuals"] == 0)
    assert result["reference_covariance_modelled"] is False


def test_collection_never_merges_different_sources_cohorts_or_donors():
    a = series(); b = series(); b["cohort_id"] = "study2"
    r = validate_collection([a, b])
    assert len(r["groups"]) == 2 and not r["auto_merge_cohorts"] and not r["ODE_initialization_complete"]
    with pytest.raises(ValueError): validate_collection([a, a])


def test_no_clipping_of_large_absolute_errors():
    s = series()
    r1 = residuals([1., 20., 30.], s, mask=np.ones(3, bool), absolute_scale=.1, relative_scale=.2)
    r2 = residuals([1., 200., 300.], s, mask=np.ones(3, bool), absolute_scale=.1, relative_scale=.2)
    assert np.linalg.norm(r2["residuals"]) > np.linalg.norm(r1["residuals"])


def test_scales_are_fixed_by_training_observations_not_predictions():
    y = np.array([[1., 2.], [10., 20.]])
    s = fixed_error_scales(y, absolute_fraction=.05, relative_fraction=.2, interpretation="engineering_normalization_not_assay_SD")
    a, b = objective_metrics(y*.9, y, s), objective_metrics(y*2, y, s)
    assert a["balanced_MSE"] < b["balanced_MSE"] and not b["assay_accuracy_established"]
    assert not s["estimated_from_model_residuals"] and a["worst_channel_MSE"] >= a["balanced_MSE"]


def test_minimax_does_not_allow_a_good_channel_to_cancel_a_bad_one():
    y = np.ones((2, 2)); s = {"absolute": [1., 1.], "relative": 0.}
    a = objective_metrics(np.array([[1., 1.], [11., 11.]]), y, s)
    b = objective_metrics(np.array([[9., 9.], [9., 9.]]), y, s)
    assert a["balanced_MSE"] < b["balanced_MSE"] and a["worst_channel_MSE"] > b["worst_channel_MSE"]


def test_exact_mass_balance_with_distinct_phase_volumes_and_forward_import():
    m = np.array([[-.58/.42], [1.]])
    y = np.array([[10., 10.-.58/.42], [1., 2.]])
    r = integral_balance_screen(m, y, [1., 4.], np.ones_like(y)*.1, reaction_bounds=[(0., None)])
    assert r["exact_measured_balances_feasible"] and r["minimum_working_error_multiplier"] == 0
    assert np.allclose(r["executed_extent_integrals"], [[1.]])


def test_infeasible_forward_balance_returns_shared_error_need_without_editing_data():
    y = np.array([[1., 0., 1.]])
    before = y.copy()
    r = integral_balance_screen([[1.]], y, [1., 4., 8.], np.ones_like(y)*.1, reaction_bounds=[(0., None)])
    assert not r["exact_measured_balances_feasible"] and r["minimum_working_error_multiplier"] == pytest.approx(10.)
    assert np.array_equal(y, before) and r["hypothetical_observation_adjustments_mM"][0][0] == 0
    assert not r["kinetic_or_ODE_feasibility_proved"]


def test_signed_relaxation_is_not_an_irreversibility_claim():
    r = integral_balance_screen([[1.]], [[1., 0.]], [1., 4.], [[.1, .1]], reaction_bounds=[(None, None)])
    assert r["exact_measured_balances_feasible"] and r["executed_extent_integrals"] == [[-1.]]


def test_zero_nominal_channel_is_not_given_a_fake_detection_limit():
    r = integral_balance_screen([[1.]], [[0., 0.]], [1., 4.], [[0., 0.]], reaction_bounds=[(0., None)])
    assert r["minimum_working_error_multiplier"] == 0 and r["hypothetical_observation_adjustments_mM"] == [[0., 0.]]


def test_zero_prediction_does_not_make_absolute_loss_depend_on_a_legacy_lognormal_domain():
    from run_fla_objective_reformulation import legacy_diagnostics
    p, y = np.ones((11, 2)), np.ones((11, 2))
    p[4] = 0
    legacy = legacy_diagnostics(p, y, {"fit_limits_mM": [2.]*13})
    assert legacy["passed"] and not legacy["lognormal_defined"] and legacy["score"] is None
    assert np.isfinite(objective_metrics(p, y, {"absolute": [1.]*11, "relative": .2})["balanced_MSE"])


def test_perfect_absolute_fit_is_not_rejected_by_zero_dispersion_diagnostic():
    from run_fla_objective_reformulation import legacy_diagnostics
    y = np.ones((11, 2))
    assert legacy_diagnostics(y, y, {"fit_limits_mM": [1.]*13})["score"] is None
    assert objective_metrics(y, y, {"absolute": [1.]*11, "relative": .2})["balanced_MSE"] == 0


@pytest.mark.parametrize("loss,expected", [("lognormal", 3), ("normalized", 3), ("minimax", 3)])
def test_fit_cache_counts_probes_and_never_filters_by_legacy_guards(tmp_path, monkeypatch, loss, expected):
    import run_fla_objective_reformulation as run
    d = json.loads((ROOT/"config/fla_objective_reformulation.json").read_text())
    f = {"design": d, "seed_log_investment": -.9, "primitive_factor_bounds": [.02, 1.],
        "primitive_capacities": {"vmax_VHK": 5., "vmax_VPFK": 2.5},
        "parameters": {"fixed": 4.}, "kinetics": {"conductance": .03}, "initial": [1.]*113+[7.2]}
    obs = {"time": [1., 4., 8.], "values": {p:[1., 1., 1.] for p in run.POOLS}}
    run.write(tmp_path/"observations.json", obs)
    monkeypatch.setattr(run, "verify_inputs", lambda out:f)
    def evaluate(x, frozen, end, loss0, times, target):
        value = float(np.sum(np.asarray(x)**2))
        return {"valid": True, "log_factors": np.asarray(x).tolist(), "predictions": target.tolist(),
            "objective_value": value, "metrics": {"channel_MSE": [value]*11},
            "legacy13": {"passed": False}}, SimpleNamespace(t=np.array([1., end]), y=np.array([f["initial"], f["initial"]]).T)
    monkeypatch.setattr(run, "evaluate", evaluate)
    def minimize(fun, x, **kw):
        fun(x); kw["jac"](x)
        if loss == "minimax": kw["constraints"][0]["fun"](x); kw["constraints"][0]["jac"](x)
        return SimpleNamespace(x=x, success=True, message="toy")
    monkeypatch.setattr(run, "minimize", minimize)
    r = run.fit_one(str(tmp_path), "toy", loss, [-.9, -.9], 10., False)
    assert r["actual_objective_integrations"] == expected and not r["legacy13"]["passed"]
    assert not r["legacy13_used_to_filter_selection"] and r["parameters"]["fixed"] == 4.
    assert run.fit_one(str(tmp_path), "toy", loss, [-.9, -.9], 10., True) == r
