"""Build and score the three-block sequential FLA temporal contract."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
SCRIPT_DIR = ROOT / "scripts"
DEFAULT_OUT_DIR = ROOT / "output" / "fla_temporal_contract_2026_08_11"
SEED_PARAMS = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "vpep_vpk_coupled_mild_feedback_46d_n20"
    / "seed_fixed_params.json"
)

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from equadiff_brodbar import BRODBAR_METABOLITE_MAP, MODEL_NETWORK_VERSION  # noqa: E402
from fla_temporal_contract import (  # noqa: E402
    NON_INDEPENDENT_STATE_TARGETS,
    REACTION_TEACHER_EXCLUSIONS,
    TEMPORAL_BLOCKS,
    block_mask,
    promotion_contract,
)
from MM_calibration import load_initial_conditions  # noqa: E402
from evaluate_brodbar_candidate_full_panel import (  # noqa: E402
    _load_brodbar_panel,
    _load_params,
    _simulate,
)


def _normalized_rmse(model: np.ndarray, teacher: np.ndarray) -> float:
    scale = max(float(np.mean(np.abs(teacher))), 0.01)
    return float(np.sqrt(np.mean((model - teacher) ** 2)) / scale)


def _score_blocks(
    *,
    solution: Any,
    time_exp: np.ndarray,
    curves: Mapping[str, np.ndarray],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for block in TEMPORAL_BLOCKS:
        mask = block_mask(solution.t, block)
        local_time = np.asarray(solution.t, dtype=float)[mask]
        for metabolite in block.concentration_targets:
            if metabolite in NON_INDEPENDENT_STATE_TARGETS or metabolite not in curves:
                continue
            teacher = PchipInterpolator(time_exp, curves[metabolite])(local_time)
            model = np.asarray(
                solution.y[int(BRODBAR_METABOLITE_MAP[metabolite])], dtype=float
            )[mask]
            rows.append(
                {
                    "block": block.name,
                    "metabolite": metabolite,
                    "start_day": block.start_day,
                    "end_day": block.end_day,
                    "nrmse": _normalized_rmse(model, teacher),
                    "model_start_mM": float(model[0]),
                    "model_end_mM": float(model[-1]),
                    "teacher_start_mM": float(teacher[0]),
                    "teacher_end_mM": float(teacher[-1]),
                }
            )
    return rows


def run_contract(
    *,
    out_dir: Path,
    dense_points: int,
    method: str,
    rtol: float,
    atol: float,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    params = _load_params(SEED_PARAMS)
    params["sam_adenylate_stoichiometry"] = "biochemical_transfer"
    time_exp, curves, _, _, _ = _load_brodbar_panel()
    solution = _simulate(
        x0=np.asarray(load_initial_conditions(), dtype=float),
        params=params,
        time_exp=time_exp,
        dense_points=dense_points,
        method=method,
        rtol=rtol,
        atol=atol,
    )
    rows = _score_blocks(solution=solution, time_exp=time_exp, curves=curves)
    frame = pd.DataFrame(rows)
    frame.to_csv(out_dir / "seed_temporal_block_metrics.csv", index=False)
    block_summary = []
    for block in TEMPORAL_BLOCKS:
        local = frame.loc[frame["block"] == block.name]
        block_summary.append(
            {
                "block": block.name,
                "mean_nrmse": float(local["nrmse"].mean()),
                "median_nrmse": float(local["nrmse"].median()),
                "worst_metabolite": str(local.loc[local["nrmse"].idxmax(), "metabolite"]),
                "worst_nrmse": float(local["nrmse"].max()),
            }
        )
    summary = {
        "contract_type": "sequential_fla_temporal_blocks",
        "contract_version": 1,
        "model_network_version": MODEL_NETWORK_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "blocks": promotion_contract(),
        "non_independent_state_targets": sorted(NON_INDEPENDENT_STATE_TARGETS),
        "reaction_teacher_exclusions": sorted(REACTION_TEACHER_EXCLUSIONS),
        "seed_params_path": str(SEED_PARAMS),
        "seed_block_summary": block_summary,
        "optimization_performed": False,
        "promotion_order": [block.name for block in TEMPORAL_BLOCKS],
        "decision": "use sequential block ownership and cumulative guards for every future FLA calibration",
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "metrics": str(out_dir / "seed_temporal_block_metrics.csv"),
            "report": str(out_dir / "decision_report.md"),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    lines = [
        "# Sequential FLA temporal contract",
        "",
        "Future calibration proceeds J1-J3, then J3-J10, then J10-J46. A later block cannot compensate for a failed earlier block.",
        "",
        "| Block | Mean nRMSE | Median nRMSE | Worst target |",
        "|---|---:|---:|---|",
    ]
    for row in block_summary:
        lines.append(
            f"| `{row['block']}` | {row['mean_nrmse']:.4f} | {row['median_nrmse']:.4f} | "
            f"{row['worst_metabolite']} ({row['worst_nrmse']:.4f}) |"
        )
    lines.extend(
        [
            "",
            "B13PG and P2G are excluded as non-independent state targets. P2G/P3G are excluded from reaction-level teacher assignment.",
            "",
            "No parameter was optimized or promoted in this contract build.",
        ]
    )
    (out_dir / "decision_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"blocks": block_summary, "summary": str(out_dir / "summary.json")}, indent=2))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--dense-points", type=int, default=451)
    parser.add_argument("--method", default="BDF")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_contract(
        out_dir=args.out_dir,
        dense_points=args.dense_points,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
