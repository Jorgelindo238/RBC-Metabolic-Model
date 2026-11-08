"""Focused tests for the guarded mono-parameter km_NADH_NAD pass."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "run_km_nadh_nad_narrow_fla.py"
SPEC = importlib.util.spec_from_file_location("run_km_nadh_nad_narrow_fla", SCRIPT_PATH)
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


def test_bounds_are_reversible_around_mild_feedback_seed() -> None:
    bounds = PROFILE._local_bounds(
        {"km_NADH_NAD": 9.184380136644775},
        ("km_NADH_NAD",),
        2.0,
    )
    center, lower, upper = bounds["km_NADH_NAD"]
    assert lower == center / 2.0
    assert upper == center * 2.0


def test_fixed_km_atp_hk_is_preserved_exactly() -> None:
    value = 0.06014413339486139
    seed = {"km_ATP_HK": value}
    candidate = {"km_ATP_HK": value, "km_NADH_NAD": 4.6}
    assert PROFILE._validate_fixed_param_lock(seed, candidate) == value


def test_acceptance_allows_vldh_improvement_with_stable_glc_and_atp() -> None:
    seed = _payload()
    candidate = _payload()
    candidate["loss"] = 9.0
    candidate["teacher_flux_details"]["VLDH"]["nrmse"] = 0.95
    accepted, reasons = PROFILE._acceptance(seed, candidate)
    assert accepted is True
    assert reasons == ["candidate passed focused km_NADH_NAD redox guards"]


def test_acceptance_rejects_glc_regression() -> None:
    seed = _payload()
    candidate = _payload()
    candidate["loss"] = 9.0
    candidate["metrics"]["LAC"]["nrmse"] = 0.95
    candidate["metrics"]["GLC"]["nrmse"] = 1.04
    accepted, reasons = PROFILE._acceptance(seed, candidate)
    assert accepted is False
    assert "GLC nRMSE regressed beyond the 2% guard" in reasons


def test_acceptance_rejects_atp_floor_failure() -> None:
    seed = _payload()
    candidate = _payload()
    candidate["loss"] = 9.0
    candidate["teacher_flux_details"]["VLDH"]["nrmse"] = 0.95
    candidate["sim_final"]["ATP"] = 0.94
    accepted, reasons = PROFILE._acceptance(seed, candidate)
    assert accepted is False
    assert "ATP endpoint floor failed" in reasons
