"""Build a local structural/practical identifiability mask for sequential FLA."""

from __future__ import annotations

import argparse
import re
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
from scipy.linalg import qr


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
SCRIPT_DIR = ROOT / "scripts"
DEFAULT_OUT_DIR = ROOT / "output" / "fla_identifiability_mask_2026_08_11"

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from audit_b23pg_balance_qss_context import (  # noqa: E402
    QSS_LABEL,
    REVERT_LABEL,
    _build_state_contract,
)
from equadiff_brodbar import (  # noqa: E402
    BRODBAR_METABOLITE_MAP,
    MODEL_NETWORK_VERSION,
    equadiff_brodbar,
)
from fla_temporal_contract import TEMPORAL_BLOCKS  # noqa: E402
from flux_visualization import FluxTracker  # noqa: E402
from MM_calibration import DEFAULT_PARAM_VALUES  # noqa: E402
from profile_glycolysis_flux_bottlenecks import _simulate_and_track  # noqa: E402
from rbc_stoichiometry import REACTION_PARAMS, STOICHIOMETRY  # noqa: E402


PERTURBATION_LOG_STEP = 0.05
PRACTICAL_RANK_RTOL = 1e-3
INACTIVE_NORM = 1e-8
B23PG_DRAIN_HOLD = frozenset({"vmax_V23DPGP", "km_B23PG"})


def _load_model_literal_defaults() -> dict[str, float]:
    source = (SRC_DIR / "equadiff_brodbar.py").read_text(encoding="utf-8")
    pattern = re.compile(
        r"_get_param\(custom_params,\s*['\"](?P<name>[A-Za-z0-9_]+)['\"],\s*"
        r"(?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\)"
    )
    return {match.group("name"): float(match.group("value")) for match in pattern.finditer(source)}


MODEL_LITERAL_DEFAULTS = _load_model_literal_defaults()


def _numeric_parameter_value(params: Mapping[str, Any], name: str) -> float | None:
    raw = params.get(name, DEFAULT_PARAM_VALUES.get(name, MODEL_LITERAL_DEFAULTS.get(name)))
    if isinstance(raw, bool) or not isinstance(raw, (int, float, np.number)):
        return None
    value = float(raw)
    if not np.isfinite(value) or value <= 0.0:
        return None
    return value


def _candidate_parameters(reactions: Sequence[str], params: Mapping[str, Any]) -> list[str]:
    names = set()
    for reaction in reactions:
        names.update(REACTION_PARAMS.get(reaction, frozenset()))
    return sorted(name for name in names if _numeric_parameter_value(params, name) is not None)


def _replay_fluxes(
    *,
    time: np.ndarray,
    states: np.ndarray,
    params: Mapping[str, Any],
    reactions: Sequence[str],
) -> np.ndarray:
    tracker = FluxTracker()
    for day, state in zip(time, states.T):
        equadiff_brodbar(
            float(day),
            np.asarray(state, dtype=float),
            custom_params=dict(params),
            curve_fit_strength=0.0,
            flux_tracker=tracker,
        )
    missing = [reaction for reaction in reactions if reaction not in tracker.fluxes]
    if missing:
        raise KeyError(f"FluxTracker is missing reactions: {missing}")
    return np.column_stack(
        [np.asarray(tracker.fluxes[reaction], dtype=float) for reaction in reactions]
    )


def _practical_rank(matrix: np.ndarray, relative_tolerance: float) -> tuple[int, np.ndarray]:
    singular_values = np.linalg.svd(np.asarray(matrix, dtype=float), compute_uv=False)
    if singular_values.size == 0 or singular_values[0] <= 0.0:
        return 0, singular_values
    rank = int(np.sum(singular_values > singular_values[0] * float(relative_tolerance)))
    return rank, singular_values


def _stoichiometric_rank(block: Any) -> tuple[int, tuple[str, ...]]:
    represented = tuple(
        metabolite
        for metabolite in block.concentration_targets
        if metabolite in BRODBAR_METABOLITE_MAP
    )
    matrix = np.asarray(
        [
            [float(STOICHIOMETRY.get(reaction, {}).get(metabolite, 0.0)) for reaction in block.flux_targets]
            for metabolite in represented
        ],
        dtype=float,
    )
    return int(np.linalg.matrix_rank(matrix)), represented


def _sample_block_trajectory(
    *, solution: Any, start: float, end: float, points: int
) -> tuple[np.ndarray, np.ndarray]:
    targets = np.linspace(float(start), float(end), int(points))
    indices = np.asarray([int(np.argmin(np.abs(solution.t - target))) for target in targets])
    indices = np.unique(indices)
    return np.asarray(solution.t[indices], dtype=float), np.asarray(solution.y[:, indices], dtype=float)


