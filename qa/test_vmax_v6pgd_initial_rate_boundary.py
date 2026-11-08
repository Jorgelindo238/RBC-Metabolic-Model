"""Tests for the J1-J2 V6PGD initial-rate boundary screen."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "src"), str(ROOT / "scripts")):
    if path not in sys.path:
        sys.path.insert(0, path)

SCRIPT_PATH = ROOT / "scripts" / "screen_vmax_v6pgd_initial_rate_boundary.py"
SPEC = importlib.util.spec_from_file_location("screen_vmax_v6pgd_initial_rate_boundary", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
SCREEN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCREEN)


def test_boundary_labels_do_not_collide_at_low_scales() -> None:
    labels = [SCREEN._boundary_label(scale) for scale in SCREEN.BOUNDARY_SCALES]
    assert len(labels) == len(set(labels))
    assert "vmax_V6PGD_0.002654x" in labels


def test_parser_accepts_refinement_scales() -> None:
    args = SCREEN.build_parser().parse_args(["--scales", "0.0125", "0.02"])
    assert args.scales == [0.0125, 0.02]


def test_teacher_matched_scale_reconstructs_initial_target() -> None:
    vpgls = 0.0003132448463427098
    seed_v6pgd = 4.3251413839963195
    teacher = -0.011165010179783242
    reconstructed = vpgls - seed_v6pgd * SCREEN.TEACHER_MATCHED_SCALE
    assert abs(reconstructed - teacher) < 1e-12


def test_assessment_selects_feasible_point_nearest_initial_teacher() -> None:
    reference = {
        "candidate": SCREEN.CASE_HISTORICAL,
        "GO6P_teacher": {"nrmse": 10.0},
        "GO6P_concentration_nrmse": 1.0,
        "teacher_dGO6P_initial": -0.011,
    }
    candidate = {
        "candidate": "candidate",
        "GO6P_teacher": {"nrmse": 1.0, "sign_agreement": 1.0},
        "GO6P_concentration_nrmse": 0.5,
        "GO6P_minimum": 0.01,
        "NADP_minimum": 0.1,
        "NADPH_minimum": 0.1,
        "NADP_NADPH_max_drift": 1e-12,
        "GO6P_final": 0.1,
        "dGO6P_initial": -0.011,
    }
    assessments, decision, selected = SCREEN._assess([reference, candidate])
    assert assessments[0]["locally_feasible"] is True
    assert decision.startswith("advance")
    assert selected == "candidate"
