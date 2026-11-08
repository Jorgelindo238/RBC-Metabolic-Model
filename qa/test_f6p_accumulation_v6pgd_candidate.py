"""Tests for fixed-parameter F6P accumulation attribution."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "src"), str(ROOT / "scripts")):
    if path not in sys.path:
        sys.path.insert(0, path)

SCRIPT_PATH = ROOT / "scripts" / "audit_f6p_accumulation_v6pgd_candidate.py"
SPEC = importlib.util.spec_from_file_location(
    "audit_f6p_accumulation_v6pgd_candidate", SCRIPT_PATH
)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_f6p_balance_contract_has_exact_coded_terms() -> None:
    assert AUDIT.F6P_TERMS == {
        "VPGI": 1.0,
        "VPFK": -1.0,
        "VTKL2": 1.0,
        "VTAL": 1.0,
    }


def test_f6p_reconstruction_matches_signed_terms() -> None:
    frame = pd.DataFrame(
        {
            "VPGI": [1.0, 2.0],
            "VPFK": [0.5, 0.75],
            "VTKL2": [0.2, 0.3],
            "VTAL": [0.1, 0.4],
        }
    )
    result = AUDIT._reconstruct_f6p_raw_balance(frame)
    assert np.allclose(result, [0.8, 1.95])


def test_sustained_crossing_rejects_short_spike() -> None:
    time = np.arange(0.0, 4.5, 0.5)
    values = np.asarray([0.0, 2.0, 0.0, 0.0, 2.0, 2.0, 2.0, 0.0, 0.0])
    crossing = AUDIT._first_sustained_crossing(
        time, values, threshold=1.0, duration=1.0
    )
    assert crossing == 2.0


def test_windows_cover_recorded_intervals() -> None:
    assert AUDIT.WINDOWS == (
        ("J1_J2", 1.0, 2.0),
        ("day_2_10", 2.0, 10.0),
        ("day_10_20", 10.0, 20.0),
        ("day_20_30", 20.0, 30.0),
        ("day_30_46", 30.0, 46.0),
    )


def test_structural_classifier_identifies_atp_limited_pfk() -> None:
    rows = []
    for window, start, end in AUDIT.WINDOWS:
        rows.append(
            {
                "window": window,
                "start_day": start,
                "end_day": end,
                "ATP_saturation_mean": 0.01 if window != "J1_J2" else 0.9,
                "F6P_saturation_mean": 0.9,
                "inferred_PFK_modulation_mean": 1.0,
                "VPFK_teacher_deficit_mean": 0.05,
                "nonoxidative_PPP_input_fraction": 0.4,
            }
        )
    result = AUDIT._structural_classification(
        candidate_rows=rows,
        candidate_divergence={"first_sustained_nerror_gt_1_day": 5.0},
        baseline_divergence={"first_sustained_nerror_gt_1_day": 5.1},
    )
    assert result["classification"].startswith("ATP-limited")
    assert all(result["classification_gates"].values())
