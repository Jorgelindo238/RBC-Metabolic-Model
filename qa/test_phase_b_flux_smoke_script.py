"""Tests for the Phase B model-flux smoke script."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_phase_b_flux_smoke.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("run_phase_b_flux_smoke", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


phase_b_smoke = _load_module()


def test_phase_b_model_flux_smoke_writes_result_json(tmp_path):
    payload = phase_b_smoke.run_smoke(
        out_dir=tmp_path,
        t_max=2.0,
        timepoints=8,
        tolerances={"VEGLC": 0.05, "VELAC": 0.05, "VLDH": 0.15},
    )

    result_path = tmp_path / "result.json"
    assert result_path.exists()
    result = json.loads(result_path.read_text(encoding="utf-8"))

    assert payload["status"] == "passed"
    assert result["contract_type"] == "phase_b_model_flux_smoke_result"
    assert result["status"] == "passed"
    assert result["source"] == "brodbar_ode_flux_tracker"
    assert result["reactions"] == ["VEGLC", "VELAC", "VLDH"]
    assert result["feature_payload"]["feature_version"] == "phase_b_v1"
    assert result["feature_payload"]["metadata"]["feature_count"] == 78

    for reaction in ("VEGLC", "VELAC", "VLDH"):
        comparison = result["comparisons"][reaction]
        assert comparison["passed"] is True
        assert comparison["nrmse_vs_model_flux"] <= comparison["tolerance"]
        assert len(result["tracked_fluxes"][reaction]) == 8
        assert len(result["inferred_fluxes"][reaction]) == 8


def test_phase_b_wide_flux_smoke_discovers_vhk(tmp_path):
    payload = phase_b_smoke.run_smoke(
        out_dir=tmp_path,
        preset="wide",
        discover_identifiable=True,
        t_max=2.0,
        timepoints=8,
        tolerances={"VEGLC": 0.08, "VELAC": 0.08, "VLDH": 0.15, "VHK": 0.08},
    )

    result = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))

    assert payload["status"] == "passed"
    assert result["preset"] == "wide"
    assert result["target_metabolites"] == list(phase_b_smoke.WIDE_METABOLITES)
    assert result["reactions"] == ["VEGLC", "VELAC", "VLDH", "VHK"]
    assert result["feature_payload"]["metadata"]["metabolite_count"] == len(phase_b_smoke.WIDE_METABOLITES)
    assert result["feature_payload"]["metadata"]["reaction_count"] == len(phase_b_smoke.WIDE_REACTIONS)
    assert result["feature_payload"]["metadata"]["feature_count"] == 244

    assert result["comparisons"]["VHK"]["passed"] is True
    assert "VHK" in result["discovery"]["accepted_reactions"]
    assert result["discovery"]["candidate_count"] >= len(phase_b_smoke.WIDE_REACTIONS)
    assert result["discovery"]["accepted_count"] >= 4
