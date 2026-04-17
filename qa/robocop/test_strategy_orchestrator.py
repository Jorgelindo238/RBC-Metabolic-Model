from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

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
