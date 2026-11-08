"""Audit IMP and adenine/PRPP transfer under the fixed VAPRT=0 VAMPD1 anchor."""

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
SCRIPT_DIR = ROOT / "scripts"
DEFAULT_SCREEN_DIR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "vmax_vampd1_vaprt_zero_screen_J1_J46"
)
DEFAULT_OUT_DIR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "imp_purine_transfer_vampd1_1p1_vaprt_zero_J1_J46"
)

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from audit_atp_transition_v6pgd_ppp_context import _integral  # noqa: E402
from equadiff_brodbar import MODEL_NETWORK_VERSION  # noqa: E402
from evaluate_brodbar_candidate_full_panel import _load_brodbar_panel  # noqa: E402
from profile_glycolysis_flux_bottlenecks import _jsonable  # noqa: E402


BASELINE_LABEL = "vmax_VAMPD1_1.000x"
ANCHOR_LABEL = "vmax_VAMPD1_1.100x"
HORIZONS = ("J1_J3", "J1_J10", "J1_J46")
WINDOWS = (
    ("J1-J3", 1.0, 3.0),
    ("J3-J10", 3.0, 10.0),
    ("J10-J21", 10.0, 21.0),
    ("J21-J35", 21.0, 35.0),
    ("J35-J46", 35.0, 46.0),
)
PURINE_STATES = ("IMP", "ADE", "EADE", "HYPX", "EHYPX", "INO", "EINO", "GMP")
IMP_TERMS = {
    "VHGPRT1": 1.0,
    "VAMPD1": 1.0,
    "VADSS": -1.0,
    "VIMPH": -1.0,
    "Vnucleo2": -1.0,
}
ADE_TERMS = {"VEADE": -1.0, "VAPRT": -1.0}
PRPP_TERMS = {
    "VPRPPASe": 1.0,
    "VAPRT": -1.0,
    "VHGPRT1": -1.0,
    "VHGPRT2": -1.0,
}
POSITIVE_REQUIREMENT_FRACTION = 0.90
MATERIAL_FLUX_INTEGRAL_MILLIMOLAR = 0.05
TEACHER_DISAGREEMENT_MILLIMOLAR = 0.10


def _raw_balance(frame: pd.DataFrame, terms: Mapping[str, float]) -> np.ndarray:
    missing = [name for name in terms if name not in frame]
    if missing:
        raise KeyError(f"Replay is missing reactions: {missing}")
    return sum(
        coefficient * frame[reaction].to_numpy(dtype=float)
        for reaction, coefficient in terms.items()
    )


def _normalized_rmse(model: np.ndarray, teacher: np.ndarray, full: np.ndarray) -> float:
    scale = max(float(np.mean(np.abs(full))), 0.01)
    return float(np.sqrt(np.mean((model - teacher) ** 2)) / scale)


def _requirement_summary(values: np.ndarray, time: np.ndarray) -> dict[str, float]:
    values = np.asarray(values, dtype=float)
    return {
        "integral_mM": _integral(values, time),
        "minimum_mM_per_day": float(np.min(values)),
        "maximum_mM_per_day": float(np.max(values)),
        "mean_mM_per_day": float(np.mean(values)),
        "nonnegative_time_fraction": float(np.mean(values >= 0.0)),
        "positive_time_fraction": float(np.mean(values > 1e-12)),
    }


def _directionality(values: np.ndarray, time: np.ndarray) -> dict[str, Any]:
    values = np.asarray(values, dtype=float)
    signs = np.where(values > 1e-12, 1, np.where(values < -1e-12, -1, 0))
    nonzero = signs[signs != 0]
    transitions = int(np.sum(nonzero[1:] != nonzero[:-1])) if nonzero.size > 1 else 0
    reverse = np.flatnonzero(values < -1e-12)
    return {
        "forward_time_fraction": float(np.mean(values >= -1e-12)),
        "reverse_time_fraction": float(np.mean(values < -1e-12)),
        "transition_count": transitions,
        "first_reverse_day": float(time[reverse[0]]) if reverse.size else None,
        "net_integral_mM": _integral(values, time),
    }


