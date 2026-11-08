"""Tests for the investment-phase G6P/F6P flux-matching audit."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "audit_investment_phase_flux_matching.py"
SPEC = importlib.util.spec_from_file_location("audit_investment_phase_flux_matching", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def _synthetic_fluxes() -> dict[str, np.ndarray]:
    return {
        "VHK": np.asarray([5.0, 5.0, 5.0]),
        "VPGI": np.asarray([3.0, 3.5, 4.0]),
        "VG6PDH": np.asarray([1.0, 1.0, 1.0]),
        "VPFK": np.asarray([2.5, 3.0, 3.5]),
        "VTKL2": np.asarray([0.2, 0.2, 0.2]),
        "VTAL": np.asarray([0.1, 0.1, 0.1]),
    }


def test_reconstructs_exact_g6p_and_f6p_balances() -> None:
    fluxes = _synthetic_fluxes()
    g6p_input, g6p_output, g6p_net = AUDIT._reconstruct_balance(fluxes, "G6P")
    f6p_input, f6p_output, f6p_net = AUDIT._reconstruct_balance(fluxes, "F6P")
    assert np.allclose(g6p_input, fluxes["VHK"])
    assert np.allclose(g6p_output, fluxes["VPGI"] + fluxes["VG6PDH"])
    assert np.allclose(g6p_net, fluxes["VHK"] - fluxes["VPGI"] - fluxes["VG6PDH"])
    assert np.allclose(f6p_input, fluxes["VPGI"] + fluxes["VTKL2"] + fluxes["VTAL"])
    assert np.allclose(f6p_output, fluxes["VPFK"])
    assert np.allclose(f6p_net, fluxes["VPGI"] + fluxes["VTKL2"] + fluxes["VTAL"] - fluxes["VPFK"])


def test_balance_closure_accepts_exact_native_derivative() -> None:
    _, _, net = AUDIT._reconstruct_balance(_synthetic_fluxes(), "G6P")
    assert AUDIT._validate_balance_closure(net, net.copy(), pool="G6P") == 0.0


def test_balance_closure_rejects_inconsistent_derivative() -> None:
    _, _, net = AUDIT._reconstruct_balance(_synthetic_fluxes(), "F6P")
    try:
        AUDIT._validate_balance_closure(net, net + 1e-3, pool="F6P")
    except RuntimeError as exc:
        assert "F6P balance closure failed" in str(exc)
    else:
        raise AssertionError("inconsistent F6P derivative should fail")


def test_window_summary_reports_flux_matching_and_integral_closure() -> None:
    time = np.asarray([1.0, 1.5, 2.0, 10.0, 15.0, 20.0, 40.0, 43.0, 46.0])
    frame = pd.DataFrame({"candidate": "seed", "time_day": time})
    for pool in AUDIT.CONTEXT_POOLS:
        frame[pool] = 2.0 * time
    for reaction in AUDIT.AUDITED_FLUXES:
        frame[reaction] = 1.0
    for pool in AUDIT.AUDITED_POOLS:
        frame[f"{pool}_input_flux"] = 3.0
        frame[f"{pool}_output_flux"] = 1.0
        frame[f"d{pool}_dt_flux"] = 2.0
        frame[f"{pool}_pointwise_closure_error"] = 0.0
    rows = AUDIT._window_rows(frame)
    early_g6p = next(
        row for row in rows if row["pool"] == "G6P" and row["window"] == "early_1_2d"
    )
    assert early_g6p["output_input_ratio"] == 1.0 / 3.0
    assert early_g6p["concentration_change"] == 2.0
    assert early_g6p["integrated_net_flux"] == 2.0
    assert early_g6p["integral_residual"] == 0.0


def test_decision_separates_kinetic_review_from_ode_correction() -> None:
    decision, _ = AUDIT._audit_decision(0.0, 1e-12)
    assert "kinetic flux matching" in decision
    decision, _ = AUDIT._audit_decision(1e-6, 1e-12)
    assert "correct the ODE" in decision


def test_key_findings_attribute_f6p_input_to_ppp_return() -> None:
    rows = []
    for candidate in ("seed", "km_ADP_ATP_0.75x"):
        for pool in AUDIT.AUDITED_POOLS:
            for window in ("early_1_2d", "mid_10_20d", "late_40_46d"):
                scale = 2.0 if candidate != "seed" else 1.0
                rows.append(
                    {
                        "candidate": candidate,
                        "pool": pool,
                        "window": window,
                        "mean_input_flux": 4.0 * scale,
                        "mean_output_flux": 2.0 * scale,
                        "output_input_ratio": 0.5,
                        "mean_net_flux": 2.0 * scale,
                        "mean_VHK": 4.0 * scale,
                        "mean_VPGI": 1.0 * scale,
                        "mean_VG6PDH": 1.0 * scale,
                        "mean_VPFK": 2.0 * scale,
                        "mean_VTKL2": 1.0 * scale,
                        "mean_VTAL": 2.0 * scale,
                        "concentration_change": 0.5,
                    }
                )
    findings = AUDIT._key_flux_findings(rows)
    assert findings["seed_f6p_ppp_return_share"]["early_1_2d"] == 0.75
    assert findings["candidate_late_relative_changes"]["VHK"] == 1.0


def test_nonnegative_damping_reconstructs_effective_native_derivative() -> None:
    net = np.asarray([-2e-3, -2e-3])
    concentration = np.asarray([5e-4, 2e-3])
    effective = np.asarray([-1e-3, -2e-3])
    reconstructed = net.copy()
    mask = (concentration < 1e-3) & (net < 0.0)
    reconstructed[mask] *= concentration[mask] / 1e-3
    assert np.allclose(reconstructed, effective)
    assert AUDIT._validate_balance_closure(
        reconstructed,
        effective,
        pool="F6P",
    ) == 0.0
