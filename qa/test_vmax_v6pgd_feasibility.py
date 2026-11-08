"""Tests for the directed V6PGD feasibility screen."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "src"), str(ROOT / "scripts")):
    if path not in sys.path:
        sys.path.insert(0, path)

SCRIPT_PATH = ROOT / "scripts" / "screen_vmax_v6pgd_feasibility.py"
SPEC = importlib.util.spec_from_file_location("screen_vmax_v6pgd_feasibility", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
SCREEN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCREEN)


def test_candidate_changes_only_vmax_v6pgd() -> None:
    seed = {"vmax_VHK": 1.0}
    params, changed = SCREEN._candidate_params(seed, 0.43)
    assert changed == ["vmax_V6PGD"]
    assert params["vmax_V6PGD"] == 4.3
    assert params["vmax_VHK"] == 1.0


def test_screen_labels_are_stable() -> None:
    assert SCREEN._candidate_label(0.60) == "vmax_V6PGD_0.60x"
    assert SCREEN._candidate_label(0.43) == "vmax_V6PGD_0.43x"


def test_parser_accepts_transfer_scale() -> None:
    args = SCREEN.build_parser().parse_args(
        ["--scales", "0.02", "--candidate-initialization", "current"]
    )
    assert args.scales == [0.02]
    assert args.candidate_initialization == "current"


def test_decision_advances_only_fully_guarded_point() -> None:
    assessments = [
        {
            "candidate": "vmax_V6PGD_0.50x",
            "early_GO6P_teacher_relative_improvement": 0.5,
            "full_GO6P_teacher_relative_improvement": 0.4,
            "passes_primary_target": True,
            "fixed_point_feasible": False,
        },
        {
            "candidate": "vmax_V6PGD_0.43x",
            "early_GO6P_teacher_relative_improvement": 0.6,
            "full_GO6P_teacher_relative_improvement": 0.5,
            "passes_primary_target": True,
            "fixed_point_feasible": True,
        },
    ]
    decision, _, selected = SCREEN._decision(assessments)
    assert "advance vmax_V6PGD_0.43x" in decision
    assert selected == "vmax_V6PGD_0.43x"


def test_decision_names_current_initialization_transfer() -> None:
    assessments = [
        {
            "candidate": "vmax_V6PGD_0.02x",
            "early_GO6P_teacher_relative_improvement": 0.8,
            "full_GO6P_teacher_relative_improvement": 0.8,
            "passes_primary_target": True,
            "fixed_point_feasible": True,
        }
    ]
    decision, _, selected = SCREEN._decision(
        assessments, candidate_initialization="current"
    )
    assert "current-initialization" in decision
    assert selected == "vmax_V6PGD_0.02x"


def test_decision_rejects_promotion_when_transfer_guards_fail() -> None:
    assessments = [
        {
            "candidate": "vmax_V6PGD_0.43x",
            "early_GO6P_teacher_relative_improvement": 0.6,
            "full_GO6P_teacher_relative_improvement": 0.5,
            "passes_primary_target": True,
            "fixed_point_feasible": False,
        }
    ]
    decision, _, selected = SCREEN._decision(assessments)
    assert decision.startswith("reject V6PGD promotion")
    assert selected is None


def test_decision_rejects_isolated_hypothesis_without_pool_recovery() -> None:
    assessments = [
        {
            "candidate": "vmax_V6PGD_0.35x",
            "early_GO6P_teacher_relative_improvement": 0.65,
            "full_GO6P_teacher_relative_improvement": 0.65,
            "passes_primary_target": False,
            "fixed_point_feasible": False,
        }
    ]
    decision, rationale, selected = SCREEN._decision(assessments)
    assert decision == "reject the isolated V6PGD hypothesis"
    assert "concentration nRMSE" in rationale
    assert selected is None
