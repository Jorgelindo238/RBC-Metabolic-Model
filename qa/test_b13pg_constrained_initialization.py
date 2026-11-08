"""Tests for the reversible B13PG-only initialization screen."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "src"), str(ROOT / "scripts")):
    if path not in sys.path:
        sys.path.insert(0, path)

SCRIPT_PATH = ROOT / "scripts" / "screen_b13pg_constrained_initialization.py"
SPEC = importlib.util.spec_from_file_location(
    "screen_b13pg_constrained_initialization", SCRIPT_PATH
)
assert SPEC is not None and SPEC.loader is not None
SCREEN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCREEN)


def test_screen_grid_preserves_exact_qss_anchor_and_revert_branch() -> None:
    assert SCREEN.QSS_SCALES == (0.25, 0.5, 1.0, 2.0, 4.0, 8.0)
    assert SCREEN.QSS_LABEL == "qss_1.000x"
    assert SCREEN.REVERT_LABEL == "duplicated_data_revert"


def test_b13pg_override_changes_only_b13pg() -> None:
    base = np.arange(114, dtype=float) + 1.0
    state = SCREEN._state_with_b13pg(base, 0.125)
    changed = set(np.flatnonzero(state != base).tolist())
    assert changed == {SCREEN.B13PG_INDEX}
    assert state[SCREEN.B23PG_INDEX] == base[SCREEN.B23PG_INDEX]


def test_qss_root_requires_and_solves_a_bracket() -> None:
    root = SCREEN._find_qss_root(lambda value: 2.0 - 4.0 * value, lower=0.0, upper=1.0)
    assert np.isclose(root, 0.5)


def test_nrmse_uses_stable_full_teacher_scale() -> None:
    model = np.asarray([1.0, 2.0])
    teacher = np.asarray([1.0, 1.0])
    full = np.asarray([1.0, 3.0])
    assert np.isclose(SCREEN._nrmse(model, teacher, full), np.sqrt(0.5) / 2.0)


def test_short_guards_require_qss_b23pg_lock_and_pulse_removal() -> None:
    row = {
        "max_B13PG_closure_error": 0.0,
        "max_ATP_closure_error": 0.0,
        "all_state_minimum_mM": 0.0,
        "NAD_minimum_mM": 0.1,
        "NADH_minimum_mM": 0.1,
        "NAD_NADH_max_drift_mM": 0.0,
        "B23PG_initial_mM": 3.5,
        "B23PG_nrmse": 0.5,
        "stock_supported_drainage_mM": 0.01,
    }
    revert = {"B23PG_nrmse": 0.5, "stock_supported_drainage_mM": 1.0}
    guards = SCREEN._short_guards(
        row=row,
        revert=revert,
        initial_balance={"effective_B13PG_derivative": 0.0},
        b23pg_locked_value=3.5,
        closure_tolerance=1e-12,
    )
    assert all(guards.values())


def test_short_selector_uses_only_fully_guarded_rows() -> None:
    selected = SCREEN._select_short_candidate(
        [
            {
                "candidate": "bad",
                "scale": 1.0,
                "ATP_nrmse": 0.1,
                "short_guard_pass": False,
            },
            {
                "candidate": "good",
                "scale": 1.0,
                "ATP_nrmse": 0.2,
                "short_guard_pass": True,
            },
        ]
    )
    assert selected == "good"


def test_long_guards_reject_atp_collapse() -> None:
    row = {
        "ATP_below_0.01_mM_day": 2.0,
        "ATP_nrmse": 0.5,
        "B23PG_nrmse": 0.5,
        "all_state_minimum_mM": 0.0,
        "NAD_minimum_mM": 0.1,
        "NADH_minimum_mM": 0.1,
        "NAD_NADH_max_drift_mM": 0.0,
    }
    guards = SCREEN._long_guards(row=row, revert={"ATP_nrmse": 0.5, "B23PG_nrmse": 0.5})
    assert not guards["ATP_does_not_collapse_below_0.01_mM"]
    assert not all(guards.values())
