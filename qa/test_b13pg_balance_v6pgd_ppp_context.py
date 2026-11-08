"""Tests for the J1-J3 B13PG balance and provenance audit."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "src"), str(ROOT / "scripts")):
    if path not in sys.path:
        sys.path.insert(0, path)

SCRIPT_PATH = ROOT / "scripts" / "audit_b13pg_balance_v6pgd_ppp_context.py"
SPEC = importlib.util.spec_from_file_location(
    "audit_b13pg_balance_v6pgd_ppp_context", SCRIPT_PATH
)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_exact_b13pg_balance_contract() -> None:
    assert AUDIT.B13PG_TERMS == {"VGAPDH": 1.0, "VPGK": -1.0, "VDPGM": -1.0}


def test_raw_b13pg_balance_uses_signed_reactions() -> None:
    raw = AUDIT._raw_b13pg_balance(
        {
            "VGAPDH": np.asarray([2.0, 3.0]),
            "VPGK": np.asarray([0.5, 0.75]),
            "VDPGM": np.asarray([0.25, 0.5]),
        }
    )
    assert np.allclose(raw, [1.25, 1.75])


def test_effective_balance_reproduces_native_low_pool_damping() -> None:
    effective, adjustment = AUDIT._effective_balance(
        np.asarray([-0.2, -0.2, 0.1]),
        np.asarray([5e-4, 2e-3, 5e-4]),
    )
    assert np.allclose(effective, [-0.1, -0.2, 0.1])
    assert np.allclose(adjustment, [0.1, 0.0, 0.0])


def test_effective_balance_reproduces_native_concentration_floor_at_zero() -> None:
    effective, _ = AUDIT._effective_balance(
        np.asarray([-0.2]),
        np.asarray([0.0]),
    )
    assert np.allclose(effective, [-0.0002])


def test_provenance_detects_duplicated_b13pg_b23pg_curves() -> None:
    provenance = AUDIT._provenance_audit()
    assert provenance["curves_pointwise_identical"] is True
    assert provenance["maximum_curve_absolute_difference"] == 0.0
    assert provenance["B13PG_supported_calibration_target"] is False
    assert provenance["B23PG_supported_calibration_target"] is True
    assert provenance["independent_B13PG_evidence"] is False


def test_windows_match_recorded_contract() -> None:
    assert AUDIT.WINDOWS == (
        ("J1_J1.1", 1.0, 1.1),
        ("J1.1_J1.3", 1.1, 1.3),
        ("J1.3_J1.6", 1.3, 1.6),
        ("J1.6_J2", 1.6, 2.0),
        ("J2_J3", 2.0, 3.0),
    )


def test_classifier_reclassifies_nonindependent_initial_stock() -> None:
    result = AUDIT._classify(
        provenance={
            "curves_pointwise_identical": True,
            "B13PG_supported_calibration_target": False,
        },
        metrics={
            "B13PG_below_1pct_initial_day": 1.2,
            "J1_J3_VGAPDH_replacement_fraction": 0.5,
            "J1_J3_VPGK_drainage_fraction": 0.75,
        },
    )
    assert result["classification"].startswith("non-independent")
    assert all(result["classification_gates"].values())
