"""Screen a reversible B13PG-only initialization at fixed kinetics."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator
from scipy.optimize import brentq


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
DEFAULT_OUT_DIR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "b13pg_constrained_initialization_screen_J1_J10"
)
BRODBAR_DATA = SRC_DIR / "Data_Bordbar_et_al_exp.xlsx"

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from equadiff_brodbar import BRODBAR_METABOLITE_MAP, equadiff_brodbar  # noqa: E402
from flux_visualization import FluxTracker  # noqa: E402
from MM_calibration import load_initial_conditions  # noqa: E402
from profile_glycolysis_flux_bottlenecks import (  # noqa: E402
    _jsonable,
    _load_params,
    _simulate_and_track,
)
from audit_atp_transition_v6pgd_ppp_context import (  # noqa: E402
    ATP_CONSUMPTION,
    ATP_PRODUCTION,
    CANDIDATE_LABEL,
    _atp_balance,
    _candidate_params,
    _effective_atp_balance,
    _first_sustained_below,
    _state_with_saved_latent,
)
from audit_b13pg_balance_v6pgd_ppp_context import (  # noqa: E402
    _build_timeseries as _build_b13pg_timeseries,
    _integral,
)


REVERT_LABEL = "duplicated_data_revert"
QSS_SCALES = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0)
QSS_LABEL = "qss_1.000x"
B13PG_INDEX = int(BRODBAR_METABOLITE_MAP["B13PG"])
B23PG_INDEX = int(BRODBAR_METABOLITE_MAP["B23PG"])
ATP_INDEX = int(BRODBAR_METABOLITE_MAP["ATP"])
NAD_INDEX = int(BRODBAR_METABOLITE_MAP["NAD"])
NADH_INDEX = int(BRODBAR_METABOLITE_MAP["NADH"])
SHORT_GUARD_TOLERANCE = 0.10
PULSE_REDUCTION_TARGET = 0.05


def _label(scale: float) -> str:
    return f"qss_{float(scale):.3f}x"


def _state_with_b13pg(
    base_state: np.ndarray,
    value: float,
) -> np.ndarray:
    state = np.asarray(base_state, dtype=float).copy()
    state[B13PG_INDEX] = float(value)
    changed = set(np.flatnonzero(state != np.asarray(base_state, dtype=float)).tolist())
    if changed - {B13PG_INDEX}:
        raise RuntimeError(f"B13PG initialization contract failed: changed={changed}")
    return state


def _initial_balance(
    *,
    state: np.ndarray,
    params: Mapping[str, Any],
) -> dict[str, float]:
    tracker = FluxTracker()
    derivative = np.asarray(
        equadiff_brodbar(
            1.0,
            np.asarray(state, dtype=float),
            custom_params=dict(params),
            curve_fit_strength=0.0,
            flux_tracker=tracker,
        ),
        dtype=float,
    )
    fluxes = {
        reaction: float(np.asarray(tracker.fluxes[reaction], dtype=float)[-1])
        for reaction in ("VGAPDH", "VPGK", "VDPGM")
    }
    raw = fluxes["VGAPDH"] - fluxes["VPGK"] - fluxes["VDPGM"]
    return {
        **fluxes,
        "raw_B13PG_balance": float(raw),
        "effective_B13PG_derivative": float(derivative[B13PG_INDEX]),
    }


def _find_qss_root(
    balance: Callable[[float], float],
    *,
    lower: float,
    upper: float,
) -> float:
    lower_value = float(balance(float(lower)))
    upper_value = float(balance(float(upper)))
    if lower_value == 0.0:
        return float(lower)
    if upper_value == 0.0:
        return float(upper)
    if lower_value * upper_value > 0.0:
        raise RuntimeError(
            "B13PG J1 balance is not bracketed: "
            f"f({lower})={lower_value}, f({upper})={upper_value}"
        )
    return float(brentq(balance, float(lower), float(upper), xtol=1e-14, rtol=1e-12))


def _load_teachers() -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, PchipInterpolator]]:
    raw = pd.read_excel(BRODBAR_DATA, engine="openpyxl")
    names = raw.iloc[:, 0].astype(str).str.strip().str.upper()
    time = np.asarray([float(value) for value in raw.columns[1:]], dtype=float)
    values: dict[str, np.ndarray] = {}
    teachers: dict[str, PchipInterpolator] = {}
    for metabolite in ("B13PG", "B23PG", "ATP"):
        matches = raw.loc[names == metabolite].iloc[:, 1:]
        if len(matches) != 1:
            raise RuntimeError(f"Expected one {metabolite} row, found {len(matches)}")
        values[metabolite] = matches.iloc[0].to_numpy(dtype=float)
        teachers[metabolite] = PchipInterpolator(time, values[metabolite])
    return time, values, teachers


def _nrmse(model: np.ndarray, teacher: np.ndarray, full_teacher: np.ndarray) -> float:
    model = np.asarray(model, dtype=float)
    teacher = np.asarray(teacher, dtype=float)
    full_teacher = np.asarray(full_teacher, dtype=float)
    rmse = float(np.sqrt(np.mean((model - teacher) ** 2)))
    scale = max(
        float(np.ptp(full_teacher)),
        float(np.median(np.abs(full_teacher))),
        1e-12,
    )
    return rmse / scale


def _replay(
    *,
    label: str,
    state: np.ndarray,
    params: Mapping[str, Any],
    t_eval: np.ndarray,
    teachers: Mapping[str, PchipInterpolator],
    teacher_values: Mapping[str, np.ndarray],
    method: str,
    rtol: float,
    atol: float,
    closure_tolerance: float,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    sol, fluxes, derivatives = _simulate_and_track(
        params=params,
        t_eval=t_eval,
        method=method,
        rtol=rtol,
        atol=atol,
        x0_override=state,
    )
    frame, b13_closure = _build_b13pg_timeseries(
        label=label,
        sol=sol,
        fluxes=fluxes,
        derivatives=derivatives,
        params=params,
        duplicated_teacher=teachers["B13PG"],
        closure_tolerance=closure_tolerance,
    )
    production, consumption, raw_atp = _atp_balance(fluxes)
    atp = np.asarray(sol.y[ATP_INDEX], dtype=float)
    effective_atp, atp_damping = _effective_atp_balance(raw_atp, atp)
    atp_derivative = np.asarray(derivatives[ATP_INDEX], dtype=float)
    atp_closure = float(np.max(np.abs(effective_atp - atp_derivative)))
    if atp_closure > float(closure_tolerance):
        raise RuntimeError(f"ATP closure failed for {label}: {atp_closure:.6g}")
    time = np.asarray(sol.t, dtype=float)
    b23pg = np.asarray(sol.y[B23PG_INDEX], dtype=float)
    nad = np.asarray(sol.y[NAD_INDEX], dtype=float)
    nadh = np.asarray(sol.y[NADH_INDEX], dtype=float)
    teacher_atp = np.asarray(teachers["ATP"](time), dtype=float)
    teacher_b23pg = np.asarray(teachers["B23PG"](time), dtype=float)
    frame["ATP_production_flux"] = production
    frame["ATP_consumption_flux"] = consumption
    frame["ATP_raw_net_flux"] = raw_atp
    frame["ATP_effective_net_flux"] = effective_atp
    frame["ATP_damping_adjustment"] = atp_damping
    frame["ATP_closure_error"] = effective_atp - atp_derivative
    frame["ATP_teacher"] = teacher_atp
    frame["B23PG_teacher"] = teacher_b23pg
    drainage = frame["VPGK"].to_numpy(dtype=float) + frame["VDPGM"].to_numpy(dtype=float)
    input_integral = _integral(frame["VGAPDH"], time)
    drainage_integral = _integral(drainage, time)
    stock_supported = max(0.0, drainage_integral - input_integral)
    nad_total = nad + nadh
    metrics = {
        "candidate": label,
        "horizon_days": [float(time[0]), float(time[-1])],
        "B13PG_initial_mM": float(sol.y[B13PG_INDEX, 0]),
        "B23PG_initial_mM": float(b23pg[0]),
        "ATP_initial_mM": float(atp[0]),
        "B13PG_final_mM": float(sol.y[B13PG_INDEX, -1]),
        "B23PG_final_mM": float(b23pg[-1]),
        "ATP_final_mM": float(atp[-1]),
        "ATP_minimum_mM": float(np.min(atp)),
        "all_state_minimum_mM": float(np.min(sol.y)),
        "NAD_minimum_mM": float(np.min(nad)),
        "NADH_minimum_mM": float(np.min(nadh)),
        "NAD_NADH_max_drift_mM": float(np.max(np.abs(nad_total - nad_total[0]))),
        "B13PG_maximum_mM": float(np.max(sol.y[B13PG_INDEX])),
        "VPGK_peak_mM_per_day": float(np.max(frame["VPGK"])),
        "VPGK_integral_ATP_yield_mM": _integral(frame["VPGK"], time),
        "VDPGM_integral_shunt_mM": _integral(frame["VDPGM"], time),
        "VGAPDH_integral_input_mM": input_integral,
        "total_B13PG_drainage_integral_mM": drainage_integral,
        "stock_supported_drainage_mM": stock_supported,
        "ATP_production_integral_mM": _integral(production, time),
        "ATP_consumption_integral_mM": _integral(consumption, time),
        "ATP_nrmse": _nrmse(atp, teacher_atp, teacher_values["ATP"]),
        "B23PG_nrmse": _nrmse(b23pg, teacher_b23pg, teacher_values["B23PG"]),
        "ATP_below_0.01_mM_day": _first_sustained_below(
            time, atp, threshold=0.01, duration=0.02
        ),
        "max_B13PG_closure_error": float(
            b13_closure["max_abs_B13PG_closure_error"]
        ),
        "max_ATP_closure_error": atp_closure,
    }
    return frame, metrics


def _short_guards(
    *,
    row: Mapping[str, Any],
    revert: Mapping[str, Any],
    initial_balance: Mapping[str, float],
    b23pg_locked_value: float,
    closure_tolerance: float,
) -> dict[str, bool]:
    return {
        "exact_J1_quasi_steady_balance": abs(
            float(initial_balance["effective_B13PG_derivative"])
        )
        <= 1e-9,
        "B13PG_closure_exact": float(row["max_B13PG_closure_error"])
        <= float(closure_tolerance),
        "ATP_closure_exact": float(row["max_ATP_closure_error"])
        <= float(closure_tolerance),
        "all_states_nonnegative": float(row["all_state_minimum_mM"]) >= -1e-10,
        "NAD_NADH_positive": float(row["NAD_minimum_mM"]) >= -1e-10
        and float(row["NADH_minimum_mM"]) >= -1e-10,
        "NAD_NADH_conserved": float(row["NAD_NADH_max_drift_mM"]) <= 1e-9,
        "B23PG_initial_locked": abs(
            float(row["B23PG_initial_mM"]) - float(b23pg_locked_value)
        )
        <= 1e-12,
        "B23PG_trajectory_noninferior_10pct": float(row["B23PG_nrmse"])
        <= (1.0 + SHORT_GUARD_TOLERANCE)
        * max(float(revert["B23PG_nrmse"]), 1e-30),
        "duplicated_stock_pulse_removed_95pct": float(
            row["stock_supported_drainage_mM"]
        )
        <= PULSE_REDUCTION_TARGET
        * max(float(revert["stock_supported_drainage_mM"]), 1e-30),
    }


def _select_short_candidate(
    assessments: Sequence[Mapping[str, Any]],
) -> str | None:
    eligible = [row for row in assessments if bool(row["short_guard_pass"])]
    if not eligible:
        return None
    return str(
        min(
            eligible,
            key=lambda row: (
                float(row["ATP_nrmse"]),
                abs(float(row["scale"]) - 1.0),
            ),
        )["candidate"]
    )


def _long_guards(
    *,
    row: Mapping[str, Any],
    revert: Mapping[str, Any],
) -> dict[str, bool]:
    return {
        "ATP_does_not_collapse_below_0.01_mM": row["ATP_below_0.01_mM_day"] is None,
        "ATP_trajectory_noninferior_5pct": float(row["ATP_nrmse"])
        <= 1.05 * max(float(revert["ATP_nrmse"]), 1e-30),
        "B23PG_trajectory_noninferior_10pct": float(row["B23PG_nrmse"])
        <= 1.10 * max(float(revert["B23PG_nrmse"]), 1e-30),
        "all_states_nonnegative": float(row["all_state_minimum_mM"]) >= -1e-10,
        "NAD_NADH_positive_and_conserved": float(row["NAD_minimum_mM"]) >= -1e-10
        and float(row["NADH_minimum_mM"]) >= -1e-10
        and float(row["NAD_NADH_max_drift_mM"]) <= 1e-9,
    }


def _plot(
    *,
    short_frames: Mapping[str, pd.DataFrame],
    short_metrics: Sequence[Mapping[str, Any]],
    long_frames: Mapping[str, pd.DataFrame],
    selected: str | None,
    qss_value: float,
    duplicated_value: float,
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.5), constrained_layout=True)
    cmap = plt.get_cmap("viridis")
    qss_labels = [_label(scale) for scale in QSS_SCALES]
    colors = {label: cmap(i / max(len(qss_labels) - 1, 1)) for i, label in enumerate(qss_labels)}
    colors[REVERT_LABEL] = "#111827"
    for label, frame in short_frames.items():
        color = colors[label]
        linewidth = 2.4 if label in {REVERT_LABEL, selected} else 1.1
        axes[0, 0].plot(frame["time_day"], frame["B13PG"], color=color, linewidth=linewidth, label=label)
        axes[0, 1].plot(frame["time_day"], frame["B23PG"], color=color, linewidth=linewidth, label=label)
        axes[0, 2].plot(frame["time_day"], frame["ATP"], color=color, linewidth=linewidth, label=label)
        axes[1, 0].plot(frame["time_day"], frame["VPGK"], color=color, linewidth=linewidth, label=label)
    reference = next(iter(short_frames.values()))
    axes[0, 1].plot(reference["time_day"], reference["B23PG_teacher"], "k--", linewidth=2, label="B23PG teacher")
    axes[0, 2].plot(reference["time_day"], reference["ATP_teacher"], "k--", linewidth=2, label="ATP teacher")
    ordered = sorted(short_metrics, key=lambda row: float(row["B13PG_initial_mM"]))
    axes[1, 1].plot(
        [row["B13PG_initial_mM"] for row in ordered],
        [row["stock_supported_drainage_mM"] for row in ordered],
        marker="o",
        color="#7c3aed",
    )
    axes[1, 1].axvline(qss_value, color="#15803d", linestyle="--", label="J1 QSS root")
    axes[1, 1].axvline(duplicated_value, color="#111827", linestyle=":", label="revert value")
    axes[1, 1].set_xscale("log")
    axes[1, 1].set_yscale("log")
    for label, frame in long_frames.items():
        color = "#15803d" if label != REVERT_LABEL else "#111827"
        axes[1, 2].plot(frame["time_day"], frame["ATP_production_flux"], color=color, label=f"{label}: production")
        axes[1, 2].plot(frame["time_day"], frame["ATP_consumption_flux"], color=color, linestyle="--", label=f"{label}: consumption")
    if not long_frames:
        axes[1, 2].text(
            0.5,
            0.5,
            "No J1-J10 transfer\nQSS root failed the B23PG guard",
            ha="center",
            va="center",
            transform=axes[1, 2].transAxes,
            fontsize=12,
        )
        axes[1, 2].set_axis_off()
    titles = (
        "B13PG initialization sensitivity",
        "B23PG locked-state guard",
        "ATP short-horizon consistency",
        "VPGK pulse sensitivity",
        "Stock-supported B13PG drainage",
        "J1-J10 ATP balance",
    )
    for axis, title in zip(axes.flat, titles):
        axis.set_title(title)
        axis.set_xlabel("Time (day)" if axis is not axes[1, 1] else "B13PG(0), mM")
        axis.grid(alpha=0.22)
        handles, labels = axis.get_legend_handles_labels()
        if handles:
            axis.legend(frameon=False, fontsize=6)
    axes[0, 0].set_ylabel("mM")
    axes[0, 0].set_yscale("symlog", linthresh=1e-5)
    axes[0, 1].set_ylabel("mM")
    axes[0, 2].set_ylabel("mM")
    axes[1, 0].set_ylabel("mM/day")
    axes[1, 1].set_ylabel("mM")
    axes[1, 2].set_ylabel("mM/day")
    fig.suptitle("Reversible B13PG(0)-only constrained initialization screen")
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    lines = [
        "# Reversible B13PG(0)-only initialization screen",
        "",
        "## Contract",
        "",
        "- Only `B13PG(0)` varied; B23PG(0), all other states, and all kinetic constants were locked.",
        "- The retained `vmax_V6PGD = 9.0` balanced PPP context was used throughout.",
        "- The duplicated `3.584045 mM` value was preserved as an explicit revert branch.",
        "- No optimization, parameter promotion, or initial-state promotion was performed.",
        "",
        "## J1 root",
        "",
        f"- Duplicated-data B13PG(0): `{summary['duplicated_B13PG_initial_mM']:.9g} mM`.",
        f"- Exact J1 quasi-steady root: `{summary['qss_B13PG_initial_mM']:.9g} mM`.",
        f"- Root/duplicated ratio: `{summary['qss_to_duplicated_ratio']:.6g}`.",
        f"- Effective derivative at root: `{summary['qss_initial_balance']['effective_B13PG_derivative']:.3e} mM/day`.",
        "",
        "## J1-J3 screen",
        "",
        "| Case | B13PG(0) | J1 derivative | Stock drainage | VPGK ATP | ATP nRMSE | B23PG nRMSE | Guard |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    balance_by_label = summary["initial_balance_by_candidate"]
    assessment_by_label = {
        str(row["candidate"]): row for row in summary["short_assessments"]
    }
    for row in summary["short_metrics"]:
        label = str(row["candidate"])
        assessment = assessment_by_label.get(label)
        guard = "revert" if assessment is None else str(bool(assessment["short_guard_pass"]))
        lines.append(
            f"| `{label}` | {row['B13PG_initial_mM']:.6g} | "
            f"{balance_by_label[label]['effective_B13PG_derivative']:.5g} | "
            f"{row['stock_supported_drainage_mM']:.5g} | "
            f"{row['VPGK_integral_ATP_yield_mM']:.5g} | "
            f"{row['ATP_nrmse']:.5g} | {row['B23PG_nrmse']:.5g} | {guard} |"
        )
    lines.extend(
        [
            "",
            "## J1-J10 transfer",
            "",
            str(summary["long_horizon_statement"]),
            "",
            "## Decision",
            "",
            f"**`{summary['decision']}`**",
            "",
            str(summary["decision_rationale"]),
            "",
            f"Next: {summary['next_step']}.",
            "",
            "No kinetic constant or initial condition was promoted.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_screen(
    *,
    refinement_dir: Path,
    out_dir: Path,
    short_timepoints: int,
    long_timepoints: int,
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
    if diagnostic_candidates["promoted"]:
        raise RuntimeError("B13PG screen requires non-promoted PPP initializations")
    seed_params_path = Path(refinement_summary["seed_params_path"])
    params = _candidate_params(_load_params(seed_params_path))
    base_state = _state_with_saved_latent(
        np.asarray(load_initial_conditions(), dtype=float),
        diagnostic_candidates["candidates"][CANDIDATE_LABEL]["latent_initial_states"],
    )
    duplicated_b13pg = float(base_state[B13PG_INDEX])
    locked_b23pg = float(base_state[B23PG_INDEX])
    _, teacher_values, teachers = _load_teachers()

    def balance(value: float) -> float:
        state = _state_with_b13pg(base_state, value)
        return float(_initial_balance(state=state, params=params)["raw_B13PG_balance"])

    qss_value = _find_qss_root(balance, lower=0.0, upper=duplicated_b13pg)
    values = {REVERT_LABEL: duplicated_b13pg}
    values.update({_label(scale): float(scale) * qss_value for scale in QSS_SCALES})
    states = {label: _state_with_b13pg(base_state, value) for label, value in values.items()}
    initial_balances = {
        label: _initial_balance(state=state, params=params)
        for label, state in states.items()
    }
    short_time = np.linspace(1.0, 3.0, int(short_timepoints))
    short_frames: dict[str, pd.DataFrame] = {}
    short_metrics: list[dict[str, Any]] = []
    for label, state in states.items():
        print(f"[b13pg-init] J1-J3 replay {label}", flush=True)
        frame, metrics = _replay(
            label=label,
            state=state,
            params=params,
            t_eval=short_time,
            teachers=teachers,
            teacher_values=teacher_values,
            method=method,
            rtol=rtol,
            atol=atol,
            closure_tolerance=closure_tolerance,
        )
        short_frames[label] = frame
        short_metrics.append(metrics)
    metrics_by_label = {str(row["candidate"]): row for row in short_metrics}
    revert_metrics = metrics_by_label[REVERT_LABEL]
    assessments: list[dict[str, Any]] = []
    for scale in QSS_SCALES:
        label = _label(scale)
        row = metrics_by_label[label]
        guards = _short_guards(
            row=row,
            revert=revert_metrics,
            initial_balance=initial_balances[label],
            b23pg_locked_value=locked_b23pg,
            closure_tolerance=closure_tolerance,
        )
        assessments.append(
            {
                "candidate": label,
                "scale": float(scale),
                "ATP_nrmse": float(row["ATP_nrmse"]),
                "B23PG_nrmse": float(row["B23PG_nrmse"]),
                "short_guards": guards,
                "short_guard_pass": bool(all(guards.values())),
            }
        )
    selected = _select_short_candidate(assessments)
    long_frames: dict[str, pd.DataFrame] = {}
    long_metrics: dict[str, dict[str, Any]] = {}
    long_assessment: dict[str, Any] | None = None
    if selected is not None:
        long_time = np.linspace(1.0, 10.0, int(long_timepoints))
        for label in (REVERT_LABEL, selected):
            print(f"[b13pg-init] J1-J10 replay {label}", flush=True)
            frame, metrics = _replay(
                label=label,
                state=states[label],
                params=params,
                t_eval=long_time,
                teachers=teachers,
                teacher_values=teacher_values,
                method=method,
                rtol=rtol,
                atol=atol,
                closure_tolerance=closure_tolerance,
            )
            long_frames[label] = frame
            long_metrics[label] = metrics
        long_guards = _long_guards(
            row=long_metrics[selected],
            revert=long_metrics[REVERT_LABEL],
        )
        long_assessment = {
            "candidate": selected,
            "long_guards": long_guards,
            "sustainable_ATP_pass": bool(all(long_guards.values())),
        }

    if selected is None:
        qss_short = metrics_by_label[QSS_LABEL]
        b23pg_ratio = float(qss_short["B23PG_nrmse"]) / max(
            float(revert_metrics["B23PG_nrmse"]), 1e-30
        )
        atp_ratio = float(qss_short["ATP_nrmse"]) / max(
            float(revert_metrics["ATP_nrmse"]), 1e-30
        )
        pulse_reduction = 1.0 - float(
            qss_short["stock_supported_drainage_mM"]
        ) / max(float(revert_metrics["stock_supported_drainage_mM"]), 1e-30)
        decision = "reject B13PG-only initialization as a guarded replacement"
        rationale = (
            "The unique exact J1 root removes "
            f"{100.0 * pulse_reduction:.2f}% of stock-supported drainage, but B23PG "
            f"nRMSE worsens {b23pg_ratio:.2f}-fold and ATP nRMSE worsens "
            f"{atp_ratio:.2f}-fold. At fixed kinetics, the duplicated B13PG stock "
            "artificially supports both the early VPGK ATP pulse and VDPGM supply to "
            "measured B23PG. A B13PG-only replacement cannot preserve both balances."
        )
        next_step = (
            "audit the exact B23PG balance VDPGM - V23DPGP in the J1 quasi-steady "
            "B13PG context before changing either initialization or kinetics"
        )
        long_statement = (
            "No candidate qualified for J1-J10 transfer because the unique exact "
            "J1 root failed the B23PG trajectory guard."
        )
    elif long_assessment is not None and long_assessment["sustainable_ATP_pass"]:
        decision = "retain the J1 quasi-steady B13PG initialization as a guarded diagnostic candidate"
        rationale = (
            "The B13PG-only root removes the duplicated-stock VPGK pulse while preserving "
            "B23PG and ATP consistency through J1-J10. It remains diagnostic until full-panel guards pass."
        )
        next_step = "run the full Brodbar concentration and extracellular flux guards before promotion"
        long_statement = "The selected root passed every J1-J10 ATP and B23PG guard."
    else:
        selected_long = long_metrics[selected]
        decision = "retain B13PG quasi-steady initialization as structural diagnostic only"
        rationale = (
            "The exact J1 root removes the non-independent VPGK pulse and preserves the "
            "locked B23PG initial state, but ATP still falls below 0.01 mM on day "
            f"{selected_long['ATP_below_0.01_mM_day']:.3f}. The early ATP support was therefore "
            "an initialization artifact, while the sustained fixed-kinetic energy deficit remains."
        )
        next_step = (
            "audit ATP production-demand immediately after J1 in the quasi-steady B13PG context, "
            "without promoting B13PG(0) or opening kinetic parameters"
        )
        long_statement = (
            f"The selected root reached ATP < 0.01 mM on day "
            f"`{selected_long['ATP_below_0.01_mM_day']:.4f}` and failed the sustainability gate."
        )

    pd.DataFrame(short_metrics).to_csv(out_dir / "short_screen_metrics.csv", index=False)
    pd.DataFrame(assessments).to_csv(out_dir / "short_screen_assessments.csv", index=False)
    pd.concat(short_frames.values(), ignore_index=True).to_csv(
        out_dir / "short_screen_timeseries.csv", index=False
    )
    if long_frames:
        pd.concat(long_frames.values(), ignore_index=True).to_csv(
            out_dir / "long_transfer_timeseries.csv", index=False
        )
    initialization_artifact = {
        "diagnostic_only": True,
        "promoted": False,
        "changed_initial_states": ["B13PG"],
        "locked_initial_states": {"B23PG": locked_b23pg},
        "revert": {"B13PG": duplicated_b13pg},
        "selected_short_candidate": selected,
        "candidates": {
            label: {"B13PG": value, "B23PG": locked_b23pg}
            for label, value in values.items()
        },
    }
    (out_dir / "diagnostic_initializations.json").write_text(
        json.dumps(_jsonable(initialization_artifact), indent=2), encoding="utf-8"
    )
    _plot(
        short_frames=short_frames,
        short_metrics=short_metrics,
        long_frames=long_frames,
        selected=selected,
        qss_value=qss_value,
        duplicated_value=duplicated_b13pg,
        out_path=out_dir / "b13pg_initialization_screen.png",
    )
    summary = {
        "contract_type": "fixed_kinetic_b13pg_only_initialization_screen",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "kinetic_optimization_performed": False,
        "parameters_promoted": False,
        "initial_conditions_promoted": False,
        "source_refinement_dir": str(refinement_dir),
        "seed_params_path": str(seed_params_path),
        "fixed_kinetic_context": {"vmax_V6PGD": float(params["vmax_V6PGD"])},
        "changed_kinetic_constants": [],
        "changed_initial_states": ["B13PG"],
        "locked_initial_states": {"B23PG": locked_b23pg},
        "duplicated_B13PG_initial_mM": duplicated_b13pg,
        "qss_B13PG_initial_mM": qss_value,
        "qss_to_duplicated_ratio": qss_value / duplicated_b13pg,
        "qss_initial_balance": initial_balances[QSS_LABEL],
        "initial_balance_by_candidate": initial_balances,
        "short_horizon_days": [1.0, 3.0],
        "long_horizon_days": [1.0, 10.0] if long_frames else None,
        "short_metrics": short_metrics,
        "short_assessments": assessments,
        "selected_short_candidate": selected,
        "long_metrics": long_metrics,
        "long_assessment": long_assessment,
        "long_horizon_statement": long_statement,
        "decision": decision,
        "decision_rationale": rationale,
        "next_step": next_step,
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "report": str(out_dir / "decision_report.md"),
            "diagnostic_initializations": str(out_dir / "diagnostic_initializations.json"),
            "short_metrics": str(out_dir / "short_screen_metrics.csv"),
            "short_assessments": str(out_dir / "short_screen_assessments.csv"),
            "short_timeseries": str(out_dir / "short_screen_timeseries.csv"),
            "long_timeseries": str(out_dir / "long_transfer_timeseries.csv") if long_frames else None,
            "plot": str(out_dir / "b13pg_initialization_screen.png"),
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
                "selected_short_candidate": selected,
                "decision": decision,
                "next_step": next_step,
            },
            indent=2,
        ),
        flush=True,
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Screen B13PG(0) alone at fixed kinetics with B23PG locked"
    )
    parser.add_argument("--refinement-dir", type=Path, default=DEFAULT_REFINEMENT_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--short-timepoints", type=int, default=401)
    parser.add_argument("--long-timepoints", type=int, default=1801)
    parser.add_argument("--method", default="BDF")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    parser.add_argument("--closure-tolerance", type=float, default=1e-12)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_screen(
        refinement_dir=args.refinement_dir,
        out_dir=args.out_dir,
        short_timepoints=args.short_timepoints,
        long_timepoints=args.long_timepoints,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
        closure_tolerance=args.closure_tolerance,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
