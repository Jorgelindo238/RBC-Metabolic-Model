"""Fixed replay scope and complete paired comparisons remain explicit and reversible."""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from run_fla_smoothed_interval_replay import METHODS, paired_comparison, replay_plan, run, validate_design
from verify_fla_smoothed_interval_replay import dense_anchor_matches


@pytest.fixture
def design():
    return json.loads((ROOT / "config/fla_smoothed_interval_replay.json").read_text())


def test_fixed_scope_and_counts(design):
    assert validate_design(design) is design
    assert design["new_fit_count"] == 0
    assert design["new_ODE_integration_count"] + design["reused_ODE_integration_count"] == 24


@pytest.mark.parametrize("key,value", [
    ("schema_version", True), ("new_fit_count", False), ("new_fit_count", 1),
    ("purpose", "optimization"), ("biological_calibration_allowed", True),
    ("global_model_promotion_allowed", True), ("teacher_forcing", True),
    ("observation_reset", True), ("raw_state_output_clipping", True),
    ("methods", ["best_case"]), ("noise_seeds", [2718]),
    ("noise_seeds", [2718., 31415, 1618, 57721, 104729]),
    ("horizon_day", [1., 22.]), ("training_end_day", 25.),
    ("new_ODE_integration_count", 24), ("reused_raw_cases", []),
])
def test_scope_mutations_rejected(design, key, value):
    design[key] = value
    with pytest.raises(ValueError):
        validate_design(design)


def test_unknown_design_control_rejected(design):
    design["optimizer"] = "new"
    with pytest.raises(ValueError):
        validate_design(design)


def test_sealed_plan_exactly_twelve_pairs_with_four_reused(design):
    fits = json.loads((ROOT / design["parent_archive"] / "conditional_results.json").read_text())
    plan = replay_plan(design, fits)
    assert len(plan) == 12
    assert sum(row["replay_source"] == "new" for row in plan) == 8
    assert sum(row["replay_source"] == "reused" for row in plan) == 4
    for row in plan:
        assert row["capacities"] == next(f["capacities"] for f in fits if f["label"] == row["label"])


@pytest.mark.parametrize("duplicate", [False, True])
def test_missing_or_duplicated_frozen_fit_rejected(design, duplicate):
    fits = json.loads((ROOT / design["parent_archive"] / "conditional_results.json").read_text())
    if duplicate:
        fits.append(next(row for row in fits if row["label"] == "clean_raw_integrated"))
    else:
        fits = [row for row in fits if row["label"] != "clean_raw_integrated"]
    with pytest.raises(ValueError):
        replay_plan(design, fits)


def test_nonfinite_capacities_rejected(design):
    fits = json.loads((ROOT / design["parent_archive"] / "conditional_results.json").read_text())
    next(row for row in fits if row["label"] == "clean_raw_integrated")["capacities"][0] = np.nan
    with pytest.raises(ValueError):
        replay_plan(design, fits)


def test_existing_archive_not_overwritten(tmp_path):
    with pytest.raises(FileExistsError):
        run(ROOT / "config/fla_smoothed_interval_replay.json", tmp_path)


def sample_comparison(design):
    fits = json.loads((ROOT / design["parent_archive"] / "conditional_results.json").read_text())
    plan = replay_plan(design, fits)
    metrics = []
    for row in plan:
        error = 1000. if row["case"] == "clean" else 2. if row["method"] == METHODS[0] else 1.
        metrics.append({"label": row["label"], "period": "holdout", "kind": "concentration", "name": "EGLC",
                        "excursion_nrmse": error, "mean_nrmse": error/2, "last_error": -.1})
    return plan, metrics


def test_clean_not_in_noisy_summary_and_paired_difference_sign(design):
    plan, metrics = sample_comparison(design)
    paired, summary = paired_comparison(metrics, plan)
    assert len(paired) == 6 and len(summary) == 1
    assert summary.iloc[0].noise_seed_count == 5
    assert summary.iloc[0].raw_median == 2. and summary.iloc[0].smoothed_median == 1.
    assert summary.iloc[0].smoothed_better_seed_count == 5
    assert summary.iloc[0].median_paired_difference == -1.
    assert paired.iloc[0].raw_endpoint_error == -.1


def test_incomplete_five_seed_summary_rejected(design):
    plan, metrics = sample_comparison(design)
    metrics = [r for r in metrics if not r["label"].startswith("noise_104729_")]
    with pytest.raises(ValueError, match="five matched seeds"):
        paired_comparison(metrics, plan)


def test_flux_uses_rms_metric_not_missing_excursion(design):
    plan, metrics = sample_comparison(design)
    for row in metrics:
        row.update(kind="executed_flux", name="VEGLC", excursion_nrmse=None)
    paired, _ = paired_comparison(metrics, plan)
    assert paired.metric.tolist() == ["mean_nrmse"]*6
    assert paired.raw_error.tolist()[1:] == [1.]*5


def test_dense_anchor_allows_only_machine_roundoff():
    initial = np.asarray([1., .5, 24.])
    assert dense_anchor_matches(initial.copy(), initial)
    assert dense_anchor_matches(initial + np.finfo(float).eps, initial)
    assert not dense_anchor_matches(initial + 1e-10, initial)


@pytest.mark.parametrize("actual", [[1., np.nan], [1.], [1., np.inf]])
def test_dense_anchor_rejects_nonfinite_or_wrong_shape(actual):
    assert not dense_anchor_matches(actual, [1., .5])
