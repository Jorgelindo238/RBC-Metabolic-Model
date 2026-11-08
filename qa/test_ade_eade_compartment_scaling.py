"""Tests for the fixed-kinetic ADE/EADE compartment-scaling audit."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from audit_ade_eade_compartment_scaling import (  # noqa: E402
    _classify,
    amount_consistent_aprt_teacher,
    analytical_external_scale,
    external_scale_from_hematocrit,
)


def test_external_scale_uses_amount_balance_volume_ratio() -> None:
    assert external_scale_from_hematocrit(0.60) == pytest.approx(2.0 / 3.0)
    with pytest.raises(ValueError):
        external_scale_from_hematocrit(1.0)


def test_amount_consistent_teacher_scales_only_external_derivative() -> None:
    teacher = amount_consistent_aprt_teacher(
        np.array([-0.1, -0.2]),
        np.array([-0.3, 0.1]),
        0.5,
    )
    np.testing.assert_allclose(teacher, [0.25, 0.15])
    with pytest.raises(ValueError):
        amount_consistent_aprt_teacher(np.array([0.0]), np.array([0.0]), -1.0)


def test_analytical_matching_scale_is_negative_for_opposed_integrals() -> None:
    scale = analytical_external_scale(
        ade_loss=0.529,
        eade_loss=0.463,
        target_integral=-0.340,
    )
    assert scale is not None
    assert scale < 0.0


def test_classifier_rejects_physiological_scaling_when_signs_conflict() -> None:
    rows = [
        {"pair_APRT_integral_trapezoid_mM": 0.8, "integrated_disagreement_mM": 1.1},
        {"pair_APRT_integral_trapezoid_mM": 0.7, "integrated_disagreement_mM": 1.0},
    ]
    analytical = {
        "total_adenylate_APRT_integral_mM": -0.34,
        "external_scale_required_for_integral_match": -1.8,
    }
    assert _classify(rows, analytical) == (
        "reject_volume_scaling_as_resolution_of_APRT_teacher_sign_conflict"
    )


def test_audit_is_non_fitting_and_does_not_mutate_the_ode() -> None:
    source = (SCRIPTS / "audit_ade_eade_compartment_scaling.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "optimize" not in called_names
    assert "solve_ivp" not in source
    assert "custom_params" not in source
    assert "minimize" not in called_names
