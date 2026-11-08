import json
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from fla_absolute_vmax import absolute_score, evaluate_screen, target_spec
from test_fla_temporal_vmax import DESIGN, PLAN, example

ABS = {"target_pools": ["ATP", "ADP"], "target_day": 15,
       "target_band": "inherited_working_scale"}


def test_absolute_target_does_not_move_with_bad_reference():
    x, ref, panel = example()
    spec = target_spec(panel, ABS)
    assert spec["ATP"]["lower_mM"] == pytest.approx(.75)
    assert spec["ADP"]["upper_mM"] == pytest.approx(1.25)
    for value in (.0001, .1):
        x[:2, -1] = value
        result = evaluate_screen(x, ref, panel, DESIGN, PLAN, spec)
        assert not result["absolute"]["target_pass"]
    assert result["absolute"]["objective"] > 0


@pytest.mark.parametrize("value,passed", [(1., True), (.75, True), (1.25, True), (.74, False), (1.26, False)])
def test_two_sided_absolute_targets(value, passed):
    x, _, panel = example()
    x[:2, -1] = value
    result = absolute_score(x, panel, target_spec(panel, ABS))
    assert result["target_pass"] is passed
    assert json.loads(json.dumps(result, allow_nan=False)) == result


def test_one_adenylate_cannot_compensate_for_the_other():
    x, _, panel = example()
    x[0,-1], x[1,-1] = 1., .01
    r = absolute_score(x, panel, target_spec(panel, ABS))
    assert r["objective"] == pytest.approx(np.log(.75/.01))
    assert not r["target_pass"]


def test_early_regression_disqualifies_late_target_hit():
    x, ref, panel = example()
    x[:2,-1] = 1.
    x[:3,0] = .1
    r = evaluate_screen(x, ref, panel, DESIGN, PLAN, target_spec(panel, ABS))
    assert r["absolute"]["target_pass"] and not r["feasibility_guards_pass"]
    assert r["feasibility_guards"]["date_gain:J4"] > 0


@pytest.mark.parametrize("pool", PLAN["critical_pointwise_pools"])
def test_critical_guard_survives_absolute_objective(pool):
    x, ref, panel = example()
    x[panel["names"].index(pool),2] *= .1 if pool == "AMP" else 2.
    r = evaluate_screen(x, ref, panel, DESIGN, PLAN, target_spec(panel, ABS))
    assert r["feasibility_guards"][f"point:{pool}:J11"] > 0


@pytest.mark.parametrize("value", [0., -1., float("nan")])
def test_no_clipping_or_pseudocount(value):
    x, _, panel = example()
    x[0,-1] = value
    with pytest.raises(ValueError):
        absolute_score(x, panel, target_spec(panel, ABS))
