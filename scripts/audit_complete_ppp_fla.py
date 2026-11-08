"""Complete Flux Learning Analysis audit of the Brodbar PPP.

This diagnostic reconstructs every coded pentose-phosphate pool balance,
compares the directly measured pools with Brodbar concentration and net-flux
teachers, and attributes model routing across the oxidative and non-oxidative
branches. Kinetic constants are held fixed and no candidate is promoted.
"""

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
from scipy.integrate import cumulative_trapezoid
from scipy.interpolate import PchipInterpolator


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
DEFAULT_OUT_DIR = (
    ROOT / "Simulations" / "brodbar" / "hermes" / "complete_ppp_fla_audit_46d"
)
HISTORICAL_INITIAL_CONDITIONS = SRC_DIR / "Initial_conditions_JA_Final.xls"

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from equadiff_brodbar import BRODBAR_METABOLITE_MAP  # noqa: E402
from MM_calibration import load_initial_conditions  # noqa: E402
from profile_atp_consumption_sinks import _all_experimental_curves  # noqa: E402
from profile_glycolysis_flux_bottlenecks import (  # noqa: E402
    _jsonable,
    _load_params,
    _simulate_and_track,
    _time_mean,
)
from run_glucose_utilization_fla import _nrmse  # noqa: E402
from diagnose_reversible_ppp_directionality import (  # noqa: E402
    CASE_TOGGLES,
    _case_params,
)
from audit_investment_phase_flux_matching import _time_grid  # noqa: E402


PPP_POOLS = (
    "G6P",
    "GL6P",
    "GO6P",
    "RU5P",
    "R5P",
    "X5P",
    "E4P",
    "S7P",
    "GA3P",
    "F6P",
)
MEASURED_PPP_POOLS = ("G6P", "GO6P", "F6P")
LATENT_PPP_POOLS = tuple(pool for pool in PPP_POOLS if pool not in MEASURED_PPP_POOLS)
CONTEXT_POOLS = ("GLC", "F16BP", "ATP", "PEP", "LAC", "EGLC", "ELAC")
PPP_CORE_FLUXES = (
    "VG6PDH",
    "VPGLS",
    "V6PGD",
    "VR5PI",
    "VR5PE",
    "VTKL1",
    "VTKL2",
    "VTAL",
)
WINDOWS = (
    ("early_1_2d", 1.0, 2.0),
    ("mid_10_20d", 10.0, 20.0),
    ("late_40_46d", 40.0, 46.0),
    ("full_1_46d", 1.0, 46.0),
)

# Coefficients reproduce dxdt[1:11] exactly, including pathway connections.
PPP_BALANCE_TERMS: dict[str, tuple[tuple[str, float], ...]] = {
    "G6P": (("VHK", 1.0), ("VPGI", -1.0), ("VG6PDH", -1.0)),
    "GL6P": (("VG6PDH", 1.0), ("VPGLS", -1.0)),
    "GO6P": (("VPGLS", 1.0), ("V6PGD", -1.0)),
    "RU5P": (("V6PGD", 1.0), ("VR5PI", -1.0), ("VR5PE", -1.0)),
    "R5P": (
        ("VR5PI", 1.0),
        ("VRKb", 1.0),
        ("VRKa", 1.0),
        ("VTKL1", -1.0),
        ("VPRPPASe", -1.0),
    ),
    "X5P": (("VR5PE", 1.0), ("VTKL1", -1.0), ("VTKL2", -1.0)),
    "E4P": (("VTAL", 1.0), ("VTKL2", -1.0)),
    "S7P": (("VTKL1", 1.0), ("VTAL", -1.0)),
    "GA3P": (
        ("VFDPA", 1.0),
        ("VTPI", 1.0),
        ("VGAPDH", -1.0),
        ("VTKL1", 1.0),
        ("VTKL2", 1.0),
        ("VTAL", -1.0),
    ),
    "F6P": (("VPGI", 1.0), ("VPFK", -1.0), ("VTKL2", 1.0), ("VTAL", 1.0)),
}


def _required_fluxes() -> tuple[str, ...]:
    return tuple(
        sorted({reaction for terms in PPP_BALANCE_TERMS.values() for reaction, _ in terms})
    )


def _initial_condition_audit_rows(
    historical_path: Path = HISTORICAL_INITIAL_CONDITIONS,
) -> list[dict[str, Any]]:
    current = np.asarray(load_initial_conditions(), dtype=float)
    historical_frame = pd.read_excel(historical_path, sheet_name=0, header=None)
    historical = {
        str(name).strip().upper(): float(value)
        for name, value in zip(historical_frame.iloc[:, 0], historical_frame.iloc[:, 1])
        if pd.notna(name) and pd.notna(value) and str(name).strip().upper() != "METABOLITE"
    }
    rows: list[dict[str, Any]] = []
    for pool in PPP_POOLS:
        current_value = float(current[int(BRODBAR_METABOLITE_MAP[pool])])
        historical_value = historical.get(pool)
        ratio = (
            current_value / max(abs(float(historical_value)), 1e-30)
            if historical_value is not None
            else float("nan")
        )
        rows.append(
            {
                "pool": pool,
                "directly_measured_brodbar": pool in MEASURED_PPP_POOLS,
                "current_initial_mM": current_value,
                "historical_JA_initial_mM": historical_value,
                "current_to_historical_ratio": ratio,
                "current_uses_generic_1mM_default": (
                    pool in LATENT_PPP_POOLS and abs(current_value - 1.0) <= 1e-12
                ),
                "large_latent_initialization_discrepancy": (
                    pool in LATENT_PPP_POOLS
                    and historical_value is not None
                    and (ratio > 5.0 or ratio < 0.2)
                ),
            }
        )
    return rows


