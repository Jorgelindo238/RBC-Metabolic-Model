"""Tests for the GL6P(0)-V6PGD identifiability map."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "src"), str(ROOT / "scripts")):
    if path not in sys.path:
        sys.path.insert(0, path)

SCRIPT_PATH = ROOT / "scripts" / "map_gl6p_v6pgd_identifiability.py"
SPEC = importlib.util.spec_from_file_location("map_gl6p_v6pgd_identifiability", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MAP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MAP)


CONSTANTS = {
    "vmax_VPGLS": 4.111138,
    "km_GL6P": 0.1,
    "km_GO6P": 0.02,
    "km_NADP_NADPH": 1.0,
}


def test_replay_grid_spans_historical_and_generic_gl6p() -> None:
    assert MAP.REPLAY_GL6P[0] == 7.62e-6
    assert MAP.REPLAY_GL6P[-1] == 1.0
    assert all(right > left for left, right in zip(MAP.REPLAY_GL6P, MAP.REPLAY_GL6P[1:]))


def test_required_vmax_reconstructs_teacher_across_ridge() -> None:
    teacher = -0.011165010179783242
    for gl6p in MAP.REPLAY_GL6P:
        required = MAP._required_vmax_v6pgd(
            gl6p=gl6p,
            teacher_flux=teacher,
            go6p=0.12817966026893696,
            nadp=1.0,
            nadph=1.0,
            constants=CONSTANTS,
        )
        _, _, net = MAP._initial_rate_components(
            gl6p=gl6p,
            vmax_v6pgd=required,
            go6p=0.12817966026893696,
            nadp=1.0,
            nadph=1.0,
            constants=CONSTANTS,
        )
        assert abs(net - teacher) < 1e-12


def test_ridge_endpoints_match_exact_j1_teacher() -> None:
    teacher = -0.011398327305375912
    historical = MAP._required_vmax_v6pgd(
        gl6p=7.62e-6,
        teacher_flux=teacher,
        go6p=0.12817966026893696,
        nadp=1.0,
        nadph=1.0,
        constants=CONSTANTS,
    )
    generic = MAP._required_vmax_v6pgd(
        gl6p=1.0,
        teacher_flux=teacher,
        go6p=0.12817966026893696,
        nadp=1.0,
        nadph=1.0,
        constants=CONSTANTS,
    )
    assert np.isclose(historical, 0.0270778943667671, rtol=1e-12)
    assert np.isclose(generic, 8.667454254778063, rtol=1e-12)


def test_case_labels_include_background_and_gl6p() -> None:
    label = MAP._case_label(MAP.BACKGROUND_CURRENT, 1e-3)
    assert label == "current_other_latent__GL6P_1.000e-03"
