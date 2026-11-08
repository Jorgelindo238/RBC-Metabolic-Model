import json
import math

import numpy as np
import pytest

from src.fla_agentic_vmax_search import inject_vmax_only, search_vmax


def score(adenylate=1.0, other=1.0, guard=0.0, **extra):
    return {"valid": True, "adenylate_loss": adenylate, "other_loss": other,
            "max_guard_excess": guard, **extra}


def test_injection_scales_named_groups_only_and_keeps_closed_branches():
    base = {"vmax_VAK": 2.0, "vmax_VAK_rev": 0.25, "vmax_VNDPK": 1.0,
            "vmax_VNDPK_rev": 3.0, "vmax_VHK": 4.0, "vmax_VAK2": 5.0,
            "vmax_VOPLAH": -0.0, "km_ATP": 0.2, "temperature": 4.0}
    before = dict(base)
    groups = {"NDPK": ("vmax_VNDPK_rev", "vmax_VNDPK"),
              "AK": ("vmax_VAK", "vmax_VAK_rev"), "closed": ("vmax_VOPLAH",),
              "HK": ("vmax_VHK",)}
    result = inject_vmax_only(base, groups, (math.log(2), math.log(0.5), math.log(3), 0))
    assert result is not base
    assert base == before
    assert result == {**before, "vmax_VAK": 1.0, "vmax_VAK_rev": 0.125,
                      "vmax_VNDPK": 2.0, "vmax_VNDPK_rev": 6.0}
    assert math.copysign(1, result["vmax_VOPLAH"]) == -1
    assert inject_vmax_only({"vmax_VAK": 1.0, "vmax_VAK_rev": 0.0},
                            {"AK": ("vmax_VAK", "vmax_VAK_rev")}, (math.log(2),)) == {
        "vmax_VAK": 2.0, "vmax_VAK_rev": 0.0,
    }


@pytest.mark.parametrize("groups, logs, message", [
    ({"bad": ("km_ATP",)}, (0,), "not an AIRBC Vmax"),
    ({"bad": ("temperature",)}, (0,), "not an AIRBC Vmax"),
    ({"bad": ("vmax_VUNKNOWN",)}, (0,), "unresolved"),
    ({"bad": ("vmax_VHK", "vmax_VHK")}, (0,), "listed more than once"),
    ({"one": ("vmax_VHK",), "two": ("vmax_VHK",)}, (0, 0), "listed more than once"),
    ({"one": ("vmax_VAK",)}, (0,), "same group"),
    ({"one": ("vmax_VAK",), "two": ("vmax_VAK_rev",)}, (0, 0), "same group"),
    ({"one": ("vmax_VNDPK_rev",)}, (0,), "same group"),
    ({"one": ("vmax_VNDPK",), "two": ("vmax_VNDPK_rev",)}, (0, 0), "same group"),
    ({"one": ("vmax_VHK",)}, (float("nan"),), "finite numeric"),
    ({"one": ("vmax_VHK",)}, (True,), "finite numeric"),
    ({"one": ("vmax_VHK",)}, (1000,), "finite positive factor"),
    ({"one": ("vmax_VHK",)}, (-1000,), "finite positive factor"),
    ({"one": ("vmax_VHK",)}, (), "1 finite numeric"),
    ({"one": "vmax_VHK"}, (0,), "sequence"),
    ({"one": ()}, (0,), "sequence"),
])
def test_injection_fails_closed_for_unregistered_or_malformed_changes(groups, logs, message):
    base = dict.fromkeys(("vmax_VHK", "vmax_VAK", "vmax_VAK_rev", "vmax_VNDPK",
                          "vmax_VNDPK_rev", "km_ATP", "temperature"), 1.0)
    before = dict(base)
    with pytest.raises(ValueError, match=message):
        inject_vmax_only(base, groups, logs)
    assert base == before


@pytest.mark.parametrize("capacity, log_factor, message", [
    (-1.0, 0.0, "invalid base"), (float("inf"), 0.0, "invalid base"),
    (True, 0.0, "invalid base"), ("1.0", 0.0, "invalid base"),
    (1e308, 1.0, "overflow or close"), (math.ulp(0.0), -1.0, "overflow or close"),
])
def test_injection_cannot_corrupt_a_capacity(capacity, log_factor, message):
    with pytest.raises(ValueError, match=message):
        inject_vmax_only({"vmax_VHK": capacity}, {"HK": ("vmax_VHK",)}, (log_factor,))


