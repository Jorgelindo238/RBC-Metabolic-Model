"""Preregistered random panels, paired comparisons and seed/start bookkeeping."""

import copy
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fla_transport_buffer_noise import (bounds_hit, generate_panel, group_diagnostics, observed_metrics,
                                      panel_times, panel_values, validate_noise)
from fla_transport_buffer_recovery import TrainingObjective, encode, training_times
from fla_transport_buffer_synthetic import simulate


@pytest.fixture
def config():
    return json.loads((ROOT / "config/fla_transport_buffer_synthetic.json").read_text())


@pytest.fixture
def design():
    return json.loads((ROOT / "config/fla_transport_buffer_noise.json").read_text())


@pytest.fixture
def reference(config):
    return simulate(config, config["scenarios"][0])


@pytest.mark.parametrize("key,value", [("concentration_CV", .01), ("pH_SD", .01), ("noise_seeds", [1, 2, 3]),
    ("biological_fitting_allowed", True), ("full_RBC_replay_allowed", True), ("production_defaults_changed", True),
    ("source_data_changed", True), ("pH_noise", "uniform")])
def test_frozen_noise_and_safeguards(config, design, key, value):
    design[key] = value
    with pytest.raises(ValueError):
        validate_noise(config, design)


def test_panel_deterministic_and_independent_streams(config, design, reference):
    before = copy.deepcopy(config)
    a = generate_panel(config, design, 0, 2718, reference)
    b = generate_panel(config, design, 0, 2718, reference)
    c = generate_panel(config, design, 0, 31415, reference)
    d = generate_panel(config, design, 1, 2718, reference)
    for key in a:
        np.testing.assert_array_equal(a[key], b[key])
    assert not np.array_equal(a["normal_draws"], c["normal_draws"])
    assert not np.array_equal(a["normal_draws"], d["normal_draws"])
    assert config == before


def test_noise_formula_and_initial_contract(config, design, reference):
    panel = generate_panel(config, design, 0, 2718, reference)
    clean, noisy, draws = [panel[k] for k in ("clean_states", "observed_states", "normal_draws")]
    lv = np.log1p(.005**2)
    np.testing.assert_allclose(noisy[:2, 1:]/clean[:2, 1:], np.exp(np.sqrt(lv)*draws[:2, 1:]-.5*lv), rtol=1e-15)
    np.testing.assert_array_equal(noisy[:2, 0], clean[:2, 0])
    np.testing.assert_allclose(noisy[2:]-clean[2:], .005*draws[2:], atol=1e-15)
    assert noisy[2, 0] != clean[2, 0] and noisy[3, 0] != clean[3, 0]
    assert np.min(noisy[:2]) > 0


@pytest.mark.parametrize("index,seed", [(0, 1), (-1, 2718), (True, 2718)])
def test_undeclared_random_stream_rejected(config, design, reference, index, seed):
    with pytest.raises(ValueError):
        generate_panel(config, design, index, seed, reference)


def test_common_noise_shared_at_schedule_intersections(config, design, reference):
    panel = generate_panel(config, design, 0, 2718, reference)
    sparse, dense = [training_times(config, name) for name in ("sparse", "dense")]
    common = np.intersect1d(sparse, dense)
    expected = panel_values(panel, common)
    for time in (sparse, dense):
        positions = np.searchsorted(time, common)
        np.testing.assert_array_equal(panel_values(panel, time)[:, positions], expected)
    assert len(panel_times(config)) == 87


def test_holdout_noise_and_unknown_pHi_do_not_enter_training(config, design, reference):
    panel = generate_panel(config, design, 0, 2718, reference)
    time = training_times(config, "sparse")
    other = {k: v.copy() for k, v in panel.items()}
    other["observed_states"][:, other["time"] > config["training_end_day"]] += .5
    hidden = copy.deepcopy(config["scenarios"][0])
    hidden["initial"][2] = 8
    a = TrainingObjective(config, config["scenarios"][0], "access_pHi", "concentrations", time, panel_values(panel, time)[:2])
    b = TrainingObjective(config, hidden, "access_pHi", "concentrations", time, panel_values(other, time)[:2])
    x = encode(a.names, {"access_i": 1.2, "phi0": 7.0})
    np.testing.assert_array_equal(a.evaluate(x), b.evaluate(x))


def test_noisy_and_latent_truth_metrics_distinct(config, design, reference):
    panel = generate_panel(config, design, 0, 2718, reference)
    metrics = observed_metrics(config, "concentrations_plus_pHi_pHe", panel, training_times(config, "sparse"), reference)
    assert metrics["holdout_noisy_observed_plan_scaled_RMSE"] > 0


def test_bound_hits_are_reported_not_suppressed(config, design):
    assert bounds_hit(config, design, {"access_i": .5, "phi0": 7.6}) == ["access_i", "phi0"]
    assert bounds_hit(config, design, {"conductance": .3, "phi0": 6.9}) == []
    with pytest.raises(ValueError):
        bounds_hit(config, design, {"access_i": .4})


def test_group_counts_starts_not_independent_noise_replicates(config):
    fits = [{"scenario": "initial_export", "noise_seed": 2718, "schedule": "sparse", "stage": "access_pHi",
        "plan": "concentrations", "start_index": i, "parameters": {"access_i": value}, "optimizer_success": True,
        "parameter_recovery_pass": i != 1, "holdout_prediction_pass": True, "recovery_pass": i != 1,
        "bound_hits": []} for i, value in enumerate([1, 1.5, 2])]
    group = group_diagnostics(config, fits)
    assert not group["all_starts_parameter_pass"] and not group["multistart_agreement_pass"]
    assert group["median_parameters_over_starts"]["access_i"] == 1.5
    with pytest.raises(ValueError):
        group_diagnostics(config, fits[:2])