def _reconstruct_pool_balance(
    fluxes: Mapping[str, np.ndarray], pool: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, np.ndarray]]:
    if pool not in PPP_BALANCE_TERMS:
        raise KeyError(f"Unsupported PPP pool: {pool}")
    contributions: dict[str, np.ndarray] = {}
    for reaction, coefficient in PPP_BALANCE_TERMS[pool]:
        if reaction not in fluxes:
            raise KeyError(f"FluxTracker is missing {reaction} required by {pool}")
        contributions[reaction] = coefficient * np.asarray(fluxes[reaction], dtype=float)
    net = sum(contributions.values())
    gross_input = sum(np.maximum(values, 0.0) for values in contributions.values())
    gross_output = sum(np.maximum(-values, 0.0) for values in contributions.values())
    return (
        np.asarray(gross_input, dtype=float),
        np.asarray(gross_output, dtype=float),
        np.asarray(net, dtype=float),
        contributions,
    )


def _effective_native_balance(
    net_flux: np.ndarray,
    concentration: np.ndarray,
    *,
    threshold: float = 1e-3,
) -> tuple[np.ndarray, np.ndarray]:
    net_flux = np.asarray(net_flux, dtype=float)
    concentration = np.asarray(concentration, dtype=float)
    effective = net_flux.copy()
    mask = (concentration < float(threshold)) & (net_flux < 0.0)
    effective[mask] *= np.maximum(concentration[mask], 0.0) / float(threshold)
    return effective, effective - net_flux


def _validate_closure(
    effective_flux: np.ndarray,
    derivative: np.ndarray,
    *,
    pool: str,
    tolerance: float,
) -> float:
    if np.asarray(effective_flux).shape != np.asarray(derivative).shape:
        raise ValueError(f"{pool} closure arrays have incompatible shapes")
    error = float(np.max(np.abs(np.asarray(effective_flux) - np.asarray(derivative))))
    if error > float(tolerance):
        raise RuntimeError(f"{pool} balance closure failed: max abs error={error:.6g}")
    return error


def _build_timeseries(
    *,
    label: str,
    sol: Any,
    fluxes: Mapping[str, np.ndarray],
    derivatives: np.ndarray,
    closure_tolerance: float,
) -> tuple[pd.DataFrame, dict[str, float]]:
    time = np.asarray(sol.t, dtype=float)
    data: dict[str, Any] = {"candidate": label, "time_day": time}
    for pool in (*PPP_POOLS, *CONTEXT_POOLS):
        data[pool] = np.asarray(sol.y[int(BRODBAR_METABOLITE_MAP[pool]), :], dtype=float)
    for reaction in _required_fluxes():
        if reaction not in fluxes:
            raise KeyError(f"FluxTracker is missing audited reaction {reaction}")
        data[reaction] = np.asarray(fluxes[reaction], dtype=float)

    closure: dict[str, float] = {}
    for pool in PPP_POOLS:
        gross_input, gross_output, raw_net, contributions = _reconstruct_pool_balance(
            fluxes, pool
        )
        concentration = np.asarray(data[pool], dtype=float)
        effective_net, damping_adjustment = _effective_native_balance(raw_net, concentration)
        derivative = np.asarray(
            derivatives[int(BRODBAR_METABOLITE_MAP[pool]), :], dtype=float
        )
        closure[pool] = _validate_closure(
            effective_net,
            derivative,
            pool=pool,
            tolerance=closure_tolerance,
        )
        concentration_change = concentration - float(concentration[0])
        cumulative_effective = cumulative_trapezoid(effective_net, time, initial=0.0)
        data[f"{pool}_gross_input"] = gross_input
        data[f"{pool}_gross_output"] = gross_output
        data[f"d{pool}_dt_raw_flux"] = raw_net
        data[f"d{pool}_dt_effective_flux"] = effective_net
        data[f"d{pool}_dt_ode"] = derivative
        data[f"{pool}_damping_adjustment"] = damping_adjustment
        data[f"{pool}_closure_error"] = derivative - effective_net
        data[f"{pool}_concentration_change"] = concentration_change
        data[f"{pool}_cumulative_effective_flux"] = cumulative_effective
        data[f"{pool}_integral_residual"] = concentration_change - cumulative_effective
        for reaction, values in contributions.items():
            data[f"{pool}_contrib_{reaction}"] = values
    return pd.DataFrame(data), closure