def _block_sensitivity(
    *,
    block: Any,
    trajectories: Mapping[str, Any],
    params: Mapping[str, Any],
    sample_points: int,
    log_step: float,
    rank_rtol: float,
) -> tuple[pd.DataFrame, dict[str, Any], np.ndarray]:
    reactions = tuple(block.flux_targets)
    parameter_names = _candidate_parameters(reactions, params)
    contexts: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
    for label, solution in trajectories.items():
        time, states = _sample_block_trajectory(
            solution=solution,
            start=block.start_day,
            end=block.end_day,
            points=sample_points,
        )
        baseline = _replay_fluxes(time=time, states=states, params=params, reactions=reactions)
        contexts.append((time, states, baseline))

    stacked_baseline = np.vstack([entry[2] for entry in contexts])
    reaction_scale = np.maximum(np.mean(np.abs(stacked_baseline), axis=0), 1e-8)
    columns = []
    for parameter in parameter_names:
        base_value = _numeric_parameter_value(params, parameter)
        assert base_value is not None
        plus_params = dict(params)
        minus_params = dict(params)
        plus_params[parameter] = base_value * np.exp(log_step)
        minus_params[parameter] = base_value * np.exp(-log_step)
        context_columns = []
        for time, states, _ in contexts:
            plus = _replay_fluxes(
                time=time, states=states, params=plus_params, reactions=reactions
            )
            minus = _replay_fluxes(
                time=time, states=states, params=minus_params, reactions=reactions
            )
            derivative = (plus - minus) / (2.0 * log_step)
            context_columns.append((derivative / reaction_scale).reshape(-1))
        columns.append(np.concatenate(context_columns))
    sensitivity = (
        np.column_stack(columns)
        if columns
        else np.empty((stacked_baseline.size, 0), dtype=float)
    )
    norms = np.linalg.norm(sensitivity, axis=0)
    active = norms > INACTIVE_NORM
    active_matrix = sensitivity[:, active]
    active_names = [name for name, keep in zip(parameter_names, active) if keep]
    rank, singular_values = _practical_rank(active_matrix, rank_rtol)
    selected: list[str] = []
    pivot_order: list[str] = []
    if active_matrix.shape[1]:
        _, _, pivots = qr(active_matrix, mode="economic", pivoting=True)
        pivot_order = [active_names[int(index)] for index in pivots]
        selected = pivot_order[:rank]

    normalized = np.zeros_like(sensitivity)
    if sensitivity.shape[1]:
        normalized[:, active] = active_matrix / norms[active]
    correlation = np.abs(normalized.T @ normalized) if sensitivity.shape[1] else np.empty((0, 0))
    if correlation.size:
        np.fill_diagonal(correlation, 0.0)

    rows = []
    for index, parameter in enumerate(parameter_names):
        max_correlation = float(np.max(correlation[index])) if correlation.size else 0.0
        if norms[index] <= INACTIVE_NORM:
            classification = "locally_inactive"
        elif parameter in selected:
            classification = "identifiable_basis_candidate"
        else:
            classification = "redundant_compensation_risk"
        hold_reason = ""
        basis_selected = classification == "identifiable_basis_candidate"
        allowed = basis_selected and block.name == TEMPORAL_BLOCKS[0].name and parameter == "vmax_VDPGM"
        if parameter in B23PG_DRAIN_HOLD:
            allowed = False
            hold_reason = "B23PG audit assigns the current defect to VDPGM supply, not V23DPGP drainage"
        elif block.name != TEMPORAL_BLOCKS[0].name:
            hold_reason = "sequential FLA contract requires the preceding temporal block to pass first"
        elif parameter != "vmax_VDPGM":
            hold_reason = "keep the next cause-directed screen one-dimensional around VDPGM supply"
        rows.append(
            {
                "block": block.name,
                "parameter": parameter,
                "baseline_value": _numeric_parameter_value(params, parameter),
                "sensitivity_norm": float(norms[index]),
                "max_abs_column_correlation": max_correlation,
                "classification": classification,
                "selected_in_local_sensitivity_basis": bool(basis_selected),
                "open_in_next_block_calibration": bool(allowed),
                "hold_reason": hold_reason,
                "pivot_position": pivot_order.index(parameter) + 1 if parameter in pivot_order else None,
            }
        )

    stoich_rank, represented = _stoichiometric_rank(block)
    structural_priority = selected[:stoich_rank]
    summary = {
        "block": block.name,
        "reaction_count": len(reactions),
        "candidate_parameter_count": len(parameter_names),
        "active_parameter_count": int(np.sum(active)),
        "practical_sensitivity_rank": rank,
        "stoichiometric_target_reaction_rank": stoich_rank,
        "represented_concentration_targets": list(represented),
        "singular_values": singular_values.tolist(),
        "identifiable_basis": selected,
        "structural_priority_basis": structural_priority,
        "recommended_open_parameters": [
            row["parameter"] for row in rows if row["open_in_next_block_calibration"]
        ],
    }
    return pd.DataFrame(rows), summary, correlation


