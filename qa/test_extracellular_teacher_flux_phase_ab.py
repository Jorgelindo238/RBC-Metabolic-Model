from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_extracellular_flux_learning_phase_ab.py"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from extracellular_teacher_flux import (  # noqa: E402
    EXTRACELLULAR_TEACHER_METABOLITES,
    build_bordbar_extracellular_teacher_flux_dataset,
    build_extracellular_teacher_flux_dataset,
)


def _load_phase_ab_script():
    spec = importlib.util.spec_from_file_location("run_extracellular_flux_learning_phase_ab", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_bordbar_phase_a_dataset_covers_all_measured_extracellular_targets(tmp_path):
    dataset_path = tmp_path / "teacher_flux_dataset.json"
    payload = build_bordbar_extracellular_teacher_flux_dataset(
        out_path=dataset_path,
        dense_points=12,
    )

    assert dataset_path.exists()
    assert payload["contract_type"] == "teacher_flux_dataset"
    assert payload["flux_rule_version"] == "extracellular_v1"
    assert payload["target_metabolites"] == list(EXTRACELLULAR_TEACHER_METABOLITES)
    assert len(payload["reaction_flux_curves"]) == len(EXTRACELLULAR_TEACHER_METABOLITES)
    assert "VEGLC" in payload["reaction_flux_curves"]
    assert "VELAC" in payload["reaction_flux_curves"]
    assert "VEASN_rate" in payload["reaction_flux_curves"]
    assert "VEGSH_rate" in payload["reaction_flux_curves"]


def test_degradation_corrected_extracellular_flux_rule_for_egsh():
    payload = build_extracellular_teacher_flux_dataset(
        {"EGSH": [1.0, 1.0, 1.0]},
        [1.0, 2.0, 3.0],
        metabolite_names=["EGSH"],
        dense_points=3,
        degradation_params={"k_EGSH_deg": 0.2},
    )

    flux_values = np.asarray(payload["reaction_flux_curves"]["VEGSH_rate"]["dense_values"], dtype=float)
    assert np.allclose(flux_values, 0.2)
    assert payload["reaction_flux_curves"]["VEGSH_rate"]["balance_correction"]["param"] == "k_EGSH_deg"


def test_phase_ab_script_writes_phase_a_and_phase_b_teacher_artifacts(tmp_path):
    script = _load_phase_ab_script()
    payload = script.run_phase_ab(
        out_dir=tmp_path,
        dense_points=10,
        skip_calibration=True,
    )

    summary_path = tmp_path / "phase_ab_summary.json"
    assert summary_path.exists()
    result = json.loads(summary_path.read_text(encoding="utf-8"))

    assert payload["phase_a"]["dataset_summary"]["target_count"] == len(EXTRACELLULAR_TEACHER_METABOLITES)
    assert result["phase_b"]["status"] == "skipped"
    assert result["phase_b"]["teacher_dataset_summary"]["reactions"] == ["VEGLC", "VELAC"]
    assert Path(result["phase_a"]["dataset_path"]).exists()
    assert Path(result["phase_b"]["teacher_dataset_path"]).exists()
