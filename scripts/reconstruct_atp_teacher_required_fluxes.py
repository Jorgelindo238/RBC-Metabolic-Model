"""Reconstruct ATP-teacher-required VPGK and VGAPDH in the fixed 3x branch."""

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
    / "atp_teacher_required_vpgk_vgapdh_3x_qss_J1_J3"
)

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from equadiff_brodbar import MODEL_NETWORK_VERSION  # noqa: E402
from audit_atp_partition_vdpgm_3x_qss_b13pg import (  # noqa: E402
    CANDIDATE_LABEL,
    WINDOWS,
    _build_contract,
    _replay,
)
from audit_atp_transition_v6pgd_ppp_context import _integral, _time_mean  # noqa: E402
from profile_glycolysis_flux_bottlenecks import _jsonable  # noqa: E402


PRIMARY_TEACHER = "pchip_full_record"
SENSITIVITY_TEACHER = "linear_J1_J4"
QSS_POLICY = "qss_zero_derivative"
NATIVE_POLICY = "native_latent_derivative"
DEFAULT_VMAX = {"VPGK": 4.690379, "VGAPDH": 6.389868}


def _load_atp_data(path: Path = BRODBAR_DATA) -> tuple[np.ndarray, np.ndarray]:
    frame = pd.read_excel(path, engine="openpyxl")
    names = frame.iloc[:, 0].astype(str).str.strip().str.upper()
    rows = frame.loc[names == "ATP"]
    if len(rows) != 1:
        raise RuntimeError(f"Expected exactly one ATP row, found {len(rows)}")
    time = np.asarray([float(value) for value in frame.columns[1:]], dtype=float)
    values = rows.iloc[0, 1:].to_numpy(dtype=float)
    if not np.all(np.diff(time) > 0.0) or not np.all(np.isfinite(values)):
        raise ValueError("ATP observations must be finite and strictly time ordered")
    return time, values


