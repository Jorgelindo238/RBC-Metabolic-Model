"""Screen VAMPD1 capacity under the reversible fixed VAPRT=0 diagnostic."""

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
from scipy.interpolate import PchipInterpolator


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
SCRIPT_DIR = ROOT / "scripts"
DEFAULT_OUT_DIR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "vmax_vampd1_vaprt_zero_screen_J1_J46"
)

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from audit_atp_partition_vdpgm_3x_qss_b13pg import _build_contract  # noqa: E402
from audit_atp_transition_v6pgd_ppp_context import _integral  # noqa: E402
from audit_joint_adenylate_balances import POOLS  # noqa: E402
from diagnose_vaprt_suppression_vampd1_requirement import (  # noqa: E402
    LATENT_GUARDS,
    OBSERVED_STATES,
    _add_teachers,
    _load_observed_curves,
    _replay,
    _required_vampd1,
    _state_metrics,
)
from equadiff_brodbar import MODEL_NETWORK_VERSION  # noqa: E402
from evaluate_brodbar_candidate_full_panel import _load_brodbar_panel  # noqa: E402
from profile_glycolysis_flux_bottlenecks import _jsonable  # noqa: E402


MULTIPLIERS = (1.0, 1.1, 1.2, 1.25, 1.3, 1.4, 1.5)
HORIZON_ENDS = {"J1_J3": 3.0, "J1_J10": 10.0, "J1_J46": 46.0}
OBSERVED_GUARD_TOLERANCE = 0.10
WHOLE_PANEL_TOLERANCE = 0.05
LATENT_EXCURSION_TOLERANCE = 0.10
VAK_DIRECTION_TOLERANCE = 0.01
AMBIGUOUS_PANEL_STATES = {"B13PG", "P2G"}


def _label(multiplier: float) -> str:
    return f"vmax_VAMPD1_{float(multiplier):.3f}x"


def _candidate_params(
    fixed_params: Mapping[str, Any], multiplier: float
) -> tuple[dict[str, Any], float, list[str], list[str]]:
    diagnostic_seed = dict(fixed_params)
    diagnostic_seed["vmax_VAPRT"] = 0.0
    seed_vmax = float(diagnostic_seed["vmax_VAMPD1"])
    candidate = dict(diagnostic_seed)
    candidate["vmax_VAMPD1"] = seed_vmax * float(multiplier)
    changed_from_seed = sorted(
        key
        for key in set(diagnostic_seed) | set(candidate)
        if diagnostic_seed.get(key) != candidate.get(key)
    )
    expected = [] if np.isclose(multiplier, 1.0) else ["vmax_VAMPD1"]
    if changed_from_seed != expected:
        raise RuntimeError(
            f"VAMPD1 one-factor contract failed: changed={changed_from_seed}"
        )
    changed_from_fixed = sorted(
        key
        for key in set(fixed_params) | set(candidate)
        if fixed_params.get(key) != candidate.get(key)
    )
    expected_fixed = ["vmax_VAPRT"] if np.isclose(multiplier, 1.0) else [
        "vmax_VAMPD1",
        "vmax_VAPRT",
    ]
    if changed_from_fixed != expected_fixed:
        raise RuntimeError(
            f"Fixed-kinetic contract failed: changed={changed_from_fixed}"
        )
    return candidate, seed_vmax, changed_from_seed, changed_from_fixed


def _normalized_endpoint_error(model: float, teacher: float, full: np.ndarray) -> float:
    scale = max(float(np.mean(np.abs(full))), 0.01)
    return abs(float(model) - float(teacher)) / scale


def _normalized_rmse(model: np.ndarray, teacher: np.ndarray, scale_values: np.ndarray) -> float:
    scale = max(float(np.mean(np.abs(scale_values))), 0.01)
    return float(
        np.sqrt(np.mean((np.asarray(model) - np.asarray(teacher)) ** 2)) / scale
    )


def _horizon_grid(exp_time: np.ndarray, end_day: float, points: int) -> np.ndarray:
    measured = exp_time[(exp_time >= 1.0) & (exp_time <= float(end_day))]
    return np.unique(
        np.concatenate([np.linspace(1.0, float(end_day), int(points)), measured])
    )


