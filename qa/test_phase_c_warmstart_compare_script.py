"""Tests for the Phase C warm-start-vs-default calibration comparator."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_phase_c_warmstart_compare.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("run_phase_c_warmstart_compare", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


phase_c_compare = _load_module()


def test_loss_comparison_requires_warmstart_to_beat_default():
    passed = phase_c_compare._loss_comparison(
        default_loss=10.0,
        warmstart_loss=8.0,
        min_relative_improvement=0.1,
    )
    failed = phase_c_compare._loss_comparison(
        default_loss=10.0,
        warmstart_loss=9.5,
        min_relative_improvement=0.1,
    )

    assert passed["passed"] is True
    assert passed["decision_gate"] == "warmstart_beats_default"
    assert failed["passed"] is False
    assert failed["decision_gate"] == "needs_review"


def test_aggregate_case_comparisons_requires_configured_win_rate():
    cases = [
        {
            "case_id": "case_a",
            "comparison": phase_c_compare._loss_comparison(
                default_loss=10.0,
                warmstart_loss=8.0,
                min_relative_improvement=0.0,
            ),
        },
        {
            "case_id": "case_b",
            "comparison": phase_c_compare._loss_comparison(
                default_loss=10.0,
                warmstart_loss=9.0,
                min_relative_improvement=0.0,
            ),
        },
        {
            "case_id": "case_c",
            "comparison": phase_c_compare._loss_comparison(
                default_loss=10.0,
                warmstart_loss=11.0,
                min_relative_improvement=0.0,
            ),
        },
    ]

    failed = phase_c_compare._aggregate_case_comparisons(
        cases,
        min_case_win_rate=1.0,
        min_mean_relative_improvement=0.0,
    )
    passed = phase_c_compare._aggregate_case_comparisons(
        cases,
        min_case_win_rate=0.5,
        min_mean_relative_improvement=0.0,
    )

    assert failed["passed"] is False
    assert failed["failed_case_ids"] == ["case_c"]
    assert failed["decision_gate"] == "needs_review"
    assert passed["passed"] is True
    assert passed["decision_gate"] == "aggregate_warmstart_beats_default"


def test_phase_c_micro_warmstart_compare_writes_result_json(tmp_path):
    payload = phase_c_compare.run_warmstart_comparison(
        out_dir=tmp_path,
        profile="micro",
        target_params=("vmax_VEGLC",),
        t_max=1.5,
        timepoints=5,
        n_trials=1,
    )

    result_path = tmp_path / "result.json"
    assert result_path.exists()
    result = json.loads(result_path.read_text(encoding="utf-8"))

    assert payload["status"] == "passed"
    assert result["contract_type"] == "phase_c_warmstart_calibration_compare_result"
    assert result["status"] == "passed"
    assert result["feature_version"] == "phase_b_v1"
    assert result["target_params"] == ["vmax_VEGLC"]
    assert result["settings"]["n_trials"] == 1
    assert result["branches"]["default_no_ml"]["final_loss"] > result["branches"]["warmstart"]["final_loss"]
    assert result["comparison"]["decision_gate"] == "warmstart_beats_default"
    assert result["comparison"]["relative_improvement"] > 0.0
    assert Path(result["branches"]["default_no_ml"]["report_path"]).exists()
    assert Path(result["branches"]["warmstart"]["report_path"]).exists()


def test_phase_c_micro_warmstart_compare_all_validation_cases(tmp_path):
    payload = phase_c_compare.run_warmstart_comparison(
        out_dir=tmp_path,
        profile="micro",
        target_params=("vmax_VEGLC",),
        t_max=1.5,
        timepoints=5,
        n_trials=1,
        all_validation_cases=True,
    )

    result_path = tmp_path / "result.json"
    assert result_path.exists()
    result = json.loads(result_path.read_text(encoding="utf-8"))

    assert payload["status"] == "passed"
    assert result["contract_version"] == 2
    assert result["settings"]["all_validation_cases"] is True
    assert result["comparison"]["decision_gate"] == "aggregate_warmstart_beats_default"
    assert result["comparison"]["case_count"] == 2
    assert result["comparison"]["win_rate"] == 1.0
    assert len(result["cases"]) == 2
    for case in result["cases"]:
        assert case["comparison"]["relative_improvement"] > 0.0
        assert Path(case["branches"]["default_no_ml"]["report_path"]).exists()
        assert Path(case["branches"]["warmstart"]["report_path"]).exists()
