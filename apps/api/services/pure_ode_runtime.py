"""Pure-ODE rerun helpers for web/worker calibration flows.

This module reuses the existing Streamlit simulation engine to run an
in-process "main.py-equivalent" ODE replay for a calibrated parameter set.
It writes isolated CSV artifacts so downstream tools can reuse the same
outputs that Hermes Phase B and teacher-flux distillation understand.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
import sys
from typing import Any, Dict, Iterable

_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parents[3]
_API = _THIS_FILE.parents[1]
_STREAMLIT_APP = _PROJECT_ROOT / "streamlit_app"
_SRC = _PROJECT_ROOT / "src"

for _path in (_API, _STREAMLIT_APP, _SRC):
    _path_str = str(_path)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)

import st_shim
st_shim.install()

from core.simulation_engine import SimulationEngine


def _normalize_metabolite_name(name: Any) -> str:
    return str(name).strip().upper()


def _sequence_values(value: Any) -> list[Any]:
    """Return list-like simulation outputs without relying on truthiness."""

    if value is None:
        return []
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (str, bytes)):
        return [value]
    try:
        return list(value)
    except TypeError:
        return [value]


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
    metabolite_names = [str(name) for name in _sequence_values(result.get("metabolite_names"))]
    timepoints = [float(value) for value in _sequence_values(result.get("t"))]
    trajectories = _sequence_values(result.get("x"))

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Time", *metabolite_names])
        for index, timepoint in enumerate(timepoints):
            row = trajectories[index]
            writer.writerow([timepoint, *[float(value) for value in row]])


def _write_reaction_fluxes_csv(result: dict[str, Any], csv_path: Path) -> None:
    flux_data = result.get("flux_data")
    if not isinstance(flux_data, dict):
        flux_data = {}
    times = [float(value) for value in _sequence_values(flux_data.get("times"))]
    fluxes = flux_data.get("fluxes")
    if not isinstance(fluxes, dict):
        fluxes = {}
    reaction_names = sorted(str(name) for name in fluxes.keys())
    flux_series = {reaction_name: _sequence_values(fluxes.get(reaction_name)) for reaction_name in reaction_names}

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time", *reaction_names])
        for index, timepoint in enumerate(times):
            writer.writerow(
                [
                    timepoint,
                    *[
                        float(flux_series[reaction_name][index])
                        for reaction_name in reaction_names
                    ],
                ]
            )


def _validate_artifact_payload(result: dict[str, Any]) -> None:
    """Reject malformed evidence before creating any output files.

    Flux tracker times may include rejected solver steps, so their order is
    preserved here. They are not an accepted-state quadrature grid.
    """
    names = _sequence_values(result.get("metabolite_names"))
    times = _sequence_values(result.get("t"))
    rows = _sequence_values(result.get("x"))
    if (not names or any(not str(name).strip() for name in names)
            or len(set(map(str, names))) != len(names)):
        raise ValueError("metabolite_names must be nonempty and unique")
    if not times or len(rows) != len(times):
        raise ValueError("trajectory rows must align with nonempty timepoints")
    if any(not math.isfinite(float(t)) for t in times):
        raise ValueError("trajectory timepoints must be finite")
    if any(float(b) <= float(a) for a, b in zip(times, times[1:])):
        raise ValueError("trajectory timepoints must be strictly increasing")
    for row in rows:
        if not isinstance(row, (list, tuple)):
            raise ValueError("trajectories must be a two-dimensional array")
        values = _sequence_values(row)
        if len(values) != len(names):
            raise ValueError("trajectory columns must align with metabolite_names")
        if any(not math.isfinite(float(value)) for value in values):
            raise ValueError("trajectory values must be finite")
    flux_data = result.get("flux_data")
    if flux_data is None:
        return
    if not isinstance(flux_data, dict):
        raise ValueError("flux_data must be a mapping or None")
    if not flux_data:
        return
    flux_times = _sequence_values(flux_data.get("times"))
    fluxes = flux_data.get("fluxes")
    if not flux_times or not isinstance(fluxes, dict) or not fluxes:
        raise ValueError("flux_data must contain nonempty times and fluxes")
    if any(not math.isfinite(float(t)) for t in flux_times):
        raise ValueError("flux timepoints must be finite")
    for name, series in fluxes.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("reaction names must be nonempty strings")
        values = _sequence_values(series)
        if len(values) != len(flux_times):
            raise ValueError(f"flux series {name} must align with flux timepoints")
        if any(not math.isfinite(float(value)) for value in values):
            raise ValueError(f"flux series {name} must be finite")


def write_simulation_artifacts(result: dict[str, Any], output_dir: Path) -> dict[str, str | None]:
    """Persist isolated CSV artifacts for pure-ODE and teacher-flux downstream steps."""

    _validate_artifact_payload(result)
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
