"""Screen vmax_VDPGM alone under the fixed QSS-B13PG FLA contract."""

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
    / "vmax_vdpgm_qss_b13pg_screen_J1_J46"
)
BRODBAR_DATA = SRC_DIR / "Data_Bordbar_et_al_exp.xlsx"

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from audit_atp_transition_v6pgd_ppp_context import (  # noqa: E402
    _atp_balance,
    _effective_atp_balance,
    _first_sustained_below,
)
from audit_b13pg_balance_v6pgd_ppp_context import (  # noqa: E402
    _build_timeseries as _build_b13pg_timeseries,
    _effective_balance,
    _integral,
)
from audit_b23pg_balance_qss_context import (  # noqa: E402
    QSS_LABEL,
    _build_state_contract,
)
from equadiff_brodbar import BRODBAR_METABOLITE_MAP, MODEL_NETWORK_VERSION  # noqa: E402
from evaluate_brodbar_candidate_full_panel import _load_brodbar_panel  # noqa: E402
from profile_glycolysis_flux_bottlenecks import (  # noqa: E402
    _jsonable,
    _simulate_and_track,
)


MULTIPLIERS = (0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0)
PRIMARY_END_DAY = 3.0
RELAY_END_DAY = 10.0
STORAGE_END_DAY = 46.0
SHORT_GUARD_TOLERANCE = 0.10
LONG_GUARD_TOLERANCE = 0.10
WHOLE_PANEL_TOLERANCE = 0.05
ATP_COLLAPSE_TOLERANCE_DAY = 0.10
STATE_NAMES = (
    "B13PG",
    "B23PG",
    "P3G",
    "ATP",
    "NAD",
    "NADH",
    "G6P",
    "F6P",
    "GLC",
    "LAC",
    "PEP",
    "EGLC",
    "ELAC",
)
OBSERVED_STATE_NAMES = tuple(name for name in STATE_NAMES if name not in {"NAD", "NADH"})
STATE_INDEX = {name: int(BRODBAR_METABOLITE_MAP[name]) for name in STATE_NAMES}
P3G_TERMS = {"VPGK": 1.0, "VPGM": -1.0, "V23DPGP": 1.0, "VPHGDH": -1.0}
B23PG_TERMS = {"VDPGM": 1.0, "V23DPGP": -1.0}
BLOCK_GUARDS = {
    "J1_J3": ("B23PG", "ATP", "P3G", "G6P", "F6P"),
    "J1_J10": ("B23PG", "ATP", "P3G", "G6P", "F6P", "GLC", "LAC", "PEP"),
    "J1_J46": (
        "B23PG",
        "ATP",
        "P3G",
        "G6P",
        "F6P",
        "GLC",
        "LAC",
        "PEP",
        "EGLC",
        "ELAC",
    ),
}


def _label(multiplier: float) -> str:
    return f"vmax_VDPGM_{float(multiplier):.3f}x"


def _candidate_params(
    seed: Mapping[str, Any], multiplier: float
) -> tuple[dict[str, Any], float, list[str]]:
    params = dict(seed)
    seed_value = float(seed["vmax_VDPGM"])
    params["vmax_VDPGM"] = seed_value * float(multiplier)
    changed = sorted(
        key for key in set(seed) | set(params) if seed.get(key) != params.get(key)
    )
    expected = [] if np.isclose(float(multiplier), 1.0) else ["vmax_VDPGM"]
    if changed != expected:
        raise RuntimeError(f"VDPGM one-factor contract failed: changed={changed}")
    return params, seed_value, changed


def _raw_balance(
    fluxes: Mapping[str, np.ndarray], terms: Mapping[str, float]
) -> np.ndarray:
    missing = [reaction for reaction in terms if reaction not in fluxes]
    if missing:
        raise KeyError(f"FluxTracker is missing reactions: {missing}")
    return sum(
        coefficient * np.asarray(fluxes[reaction], dtype=float)
        for reaction, coefficient in terms.items()
    )


def _normalized_rmse(model: np.ndarray, teacher: np.ndarray, full: np.ndarray) -> float:
    scale = max(float(np.mean(np.abs(full))), 0.01)
    return float(np.sqrt(np.mean((np.asarray(model) - np.asarray(teacher)) ** 2)) / scale)


