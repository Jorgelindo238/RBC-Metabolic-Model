from __future__ import annotations

import pytest

from scripts.run_vpep_vpk_coupled_fla import _acceptance, _directed_bounds


def _payload() -> dict:
    return {
        "loss": 10.0,
        "metrics": {
            "EGLC": {"nrmse": 0.12, "endpoint_error": 0.01},
            "ELAC": {"nrmse": 0.32},
            "GLC": {"nrmse": 6.0},
            "G6P": {"nrmse": 12.0},
            "LAC": {"nrmse": 0.95},
            "ATP": {"nrmse": 0.90},
            "PEP": {"nrmse": 0.30},
        },
        "slopes": {"EGLC": 1.0},
        "teacher_flux_details": {"VEGLC": {"nrmse": 1.0}, "VELAC": {"nrmse": 0.5}, "VLDH": {"nrmse": 0.7}},
        "routing_metrics": {"PEP_to_VPK_share": 0.07},
        "sim_final": {"ATP": 0.00005},
    }


def test_directed_bounds_are_one_way() -> None:
    bounds = _directed_bounds({"vmax_VPEP_PASE": 8.95, "vmax_VPK": 0.713}, vpep_lower=0.5, vpep_upper_ratio=0.5, vpk_upper=5.0)
    assert bounds["vmax_VPEP_PASE"][2] < bounds["vmax_VPEP_PASE"][0]
    assert bounds["vmax_VPK"][1] == pytest.approx(0.713)
    assert bounds["vmax_VPK"][2] > bounds["vmax_VPK"][1]


def test_acceptance_requires_pep_and_g6p_guards() -> None:
    neutral = _payload()
    seed = _payload()
    candidate = _payload()
    candidate["loss"] = 8.0
    candidate["metrics"]["GLC"]["nrmse"] = 5.5
    candidate["metrics"]["ATP"]["nrmse"] = 0.85
    candidate["metrics"]["G6P"]["nrmse"] = 11.5
    candidate["metrics"]["PEP"]["nrmse"] = 0.8
    candidate["sim_final"]["ATP"] = 0.00008
    candidate["routing_metrics"]["PEP_to_VPK_share"] = 0.15
    accepted, reasons = _acceptance(neutral, seed, candidate)
    assert accepted is True
    assert reasons == ["candidate passed coupled routing, trajectory, concentration, and teacher-flux guards"]


def test_acceptance_rejects_pep_transient_even_with_better_atp() -> None:
    neutral = _payload()
    seed = _payload()
    candidate = _payload()
    candidate["loss"] = 8.0
    candidate["metrics"]["GLC"]["nrmse"] = 5.5
    candidate["metrics"]["ATP"]["nrmse"] = 0.85
    candidate["metrics"]["PEP"]["nrmse"] = 4.0
    candidate["sim_final"]["ATP"] = 0.00008
    candidate["routing_metrics"]["PEP_to_VPK_share"] = 0.15
    accepted, reasons = _acceptance(neutral, seed, candidate)
    assert accepted is False
    assert "PEP trajectory guard failed" in reasons
