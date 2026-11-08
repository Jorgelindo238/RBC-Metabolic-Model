from __future__ import annotations

import math

import pytest

from scripts.run_vpep_pase_downward_fla import (
    _downward_bounds,
    _fixed_mild_feedback,
    _focused_acceptance,
)


def _payload() -> dict:
    return {
        "loss": 10.0,
        "metrics": {
            "EGLC": {"nrmse": 0.12, "endpoint_error": 0.01},
            "ELAC": {"nrmse": 0.32, "endpoint_error": 0.28},
            "GLC": {"nrmse": 6.0, "endpoint_error": 10.0},
            "LAC": {"nrmse": 0.95, "endpoint_error": 0.97},
            "ATP": {"nrmse": 0.90, "endpoint_error": 0.90},
            "PEP": {"nrmse": 0.30, "endpoint_error": 0.90},
        },
        "slope_metrics": {"EGLC": 1.0},
        "teacher_flux_details": {
            "VEGLC": {"nrmse": 1.0},
            "VELAC": {"nrmse": 0.5},
            "VLDH": {"nrmse": 0.7},
        },
        "routing_metrics": {"PEP_to_VPK_share": 0.07},
        "sim_final": {"ATP": 0.00005},
    }


def test_downward_bounds_ignore_legacy_terminal_upper_bound() -> None:
    center, lower, upper = _downward_bounds(8.95, lower=0.01, upper_ratio=0.999)
    assert center == pytest.approx(8.95)
    assert lower == pytest.approx(0.01)
    assert 2.0 < upper < center


def test_downward_bounds_reject_non_decreasing_search() -> None:
    with pytest.raises(ValueError, match="strictly between"):
        _downward_bounds(8.95, lower=0.01, upper_ratio=1.0)


def test_fixed_feedback_is_explicit_and_reversible() -> None:
    params = _fixed_mild_feedback(strength=0.1, km_glc=8.5, hill=0.7, import_cap=5.0)
    assert params["kinetic_family_VEGLC"] == "transport_depletion_gate_import_feedback"
    assert params["transport_gate_feedback_strength_VEGLC"] == pytest.approx(0.1)
    assert params["transport_gate_import_cap_VEGLC"] == pytest.approx(5.0)


def test_focused_acceptance_requires_glucose_energy_and_route_improvement() -> None:
    neutral = _payload()
    mild = _payload()
    candidate = _payload()
    candidate["loss"] = 8.0
    candidate["metrics"]["GLC"]["nrmse"] = 5.5
    candidate["metrics"]["ATP"]["nrmse"] = 0.85
    candidate["sim_final"]["ATP"] = 0.00008
    candidate["routing_metrics"]["PEP_to_VPK_share"] = 0.15
    accepted, reasons = _focused_acceptance(neutral, mild, candidate)
    assert accepted is True
    assert reasons == ["focused candidate passed concentration, energy-routing, and teacher-flux guards"]


def test_focused_acceptance_rejects_energy_only_compensation() -> None:
    neutral = _payload()
    mild = _payload()
    candidate = _payload()
    candidate["loss"] = 8.0
    candidate["metrics"]["ATP"]["nrmse"] = 0.80
    candidate["sim_final"]["ATP"] = 0.00008
    candidate["routing_metrics"]["PEP_to_VPK_share"] = 0.15
    accepted, reasons = _focused_acceptance(neutral, mild, candidate)
    assert accepted is False
    assert "GLC nRMSE did not improve by at least 5%" in reasons
    assert all(math.isfinite(float(value)) for value in (candidate["loss"], candidate["sim_final"]["ATP"]))


def test_focused_acceptance_rejects_pep_transient_accumulation() -> None:
    neutral = _payload()
    mild = _payload()
    candidate = _payload()
    candidate["loss"] = 8.0
    candidate["metrics"]["GLC"]["nrmse"] = 5.5
    candidate["metrics"]["ATP"]["nrmse"] = 0.85
    candidate["metrics"]["PEP"]["nrmse"] = 20.0
    candidate["sim_final"]["ATP"] = 0.00008
    candidate["routing_metrics"]["PEP_to_VPK_share"] = 0.15
    accepted, reasons = _focused_acceptance(neutral, mild, candidate)
    assert accepted is False
    assert "PEP trajectory guard failed" in reasons
