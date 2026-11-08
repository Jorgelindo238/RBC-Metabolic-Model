"""Focused tests for the native ATP/ADP/redox diagnostic profiler."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "profile_energy_redox_controls.py"
SPEC = importlib.util.spec_from_file_location("profile_energy_redox_controls", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
PROFILE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROFILE)


def _fluxes(size: int = 3) -> dict[str, np.ndarray]:
    names = set(PROFILE.ATP_PRODUCTION) | set(PROFILE.ATP_CONSUMPTION)
    names.update(("VHK", "VPFK", "VPGK", "VPK", "VLDH", "VPEP_PASE", "VEGLC", "VELAC"))
    return {name: np.ones(size, dtype=float) for name in names}


def test_native_atp_and_redox_factors_match_equations() -> None:
    state = np.zeros((114, 3), dtype=float)
    state[PROFILE.STATE["GLC"]] = 1.0
    state[PROFILE.STATE["F6P"]] = 1.0
    state[PROFILE.STATE["F16BP"]] = 0.005
    state[PROFILE.STATE["PEP"]] = 0.175
    state[PROFILE.STATE["PYR"]] = 0.697
    state[PROFILE.STATE["ATP"]] = 0.1
    state[PROFILE.STATE["ADP"]] = 1.0
    state[PROFILE.STATE["NAD"]] = 1.0
    state[PROFILE.STATE["NADH"]] = 1.0
    sol = SimpleNamespace(t=np.asarray([1.0, 2.0, 46.0]), y=state)

    frame = PROFILE._factor_timeseries(sol, _fluxes(), {})

    assert np.isclose(frame["VHK_ATP_occupancy"].iloc[0], 1.0 / 6.0)
    assert np.isclose(frame["VPFK_ATP_occupancy"].iloc[0], 0.5)
    assert np.isclose(frame["VPK_ATP_inhibition"].iloc[0], 1.0 / 1.04)
    assert np.isclose(frame["VLDH_NADH_NAD_drive"].iloc[0], 0.5)


def test_control_ranking_prioritizes_active_atp_occupancy_over_pk_inhibition() -> None:
    rows = []
    values = {
        "VHK_ATP_occupancy": 0.01,
        "VPFK_ATP_occupancy": 0.02,
        "VPK_ATP_inhibition": 0.999,
        "VLDH_NADH_NAD_drive": 0.15,
    }
    for metric, late_factor in values.items():
        rows.append(
            {
                "candidate": "reference",
                "metric": metric,
                "late_40_46d": late_factor,
                "endpoint": late_factor,
                "overall_mean": late_factor,
                "min": late_factor,
                "max": late_factor,
                "early_1_2d": late_factor,
                "mid_10_20d": late_factor,
            }
        )
    ranking = PROFILE._rank_controls(pd.DataFrame(rows), "reference")
    assert ranking.iloc[0]["parameter"] == "km_ATP_HK"
    assert ranking.iloc[-1]["parameter"] == "ki_ATP_PK"
    assert ranking.iloc[-1]["suggested_direction"] == "do not open"
