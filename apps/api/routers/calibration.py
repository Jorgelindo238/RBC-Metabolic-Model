"""Parameter calibration router — optimise enzyme parameters against experimental data."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import traceback

from services.mm_calibration_adapter import get_web_calibration_taxonomy, run_web_calibration

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
    try:
        return run_web_calibration(request)

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/available-parameters")
async def get_available_parameters():
    """Return the canonical calibration taxonomy for the web UI."""
    try:
        return get_web_calibration_taxonomy()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
