import json
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from fla_agentic_vmax_panel import measure, panel_from_observations
from fla_temporal_vmax import evaluate_panel, lp_step

DAYS = [4, 8, 11, 15]
DESIGN = {"fit_days": DAYS, "source_aliases": ["B13PG", "P2G"], "ambiguous_nominal_guards_only": ["B23PG", "P3G"],
          "working_allowance_fraction": .01, "zero_band_absolute_allowance_mM": 1e-6}
PLAN = {"critical_pointwise_pools": ["PEP", "G6P", "F6P", "AMP"], "minimum_each_day_relative_gain": .001}


def example():
    names = ["ATP", "ADP", "AMP", "PEP", "G6P", "F6P", "B13PG", "B23PG", "P2G", "P3G", *[f"P{i}" for i in range(45)]]
    p = panel_from_observations({"values": {k: [1.]*14 for k in names}, "time": [1, *DAYS, 18,22,25,29,32,36,38,43,46]}, DAYS, DESIGN)
    x = p["target"].copy()
    x[:3] = .5
    return x, measure(x, p), p


def test_late_regression_cannot_be_hidden_by_early_improvement():
    x, ref, p = example()
    x[:3, 0] = .95
    x[:3, -1] = .4
    r = evaluate_panel(x, ref, p, DESIGN, PLAN)
    assert r["mean_log_error"] < ref["adenylate_loss_raw"] and r["objective"] > 1
    assert not r["sufficient_every_day"] and not r["guards_pass"]


@pytest.mark.parametrize("pool", PLAN["critical_pointwise_pools"])
def test_every_critical_pool_has_a_dated_guard(pool):
    x, ref, p = example()
    x[p["names"].index(pool), 2] *= 1.3 if pool != "AMP" else .7
    r = evaluate_panel(x, ref, p, DESIGN, PLAN)
    assert r["guards"][f"point:{pool}:J11"] > 0 and not r["guards_pass"]


def test_minimax_lp_respects_guard_reserve_and_box():
    r = lp_step(np.array([0.]), np.array([-1.]), np.array([1.]), .5, [1., 1.],
                np.array([[-2.], [-1.]]), [-.2], np.array([[1.]]), np.array([.01]))
    assert r["delta"] == pytest.approx([.19]) and r["predicted_objective"] == pytest.approx(.81)


def test_scoring_record_is_strict_json():
    x, ref, p = example()
    assert json.loads(json.dumps(evaluate_panel(x, ref, p, DESIGN, PLAN), allow_nan=False))["guards_pass"] is True
