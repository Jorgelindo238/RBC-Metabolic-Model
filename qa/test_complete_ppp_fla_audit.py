"""Tests for the complete PPP Flux Learning Analysis audit."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "src"), str(ROOT / "scripts")):
    if path not in sys.path:
        sys.path.insert(0, path)

SCRIPT_PATH = ROOT / "scripts" / "audit_complete_ppp_fla.py"
SPEC = importlib.util.spec_from_file_location("audit_complete_ppp_fla", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def _constant_fluxes() -> dict[str, np.ndarray]:
    return {
        reaction: np.asarray([float(index + 1), float(index + 1)])
        for index, reaction in enumerate(AUDIT._required_fluxes())
    }


def test_balance_specs_cover_every_ppp_pool() -> None:
    assert tuple(AUDIT.PPP_BALANCE_TERMS) == AUDIT.PPP_POOLS
    assert set(AUDIT.MEASURED_PPP_POOLS) | set(AUDIT.LATENT_PPP_POOLS) == set(
        AUDIT.PPP_POOLS
    )


def test_reconstruct_f6p_balance_supports_signed_reversible_fluxes() -> None:
    fluxes = _constant_fluxes()
    fluxes.update(
        {
            "VPGI": np.asarray([1.0, 1.0]),
            "VPFK": np.asarray([0.4, 0.4]),
            "VTKL2": np.asarray([-0.3, -0.3]),
            "VTAL": np.asarray([0.2, 0.2]),
        }
    )
    gross_input, gross_output, net, contributions = AUDIT._reconstruct_pool_balance(
        fluxes, "F6P"
    )
    assert np.allclose(gross_input, 1.2)
    assert np.allclose(gross_output, 0.7)
    assert np.allclose(net, 0.5)
    assert np.allclose(contributions["VTKL2"], -0.3)


def test_r5p_balance_includes_purine_connections() -> None:
    reactions = dict(AUDIT.PPP_BALANCE_TERMS["R5P"])
    assert reactions == {
        "VR5PI": 1.0,
        "VRKb": 1.0,
        "VRKa": 1.0,
        "VTKL1": -1.0,
        "VPRPPASe": -1.0,
    }


def test_ga3p_balance_includes_glycolysis_connections() -> None:
    reactions = dict(AUDIT.PPP_BALANCE_TERMS["GA3P"])
    assert reactions["VFDPA"] == 1.0
    assert reactions["VTPI"] == 1.0
    assert reactions["VGAPDH"] == -1.0
    assert reactions["VTKL1"] == 1.0
    assert reactions["VTKL2"] == 1.0
    assert reactions["VTAL"] == -1.0


def test_nonnegative_damping_matches_native_linear_rule() -> None:
    raw = np.asarray([-2e-3, -2e-3, 1e-3])
    concentration = np.asarray([5e-4, 2e-3, 2e-4])
    effective, adjustment = AUDIT._effective_native_balance(raw, concentration)
    assert np.allclose(effective, [-1e-3, -2e-3, 1e-3])
    assert np.allclose(adjustment, [1e-3, 0.0, 0.0])


def test_net_teacher_uses_concentration_derivative() -> None:
    time = np.asarray([1.0, 2.0, 3.0])
    curves = {
        "G6P": np.asarray([1.0, 3.0, 5.0]),
        "GO6P": np.asarray([2.0, 1.0, 0.0]),
        "F6P": np.asarray([4.0, 4.0, 4.0]),
    }
    teachers = AUDIT._build_net_flux_teachers(time, curves, dense_points=5)
    assert np.allclose(teachers["curves"]["G6P"]["dense_net_flux"], 2.0)
    assert np.allclose(teachers["curves"]["GO6P"]["dense_net_flux"], -1.0)
    assert np.allclose(teachers["curves"]["F6P"]["dense_net_flux"], 0.0)
    assert teachers["curves"]["G6P"]["identifiability"] == "net_pool_balance_only"


def test_teacher_metric_reports_exact_match() -> None:
    values = np.asarray([-1.0, 0.5, 2.0])
    metric = AUDIT._net_teacher_metric(values, values)
    assert metric["rmse"] == 0.0
    assert metric["nrmse"] == 0.0
    assert metric["sign_agreement"] == 1.0


def test_next_hypothesis_prefers_non_reversing_vtal_feedback() -> None:
    measured = []
    for candidate, f6p_nrmse, g6p_endpoint in (
        ("seed_irreversible", 10.0, 0.05),
        ("reversible_VTAL", 5.0, 0.20),
    ):
        measured.extend(
            [
                {
                    "candidate": candidate,
                    "pool": "F6P",
                    "concentration_nrmse": f6p_nrmse,
                    "concentration_endpoint_error": 0.1,
                },
                {
                    "candidate": candidate,
                    "pool": "G6P",
                    "concentration_nrmse": 1.0,
                    "concentration_endpoint_error": g6p_endpoint,
                },
            ]
        )
    context = [
        {"candidate": "seed_irreversible", "pool": "F16BP", "endpoint_error": 0.1},
        {"candidate": "reversible_VTAL", "pool": "F16BP", "endpoint_error": 0.2},
    ]
    routing = [
        {
            "candidate": "seed_irreversible",
            "window": "late_40_46d",
            "mean_net_F6P_PPP_return": 0.01,
            "mean_reverse_F6P_drain": 0.0,
        },
        {
            "candidate": "reversible_VTAL",
            "window": "late_40_46d",
            "mean_net_F6P_PPP_return": -0.01,
            "mean_reverse_F6P_drain": 0.02,
        },
    ]
    decision, _, _ = AUDIT._select_next_hypothesis(
        measured, context, routing, 0.0, 1e-12, []
    )
    assert "forward-only VTAL product-feedback" in decision


def test_next_hypothesis_supports_short_smoke_window() -> None:
    measured = []
    for candidate, f6p_nrmse, g6p_endpoint in (
        ("seed_irreversible", 10.0, 0.05),
        ("reversible_VTAL", 5.0, 0.20),
    ):
        measured.extend(
            [
                {
                    "candidate": candidate,
                    "pool": "F6P",
                    "concentration_nrmse": f6p_nrmse,
                    "concentration_endpoint_error": 0.1,
                },
                {
                    "candidate": candidate,
                    "pool": "G6P",
                    "concentration_nrmse": 1.0,
                    "concentration_endpoint_error": g6p_endpoint,
                },
            ]
        )
    context = [
        {"candidate": "seed_irreversible", "pool": "F16BP", "endpoint_error": 0.1},
        {"candidate": "reversible_VTAL", "pool": "F16BP", "endpoint_error": 0.2},
    ]
    routing = [
        {
            "candidate": "seed_irreversible",
            "window": "full_1_46d",
            "mean_net_F6P_PPP_return": 0.01,
            "mean_reverse_F6P_drain": 0.0,
        },
        {
            "candidate": "reversible_VTAL",
            "window": "full_1_46d",
            "mean_net_F6P_PPP_return": -0.01,
            "mean_reverse_F6P_drain": 0.02,
        },
    ]
    _, _, evidence = AUDIT._select_next_hypothesis(
        measured, context, routing, 0.0, 1e-12, []
    )
    assert evidence["routing_comparison_window"] == "full_1_46d"


def test_latent_default_initialization_precedes_kinetic_probe() -> None:
    initialization = [
        {
            "pool": "GA3P",
            "current_initial_mM": 1.0,
            "historical_JA_initial_mM": 0.007589,
            "current_to_historical_ratio": 131.77,
            "current_uses_generic_1mM_default": True,
            "large_latent_initialization_discrepancy": True,
        }
    ]
    decision, _, evidence = AUDIT._select_next_hypothesis(
        [], [], [], 0.0, 1e-12, initialization
    )
    assert "initial-condition replay" in decision
    assert evidence["problematic_latent_initializations"][0]["pool"] == "GA3P"
