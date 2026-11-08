"""Focused tests for the pre-optimization glycolysis flux profiler."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "profile_glycolysis_flux_bottlenecks.py"
SPEC = importlib.util.spec_from_file_location("profile_glycolysis_flux_bottlenecks", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
PROFILE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROFILE)


def _pool_summary() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "candidate": "reference",
                "pool": "G6P",
                "restriction_score": 2.0,
                "outlet_utilization": 0.4,
            },
            {
                "candidate": "reference",
                "pool": "PEP",
                "restriction_score": 1.0,
                "outlet_utilization": 0.8,
            },
        ]
    )


def test_time_mean_uses_trapezoidal_integration() -> None:
    time = np.asarray([1.0, 2.0, 4.0])
    values = np.asarray([0.0, 2.0, 2.0])
    assert PROFILE._time_mean(values, time) == 5.0 / 3.0


def test_low_substrate_occupancy_selects_affinity_lever() -> None:
    factors = pd.DataFrame(
        [
            {
                "candidate": "reference",
                "kinetic_factor": "VPGI_G6P",
                "late_mean_factor": 0.2,
            },
            {
                "candidate": "reference",
                "kinetic_factor": "VPK_PEP",
                "late_mean_factor": 0.9,
            },
        ]
    )
    lever, ranking = PROFILE.select_downstream_lever(_pool_summary(), factors, "reference")
    assert lever == "km_G6P"
    assert ranking.iloc[0]["recommended_parameter"] == "km_G6P"


def test_high_substrate_occupancy_selects_capacity_lever() -> None:
    factors = pd.DataFrame(
        [
            {
                "candidate": "reference",
                "kinetic_factor": "VPGI_G6P",
                "late_mean_factor": 0.9,
            },
            {
                "candidate": "reference",
                "kinetic_factor": "VPK_PEP",
                "late_mean_factor": 0.9,
            },
        ]
    )
    lever, ranking = PROFILE.select_downstream_lever(_pool_summary(), factors, "reference")
    assert lever == "vmax_VPGI"
    assert ranking.iloc[0]["recommended_parameter"] == "vmax_VPGI"


def test_glucose_pool_balance_matches_model_equation() -> None:
    assert PROFILE.POOL_BALANCE_TERMS["GLC"] == (("VEGLC", 1.0), ("VHK", -1.0))
    assert PROFILE.POOL_BALANCE_TERMS["LAC"] == (("VLDH", 1.0), ("VELAC", -1.0))


def test_atp_collapse_and_pep_bypass_select_vpep_pase() -> None:
    trajectory = pd.DataFrame(
        [
            {
                "candidate": "reference",
                "metabolite": "ATP",
                "time_day": 1.0,
                "concentration": 1.0,
                "experimental": 1.0,
            },
            {
                "candidate": "reference",
                "metabolite": "ATP",
                "time_day": 46.0,
                "concentration": 0.01,
                "experimental": 0.5,
            },
        ]
    )
    flux_summary = pd.DataFrame(
        [
            {"candidate": "reference", "reaction": "VPK", "mean_abs_flux": 0.05},
            {"candidate": "reference", "reaction": "VPEP_PASE", "mean_abs_flux": 0.95},
        ]
    )
    result = PROFILE.diagnose_structural_lever(
        symptom_lever="vmax_VPFK",
        reference="reference",
        trajectory=trajectory,
        flux_summary=flux_summary,
    )
    assert result["recommended_parameter"] == "vmax_VPEP_PASE"
    assert result["recommended_direction"] == "decrease"
