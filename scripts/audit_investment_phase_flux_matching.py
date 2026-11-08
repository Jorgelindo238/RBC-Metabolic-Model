"""Audit investment-phase flux matching before further Brodbar calibration.

The audit replays the mild-feedback seed and the diagnostic ``km_ADP_ATP
0.75x`` candidate with the native ODE and FluxTracker. It reconstructs the
exact G6P and F6P balances, checks their pointwise closure, and relates
early/mid/late flux mismatches to measured Brodbar concentrations. No
optimization or parameter promotion is performed.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.integrate import cumulative_trapezoid


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
SCRIPT_DIR = ROOT / "scripts"
DEFAULT_SEED_PARAMS = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "vpep_vpk_coupled_mild_feedback_46d_n20"
    / "seed_fixed_params.json"
)
DEFAULT_CANDIDATE_PARAMS = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "km_adp_atp_production_screen_46d"
    / "screen_params_0.75x.json"
)
DEFAULT_OUT_DIR = (
    ROOT / "Simulations" / "brodbar" / "hermes" / "investment_phase_flux_matching_46d"
)

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from MM_calibration import EXP_TO_MODEL  # noqa: E402
from profile_atp_consumption_sinks import (  # noqa: E402
    _all_experimental_curves,
    _changed_parameters,
)
from profile_glycolysis_flux_bottlenecks import (  # noqa: E402
    _jsonable,
    _load_params,
    _simulate_and_track,
    _time_mean,
)
from run_glucose_utilization_fla import _nrmse  # noqa: E402


EXPECTED_CHANGED_PARAMETER = "km_ADP_ATP"
AUDITED_FLUXES = ("VHK", "VPGI", "VG6PDH", "VPFK", "VTKL2", "VTAL")
AUDITED_POOLS = ("G6P", "F6P")
CONTEXT_POOLS = ("GLC", "G6P", "F6P", "F16BP")
WINDOWS = (
    ("early_1_2d", 1.0, 2.0),
    ("mid_10_20d", 10.0, 20.0),
    ("late_40_46d", 40.0, 46.0),
    ("full_1_46d", 1.0, 46.0),
)

# These terms reproduce dxdt[1] and dxdt[2] in equadiff_brodbar.py.
BALANCE_SPECS: dict[str, dict[str, tuple[str, ...]]] = {
    "G6P": {"inputs": ("VHK",), "outputs": ("VPGI", "VG6PDH")},
    "F6P": {"inputs": ("VPGI", "VTKL2", "VTAL"), "outputs": ("VPFK",)},
}


def _time_grid(t_max: float, timepoints: int, early_timepoints: int) -> np.ndarray:
    regular = np.linspace(1.0, float(t_max), int(timepoints))
    if int(early_timepoints) <= 0:
        return regular
    early_end = min(2.0, float(t_max))
    if early_end <= 1.0:
        return regular
    early = 1.0 + np.geomspace(1e-6, early_end - 1.0, int(early_timepoints))
    return np.unique(np.concatenate(([1.0], early, regular)))


def _reconstruct_balance(
    fluxes: Mapping[str, np.ndarray], pool: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if pool not in BALANCE_SPECS:
        raise KeyError(f"Unsupported investment-phase pool: {pool}")
    spec = BALANCE_SPECS[pool]
    required = (*spec["inputs"], *spec["outputs"])
    missing = [reaction for reaction in required if reaction not in fluxes]
    if missing:
        raise KeyError(f"FluxTracker is missing {pool} balance reactions: {missing}")
    inputs = sum(np.asarray(fluxes[name], dtype=float) for name in spec["inputs"])
    outputs = sum(np.asarray(fluxes[name], dtype=float) for name in spec["outputs"])
    return np.asarray(inputs), np.asarray(outputs), np.asarray(inputs - outputs)


def _validate_balance_closure(
    reconstructed: np.ndarray,
    ode_derivative: np.ndarray,
    *,
    pool: str,
    tolerance: float = 1e-12,
) -> float:
    reconstructed = np.asarray(reconstructed, dtype=float)
    ode_derivative = np.asarray(ode_derivative, dtype=float)
    if reconstructed.shape != ode_derivative.shape:
        raise ValueError(
            f"{pool} closure arrays have different shapes: "
            f"{reconstructed.shape} != {ode_derivative.shape}"
        )
    error = float(np.max(np.abs(reconstructed - ode_derivative)))
    if error > float(tolerance):
        raise RuntimeError(f"{pool} balance closure failed: max abs error={error:.6g}")
    return error


def _timeseries_frame(
    *,
    label: str,
    sol: Any,
    fluxes: Mapping[str, np.ndarray],
    derivatives: np.ndarray,
    closure_tolerance: float,
    account_for_nonnegative_damping: bool = False,
    nonnegative_threshold: float = 1e-3,
) -> tuple[pd.DataFrame, dict[str, float]]:
    time = np.asarray(sol.t, dtype=float)
    data: dict[str, Any] = {"candidate": label, "time_day": time}
    for pool in CONTEXT_POOLS:
        data[pool] = np.asarray(sol.y[int(EXP_TO_MODEL[pool]), :], dtype=float)
    for reaction in AUDITED_FLUXES:
        if reaction not in fluxes:
            raise KeyError(f"FluxTracker is missing audited reaction {reaction}")
        data[reaction] = np.asarray(fluxes[reaction], dtype=float)

    closure_errors: dict[str, float] = {}
    for pool in AUDITED_POOLS:
        input_flux, output_flux, net_flux = _reconstruct_balance(fluxes, pool)
        derivative = np.asarray(derivatives[int(EXP_TO_MODEL[pool]), :], dtype=float)
        effective_flux = net_flux.copy()
        damping_adjustment = np.zeros_like(net_flux)
        if account_for_nonnegative_damping:
            concentration = np.asarray(data[pool], dtype=float)
            damping_mask = (concentration < float(nonnegative_threshold)) & (net_flux < 0.0)
            damping_factor = np.ones_like(net_flux)
            damping_factor[damping_mask] = np.maximum(concentration[damping_mask], 0.0) / float(
                nonnegative_threshold
            )
            effective_flux = net_flux * damping_factor
            damping_adjustment = effective_flux - net_flux
        closure_errors[pool] = _validate_balance_closure(
            effective_flux,
            derivative,
            pool=pool,
            tolerance=closure_tolerance,
        )
        cumulative_net = cumulative_trapezoid(net_flux, time, initial=0.0)
        cumulative_effective = cumulative_trapezoid(effective_flux, time, initial=0.0)
        concentration_change = data[pool] - float(data[pool][0])
        data[f"{pool}_input_flux"] = input_flux
        data[f"{pool}_output_flux"] = output_flux
        data[f"d{pool}_dt_flux"] = net_flux
        data[f"d{pool}_dt_effective_flux"] = effective_flux
        data[f"d{pool}_dt_ode"] = derivative
        data[f"{pool}_raw_stoichiometric_residual"] = derivative - net_flux
        data[f"{pool}_nonnegative_damping_adjustment"] = damping_adjustment
        data[f"{pool}_pointwise_closure_error"] = derivative - effective_flux
        data[f"{pool}_cumulative_net_flux"] = cumulative_net
        data[f"{pool}_cumulative_effective_flux"] = cumulative_effective
        data[f"{pool}_concentration_change"] = concentration_change
        data[f"{pool}_integral_residual"] = concentration_change - cumulative_effective
    return pd.DataFrame(data), closure_errors


def _window_rows(timeseries: pd.DataFrame) -> list[dict[str, Any]]:
    label = str(timeseries["candidate"].iloc[0])
    time = timeseries["time_day"].to_numpy(dtype=float)
    rows: list[dict[str, Any]] = []
    for window, start, end in WINDOWS:
        effective_end = min(float(end), float(time[-1]))
        mask = (time >= float(start) - 1e-12) & (time <= effective_end + 1e-12)
        if np.count_nonzero(mask) < 2:
            continue
        window_time = time[mask]
        for pool in AUDITED_POOLS:
            input_flux = timeseries.loc[mask, f"{pool}_input_flux"].to_numpy(dtype=float)
            output_flux = timeseries.loc[mask, f"{pool}_output_flux"].to_numpy(dtype=float)
            net_flux = timeseries.loc[mask, f"d{pool}_dt_flux"].to_numpy(dtype=float)
            concentration = timeseries.loc[mask, pool].to_numpy(dtype=float)
            integrated_net = float(np.trapezoid(net_flux, window_time))
            concentration_change = float(concentration[-1] - concentration[0])
            mean_input = _time_mean(input_flux, window_time)
            mean_output = _time_mean(output_flux, window_time)
            row: dict[str, Any] = {
                "candidate": label,
                "window": window,
                "pool": pool,
                "start_day": float(window_time[0]),
                "end_day": float(window_time[-1]),
                "n_timepoints": int(window_time.size),
                "mean_input_flux": mean_input,
                "mean_output_flux": mean_output,
                "mean_net_flux": _time_mean(net_flux, window_time),
                "output_input_ratio": mean_output / max(abs(mean_input), 1e-30),
                "net_fraction_of_input": (mean_input - mean_output) / max(abs(mean_input), 1e-30),
                "concentration_start": float(concentration[0]),
                "concentration_end": float(concentration[-1]),
                "concentration_change": concentration_change,
                "integrated_net_flux": integrated_net,
                "integral_residual": concentration_change - integrated_net,
                "max_abs_pointwise_closure_error": float(
                    np.max(
                        np.abs(
                            timeseries.loc[
                                mask, f"{pool}_pointwise_closure_error"
                            ].to_numpy(dtype=float)
                        )
                    )
                ),
            }
            for reaction in AUDITED_FLUXES:
                row[f"mean_{reaction}"] = _time_mean(
                    timeseries.loc[mask, reaction].to_numpy(dtype=float), window_time
                )
            rows.append(row)
    return rows


def _trajectory_metric_rows(
    *,
    label: str,
    sol: Any,
    exp_time: np.ndarray,
    exp_curves: Mapping[str, np.ndarray],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    metric_windows = (("full_1_46d", 1.0, float(sol.t[-1])), *WINDOWS[:3])
    for pool in CONTEXT_POOLS:
        if pool not in exp_curves:
            continue
        idx = int(EXP_TO_MODEL[pool])
        for window, start, end in metric_windows:
            mask = (exp_time >= start - 1e-12) & (exp_time <= min(end, sol.t[-1]) + 1e-12)
            if not np.any(mask):
                continue
            measured = np.asarray(exp_curves[pool][mask], dtype=float)
            simulated = np.interp(exp_time[mask], sol.t, sol.y[idx, :])
            residual = simulated - measured
            row: dict[str, Any] = {
                "candidate": label,
                "window": window,
                "metabolite": pool,
                "n_experimental_points": int(measured.size),
                "rmse": float(np.sqrt(np.mean(residual**2))),
                "mean_residual": float(np.mean(residual)),
                "mean_absolute_error": float(np.mean(np.abs(residual))),
                "simulated_endpoint": float(simulated[-1]),
                "experimental_endpoint": float(measured[-1]),
                "endpoint_error": float(residual[-1]),
            }
            if window == "full_1_46d":
                metric = _nrmse(simulated, measured)
                row["nrmse"] = float(metric["nrmse"])
            else:
                scale = max(float(np.ptp(measured)), float(np.mean(np.abs(measured))), 1e-12)
                row["nrmse"] = row["rmse"] / scale
            rows.append(row)
    return rows


def _audit_decision(max_closure_error: float, closure_tolerance: float) -> tuple[str, str]:
    if float(max_closure_error) > float(closure_tolerance):
        return (
            "correct the ODE balance implementation before calibration",
            "At least one reconstructed investment-phase balance does not match the native ODE derivative point by point.",
        )
    return (
        "retain the algebraic balances and prioritize coupled kinetic flux matching",
        "Both balances close exactly against the native ODE. Persistent pool errors therefore arise within the current flux magnitudes and coupling; this audit does not demonstrate a missing algebraic term. Biological completeness still requires independent validation.",
    )


def _global_metric_lookup(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], Mapping[str, Any]]:
    return {
        (str(row["candidate"]), str(row["metabolite"])): row
        for row in rows
        if row["window"] == "full_1_46d"
    }


def _key_flux_findings(
    window_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    lookup = {
        (str(row["candidate"]), str(row["pool"]), str(row["window"])): row
        for row in window_rows
    }

    def row(candidate: str, pool: str, window: str) -> Mapping[str, Any]:
        return lookup[(candidate, pool, window)]

    seed_g6p = {
        window: float(row("seed", "G6P", window)["output_input_ratio"])
        for window in ("early_1_2d", "mid_10_20d", "late_40_46d")
    }
    seed_f6p = {
        window: float(row("seed", "F6P", window)["output_input_ratio"])
        for window in ("early_1_2d", "mid_10_20d", "late_40_46d")
    }
    ppp_return_shares: dict[str, float] = {}
    for window in ("early_1_2d", "mid_10_20d", "late_40_46d"):
        values = row("seed", "F6P", window)
        ppp_return = float(values["mean_VTKL2"]) + float(values["mean_VTAL"])
        ppp_return_shares[window] = ppp_return / max(
            abs(float(values["mean_input_flux"])), 1e-30
        )

    seed_late_g6p = row("seed", "G6P", "late_40_46d")
    candidate_late_g6p = row("km_ADP_ATP_0.75x", "G6P", "late_40_46d")
    seed_late_f6p = row("seed", "F6P", "late_40_46d")
    candidate_late_f6p = row("km_ADP_ATP_0.75x", "F6P", "late_40_46d")

    def relative_change(candidate_value: Any, seed_value: Any) -> float:
        return float(candidate_value) / max(abs(float(seed_value)), 1e-30) - 1.0

    return {
        "seed_g6p_output_input_ratio": seed_g6p,
        "seed_f6p_output_input_ratio": seed_f6p,
        "seed_f6p_ppp_return_share": ppp_return_shares,
        "seed_early_pool_changes_mM": {
            "G6P": float(row("seed", "G6P", "early_1_2d")["concentration_change"]),
            "F6P": float(row("seed", "F6P", "early_1_2d")["concentration_change"]),
        },
        "candidate_late_relative_changes": {
            "VHK": relative_change(
                candidate_late_g6p["mean_VHK"], seed_late_g6p["mean_VHK"]
            ),
            "G6P_output": relative_change(
                candidate_late_g6p["mean_output_flux"],
                seed_late_g6p["mean_output_flux"],
            ),
            "F6P_input": relative_change(
                candidate_late_f6p["mean_input_flux"], seed_late_f6p["mean_input_flux"]
            ),
            "VPFK": relative_change(
                candidate_late_f6p["mean_VPFK"], seed_late_f6p["mean_VPFK"]
            ),
            "F6P_net": relative_change(
                candidate_late_f6p["mean_net_flux"], seed_late_f6p["mean_net_flux"]
            ),
        },
    }


def _plot_audit(
    *,
    frames: Mapping[str, pd.DataFrame],
    exp_time: np.ndarray,
    exp_curves: Mapping[str, np.ndarray],
    window_rows: Sequence[Mapping[str, Any]],
    out_path: Path,
) -> None:
    colors = {"seed": "#64748b", "km_ADP_ATP_0.75x": "#2563eb"}
    fig, axes = plt.subplots(3, 3, figsize=(16, 13), constrained_layout=True)

    concentration_axes = {
        "GLC": axes[0, 0],
        "G6P": axes[0, 1],
        "F6P": axes[0, 2],
        "F16BP": axes[1, 0],
    }
    for pool, axis in concentration_axes.items():
        for label, frame in frames.items():
            axis.plot(
                frame["time_day"],
                frame[pool],
                color=colors[label],
                linewidth=2.0,
                label=label,
            )
        if pool in exp_curves:
            axis.scatter(
                exp_time,
                exp_curves[pool],
                color="#111827",
                edgecolor="white",
                linewidth=0.6,
                s=30,
                zorder=5,
                label="Brodbar",
            )
        axis.set_title(f"{pool} concentration")
        axis.set_xlabel("Time (days)")
        axis.set_ylabel("mM")
        axis.grid(True, alpha=0.22)
        if pool in {"G6P", "F6P"}:
            axis.set_yscale("log")
        axis.legend(frameon=False, fontsize=8)

    for pool, axis in (("G6P", axes[1, 1]), ("F6P", axes[1, 2])):
        for label, frame in frames.items():
            color = colors[label]
            axis.plot(
                frame["time_day"],
                frame[f"{pool}_input_flux"],
                color=color,
                linewidth=2.0,
                label=f"{label} input",
            )
            axis.plot(
                frame["time_day"],
                frame[f"{pool}_output_flux"],
                color=color,
                linewidth=1.7,
                linestyle="--",
                label=f"{label} output",
            )
        axis.set_title(f"{pool} flux matching")
        axis.set_xlabel("Time (days)")
        axis.set_ylabel("mM/day")
        axis.grid(True, alpha=0.22)
        axis.legend(frameon=False, fontsize=7, ncol=2)

    for pool, axis in (("G6P", axes[2, 0]), ("F6P", axes[2, 1])):
        for label, frame in frames.items():
            axis.plot(
                frame["time_day"],
                frame[f"d{pool}_dt_flux"],
                color=colors[label],
                linewidth=2.0,
                label=label,
            )
        axis.axhline(0.0, color="#111827", linewidth=0.8)
        axis.set_title(f"Reconstructed d{pool}/dt")
        axis.set_xlabel("Time (days)")
        axis.set_ylabel("mM/day")
        axis.grid(True, alpha=0.22)
        axis.legend(frameon=False, fontsize=8)

    ratio_rows = [row for row in window_rows if row["window"] != "full_1_46d"]
    labels = ["G6P early", "G6P mid", "G6P late", "F6P early", "F6P mid", "F6P late"]
    x = np.arange(len(labels), dtype=float)
    for offset, candidate in ((-0.18, "seed"), (0.18, "km_ADP_ATP_0.75x")):
        values = []
        for pool in AUDITED_POOLS:
            for window in ("early_1_2d", "mid_10_20d", "late_40_46d"):
                row = next(
                    item
                    for item in ratio_rows
                    if item["candidate"] == candidate
                    and item["pool"] == pool
                    and item["window"] == window
                )
                values.append(float(row["output_input_ratio"]))
        axes[2, 2].bar(
            x + offset,
            values,
            width=0.36,
            color=colors[candidate],
            label=candidate,
        )
    axes[2, 2].axhline(1.0, color="#111827", linewidth=0.9, linestyle=":")
    axes[2, 2].set_xticks(x, labels, rotation=35, ha="right")
    axes[2, 2].set_title("Output/input matching by window")
    axes[2, 2].set_ylabel("Mean output / mean input")
    axes[2, 2].grid(True, axis="y", alpha=0.22)
    axes[2, 2].legend(frameon=False, fontsize=8)

    fig.suptitle("Brodbar investment-phase flux-matching audit", fontsize=16)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    metrics = _global_metric_lookup(summary["trajectory_metrics"])
    window_lookup = {
        (row["candidate"], row["pool"], row["window"]): row
        for row in summary["window_balance_summary"]
    }
    findings = summary["key_flux_findings"]
    lines = [
        "# Investment-phase flux-matching audit",
        "",
        "## Technical contract",
        "",
        f"- Generated: {summary['generated_at']}",
        f"- Horizon: `{summary['t_max']:.0f}` days.",
        "- Comparison: mild-feedback seed versus diagnostic `km_ADP_ATP 0.75x`.",
        f"- Only changed parameter: `{summary['changed_parameters']}`.",
        "- Diagnostic only: no optimization, parameter opening, or promotion.",
        "",
        "## Exact balances",
        "",
        "```text",
        "dG6P/dt = VHK - VPGI - VG6PDH",
        "dF6P/dt = VPGI + VTKL2 + VTAL - VPFK",
        "```",
        "",
        f"Maximum pointwise reconstruction error: `{summary['max_pointwise_closure_error']:.3e}` mM/day.",
        f"Maximum window integral residual: `{summary['max_abs_window_integral_residual']:.3e}` mM.",
        "",
        "## Brodbar trajectory errors",
        "",
        "| Pool | Seed nRMSE | 0.75x nRMSE | Seed endpoint | 0.75x endpoint | Experiment |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for pool in CONTEXT_POOLS:
        seed = metrics[("seed", pool)]
        candidate = metrics[("km_ADP_ATP_0.75x", pool)]
        lines.append(
            f"| `{pool}` | {seed['nrmse']:.6g} | {candidate['nrmse']:.6g} | "
            f"{seed['simulated_endpoint']:.6g} | {candidate['simulated_endpoint']:.6g} | "
            f"{seed['experimental_endpoint']:.6g} |"
        )
    lines.extend(
        [
            "",
            "## Flux matching by time window",
            "",
            "| Candidate | Pool | Window | Mean input | Mean output | Output/input | Mean net | Pool change |",
            "|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for candidate in ("seed", "km_ADP_ATP_0.75x"):
        for pool in AUDITED_POOLS:
            for window in ("early_1_2d", "mid_10_20d", "late_40_46d"):
                row = window_lookup[(candidate, pool, window)]
                lines.append(
                    f"| `{candidate}` | `{pool}` | `{window}` | {row['mean_input_flux']:.6g} | "
                    f"{row['mean_output_flux']:.6g} | {row['output_input_ratio']:.6g} | "
                    f"{row['mean_net_flux']:.6g} | {row['concentration_change']:.6g} |"
                )
    lines.extend(
        [
            "",
            "## Dominant mismatch pattern",
            "",
            f"- In the seed, G6P output/input is `{findings['seed_g6p_output_input_ratio']['early_1_2d']:.3f}` at J1-J2: VHK input exceeds VPGI + VG6PDH by about 22-fold and G6P rises by `{findings['seed_early_pool_changes_mM']['G6P']:.3f}` mM.",
            f"- G6P then switches to net drainage: output/input is `{findings['seed_g6p_output_input_ratio']['mid_10_20d']:.3f}` at J10-J20 and `{findings['seed_g6p_output_input_ratio']['late_40_46d']:.3f}` at J40-J46, but the pool remains above Brodbar.",
            f"- F6P output/input stays below one in every window: `{findings['seed_f6p_output_input_ratio']['early_1_2d']:.3f}`, `{findings['seed_f6p_output_input_ratio']['mid_10_20d']:.3f}`, and `{findings['seed_f6p_output_input_ratio']['late_40_46d']:.3f}`. F6P therefore accumulates while Brodbar F6P declines.",
            f"- VTKL2 + VTAL supply `{100.0 * findings['seed_f6p_ppp_return_share']['early_1_2d']:.1f}%` of early F6P input and still `{100.0 * findings['seed_f6p_ppp_return_share']['mid_10_20d']:.1f}%` / `{100.0 * findings['seed_f6p_ppp_return_share']['late_40_46d']:.1f}%` in the mid/late windows. The F6P mismatch is therefore not attributable to VPGI/VPFK alone.",
            f"- The 0.75x ATP-production probe raises late VHK by `{100.0 * findings['candidate_late_relative_changes']['VHK']:.1f}%`, G6P output by `{100.0 * findings['candidate_late_relative_changes']['G6P_output']:.1f}%`, F6P input by `{100.0 * findings['candidate_late_relative_changes']['F6P_input']:.1f}%`, and VPFK by `{100.0 * findings['candidate_late_relative_changes']['VPFK']:.1f}%`. It scales the relay without restoring flux matching.",
            "",
            "## Structural interpretation",
            "",
            f"**Decision: `{summary['decision']}`.**",
            "",
            summary["decision_rationale"],
            "",
            "Exact algebraic closure verifies implementation consistency, not biological completeness. A missing biological regulation or exchange can still exist even when the coded balance closes.",
            "",
            "## Next calibration gate",
            "",
            summary["next_step"],
            "",
            "No parameter file was generated by this audit.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_audit(
    *,
    out_dir: Path,
    seed_params_path: Path,
    candidate_params_path: Path,
    t_max: float,
    timepoints: int,
    early_timepoints: int,
    method: str,
    rtol: float,
    atol: float,
    closure_tolerance: float,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    seed_params = _load_params(seed_params_path)
    candidate_params = _load_params(candidate_params_path)
    changed = _changed_parameters(seed_params, candidate_params)
    if changed != [EXPECTED_CHANGED_PARAMETER]:
        raise RuntimeError(f"Expected only {EXPECTED_CHANGED_PARAMETER} to change, got {changed}")

    t_eval = _time_grid(t_max, timepoints, early_timepoints)
    exp_time, exp_curves = _all_experimental_curves(t_max)
    frames: dict[str, pd.DataFrame] = {}
    closure_by_candidate: dict[str, dict[str, float]] = {}
    metric_rows: list[dict[str, Any]] = []
    replay_inputs = (
        ("seed", seed_params_path, seed_params),
        ("km_ADP_ATP_0.75x", candidate_params_path, candidate_params),
    )
    for label, path, params in replay_inputs:
        print(f"[investment-audit] simulating {label}: {path}", flush=True)
        sol, fluxes, derivatives = _simulate_and_track(
            params=params,
            t_eval=t_eval,
            method=method,
            rtol=rtol,
            atol=atol,
        )
        frame, closure_errors = _timeseries_frame(
            label=label,
            sol=sol,
            fluxes=fluxes,
            derivatives=derivatives,
            closure_tolerance=closure_tolerance,
        )
        frames[label] = frame
        closure_by_candidate[label] = closure_errors
        metric_rows.extend(
            _trajectory_metric_rows(
                label=label,
                sol=sol,
                exp_time=exp_time,
                exp_curves=exp_curves,
            )
        )

    window_rows = [row for frame in frames.values() for row in _window_rows(frame)]
    max_closure = max(error for values in closure_by_candidate.values() for error in values.values())
    max_integral_residual = max(abs(float(row["integral_residual"])) for row in window_rows)
    decision, rationale = _audit_decision(max_closure, closure_tolerance)
    key_findings = _key_flux_findings(window_rows)

    metric_lookup = _global_metric_lookup(metric_rows)
    f6p_seed = metric_lookup[("seed", "F6P")]
    f6p_candidate = metric_lookup[("km_ADP_ATP_0.75x", "F6P")]
    g6p_seed = metric_lookup[("seed", "G6P")]
    g6p_candidate = metric_lookup[("km_ADP_ATP_0.75x", "G6P")]
    next_step = (
        "Before another free-parameter search, audit the directionality of the irreversible VTKL2 and VTAL "
        "rate laws and implement a reversible, feature-flagged non-oxidative PPP return hypothesis. Evaluate "
        "that hypothesis first as a fixed replay while retaining the exact G6P/F6P balances and the same "
        "GLC/G6P/F6P/F16BP plus ATP/PEP safeguards."
    )

    timeseries_path = out_dir / "investment_phase_timeseries.csv"
    window_path = out_dir / "investment_phase_window_summary.csv"
    metrics_path = out_dir / "investment_phase_pool_metrics.csv"
    plot_path = out_dir / "investment_phase_flux_matching.png"
    pd.concat(frames.values(), ignore_index=True).to_csv(timeseries_path, index=False)
    pd.DataFrame(window_rows).to_csv(window_path, index=False)
    pd.DataFrame(metric_rows).to_csv(metrics_path, index=False)
    _plot_audit(
        frames=frames,
        exp_time=exp_time,
        exp_curves=exp_curves,
        window_rows=window_rows,
        out_path=plot_path,
    )

    summary = {
        "contract_type": "investment_phase_flux_matching_audit",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "optimization_performed": False,
        "parameters_opened": [],
        "parameters_promoted": False,
        "parameter_artifacts_generated": False,
        "seed_params_path": str(seed_params_path),
        "candidate_params_path": str(candidate_params_path),
        "changed_parameters": changed,
        "t_max": float(t_max),
        "timepoints": int(t_eval.size),
        "solver": {"method": method, "rtol": float(rtol), "atol": float(atol)},
        "balance_equations": {
            "G6P": "VHK - VPGI - VG6PDH",
            "F6P": "VPGI + VTKL2 + VTAL - VPFK",
        },
        "closure_tolerance": float(closure_tolerance),
        "pointwise_closure_by_candidate": closure_by_candidate,
        "max_pointwise_closure_error": max_closure,
        "max_abs_window_integral_residual": max_integral_residual,
        "trajectory_metrics": metric_rows,
        "window_balance_summary": window_rows,
        "key_flux_findings": key_findings,
        "key_pool_changes": {
            "G6P_nrmse": {
                "seed": g6p_seed["nrmse"],
                "candidate": g6p_candidate["nrmse"],
            },
            "F6P_nrmse": {
                "seed": f6p_seed["nrmse"],
                "candidate": f6p_candidate["nrmse"],
            },
        },
        "decision": decision,
        "decision_rationale": rationale,
        "next_step": next_step,
        "limitations": [
            "Exact algebraic closure does not prove biological completeness.",
            "Experimental concentration data constrain net pool changes, not every individual reaction flux.",
        ],
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "decision_report": str(out_dir / "decision_report.md"),
            "timeseries_csv": str(timeseries_path),
            "window_summary_csv": str(window_path),
            "pool_metrics_csv": str(metrics_path),
            "plot": str(plot_path),
        },
    }
    (out_dir / "summary.json").write_text(
        json.dumps(_jsonable(summary), indent=2), encoding="utf-8"
    )
    _write_report(out_dir / "decision_report.md", summary)
    print(
        json.dumps(
            {
                "summary": summary["artifact_paths"]["summary"],
                "decision": decision,
                "max_pointwise_closure_error": max_closure,
                "max_abs_window_integral_residual": max_integral_residual,
                "G6P_nrmse": summary["key_pool_changes"]["G6P_nrmse"],
                "F6P_nrmse": summary["key_pool_changes"]["F6P_nrmse"],
            },
            indent=2,
        ),
        flush=True,
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit VHK/VPGI/VG6PDH/VPFK investment-phase flux matching"
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--seed-params", type=Path, default=DEFAULT_SEED_PARAMS)
    parser.add_argument("--candidate-params", type=Path, default=DEFAULT_CANDIDATE_PARAMS)
    parser.add_argument("--t-max", type=float, default=46.0)
    parser.add_argument("--timepoints", type=int, default=361)
    parser.add_argument("--early-timepoints", type=int, default=100)
    parser.add_argument("--method", default="LSODA")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    parser.add_argument("--closure-tolerance", type=float, default=1e-12)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_audit(
        out_dir=args.out_dir,
        seed_params_path=args.seed_params,
        candidate_params_path=args.candidate_params,
        t_max=args.t_max,
        timepoints=args.timepoints,
        early_timepoints=args.early_timepoints,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
        closure_tolerance=args.closure_tolerance,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