def _build_net_flux_teachers(
    exp_time: np.ndarray,
    exp_curves: Mapping[str, np.ndarray],
    *,
    dense_points: int,
) -> dict[str, Any]:
    measured = [pool for pool in MEASURED_PPP_POOLS if pool in exp_curves]
    if measured != list(MEASURED_PPP_POOLS):
        missing = sorted(set(MEASURED_PPP_POOLS) - set(measured))
        raise KeyError(f"Missing measured Brodbar PPP pools: {missing}")
    dense_time = np.linspace(float(exp_time[0]), float(exp_time[-1]), int(dense_points))
    curves: dict[str, Any] = {}
    for pool in measured:
        interpolator = PchipInterpolator(exp_time, np.asarray(exp_curves[pool], dtype=float))
        curves[pool] = {
            "equation": " + ".join(
                f"{coefficient:+g}*{reaction}"
                for reaction, coefficient in PPP_BALANCE_TERMS[pool]
            ),
            "experimental_values": np.asarray(exp_curves[pool], dtype=float).tolist(),
            "dense_concentration": np.asarray(interpolator(dense_time), dtype=float).tolist(),
            "dense_net_flux": np.asarray(interpolator.derivative()(dense_time), dtype=float).tolist(),
            "identifiability": "net_pool_balance_only",
        }
    return {
        "contract_type": "ppp_net_pool_flux_teacher",
        "contract_version": 1,
        "source": "Brodbar PCHIP concentration derivative",
        "timepoints": np.asarray(exp_time, dtype=float).tolist(),
        "dense_timepoints": dense_time.tolist(),
        "measured_pools": measured,
        "latent_pools": list(LATENT_PPP_POOLS),
        "curves": curves,
        "limitation": "Each derivative identifies only the net pool balance, not its individual reaction fluxes.",
    }


def _net_teacher_metric(model: np.ndarray, teacher: np.ndarray) -> dict[str, float]:
    model = np.asarray(model, dtype=float)
    teacher = np.asarray(teacher, dtype=float)
    residual = model - teacher
    rmse = float(np.sqrt(np.mean(residual**2)))
    scale = max(float(np.mean(np.abs(teacher))), float(np.ptp(teacher)), 1e-4)
    sign_tolerance = max(float(np.max(np.abs(teacher))) * 1e-8, 1e-12)
    active = np.abs(teacher) > sign_tolerance
    sign_agreement = float(np.mean(np.sign(model[active]) == np.sign(teacher[active]))) if np.any(active) else 1.0
    if np.std(model) > 1e-15 and np.std(teacher) > 1e-15:
        correlation = float(np.corrcoef(model, teacher)[0, 1])
    else:
        correlation = float("nan")
    return {
        "rmse": rmse,
        "nrmse": rmse / scale,
        "mean_model_flux": float(np.mean(model)),
        "mean_teacher_flux": float(np.mean(teacher)),
        "mean_bias": float(np.mean(residual)),
        "sign_agreement": sign_agreement,
        "correlation": correlation,
    }


