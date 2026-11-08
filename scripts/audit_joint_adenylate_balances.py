"""Audit joint ATP, ADP, and AMP teachers and adenylate-kinase directionality."""

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
BRODBAR_DATA = SRC_DIR / "Data_Bordbar_et_al_exp.xlsx"
DEFAULT_OUT_DIR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "joint_adenylate_balance_3x_qss_J1_J3"
)

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from equadiff_brodbar import BRODBAR_METABOLITE_MAP, MODEL_NETWORK_VERSION  # noqa: E402
from audit_atp_partition_vdpgm_3x_qss_b13pg import (  # noqa: E402
    CANDIDATE_LABEL,
    WINDOWS,
    _build_contract,
)
from audit_atp_transition_v6pgd_ppp_context import _integral, _time_mean  # noqa: E402
from audit_b13pg_balance_v6pgd_ppp_context import (  # noqa: E402
    _effective_balance,
    _mm,
)
from profile_glycolysis_flux_bottlenecks import (  # noqa: E402
    _jsonable,
    _simulate_and_track,
)


POOLS = ("ATP", "ADP", "AMP")
POOL_INDICES = {name: int(BRODBAR_METABOLITE_MAP[name]) for name in POOLS}
PRIMARY_TEACHER = "pchip_full_record"
SENSITIVITY_TEACHER = "linear_J1_J4"

ATP_TERMS = {
    "VPGK": 1.0,
    "VPK": 1.0,
    "VAK": 1.0,
    "VHK": -1.0,
    "VPFK": -1.0,
    "VAK2": -1.0,
    "VGLNS": -1.0,
    "VGLUCYS": -1.0,
    "VGSS": -1.0,
    "VSAM": -1.0,
    "VRKa": -1.0,
    "VPRPPASe": -1.0,
    "VGMPS": -1.0,
    "VGMPK": -1.0,
    "VNDPK": -1.0,
    "VOPLAH": -1.0,
}
ADP_TERMS = {
    "VHK": 1.0,
    "VPFK": 1.0,
    "VAK2": 1.0,
    "VGLNS": 1.0,
    "VGLUCYS": 1.0,
    "VGSS": 1.0,
    "VRKa": 1.0,
    "VGMPK": 1.0,
    "VNDPK": 1.0,
    "VOPLAH": 1.0,
    "VPGK": -1.0,
    "VPK": -1.0,
    "VAK": -2.0,
}
AMP_TERMS = {
    "VAK": 1.0,
    "VAK2": 1.0,
    "VADSL": 1.0,
    "VPRPPASe": 1.0,
    "VGMPS": 1.0,
    "VAPRT": 1.0,
    "VAMPD1": -1.0,
    "VAMP_NT": -1.0,
}
POOL_TERMS = {"ATP": ATP_TERMS, "ADP": ADP_TERMS, "AMP": AMP_TERMS}
DEFAULT_PARAMS = {
    "vmax_VAK": 0.8,
    "vmax_VAK_rev": 0.5,
    "vmax_VAK2": 0.5,
    "vmax_VSAM": 0.2,
    "vmax_VAMPD1": 0.5,
    "km_ADP": 0.402663,
    "km_AMP": 0.282865,
    "km_ATP": 0.569395,
}


def _sum_terms(*term_sets: Mapping[str, float]) -> dict[str, float]:
    result: dict[str, float] = {}
    for terms in term_sets:
        for reaction, coefficient in terms.items():
            result[reaction] = result.get(reaction, 0.0) + float(coefficient)
    return {
        reaction: coefficient
        for reaction, coefficient in result.items()
        if not np.isclose(coefficient, 0.0)
    }


TOTAL_TERMS = _sum_terms(ATP_TERMS, ADP_TERMS, AMP_TERMS)


def _param(params: Mapping[str, Any], name: str) -> float:
    return float(params.get(name, DEFAULT_PARAMS[name]))


def _raw_balance(
    fluxes: Mapping[str, np.ndarray], terms: Mapping[str, float]
) -> np.ndarray:
    missing = [reaction for reaction in terms if reaction not in fluxes]
    if missing:
        raise KeyError(f"FluxTracker is missing adenylate reactions: {missing}")
    return sum(
        coefficient * np.asarray(fluxes[reaction], dtype=float)
        for reaction, coefficient in terms.items()
    )


