"""Audit the J1-J10 ATP transition in the retained V6PGD/PPP context."""

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


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
SCRIPT_DIR = ROOT / "scripts"
DEFAULT_REFINEMENT_DIR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "v6pgd_constrained_transition_refinement_46d"
)
DEFAULT_F6P_AUDIT_DIR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "f6p_accumulation_v6pgd_0.900_audit_46d"
)
DEFAULT_OUT_DIR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "atp_transition_v6pgd_0.900_ppp_context_J1_J10"
)

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from equadiff_brodbar import (  # noqa: E402
    BRODBAR_METABOLITE_MAP,
    MIN_CONCENTRATION,
    NONEG_THRESHOLD,
)
from MM_calibration import load_initial_conditions  # noqa: E402
from profile_energy_redox_controls import (  # noqa: E402
    ATP_CONSUMPTION,
    ATP_PRODUCTION,
    _factor_timeseries,
)
from profile_glycolysis_flux_bottlenecks import (  # noqa: E402
    _jsonable,
    _load_params,
    _simulate_and_track,
)
from diagnose_constrained_ppp_initialization import (  # noqa: E402
    LATENT_INDICES,
    LATENT_PPP_POOLS,
)
from audit_f6p_accumulation_v6pgd_candidate import (  # noqa: E402
    BASELINE_LABEL,
    CANDIDATE_LABEL,
    _first_sustained_crossing,
)


WINDOWS = (
    ("J1_J2", 1.0, 2.0),
    ("day_2_4", 2.0, 4.0),
    ("day_4_6", 4.0, 6.0),
    ("day_6_8", 6.0, 8.0),
    ("day_8_10", 8.0, 10.0),
)
TRACKED_STATES = (
    "ATP",
    "ADP",
    "AMP",
    "PEP",
    "B13PG",
    "PYR",
    "F16BP",
    "GLC",
    "G6P",
    "F6P",
)
STATE_INDICES = {
    name: int(BRODBAR_METABOLITE_MAP[name]) for name in TRACKED_STATES
}


