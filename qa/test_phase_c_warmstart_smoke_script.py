"""Tests for the Phase C offline warm-start smoke script."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_phase_c_warmstart_smoke.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("run_phase_c_warmstart_smoke", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


phase_c_smoke = _load_module()


def test_standardized_ridge_reconstructs_linear_signal():
    features = np.asarray(
        [
            [0.0, 0.0],
            [1.0, 0.0],
            [0.0, 1.0],
            [1.0, 1.0],
        ],
        dtype=float,
    )
    targets = np.asarray(
        [
            [0.0],
            [0.2],
            [-0.1],
            [0.1],
        ],
        dtype=float,
    )

    model = phase_c_smoke._fit_standardized_ridge(features, targets, regularization=1e-8)
    prediction = phase_c_smoke._predict_log_multipliers(model, np.asarray([0.25, 0.5], dtype=float))[0, 0]

    assert abs(prediction - 0.0) < 1e-6


def test_phase_c_micro_warmstart_smoke_writes_result_json(tmp_path):
    payload = phase_c_smoke.run_warmstart_smoke(
        out_dir=tmp_path,
        target_params=("vmax_VEGLC",),
        profile="micro",
        t_max=1.5,
        timepoints=5,
        max_improvement_ratio=0.5,
        max_abs_log_error=0.05,
    )

    result_path = tmp_path / "result.json"
    assert result_path.exists()
    result = json.loads(result_path.read_text(encoding="utf-8"))

    assert payload["status"] == "passed"
    assert result["contract_type"] == "phase_c_warmstart_smoke_result"
    assert result["status"] == "passed"
    assert result["feature_version"] == "phase_b_v1"
    assert result["target_params"] == ["vmax_VEGLC"]
    assert result["training"]["case_count"] == 3
    assert result["model"]["kind"] == "standardized_ridge"
    assert result["model"]["feature_count"] == 244
    assert result["validation"]["improvement_ratio"] < result["gate"]["max_improvement_ratio"]
    assert result["validation"]["max_abs_log_error"] < result["gate"]["max_abs_log_error"]