def _measured_metric_rows(
    *,
    label: str,
    sol: Any,
    frame: pd.DataFrame,
    exp_time: np.ndarray,
    exp_curves: Mapping[str, np.ndarray],
    teachers: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    teacher_time = np.asarray(teachers["dense_timepoints"], dtype=float)
    for pool in MEASURED_PPP_POOLS:
        simulated = np.interp(
            exp_time,
            sol.t,
            sol.y[int(BRODBAR_METABOLITE_MAP[pool]), :],
        )
        concentration_metric = _nrmse(simulated, np.asarray(exp_curves[pool], dtype=float))
        model_net = np.interp(
            teacher_time,
            frame["time_day"].to_numpy(dtype=float),
            frame[f"d{pool}_dt_effective_flux"].to_numpy(dtype=float),
        )
        teacher_net = np.asarray(teachers["curves"][pool]["dense_net_flux"], dtype=float)
        rows.append(
            {
                "candidate": label,
                "pool": pool,
                "concentration_nrmse": float(concentration_metric["nrmse"]),
                "concentration_endpoint_error": float(concentration_metric["endpoint_error"]),
                "simulated_final": float(simulated[-1]),
                "experimental_final": float(exp_curves[pool][-1]),
                **{f"net_teacher_{key}": value for key, value in _net_teacher_metric(model_net, teacher_net).items()},
            }
        )
    return rows


def _context_metric_rows(
    *,
    label: str,
    sol: Any,
    exp_time: np.ndarray,
    exp_curves: Mapping[str, np.ndarray],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pool in CONTEXT_POOLS:
        if pool not in exp_curves:
            continue
        simulated = np.interp(
            exp_time,
            sol.t,
            sol.y[int(BRODBAR_METABOLITE_MAP[pool]), :],
        )
        metric = _nrmse(simulated, np.asarray(exp_curves[pool], dtype=float))
        rows.append(
            {
                "candidate": label,
                "pool": pool,
                "nrmse": float(metric["nrmse"]),
                "endpoint_error": float(metric["endpoint_error"]),
                "simulated_final": float(simulated[-1]),
                "experimental_final": float(exp_curves[pool][-1]),
            }
        )
    return rows


def _window_and_attribution_rows(
    frame: pd.DataFrame,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    label = str(frame["candidate"].iloc[0])
    time = frame["time_day"].to_numpy(dtype=float)
    window_rows: list[dict[str, Any]] = []
    attribution_rows: list[dict[str, Any]] = []
    for window, start, end in WINDOWS:
        mask = (time >= start - 1e-12) & (time <= min(end, time[-1]) + 1e-12)
        if np.count_nonzero(mask) < 2:
            continue
        window_time = time[mask]
        for pool in PPP_POOLS:
            gross_input = frame.loc[mask, f"{pool}_gross_input"].to_numpy(dtype=float)
            gross_output = frame.loc[mask, f"{pool}_gross_output"].to_numpy(dtype=float)
            effective_net = frame.loc[mask, f"d{pool}_dt_effective_flux"].to_numpy(dtype=float)
            concentration = frame.loc[mask, pool].to_numpy(dtype=float)
            mean_input = _time_mean(gross_input, window_time)
            mean_output = _time_mean(gross_output, window_time)
            window_rows.append(
                {
                    "candidate": label,
                    "window": window,
                    "pool": pool,
                    "start_day": float(window_time[0]),
                    "end_day": float(window_time[-1]),
                    "mean_gross_input": mean_input,
                    "mean_gross_output": mean_output,
                    "output_input_ratio": mean_output / max(abs(mean_input), 1e-30),
                    "mean_effective_net_flux": _time_mean(effective_net, window_time),
                    "concentration_start": float(concentration[0]),
                    "concentration_end": float(concentration[-1]),
                    "concentration_change": float(concentration[-1] - concentration[0]),
                    "integrated_effective_net_flux": float(np.trapezoid(effective_net, window_time)),
                    "max_abs_closure_error": float(
                        np.max(np.abs(frame.loc[mask, f"{pool}_closure_error"].to_numpy(dtype=float)))
                    ),
                }
            )
            gross_turnover = mean_input + mean_output
            for reaction, coefficient in PPP_BALANCE_TERMS[pool]:
                flux_values = frame.loc[mask, reaction].to_numpy(dtype=float)
                contribution = frame.loc[mask, f"{pool}_contrib_{reaction}"].to_numpy(dtype=float)
                mean_contribution = _time_mean(contribution, window_time)
                attribution_rows.append(
                    {
                        "candidate": label,
                        "window": window,
                        "pool": pool,
                        "reaction": reaction,
                        "stoichiometric_coefficient": coefficient,
                        "mean_signed_flux": _time_mean(flux_values, window_time),
                        "mean_pool_contribution": mean_contribution,
                        "role_at_window_mean": "input" if mean_contribution >= 0.0 else "output",
                        "absolute_turnover_share": abs(mean_contribution) / max(gross_turnover, 1e-30),
                    }
                )
    return window_rows, attribution_rows


def _routing_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    label = str(frame["candidate"].iloc[0])
    time = frame["time_day"].to_numpy(dtype=float)
    rows: list[dict[str, Any]] = []
    for window, start, end in WINDOWS:
        mask = (time >= start - 1e-12) & (time <= min(end, time[-1]) + 1e-12)
        if np.count_nonzero(mask) < 2:
            continue
        window_time = time[mask]
        means = {
            reaction: _time_mean(frame.loc[mask, reaction].to_numpy(dtype=float), window_time)
            for reaction in PPP_CORE_FLUXES
        }
        vtkl2 = frame.loc[mask, "VTKL2"].to_numpy(dtype=float)
        vtal = frame.loc[mask, "VTAL"].to_numpy(dtype=float)
        rows.append(
            {
                "candidate": label,
                "window": window,
                **{f"mean_{reaction}": value for reaction, value in means.items()},
                "mean_positive_F6P_return": _time_mean(
                    np.maximum(vtkl2, 0.0) + np.maximum(vtal, 0.0), window_time
                ),
                "mean_reverse_F6P_drain": _time_mean(
                    np.maximum(-vtkl2, 0.0) + np.maximum(-vtal, 0.0), window_time
                ),
                "mean_net_F6P_PPP_return": means["VTKL2"] + means["VTAL"],
                "mean_net_GA3P_PPP_return": means["VTKL1"] + means["VTKL2"] - means["VTAL"],
                "VTKL2_fraction_negative": float(np.mean(vtkl2 < 0.0)),
                "VTAL_fraction_negative": float(np.mean(vtal < 0.0)),
            }
        )
    return rows


def _teacher_window_rows(
    *,
    label: str,
    frame: pd.DataFrame,
    teachers: Mapping[str, Any],
) -> list[dict[str, Any]]:
    teacher_time = np.asarray(teachers["dense_timepoints"], dtype=float)
    rows: list[dict[str, Any]] = []
    for window, start, end in WINDOWS:
        mask = (teacher_time >= start - 1e-12) & (teacher_time <= end + 1e-12)
        if np.count_nonzero(mask) < 2:
            continue
        for pool in MEASURED_PPP_POOLS:
            teacher = np.asarray(teachers["curves"][pool]["dense_net_flux"], dtype=float)[mask]
            model = np.interp(
                teacher_time[mask],
                frame["time_day"].to_numpy(dtype=float),
                frame[f"d{pool}_dt_effective_flux"].to_numpy(dtype=float),
            )
            rows.append(
                {
                    "candidate": label,
                    "window": window,
                    "pool": pool,
                    **_net_teacher_metric(model, teacher),
                }
            )
    return rows


def _lookup(rows: Sequence[Mapping[str, Any]], *keys: str) -> dict[tuple[str, ...], Mapping[str, Any]]:
    return {tuple(str(row[key]) for key in keys): row for row in rows}


def _select_next_hypothesis(
    measured_rows: Sequence[Mapping[str, Any]],
    context_rows: Sequence[Mapping[str, Any]],
    routing_rows: Sequence[Mapping[str, Any]],
    max_closure: float,
    closure_tolerance: float,
    initialization_rows: Sequence[Mapping[str, Any]] = (),
) -> tuple[str, str, dict[str, Any]]:
    if max_closure > closure_tolerance:
        return (
            "correct the PPP ODE reconstruction before calibration",
            "At least one native pool balance did not close point by point.",
            {},
        )
    problematic_initialization = [
        row
        for row in initialization_rows
        if bool(row.get("current_uses_generic_1mM_default"))
        and bool(row.get("large_latent_initialization_discrepancy"))
    ]
    if problematic_initialization:
        return (
            "run a fixed historical latent-PPP initial-condition replay before changing kinetics",
            "Several unmeasured PPP pools are initialized by a generic 1 mM fallback despite substantially different values in Initial_conditions_JA_Final.xls. These latent pools generate the dominant J1-J2 PPP transient, so kinetic attribution is confounded until their initialization is tested with all parameters fixed.",
            {
                "problematic_latent_initializations": [
                    {
                        "pool": row["pool"],
                        "current_initial_mM": row["current_initial_mM"],
                        "historical_JA_initial_mM": row["historical_JA_initial_mM"],
                        "current_to_historical_ratio": row["current_to_historical_ratio"],
                    }
                    for row in problematic_initialization
                ],
                "conditional_kinetic_hypothesis": "fixed forward-only VTAL product-feedback gate",
            },
        )
    measured = _lookup(measured_rows, "candidate", "pool")
    context = _lookup(context_rows, "candidate", "pool")
    routing = _lookup(routing_rows, "candidate", "window")
    seed_f6p = measured[("seed_irreversible", "F6P")]
    vtal_f6p = measured[("reversible_VTAL", "F6P")]
    comparison_window = (
        "late_40_46d"
        if ("seed_irreversible", "late_40_46d") in routing
        else "full_1_46d"
    )
    seed_late = routing[("seed_irreversible", comparison_window)]
    vtal_late = routing[("reversible_VTAL", comparison_window)]
    f6p_gain = 1.0 - float(vtal_f6p["concentration_nrmse"]) / max(
        float(seed_f6p["concentration_nrmse"]), 1e-30
    )
    g6p_endpoint_worse = abs(float(measured[("reversible_VTAL", "G6P")]["concentration_endpoint_error"])) > abs(
        float(measured[("seed_irreversible", "G6P")]["concentration_endpoint_error"])
    )
    f16bp_endpoint_worse = abs(float(context[("reversible_VTAL", "F16BP")]["endpoint_error"])) > abs(
        float(context[("seed_irreversible", "F16BP")]["endpoint_error"])
    )
    evidence = {
        "reversible_VTAL_F6P_relative_improvement": f6p_gain,
        "routing_comparison_window": comparison_window,
        "seed_late_net_F6P_PPP_return": float(seed_late["mean_net_F6P_PPP_return"]),
        "reversible_VTAL_late_net_F6P_PPP_return": float(vtal_late["mean_net_F6P_PPP_return"]),
        "reversible_VTAL_late_reverse_F6P_drain": float(vtal_late["mean_reverse_F6P_drain"]),
        "reversible_VTAL_G6P_endpoint_worse": g6p_endpoint_worse,
        "reversible_VTAL_F16BP_endpoint_worse": f16bp_endpoint_worse,
    }
    if (
        f6p_gain >= 0.10
        and float(vtal_late["mean_reverse_F6P_drain"]) > 0.0
        and (g6p_endpoint_worse or f16bp_endpoint_worse)
    ):
        return (
            "test a fixed forward-only VTAL product-feedback gate before optimization",
            "The PPP audit confirms that reducing VTAL-derived F6P return is useful, while allowing sustained reverse VTAL over-drains late F6P/F16BP and transfers carbon upstream. The next probe should attenuate forward VTAL as F6P accumulates but must never make VTAL negative.",
            evidence,
        )
    return (
        "defer PPP kinetic calibration pending stronger directionality information",
        "The measured net-pool teachers do not isolate a single non-oxidative PPP reaction strongly enough for a guarded structural probe.",
        evidence,
    )


def _plot_measured(
    *,
    frames: Mapping[str, pd.DataFrame],
    exp_time: np.ndarray,
    exp_curves: Mapping[str, np.ndarray],
    teachers: Mapping[str, Any],
    out_path: Path,
) -> None:
    colors = {
        "seed_irreversible": "#64748b",
        "reversible_VTKL2": "#2563eb",
        "reversible_VTAL": "#b45309",
        "reversible_both": "#dc2626",
    }
    teacher_time = np.asarray(teachers["dense_timepoints"], dtype=float)
    fig, axes = plt.subplots(2, 3, figsize=(16, 9), constrained_layout=True)
    for column, pool in enumerate(MEASURED_PPP_POOLS):
        axis = axes[0, column]
        for label, frame in frames.items():
            axis.plot(frame["time_day"], frame[pool], color=colors[label], linewidth=2, label=label)
        axis.scatter(exp_time, exp_curves[pool], color="#111827", s=28, zorder=5, label="Brodbar")
        axis.set_title(f"{pool} concentration")
        axis.set_xlabel("Time (days)")
        axis.set_ylabel("mM")
        axis.grid(True, alpha=0.22)
        if pool in {"G6P", "F6P"}:
            axis.set_yscale("log")

        axis = axes[1, column]
        axis.plot(
            teacher_time,
            teachers["curves"][pool]["dense_net_flux"],
            color="#111827",
            linewidth=2.4,
            linestyle=":",
            label="Brodbar net teacher",
        )
        for label, frame in frames.items():
            axis.plot(
                frame["time_day"],
                frame[f"d{pool}_dt_effective_flux"],
                color=colors[label],
                linewidth=1.8,
                label=label,
            )
        axis.axhline(0.0, color="#111827", linewidth=0.8)
        axis.set_title(f"Net pool flux d{pool}/dt")
        axis.set_xlabel("Time (days)")
        axis.set_ylabel("mM/day")
        axis.set_yscale("symlog", linthresh=1e-3)
        axis.grid(True, alpha=0.22)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=5, frameon=False)
    fig.suptitle("Brodbar FLA: directly measured PPP pools", fontsize=15)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _plot_latent(frames: Mapping[str, pd.DataFrame], out_path: Path) -> None:
    colors = {
        "seed_irreversible": "#64748b",
        "reversible_VTKL2": "#2563eb",
        "reversible_VTAL": "#b45309",
        "reversible_both": "#dc2626",
    }
    fig, axes = plt.subplots(2, 4, figsize=(17, 9), constrained_layout=True)
    for axis, pool in zip(axes.flat, LATENT_PPP_POOLS):
        for label, frame in frames.items():
            axis.plot(frame["time_day"], frame[pool], color=colors[label], linewidth=2, label=label)
        axis.set_title(f"{pool} latent concentration")
        axis.set_xlabel("Time (days)")
        axis.set_ylabel("mM")
        axis.grid(True, alpha=0.22)
    axes.flat[-1].axis("off")
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False)
    fig.suptitle("Model-implied PPP pools without direct Brodbar measurements", fontsize=15)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _plot_routing(frames: Mapping[str, pd.DataFrame], out_path: Path) -> None:
    colors = {
        "seed_irreversible": "#64748b",
        "reversible_VTKL2": "#2563eb",
        "reversible_VTAL": "#b45309",
        "reversible_both": "#dc2626",
    }
    fig, axes = plt.subplots(2, 4, figsize=(17, 9), constrained_layout=True)
    for axis, reaction in zip(axes.flat, PPP_CORE_FLUXES):
        for label, frame in frames.items():
            axis.plot(frame["time_day"], frame[reaction], color=colors[label], linewidth=1.9, label=label)
        axis.axhline(0.0, color="#111827", linewidth=0.8)
        axis.set_title(reaction)
        axis.set_xlabel("Time (days)")
        axis.set_ylabel("mM/day")
        axis.set_yscale("symlog", linthresh=1e-3)
        axis.grid(True, alpha=0.22)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False)
    fig.suptitle("Oxidative and non-oxidative PPP routing", fontsize=15)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    measured = _lookup(summary["measured_pool_metrics"], "candidate", "pool")
    routing = _lookup(summary["routing_windows"], "candidate", "window")
    lines = [
        "# Complete PPP Flux Learning Analysis audit",
        "",
        "## Contract",
        "",
        f"- Generated: {summary['generated_at']}",
        f"- Horizon: `{summary['t_max']:.0f}` days.",
        "- Four fixed replays: irreversible seed, reversible VTKL2, reversible VTAL, and both reversible.",
        "- No kinetic constant fitted, optimized, or promoted.",
        f"- Maximum pointwise closure error across ten PPP pools: `{summary['max_pointwise_closure_error']:.3e}` mM/day.",
        "",
        "## Initial-condition provenance",
        "",
        "| Pool | Brodbar measured | Current initial | Historical JA initial | Current/JA | Generic 1 mM fallback |",
        "|---|---|---:|---:|---:|---|",
    ]
    for row in summary["initial_condition_audit"]:
        historical = row["historical_JA_initial_mM"]
        lines.append(
            f"| `{row['pool']}` | `{row['directly_measured_brodbar']}` | "
            f"{row['current_initial_mM']:.6g} | "
            f"{float(historical):.6g} | {row['current_to_historical_ratio']:.6g} | "
            f"`{row['current_uses_generic_1mM_default']}` |"
        )
    lines.extend(
        [
        "",
        "## Data identifiability",
        "",
        "Brodbar directly measures `G6P`, `GO6P`, and `F6P` in the coded PPP. Their PCHIP derivatives identify only these net balances:",
        "",
        "```text",
        "dG6P/dt  = VHK - VPGI - VG6PDH",
        "dGO6P/dt = VPGLS - V6PGD",
        "dF6P/dt  = VPGI + VTKL2 + VTAL - VPFK",
        "```",
        "",
        "The individual fluxes in each equation are not uniquely identifiable from the measured concentration alone. GL6P, RU5P, R5P, X5P, E4P, S7P, and GA3P are latent model pools in this dataset.",
        "",
        "## Measured PPP pools",
        "",
        "| Case | Pool | Concentration nRMSE | Net-teacher nRMSE | Sign agreement | Final model | Final experiment |",
        "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for label in CASE_TOGGLES:
        for pool in MEASURED_PPP_POOLS:
            row = measured[(label, pool)]
            lines.append(
                f"| `{label}` | `{pool}` | {row['concentration_nrmse']:.6g} | "
                f"{row['net_teacher_nrmse']:.6g} | {row['net_teacher_sign_agreement']:.3f} | "
                f"{row['simulated_final']:.6g} | {row['experimental_final']:.6g} |"
            )
    lines.extend(
        [
            "",
            "## PPP routing by time window",
            "",
            "| Case | Window | VG6PDH | V6PGD | Net F6P return | Reverse F6P drain | Net GA3P return |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for label in CASE_TOGGLES:
        for window in ("early_1_2d", "mid_10_20d", "late_40_46d"):
            row = routing.get((label, window))
            if row is None:
                continue
            lines.append(
                f"| `{label}` | `{window}` | {row['mean_VG6PDH']:.6g} | "
                f"{row['mean_V6PGD']:.6g} | {row['mean_net_F6P_PPP_return']:.6g} | "
                f"{row['mean_reverse_F6P_drain']:.6g} | {row['mean_net_GA3P_PPP_return']:.6g} |"
            )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"**`{summary['decision']}`**",
            "",
            summary["decision_rationale"],
            "",
            "The proposed next probe remains structural and fixed. It must be evaluated with the same concentration, endpoint, teacher-flux, ATP, PEP, and lactate safeguards before any parameter optimization.",
            "",
            "No parameter file was generated by this audit.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_audit(
    *,
    out_dir: Path,
    seed_params_path: Path,
    t_max: float,
    timepoints: int,
    early_timepoints: int,
    teacher_dense_points: int,
    method: str,
    rtol: float,
    atol: float,
    closure_tolerance: float,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    seed_params = _load_params(seed_params_path)
    t_eval = _time_grid(t_max, timepoints, early_timepoints)
    exp_time, exp_curves = _all_experimental_curves(t_max)
    teachers = _build_net_flux_teachers(
        exp_time,
        exp_curves,
        dense_points=teacher_dense_points,
    )
    initial_condition_rows = _initial_condition_audit_rows()

    frames: dict[str, pd.DataFrame] = {}
    closure_by_case: dict[str, dict[str, float]] = {}
    measured_rows: list[dict[str, Any]] = []
    context_rows: list[dict[str, Any]] = []
    window_rows: list[dict[str, Any]] = []
    attribution_rows: list[dict[str, Any]] = []
    routing_rows: list[dict[str, Any]] = []
    teacher_window_rows: list[dict[str, Any]] = []
    case_contracts: list[dict[str, Any]] = []

    for label, toggles in CASE_TOGGLES.items():
        params, changed = _case_params(seed_params, toggles)
        print(f"[complete-ppp] simulating {label}", flush=True)
        sol, fluxes, derivatives = _simulate_and_track(
            params=params,
            t_eval=t_eval,
            method=method,
            rtol=rtol,
            atol=atol,
        )
        frame, closure = _build_timeseries(
            label=label,
            sol=sol,
            fluxes=fluxes,
            derivatives=derivatives,
            closure_tolerance=closure_tolerance,
        )
        frames[label] = frame
        closure_by_case[label] = closure
        measured_rows.extend(
            _measured_metric_rows(
                label=label,
                sol=sol,
                frame=frame,
                exp_time=exp_time,
                exp_curves=exp_curves,
                teachers=teachers,
            )
        )
        context_rows.extend(
            _context_metric_rows(
                label=label,
                sol=sol,
                exp_time=exp_time,
                exp_curves=exp_curves,
            )
        )
        case_windows, case_attributions = _window_and_attribution_rows(frame)
        window_rows.extend(case_windows)
        attribution_rows.extend(case_attributions)
        routing_rows.extend(_routing_rows(frame))
        teacher_window_rows.extend(
            _teacher_window_rows(label=label, frame=frame, teachers=teachers)
        )
        case_contracts.append(
            {
                "candidate": label,
                "fixed_toggles": dict(toggles),
                "changed_configuration_keys": changed,
            }
        )

    max_closure = max(error for case in closure_by_case.values() for error in case.values())
    decision, rationale, evidence = _select_next_hypothesis(
        measured_rows,
        context_rows,
        routing_rows,
        max_closure,
        closure_tolerance,
        initial_condition_rows,
    )

    timeseries_path = out_dir / "complete_ppp_timeseries.csv"
    window_path = out_dir / "complete_ppp_pool_windows.csv"
    attribution_path = out_dir / "complete_ppp_reaction_attribution.csv"
    routing_path = out_dir / "complete_ppp_routing_windows.csv"
    metrics_path = out_dir / "complete_ppp_measured_metrics.csv"
    context_path = out_dir / "complete_ppp_context_metrics.csv"
    teacher_windows_path = out_dir / "complete_ppp_teacher_windows.csv"
    initial_conditions_path = out_dir / "complete_ppp_initial_condition_audit.csv"
    teacher_path = out_dir / "ppp_net_pool_flux_teachers.json"
    measured_plot_path = out_dir / "ppp_measured_pool_fla.png"
    latent_plot_path = out_dir / "ppp_latent_pool_trajectories.png"
    routing_plot_path = out_dir / "ppp_flux_routing.png"

    pd.concat(frames.values(), ignore_index=True).to_csv(timeseries_path, index=False)
    pd.DataFrame(window_rows).to_csv(window_path, index=False)
    pd.DataFrame(attribution_rows).to_csv(attribution_path, index=False)
    pd.DataFrame(routing_rows).to_csv(routing_path, index=False)
    pd.DataFrame(measured_rows).to_csv(metrics_path, index=False)
    pd.DataFrame(context_rows).to_csv(context_path, index=False)
    pd.DataFrame(teacher_window_rows).to_csv(teacher_windows_path, index=False)
    pd.DataFrame(initial_condition_rows).to_csv(initial_conditions_path, index=False)
    teacher_path.write_text(json.dumps(_jsonable(teachers), indent=2), encoding="utf-8")
    _plot_measured(
        frames=frames,
        exp_time=exp_time,
        exp_curves=exp_curves,
        teachers=teachers,
        out_path=measured_plot_path,
    )
    _plot_latent(frames, latent_plot_path)
    _plot_routing(frames, routing_plot_path)

    summary = {
        "contract_type": "complete_ppp_flux_learning_audit",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "optimization_performed": False,
        "parameters_promoted": False,
        "parameter_artifacts_generated": False,
        "default_model_family_preserved": True,
        "seed_params_path": str(seed_params_path),
        "t_max": float(t_max),
        "timepoints": int(t_eval.size),
        "teacher_dense_points": int(teacher_dense_points),
        "solver": {"method": method, "rtol": float(rtol), "atol": float(atol)},
        "closure_tolerance": float(closure_tolerance),
        "measured_ppp_pools": list(MEASURED_PPP_POOLS),
        "latent_ppp_pools": list(LATENT_PPP_POOLS),
        "balance_terms": PPP_BALANCE_TERMS,
        "case_contracts": case_contracts,
        "closure_by_case": closure_by_case,
        "max_pointwise_closure_error": max_closure,
        "initial_condition_audit": initial_condition_rows,
        "measured_pool_metrics": measured_rows,
        "context_metrics": context_rows,
        "pool_windows": window_rows,
        "reaction_attribution": attribution_rows,
        "routing_windows": routing_rows,
        "teacher_windows": teacher_window_rows,
        "decision": decision,
        "decision_rationale": rationale,
        "decision_evidence": evidence,
        "limitations": [
            "Only G6P, GO6P, and F6P are directly measured among the coded PPP pools.",
            "Experimental concentration derivatives identify net pool balances, not unique reaction fluxes.",
            "Latent PPP trajectories and reaction attributions remain model-dependent.",
            "The reversible saturation-difference probes are not Haldane-consistent.",
        ],
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "report": str(out_dir / "decision_report.md"),
            "teachers": str(teacher_path),
            "timeseries": str(timeseries_path),
            "pool_windows": str(window_path),
            "reaction_attribution": str(attribution_path),
            "routing_windows": str(routing_path),
            "measured_metrics": str(metrics_path),
            "context_metrics": str(context_path),
            "teacher_windows": str(teacher_windows_path),
            "initial_condition_audit": str(initial_conditions_path),
            "measured_plot": str(measured_plot_path),
            "latent_plot": str(latent_plot_path),
            "routing_plot": str(routing_plot_path),
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
                "max_closure": max_closure,
                "decision": decision,
                "decision_evidence": evidence,
            },
            indent=2,
        ),
        flush=True,
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit all coded PPP pools with Brodbar FLA")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--seed-params", type=Path, default=DEFAULT_SEED_PARAMS)
    parser.add_argument("--t-max", type=float, default=46.0)
    parser.add_argument("--timepoints", type=int, default=361)
    parser.add_argument("--early-timepoints", type=int, default=100)
    parser.add_argument("--teacher-dense-points", type=int, default=181)
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
        t_max=args.t_max,
        timepoints=args.timepoints,
        early_timepoints=args.early_timepoints,
        teacher_dense_points=args.teacher_dense_points,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
        closure_tolerance=args.closure_tolerance,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