def _teacher_variants(
    exp_time: np.ndarray, exp_values: np.ndarray, grid: np.ndarray
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    pchip = PchipInterpolator(exp_time, exp_values, extrapolate=False)
    slope = float((exp_values[1] - exp_values[0]) / (exp_time[1] - exp_time[0]))
    linear = exp_values[0] + slope * (grid - exp_time[0])
    return {
        PRIMARY_TEACHER: (
            np.asarray(pchip(grid), dtype=float),
            np.asarray(pchip.derivative()(grid), dtype=float),
        ),
        SENSITIVITY_TEACHER: (
            np.asarray(linear, dtype=float),
            np.full_like(grid, slope, dtype=float),
        ),
    }


def _required_vpgk(
    atp_derivative: np.ndarray,
    consumption: np.ndarray,
    vpk: np.ndarray,
    vak: np.ndarray,
) -> np.ndarray:
    return (
        np.asarray(atp_derivative, dtype=float)
        + np.asarray(consumption, dtype=float)
        - np.asarray(vpk, dtype=float)
        - np.asarray(vak, dtype=float)
    )


def _required_vgapdh(
    b13pg_derivative: np.ndarray,
    required_vpgk: np.ndarray,
    vdpgm: np.ndarray,
) -> np.ndarray:
    return (
        np.asarray(b13pg_derivative, dtype=float)
        + np.asarray(required_vpgk, dtype=float)
        + np.asarray(vdpgm, dtype=float)
    )


def _build_reconstruction(
    *,
    native: pd.DataFrame,
    teacher_name: str,
    teacher_atp: np.ndarray,
    teacher_derivative: np.ndarray,
    b13_policy: str,
) -> pd.DataFrame:
    frame = native.copy()
    required_vpgk = _required_vpgk(
        teacher_derivative,
        frame["ATP_consumption_flux"].to_numpy(dtype=float),
        frame["VPK"].to_numpy(dtype=float),
        frame["VAK"].to_numpy(dtype=float),
    )
    if b13_policy == QSS_POLICY:
        b13_derivative = np.zeros_like(required_vpgk)
    elif b13_policy == NATIVE_POLICY:
        b13_derivative = frame["B13PG_ode_derivative"].to_numpy(dtype=float)
    else:
        raise ValueError(f"Unknown B13PG policy: {b13_policy}")
    required_vgapdh = _required_vgapdh(
        b13_derivative,
        required_vpgk,
        frame["VDPGM"].to_numpy(dtype=float),
    )
    reconstructed_atp = (
        required_vpgk
        + frame["VPK"].to_numpy(dtype=float)
        + frame["VAK"].to_numpy(dtype=float)
        - frame["ATP_consumption_flux"].to_numpy(dtype=float)
    )
    reconstructed_b13 = (
        required_vgapdh
        - required_vpgk
        - frame["VDPGM"].to_numpy(dtype=float)
    )
    frame["teacher_method"] = teacher_name
    frame["B13PG_policy"] = b13_policy
    frame["ATP_teacher"] = teacher_atp
    frame["dATP_teacher_dt"] = teacher_derivative
    frame["VPGK_required"] = required_vpgk
    frame["VPGK_required_projected_nonnegative"] = np.maximum(required_vpgk, 0.0)
    frame["ATP_teacher_balance_reconstruction"] = reconstructed_atp
    frame["ATP_teacher_balance_error"] = reconstructed_atp - teacher_derivative
    frame["dB13PG_assumed_dt"] = b13_derivative
    frame["VGAPDH_required"] = required_vgapdh
    frame["B13PG_required_balance_reconstruction"] = reconstructed_b13
    frame["B13PG_required_balance_error"] = reconstructed_b13 - b13_derivative
    return frame


def _vmax(params: Mapping[str, Any], reaction: str) -> float:
    return float(params.get(f"vmax_{reaction}", DEFAULT_VMAX[reaction]))


def _feasibility(
    *,
    frame: pd.DataFrame,
    reaction: str,
    required_column: str,
    native_column: str,
    vmax: float,
) -> dict[str, Any]:
    time = frame["time_day"].to_numpy(dtype=float)
    required = frame[required_column].to_numpy(dtype=float)
    native = frame[native_column].to_numpy(dtype=float)
    nonnegative = required >= 0.0
    below_hard_ceiling = required <= float(vmax)
    feasible = nonnegative & below_hard_ceiling
    projected = np.clip(required, 0.0, float(vmax))
    positive_required = required > 0.0
    scalable = positive_required & (native > 1e-12)
    required_vmax = np.full_like(required, np.nan)
    required_vmax[scalable] = float(vmax) * required[scalable] / native[scalable]
    finite_required_vmax = required_vmax[np.isfinite(required_vmax)]
    return {
        "reaction": reaction,
        "current_vmax": float(vmax),
        "required_min": float(np.min(required)),
        "required_max": float(np.max(required)),
        "required_integral": _integral(required, time),
        "native_integral": _integral(native, time),
        "required_to_native_integral_ratio": _integral(required, time)
        / max(abs(_integral(native, time)), 1e-30),
        "time_fraction_nonnegative": float(np.mean(nonnegative)),
        "time_fraction_below_hard_ceiling": float(np.mean(below_hard_ceiling)),
        "time_fraction_hard_feasible": float(np.mean(feasible)),
        "negative_requirement_integral": _integral(np.minimum(required, 0.0), time),
        "hard_ceiling_excess_integral": _integral(
            np.maximum(required - float(vmax), 0.0), time
        ),
        "projected_requirement_rmse": float(np.sqrt(np.mean((projected - required) ** 2))),
        "first_negative_day": (
            float(time[np.flatnonzero(~nonnegative)[0]])
            if np.any(~nonnegative)
            else None
        ),
        "first_hard_ceiling_exceedance_day": (
            float(time[np.flatnonzero(~below_hard_ceiling)[0]])
            if np.any(~below_hard_ceiling)
            else None
        ),
        "fixed_state_required_vmax_median": (
            float(np.median(finite_required_vmax))
            if finite_required_vmax.size
            else None
        ),
        "fixed_state_required_vmax_p95": (
            float(np.quantile(finite_required_vmax, 0.95))
            if finite_required_vmax.size
            else None
        ),
        "fixed_state_required_vmax_max": (
            float(np.max(finite_required_vmax))
            if finite_required_vmax.size
            else None
        ),
    }


def _window_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    all_time = frame["time_day"].to_numpy(dtype=float)
    for window, start, end in WINDOWS:
        mask = (all_time >= start - 1e-12) & (all_time <= end + 1e-12)
        local = frame.loc[mask]
        time = local["time_day"].to_numpy(dtype=float)
        required_vpgk = local["VPGK_required"].to_numpy(dtype=float)
        required_vgapdh = local["VGAPDH_required"].to_numpy(dtype=float)
        rows.append(
            {
                "teacher_method": str(frame["teacher_method"].iloc[0]),
                "B13PG_policy": str(frame["B13PG_policy"].iloc[0]),
                "window": window,
                "VPGK_required_integral": _integral(required_vpgk, time),
                "VPGK_native_integral": _integral(local["VPGK"], time),
                "VPGK_required_to_native_ratio": _integral(required_vpgk, time)
                / max(abs(_integral(local["VPGK"], time)), 1e-30),
                "VPGK_negative_time_fraction": float(np.mean(required_vpgk < 0.0)),
                "VGAPDH_required_integral": _integral(required_vgapdh, time),
                "VGAPDH_native_integral": _integral(local["VGAPDH"], time),
                "VGAPDH_required_to_native_ratio": _integral(required_vgapdh, time)
                / max(abs(_integral(local["VGAPDH"], time)), 1e-30),
                "ATP_teacher_mean_mM": _time_mean(local["ATP_teacher"], time),
                "ATP_native_mean_mM": _time_mean(local["ATP"], time),
            }
        )
    return rows


def _classify(
    *,
    primary_vpgk: Mapping[str, Any],
    primary_vgapdh: Mapping[str, Any],
    observed_points_j1_j3: int,
    pchip_linear_integral_difference: float,
) -> dict[str, Any]:
    gates = {
        "ATP_teacher_has_fewer_than_two_observations_in_J1_J3": observed_points_j1_j3 < 2,
        "VPGK_requirement_changes_sign": float(primary_vpgk["time_fraction_nonnegative"])
        < 1.0,
        "VGAPDH_requirement_exceeds_current_hard_ceiling": float(
            primary_vgapdh["hard_ceiling_excess_integral"]
        )
        > 0.0,
        "PCHIP_linear_integrals_agree_within_1pct": abs(
            pchip_linear_integral_difference
        )
        <= 0.01,
    }
    if (
        gates["ATP_teacher_has_fewer_than_two_observations_in_J1_J3"]
        and gates["VPGK_requirement_changes_sign"]
    ):
        classification = (
            "ATP-only inversion is temporally underconstrained and sign-infeasible "
            "with the other ATP fluxes frozen"
        )
    elif gates["VGAPDH_requirement_exceeds_current_hard_ceiling"]:
        classification = "required upstream glycolytic supply exceeds current GAPDH capacity"
    else:
        classification = "required fluxes are algebraically and kinetically feasible"
    return {"classification": classification, "classification_gates": gates}


def _plot(primary: pd.DataFrame, params: Mapping[str, Any], out_path: Path) -> None:
    time = primary["time_day"].to_numpy(dtype=float)
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), constrained_layout=True)
    axes[0, 0].plot(time, primary["ATP_teacher"], "#b45309", label="ATP teacher")
    axes[0, 0].plot(time, primary["ATP"], "#111827", label="ATP native 3x")
    axes[0, 1].plot(time, primary["VPGK_required"], "#b45309", label="VPGK required")
    axes[0, 1].plot(time, primary["VPGK"], "#111827", label="VPGK native")
    axes[0, 1].axhline(0.0, color="#6b7280", lw=1)
    axes[0, 1].text(
        0.98,
        0.95,
        f"current Vmax = {_vmax(params, 'VPGK'):.2f} mM/day",
        transform=axes[0, 1].transAxes,
        ha="right",
        va="top",
        color="#991b1b",
    )
    axes[1, 0].plot(time, primary["VGAPDH_required"], "#b45309", label="VGAPDH required")
    axes[1, 0].plot(time, primary["VGAPDH"], "#111827", label="VGAPDH native")
    axes[1, 0].axhline(_vmax(params, "VGAPDH"), color="#991b1b", ls="--", label="VGAPDH Vmax")
    axes[1, 1].plot(time, primary["ATP_consumption_flux"], "#991b1b", label="ATP consumption")
    axes[1, 1].plot(time, primary["VPK"], "#2563eb", label="VPK")
    axes[1, 1].plot(time, primary["VAK"], "#0f766e", label="VAK")
    axes[0, 0].set_title("Measured ATP interpolation versus fixed 3x replay")
    axes[0, 1].set_title("ATP-balance inversion for VPGK")
    axes[1, 0].set_title("QSS-B13PG inversion for VGAPDH")
    axes[1, 1].set_title("Frozen ATP terms driving the inversion")
    axes[0, 0].set_ylabel("mM")
    for axis in (axes[0, 1], axes[1, 0], axes[1, 1]):
        axis.set_ylabel("mM/day")
    for axis in axes.flat:
        axis.set_xlabel("Day")
        axis.grid(alpha=0.2)
        axis.legend(frameon=False)
    fig.suptitle("FLA ATP teacher inversion in fixed VDPGM 3x QSS-B13PG context")
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _report(summary: Mapping[str, Any]) -> str:
    primary = summary["primary_feasibility"]
    vpgk = primary["VPGK"]
    gapdh = primary["VGAPDH"]
    sensitivity = summary["teacher_sensitivity"]
    return "\n".join(
        [
            "# Reconstruction ATP -> VPGK -> VGAPDH, J1-J3",
            "",
            "## Contract",
            "",
            "The fixed `vmax_VDPGM = 3x` QSS-B13PG replay is not refitted. The ATP concentration teacher is differentiated, while every other ATP-producing and ATP-consuming flux remains native. B13PG is not treated as an observed teacher.",
            "",
            "## Results",
            "",
            f"- Classification: **{summary['classification']['classification']}**.",
            f"- ATP observations inside J1-J3: `{summary['data_contract']['observed_ATP_points_J1_J3']}`; the next observation is day 4.",
            f"- Integrated required/native VPGK ratio: `{vpgk['required_to_native_integral_ratio']:.3f}x`.",
            f"- VPGK requirement range: `{vpgk['required_min']:.4f}` to `{vpgk['required_max']:.4f}` mM/day.",
            f"- Fraction of time with nonnegative required VPGK: `{100.0 * vpgk['time_fraction_nonnegative']:.1f}%`.",
            f"- Fixed-state VPGK Vmax required, median/p95: `{vpgk['fixed_state_required_vmax_median']:.3f}` / `{vpgk['fixed_state_required_vmax_p95']:.3f}`.",
            f"- Integrated required/native VGAPDH ratio: `{gapdh['required_to_native_integral_ratio']:.3f}x`.",
            f"- VGAPDH maximum requirement/current Vmax: `{gapdh['required_max']:.4f}` / `{gapdh['current_vmax']:.4f}` mM/day.",
            f"- PCHIP versus linear VPGK integral difference: `{100.0 * sensitivity['relative_VPGK_integral_difference']:.4f}%`.",
            "",
            "## Decision",
            "",
            "Do not open `vmax_VPGK`, `vmax_VGAPDH`, redox constants, or ATP-demand kinetics from this ATP-only inversion. Its integrated demand is robust to the interpolation choice, but its pointwise sign is incompatible with an irreversible PGK flux when VPK, VAK, and ATP consumption are frozen. The early upstream requirement also exceeds the current GAPDH hard ceiling. The next structural audit must jointly reconstruct ATP, ADP, and AMP balances and verify adenylate-kinase directionality before defining another kinetic scope.",
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
    grid = np.linspace(1.0, 3.0, args.points)
    state, _seed_params, params, seed_path = _build_contract()
    native, closures = _replay(
        label=CANDIDATE_LABEL,
        state=state,
        params=params,
        time=grid,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
        closure_tolerance=args.closure_tolerance,
    )
    exp_time, exp_atp = _load_atp_data()
    teachers = _teacher_variants(exp_time, exp_atp, grid)
    reconstructions: dict[tuple[str, str], pd.DataFrame] = {}
    for teacher_name, (teacher_atp, teacher_derivative) in teachers.items():
        for policy in (QSS_POLICY, NATIVE_POLICY):
            reconstructions[(teacher_name, policy)] = _build_reconstruction(
                native=native,
                teacher_name=teacher_name,
                teacher_atp=teacher_atp,
                teacher_derivative=teacher_derivative,
                b13_policy=policy,
            )
    primary = reconstructions[(PRIMARY_TEACHER, QSS_POLICY)]
    vmax_vpgk = _vmax(params, "VPGK")
    vmax_vgapdh = _vmax(params, "VGAPDH")
    feasibility: dict[str, Any] = {}
    for (teacher_name, policy), frame in reconstructions.items():
        key = f"{teacher_name}__{policy}"
        feasibility[key] = {
            "VPGK": _feasibility(
                frame=frame,
                reaction="VPGK",
                required_column="VPGK_required",
                native_column="VPGK",
                vmax=vmax_vpgk,
            ),
            "VGAPDH": _feasibility(
                frame=frame,
                reaction="VGAPDH",
                required_column="VGAPDH_required",
                native_column="VGAPDH",
                vmax=vmax_vgapdh,
            ),
        }
    primary_key = f"{PRIMARY_TEACHER}__{QSS_POLICY}"
    linear_key = f"{SENSITIVITY_TEACHER}__{QSS_POLICY}"
    primary_vpgk_integral = feasibility[primary_key]["VPGK"]["required_integral"]
    linear_vpgk_integral = feasibility[linear_key]["VPGK"]["required_integral"]
    relative_difference = float(
        (linear_vpgk_integral - primary_vpgk_integral)
        / max(abs(primary_vpgk_integral), 1e-30)
    )
    observed_j1_j3 = int(np.sum((exp_time >= 1.0) & (exp_time <= 3.0)))
    classification = _classify(
        primary_vpgk=feasibility[primary_key]["VPGK"],
        primary_vgapdh=feasibility[primary_key]["VGAPDH"],
        observed_points_j1_j3=observed_j1_j3,
        pchip_linear_integral_difference=relative_difference,
    )
    all_frames = pd.concat(reconstructions.values(), ignore_index=True)
    windows = pd.DataFrame(
        [row for frame in reconstructions.values() for row in _window_rows(frame)]
    )
    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "model_network_version": MODEL_NETWORK_VERSION,
        "seed_params_path": str(seed_path.resolve()),
        "kinetic_contract": "fixed 3x vmax_VDPGM QSS-B13PG replay; no optimization",
        "changed_parameters_in_this_run": [],
        "data_contract": {
            "ATP_source": str(BRODBAR_DATA.resolve()),
            "ATP_observation_days": exp_time.tolist(),
            "observed_ATP_points_J1_J3": observed_j1_j3,
            "next_ATP_observation_day": 4.0,
            "primary_teacher": PRIMARY_TEACHER,
            "sensitivity_teacher": SENSITIVITY_TEACHER,
            "B13PG_observation_used": False,
            "B13PG_policies": [QSS_POLICY, NATIVE_POLICY],
        },
        "solver": {
            "method": args.method,
            "rtol": args.rtol,
            "atol": args.atol,
            "points": args.points,
        },
        "native_closures": closures,
        "primary_feasibility": feasibility[primary_key],
        "all_feasibility": feasibility,
        "teacher_sensitivity": {
            "PCHIP_VPGK_required_integral": primary_vpgk_integral,
            "linear_VPGK_required_integral": linear_vpgk_integral,
            "relative_VPGK_integral_difference": relative_difference,
        },
        "classification": classification,
        "decision": "do not calibrate VPGK or VGAPDH from ATP alone",
        "next_step": "joint ATP-ADP-AMP teacher-balance and adenylate-kinase directionality audit",
    }
    all_frames.to_csv(args.out_dir / "required_flux_timeseries.csv", index=False)
    windows.to_csv(args.out_dir / "required_flux_window_metrics.csv", index=False)
    (args.out_dir / "summary.json").write_text(
        json.dumps(_jsonable(summary), indent=2), encoding="utf-8"
    )
    (args.out_dir / "report.md").write_text(_report(summary), encoding="utf-8")
    _plot(primary, params, args.out_dir / "atp_required_flux_reconstruction.png")
    print(json.dumps(_jsonable(summary), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
