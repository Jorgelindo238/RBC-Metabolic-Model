"""Data router — upload, preprocess, map metabolites, and load reference data."""

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
import io
from pathlib import Path

from core.metabolite_mapper import MetaboliteMapper
from core.data_preprocessor import DataPreprocessor
from core.reaction_info_complete import REACTION_INFO_COMPLETE
from core.flux_estimator import FluxEstimator, compare_fluxes

router = APIRouter(prefix="/data", tags=["data"])

# Project root for locating data files
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SRC = _PROJECT_ROOT / "src"


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


# ── Reference Data ───────────────────────────────────────────────────────────

@router.get("/experimental")
async def get_experimental_data():
    """Load the built-in Bordbar et al. experimental dataset."""
    try:
        data_path = _SRC / "Data_Bordbar_et_al_exp.xlsx"
        df = pd.read_excel(data_path, engine="openpyxl")

        metabolite_names = df.iloc[:, 0].tolist()
        time_points = [float(c) for c in df.columns[1:]]
        values = df.iloc[:, 1:].values  # (n_metabolites, n_timepoints)

        return _to_native({
            "metabolites": metabolite_names,
            "time_points": time_points,
            "values": values,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/initial-conditions")
async def get_initial_conditions():
    """Load default initial conditions (JA Final)."""
    try:
        from equadiff_brodbar import BRODBAR_METABOLITE_MAP, NUM_BASE_METABOLITES
        from parse_initial_conditions import parse_initial_conditions

        n_with_phi = NUM_BASE_METABOLITES + 1
        metabolite_list = [''] * n_with_phi
        for name, idx in BRODBAR_METABOLITE_MAP.items():
            if idx < n_with_phi:
                metabolite_list[idx] = name
        model = {'metab': metabolite_list}

        ic_file = _SRC / "Initial_conditions_JA_Final.xls"
        x0, _ = parse_initial_conditions(model, str(ic_file))

        ic_dict = {}
        for i, val in enumerate(x0):
            if i < len(metabolite_list) and metabolite_list[i]:
                ic_dict[metabolite_list[i]] = float(val)

        return ic_dict
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Reaction Info ────────────────────────────────────────────────────────────

@router.get("/reactions")
async def get_reaction_info():
    """Return the complete reaction info dictionary."""
    return REACTION_INFO_COMPLETE


# ── Data Upload & Processing ─────────────────────────────────────────────────

@router.post("/upload")
async def upload_data(file: UploadFile = File(...)):
    """Upload a CSV or Excel file and return parsed + preprocessed data."""
    try:
        print("[data.upload] request received", flush=True)
        contents = await file.read()
        print(f"[data.upload] read {len(contents)} bytes from {file.filename}", flush=True)
        filename = file.filename or "upload"

        if filename.endswith(".csv"):
            print("[data.upload] parsing CSV", flush=True)
            df = pd.read_csv(io.BytesIO(contents))
        elif filename.endswith((".xls", ".xlsx")):
            print("[data.upload] parsing Excel", flush=True)
            df = pd.read_excel(io.BytesIO(contents))
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format. Use CSV or Excel.")

        preprocessor = DataPreprocessor()
        print("[data.upload] detecting format", flush=True)
        fmt = preprocessor.detect_format(df)

        if fmt.get("needs_transpose", False):
            print("[data.upload] transposing input", flush=True)
            df = preprocessor.transpose_data(df)

        columns = df.columns.tolist()
        n_rows = len(df)
        preview = df.head(10).to_dict(orient="records")
        time_points = df.iloc[:, 0].tolist()
        metabolites = [str(col) for col in columns[1:]]
        values = df.loc[:, metabolites].to_numpy().T

        return _to_native({
            "filename": filename,
            "columns": columns,
            "n_rows": n_rows,
            "format_detected": fmt,
            "preview": preview,
            "time_points": time_points,
            "metabolites": metabolites,
            "values": values,
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class MapColumnsRequest(BaseModel):
    columns: List[str] = Field(..., description="Column names from the uploaded file")


@router.post("/map-metabolites")
async def map_metabolite_columns(request: MapColumnsRequest):
    """Auto-map column names to known RBC metabolite identifiers."""
    try:
        mapper = MetaboliteMapper()
        mappings = {}
        unmapped = []

        for col, match in mapper.map_dataframe_columns(request.columns).items():
            if match.get("method") == "time_column":
                continue

            if match.get("matched") and match.get("metabolite"):
                mappings[col] = {
                    "metabolite": match["metabolite"],
                    "confidence": float(match.get("confidence", 0.0)),
                }
            else:
                unmapped.append(col)

        return {"mappings": mappings, "unmapped": unmapped}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Flux Comparison ──────────────────────────────────────────────────────────

class FluxComparisonRequest(BaseModel):
    simulated_flux: Dict[str, object] = Field(
        ..., description="Flux data from simulation {times: [...], fluxes: {rxn: [...]}}"
    )
    experimental_flux: Dict[str, object] = Field(
        ..., description="Flux data from experimental concentrations"
    )


@router.post("/compare-fluxes")
async def compare_flux_data(request: FluxComparisonRequest):
    """Compare simulated vs experimental-derived fluxes."""
    try:
        df = compare_fluxes(request.simulated_flux, request.experimental_flux)
        return _to_native({"comparison": df.to_dict(orient="records")})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Simulation CSV export ────────────────────────────────────────────────────

class ExportRequest(BaseModel):
    t: List[float]
    x: List[List[float]]
    metabolite_names: List[str]


@router.post("/export-csv")
async def export_simulation_csv(request: ExportRequest):
    """Convert simulation results into a CSV string."""
    try:
        header = "Time," + ",".join(request.metabolite_names) + "\n"
        rows = []
        for i, t in enumerate(request.t):
            row = [str(t)] + [str(request.x[i][j]) for j in range(len(request.metabolite_names))]
            rows.append(",".join(row))
        csv_str = header + "\n".join(rows)
        return {"csv": csv_str}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
