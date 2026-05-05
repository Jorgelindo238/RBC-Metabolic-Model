"""Run the Phase B model-flux smoke test.

This script validates the first Phase B flux-inference slice against the ODE
itself:

1. solve the Brodbar RBC ODE on a fixed time grid
2. replay the solved states through the ODE with ``FluxTracker`` enabled
3. infer VEGLC / VELAC / VLDH from simulated EGLC / ELAC / LAC curves
4. compare inferred fluxes with tracked model fluxes
5. write a JSON artifact for AgentOps / future campaign gates
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np
from scipy.integrate import solve_ivp


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
DEFAULT_OUT_DIR = ROOT / "Simulations" / "auto_param_scope" / "phase_b_model_flux_smoke"
DEFAULT_METABOLITES = ("EGLC", "ELAC", "LAC", "ATP")
DEFAULT_REACTIONS = ("VEGLC", "VELAC", "VLDH")
DEFAULT_TOLERANCES = {
    "VEGLC": 0.02,
    "VELAC": 0.03,
    "VLDH": 0.08,
}


def _configure_imports() -> None:
    for path in (str(ROOT), str(SRC_DIR)):
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


def _read_params(path: Optional[Path]) -> Optional[Dict[str, float]]:
    if path is None:
        return None
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return {str(name): float(value) for name, value in payload.items()}


def _nrmse(actual: Sequence[float], expected: Sequence[float]) -> float:
    actual_arr = np.asarray(actual, dtype=float)
    expected_arr = np.asarray(expected, dtype=float)
    scale = max(float(np.mean(np.abs(expected_arr))), 1e-12)
    return float(np.sqrt(np.mean((actual_arr - expected_arr) ** 2)) / scale)


def _max_abs_error(actual: Sequence[float], expected: Sequence[float]) -> float:
    actual_arr = np.asarray(actual, dtype=float)
    expected_arr = np.asarray(expected, dtype=float)
    return float(np.max(np.abs(actual_arr - expected_arr)))


def _solve_model(
    *,
    t_max: float,
    timepoints: int,
    params: Optional[Mapping[str, float]],
    method: str,
    rtol: float,
    atol: float,
):
    import MM_calibration as mm
    from equadiff_brodbar import equadiff_brodbar

    x0 = mm.load_initial_conditions()
    t_eval = np.linspace(1.0, float(t_max), int(timepoints))
    return solve_ivp(
        lambda t, y: equadiff_brodbar(
            t,
            y,
            custom_params=dict(params) if params else None,
            curve_fit_strength=0.0,
        ),
        (1.0, float(t_max)),
        x0,
        method=method,
        t_eval=t_eval,
        rtol=float(rtol),
        atol=float(atol),
    )


def _tracked_fluxes(
    *,
    time: np.ndarray,
    states: np.ndarray,
    params: Optional[Mapping[str, float]],
) -> Dict[str, np.ndarray]:
    from equadiff_brodbar import equadiff_brodbar
    from flux_visualization import FluxTracker

    tracker = FluxTracker()
    for t, y in zip(time, states.T):
        equadiff_brodbar(
            float(t),
            np.asarray(y, dtype=float),
            custom_params=dict(params) if params else None,
            curve_fit_strength=0.0,
            flux_tracker=tracker,
        )
    return {reaction: np.asarray(values, dtype=float) for reaction, values in tracker.fluxes.items()}


def _model_curves(states: np.ndarray, metabolites: Sequence[str]) -> Dict[str, np.ndarray]:
    from equadiff_brodbar import BRODBAR_METABOLITE_MAP

    curves: Dict[str, np.ndarray] = {}
    for metabolite in metabolites:
        name = str(metabolite).strip().upper()
        if name not in BRODBAR_METABOLITE_MAP:
            raise KeyError(f"Unknown Brodbar metabolite: {name}")
        curves[name] = np.asarray(states[int(BRODBAR_METABOLITE_MAP[name]), :], dtype=float)
    return curves


def _compare_fluxes(
    inferred: Mapping[str, Sequence[float]],
    tracked: Mapping[str, Sequence[float]],
    reactions: Sequence[str],
    tolerances: Mapping[str, float],
) -> Tuple[Dict[str, Dict[str, float | bool]], bool]:
    comparisons: Dict[str, Dict[str, float | bool]] = {}
    all_passed = True
    for reaction in reactions:
        if reaction not in inferred:
            raise KeyError(f"Inferred fluxes did not include {reaction}.")
        if reaction not in tracked:
            raise KeyError(f"Tracked model fluxes did not include {reaction}.")
        nrmse = _nrmse(inferred[reaction], tracked[reaction])
        max_error = _max_abs_error(inferred[reaction], tracked[reaction])
        tolerance = float(tolerances.get(reaction, 0.1))
        passed = bool(nrmse <= tolerance)
        all_passed = all_passed and passed
        comparisons[reaction] = {
            "nrmse_vs_model_flux": nrmse,
            "max_abs_error": max_error,
            "tolerance": tolerance,
            "passed": passed,
        }
    return comparisons, all_passed


def run_smoke(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    t_max: float = 7.0,
    timepoints: int = 25,
    params_path: Optional[Path] = None,
    method: str = "LSODA",
    rtol: float = 1e-5,
    atol: float = 1e-7,
    tolerances: Optional[Mapping[str, float]] = None,
) -> Dict[str, Any]:
    _configure_imports()

    import rbc_stoichiometry as rs
    from flux_inference import infer_user_fluxes
    from ml_features import build_feature_payload

    resolved_tolerances = dict(DEFAULT_TOLERANCES)
    if tolerances:
        resolved_tolerances.update({str(k).strip().upper(): float(v) for k, v in tolerances.items()})

    params = _read_params(params_path)
    sol = _solve_model(
        t_max=float(t_max),
        timepoints=int(timepoints),
        params=params,
        method=str(method),
        rtol=float(rtol),
        atol=float(atol),
    )
    if not sol.success:
        raise RuntimeError(f"ODE solve failed: {sol.message}")

    time = np.asarray(sol.t, dtype=float)
    states = np.asarray(sol.y, dtype=float)
    curves = _model_curves(states, DEFAULT_METABOLITES)
    tracked = _tracked_fluxes(time=time, states=states, params=params)
    inferred = infer_user_fluxes(
        curves,
        time,
        rs.STOICHIOMETRY,
        reactions=DEFAULT_REACTIONS,
    )
    comparisons, passed = _compare_fluxes(
        inferred["fluxes"],
        tracked,
        DEFAULT_REACTIONS,
        resolved_tolerances,
    )
    feature_payload = build_feature_payload(
        inferred["curves"],
        inferred["fluxes"],
        inferred["time"],
        metabolites=DEFAULT_METABOLITES,
        reactions=DEFAULT_REACTIONS,
    )

    payload: Dict[str, Any] = {
        "contract_type": "phase_b_model_flux_smoke_result",
        "contract_version": 1,
        "status": "passed" if passed else "failed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "brodbar_ode_flux_tracker",
        "solver": {
            "method": str(method),
            "rtol": float(rtol),
            "atol": float(atol),
            "t_max": float(t_max),
            "timepoints": int(timepoints),
        },
        "params_path": str(params_path) if params_path else None,
        "target_metabolites": list(DEFAULT_METABOLITES),
        "reactions": list(DEFAULT_REACTIONS),
        "time": time,
        "comparisons": comparisons,
        "inference_diagnostics": inferred["diagnostics"],
        "confidence": inferred["confidence"],
        "model_curves": curves,
        "tracked_fluxes": {reaction: tracked[reaction] for reaction in DEFAULT_REACTIONS},
        "inferred_fluxes": {reaction: inferred["fluxes"][reaction] for reaction in DEFAULT_REACTIONS},
        "feature_payload": {
            "contract_type": feature_payload["contract_type"],
            "contract_version": feature_payload["contract_version"],
            "feature_version": feature_payload["feature_version"],
            "schema": feature_payload["schema"],
            "values": feature_payload["values"],
            "metadata": feature_payload["metadata"],
        },
    }

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "result.json"
    payload["out_path"] = str(out_path)
    out_path.write_text(json.dumps(_jsonable(payload), indent=2), encoding="utf-8")
    return payload


def _parse_tolerance(value: str) -> Tuple[str, float]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Tolerance must be formatted REACTION=value")
    name, raw = value.split("=", 1)
    return name.strip().upper(), float(raw)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Phase B model-flux smoke")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--t-max", type=float, default=7.0)
    parser.add_argument("--timepoints", type=int, default=25)
    parser.add_argument("--params-json", type=Path)
    parser.add_argument("--method", default="LSODA")
    parser.add_argument("--rtol", type=float, default=1e-5)
    parser.add_argument("--atol", type=float, default=1e-7)
    parser.add_argument(
        "--tolerance",
        action="append",
        type=_parse_tolerance,
        default=[],
        help="Override per-reaction NRMSE tolerance, e.g. --tolerance VLDH=0.1",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    tolerances = dict(args.tolerance or [])
    payload = run_smoke(
        out_dir=args.out_dir,
        t_max=args.t_max,
        timepoints=args.timepoints,
        params_path=args.params_json,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
        tolerances=tolerances,
    )
    summary = {
        "status": payload["status"],
        "out_path": payload["out_path"],
        "comparisons": payload["comparisons"],
        "feature_count": payload["feature_payload"]["metadata"]["feature_count"],
    }
    print(json.dumps(_jsonable(summary), indent=2))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
