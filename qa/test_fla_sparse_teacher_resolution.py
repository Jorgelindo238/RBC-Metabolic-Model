"""Sparse continuation preserves source times, paired observations and sealed controls."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from fla_synthetic_recovery import add_synthetic_noise, OBSERVED_POOLS
from fla_teacher_resolution import method_names
from fla_working_reference import reference_options
from run_fla_sparse_teacher_resolution import (
    conditional_case, load_sparse_context, run, validate_sparse_design, verify_archive_inputs,
)


@pytest.fixture
def design():
    return json.loads((ROOT / "config/fla_sparse_teacher_resolution.json").read_text())


@pytest.fixture(scope="module")
def context():
    return load_sparse_context(json.loads((ROOT / "config/fla_sparse_teacher_resolution.json").read_text()))


def test_sparse_scope_counts_and_fixed_replay_subset(design):
    assert validate_sparse_design(design) is design
    assert design["training_times_day"] == [1, 4, 8, 11, 15, 18, 22]
    assert len(method_names(design)) == 15
    assert (len(design["noise_seeds"])+1)*len(method_names(design)) == 90
    assert (len(design["replay_noise_seeds"])+1)*len(design["replay_methods"])*2 == 32


@pytest.mark.parametrize("key,value", [
    ("purpose", "experimental_optimization"), ("sampling_scope", "experimental_concentrations"),
    ("training_times_day", [1, 2, 4, 8, 11, 15, 22]), ("training_times_day", [1, 4, 8, 11, 15, 18, 25]),
    ("training_times_day", [True, 4, 8, 11, 15, 18, 22]), ("global_model_promotion_allowed", True),
    ("biological_calibration_allowed", True), ("change_scientific_readiness_contract", True),
    ("replay_methods", ["best_case"]), ("replay_noise_seeds", [2718.0]),
    ("noise_coefficient_of_variation", float("nan")), ("uniform_grid_counts", [101, 1601]),
])
def test_invalid_sparse_design_is_rejected(design, key, value):
    design[key] = value
    with pytest.raises(ValueError):
        validate_sparse_design(design)


def test_loaded_observations_are_exact_parent_synthetic_schedule(context):
    contract, params, initial, names, time, clean, partition = context
    assert time.tolist() == contract["sparse_training_times"]
    assert clean.shape == (4, 7) and np.all(clean > 0)
    assert initial.shape == (114,) and len(names) == 114
    assert partition["original_count"] == partition["canonical_count"] == 7
    assert partition["source_index_groups"] == [[i] for i in range(7)]
    assert contract["real_concentrations_used_as_training_targets"] is False


@pytest.mark.parametrize("seed", [2718, 31415, 1618])
def test_sparse_noise_reproduces_parent_but_does_not_claim_matched_dense_draws(context, seed):
    clean = context[5]
    actual, _ = add_synthetic_noise(clean, cv=.005, seed=seed)
    frame = pd.read_csv(ROOT / f"output/fla_synthetic_recovery_2026_10_05_v2/datasets/sparse_noisy_{seed}/observations.csv", float_precision="round_trip")
    np.testing.assert_array_equal(actual, frame[list(OBSERVED_POOLS)].to_numpy().T)
    np.testing.assert_array_equal(actual[:, 0], clean[:, 0])


def test_sparse_conditional_adapter_preserves_raw_interval_targets_and_all_methods(context, design, tmp_path):
    contract, params, initial, names, time, clean, _ = context
    ode, _ = reference_options(contract["working_reference"])
    design["uniform_grid_counts"] = [401]
    base = np.asarray([params["vmax_VEGLC"], params["vmax_VELAC"]])
    fits, parity, quadrature = conditional_case("clean", time, clean, initial, params, ode, design, contract["design"], base*contract["design"]["truth_multipliers"], tmp_path)
    assert {row["method"] for row in fits} == set(method_names(design))
    assert all(row["passes"] for row in parity) and all(row["integral_order8_order16_pass"] for row in quadrature)
    for name in ("raw_integrated", "smoothed_inputs_integrated"):
        data = np.load(tmp_path / "fits" / f"clean_{name}" / "training_problem.npz")
        np.testing.assert_array_equal(data["targets"], np.asarray([-1., 1.])[:, None]*np.diff(clean[:2], axis=1))
        assert data["basis"].shape == (2, 6)


def test_sparse_continuation_rejects_different_noise_control(design):
    design["noise_coefficient_of_variation"] = .01
    with pytest.raises(ValueError, match="paired control"):
        load_sparse_context(design)


def test_comparison_archive_requires_unchanged_inputs_and_outputs(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("changed")
    (tmp_path / "preregistered_contract.json").write_text(json.dumps({"input_sha256": {str(source): "invalid"}}))
    (tmp_path / "final_verification.json").write_text(json.dumps({"independent_archive_checks_pass": True, "biological_contract_changed": False}))
    with pytest.raises(ValueError, match="input changed"):
        verify_archive_inputs(tmp_path)


def test_sparse_runner_never_overwrites_an_archive(tmp_path):
    with pytest.raises(FileExistsError):
        run(ROOT / "config/fla_sparse_teacher_resolution.json", tmp_path)
