"""Tests for sequential FLA temporal blocks."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fla_temporal_contract import (  # noqa: E402
    TEMPORAL_BLOCKS,
    block_mask,
    promotion_contract,
    sequential_promotion_allowed,
    validate_blocks,
)


def test_blocks_span_j1_j46_without_gap() -> None:
    validate_blocks()
    assert TEMPORAL_BLOCKS[0].start_day == 1.0
    assert TEMPORAL_BLOCKS[-1].end_day == 46.0
    assert [block.end_day for block in TEMPORAL_BLOCKS[:-1]] == [
        block.start_day for block in TEMPORAL_BLOCKS[1:]
    ]


def test_non_independent_rows_are_absent_from_targets() -> None:
    contract = promotion_contract()
    targets = {name for block in contract for name in block["concentration_targets"]}
    assert "B13PG" not in targets
    assert "P2G" not in targets


def test_block_mask_and_sequential_gate() -> None:
    mask = block_mask(np.array([1.0, 2.0, 3.0, 4.0]), TEMPORAL_BLOCKS[0])
    assert mask.tolist() == [True, True, True, False]
    assessments = {block.name: {"fit": True, "guards": True} for block in TEMPORAL_BLOCKS}
    assert sequential_promotion_allowed(assessments) == (True, None)
    assessments[TEMPORAL_BLOCKS[1].name]["guards"] = False
    allowed, reason = sequential_promotion_allowed(assessments)
    assert allowed is False
    assert TEMPORAL_BLOCKS[1].name in str(reason)
