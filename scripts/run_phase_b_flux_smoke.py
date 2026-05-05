"""Run the Phase B model-flux smoke test.

This script validates the first Phase B flux-inference slice against the ODE
itself:

1. solve the Brodbar RBC ODE on a fixed time grid
2. replay the solved states through the ODE with ``FluxTracker`` enabled
3. infer VEGLC / VELAC / VLDH from simulated EGLC / ELAC / LAC curves
4. compare inferred fluxes with tracked model fluxes
5. write a JSON artifact for AgentOps / future campaign gates

The default ``direct`` preset preserves the original three-reaction contract.
The ``wide`` preset adds the next conservative singleton reaction (VHK), and
``--discover-identifiable`` emits a discovery report for all reactions touching
the measured wide metabolite panel.
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
from scipy.integrate import solve_ivp


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
DEFAULT_OUT_DIR = ROOT / "Simulations" / "auto_param_scope" / "phase_b_model_flux_smoke"
DIRECT_METABOLITES = ("EGLC", "ELAC", "LAC", "ATP")
DIRECT_REACTIONS = ("VEGLC", "VELAC", "VLDH")
WIDE_METABOLITES = (
    "EGLC",
    "ELAC",
    "LAC",
    "GLC",
    "G6P",
    "F6P",
    "F16BP",
    "P3G",
    "B23PG",
    "P2G",
    "PEP",
    "PYR",
    "ATP",
    "ADP",
    "AMP",
    "NAD",
    "NADH",
)
WIDE_REACTIONS = ("VEGLC", "VELAC", "VLDH", "VHK")
PRESET_CONFIG = {
    "direct": {
        "metabolites": DIRECT_METABOLITES,
        "inference_metabolites": DIRECT_METABOLITES,
        "reactions": DIRECT_REACTIONS,
    },
    "wide": {
        "metabolites": WIDE_METABOLITES,
        "inference_metabolites": ("EGLC", "ELAC", "LAC", "GLC"),
        "reactions": WIDE_REACTIONS,
    },
}
DEFAULT_TOLERANCES: Dict[str, float] = {
    "VEGLC": 0.02,
    "VELAC": 0.03,
    "VLDH": 0.08,
    "VHK": 0.05,
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


def _normalize_names(values: Iterable[str]) -> Tuple[str, ...]:
    return tuple(str(value).strip().upper() for value in values if str(value).strip())


def _resolve_preset(
    preset: str,
    *,
    metabolites: Optional[Sequence[str]] = None,
    reactions: Optional[Sequence[str]] = None,
) -> Tuple[Tuple[str, ...], Tuple[str, ...], Tuple[str, ...]]:
    preset_key = str(preset).strip().lower()
    if preset_key not in PRESET_CONFIG:
        valid = ", ".join(sorted(PRESET_CONFIG))
        raise ValueError(f"Unknown Phase B smoke preset '{preset}'. Expected one of: {valid}.")
    config = PRESET_CONFIG[preset_key]
    selected_metabolites = _normalize_names(metabolites or config["metabolites"])
    inference_metabolites = _normalize_names(
        selected_metabolites if metabolites is not None else config.get("inference_metabolites", selected_metabolites)
    )
    selected_reactions = _normalize_names(reactions or config["reactions"])
    if not selected_metabolites:
        raise ValueError("At least one metabolite is required.")
    if not inference_metabolites:
        raise ValueError("At least one inference metabolite is required.")
    if not selected_reactions:
        raise ValueError("At least one reaction is required.")
    return selected_metabolites, inference_metabolites, selected_reactions


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


def _candidate_reactions_for_metabolites(
    metabolites: Sequence[str],
    stoichiometry: Mapping[str, Mapping[str, float]],
) -> Tuple[str, ...]:
    measured = set(_normalize_names(metabolites))
    candidates = []
    for reaction, participants in stoichiometry.items():
        if measured.intersection(_normalize_names(participants.keys())):
            candidates.append(str(reaction).strip().upper())
    return tuple(sorted(set(candidates)))


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


def _discover_identifiable_fluxes(
    *,
    time: np.ndarray,
    states: np.ndarray,
    tracked: Mapping[str, Sequence[float]],
    metabolites: Sequence[str],
    tolerances: Mapping[str, float],
    default_tolerance: float,
) -> Dict[str, Any]:
    import rbc_stoichiometry as rs
    from flux_inference import infer_user_fluxes

    candidate_reactions = _candidate_reactions_for_metabolites(metabolites, rs.STOICHIOMETRY)
    curves = _model_curves(states, metabolites)
    inferred = infer_user_fluxes(
        curves,
        time,
        rs.STOICHIOMETRY,
        reactions=candidate_reactions,
    )

    rows = []
    accepted_reactions = []
    for reaction in candidate_reactions:
        confidence = dict(inferred["confidence"].get(reaction, {}))
        method = str(confidence.get("method", "unknown"))
        tolerance = float(tolerances.get(reaction, default_tolerance))
        row: Dict[str, Any] = {
            "reaction": reaction,
            "method": method,
            "tolerance": tolerance,
            "confidence": confidence.get("confidence"),
        }
        if reaction in inferred["fluxes"] and reaction in tracked:
            nrmse = _nrmse(inferred["fluxes"][reaction], tracked[reaction])
            max_error = _max_abs_error(inferred["fluxes"][reaction], tracked[reaction])
            accepted = bool(method == "stoichiometric_singleton" and nrmse <= tolerance)
            row.update(
                {
                    "nrmse_vs_model_flux": nrmse,
                    "max_abs_error": max_error,
                    "classification": "accepted_singleton" if accepted else "review",
                }
            )
            if accepted:
                accepted_reactions.append(reaction)
        else:
            row["classification"] = "unsupported"
        rows.append(row)

    def _sort_key(row: Mapping[str, Any]) -> Tuple[int, float, str]:
        classification_rank = 0 if row.get("classification") == "accepted_singleton" else 1
        nrmse = row.get("nrmse_vs_model_flux")
        return classification_rank, float(nrmse) if isinstance(nrmse, (int, float)) else math.inf, str(row["reaction"])

    rows = sorted(rows, key=_sort_key)
    return {
        "contract_type": "phase_b_identifiable_flux_discovery",
        "contract_version": 1,
        "target_metabolites": list(_normalize_names(metabolites)),
        "candidate_count": len(candidate_reactions),
        "accepted_reactions": sorted(accepted_reactions),
        "accepted_count": len(accepted_reactions),
        "default_tolerance": float(default_tolerance),
        "rows": rows,
    }


def run_smoke(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    preset: str = "direct",
    metabolites: Optional[Sequence[str]] = None,
    reactions: Optional[Sequence[str]] = None,
    t_max: float = 7.0,
    timepoints: int = 25,
    params_path: Optional[Path] = None,
    method: str = "LSODA",
    rtol: float = 1e-5,
    atol: float = 1e-7,
    tolerances: Optional[Mapping[str, float]] = None,
    discover_identifiable: bool = False,
    discovery_nrmse_tolerance: float = 0.08,
) -> Dict[str, Any]:
    _configure_imports()

    import rbc_stoichiometry as rs
    from flux_inference import infer_user_fluxes
    from ml_features import build_feature_payload

    resolved_tolerances = dict(DEFAULT_TOLERANCES)
    if tolerances:
        resolved_tolerances.update({str(k).strip().upper(): float(v) for k, v in tolerances.items()})
    selected_metabolites, inference_metabolites, selected_reactions = _resolve_preset(
        preset,
        metabolites=metabolites,
        reactions=reactions,
    )

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
    curves = _model_curves(states, selected_metabolites)
    inference_curves = _model_curves(states, inference_metabolites)
    tracked = _tracked_fluxes(time=time, states=states, params=params)
    inferred = infer_user_fluxes(
        inference_curves,
        time,
        rs.STOICHIOMETRY,
        reactions=selected_reactions,
    )
    comparisons, passed = _compare_fluxes(
        inferred["fluxes"],
        tracked,
        selected_reactions,
        resolved_tolerances,
    )
    feature_payload = build_feature_payload(
        curves,
        inferred["fluxes"],
        inferred["time"],
        metabolites=selected_metabolites,
        reactions=selected_reactions,
    )
    discovery = None
    if discover_identifiable:
        discovery = _discover_identifiable_fluxes(
            time=time,
            states=states,
            tracked=tracked,
            metabolites=selected_metabolites,
            tolerances=resolved_tolerances,
            default_tolerance=float(discovery_nrmse_tolerance),
        )

    payload: Dict[str, Any] = {
        "contract_type": "phase_b_model_flux_smoke_result",
        "contract_version": 1,
        "status": "passed" if passed else "failed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "brodbar_ode_flux_tracker",
        "preset": str(preset).strip().lower(),
        "solver": {
            "method": str(method),
            "rtol": float(rtol),
            "atol": float(atol),
            "t_max": float(t_max),
            "timepoints": int(timepoints),
        },
        "params_path": str(params_path) if params_path else None,
        "target_metabolites": list(selected_metabolites),
        "inference_metabolites": list(inference_metabolites),
        "reactions": list(selected_reactions),
        "time": time,
        "comparisons": comparisons,
        "inference_diagnostics": inferred["diagnostics"],
        "confidence": inferred["confidence"],
        "model_curves": curves,
        "tracked_fluxes": {reaction: tracked[reaction] for reaction in selected_reactions},
        "inferred_fluxes": {reaction: inferred["fluxes"][reaction] for reaction in selected_reactions},
        "feature_payload": {
            "contract_type": feature_payload["contract_type"],
            "contract_version": feature_payload["contract_version"],
            "feature_version": feature_payload["feature_version"],
            "schema": feature_payload["schema"],
            "values": feature_payload["values"],
            "metadata": feature_payload["metadata"],
        },
    }
    if discovery is not None:
        payload["discovery"] = discovery

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
    parser.add_argument("--preset", choices=sorted(PRESET_CONFIG), default="direct")
    parser.add_argument(
        "--discover-identifiable",
        action="store_true",
        help="Emit a discovery report for reactions identifiable from the selected metabolite panel.",
    )
    parser.add_argument(
        "--discovery-nrmse-tolerance",
        type=float,
        default=0.08,
        help="Default NRMSE tolerance for discovery reactions without an explicit per-reaction tolerance.",
    )
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
        preset=args.preset,
        t_max=args.t_max,
        timepoints=args.timepoints,
        params_path=args.params_json,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
        tolerances=tolerances,
        discover_identifiable=bool(args.discover_identifiable),
        discovery_nrmse_tolerance=float(args.discovery_nrmse_tolerance),
    )
    summary = {
        "status": payload["status"],
        "preset": payload["preset"],
        "out_path": payload["out_path"],
        "comparisons": payload["comparisons"],
        "feature_count": payload["feature_payload"]["metadata"]["feature_count"],
    }
    if "discovery" in payload:
        summary["discovery"] = {
            "candidate_count": payload["discovery"]["candidate_count"],
            "accepted_reactions": payload["discovery"]["accepted_reactions"],
        }
    print(json.dumps(_jsonable(summary), indent=2))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
