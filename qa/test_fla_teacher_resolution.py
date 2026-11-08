"""Resolution, temporal weights and training-only smoothing remain scientifically isolated."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from equadiff_brodbar import BRODBAR_METABOLITE_MAP
from fla_synthetic_recovery import fit_capacities, unit_capacity_basis
from fla_teacher_resolution import (
    TrainingCurves, canonical_partition, fast_transport_basis, integrated_problem, method_names,
    time_grid, validate_design, weighted_problem,
)
from fla_working_reference import load_working_reference, reference_options
from run_fla_teacher_resolution import run
from verify_fla_teacher_resolution import analytic_fit, independent_metrics


@pytest.fixture
def design():
    return json.loads((ROOT / "config/fla_teacher_resolution.json").read_text())


@pytest.fixture
def context():
    source = ROOT / "output/ppp_numerical_audit_2026_10_05"
    initial = pd.read_csv(source / "fixed_initial_state.csv", float_precision="round_trip").initial_value.to_numpy()
    params = json.loads((source / "fixed_parameters.json").read_text())
    ode, _ = reference_options(load_working_reference())
    return initial, params, ode


def test_preregistered_subset_and_counts_are_not_selected_using_results(design):
    assert validate_design(design) is design
    assert len(method_names(design)) == 15
    assert (len(design["noise_seeds"])+1) * len(method_names(design)) == 90
    assert (len(design["replay_noise_seeds"])+1) * len(design["replay_methods"]) * 2 == 32
    assert design["biological_calibration_allowed"] is False


@pytest.mark.parametrize("key,value", [
    ("global_model_promotion_allowed", True), ("biological_calibration_allowed", True),
    ("change_scientific_readiness_contract", True), ("noise_seeds", [1, 2, 3]),
    ("noise_seeds", [1, 2, 3, 4, 4]), ("uniform_grid_counts", [401, 101]),
    ("uniform_grid_counts", [101, 1601]), ("aligned_quadrature_orders", [2, 8]),
    ("replay_methods", ["best_case"]), ("replay_noise_seeds", [987654321]),
    ("smoothing", "selected_using_true_parameter_error"), ("noise_coefficient_of_variation", float("nan")),
])
def test_invalid_design_fails_closed(design, key, value):
    design[key] = value
    with pytest.raises(ValueError):
        validate_design(design)


def test_quadrature_is_observation_aligned_and_weights_have_time_units():
    observations = np.asarray([1., 1.1, 4., 8., 22.])
    nodes, weights, intervals = time_grid(observations, order=4)
    assert np.all(nodes > observations[0]) and np.all(nodes < observations[-1])
    for i, (start, end) in enumerate(zip(observations[:-1], observations[1:])):
        assert np.all((nodes[intervals == i] > start) & (nodes[intervals == i] < end))
        np.testing.assert_allclose(weights[intervals == i].sum(), end-start)
    np.testing.assert_allclose(weights.sum(), 21.)
    np.testing.assert_allclose(weights @ nodes**2, (22.**3-1.)/3, rtol=1e-12)


def test_uniform_trapezoid_has_half_endpoint_weights():
    nodes, weights, _ = time_grid([1., 4., 22.], count=401)
    np.testing.assert_allclose(weights.sum(), 21.)
    assert weights[0] == weights[1]/2 and weights[-1] == weights[-2]/2
    assert nodes[0] == 1. and nodes[-1] == 22.


def test_temporal_weighting_recovers_known_capacities():
    basis = np.asarray([[.2, .3, .1], [.4, .2, .5]])
    target = np.asarray([1.7, .8])[:, None]*basis
    weighted_b, weighted_y = weighted_problem(basis, target, [.1, 20., .9])
    fit = fit_capacities(weighted_b, weighted_y, [2., 1.], [.25, 2.], [[.6, 1.4], [1.4, .6]])
    np.testing.assert_allclose(fit["capacities"], [1.7, .8], rtol=1e-9)
    with pytest.raises(ValueError):
        weighted_problem(basis, target, [.1, 0., .9])


@pytest.mark.parametrize("mode", ["raw", "smooth"])
def test_reconstruction_preserves_known_initial_anchor_and_has_no_holdout_access(mode):
    time = np.linspace(1., 22., 21)
    values = np.asarray([10.*np.exp(-.01*(time-1)), 1.+.1*(time-1), 1.+.02*(time-1), 2.+.03*(time-1)])
    old = values.copy()
    curves = TrainingCurves(time, values, training_end=22., mode=mode, noise_cv=.005)
    actual, derivative = curves.evaluate(np.asarray([1., 4., 22.]))
    np.testing.assert_allclose(actual[:, 0], values[:, 0], rtol=1e-12, atol=1e-12)
    np.testing.assert_array_equal(values, old)
    assert np.all(actual > 0) and np.all(np.isfinite(derivative))
    with pytest.raises(ValueError, match="holdout"):
        curves.evaluate([22.1])
    with pytest.raises(ValueError):
        TrainingCurves(np.r_[time, 25.], np.c_[values, values[:, -1]], training_end=22., mode=mode, noise_cv=.005)


def test_log_smoothing_derivative_chain_rule_and_receipt():
    time = np.linspace(1., 22., 21)
    values = np.exp(np.asarray([.01, .02, -.03, -.01])[:, None]*(time-1))
    curves = TrainingCurves(time, values, training_end=22., mode="smooth", noise_cv=0.)
    query = np.asarray([2., 10., 21.])
    _, derivative = curves.evaluate(query)
    upper, _ = curves.evaluate(query+1e-5)
    lower, _ = curves.evaluate(query-1e-5)
    np.testing.assert_allclose(derivative, (upper-lower)/2e-5, rtol=1e-6, atol=1e-9)
    receipt = curves.receipt()
    assert receipt["smoothing_selection"] == "GCV_training_only"
    assert receipt["initial_anchor_is_exact_constrained_spline_optimum"] is False
    assert len(receipt["coefficient_receipts"]) == 4


def test_log_smoothing_never_floors_zero_observations():
    values = np.ones((4, 5))
    values[0, 3] = 0.
    with pytest.raises(ValueError, match="do not insert floors"):
        TrainingCurves([1., 4., 8., 15., 22.], values, training_end=22., mode="smooth", noise_cv=.005)


def test_fast_basis_matches_full_kernel_for_floor_boundary_and_signed_rates(context):
    initial, params, ode = context
    states = np.repeat(initial[:, None], 5, axis=1)
    states[BRODBAR_METABOLITE_MAP["EGLC"], 1] = 0.
    states[BRODBAR_METABOLITE_MAP["GLC"], 2] = 0.
    states[BRODBAR_METABOLITE_MAP["LAC"], 3] = .0001
    states[BRODBAR_METABOLITE_MAP["LAC"], 4] = 0.
    time = np.linspace(1., 22., 5)
    fast = fast_transport_basis(time, states, params, ode)
    direct = unit_capacity_basis(time, states, params, ode)
    np.testing.assert_allclose(fast["basis"], direct, rtol=1e-12, atol=1e-12)
    assert np.any(fast["native"] < 0) and np.any(fast["factors"] < 1.)
    np.testing.assert_array_equal(fast["basis"][:, -1][1:], [0.])


def test_fast_basis_requires_explicit_affinities_and_no_teacher_forcing(context):
    initial, params, ode = context
    with pytest.raises(ValueError, match="forcing"):
        fast_transport_basis([1.], initial[:, None], dict(params, kinetic_family_VEGLC="teacher_curve_flux"), ode)
    no_affinity = dict(params)
    del no_affinity["km_LAC"]
    with pytest.raises(ValueError, match="affinities"):
        fast_transport_basis([1.], initial[:, None], no_affinity, ode)
    with pytest.raises(ValueError, match="unforced"):
        fast_transport_basis([1.], initial[:, None], params, dict(ode, positivity_policy="legacy"))


def test_integrated_teacher_retains_raw_observed_increments_with_smoothed_inputs(context):
    initial, params, ode = context
    time = np.asarray([1., 4., 8., 15., 22.])
    values = np.asarray([[10., 9.9, 8.1, 7., 6.8], [1., 1.8, 2.2, 3.9, 4.1], [1., 1.1, 1.2, 1.5, 1.7], [2., 2.2, 2.5, 2.8, 3.]])
    curve = TrainingCurves(time, values, training_end=22., mode="smooth", noise_cv=.005)
    basis, targets = integrated_problem(curve, initial, params, ode, order=8)
    np.testing.assert_allclose(targets, np.asarray([-1., 1.])[:, None]*np.diff(values[:2], axis=1))
    assert basis.shape == (2, 4)


def test_runner_does_not_overwrite_any_archive(tmp_path):
    with pytest.raises(FileExistsError):
        run(ROOT / "config/fla_teacher_resolution.json", tmp_path)


def test_machine_precision_duplicates_are_merged_before_noise_without_changing_inputs():
    time = np.asarray([1., 1.63, 1.6300000000000001, 2., 4., 8., 22.])
    values = np.ones((4, len(time)))
    original = time.copy()
    repaired, clean, receipt = canonical_partition(time, values)
    assert len(repaired) == 6 and receipt["source_index_groups"][1] == [1, 2]
    assert receipt["before_noise"] is True
    np.testing.assert_array_equal(time, original)
    assert clean.shape == (4, 6)
    values[0, 2] = 2.
    with pytest.raises(ValueError, match="inconsistent"):
        canonical_partition(time, values)


def test_actual_parent_partition_supports_gcv_after_roundoff_repair():
    frame = pd.read_csv(ROOT / "output/fla_synthetic_recovery_2026_10_05_v2/datasets/dense_clean/observations.csv", float_precision="round_trip")
    time, values, receipt = canonical_partition(frame.time_day.to_numpy(), frame[["EGLC", "ELAC", "GLC", "LAC"]].to_numpy().T)
    assert receipt["original_count"] == 689 and receipt["canonical_count"] == 687
    curve = TrainingCurves(time, values, training_end=22., mode="smooth", noise_cv=0.)
    actual, derivative = curve.evaluate(time)
    assert np.all(actual > 0) and np.all(np.isfinite(derivative))


def test_independent_bounded_fit_uses_temporal_weights_and_clips_only_parameters():
    basis = np.asarray([[1., 2.], [2., 1.]])
    target = np.asarray([[2., 1.], [1., 4.]])
    weights = np.asarray([1., 3.])
    actual = analytic_fit(basis, target, weights, [.25, .25], [2., 2.])
    np.testing.assert_allclose(actual, [8./13., 2.])
    with pytest.raises(ValueError):
        analytic_fit(basis, target, [1., 0.], [.25, .25], [2., 2.])
    with pytest.raises(ValueError, match="unexcited"):
        analytic_fit(np.zeros((2, 2)), target, weights, [.25, .25], [2., 2.])


def test_independent_metric_retains_absolute_error_for_flat_pools():
    reference = np.asarray([[2., 2., 2.], [1., 2., 3.]])
    actual = reference+.01
    result = independent_metrics(actual, reference)
    np.testing.assert_allclose(result["absolute_rmse"], [.01, .01])
    np.testing.assert_allclose(result["mean_nrmse"], [.005, .005])
    np.testing.assert_allclose(result["excursion_nrmse"], [10., .005])
    flux = independent_metrics(actual, reference, flux=True)
    assert flux["excursion_nrmse"] is None
    with pytest.raises(ValueError):
        independent_metrics(np.full((2, 3), np.nan), reference)
