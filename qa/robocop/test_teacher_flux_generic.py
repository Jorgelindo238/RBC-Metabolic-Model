from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api.services.teacher_flux_generic import (
    build_teacher_flux_dataset_from_request,
    infer_teacher_flux_targets,
    run_teacher_flux_rescue,
)


def _make_request():
    return SimpleNamespace(
        target_metabolites=["EGLC", "ELAC", "ATP"],
        exp_time=[1.0, 7.0, 14.0, 21.0],
        exp_data={
            "EGLC": [5.0, 4.0, 3.0, 2.0],
            "ELAC": [1.0, 1.4, 1.8, 2.2],
            "ATP": [1.2, 1.1, 1.0, 0.95],
        },
        t_max=21.0,
        solver_method="RK45",
        research_data_mode="custom_user_data_mode",
        active_dataset_id="custom-dataset",
        active_dataset_label="Custom dataset",
    )


def test_infer_teacher_flux_targets_filters_supported_reactions():
    assert infer_teacher_flux_targets(["ATP", "EGLC", "ELAC", "UNKNOWN"]) == ["EGLC", "ELAC"]


def test_build_teacher_flux_dataset_from_request_writes_contract(tmp_path):
    dataset_path = tmp_path / "teacher_flux_dataset.json"
    payload = build_teacher_flux_dataset_from_request(
        _make_request(),
        metabolite_names=["EGLC", "ELAC"],
        out_path=dataset_path,
    )

    assert dataset_path.exists()
    assert payload["contract_type"] == "teacher_flux_dataset"
    assert sorted(payload["reaction_flux_curves"].keys()) == ["VEGLC", "VELAC"]


def test_teacher_flux_rescue_skips_when_panel_has_no_supported_targets(tmp_path):
    request = SimpleNamespace(
        target_metabolites=["ATP", "ADP"],
        exp_time=[1.0, 7.0],
        exp_data={"ATP": [1.0, 0.9], "ADP": [0.4, 0.5]},
    )
    result = run_teacher_flux_rescue(
        request=request,
        params={"vmax_VHK": 1.0},
        output_dir=tmp_path / "teacher_flux",
    )

    assert result["status"] == "skipped"
    assert "No supported teacher-flux targets" in result["reason"]
