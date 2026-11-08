"""Tests for the fixed V6PGD plus constrained-initialization screen."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "src"), str(ROOT / "scripts")):
    if path not in sys.path:
        sys.path.insert(0, path)

SCRIPT_PATH = ROOT / "scripts" / "screen_vmax_v6pgd_constrained_initialization.py"
SPEC = importlib.util.spec_from_file_location(
    "screen_vmax_v6pgd_constrained_initialization", SCRIPT_PATH
)
assert SPEC is not None and SPEC.loader is not None
SCREEN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCREEN)


def test_screen_points_straddle_the_analytical_boundary() -> None:
    values = [SCREEN.SEED_VMAX_V6PGD * scale for scale in SCREEN.SCREEN_SCALES]
    assert max(values) > SCREEN.GO6P_BOUNDARY_VMAX
    assert min(values) < SCREEN.GO6P_BOUNDARY_VMAX
    assert 0.9532 in SCREEN.SCREEN_SCALES


def test_candidate_changes_only_vmax_v6pgd() -> None:
    seed = {"vmax_VHK": 1.2, "vmax_VPGLS": 4.1}
    candidate, changed = SCREEN._candidate_params(seed, 0.93)
    assert changed == ["vmax_V6PGD"]
    assert candidate["vmax_V6PGD"] == 9.3
    assert candidate["vmax_VHK"] == seed["vmax_VHK"]
    assert candidate["vmax_VPGLS"] == seed["vmax_VPGLS"]


def test_g6p_is_a_noninferiority_guard_not_a_target() -> None:
    assert SCREEN.G6P_NONINFERIORITY_TOLERANCE == 0.02
    assert SCREEN.LATENT_RESIDUAL_REDUCTION_FLOOR == 0.01
    assert "G6P" not in ("GO6P", "F6P")


def test_assessment_requires_every_guard() -> None:
    baseline = {
        "G6P_concentration_nrmse": 10.0,
        "G6P_teacher_nrmse": 10.0,
        "GO6P_concentration_nrmse": 10.0,
        "GO6P_teacher_nrmse": 10.0,
        "F6P_concentration_nrmse": 10.0,
        "F6P_teacher_nrmse": 10.0,
        "latent_residual_nRMS": 10.0,
    }
    candidate = {
        "candidate": "candidate",
        "mode": "mode",
        "scale": 0.93,
        "vmax_V6PGD": 9.3,
        "G6P_concentration_nrmse": 10.1,
        "G6P_teacher_nrmse": 10.1,
        "GO6P_concentration_nrmse": 9.0,
        "GO6P_teacher_nrmse": 9.0,
        "F6P_concentration_nrmse": 9.0,
        "F6P_teacher_nrmse": 9.0,
        "latent_residual_nRMS": 9.0,
        "GL6P_initial": 1.0,
        "solver_success": True,
        "PPP_minimum": 0.0,
        "redox_valid": True,
        "max_pointwise_closure_error": 0.0,
    }
    assessment = SCREEN._assess_candidate(
        row=candidate,
        baseline=baseline,
        feasibility={"bounded_feasible": True},
        bounded_gl6p_max=2.0,
        closure_tolerance=1e-12,
    )
    assert assessment["fully_guarded_early_pass"] is True
    candidate["F6P_teacher_nrmse"] = 9.9
    failed = SCREEN._assess_candidate(
        row=candidate,
        baseline=baseline,
        feasibility={"bounded_feasible": True},
        bounded_gl6p_max=2.0,
        closure_tolerance=1e-12,
    )
    assert failed["fully_guarded_early_pass"] is False


def test_selection_returns_none_without_a_full_pass() -> None:
    assert (
        SCREEN._select_candidate(
            [{"candidate": "x", "fully_guarded_early_pass": False}],
            [{"candidate": "x"}],
        )
        is None
    )
