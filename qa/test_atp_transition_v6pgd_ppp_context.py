"""Tests for the J1-J10 ATP transition audit."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "src"), str(ROOT / "scripts")):
    if path not in sys.path:
        sys.path.insert(0, path)

SCRIPT_PATH = ROOT / "scripts" / "audit_atp_transition_v6pgd_ppp_context.py"
SPEC = importlib.util.spec_from_file_location(
    "audit_atp_transition_v6pgd_ppp_context", SCRIPT_PATH
)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_exact_atp_reaction_contract() -> None:
    assert AUDIT.ATP_PRODUCTION == ("VPGK", "VPK", "VAK")
    assert AUDIT.ATP_CONSUMPTION == (
        "VHK",
        "VPFK",
        "VAK2",
        "VGLNS",
        "VGLUCYS",
        "VGSS",
        "VSAM",
        "VRKa",
        "VPRPPASe",
        "VGMPS",
        "VGMPK",
        "VNDPK",
        "VOPLAH",
    )


def test_atp_balance_uses_signed_production_minus_consumption() -> None:
    fluxes = {
        reaction: np.full(3, 2.0) for reaction in AUDIT.ATP_PRODUCTION
    }
    fluxes.update(
        {reaction: np.full(3, 0.25) for reaction in AUDIT.ATP_CONSUMPTION}
    )
    production, consumption, net = AUDIT._atp_balance(fluxes)
    assert np.allclose(production, 6.0)
    assert np.allclose(consumption, 3.25)
    assert np.allclose(net, 2.75)


def test_effective_atp_balance_reproduces_native_nonnegative_damping() -> None:
    raw = np.asarray([-0.2, -0.2, 0.1])
    atp = np.asarray([5e-4, 2e-3, 5e-4])
    effective, adjustment = AUDIT._effective_atp_balance(raw, atp)
    assert np.allclose(effective, [-0.1, -0.2, 0.1])
    assert np.allclose(adjustment, [0.1, 0.0, 0.0])


def test_effective_atp_balance_reproduces_native_floor_at_zero() -> None:
    raw = np.asarray([-2.0])
    effective, adjustment = AUDIT._effective_atp_balance(raw, np.asarray([0.0]))
    expected = raw * AUDIT.MIN_CONCENTRATION / AUDIT.NONEG_THRESHOLD
    assert np.allclose(effective, expected)
    assert np.allclose(adjustment, expected - raw)


def test_saved_latent_override_changes_only_seven_states() -> None:
    base = np.arange(114, dtype=float) + 1.0
    values = {pool: index + 0.1 for index, pool in enumerate(AUDIT.LATENT_PPP_POOLS)}
    state = AUDIT._state_with_saved_latent(base, values)
    changed = set(np.flatnonzero(state != base).tolist())
    assert changed == set(AUDIT.LATENT_INDICES.tolist())


def test_candidate_changes_only_vmax_v6pgd() -> None:
    seed = {"vmax_VHK": 1.0, "vmax_VPFK": 2.0}
    candidate = AUDIT._candidate_params(seed)
    assert candidate["vmax_V6PGD"] == 9.0
    assert candidate["vmax_VHK"] == seed["vmax_VHK"]
    assert candidate["vmax_VPFK"] == seed["vmax_VPFK"]


def test_transition_windows_match_recorded_contract() -> None:
    assert AUDIT.WINDOWS == (
        ("J1_J2", 1.0, 2.0),
        ("day_2_4", 2.0, 4.0),
        ("day_4_6", 4.0, 6.0),
        ("day_6_8", 6.0, 8.0),
        ("day_8_10", 8.0, 10.0),
    )


def test_first_fraction_loss_detects_sustained_drop() -> None:
    time = np.arange(1.0, 4.25, 0.25)
    values = np.asarray([1.0, 1.0, 0.4, 0.8, 0.4, 0.4, 0.4, 0.4, 0.3, 0.3, 0.3, 0.3, 0.3])
    result = AUDIT._first_fraction_loss(
        time, values, fraction=0.5, duration=0.5
    )
    assert result == 2.0


def test_classifier_assigns_vpgk_pulse_exhaustion_with_vhk_demand() -> None:
    result = AUDIT._classify_transition(
        {
            "production_half_loss_day": 1.2,
            "consumption_half_loss_day": 1.3,
            "ATP_collapse_to_F6P_divergence_delay_day": 2.0,
            "factors_at_ATP_collapse": {
                "VPGK_vmax_utilization": 0.01,
                "VPK_vmax_utilization": 0.6,
                "VPGK_ADP_ATP_drive": 0.8,
            },
            "states_at_ATP_collapse": {"B13PG": 1e-5},
            "consumer_shares_at_ATP_collapse": {"VHK": 0.75},
        }
    )
    assert result["classification"].startswith("VPGK/B13PG")
    assert all(result["classification_gates"].values())
