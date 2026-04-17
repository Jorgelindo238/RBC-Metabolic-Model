"""Unit tests for services.robocop.custom_dataset_planner."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.robocop.custom_dataset_planner import (  # noqa: E402
    ENERGY_ANCHORS,
    PRIORITY_1_METABOLITES,
    PRIORITY_2_METABOLITES,
    PRIORITY_3_METABOLITES,
    PRIORITY_4_METABOLITES,
    assess_custom_dataset,
    build_custom_data_plan,
)


class TestAssessCustomDataset:
    def test_empty_input_returns_empty_profile(self):
        assessment = assess_custom_dataset(None)
        assert assessment.measured == []
        assert assessment.profile_signal == "empty"
        assert assessment.priority_1_coverage == 0.0
        assert assessment.warnings, "expected a warning about empty dataset"

    def test_full_priority_1_coverage(self):
        assessment = assess_custom_dataset(sorted(PRIORITY_1_METABOLITES))
        assert set(assessment.priority_1_measured) == PRIORITY_1_METABOLITES
        assert assessment.priority_1_coverage == 1.0
        assert assessment.energy_core_present is True
        assert assessment.extracellular_present is True
        assert assessment.anchors_present["energy"] is True
        assert assessment.anchors_present["glucose_commitment"] is True
        assert assessment.anchors_present["lactate_outlet"] is True
        assert assessment.anchors_present["redox"] is True
        assert assessment.profile_signal == "priority1_extracellular_anchor"

    def test_energy_only_dataset(self):
        assessment = assess_custom_dataset(["ATP", "ADP", "AMP"])
        assert assessment.priority_1_measured == ["ADP", "AMP", "ATP"]
        assert assessment.energy_core_present is True
        assert assessment.extracellular_present is False
        assert assessment.profile_signal == "priority1_energy_anchor"

    def test_purine_only_warns_about_missing_anchors(self):
        assessment = assess_custom_dataset(["IMP", "HYPX", "XAN"])
        assert assessment.priority_3_measured == ["HYPX", "IMP", "XAN"]
        assert assessment.energy_core_present is False
        assert any("energy anchors" in w.lower() for w in assessment.warnings)

    def test_unknown_metabolites_reported(self):
        assessment = assess_custom_dataset(["ATP", "FAKE", "FOO"])
        assert assessment.unknown_metabolites == ["FAKE", "FOO"]
        assert any("not recognised" in w for w in assessment.warnings)

    def test_priority_4_only_triggers_warning(self):
        assessment = assess_custom_dataset(["GLU", "SER", "MAL"])
        assert assessment.profile_signal == "side_only"
        assert any("Priority 4" in w for w in assessment.warnings)


class TestStrategyRecommendation:
    def test_extracellular_plus_energy_prefers_glycolysis_extracellular(self):
        plan = build_custom_data_plan(
            measured_metabolites=["EGLC", "ELAC", "ATP", "ADP", "AMP"],
            selected_params=[],
        )
        assert plan.target_scope == "glycolysis_extracellular"
        assert plan.recommended_strategy == "vmax_then_km"
        assert plan.atp_focus is True

    def test_energy_only_uses_core_glycolysis_energy(self):
        plan = build_custom_data_plan(
            measured_metabolites=["ATP", "ADP", "AMP"],
            selected_params=[],
        )
        assert plan.target_scope == "core_glycolysis_energy"
        assert plan.atp_focus is True
        assert plan.recommended_strategy == "vmax_then_km"

    def test_purine_only_uses_core_km_then_purine_transport(self):
        plan = build_custom_data_plan(
            measured_metabolites=["IMP", "HYPX", "URT"],
            selected_params=[],
        )
        assert plan.target_scope == "core_glycolysis_energy"
        assert plan.recommended_strategy == "core_km_then_purine_transport"
        assert plan.atp_focus is False

    def test_glycolysis_only_uses_glycolysis_scope(self):
        plan = build_custom_data_plan(
            measured_metabolites=["G6P", "F6P", "PEP", "PYR"],
            selected_params=[],
        )
        assert plan.target_scope == "glycolysis"
        assert plan.recommended_strategy == "vmax_then_km"

    def test_user_requested_strategy_is_honoured_when_valid(self):
        plan = build_custom_data_plan(
            measured_metabolites=["EGLC", "ATP", "ADP", "AMP"],
            selected_params=[],
            requested_strategy="joint_vmax_km",
        )
        assert plan.recommended_strategy == "joint_vmax_km"
        assert plan.target_scope == "glycolysis_extracellular"

    def test_invalid_user_strategy_falls_back_and_notes(self):
        plan = build_custom_data_plan(
            measured_metabolites=["EGLC", "ATP", "ADP", "AMP"],
            selected_params=[],
            requested_strategy="nonsense_strategy",
        )
        assert plan.recommended_strategy == "vmax_then_km"
        assert any("not a supported" in note for note in plan.notes)

    def test_fallback_when_nothing_recognised(self):
        plan = build_custom_data_plan(
            measured_metabolites=["FAKE", "NONSENSE"],
            selected_params=[],
        )
        assert plan.target_scope == "all"
        assert plan.recommended_strategy == "vmax_then_km"


class TestParameterGating:
    def test_purine_additions_dropped_without_purine_data(self):
        plan = build_custom_data_plan(
            measured_metabolites=["EGLC", "ATP", "ADP", "AMP"],
            selected_params=[],
        )
        assert "vmax_VAMPD1" in plan.rejected_parameter_additions
        assert "vmax_VAPRT" in plan.rejected_parameter_additions
        assert "vmax_VADSL" in plan.rejected_parameter_additions
        assert "vmax_VAMPD1" not in plan.parameter_additions
        assert "vmax_VAK" in plan.parameter_additions
        assert "vmax_VAK_rev" in plan.parameter_additions
        assert "vmax_VAK2" in plan.parameter_additions

    def test_purine_additions_kept_when_purine_measured(self):
        plan = build_custom_data_plan(
            measured_metabolites=["EGLC", "ATP", "ADP", "AMP", "IMP", "HYPX"],
            selected_params=[],
        )
        assert plan.rejected_parameter_additions == {}
        assert set(plan.parameter_additions) == {
            "vmax_VAK", "vmax_VAK_rev", "vmax_VAK2",
            "vmax_VAMPD1", "vmax_VAPRT", "vmax_VADSL",
        }

    def test_adenylate_additions_dropped_without_energy_data(self):
        plan = build_custom_data_plan(
            measured_metabolites=["EGLC", "ELAC", "LAC"],
            selected_params=[],
        )
        # Without any ATP/ADP/AMP, the adenylate interconversion terms add
        # nothing but noise.
        assert "vmax_VAK" in plan.rejected_parameter_additions
        assert "vmax_VAK_rev" in plan.rejected_parameter_additions
        assert "vmax_VAK2" in plan.rejected_parameter_additions
        assert not any(name.startswith("vmax_VA") for name in plan.parameter_additions)


class TestDangerousCompensators:
    def test_pep_pase_flagged(self):
        plan = build_custom_data_plan(
            measured_metabolites=["EGLC", "ATP", "ADP", "AMP"],
            selected_params=["vmax_VPEP_PASE", "vmax_VPK"],
        )
        assert "vmax_VPEP_PASE" in plan.dangerous_compensators_present
        assert "vmax_VPEP_PASE" in plan.dangerous_compensators_guarded
        assert "vmax_VPK" not in plan.dangerous_compensators_present

    def test_secondary_exports_flagged(self):
        plan = build_custom_data_plan(
            measured_metabolites=["EGLC", "ATP", "ADP", "AMP"],
            selected_params=["vmax_VEXAN", "vmax_VEURT", "vmax_VEINO"],
        )
        assert {
            "vmax_VEXAN", "vmax_VEURT", "vmax_VEINO",
        }.issubset(plan.dangerous_compensators_present.keys())

    def test_non_dangerous_params_not_flagged(self):
        plan = build_custom_data_plan(
            measured_metabolites=["EGLC", "ATP", "ADP", "AMP"],
            selected_params=["vmax_VHK", "km_VHK_GLC"],
        )
        assert plan.dangerous_compensators_present == {}


class TestWeightEmphasis:
    def test_weight_emphasis_mirrors_target_scope(self):
        plan = build_custom_data_plan(
            measured_metabolites=["EGLC", "ELAC", "ATP", "ADP", "AMP"],
            selected_params=[],
        )
        weights = plan.weight_emphasis
        assert weights.get("EGLC") == 14.0
        assert weights.get("ELAC") == 9.0
        assert weights.get("ATP") == 45.0
        assert weights.get("ADP") == 45.0
        assert weights.get("AMP") == 24.0

    def test_weight_emphasis_only_reports_measured(self):
        plan = build_custom_data_plan(
            measured_metabolites=["ATP", "ADP"],
            selected_params=[],
        )
        assert set(plan.weight_emphasis.keys()) == {"ATP", "ADP"}


class TestStageOutline:
    def test_stage_outline_mirrors_priority_coverage(self):
        plan = build_custom_data_plan(
            measured_metabolites=["EGLC", "ELAC", "ATP", "ADP", "AMP", "G6P", "IMP"],
            selected_params=[],
        )
        stage_names = [stage.name for stage in plan.stage_outline]
        assert "anchor_priority_1" in stage_names
        assert "glycolysis_priority_2" in stage_names
        assert "purine_priority_3" in stage_names

    def test_fallback_stage_when_nothing_recognised(self):
        plan = build_custom_data_plan(
            measured_metabolites=["FAKE"],
            selected_params=[],
        )
        stage_names = [stage.name for stage in plan.stage_outline]
        assert stage_names == ["fallback_broad"]


class TestSerialisation:
    def test_plan_to_dict_round_trip(self):
        plan = build_custom_data_plan(
            measured_metabolites=["EGLC", "ATP", "ADP", "AMP"],
            selected_params=["vmax_VHK"],
        )
        payload = plan.to_dict()
        assert set(payload.keys()) >= {
            "assessment",
            "recommended_strategy",
            "target_scope",
            "atp_focus",
            "parameter_additions",
            "rejected_parameter_additions",
            "dangerous_compensators_present",
            "dangerous_compensators_guarded",
            "weight_emphasis",
            "stage_outline",
            "notes",
            "rationale",
        }
        assert isinstance(payload["assessment"], dict)
        assert isinstance(payload["stage_outline"], list)
        assert all(isinstance(stage, dict) for stage in payload["stage_outline"])