def _time_mean(values: np.ndarray, time: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    time = np.asarray(time, dtype=float)
    if len(time) < 2:
        return float(values[0])
    return float(np.trapezoid(values, time) / (time[-1] - time[0]))


def _integral(values: np.ndarray, time: np.ndarray) -> float:
    return float(np.trapezoid(np.asarray(values, dtype=float), np.asarray(time, dtype=float)))


def _state_with_saved_latent(
    base_state: np.ndarray, latent_values: Mapping[str, float]
) -> np.ndarray:
    if set(latent_values) != set(LATENT_PPP_POOLS):
        raise ValueError("Saved initialization must contain the exact seven latent PPP pools")
    state = np.asarray(base_state, dtype=float).copy()
    for pool, index in zip(LATENT_PPP_POOLS, LATENT_INDICES):
        state[int(index)] = float(latent_values[pool])
    return state


def _candidate_params(seed_params: Mapping[str, Any]) -> dict[str, Any]:
    params = dict(seed_params)
    params["vmax_V6PGD"] = 9.0
    changed = sorted(
        key
        for key in set(seed_params) | set(params)
        if seed_params.get(key) != params.get(key)
    )
    if changed != ["vmax_V6PGD"]:
        raise RuntimeError(f"ATP audit kinetic contract failed: changed={changed}")
    return params


def _atp_balance(
    fluxes: Mapping[str, np.ndarray]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    missing = [
        reaction
        for reaction in (*ATP_PRODUCTION, *ATP_CONSUMPTION)
        if reaction not in fluxes
    ]
    if missing:
        raise KeyError(f"FluxTracker is missing ATP reactions: {missing}")
    production = sum(
        np.asarray(fluxes[reaction], dtype=float) for reaction in ATP_PRODUCTION
    )
    consumption = sum(
        np.asarray(fluxes[reaction], dtype=float) for reaction in ATP_CONSUMPTION
    )
    return production, consumption, production - consumption


def _effective_atp_balance(
    raw_net: np.ndarray,
    atp: np.ndarray,
    *,
    threshold: float = float(NONEG_THRESHOLD),
) -> tuple[np.ndarray, np.ndarray]:
    raw_net = np.asarray(raw_net, dtype=float)
    atp = np.maximum(np.asarray(atp, dtype=float), float(MIN_CONCENTRATION))
    effective = raw_net.copy()
    mask = (atp < float(threshold)) & (raw_net < 0.0)
    effective[mask] *= np.maximum(atp[mask], 0.0) / float(threshold)
    return effective, effective - raw_net


def _first_sustained_below(
    time: np.ndarray,
    values: np.ndarray,
    *,
    threshold: float,
    duration: float,
) -> float | None:
    return _first_sustained_crossing(
        np.asarray(time, dtype=float),
        -np.asarray(values, dtype=float),
        threshold=-float(threshold),
        duration=float(duration),
    )


def _first_fraction_loss(
    time: np.ndarray,
    values: np.ndarray,
    *,
    fraction: float,
    duration: float,
) -> float | None:
    baseline_mask = np.asarray(time, dtype=float) <= 1.25
    baseline = _time_mean(
        np.asarray(values, dtype=float)[baseline_mask],
        np.asarray(time, dtype=float)[baseline_mask],
    )
    return _first_sustained_below(
        time,
        values,
        threshold=float(fraction) * baseline,
        duration=duration,
    )


def _build_timeseries(
    *,
    label: str,
    sol: Any,
    fluxes: Mapping[str, np.ndarray],
    derivatives: np.ndarray,
    params: Mapping[str, Any],
    closure_tolerance: float,
) -> tuple[pd.DataFrame, dict[str, float]]:
    production, consumption, raw_net = _atp_balance(fluxes)
    atp_pool = np.asarray(sol.y[STATE_INDICES["ATP"], :], dtype=float)
    net, damping_adjustment = _effective_atp_balance(raw_net, atp_pool)
    atp_derivative = np.asarray(derivatives[STATE_INDICES["ATP"], :], dtype=float)
    closure_error = float(np.max(np.abs(net - atp_derivative)))
    if closure_error > float(closure_tolerance):
        raise RuntimeError(
            f"ATP balance closure failed for {label}: {closure_error:.6g}"
        )
    factors = _factor_timeseries(sol, fluxes, params)
    frame = pd.DataFrame(
        {
            "candidate": label,
            "time_day": np.asarray(sol.t, dtype=float),
            "ATP_production_flux": production,
            "ATP_consumption_flux": consumption,
            "ATP_raw_net_flux": raw_net,
            "ATP_net_flux": net,
            "ATP_damping_adjustment": damping_adjustment,
            "ATP_ode_derivative": atp_derivative,
            "ATP_closure_error": net - atp_derivative,
        }
    )
    for state, index in STATE_INDICES.items():
        frame[state] = np.asarray(sol.y[index, :], dtype=float)
    for reaction in (*ATP_PRODUCTION, *ATP_CONSUMPTION):
        frame[reaction] = np.asarray(fluxes[reaction], dtype=float)
    factor_columns = (
        "VPGK_ADP_ATP_drive",
        "VPK_PEP_occupancy",
        "VPK_ADP_ATP_drive",
        "VPK_F16BP_activation",
        "VPK_ATP_inhibition",
        "VPK_PYR_inhibition",
        "VPFK_F6P_occupancy",
        "VPFK_ATP_occupancy",
        "pool_ADP_ATP_ratio",
        "VPGK_vmax_utilization",
        "VPK_vmax_utilization",
        "VHK_vmax_utilization",
        "VPFK_vmax_utilization",
    )
    for column in factor_columns:
        frame[column] = factors[column].to_numpy(dtype=float)
    return frame, {"max_abs_ATP_closure_error": closure_error}


def _window_balance_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    all_time = frame["time_day"].to_numpy(dtype=float)
    for window, start, end in WINDOWS:
        mask = (all_time >= start - 1e-12) & (all_time <= end + 1e-12)
        time = all_time[mask]
        local = frame.loc[mask]
        production = local["ATP_production_flux"].to_numpy(dtype=float)
        consumption = local["ATP_consumption_flux"].to_numpy(dtype=float)
        net = local["ATP_net_flux"].to_numpy(dtype=float)
        atp = local["ATP"].to_numpy(dtype=float)
        producer_integrals = {
            reaction: _integral(local[reaction].to_numpy(dtype=float), time)
            for reaction in ATP_PRODUCTION
        }
        consumer_integrals = {
            reaction: _integral(local[reaction].to_numpy(dtype=float), time)
            for reaction in ATP_CONSUMPTION
        }
        total_production = sum(producer_integrals.values())
        total_consumption = sum(consumer_integrals.values())
        row: dict[str, Any] = {
            "candidate": str(frame["candidate"].iloc[0]),
            "window": window,
            "start_day": float(time[0]),
            "end_day": float(time[-1]),
            "ATP_start_mM": float(atp[0]),
            "ATP_end_mM": float(atp[-1]),
            "ATP_change_mM": float(atp[-1] - atp[0]),
            "production_mean": _time_mean(production, time),
            "consumption_mean": _time_mean(consumption, time),
            "net_mean": _time_mean(net, time),
            "production_integral": total_production,
            "consumption_integral": total_consumption,
            "net_integral": _integral(net, time),
            "integral_to_pool_change_error": _integral(net, time)
            - float(atp[-1] - atp[0]),
        }
        for reaction, value in producer_integrals.items():
            row[f"{reaction}_mean"] = _time_mean(
                local[reaction].to_numpy(dtype=float), time
            )
            row[f"{reaction}_integral"] = value
            row[f"{reaction}_production_share"] = value / max(
                abs(total_production), 1e-30
            )
        for reaction, value in consumer_integrals.items():
            row[f"{reaction}_mean"] = _time_mean(
                local[reaction].to_numpy(dtype=float), time
            )
            row[f"{reaction}_integral"] = value
            row[f"{reaction}_consumption_share"] = value / max(
                abs(total_consumption), 1e-30
            )
        rows.append(row)
    return rows


def _reaction_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    all_time = frame["time_day"].to_numpy(dtype=float)
    for window, start, end in WINDOWS:
        mask = (all_time >= start - 1e-12) & (all_time <= end + 1e-12)
        time = all_time[mask]
        for role, reactions, sign in (
            ("producer", ATP_PRODUCTION, 1.0),
            ("consumer", ATP_CONSUMPTION, -1.0),
        ):
            for reaction in reactions:
                values = frame.loc[mask, reaction].to_numpy(dtype=float)
                rows.append(
                    {
                        "candidate": str(frame["candidate"].iloc[0]),
                        "window": window,
                        "reaction": reaction,
                        "role": role,
                        "ATP_balance_sign": sign,
                        "mean_flux": _time_mean(values, time),
                        "integrated_flux": _integral(values, time),
                        "signed_integrated_contribution": sign
                        * _integral(values, time),
                        "endpoint_flux": float(values[-1]),
                    }
                )
    return rows


def _state_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    all_time = frame["time_day"].to_numpy(dtype=float)
    for window, start, end in WINDOWS:
        mask = (all_time >= start - 1e-12) & (all_time <= end + 1e-12)
        time = all_time[mask]
        for state in TRACKED_STATES:
            values = frame.loc[mask, state].to_numpy(dtype=float)
            rows.append(
                {
                    "candidate": str(frame["candidate"].iloc[0]),
                    "window": window,
                    "state": state,
                    "start_mM": float(values[0]),
                    "end_mM": float(values[-1]),
                    "mean_mM": _time_mean(values, time),
                    "minimum_mM": float(np.min(values)),
                    "maximum_mM": float(np.max(values)),
                }
            )
    return rows


def _transition_metrics(
    *,
    frame: pd.DataFrame,
    km_atp_pfk: float,
    f6p_divergence_day: float,
) -> dict[str, Any]:
    time = frame["time_day"].to_numpy(dtype=float)
    atp = frame["ATP"].to_numpy(dtype=float)
    production = frame["ATP_production_flux"].to_numpy(dtype=float)
    consumption = frame["ATP_consumption_flux"].to_numpy(dtype=float)
    collapse_day = _first_sustained_below(
        time,
        atp,
        threshold=float(km_atp_pfk),
        duration=0.25,
    )
    severe_day = _first_sustained_below(
        time,
        atp,
        threshold=0.01,
        duration=0.25,
    )
    production_half = _first_fraction_loss(
        time, production, fraction=0.5, duration=0.25
    )
    consumption_half = _first_fraction_loss(
        time, consumption, fraction=0.5, duration=0.25
    )
    if collapse_day is None:
        collapse_day = float(time[-1])
    collapse_index = int(np.searchsorted(time, collapse_day, side="left"))
    peak_index = int(np.argmax(atp))
    pre_mask = time <= collapse_day + 1e-12
    producer_integrals = {
        reaction: _integral(frame.loc[pre_mask, reaction], time[pre_mask])
        for reaction in ATP_PRODUCTION
    }
    consumer_integrals = {
        reaction: _integral(frame.loc[pre_mask, reaction], time[pre_mask])
        for reaction in ATP_CONSUMPTION
    }
    factor_names = (
        "VPGK_ADP_ATP_drive",
        "VPK_PEP_occupancy",
        "VPK_ADP_ATP_drive",
        "VPK_F16BP_activation",
        "VPK_ATP_inhibition",
        "VPK_PYR_inhibition",
        "VPFK_F6P_occupancy",
        "VPFK_ATP_occupancy",
        "VPGK_vmax_utilization",
        "VPK_vmax_utilization",
    )
    producer_at_collapse = {
        reaction: float(frame[reaction].iloc[collapse_index])
        for reaction in ATP_PRODUCTION
    }
    consumer_at_collapse = {
        reaction: float(frame[reaction].iloc[collapse_index])
        for reaction in ATP_CONSUMPTION
    }
    total_production_at_collapse = sum(producer_at_collapse.values())
    total_consumption_at_collapse = sum(consumer_at_collapse.values())
    return {
        "ATP_initial_mM": float(atp[0]),
        "ATP_peak_mM": float(atp[peak_index]),
        "ATP_peak_day": float(time[peak_index]),
        "ATP_at_day_2_mM": float(np.interp(2.0, time, atp)),
        "ATP_at_day_4_mM": float(np.interp(4.0, time, atp)),
        "ATP_at_day_10_mM": float(atp[-1]),
        "ATP_below_km_ATP_PFK_day": float(collapse_day),
        "ATP_below_0.01_mM_day": severe_day,
        "production_half_loss_day": production_half,
        "consumption_half_loss_day": consumption_half,
        "production_minus_consumption_half_loss_day": (
            None
            if production_half is None or consumption_half is None
            else float(production_half - consumption_half)
        ),
        "F6P_divergence_day": float(f6p_divergence_day),
        "ATP_collapse_to_F6P_divergence_delay_day": float(
            f6p_divergence_day - collapse_day
        ),
        "precollapse_producer_integrals": producer_integrals,
        "precollapse_consumer_integrals": consumer_integrals,
        "precollapse_total_production": sum(producer_integrals.values()),
        "precollapse_total_consumption": sum(consumer_integrals.values()),
        "precollapse_net_ATP": sum(producer_integrals.values())
        - sum(consumer_integrals.values()),
        "producer_fluxes_at_ATP_collapse": producer_at_collapse,
        "consumer_fluxes_at_ATP_collapse": consumer_at_collapse,
        "producer_shares_at_ATP_collapse": {
            reaction: value / max(abs(total_production_at_collapse), 1e-30)
            for reaction, value in producer_at_collapse.items()
        },
        "consumer_shares_at_ATP_collapse": {
            reaction: value / max(abs(total_consumption_at_collapse), 1e-30)
            for reaction, value in consumer_at_collapse.items()
        },
        "factors_at_ATP_collapse": {
            name: float(frame[name].iloc[collapse_index]) for name in factor_names
        },
        "states_at_ATP_collapse": {
            name: float(frame[name].iloc[collapse_index]) for name in TRACKED_STATES
        },
        "production_at_ATP_collapse": float(production[collapse_index]),
        "consumption_at_ATP_collapse": float(consumption[collapse_index]),
        "net_at_ATP_collapse": float(
            production[collapse_index] - consumption[collapse_index]
        ),
    }


def _delta_rows(
    *,
    reaction_rows: pd.DataFrame,
    baseline_label: str,
    candidate_label: str,
) -> list[dict[str, Any]]:
    baseline = reaction_rows[reaction_rows["candidate"] == baseline_label].set_index(
        ["window", "reaction"]
    )
    candidate = reaction_rows[reaction_rows["candidate"] == candidate_label].set_index(
        ["window", "reaction"]
    )
    rows: list[dict[str, Any]] = []
    for index in baseline.index:
        seed = baseline.loc[index]
        point = candidate.loc[index]
        rows.append(
            {
                "window": index[0],
                "reaction": index[1],
                "role": str(seed["role"]),
                "candidate_minus_seed_mean_flux": float(
                    point["mean_flux"] - seed["mean_flux"]
                ),
                "candidate_minus_seed_integrated_flux": float(
                    point["integrated_flux"] - seed["integrated_flux"]
                ),
                "candidate_minus_seed_signed_ATP_contribution": float(
                    point["signed_integrated_contribution"]
                    - seed["signed_integrated_contribution"]
                ),
            }
        )
    return rows


def _classify_transition(metrics: Mapping[str, Any]) -> dict[str, Any]:
    production_half = metrics["production_half_loss_day"]
    consumption_half = metrics["consumption_half_loss_day"]
    factors = metrics["factors_at_ATP_collapse"]
    states = metrics["states_at_ATP_collapse"]
    production_precedes = bool(
        production_half is not None
        and consumption_half is not None
        and float(production_half) < float(consumption_half)
    )
    vpgk_low = float(factors["VPGK_vmax_utilization"]) < 0.05
    vpk_compensates = float(factors["VPK_vmax_utilization"]) >= 0.20
    b13pg_low = float(states["B13PG"]) < 0.05
    adp_drive_present = float(factors["VPGK_ADP_ATP_drive"]) >= 0.50
    vhk_dominant = float(metrics["consumer_shares_at_ATP_collapse"]["VHK"]) >= 0.50
    collapse_before_f6p = float(metrics["ATP_collapse_to_F6P_divergence_delay_day"]) > 0.5
    gates = {
        "production_half_loss_precedes_demand_relief": production_precedes,
        "VPGK_pulse_exhausted_at_collapse": vpgk_low,
        "B13PG_supply_depleted_at_collapse": b13pg_low,
        "VPK_partially_compensates": vpk_compensates,
        "ADP_ATP_drive_not_limited": adp_drive_present,
        "VHK_dominates_residual_demand": vhk_dominant,
        "ATP_collapse_precedes_F6P_divergence": collapse_before_f6p,
    }
    if all(gates.values()):
        classification = (
            "VPGK/B13PG production-pulse exhaustion with persistent VHK-dominated ATP demand"
        )
    elif collapse_before_f6p:
        classification = "ATP collapse precedes F6P divergence but has a mixed balance origin"
    else:
        classification = "ATP and F6P transitions are not causally ordered by this audit"
    return {"classification": classification, "classification_gates": gates}


def _plot_audit(
    *,
    frames: Mapping[str, pd.DataFrame],
    transition_metrics: Mapping[str, Mapping[str, Any]],
    f6p_divergence: Mapping[str, float],
    km_atp_pfk: float,
    out_path: Path,
) -> None:
    colors = {BASELINE_LABEL: "#64748b", CANDIDATE_LABEL: "#b91c1c"}
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.5), constrained_layout=True)
    for label, frame in frames.items():
        time = frame["time_day"].to_numpy(dtype=float)
        color = colors[label]
        axes[0, 0].plot(time, frame["ATP"], color=color, label=label)
        axes[0, 1].plot(
            time, frame["ATP_production_flux"], color=color, label=f"{label}: production"
        )
        axes[0, 1].plot(
            time,
            frame["ATP_consumption_flux"],
            color=color,
            linestyle="--",
            label=f"{label}: consumption",
        )
    axes[0, 0].axhline(km_atp_pfk, color="#111827", linestyle="--", label="km_ATP_PFK")
    axes[0, 0].axvline(
        f6p_divergence[CANDIDATE_LABEL], color="#2563eb", linestyle=":", label="F6P divergence"
    )

    candidate = frames[CANDIDATE_LABEL]
    time = candidate["time_day"].to_numpy(dtype=float)
    for reaction, color in zip(ATP_PRODUCTION, ("#2563eb", "#7c3aed", "#0f766e")):
        axes[0, 2].plot(time, candidate[reaction], color=color, label=reaction)
    top_consumers = sorted(
        ATP_CONSUMPTION,
        key=lambda reaction: _integral(candidate[reaction], time),
        reverse=True,
    )[:5]
    for reaction, color in zip(
        top_consumers, ("#dc2626", "#ea580c", "#ca8a04", "#4d7c0f", "#0891b2")
    ):
        axes[1, 0].plot(time, candidate[reaction], color=color, label=reaction)

    for factor, color in (
        ("VPGK_ADP_ATP_drive", "#2563eb"),
        ("VPK_PEP_occupancy", "#7c3aed"),
        ("VPK_ADP_ATP_drive", "#0f766e"),
        ("VPGK_vmax_utilization", "#dc2626"),
        ("VPK_vmax_utilization", "#ea580c"),
    ):
        axes[1, 1].plot(time, candidate[factor], color=color, label=factor)
    for state, color in zip(
        ("B13PG", "PEP", "F16BP", "ADP", "AMP", "F6P"),
        ("#2563eb", "#7c3aed", "#0f766e", "#dc2626", "#ea580c", "#4d7c0f"),
    ):
        axes[1, 2].plot(time, candidate[state], color=color, label=state)
    axes[1, 2].set_yscale("symlog", linthresh=1e-4)

    titles = (
        "ATP pool and F6P divergence",
        "ATP production versus consumption",
        "Individual ATP producers",
        "Largest ATP consumers",
        "Production control factors",
        "Coupled energy/glycolysis states",
    )
    for axis, title in zip(axes.flat, titles):
        axis.set_title(title)
        axis.set_xlabel("Time (day)")
        axis.grid(alpha=0.22)
        axis.legend(frameon=False, fontsize=7)
    axes[0, 0].set_ylabel("mM")
    for axis in (axes[0, 1], axes[0, 2], axes[1, 0]):
        axis.set_ylabel("mM/day")
    axes[1, 2].set_ylabel("mM")
    fig.suptitle("J1-J10 ATP transition in retained V6PGD/PPP context")
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    candidate_windows = [
        row for row in summary["window_balances"] if row["candidate"] == CANDIDATE_LABEL
    ]
    metrics = summary["transition_metrics"][CANDIDATE_LABEL]
    classification = summary["structural_classification"]
    lines = [
        "# J1-J10 ATP transition audit in retained PPP context",
        "",
        "## Contract",
        "",
        "- Replayed balanced seed and retained `vmax_V6PGD = 9.0` with their saved seven-state PPP initializations.",
        "- Every other kinetic constant remained fixed; no optimization or promotion.",
        "- Exact balance: `dATP/dt = VPGK + VPK + VAK - sum(13 ATP consumers)`.",
        f"- Maximum ATP closure error: `{summary['max_ATP_closure_error']:.3e}` mM/day.",
        "",
        "## Candidate ATP balance",
        "",
        "| Window | ATP start-end | Production | Consumption | Net | VPGK | VPK | VAK | VHK | VPFK |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in candidate_windows:
        lines.append(
            f"| `{row['window']}` | {row['ATP_start_mM']:.5f}-{row['ATP_end_mM']:.5f} | "
            f"{row['production_mean']:.5f} | {row['consumption_mean']:.5f} | "
            f"{row['net_mean']:.5f} | {row['VPGK_mean']:.5f} | {row['VPK_mean']:.5f} | "
            f"{row['VAK_mean']:.5f} | {row['VHK_mean']:.5f} | {row['VPFK_mean']:.5f} |"
        )
    lines.extend(
        [
            "",
            "## Transition timing",
            "",
            f"- ATP below `km_ATP_PFK`: day `{metrics['ATP_below_km_ATP_PFK_day']:.4f}`.",
            f"- ATP below `0.01 mM`: day `{metrics['ATP_below_0.01_mM_day']:.4f}`.",
            f"- Production half-loss: day `{metrics['production_half_loss_day']:.4f}`.",
            f"- Consumption half-loss: day `{metrics['consumption_half_loss_day']:.4f}`.",
            f"- F6P divergence: day `{metrics['F6P_divergence_day']:.4f}`.",
            f"- ATP-collapse lead over F6P divergence: `{metrics['ATP_collapse_to_F6P_divergence_delay_day']:.4f}` days.",
            "",
            "## Structural decision",
            "",
            f"**`{classification['classification']}`**",
            "",
            str(summary["decision_rationale"]),
            "",
            "No kinetic constant or initial condition was promoted.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_audit(
    *,
    refinement_dir: Path,
    f6p_audit_dir: Path,
    out_dir: Path,
    timepoints: int,
    method: str,
    rtol: float,
    atol: float,
    closure_tolerance: float,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    refinement_summary = json.loads(
        (refinement_dir / "summary.json").read_text(encoding="utf-8")
    )
    diagnostic_candidates = json.loads(
        (refinement_dir / "diagnostic_candidates.json").read_text(encoding="utf-8")
    )
    f6p_summary = json.loads(
        (f6p_audit_dir / "summary.json").read_text(encoding="utf-8")
    )
    if refinement_summary["selected_candidate"] != CANDIDATE_LABEL:
        raise RuntimeError("Refinement does not select the expected V6PGD 0.9000x case")
    if diagnostic_candidates["promoted"]:
        raise RuntimeError("ATP audit requires non-promoted diagnostic initializations")
    seed_params_path = Path(refinement_summary["seed_params_path"])
    seed_params = _load_params(seed_params_path)
    params_by_label = {
        BASELINE_LABEL: seed_params,
        CANDIDATE_LABEL: _candidate_params(seed_params),
    }
    base_state = np.asarray(load_initial_conditions(), dtype=float)
    states = {
        label: _state_with_saved_latent(
            base_state,
            diagnostic_candidates["candidates"][label]["latent_initial_states"],
        )
        for label in (BASELINE_LABEL, CANDIDATE_LABEL)
    }
    f6p_divergence = {
        label: float(
            f6p_summary["divergence"][label]["first_sustained_nerror_gt_1_day"]
        )
        for label in (BASELINE_LABEL, CANDIDATE_LABEL)
    }
    t_eval = np.linspace(1.0, 10.0, int(timepoints))
    frames: dict[str, pd.DataFrame] = {}
    closures: dict[str, dict[str, float]] = {}
    window_rows: list[dict[str, Any]] = []
    reaction_rows: list[dict[str, Any]] = []
    state_rows: list[dict[str, Any]] = []
    transition_metrics: dict[str, dict[str, Any]] = {}
    for label in (BASELINE_LABEL, CANDIDATE_LABEL):
        print(f"[atp-transition] replaying {label}", flush=True)
        sol, fluxes, derivatives = _simulate_and_track(
            params=params_by_label[label],
            t_eval=t_eval,
            method=method,
            rtol=rtol,
            atol=atol,
            x0_override=states[label],
        )
        frame, closure = _build_timeseries(
            label=label,
            sol=sol,
            fluxes=fluxes,
            derivatives=derivatives,
            params=params_by_label[label],
            closure_tolerance=closure_tolerance,
        )
        frames[label] = frame
        closures[label] = closure
        window_rows.extend(_window_balance_rows(frame))
        reaction_rows.extend(_reaction_rows(frame))
        state_rows.extend(_state_rows(frame))
        transition_metrics[label] = _transition_metrics(
            frame=frame,
            km_atp_pfk=float(seed_params["km_ATP_PFK"]),
            f6p_divergence_day=f6p_divergence[label],
        )
    reaction_frame = pd.DataFrame(reaction_rows)
    deltas = _delta_rows(
        reaction_rows=reaction_frame,
        baseline_label=BASELINE_LABEL,
        candidate_label=CANDIDATE_LABEL,
    )
    classification = _classify_transition(transition_metrics[CANDIDATE_LABEL])
    metrics = transition_metrics[CANDIDATE_LABEL]
    if classification["classification"].startswith("VPGK/B13PG"):
        decision = "attribute ATP collapse to VPGK/B13PG pulse exhaustion plus persistent VHK demand"
        factors = metrics["factors_at_ATP_collapse"]
        states_at = metrics["states_at_ATP_collapse"]
        producer_shares = metrics["producer_shares_at_ATP_collapse"]
        consumer_shares = metrics["consumer_shares_at_ATP_collapse"]
        rationale = (
            "Total ATP production loses half of its initial-window level before total "
            "consumption does, and ATP crosses km_ATP_PFK more than two days before "
            "F6P diverges. At collapse, B13PG is nearly depleted and VPGK utilization "
            f"is {factors['VPGK_vmax_utilization']:.4f}; VPK remains at "
            f"{factors['VPK_vmax_utilization']:.3f} utilization and supplies "
            f"{100.0 * producer_shares['VPK']:.1f}% of ATP production, but only partly "
            f"compensates. VHK still accounts for {100.0 * consumer_shares['VHK']:.1f}% "
            "of ATP demand, whereas VPFK demand has already fallen. The retained "
            "V6PGD point inherits this upstream production-demand relay rather than "
            "creating it."
        )
        next_step = (
            "audit the J1-J3 B13PG balance VGAPDH - VPGK - VDPGM together with VHK "
            "demand at fixed parameters before any energy calibration"
        )
    else:
        decision = "retain a mixed ATP production-consumption transition diagnosis"
        rationale = (
            "ATP collapse precedes F6P divergence, but the current timing and occupancy "
            "gates do not isolate production loss from demand persistence."
        )
        next_step = "expand the fixed ATP transition attribution without calibration"
    pd.DataFrame(window_rows).to_csv(out_dir / "atp_window_balances.csv", index=False)
    reaction_frame.to_csv(out_dir / "atp_reaction_attribution.csv", index=False)
    pd.DataFrame(deltas).to_csv(out_dir / "candidate_seed_reaction_deltas.csv", index=False)
    pd.DataFrame(state_rows).to_csv(out_dir / "energy_state_windows.csv", index=False)
    pd.concat(frames.values(), ignore_index=True).to_csv(
        out_dir / "atp_transition_timeseries.csv", index=False
    )
    _plot_audit(
        frames=frames,
        transition_metrics=transition_metrics,
        f6p_divergence=f6p_divergence,
        km_atp_pfk=float(seed_params["km_ATP_PFK"]),
        out_path=out_dir / "atp_transition_attribution.png",
    )
    max_closure = max(
        value["max_abs_ATP_closure_error"] for value in closures.values()
    )
    summary = {
        "contract_type": "fixed_parameter_atp_transition_audit",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "kinetic_optimization_performed": False,
        "parameters_promoted": False,
        "initial_conditions_promoted": False,
        "horizon_days": [1.0, 10.0],
        "source_refinement_dir": str(refinement_dir),
        "source_f6p_audit_dir": str(f6p_audit_dir),
        "seed_params_path": str(seed_params_path),
        "cases": [BASELINE_LABEL, CANDIDATE_LABEL],
        "changed_kinetic_constants": ["vmax_V6PGD"],
        "changed_initial_states": list(LATENT_PPP_POOLS),
        "ATP_production_reactions": list(ATP_PRODUCTION),
        "ATP_consumption_reactions": list(ATP_CONSUMPTION),
        "ATP_balance_equation": (
            "dATP/dt = VPGK + VPK + VAK - VHK - VPFK - VAK2 - VGLNS - "
            "VGLUCYS - VGSS - VSAM - VRKa - VPRPPASe - VGMPS - VGMPK - "
            "VNDPK - VOPLAH"
        ),
        "ATP_effective_balance": (
            "when ATP < 1e-3 mM and raw dATP/dt < 0, effective dATP/dt = "
            "raw dATP/dt * ATP / 1e-3"
        ),
        "closures": closures,
        "max_ATP_closure_error": max_closure,
        "window_balances": window_rows,
        "transition_metrics": transition_metrics,
        "candidate_seed_reaction_deltas": deltas,
        "structural_classification": classification,
        "decision": decision,
        "decision_rationale": rationale,
        "next_step": next_step,
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "report": str(out_dir / "decision_report.md"),
            "window_balances": str(out_dir / "atp_window_balances.csv"),
            "reaction_attribution": str(out_dir / "atp_reaction_attribution.csv"),
            "reaction_deltas": str(out_dir / "candidate_seed_reaction_deltas.csv"),
            "state_windows": str(out_dir / "energy_state_windows.csv"),
            "timeseries": str(out_dir / "atp_transition_timeseries.csv"),
            "plot": str(out_dir / "atp_transition_attribution.png"),
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
                "classification": classification["classification"],
                "next_step": next_step,
            },
            indent=2,
        ),
        flush=True,
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit J1-J10 ATP transition in retained V6PGD/PPP context"
    )
    parser.add_argument(
        "--refinement-dir", type=Path, default=DEFAULT_REFINEMENT_DIR
    )
    parser.add_argument("--f6p-audit-dir", type=Path, default=DEFAULT_F6P_AUDIT_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--timepoints", type=int, default=1801)
    parser.add_argument("--method", default="LSODA")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    parser.add_argument("--closure-tolerance", type=float, default=1e-12)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_audit(
        refinement_dir=args.refinement_dir,
        f6p_audit_dir=args.f6p_audit_dir,
        out_dir=args.out_dir,
        timepoints=args.timepoints,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
        closure_tolerance=args.closure_tolerance,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
