"""Tests for the finite-bound V6PGD refinement screen."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "src"), str(ROOT / "scripts")):
    if path not in sys.path:
        sys.path.insert(0, path)

SCRIPT_PATH = ROOT / "scripts" / "refine_vmax_v6pgd_constrained_transition.py"
SPEC = importlib.util.spec_from_file_location(
    "refine_vmax_v6pgd_constrained_transition", SCRIPT_PATH
)
assert SPEC is not None and SPEC.loader is not None
REFINE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REFINE)


def test_refinement_grid_matches_the_recorded_contract() -> None:
    assert REFINE.REFINEMENT_SCALES == (0.895, 0.900, 0.9025, 0.905, 0.9075)
    assert REFINE.BASELINE_SCALE == 1.0
    assert max(REFINE.REFINEMENT_SCALES) < 0.91


def test_labels_preserve_seed_and_fixed_capacity_identity() -> None:
    assert REFINE._label(1.0) == "constrained_balanced_teacher__seed"
    assert REFINE._label(0.9025).endswith("v6pgd_0.9025x")


def test_full_horizon_guards_require_joint_improvement() -> None:
    baseline = {
        **{f"{pool}_nrmse": 1.0 for pool in REFINE.LONG_GUARD_POOLS},
        **{
            f"{pool}_{metric}": 1.0
            for pool in REFINE.MEASURED_PPP_POOLS
            for metric in ("concentration_nrmse", "teacher_nrmse")
        },
        "GO6P_F6P_joint_score": 4.0,
    }
    candidate = {
        **{f"{pool}_nrmse": 1.01 for pool in REFINE.LONG_GUARD_POOLS},
        **{
            f"{pool}_{metric}": 0.99
            for pool in REFINE.MEASURED_PPP_POOLS
            for metric in ("concentration_nrmse", "teacher_nrmse")
        },
        "GO6P_F6P_joint_score": 3.96,
        "PPP_minimum": 1e-6,
        "NADP_minimum": 0.1,
        "NADPH_minimum": 0.1,
        "NADP_NADPH_max_drift": 0.0,
        "max_pointwise_closure_error": 0.0,
    }
    guards = REFINE._full_horizon_guards(
        candidate=candidate,
        baseline=baseline,
        early_pass=True,
        finite_bound_feasible=True,
        closure_tolerance=1e-12,
    )
    assert all(guards.values())
    candidate["GO6P_F6P_joint_score"] = 4.01
    failed = REFINE._full_horizon_guards(
        candidate=candidate,
        baseline=baseline,
        early_pass=True,
        finite_bound_feasible=True,
        closure_tolerance=1e-12,
    )
    assert failed["GO6P_F6P_joint_full_improves"] is False


def test_selection_uses_lowest_guarded_full_horizon_score() -> None:
    rows = [
        {
            "candidate": "a",
            "scale": 0.895,
            "GO6P_F6P_joint_score": 3.5,
            "fully_guarded_full_horizon_pass": True,
        },
        {
            "candidate": "b",
            "scale": 0.900,
            "GO6P_F6P_joint_score": 3.4,
            "fully_guarded_full_horizon_pass": True,
        },
        {
            "candidate": "c",
            "scale": 0.9025,
            "GO6P_F6P_joint_score": 3.0,
            "fully_guarded_full_horizon_pass": False,
        },
    ]
    assert REFINE._select_full_horizon_candidate(rows) == "b"


def test_selection_returns_none_when_no_point_is_guarded() -> None:
    assert (
        REFINE._select_full_horizon_candidate(
            [
                {
                    "candidate": "x",
                    "fully_guarded_full_horizon_pass": False,
                }
            ]
        )
        is None
    )
