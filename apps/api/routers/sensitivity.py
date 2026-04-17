"""Sensitivity analysis router — compare simulation fit against experimental datasets."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import numpy as np

from core.simulation_engine import SimulationEngine
from core.sensitivity_engine import SensitivityAnalyzer

router = APIRouter(prefix="/sensitivity", tags=["sensitivity"])


def _to_native(obj):
    """Recursively convert numpy types to Python native types."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_native(i) for i in obj]
    return obj


class SensitivityRequest(BaseModel):
    custom_time: List[float] = Field(..., description="Time points of the custom dataset")
    custom_metabolites: List[str] = Field(..., description="Metabolite names in custom dataset")
    custom_values: List[List[float]] = Field(
        ..., description="Values matrix (n_metabolites × n_timepoints)"
    )
    t_max: float = Field(42, description="Simulation duration (days)")
    solver_method: str = Field("RK45", description="ODE solver")


@router.post("/compare")
async def run_sensitivity_comparison(request: SensitivityRequest):
    """Run simulation and compare against both Bordbar and custom datasets."""
    try:
        engine = SimulationEngine()
        results = engine.run_simulation(
            t_max=request.t_max,
            solver_method=request.solver_method,
            progress_callback=lambda p, m: None,
        )

        if "error" in results:
            raise HTTPException(status_code=500, detail=results["error"])

        # Attach custom validation data
        custom_results = dict(results)
        custom_results["custom_validation_data"] = {
            "time": np.array(request.custom_time),
            "metabolites": request.custom_metabolites,
            "values": np.array(request.custom_values),
        }

        analyzer = SensitivityAnalyzer(results, custom_results)

        metabolite_comparison = analyzer.compare_metabolite_concentrations()
        top_sensitive = analyzer.get_top_sensitive_metabolites(n=15)
        validation_metrics = analyzer.calculate_validation_metrics()

        return _to_native({
            "metabolite_comparison": metabolite_comparison.to_dict(orient="records") if not metabolite_comparison.empty else [],
            "top_sensitive_metabolites": [{"name": n, "pct_change": p} for n, p in top_sensitive],
            "validation_metrics": validation_metrics,
            "simulation_summary": {
                "success": results.get("success", False),
                "n_metabolites": results.get("n_metabolites", 0),
                "duration": results.get("duration", 0),
            },
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
