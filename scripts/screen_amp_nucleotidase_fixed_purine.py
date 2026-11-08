"""Screen optional AMP-to-ADO 5'-nucleotidase at fixed purine kinetics."""

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
from scipy.integrate import trapezoid
from scipy.interpolate import PchipInterpolator


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
DEFAULT_ANCHOR_SUMMARY = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "vmax_vampd1_vaprt_zero_screen_J1_J46"
    / "summary.json"
)
DEFAULT_OUT_DIR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "amp_nucleotidase_fixed_purine_J1_J46"
)
for path in (str(SRC), str(SCRIPTS)):
    if path not in sys.path:
        sys.path.insert(0, path)

from audit_atp_partition_vdpgm_3x_qss_b13pg import _build_contract  # noqa: E402
from audit_b13pg_balance_v6pgd_ppp_context import _effective_balance  # noqa: E402
from equadiff_brodbar import BRODBAR_METABOLITE_MAP, MODEL_NETWORK_VERSION  # noqa: E402
from evaluate_brodbar_candidate_full_panel import _load_brodbar_panel  # noqa: E402
from fla_integrated_flux import (  # noqa: E402
    build_integrated_flux_targets,
    integrated_flux_nrmse,
    irreversible_teacher_is_feasible,
)
from fla_validation_v2 import CandidateEvidence, evaluate_candidate, pareto_front  # noqa: E402
from profile_glycolysis_flux_bottlenecks import _jsonable, _simulate_and_track  # noqa: E402
import rbc_stoichiometry as STOICH  # noqa: E402


VMAX_GRID = (0.0, 0.005, 0.010, 0.015, 0.020, 0.030, 0.050)
PURINE_STATES = (
    "ATP",
    "ADP",
    "AMP",
    "IMP",
    "ADE",
    "EADE",
    "INO",
    "EINO",
    "HYPX",
    "EHYPX",
    "GMP",
    "SAH",
)
AMBIGUOUS_PANEL_STATES = {"B13PG", "P2G"}
INTEGRATED_WINDOWS = ((1.0, 11.0), (11.0, 22.0), (22.0, 46.0))


def _label(vmax: float) -> str:
    return f"vmax_VAMP_NT_{vmax:.3f}"


def _integral(values: np.ndarray, time: np.ndarray) -> float:
    return float(trapezoid(np.asarray(values, dtype=float), np.asarray(time, dtype=float)))


def _nrmse(model: np.ndarray, teacher: np.ndarray, full: np.ndarray) -> float:
    scale = max(float(np.mean(np.abs(full))), 0.01)
    return float(np.sqrt(np.mean((model - teacher) ** 2)) / scale)


def _relative_change(candidate: float, baseline: float) -> float:
    return float((candidate - baseline) / max(abs(baseline), 1e-12))


def _raw_state_balance(
    state: str, fluxes: Mapping[str, np.ndarray]
) -> np.ndarray:
    reactions = STOICH.REVERSE_INDEX[state]
    return sum(
        float(STOICH.STOICHIOMETRY[reaction][state])
        * np.asarray(fluxes[reaction], dtype=float)
        for reaction in reactions
    )


def _build_anchor(
    anchor_summary: Path,
) -> tuple[np.ndarray, dict[str, Any], Path, float]:
    state, _seed, params, seed_path = _build_contract()
    anchor = json.loads(anchor_summary.read_text(encoding="utf-8"))
    selected_vampd1 = float(anchor["selected_vmax_VAMPD1"])
    params = dict(params)
    params["vmax_VAPRT"] = 0.0
    params["vmax_VAMPD1"] = selected_vampd1
    params["purine_structure_mode"] = "amp_nucleotidase"
    params["vmax_VAMP_NT"] = 0.0
    return np.asarray(state, dtype=float), params, seed_path, selected_vampd1