def _augment_teachers(
    *,
    frame: pd.DataFrame,
    exp_time: np.ndarray,
    panel_curves: Mapping[str, np.ndarray],
) -> pd.DataFrame:
    result = frame.copy()
    time = result["time_day"].to_numpy(dtype=float)
    for state in PURINE_STATES:
        if state not in panel_curves:
            continue
        teacher = PchipInterpolator(exp_time, panel_curves[state])
        result[f"{state}_teacher"] = np.asarray(teacher(time), dtype=float)
        result[f"d{state}_teacher_dt"] = np.asarray(
            teacher.derivative()(time), dtype=float
        )
    result["dIMP_reconstructed_dt"] = _raw_balance(result, IMP_TERMS)
    result["dADE_reconstructed_dt"] = _raw_balance(result, ADE_TERMS)
    result["dPRPP_reconstructed_dt"] = _raw_balance(result, PRPP_TERMS)
    result["IMP_teacher_residual_mM_per_day"] = (
        result["dIMP_teacher_dt"] - result["dIMP_ode_dt"]
    )
    result["VAMPD1_teacher_from_IMP"] = (
        result["dIMP_teacher_dt"]
        - result["VHGPRT1"]
        + result["VADSS"]
        + result["VIMPH"]
        + result["Vnucleo2"]
    )
    result["ADE_EADE_model"] = result["ADE"] + result["EADE"]
    result["ADE_EADE_teacher"] = result["ADE_teacher"] + result["EADE_teacher"]
    result["VAPRT_teacher_from_ADE_EADE"] = -(
        result["dADE_teacher_dt"] + result["dEADE_teacher_dt"]
    )
    result["VEADE_teacher_from_EADE"] = result["dEADE_teacher_dt"]
    result["VAPRT_teacher_from_ADE"] = -result["VEADE"] - result["dADE_teacher_dt"]
    result["VAPRT_teacher_from_total_adenylate"] = (
        result["dadenylate_total_teacher_dt"]
        - result["VAK2"]
        + result["VSAM"]
        - result["VADSL"]
        + result["VAMPD1"]
    )
    result["VAPRT_teacher_disagreement"] = (
        result["VAPRT_teacher_from_ADE_EADE"]
        - result["VAPRT_teacher_from_total_adenylate"]
    )
    return result


def _state_metrics(
    *,
    frame: pd.DataFrame,
    panel_curves: Mapping[str, np.ndarray],
) -> dict[str, dict[str, float]]:
    metrics: dict[str, dict[str, float]] = {}
    for state in PURINE_STATES:
        teacher_column = f"{state}_teacher"
        if state not in frame or teacher_column not in frame:
            continue
        model = frame[state].to_numpy(dtype=float)
        teacher = frame[teacher_column].to_numpy(dtype=float)
        metrics[state] = {
            "nrmse": _normalized_rmse(model, teacher, panel_curves[state]),
            "model_endpoint_mM": float(model[-1]),
            "teacher_endpoint_mM": float(teacher[-1]),
            "model_change_mM": float(model[-1] - model[0]),
            "teacher_change_mM": float(teacher[-1] - teacher[0]),
        }
    return metrics


