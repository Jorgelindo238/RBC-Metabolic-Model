"""Integration tests for the calibration adapter + planner/triage hookup.

These tests exercise the seams without actually calling
``MM_calibration.run_calibration`` (which needs an ODE integrator). They
verify that:

* the adapter loads the planner and triage modules exactly the way the live
  FastAPI app will,
* the guarded helpers return structured payloads for representative inputs.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = ROOT / "apps" / "api"
STREAMLIT_APP = ROOT / "streamlit_app"
SRC = ROOT / "src"

# Mirror the FastAPI startup path strategy (see apps/api/main.py).
for entry in (str(APP_ROOT), str(STREAMLIT_APP), str(SRC)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import st_shim  # noqa: E402  (registered by main.py before core imports)
st_shim.install()

from services.mm_calibration_adapter import (  # noqa: E402
    _ROBOCOP_PLANNER_AVAILABLE,
    _build_combined_triage_safely,
    _build_custom_data_plan_safely,
    _build_pure_ode_triage_safely,
    _triage_report_safely,
)


class TestAdapterRobocopWiring:
    def test_planner_and_triage_modules_are_available(self):
        assert _ROBOCOP_PLANNER_AVAILABLE is True

    def test_build_custom_data_plan_returns_expected_shape(self):
        plan_dict, plan_obj = _build_custom_data_plan_safely(
            measured_metabolites=["EGLC", "ELAC", "ATP", "ADP", "AMP"],
            user_selected_params=["vmax_VHK", "vmax_VEGLC"],
            requested_strategy=None,
            profile_additions_candidates=[
                "vmax_VAK", "vmax_VAK_rev", "vmax_VAK2",
                "vmax_VAMPD1", "vmax_VAPRT", "vmax_VADSL",
            ],
        )
        assert plan_dict is not None
        assert plan_obj is not None
        assert plan_obj.target_scope == "glycolysis_extracellular"
        assert plan_obj.recommended_strategy == "vmax_then_km"
        assert set(plan_obj.parameter_additions) == {
            "vmax_VAK", "vmax_VAK_rev", "vmax_VAK2",
        }
        assert set(plan_obj.rejected_parameter_additions.keys()) == {
            "vmax_VAMPD1", "vmax_VAPRT", "vmax_VADSL",
        }
        assert plan_dict["target_scope"] == plan_obj.target_scope
        assert "assessment" in plan_dict

    def test_planner_flags_dangerous_compensators(self):
        plan_dict, _plan_obj = _build_custom_data_plan_safely(
            measured_metabolites=["EGLC", "ATP", "ADP", "AMP"],
            user_selected_params=["vmax_VPEP_PASE"],
            requested_strategy=None,
            profile_additions_candidates=[],
        )
        assert plan_dict is not None
        assert "vmax_VPEP_PASE" in plan_dict["dangerous_compensators_present"]

    def test_triage_returns_discard_when_atp_collapses(self):
        fake_report = {
            "baseline_loss": 1.0,
            "final_loss": 0.5,
            "improvement_pct": 50.0,
            "per_metabolite": [
                {"name": "EGLC", "nrmse": 0.2, "rmse": 0.02, "sim_final": 1.0, "exp_final": 1.0, "norm_factor": 0.1},
                {"name": "ATP", "nrmse": 1.6, "rmse": 0.2, "sim_final": 0.3, "exp_final": 1.0, "norm_factor": 0.1},
                {"name": "ADP", "nrmse": 0.3, "rmse": 0.03, "sim_final": 0.9, "exp_final": 1.0, "norm_factor": 0.1},
                {"name": "AMP", "nrmse": 0.3, "rmse": 0.03, "sim_final": 0.9, "exp_final": 1.0, "norm_factor": 0.1},
            ],
        }
        triage = _triage_report_safely(
            fake_report,
            measured_metabolites=["EGLC", "ATP", "ADP", "AMP"],
            user_selected_params=["vmax_VHK"],
        )
        assert triage is not None
        assert triage["overall"] == "discard"
        assert any("ATP" in trig for trig in triage["discard_triggers"])

    def test_triage_returns_keep_for_all_good_priority_1(self):
        fake_report = {
            "baseline_loss": 1.0,
            "final_loss": 0.4,
            "improvement_pct": 60.0,
            "per_metabolite": [
                {"name": "EGLC", "nrmse": 0.1},
                {"name": "ELAC", "nrmse": 0.1},
                {"name": "GLC", "nrmse": 0.1},
                {"name": "LAC", "nrmse": 0.1},
                {"name": "ATP", "nrmse": 0.1},
                {"name": "ADP", "nrmse": 0.1},
                {"name": "AMP", "nrmse": 0.1},
                {"name": "B23PG", "nrmse": 0.1},
                {"name": "GSH", "nrmse": 0.1},
                {"name": "GSSG", "nrmse": 0.1},
            ],
        }
        triage = _triage_report_safely(
            fake_report,
            measured_metabolites=[
                "EGLC", "ELAC", "GLC", "LAC", "ATP", "ADP", "AMP",
                "B23PG", "GSH", "GSSG",
            ],
            user_selected_params=["vmax_VHK"],
        )
        assert triage is not None
        assert triage["overall"] == "keep"
        assert triage["next_best_experiment"]

    def test_pure_ode_triage_placeholder_is_structured(self):
        pure_ode_triage = _build_pure_ode_triage_safely()

        assert pure_ode_triage is not None
        assert pure_ode_triage["overall"] == "needs_review"
        assert pure_ode_triage["skipped"] is True
        assert "main.py" in pure_ode_triage["reason"]

    def test_combined_triage_is_deferred_until_real_pure_ode_exists(self):
        calibration_triage = {
            "overall": "keep",
            "reason": "Calibration-report triage passed.",
            "discard_triggers": [],
            "caveats": [],
        }
        pure_ode_triage = _build_pure_ode_triage_safely()

        combined = _build_combined_triage_safely(calibration_triage, pure_ode_triage)

        assert combined is None

    def test_combined_triage_runs_when_real_pure_ode_verdict_is_present(self):
        calibration_triage = {
            "overall": "keep",
            "reason": "Calibration-report triage passed.",
            "discard_triggers": [],
            "caveats": [],
        }
        pure_ode_triage = {
            "overall": "healthy",
            "reason": "Pure ODE stayed healthy.",
            "collapse_signals": [],
            "concern_signals": [],
            "caveats": [],
            "skipped": False,
        }

        combined = _build_combined_triage_safely(calibration_triage, pure_ode_triage)

        assert combined is not None
        assert combined["overall"] == "keep"