def _load_teachers(
    path: Path = BRODBAR_DATA,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    frame = pd.read_excel(path, engine="openpyxl")
    names = frame.iloc[:, 0].astype(str).str.strip().str.upper()
    time = np.asarray([float(value) for value in frame.columns[1:]], dtype=float)
    curves: dict[str, np.ndarray] = {}
    for pool in POOLS:
        rows = frame.loc[names == pool]
        if len(rows) != 1:
            raise RuntimeError(f"Expected exactly one {pool} row, found {len(rows)}")
        curves[pool] = rows.iloc[0, 1:].to_numpy(dtype=float)
    return time, curves


def _teacher_variants(
    exp_time: np.ndarray,
    curves: Mapping[str, np.ndarray],
    grid: np.ndarray,
) -> dict[str, dict[str, tuple[np.ndarray, np.ndarray]]]:
    result: dict[str, dict[str, tuple[np.ndarray, np.ndarray]]] = {
        PRIMARY_TEACHER: {},
        SENSITIVITY_TEACHER: {},
    }
    for pool in POOLS:
        values = np.asarray(curves[pool], dtype=float)
        pchip = PchipInterpolator(exp_time, values, extrapolate=False)
        slope = float((values[1] - values[0]) / (exp_time[1] - exp_time[0]))
        result[PRIMARY_TEACHER][pool] = (
            np.asarray(pchip(grid), dtype=float),
            np.asarray(pchip.derivative()(grid), dtype=float),
        )
        result[SENSITIVITY_TEACHER][pool] = (
            values[0] + slope * (grid - exp_time[0]),
            np.full_like(grid, slope),
        )
    return result


def _vak_components(
    *, params: Mapping[str, Any], adp: np.ndarray, amp: np.ndarray, atp: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    adp_floor = np.maximum(np.asarray(adp, dtype=float), 1e-6)
    amp_floor = np.maximum(np.asarray(amp, dtype=float), 1e-6)
    atp_floor = np.maximum(np.asarray(atp, dtype=float), 1e-6)
    forward = _param(params, "vmax_VAK") * _mm(
        adp_floor, _param(params, "km_ADP")
    )
    reverse = (
        _param(params, "vmax_VAK_rev")
        * _mm(amp_floor, _param(params, "km_AMP"))
        * _mm(atp_floor, _param(params, "km_ATP"))
    )
    return forward, reverse, forward - reverse


def _build_native_frame(
    *,
    state: np.ndarray,
    params: Mapping[str, Any],
    time: np.ndarray,
    method: str,
    rtol: float,
    atol: float,
    closure_tolerance: float,
) -> tuple[pd.DataFrame, dict[str, float]]:
    if params.get("sam_adenylate_stoichiometry", "biochemical_transfer") != "biochemical_transfer":
        raise RuntimeError("Joint adenylate audit requires corrected SAM transfer stoichiometry")
    sol, fluxes, derivatives = _simulate_and_track(
        params=params,
        t_eval=time,
        method=method,
        rtol=rtol,
        atol=atol,
        x0_override=state,
    )
    data: dict[str, Any] = {"time_day": time, "candidate": CANDIDATE_LABEL}
    closures: dict[str, float] = {}
    for pool in POOLS:
        concentration = np.asarray(sol.y[POOL_INDICES[pool], :], dtype=float)
        raw = _raw_balance(fluxes, POOL_TERMS[pool])
        effective, damping = _effective_balance(raw, concentration)
        derivative = np.asarray(derivatives[POOL_INDICES[pool], :], dtype=float)
        closure = float(np.max(np.abs(effective - derivative)))
        if closure > float(closure_tolerance):
            raise RuntimeError(f"{pool} closure failed: {closure:.6g}")
        data[pool] = concentration
        data[f"d{pool}_raw_dt"] = raw
        data[f"d{pool}_effective_dt"] = effective
        data[f"d{pool}_ode_dt"] = derivative
        data[f"{pool}_damping_adjustment"] = damping
        data[f"{pool}_closure_error"] = effective - derivative
        closures[f"max_abs_{pool}_closure_error"] = closure
    reaction_names = sorted(set().union(*[set(terms) for terms in POOL_TERMS.values()]))
    for reaction in reaction_names:
        data[reaction] = np.asarray(fluxes[reaction], dtype=float)
    frame = pd.DataFrame(data)
    forward, reverse, reconstructed = _vak_components(
        params=params,
        adp=frame["ADP"].to_numpy(dtype=float),
        amp=frame["AMP"].to_numpy(dtype=float),
        atp=frame["ATP"].to_numpy(dtype=float),
    )
    vak_split_error = float(np.max(np.abs(reconstructed - frame["VAK"])))
    if vak_split_error > float(closure_tolerance):
        raise RuntimeError(f"VAK split closure failed: {vak_split_error:.6g}")
    frame["VAK_forward_2ADP_to_AMP_ATP"] = forward
    frame["VAK_reverse_AMP_ATP_to_2ADP"] = reverse
    frame["VAK_split_error"] = reconstructed - frame["VAK"]
    frame["adenylate_total"] = frame[list(POOLS)].sum(axis=1)
    frame["dadenylate_total_raw_dt"] = _raw_balance(fluxes, TOTAL_TERMS)
    frame["dadenylate_total_effective_dt"] = frame[
        [f"d{pool}_effective_dt" for pool in POOLS]
    ].sum(axis=1)
    frame["dadenylate_total_ode_dt"] = frame[
        [f"d{pool}_ode_dt" for pool in POOLS]
    ].sum(axis=1)
    frame["adenylate_total_damping_adjustment"] = frame[
        [f"{pool}_damping_adjustment" for pool in POOLS]
    ].sum(axis=1)
    total_closure = float(
        np.max(
            np.abs(
                frame["dadenylate_total_raw_dt"]
                + frame["adenylate_total_damping_adjustment"]
                - frame["dadenylate_total_ode_dt"]
            )
        )
    )
    if total_closure > float(closure_tolerance):
        raise RuntimeError(f"Total adenylate closure failed: {total_closure:.6g}")
    closures["max_abs_VAK_split_error"] = vak_split_error
    closures["max_abs_total_adenylate_closure_error"] = total_closure
    return frame, closures


def _required_vak_estimates(
    *,
    teacher_derivatives: Mapping[str, np.ndarray],
    native: pd.DataFrame,
) -> dict[str, np.ndarray]:
    vak = native["VAK"].to_numpy(dtype=float)
    base_atp = native["dATP_raw_dt"].to_numpy(dtype=float) - vak
    base_adp = native["dADP_raw_dt"].to_numpy(dtype=float) + 2.0 * vak
    base_amp = native["dAMP_raw_dt"].to_numpy(dtype=float) - vak
    return {
        "ATP": np.asarray(teacher_derivatives["ATP"], dtype=float) - base_atp,
        "ADP": 0.5
        * (base_adp - np.asarray(teacher_derivatives["ADP"], dtype=float)),
        "AMP": np.asarray(teacher_derivatives["AMP"], dtype=float) - base_amp,
    }


def _joint_correction(
    teacher_derivatives: Mapping[str, np.ndarray],
    native_raw_derivatives: Mapping[str, np.ndarray],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    residual_atp = np.asarray(teacher_derivatives["ATP"], dtype=float) - np.asarray(
        native_raw_derivatives["ATP"], dtype=float
    )
    residual_adp = np.asarray(teacher_derivatives["ADP"], dtype=float) - np.asarray(
        native_raw_derivatives["ADP"], dtype=float
    )
    residual_amp = np.asarray(teacher_derivatives["AMP"], dtype=float) - np.asarray(
        native_raw_derivatives["AMP"], dtype=float
    )
    delta_vak = -(residual_atp + residual_adp)
    delta_vpgk = 2.0 * residual_atp + residual_adp
    missing_total = residual_atp + residual_adp + residual_amp
    return delta_vpgk, delta_vak, missing_total


def _add_teacher_reconstruction(
    *,
    native: pd.DataFrame,
    teacher_name: str,
    teacher: Mapping[str, tuple[np.ndarray, np.ndarray]],
) -> pd.DataFrame:
    frame = native.copy()
    concentrations = {pool: teacher[pool][0] for pool in POOLS}
    derivatives = {pool: teacher[pool][1] for pool in POOLS}
    frame["teacher_method"] = teacher_name
    for pool in POOLS:
        frame[f"{pool}_teacher"] = concentrations[pool]
        frame[f"d{pool}_teacher_dt"] = derivatives[pool]
        frame[f"{pool}_teacher_minus_native_derivative"] = (
            derivatives[pool] - frame[f"d{pool}_raw_dt"].to_numpy(dtype=float)
        )
    frame["adenylate_total_teacher"] = sum(concentrations.values())
    frame["dadenylate_total_teacher_dt"] = sum(derivatives.values())
    estimates = _required_vak_estimates(
        teacher_derivatives=derivatives, native=native
    )
    for pool, values in estimates.items():
        frame[f"VAK_required_from_{pool}"] = values
    native_raw = {
        pool: frame[f"d{pool}_raw_dt"].to_numpy(dtype=float) for pool in POOLS
    }
    delta_vpgk, delta_vak, missing_total = _joint_correction(derivatives, native_raw)
    frame["delta_VPGK_joint"] = delta_vpgk
    frame["delta_VAK_joint"] = delta_vak
    frame["missing_total_adenylate_flux"] = missing_total
    frame["VPGK_joint_required"] = frame["VPGK"] + delta_vpgk
    frame["VAK_joint_required"] = frame["VAK"] + delta_vak
    corrected_atp = frame["dATP_raw_dt"] + delta_vpgk + delta_vak
    corrected_adp = frame["dADP_raw_dt"] - delta_vpgk - 2.0 * delta_vak
    corrected_amp = frame["dAMP_raw_dt"] + delta_vak + missing_total
    frame["joint_corrected_ATP_derivative"] = corrected_atp
    frame["joint_corrected_ADP_derivative"] = corrected_adp
    frame["joint_corrected_AMP_derivative"] = corrected_amp
    frame["joint_ATP_closure_error"] = corrected_atp - derivatives["ATP"]
    frame["joint_ADP_closure_error"] = corrected_adp - derivatives["ADP"]
    frame["joint_AMP_closure_error"] = corrected_amp - derivatives["AMP"]
    other_without_vak2 = frame["dadenylate_total_raw_dt"] - frame["VAK2"]
    other_without_vsam = frame["dadenylate_total_raw_dt"] + frame["VSAM"]
    other_without_vadsl = frame["dadenylate_total_raw_dt"] - frame["VADSL"]
    other_without_vaprt = frame["dadenylate_total_raw_dt"] - frame["VAPRT"]
    other_without_vampd1 = frame["dadenylate_total_raw_dt"] + frame["VAMPD1"]
    frame["VAK2_required_if_single_total_lever"] = (
        frame["dadenylate_total_teacher_dt"] - other_without_vak2
    )
    frame["VSAM_required_if_single_total_lever"] = (
        other_without_vsam - frame["dadenylate_total_teacher_dt"]
    )
    frame["VADSL_required_if_single_total_lever"] = (
        frame["dadenylate_total_teacher_dt"] - other_without_vadsl
    )
    frame["VAPRT_required_if_single_total_lever"] = (
        frame["dadenylate_total_teacher_dt"] - other_without_vaprt
    )
    frame["VAMPD1_required_if_single_total_lever"] = (
        other_without_vampd1 - frame["dadenylate_total_teacher_dt"]
    )
    return frame


def _integrated_reaction_contributions(frame: pd.DataFrame) -> list[dict[str, Any]]:
    time = frame["time_day"].to_numpy(dtype=float)
    rows: list[dict[str, Any]] = []
    for reaction, coefficient in TOTAL_TERMS.items():
        flux_integral = _integral(frame[reaction], time)
        rows.append(
            {
                "reaction": reaction,
                "total_adenylate_coefficient": coefficient,
                "integrated_flux_J1_J3": flux_integral,
                "integrated_total_contribution_J1_J3": coefficient * flux_integral,
            }
        )
    return sorted(
        rows,
        key=lambda row: abs(row["integrated_total_contribution_J1_J3"]),
        reverse=True,
    )


def _metrics(
    frame: pd.DataFrame, params: Mapping[str, Any]
) -> dict[str, Any]:
    time = frame["time_day"].to_numpy(dtype=float)
    vak_required = frame["VAK_joint_required"].to_numpy(dtype=float)
    vpgk_required = frame["VPGK_joint_required"].to_numpy(dtype=float)
    vak_estimates = np.vstack(
        [frame[f"VAK_required_from_{pool}"].to_numpy(dtype=float) for pool in POOLS]
    )
    estimate_spread = np.max(vak_estimates, axis=0) - np.min(vak_estimates, axis=0)
    vmax_forward = _param(params, "vmax_VAK")
    vmax_reverse = _param(params, "vmax_VAK_rev")
    total_teacher_change = float(
        frame["adenylate_total_teacher"].iloc[-1]
        - frame["adenylate_total_teacher"].iloc[0]
    )
    total_native_change = float(
        frame["adenylate_total"].iloc[-1] - frame["adenylate_total"].iloc[0]
    )
    return {
        "teacher_total_change_J1_J3_mM": total_teacher_change,
        "native_total_change_J1_J3_mM": total_native_change,
        "integrated_native_raw_total_flux_mM": _integral(
            frame["dadenylate_total_raw_dt"], time
        ),
        "integrated_native_damping_adjustment_mM": _integral(
            frame["adenylate_total_damping_adjustment"], time
        ),
        "integrated_missing_total_adenylate_flux_mM": _integral(
            frame["missing_total_adenylate_flux"], time
        ),
        "native_VAK_integral_mM": _integral(frame["VAK"], time),
        "joint_required_VAK_integral_mM": _integral(vak_required, time),
        "joint_required_VPGK_integral_mM": _integral(vpgk_required, time),
        "native_VAK_forward_time_fraction": float(np.mean(frame["VAK"] > 0.0)),
        "joint_required_VAK_forward_time_fraction": float(np.mean(vak_required > 0.0)),
        "joint_required_VAK_reverse_time_fraction": float(np.mean(vak_required < 0.0)),
        "joint_required_VAK_min": float(np.min(vak_required)),
        "joint_required_VAK_max": float(np.max(vak_required)),
        "joint_required_VAK_within_hard_bounds_time_fraction": float(
            np.mean((vak_required >= -vmax_reverse) & (vak_required <= vmax_forward))
        ),
        "joint_required_VPGK_negative_time_fraction": float(
            np.mean(vpgk_required < 0.0)
        ),
        "VAK_balance_estimate_mean_spread": _time_mean(estimate_spread, time),
        "VAK_balance_estimate_max_spread": float(np.max(estimate_spread)),
        "VAK_required_from_ATP_integral_mM": _integral(
            frame["VAK_required_from_ATP"], time
        ),
        "VAK_required_from_ADP_integral_mM": _integral(
            frame["VAK_required_from_ADP"], time
        ),
        "VAK_required_from_AMP_integral_mM": _integral(
            frame["VAK_required_from_AMP"], time
        ),
        "VAK2_single_lever_nonnegative_time_fraction": float(
            np.mean(frame["VAK2_required_if_single_total_lever"] >= 0.0)
        ),
        "VSAM_single_lever_nonnegative_time_fraction": float(
            np.mean(frame["VSAM_required_if_single_total_lever"] >= 0.0)
        ),
        "VADSL_single_lever_nonnegative_time_fraction": float(
            np.mean(frame["VADSL_required_if_single_total_lever"] >= 0.0)
        ),
        "VAPRT_single_lever_nonnegative_time_fraction": float(
            np.mean(frame["VAPRT_required_if_single_total_lever"] >= 0.0)
        ),
        "VAMPD1_single_lever_nonnegative_time_fraction": float(
            np.mean(frame["VAMPD1_required_if_single_total_lever"] >= 0.0)
        ),
        "single_lever_required_integrals_mM": {
            reaction: _integral(
                frame[f"{reaction}_required_if_single_total_lever"], time
            )
            for reaction in ("VAK2", "VSAM", "VADSL", "VAPRT", "VAMPD1")
        },
        "max_abs_joint_teacher_closure_error": float(
            max(
                np.max(np.abs(frame["joint_ATP_closure_error"])),
                np.max(np.abs(frame["joint_ADP_closure_error"])),
                np.max(np.abs(frame["joint_AMP_closure_error"])),
            )
        ),
    }


def _window_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    all_time = frame["time_day"].to_numpy(dtype=float)
    for window, start, end in WINDOWS:
        mask = (all_time >= start - 1e-12) & (all_time <= end + 1e-12)
        local = frame.loc[mask]
        time = local["time_day"].to_numpy(dtype=float)
        rows.append(
            {
                "teacher_method": str(frame["teacher_method"].iloc[0]),
                "window": window,
                "teacher_total_change_mM": float(
                    local["adenylate_total_teacher"].iloc[-1]
                    - local["adenylate_total_teacher"].iloc[0]
                ),
                "native_total_change_mM": float(
                    local["adenylate_total"].iloc[-1]
                    - local["adenylate_total"].iloc[0]
                ),
                "missing_total_flux_integral_mM": _integral(
                    local["missing_total_adenylate_flux"], time
                ),
                "VAK_native_integral_mM": _integral(local["VAK"], time),
                "VAK_joint_required_integral_mM": _integral(
                    local["VAK_joint_required"], time
                ),
                "VPGK_joint_required_integral_mM": _integral(
                    local["VPGK_joint_required"], time
                ),
                "VAK_joint_reverse_time_fraction": float(
                    np.mean(local["VAK_joint_required"] < 0.0)
                ),
            }
        )
    return rows


def _classify(primary: Mapping[str, Any]) -> dict[str, Any]:
    gates = {
        "native_total_increases_while_teacher_decreases": (
            float(primary["native_total_change_J1_J3_mM"]) > 0.0
            and float(primary["teacher_total_change_J1_J3_mM"]) < 0.0
        ),
        "VAK_balance_estimates_disagree": float(
            primary["VAK_balance_estimate_mean_spread"]
        )
        > 0.1,
        "joint_required_VAK_opposes_native_direction": (
            float(primary["native_VAK_forward_time_fraction"]) >= 0.95
            and float(primary["joint_required_VAK_reverse_time_fraction"]) >= 0.95
        ),
        "internal_VAK_cannot_change_total_pool": TOTAL_TERMS.get("VAK", 0.0) == 0.0,
    }
    if gates["native_total_increases_while_teacher_decreases"] and gates[
        "internal_VAK_cannot_change_total_pool"
    ]:
        classification = (
            "adenylate-total source/sink mismatch precedes any adenylate-kinase calibration"
        )
    elif gates["VAK_balance_estimates_disagree"]:
        classification = "single-flux adenylate-kinase reconstruction is inconsistent"
    else:
        classification = "joint adenylate teachers are compatible with native pool ownership"
    return {"classification": classification, "classification_gates": gates}


def _plot(frame: pd.DataFrame, out_path: Path) -> None:
    time = frame["time_day"].to_numpy(dtype=float)
    colors = {"ATP": "#b45309", "ADP": "#2563eb", "AMP": "#0f766e"}
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), constrained_layout=True)
    for pool in POOLS:
        axes[0, 0].plot(time, frame[f"{pool}_teacher"], color=colors[pool], label=f"{pool} teacher")
        axes[0, 0].plot(time, frame[pool], color=colors[pool], ls="--", label=f"{pool} native")
        axes[0, 1].plot(time, frame[f"d{pool}_teacher_dt"], color=colors[pool], label=f"d{pool} teacher")
        axes[0, 1].plot(time, frame[f"d{pool}_raw_dt"], color=colors[pool], ls="--", label=f"d{pool} native")
    axes[1, 0].plot(time, frame["VAK"], "#111827", label="VAK native net")
    axes[1, 0].plot(time, frame["VAK_joint_required"], "#b45309", label="VAK joint required")
    axes[1, 0].plot(time, frame["VAK_forward_2ADP_to_AMP_ATP"], "#2563eb", ls=":", label="VAK forward component")
    axes[1, 0].plot(time, -frame["VAK_reverse_AMP_ATP_to_2ADP"], "#0f766e", ls=":", label="-VAK reverse component")
    axes[1, 0].axhline(0.0, color="#6b7280", lw=1)
    axes[1, 1].plot(time, frame["adenylate_total_teacher"], "#b45309", label="total teacher")
    axes[1, 1].plot(time, frame["adenylate_total"], "#111827", label="total native")
    twin = axes[1, 1].twinx()
    twin.plot(time, frame["missing_total_adenylate_flux"], "#991b1b", ls="--", label="missing total flux")
    axes[0, 0].set_title("Joint adenylate concentrations")
    axes[0, 1].set_title("Teacher versus native net derivatives")
    axes[1, 0].set_title("Adenylate-kinase directionality")
    axes[1, 1].set_title("Total adenylate pool and missing net flux")
    axes[0, 0].set_ylabel("mM")
    axes[0, 1].set_ylabel("mM/day")
    axes[1, 0].set_ylabel("mM/day")
    axes[1, 1].set_ylabel("mM")
    twin.set_ylabel("mM/day", color="#991b1b")
    for axis in axes.flat:
        axis.set_xlabel("Day")
        axis.grid(alpha=0.2)
        axis.legend(frameon=False, fontsize=8)
    lines, labels = axes[1, 1].get_legend_handles_labels()
    twin_lines, twin_labels = twin.get_legend_handles_labels()
    axes[1, 1].legend(lines + twin_lines, labels + twin_labels, frameon=False, fontsize=8)
    fig.suptitle("Joint ATP-ADP-AMP FLA audit in fixed VDPGM 3x branch")
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _report(summary: Mapping[str, Any]) -> str:
    primary = summary["primary_metrics"]
    contributions = summary["native_total_reaction_contributions"]
    top = ", ".join(
        f"{row['reaction']} ({row['integrated_total_contribution_J1_J3']:.4f} mM)"
        for row in contributions[:4]
    )
    single = primary["single_lever_required_integrals_mM"]
    return "\n".join(
        [
            "# Joint ATP-ADP-AMP balance audit, J1-J3",
            "",
            "## Result",
            "",
            f"- Classification: **{summary['classification']['classification']}**.",
            f"- Teacher total change: `{primary['teacher_total_change_J1_J3_mM']:.5f} mM`.",
            f"- Native total change: `{primary['native_total_change_J1_J3_mM']:.5f} mM`.",
            f"- Integrated missing total flux: `{primary['integrated_missing_total_adenylate_flux_mM']:.5f} mM`.",
            f"- Dominant native total-pool terms: {top}.",
            f"- Native/joint-required VAK integrals: `{primary['native_VAK_integral_mM']:.5f}` / `{primary['joint_required_VAK_integral_mM']:.5f} mM`.",
            f"- Joint-required VAK reverse-time fraction: `{100.0 * primary['joint_required_VAK_reverse_time_fraction']:.1f}%`.",
            f"- Joint-required VAK within current forward/reverse hard bounds: `{100.0 * primary['joint_required_VAK_within_hard_bounds_time_fraction']:.1f}%`.",
            f"- Mean spread among ATP-, ADP-, and AMP-derived VAK estimates: `{primary['VAK_balance_estimate_mean_spread']:.4f} mM/day`.",
            f"- VAPRT-only required integral: `{single['VAPRT']:.5f} mM`; nonnegative for only `{100.0 * primary['VAPRT_single_lever_nonnegative_time_fraction']:.1f}%` of J1-J3.",
            f"- Required sink integrals if used alone, VAMPD1 / VSAM: `{single['VAMPD1']:.5f}` / `{single['VSAM']:.5f} mM`.",
            "",
            "## Decision",
            "",
            "Do not calibrate adenylate kinase first. VAK redistributes ATP, ADP, and AMP but cancels exactly from their total. The measured total decreases while the model total increases. The next reversible diagnostic is VAPRT suppression at fixed kinetics, followed by attribution of the residual total-pool sink to VAMPD1 with IMP, ADE, PRPP, ATP, ADP, and AMP safeguards.",
            "",
        ]
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--points", type=int, default=2001)
    parser.add_argument("--method", default="BDF")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    parser.add_argument("--closure-tolerance", type=float, default=1e-7)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    time = np.linspace(1.0, 3.0, args.points)
    state, _seed_params, params, seed_path = _build_contract()
    native, closures = _build_native_frame(
        state=state,
        params=params,
        time=time,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
        closure_tolerance=args.closure_tolerance,
    )
    exp_time, curves = _load_teachers()
    teachers = _teacher_variants(exp_time, curves, time)
    frames = {
        name: _add_teacher_reconstruction(native=native, teacher_name=name, teacher=teacher)
        for name, teacher in teachers.items()
    }
    primary = frames[PRIMARY_TEACHER]
    metrics = {name: _metrics(frame, params) for name, frame in frames.items()}
    contributions = _integrated_reaction_contributions(primary)
    classification = _classify(metrics[PRIMARY_TEACHER])
    windows = pd.DataFrame(
        [row for frame in frames.values() for row in _window_rows(frame)]
    )
    pchip_missing = metrics[PRIMARY_TEACHER]["integrated_missing_total_adenylate_flux_mM"]
    linear_missing = metrics[SENSITIVITY_TEACHER]["integrated_missing_total_adenylate_flux_mM"]
    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "model_network_version": MODEL_NETWORK_VERSION,
        "seed_params_path": str(seed_path.resolve()),
        "kinetic_contract": "fixed 3x vmax_VDPGM QSS-B13PG replay; no optimization",
        "changed_parameters_in_this_run": [],
        "data_contract": {
            "source": str(BRODBAR_DATA.resolve()),
            "pools": list(POOLS),
            "observation_days": exp_time.tolist(),
            "observations_per_pool_inside_J1_J3": int(
                np.sum((exp_time >= 1.0) & (exp_time <= 3.0))
            ),
            "next_observation_day": 4.0,
            "primary_teacher": PRIMARY_TEACHER,
            "sensitivity_teacher": SENSITIVITY_TEACHER,
        },
        "balance_contract": {
            "ATP_terms": ATP_TERMS,
            "ADP_terms": ADP_TERMS,
            "AMP_terms": AMP_TERMS,
            "total_adenylate_terms": TOTAL_TERMS,
            "VAK_direction_convention": "positive: 2 ADP -> AMP + ATP; negative: AMP + ATP -> 2 ADP",
            "VAK2_identity": "adenosine kinase ADO + ATP -> ADP + AMP; total adenylate source",
            "sam_stoichiometry": "biochemical_transfer",
        },
        "native_closures": closures,
        "primary_metrics": metrics[PRIMARY_TEACHER],
        "all_teacher_metrics": metrics,
        "teacher_sensitivity": {
            "PCHIP_missing_total_integral_mM": pchip_missing,
            "linear_missing_total_integral_mM": linear_missing,
            "relative_difference": float(
                (linear_missing - pchip_missing) / max(abs(pchip_missing), 1e-30)
            ),
        },
        "native_total_reaction_contributions": contributions,
        "classification": classification,
        "decision": "total-pool mismatch is dominated by VAPRT; VAK direction is secondary and opposite to the native replay",
        "next_step": "reversible fixed-kinetic VAPRT suppression diagnostic, then quantify residual VAMPD1 sink with purine and adenylate safeguards",
    }
    pd.concat(frames.values(), ignore_index=True).to_csv(
        args.out_dir / "joint_adenylate_timeseries.csv", index=False
    )
    windows.to_csv(args.out_dir / "joint_adenylate_window_metrics.csv", index=False)
    pd.DataFrame(contributions).to_csv(
        args.out_dir / "native_total_reaction_contributions.csv", index=False
    )
    (args.out_dir / "summary.json").write_text(
        json.dumps(_jsonable(summary), indent=2), encoding="utf-8"
    )
    (args.out_dir / "report.md").write_text(_report(summary), encoding="utf-8")
    _plot(primary, args.out_dir / "joint_adenylate_balance.png")
    print(json.dumps(_jsonable(summary), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