def _horizon_metrics(
    *,
    frame: pd.DataFrame,
    panel_curves: Mapping[str, np.ndarray],
) -> dict[str, Any]:
    time = frame["time_day"].to_numpy(dtype=float)
    imp_raw = _raw_balance(frame, IMP_TERMS)
    ade_raw = _raw_balance(frame, ADE_TERMS)
    prpp_raw = _raw_balance(frame, PRPP_TERMS)
    closures = {
        "max_abs_IMP_reconstruction_error": float(
            np.max(np.abs(imp_raw - frame["dIMP_raw_dt"]))
        ),
        "max_abs_ADE_reconstruction_error": float(
            np.max(np.abs(ade_raw - frame["dADE_raw_dt"]))
        ),
        "max_abs_PRPP_reconstruction_error": float(
            np.max(np.abs(prpp_raw - frame["dPRPP_raw_dt"]))
        ),
        "max_abs_IMP_ODE_closure_error": float(np.max(np.abs(frame["IMP_closure_error"]))),
        "max_abs_ADE_ODE_closure_error": float(np.max(np.abs(frame["ADE_closure_error"]))),
        "max_abs_PRPP_ODE_closure_error": float(np.max(np.abs(frame["PRPP_closure_error"]))),
    }
    imp_contributions = {
        reaction: coefficient * _integral(frame[reaction].to_numpy(dtype=float), time)
        for reaction, coefficient in IMP_TERMS.items()
    }
    prpp_contributions = {
        reaction: coefficient * _integral(frame[reaction].to_numpy(dtype=float), time)
        for reaction, coefficient in PRPP_TERMS.items()
    }
    pair_model = frame["ADE_EADE_model"].to_numpy(dtype=float)
    pair_teacher = frame["ADE_EADE_teacher"].to_numpy(dtype=float)
    vaprt_pair = frame["VAPRT_teacher_from_ADE_EADE"].to_numpy(dtype=float)
    vaprt_total = frame["VAPRT_teacher_from_total_adenylate"].to_numpy(dtype=float)
    vampd1_imp = frame["VAMPD1_teacher_from_IMP"].to_numpy(dtype=float)
    actual_vampd1 = frame["VAMPD1"].to_numpy(dtype=float)
    return {
        "horizon_end_day": float(time[-1]),
        "state_metrics": _state_metrics(frame=frame, panel_curves=panel_curves),
        "closures": closures,
        "IMP_contributions_mM": imp_contributions,
        "IMP_model_change_mM": float(frame["IMP"].iloc[-1] - frame["IMP"].iloc[0]),
        "IMP_teacher_change_mM": float(
            frame["IMP_teacher"].iloc[-1] - frame["IMP_teacher"].iloc[0]
        ),
        "IMP_teacher_residual_integral_mM": _integral(
            frame["IMP_teacher_residual_mM_per_day"].to_numpy(dtype=float), time
        ),
        "VAMPD1_actual": _requirement_summary(actual_vampd1, time),
        "VAMPD1_teacher_from_IMP": _requirement_summary(vampd1_imp, time),
        "VAMPD1_IMP_teacher_nrmse": _normalized_rmse(
            actual_vampd1,
            vampd1_imp,
            np.maximum(np.abs(vampd1_imp), 0.01),
        ),
        "ADE_EADE_model_change_mM": float(pair_model[-1] - pair_model[0]),
        "ADE_EADE_teacher_change_mM": float(pair_teacher[-1] - pair_teacher[0]),
        "ADE_EADE_endpoint_error_mM": float(pair_model[-1] - pair_teacher[-1]),
        "VAPRT_teacher_from_ADE_EADE": _requirement_summary(vaprt_pair, time),
        "VAPRT_teacher_from_total_adenylate": _requirement_summary(vaprt_total, time),
        "VAPRT_teacher_disagreement_integral_mM": _integral(
            vaprt_pair - vaprt_total, time
        ),
        "VAPRT_teacher_mean_absolute_disagreement_mM_per_day": float(
            np.mean(np.abs(vaprt_pair - vaprt_total))
        ),
        "VEADE_teacher_nrmse": _normalized_rmse(
            frame["VEADE"].to_numpy(dtype=float),
            frame["VEADE_teacher_from_EADE"].to_numpy(dtype=float),
            np.maximum(np.abs(frame["VEADE_teacher_from_EADE"].to_numpy(dtype=float)), 0.01),
        ),
        "PRPP_contributions_mM": prpp_contributions,
        "PRPP_endpoint_mM": float(frame["PRPP"].iloc[-1]),
        "PRPP_minimum_mM": float(frame["PRPP"].min()),
        "ADOMET_endpoint_mM": float(frame["ADOMET"].iloc[-1]),
        "ADOMET_minimum_mM": float(frame["ADOMET"].min()),
        "VAK_directionality": _directionality(frame["VAK"].to_numpy(dtype=float), time),
    }


