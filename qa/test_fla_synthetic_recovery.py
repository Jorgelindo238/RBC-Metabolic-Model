"""Synthetic recovery is isolated, leakage-free and uses executed transport rates."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from fla_synthetic_recovery import (
    OBSERVED_POOLS, PARAMETERS, REACTIONS, add_synthetic_noise, check_linear_capacity_domain,
    executed_transport, excursion_metrics, fit_capacities, proxy_states, reconstruction,
    unit_capacity_basis, validate_config, validate_observations,
)
from fla_working_reference import load_working_reference, reference_options
from equadiff_brodbar import BRODBAR_METABOLITE_MAP
from run_fla_synthetic_recovery import run


@pytest.fixture
def design():
    return json.loads((ROOT / "config/fla_synthetic_recovery.json").read_text())


@pytest.fixture
def context():
    source = ROOT / "output/ppp_numerical_audit_2026_10_05"
    x0 = pd.read_csv(source / "fixed_initial_state.csv", float_precision="round_trip").initial_value.to_numpy()
    params = json.loads((source / "fixed_parameters.json").read_text())
    ode, _ = reference_options(load_working_reference())
    return x0, params, ode


def test_default_design_is_synthetic_only_and_biological_contract_stays_blocked(design):
    assert validate_config(design) is design
    readiness = json.loads((ROOT / "config/fla_adenylate_redox_readiness.json").read_text())
    assert not readiness["accuracy"]["verified"]
    assert all(value is None for value in readiness["accuracy"]["absolute_endpoint_error_mM"].values())
    plan = json.loads((ROOT / "output/adenylate_redox_readiness_2026_10_05_v2/coupled_sensitivity_protocol.json").read_text())
    assert plan["execution_authorized"] is False


@pytest.mark.parametrize("key", ["biological_calibration_allowed", "global_model_promotion_allowed", "change_scientific_readiness_contract"])
def test_synthetic_design_cannot_enable_biological_work(design, key):
    design[key] = True
    with pytest.raises(ValueError, match="biological"):
        validate_config(design)


@pytest.mark.parametrize("key,value", [
    ("parameters", ["vmax_VHK", "vmax_VELAC"]), ("training_end_day", 46.),
    ("truth_multipliers", [0., 1.]), ("truth_multipliers", [float("nan"), 1.]),
    ("start_multipliers", [[3., 1.]]), ("noise_seeds", [1, 1]), ("noise_seeds", [True]),
    ("quadrature_orders", [16, 8]), ("teacher_point_count", 2), ("noise_coefficient_of_variation", 0.),
])
def test_invalid_design_is_rejected(design, key, value):
    design[key] = value
    with pytest.raises(ValueError):
        validate_config(design)


def test_synthetic_noise_is_reproducible_and_leaves_known_initial_state_exact():
    values = np.asarray([[20., 18., 16.], [1., 2., 3.], [2., 4., 5.], [3., 4., 6.]])
    old = values.copy()
    first, sigma = add_synthetic_noise(values, cv=.005, seed=2718)
    second, _ = add_synthetic_noise(values, cv=.005, seed=2718)
    other, _ = add_synthetic_noise(values, cv=.005, seed=31415)
    np.testing.assert_array_equal(values, old)
    np.testing.assert_array_equal(first, second)
    np.testing.assert_array_equal(first[:, 0], values[:, 0])
    np.testing.assert_allclose(sigma[:, 1:], .005 * values[:, 1:])
    np.testing.assert_array_equal(sigma[:, 0], np.zeros(4))
    assert not np.array_equal(first[:, 1:], other[:, 1:])


def test_noise_preserves_zero_and_positive_small_pools_without_clipping():
    values = np.asarray([[0., 1e-12, 1e-9]] * 4)
    noisy, _ = add_synthetic_noise(values, cv=.5, seed=2718)
    np.testing.assert_array_equal(noisy[:, 0], values[:, 0])
    assert np.all(noisy[:, 1:] > 0)
    assert not np.array_equal(noisy[:, 1:], values[:, 1:])
    with pytest.raises(ValueError):
        add_synthetic_noise(values, cv=float("nan"), seed=2718)


def test_observations_cannot_include_holdout_or_invalid_rows():
    values = np.ones((4, 3))
    for time in ([1., 22., 25.], [1., 1., 4.], [1., np.nan, 4.]):
        with pytest.raises(ValueError):
            validate_observations(time, values, training_end=22.)
    values[0, 1] = -1.
    with pytest.raises(ValueError):
        validate_observations([1., 4., 8.], values, training_end=22.)


def test_proxy_only_uses_four_observed_pools_and_cannot_extrapolate(context):
    x0, _, _ = context
    values = np.asarray([[10., 9.], [1., 2.], [.3, .4], [2., 2.1]])
    states = proxy_states([1., 4.], values, [1., 2., 4.], x0, training_end=4.)
    indices = [BRODBAR_METABOLITE_MAP[pool] for pool in OBSERVED_POOLS]
    latent = [i for i in range(114) if i not in indices]
    np.testing.assert_array_equal(states[latent], np.repeat(x0[latent, None], 3, axis=1))
    np.testing.assert_array_equal(states[indices, 0], values[:, 0])
    with pytest.raises(ValueError, match="extrapolate"):
        proxy_states([1., 4.], values, [4.01], x0, training_end=4.)


def test_kernel_basis_is_exact_inside_uncapped_positive_capacity_domain(context):
    x0, params, ode = context
    states = np.repeat(x0[:, None], 3, axis=1)
    states[BRODBAR_METABOLITE_MAP["GLC"], 1] = .0001
    states[BRODBAR_METABOLITE_MAP["LAC"], 1] = .0001
    states[BRODBAR_METABOLITE_MAP["EGLC"], 2] = 0.
    base = np.asarray([params[p] for p in PARAMETERS])
    check_linear_capacity_domain(params, base, [.25, 2.])
    basis = unit_capacity_basis([1., 2., 4.], states, params, ode)
    for multiplier in (.25, 1., 2.):
        candidate = dict(params)
        candidate.update(dict(zip(PARAMETERS, base * multiplier)))
        direct = executed_transport([1., 2., 4.], states, candidate, ode)
        np.testing.assert_allclose(direct["effective"], base[:, None] * multiplier * basis, rtol=1e-12, atol=1e-12)
        assert max(direct["closure"]) < 1e-10
        assert np.any(direct["factors"] < 1.)
        assert not np.array_equal(direct["effective"], direct["native"])


def test_inert_latent_proxy_entries_cannot_leak_truth_into_transport(context):
    x0, params, ode = context
    state = x0.copy()
    other = x0.copy()
    for pool in ("ATP", "ADP", "AMP", "NAD", "NADH", "G6P", "F6P"):
        other[BRODBAR_METABOLITE_MAP[pool]] *= 3.
    direct = executed_transport([1.], state[:, None], params, ode)
    alternative = executed_transport([1.], other[:, None], params, ode)
    np.testing.assert_array_equal(direct["effective"], alternative["effective"])


def test_cap_active_domains_are_rejected_instead_of_linearized(context):
    _, params, _ = context
    base = np.asarray([params[p] for p in PARAMETERS])
    with pytest.raises(ValueError, match="cap"):
        check_linear_capacity_domain(params, base, [.25, 3.])
    with pytest.raises(ValueError, match="feedback"):
        check_linear_capacity_domain(dict(params, transport_gate_feedback_strength_VEGLC=-.1), base, [.25, 2.])


def test_forcing_and_legacy_replay_are_rejected(context):
    x0, params, ode = context
    bad = dict(params, kinetic_family_VEGLC="teacher_curve_flux")
    with pytest.raises(ValueError, match="forcing"):
        executed_transport([1.], x0[:, None], bad, ode)
    with pytest.raises(ValueError, match="unforced"):
        executed_transport([1.], x0[:, None], params, dict(ode, positivity_policy="legacy"))


def test_reconstruction_reuses_teacher_and_exact_signed_observed_increments(context):
    x0, params, ode = context
    time = np.asarray([1., 2., 4.])
    values = np.asarray([[10., 9., 7.], [1., 2., 4.], [.3, .3, .3], [2., 2., 2.]])
    result = reconstruction(time, values, x0, params, ode, training_end=4., point_count=11, order=8)
    assert result["teacher"]["contract_type"] == "teacher_flux_dataset"
    np.testing.assert_allclose(result["targets"], np.ones((2, 11)))
    np.testing.assert_allclose(result["integral_targets"], [[1., 2.], [1., 2.]])
    assert result["integrated_basis"].shape == (2, 2)
    assert result["time"][-1] == 4.


def test_multistart_recovers_known_capacities_from_signed_rates_without_truth_input():
    basis = np.asarray([[.1, -.2, .3, -.1], [.2, .4, .5, .2]])
    truth = np.array([1.7, .8])
    result = fit_capacities(basis, truth[:, None] * basis, [2., 1.], [.25, 2.], [[.6, 1.4], [1.4, .6], [1., 1.]])
    np.testing.assert_allclose(result["capacities"], truth, rtol=1e-8)
    assert result["conditional_log_jacobian_rank"] == 2
    assert result["multistart_max_capacity_spread"] < 1e-8
    assert not result["global_identifiability_established"]
    assert not any(result["at_bound"])


def test_unexcited_rate_is_not_reported_as_identifiable():
    result = fit_capacities([[0., 0.], [.2, .3]], [[0., 0.], [.4, .6]], [1., 1.], [.25, 3.], [[.6, 1.4], [1.4, .6]])
    assert result["conditional_log_jacobian_rank"] == 1
    assert result["multistart_max_capacity_spread"] > .1
    assert not result["global_identifiability_established"]


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_nonfinite_recovery_data_fails_closed(bad):
    with pytest.raises(ValueError):
        fit_capacities([[bad, .1], [.2, .3]], [[1., 1.], [1., 1.]], [1., 1.], [.25, 2.], [[1., 1.]])


def test_metrics_use_excursion_and_reject_nonfinite_output():
    truth = np.asarray([[10., 11., 12.], [1., 1., 1.]])
    np.testing.assert_allclose(excursion_metrics(truth+.1, truth), [.05, 100.])
    with pytest.raises(ValueError):
        excursion_metrics(truth+float("nan"), truth)


def test_runner_never_overwrites_existing_evidence(tmp_path):
    with pytest.raises(FileExistsError):
        run(ROOT / "config/fla_synthetic_recovery.json", tmp_path)
