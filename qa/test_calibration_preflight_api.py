"""Calibration router: data-contract gate and legacy notice. No solver runs.

The calibration core is replaced by a stub. Written on 2026-11-12 and NOT
executed by their author.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for path in (PROJECT_ROOT, PROJECT_ROOT / "apps" / "api", PROJECT_ROOT / "streamlit_app", PROJECT_ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from fastapi import HTTPException  # noqa: E402

from apps.api.routers import calibration as router_module  # noqa: E402
from apps.api.routers.calibration import CalibrationRequest, PreflightRequest  # noqa: E402

SCHEMA_VERSION = "airbc.user_calibration_data/1"


def data_contract():
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset": {"dataset_id": "lab-a-2026-01", "cohort_id": "lab-a", "subject": {"kind": "donor", "id": "donor-07"}},
        "time": {"unit": "day", "origin": {"kind": "collection", "description": "day 0 is collection"}, "points": [1.0, 4.0, 8.0]},
        "geometry": {"hematocrit": 0.6, "provenance": {"kind": "measured_this_dataset", "source": "unit record"}},
        "initial_state": {"policy": "user_measured_at_first_time", "time": 1.0, "unmeasured_pools_policy": "declared_latent_contract"},
        "channels": [{"name": "ATP", "compartment": "intracellular", "kind": "absolute", "unit": "mM", "values": [1.0, 1.1, 1.2]}],
    }


def make_request(**overrides):
    base = dict(target_metabolites=["ATP"], exp_time=[1.0, 4.0, 8.0], exp_data={"ATP": [1.0, 1.1, 1.2]},
                params_to_optimize={"vmax_VHK": [1.0, 0.1, 5.0]}, max_iterations=1, t_max=2)
    base.update(overrides)
    return CalibrationRequest(**base)


def forbid_core(monkeypatch):
    def forbidden(request):
        pytest.fail("a blocked request must never reach the calibration adapter")

    monkeypatch.setattr(router_module, "run_web_calibration", forbidden)


def test_preflight_endpoint_reports_without_running_anything(monkeypatch):
    forbid_core(monkeypatch)
    report = asyncio.run(router_module.preflight_user_data(PreflightRequest(data_contract=data_contract())))
    assert report["schema_version"] == SCHEMA_VERSION and report["data_valid"] is True
    assert report["engine_compatibility"]["compatible"] is False and report["launch_allowed"] is False


def test_run_with_an_invalid_data_contract_is_refused_with_400_and_the_report(monkeypatch):
    forbid_core(monkeypatch)
    broken = data_contract(); broken["time"]["points"] = [1.0, 1.0, 8.0]
    with pytest.raises(HTTPException) as error:
        asyncio.run(router_module.run_calibration(make_request(data_contract=broken)))
    assert error.value.status_code == 400
    assert error.value.detail["reason"] == "data_contract_invalid"
    assert "time_points_not_increasing" in [issue["code"] for issue in error.value.detail["preflight"]["errors"]]


def test_run_with_a_valid_data_contract_is_blocked_with_409_while_the_engine_is_incompatible(monkeypatch):
    forbid_core(monkeypatch)
    with pytest.raises(HTTPException) as error:
        asyncio.run(router_module.run_calibration(make_request(data_contract=data_contract())))
    assert error.value.status_code == 409
    assert error.value.detail["reason"] == "engine_not_compatible_with_data_contract"
    report = error.value.detail["preflight"]
    assert report["data_valid"] is True and report["launch_allowed"] is False
    assert "engine_initial_state_ignores_user_data" in [issue["code"] for issue in report["engine_compatibility"]["blocking"]]


def test_run_without_a_data_contract_keeps_the_legacy_path_and_states_its_limits(monkeypatch):
    seen = []

    def fake_core(request):
        seen.append(request)
        return {"success": True, "final_loss": 1.0}

    monkeypatch.setattr(router_module, "run_web_calibration", fake_core)
    request = make_request()
    result = asyncio.run(router_module.run_calibration(request))
    assert seen == [request] and result["success"] is True and result["final_loss"] == 1.0
    assert result["data_contract"]["status"] == "legacy_no_data_contract"
    assert result["data_contract"]["schema_version"] is None and result["data_contract"]["limits"]


def test_legacy_notice_does_not_overwrite_a_field_the_core_already_set(monkeypatch):
    monkeypatch.setattr(router_module, "run_web_calibration", lambda request: {"success": True, "data_contract": {"status": "from_core"}})
    result = asyncio.run(router_module.run_calibration(make_request()))
    assert result["data_contract"] == {"status": "from_core"}


def test_request_model_exposes_both_contract_fields_with_safe_defaults():
    request = make_request()
    assert request.data_contract is None and request.parameter_contract is None
