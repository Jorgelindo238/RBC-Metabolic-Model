"""
Minimal teacher-flux sandbox for Hermes-driven hybrid kinetics work.

This keeps the loop intentionally simple:
1. Build pure-fit teacher flux curves from experimental data.
2. Swap selected ODE reactions to those teacher fluxes.
3. Distill MM / Hill kinetics back from the recovered teacher flux traces.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from src.teacher_flux_bridge import (
    build_teacher_flux_dataset,
    distill_teacher_flux_kinetics,
    write_teacher_override_params,
)
from src.teacher_flux_autoresearch_glucose import run_glucose_autoresearch


ROOT = Path(__file__).resolve().parents[2]


def prepare_teacher_flux_sandbox(
    *,
    seed_params_path: Path,
    out_root: Path,
    metabolites: Iterable[str] = ("EGLC", "ELAC"),
    reactions: Iterable[str] = ("VEGLC", "VELAC"),
) -> dict:
    out_root = Path(out_root)
    dataset_path = out_root / "teacher_flux_dataset.json"
    params_path = out_root / "teacher_override_params.json"

    dataset = build_teacher_flux_dataset(metabolite_names=metabolites, out_path=dataset_path)
    params = write_teacher_override_params(
        Path(seed_params_path),
        dataset_path,
        params_path,
        reactions=reactions,
    )

    summary = {
        "dataset_path": str(dataset_path),
        "params_path": str(params_path),
        "targets": list(dataset.get("target_metabolites", [])),
        "reactions": list(reactions),
        "teacher_flux_dataset_path": params.get("teacher_flux_dataset_path"),
    }
    (out_root / "sandbox_prepare_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def distill_from_teacher_run(
    *,
    state_csv_path: Path,
    flux_csv_path: Path,
    out_root: Path,
) -> dict:
    report = distill_teacher_flux_kinetics(
        state_csv_path=Path(state_csv_path),
        flux_csv_path=Path(flux_csv_path),
        out_dir=Path(out_root),
    )
    return report


def run_glucose_teacher_autoresearch(
    *,
    seed_params_path: Path,
    out_root: Path,
    budget_per_family_seconds: float = 45.0,
    rng_seed: int = 29,
) -> dict:
    return run_glucose_autoresearch(
        seed_params_path=Path(seed_params_path),
        out_root=Path(out_root),
        budget_per_family_seconds=budget_per_family_seconds,
        rng_seed=rng_seed,
    )
