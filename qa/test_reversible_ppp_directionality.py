"""Tests for optional reversible VTKL2/VTAL kinetics and diagnostics."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
SCRIPT_DIR = ROOT / "scripts"
for path in (str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from equadiff_brodbar import _compute_vtal_flux, _compute_vtkl2_flux, mm  # noqa: E402


SCRIPT_PATH = SCRIPT_DIR / "diagnose_reversible_ppp_directionality.py"
SPEC = importlib.util.spec_from_file_location("diagnose_reversible_ppp_directionality", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
DIAGNOSTIC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DIAGNOSTIC)


def _state() -> np.ndarray:
    x = np.zeros(114, dtype=float)
    x[2] = 0.4
    x[7] = 0.5
    x[8] = 0.3
    x[9] = 0.6
    x[10] = 0.2
    return x


def test_vtkl2_default_is_historical_forward_mm() -> None:
    x = _state()
    expected = 12.0 * mm(x[8], 0.03) * mm(x[7], 0.05)
    actual = _compute_vtkl2_flux(x, {}, 12.0, 0.03, 0.05, 0.207, 0.02)
    assert actual == expected


def test_vtkl2_full_reversible_blend_subtracts_product_term() -> None:
    x = _state()
    params = {
        "kinetic_family_VTKL2": DIAGNOSTIC.REVERSIBLE_FAMILY,
        "hybrid_blend_VTKL2": 1.0,
        "hybrid_reverse_scale_VTKL2": 1.0,
    }
    expected = 12.0 * (
        mm(x[8], 0.03) * mm(x[7], 0.05)
        - mm(x[2], 0.207) * mm(x[10], 0.02)
    )
    assert _compute_vtkl2_flux(x, params, 12.0, 0.03, 0.05, 0.207, 0.02) == expected


def test_vtal_zero_blend_preserves_forward_flux() -> None:
    x = _state()
    params = {
        "kinetic_family_VTAL": DIAGNOSTIC.REVERSIBLE_FAMILY,
        "hybrid_blend_VTAL": 0.0,
        "hybrid_reverse_scale_VTAL": 1.0,
    }
    expected = 14.0 * mm(x[10], 0.02) * mm(x[9], 0.05)
    assert _compute_vtal_flux(x, params, 14.0, 0.02, 0.05, 0.207, 0.03) == expected


def test_vtal_reversible_flux_can_run_in_reverse() -> None:
    x = _state()
    x[10] = 0.0
    params = {
        "kinetic_family_VTAL": DIAGNOSTIC.REVERSIBLE_FAMILY,
        "hybrid_blend_VTAL": 1.0,
        "hybrid_reverse_scale_VTAL": 1.0,
    }
    assert _compute_vtal_flux(x, params, 14.0, 0.02, 0.05, 0.207, 0.03) < 0.0


def test_fixed_case_changes_only_configuration_toggles() -> None:
    seed = {"vmax_VTKL2": 12.0, "km_E4P": 0.03}
    toggles = DIAGNOSTIC._fixed_reversible_toggles("VTKL2")
    params, changed = DIAGNOSTIC._case_params(seed, toggles)
    assert changed == sorted(toggles)
    assert params["vmax_VTKL2"] == seed["vmax_VTKL2"]
    assert params["km_E4P"] == seed["km_E4P"]


def test_gross_f6p_balance_reclassifies_negative_ppp_flux_as_outflow() -> None:
    frame = pd.DataFrame(
        {
            "VHK": [2.0],
            "VPGI": [1.0],
            "VG6PDH": [0.5],
            "VPFK": [0.4],
            "VTKL2": [-0.3],
            "VTAL": [0.2],
        }
    )
    result = DIAGNOSTIC._gross_balance_columns(frame)
    assert result["F6P_gross_inflow"].iloc[0] == 1.2
    assert result["F6P_gross_outflow"].iloc[0] == 0.7
    assert result["PPP_reverse_F6P_drain"].iloc[0] == 0.3
    assert np.isclose(result["PPP_net_F6P_return"].iloc[0], -0.1)


def test_decision_advances_only_guarded_f6p_improvement() -> None:
    assessments = [
        {
            "candidate": "reversible_VTKL2",
            "f6p_relative_nrmse_improvement": 0.04,
            "fixed_hypothesis_feasible": False,
        },
        {
            "candidate": "reversible_both",
            "f6p_relative_nrmse_improvement": 0.12,
            "fixed_hypothesis_feasible": True,
        },
    ]
    decision, _, selected = DIAGNOSTIC._decision(assessments)
    assert "advance reversible_both" in decision
    assert selected == "reversible_both"
