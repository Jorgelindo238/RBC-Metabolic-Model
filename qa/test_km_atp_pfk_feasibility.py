"""Tests for the directed km_ATP_PFK feasibility screen."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "screen_km_atp_pfk_feasibility.py"
SPEC = importlib.util.spec_from_file_location("screen_km_atp_pfk_feasibility", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
SCREEN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCREEN)


def _payload() -> dict:
    return {
        "loss": 10.0,
        "metrics": {
            name: {"nrmse": 1.0, "endpoint_error": 0.1}
            for name in ("EGLC", "ELAC", "GLC", "LAC", "PYR")
        },
        "energy_metrics": {
            name: {"nrmse": 1.0, "endpoint_error": 0.1}
            for name in ("ATP", "PEP", "G6P")
        },
        "sim_final": {"ATP": 1.0},
        "guard_violations": [],
    }


def test_directed_values_are_strictly_downward() -> None:
    center = 0.03302569060009802
    values = SCREEN._directed_values(center, (0.90, 0.75, 0.50))
    assert values == [center * 0.90, center * 0.75, center * 0.50]
    assert center > values[0] > values[1] > values[2]


def test_seed_locks_are_preserved_exactly() -> None:
    seed = {"km_ATP_HK": 0.06014413339486139, "km_NADH_NAD": 9.184380136644775}
    candidate = {**seed, "km_ATP_PFK": 0.02}
    assert SCREEN._validate_locks(seed, candidate) == seed


def test_hard_stop_detects_atp_floor() -> None:
    seed = _payload()
    candidate = _payload()
    candidate["sim_final"]["ATP"] = 0.94
    assert "ATP endpoint below 95% of seed" in SCREEN._hard_stop_reasons(seed, candidate)


def test_hard_stop_detects_pep_regression() -> None:
    seed = _payload()
    candidate = _payload()
    candidate["energy_metrics"]["PEP"]["nrmse"] = 1.07
    assert "PEP nRMSE exceeded the hard guard" in SCREEN._hard_stop_reasons(seed, candidate)


def test_promising_point_requires_guarded_direct_gain() -> None:
    seed = _payload()
    candidate = _payload()
    candidate["loss"] = 9.0
    candidate["energy_metrics"]["G6P"]["nrmse"] = 0.95
    assert SCREEN._is_promising(seed, candidate) is True


def test_guard_violation_blocks_promising_point() -> None:
    seed = _payload()
    candidate = _payload()
    candidate["loss"] = 9.0
    candidate["metrics"]["GLC"]["nrmse"] = 0.95
    candidate["guard_violations"] = ["ELAC nRMSE guard"]
    assert SCREEN._is_promising(seed, candidate) is False
