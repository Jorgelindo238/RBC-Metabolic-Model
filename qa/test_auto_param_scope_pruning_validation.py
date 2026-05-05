"""Tests for the Phase A2 pruning-validation harness."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_auto_param_scope_pruning_validation.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "run_auto_param_scope_pruning_validation",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


pruning = _load_module()


def _fake_sensitivity():
    return {
        "baseline": {"target_loss": 10.0, "param_count": 6},
        "probes": [
            {
                "name": "vmax_KEEP",
                "classification": "keep_high_sensitivity",
                "recommendation": "keep",
                "effect_frac_of_baseline_loss": 0.08,
                "classes": ["vmax"],
                "identifiability": "compensation_risk",
            },
            {
                "name": "km_EGLC",
                "classification": "candidate_prune_low_sensitivity",
                "recommendation": "prune_candidate",
                "effect_frac_of_baseline_loss": 0.003,
                "classes": ["km", "transport"],
                "identifiability": "core",
            },
            {
                "name": "alpha_REG",
                "classification": "candidate_prune_low_sensitivity",
                "recommendation": "prune_candidate",
                "effect_frac_of_baseline_loss": 0.0001,
                "classes": ["regulation"],
                "identifiability": "caution",
            },
            {
                "name": "vmax_SIDE",
                "classification": "candidate_prune_low_sensitivity",
                "recommendation": "prune_candidate",
                "effect_frac_of_baseline_loss": 0.002,
                "classes": ["vmax"],
                "identifiability": "compensation_risk",
            },
        ],
    }


def test_candidate_scope_builder_keeps_sensitive_and_core_tokens():
    scopes = pruning._build_candidate_scopes(
        _fake_sensitivity(),
        requested_candidates=["sensitive_only", "core_plus_sensitive", "drop_low_regulation"],
        near_effect_frac=0.001,
        top_k=2,
        protected_tokens=["EGLC"],
        include_full_reference=False,
    )

    assert scopes["sensitive_only"]["params"] == ["vmax_KEEP"]
    assert scopes["core_plus_sensitive"]["params"] == ["km_EGLC", "vmax_KEEP"]
    assert "alpha_REG" not in scopes["drop_low_regulation"]["params"]
    assert "vmax_SIDE" in scopes["drop_low_regulation"]["params"]


def test_candidate_decision_rejects_gate_failure_before_loss():
    decision = pruning._candidate_decision(
        final_loss=9.0,
        reference_loss=10.0,
        eglc_gate={"state": "fail"},
        loss_tolerance_pct=0.10,
        review_loss_tolerance_pct=0.25,
    )

    assert decision["decision"] == "reject_pruned_scope"
    assert "EGLC" in decision["reason"]


def test_candidate_decision_accepts_loss_within_tolerance():
    decision = pruning._candidate_decision(
        final_loss=10.5,
        reference_loss=10.0,
        eglc_gate={"state": "pass"},
        loss_tolerance_pct=0.10,
        review_loss_tolerance_pct=0.25,
    )

    assert decision["decision"] == "accept_pruned_scope"
    assert decision["loss_delta_pct_of_reference"] == 0.05


def test_candidate_decision_sends_medium_regression_to_review():
    decision = pruning._candidate_decision(
        final_loss=11.5,
        reference_loss=10.0,
        eglc_gate={"state": "pass"},
        loss_tolerance_pct=0.10,
        review_loss_tolerance_pct=0.25,
    )

    assert decision["decision"] == "needs_review"


def test_recommended_candidate_prefers_smallest_accepted_scope():
    winner = pruning._recommend_candidate(
        [
            {
                "name": "wide",
                "decision": "accept_pruned_scope",
                "param_count": 20,
                "final_loss": 8.0,
                "loss_delta_pct_of_reference": -0.2,
                "params": ["a"] * 20,
            },
            {
                "name": "small",
                "decision": "accept_pruned_scope",
                "param_count": 5,
                "final_loss": 9.5,
                "loss_delta_pct_of_reference": -0.05,
                "params": ["b"] * 5,
            },
        ]
    )

    assert winner["name"] == "small"
    assert winner["param_count"] == 5
