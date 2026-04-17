"""Generic teacher-flux helpers for supported custom-data reactions.

The current kinetics surface can learn explicit teacher curves for a small set
of reactions that are already supported by the ODE:

* EGLC -> VEGLC
* ELAC -> VELAC
* LAC  -> VLDH (via LAC balance reconstruction with VELAC as auxiliary flux)

This service builds teacher datasets directly from the active calibration
request instead of relying on the Bordbar spreadsheet.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List

import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator

_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parents[3]
_SRC = _PROJECT_ROOT / "src"
_APP_API = _PROJECT_ROOT / "apps" / "api"

for _path in (_APP_API, _SRC):
    _path_str = str(_path)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)

from services.pure_ode_runtime import run_pure_ode_rerun
from teacher_flux_bridge import distill_teacher_flux_kinetics, write_teacher_override_params


_SUPPORTED_TARGETS = {
    "EGLC": {"reaction": "VEGLC", "sign": -1.0},
    "ELAC": {"reaction": "VELAC", "sign": 1.0},
    "LAC": {
        "reaction": "VLDH",
        "auxiliary_reaction": "VELAC",
        "derivative_scale": 1.0,
        "auxiliary_scale": 1.0,
    },
}


def _normalize(name: Any) -> str:
    return str(name).strip().upper()


def infer_teacher_flux_targets(measured_metabolites: Iterable[str]) -> List[str]:
    return [name for name in (_normalize(item) for item in measured_metabolites) if name in _SUPPORTED_TARGETS]


def _load_auxiliary_flux_series(flux_csv_path: Path, reaction_name: str) -> tuple[np.ndarray, np.ndarray]:
    flux_df = pd.read_csv(flux_csv_path)
    time_col = "time" if "time" in flux_df.columns else flux_df.columns[0]
    if reaction_name not in flux_df.columns:
        raise KeyError(f"Reaction {reaction_name} not found in {flux_csv_path}")
    return (
        flux_df[time_col].to_numpy(dtype=float),
        flux_df[reaction_name].to_numpy(dtype=float),
    )


def build_teacher_flux_dataset_from_request(
    request: Any,
    *,
    metabolite_names: Iterable[str],
    out_path: Path,
    auxiliary_flux_csv_path: Path | None = None,
    dense_points: int = 200,
) -> dict[str, Any]:
    exp_time = np.asarray([float(value) for value in getattr(request, "exp_time", [])], dtype=float)
    exp_data = getattr(request, "exp_data", {}) or {}
    if exp_time.size < 2:
        raise ValueError("Teacher-flux dataset requires at least two experimental time points.")

    dense_timepoints = np.linspace(float(exp_time[0]), float(exp_time[-1]), int(dense_points))
    teacher_curves: Dict[str, Dict[str, Any]] = {}
    reaction_flux_curves: Dict[str, Dict[str, Any]] = {}
    normalized_targets = infer_teacher_flux_targets(metabolite_names)
    if not normalized_targets:
        raise ValueError("No supported teacher-flux targets were present in the request.")

    for metabolite_name in normalized_targets:
        values = exp_data.get(metabolite_name) or exp_data.get(metabolite_name.lower()) or exp_data.get(metabolite_name.upper())
        if not values:
            raise KeyError(f"Experimental series for {metabolite_name} was not present in the request.")

        curve_values = np.asarray([float(value) for value in values], dtype=float)
        pchip = PchipInterpolator(exp_time, curve_values)
        dense_values = pchip(dense_timepoints)
        dense_derivative = pchip.derivative()(dense_timepoints)

        teacher_curves[metabolite_name] = {
            "source": "request_experimental_pchip",
            "timepoints": exp_time.tolist(),
            "values": curve_values.tolist(),
            "dense_values": dense_values.tolist(),
            "dense_derivative": dense_derivative.tolist(),
        }

        rule = _SUPPORTED_TARGETS[metabolite_name]
        reaction_name = str(rule["reaction"])
        if metabolite_name != "LAC":
            reaction_flux_curves[reaction_name] = {
                "source_metabolite": metabolite_name,
                "source": "request_experimental_pchip_derivative",
                "dense_values": (float(rule["sign"]) * dense_derivative).tolist(),
            }
            continue

        if auxiliary_flux_csv_path is None:
            raise ValueError("LAC teacher-flux reconstruction requires auxiliary_flux_csv_path with VELAC.")
        aux_time, aux_values = _load_auxiliary_flux_series(Path(auxiliary_flux_csv_path), str(rule["auxiliary_reaction"]))
        aux_interp = np.interp(dense_timepoints, aux_time, aux_values)
        reaction_flux_curves[reaction_name] = {
            "source_metabolite": metabolite_name,
            "source": "request_experimental_pchip_balance_reconstruction",
            "auxiliary_flux_csv_path": str(auxiliary_flux_csv_path),
            "auxiliary_reaction": str(rule["auxiliary_reaction"]),
            "dense_values": (
                float(rule["derivative_scale"]) * dense_derivative
                + float(rule["auxiliary_scale"]) * aux_interp
            ).tolist(),
        }

    payload = {
        "contract_type": "teacher_flux_dataset",
        "contract_version": 1,
        "dataset_label": "teacher_flux_" + "_".join(name.lower() for name in normalized_targets),
        "data_path": "request_payload",
        "auxiliary_flux_csv_path": str(auxiliary_flux_csv_path) if auxiliary_flux_csv_path is not None else None,
        "target_metabolites": normalized_targets,
        "dense_timepoints": dense_timepoints.tolist(),
        "teacher_curves": teacher_curves,
        "reaction_flux_curves": reaction_flux_curves,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def run_teacher_flux_rescue(
    *,
    request: Any,
    params: dict[str, float],
    output_dir: Path,
    simulation_artifacts: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Build explicit teacher-flux artifacts and optional distillation outputs."""

    output_dir = Path(output_dir)
    measured_metabolites = list(getattr(request, "target_metabolites", None) or list((getattr(request, "exp_data", {}) or {}).keys()))
    targets = infer_teacher_flux_targets(measured_metabolites)
    if not targets:
        return {
            "status": "skipped",
            "reason": "No supported teacher-flux targets were present in the measured metabolite panel.",
        }

    artifacts = dict(simulation_artifacts or {})
    if not artifacts.get("all_metabolites_csv") or not artifacts.get("reaction_fluxes_csv"):
        rerun = run_pure_ode_rerun(
            request=request,
            custom_params=params,
            output_dir=output_dir / "simulation",
        )
        if not rerun.get("success"):
            return {
                "status": "skipped",
                "reason": "Teacher-flux rescue could not generate the candidate simulation artifacts.",
                "simulation_error": rerun.get("error"),
            }
        artifacts = dict(rerun.get("artifacts") or {})

    reaction_flux_csv_path = artifacts.get("reaction_fluxes_csv")
    if "LAC" in targets and not reaction_flux_csv_path:
        targets = [name for name in targets if name != "LAC"]
        if not targets:
            return {
                "status": "skipped",
                "reason": "Teacher-flux rescue needs reaction_fluxes.csv to reconstruct VLDH from LAC.",
            }

    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = output_dir / "teacher_flux_dataset.json"
    teacher_dataset = build_teacher_flux_dataset_from_request(
        request,
        metabolite_names=targets,
        out_path=dataset_path,
        auxiliary_flux_csv_path=Path(reaction_flux_csv_path) if reaction_flux_csv_path else None,
    )

    seed_params_path = output_dir / "base_params.json"
    seed_params_path.write_text(json.dumps({str(name): float(value) for name, value in params.items()}, indent=2), encoding="utf-8")
    teacher_override_params_path = output_dir / "teacher_override_params.json"
    write_teacher_override_params(
        seed_params_path=seed_params_path,
        dataset_path=dataset_path,
        out_path=teacher_override_params_path,
        reactions=[_SUPPORTED_TARGETS[target]["reaction"] for target in targets],
    )

    distillation_payload: dict[str, Any] | None = None
    state_csv_path = artifacts.get("all_metabolites_csv")
    if state_csv_path and reaction_flux_csv_path:
        distillation_dir = output_dir / "distillation"
        distillation_report = distill_teacher_flux_kinetics(
            state_csv_path=Path(state_csv_path),
            flux_csv_path=Path(reaction_flux_csv_path),
            out_dir=distillation_dir,
            base_params_path=seed_params_path,
        )
        recommended_params_path = distillation_dir / "teacher_flux_recommended_params.json"
        distillation_payload = {
            "report": distillation_report,
            "report_path": str(distillation_dir / "teacher_flux_distillation_report.json"),
            "recommended_params_path": str(recommended_params_path) if recommended_params_path.exists() else None,
            "recommended_params": (
                json.loads(recommended_params_path.read_text(encoding="utf-8"))
                if recommended_params_path.exists()
                else None
            ),
        }

    return {
        "status": "completed",
        "targets": targets,
        "reactions": [_SUPPORTED_TARGETS[target]["reaction"] for target in targets],
        "teacher_flux_dataset_path": str(dataset_path),
        "teacher_flux_dataset": teacher_dataset,
        "teacher_override_params_path": str(teacher_override_params_path),
        "teacher_override_params": json.loads(teacher_override_params_path.read_text(encoding="utf-8")),
        "simulation_artifacts": artifacts,
        "distillation": distillation_payload,
    }
