from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api.services import custom_calibration_orchestrator as orchestrator


def _make_request(**overrides):
    payload = {
        "target_metabolites": ["ATP", "ADP", "AMP", "EGLC", "ELAC"],
        "exp_time": [1.0, 7.0, 14.0, 21.0],
        "exp_data": {
            "ATP": [1.2, 1.1, 1.0, 0.9],
            "ADP": [0.4, 0.45, 0.48, 0.5],
            "AMP": [0.05, 0.06, 0.07, 0.08],
            "EGLC": [5.0, 4.0, 3.0, 2.0],
            "ELAC": [1.0, 1.3, 1.7, 2.1],
        },
        "optimization_strategy": None,
        "enable_strategy_memory": True,
        "enable_teacher_flux_rescue": False,
        "strategy_race_budget": 3,
        "orchestration_mode": "strategy_race",
        "rerun_pure_ode": True,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_build_dataset_fingerprint_is_stable():
    request = _make_request()
    a = orchestrator.build_dataset_fingerprint(request)
    b = orchestrator.build_dataset_fingerprint(request)

    assert a["fingerprint"] == b["fingerprint"]
    assert a["measured_metabolites"] == ["ATP", "ADP", "AMP", "EGLC", "ELAC"]


def test_strategy_race_selects_best_combined_verdict(monkeypatch, tmp_path):
    monkeypatch.setattr(orchestrator, "_MEMORY_PATH", tmp_path / "memory.jsonl")

    def _single_run(request):
        strategy = request.optimization_strategy
        if strategy == "vmax_then_km":
            return {
                "success": True,
                "optimization_strategy": strategy,
                "optimized_params": {"vmax_VHK": 1.1},
                "all_optimized_params": {"vmax_VHK": 1.1},
                "final_loss": 1.2,
                "improvement_pct": 12.0,
                "r_squared": 0.71,
                "combined_triage": {"overall": "keep", "reason": "best"},
                "triage": {"overall": "keep"},
                "pure_ode_triage": {"overall": "healthy"},
            }
        return {
            "success": True,
            "optimization_strategy": strategy,
            "optimized_params": {"vmax_VHK": 0.9},
            "all_optimized_params": {"vmax_VHK": 0.9},
            "final_loss": 0.8,
            "improvement_pct": 8.0,
            "r_squared": 0.65,
            "combined_triage": {"overall": "discard", "reason": "collapsed"},
            "triage": {"overall": "discard"},
            "pure_ode_triage": {"overall": "collapsed"},
        }

    result = orchestrator.run_strategy_race_calibration(
        _make_request(),
        single_run_callable=_single_run,
    )

    assert result["optimization_strategy"] == "vmax_then_km"
    assert result["orchestration"]["winner_strategy"] == "vmax_then_km"
    assert result["orchestration"]["winner_verdict"] == "keep"
    assert len(result["orchestration"]["runs"]) == 3
    assert (tmp_path / "memory.jsonl").exists()


def test_strategy_candidates_prioritize_memory_hits(monkeypatch, tmp_path):
    memory_path = tmp_path / "memory.jsonl"
    memory_path.write_text(
        '{"fingerprint":"abc","winning_strategy":"km_then_vmax"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(orchestrator, "_MEMORY_PATH", memory_path)
    request = _make_request()
    fingerprint = orchestrator.build_dataset_fingerprint(request)
    fingerprint["fingerprint"] = "abc"

    strategies, memory_hits = orchestrator._build_strategy_candidates(request, fingerprint)

    assert memory_hits == ["km_then_vmax"]
    assert strategies[0] == "km_then_vmax"


@pytest.mark.parametrize("fields", [
    {"optimization_strategy": "vmax_only"},
    {"method": "vmax_only"},
    {"optimization_strategy": "joint_vmax_km", "method": "vmax_only"},
    {"optimization_strategy": "vmax_only", "method": "km_only"},
    {"optimization_strategy": " VMAX_ONLY "},
])
@pytest.mark.parametrize("budget", [1, 8])
def test_explicit_vmax_only_never_reads_strategy_memory(monkeypatch, fields, budget):
    def forbidden_memory(*args):
        pytest.fail("fixed-Km candidates must not depend on strategy memory")

    monkeypatch.setattr(orchestrator, "_memory_hits_for_fingerprint", forbidden_memory)
    request = _make_request(**fields, strategy_race_budget=budget)
    assert orchestrator._build_strategy_candidates(
        request, orchestrator.build_dataset_fingerprint(request)
    ) == (["vmax_only"], [])


@pytest.mark.parametrize("field", ["optimization_strategy", "method"])
def test_vmax_only_race_preserves_request_and_skips_teacher_rescue(monkeypatch, field):
    request = _make_request(**{field: "vmax_only"}, enable_teacher_flux_rescue=True)
    before = vars(request).copy()
    calls = []

    def single_run(candidate):
        calls.append(candidate)
        assert candidate.optimization_strategy == candidate.method == "vmax_only"
        assert candidate.orchestration_mode == "single_run"
        assert candidate.rerun_pure_ode is True
        return {"success": True, "final_loss": 0.0, "combined_triage": {"overall": "discard"}}

    def forbidden_rescue(**kwargs):
        pytest.fail("generic teacher rescue cannot guarantee fixed Km")

    monkeypatch.setattr(orchestrator, "run_teacher_flux_rescue", forbidden_rescue)
    result = orchestrator.run_strategy_race_calibration(request, single_run_callable=single_run)
    assert len(calls) == 1
    assert vars(request) == before
    assert result["optimization_strategy"] == "vmax_only"
    assert result["final_loss"] == 0.0
    assert result["orchestration"]["strategies_considered"] == ["vmax_only"]
    assert result["orchestration"]["teacher_flux_rescue"] is None
    assert result["orchestration"]["teacher_flux_rescue_skipped_reason"] == "fixed_km_constraint"


@pytest.mark.parametrize("loss_fields, expected", [
    ({"final_loss": 0.0, "objective_value": 9.0}, 0.0),
    ({"objective_value": 0.0}, 0.0),
    ({"final_loss": None, "objective_value": 0.0}, 0.0),
    ({"final_loss": 2.0, "objective_value": 9.0}, 2.0),
    ({}, 1e9),
])
def test_candidate_sort_key_preserves_zero_loss(loss_fields, expected):
    assert orchestrator._candidate_sort_key(loss_fields)[1] == -expected


def test_zero_loss_candidate_wins_at_equal_verdict(monkeypatch):
    monkeypatch.setattr(orchestrator, "_read_strategy_memory", lambda: [])

    def single_run(request):
        return {
            "final_loss": 0.0 if request.optimization_strategy == "km_then_vmax" else 1.0,
            "combined_triage": {"overall": "needs_review"},
        }

    result = orchestrator.run_strategy_race_calibration(_make_request(), single_run_callable=single_run)
    assert result["orchestration"]["winner_strategy"] == "km_then_vmax"


def test_parameter_contract_alone_restricts_the_race_to_vmax_only(monkeypatch):
    def forbidden_memory(*args):
        pytest.fail("fixed-Km candidates must not depend on strategy memory")

    monkeypatch.setattr(orchestrator, "_memory_hits_for_fingerprint", forbidden_memory)
    request = _make_request(parameter_contract="vmax_only_fixed_km", strategy_race_budget=8)
    assert orchestrator._build_strategy_candidates(
        request, orchestrator.build_dataset_fingerprint(request)
    ) == (["vmax_only"], [])


@pytest.mark.parametrize("verdict", ["keep", "keep_with_caveats"])
def test_fixed_km_race_never_writes_strategy_memory(monkeypatch, tmp_path, verdict):
    memory_path = tmp_path / "memory.jsonl"
    monkeypatch.setattr(orchestrator, "_MEMORY_PATH", memory_path)

    def forbidden_append(entry):
        pytest.fail("fixed-Km runs must not write strategy memory")

    monkeypatch.setattr(orchestrator, "_append_strategy_memory", forbidden_append)
    result = orchestrator.run_strategy_race_calibration(
        _make_request(optimization_strategy="vmax_only"),
        single_run_callable=lambda request: {"final_loss": 1.0, "combined_triage": {"overall": verdict}},
    )
    assert not memory_path.exists()
    assert result["orchestration"]["fixed_km"] is True
    assert result["orchestration"]["strategy_memory_used"] is False
    assert result["orchestration"]["strategies_considered"] == ["vmax_only"]


def test_legacy_race_reports_that_it_is_not_fixed_km(monkeypatch):
    monkeypatch.setattr(orchestrator, "_read_strategy_memory", lambda: [])
    result = orchestrator.run_strategy_race_calibration(
        _make_request(),
        single_run_callable=lambda request: {"final_loss": 1.0, "combined_triage": {"overall": "needs_review"}},
    )
    assert result["orchestration"]["fixed_km"] is False
    assert result["orchestration"]["strategy_memory_used"] is True


def test_legacy_race_still_dispatches_teacher_rescue(monkeypatch):
    monkeypatch.setattr(orchestrator, "_read_strategy_memory", lambda: [])
    calls = []

    def rescue(**kwargs):
        calls.append(kwargs)
        return {"status": "stubbed"}

    monkeypatch.setattr(orchestrator, "run_teacher_flux_rescue", rescue)
    result = orchestrator.run_strategy_race_calibration(
        _make_request(enable_teacher_flux_rescue=True),
        single_run_callable=lambda request: {
            "final_loss": 1.0,
            "optimized_params": {"vmax_VHK": 1.1},
            "combined_triage": {"overall": "needs_review"},
        },
    )
    assert result["orchestration"]["strategies_considered"] == [
        "vmax_then_km", "km_then_vmax", "joint_vmax_km",
    ]
    assert len(calls) == 1
    assert calls[0]["params"] == {"vmax_VHK": 1.1}
    assert result["orchestration"]["teacher_flux_rescue"] == {"status": "stubbed"}
    assert "teacher_flux_rescue_skipped_reason" not in result["orchestration"]
