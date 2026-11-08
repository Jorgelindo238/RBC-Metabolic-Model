"""Tests for full-ODE VAMPD1 storage-decay evaluation helpers."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from evaluate_vampd1_storage_decay_candidate import (  # noqa: E402
    _primary_concentration_score,
    _relative_degradation,
    _strict_invariance,
)


def test_primary_score_combines_imp_and_total_without_hidden_weights() -> None:
    metrics = {
        "adenylate_total": {"nrmse": 3.0},
        "state_metrics": {"IMP": {"nrmse": 4.0}},
    }
    assert _primary_concentration_score(metrics) == (12.5) ** 0.5


def test_relative_degradation_is_candidate_minus_baseline() -> None:
    assert _relative_degradation(1.1, 1.0) == pytest.approx(0.1)


def test_strict_gate_uses_decision_metrics_and_reports_transient_difference() -> None:
    frame = pd.DataFrame(
        {
            "ATP": [1.0, 1.0],
            "ADP": [1.0, 1.0],
            "AMP": [1.0, 1.0],
            "IMP": [1.0, 1.0],
            "VAMPD1": [0.1, 0.1],
        }
    )
    strict = frame.copy()
    strict.loc[1, "IMP"] = 1.05
    metrics = {
        "adenylate_total": {"nrmse": 1.0, "endpoint_error_mM": 1.0},
        "state_metrics": {"IMP": {"nrmse": 1.0, "endpoint_error_mM": 1.0}},
        "VAMPD1_integrated_teachers": {"combined_nrmse": 1.0},
    }
    result = _strict_invariance(frame, strict, metrics, metrics)
    assert result["maximum_normalized_trajectory_difference"] > 0.01
    assert result["pass"] is True


def test_evaluator_contains_no_optimizer() -> None:
    source = (SCRIPTS / "evaluate_vampd1_storage_decay_candidate.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "optimize" not in called_names
    assert "create_study" not in source