def _simulate_candidate(
    *,
    label: str,
    state: np.ndarray,
    params: Mapping[str, Any],
    time: np.ndarray,
    exp_time: np.ndarray,
    curves: Mapping[str, np.ndarray],
    method: str,
    rtol: float,
    atol: float,
    closure_tolerance: float,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    sol, fluxes, derivatives = _simulate_and_track(
        params=params,
        t_eval=time,
        method=method,
        rtol=rtol,
        atol=atol,
        x0_override=state,
    )
    frame = pd.DataFrame({"candidate": label, "time_day": time})
    for reaction in (
        "VHK",
        "VPFK",
        "VPGK",
        "VPK",
        "VAK",
        "VGLNS",
        "VGLUCYS",
        "VGSS",
        "VRKa",
        "VPRPPASe",
        "VGMPS",
        "VGMPK",
        "VOPLAH",
        "VAMP_NT",
        "VAMPD1",
        "VAPRT",
        "VADSS",
        "VNDPK",
        "VIMPH",
        "Vnucleo2",
        "VAK2",
        "VSAM",
        "VADSL",
        "VADA",
        "VEADO",
        "VPNPase1",
        "VEINO",
        "VHGPRT1",
        "VEHYPX",
    ):
        frame[reaction] = np.asarray(fluxes[reaction], dtype=float)
    for name, index in BRODBAR_METABOLITE_MAP.items():
        if int(index) < sol.y.shape[0]:
            frame[name] = np.asarray(sol.y[int(index), :], dtype=float)

    teachers: dict[str, np.ndarray] = {}
    derivatives_teacher: dict[str, np.ndarray] = {}
    for name, values in curves.items():
        teacher = PchipInterpolator(exp_time, values)
        teachers[name] = np.asarray(teacher(time), dtype=float)
        derivatives_teacher[name] = np.asarray(teacher.derivative()(time), dtype=float)
        frame[f"{name}_teacher"] = teachers[name]

    total_model = sum(frame[name].to_numpy(dtype=float) for name in ("ATP", "ADP", "AMP"))
    total_teacher = sum(teachers[name] for name in ("ATP", "ADP", "AMP"))
    total_teacher_derivative = sum(
        derivatives_teacher[name] for name in ("ATP", "ADP", "AMP")
    )
    total_ode_derivative = sum(
        derivatives[int(BRODBAR_METABOLITE_MAP[name]), :]
        for name in ("ATP", "ADP", "AMP")
    )
    required_nt = (
        frame["VAK2"].to_numpy(dtype=float)
        - frame["VSAM"].to_numpy(dtype=float)
        + frame["VADSL"].to_numpy(dtype=float)
        + frame["VAPRT"].to_numpy(dtype=float)
        - frame["VAMPD1"].to_numpy(dtype=float)
        - total_teacher_derivative
    )
    frame["adenylate_total"] = total_model
    frame["adenylate_total_teacher"] = total_teacher
    frame["dadenylate_total_ode_dt"] = total_ode_derivative
    frame["dadenylate_total_teacher_dt"] = total_teacher_derivative
    frame["VAMP_NT_teacher"] = required_nt

    closures: dict[str, float] = {}
    for name in ("ATP", "ADP", "AMP", "ADO", "IMP", "GTP", "GDP", "ASP", "ADESUC"):
        concentration = frame[name].to_numpy(dtype=float)
        raw = _raw_state_balance(name, fluxes)
        effective, _damping = _effective_balance(raw, concentration)
        ode = np.asarray(derivatives[int(BRODBAR_METABOLITE_MAP[name]), :], dtype=float)
        closures[f"max_abs_{name}_closure_error"] = float(np.max(np.abs(effective - ode)))
    closures["max_abs_closure_error"] = max(closures.values())
    if closures["max_abs_closure_error"] > closure_tolerance:
        raise RuntimeError(f"Balance closure failed for {label}: {closures}")

    state_metrics: dict[str, dict[str, float]] = {}
    for name in PURINE_STATES:
        model = frame[name].to_numpy(dtype=float)
        teacher = teachers[name]
        state_metrics[name] = {
            "nrmse": _nrmse(model, teacher, np.asarray(curves[name], dtype=float)),
            "endpoint_error_mM": float(model[-1] - teacher[-1]),
            "model_change_mM": float(model[-1] - model[0]),
            "teacher_change_mM": float(teacher[-1] - teacher[0]),
        }
    total_full = sum(np.asarray(curves[name], dtype=float) for name in ("ATP", "ADP", "AMP"))
    total_slope_scale = max(float(np.mean(np.abs(total_teacher_derivative))), 0.01)
    total_metrics = {
        "nrmse": _nrmse(total_model, total_teacher, total_full),
        "slope_nrmse": float(
            np.sqrt(np.mean((total_ode_derivative - total_teacher_derivative) ** 2))
            / total_slope_scale
        ),
        "endpoint_error_mM": float(total_model[-1] - total_teacher[-1]),
        "model_change_mM": float(total_model[-1] - total_model[0]),
        "teacher_change_mM": float(total_teacher[-1] - total_teacher[0]),
    }
    flux_scale = max(float(np.mean(np.abs(required_nt))), 0.01)
    nt_flux = frame["VAMP_NT"].to_numpy(dtype=float)
    flux_metrics = {
        "nrmse": float(np.sqrt(np.mean((nt_flux - required_nt) ** 2)) / flux_scale),
        "integral_mM": _integral(nt_flux, time),
        "teacher_integral_mM": _integral(required_nt, time),
        "teacher_positive_time_fraction": float(np.mean(required_nt > 1e-12)),
    }
    measured_total = sum(
        np.asarray(curves[name], dtype=float) for name in ("ATP", "ADP", "AMP")
    )
    known_rate = (
        frame["VAK2"].to_numpy(dtype=float)
        - frame["VSAM"].to_numpy(dtype=float)
        + frame["VADSL"].to_numpy(dtype=float)
        + frame["VAPRT"].to_numpy(dtype=float)
        - frame["VAMPD1"].to_numpy(dtype=float)
    )
    integrated_targets = build_integrated_flux_targets(
        measurement_time=exp_time,
        measurement_values=measured_total,
        dense_time=time,
        known_rate=known_rate,
        model_unknown_rate=nt_flux,
        unknown_stoichiometric_coefficient=-1.0,
        windows=INTEGRATED_WINDOWS,
    )
    integrated_metrics = {
        "nrmse": integrated_flux_nrmse(integrated_targets),
        "irreversible_teacher_feasible": irreversible_teacher_is_feasible(
            integrated_targets
        ),
        "windows": [target.to_dict() for target in integrated_targets],
    }
    per_panel = {
        name: _nrmse(
            frame[name].to_numpy(dtype=float),
            teachers[name],
            np.asarray(curves[name], dtype=float),
        )
        for name in curves
        if name not in AMBIGUOUS_PANEL_STATES
    }
    panel_values = np.asarray(list(per_panel.values()), dtype=float)
    purine_values = np.asarray([state_metrics[name]["nrmse"] for name in PURINE_STATES])
    metrics = {
        "state_metrics": state_metrics,
        "adenylate_total": total_metrics,
        "VAMP_NT_flux": flux_metrics,
        "VAMP_NT_integrated_flux": integrated_metrics,
        "purine_panel_mean_nrmse": float(np.mean(purine_values)),
        "purine_panel_median_nrmse": float(np.median(purine_values)),
        "whole_panel_mean_nrmse": float(np.mean(panel_values)),
        "whole_panel_median_nrmse": float(np.median(panel_values)),
        "whole_panel_per_metabolite_nrmse": per_panel,
        "closures": closures,
        "minimum_state_mM": sol.raw_minimum_state_mM,
        "minimum_state_measured_before_clipping": True,
        "negative_state_sample_count": sol.negative_state_sample_count,
        "integrated_downstream_fluxes_mM": {
            reaction: _integral(frame[reaction].to_numpy(dtype=float), time)
            for reaction in (
                "VAMP_NT",
                "VADA",
                "VEADO",
                "VPNPase1",
                "VEINO",
                "VHGPRT1",
                "VEHYPX",
            )
        },
    }
    return frame, metrics


def _assess(
    metrics: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], str | None, dict[str, Any] | None]:
    baseline = metrics[_label(0.0)]
    rows: list[dict[str, Any]] = []
    protected = ("ATP", "ADP", "AMP", "IMP", "INO", "EINO", "HYPX", "EHYPX")
    for vmax in VMAX_GRID[1:]:
        label = _label(vmax)
        current = metrics[label]
        protected_degradation = max(
            _relative_change(
                current["state_metrics"][name]["nrmse"],
                baseline["state_metrics"][name]["nrmse"],
            )
            for name in protected
        )
        row = {
            "candidate": label,
            "vmax_VAMP_NT": vmax,
            "adenylate_total_nrmse": current["adenylate_total"]["nrmse"],
            "adenylate_total_slope_nrmse": current["adenylate_total"]["slope_nrmse"],
            "VAMP_NT_flux_nrmse": current["VAMP_NT_flux"]["nrmse"],
            "VAMP_NT_integrated_flux_nrmse": current["VAMP_NT_integrated_flux"]["nrmse"],
            "irreversible_teacher_feasible": current["VAMP_NT_integrated_flux"]["irreversible_teacher_feasible"],
            "purine_panel_mean_nrmse": current["purine_panel_mean_nrmse"],
            "whole_panel_mean_nrmse": current["whole_panel_mean_nrmse"],
            "whole_panel_median_nrmse": current["whole_panel_median_nrmse"],
            "trajectory_improvement": -_relative_change(
                current["adenylate_total"]["nrmse"],
                baseline["adenylate_total"]["nrmse"],
            ),
            "flux_improvement": -_relative_change(
                current["VAMP_NT_integrated_flux"]["nrmse"],
                baseline["VAMP_NT_integrated_flux"]["nrmse"],
            ),
            "slope_improves": current["adenylate_total"]["slope_nrmse"]
            < baseline["adenylate_total"]["slope_nrmse"],
            "endpoint_improves": abs(current["adenylate_total"]["endpoint_error_mM"])
            < abs(baseline["adenylate_total"]["endpoint_error_mM"]),
            "max_protected_nrmse_degradation": protected_degradation,
            "panel_mean_degradation": _relative_change(
                current["whole_panel_mean_nrmse"],
                baseline["whole_panel_mean_nrmse"],
            ),
            "panel_median_degradation": _relative_change(
                current["whole_panel_median_nrmse"],
                baseline["whole_panel_median_nrmse"],
            ),
            "numerical_pass": current["closures"]["max_abs_closure_error"] <= 1e-7
            and current["minimum_state_mM"] >= -1e-10,
        }
        row["diagnostic_guard_pass"] = bool(
            row["numerical_pass"]
            and row["trajectory_improvement"] >= 0.20
            and row["flux_improvement"] >= 0.15
            and row["irreversible_teacher_feasible"]
            and row["slope_improves"]
            and row["endpoint_improves"]
            and row["max_protected_nrmse_degradation"] <= 0.10
            and row["panel_mean_degradation"] <= 0.05
            and row["panel_median_degradation"] <= 0.05
        )
        rows.append(row)

    frontier_indices = pareto_front(
        rows,
        {
            "adenylate_total_nrmse": "min",
            "VAMP_NT_integrated_flux_nrmse": "min",
            "purine_panel_mean_nrmse": "min",
            "whole_panel_mean_nrmse": "min",
        },
    )
    for index, row in enumerate(rows):
        row["pareto_nondominated"] = index in frontier_indices
    eligible = [
        row for row in rows if row["diagnostic_guard_pass"] and row["pareto_nondominated"]
    ]
    selected_row = min(eligible, key=lambda row: row["vmax_VAMP_NT"], default=None)
    selected = str(selected_row["candidate"]) if selected_row else None
    return rows, selected, selected_row