@pytest.mark.parametrize("dimension, budget", [(8, 150), (14, 350)])
@pytest.mark.parametrize("explore_infeasible", [False, True])
def test_mixed_search_respects_real_budget_and_log_bounds(dimension, budget, explore_infeasible):
    bounds = {f"g{i}": (-0.4, 0.2) for i in reversed(range(dimension))}
    bounds["fixed"] = (0.1, 0.1)
    calls = []

    def evaluate(vector):
        assert isinstance(vector, tuple)
        assert all(lo <= v <= hi for v, (lo, hi) in zip(vector, bounds.values(), strict=True))
        calls.append(vector)
        return score(sum((v - 0.05) ** 2 for v in vector[:-1]), sum(v * v for v in vector[:-1]), vector[0] - 0.1)

    anchor = (0.0,) * dimension + (0.1,)
    result = search_vmax(evaluate, bounds, budget=budget, seed=12, starts=(anchor, anchor),
                         explore_infeasible=explore_infeasible)
    assert result["group_order"] == list(bounds)
    assert result["actual_evaluations"] == len(set(calls)) == len(calls) == budget
    assert result["probes"] == len(result["trace"]) == budget + result["cache_hits"]
    assert result["cache_hits"] >= 2 + len(result["refinements"])
    assert result["stop_reason"] == "budget_exhausted"
    expected_policies = ["guarded", "adenylate_only", "guard_restoration"] if explore_infeasible else ["guarded"] * 3
    assert [run["policy"] for run in result["refinements"]] == expected_policies
    stages = {row["stage"] for row in result["trace"]}
    assert {"global_exploration", "near_anchor_exploration", "refinement_1"} <= stages
    actual = [row for row in result["trace"] if row["source"] == "evaluation"]
    assert [row["evaluation_id"] for row in actual] == list(range(1, budget + 1))
    assert [tuple(row["log_factors"]) for row in actual] == calls
    for row in result["trace"]:
        assert row["log_factors"] == actual[row["evaluation_id"] - 1]["log_factors"]
    best = result["best_feasible"]
    assert best["adenylate_loss"] < actual[0]["adenylate_loss"]
    assert best in actual
    json.dumps(result, allow_nan=False)


def test_seeded_starts_and_entire_trace_are_deterministic():
    bounds = {"high": (0.1, 1.0), "low": (-1.0, -0.2), "variable": (-0.3, 0.4)}

    def evaluate(vector):
        return score(sum(v * v for v in vector), sum(abs(v + 0.15) for v in vector), vector[2] - 0.2)

    params = {"budget": 75, "starts": [(0.2, -0.3, 0.1)]}
    first = search_vmax(evaluate, bounds, seed=42, **params)
    assert first == search_vmax(evaluate, bounds, seed=42, **params)
    different = search_vmax(evaluate, bounds, seed=43, **params)
    assert first["trace"][:2] == different["trace"][:2]
    assert first["trace"][0]["log_factors"] == [0.1, -0.2, 0.0]
    assert first["trace"][2]["log_factors"] != different["trace"][2]["log_factors"]


def test_gates_rank_real_vectors_and_preserve_two_objective_pareto_ties():
    cases = {0.0: score(2.0, 2.0), 1.0: score(1.0, 4.0), 2.0: score(4.0, 1.0),
             3.0: score(2.0, 2.0), 4.0: score(3.0, 3.0, -10.0),
             5.0: score(0.0, 0.0, math.ulp(0.0)), 6.0: score(-1.0, -1.0, 0.1),
             7.0: score(0.0, 0.0, valid=False), 8.0: score(2.0, 4.0, -1.0),
             9.0: score(1.0, 5.0, -2.0)}
    result = search_vmax(lambda x: cases[x[0]], {"g": (0, 9)}, budget=len(cases),
                         starts=[(x,) for x in cases if x])
    assert [r["log_factors"][0] for r in result["ranked_feasible"]] == [1, 9, 0, 3, 8, 4, 2]
    assert [r["log_factors"][0] for r in result["pareto_feasible"]] == [1, 0, 3, 2]
    assert [r["log_factors"][0] for r in result["ranked_infeasible"]] == [5, 6]
    assert result["best_feasible"]["log_factors"] == [1.0]
    assert not result["ranked_infeasible"][0]["guard_pass"]
    assert result["ranked_infeasible"][0]["max_guard_excess"] > 0.0
    assert result["trace"][7]["guard_pass"] and not result["trace"][7]["feasible"]


