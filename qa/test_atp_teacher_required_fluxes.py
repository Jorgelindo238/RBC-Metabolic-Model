"""Tests for ATP-teacher-required VPGK and VGAPDH reconstruction."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "src"), str(ROOT / "scripts")):
    if path not in sys.path:
        sys.path.insert(0, path)

SCRIPT = ROOT / "scripts" / "reconstruct_atp_teacher_required_fluxes.py"
SPEC = importlib.util.spec_from_file_location("required_atp_fluxes", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_atp_row_has_only_one_observation_inside_j1_j3() -> None:
    time, values = AUDIT._load_atp_data()
    assert len(time) == len(values) == 14
    assert int(np.sum((time >= 1.0) & (time <= 3.0))) == 1
    assert time[1] == 4.0


def test_required_vpgk_closes_teacher_balance() -> None:
    derivative = np.asarray([0.1, -0.2])
    consumption = np.asarray([2.0, 3.0])
    vpk = np.asarray([0.4, 0.5])
    vak = np.asarray([0.1, 0.3])
    required = AUDIT._required_vpgk(derivative, consumption, vpk, vak)
    reconstructed = required + vpk + vak - consumption
    np.testing.assert_allclose(reconstructed, derivative)


def test_required_vgapdh_closes_b13pg_balance() -> None:
    derivative = np.asarray([0.0, 0.2])
    vpgk = np.asarray([1.0, 2.0])
    vdpgm = np.asarray([0.1, 0.2])
    required = AUDIT._required_vgapdh(derivative, vpgk, vdpgm)
    np.testing.assert_allclose(required - vpgk - vdpgm, derivative, atol=1e-15)


def test_feasibility_detects_negative_and_ceiling_violations() -> None:
    frame = pd.DataFrame(
        {
            "time_day": [1.0, 2.0, 3.0],
            "required": [-1.0, 1.0, 3.0],
            "native": [0.5, 0.5, 0.5],
        }
    )
    result = AUDIT._feasibility(
        frame=frame,
        reaction="VPGK",
        required_column="required",
        native_column="native",
        vmax=2.0,
    )
    assert result["time_fraction_hard_feasible"] == 1.0 / 3.0
    assert result["first_negative_day"] == 1.0
    assert result["first_hard_ceiling_exceedance_day"] == 3.0


def test_classifier_blocks_underconstrained_sign_inversion() -> None:
    result = AUDIT._classify(
        primary_vpgk={"time_fraction_nonnegative": 0.8},
        primary_vgapdh={"hard_ceiling_excess_integral": 0.1},
        observed_points_j1_j3=1,
        pchip_linear_integral_difference=0.001,
    )
    assert result["classification"].startswith("ATP-only inversion")
    assert all(result["classification_gates"].values())