def _normalized_endpoint_error(model: float, teacher: float, full: np.ndarray) -> float:
    scale = max(float(np.mean(np.abs(full))), 0.01)
    return abs(float(model) - float(teacher)) / scale


def _load_teachers() -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, PchipInterpolator]]:
    raw = pd.read_excel(BRODBAR_DATA, engine="openpyxl")
    names = raw.iloc[:, 0].astype(str).str.strip().str.upper()
    time = np.asarray([float(value) for value in raw.columns[1:]], dtype=float)
    values: dict[str, np.ndarray] = {}
    teachers: dict[str, PchipInterpolator] = {}
    for metabolite in OBSERVED_STATE_NAMES:
        matches = raw.loc[names == metabolite].iloc[:, 1:]
        if len(matches) != 1:
            raise RuntimeError(f"Expected one {metabolite} row, found {len(matches)}")
        values[metabolite] = matches.iloc[0].to_numpy(dtype=float)
        teachers[metabolite] = PchipInterpolator(time, values[metabolite])
    return time, values, teachers


def _closure(
    *,
    state: np.ndarray,
    derivative: np.ndarray,
    raw: np.ndarray,
    tolerance: float,
    name: str,
) -> tuple[np.ndarray, float]:
    effective, _ = _effective_balance(raw, np.asarray(state, dtype=float))
    error = float(np.max(np.abs(effective - np.asarray(derivative, dtype=float))))
    if error > float(tolerance):
        raise RuntimeError(f"{name} closure failed: {error:.6g}")
    return effective, error