def test_invalid_attempts_and_diagnostics_survive_and_are_cached():
    calls, checkpoints = [], []

    def evaluate(vector):
        calls.append(vector)
        value = vector[0]
        if value == 0:
            raise RuntimeError("BDF failed")
        if value == 1:
            return score(float("nan"), trace=np.array([1.0, np.inf, -np.inf]))
        if value == 2:
            return {"valid": False, "reason": "negative pool", "step": np.int64(17)}
        if value == 3:
            return score(valid=1)
        if value == 4:
            return None
        if value == 5:
            return score(guard=float("inf"))
        return score(valid=np.bool_(True), extra={"ATP": (np.float32(0.125),)})

    def checkpoint(row):
        checkpoints.append(json.loads(json.dumps(row, allow_nan=False)))
        row["log_factors"][0] = 999

    result = search_vmax(evaluate, {"g": (0, 6)}, budget=7, on_probe=checkpoint,
                         starts=[(0,), (1,), (2,), (3,), (4,), (5,), (6,)])
    assert checkpoints == result["trace"]
    assert len(calls) == result["actual_evaluations"] == 7
    assert result["probes"] == 8 and result["cache_hits"] == 1
    assert result["failed_evaluations"] == 6
    assert [r["failure"]["kind"] for r in result["trace"][:-1]] == [
        "exception", "exception", "invalid_scores", "invalid_evaluation", "invalid_return",
        "invalid_return", "invalid_scores",
    ]
    first, cached, nan, invalid, *_ = result["trace"]
    assert first["evaluation_id"] == cached["evaluation_id"] == 1
    assert cached["source"] == "cache"
    assert first["failure"] == {"kind": "exception", "type": "RuntimeError", "message": "BDF failed"}
    assert nan["callback_result"]["trace"] == [1.0, "inf", "-inf"]
    assert nan["callback_result"]["adenylate_loss"] == "nan"
    assert invalid["callback_result"] == {"valid": False, "reason": "negative pool", "step": 17}
    assert result["best_feasible"]["callback_result"]["extra"] == {"ATP": [0.125]}
    assert not result["ranked_infeasible"]


def test_all_invalid_falls_back_to_exploration_without_a_candidate():
    result = search_vmax(lambda _: {"valid": False}, {"g": (-1, 1)}, budget=25)
    assert result["actual_evaluations"] == result["failed_evaluations"] == 25
    assert result["best_feasible"] is None
    assert result["ranked_feasible"] == result["pareto_feasible"] == result["ranked_infeasible"] == []
    assert not result["refinements"]
    assert result["trace"][-1]["stage"] == "fill_exploration"


def test_infeasible_search_refines_guard_excess_without_accepting_violation():
    def evaluate(x):
        return score(x[0], x[1], 0.1 + (x[0] - 0.2) ** 2 + (x[1] - 0.3) ** 2)

    result = search_vmax(evaluate, {"g": (-1, 1), "h": (-1, 1)}, budget=120)
    assert result["best_feasible"] is None
    assert result["pareto_feasible"] == []
    best = result["ranked_infeasible"][0]
    assert best["stage"].startswith("refinement_")
    assert best["max_guard_excess"] == pytest.approx(0.1, abs=2e-5)


