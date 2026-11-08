"""Replay VAPRT suppression and infer the residual VAMPD1 sink requirement."""

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
    / "vaprt_zero_vampd1_requirement_3x_qss_J1_J3"
)

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from equadiff_brodbar import BRODBAR_METABOLITE_MAP, MODEL_NETWORK_VERSION  # noqa: E402
from audit_atp_partition_vdpgm_3x_qss_b13pg import WINDOWS, _build_contract  # noqa: E402
from audit_atp_transition_v6pgd_ppp_context import _integral, _time_mean  # noqa: E402
from audit_b13pg_balance_v6pgd_ppp_context import _effective_balance  # noqa: E402
from audit_joint_adenylate_balances import (  # noqa: E402
    AMP_TERMS,
    ATP_TERMS,
    ADP_TERMS,
    POOLS,
    POOL_TERMS,
    TOTAL_TERMS,
    _load_teachers,
    _param,
    _raw_balance,
    _teacher_variants,
    _vak_components,
)
from profile_glycolysis_flux_bottlenecks import (  # noqa: E402
    _jsonable,
    _simulate_and_track,
)


BASELINE_LABEL = "fixed_3x_VAPRT_native"
CANDIDATE_LABEL = "fixed_3x_VAPRT_zero"
PRIMARY_TEACHER = "pchip_full_record"
SENSITIVITY_TEACHER = "linear_J1_J4"
OBSERVED_STATES = ("ATP", "ADP", "AMP", "IMP", "ADE")
LATENT_GUARDS = ("PRPP", "ADOMET")
TRACKED_STATES = OBSERVED_STATES + LATENT_GUARDS
STATE_INDICES = {
    name: int(BRODBAR_METABOLITE_MAP[name]) for name in TRACKED_STATES
}
STATE_TERMS = {
    "ATP": ATP_TERMS,
    "ADP": ADP_TERMS,
    "AMP": AMP_TERMS,
    "ADE": {"VEADE": -1.0, "VAPRT": -1.0},
    "PRPP": {
        "VPRPPASe": 1.0,
        "VAPRT": -1.0,
        "VHGPRT1": -1.0,
        "VHGPRT2": -1.0,
    },
    "IMP": {
        "VHGPRT1": 1.0,
        "VAMPD1": 1.0,
        "VADSS": -1.0,
        "VIMPH": -1.0,
        "Vnucleo2": -1.0,
    },
    "ADOMET": {"VSAM": 1.0, "VSAH": -1.0},
}
DEFAULT_VMAX_VAMPD1 = 0.538065


def _candidate_params(
    fixed_params: Mapping[str, Any]
) -> tuple[dict[str, Any], float, list[str]]:
    candidate = dict(fixed_params)
    seed_value = float(fixed_params.get("vmax_VAPRT", 1.087935))
    candidate["vmax_VAPRT"] = 0.0
    changed = sorted(
        key
        for key in set(fixed_params) | set(candidate)
        if fixed_params.get(key) != candidate.get(key)
    )
    if changed != ["vmax_VAPRT"]:
        raise RuntimeError(f"VAPRT suppression contract failed: changed={changed}")
    return candidate, seed_value, changed


def _load_observed_curves() -> tuple[np.ndarray, dict[str, np.ndarray]]:
    frame = pd.read_excel(BRODBAR_DATA, engine="openpyxl")
    names = frame.iloc[:, 0].astype(str).str.strip().str.upper()
    time = np.asarray([float(value) for value in frame.columns[1:]], dtype=float)
    curves: dict[str, np.ndarray] = {}
    for state in OBSERVED_STATES:
        rows = frame.loc[names == state]
        if len(rows) != 1:
            raise RuntimeError(f"Expected exactly one {state} row, found {len(rows)}")
        curves[state] = rows.iloc[0, 1:].to_numpy(dtype=float)
    return time, curves


def _normalized_rmse(
    model: np.ndarray, teacher: np.ndarray, full_curve: np.ndarray
) -> float:
    scale = max(float(np.mean(np.abs(full_curve))), 0.01)
    return float(np.sqrt(np.mean((np.asarray(model) - np.asarray(teacher)) ** 2)) / scale)


