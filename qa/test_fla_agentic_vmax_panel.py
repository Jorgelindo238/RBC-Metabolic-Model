from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from fla_agentic_vmax_panel import compare_metrics, measure, panel_from_observations

DESIGN = {"fit_days": [4], "source_aliases": ["B13PG", "P2G"], "ambiguous_nominal_guards_only": ["B23PG", "P3G"],
          "working_allowance_fraction": .01, "zero_band_absolute_allowance_mM": 1e-6, "minimum_relative_adenylate_gain": .001}


def panel():
    names = ["ATP", "ADP", "AMP", "B13PG", "B23PG", "P2G", "P3G", "ZERO", *[f"P{i}" for i in range(47)]]
    values = {p: [1.]*14 if p != "ZERO" else [0.]*14 for p in names}
    times = [1,4,8,11,15,18,22,25,29,32,36,38,43,46]
    return panel_from_observations({"values": values, "time": times}, [4], DESIGN)


def test_alias_has_no_score_or_guard_but_nominal_pair_guard_remains():
    p = panel()
    y = p["target"].copy()
    ref = measure(y, p)
    y[p["names"].index("B13PG")] = 100
    y[p["names"].index("B23PG")] = 3
    m = measure(y, p)
    assert m["other_loss_raw"] == 0
    assert compare_metrics(m, ref, p, DESIGN)["off_target_failures"] == ["B23PG"]


def test_zero_band_requires_absolute_guard_without_division_or_pseudocount():
    p = panel()
    y = p["target"].copy()
    ref = measure(y, p)
    i = p["names"].index("ZERO")
    y[i] = .00001
    m = measure(y, p)
    assert m["scaled_sample_count"][i] == 0 and compare_metrics(m, ref, p, DESIGN)["off_target_failures"] == ["ZERO"]


def test_adenylates_fail_closed_at_zero():
    p = panel()
    y = p["target"].copy()
    y[0] = 0
    with pytest.raises(ValueError, match="no pseudocount"):
        measure(y, p)
