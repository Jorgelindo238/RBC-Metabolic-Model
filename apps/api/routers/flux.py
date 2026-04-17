"""Flux analysis router — estimates metabolic fluxes from simulation results."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import numpy as np

from core.flux_estimator import FluxEstimator, KINETIC_PARAMS

router = APIRouter(prefix="/flux", tags=["flux"])


class FluxRequest(BaseModel):
    concentrations: Dict[str, float] = Field(
        ..., description="Metabolite concentrations {name: mM}"
    )
    custom_params: Optional[Dict] = Field(
        None, description="Custom kinetic parameters to override defaults"
    )


class FluxTimeseriesRequest(BaseModel):
    metabolite_names: List[str] = Field(..., description="Ordered metabolite names")
    concentration_matrix: List[List[float]] = Field(
        ..., description="Matrix of shape (n_timepoints, n_metabolites)"
    )
    time_points: List[float] = Field(..., description="Time values for each row")
    custom_params: Optional[Dict] = None


@router.get("/kinetic-params")
async def get_kinetic_params():
    """Return the default kinetic parameters used for flux estimation."""
    return KINETIC_PARAMS


@router.post("/estimate")
async def estimate_fluxes(request: FluxRequest):
    """Estimate all reaction fluxes for a single set of concentrations."""
    try:
        estimator = FluxEstimator(custom_params=request.custom_params)
        fluxes = estimator.estimate_all_fluxes(request.concentrations)
        return {"fluxes": fluxes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/timeseries")
async def estimate_flux_timeseries(request: FluxTimeseriesRequest):
    """Estimate fluxes over a time series of concentration snapshots."""
    try:
        estimator = FluxEstimator(custom_params=request.custom_params)
        names = request.metabolite_names
        matrix = np.array(request.concentration_matrix)

        all_fluxes: Dict[str, List[float]] = {}
        for row in matrix:
            conc_dict = {name: float(val) for name, val in zip(names, row)}
            snapshot = estimator.estimate_all_fluxes(conc_dict)
            for rxn, val in snapshot.items():
                all_fluxes.setdefault(rxn, []).append(val)

        return {
            "time": request.time_points,
            "fluxes": all_fluxes,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
