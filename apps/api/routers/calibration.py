"""Parameter calibration router — optimise enzyme parameters against experimental data."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
import traceback

from services.mm_calibration_adapter import get_web_calibration_taxonomy, run_web_calibration
from services.user_data_contract import legacy_path_notice, preflight
from services.reference_profiles import check_profile_id, list_profiles, load_profile

router = APIRouter(prefix="/calibration", tags=["calibration"])


class CalibrationRequest(BaseModel):
    target_metabolites: List[str] = Field(
        ..., description="Metabolite names to calibrate against"
    )
    exp_time: List[float] = Field(..., description="Experimental time points")
    exp_data: Dict[str, List[float]] = Field(
        ..., description="Experimental data {metabolite: [values]}"
    )
    params_to_optimize: Dict[str, List[float]] = Field(
        default_factory=dict,
        description=(
            "Parameters to optimise: {name: [initial, lower_bound, upper_bound]}. "
            "May be empty when auto_param_scope is enabled (default behaviour for "
            "custom data uploads): the worker derives a stoichiometric reachability "
            "scope and seeds bounds from PHASE_MAP automatically."
        ),
    )
    auto_param_scope: Optional[bool] = Field(
        None,
        description=(
            "Phase 0 auto-calibrate-all toggle. Tri-state: None (default) = "
            "auto-detect (enabled when params_to_optimize is empty AND custom "
            "experimental data is provided); True = force-on (always derive "
            "scope from uploaded metabolites' stoichiometric neighbourhood); "
            "False = force-off (preserve legacy strict behaviour where "
            "params_to_optimize must be supplied by the caller). Overridable "
            "by the AIRBC_DISABLE_AUTO_PARAM_SCOPE environment variable on the "
            "worker."
        ),
    )
    base_params: Optional[Dict[str, float]] = Field(
        None, description="Base simulation parameters (all vmax/km values)"
    )
    optimization_strategy: Optional[str] = Field(
        None, description="Canonical optimization strategy family"
    )
    method: Optional[str] = Field(
        None, description="Legacy compatibility alias for optimization_strategy"
    )
    parameter_contract: Optional[str] = Field(
        None,
        description=(
            "Parameter contract. 'vmax_only_fixed_km' optimises Vmax parameters only: every Km, "
            "regulation and hybrid parameter stays fixed, strategy memory, teacher rescue and "
            "Km-opening auto-scope or profile additions are disabled, and a conflicting "
            "optimization_strategy or method is refused with a 400. None or "
            "'legacy_unconstrained' keeps the historical behaviour, which may optimise Km and "
            "regulation parameters. Naming 'vmax_only' in optimization_strategy or method also "
            "selects the fixed-Km contract."
        ),
    )
    data_contract: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Versioned user-data contract (airbc.user_calibration_data/1): dataset, cohort and donor "
            "or declared group, time origin, hematocrit with provenance, initial-state contract and "
            "per-channel compartment, unit and absolute/relative kind. When present the request is "
            "checked by the preflight and is refused unless the data are valid AND the engine can "
            "honour the declaration; the current engine cannot, so this path is blocked. When absent "
            "the historical path runs and its limits are returned under data_contract."
        ),
    )
    max_iterations: int = Field(200, description="Max iterations")
    t_max: float = Field(42, description="Simulation duration (days)")
    solver_method: str = Field("RK45", description="ODE solver")
    research_data_mode: Optional[str] = Field(
        "default_bordbar_mode",
        description="Active research data mode: default Bordbar/reference or custom user data",
    )
    active_dataset_id: Optional[str] = Field(
        None, description="Active research dataset identifier"
    )
    active_dataset_label: Optional[str] = Field(
        None, description="Active research dataset label"
    )
    rerun_pure_ode: bool = Field(
        False,
        description="Whether to replay the calibrated candidate through the pure ODE and score combined triage.",
    )
    orchestration_mode: Optional[str] = Field(
        "single_run",
        description="single_run or strategy_race; worker uses this to select the execution path.",
    )
    enable_strategy_memory: bool = Field(
        True,
        description="Whether orchestration can reuse prior winning strategies for similar datasets.",
    )
    enable_teacher_flux_rescue: bool = Field(
        False,
        description="Whether orchestration may launch a generic teacher-flux rescue pass for supported reactions.",
    )
    strategy_race_budget: Optional[int] = Field(
        None,
        description="Optional cap on how many strategy candidates the worker should race for this dataset.",
    )


@router.post("/run")
async def run_calibration(request: CalibrationRequest):
    """Run parameter calibration against experimental data."""
    if request.data_contract is not None:
        # Contractual path: data validity and engine compatibility are two
        # separate answers, and both must hold before anything is launched.
        report = preflight(request.data_contract)
        if not report["data_valid"]:
            raise HTTPException(status_code=400, detail={"reason": "data_contract_invalid", "preflight": report})
        if not report["launch_allowed"]:
            raise HTTPException(status_code=409, detail={"reason": "engine_not_compatible_with_data_contract", "preflight": report})
    try:
        result = run_web_calibration(request)
        if isinstance(result, dict) and request.data_contract is None:
            result.setdefault("data_contract", legacy_path_notice())
        return result

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


class PreflightRequest(BaseModel):
    data_contract: Dict[str, Any] = Field(..., description="User-data contract to check; nothing is run.")


@router.post("/preflight")
async def preflight_user_data(request: PreflightRequest):
    """Check a user dataset against the versioned contract. Runs no solver and no calibration."""
    return preflight(request.data_contract)


@router.get("/reference-profiles")
async def get_reference_profiles():
    """Allowlisted, read-only reference profiles with their real availability state."""
    return list_profiles()


@router.get("/reference-profiles/{profile_id}")
async def get_reference_profile(profile_id: str):
    """One verified reference profile, or an explicit unavailable state. Never activatable."""
    if not check_profile_id(profile_id):
        raise HTTPException(status_code=404, detail={"reason": "unknown_profile"})
    return load_profile(profile_id)


@router.get("/available-parameters")
async def get_available_parameters():
    """Return the canonical calibration taxonomy for the web UI."""
    try:
        return get_web_calibration_taxonomy()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