def test_optional_adenylate_exploration_can_improve_violating_seed_but_not_pass_it():
    def evaluate(vector):
        x = vector[0]
        return score((x - 0.8) ** 2, (x + 0.2) ** 2, abs(x))

    bounds = {"g": (-1, 1)}
    starts = [(-i / 20,) for i in range(1, 19)] + [(0.4,)]
    baseline = search_vmax(evaluate, bounds, budget=60, starts=starts)
    result = search_vmax(evaluate, bounds, budget=60, starts=starts, explore_infeasible=True)
    assert result["actual_evaluations"] == baseline["actual_evaluations"] == 60
    assert [run["policy"] for run in result["refinements"]] == [
        "guarded", "adenylate_only", "guard_restoration",
    ]
    exploratory, restoration = result["refinements"][1:]
    stages = {run["stage"]: [row for row in result["trace"] if row["stage"] == run["stage"]]
              for run in result["refinements"]}
    all_prior = result["trace"][:stages[exploratory["stage"]][0]["probe_id"] - 1]
    assert exploratory["start_evaluation_id"] == min(all_prior, key=lambda r: r["adenylate_loss"])["evaluation_id"]
    seed = stages[exploratory["stage"]][0]
    assert seed["source"] == "cache" and not seed["feasible"]
    assert min(r["adenylate_loss"] for r in stages[exploratory["stage"]]) < seed["adenylate_loss"] / 10
    restoration_seed = stages[restoration["stage"]][0]
    assert restoration_seed["max_guard_excess"] > 0
    assert min(r["max_guard_excess"] for r in stages[restoration["stage"]]) < restoration_seed["max_guard_excess"]
    assert result["best_feasible"] == baseline["best_feasible"] == result["trace"][0]
    assert result["pareto_feasible"] == [result["best_feasible"]]
    assert all(r["max_guard_excess"] > 0 for r in result["ranked_infeasible"])


def test_exploratory_mode_reserves_two_local_starts_when_budget_allows():
    bounds = {"g": (-1, 1), "h": (-1, 1)}
    evaluate = lambda x: score((x[0] - 0.2) ** 2, 0.0, abs(x[0]))
    small = search_vmax(evaluate, bounds, budget=8, explore_infeasible=True)
    assert [r["policy"] for r in small["refinements"]] == ["guard_restoration", "adenylate_only"]
    tiny = search_vmax(evaluate, bounds, budget=5, explore_infeasible=True)
    assert [r["policy"] for r in tiny["refinements"]] == ["guarded"]
    assert small["actual_evaluations"] == 8 and tiny["actual_evaluations"] == 5


def test_fixed_and_float_resolution_boxes_do_not_repeat_integrations():
    fixed = search_vmax(lambda _: score(), {"g": (0.2, 0.2)}, budget=10, starts=[(0.2,)])
    assert fixed["actual_evaluations"] == 1 and fixed["probes"] == 2
    assert fixed["stop_reason"] == "fixed_box"
    adjacent = search_vmax(lambda _: score(), {"g": (1.0, math.nextafter(1.0, 2.0))}, budget=25)
    assert adjacent["actual_evaluations"] == 2
    assert adjacent["stop_reason"] == "design_exhausted"


@pytest.mark.parametrize("bounds, kwargs, message", [
    ({}, {}, "nonempty"), ({"g": (2, 1)}, {}, "lower log bounds"),
    ({"g": (0, 1000)}, {}, "finite positive factor"),
    ({"g": (0, float("inf"))}, {}, "finite numeric"),
    ({"g": (0, 1)}, {"starts": [(0.1,), (1.1,)]}, "inside"),
    ({"g": (0, 1)}, {"starts": [(0.1, 0.2)]}, "1 finite numeric"),
    ({"g": (0, 1)}, {"starts": [(0.1,)], "budget": 1}, "distinct required starts"),
    ({"g": (0, 1)}, {"budget": 0}, "positive integer"),
    ({"g": (0, 1)}, {"budget": True}, "positive integer"),
    ({"g": (0, 1)}, {"seed": -1}, "nonnegative integer"),
    ({"g": (0, 1)}, {"explore_infeasible": 1}, "must be a boolean"),
])
def test_invalid_configuration_rejected_before_evaluation(bounds, kwargs, message):
    def unexpected(_):
        pytest.fail("evaluation was invoked for a malformed search")

    with pytest.raises(ValueError, match=message):
        search_vmax(unexpected, bounds, **{"budget": 10, **kwargs})


def test_checkpoint_failure_propagates_and_stops_before_another_integration():
    calls = []

    def evaluate(vector):
        calls.append(vector)
        return score()

    def checkpoint(row):
        assert row["evaluation_id"] == 1
        raise OSError("checkpoint unavailable")

    with pytest.raises(OSError, match="checkpoint unavailable"):
        search_vmax(evaluate, {"g": (-1, 1)}, budget=150, on_probe=checkpoint)
    assert calls == [(0.0,)]
