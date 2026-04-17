"""
Explicit teacher-flux cycle for one or more reactions.

Workflow:
1. Build a teacher flux dataset directly from experimental curves.
2. Override selected ODE reactions with teacher-driven fluxes.
3. Run the full ODE with those overrides.
4. Distill MM / Hill kinetics back from the recovered teacher flux traces.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.teacher_flux_bridge import (
    build_teacher_flux_dataset,
    distill_teacher_flux_kinetics,
    write_teacher_override_params,
)


MAIN = ROOT / "src" / "main.py"
MODEL_METABOLITES = ROOT / "Simulations" / "brodbar" / "metabolites" / "all_metabolites.csv"
MODEL_FLUXES = ROOT / "Simulations" / "brodbar" / "fluxes" / "reaction_fluxes.csv"


def _run_main_and_capture(params_path: Path, out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, str(MAIN), "--model", "brodbar", "--load-params", str(params_path)],
        cwd=ROOT,
        check=True,
    )
    state_copy = out_dir / "teacher_all_metabolites.csv"
    flux_copy = out_dir / "teacher_reaction_fluxes.csv"
    shutil.copy2(MODEL_METABOLITES, state_copy)
    shutil.copy2(MODEL_FLUXES, flux_copy)
    return {
        "states": str(state_copy),
        "fluxes": str(flux_copy),
    }


def run_explicit_teacher_cycle(
    *,
    seed_params_path: Path,
    out_dir: Path,
    metabolites: list[str],
    reactions: list[str],
    dense_points: int = 200,
    auxiliary_flux_csv_path: Path | None = None,
) -> dict[str, object]:
    out_dir = Path(out_dir)
    dataset_path = out_dir / "teacher_flux_dataset.json"
    override_params_path = out_dir / "teacher_override_params.json"
    teacher_run_dir = out_dir / "teacher_run"
    distill_dir = out_dir / "distillation"

    dataset = build_teacher_flux_dataset(
        metabolite_names=metabolites,
        dense_points=dense_points,
        auxiliary_flux_csv_path=auxiliary_flux_csv_path,
        out_path=dataset_path,
    )
    override_params = write_teacher_override_params(
        Path(seed_params_path),
        dataset_path,
        override_params_path,
        reactions=reactions,
    )
    teacher_artifacts = _run_main_and_capture(override_params_path, teacher_run_dir)
    report = distill_teacher_flux_kinetics(
        state_csv_path=Path(teacher_artifacts["states"]),
        flux_csv_path=Path(teacher_artifacts["fluxes"]),
        out_dir=distill_dir,
        base_params_path=Path(seed_params_path),
    )

    summary = {
        "contract_type": "explicit_teacher_flux_cycle_summary",
        "contract_version": 1,
        "seed_params_path": str(seed_params_path),
        "teacher_dataset_path": str(dataset_path),
        "teacher_override_params_path": str(override_params_path),
        "teacher_targets": list(dataset.get("target_metabolites", [])),
        "teacher_reactions": list(reactions),
        "auxiliary_flux_csv_path": str(auxiliary_flux_csv_path) if auxiliary_flux_csv_path is not None else None,
        "teacher_run_artifacts": teacher_artifacts,
        "distillation_report_path": str(distill_dir / "teacher_flux_distillation_report.json"),
        "recommended_params_path": str(distill_dir / "teacher_flux_recommended_params.json"),
        "best_families": {name: payload["best_family"] for name, payload in report.get("reactions", {}).items()},
        "velac_recommended_params": report.get("reactions", {}).get("VELAC", {}).get("recommended_params"),
        "vldh_recommended_params": report.get("reactions", {}).get("VLDH", {}).get("recommended_params"),
        "override_param_count": len(override_params),
    }
    (out_dir / "explicit_teacher_flux_cycle_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an explicit teacher-flux cycle and distill kinetics back")
    parser.add_argument("--seed-params", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--metabolites", default="ELAC")
    parser.add_argument("--reactions", default="VELAC")
    parser.add_argument("--dense-points", type=int, default=200)
    parser.add_argument("--aux-flux-csv")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    summary = run_explicit_teacher_cycle(
        seed_params_path=Path(args.seed_params),
        out_dir=Path(args.out_dir),
        metabolites=[name.strip() for name in args.metabolites.split(",") if name.strip()],
        reactions=[name.strip() for name in args.reactions.split(",") if name.strip()],
        dense_points=int(args.dense_points),
        auxiliary_flux_csv_path=Path(args.aux_flux_csv) if args.aux_flux_csv else None,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
