from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import screen_vmax_vdpgm_qss_b13pg as SCREEN  # noqa: E402


def test_deterministic_grid_contains_seed_and_high_capacity_points():
    assert SCREEN.MULTIPLIERS == (0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0)
    assert "NAD" in SCREEN.STATE_NAMES
    assert "NAD" not in SCREEN.OBSERVED_STATE_NAMES


def test_candidate_contract_changes_only_vmax_vdpgm():
    seed = {"vmax_VDPGM": 2.0, "vmax_V23DPGP": 3.0, "km_B13PG": 1.0}
    candidate, seed_value, changed = SCREEN._candidate_params(seed, 4.0)
    assert seed_value == 2.0
    assert candidate["vmax_VDPGM"] == 8.0
    assert candidate["vmax_V23DPGP"] == seed["vmax_V23DPGP"]
    assert changed == ["vmax_VDPGM"]


def test_exact_balance_definitions():
    fluxes = {
        "VDPGM": np.asarray([2.0]),
        "V23DPGP": np.asarray([0.5]),
        "VPGK": np.asarray([3.0]),
        "VPGM": np.asarray([1.0]),
        "VPHGDH": np.asarray([0.25]),
    }
    assert np.allclose(SCREEN._raw_balance(fluxes, SCREEN.B23PG_TERMS), [1.5])
    assert np.allclose(SCREEN._raw_balance(fluxes, SCREEN.P3G_TERMS), [2.25])


def test_atp_collapse_guard_rejects_advanced_collapse():
    assert SCREEN._collapse_noninferior(2.0, 2.2) is False
    assert SCREEN._collapse_noninferior(2.15, 2.2) is True
    assert SCREEN._collapse_noninferior(None, 2.2) is True


def test_selector_requires_all_guards():
    selected = SCREEN._select_best(
        [
            {
                "candidate": "bad",
                "guard_pass": False,
                "B23PG_nrmse": 0.1,
                "B23PG_endpoint_error": 0.1,
                "multiplier": 2.0,
            },
            {
                "candidate": "good",
                "guard_pass": True,
                "B23PG_nrmse": 0.2,
                "B23PG_endpoint_error": 0.2,
                "multiplier": 4.0,
            },
        ]
    )
    assert selected == "good"


def test_plateau_classification_uses_high_capacity_response():
    metrics = {
        SCREEN._label(16.0): {
            "VDPGM_integral_mM": 1.0,
            "B13PG_mean_occupancy": 0.1,
            "GAPDH_mean_redox_drive": 0.1,
        },
        SCREEN._label(32.0): {
            "VDPGM_integral_mM": 1.05,
            "B13PG_mean_occupancy": 0.001,
            "GAPDH_mean_redox_drive": 0.2,
        },
    }
    result = SCREEN._plateau_classification(metrics)
    assert result["classification"] == "B13PG_substrate_limited_plateau"
