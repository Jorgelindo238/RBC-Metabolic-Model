"""Tests for the directed km_ADP_ATP production-side screen."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "screen_km_adp_atp_production.py"
SPEC = importlib.util.spec_from_file_location("screen_km_adp_atp_production", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
SCREEN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCREEN)


def _metric(nrmse: float = 1.0, endpoint: float = 0.1, final: float = 1.0) -> dict:
    return {"nrmse": nrmse, "endpoint_error": endpoint, "final_value": final}


def _payload() -> dict:
    return {
        "concentration_metrics": {
            name: _metric()
            for name in SCREEN.METABOLITE_TARGETS
        },
        "teacher_flux_metrics": {
            name: {"nrmse": 1.0}
            for name in SCREEN.TEACHER_FLUXES
        },
        "balance_summary": {
            "ATP_production_flux": {"late_mean": 1.0},
        },
        "guard_reasons": [],
    }


def test_directed_values_are_strictly_downward() -> None:
    center = 0.2660124987032184
    values = SCREEN._directed_values(center, (0.90, 0.75, 0.50))
    assert values == [center * 0.90, center * 0.75, center * 0.50]
    assert center > values[0] > values[1] > values[2]


def test_affinity_and_capacity_locks_are_exact() -> None:
    seed = {
        "km_ATP_HK": 0.06014413339486139,
        "km_ATP_PFK": 0.03302569060009802,
        "km_NADH_NAD": 9.184380136644775,
        "vmax_VPGK": 40.02263055538305,
        "vmax_VPK": 0.7134227571052547,
    }
    candidate = {**seed, "km_ADP_ATP": 0.2}
    assert SCREEN._validate_locks(seed, candidate) == seed


def test_transfer_guard_detects_atp_floor() -> None:
    seed = _payload()
    candidate = _payload()
    candidate["concentration_metrics"]["ATP"]["final_value"] = 0.94
    assert "ATP endpoint below 95% of seed" in SCREEN._transfer_guard_reasons(seed, candidate)


def test_transfer_guard_detects_p3g_regression() -> None:
    seed = _payload()
    candidate = _payload()
    candidate["concentration_metrics"]["P3G"]["nrmse"] = 1.07
    assert "P3G nRMSE transfer guard" in SCREEN._transfer_guard_reasons(seed, candidate)


def test_transfer_guard_detects_teacher_flux_regression() -> None:
    seed = _payload()
    candidate = _payload()
    candidate["teacher_flux_metrics"]["VLDH"]["nrmse"] = 1.10
    assert "VLDH teacher-flux transfer guard" in SCREEN._transfer_guard_reasons(seed, candidate)


def test_promising_requires_production_and_direct_gain() -> None:
    seed = _payload()
    candidate = _payload()
    candidate["balance_summary"]["ATP_production_flux"]["late_mean"] = 1.03
    candidate["concentration_metrics"]["GLC"]["nrmse"] = 0.98
    assert SCREEN._is_promising(seed, candidate) is True


def test_guarded_candidate_is_not_promising() -> None:
    seed = _payload()
    candidate = _payload()
    candidate["balance_summary"]["ATP_production_flux"]["late_mean"] = 1.03
    candidate["concentration_metrics"]["LAC"]["nrmse"] = 0.98
    candidate["guard_reasons"] = ["PEP nRMSE transfer guard"]
    assert SCREEN._is_promising(seed, candidate) is False


def test_teacher_flux_contract_requires_dense_timepoints() -> None:
    try:
        SCREEN._teacher_flux_metrics(sol=None, fluxes={}, teacher_dataset={})
    except KeyError as exc:
        assert "dense_timepoints" in str(exc)
    else:
        raise AssertionError("missing teacher time grid should fail before flux access")
