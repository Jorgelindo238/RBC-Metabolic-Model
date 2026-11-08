from __future__ import annotations

import pytest

from scripts.run_vpep_pase_vpk_coupled_fla import (
    VPEP_PARAM,
    VPK_PARAM,
    _coupled_acceptance,
    _directional_bounds,
)


def _payload() -> dict:
    return {
        "loss": 10.0,
        VPEP_PARAM: 8.95,
        VPK_PARAM: 0.713,
        "metrics": {
            "EGLC": {"nrmse": 0.11, "endpoint_error": 0.04},
            "ELAC": {"nrmse": 0.32, "endpoint_error": 0.28},
            "GLC": {"nrmse": 5.9, "endpoint_error": 10.0},
            "LAC": {"nrmse": 0.95, "endpoint_error": 0.97},
            "ATP": {"nrmse": 1.01, "endpoint_error": 1.0},
            "PEP": {"nrmse": 0.30, "endpoint_error": 0.90},
            "G6P": {"nrmse": 12.9, "endpoint_error": 2.0},
        },
        "slope_metrics": {"EGLC": 0.96},
        "teacher_flux_details": {
            "VEGLC": {"nrmse": 0.97},
            "VELAC": {"nrmse": 0.52},
            "VLDH": {"nrmse": 0.67},
        },
        "routing_metrics": {"PEP_to_VPK_share": 0.075},
        "sim_final": {"ATP": 0.000056},
    }


def test_directional_bounds_only_move_in_requested_directions() -> None:
    bounds = _directional_bounds(
        {VPEP_PARAM: 8.95, VPK_PARAM: 0.713},
        vpep_lower_ratio=0.05,
        vpep_upper_ratio=0.999,
        vpk_lower_ratio=1.001,
        vpk_upper_multiplier=10.0,
    )
    assert bounds[VPEP_PARAM][1] < bounds[VPEP_PARAM][2] < bounds[VPEP_PARAM][0]
    assert bounds[VPK_PARAM][0] < bounds[VPK_PARAM][1] < bounds[VPK_PARAM][2]


def test_directional_bounds_reject_bidirectional_vpk_range() -> None:
    with pytest.raises(ValueError, match="VPK ratios"):
        _directional_bounds(
            {VPEP_PARAM: 8.95, VPK_PARAM: 0.713},
            vpep_lower_ratio=0.05,
            vpep_upper_ratio=0.999,
            vpk_lower_ratio=0.9,
            vpk_upper_multiplier=10.0,
        )


def test_coupled_acceptance_requires_g6p_guard() -> None:
    neutral = _payload()
    mild = _payload()
    candidate = _payload()
    candidate["loss"] = 8.0
    candidate[VPEP_PARAM] = 2.0
    candidate[VPK_PARAM] = 2.0
    candidate["metrics"]["GLC"]["nrmse"] = 5.4
    candidate["metrics"]["ATP"]["nrmse"] = 0.99
    candidate["metrics"]["G6P"]["nrmse"] = 14.0
    candidate["sim_final"]["ATP"] = 0.00008
    candidate["routing_metrics"]["PEP_to_VPK_share"] = 0.20
    accepted, reasons = _coupled_acceptance(neutral, mild, candidate, vpk_seed=0.713)
    assert accepted is False
    assert "G6P trajectory guard failed" in reasons


def test_coupled_acceptance_passes_balanced_candidate() -> None:
    neutral = _payload()
    mild = _payload()
    candidate = _payload()
    candidate["loss"] = 8.0
    candidate[VPEP_PARAM] = 2.0
    candidate[VPK_PARAM] = 2.0
    candidate["metrics"]["GLC"]["nrmse"] = 5.4
    candidate["metrics"]["ATP"]["nrmse"] = 0.99
    candidate["metrics"]["G6P"]["nrmse"] = 12.8
    candidate["sim_final"]["ATP"] = 0.00008
    candidate["routing_metrics"]["PEP_to_VPK_share"] = 0.20
    accepted, reasons = _coupled_acceptance(neutral, mild, candidate, vpk_seed=0.713)
    assert accepted is True
    assert reasons == ["coupled candidate passed PEP, G6P, energy, extracellular, and teacher-flux guards"]
