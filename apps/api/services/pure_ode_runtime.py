"""Pure-ODE rerun helpers for web/worker calibration flows.

This module reuses the existing Streamlit simulation engine to run an
in-process "main.py-equivalent" ODE replay for a calibrated parameter set.
It writes isolated CSV artifacts so downstream tools can reuse the same
outputs that Hermes Phase B and teacher-flux distillation understand.
"""

from __future__ import annotations

import csv
from pathlib import Path
import sys
from typing import Any, Dict, Iterable

_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parents[3]
_STREAMLIT_APP = _PROJECT_ROOT / "streamlit_app"
_SRC = _PROJECT_ROOT / "src"

for _path in (_STREAMLIT_APP, _SRC):
    _path_str = str(_path)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)

import st_shim
st_shim.install()

from core.simulation_engine import SimulationEngine


def _normalize_metabolite_name(name: Any) -> str:
    return str(name).strip().upper()


def build_active_dataset_from_request(request: Any) -> dict[str, Any] | None:
    """Translate a calibration request into the dataset shape the simulation engine expects."""

    exp_data = getattr(request, "exp_data", None) or {}
    exp_time = getattr(request, "exp_time", None) or []
    if not exp_data or not exp_time:
        return None

    mapped_series_by_metabolite = {
        _normalize_metabolite_name(name): [float(value) for value in values]
        for name, values in exp_data.items()
        if values
    }
    mapped_metabolites = list(mapped_series_by_metabolite.keys())
    if not mapped_metabolites:
        return None

    return {
        "mapped_series_by_metabolite": mapped_series_by_metabolite,
        "mapped_metabolites": mapped_metabolites,
        "time_points": [float(value) for value in exp_time],
    }


def _write_all_metabolites_csv(result: dict[str, Any], csv_path: Path) -> None:
    metabolite_names = [str(name) for name in result.get("metabolite_names") or []]
    timepoints = [float(value) for value in result.get("t") or []]
    trajectories = result.get("x") or []

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Time", *metabolite_names])
        for index, timepoint in enumerate(timepoints):
            row = trajectories[index] if index < len(trajectories) else []
            writer.writerow([timepoint, *[float(value) for value in row]])


def _write_reaction_fluxes_csv(result: dict[str, Any], csv_path: Path) -> None:
    flux_data = result.get("flux_data") or {}
    times = [float(value) for value in flux_data.get("times") or []]
    fluxes = flux_data.get("fluxes") or {}
    reaction_names = sorted(str(name) for name in fluxes.keys())

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time", *reaction_names])
        for index, timepoint in enumerate(times):
            writer.writerow(
                [
                    timepoint,
                    *[
                        float((fluxes.get(reaction_name) or [0.0])[index])
                        if index < len(fluxes.get(reaction_name) or [])
                        else 0.0
                        for reaction_name in reaction_names
                    ],
                ]
            )


def write_simulation_artifacts(result: dict[str, Any], output_dir: Path) -> dict[str, str | None]:
    """Persist isolated CSV artifacts for pure-ODE and teacher-flux downstream steps."""

    output_dir = Path(output_dir)
    metabolites_csv = output_dir / "metabolites" / "all_metabolites.csv"
    reaction_fluxes_csv = output_dir / "fluxes" / "reaction_fluxes.csv"

    _write_all_metabolites_csv(result, metabolites_csv)
    if result.get("flux_data"):
        _write_reaction_fluxes_csv(result, reaction_fluxes_csv)
        reaction_fluxes_path: str | None = str(reaction_fluxes_csv)
    else:
        reaction_fluxes_path = None

    return {
        "all_metabolites_csv": str(metabolites_csv),
        "reaction_fluxes_csv": reaction_fluxes_path,
    }


def run_pure_ode_rerun(
    *,
    request: Any,
    custom_params: dict[str, float],
    output_dir: Path,
) -> dict[str, Any]:
    """Run a pure-ODE replay with the calibrated parameter set and write isolated artifacts."""

    research_data_mode = getattr(request, "research_data_mode", None) or "default_bordbar_mode"
    active_dataset = None
    if research_data_mode == "custom_user_data_mode":
        active_dataset = build_active_dataset_from_request(request)

    engine = SimulationEngine()
    result = engine.run_simulation(
        t_max=float(getattr(request, "t_max", 42.0)),
        solver_method=str(getattr(request, "solver_method", "RK45")),
        curve_fit_strength=0.0,
        custom_params={str(name): float(value) for name, value in custom_params.items()},
        research_data_mode=research_data_mode,
        active_dataset=active_dataset,
        active_dataset_id=getattr(request, "active_dataset_id", None),
        active_dataset_label=getattr(request, "active_dataset_label", None),
        autoload_calibrated_params=False,
    )
    if not result.get("success"):
        return {
            "success": False,
            "error": result.get("error") or "Pure ODE rerun failed.",
            "result": result,
            "artifacts": None,
        }

    artifacts = write_simulation_artifacts(result, Path(output_dir))
    return {
        "success": True,
        "result": result,
        "artifacts": artifacts,
    }