def _panel_metrics(
    *,
    frame: pd.DataFrame,
    exp_time: np.ndarray,
    curves: Mapping[str, np.ndarray],
) -> dict[str, Any]:
    time = frame["time_day"].to_numpy(dtype=float)
    rows: dict[str, float] = {}
    for state, full_curve in curves.items():
        if state in AMBIGUOUS_PANEL_STATES or state not in frame:
            continue
        teacher = np.asarray(PchipInterpolator(exp_time, full_curve)(time), dtype=float)
        rows[state] = _normalized_rmse(
            frame[state].to_numpy(dtype=float), teacher, np.asarray(full_curve)
        )
    values = np.asarray(list(rows.values()), dtype=float)
    return {
        "target_count": int(values.size),
        "mean_nrmse": float(np.mean(values)),
        "median_nrmse": float(np.median(values)),
        "per_metabolite_nrmse": rows,
    }


def _replay_with_metrics(
    *,
    label: str,
    state: np.ndarray,
    params: Mapping[str, Any],
    time: np.ndarray,
    exp_time: np.ndarray,
    observed_curves: Mapping[str, np.ndarray],
    panel_curves: Mapping[str, np.ndarray],
    panel_indices: Mapping[str, int],
    method: str,
    rtol: float,
    atol: float,
    closure_tolerance: float,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame, closures = _replay(
        label=label,
        state=state,
        params=params,
        time=time,
        method=method,
        rtol=rtol,
        atol=atol,
        closure_tolerance=closure_tolerance,
        extra_state_indices=panel_indices,
    )
    frame = _add_teachers(
        frame=frame, exp_time=exp_time, curves=observed_curves
    )
    teacher_interpolators = {
        pool: PchipInterpolator(exp_time, observed_curves[pool]) for pool in POOLS
    }
    total_teacher_derivative = sum(
        teacher.derivative()(time) for teacher in teacher_interpolators.values()
    )
    required_vampd1 = _required_vampd1(
        total_teacher_derivative=total_teacher_derivative,
        vak2=frame["VAK2"].to_numpy(dtype=float),
        vsam=frame["VSAM"].to_numpy(dtype=float),
        vadsl=frame["VADSL"].to_numpy(dtype=float),
        vaprt=frame["VAPRT"].to_numpy(dtype=float),
    )
    frame["dadenylate_total_teacher_dt"] = total_teacher_derivative
    frame["VAMPD1_teacher"] = required_vampd1
    state_metrics = _state_metrics(frame=frame, curves=observed_curves)
    total_full = sum(np.asarray(observed_curves[pool]) for pool in POOLS)
    slope_scale = max(float(np.mean(np.abs(total_teacher_derivative))), 0.01)
    total_slope_nrmse = float(
        np.sqrt(
            np.mean(
                (
                    frame["dadenylate_total_ode_dt"].to_numpy(dtype=float)
                    - total_teacher_derivative
                )
                ** 2
            )
        )
        / slope_scale
    )
    total_metrics = state_metrics["adenylate_total"]
    total_metrics["endpoint_error"] = _normalized_endpoint_error(
        total_metrics["model_endpoint_mM"],
        total_metrics["teacher_endpoint_mM"],
        total_full,
    )
    total_metrics["slope_nrmse"] = total_slope_nrmse
    actual_vampd1 = frame["VAMPD1"].to_numpy(dtype=float)
    teacher_scale = np.maximum(np.abs(required_vampd1), 0.01)
    state_metrics["VAMPD1_flux"] = {
        "nrmse": float(
            np.sqrt(np.mean((actual_vampd1 - required_vampd1) ** 2))
            / float(np.mean(teacher_scale))
        ),
        "integral_mM": _integral(actual_vampd1, time),
        "teacher_integral_mM": _integral(required_vampd1, time),
        "endpoint_mM_per_day": float(actual_vampd1[-1]),
        "teacher_endpoint_mM_per_day": float(required_vampd1[-1]),
    }
    for latent in LATENT_GUARDS:
        values = frame[latent].to_numpy(dtype=float)
        state_metrics[latent]["max_abs_excursion_mM"] = float(
            np.max(np.abs(values - values[0]))
        )
    vak = frame["VAK"].to_numpy(dtype=float)
    state_metrics["VAK_directionality"] = {
        "forward_time_fraction": float(np.mean(vak >= -1e-12)),
        "reverse_time_fraction": float(np.mean(vak < -1e-12)),
        "net_integral_mM": _integral(vak, time),
        "minimum_mM_per_day": float(np.min(vak)),
        "maximum_mM_per_day": float(np.max(vak)),
    }
    state_metrics["whole_panel"] = _panel_metrics(
        frame=frame,
        exp_time=exp_time,
        curves=panel_curves,
    )
    metrics = {
        "candidate": label,
        "horizon_end_day": float(time[-1]),
        "vmax_VAMPD1": float(params["vmax_VAMPD1"]),
        "vmax_VAPRT": float(params["vmax_VAPRT"]),
        "state_metrics": state_metrics,
        "closures": closures,
    }
    return frame, metrics


def _latent_preserved(
    candidate: Mapping[str, Any], baseline: Mapping[str, Any], state: str
) -> bool:
    candidate_excursion = float(
        candidate["state_metrics"][state]["max_abs_excursion_mM"]
    )
    baseline_excursion = float(
        baseline["state_metrics"][state]["max_abs_excursion_mM"]
    )
    allowance = max(
        (1.0 + LATENT_EXCURSION_TOLERANCE) * baseline_excursion,
        baseline_excursion + 0.01,
    )
    return (
        float(candidate["state_metrics"][state]["minimum_mM"]) >= -1e-10
        and candidate_excursion <= allowance
    )


def _guards(
    *,
    candidate: Mapping[str, Any],
    baseline: Mapping[str, Any],
    closure_tolerance: float,
    include_whole_panel: bool,
) -> dict[str, bool]:
    candidate_states = candidate["state_metrics"]
    baseline_states = baseline["state_metrics"]
    candidate_total = candidate_states["adenylate_total"]
    baseline_total = baseline_states["adenylate_total"]
    closures = candidate["closures"]
    guards = {
        "all_balances_close": all(
            float(value) <= closure_tolerance
            for key, value in closures.items()
            if key.startswith("max_abs_")
        ),
        "all_states_nonnegative": float(closures["all_state_minimum_mM"])
        >= -1e-10,
        "adenylate_total_trajectory_improves": float(candidate_total["nrmse"])
        < float(baseline_total["nrmse"]),
        "adenylate_total_slope_improves": float(candidate_total["slope_nrmse"])
        < float(baseline_total["slope_nrmse"]),
        "adenylate_total_endpoint_improves": float(
            candidate_total["endpoint_error"]
        )
        < float(baseline_total["endpoint_error"]),
        "AMP_trajectory_improves": float(candidate_states["AMP"]["nrmse"])
        < float(baseline_states["AMP"]["nrmse"]),
        "VAMPD1_teacher_flux_improves": float(
            candidate_states["VAMPD1_flux"]["nrmse"]
        )
        < float(baseline_states["VAMPD1_flux"]["nrmse"]),
        "PRPP_preserved": _latent_preserved(candidate, baseline, "PRPP"),
        "ADOMET_preserved": _latent_preserved(candidate, baseline, "ADOMET"),
        "VAK_directionality_preserved": float(
            candidate_states["VAK_directionality"]["forward_time_fraction"]
        )
        >= float(baseline_states["VAK_directionality"]["forward_time_fraction"])
        - VAK_DIRECTION_TOLERANCE,
    }
    for state in ("ATP", "ADP", "IMP", "ADE"):
        guards[f"{state}_trajectory_noninferior_10pct"] = float(
            candidate_states[state]["nrmse"]
        ) <= (1.0 + OBSERVED_GUARD_TOLERANCE) * float(
            baseline_states[state]["nrmse"]
        )
    if include_whole_panel:
        guards["whole_panel_mean_noninferior_5pct"] = float(
            candidate_states["whole_panel"]["mean_nrmse"]
        ) <= (1.0 + WHOLE_PANEL_TOLERANCE) * float(
            baseline_states["whole_panel"]["mean_nrmse"]
        )
        guards["whole_panel_median_noninferior_5pct"] = float(
            candidate_states["whole_panel"]["median_nrmse"]
        ) <= (1.0 + WHOLE_PANEL_TOLERANCE) * float(
            baseline_states["whole_panel"]["median_nrmse"]
        )
    return guards


def _assess(
    *,
    labels: Sequence[str],
    metrics: Mapping[str, Mapping[str, Any]],
    multipliers: Mapping[str, float],
    closure_tolerance: float,
    include_whole_panel: bool,
) -> list[dict[str, Any]]:
    baseline = metrics[_label(1.0)]
    rows: list[dict[str, Any]] = []
    for label in labels:
        guards = _guards(
            candidate=metrics[label],
            baseline=baseline,
            closure_tolerance=closure_tolerance,
            include_whole_panel=include_whole_panel,
        )
        states = metrics[label]["state_metrics"]
        rows.append(
            {
                "candidate": label,
                "multiplier": float(multipliers[label]),
                "guard_pass": bool(all(guards.values())),
                "guards": guards,
                "adenylate_total_nrmse": states["adenylate_total"]["nrmse"],
                "adenylate_total_slope_nrmse": states["adenylate_total"][
                    "slope_nrmse"
                ],
                "adenylate_total_endpoint_error": states["adenylate_total"][
                    "endpoint_error"
                ],
                "AMP_nrmse": states["AMP"]["nrmse"],
                "VAMPD1_teacher_flux_nrmse": states["VAMPD1_flux"]["nrmse"],
            }
        )
    return rows


def _flatten_metrics(
    metrics: Mapping[str, Mapping[str, Mapping[str, Any]]]
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for horizon, by_label in metrics.items():
        for label, payload in by_label.items():
            row: dict[str, Any] = {
                "horizon": horizon,
                "candidate": label,
                "vmax_VAMPD1": payload["vmax_VAMPD1"],
                "vmax_VAPRT": payload["vmax_VAPRT"],
            }
            for state, state_metrics in payload["state_metrics"].items():
                if state == "whole_panel":
                    for metric in ("target_count", "mean_nrmse", "median_nrmse"):
                        row[f"whole_panel_{metric}"] = state_metrics[metric]
                elif isinstance(state_metrics, Mapping):
                    for metric, value in state_metrics.items():
                        if np.isscalar(value):
                            row[f"{state}_{metric}"] = value
            row.update(payload["closures"])
            rows.append(row)
    return pd.DataFrame(rows)


def _plot(
    *,
    frames: Mapping[str, pd.DataFrame],
    assessments: Sequence[Mapping[str, Any]],
    selected: str | None,
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(15.5, 8.5), constrained_layout=True)
    palette = plt.get_cmap("viridis")
    labels = list(frames)
    for index, label in enumerate(labels):
        frame = frames[label]
        color = palette(index / max(len(labels) - 1, 1))
        width = 2.4 if label == selected else 1.15
        alpha = 1.0 if label == selected else 0.75
        multiplier_label = label.removeprefix("vmax_VAMPD1_")
        time = frame["time_day"]
        axes[0, 0].plot(
            time,
            frame["adenylate_total"],
            color=color,
            lw=width,
            alpha=alpha,
            label=multiplier_label,
        )
        axes[0, 1].plot(time, frame["dadenylate_total_ode_dt"], color=color, lw=width, alpha=alpha)
        axes[0, 2].plot(time, frame["AMP"], color=color, lw=width, alpha=alpha)
        axes[1, 0].plot(time, frame["VAMPD1"], color=color, lw=width, alpha=alpha)
        axes[1, 1].plot(time, frame["IMP"], color=color, lw=width, alpha=alpha)
    reference = next(iter(frames.values()))
    axes[0, 0].plot(
        reference["time_day"],
        reference["adenylate_total_teacher"],
        "k--",
        lw=2.0,
        label="Brodbar teacher",
    )
    axes[0, 1].plot(
        reference["time_day"], reference["dadenylate_total_teacher_dt"], "k--", lw=2.0
    )
    axes[0, 2].plot(reference["time_day"], reference["AMP_teacher"], "k--", lw=2.0)
    axes[1, 0].plot(reference["time_day"], reference["VAMPD1_teacher"], "k--", lw=2.0)
    axes[1, 1].plot(reference["time_day"], reference["IMP_teacher"], "k--", lw=2.0)
    axes[0, 0].set_title("Total adenylate")
    axes[0, 0].legend(ncol=3, fontsize=7, loc="lower left")
    axes[0, 1].set_title("Total-pool slope")
    axes[0, 2].set_title("AMP")
    axes[1, 0].set_title("VAMPD1 and FLA teacher")
    axes[1, 1].set_title("IMP safeguard")
    for axis in axes.flat[:5]:
        axis.set_xlabel("Storage day")
        axis.grid(alpha=0.2)
    for axis in (axes[0, 0], axes[0, 2], axes[1, 1]):
        axis.set_ylabel("Concentration (mM)")
    axes[0, 1].set_ylabel("Rate (mM/day)")
    axes[1, 0].set_ylabel("Flux (mM/day)")
    multipliers = [float(row["multiplier"]) for row in assessments]
    axes[1, 2].plot(
        multipliers,
        [float(row["adenylate_total_nrmse"]) for row in assessments],
        marker="o",
        label="Total nRMSE",
    )
    axes[1, 2].plot(
        multipliers,
        [float(row["adenylate_total_slope_nrmse"]) for row in assessments],
        marker="s",
        label="Slope nRMSE",
    )
    axes[1, 2].plot(
        multipliers,
        [float(row["VAMPD1_teacher_flux_nrmse"]) for row in assessments],
        marker="^",
        label="Flux-teacher nRMSE",
    )
    for row in assessments:
        if row["guard_pass"]:
            axes[1, 2].scatter(float(row["multiplier"]), 0.0, marker="|", s=180, c="green")
    axes[1, 2].set_title("J1-J3 deterministic screen")
    axes[1, 2].set_xlabel("vmax_VAMPD1 multiplier")
    axes[1, 2].set_ylabel("Normalized error")
    axes[1, 2].grid(alpha=0.2)
    axes[1, 2].legend(fontsize=8)
    fig.suptitle("FLA VAMPD1 capacity screen under fixed VAPRT=0", fontsize=15)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    selected = summary["selected_candidate"] or "none"
    lines = [
        "# VAMPD1 capacity screen under fixed VAPRT=0",
        "",
        "## Contract",
        "",
        "- Deterministic multipliers: `1.0x, 1.1x, 1.2x, 1.25x, 1.3x, 1.4x, 1.5x`.",
        "- `vmax_VAPRT=0`; only `vmax_VAMPD1` varies relative to that diagnostic seed.",
        "- Sequential relay: J1-J3, J1-J10, then J1-J46; no optimization.",
        "",
        "## Eligibility",
        "",
        f"- J1-J3: `{', '.join(summary['J1_J3_eligible']) or 'none'}`.",
        f"- J1-J10: `{', '.join(summary['J1_J10_eligible']) or 'none'}`.",
        f"- J1-J46: `{', '.join(summary['J1_J46_eligible']) or 'none'}`.",
        f"- Smallest fully guarded candidate: `{selected}`.",
    ]
    if summary["selected_candidate"]:
        lines.extend(
            [
                "",
                "## Selected-anchor metrics",
                "",
                "| Horizon | Total nRMSE | Slope nRMSE | Endpoint error | AMP nRMSE | VAMPD1-teacher nRMSE |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for horizon in ("J1_J3", "J1_J10", "J1_J46"):
            states = summary["metrics"][horizon][selected]["state_metrics"]
            lines.append(
                f"| {horizon.replace('_', '-')} | "
                f"{states['adenylate_total']['nrmse']:.5g} | "
                f"{states['adenylate_total']['slope_nrmse']:.5g} | "
                f"{states['adenylate_total']['endpoint_error']:.5g} | "
                f"{states['AMP']['nrmse']:.5g} | "
                f"{states['VAMPD1_flux']['nrmse']:.5g} |"
            )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            summary["decision"],
            "",
            summary["decision_rationale"],
            "",
            f"Next: {summary['next_step']}.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_screen(
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
    state, _seed_params, fixed_params, seed_path = _build_contract()
    exp_time, observed_curves = _load_observed_curves()
    panel_time, panel_curves, _panel_order, panel_indices, unmapped = _load_brodbar_panel()
    if not np.array_equal(exp_time, panel_time):
        raise RuntimeError("Observed and full-panel Brodbar time grids differ")
    parameter_sets: dict[str, dict[str, Any]] = {}
    multipliers_by_label: dict[str, float] = {}
    changed_from_seed: dict[str, list[str]] = {}
    changed_from_fixed: dict[str, list[str]] = {}
    seed_vmax = None
    for multiplier in MULTIPLIERS:
        label = _label(multiplier)
        (
            parameter_sets[label],
            seed_vmax,
            changed_from_seed[label],
            changed_from_fixed[label],
        ) = _candidate_params(fixed_params, multiplier)
        multipliers_by_label[label] = float(multiplier)
    grids = {
        "J1_J3": _horizon_grid(exp_time, HORIZON_ENDS["J1_J3"], short_points),
        "J1_J10": _horizon_grid(exp_time, HORIZON_ENDS["J1_J10"], relay_points),
        "J1_J46": _horizon_grid(exp_time, HORIZON_ENDS["J1_J46"], storage_points),
    }
    frames: dict[str, dict[str, pd.DataFrame]] = {key: {} for key in grids}
    metrics: dict[str, dict[str, dict[str, Any]]] = {key: {} for key in grids}

    for multiplier in MULTIPLIERS:
        label = _label(multiplier)
        print(f"[VAMPD1] J1-J3 replay {label}", flush=True)
        frames["J1_J3"][label], metrics["J1_J3"][label] = _replay_with_metrics(
            label=label,
            state=state,
            params=parameter_sets[label],
            time=grids["J1_J3"],
            exp_time=exp_time,
            observed_curves=observed_curves,
            panel_curves=panel_curves,
            panel_indices=panel_indices,
            method=method,
            rtol=rtol,
            atol=atol,
            closure_tolerance=closure_tolerance,
        )
    candidate_labels = [_label(value) for value in MULTIPLIERS if not np.isclose(value, 1.0)]
    short_assessments = _assess(
        labels=candidate_labels,
        metrics=metrics["J1_J3"],
        multipliers=multipliers_by_label,
        closure_tolerance=closure_tolerance,
        include_whole_panel=False,
    )
    short_eligible = [row["candidate"] for row in short_assessments if row["guard_pass"]]

    relay_labels = [_label(1.0), *short_eligible]
    for label in relay_labels:
        print(f"[VAMPD1] J1-J10 replay {label}", flush=True)
        frames["J1_J10"][label], metrics["J1_J10"][label] = _replay_with_metrics(
            label=label,
            state=state,
            params=parameter_sets[label],
            time=grids["J1_J10"],
            exp_time=exp_time,
            observed_curves=observed_curves,
            panel_curves=panel_curves,
            panel_indices=panel_indices,
            method=method,
            rtol=rtol,
            atol=atol,
            closure_tolerance=closure_tolerance,
        )
    relay_assessments = _assess(
        labels=short_eligible,
        metrics=metrics["J1_J10"],
        multipliers=multipliers_by_label,
        closure_tolerance=closure_tolerance,
        include_whole_panel=False,
    ) if short_eligible else []
    relay_eligible = [row["candidate"] for row in relay_assessments if row["guard_pass"]]

    storage_labels = [_label(1.0), *relay_eligible]
    for label in storage_labels:
        print(f"[VAMPD1] J1-J46 replay {label}", flush=True)
        frames["J1_J46"][label], metrics["J1_J46"][label] = _replay_with_metrics(
            label=label,
            state=state,
            params=parameter_sets[label],
            time=grids["J1_J46"],
            exp_time=exp_time,
            observed_curves=observed_curves,
            panel_curves=panel_curves,
            panel_indices=panel_indices,
            method=method,
            rtol=rtol,
            atol=atol,
            closure_tolerance=closure_tolerance,
        )
    storage_assessments = _assess(
        labels=relay_eligible,
        metrics=metrics["J1_J46"],
        multipliers=multipliers_by_label,
        closure_tolerance=closure_tolerance,
        include_whole_panel=True,
    ) if relay_eligible else []
    storage_eligible = [row["candidate"] for row in storage_assessments if row["guard_pass"]]
    selected = min(
        storage_eligible,
        key=lambda label: multipliers_by_label[label],
        default=None,
    )
    if selected is not None:
        decision = "retain the smallest fully guarded VAMPD1 capacity as a reversible diagnostic anchor"
        rationale = (
            f"{selected} passed the predeclared concentration, flux-teacher, balance, "
            "directionality, latent-pool, temporal-transfer, and full-panel guards. "
            "The point is retained diagnostically and is not yet promoted to the global parameter set."
        )
        next_step = "repeat the selected point with strict solver tolerances, then audit IMP production and purine transfer before promotion"
    elif relay_eligible:
        decision = "reject global VAMPD1 promotion because no candidate survives J1-J46"
        rationale = "At least one capacity passed J1-J10, but every candidate failed a storage-horizon or full-panel guard."
        next_step = "attribute the first J1-J46 failure before opening another purine kinetic lever"
    elif short_eligible:
        decision = "retain only a local J1-J3 VAMPD1 hypothesis"
        rationale = "The residual early adenylate sink is locally correctable, but no capacity preserves the J1-J10 relay."
        next_step = "attribute the first J1-J10 failure before changing another kinetic parameter"
    else:
        decision = "reject VAMPD1 capacity alone under fixed VAPRT=0"
        rationale = "No multiplier improved every predeclared early target while preserving the purine and adenylate safeguards."
        next_step = "audit whether the residual requires time-dependent APRT suppression or another measured purine sink"

    pd.concat(frames["J1_J3"].values(), ignore_index=True).to_csv(
        out_dir / "J1_J3_timeseries.csv", index=False
    )
    for horizon in ("J1_J10", "J1_J46"):
        if frames[horizon]:
            pd.concat(frames[horizon].values(), ignore_index=True).to_csv(
                out_dir / f"{horizon}_timeseries.csv", index=False
            )
    _flatten_metrics(metrics).to_csv(out_dir / "candidate_metrics.csv", index=False)
    (out_dir / "candidate_parameter_sets.json").write_text(
        json.dumps(_jsonable(parameter_sets), indent=2), encoding="utf-8"
    )
    _plot(
        frames=frames["J1_J3"],
        assessments=short_assessments,
        selected=selected,
        out_path=out_dir / "vmax_vampd1_screen.png",
    )
    summary = {
        "contract_type": "deterministic_vmax_VAMPD1_screen_under_fixed_VAPRT_zero",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_network_version": MODEL_NETWORK_VERSION,
        "diagnostic_only": True,
        "optimization_performed": False,
        "parameters_promoted": False,
        "seed_params_path": str(seed_path),
        "solver": {
            "method": method,
            "rtol": rtol,
            "atol": atol,
            "points": {
                "J1_J3": short_points,
                "J1_J10": relay_points,
                "J1_J46": storage_points,
            },
        },
        "seed_vmax_VAMPD1": seed_vmax,
        "fixed_vmax_VAPRT": 0.0,
        "multipliers": list(MULTIPLIERS),
        "changed_from_diagnostic_seed": changed_from_seed,
        "changed_from_fixed_3x_contract": changed_from_fixed,
        "locked_contract": {
            "initialization": "fixed 3x QSS-B13PG state",
            "kinetics": "all parameters except vmax_VAMPD1 fixed; VAPRT fixed to zero",
            "selection": "smallest multiplier passing all sequential guards",
        },
        "unmapped_panel_states": unmapped,
        "metrics": metrics,
        "J1_J3_assessments": short_assessments,
        "J1_J3_eligible": short_eligible,
        "J1_J10_assessments": relay_assessments,
        "J1_J10_eligible": relay_eligible,
        "J1_J46_assessments": storage_assessments,
        "J1_J46_eligible": storage_eligible,
        "selected_candidate": selected,
        "selected_multiplier": multipliers_by_label[selected] if selected else None,
        "selected_vmax_VAMPD1": (
            parameter_sets[selected]["vmax_VAMPD1"] if selected else None
        ),
        "decision": decision,
        "decision_rationale": rationale,
        "next_step": next_step,
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "report": str(out_dir / "decision_report.md"),
            "metrics": str(out_dir / "candidate_metrics.csv"),
            "parameter_sets": str(out_dir / "candidate_parameter_sets.json"),
            "J1_J3_timeseries": str(out_dir / "J1_J3_timeseries.csv"),
            "J1_J10_timeseries": str(out_dir / "J1_J10_timeseries.csv"),
            "J1_J46_timeseries": str(out_dir / "J1_J46_timeseries.csv"),
            "plot": str(out_dir / "vmax_vampd1_screen.png"),
        },
    }
    (out_dir / "summary.json").write_text(
        json.dumps(_jsonable(summary), indent=2), encoding="utf-8"
    )
    _write_report(out_dir / "decision_report.md", summary)
    print(
        json.dumps(
            {
                "J1_J3_eligible": short_eligible,
                "J1_J10_eligible": relay_eligible,
                "J1_J46_eligible": storage_eligible,
                "selected_candidate": selected,
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
    parser.add_argument("--relay-points", type=int, default=901)
    parser.add_argument("--storage-points", type=int, default=1801)
    parser.add_argument("--method", default="BDF")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    parser.add_argument("--closure-tolerance", type=float, default=1e-7)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_screen(
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
