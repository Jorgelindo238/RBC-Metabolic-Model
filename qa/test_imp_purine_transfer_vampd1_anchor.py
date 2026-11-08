"""Tests for the fixed-kinetic IMP and purine-transfer audit."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from audit_imp_purine_transfer_vampd1_anchor import (  # noqa: E402
    ADE_TERMS,
    IMP_TERMS,
    PRPP_TERMS,
    _classify,
    _raw_balance,
)


def test_declared_balances_match_the_ode_contract() -> None:
    assert IMP_TERMS == {
        "VHGPRT1": 1.0,
        "VAMPD1": 1.0,
        "VADSS": -1.0,
        "VIMPH": -1.0,
        "Vnucleo2": -1.0,
    }
    assert ADE_TERMS == {"VEADE": -1.0, "VAPRT": -1.0}
    assert PRPP_TERMS == {
        "VPRPPASe": 1.0,
        "VAPRT": -1.0,
        "VHGPRT1": -1.0,
        "VHGPRT2": -1.0,
    }


def test_raw_imp_balance_is_exactly_reconstructed() -> None:
    frame = pd.DataFrame(
        {
            "VHGPRT1": [1.0, 2.0],
            "VAMPD1": [3.0, 4.0],
            "VADSS": [0.5, 0.5],
            "VIMPH": [0.25, 0.5],
            "Vnucleo2": [0.25, 1.0],
        }
    )
    np.testing.assert_allclose(_raw_balance(frame, IMP_TERMS), [3.0, 4.0])


def test_classifier_rejects_hard_zero_when_teachers_disagree() -> None:
    metrics = {
        "VAPRT_teacher_from_ADE_EADE": {
            "integral_mM": 1.0,
            "positive_time_fraction": 1.0,
        },
        "VAPRT_teacher_from_total_adenylate": {
            "integral_mM": -0.2,
            "positive_time_fraction": 0.2,
        },
        "VAPRT_teacher_disagreement_integral_mM": 1.2,
    }
    assert _classify(metrics) == (
        "hard_VAPRT_zero_rejected_but_positive_APRT_alone_is_teacher_incompatible"
    )


def test_classifier_supports_bounded_positive_aprt_when_teachers_agree() -> None:
    metrics = {
        "VAPRT_teacher_from_ADE_EADE": {
            "integral_mM": 0.5,
            "positive_time_fraction": 1.0,
        },
        "VAPRT_teacher_from_total_adenylate": {
            "integral_mM": 0.45,
            "positive_time_fraction": 1.0,
        },
        "VAPRT_teacher_disagreement_integral_mM": 0.05,
    }
    assert _classify(metrics) == "hard_VAPRT_zero_rejected_bounded_positive_APRT_supported"


def test_audit_contains_no_optimizer_or_parameter_mutation() -> None:
    source = (SCRIPTS / "audit_imp_purine_transfer_vampd1_anchor.py").read_text(
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
