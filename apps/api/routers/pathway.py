"""Pathway visualization router — returns the canonical RBC pathway graph for the frontend."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional

from core.pathway_registry import build_pathway_network_payload

router = APIRouter(prefix="/pathway", tags=["pathway"])


@router.get("/network")
async def get_network():
    """Return the canonical RBC metabolic network as nodes + edges for frontend rendering."""
    try:
        return build_pathway_network_payload()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class PathwayStateRequest(BaseModel):
    concentrations: Dict[str, float] = Field(
        ..., description="Current metabolite concentrations {name: mM}"
    )
    fluxes: Optional[Dict[str, float]] = Field(
        None, description="Current reaction fluxes {rxn: mM/day}"
    )


@router.post("/network-state")
async def get_network_with_state(request: PathwayStateRequest):
    """Return the canonical network with node sizes/colors driven by live concentrations."""
    try:
        return build_pathway_network_payload(request.concentrations, request.fluxes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
