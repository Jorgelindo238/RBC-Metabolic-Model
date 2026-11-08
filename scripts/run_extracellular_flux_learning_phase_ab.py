"""Run extracellular flux-learning Phases A and B.

Phase A builds teacher-flux targets for the measured extracellular Bordbar
panel. Phase B runs a conservative pilot calibration focused on EGLC/ELAC and
energy protection, using flux supervision from the Phase A dataset.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
DEFAULT_OUT_DIR = ROOT / "Simulations" / "brodbar" / "hermes" / "extracellular_flux_phase_ab"
DEFAULT_PHASE_B_TEACHER_METABOLITES = ("EGLC", "ELAC")
DEFAULT_PHASE_B_TARGET_METABOLITES = (
    "EGLC",
    "ELAC",
    "GLC",
    "LAC",
    "ATP",
    "ADP",
    "AMP",
    "B23PG",
    "PEP",
    "PYR",
)


def _configure_imports() -> None:
    for path in (str(ROOT), str(SRC_DIR)):
        if path not in sys.path:
            sys.path.insert(0, path)


def _normalize_names(values: Iterable[str] | str | None) -> tuple[str, ...]:
    if values is None:
        return tuple()
    if isinstance(values, str):
        values = [part.strip() for part in values.split(",")]
    return tuple(str(value).strip().upper() for value in values if str(value).strip())


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
    if isinstance(value, Path):
        return str(value)
    return value


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _parse_weight_map(value: Mapping[str, float] | str | None) -> dict[str, float]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return {str(name).strip().upper(): float(weight) for name, weight in value.items()}
    out: dict[str, float] = {}
    for item in str(value).split(","):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError("Weight maps must be formatted NAME=value,NAME=value")
        name, raw_weight = item.split("=", 1)
        out[str(name).strip().upper()] = float(raw_weight)
    return out


def _summarize_teacher_dataset(dataset: Mapping[str, Any]) -> dict[str, Any]:
    reactions = sorted((dataset.get("reaction_flux_curves") or {}).keys())
    diagnostics = {}
    for reaction_name, entry in (dataset.get("reaction_flux_curves") or {}).items():
        if isinstance(entry, dict):
            diagnostics[reaction_name] = entry.get("diagnostics", {})
    return {
        "target_count": len(dataset.get("target_metabolites", [])),
        "targets": list(dataset.get("target_metabolites", [])),
        "reaction_count": len(reactions),
        "reactions": reactions,
        "diagnostics": diagnostics,
    }


def run_phase_ab(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    dense_points: int = 200,
    skip_calibration: bool = False,
    phase_b_teacher_metabolites: Sequence[str] = DEFAULT_PHASE_B_TEACHER_METABOLITES,
    phase_b_target_metabolites: Sequence[str] = DEFAULT_PHASE_B_TARGET_METABOLITES,
    target_scope: str = "glycolysis_extracellular",
    param_scope: str = "glycolysis_terminal",
    optimization_strategy: str = "vmax_then_km",
    n_trials: int = 8,
    global_trials: int = 0,
    t_max: float = 46.0,
    load_params: Optional[Path] = None,
    teacher_flux_weight: float = 0.5,
    teacher_target_weights: Mapping[str, float] | str | None = None,
    teacher_focus_weight: float = 4.0,
    atp_focus: bool = True,
    min_eglc_depletion_frac: float | None = 0.05,
    seed: int = 42,
    generate_plots: bool = False,
    dump_trajectories: bool = False,
) -> dict[str, Any]:
    _configure_imports()

    import MM_calibration as mm
    from extracellular_teacher_flux import (
        EXTRACELLULAR_TEACHER_METABOLITES,
        build_bordbar_extracellular_teacher_flux_dataset,
    )

    out_dir = Path(out_dir)
    phase_a_dir = out_dir / "phase_a_teacher_flux"
    phase_b_dir = out_dir / "phase_b_eglc_elac_energy_calibration"
    phase_a_dataset_path = phase_a_dir / "teacher_flux_dataset.json"
    phase_b_dataset_path = phase_b_dir / "teacher_flux_dataset.json"

    phase_a_dataset = build_bordbar_extracellular_teacher_flux_dataset(
        metabolite_names=EXTRACELLULAR_TEACHER_METABOLITES,
        dense_points=int(dense_points),
        out_path=phase_a_dataset_path,
        dataset_label="teacher_flux_bordbar_all_extracellular",
    )

    selected_teacher_metabolites = _normalize_names(phase_b_teacher_metabolites) or DEFAULT_PHASE_B_TEACHER_METABOLITES
    phase_b_dataset = build_bordbar_extracellular_teacher_flux_dataset(
        metabolite_names=selected_teacher_metabolites,
        dense_points=int(dense_points),
        out_path=phase_b_dataset_path,
        dataset_label="teacher_flux_phase_b_" + "_".join(name.lower() for name in selected_teacher_metabolites),
    )

    calibration_summary: dict[str, Any] | None = None
    if not skip_calibration:
        calibration_params, final_loss, trajectory_csv_path = mm.run_calibration(
            phases=[1],
            n_trials=int(n_trials),
            global_trials=int(global_trials),
            load_params=str(load_params) if load_params else None,
            target_scope=str(target_scope),
            param_scope=str(param_scope),
            optimization_strategy=str(optimization_strategy),
            target_metabolites=list(_normalize_names(phase_b_target_metabolites) or DEFAULT_PHASE_B_TARGET_METABOLITES),
            t_max=float(t_max),
            curve_fit_strength=0.0,
            out_dir=phase_b_dir,
            generate_plots=bool(generate_plots),
            atp_focus=bool(atp_focus),
            atp_floor=0.15,
            adp_floor=0.05,
            amp_floor=0.04,
            imp_floor=0.02,
            adenylate_target=0.65,
            teacher_dataset_path=str(phase_b_dataset_path),
            teacher_curve_weight=0.0,
            teacher_flux_weight=float(teacher_flux_weight),
            teacher_target_weights=_parse_weight_map(teacher_target_weights),
            teacher_focus_metabolites=list(selected_teacher_metabolites),
            teacher_focus_weight=float(teacher_focus_weight),
            min_eglc_depletion_frac=(
                None if min_eglc_depletion_frac is None else float(min_eglc_depletion_frac)
            ),
            seed=int(seed),
            dump_trajectories=bool(dump_trajectories),
        )
        report_path = phase_b_dir / "calibration_report.json"
        calibration_summary = {
            "status": "completed",
            "out_dir": str(phase_b_dir),
            "final_loss": float(final_loss),
            "optimized_param_count": len(calibration_params),
            "optimized_params": calibration_params,
            "trajectory_csv_path": str(trajectory_csv_path) if trajectory_csv_path else None,
            "report_path": str(report_path) if report_path.exists() else None,
            "report": _read_json(report_path) if report_path.exists() else None,
        }

    payload = {
        "contract_type": "extracellular_flux_learning_phase_ab_result",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "out_dir": str(out_dir),
        "phase_a": {
            "status": "completed",
            "dataset_path": str(phase_a_dataset_path),
            "dataset_summary": _summarize_teacher_dataset(phase_a_dataset),
        },
        "phase_b": {
            "status": "skipped" if skip_calibration else "completed",
            "teacher_dataset_path": str(phase_b_dataset_path),
            "teacher_dataset_summary": _summarize_teacher_dataset(phase_b_dataset),
            "target_metabolites": list(_normalize_names(phase_b_target_metabolites) or DEFAULT_PHASE_B_TARGET_METABOLITES),
            "target_scope": str(target_scope),
            "param_scope": str(param_scope),
            "optimization_strategy": str(optimization_strategy),
            "teacher_flux_weight": float(teacher_flux_weight),
            "teacher_target_weights": _parse_weight_map(teacher_target_weights),
            "teacher_focus_weight": float(teacher_focus_weight),
            "atp_focus": bool(atp_focus),
            "min_eglc_depletion_frac": (
                None if min_eglc_depletion_frac is None else float(min_eglc_depletion_frac)
            ),
            "calibration": calibration_summary,
        },
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "phase_ab_summary.json"
    payload["summary_path"] = str(summary_path)
    summary_path.write_text(json.dumps(_jsonable(payload), indent=2), encoding="utf-8")
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run extracellular flux-learning Phases A and B")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--dense-points", type=int, default=200)
    parser.add_argument("--skip-calibration", action="store_true")
    parser.add_argument(
        "--phase-b-teacher-metabolites",
        default=",".join(DEFAULT_PHASE_B_TEACHER_METABOLITES),
        help="Comma-separated extracellular teacher metabolites for the Phase B pilot.",
    )
    parser.add_argument(
        "--phase-b-target-metabolites",
        default=",".join(DEFAULT_PHASE_B_TARGET_METABOLITES),
        help="Comma-separated concentration targets for the Phase B pilot.",
    )
    parser.add_argument("--n-trials", type=int, default=8)
    parser.add_argument("--global-trials", type=int, default=0)
    parser.add_argument("--t-max", type=float, default=46.0)
    parser.add_argument("--load-params", type=Path)
    parser.add_argument("--target-scope", default="glycolysis_extracellular")
    parser.add_argument("--param-scope", default="glycolysis_terminal")
    parser.add_argument("--optimization-strategy", default="vmax_then_km")
    parser.add_argument("--teacher-flux-weight", type=float, default=0.5)
    parser.add_argument(
        "--teacher-target-weights",
        default="",
        help="Comma-separated flux teacher weights, e.g. EGLC=6,ELAC=2.",
    )
    parser.add_argument("--teacher-focus-weight", type=float, default=4.0)
    parser.add_argument("--no-atp-focus", action="store_true")
    parser.add_argument("--min-eglc-depletion-frac", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--generate-plots", action="store_true")
    parser.add_argument("--dump-trajectories", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    payload = run_phase_ab(
        out_dir=args.out_dir,
        dense_points=args.dense_points,
        skip_calibration=bool(args.skip_calibration),
        phase_b_teacher_metabolites=_normalize_names(args.phase_b_teacher_metabolites),
        phase_b_target_metabolites=_normalize_names(args.phase_b_target_metabolites),
        target_scope=args.target_scope,
        param_scope=args.param_scope,
        optimization_strategy=args.optimization_strategy,
        n_trials=args.n_trials,
        global_trials=args.global_trials,
        t_max=args.t_max,
        load_params=args.load_params,
        teacher_flux_weight=args.teacher_flux_weight,
        teacher_target_weights=args.teacher_target_weights,
        teacher_focus_weight=args.teacher_focus_weight,
        atp_focus=not bool(args.no_atp_focus),
        min_eglc_depletion_frac=args.min_eglc_depletion_frac,
        seed=args.seed,
        generate_plots=bool(args.generate_plots),
        dump_trajectories=bool(args.dump_trajectories),
    )
    print(
        json.dumps(
            {
                "summary_path": payload["summary_path"],
                "phase_a_targets": payload["phase_a"]["dataset_summary"]["target_count"],
                "phase_a_reactions": payload["phase_a"]["dataset_summary"]["reaction_count"],
                "phase_b_status": payload["phase_b"]["status"],
                "phase_b_teacher_reactions": payload["phase_b"]["teacher_dataset_summary"]["reactions"],
                "phase_b_final_loss": (
                    payload["phase_b"]["calibration"]["final_loss"]
                    if payload["phase_b"]["calibration"]
                    else None
                ),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
