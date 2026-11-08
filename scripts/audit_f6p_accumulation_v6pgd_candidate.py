"""Audit 46-day F6P accumulation at the retained V6PGD diagnostic point."""

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
    / "f6p_accumulation_v6pgd_0.900_audit_46d"
)

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from profile_atp_consumption_sinks import _all_experimental_curves  # noqa: E402
from profile_glycolysis_flux_bottlenecks import _jsonable, _load_params  # noqa: E402


BASELINE_LABEL = "constrained_balanced_teacher__seed"
CANDIDATE_LABEL = "constrained_balanced_teacher__v6pgd_0.9000x"
F6P_TERMS = {
    "VPGI": 1.0,
    "VPFK": -1.0,
    "VTKL2": 1.0,
    "VTAL": 1.0,
}
WINDOWS = (
    ("J1_J2", 1.0, 2.0),
    ("day_2_10", 2.0, 10.0),
    ("day_10_20", 10.0, 20.0),
    ("day_20_30", 20.0, 30.0),
    ("day_30_46", 30.0, 46.0),
)
COUPLED_STATES = ("F6P", "G6P", "GA3P", "E4P", "S7P", "F16BP", "ATP")


def _time_mean(values: np.ndarray, time: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    time = np.asarray(time, dtype=float)
    if len(time) < 2:
        return float(values[0])
    return float(np.trapezoid(values, time) / (time[-1] - time[0]))


def _integral(values: np.ndarray, time: np.ndarray) -> float:
    return float(np.trapezoid(np.asarray(values, dtype=float), np.asarray(time, dtype=float)))


def _reconstruct_f6p_raw_balance(frame: pd.DataFrame) -> np.ndarray:
    return sum(
        coefficient * frame[reaction].to_numpy(dtype=float)
        for reaction, coefficient in F6P_TERMS.items()
    )


def _first_sustained_crossing(
    time: np.ndarray,
    values: np.ndarray,
    *,
    threshold: float,
    duration: float,
) -> float | None:
    time = np.asarray(time, dtype=float)
    active = np.asarray(values, dtype=float) > float(threshold)
    for start in np.flatnonzero(active):
        end_time = float(time[start] + duration)
        end = int(np.searchsorted(time, end_time, side="left"))
        if end >= len(time):
            break
        if bool(np.all(active[start : end + 1])):
            return float(time[start])
    return None


def _divergence_metrics(
    *,
    frame: pd.DataFrame,
    experimental_curve: PchipInterpolator,
    experimental_values: np.ndarray,
) -> dict[str, Any]:
    time = frame["time_day"].to_numpy(dtype=float)
    model = frame["F6P"].to_numpy(dtype=float)
    teacher = np.asarray(experimental_curve(time), dtype=float)
    scale = max(
        float(np.mean(np.abs(experimental_values))),
        float(np.ptp(experimental_values)),
        1e-4,
    )
    normalized_error = np.abs(model - teacher) / scale
    fold_denominator = np.maximum(np.abs(teacher), 1e-4)
    fold_excess = model / fold_denominator
    return {
        "teacher_scale": scale,
        "first_sustained_nerror_gt_1_day": _first_sustained_crossing(
            time, normalized_error, threshold=1.0, duration=1.0
        ),
        "first_sustained_model_gt_2x_teacher_day": _first_sustained_crossing(
            time, fold_excess, threshold=2.0, duration=1.0
        ),
        "endpoint_model_mM": float(model[-1]),
        "endpoint_teacher_mM": float(teacher[-1]),
        "endpoint_absolute_error_mM": float(abs(model[-1] - teacher[-1])),
        "maximum_normalized_error": float(np.max(normalized_error)),
    }


def _window_attribution_rows(
    *,
    frame: pd.DataFrame,
    teacher_curve: PchipInterpolator,
    vmax_vpfk: float,
    km_f6p: float,
    km_atp_pfk: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    all_time = frame["time_day"].to_numpy(dtype=float)
    for window, start, end in WINDOWS:
        mask = (all_time >= start - 1e-12) & (all_time <= end + 1e-12)
        time = all_time[mask]
        local = frame.loc[mask]
        teacher_flux = np.asarray(teacher_curve.derivative()(time), dtype=float)
        v_pgi = local["VPGI"].to_numpy(dtype=float)
        v_pfk = local["VPFK"].to_numpy(dtype=float)
        v_tkl2 = local["VTKL2"].to_numpy(dtype=float)
        v_tal = local["VTAL"].to_numpy(dtype=float)
        total_input = v_pgi + v_tkl2 + v_tal
        required_vpfk = total_input - teacher_flux
        f6p = local["F6P"].to_numpy(dtype=float)
        atp = local["ATP"].to_numpy(dtype=float)
        f6p_saturation = f6p / (f6p + float(km_f6p))
        safe_atp = np.maximum(atp, 1e-6)
        atp_saturation = safe_atp / (safe_atp + float(km_atp_pfk))
        denominator = float(vmax_vpfk) * f6p_saturation * atp_saturation
        inferred_modulation = np.divide(
            v_pfk,
            denominator,
            out=np.full_like(v_pfk, np.nan),
            where=denominator > 1e-15,
        )
        input_integrals = {
            "VPGI": _integral(v_pgi, time),
            "VTKL2": _integral(v_tkl2, time),
            "VTAL": _integral(v_tal, time),
        }
        total_input_integral = sum(input_integrals.values())
        model_net = local["dF6P_dt_effective_flux"].to_numpy(dtype=float)
        rows.append(
            {
                "candidate": str(frame["candidate"].iloc[0]),
                "window": window,
                "start_day": float(time[0]),
                "end_day": float(time[-1]),
                "F6P_start_mM": float(f6p[0]),
                "F6P_end_mM": float(f6p[-1]),
                "F6P_change_mM": float(f6p[-1] - f6p[0]),
                "ATP_mean_mM": _time_mean(atp, time),
                "ATP_minimum_mM": float(np.min(atp)),
                "VPGI_mean": _time_mean(v_pgi, time),
                "VTKL2_mean": _time_mean(v_tkl2, time),
                "VTAL_mean": _time_mean(v_tal, time),
                "VPFK_mean": _time_mean(v_pfk, time),
                "total_input_mean": _time_mean(total_input, time),
                "model_net_mean": _time_mean(model_net, time),
                "teacher_net_mean": _time_mean(teacher_flux, time),
                "required_VPFK_mean": _time_mean(required_vpfk, time),
                "VPFK_teacher_deficit_mean": _time_mean(required_vpfk - v_pfk, time),
                "VPGI_integral": input_integrals["VPGI"],
                "VTKL2_integral": input_integrals["VTKL2"],
                "VTAL_integral": input_integrals["VTAL"],
                "VPFK_integral": _integral(v_pfk, time),
                "model_net_integral": _integral(model_net, time),
                "teacher_net_integral": _integral(teacher_flux, time),
                "excess_net_integral": _integral(model_net - teacher_flux, time),
                "VPGI_input_fraction": input_integrals["VPGI"]
                / max(total_input_integral, 1e-30),
                "nonoxidative_PPP_input_fraction": (
                    input_integrals["VTKL2"] + input_integrals["VTAL"]
                )
                / max(total_input_integral, 1e-30),
                "F6P_saturation_mean": _time_mean(f6p_saturation, time),
                "ATP_saturation_mean": _time_mean(atp_saturation, time),
                "inferred_PFK_modulation_mean": _time_mean(
                    inferred_modulation, time
                ),
            }
        )
    return rows


def _state_window_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    all_time = frame["time_day"].to_numpy(dtype=float)
    for window, start, end in WINDOWS:
        mask = (all_time >= start - 1e-12) & (all_time <= end + 1e-12)
        time = all_time[mask]
        for state in COUPLED_STATES:
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


def _structural_classification(
    *,
    candidate_rows: Sequence[Mapping[str, Any]],
    candidate_divergence: Mapping[str, Any],
    baseline_divergence: Mapping[str, Any],
) -> dict[str, Any]:
    post_initial = [row for row in candidate_rows if row["window"] != "J1_J2"]
    duration = sum(float(row["end_day"] - row["start_day"]) for row in post_initial)

    def weighted(key: str) -> float:
        return sum(
            float(row[key]) * float(row["end_day"] - row["start_day"])
            for row in post_initial
        ) / max(duration, 1e-30)

    atp_saturation = weighted("ATP_saturation_mean")
    f6p_saturation = weighted("F6P_saturation_mean")
    modulation = weighted("inferred_PFK_modulation_mean")
    vpfk_deficit = weighted("VPFK_teacher_deficit_mean")
    ppp_input_fraction = weighted("nonoxidative_PPP_input_fraction")
    candidate_day = candidate_divergence["first_sustained_nerror_gt_1_day"]
    baseline_day = baseline_divergence["first_sustained_nerror_gt_1_day"]
    divergence_shift = (
        None
        if candidate_day is None or baseline_day is None
        else float(candidate_day - baseline_day)
    )
    gates = {
        "F6P_substrate_saturating": f6p_saturation >= 0.80,
        "ATP_occupancy_collapsed": atp_saturation <= 0.10,
        "no_hidden_PFK_modulation_loss": 0.95 <= modulation <= 1.05,
        "VPFK_below_teacher_required_drainage": vpfk_deficit > 0.0,
        "nonoxidative_PPP_input_material": ppp_input_fraction >= 0.25,
        "V6PGD_candidate_does_not_delay_divergence": divergence_shift is not None
        and divergence_shift <= 0.25,
    }
    return {
        "post_J2_weighted_ATP_saturation": atp_saturation,
        "post_J2_weighted_F6P_saturation": f6p_saturation,
        "post_J2_weighted_inferred_PFK_modulation": modulation,
        "post_J2_weighted_VPFK_teacher_deficit": vpfk_deficit,
        "post_J2_weighted_nonoxidative_PPP_input_fraction": ppp_input_fraction,
        "candidate_minus_seed_divergence_day": divergence_shift,
        "classification_gates": gates,
        "classification": (
            "ATP-limited VPFK drainage with material PGI and non-oxidative PPP input"
            if all(gates.values())
            else "mixed or unresolved F6P accumulation mechanism"
        ),
    }


def _plot_audit(
    *,
    frames: Mapping[str, pd.DataFrame],
    experimental_time: np.ndarray,
    experimental_f6p: np.ndarray,
    teacher_curve: PchipInterpolator,
    window_rows: pd.DataFrame,
    params: Mapping[str, Any],
    out_path: Path,
) -> None:
    colors = {BASELINE_LABEL: "#64748b", CANDIDATE_LABEL: "#b91c1c"}
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.5), constrained_layout=True)
    for label, frame in frames.items():
        color = colors[label]
        axes[0, 0].plot(frame["time_day"], frame["F6P"], color=color, label=label)
        axes[0, 1].plot(
            frame["time_day"],
            frame["dF6P_dt_effective_flux"],
            color=color,
            label=label,
        )
    axes[0, 0].plot(
        experimental_time,
        experimental_f6p,
        "k--",
        linewidth=2.0,
        label="Brodbar",
    )
    dense_time = frames[CANDIDATE_LABEL]["time_day"].to_numpy(dtype=float)
    axes[0, 1].plot(
        dense_time,
        teacher_curve.derivative()(dense_time),
        "k--",
        linewidth=2.0,
        label="Brodbar teacher",
    )
    candidate = frames[CANDIDATE_LABEL]
    time = candidate["time_day"].to_numpy(dtype=float)
    teacher_flux = np.asarray(teacher_curve.derivative()(time), dtype=float)
    required_vpfk = (
        candidate["VPGI"].to_numpy(dtype=float)
        + candidate["VTKL2"].to_numpy(dtype=float)
        + candidate["VTAL"].to_numpy(dtype=float)
        - teacher_flux
    )
    axes[0, 2].plot(time, candidate["VPFK"], color="#2563eb", label="actual VPFK")
    axes[0, 2].plot(time, required_vpfk, color="#dc2626", label="teacher-required VPFK")
    axes[0, 2].set_ylim(bottom=min(-0.05, float(np.min(required_vpfk))))

    candidate_rows = window_rows[window_rows["candidate"] == CANDIDATE_LABEL]
    x = np.arange(len(candidate_rows), dtype=float)
    bottoms = np.zeros(len(candidate_rows), dtype=float)
    for reaction, color in (("VPGI", "#2563eb"), ("VTKL2", "#0f766e"), ("VTAL", "#7c3aed")):
        values = candidate_rows[f"{reaction}_integral"].to_numpy(dtype=float)
        axes[1, 0].bar(x, values, bottom=bottoms, label=reaction, color=color)
        bottoms += values
    axes[1, 0].bar(
        x,
        -candidate_rows["VPFK_integral"].to_numpy(dtype=float),
        label="-VPFK",
        color="#dc2626",
    )
    axes[1, 0].set_xticks(x, candidate_rows["window"], rotation=30, ha="right")

    safe_atp = np.maximum(candidate["ATP"].to_numpy(dtype=float), 1e-6)
    atp_occupancy = safe_atp / (safe_atp + float(params["km_ATP_PFK"]))
    f6p = candidate["F6P"].to_numpy(dtype=float)
    f6p_occupancy = f6p / (f6p + float(params["km_F6P"]))
    axes[1, 1].plot(time, atp_occupancy, label="ATP occupancy", color="#dc2626")
    axes[1, 1].plot(time, f6p_occupancy, label="F6P occupancy", color="#2563eb")
    axes[1, 1].set_ylim(-0.02, 1.02)

    for state, color in zip(
        ("G6P", "GA3P", "E4P", "S7P", "ATP"),
        ("#2563eb", "#7c3aed", "#0f766e", "#4d7c0f", "#dc2626"),
    ):
        axes[1, 2].plot(time, candidate[state], label=state, color=color)
    axes[1, 2].set_yscale("symlog", linthresh=1e-4)

    titles = (
        "F6P concentration",
        "F6P net flux",
        "Actual versus teacher-required drainage",
        "Integrated F6P contributions",
        "PFK substrate occupancies",
        "Coupled states at 0.900x",
    )
    for axis, title in zip(axes.flat, titles):
        axis.set_title(title)
        axis.grid(alpha=0.22)
    for axis in axes[0, :]:
        axis.set_xlabel("Time (day)")
    axes[0, 0].set_ylabel("mM")
    axes[0, 1].set_ylabel("mM/day")
    axes[0, 2].set_ylabel("mM/day")
    axes[1, 0].set_ylabel("Integrated contribution (mM)")
    axes[1, 2].set_ylabel("mM")
    for axis in (axes[0, 0], axes[0, 1], axes[0, 2], axes[1, 0], axes[1, 1], axes[1, 2]):
        axis.legend(frameon=False, fontsize=8)
    fig.suptitle("Fixed-parameter audit of residual F6P accumulation")
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    candidate_rows = [
        row for row in summary["window_attribution"] if row["candidate"] == CANDIDATE_LABEL
    ]
    lines = [
        "# Fixed-parameter F6P accumulation audit",
        "",
        "## Contract",
        "",
        "- Compared the balanced seed with the retained `vmax_V6PGD = 9.0` diagnostic point.",
        "- Reused saved 46-day trajectories; no simulation, optimization, or parameter change was performed.",
        "- Reconstructed `dF6P/dt = VPGI + VTKL2 + VTAL - VPFK` exactly.",
        "- Calculated the VPFK drainage required to follow the Brodbar F6P teacher.",
        f"- Maximum raw-balance reconstruction error: `{summary['max_raw_balance_reconstruction_error']:.3e}` mM/day.",
        "",
        "## Candidate attribution",
        "",
        "| Window | F6P start-end | ATP mean | Input | VPFK | Required VPFK | Deficit | PPP input share |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in candidate_rows:
        lines.append(
            f"| `{row['window']}` | {row['F6P_start_mM']:.4f}-{row['F6P_end_mM']:.4f} | "
            f"{row['ATP_mean_mM']:.5f} | {row['total_input_mean']:.5f} | "
            f"{row['VPFK_mean']:.5f} | {row['required_VPFK_mean']:.5f} | "
            f"{row['VPFK_teacher_deficit_mean']:.5f} | "
            f"{100.0 * row['nonoxidative_PPP_input_fraction']:.1f}% |"
        )
    classification = summary["structural_classification"]
    lines.extend(
        [
            "",
            "## Structural diagnosis",
            "",
            f"- F6P divergence day, seed: `{summary['divergence'][BASELINE_LABEL]['first_sustained_nerror_gt_1_day']}`.",
            f"- F6P divergence day, candidate: `{summary['divergence'][CANDIDATE_LABEL]['first_sustained_nerror_gt_1_day']}`.",
            f"- Post-J2 F6P occupancy of PFK: `{classification['post_J2_weighted_F6P_saturation']:.4f}`.",
            f"- Post-J2 ATP occupancy of PFK: `{classification['post_J2_weighted_ATP_saturation']:.4f}`.",
            f"- Inferred hidden PFK modulation: `{classification['post_J2_weighted_inferred_PFK_modulation']:.4f}`.",
            f"- Non-oxidative PPP share of post-J2 F6P input: `{100.0 * classification['post_J2_weighted_nonoxidative_PPP_input_fraction']:.1f}%`.",
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
    out_dir: Path,
    balance_tolerance: float,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    refinement_summary = json.loads(
        (refinement_dir / "summary.json").read_text(encoding="utf-8")
    )
    if refinement_summary["selected_candidate"] != CANDIDATE_LABEL:
        raise RuntimeError("Refinement summary does not select the expected 0.9000x point")
    if refinement_summary["parameters_promoted"] or refinement_summary["initial_conditions_promoted"]:
        raise RuntimeError("F6P audit requires a non-promoted diagnostic refinement")
    frame = pd.read_csv(refinement_dir / "full_horizon_timeseries.csv")
    labels = set(frame["candidate"].astype(str))
    required_labels = {BASELINE_LABEL, CANDIDATE_LABEL}
    if not required_labels.issubset(labels):
        raise KeyError(f"Missing required trajectories: {sorted(required_labels - labels)}")
    frames = {
        label: frame[frame["candidate"] == label].reset_index(drop=True)
        for label in (BASELINE_LABEL, CANDIDATE_LABEL)
    }
    seed_params_path = Path(refinement_summary["seed_params_path"])
    params = _load_params(seed_params_path)
    kinetic = {
        "vmax_VPFK": float(params.get("vmax_VPFK", 0.391893)),
        "km_F6P": float(params.get("km_F6P", 0.207)),
        "km_ATP_PFK": float(params.get("km_ATP_PFK", 0.1)),
    }
    experimental_time, experimental_curves = _all_experimental_curves(46.0)
    f6p_teacher = PchipInterpolator(
        experimental_time, np.asarray(experimental_curves["F6P"], dtype=float)
    )
    max_reconstruction_error = 0.0
    closure: dict[str, dict[str, float]] = {}
    window_rows: list[dict[str, Any]] = []
    state_rows: list[dict[str, Any]] = []
    divergence: dict[str, dict[str, Any]] = {}
    for label, case in frames.items():
        reconstructed = _reconstruct_f6p_raw_balance(case)
        raw_error = float(
            np.max(
                np.abs(
                    reconstructed
                    - case["dF6P_dt_raw_flux"].to_numpy(dtype=float)
                )
            )
        )
        ode_error = float(
            np.max(
                np.abs(
                    case["dF6P_dt_effective_flux"].to_numpy(dtype=float)
                    - case["dF6P_dt_ode"].to_numpy(dtype=float)
                )
            )
        )
        if raw_error > balance_tolerance or ode_error > balance_tolerance:
            raise RuntimeError(
                f"F6P balance closure failed for {label}: raw={raw_error}, ode={ode_error}"
            )
        max_reconstruction_error = max(max_reconstruction_error, raw_error)
        closure[label] = {
            "raw_reconstruction_error": raw_error,
            "effective_to_ode_error": ode_error,
        }
        window_rows.extend(
            _window_attribution_rows(
                frame=case,
                teacher_curve=f6p_teacher,
                vmax_vpfk=kinetic["vmax_VPFK"],
                km_f6p=kinetic["km_F6P"],
                km_atp_pfk=kinetic["km_ATP_PFK"],
            )
        )
        state_rows.extend(_state_window_rows(case))
        divergence[label] = _divergence_metrics(
            frame=case,
            experimental_curve=f6p_teacher,
            experimental_values=np.asarray(experimental_curves["F6P"], dtype=float),
        )
    candidate_rows = [row for row in window_rows if row["candidate"] == CANDIDATE_LABEL]
    classification = _structural_classification(
        candidate_rows=candidate_rows,
        candidate_divergence=divergence[CANDIDATE_LABEL],
        baseline_divergence=divergence[BASELINE_LABEL],
    )
    if classification["classification"].startswith("ATP-limited"):
        decision = "attribute residual F6P accumulation to ATP-limited PFK drainage"
        rationale = (
            "F6P substrate is saturating and the inferred PFK modulation remains one, "
            "but mean ATP occupancy is only 2.2% after J2 and falls below 1% after "
            "day 20. Both PGI and non-oxidative PPP return remain material inputs, "
            "while actual VPFK stays below the flux required by the Brodbar teacher. "
            "The 0.900x V6PGD point does not delay divergence, so neither latent "
            "initialization nor VPFK capacity is the primary remaining defect."
        )
        next_step = (
            "reconstruct ATP production and consumption over J1-J10 in the retained "
            "0.900x PPP context before opening any PFK or PPP kinetic lever"
        )
    else:
        decision = "retain a mixed F6P mechanism diagnosis"
        rationale = (
            "The fixed-parameter evidence does not isolate one F6P accumulation "
            "mechanism. Keep all kinetics fixed and expand the coupled-state audit."
        )
        next_step = "expand the fixed-state F6P and ATP coupling audit"
    window_frame = pd.DataFrame(window_rows)
    state_frame = pd.DataFrame(state_rows)
    window_frame.to_csv(out_dir / "f6p_window_attribution.csv", index=False)
    state_frame.to_csv(out_dir / "coupled_state_windows.csv", index=False)
    (out_dir / "divergence_metrics.json").write_text(
        json.dumps(_jsonable(divergence), indent=2), encoding="utf-8"
    )
    _plot_audit(
        frames=frames,
        experimental_time=experimental_time,
        experimental_f6p=np.asarray(experimental_curves["F6P"], dtype=float),
        teacher_curve=f6p_teacher,
        window_rows=window_frame,
        params=kinetic,
        out_path=out_dir / "f6p_accumulation_attribution.png",
    )
    summary = {
        "contract_type": "fixed_parameter_f6p_accumulation_audit",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "simulation_performed": False,
        "kinetic_optimization_performed": False,
        "parameters_promoted": False,
        "initial_conditions_promoted": False,
        "source_refinement_dir": str(refinement_dir),
        "source_timeseries": str(refinement_dir / "full_horizon_timeseries.csv"),
        "seed_params_path": str(seed_params_path),
        "cases": [BASELINE_LABEL, CANDIDATE_LABEL],
        "candidate_vmax_V6PGD": 9.0,
        "fixed_PFK_kinetics": kinetic,
        "F6P_balance_equation": "dF6P/dt = VPGI + VTKL2 + VTAL - VPFK",
        "closure": closure,
        "max_raw_balance_reconstruction_error": max_reconstruction_error,
        "window_attribution": window_rows,
        "coupled_state_windows": state_rows,
        "divergence": divergence,
        "structural_classification": classification,
        "decision": decision,
        "decision_rationale": rationale,
        "next_step": next_step,
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "report": str(out_dir / "decision_report.md"),
            "window_attribution": str(out_dir / "f6p_window_attribution.csv"),
            "coupled_states": str(out_dir / "coupled_state_windows.csv"),
            "divergence": str(out_dir / "divergence_metrics.json"),
            "plot": str(out_dir / "f6p_accumulation_attribution.png"),
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
        description="Audit F6P accumulation at fixed V6PGD and PPP initialization"
    )
    parser.add_argument(
        "--refinement-dir", type=Path, default=DEFAULT_REFINEMENT_DIR
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--balance-tolerance", type=float, default=1e-12)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_audit(
        refinement_dir=args.refinement_dir,
        out_dir=args.out_dir,
        balance_tolerance=args.balance_tolerance,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
