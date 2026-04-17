"""Simulation router — runs the ODE simulation and returns JSON-safe results."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import numpy as np

from core.simulation_engine import SimulationEngine

router = APIRouter(prefix="/simulate", tags=["simulation"])


class SimulationDatasetPayload(BaseModel):
    dataset_id: str = Field(..., description="Active dataset identifier")
    source: str = Field(..., description="Dataset source")
    mode: str = Field(..., description="Research data mode")
    label: str = Field(..., description="Dataset label")
    file_name: Optional[str] = Field(None, description="Uploaded file name")
    time_points: List[float] = Field(default_factory=list, description="Dataset time points")
    mapped_metabolites: List[str] = Field(default_factory=list, description="Mapped metabolite identifiers")
    mapped_series_by_metabolite: Dict[str, List[float]] = Field(
        default_factory=dict,
        description="Mapped concentration series keyed by metabolite",
    )


class SimulationRequest(BaseModel):
    t_max: float = Field(42, description="Simulation duration in days")
    curve_fit_strength: float = Field(0.0, description="Curve fitting strength (0 to 1)")
    ic_source: str = Field("JA Final", description="Initial conditions source")
    solver_method: str = Field("RK45", description="ODE solver method")
    rtol: float = Field(1e-6, description="Relative tolerance")
    atol: float = Field(1e-8, description="Absolute tolerance")
    ph_perturbation_type: str = Field("None", description="pH perturbation type")
    ph_severity: str = Field("Moderate", description="pH severity")
    ph_target: float = Field(7.0, description="Target pH")
    ph_duration: float = Field(6.0, description="Duration in hours")
    research_data_mode: str = Field(
        "default_bordbar_mode",
        description="Active research data mode for the current research workflow",
    )
    active_dataset_id: Optional[str] = Field(
        None, description="Active research dataset identifier"
    )
    active_dataset_label: Optional[str] = Field(
        None, description="Active research dataset label"
    )
    active_dataset: Optional[SimulationDatasetPayload] = Field(
        None, description="Active research dataset payload for dataset-aware simulation"
    )
    custom_params: Optional[Dict[str, float]] = Field(
        None, description="Optimized parameter overrides from the latest calibration run"
    )


def _to_serializable(obj):
    """Recursively convert numpy types to Python native types for JSON."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_serializable(i) for i in obj]
    return obj


@router.post("/")
async def run_simulation(request: SimulationRequest):
    try:
        engine = SimulationEngine()

        log_messages: list[str] = []

        def progress_callback(progress, message):
            log_messages.append(f"[{progress:.0%}] {message}")

        results = engine.run_simulation(
            t_max=request.t_max,
            curve_fit_strength=request.curve_fit_strength,
            ic_source=request.ic_source,
            solver_method=request.solver_method,
            rtol=request.rtol,
            atol=request.atol,
            ph_perturbation_type=request.ph_perturbation_type,
            ph_severity=request.ph_severity,
            ph_target=request.ph_target,
            ph_duration=request.ph_duration,
            research_data_mode=request.research_data_mode,
            active_dataset=request.active_dataset.model_dump() if request.active_dataset else None,
            active_dataset_id=request.active_dataset_id,
            active_dataset_label=request.active_dataset_label,
            custom_params=request.custom_params,
            progress_callback=progress_callback,
        )

        if "error" in results:
            raise HTTPException(status_code=500, detail=results["error"])

        # Build a fully JSON-safe payload
        payload = _to_serializable(results)
        payload["log"] = log_messages
        payload["research_data_mode"] = request.research_data_mode
        payload["active_dataset_id"] = request.active_dataset_id
        payload["active_dataset_label"] = request.active_dataset_label
        return payload

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