def _window_rows(frames: Mapping[str, pd.DataFrame]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, frame in frames.items():
        all_time = frame["time_day"].to_numpy(dtype=float)
        for window, start, end in WINDOWS:
            mask = (all_time >= start - 1e-12) & (all_time <= end + 1e-12)
            if np.sum(mask) < 2:
                continue
            part = frame.loc[mask]
            time = part["time_day"].to_numpy(dtype=float)
            row: dict[str, Any] = {
                "candidate": label,
                "window": window,
                "IMP_model_change_mM": float(part["IMP"].iloc[-1] - part["IMP"].iloc[0]),
                "IMP_teacher_change_mM": float(
                    part["IMP_teacher"].iloc[-1] - part["IMP_teacher"].iloc[0]
                ),
                "VAMPD1_actual_integral_mM": _integral(part["VAMPD1"], time),
                "VAMPD1_teacher_from_IMP_integral_mM": _integral(
                    part["VAMPD1_teacher_from_IMP"], time
                ),
                "VAPRT_teacher_from_ADE_EADE_integral_mM": _integral(
                    part["VAPRT_teacher_from_ADE_EADE"], time
                ),
                "VAPRT_teacher_from_total_integral_mM": _integral(
                    part["VAPRT_teacher_from_total_adenylate"], time
                ),
            }
            for reaction, coefficient in IMP_TERMS.items():
                row[f"IMP_{reaction}_signed_integral_mM"] = coefficient * _integral(
                    part[reaction], time
                )
            rows.append(row)
    return rows


def _classify(anchor_metrics: Mapping[str, Any]) -> str:
    pair = anchor_metrics["VAPRT_teacher_from_ADE_EADE"]
    total = anchor_metrics["VAPRT_teacher_from_total_adenylate"]
    disagreement = abs(float(anchor_metrics["VAPRT_teacher_disagreement_integral_mM"]))
    pair_demands_flux = (
        float(pair["integral_mM"]) > MATERIAL_FLUX_INTEGRAL_MILLIMOLAR
        and float(pair["positive_time_fraction"]) >= POSITIVE_REQUIREMENT_FRACTION
    )
    total_demands_flux = (
        float(total["integral_mM"]) > MATERIAL_FLUX_INTEGRAL_MILLIMOLAR
        and float(total["positive_time_fraction"]) >= POSITIVE_REQUIREMENT_FRACTION
    )
    if pair_demands_flux and (
        not total_demands_flux or disagreement > TEACHER_DISAGREEMENT_MILLIMOLAR
    ):
        return "hard_VAPRT_zero_rejected_but_positive_APRT_alone_is_teacher_incompatible"
    if pair_demands_flux and total_demands_flux:
        return "hard_VAPRT_zero_rejected_bounded_positive_APRT_supported"
    if abs(float(pair["integral_mM"])) <= MATERIAL_FLUX_INTEGRAL_MILLIMOLAR:
        return "hard_VAPRT_zero_compatible_with_ADE_EADE_teacher"
    return "mixed_VAPRT_requirement_requires_scaling_or_time_dependent_audit"


def _plot(
    *,
    frames: Mapping[str, pd.DataFrame],
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(15.5, 8.5), constrained_layout=True)
    colors = {BASELINE_LABEL: "#4c78a8", ANCHOR_LABEL: "#d1495b"}
    labels = {BASELINE_LABEL: "VAMPD1 1.0x", ANCHOR_LABEL: "VAMPD1 1.1x"}
    for key, frame in frames.items():
        time = frame["time_day"]
        axes[0, 0].plot(time, frame["IMP"], color=colors[key], lw=2, label=labels[key])
        axes[0, 1].plot(time, frame["VAMPD1"], color=colors[key], lw=2, label=labels[key])
        axes[0, 2].plot(time, frame["ADE_EADE_model"], color=colors[key], lw=2, label=labels[key])
        axes[1, 0].plot(
            time,
            frame["VAPRT_teacher_from_total_adenylate"],
            color=colors[key],
            lw=2,
            label=labels[key],
        )
        axes[1, 1].plot(time, frame["PRPP"], color=colors[key], lw=2, label=labels[key])
        axes[1, 2].plot(time, frame["VAK"], color=colors[key], lw=2, label=labels[key])
    reference = frames[BASELINE_LABEL]
    time = reference["time_day"]
    axes[0, 0].plot(time, reference["IMP_teacher"], "k--", lw=2, label="Brodbar teacher")
    axes[0, 1].plot(
        time,
        reference["VAMPD1_teacher_from_IMP"],
        "k--",
        lw=2,
        label="IMP-derived teacher",
    )
    axes[0, 2].plot(
        time,
        reference["ADE_EADE_teacher"],
        "k--",
        lw=2,
        label="Brodbar ADE+EADE",
    )
    axes[1, 0].plot(
        time,
        reference["VAPRT_teacher_from_ADE_EADE"],
        "k--",
        lw=2,
        label="ADE+EADE teacher",
    )
    axes[1, 0].axhline(0.0, color="0.5", lw=1)
    axes[1, 2].axhline(0.0, color="0.5", lw=1)
    titles = (
        "IMP concentration",
        "VAMPD1 constrained by IMP",
        "Adenine pool ownership",
        "Divergent VAPRT teachers",
        "PRPP latent pool",
        "VAK directionality",
    )
    for axis, title in zip(axes.flat, titles):
        axis.set_title(title)
        axis.set_xlabel("Storage day")
        axis.grid(alpha=0.2)
        axis.legend(fontsize=7)
    axes[0, 0].set_ylabel("Concentration (mM)")
    axes[0, 1].set_ylabel("Flux (mM/day)")
    axes[0, 2].set_ylabel("ADE + EADE (current model units)")
    axes[1, 0].set_ylabel("Required VAPRT (mM/day)")
    axes[1, 1].set_ylabel("Concentration (mM)")
    axes[1, 1].set_yscale("log")
    axes[1, 2].set_ylabel("Net VAK (mM/day)")
    axes[1, 2].set_yscale("symlog", linthresh=1e-3)
    fig.suptitle("FLA audit of IMP and purine transfer under VAPRT=0", fontsize=15)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    anchor = summary["metrics"]["J1_J46"][ANCHOR_LABEL]
    baseline = summary["metrics"]["J1_J46"][BASELINE_LABEL]
    lines = [
        "# IMP and purine-transfer audit under VAPRT=0",
        "",
        "## Contract",
        "",
        "- Compared fixed VAMPD1 `1.0x` and `1.1x` replays over J1-J3, J1-J10, and J1-J46.",
        "- No ODE state, kinetic constant, or replay trajectory was refitted.",
        "- Reconstructed exact IMP, ADE, and PRPP balances and independent concentration-derived flux requirements.",
        "",
        "## J1-J46 results",
        "",
        f"- IMP nRMSE: `{baseline['state_metrics']['IMP']['nrmse']:.5g} -> {anchor['state_metrics']['IMP']['nrmse']:.5g}`.",
        f"- Actual versus IMP-required VAMPD1 integral: `{anchor['VAMPD1_actual']['integral_mM']:.5g}` versus `{anchor['VAMPD1_teacher_from_IMP']['integral_mM']:.5g} mM`.",
        f"- ADE+EADE-derived VAPRT integral: `{anchor['VAPRT_teacher_from_ADE_EADE']['integral_mM']:.5g} mM`.",
        f"- Total-adenylate-derived VAPRT integral: `{anchor['VAPRT_teacher_from_total_adenylate']['integral_mM']:.5g} mM`.",
        f"- Integrated disagreement between VAPRT teachers: `{anchor['VAPRT_teacher_disagreement_integral_mM']:.5g} mM`.",
        f"- PRPP/ADOMET endpoints: `{anchor['PRPP_endpoint_mM']:.5g}` / `{anchor['ADOMET_endpoint_mM']:.5g} mM`.",
        "",
        "## Decision",
        "",
        summary["decision"],
        "",
        summary["decision_rationale"],
        "",
        f"Next: {summary['next_step']}.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_audit(*, screen_dir: Path, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    screen_summary = json.loads((screen_dir / "summary.json").read_text(encoding="utf-8"))
    if screen_summary["selected_candidate"] != ANCHOR_LABEL:
        raise RuntimeError("Expected the fixed 1.1x VAMPD1 anchor from the upstream screen")
    if float(screen_summary["fixed_vmax_VAPRT"]) != 0.0:
        raise RuntimeError("Purine audit requires the fixed VAPRT=0 screen")
    exp_time, panel_curves, _order, _indices, unmapped = _load_brodbar_panel()
    required_states = {"IMP", "ADE", "EADE"}
    if not required_states.issubset(panel_curves):
        raise RuntimeError(f"Missing teacher curves: {required_states - set(panel_curves)}")

    frames: dict[str, dict[str, pd.DataFrame]] = {horizon: {} for horizon in HORIZONS}
    metrics: dict[str, dict[str, Any]] = {horizon: {} for horizon in HORIZONS}
    for horizon in HORIZONS:
        source = pd.read_csv(screen_dir / f"{horizon}_timeseries.csv")
        for label in (BASELINE_LABEL, ANCHOR_LABEL):
            frame = source.loc[source["candidate"] == label].reset_index(drop=True)
            if frame.empty:
                raise RuntimeError(f"{horizon} replay is missing {label}")
            frame = _augment_teachers(
                frame=frame,
                exp_time=exp_time,
                panel_curves=panel_curves,
            )
            frames[horizon][label] = frame
            metrics[horizon][label] = _horizon_metrics(
                frame=frame,
                panel_curves=panel_curves,
            )

    anchor_long = metrics["J1_J46"][ANCHOR_LABEL]
    classification = _classify(anchor_long)
    if classification == "hard_VAPRT_zero_rejected_but_positive_APRT_alone_is_teacher_incompatible":
        decision = "reject hard VAPRT=0 as a globally promotable mechanism, but do not restore positive APRT alone"
        rationale = (
            "The measured ADE+EADE pair requires sustained adenine-pool removal, whereas the total-adenylate "
            "teacher requires a materially different APRT trajectory under the selected VAMPD1 anchor. "
            "A single irreversible APRT flux cannot satisfy both constraints under the current compartment scaling and network ownership."
        )
        next_step = "audit intracellular/extracellular adenine scaling and test an explicit EADE loss term against a bounded APRT branch at fixed kinetics"
    elif classification == "hard_VAPRT_zero_rejected_bounded_positive_APRT_supported":
        decision = "reject hard VAPRT=0 and retain a bounded positive APRT hypothesis"
        rationale = "The independent adenine-pair and total-adenylate teachers both require positive APRT over storage."
        next_step = "screen a narrow bounded VAPRT activity fraction without opening another kinetic family"
    elif classification == "hard_VAPRT_zero_compatible_with_ADE_EADE_teacher":
        decision = "retain hard VAPRT=0 as an adenine-pair-compatible diagnostic"
        rationale = "The integrated ADE+EADE teacher does not require material APRT flux under the current scaling."
        next_step = "audit the residual IMP sink mismatch before promotion"
    else:
        decision = "defer VAPRT promotion because its teacher requirement is mixed"
        rationale = "The concentration-derived APRT direction is not stable enough for a fixed activity decision."
        next_step = "audit volume scaling and time-localized APRT requirements before calibration"

    long_frames = frames["J1_J46"]
    combined = pd.concat(long_frames.values(), ignore_index=True)
    combined.to_csv(out_dir / "J1_J46_purine_audit_timeseries.csv", index=False)
    window_rows = _window_rows(long_frames)
    pd.DataFrame(window_rows).to_csv(out_dir / "window_attribution.csv", index=False)
    flat_rows = []
    for horizon, by_label in metrics.items():
        for label, values in by_label.items():
            flat_rows.append(
                {
                    "horizon": horizon,
                    "candidate": label,
                    "IMP_nrmse": values["state_metrics"]["IMP"]["nrmse"],
                    "IMP_model_change_mM": values["IMP_model_change_mM"],
                    "IMP_teacher_change_mM": values["IMP_teacher_change_mM"],
                    "VAMPD1_actual_integral_mM": values["VAMPD1_actual"]["integral_mM"],
                    "VAMPD1_teacher_from_IMP_integral_mM": values[
                        "VAMPD1_teacher_from_IMP"
                    ]["integral_mM"],
                    "VAPRT_teacher_from_ADE_EADE_integral_mM": values[
                        "VAPRT_teacher_from_ADE_EADE"
                    ]["integral_mM"],
                    "VAPRT_teacher_from_total_integral_mM": values[
                        "VAPRT_teacher_from_total_adenylate"
                    ]["integral_mM"],
                    "VAPRT_teacher_disagreement_integral_mM": values[
                        "VAPRT_teacher_disagreement_integral_mM"
                    ],
                    "PRPP_endpoint_mM": values["PRPP_endpoint_mM"],
                    "ADOMET_endpoint_mM": values["ADOMET_endpoint_mM"],
                    "VAK_forward_time_fraction": values["VAK_directionality"][
                        "forward_time_fraction"
                    ],
                }
            )
    pd.DataFrame(flat_rows).to_csv(out_dir / "horizon_metrics.csv", index=False)
    _plot(frames=long_frames, out_path=out_dir / "imp_purine_transfer_audit.png")
    summary = {
        "contract_type": "fixed_kinetic_IMP_ADE_PRPP_flux_learning_audit",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_network_version": MODEL_NETWORK_VERSION,
        "source_screen": str(screen_dir.resolve()),
        "optimization_performed": False,
        "parameters_promoted": False,
        "compared_candidates": [BASELINE_LABEL, ANCHOR_LABEL],
        "fixed_vmax_VAPRT": 0.0,
        "anchor_vmax_VAMPD1": screen_summary["selected_vmax_VAMPD1"],
        "balance_contracts": {
            "IMP": IMP_TERMS,
            "ADE": ADE_TERMS,
            "PRPP": PRPP_TERMS,
            "direct_VAPRT_teacher": "VAPRT_T = -d(ADE_T + EADE_T)/dt in current model units",
            "total_pool_VAPRT_teacher": "VAPRT_T = dA_tot_T/dt - VAK2 + VSAM - VADSL + VAMPD1",
            "conditional_VAMPD1_teacher": "VAMPD1_T = dIMP_T/dt - VHGPRT1 + VADSS + VIMPH + Vnucleo2",
        },
        "scaling_caveat": (
            "ADE and EADE are combined in the current standardized/model concentration units. "
            "The direct teacher must be re-evaluated after explicit intracellular/extracellular volume scaling."
        ),
        "unmapped_panel_states": unmapped,
        "metrics": metrics,
        "window_attribution": window_rows,
        "classification": classification,
        "decision": decision,
        "decision_rationale": rationale,
        "next_step": next_step,
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "report": str(out_dir / "decision_report.md"),
            "horizon_metrics": str(out_dir / "horizon_metrics.csv"),
            "window_attribution": str(out_dir / "window_attribution.csv"),
            "timeseries": str(out_dir / "J1_J46_purine_audit_timeseries.csv"),
            "plot": str(out_dir / "imp_purine_transfer_audit.png"),
        },
    }
    (out_dir / "summary.json").write_text(
        json.dumps(_jsonable(summary), indent=2), encoding="utf-8"
    )
    _write_report(out_dir / "decision_report.md", summary)
    print(
        json.dumps(
            {
                "classification": classification,
                "decision": decision,
                "VAPRT_ADE_EADE_integral_mM": anchor_long[
                    "VAPRT_teacher_from_ADE_EADE"
                ]["integral_mM"],
                "VAPRT_total_integral_mM": anchor_long[
                    "VAPRT_teacher_from_total_adenylate"
                ]["integral_mM"],
                "VAMPD1_actual_integral_mM": anchor_long["VAMPD1_actual"][
                    "integral_mM"
                ],
                "VAMPD1_IMP_teacher_integral_mM": anchor_long[
                    "VAMPD1_teacher_from_IMP"
                ]["integral_mM"],
                "summary": str(out_dir / "summary.json"),
            },
            indent=2,
        )
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen-dir", type=Path, default=DEFAULT_SCREEN_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_audit(screen_dir=args.screen_dir, out_dir=args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
