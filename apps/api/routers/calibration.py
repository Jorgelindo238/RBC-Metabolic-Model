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
        ..., description="Parameters to optimise: {name: [initial, lower_bound, upper_bound]}"
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
