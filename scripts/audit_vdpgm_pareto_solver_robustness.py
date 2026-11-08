"""Compare standard and strict-solver vmax_VDPGM Pareto refinements."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STANDARD = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "vmax_vdpgm_qss_b13pg_pareto_refinement_J1_J46"
    / "summary.json"
)
DEFAULT_STRICT = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "vmax_vdpgm_qss_b13pg_pareto_refinement_J1_J46_solver_check"
    / "summary.json"
)
DEFAULT_OUT_DIR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "vmax_vdpgm_qss_b13pg_pareto_refinement_J1_J46"
    / "solver_robustness"
)
METRICS = (
    "B23PG_nrmse",
    "B23PG_endpoint_error",
    "B23PG_slope_nrmse",
    "F6P_nrmse",
    "GLC_nrmse",
    "ELAC_nrmse",
    "ideal_distance",
)


def _rows_by_multiplier(payload: Mapping[str, Any]) -> dict[float, Mapping[str, Any]]:
    return {float(row["multiplier"]): row for row in payload["pareto_rows"]}


def _compare(
    standard: Mapping[str, Any], strict: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    standard_rows = _rows_by_multiplier(standard)
    strict_rows = _rows_by_multiplier(strict)
    if set(standard_rows) != set(strict_rows):
        raise ValueError("Solver robustness comparison requires identical multiplier grids")
    rows = []
    for multiplier in sorted(standard_rows):
        base = standard_rows[multiplier]
        check = strict_rows[multiplier]
        for metric in METRICS:
            standard_value = float(base[metric])
            strict_value = float(check[metric])
            rows.append(
                {
                    "multiplier": multiplier,
                    "metric": metric,
                    "standard_value": standard_value,
                    "strict_value": strict_value,
                    "absolute_difference": strict_value - standard_value,
                    "relative_absolute_difference": abs(strict_value - standard_value)
                    / max(abs(standard_value), 1e-30),
                }
            )
    standard_selection = standard["selection"]
    strict_selection = strict["selection"]
    summary = {
        "standard_selected_candidate": standard_selection["selected_candidate"],
        "strict_selected_candidate": strict_selection["selected_candidate"],
        "selection_invariant": standard_selection["selected_candidate"]
        == strict_selection["selected_candidate"],
        "standard_interior_improvement_fraction": float(
            standard_selection["interior_improvement_fraction"]
        ),
        "strict_interior_improvement_fraction": float(
            strict_selection["interior_improvement_fraction"]
        ),
        "maximum_relative_metric_difference": max(
            row["relative_absolute_difference"] for row in rows
        ),
    }
    return rows, summary


def run_audit(
    *, standard_path: Path, strict_path: Path, out_dir: Path
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    standard = json.loads(standard_path.read_text(encoding="utf-8"))
    strict = json.loads(strict_path.read_text(encoding="utf-8"))
    rows, comparison = _compare(standard, strict)
    pd.DataFrame(rows).to_csv(out_dir / "solver_metric_comparison.csv", index=False)
    decision = (
        "retain the 3x diagnostic Pareto anchor as solver-robust"
        if comparison["selection_invariant"]
        else "reject a solver-dependent Pareto selection"
    )
    summary = {
        "contract_type": "vmax_VDPGM_pareto_solver_robustness_audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "standard_summary_path": str(standard_path),
        "strict_summary_path": str(strict_path),
        "standard_solver": {"rtol": 3e-4, "atol": 1e-6},
        "strict_solver": {"rtol": 1e-5, "atol": 1e-8},
        **comparison,
        "decision": decision,
        "parameters_promoted": False,
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "report": str(out_dir / "decision_report.md"),
            "metrics": str(out_dir / "solver_metric_comparison.csv"),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    report = [
        "# vmax_VDPGM Pareto solver robustness",
        "",
        f"- Standard selection: `{comparison['standard_selected_candidate']}`.",
        f"- Strict-solver selection: `{comparison['strict_selected_candidate']}`.",
        f"- Standard improvement over best anchor: `{100.0 * comparison['standard_interior_improvement_fraction']:.3g}%`.",
        f"- Strict improvement over best anchor: `{100.0 * comparison['strict_interior_improvement_fraction']:.3g}%`.",
        f"- Maximum relative difference among compared metrics: `{100.0 * comparison['maximum_relative_metric_difference']:.3g}%`.",
        "",
        f"**{decision}**",
        "",
        "The strict replay is a numerical robustness check, not an independent biological validation. No parameter was promoted.",
    ]
    (out_dir / "decision_report.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"comparison": comparison, "decision": decision}, indent=2))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--standard", type=Path, default=DEFAULT_STANDARD)
    parser.add_argument("--strict", type=Path, default=DEFAULT_STRICT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_audit(standard_path=args.standard, strict_path=args.strict, out_dir=args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
