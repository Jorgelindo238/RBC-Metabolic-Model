"""Focused tests for the guarded mono-parameter km_ATP_HK pass."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "run_km_atp_hk_narrow_fla.py"
SPEC = importlib.util.spec_from_file_location("run_km_atp_hk_narrow_fla", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
PROFILE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROFILE)


def _payload() -> dict:
    metrics = {
        name: {"nrmse": 1.0, "endpoint_error": 0.1}
        for name in ("EGLC", "ELAC", "GLC", "LAC", "PYR")
    }
    energy_metrics = {
        name: {"nrmse": 1.0, "endpoint_error": 0.1}
        for name in ("ATP", "PEP", "G6P")
    }
    return {
        "loss": 10.0,
        "metrics": metrics,
        "energy_metrics": energy_metrics,
        "sim_final": {"ATP": 1.0},
        "teacher_flux_details": {
            name: {"nrmse": 1.0}
            for name in ("VEGLC", "VELAC", "VLDH")
        },
        "guard_violations": [],
    }


def test_bounds_are_reversible_and_narrow() -> None:
    bounds = PROFILE._local_bounds(
        {"km_ATP_HK": 0.06014413339486139},
        ("km_ATP_HK",),
        2.0,
    )
    center, lower, upper = bounds["km_ATP_HK"]
    assert lower < center < upper
    assert lower == 0.05
    assert upper == center * 2.0


def test_acceptance_rejects_glc_regression_even_when_loss_improves() -> None:
    seed = _payload()
    candidate = _payload()
    candidate["loss"] = 9.0
    candidate["metrics"]["GLC"]["nrmse"] = 1.0
    accepted, reasons = PROFILE._acceptance(seed, candidate)
    assert accepted is False
    assert "GLC nRMSE improvement below 2%" in reasons


def test_final_value_prefers_explicit_sim_final() -> None:
    payload = {"sim_final": {"ATP": 0.25}, "trajectory_guard": []}
    assert PROFILE._final_value(payload, "ATP") == 0.25
