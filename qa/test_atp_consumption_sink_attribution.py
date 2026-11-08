"""Tests for native ATP-consumption sink attribution."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "profile_atp_consumption_sinks.py"
SPEC = importlib.util.spec_from_file_location("profile_atp_consumption_sinks", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
PROFILE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROFILE)


def _fluxes(seed_scale: float = 1.0, induced_reaction: str | None = None) -> dict[str, np.ndarray]:
    values: dict[str, np.ndarray] = {}
    for index, reaction in enumerate(PROFILE.ATP_CONSUMPTION, start=1):
        scale = seed_scale * float(index)
        if reaction == induced_reaction:
            scale += 2.0
        values[reaction] = np.asarray([scale, scale, scale], dtype=float)
    return values


def test_changed_parameters_accepts_only_km_adp_atp_difference() -> None:
    seed = {"km_ADP_ATP": 0.266, "km_ATP_HK": 0.06}
    candidate = {"km_ADP_ATP": 0.1995, "km_ATP_HK": 0.06}
    assert PROFILE._changed_parameters(seed, candidate) == ["km_ADP_ATP"]


def test_consumption_sum_contains_every_declared_sink() -> None:
    fluxes = _fluxes()
    expected = sum(fluxes[name] for name in PROFILE.ATP_CONSUMPTION)
    assert np.allclose(PROFILE._consumption_sum(fluxes), expected)


def test_closure_accepts_exact_native_sum() -> None:
    fluxes = _fluxes()
    total = PROFILE._consumption_sum(fluxes)
    factors = pd.DataFrame({"ATP_consumption_flux": total})
    assert PROFILE._validate_closure(fluxes, factors) == 0.0


def test_closure_rejects_inconsistent_balance() -> None:
    fluxes = _fluxes()
    total = PROFILE._consumption_sum(fluxes) + 1e-3
    factors = pd.DataFrame({"ATP_consumption_flux": total})
    try:
        PROFILE._validate_closure(fluxes, factors)
    except RuntimeError as exc:
        assert "closure failed" in str(exc)
    else:
        raise AssertionError("inconsistent ATP consumption should fail")


def test_sink_ranking_finds_induced_reaction() -> None:
    seed = _fluxes()
    candidate = _fluxes(induced_reaction="VHK")
    rows = PROFILE._sink_rows(
        seed_fluxes=seed,
        candidate_fluxes=candidate,
        time=np.asarray([40.0, 43.0, 46.0]),
    )
    assert rows[0]["reaction"] == "VHK"
    assert rows[0]["delta_late_mean"] == 2.0
    assert rows[0]["share_of_induced_late_consumption"] == 1.0
