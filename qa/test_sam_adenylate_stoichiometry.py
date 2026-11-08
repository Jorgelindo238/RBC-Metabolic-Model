"""Regression tests for SAM adenylate stoichiometry."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from equadiff_brodbar import BRODBAR_METABOLITE_MAP, equadiff_brodbar  # noqa: E402
from MM_calibration import load_initial_conditions  # noqa: E402


def test_biochemical_sam_mode_removes_only_legacy_amp_coproduct() -> None:
    state = np.asarray(load_initial_conditions(), dtype=float)
    biochemical = equadiff_brodbar(
        1.0,
        state,
        custom_params={"sam_adenylate_stoichiometry": "biochemical_transfer"},
    )
    legacy = equadiff_brodbar(
        1.0,
        state,
        custom_params={"sam_adenylate_stoichiometry": "legacy_amp_coproduct"},
    )
    difference = np.asarray(legacy, dtype=float) - np.asarray(biochemical, dtype=float)
    changed = set(np.flatnonzero(np.abs(difference) > 1e-12).tolist())
    assert changed == {BRODBAR_METABOLITE_MAP["AMP"]}
    assert difference[BRODBAR_METABOLITE_MAP["AMP"]] > 0.0


def test_biochemical_sam_mode_is_default() -> None:
    state = np.asarray(load_initial_conditions(), dtype=float)
    default = equadiff_brodbar(1.0, state, custom_params={})
    explicit = equadiff_brodbar(
        1.0,
        state,
        custom_params={"sam_adenylate_stoichiometry": "biochemical_transfer"},
    )
    assert np.allclose(default, explicit, rtol=0.0, atol=0.0)


def test_unknown_sam_stoichiometry_is_rejected() -> None:
    state = np.asarray(load_initial_conditions(), dtype=float)
    try:
        equadiff_brodbar(
            1.0,
            state,
            custom_params={"sam_adenylate_stoichiometry": "unknown"},
        )
    except ValueError as exc:
        assert "sam_adenylate_stoichiometry" in str(exc)
    else:
        raise AssertionError("Unknown SAM stoichiometry mode was accepted")