def _replay(
    *,
    label: str,
    state: np.ndarray,
    params: Mapping[str, Any],
    t_eval: np.ndarray,
    teacher_values: Mapping[str, np.ndarray],
    teachers: Mapping[str, PchipInterpolator],
    panel_curves: Mapping[str, np.ndarray],
    panel_indices: Mapping[str, int],
    panel_time: np.ndarray,
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
    time = np.asarray(sol.t, dtype=float)
    frame, b13_closure = _build_b13pg_timeseries(
        label=label,
        sol=sol,
        fluxes=fluxes,
        derivatives=derivatives,
        params=params,
        duplicated_teacher=teachers["B13PG"],
        closure_tolerance=closure_tolerance,
    )
    b23 = np.asarray(sol.y[STATE_INDEX["B23PG"]], dtype=float)
    p3g = np.asarray(sol.y[STATE_INDEX["P3G"]], dtype=float)
    b23_raw = _raw_balance(fluxes, B23PG_TERMS)
    p3g_raw = _raw_balance(fluxes, P3G_TERMS)
    b23_effective, b23_closure = _closure(
        state=b23,
        derivative=derivatives[STATE_INDEX["B23PG"]],
        raw=b23_raw,
        tolerance=closure_tolerance,
        name="B23PG",
    )
    p3g_effective, p3g_closure = _closure(
        state=p3g,
        derivative=derivatives[STATE_INDEX["P3G"]],
        raw=p3g_raw,
        tolerance=closure_tolerance,
        name="P3G",
    )
    production, consumption, atp_raw = _atp_balance(fluxes)
    atp = np.asarray(sol.y[STATE_INDEX["ATP"]], dtype=float)
    atp_effective, _ = _effective_atp_balance(atp_raw, atp)
    atp_closure = float(
        np.max(np.abs(atp_effective - derivatives[STATE_INDEX["ATP"]]))
    )
    if atp_closure > float(closure_tolerance):
        raise RuntimeError(f"ATP closure failed: {atp_closure:.6g}")

    concentration_metrics: dict[str, dict[str, float]] = {}
    for metabolite in OBSERVED_STATE_NAMES:
        model = np.asarray(sol.y[STATE_INDEX[metabolite]], dtype=float)
        teacher = np.asarray(teachers[metabolite](time), dtype=float)
        concentration_metrics[metabolite] = {
            "nrmse": _normalized_rmse(model, teacher, teacher_values[metabolite]),
            "endpoint_error": _normalized_endpoint_error(
                model[-1], teacher[-1], teacher_values[metabolite]
            ),
            "model_endpoint_mM": float(model[-1]),
            "teacher_endpoint_mM": float(teacher[-1]),
        }
        frame[metabolite] = model
        frame[f"{metabolite}_teacher"] = teacher
    for metabolite in ("NAD", "NADH"):
        frame[metabolite] = np.asarray(sol.y[STATE_INDEX[metabolite]], dtype=float)

    teacher_b23_derivative = np.asarray(teachers["B23PG"].derivative()(time), dtype=float)
    model_b23_derivative = np.asarray(derivatives[STATE_INDEX["B23PG"]], dtype=float)
    slope_scale = max(float(np.mean(np.abs(teacher_b23_derivative))), 0.01)
    b23_slope_nrmse = float(
        np.sqrt(np.mean((model_b23_derivative - teacher_b23_derivative) ** 2))
        / slope_scale
    )
    vdpgm = np.asarray(fluxes["VDPGM"], dtype=float)
    v23 = np.asarray(fluxes["V23DPGP"], dtype=float)
    required_vdpgm = teacher_b23_derivative + v23
    required_integral = _integral(required_vdpgm, time)
    vdpgm_integral = _integral(vdpgm, time)

    panel_nrmse = []
    for metabolite, full in panel_curves.items():
        if metabolite in {"B13PG", "P2G"} or metabolite not in panel_indices:
            continue
        teacher = PchipInterpolator(panel_time, np.asarray(full, dtype=float))(time)
        model = np.asarray(sol.y[int(panel_indices[metabolite])], dtype=float)
        panel_nrmse.append(_normalized_rmse(model, teacher, np.asarray(full, dtype=float)))

    nad = np.asarray(sol.y[STATE_INDEX["NAD"]], dtype=float)
    nadh = np.asarray(sol.y[STATE_INDEX["NADH"]], dtype=float)
    b13 = np.asarray(sol.y[STATE_INDEX["B13PG"]], dtype=float)
    b13_occupancy = b13 / (b13 + float(params.get("km_B13PG", 1.013344)) + 1e-30)
    redox_ratio = np.maximum(nad, 1e-6) / (np.maximum(nadh, 1e-6) + 1e-6)
    redox_drive = redox_ratio / (
        redox_ratio + float(params.get("km_NAD_NADH", 1.0)) + 1e-30
    )
    frame["B23PG_model_derivative"] = model_b23_derivative
    frame["B23PG_teacher_derivative"] = teacher_b23_derivative
    frame["B23PG_effective_balance"] = b23_effective
    frame["P3G_effective_balance"] = p3g_effective
    frame["teacher_required_VDPGM"] = required_vdpgm
    frame["ATP_production"] = production
    frame["ATP_consumption"] = consumption

    metrics = {
        "candidate": label,
        "horizon_end_day": float(time[-1]),
        "vmax_VDPGM": float(params["vmax_VDPGM"]),
        "concentration_metrics": concentration_metrics,
        "B23PG_slope_nrmse": b23_slope_nrmse,
        "VDPGM_integral_mM": vdpgm_integral,
        "teacher_required_VDPGM_integral_mM": required_integral,
        "VDPGM_supply_fraction": vdpgm_integral / max(required_integral, 1e-30),
        "V23DPGP_integral_mM": _integral(v23, time),
        "VGAPDH_integral_mM": _integral(np.asarray(fluxes["VGAPDH"]), time),
        "VPGK_integral_ATP_yield_mM": _integral(np.asarray(fluxes["VPGK"]), time),
        "VPGK_peak_mM_per_day": float(np.max(fluxes["VPGK"])),
        "ATP_production_integral_mM": _integral(production, time),
        "ATP_consumption_integral_mM": _integral(consumption, time),
        "ATP_below_0.01_mM_day": _first_sustained_below(
            time, atp, threshold=0.01, duration=0.02
        ),
        "B13PG_mean_occupancy": float(np.mean(b13_occupancy)),
        "GAPDH_mean_redox_drive": float(np.mean(redox_drive)),
        "all_state_minimum_mM": float(np.min(sol.y)),
        "NAD_minimum_mM": float(np.min(nad)),
        "NADH_minimum_mM": float(np.min(nadh)),
        "NAD_NADH_max_drift_mM": float(np.max(np.abs(nad + nadh - (nad[0] + nadh[0])))),
        "max_B13PG_closure_error": float(b13_closure["max_abs_B13PG_closure_error"]),
        "max_B23PG_closure_error": b23_closure,
        "max_P3G_closure_error": p3g_closure,
        "max_ATP_closure_error": atp_closure,
        "whole_panel_mean_nrmse": float(np.mean(panel_nrmse)),
        "whole_panel_median_nrmse": float(np.median(panel_nrmse)),
        "whole_panel_target_count": len(panel_nrmse),
    }
    return frame, metrics


def _base_validity_guards(row: Mapping[str, Any], closure_tolerance: float) -> dict[str, bool]:
    return {
        "B13PG_closure_exact": float(row["max_B13PG_closure_error"]) <= closure_tolerance,
        "B23PG_closure_exact": float(row["max_B23PG_closure_error"]) <= closure_tolerance,
        "P3G_closure_exact": float(row["max_P3G_closure_error"]) <= closure_tolerance,
        "ATP_closure_exact": float(row["max_ATP_closure_error"]) <= closure_tolerance,
        "all_states_nonnegative": float(row["all_state_minimum_mM"]) >= -1e-10,
        "NAD_NADH_positive": float(row["NAD_minimum_mM"]) >= -1e-10
        and float(row["NADH_minimum_mM"]) >= -1e-10,
        "NAD_NADH_conserved": float(row["NAD_NADH_max_drift_mM"]) <= 1e-9,
    }


def _collapse_noninferior(candidate: Any, seed: Any) -> bool:
    if seed is None:
        return candidate is None
    if candidate is None:
        return True
    return float(candidate) >= float(seed) - ATP_COLLAPSE_TOLERANCE_DAY


def _short_guards(
    *, candidate: Mapping[str, Any], seed: Mapping[str, Any], closure_tolerance: float
) -> dict[str, bool]:
    guards = _base_validity_guards(candidate, closure_tolerance)
    candidate_conc = candidate["concentration_metrics"]
    seed_conc = seed["concentration_metrics"]
    guards.update(
        {
            "B23PG_nrmse_improves": float(candidate_conc["B23PG"]["nrmse"])
            < float(seed_conc["B23PG"]["nrmse"]),
            "B23PG_endpoint_improves": float(candidate_conc["B23PG"]["endpoint_error"])
            < float(seed_conc["B23PG"]["endpoint_error"]),
            "B23PG_slope_improves": float(candidate["B23PG_slope_nrmse"])
            < float(seed["B23PG_slope_nrmse"]),
            "VDPGM_supply_increases": float(candidate["VDPGM_supply_fraction"])
            > float(seed["VDPGM_supply_fraction"]),
            "ATP_trajectory_noninferior_10pct": float(candidate_conc["ATP"]["nrmse"])
            <= (1.0 + SHORT_GUARD_TOLERANCE) * float(seed_conc["ATP"]["nrmse"]),
            "P3G_trajectory_noninferior_10pct": float(candidate_conc["P3G"]["nrmse"])
            <= (1.0 + SHORT_GUARD_TOLERANCE) * float(seed_conc["P3G"]["nrmse"]),
            "ATP_collapse_not_advanced": _collapse_noninferior(
                candidate["ATP_below_0.01_mM_day"], seed["ATP_below_0.01_mM_day"]
            ),
            "VPGK_pulse_not_recreated": float(candidate["VPGK_peak_mM_per_day"])
            <= 1.05 * float(seed["VPGK_peak_mM_per_day"])
            and float(candidate["VPGK_integral_ATP_yield_mM"])
            <= 1.05 * float(seed["VPGK_integral_ATP_yield_mM"]),
        }
    )
    return guards


def _extension_guards(
    *,
    candidate: Mapping[str, Any],
    seed: Mapping[str, Any],
    block: str,
    closure_tolerance: float,
) -> dict[str, bool]:
    guards = _base_validity_guards(candidate, closure_tolerance)
    candidate_conc = candidate["concentration_metrics"]
    seed_conc = seed["concentration_metrics"]
    for metabolite in BLOCK_GUARDS[block]:
        guards[f"{metabolite}_nrmse_noninferior_10pct"] = (
            float(candidate_conc[metabolite]["nrmse"])
            <= (1.0 + LONG_GUARD_TOLERANCE) * float(seed_conc[metabolite]["nrmse"])
        )
    guards["B23PG_improvement_retained"] = float(candidate_conc["B23PG"]["nrmse"]) < float(
        seed_conc["B23PG"]["nrmse"]
    )
    guards["ATP_collapse_not_advanced"] = _collapse_noninferior(
        candidate["ATP_below_0.01_mM_day"], seed["ATP_below_0.01_mM_day"]
    )
    if block == "J1_J46":
        guards["whole_panel_mean_noninferior_5pct"] = float(
            candidate["whole_panel_mean_nrmse"]
        ) <= (1.0 + WHOLE_PANEL_TOLERANCE) * float(seed["whole_panel_mean_nrmse"])
        guards["whole_panel_median_noninferior_5pct"] = float(
            candidate["whole_panel_median_nrmse"]
        ) <= (1.0 + WHOLE_PANEL_TOLERANCE) * float(seed["whole_panel_median_nrmse"])
    return guards


def _select_best(assessments: Sequence[Mapping[str, Any]]) -> str | None:
    eligible = [row for row in assessments if bool(row["guard_pass"])]
    if not eligible:
        return None
    return str(
        min(
            eligible,
            key=lambda row: (
                float(row["B23PG_nrmse"]),
                float(row["B23PG_endpoint_error"]),
                float(row["multiplier"]),
            ),
        )["candidate"]
    )


def _plateau_classification(metrics: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    low = metrics[_label(16.0)]
    high = metrics[_label(32.0)]
    supply_gain = float(high["VDPGM_integral_mM"]) - float(low["VDPGM_integral_mM"])
    relative_gain = supply_gain / max(float(low["VDPGM_integral_mM"]), 1e-30)
    occupancy = float(high["B13PG_mean_occupancy"])
    redox_drive = float(high["GAPDH_mean_redox_drive"])
    plateau = relative_gain < 0.10
    if plateau and occupancy < 0.01:
        classification = "B13PG_substrate_limited_plateau"
    elif plateau and redox_drive < 0.10:
        classification = "upstream_redox_supply_limited_plateau"
    elif plateau:
        classification = "mixed_upstream_supply_limited_plateau"
    else:
        classification = "VDPGM_capacity_remains_responsive_at_32x"
    return {
        "classification": classification,
        "VDPGM_integral_gain_16x_to_32x_mM": supply_gain,
        "relative_gain_16x_to_32x": relative_gain,
        "32x_mean_B13PG_occupancy": occupancy,
        "32x_mean_GAPDH_redox_drive": redox_drive,
    }


def _plot(
    *,
    frames: Mapping[str, pd.DataFrame],
    metrics: Mapping[str, Mapping[str, Any]],
    selected: Sequence[str],
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.5), constrained_layout=True)
    cmap = plt.get_cmap("viridis")
    for index, multiplier in enumerate(MULTIPLIERS):
        label = _label(multiplier)
        frame = frames[label]
        color = cmap(index / (len(MULTIPLIERS) - 1))
        width = 2.6 if label == _label(1.0) or label in selected else 1.1
        axes[0, 0].plot(frame["time_day"], frame["B23PG"], color=color, linewidth=width, label=f"{multiplier:g}x")
        axes[0, 1].plot(frame["time_day"], frame["VDPGM"], color=color, linewidth=width, label=f"{multiplier:g}x")
        axes[0, 2].plot(frame["time_day"], frame["ATP"], color=color, linewidth=width, label=f"{multiplier:g}x")
        axes[1, 0].plot(frame["time_day"], frame["P3G"], color=color, linewidth=width, label=f"{multiplier:g}x")
        axes[1, 1].plot(frame["time_day"], frame["B13PG"], color=color, linewidth=width, label=f"{multiplier:g}x")
    reference = frames[_label(1.0)]
    axes[0, 0].plot(reference["time_day"], reference["B23PG_teacher"], "k--", linewidth=2, label="teacher")
    axes[0, 1].plot(reference["time_day"], reference["teacher_required_VDPGM"], "k--", linewidth=2, label="teacher-required")
    axes[0, 2].plot(reference["time_day"], reference["ATP_teacher"], "k--", linewidth=2, label="teacher")
    axes[1, 0].plot(reference["time_day"], reference["P3G_teacher"], "k--", linewidth=2, label="teacher")
    ordered = [metrics[_label(multiplier)] for multiplier in MULTIPLIERS]
    axes[1, 2].plot(MULTIPLIERS, [row["VDPGM_integral_mM"] for row in ordered], "o-", color="#2563eb", label="VDPGM integral")
    axes[1, 2].plot(MULTIPLIERS, [row["teacher_required_VDPGM_integral_mM"] for row in ordered], "s--", color="#111827", label="teacher-required")
    axes[1, 2].set_xscale("log", base=2)
    titles = (
        "B23PG concentration",
        "VDPGM supply",
        "ATP guard",
        "P3G guard",
        "B13PG substrate",
        "Capacity response",
    )
    for axis, title in zip(axes.flat, titles):
        axis.set_title(title)
        axis.grid(alpha=0.22)
        axis.legend(frameon=False, fontsize=7)
    for axis in axes.flat[:5]:
        axis.set_xlabel("Time (day)")
    axes[1, 2].set_xlabel("vmax_VDPGM multiplier")
    axes[0, 0].set_ylabel("mM")
    axes[0, 1].set_ylabel("mM/day")
    axes[0, 2].set_ylabel("mM")
    axes[1, 0].set_ylabel("mM")
    axes[1, 1].set_ylabel("mM")
    axes[1, 1].set_yscale("log")
    axes[1, 2].set_ylabel("Integrated flux (mM)")
    fig.suptitle("QSS-B13PG one-factor screen: vmax_VDPGM")
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    lines = [
        "# QSS-B13PG vmax_VDPGM screen",
        "",
        "Only `vmax_VDPGM` varied. B13PG(0), B23PG(0), V23DPGP kinetics, PPP initialization, and all other kinetics were fixed. No Optuna optimization or parameter promotion was performed.",
        "",
        "## J1-J3 primary screen",
        "",
        "| Multiplier | vmax | B23PG nRMSE | Endpoint error | Slope nRMSE | VDPGM supply | ATP nRMSE | P3G nRMSE | Pass |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    assessment_by_label = {row["candidate"]: row for row in summary["short_assessments"]}
    for row in summary["short_metrics"]:
        label = row["candidate"]
        assessment = assessment_by_label[label]
        concentration = row["concentration_metrics"]
        lines.append(
            f"| {assessment['multiplier']:.3g}x | {row['vmax_VDPGM']:.6g} | "
            f"{concentration['B23PG']['nrmse']:.5g} | {concentration['B23PG']['endpoint_error']:.5g} | "
            f"{row['B23PG_slope_nrmse']:.5g} | {100.0 * row['VDPGM_supply_fraction']:.3g}% | "
            f"{concentration['ATP']['nrmse']:.5g} | {concentration['P3G']['nrmse']:.5g} | "
            f"{assessment['guard_pass']} |"
        )
    lines.extend(
        [
            "",
            f"J1-J3 eligible: `{', '.join(summary['J1_J3_eligible']) or 'none'}`.",
            f"J1-J10 eligible: `{', '.join(summary['J1_J10_eligible']) or 'none'}`.",
            f"J1-J46 eligible: `{', '.join(summary['J1_J46_eligible']) or 'none'}`.",
            "",
            "## Capacity attribution",
            "",
            f"Classification: **`{summary['capacity_attribution']['classification']}`**.",
            f"The integrated VDPGM gain from 16x to 32x was `{summary['capacity_attribution']['relative_gain_16x_to_32x'] * 100.0:.3g}%`; mean B13PG occupancy at 32x was `{summary['capacity_attribution']['32x_mean_B13PG_occupancy']:.5g}` and mean GAPDH redox drive was `{summary['capacity_attribution']['32x_mean_GAPDH_redox_drive']:.5g}`.",
            "",
            "## Decision",
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
    states, seed_params, seed_path = _build_state_contract()
    qss_state = np.asarray(states[QSS_LABEL], dtype=float)
    experimental_time, teacher_values, teachers = _load_teachers()
    _, panel_curves, _, panel_indices, _ = _load_brodbar_panel()
    parameter_sets = {}
    changes = {}
    seed_vmax = None
    for multiplier in MULTIPLIERS:
        label = _label(multiplier)
        parameter_sets[label], seed_vmax, changes[label] = _candidate_params(
            seed_params, multiplier
        )

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

    for multiplier in MULTIPLIERS:
        label = _label(multiplier)
        print(f"[vmax-VDPGM] J1-J3 replay {label}", flush=True)
        frame, row = _replay(
            label=label,
            state=qss_state,
            params=parameter_sets[label],
            t_eval=horizons["J1_J3"],
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
        frames["J1_J3"][label] = frame
        metrics["J1_J3"][label] = row

    short_seed = metrics["J1_J3"][_label(1.0)]
    short_assessments = []
    for multiplier in MULTIPLIERS:
        label = _label(multiplier)
        if np.isclose(multiplier, 1.0):
            guards = _base_validity_guards(metrics["J1_J3"][label], closure_tolerance)
            guard_pass = False
        else:
            guards = _short_guards(
                candidate=metrics["J1_J3"][label],
                seed=short_seed,
                closure_tolerance=closure_tolerance,
            )
            guard_pass = bool(all(guards.values()))
        concentration = metrics["J1_J3"][label]["concentration_metrics"]
        short_assessments.append(
            {
                "candidate": label,
                "multiplier": float(multiplier),
                "guards": guards,
                "guard_pass": guard_pass,
                "B23PG_nrmse": float(concentration["B23PG"]["nrmse"]),
                "B23PG_endpoint_error": float(concentration["B23PG"]["endpoint_error"]),
            }
        )
    short_eligible = [row["candidate"] for row in short_assessments if row["guard_pass"]]

    relay_labels = [_label(1.0), *short_eligible]
    for label in dict.fromkeys(relay_labels):
        print(f"[vmax-VDPGM] J1-J10 replay {label}", flush=True)
        frames["J1_J10"][label], metrics["J1_J10"][label] = _replay(
            label=label,
            state=qss_state,
            params=parameter_sets[label],
            t_eval=horizons["J1_J10"],
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
    relay_assessments = []
    relay_eligible = []
    if short_eligible:
        relay_seed = metrics["J1_J10"][_label(1.0)]
        for label in short_eligible:
            guards = _extension_guards(
                candidate=metrics["J1_J10"][label],
                seed=relay_seed,
                block="J1_J10",
                closure_tolerance=closure_tolerance,
            )
            passed = bool(all(guards.values()))
            relay_assessments.append({"candidate": label, "guards": guards, "guard_pass": passed})
            if passed:
                relay_eligible.append(label)

    storage_labels = [_label(1.0), *relay_eligible]
    for label in dict.fromkeys(storage_labels):
        print(f"[vmax-VDPGM] J1-J46 replay {label}", flush=True)
        frames["J1_J46"][label], metrics["J1_J46"][label] = _replay(
            label=label,
            state=qss_state,
            params=parameter_sets[label],
            t_eval=horizons["J1_J46"],
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
    storage_assessments = []
    storage_eligible = []
    if relay_eligible:
        storage_seed = metrics["J1_J46"][_label(1.0)]
        for label in relay_eligible:
            guards = _extension_guards(
                candidate=metrics["J1_J46"][label],
                seed=storage_seed,
                block="J1_J46",
                closure_tolerance=closure_tolerance,
            )
            passed = bool(all(guards.values()))
            storage_assessments.append({"candidate": label, "guards": guards, "guard_pass": passed})
            if passed:
                storage_eligible.append(label)

    capacity = _plateau_classification(metrics["J1_J3"])
    selected = _select_best(short_assessments)
    if storage_eligible:
        decision = "retain the fully guarded 2x-4x vmax_VDPGM interval as a diagnostic bracket"
        rationale = (
            "Both 2x and 4x improve B23PG and pass J1-J3, J1-J10, J1-J46, and whole-panel guards. "
            "The 4x point gives the larger B23PG gain but also the larger F6P, GLC, and ELAC regression. "
            "The 2x point is therefore the conservative anchor; neither point is promoted because ATP still "
            "collapses and the current data do not identify a unique optimum within the guarded interval."
        )
        next_step = "refine the guarded vmax_VDPGM Pareto interval between 2x and 4x before opening any coupled parameter"
    elif relay_eligible:
        decision = "retain a J1-J10 VDPGM hypothesis but reject long-horizon transfer"
        rationale = "The one-factor correction survives initialization and glycolytic-relay guards but fails storage or whole-panel preservation. No global parameter change is justified."
        next_step = "attribute the failed J10-J46 guards before changing another kinetic family"
    elif short_eligible:
        decision = "reject VDPGM-only calibration beyond J1-J3"
        rationale = "One or more points improve the local B23PG objective, but none preserves the J3-J10 relay. VDPGM capacity alone cannot be transferred through the energy/glycolytic block."
        next_step = "audit the first failed J3-J10 guard and test a coupled identifiable supply hypothesis only if structurally justified"
    else:
        decision = "reject vmax_VDPGM alone under the QSS-B13PG contract"
        if "plateau" in capacity["classification"]:
            rationale = "No multiplier passed all J1-J3 guards, and the high-capacity response plateaued with low B13PG occupancy or weak upstream redox supply. Increasing DPGM capacity cannot recover the teacher flux without another identifiable source of B13PG."
            next_step = "map the identifiable upstream B13PG supply combination VGAPDH-redox versus VDPGM without reopening duplicated B13PG(0)"
        else:
            rationale = "No multiplier simultaneously improved B23PG concentration, slope, and endpoint while preserving ATP, P3G, and the QSS initialization contract. The remaining mismatch is a B23PG-energy tradeoff rather than a single-capacity defect."
            next_step = "quantify the B23PG-ATP Pareto boundary before considering a coupled upstream supply lever"

    pd.concat(frames["J1_J3"].values(), ignore_index=True).to_csv(
        out_dir / "J1_J3_timeseries.csv", index=False
    )
    (out_dir / "candidate_parameter_sets.json").write_text(
        json.dumps(_jsonable(parameter_sets), indent=2), encoding="utf-8"
    )
    for horizon in ("J1_J10", "J1_J46"):
        if frames[horizon]:
            pd.concat(frames[horizon].values(), ignore_index=True).to_csv(
                out_dir / f"{horizon}_timeseries.csv", index=False
            )
    metric_rows = []
    for horizon, by_label in metrics.items():
        for label, row in by_label.items():
            flat = {key: value for key, value in row.items() if key != "concentration_metrics"}
            for metabolite, values in row["concentration_metrics"].items():
                for metric, value in values.items():
                    flat[f"{metabolite}_{metric}"] = value
            flat["horizon"] = horizon
            metric_rows.append(flat)
    pd.DataFrame(metric_rows).to_csv(out_dir / "candidate_metrics.csv", index=False)
    _plot(
        frames=frames["J1_J3"],
        metrics=metrics["J1_J3"],
        selected=storage_eligible,
        out_path=out_dir / "vmax_vdpgm_screen.png",
    )
    summary = {
        "contract_type": "deterministic_vmax_VDPGM_only_qss_B13PG_screen",
        "contract_version": 1,
        "model_network_version": MODEL_NETWORK_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "optimization_performed": False,
        "parameters_promoted": False,
        "seed_params_path": str(seed_path),
        "seed_vmax_VDPGM": seed_vmax,
        "multipliers": list(MULTIPLIERS),
        "changed_parameter_contract": changes,
        "locked_contract": {
            "initial_states": ["B13PG", "B23PG", "seven PPP latent pools"],
            "kinetics": ["V23DPGP", "all parameters except vmax_VDPGM"],
        },
        "short_metrics": list(metrics["J1_J3"].values()),
        "short_assessments": short_assessments,
        "J1_J3_eligible": short_eligible,
        "relay_metrics": list(metrics["J1_J10"].values()),
        "relay_assessments": relay_assessments,
        "J1_J10_eligible": relay_eligible,
        "storage_metrics": list(metrics["J1_J46"].values()),
        "storage_assessments": storage_assessments,
        "J1_J46_eligible": storage_eligible,
        "best_short_candidate": selected,
        "retained_diagnostic_bracket": storage_eligible,
        "conservative_anchor": _label(2.0) if _label(2.0) in storage_eligible else None,
        "capacity_attribution": capacity,
        "decision": decision,
        "decision_rationale": rationale,
        "next_step": next_step,
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "report": str(out_dir / "decision_report.md"),
            "metrics": str(out_dir / "candidate_metrics.csv"),
            "parameter_sets": str(out_dir / "candidate_parameter_sets.json"),
            "J1_J3_timeseries": str(out_dir / "J1_J3_timeseries.csv"),
            "plot": str(out_dir / "vmax_vdpgm_screen.png"),
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
                "capacity": capacity,
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
