"""Audit the J1-J3 B13PG balance and initialization provenance."""

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
    / "b13pg_balance_v6pgd_0.900_ppp_context_J1_J3"
)
BRODBAR_DATA = SRC_DIR / "Data_Bordbar_et_al_exp.xlsx"
HISTORICAL_INITIAL_CONDITIONS = SRC_DIR / "Initial_conditions_JA_Final.xls"

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from equadiff_brodbar import (  # noqa: E402
    BRODBAR_METABOLITE_MAP,
    MIN_CONCENTRATION,
    NONEG_THRESHOLD,
)
from MM_calibration import EXP_TO_MODEL, load_initial_conditions  # noqa: E402
from profile_glycolysis_flux_bottlenecks import (  # noqa: E402
    _jsonable,
    _load_params,
    _simulate_and_track,
)
from audit_atp_transition_v6pgd_ppp_context import (  # noqa: E402
    BASELINE_LABEL,
    CANDIDATE_LABEL,
    _candidate_params,
    _first_sustained_below,
    _state_with_saved_latent,
)


B13PG_TERMS = {"VGAPDH": 1.0, "VPGK": -1.0, "VDPGM": -1.0}
WINDOWS = (
    ("J1_J1.1", 1.0, 1.1),
    ("J1.1_J1.3", 1.1, 1.3),
    ("J1.3_J1.6", 1.3, 1.6),
    ("J1.6_J2", 1.6, 2.0),
    ("J2_J3", 2.0, 3.0),
)
TRACKED_STATES = (
    "B13PG",
    "B23PG",
    "GA3P",
    "NAD",
    "NADH",
    "ADP",
    "ATP",
    "P3G",
    "G6P",
    "F6P",
    "GLC",
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


def _mm(values: np.ndarray, km: float) -> np.ndarray:
    values = np.maximum(np.asarray(values, dtype=float), 0.0)
    return values / (values + float(km) + 1e-30)


def _provenance_audit(
    data_path: Path = BRODBAR_DATA,
    historical_path: Path = HISTORICAL_INITIAL_CONDITIONS,
) -> dict[str, Any]:
    frame = pd.read_excel(data_path, engine="openpyxl")
    names = frame.iloc[:, 0].astype(str).str.strip().str.upper()
    rows: dict[str, np.ndarray] = {}
    for metabolite in ("B13PG", "B23PG"):
        matches = frame.loc[names == metabolite].iloc[:, 1:]
        if len(matches) != 1:
            raise RuntimeError(f"Expected one {metabolite} row, found {len(matches)}")
        rows[metabolite] = matches.iloc[0].to_numpy(dtype=float)
    difference = rows["B13PG"] - rows["B23PG"]
    historical = pd.read_excel(historical_path, sheet_name=0, header=None)
    historical_names = historical.iloc[:, 0].astype(str).str.strip().str.upper()
    historical_values = {
        metabolite: float(
            historical.loc[historical_names == metabolite].iloc[0, 1]
        )
        for metabolite in ("B13PG", "B23PG")
    }
    return {
        "B13PG_curve_present_in_workbook": True,
        "B23PG_curve_present_in_workbook": True,
        "B13PG_supported_calibration_target": "B13PG" in EXP_TO_MODEL,
        "B23PG_supported_calibration_target": "B23PG" in EXP_TO_MODEL,
        "curves_pointwise_identical": bool(np.allclose(difference, 0.0, rtol=0.0, atol=0.0)),
        "maximum_curve_absolute_difference": float(np.max(np.abs(difference))),
        "B13PG_initial_workbook_mM": float(rows["B13PG"][0]),
        "B23PG_initial_workbook_mM": float(rows["B23PG"][0]),
        "historical_initial_values_mM": historical_values,
        "independent_B13PG_evidence": False
        if np.allclose(difference, 0.0, rtol=0.0, atol=0.0)
        else True,
        "interpretation": (
            "B13PG is initialized from a workbook row duplicated exactly from B23PG, "
            "while only B23PG is exposed as a calibration target. Treat B13PG(0) as "
            "non-independent and potentially latent."
        ),
    }


def _raw_b13pg_balance(fluxes: Mapping[str, np.ndarray]) -> np.ndarray:
    missing = [reaction for reaction in B13PG_TERMS if reaction not in fluxes]
    if missing:
        raise KeyError(f"FluxTracker is missing B13PG reactions: {missing}")
    return sum(
        coefficient * np.asarray(fluxes[reaction], dtype=float)
        for reaction, coefficient in B13PG_TERMS.items()
    )


def _effective_balance(
    raw_net: np.ndarray,
    concentration: np.ndarray,
    *,
    threshold: float = float(NONEG_THRESHOLD),
) -> tuple[np.ndarray, np.ndarray]:
    raw_net = np.asarray(raw_net, dtype=float)
    concentration = np.maximum(
        np.asarray(concentration, dtype=float), float(MIN_CONCENTRATION)
    )
    effective = raw_net.copy()
    mask = (concentration < float(threshold)) & (raw_net < 0.0)
    effective[mask] *= np.maximum(concentration[mask], 0.0) / float(threshold)
    return effective, effective - raw_net


def _param(params: Mapping[str, Any], name: str, default: float) -> float:
    return float(params.get(name, default))


def _build_timeseries(
    *,
    label: str,
    sol: Any,
    fluxes: Mapping[str, np.ndarray],
    derivatives: np.ndarray,
    params: Mapping[str, Any],
    duplicated_teacher: PchipInterpolator,
    closure_tolerance: float,
) -> tuple[pd.DataFrame, dict[str, float]]:
    time = np.asarray(sol.t, dtype=float)
    b13pg = np.asarray(sol.y[STATE_INDICES["B13PG"], :], dtype=float)
    raw_net = _raw_b13pg_balance(fluxes)
    effective_net, damping = _effective_balance(raw_net, b13pg)
    derivative = np.asarray(derivatives[STATE_INDICES["B13PG"], :], dtype=float)
    closure_error = float(np.max(np.abs(effective_net - derivative)))
    if closure_error > float(closure_tolerance):
        raise RuntimeError(f"B13PG closure failed for {label}: {closure_error:.6g}")

    ga3p = np.asarray(sol.y[STATE_INDICES["GA3P"], :], dtype=float)
    nad = np.maximum(np.asarray(sol.y[STATE_INDICES["NAD"], :], dtype=float), 1e-6)
    nadh = np.maximum(np.asarray(sol.y[STATE_INDICES["NADH"], :], dtype=float), 1e-6)
    adp = np.maximum(np.asarray(sol.y[STATE_INDICES["ADP"], :], dtype=float), 1e-6)
    atp = np.maximum(np.asarray(sol.y[STATE_INDICES["ATP"], :], dtype=float), 1e-6)
    gapdh_ga3p = _mm(ga3p, _param(params, "km_GA3P", 0.02))
    nad_nadh_ratio = nad / (nadh + 1e-6)
    gapdh_redox = _mm(nad_nadh_ratio, _param(params, "km_NAD_NADH", 1.0))
    b13pg_occupancy = _mm(b13pg, _param(params, "km_B13PG", 1.013344))
    adp_atp_ratio = adp / (atp + 1e-6)
    pgk_drive = _mm(adp_atp_ratio, _param(params, "km_ADP_ATP", 1.0))
    vgapdh = np.asarray(fluxes["VGAPDH"], dtype=float)
    vpgk = np.asarray(fluxes["VPGK"], dtype=float)
    vdpgm = np.asarray(fluxes["VDPGM"], dtype=float)
    gapdh_denominator = (
        _param(params, "vmax_VGAPDH", 6.389868) * gapdh_ga3p * gapdh_redox
    )
    pgk_denominator = (
        _param(params, "vmax_VPGK", 4.690379) * b13pg_occupancy * pgk_drive
    )
    dpgm_denominator = _param(params, "vmax_VDPGM", 2.5) * b13pg_occupancy
    inferred_gapdh_modulation = np.divide(
        vgapdh,
        gapdh_denominator,
        out=np.full_like(vgapdh, np.nan),
        where=gapdh_denominator > 1e-15,
    )
    inferred_pgk_modulation = np.divide(
        vpgk,
        pgk_denominator,
        out=np.full_like(vpgk, np.nan),
        where=pgk_denominator > 1e-15,
    )
    inferred_dpgm_modulation = np.divide(
        vdpgm,
        dpgm_denominator,
        out=np.full_like(vdpgm, np.nan),
        where=dpgm_denominator > 1e-15,
    )
    total_drainage = vpgk + vdpgm
    frame = pd.DataFrame(
        {
            "candidate": label,
            "time_day": time,
            "VGAPDH": vgapdh,
            "VPGK": vpgk,
            "VDPGM": vdpgm,
            "V23DPGP": np.asarray(fluxes["V23DPGP"], dtype=float),
            "VHK": np.asarray(fluxes["VHK"], dtype=float),
            "B13PG_raw_net_flux": raw_net,
            "B13PG_effective_net_flux": effective_net,
            "B13PG_ode_derivative": derivative,
            "B13PG_damping_adjustment": damping,
            "B13PG_closure_error": effective_net - derivative,
            "duplicated_B13PG_teacher_concentration": np.asarray(
                duplicated_teacher(time), dtype=float
            ),
            "duplicated_B13PG_teacher_flux": np.asarray(
                duplicated_teacher.derivative()(time), dtype=float
            ),
            "VGAPDH_GA3P_occupancy": gapdh_ga3p,
            "VGAPDH_NAD_NADH_drive": gapdh_redox,
            "VPGK_B13PG_occupancy": b13pg_occupancy,
            "VPGK_ADP_ATP_drive": pgk_drive,
            "inferred_GAPDH_modulation": inferred_gapdh_modulation,
            "inferred_PGK_modulation": inferred_pgk_modulation,
            "inferred_DPGM_modulation": inferred_dpgm_modulation,
            "VPGK_drainage_fraction": np.divide(
                vpgk, total_drainage, out=np.zeros_like(vpgk), where=total_drainage > 1e-30
            ),
            "VDPGM_shunt_fraction": np.divide(
                vdpgm, total_drainage, out=np.zeros_like(vdpgm), where=total_drainage > 1e-30
            ),
        }
    )
    for state, index in STATE_INDICES.items():
        frame[state] = np.asarray(sol.y[index, :], dtype=float)
    return frame, {"max_abs_B13PG_closure_error": closure_error}


def _window_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    all_time = frame["time_day"].to_numpy(dtype=float)
    for window, start, end in WINDOWS:
        mask = (all_time >= start - 1e-12) & (all_time <= end + 1e-12)
        time = all_time[mask]
        local = frame.loc[mask]
        input_flux = local["VGAPDH"].to_numpy(dtype=float)
        pgk = local["VPGK"].to_numpy(dtype=float)
        dpgm = local["VDPGM"].to_numpy(dtype=float)
        drainage = pgk + dpgm
        b13pg = local["B13PG"].to_numpy(dtype=float)
        input_integral = _integral(input_flux, time)
        pgk_integral = _integral(pgk, time)
        dpgm_integral = _integral(dpgm, time)
        drainage_integral = pgk_integral + dpgm_integral
        net = local["B13PG_effective_net_flux"].to_numpy(dtype=float)
        rows.append(
            {
                "candidate": str(frame["candidate"].iloc[0]),
                "window": window,
                "start_day": float(time[0]),
                "end_day": float(time[-1]),
                "B13PG_start_mM": float(b13pg[0]),
                "B13PG_end_mM": float(b13pg[-1]),
                "B13PG_change_mM": float(b13pg[-1] - b13pg[0]),
                "VGAPDH_mean": _time_mean(input_flux, time),
                "VPGK_mean": _time_mean(pgk, time),
                "VDPGM_mean": _time_mean(dpgm, time),
                "total_drainage_mean": _time_mean(drainage, time),
                "effective_net_mean": _time_mean(net, time),
                "VGAPDH_integral": input_integral,
                "VPGK_integral_ATP_yield": pgk_integral,
                "VDPGM_integral_shunt": dpgm_integral,
                "total_drainage_integral": drainage_integral,
                "effective_net_integral": _integral(net, time),
                "integral_to_pool_change_error": _integral(net, time)
                - float(b13pg[-1] - b13pg[0]),
                "VGAPDH_replacement_fraction": input_integral
                / max(drainage_integral, 1e-30),
                "VPGK_drainage_fraction": pgk_integral
                / max(drainage_integral, 1e-30),
                "VDPGM_shunt_fraction": dpgm_integral
                / max(drainage_integral, 1e-30),
                "VGAPDH_GA3P_occupancy_mean": _time_mean(
                    local["VGAPDH_GA3P_occupancy"], time
                ),
                "VGAPDH_NAD_NADH_drive_mean": _time_mean(
                    local["VGAPDH_NAD_NADH_drive"], time
                ),
                "VPGK_B13PG_occupancy_mean": _time_mean(
                    local["VPGK_B13PG_occupancy"], time
                ),
                "VPGK_ADP_ATP_drive_mean": _time_mean(
                    local["VPGK_ADP_ATP_drive"], time
                ),
                "inferred_GAPDH_modulation_mean": _time_mean(
                    local["inferred_GAPDH_modulation"], time
                ),
            }
        )
    return rows


def _transition_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    time = frame["time_day"].to_numpy(dtype=float)
    b13pg = frame["B13PG"].to_numpy(dtype=float)
    initial = float(b13pg[0])
    depletion_1pct = _first_sustained_below(
        time, b13pg, threshold=0.01 * initial, duration=0.02
    )
    depletion_threshold = _first_sustained_below(
        time, b13pg, threshold=float(NONEG_THRESHOLD), duration=0.02
    )
    full_input = _integral(frame["VGAPDH"], time)
    full_pgk = _integral(frame["VPGK"], time)
    full_dpgm = _integral(frame["VDPGM"], time)
    full_drainage = full_pgk + full_dpgm
    return {
        "B13PG_initial_mM": initial,
        "B13PG_at_day_1.1_mM": float(np.interp(1.1, time, b13pg)),
        "B13PG_at_day_1.3_mM": float(np.interp(1.3, time, b13pg)),
        "B13PG_at_day_2_mM": float(np.interp(2.0, time, b13pg)),
        "B13PG_at_day_3_mM": float(b13pg[-1]),
        "B13PG_below_1pct_initial_day": depletion_1pct,
        "B13PG_below_native_damping_threshold_day": depletion_threshold,
        "J1_J3_VGAPDH_input_integral": full_input,
        "J1_J3_VPGK_ATP_yield_integral": full_pgk,
        "J1_J3_VDPGM_shunt_integral": full_dpgm,
        "J1_J3_total_drainage_integral": full_drainage,
        "J1_J3_VGAPDH_replacement_fraction": full_input
        / max(full_drainage, 1e-30),
        "J1_J3_VPGK_drainage_fraction": full_pgk
        / max(full_drainage, 1e-30),
        "J1_J3_VDPGM_shunt_fraction": full_dpgm
        / max(full_drainage, 1e-30),
        "J1_J3_pool_change_mM": float(b13pg[-1] - b13pg[0]),
        "J1_J3_effective_net_integral": _integral(
            frame["B13PG_effective_net_flux"], time
        ),
        "initial_factors": {
            key: float(frame[key].iloc[0])
            for key in (
                "VGAPDH_GA3P_occupancy",
                "VGAPDH_NAD_NADH_drive",
                "VPGK_B13PG_occupancy",
                "VPGK_ADP_ATP_drive",
                "inferred_GAPDH_modulation",
                "inferred_PGK_modulation",
                "inferred_DPGM_modulation",
            )
        },
    }


def _classify(
    *, provenance: Mapping[str, Any], metrics: Mapping[str, Any]
) -> dict[str, Any]:
    gates = {
        "B13PG_curve_duplicates_B23PG": bool(provenance["curves_pointwise_identical"]),
        "B13PG_not_a_supported_calibration_target": not bool(
            provenance["B13PG_supported_calibration_target"]
        ),
        "B13PG_stock_depletes_before_day_1.3": metrics[
            "B13PG_below_1pct_initial_day"
        ]
        is not None
        and float(metrics["B13PG_below_1pct_initial_day"]) <= 1.3,
        "VGAPDH_replacement_is_incomplete": float(
            metrics["J1_J3_VGAPDH_replacement_fraction"]
        )
        < 0.95,
        "PGK_is_primary_drainage_route": float(
            metrics["J1_J3_VPGK_drainage_fraction"]
        )
        > 0.50,
    }
    if all(gates.values()):
        classification = (
            "non-independent B13PG initialization creates a transient PGK pulse that GAPDH cannot sustain"
        )
    else:
        classification = "mixed B13PG initialization and kinetic replacement defect"
    return {"classification": classification, "classification_gates": gates}


def _plot(
    *,
    frames: Mapping[str, pd.DataFrame],
    out_path: Path,
) -> None:
    colors = {BASELINE_LABEL: "#64748b", CANDIDATE_LABEL: "#b91c1c"}
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.5), constrained_layout=True)
    for label, frame in frames.items():
        time = frame["time_day"].to_numpy(dtype=float)
        color = colors[label]
        axes[0, 0].plot(time, frame["B13PG"], color=color, label=label)
        axes[0, 1].plot(time, frame["VGAPDH"], color=color, label=f"{label}: VGAPDH")
        axes[0, 1].plot(time, frame["VPGK"], color=color, linestyle="--", label=f"{label}: VPGK")
        axes[0, 1].plot(time, frame["VDPGM"], color=color, linestyle=":", label=f"{label}: VDPGM")
    candidate = frames[CANDIDATE_LABEL]
    time = candidate["time_day"].to_numpy(dtype=float)
    axes[0, 0].plot(
        time,
        candidate["duplicated_B13PG_teacher_concentration"],
        "k--",
        linewidth=2,
        label="duplicated B13PG/B23PG curve",
    )
    axes[0, 2].plot(time, candidate["B13PG_effective_net_flux"], color="#b91c1c", label="model net")
    axes[0, 2].plot(time, candidate["duplicated_B13PG_teacher_flux"], "k--", label="duplicated curve derivative")
    axes[1, 0].plot(time, candidate["VGAPDH_GA3P_occupancy"], label="GA3P occupancy", color="#2563eb")
    axes[1, 0].plot(time, candidate["VGAPDH_NAD_NADH_drive"], label="NAD/NADH drive", color="#0f766e")
    axes[1, 0].plot(time, candidate["VPGK_B13PG_occupancy"], label="B13PG occupancy", color="#7c3aed")
    axes[1, 0].plot(time, candidate["VPGK_ADP_ATP_drive"], label="ADP/ATP drive", color="#dc2626")
    axes[1, 1].plot(time, candidate["VPGK_drainage_fraction"], label="PGK fraction", color="#2563eb")
    axes[1, 1].plot(time, candidate["VDPGM_shunt_fraction"], label="DPGM shunt fraction", color="#7c3aed")
    for state, color in zip(
        ("GA3P", "NAD", "NADH", "ATP", "B23PG", "P3G"),
        ("#2563eb", "#0f766e", "#7c3aed", "#dc2626", "#ea580c", "#4d7c0f"),
    ):
        axes[1, 2].plot(time, candidate[state], label=state, color=color)
    axes[1, 2].set_yscale("symlog", linthresh=1e-5)
    titles = (
        "B13PG concentration and duplicated curve",
        "B13PG production and drainage",
        "B13PG net flux",
        "GAPDH/PGK control factors",
        "PGK versus Rapoport-Luebering routing",
        "Coupled states at V6PGD 0.900x",
    )
    for axis, title in zip(axes.flat, titles):
        axis.set_title(title)
        axis.set_xlabel("Time (day)")
        axis.grid(alpha=0.22)
        axis.legend(frameon=False, fontsize=7)
    axes[0, 0].set_ylabel("mM")
    axes[0, 1].set_ylabel("mM/day")
    axes[0, 2].set_ylabel("mM/day")
    axes[1, 2].set_ylabel("mM")
    fig.suptitle("J1-J3 B13PG balance and initialization provenance audit")
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    rows = [
        row for row in summary["window_attribution"] if row["candidate"] == CANDIDATE_LABEL
    ]
    metrics = summary["transition_metrics"][CANDIDATE_LABEL]
    provenance = summary["initialization_provenance"]
    lines = [
        "# J1-J3 B13PG balance and provenance audit",
        "",
        "## Contract",
        "",
        "- Balanced seed and retained `vmax_V6PGD = 9.0` replayed at fixed parameters and saved PPP initializations.",
        "- Exact balance: `dB13PG/dt = VGAPDH - VPGK - VDPGM`, including native low-pool damping.",
        "- No optimization, parameter promotion, or initial-state promotion.",
        f"- Maximum closure error: `{summary['max_B13PG_closure_error']:.3e}` mM/day.",
        "",
        "## Initialization provenance",
        "",
        f"- B13PG and B23PG workbook curves pointwise identical: `{provenance['curves_pointwise_identical']}`.",
        f"- Maximum curve difference: `{provenance['maximum_curve_absolute_difference']:.3e}` mM.",
        f"- B13PG calibration target: `{provenance['B13PG_supported_calibration_target']}`; B23PG target: `{provenance['B23PG_supported_calibration_target']}`.",
        f"- Shared J1 value: `{provenance['B13PG_initial_workbook_mM']:.6g}` mM.",
        "",
        "## Candidate balance",
        "",
        "| Window | B13PG start-end | GAPDH input | PGK drain | DPGM shunt | Replacement | PGK share |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['window']}` | {row['B13PG_start_mM']:.6g}-{row['B13PG_end_mM']:.6g} | "
            f"{row['VGAPDH_mean']:.5f} | {row['VPGK_mean']:.5f} | "
            f"{row['VDPGM_mean']:.5f} | {100.0 * row['VGAPDH_replacement_fraction']:.1f}% | "
            f"{100.0 * row['VPGK_drainage_fraction']:.1f}% |"
        )
    lines.extend(
        [
            "",
            "## Structural decision",
            "",
            f"- B13PG below 1% of initial stock: day `{metrics['B13PG_below_1pct_initial_day']:.4f}`.",
            f"- J1-J3 GAPDH replacement fraction: `{100.0 * metrics['J1_J3_VGAPDH_replacement_fraction']:.1f}%`.",
            f"- J1-J3 PGK drainage share: `{100.0 * metrics['J1_J3_VPGK_drainage_fraction']:.1f}%`.",
            f"- J1-J3 DPGM shunt share: `{100.0 * metrics['J1_J3_VDPGM_shunt_fraction']:.1f}%`.",
            "",
            f"**`{summary['structural_classification']['classification']}`**",
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
    provenance = _provenance_audit()
    raw_data = pd.read_excel(BRODBAR_DATA, engine="openpyxl")
    names = raw_data.iloc[:, 0].astype(str).str.strip().str.upper()
    time_columns = np.asarray([float(value) for value in raw_data.columns[1:]], dtype=float)
    duplicated_values = raw_data.loc[names == "B13PG"].iloc[0, 1:].to_numpy(dtype=float)
    duplicated_teacher = PchipInterpolator(time_columns, duplicated_values)
    t_eval = np.linspace(1.0, 3.0, int(timepoints))
    frames: dict[str, pd.DataFrame] = {}
    closures: dict[str, dict[str, float]] = {}
    window_rows: list[dict[str, Any]] = []
    transition_metrics: dict[str, dict[str, Any]] = {}
    for label in (BASELINE_LABEL, CANDIDATE_LABEL):
        print(f"[b13pg-audit] replaying {label}", flush=True)
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
            duplicated_teacher=duplicated_teacher,
            closure_tolerance=closure_tolerance,
        )
        frames[label] = frame
        closures[label] = closure
        window_rows.extend(_window_rows(frame))
        transition_metrics[label] = _transition_metrics(frame)
    candidate_metrics = transition_metrics[CANDIDATE_LABEL]
    classification = _classify(provenance=provenance, metrics=candidate_metrics)
    if classification["classification"].startswith("non-independent"):
        decision = "reclassify B13PG(0) as a non-independent latent initialization"
        rationale = (
            "The B13PG workbook curve is an exact duplicate of B23PG and is not an "
            "active calibration target, yet its J1 value initializes B13PG. This "
            "non-independent 3.584 mM stock is depleted to below 1% before day "
            f"{candidate_metrics['B13PG_below_1pct_initial_day']:.3f}, generating a "
            "large transient PGK ATP pulse. GAPDH replaces only "
            f"{100.0 * candidate_metrics['J1_J3_VGAPDH_replacement_fraction']:.1f}% "
            "of J1-J3 drainage. The ATP pulse therefore cannot be used to identify "
            "PGK/GAPDH kinetics until B13PG initialization is separated from B23PG."
        )
        next_step = (
            "build a reversible constrained B13PG initial-state diagnostic at fixed "
            "kinetics, with B23PG locked to data and B13PG treated as latent"
        )
    else:
        decision = "retain mixed B13PG initialization and replacement diagnosis"
        rationale = "The audit does not isolate initialization provenance from kinetic replacement."
        next_step = "expand B13PG provenance and fixed-state sensitivity diagnostics"
    pd.DataFrame(window_rows).to_csv(out_dir / "b13pg_window_attribution.csv", index=False)
    pd.concat(frames.values(), ignore_index=True).to_csv(
        out_dir / "b13pg_transition_timeseries.csv", index=False
    )
    (out_dir / "initialization_provenance.json").write_text(
        json.dumps(_jsonable(provenance), indent=2), encoding="utf-8"
    )
    _plot(frames=frames, out_path=out_dir / "b13pg_balance_provenance.png")
    max_closure = max(
        row["max_abs_B13PG_closure_error"] for row in closures.values()
    )
    summary = {
        "contract_type": "fixed_parameter_b13pg_balance_provenance_audit",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "kinetic_optimization_performed": False,
        "parameters_promoted": False,
        "initial_conditions_promoted": False,
        "horizon_days": [1.0, 3.0],
        "source_refinement_dir": str(refinement_dir),
        "seed_params_path": str(seed_params_path),
        "cases": [BASELINE_LABEL, CANDIDATE_LABEL],
        "changed_kinetic_constants": ["vmax_V6PGD"],
        "B13PG_balance_equation": "dB13PG/dt = VGAPDH - VPGK - VDPGM",
        "B13PG_effective_balance": (
            "when B13PG < 1e-3 mM and raw derivative < 0, effective derivative = "
            "raw derivative * B13PG / 1e-3"
        ),
        "initialization_provenance": provenance,
        "closures": closures,
        "max_B13PG_closure_error": max_closure,
        "window_attribution": window_rows,
        "transition_metrics": transition_metrics,
        "structural_classification": classification,
        "decision": decision,
        "decision_rationale": rationale,
        "next_step": next_step,
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "report": str(out_dir / "decision_report.md"),
            "window_attribution": str(out_dir / "b13pg_window_attribution.csv"),
            "timeseries": str(out_dir / "b13pg_transition_timeseries.csv"),
            "provenance": str(out_dir / "initialization_provenance.json"),
            "plot": str(out_dir / "b13pg_balance_provenance.png"),
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
        description="Audit J1-J3 B13PG balance and initialization provenance"
    )
    parser.add_argument(
        "--refinement-dir", type=Path, default=DEFAULT_REFINEMENT_DIR
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--timepoints", type=int, default=2001)
    parser.add_argument("--method", default="LSODA")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    parser.add_argument("--closure-tolerance", type=float, default=1e-12)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_audit(
        refinement_dir=args.refinement_dir,
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
