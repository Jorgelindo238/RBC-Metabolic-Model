"""Extracellular teacher-flux targets for RBC storage calibration.

Phase A of the extracellular flux-learning workflow turns measured
extracellular concentration curves into direct reaction-flux targets.  The
output contract intentionally matches ``teacher_flux_dataset`` so
``MM_calibration`` can consume it with ``teacher_flux_weight``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator


_SRC_DIR = Path(__file__).resolve().parent
DEFAULT_BORDBAR_DATA_PATH = _SRC_DIR / "Data_Bordbar_et_al_exp.xlsx"

EXTRACELLULAR_TEACHER_METABOLITES = (
    "EADE",
    "EASN",
    "ECIT",
    "ECYS",
    "EFUM",
    "EGLC",
    "EGLN",
    "EGLU",
    "EGSSG",
    "EGSH",
    "EHYPX",
    "EINO",
    "ELAC",
    "EMAL",
    "EARG",
    "EURT",
    "EXAN",
    "EOXOP",
    "ESER",
)

EXTRACELLULAR_TEACHER_FLUX_RULES: Dict[str, Dict[str, Any]] = {
    "EADE": {"reaction": "VEADE", "sign": 1.0, "equation": "dEADE/dt = VEADE"},
    "EASN": {"reaction": "VEASN_rate", "sign": 1.0, "equation": "dEASN/dt = VEASN_rate"},
    "ECIT": {"reaction": "VECIT", "sign": 1.0, "equation": "dECIT/dt = VECIT"},
    "ECYS": {"reaction": "VECYS", "sign": 1.0, "equation": "dECYS/dt = VECYS"},
    "EFUM": {"reaction": "VEFUM", "sign": 1.0, "equation": "dEFUM/dt = VEFUM"},
    "EGLC": {"reaction": "VEGLC", "sign": -1.0, "equation": "dEGLC/dt = -VEGLC"},
    "EGLN": {"reaction": "VEGLN", "sign": 1.0, "equation": "dEGLN/dt = VEGLN"},
    "EGLU": {"reaction": "VEGLU", "sign": 1.0, "equation": "dEGLU/dt = VEGLU"},
    "EGSSG": {
        "reaction": "VEGSSG",
        "sign": 1.0,
        "degradation_param": "k_EGSSG_deg",
        "degradation_default": 0.05,
        "equation": "dEGSSG/dt = VEGSSG - k_EGSSG_deg * EGSSG",
    },
    "EGSH": {
        "reaction": "VEGSH_rate",
        "sign": 1.0,
        "degradation_param": "k_EGSH_deg",
        "degradation_default": 0.1,
        "equation": "dEGSH/dt = VEGSH_rate - k_EGSH_deg * EGSH",
    },
    "EHYPX": {"reaction": "VEHYPX", "sign": 1.0, "equation": "dEHYPX/dt = VEHYPX"},
    "EINO": {"reaction": "VEINO", "sign": 1.0, "equation": "dEINO/dt = VEINO"},
    "ELAC": {"reaction": "VELAC", "sign": 1.0, "equation": "dELAC/dt = VELAC"},
    "EMAL": {"reaction": "VEMAL", "sign": 1.0, "equation": "dEMAL/dt = VEMAL"},
    "EARG": {"reaction": "VEARG", "sign": 1.0, "equation": "dEARG/dt = VEARG"},
    "EURT": {"reaction": "VEURT", "sign": 1.0, "equation": "dEURT/dt = VEURT"},
    "EXAN": {"reaction": "VEXAN", "sign": 1.0, "equation": "dEXAN/dt = VEXAN"},
    "EOXOP": {"reaction": "VEOXOP", "sign": 1.0, "equation": "dEOXOP/dt = VEOXOP"},
    "ESER": {"reaction": "VESER", "sign": 1.0, "equation": "dESER/dt = VESER"},
}


def _normalize_name(name: Any) -> str:
    return str(name).strip().upper()


def normalize_extracellular_targets(metabolite_names: Iterable[str] | None) -> list[str]:
    if metabolite_names is None:
        return list(EXTRACELLULAR_TEACHER_METABOLITES)
    seen: set[str] = set()
    targets: list[str] = []
    for raw_name in metabolite_names:
        name = _normalize_name(raw_name)
        if not name or name in seen:
            continue
        if name in EXTRACELLULAR_TEACHER_FLUX_RULES:
            targets.append(name)
            seen.add(name)
    return targets


def infer_extracellular_teacher_flux_targets(measured_metabolites: Iterable[str]) -> list[str]:
    return normalize_extracellular_targets(measured_metabolites)


def _normalize_time_and_curves(
    exp_data: Mapping[str, Sequence[float]],
    exp_time: Sequence[float],
) -> tuple[np.ndarray, Dict[str, np.ndarray]]:
    source_time = np.asarray([float(value) for value in exp_time], dtype=float)
    if source_time.ndim != 1 or source_time.size < 2:
        raise ValueError("exp_time must contain at least two time points.")
    if not np.all(np.isfinite(source_time)):
        raise ValueError("exp_time contains non-finite values.")
    order = np.argsort(source_time)
    time = source_time[order]
    if np.any(np.diff(time) <= 0):
        raise ValueError("exp_time must be strictly increasing after sorting.")

    curves: Dict[str, np.ndarray] = {}
    for raw_name, raw_values in exp_data.items():
        name = _normalize_name(raw_name)
        if not name:
            continue
        values = np.asarray([float(value) for value in raw_values], dtype=float)
        if values.ndim != 1 or values.size != source_time.size:
            raise ValueError(f"Series for {name} must align with exp_time.")
        if not np.all(np.isfinite(values)):
            continue
        curves[name] = values[order]
    if not curves:
        raise ValueError("exp_data did not contain any finite metabolite series.")
    return time, curves


def _smoothness_score(values: np.ndarray) -> float:
    if values.size < 3:
        return 1.0
    first = np.diff(values)
    second = np.diff(first)
    scale = float(np.nanmedian(np.abs(first))) + 1e-12
    roughness = float(np.nanmedian(np.abs(second))) / scale
    return float(np.clip(1.0 / (1.0 + roughness), 0.0, 1.0))


def _flux_confidence(values: np.ndarray, *, expected_nonnegative: bool = True) -> Dict[str, float]:
    if values.size == 0:
        return {
            "confidence": 0.0,
            "sign_consistency": 0.0,
            "smoothness": 0.0,
            "mean_abs_flux": 0.0,
            "max_abs_flux": 0.0,
        }
    tolerance = max(float(np.nanmax(np.abs(values))) * 1e-9, 1e-12)
    sign_consistency = (
        float(np.mean(values >= -tolerance))
        if expected_nonnegative
        else 1.0
    )
    smoothness = _smoothness_score(values)
    mean_abs_flux = float(np.nanmean(np.abs(values)))
    max_abs_flux = float(np.nanmax(np.abs(values)))
    signal_component = float(np.clip(mean_abs_flux / max(max_abs_flux, 1e-12), 0.0, 1.0))
    confidence = 0.20 + 0.45 * sign_consistency + 0.25 * smoothness + 0.10 * signal_component
    return {
        "confidence": float(np.clip(confidence, 0.0, 1.0)),
        "sign_consistency": float(np.clip(sign_consistency, 0.0, 1.0)),
        "smoothness": smoothness,
        "mean_abs_flux": mean_abs_flux,
        "max_abs_flux": max_abs_flux,
    }


def build_extracellular_teacher_flux_dataset(
    exp_data: Mapping[str, Sequence[float]],
    exp_time: Sequence[float],
    *,
    metabolite_names: Iterable[str] | None = None,
    dense_points: int = 200,
    degradation_params: Mapping[str, float] | None = None,
    dataset_label: str | None = None,
    data_path: str | Path | None = None,
    out_path: str | Path | None = None,
    strict: bool = True,
) -> dict[str, Any]:
    """Build a JSON-friendly extracellular ``teacher_flux_dataset`` payload."""

    if int(dense_points) < 2:
        raise ValueError("dense_points must be at least 2.")

    time, curves = _normalize_time_and_curves(exp_data, exp_time)
    targets = normalize_extracellular_targets(metabolite_names)
    if not targets:
        raise ValueError("No supported extracellular teacher-flux targets were requested.")

    dense_timepoints = np.linspace(float(time[0]), float(time[-1]), int(dense_points))
    degradation_values = {
        str(name): float(value)
        for name, value in (degradation_params or {}).items()
    }

    retained_targets: list[str] = []
    teacher_curves: Dict[str, Dict[str, Any]] = {}
    reaction_flux_curves: Dict[str, Dict[str, Any]] = {}
    teacher_target_weights: Dict[str, float] = {}

    missing = [name for name in targets if name not in curves]
    if missing and strict:
        raise KeyError(f"Missing experimental series for extracellular targets: {', '.join(missing)}")

    for metabolite_name in targets:
        values = curves.get(metabolite_name)
        if values is None:
            continue

        rule = EXTRACELLULAR_TEACHER_FLUX_RULES[metabolite_name]
        pchip = PchipInterpolator(time, values)
        dense_values = np.asarray(pchip(dense_timepoints), dtype=float)
        dense_derivative = np.asarray(pchip.derivative()(dense_timepoints), dtype=float)

        flux_values = float(rule["sign"]) * dense_derivative
        balance_correction = None
        degradation_param = rule.get("degradation_param")
        if degradation_param:
            k_value = float(degradation_values.get(str(degradation_param), rule["degradation_default"]))
            correction = k_value * np.maximum(dense_values, 0.0)
            flux_values = flux_values + correction
            balance_correction = {
                "type": "first_order_degradation",
                "param": str(degradation_param),
                "value": k_value,
            }

        diagnostics = _flux_confidence(flux_values, expected_nonnegative=True)
        reaction_name = str(rule["reaction"])
        retained_targets.append(metabolite_name)
        teacher_target_weights[metabolite_name] = float(max(0.10, diagnostics["confidence"]))
        teacher_curves[metabolite_name] = {
            "source": "experimental_pchip",
            "timepoints": time.tolist(),
            "values": values.tolist(),
            "dense_values": dense_values.tolist(),
            "dense_derivative": dense_derivative.tolist(),
        }
        reaction_flux_curves[reaction_name] = {
            "source_metabolite": metabolite_name,
            "source": "extracellular_balance_pchip_derivative",
            "equation": str(rule["equation"]),
            "dense_values": flux_values.tolist(),
            "expected_nonnegative": True,
            "diagnostics": diagnostics,
        }
        if balance_correction is not None:
            reaction_flux_curves[reaction_name]["balance_correction"] = balance_correction

    if not retained_targets:
        raise ValueError("No requested extracellular teacher-flux targets were present in exp_data.")

    payload = {
        "contract_type": "teacher_flux_dataset",
        "contract_version": 1,
        "flux_rule_version": "extracellular_v1",
        "dataset_label": dataset_label
        or "teacher_flux_extracellular_" + "_".join(name.lower() for name in retained_targets),
        "data_path": str(data_path) if data_path is not None else "request_payload",
        "target_metabolites": retained_targets,
        "dense_timepoints": dense_timepoints.tolist(),
        "teacher_target_weights": teacher_target_weights,
        "teacher_curves": teacher_curves,
        "reaction_flux_curves": reaction_flux_curves,
    }

    if out_path is not None:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return payload


def load_bordbar_extracellular_data(
    data_path: str | Path = DEFAULT_BORDBAR_DATA_PATH,
) -> tuple[np.ndarray, Dict[str, list[float]]]:
    data_path = Path(data_path)
    df = pd.read_excel(data_path, sheet_name="Sheet1")
    if "Conc / mM" not in df.columns:
        raise ValueError(f"Unsupported experimental sheet format in {data_path}")
    time_cols = [col for col in df.columns if col != "Conc / mM"]
    timepoints = np.asarray([float(col) for col in time_cols], dtype=float)
    exp_data: Dict[str, list[float]] = {}
    for _, row in df.iterrows():
        name = _normalize_name(row["Conc / mM"])
        if name in EXTRACELLULAR_TEACHER_FLUX_RULES:
            exp_data[name] = [float(row[col]) for col in time_cols]
    return timepoints, exp_data


def build_bordbar_extracellular_teacher_flux_dataset(
    *,
    metabolite_names: Iterable[str] | None = None,
    dense_points: int = 200,
    data_path: str | Path = DEFAULT_BORDBAR_DATA_PATH,
    out_path: str | Path | None = None,
    degradation_params: Mapping[str, float] | None = None,
    dataset_label: str | None = None,
) -> dict[str, Any]:
    timepoints, exp_data = load_bordbar_extracellular_data(data_path)
    return build_extracellular_teacher_flux_dataset(
        exp_data,
        timepoints,
        metabolite_names=metabolite_names,
        dense_points=dense_points,
        degradation_params=degradation_params,
        dataset_label=dataset_label or "teacher_flux_bordbar_extracellular",
        data_path=data_path,
        out_path=out_path,
        strict=True,
    )


__all__ = [
    "DEFAULT_BORDBAR_DATA_PATH",
    "EXTRACELLULAR_TEACHER_FLUX_RULES",
    "EXTRACELLULAR_TEACHER_METABOLITES",
    "build_bordbar_extracellular_teacher_flux_dataset",
    "build_extracellular_teacher_flux_dataset",
    "infer_extracellular_teacher_flux_targets",
    "load_bordbar_extracellular_data",
    "normalize_extracellular_targets",
]