def _replay(
    *,
    label: str,
    state: np.ndarray,
    params: Mapping[str, Any],
    time: np.ndarray,
    method: str,
    rtol: float,
    atol: float,
    closure_tolerance: float,
    extra_state_indices: Mapping[str, int] | None = None,
) -> tuple[pd.DataFrame, dict[str, float]]:
    sol, fluxes, derivatives = _simulate_and_track(
        params=params,
        t_eval=time,
        method=method,
        rtol=rtol,
        atol=atol,
        x0_override=state,
    )
    data: dict[str, Any] = {"candidate": label, "time_day": time}
    closures: dict[str, float] = {}
    reactions = sorted(set().union(*[set(terms) for terms in STATE_TERMS.values()]))
    for reaction in reactions:
        if reaction not in fluxes:
            raise KeyError(f"FluxTracker is missing {reaction}")
        data[reaction] = np.asarray(fluxes[reaction], dtype=float)
    for name, index in STATE_INDICES.items():
        concentration = np.asarray(sol.y[index, :], dtype=float)
        raw = _raw_balance(fluxes, STATE_TERMS[name])
        effective, damping = _effective_balance(raw, concentration)
        derivative = np.asarray(derivatives[index, :], dtype=float)
        closure = float(np.max(np.abs(effective - derivative)))
        if closure > float(closure_tolerance):
            raise RuntimeError(f"{name} closure failed for {label}: {closure:.6g}")
        data[name] = concentration
        data[f"d{name}_raw_dt"] = raw
        data[f"d{name}_effective_dt"] = effective
        data[f"d{name}_ode_dt"] = derivative
        data[f"{name}_damping_adjustment"] = damping
        data[f"{name}_closure_error"] = effective - derivative
        closures[f"max_abs_{name}_closure_error"] = closure
    for name, index in (extra_state_indices or {}).items():
        if name not in data:
            data[name] = np.asarray(sol.y[int(index), :], dtype=float)
    frame = pd.DataFrame(data)
    forward, reverse, net = _vak_components(
        params=params,
        adp=frame["ADP"].to_numpy(dtype=float),
        amp=frame["AMP"].to_numpy(dtype=float),
        atp=frame["ATP"].to_numpy(dtype=float),
    )
    vak_error = float(np.max(np.abs(net - frame["VAK"])))
    if vak_error > float(closure_tolerance):
        raise RuntimeError(f"VAK split closure failed for {label}: {vak_error:.6g}")
    frame["VAK_forward_2ADP_to_AMP_ATP"] = forward
    frame["VAK_reverse_AMP_ATP_to_2ADP"] = reverse
    frame["adenylate_total"] = frame[list(POOLS)].sum(axis=1)
    frame["dadenylate_total_raw_dt"] = _raw_balance(fluxes, TOTAL_TERMS)
    frame["adenylate_total_damping_adjustment"] = frame[
        [f"{pool}_damping_adjustment" for pool in POOLS]
    ].sum(axis=1)
    frame["dadenylate_total_ode_dt"] = frame[
        [f"d{pool}_ode_dt" for pool in POOLS]
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
        raise RuntimeError(f"Total closure failed for {label}: {total_closure:.6g}")
    closures["max_abs_VAK_split_error"] = vak_error
    closures["max_abs_total_adenylate_closure_error"] = total_closure
    closures["all_state_minimum_mM"] = float(np.min(sol.y))
    return frame, closures


def _add_teachers(
    *,
    frame: pd.DataFrame,
    exp_time: np.ndarray,
    curves: Mapping[str, np.ndarray],
) -> pd.DataFrame:
    result = frame.copy()
    time = result["time_day"].to_numpy(dtype=float)
    for state in OBSERVED_STATES:
        teacher = np.asarray(PchipInterpolator(exp_time, curves[state])(time), dtype=float)
        result[f"{state}_teacher"] = teacher
    result["adenylate_total_teacher"] = result[
        [f"{pool}_teacher" for pool in POOLS]
    ].sum(axis=1)
    return result


def _required_vampd1(
    *,
    total_teacher_derivative: np.ndarray,
    vak2: np.ndarray,
    vsam: np.ndarray,
    vadsl: np.ndarray,
    vaprt: np.ndarray,
) -> np.ndarray:
    return (
        np.asarray(vak2, dtype=float)
        - np.asarray(vsam, dtype=float)
        + np.asarray(vadsl, dtype=float)
        + np.asarray(vaprt, dtype=float)
        - np.asarray(total_teacher_derivative, dtype=float)
    )


def _vampd1_feasibility(
    *,
    frame: pd.DataFrame,
    required: np.ndarray,
    current_vmax: float,
) -> dict[str, Any]:
    time = frame["time_day"].to_numpy(dtype=float)
    native = frame["VAMPD1"].to_numpy(dtype=float)
    scalable = (required > 0.0) & (native > 1e-12)
    required_vmax = np.full_like(required, np.nan)
    required_vmax[scalable] = current_vmax * required[scalable] / native[scalable]
    finite = required_vmax[np.isfinite(required_vmax)]
    return {
        "current_vmax_VAMPD1": current_vmax,
        "native_integral_mM": _integral(native, time),
        "required_integral_mM": _integral(required, time),
        "additional_required_integral_mM": _integral(required - native, time),
        "required_min_mM_per_day": float(np.min(required)),
        "required_max_mM_per_day": float(np.max(required)),
        "nonnegative_time_fraction": float(np.mean(required >= 0.0)),
        "within_current_hard_ceiling_time_fraction": float(
            np.mean((required >= 0.0) & (required <= current_vmax))
        ),
        "hard_ceiling_excess_integral_mM": _integral(
            np.maximum(required - current_vmax, 0.0), time
        ),
        "fixed_state_required_vmax_median": (
            float(np.median(finite)) if finite.size else None
        ),
        "fixed_state_required_vmax_p95": (
            float(np.quantile(finite, 0.95)) if finite.size else None
        ),
        "fixed_state_required_vmax_max": (
            float(np.max(finite)) if finite.size else None
        ),
    }


def _state_metrics(
    *,
    frame: pd.DataFrame,
    curves: Mapping[str, np.ndarray],
) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for state in OBSERVED_STATES:
        model = frame[state].to_numpy(dtype=float)
        teacher = frame[f"{state}_teacher"].to_numpy(dtype=float)
        metrics[state] = {
            "nrmse": _normalized_rmse(model, teacher, curves[state]),
            "model_endpoint_mM": float(model[-1]),
            "teacher_endpoint_mM": float(teacher[-1]),
            "minimum_mM": float(np.min(model)),
        }
    total_model = frame["adenylate_total"].to_numpy(dtype=float)
    total_teacher = frame["adenylate_total_teacher"].to_numpy(dtype=float)
    total_full = curves["ATP"] + curves["ADP"] + curves["AMP"]
    metrics["adenylate_total"] = {
        "nrmse": _normalized_rmse(total_model, total_teacher, total_full),
        "model_endpoint_mM": float(total_model[-1]),
        "teacher_endpoint_mM": float(total_teacher[-1]),
        "model_change_mM": float(total_model[-1] - total_model[0]),
        "teacher_change_mM": float(total_teacher[-1] - total_teacher[0]),
    }
    for state in LATENT_GUARDS:
        values = frame[state].to_numpy(dtype=float)
        metrics[state] = {
            "initial_mM": float(values[0]),
            "endpoint_mM": float(values[-1]),
            "minimum_mM": float(np.min(values)),
            "maximum_mM": float(np.max(values)),
        }
    return metrics


def _guard_assessment(
    *,
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    closures: Mapping[str, float],
    feasibility: Mapping[str, Any],
    closure_tolerance: float,
) -> dict[str, bool]:
    guards = {
        "all_balances_close": all(
            float(value) <= closure_tolerance
            for key, value in closures.items()
            if key.startswith("max_abs_")
        ),
        "all_states_nonnegative": float(closures["all_state_minimum_mM"]) >= -1e-10,
        "adenylate_total_nrmse_improves": float(candidate["adenylate_total"]["nrmse"])
        < float(baseline["adenylate_total"]["nrmse"]),
        "ATP_noninferior_10pct": float(candidate["ATP"]["nrmse"])
        <= 1.10 * float(baseline["ATP"]["nrmse"]),
        "ADP_noninferior_10pct": float(candidate["ADP"]["nrmse"])
        <= 1.10 * float(baseline["ADP"]["nrmse"]),
        "AMP_noninferior_10pct": float(candidate["AMP"]["nrmse"])
        <= 1.10 * float(baseline["AMP"]["nrmse"]),
        "IMP_noninferior_10pct": float(candidate["IMP"]["nrmse"])
        <= 1.10 * float(baseline["IMP"]["nrmse"]),
        "ADE_noninferior_10pct": float(candidate["ADE"]["nrmse"])
        <= 1.10 * float(baseline["ADE"]["nrmse"]),
        "PRPP_nonnegative": float(candidate["PRPP"]["minimum_mM"]) >= -1e-10,
        "ADOMET_nonnegative": float(candidate["ADOMET"]["minimum_mM"]) >= -1e-10,
        "required_VAMPD1_nonnegative": float(feasibility["nonnegative_time_fraction"])
        == 1.0,
        "required_VAMPD1_within_current_ceiling": float(
            feasibility["within_current_hard_ceiling_time_fraction"]
        )
        == 1.0,
    }
    return guards


def _classify(guards: Mapping[str, bool]) -> str:
    if not guards["ADE_noninferior_10pct"]:
        return "VAPRT_zero_rejected_by_ADE_teacher"
    if not guards["adenylate_total_nrmse_improves"]:
        return "VAPRT_zero_does_not_improve_total_adenylate"
    if not guards["required_VAMPD1_nonnegative"]:
        return "residual_VAMPD1_requirement_is_sign_infeasible"
    if not guards["required_VAMPD1_within_current_ceiling"]:
        return "residual_VAMPD1_requires_capacity_increase"
    if all(guards.values()):
        return "VAPRT_zero_and_native_VAMPD1_capacity_are_feasible"
    return "VAPRT_zero_fails_secondary_purine_or_adenylate_guards"


def _window_rows(
    *, frame: pd.DataFrame, teacher_derivative: np.ndarray, required: np.ndarray
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    all_time = frame["time_day"].to_numpy(dtype=float)
    for window, start, end in WINDOWS:
        mask = (all_time >= start - 1e-12) & (all_time <= end + 1e-12)
        time = all_time[mask]
        rows.append(
            {
                "candidate": str(frame["candidate"].iloc[0]),
                "window": window,
                "native_total_flux_integral_mM": _integral(
                    frame.loc[mask, "dadenylate_total_raw_dt"], time
                ),
                "teacher_total_flux_integral_mM": _integral(
                    teacher_derivative[mask], time
                ),
                "VAPRT_integral_mM": _integral(frame.loc[mask, "VAPRT"], time),
                "VAMPD1_native_integral_mM": _integral(
                    frame.loc[mask, "VAMPD1"], time
                ),
                "VAMPD1_required_integral_mM": _integral(required[mask], time),
                "VAMPD1_additional_integral_mM": _integral(
                    required[mask] - frame.loc[mask, "VAMPD1"].to_numpy(dtype=float),
                    time,
                ),
                "ADE_endpoint_mM": float(frame.loc[mask, "ADE"].iloc[-1]),
                "IMP_endpoint_mM": float(frame.loc[mask, "IMP"].iloc[-1]),
                "PRPP_endpoint_mM": float(frame.loc[mask, "PRPP"].iloc[-1]),
                "VAK_mean_mM_per_day": _time_mean(
                    frame.loc[mask, "VAK"].to_numpy(dtype=float), time
                ),
            }
        )
    return rows


def _plot(
    *,
    baseline: pd.DataFrame,
    candidate: pd.DataFrame,
    required_vampd1: np.ndarray,
    current_vmax: float,
    out_path: Path,
) -> None:
    time = candidate["time_day"].to_numpy(dtype=float)
    fig, axes = plt.subplots(2, 3, figsize=(15, 9), constrained_layout=True)
    axes[0, 0].plot(time, baseline["adenylate_total"], "#111827", label="native VAPRT")
    axes[0, 0].plot(time, candidate["adenylate_total"], "#2563eb", label="VAPRT=0")
    axes[0, 0].plot(time, candidate["adenylate_total_teacher"], "#b45309", label="teacher")
    for pool, color in zip(POOLS, ("#b45309", "#2563eb", "#0f766e")):
        axes[0, 1].plot(time, candidate[pool], color=color, label=f"{pool} VAPRT=0")
        axes[0, 1].plot(time, candidate[f"{pool}_teacher"], color=color, ls="--", label=f"{pool} teacher")
    axes[0, 2].plot(time, baseline["ADE"], "#111827", label="native VAPRT")
    axes[0, 2].plot(time, candidate["ADE"], "#2563eb", label="VAPRT=0")
    axes[0, 2].plot(time, candidate["ADE_teacher"], "#b45309", label="teacher")
    axes[1, 0].plot(time, baseline["IMP"], "#111827", label="native VAPRT")
    axes[1, 0].plot(time, candidate["IMP"], "#2563eb", label="VAPRT=0")
    axes[1, 0].plot(time, candidate["IMP_teacher"], "#b45309", label="teacher")
    axes[1, 1].plot(time, baseline["PRPP"], "#111827", label="native VAPRT")
    axes[1, 1].plot(time, candidate["PRPP"], "#2563eb", label="VAPRT=0")
    axes[1, 2].plot(time, candidate["VAMPD1"], "#111827", label="native VAMPD1 after VAPRT=0")
    axes[1, 2].plot(time, required_vampd1, "#b45309", label="teacher-required VAMPD1")
    axes[1, 2].axhline(current_vmax, color="#991b1b", ls="--", label="current VAMPD1 Vmax")
    titles = (
        "Total adenylate",
        "ATP, ADP, and AMP",
        "ADE safeguard",
        "IMP safeguard",
        "Latent PRPP safeguard",
        "Residual AMP-deaminase requirement",
    )
    for axis, title in zip(axes.flat, titles):
        axis.set_title(title)
        axis.set_xlabel("Day")
        axis.grid(alpha=0.2)
        axis.legend(frameon=False, fontsize=8)
    for axis in axes.flat:
        axis.set_ylabel("mM" if axis is not axes[1, 2] else "mM/day")
    fig.suptitle("Fixed VAPRT suppression and residual VAMPD1 diagnosis")
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _report(summary: Mapping[str, Any]) -> str:
    baseline = summary["state_metrics"][BASELINE_LABEL]
    candidate = summary["state_metrics"][CANDIDATE_LABEL]
    feasibility = summary["VAMPD1_requirement"][PRIMARY_TEACHER]
    failed = [name for name, passed in summary["guards"].items() if not passed]
    return "\n".join(
        [
            "# Fixed VAPRT suppression and VAMPD1 requirement, J1-J3",
            "",
            f"- Classification: **{summary['classification']}**.",
            f"- Total adenylate nRMSE native / VAPRT=0: `{baseline['adenylate_total']['nrmse']:.4f}` / `{candidate['adenylate_total']['nrmse']:.4f}`.",
            f"- ADE nRMSE native / VAPRT=0: `{baseline['ADE']['nrmse']:.4f}` / `{candidate['ADE']['nrmse']:.4f}`.",
            f"- IMP nRMSE native / VAPRT=0: `{baseline['IMP']['nrmse']:.4f}` / `{candidate['IMP']['nrmse']:.4f}`.",
            f"- Residual VAMPD1 native / required integral: `{feasibility['native_integral_mM']:.5f}` / `{feasibility['required_integral_mM']:.5f} mM`.",
            f"- Additional VAMPD1 integral: `{feasibility['additional_required_integral_mM']:.5f} mM`.",
            f"- Required VAMPD1 within current hard ceiling: `{100.0 * feasibility['within_current_hard_ceiling_time_fraction']:.1f}%` of J1-J3.",
            f"- Failed guards: `{', '.join(failed) if failed else 'none'}`.",
            "",
            "## Decision",
            "",
            summary["decision"],
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
    state, _seed_params, fixed_params, seed_path = _build_contract()
    candidate_params, vaprt_seed, changed = _candidate_params(fixed_params)
    baseline, baseline_closures = _replay(
        label=BASELINE_LABEL,
        state=state,
        params=fixed_params,
        time=time,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
        closure_tolerance=args.closure_tolerance,
    )
    candidate, candidate_closures = _replay(
        label=CANDIDATE_LABEL,
        state=state,
        params=candidate_params,
        time=time,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
        closure_tolerance=args.closure_tolerance,
    )
    exp_time, observed_curves = _load_observed_curves()
    baseline = _add_teachers(frame=baseline, exp_time=exp_time, curves=observed_curves)
    candidate = _add_teachers(frame=candidate, exp_time=exp_time, curves=observed_curves)
    adenylate_time, adenylate_curves = _load_teachers()
    teacher_variants = _teacher_variants(adenylate_time, adenylate_curves, time)
    requirements: dict[str, np.ndarray] = {}
    feasibility: dict[str, Any] = {}
    current_vmax_vampd1 = float(
        candidate_params.get("vmax_VAMPD1", DEFAULT_VMAX_VAMPD1)
    )
    for teacher_name, teacher in teacher_variants.items():
        total_derivative = sum(teacher[pool][1] for pool in POOLS)
        required = _required_vampd1(
            total_teacher_derivative=total_derivative,
            vak2=candidate["VAK2"].to_numpy(dtype=float),
            vsam=candidate["VSAM"].to_numpy(dtype=float),
            vadsl=candidate["VADSL"].to_numpy(dtype=float),
            vaprt=candidate["VAPRT"].to_numpy(dtype=float),
        )
        requirements[teacher_name] = required
        feasibility[teacher_name] = _vampd1_feasibility(
            frame=candidate,
            required=required,
            current_vmax=current_vmax_vampd1,
        )
        candidate[f"dadenylate_total_{teacher_name}_dt"] = total_derivative
        candidate[f"VAMPD1_required_{teacher_name}"] = required
        candidate[f"total_balance_with_required_VAMPD1_{teacher_name}"] = (
            candidate["VAK2"]
            - candidate["VSAM"]
            + candidate["VADSL"]
            + candidate["VAPRT"]
            - required
        )
        candidate[f"total_required_closure_error_{teacher_name}"] = (
            candidate[f"total_balance_with_required_VAMPD1_{teacher_name}"]
            - total_derivative
        )
    baseline_metrics = _state_metrics(frame=baseline, curves=observed_curves)
    candidate_metrics = _state_metrics(frame=candidate, curves=observed_curves)
    guards = _guard_assessment(
        baseline=baseline_metrics,
        candidate=candidate_metrics,
        closures=candidate_closures,
        feasibility=feasibility[PRIMARY_TEACHER],
        closure_tolerance=args.closure_tolerance,
    )
    classification = _classify(guards)
    if classification == "VAPRT_zero_rejected_by_ADE_teacher":
        decision = (
            "Reject VAPRT=0 as a promotable hypothesis because it violates the measured ADE trajectory. "
            "Use a narrow reversible VAPRT-fraction map and infer the residual VAMPD1 requirement at each point; do not optimize yet."
        )
        next_step = "map VAPRT fractions at fixed kinetics with residual VAMPD1 feasibility and ADE/IMP guards"
    elif classification == "residual_VAMPD1_requires_capacity_increase":
        decision = (
            "Retain VAPRT=0 only as a diagnostic and run a bounded one-factor VAMPD1 capacity screen "
            "after confirming all concentration safeguards."
        )
        next_step = "bounded one-factor vmax_VAMPD1 screen under the VAPRT=0 diagnostic"
    elif all(guards.values()):
        decision = "Retain VAPRT=0 diagnostically; native VAMPD1 capacity can close the total teacher."
        next_step = "reconstruct joint ATP-ADP-AMP fluxes under the retained VAPRT=0 diagnostic"
    else:
        decision = "Reject VAPRT=0 pending attribution of the failed purine and adenylate guards."
        next_step = "attribute the first failed IMP/ADE/ATP/ADP/AMP guard before changing kinetics"
    primary_required = requirements[PRIMARY_TEACHER]
    window_rows = _window_rows(
        frame=candidate,
        teacher_derivative=candidate[f"dadenylate_total_{PRIMARY_TEACHER}_dt"].to_numpy(
            dtype=float
        ),
        required=primary_required,
    )
    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "model_network_version": MODEL_NETWORK_VERSION,
        "seed_params_path": str(seed_path.resolve()),
        "contract": "fixed 3x QSS-B13PG replay; VAPRT suppressed without optimization",
        "changed_parameters": changed,
        "vmax_VAPRT_seed": vaprt_seed,
        "vmax_VAPRT_candidate": 0.0,
        "solver": {
            "method": args.method,
            "rtol": args.rtol,
            "atol": args.atol,
            "points": args.points,
        },
        "observed_safeguards": list(OBSERVED_STATES),
        "latent_safeguards": list(LATENT_GUARDS),
        "closures": {
            BASELINE_LABEL: baseline_closures,
            CANDIDATE_LABEL: candidate_closures,
        },
        "state_metrics": {
            BASELINE_LABEL: baseline_metrics,
            CANDIDATE_LABEL: candidate_metrics,
        },
        "VAMPD1_requirement": feasibility,
        "guards": guards,
        "guard_pass": bool(all(guards.values())),
        "classification": classification,
        "decision": decision,
        "next_step": next_step,
    }
    pd.concat([baseline, candidate], ignore_index=True).to_csv(
        args.out_dir / "vaprt_zero_replay_timeseries.csv", index=False
    )
    pd.DataFrame(window_rows).to_csv(
        args.out_dir / "vaprt_zero_window_metrics.csv", index=False
    )
    (args.out_dir / "summary.json").write_text(
        json.dumps(_jsonable(summary), indent=2), encoding="utf-8"
    )
    (args.out_dir / "report.md").write_text(_report(summary), encoding="utf-8")
    _plot(
        baseline=baseline,
        candidate=candidate,
        required_vampd1=primary_required,
        current_vmax=current_vmax_vampd1,
        out_path=args.out_dir / "vaprt_zero_vampd1_diagnostic.png",
    )
    print(json.dumps(_jsonable(summary), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