def _plot(
    frames: Mapping[str, pd.DataFrame],
    rows: Sequence[Mapping[str, Any]],
    selected: str | None,
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(15.5, 8.5), constrained_layout=True)
    cmap = plt.get_cmap("viridis")
    labels = list(frames)
    for index, label in enumerate(labels):
        frame = frames[label]
        color = cmap(index / max(len(labels) - 1, 1))
        width = 2.5 if label == selected else 1.1
        alpha = 1.0 if label in {_label(0.0), selected} else 0.65
        axes[0, 0].plot(frame["time_day"], frame["adenylate_total"], color=color, lw=width, alpha=alpha, label=label)
        axes[0, 1].plot(frame["time_day"], frame["AMP"], color=color, lw=width, alpha=alpha)
        axes[0, 2].plot(frame["time_day"], frame["VAMP_NT"], color=color, lw=width, alpha=alpha)
        axes[1, 0].plot(frame["time_day"], frame["IMP"], color=color, lw=width, alpha=alpha)
        axes[1, 1].plot(frame["time_day"], frame["HYPX"] + frame["EHYPX"], color=color, lw=width, alpha=alpha)
    reference = frames[_label(0.0)]
    axes[0, 0].plot(reference["time_day"], reference["adenylate_total_teacher"], "k--", lw=2, label="Brodbar")
    axes[0, 1].plot(reference["time_day"], reference["AMP_teacher"], "k--", lw=2)
    axes[0, 2].plot(reference["time_day"], reference["VAMP_NT_teacher"], "k--", lw=2)
    axes[1, 0].plot(reference["time_day"], reference["IMP_teacher"], "k--", lw=2)
    axes[1, 1].plot(reference["time_day"], reference["HYPX_teacher"] + reference["EHYPX_teacher"], "k--", lw=2)
    x = [row["vmax_VAMP_NT"] for row in rows]
    axes[1, 2].plot(x, [row["adenylate_total_nrmse"] for row in rows], "o-", label="A-total")
    axes[1, 2].plot(x, [row["VAMP_NT_integrated_flux_nrmse"] for row in rows], "s-", label="integrated flux")
    axes[1, 2].plot(x, [row["purine_panel_mean_nrmse"] for row in rows], "^-", label="purine panel")
    titles = (
        "ATP + ADP + AMP",
        "AMP",
        "AMP 5'-nucleotidase",
        "IMP safeguard",
        "HYPX + EHYPX",
        "Deterministic screen",
    )
    for axis, title in zip(axes.flat, titles):
        axis.set_title(title)
        axis.grid(alpha=0.2)
        axis.set_xlabel("Storage day" if axis is not axes[1, 2] else "vmax VAMP_NT")
    axes[0, 0].legend(fontsize=7, ncol=2)
    axes[1, 2].legend(fontsize=8)
    for axis in (axes[0, 0], axes[0, 1], axes[1, 0], axes[1, 1]):
        axis.set_ylabel("Concentration (mM)")
    axes[0, 2].set_ylabel("Flux (mM/day)")
    axes[1, 2].set_ylabel("Normalized error")
    fig.suptitle("Fixed-kinetic structural screen: AMP -> ADO", fontsize=15)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def run_screen(
    *,
    anchor_summary: Path,
    out_dir: Path,
    points: int,
    method: str,
    rtol: float,
    atol: float,
    closure_tolerance: float,
) -> dict[str, Any]:
    state, anchor_params, seed_path, selected_vampd1 = _build_anchor(anchor_summary)
    exp_time, curves, _order, _indices, unmapped = _load_brodbar_panel()
    time = np.unique(np.concatenate([np.linspace(1.0, 46.0, points), exp_time]))
    frames: dict[str, pd.DataFrame] = {}
    metrics: dict[str, dict[str, Any]] = {}
    parameter_sets: dict[str, dict[str, Any]] = {}
    for vmax in VMAX_GRID:
        label = _label(vmax)
        params = dict(anchor_params)
        params["vmax_VAMP_NT"] = float(vmax)
        parameter_sets[label] = params
        print(f"[AMP-NT] replay {label}", flush=True)
        frames[label], metrics[label] = _simulate_candidate(
            label=label,
            state=state,
            params=params,
            time=time,
            exp_time=exp_time,
            curves=curves,
            method=method,
            rtol=rtol,
            atol=atol,
            closure_tolerance=closure_tolerance,
        )
    rows, selected, selected_row = _assess(metrics)
    baseline = metrics[_label(0.0)]
    validation = None
    if selected is not None and selected_row is not None:
        chosen = metrics[selected]
        validation = evaluate_candidate(
            CandidateEvidence(
                candidate_id=selected,
                training_datasets=("brodbar_J1_J46",),
                temporal_validation_datasets=(),
                external_validation_datasets=(),
                data_contract_complete=False,
                exact_balance_max_error_mM_per_day=chosen["closures"]["max_abs_closure_error"],
                minimum_state_mM=chosen["minimum_state_mM"],
                independent_teachers_compatible=False,
                sensitivity_block_identifiable=False,
                primary_trajectory_baseline=baseline["adenylate_total"]["nrmse"],
                primary_trajectory_candidate=chosen["adenylate_total"]["nrmse"],
                primary_flux_baseline=baseline["VAMP_NT_integrated_flux"]["nrmse"],
                primary_flux_candidate=chosen["VAMP_NT_integrated_flux"]["nrmse"],
                all_primary_endpoints_improve=bool(selected_row["endpoint_improves"]),
                all_primary_slopes_improve=bool(selected_row["slope_improves"]),
                max_protected_nrmse_degradation=float(selected_row["max_protected_nrmse_degradation"]),
                panel_mean_nrmse_degradation=float(selected_row["panel_mean_degradation"]),
                panel_median_nrmse_degradation=float(selected_row["panel_median_degradation"]),
                strict_solver_invariant=False,
                temporal_holdout_improves=None,
                external_holdout_improves=None,
                complexity_supported_by_prediction=None,
            )
        ).to_dict()

    out_dir.mkdir(parents=True, exist_ok=True)
    pd.concat(frames.values(), ignore_index=True).to_csv(out_dir / "J1_J46_timeseries.csv", index=False)
    pd.DataFrame(rows).to_csv(out_dir / "candidate_metrics.csv", index=False)
    (out_dir / "candidate_parameter_sets.json").write_text(
        json.dumps(_jsonable(parameter_sets), indent=2), encoding="utf-8"
    )
    _plot(frames, rows, selected, out_dir / "amp_nucleotidase_screen.png")
    if selected:
        decision = "retain the selected AMP-to-ADO capacity as a structural diagnostic only"
        rationale = (
            "The candidate passes the local concentration, slope, flux, protected-purine, panel, "
            "and numerical guards. Global promotion remains blocked because ADE/EADE ownership, "
            "identifiability, temporal holdout, strict solver, and external validation are unresolved."
        )
    else:
        decision = "reject AMP-to-ADO capacity alone under fixed purine kinetics"
        rationale = "No deterministic capacity passes all local diagnostic guards."
    summary = {
        "contract_type": "deterministic_optional_AMP_nucleotidase_fixed_purine_screen",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_network_version": MODEL_NETWORK_VERSION,
        "optimization_performed": False,
        "parameters_promoted": False,
        "anchor_summary": str(anchor_summary.resolve()),
        "seed_params_path": str(seed_path),
        "fixed_vmax_VAPRT": 0.0,
        "fixed_vmax_VAMPD1": selected_vampd1,
        "fixed_purine_structure_mode": "amp_nucleotidase",
        "vmax_grid": list(VMAX_GRID),
        "integrated_flux_windows": [list(window) for window in INTEGRATED_WINDOWS],
        "dense_derivative_role": "diagnostic_only",
        "solver": {"method": method, "rtol": rtol, "atol": atol, "points": points},
        "unmapped_panel_states": unmapped,
        "metrics": metrics,
        "assessment_rows": rows,
        "selected_candidate": selected,
        "selected_vmax_VAMP_NT": parameter_sets[selected]["vmax_VAMP_NT"] if selected else None,
        "validation_v2": validation,
        "decision": decision,
        "decision_rationale": rationale,
        "next_step": (
            "if retained, repeat with strict solver and then compare the APRT-rich versus "
            "EADE-loss-rich structural corners; otherwise audit another measured adenylate exit"
        ),
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "report": str(out_dir / "decision_report.md"),
            "metrics": str(out_dir / "candidate_metrics.csv"),
            "timeseries": str(out_dir / "J1_J46_timeseries.csv"),
            "plot": str(out_dir / "amp_nucleotidase_screen.png"),
        },
    }
    (out_dir / "summary.json").write_text(
        json.dumps(_jsonable(summary), indent=2), encoding="utf-8"
    )
    report = [
        "# Fixed-purine AMP 5'-nucleotidase screen",
        "",
        "- Optional `AMP -> ADO` branch enabled; default ODE behavior remains unchanged.",
        f"- VAPRT fixed at zero and VAMPD1 fixed at `{selected_vampd1:.7g}`.",
        f"- Deterministic capacities: `{', '.join(f'{value:.3f}' for value in VMAX_GRID)}`.",
        "- Primary flux evidence uses measured-endpoint balances on J1-J11, J11-J22, and J22-J46.",
        "- Dense PCHIP derivatives are diagnostic only.",
        "- No optimizer or parameter promotion.",
        "",
        f"Selected diagnostic: `{selected or 'none'}`.",
        "",
        decision,
        "",
        rationale,
    ]
    (out_dir / "decision_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "selected_candidate": selected,
                "decision": decision,
                "validation_v2_status": validation["status"] if validation else None,
                "summary": str(out_dir / "summary.json"),
            },
            indent=2,
        )
    )
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchor-summary", type=Path, default=DEFAULT_ANCHOR_SUMMARY)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--points", type=int, default=901)
    parser.add_argument("--method", default="BDF")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    parser.add_argument("--closure-tolerance", type=float, default=1e-7)
    args = parser.parse_args(argv)
    run_screen(
        anchor_summary=args.anchor_summary,
        out_dir=args.out_dir,
        points=args.points,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
        closure_tolerance=args.closure_tolerance,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