def _plot_correlations(
    frames: Mapping[str, pd.DataFrame], correlations: Mapping[str, np.ndarray], out_path: Path
) -> None:
    fig, axes = plt.subplots(1, len(frames), figsize=(18, 6), constrained_layout=True)
    axes = np.atleast_1d(axes)
    image = None
    for axis, (block, frame) in zip(axes, frames.items()):
        matrix = correlations[block]
        image = axis.imshow(matrix, vmin=0.0, vmax=1.0, cmap="magma", aspect="auto")
        labels = frame["parameter"].tolist()
        axis.set_title(block.replace("_", "\n"), fontsize=9)
        axis.set_xticks(range(len(labels)), labels, rotation=90, fontsize=5)
        axis.set_yticks(range(len(labels)), labels, fontsize=5)
    if image is not None:
        fig.colorbar(image, ax=axes.tolist(), label="absolute normalized sensitivity correlation")
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def run_mask(
    *,
    out_dir: Path,
    trajectory_points: int,
    sample_points: int,
    method: str,
    rtol: float,
    atol: float,
    rank_rtol: float,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    states, params, seed_path = _build_state_contract()
    params = dict(params)
    params["sam_adenylate_stoichiometry"] = "biochemical_transfer"
    time = np.linspace(1.0, 46.0, int(trajectory_points))
    trajectories = {}
    for label in (REVERT_LABEL, QSS_LABEL):
        solution, _, _ = _simulate_and_track(
            params=params,
            t_eval=time,
            method=method,
            rtol=rtol,
            atol=atol,
            x0_override=states[label],
        )
        trajectories[label] = solution

    frames: dict[str, pd.DataFrame] = {}
    block_summaries = []
    correlations = {}
    for block in TEMPORAL_BLOCKS:
        frame, block_summary, correlation = _block_sensitivity(
            block=block,
            trajectories=trajectories,
            params=params,
            sample_points=sample_points,
            log_step=PERTURBATION_LOG_STEP,
            rank_rtol=rank_rtol,
        )
        frames[block.name] = frame
        block_summaries.append(block_summary)
        correlations[block.name] = correlation
    all_rows = pd.concat(frames.values(), ignore_index=True)
    all_rows.to_csv(out_dir / "parameter_identifiability_mask.csv", index=False)
    _plot_correlations(frames, correlations, out_dir / "sensitivity_correlation.png")

    next_block = block_summaries[0]
    summary = {
        "contract_type": "fla_local_structural_practical_identifiability_mask",
        "contract_version": 1,
        "model_network_version": MODEL_NETWORK_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed_params_path": str(seed_path),
        "state_contexts": [REVERT_LABEL, QSS_LABEL],
        "method": {
            "kinetic_sensitivity": "central finite difference in log-parameter space at fixed trajectory states",
            "log_step": PERTURBATION_LOG_STEP,
            "practical_rank_relative_tolerance": rank_rtol,
            "important_limitation": "local direct-flux sensitivity is a screening mask, not a profile-likelihood proof of global identifiability",
        },
        "blocks": block_summaries,
        "next_calibration_block": next_block["block"],
        "next_open_parameter_mask": next_block["recommended_open_parameters"],
        "forced_holds": sorted(B23PG_DRAIN_HOLD),
        "optimization_performed": False,
        "decision": "screen vmax_VDPGM alone next; retain the wider sensitivity basis only as an attribution map and preserve cumulative temporal guards",
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "mask": str(out_dir / "parameter_identifiability_mask.csv"),
            "correlation_plot": str(out_dir / "sensitivity_correlation.png"),
            "report": str(out_dir / "decision_report.md"),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    lines = [
        "# FLA identifiability mask",
        "",
        "This is a reversible pre-calibration screen. It combines the parsed reaction-parameter map with direct local flux sensitivities in both B13PG initialization contexts.",
        "",
        "| Temporal block | Candidate parameters | Active | Practical rank | Stoichiometric rank | Recommended open mask |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for block in block_summaries:
        recommended = ", ".join(f"`{name}`" for name in block["recommended_open_parameters"]) or "none"
        lines.append(
            f"| `{block['block']}` | {block['candidate_parameter_count']} | "
            f"{block['active_parameter_count']} | {block['practical_sensitivity_rank']} | "
            f"{block['stoichiometric_target_reaction_rank']} | {recommended} |"
        )
    lines.extend(
        [
            "",
            "`vmax_V23DPGP` and `km_B23PG` remain held even if locally sensitive: the exact J1-J3 balance attributes the present B23PG defect to insufficient VDPGM supply.",
            "",
            "The selected columns define a basis, not permission for simultaneous unconstrained fitting. Future optimization must still open the smallest mechanistically coherent subset and retain prior-block and whole-horizon guards.",
            "",
            "No kinetic parameter was optimized or promoted here.",
        ]
    )
    (out_dir / "decision_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"blocks": block_summaries, "summary": str(out_dir / "summary.json")}, indent=2))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--trajectory-points", type=int, default=181)
    parser.add_argument("--sample-points", type=int, default=21)
    parser.add_argument("--method", default="BDF")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    parser.add_argument("--rank-rtol", type=float, default=PRACTICAL_RANK_RTOL)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_mask(
        out_dir=args.out_dir,
        trajectory_points=args.trajectory_points,
        sample_points=args.sample_points,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
        rank_rtol=args.rank_rtol,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
