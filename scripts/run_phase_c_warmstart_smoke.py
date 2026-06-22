"""Run the Phase C offline warm-start smoke harness.

Phase C is intentionally offline and additive. This script creates a small
synthetic dataset by perturbing a conservative subset of Brodbar parameters,
extracts the Phase B ``phase_b_v1`` feature vector, trains a deterministic
NumPy ridge model, and checks that predicted log-parameter multipliers beat the
default-parameter baseline on held-out synthetic cases.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
SCRIPTS_DIR = ROOT / "scripts"
DEFAULT_OUT_DIR = ROOT / "Simulations" / "auto_param_scope" / "phase_c_warmstart_smoke"
DEFAULT_TARGET_PARAMS = ("vmax_VEGLC", "vmax_VELAC", "vmax_VLDH", "vmax_VHK")


def _configure_imports() -> None:
    for path in (str(ROOT), str(SRC_DIR), str(SCRIPTS_DIR)):
        if path not in sys.path:
            sys.path.insert(0, path)


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return [_jsonable(v) for v in value.tolist()]
    if isinstance(value, (np.integer, np.floating)):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _normalize_names(values: Iterable[str]) -> Tuple[str, ...]:
    return tuple(str(value).strip() for value in values if str(value).strip())


def _param_defaults_and_bounds(params: Sequence[str]) -> Tuple[Dict[str, float], Dict[str, Tuple[float, float, float]]]:
    import MM_calibration as mm

    defaults: Dict[str, float] = {}
    bounds: Dict[str, Tuple[float, float, float]] = {}
    for name in params:
        if name not in mm.DEFAULT_PARAM_BOUNDS:
            raise KeyError(f"Unknown calibration parameter: {name}")
        default, lower, upper = mm.DEFAULT_PARAM_BOUNDS[name]
        defaults[name] = float(default)
        bounds[name] = (float(default), float(lower), float(upper))
    return defaults, bounds


def _case_profiles(param_count: int, profile: str) -> Tuple[Tuple[Tuple[float, ...], ...], Tuple[Tuple[float, ...], ...]]:
    if param_count < 1:
        raise ValueError("param_count must be positive.")

    profile_key = str(profile).strip().lower()
    if profile_key == "micro":
        train = [tuple([1.0] * param_count)]
        validate = []
        for factor in (0.9, 1.1):
            train.append(tuple([factor] + [1.0] * (param_count - 1)))
        for factor in (0.95, 1.05):
            validate.append(tuple([factor] + [1.0] * (param_count - 1)))
        return tuple(train), tuple(validate)

    if profile_key != "smoke":
        raise ValueError("profile must be 'micro' or 'smoke'.")

    train = [tuple([1.0] * param_count)]
    for idx in range(param_count):
        for factor in (0.75, 1.25):
            values = [1.0] * param_count
            values[idx] = factor
            train.append(tuple(values))

    # A few deterministic mixed cases help the ridge model learn interactions
    # without making the smoke expensive.
    mixed_templates = (
        (0.85, 1.15, 0.9, 1.1),
        (1.15, 0.85, 1.1, 0.9),
    )
    for template in mixed_templates:
        train.append(tuple(template[idx % len(template)] for idx in range(param_count)))

    validation_templates = (
        (0.9, 1.05, 1.15, 0.85),
        (1.1, 0.95, 0.85, 1.15),
        (1.2, 1.1, 0.9, 0.8),
    )
    validate = [tuple(template[idx % len(template)] for idx in range(param_count)) for template in validation_templates]
    return tuple(train), tuple(validate)


def _params_from_factors(
    factors: Sequence[float],
    params: Sequence[str],
    defaults: Mapping[str, float],
    bounds: Mapping[str, Tuple[float, float, float]],
) -> Dict[str, float]:
    if len(factors) != len(params):
        raise ValueError("factors must align with params.")
    values: Dict[str, float] = {}
    for name, factor in zip(params, factors):
        _default, lower, upper = bounds[name]
        values[name] = float(np.clip(float(defaults[name]) * float(factor), lower, upper))
    return values


def _extract_phase_b_features(
    *,
    params: Mapping[str, float],
    preset: str,
    t_max: float,
    timepoints: int,
    method: str,
    rtol: float,
    atol: float,
) -> Dict[str, Any]:
    import rbc_stoichiometry as rs
    import run_phase_b_flux_smoke as phase_b
    from flux_inference import infer_user_fluxes
    from ml_features import build_feature_payload

    selected_metabolites, inference_metabolites, selected_reactions = phase_b._resolve_preset(preset)
    sol = phase_b._solve_model(
        t_max=float(t_max),
        timepoints=int(timepoints),
        params=dict(params),
        method=str(method),
        rtol=float(rtol),
        atol=float(atol),
    )
    if not sol.success:
        raise RuntimeError(f"ODE solve failed: {sol.message}")

    time = np.asarray(sol.t, dtype=float)
    states = np.asarray(sol.y, dtype=float)
    curves = phase_b._model_curves(states, selected_metabolites)
    inference_curves = phase_b._model_curves(states, inference_metabolites)
    inferred = infer_user_fluxes(
        inference_curves,
        time,
        rs.STOICHIOMETRY,
        reactions=selected_reactions,
    )
    feature_payload = build_feature_payload(
        curves,
        inferred["fluxes"],
        inferred["time"],
        metabolites=selected_metabolites,
        reactions=selected_reactions,
    )
    return {
        "feature_payload": feature_payload,
        "time": time,
        "target_metabolites": selected_metabolites,
        "inference_metabolites": inference_metabolites,
        "reactions": selected_reactions,
    }


def _build_case(
    *,
    case_id: str,
    factors: Sequence[float],
    target_params: Sequence[str],
    defaults: Mapping[str, float],
    bounds: Mapping[str, Tuple[float, float, float]],
    preset: str,
    t_max: float,
    timepoints: int,
    method: str,
    rtol: float,
    atol: float,
) -> Dict[str, Any]:
    params = _params_from_factors(factors, target_params, defaults, bounds)
    feature_result = _extract_phase_b_features(
        params=params,
        preset=preset,
        t_max=t_max,
        timepoints=timepoints,
        method=method,
        rtol=rtol,
        atol=atol,
    )
    true_log_multipliers = np.asarray(
        [math.log(float(params[name]) / float(defaults[name])) for name in target_params],
        dtype=float,
    )
    return {
        "case_id": case_id,
        "factors": tuple(float(v) for v in factors),
        "params": params,
        "true_log_multipliers": true_log_multipliers,
        "feature_payload": feature_result["feature_payload"],
        "target_metabolites": feature_result["target_metabolites"],
        "inference_metabolites": feature_result["inference_metabolites"],
        "reactions": feature_result["reactions"],
    }


def _fit_standardized_ridge(
    features: np.ndarray,
    targets: np.ndarray,
    *,
    regularization: float,
) -> Dict[str, np.ndarray | float | str]:
    x = np.asarray(features, dtype=float)
    y = np.asarray(targets, dtype=float)
    if x.ndim != 2 or y.ndim != 2:
        raise ValueError("features and targets must be two-dimensional.")
    if x.shape[0] != y.shape[0]:
        raise ValueError("features and targets must have the same row count.")
    if x.shape[0] < 2:
        raise ValueError("at least two training cases are required.")

    feature_mean = np.mean(x, axis=0)
    feature_scale = np.std(x, axis=0)
    feature_scale = np.where(feature_scale < 1e-8, 1.0, feature_scale)
    target_mean = np.mean(y, axis=0)

    x_scaled = (x - feature_mean) / feature_scale
    y_centered = y - target_mean
    reg = float(max(regularization, 0.0))
    system = x_scaled.T @ x_scaled + reg * np.eye(x_scaled.shape[1])
    weights = np.linalg.solve(system, x_scaled.T @ y_centered)
    return {
        "kind": "standardized_ridge",
        "regularization": reg,
        "feature_mean": feature_mean,
        "feature_scale": feature_scale,
        "target_mean": target_mean,
        "weights": weights,
    }


def _predict_log_multipliers(model: Mapping[str, Any], features: np.ndarray) -> np.ndarray:
    x = np.asarray(features, dtype=float)
    if x.ndim == 1:
        x = x.reshape(1, -1)
    feature_mean = np.asarray(model["feature_mean"], dtype=float)
    feature_scale = np.asarray(model["feature_scale"], dtype=float)
    target_mean = np.asarray(model["target_mean"], dtype=float)
    weights = np.asarray(model["weights"], dtype=float)
    return ((x - feature_mean) / feature_scale) @ weights + target_mean


def _params_from_prediction(
    prediction: Sequence[float],
    target_params: Sequence[str],
    defaults: Mapping[str, float],
    bounds: Mapping[str, Tuple[float, float, float]],
) -> Dict[str, float]:
    values: Dict[str, float] = {}
    for name, log_multiplier in zip(target_params, prediction):
        _default, lower, upper = bounds[name]
        raw = float(defaults[name]) * math.exp(float(log_multiplier))
        values[name] = float(np.clip(raw, lower, upper))
    return values


def _evaluate_cases(
    *,
    model: Mapping[str, Any],
    cases: Sequence[Mapping[str, Any]],
    target_params: Sequence[str],
    defaults: Mapping[str, float],
    bounds: Mapping[str, Tuple[float, float, float]],
) -> Dict[str, Any]:
    rows = []
    log_maes = []
    baseline_log_maes = []
    max_abs_errors = []
    for case in cases:
        features = np.asarray(case["feature_payload"]["values"], dtype=float)
        true_log = np.asarray(case["true_log_multipliers"], dtype=float)
        pred_log = _predict_log_multipliers(model, features)[0]
        pred_params = _params_from_prediction(pred_log, target_params, defaults, bounds)
        predicted_log_from_clipped = np.asarray(
            [math.log(pred_params[name] / float(defaults[name])) for name in target_params],
            dtype=float,
        )
        abs_errors = np.abs(predicted_log_from_clipped - true_log)
        log_mae = float(np.mean(abs_errors))
        baseline_log_mae = float(np.mean(np.abs(true_log)))
        log_maes.append(log_mae)
        baseline_log_maes.append(baseline_log_mae)
        max_abs_errors.append(float(np.max(abs_errors)))
        rows.append(
            {
                "case_id": case["case_id"],
                "factors": case["factors"],
                "true_params": case["params"],
                "predicted_params": pred_params,
                "true_log_multipliers": true_log,
                "predicted_log_multipliers": predicted_log_from_clipped,
                "log_mae": log_mae,
                "baseline_log_mae": baseline_log_mae,
                "max_abs_log_error": float(np.max(abs_errors)),
            }
        )

    mean_log_mae = float(np.mean(log_maes)) if log_maes else math.inf
    baseline_mean_log_mae = float(np.mean(baseline_log_maes)) if baseline_log_maes else math.inf
    improvement_ratio = mean_log_mae / max(baseline_mean_log_mae, 1e-12)
    return {
        "mean_log_mae": mean_log_mae,
        "baseline_mean_log_mae": baseline_mean_log_mae,
        "improvement_ratio": float(improvement_ratio),
        "max_abs_log_error": float(max(max_abs_errors)) if max_abs_errors else math.inf,
        "cases": rows,
    }


def run_warmstart_smoke(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    preset: str = "wide",
    target_params: Sequence[str] = DEFAULT_TARGET_PARAMS,
    profile: str = "smoke",
    t_max: float = 2.0,
    timepoints: int = 8,
    method: str = "LSODA",
    rtol: float = 1e-5,
    atol: float = 1e-7,
    regularization: float = 1.0,
    max_improvement_ratio: float = 0.75,
    max_abs_log_error: float = 0.3,
) -> Dict[str, Any]:
    _configure_imports()

    target_param_tuple = _normalize_names(target_params)
    defaults, bounds = _param_defaults_and_bounds(target_param_tuple)
    train_factors, validation_factors = _case_profiles(len(target_param_tuple), profile)

    training_cases = [
        _build_case(
            case_id=f"train_{idx:02d}",
            factors=factors,
            target_params=target_param_tuple,
            defaults=defaults,
            bounds=bounds,
            preset=preset,
            t_max=t_max,
            timepoints=timepoints,
            method=method,
            rtol=rtol,
            atol=atol,
        )
        for idx, factors in enumerate(train_factors)
    ]
    validation_cases = [
        _build_case(
            case_id=f"validation_{idx:02d}",
            factors=factors,
            target_params=target_param_tuple,
            defaults=defaults,
            bounds=bounds,
            preset=preset,
            t_max=t_max,
            timepoints=timepoints,
            method=method,
            rtol=rtol,
            atol=atol,
        )
        for idx, factors in enumerate(validation_factors)
    ]

    x_train = np.vstack([np.asarray(case["feature_payload"]["values"], dtype=float) for case in training_cases])
    y_train = np.vstack([np.asarray(case["true_log_multipliers"], dtype=float) for case in training_cases])
    model = _fit_standardized_ridge(x_train, y_train, regularization=float(regularization))
    validation = _evaluate_cases(
        model=model,
        cases=validation_cases,
        target_params=target_param_tuple,
        defaults=defaults,
        bounds=bounds,
    )

    passed = bool(
        validation["improvement_ratio"] <= float(max_improvement_ratio)
        and validation["max_abs_log_error"] <= float(max_abs_log_error)
    )

    feature_payload = training_cases[0]["feature_payload"]
    payload: Dict[str, Any] = {
        "contract_type": "phase_c_warmstart_smoke_result",
        "contract_version": 1,
        "status": "passed" if passed else "failed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "feature_version": feature_payload["feature_version"],
        "preset": str(preset).strip().lower(),
        "synthetic_profile": str(profile).strip().lower(),
        "target_params": list(target_param_tuple),
        "param_defaults": defaults,
        "param_bounds": bounds,
        "solver": {
            "method": str(method),
            "rtol": float(rtol),
            "atol": float(atol),
            "t_max": float(t_max),
            "timepoints": int(timepoints),
        },
        "gate": {
            "max_improvement_ratio": float(max_improvement_ratio),
            "max_abs_log_error": float(max_abs_log_error),
        },
        "model": {
            "kind": model["kind"],
            "regularization": model["regularization"],
            "target_params": list(target_param_tuple),
            "feature_schema": feature_payload["schema"],
            "feature_count": int(feature_payload["metadata"]["feature_count"]),
            "feature_mean": model["feature_mean"],
            "feature_scale": model["feature_scale"],
            "target_mean": model["target_mean"],
            "weights": model["weights"],
        },
        "training": {
            "case_count": len(training_cases),
            "case_ids": [case["case_id"] for case in training_cases],
            "factors": [case["factors"] for case in training_cases],
        },
        "validation": validation,
    }

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "result.json"
    payload["out_path"] = str(out_path)
    out_path.write_text(json.dumps(_jsonable(payload), indent=2), encoding="utf-8")
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Phase C offline warm-start smoke")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--preset", default="wide")
    parser.add_argument("--profile", choices=("micro", "smoke"), default="smoke")
    parser.add_argument("--target-param", action="append", default=[])
    parser.add_argument("--t-max", type=float, default=2.0)
    parser.add_argument("--timepoints", type=int, default=8)
    parser.add_argument("--method", default="LSODA")
    parser.add_argument("--rtol", type=float, default=1e-5)
    parser.add_argument("--atol", type=float, default=1e-7)
    parser.add_argument("--regularization", type=float, default=1.0)
    parser.add_argument("--max-improvement-ratio", type=float, default=0.75)
    parser.add_argument("--max-abs-log-error", type=float, default=0.3)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    target_params = tuple(args.target_param) if args.target_param else DEFAULT_TARGET_PARAMS
    payload = run_warmstart_smoke(
        out_dir=args.out_dir,
        preset=args.preset,
        target_params=target_params,
        profile=args.profile,
        t_max=args.t_max,
        timepoints=args.timepoints,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
        regularization=args.regularization,
        max_improvement_ratio=args.max_improvement_ratio,
        max_abs_log_error=args.max_abs_log_error,
    )
    summary = {
        "status": payload["status"],
        "out_path": payload["out_path"],
        "feature_version": payload["feature_version"],
        "target_params": payload["target_params"],
        "training_case_count": payload["training"]["case_count"],
        "validation_mean_log_mae": payload["validation"]["mean_log_mae"],
        "baseline_mean_log_mae": payload["validation"]["baseline_mean_log_mae"],
        "improvement_ratio": payload["validation"]["improvement_ratio"],
        "max_abs_log_error": payload["validation"]["max_abs_log_error"],
    }
    print(json.dumps(_jsonable(summary), indent=2))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
