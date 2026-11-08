"""Refine the guarded 2x-4x vmax_VDPGM interval with a Pareto screen."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
SCRIPT_DIR = ROOT / "scripts"
DEFAULT_OUT_DIR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "vmax_vdpgm_qss_b13pg_pareto_refinement_J1_J46"
)

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from audit_b23pg_balance_qss_context import QSS_LABEL, _build_state_contract  # noqa: E402
from equadiff_brodbar import MODEL_NETWORK_VERSION  # noqa: E402
from evaluate_brodbar_candidate_full_panel import _load_brodbar_panel  # noqa: E402
from profile_glycolysis_flux_bottlenecks import _jsonable  # noqa: E402
from screen_vmax_vdpgm_qss_b13pg import (  # noqa: E402
    PRIMARY_END_DAY,
    RELAY_END_DAY,
    STORAGE_END_DAY,
    _candidate_params,
    _extension_guards,
    _label,
    _load_teachers,
    _replay,
    _short_guards,
)


REFINEMENT_MULTIPLIERS = (2.0, 2.5, 3.0, 3.5, 4.0)
REFERENCE_MULTIPLIER = 1.0
MIN_INTERIOR_IMPROVEMENT = 0.05
B23PG_OBJECTIVES = (
    "B23PG_nrmse",
    "B23PG_endpoint_error",
    "B23PG_slope_nrmse",
)
TRANSFER_OBJECTIVES = ("F6P_nrmse", "GLC_nrmse", "ELAC_nrmse")


def _flatten_metrics(row: Mapping[str, Any]) -> dict[str, float]:
    concentrations = row["concentration_metrics"]
    return {
        "B23PG_nrmse": float(concentrations["B23PG"]["nrmse"]),
        "B23PG_endpoint_error": float(concentrations["B23PG"]["endpoint_error"]),
        "B23PG_slope_nrmse": float(row["B23PG_slope_nrmse"]),
        "F6P_nrmse": float(concentrations["F6P"]["nrmse"]),
        "GLC_nrmse": float(concentrations["GLC"]["nrmse"]),
        "ELAC_nrmse": float(concentrations["ELAC"]["nrmse"]),
        "whole_panel_mean_nrmse": float(row["whole_panel_mean_nrmse"]),
        "whole_panel_median_nrmse": float(row["whole_panel_median_nrmse"]),
    }


def _pareto_mask(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    retained = np.ones(values.shape[0], dtype=bool)
    for index, row in enumerate(values):
        dominated = np.any(
            np.all(values <= row + 1e-12, axis=1)
            & np.any(values < row - 1e-12, axis=1)
        )
        retained[index] = not dominated
    return retained


def _normalize_objectives(frame: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    normalized = pd.DataFrame(index=frame.index)
    for column in columns:
        values = frame[column].to_numpy(dtype=float)
        span = float(np.max(values) - np.min(values))
        normalized[column] = 0.0 if span <= 1e-15 else (values - np.min(values)) / span
    return normalized


def _rank_pareto(rows: Sequence[Mapping[str, Any]]) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = pd.DataFrame(rows).sort_values("multiplier").reset_index(drop=True)
    objective_columns = (*B23PG_OBJECTIVES, *TRANSFER_OBJECTIVES)
    normalized = _normalize_objectives(frame, objective_columns)
    frame["B23PG_objective_score"] = normalized[list(B23PG_OBJECTIVES)].mean(axis=1)
    frame["transfer_cost_score"] = normalized[list(TRANSFER_OBJECTIVES)].mean(axis=1)
    frame["ideal_distance"] = np.sqrt(
        frame["B23PG_objective_score"] ** 2 + frame["transfer_cost_score"] ** 2
    )
    frame["pareto_nondominated"] = _pareto_mask(
        frame[list(objective_columns)].to_numpy(dtype=float)
    )
    eligible = frame.loc[frame["all_temporal_guards_pass"] & frame["pareto_nondominated"]]
    if eligible.empty:
        return frame, {
            "selected_candidate": None,
            "selection_reason": "no candidate passed all temporal guards on the non-dominated front",
            "interior_improvement_fraction": None,
        }
    best_index = eligible.sort_values(["ideal_distance", "multiplier"]).index[0]
    selected = frame.loc[best_index]
    anchor_distances = frame.loc[
        frame["multiplier"].isin((2.0, 4.0)), "ideal_distance"
    ].to_numpy(dtype=float)
    best_anchor = float(np.min(anchor_distances))
    improvement = (best_anchor - float(selected["ideal_distance"])) / max(best_anchor, 1e-30)
    is_interior = 2.0 < float(selected["multiplier"]) < 4.0
    retained = bool(is_interior and improvement >= MIN_INTERIOR_IMPROVEMENT)
    return frame, {
        "selected_candidate": str(selected["candidate"]) if retained else None,
        "computational_knee": str(selected["candidate"]),
        "computational_knee_multiplier": float(selected["multiplier"]),
        "computational_knee_distance": float(selected["ideal_distance"]),
        "best_anchor_distance": best_anchor,
        "interior_improvement_fraction": improvement,
        "minimum_required_improvement_fraction": MIN_INTERIOR_IMPROVEMENT,
        "selection_reason": (
            "interior knee improves the normalized six-objective compromise over both anchors"
            if retained
            else "no interior knee improves the best anchor by the predeclared 5% margin"
        ),
    }


def _plot(
    *,
    frame: pd.DataFrame,
    storage_frames: Mapping[str, pd.DataFrame],
    selected: str | None,
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 9), constrained_layout=True)
    colors = plt.get_cmap("viridis")
    for index, multiplier in enumerate(REFINEMENT_MULTIPLIERS):
        label = _label(multiplier)
        trajectory = storage_frames[label]
        color = colors(index / (len(REFINEMENT_MULTIPLIERS) - 1))
        width = 2.8 if label == selected else 1.4
        axes[0, 0].plot(
            trajectory["time_day"], trajectory["B23PG"],
            color=color, linewidth=width, label=f"{multiplier:g}x",
        )
        axes[0, 1].plot(
            trajectory["time_day"], trajectory["F6P"],
            color=color, linewidth=width, label=f"{multiplier:g}x",
        )
    reference = storage_frames[_label(2.0)]
    axes[0, 0].plot(reference["time_day"], reference["B23PG_teacher"], "k--", linewidth=2, label="teacher")
    axes[0, 1].plot(reference["time_day"], reference["F6P_teacher"], "k--", linewidth=2, label="teacher")

    scatter = axes[1, 0].scatter(
        frame["transfer_cost_score"],
        frame["B23PG_objective_score"],
        c=frame["multiplier"], cmap="viridis", s=75, edgecolor="#111827",
    )
    for row in frame.itertuples():
        axes[1, 0].annotate(f"{row.multiplier:g}x", (row.transfer_cost_score, row.B23PG_objective_score), xytext=(4, 4), textcoords="offset points")
    fig.colorbar(scatter, ax=axes[1, 0], label="vmax_VDPGM multiplier")
    axes[1, 0].set_xlabel("Normalized F6P/GLC/ELAC transfer cost")
    axes[1, 0].set_ylabel("Normalized B23PG objective")

    axes[1, 1].plot(frame["multiplier"], frame["ideal_distance"], "o-", color="#2563eb", label="ideal distance")
    if selected is not None:
        selected_row = frame.loc[frame["candidate"] == selected].iloc[0]
        axes[1, 1].scatter([selected_row["multiplier"]], [selected_row["ideal_distance"]], s=130, marker="*", color="#b91c1c", label="retained knee", zorder=4)
    axes[1, 1].set_xlabel("vmax_VDPGM multiplier")
    axes[1, 1].set_ylabel("Six-objective ideal distance")
    axes[1, 1].legend(frameon=False)
    axes[0, 0].set_title("B23PG over J1-J46")
    axes[0, 1].set_title("F6P transfer guard")
    axes[1, 0].set_title("Pareto objective plane")
    axes[1, 1].set_title("Predeclared compromise score")
    axes[0, 0].set_ylabel("mM")
    axes[0, 1].set_ylabel("mM")
    for axis in axes.flat:
        axis.grid(alpha=0.22)
    axes[0, 0].legend(frameon=False, fontsize=7)
    axes[0, 1].legend(frameon=False, fontsize=7)
    fig.suptitle("QSS-B13PG vmax_VDPGM Pareto refinement")
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    lines = [
        "# QSS-B13PG vmax_VDPGM Pareto refinement",
        "",
        "Only `vmax_VDPGM` varied over `2x, 2.5x, 3x, 3.5x, 4x`. Every point was replayed through J1-J3, J1-J10, and J1-J46 under the existing cumulative guards.",
        "",
        "| Multiplier | B23PG nRMSE | B23PG endpoint | B23PG slope | F6P nRMSE | GLC nRMSE | ELAC nRMSE | Ideal distance | Guards |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary["pareto_rows"]:
        lines.append(
            f"| {row['multiplier']:.3g}x | {row['B23PG_nrmse']:.5g} | "
            f"{row['B23PG_endpoint_error']:.5g} | {row['B23PG_slope_nrmse']:.5g} | "
            f"{row['F6P_nrmse']:.5g} | {row['GLC_nrmse']:.5g} | {row['ELAC_nrmse']:.5g} | "
            f"{row['ideal_distance']:.5g} | {row['all_temporal_guards_pass']} |"
        )
    selection = summary["selection"]
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"Computational knee: `{selection.get('computational_knee')}`.",
            f"Improvement over the best endpoint anchor: `{100.0 * float(selection.get('interior_improvement_fraction') or 0.0):.3g}%`.",
            "",
            f"**{summary['decision']}**",
            "",
            summary["decision_rationale"],
            "",
            f"Next: {summary['next_step']}",
            "",
            "No parameter was promoted.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_refinement(
    *,
    out_dir: Path,
    short_points: int,
    relay_points: int,
    storage_points: int,
    method: str,
    rtol: float,
    atol: float,
    closure_tolerance: float,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    states, seed_params, seed_path = _build_state_contract()
    qss_state = np.asarray(states[QSS_LABEL], dtype=float)
    experimental_time, teacher_values, teachers = _load_teachers()
    _, panel_curves, _, panel_indices, _ = _load_brodbar_panel()
    multipliers = (REFERENCE_MULTIPLIER, *REFINEMENT_MULTIPLIERS)
    parameter_sets = {
        _label(multiplier): _candidate_params(seed_params, multiplier)[0]
        for multiplier in multipliers
    }
    horizons = {
        "J1_J3": np.linspace(1.0, PRIMARY_END_DAY, int(short_points)),
        "J1_J10": np.linspace(1.0, RELAY_END_DAY, int(relay_points)),
        "J1_J46": np.unique(
            np.concatenate(
                [np.linspace(1.0, STORAGE_END_DAY, int(storage_points)), experimental_time]
            )
        ),
    }
    frames: dict[str, dict[str, pd.DataFrame]] = {name: {} for name in horizons}
    metrics: dict[str, dict[str, dict[str, Any]]] = {name: {} for name in horizons}
    for horizon, time in horizons.items():
        for multiplier in multipliers:
            label = _label(multiplier)
            print(f"[VDPGM-Pareto] {horizon} replay {label}", flush=True)
            frames[horizon][label], metrics[horizon][label] = _replay(
                label=label,
                state=qss_state,
                params=parameter_sets[label],
                t_eval=time,
                teacher_values=teacher_values,
                teachers=teachers,
                panel_curves=panel_curves,
                panel_indices=panel_indices,
                panel_time=experimental_time,
                method=method,
                rtol=rtol,
                atol=atol,
                closure_tolerance=closure_tolerance,
            )

    guard_rows = []
    for multiplier in REFINEMENT_MULTIPLIERS:
        label = _label(multiplier)
        short_guards = _short_guards(
            candidate=metrics["J1_J3"][label],
            seed=metrics["J1_J3"][_label(REFERENCE_MULTIPLIER)],
            closure_tolerance=closure_tolerance,
        )
        relay_guards = _extension_guards(
            candidate=metrics["J1_J10"][label],
            seed=metrics["J1_J10"][_label(REFERENCE_MULTIPLIER)],
            block="J1_J10",
            closure_tolerance=closure_tolerance,
        )
        storage_guards = _extension_guards(
            candidate=metrics["J1_J46"][label],
            seed=metrics["J1_J46"][_label(REFERENCE_MULTIPLIER)],
            block="J1_J46",
            closure_tolerance=closure_tolerance,
        )
        guard_rows.append(
            {
                "candidate": label,
                "multiplier": multiplier,
                "J1_J3_guards_pass": bool(all(short_guards.values())),
                "J1_J10_guards_pass": bool(all(relay_guards.values())),
                "J1_J46_guards_pass": bool(all(storage_guards.values())),
                "all_temporal_guards_pass": bool(
                    all(short_guards.values())
                    and all(relay_guards.values())
                    and all(storage_guards.values())
                ),
                "failed_guards": sorted(
                    [
                        f"J1_J3:{name}" for name, passed in short_guards.items() if not passed
                    ]
                    + [
                        f"J1_J10:{name}" for name, passed in relay_guards.items() if not passed
                    ]
                    + [
                        f"J1_J46:{name}" for name, passed in storage_guards.items() if not passed
                    ]
                ),
                **_flatten_metrics(metrics["J1_J46"][label]),
            }
        )
    pareto_frame, selection = _rank_pareto(guard_rows)
    selected = selection["selected_candidate"]
    if selected is not None:
        selected_multiplier = float(
            pareto_frame.loc[pareto_frame["candidate"] == selected, "multiplier"].iloc[0]
        )
        decision = f"retain {selected_multiplier:g}x as the interior diagnostic Pareto anchor"
        rationale = (
            "The interior point passed every temporal and whole-panel guard and improved the predeclared "
            "six-objective ideal distance by at least 5% relative to both endpoint anchors. It remains "
            "diagnostic because ATP collapse and global parameter uncertainty are unresolved."
        )
        next_step = "audit ATP production-consumption and VPGK-versus-VDPGM partitioning in the fixed 3x branch"
    else:
        decision = "keep 2x as the conservative diagnostic anchor"
        rationale = (
            "The narrow grid did not produce an interior point that improved the normalized B23PG-versus-"
            "F6P/GLC/ELAC compromise by the predeclared 5% margin over the endpoint anchors. The higher "
            "points remain useful sensitivity cases but do not justify replacing the conservative 2x anchor."
        )
        next_step = "stop DPGM refinement and return to the unresolved ATP sustainability attribution"

    for horizon in horizons:
        pd.concat(frames[horizon].values(), ignore_index=True).to_csv(
            out_dir / f"{horizon}_timeseries.csv", index=False
        )
    pareto_frame.to_csv(out_dir / "pareto_metrics.csv", index=False)
    (out_dir / "candidate_parameter_sets.json").write_text(
        json.dumps(_jsonable(parameter_sets), indent=2), encoding="utf-8"
    )
    _plot(
        frame=pareto_frame,
        storage_frames=frames["J1_J46"],
        selected=selected,
        out_path=out_dir / "vmax_vdpgm_pareto_refinement.png",
    )
    summary = {
        "contract_type": "deterministic_vmax_VDPGM_qss_B13PG_pareto_refinement",
        "contract_version": 1,
        "model_network_version": MODEL_NETWORK_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "optimization_performed": False,
        "parameters_promoted": False,
        "seed_params_path": str(seed_path),
        "multipliers": list(REFINEMENT_MULTIPLIERS),
        "objective_contract": {
            "B23PG_objectives": list(B23PG_OBJECTIVES),
            "transfer_costs": list(TRANSFER_OBJECTIVES),
            "normalization": "min-max within the fully specified 2x-4x grid",
            "knee_metric": "Euclidean distance between mean normalized B23PG objective and mean normalized transfer cost",
            "minimum_interior_improvement_fraction": MIN_INTERIOR_IMPROVEMENT,
        },
        "pareto_rows": pareto_frame.to_dict(orient="records"),
        "selection": selection,
        "decision": decision,
        "decision_rationale": rationale,
        "next_step": next_step,
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "report": str(out_dir / "decision_report.md"),
            "metrics": str(out_dir / "pareto_metrics.csv"),
            "parameter_sets": str(out_dir / "candidate_parameter_sets.json"),
            "plot": str(out_dir / "vmax_vdpgm_pareto_refinement.png"),
        },
    }
    (out_dir / "summary.json").write_text(
        json.dumps(_jsonable(summary), indent=2), encoding="utf-8"
    )
    _write_report(out_dir / "decision_report.md", summary)
    print(
        json.dumps(
            {
                "selection": selection,
                "decision": decision,
                "summary": str(out_dir / "summary.json"),
            },
            indent=2,
        )
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--short-points", type=int, default=401)
    parser.add_argument("--relay-points", type=int, default=451)
    parser.add_argument("--storage-points", type=int, default=451)
    parser.add_argument("--method", default="BDF")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    parser.add_argument("--closure-tolerance", type=float, default=1e-12)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_refinement(
        out_dir=args.out_dir,
        short_points=args.short_points,
        relay_points=args.relay_points,
        storage_points=args.storage_points,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
        closure_tolerance=args.closure_tolerance,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
