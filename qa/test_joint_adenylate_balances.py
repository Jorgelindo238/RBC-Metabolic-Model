"""Tests for the joint ATP-ADP-AMP balance audit."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "src"), str(ROOT / "scripts")):
    if path not in sys.path:
        sys.path.insert(0, path)

SCRIPT = ROOT / "scripts" / "audit_joint_adenylate_balances.py"
SPEC = importlib.util.spec_from_file_location("joint_adenylate", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_total_balance_cancels_internal_adenylate_redistribution() -> None:
    assert AUDIT.TOTAL_TERMS == {
        "VAK2": 1.0,
        "VSAM": -1.0,
        "VADSL": 1.0,
        "VAPRT": 1.0,
        "VAMPD1": -1.0,
        "VAMP_NT": -1.0,
    }
    assert "VAK" not in AUDIT.TOTAL_TERMS
    assert "VPGK" not in AUDIT.TOTAL_TERMS
    assert "VPK" not in AUDIT.TOTAL_TERMS


def test_joint_correction_closes_all_three_teacher_residuals() -> None:
    teacher = {
        "ATP": np.asarray([1.0, 2.0]),
        "ADP": np.asarray([-0.5, -1.0]),
        "AMP": np.asarray([-0.2, 0.1]),
    }
    native = {
        "ATP": np.asarray([0.1, 0.2]),
        "ADP": np.asarray([0.3, 0.4]),
        "AMP": np.asarray([0.5, 0.6]),
    }
    delta_vpgk, delta_vak, missing = AUDIT._joint_correction(teacher, native)
    np.testing.assert_allclose(native["ATP"] + delta_vpgk + delta_vak, teacher["ATP"])
    np.testing.assert_allclose(native["ADP"] - delta_vpgk - 2.0 * delta_vak, teacher["ADP"])
    np.testing.assert_allclose(native["AMP"] + delta_vak + missing, teacher["AMP"])


def test_vak_components_follow_declared_direction() -> None:
    params = {
        "vmax_VAK": 2.0,
        "vmax_VAK_rev": 1.0,
        "km_ADP": 1.0,
        "km_AMP": 1.0,
        "km_ATP": 1.0,
    }
    forward, reverse, net = AUDIT._vak_components(
        params=params,
        adp=np.asarray([1.0]),
        amp=np.asarray([1.0]),
        atp=np.asarray([1.0]),
    )
    np.testing.assert_allclose(forward, [1.0])
    np.testing.assert_allclose(reverse, [0.25])
    np.testing.assert_allclose(net, [0.75])


def test_vak_components_match_the_ode_floor_for_depleted_pools() -> None:
    params = {
        "vmax_VAK": 2.0,
        "vmax_VAK_rev": 1.0,
        "km_ADP": 1.0,
        "km_AMP": 1.0,
        "km_ATP": 1.0,
    }
    forward, reverse, net = AUDIT._vak_components(
        params=params,
        adp=np.asarray([0.0]),
        amp=np.asarray([0.0]),
        atp=np.asarray([0.0]),
    )
    mm_floor = 1e-6 / (1.0 + 1e-6)
    np.testing.assert_allclose(forward, [2.0 * mm_floor])
    np.testing.assert_allclose(reverse, [mm_floor**2])
    np.testing.assert_allclose(net, forward - reverse)


def test_brodbar_contains_joint_adenylate_curves() -> None:
    time, curves = AUDIT._load_teachers()
    assert set(curves) == {"ATP", "ADP", "AMP"}
    assert len(time) == 14
    assert int(np.sum((time >= 1.0) & (time <= 3.0))) == 1


def test_classifier_prioritizes_total_pool_ownership() -> None:
    result = AUDIT._classify(
        {
            "native_total_change_J1_J3_mM": 0.4,
            "teacher_total_change_J1_J3_mM": -0.1,
            "VAK_balance_estimate_mean_spread": 1.0,
            "native_VAK_forward_time_fraction": 1.0,
            "joint_required_VAK_forward_time_fraction": 0.5,
            "joint_required_VAK_reverse_time_fraction": 1.0,
        }
    )
    assert result["classification"].startswith("adenylate-total source/sink")
    assert all(result["classification_gates"].values())
