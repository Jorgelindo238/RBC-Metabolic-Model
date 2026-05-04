"""Tests for the Phase A auto-param-scope sensitivity harness."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_auto_param_scope_sensitivity.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("run_auto_param_scope_sensitivity", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


sensitivity = _load_module()


def test_perturbation_values_are_clamped_to_bounds():
    values = sensitivity._perturbation_values(
        9.8,
        0.0,
        10.0,
        step_frac=0.10,
    )

    assert values["up"]["value"] == 10.0
    assert values["down"]["value"] == 8.82


def test_eglc_gate_passes_and_fails_on_configured_depletion():
    passed = sensitivity._eglc_gate(
        {"eglc_depletion_frac": 0.06, "initial_EGLC": 25.0, "final_EGLC": 23.5},
        0.05,
    )
    failed = sensitivity._eglc_gate(
        {"eglc_depletion_frac": 0.009, "initial_EGLC": 25.0, "final_EGLC": 24.775},
        0.05,
    )

    assert passed["state"] == "pass"
    assert failed["state"] == "fail"


def test_classifier_prioritizes_eglc_gate_failure_over_low_effect():
    classification, rationale = sensitivity._classify_probe(
        baseline_loss=10.0,
        perturbations={
            "up": {
                "target_loss": 10.001,
                "eglc_gate": {"state": "fail"},
            }
        },
        low_effect_frac=0.005,
        high_effect_frac=0.02,
        danger_regression_frac=0.10,
    )

    assert classification == "dangerous_eglc_gate_sensitive"
    assert "EGLC" in rationale


def test_classifier_detects_low_and_high_effect_params():
    low, _ = sensitivity._classify_probe(
        baseline_loss=10.0,
        perturbations={"up": {"target_loss": 10.01, "eglc_gate": {"state": "pass"}}},
        low_effect_frac=0.005,
        high_effect_frac=0.02,
        danger_regression_frac=0.10,
    )
    high, _ = sensitivity._classify_probe(
        baseline_loss=10.0,
        perturbations={"up": {"target_loss": 10.5, "eglc_gate": {"state": "pass"}}},
        low_effect_frac=0.005,
        high_effect_frac=0.02,
        danger_regression_frac=0.10,
    )

    assert low == "candidate_prune_low_sensitivity"
    assert high == "keep_high_sensitivity"


def test_summary_splits_pruned_guarded_and_kept_params():
    summary = sensitivity._summarize_probes(
        [
            {
                "name": "km_LOW",
                "classification": "candidate_prune_low_sensitivity",
                "effect_frac_of_baseline_loss": 0.001,
                "recommendation": "prune_candidate",
            },
            {
                "name": "vmax_GUARDED",
                "classification": "dangerous_eglc_gate_sensitive",
                "effect_frac_of_baseline_loss": 0.10,
                "recommendation": "keep_guarded",
            },
            {
                "name": "vmax_KEEP",
                "classification": "keep_high_sensitivity",
                "effect_frac_of_baseline_loss": 0.08,
                "recommendation": "keep",
            },
        ]
    )

    assert summary["recommended_pruned_params"] == ["km_LOW"]
    assert summary["guarded_params"] == ["vmax_GUARDED"]
    assert summary["recommended_kept_params"] == ["vmax_GUARDED", "vmax_KEEP"]
