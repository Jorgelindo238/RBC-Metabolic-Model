from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import refine_vmax_vdpgm_pareto as REFINE  # noqa: E402


def test_refinement_grid_is_exactly_the_registered_interval():
    assert REFINE.REFINEMENT_MULTIPLIERS == (2.0, 2.5, 3.0, 3.5, 4.0)
    assert REFINE.MIN_INTERIOR_IMPROVEMENT == 0.05


def test_pareto_mask_removes_dominated_row():
    values = np.asarray([[1.0, 1.0], [2.0, 2.0], [0.5, 3.0]])
    assert REFINE._pareto_mask(values).tolist() == [True, False, True]


def test_rank_retains_clear_interior_knee():
    rows = []
    for multiplier, benefit, cost in (
        (2.0, 1.0, 0.0),
        (2.5, 0.7, 0.2),
        (3.0, 0.45, 0.35),
        (3.5, 0.2, 0.7),
        (4.0, 0.0, 1.0),
    ):
        rows.append(
            {
                "candidate": f"p{multiplier}",
                "multiplier": multiplier,
                "all_temporal_guards_pass": True,
                **{name: benefit for name in REFINE.B23PG_OBJECTIVES},
                **{name: cost for name in REFINE.TRANSFER_OBJECTIVES},
            }
        )
    _, selection = REFINE._rank_pareto(rows)
    assert selection["selected_candidate"] == "p3.0"
    assert selection["interior_improvement_fraction"] >= 0.05


def test_rank_rejects_knee_when_guard_fails():
    rows = []
    for multiplier, benefit, cost in (
        (2.0, 1.0, 0.0),
        (3.0, 0.4, 0.4),
        (4.0, 0.0, 1.0),
    ):
        rows.append(
            {
                "candidate": f"p{multiplier}",
                "multiplier": multiplier,
                "all_temporal_guards_pass": multiplier != 3.0,
                **{name: benefit for name in REFINE.B23PG_OBJECTIVES},
                **{name: cost for name in REFINE.TRANSFER_OBJECTIVES},
            }
        )
    _, selection = REFINE._rank_pareto(rows)
    assert selection["selected_candidate"] is None
