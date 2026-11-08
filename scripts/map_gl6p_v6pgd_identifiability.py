"""Map the GL6P(0)-V6PGD initial-rate ridge and replay representative points."""

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
from matplotlib.colors import LogNorm, SymLogNorm
import numpy as np
import pandas as pd


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
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "gl6p_v6pgd_identifiability_J1_J2"
)

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from equadiff_brodbar import BRODBAR_METABOLITE_MAP, mm  # noqa: E402
from MM_calibration import load_initial_conditions  # noqa: E402
from profile_atp_consumption_sinks import _all_experimental_curves  # noqa: E402
from profile_glycolysis_flux_bottlenecks import (  # noqa: E402
    _jsonable,
    _load_params,
    _simulate_and_track,
)
from run_glucose_utilization_fla import _nrmse  # noqa: E402
from audit_complete_ppp_fla import (  # noqa: E402
    _build_net_flux_teachers,
    _build_timeseries,
    _net_teacher_metric,
)
from diagnose_ppp_initial_conditions import (  # noqa: E402
    _historical_latent_ppp_state,
    _historical_values,
)
from screen_vmax_v6pgd_feasibility import NADPH_INDEX, NADP_INDEX  # noqa: E402


GL6P_INDEX = int(BRODBAR_METABOLITE_MAP["GL6P"])
GO6P_INDEX = int(BRODBAR_METABOLITE_MAP["GO6P"])
REPLAY_GL6P = (
    7.62e-6,
    1e-4,
    3e-4,
    5e-4,
    7e-4,
    1e-3,
    1.2e-3,
    1.3e-3,
    1.4e-3,
    1.5e-3,
    1.6e-3,
    1.7e-3,
    1.8e-3,
    2e-3,
    3e-3,
    5e-3,
    1e-2,
    1e-1,
    3e-1,
    1.0,
)
BACKGROUND_CURRENT = "current_other_latent"
BACKGROUND_HISTORICAL = "historical_other_latent"
TRACKED_POOLS = ("GO6P", "G6P", "F6P", "RU5P")


def _kinetic_constants(params: Mapping[str, Any]) -> dict[str, float]:
    return {
        "vmax_VPGLS": float(params.get("vmax_VPGLS", 4.111138)),
        "km_GL6P": float(params.get("km_GL6P", 0.1)),
        "km_GO6P": float(params.get("km_GO6P", 0.02)),
        "km_NADP_NADPH": float(params.get("km_NADP_NADPH", 1.0)),
    }


def _initial_rate_components(
    *,
    gl6p: float,
    vmax_v6pgd: float,
    go6p: float,
    nadp: float,
    nadph: float,
    constants: Mapping[str, float],
) -> tuple[float, float, float]:
    vpgls = float(constants["vmax_VPGLS"]) * mm(
        float(gl6p), float(constants["km_GL6P"])
    )
    redox_ratio = float(nadp) / (float(nadph) + 1e-6)
    v6pgd = (
        float(vmax_v6pgd)
        * mm(float(go6p), float(constants["km_GO6P"]))
        * mm(redox_ratio, float(constants["km_NADP_NADPH"]))
    )
    return vpgls, v6pgd, vpgls - v6pgd


def _required_vmax_v6pgd(
    *,
    gl6p: float,
    teacher_flux: float,
    go6p: float,
    nadp: float,
    nadph: float,
    constants: Mapping[str, float],
) -> float:
    vpgls, unit_v6pgd, _ = _initial_rate_components(
        gl6p=gl6p,
        vmax_v6pgd=1.0,
        go6p=go6p,
        nadp=nadp,
        nadph=nadph,
        constants=constants,
    )
    return max((vpgls - float(teacher_flux)) / max(unit_v6pgd, 1e-30), 0.0)


def _dense_map(
    *,
    gl6p_values: np.ndarray,
    vmax_values: np.ndarray,
    teacher_flux: float,
    go6p: float,
    nadp: float,
    nadph: float,
    constants: Mapping[str, float],
) -> tuple[list[dict[str, float]], list[dict[str, float]], np.ndarray]:
    rows: list[dict[str, float]] = []
    ridge_rows: list[dict[str, float]] = []
    residual_grid = np.empty((gl6p_values.size, vmax_values.size), dtype=float)
    for i, gl6p in enumerate(gl6p_values):
        required = _required_vmax_v6pgd(
            gl6p=float(gl6p),
            teacher_flux=teacher_flux,
            go6p=go6p,
            nadp=nadp,
            nadph=nadph,
            constants=constants,
        )
        vpgls, matched_v6pgd, matched_net = _initial_rate_components(
            gl6p=float(gl6p),
            vmax_v6pgd=required,
            go6p=go6p,
            nadp=nadp,
            nadph=nadph,
            constants=constants,
        )
        ridge_rows.append(
            {
                "GL6P_initial": float(gl6p),
                "required_vmax_V6PGD": required,
                "VPGLS_initial": vpgls,
                "V6PGD_initial": matched_v6pgd,
                "dGO6P_initial": matched_net,
                "teacher_residual": matched_net - float(teacher_flux),
            }
        )
        for j, vmax in enumerate(vmax_values):
            vpgls, v6pgd, net = _initial_rate_components(
                gl6p=float(gl6p),
                vmax_v6pgd=float(vmax),
                go6p=go6p,
                nadp=nadp,
                nadph=nadph,
                constants=constants,
            )
            residual = net - float(teacher_flux)
            residual_grid[i, j] = residual
            rows.append(
                {
                    "GL6P_initial": float(gl6p),
                    "vmax_V6PGD": float(vmax),
                    "VPGLS_initial": vpgls,
                    "V6PGD_initial": v6pgd,
                    "dGO6P_initial": net,
                    "teacher_dGO6P_initial": float(teacher_flux),
                    "teacher_residual": residual,
                }
            )
    return rows, ridge_rows, residual_grid


def _window_teacher(
    teachers: Mapping[str, Any], pool: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    time = np.asarray(teachers["dense_timepoints"], dtype=float)
    mask = (time >= 1.0) & (time <= 2.0)
    curve = teachers["curves"][pool]
    return (
        time[mask],
        np.asarray(curve["dense_concentration"], dtype=float)[mask],
        np.asarray(curve["dense_net_flux"], dtype=float)[mask],
    )


def _case_metrics(
    *,
    label: str,
    background: str,
    gl6p: float,
    vmax_v6pgd: float,
    frame: pd.DataFrame,
    teachers: Mapping[str, Any],
) -> dict[str, Any]:
    model_time = frame["time_day"].to_numpy(dtype=float)
    metrics: dict[str, Any] = {
        "candidate": label,
        "background": background,
        "GL6P_initial": float(gl6p),
        "vmax_V6PGD": float(vmax_v6pgd),
        "NADP_minimum": float(frame["NADP"].min()),
        "NADPH_minimum": float(frame["NADPH"].min()),
        "NADP_NADPH_max_drift": float(
            np.max(
                np.abs(
                    frame["NADP"].to_numpy(dtype=float)
                    + frame["NADPH"].to_numpy(dtype=float)
                    - float(frame["NADP"].iloc[0] + frame["NADPH"].iloc[0])
                )
            )
        ),
        "VPGLS_initial": float(frame["VPGLS"].iloc[0]),
        "V6PGD_initial": float(frame["V6PGD"].iloc[0]),
        "dGO6P_initial": float(frame["dGO6P_dt_effective_flux"].iloc[0]),
    }
    for pool in ("GO6P", "G6P", "F6P"):
        teacher_time, teacher_concentration, teacher_flux = _window_teacher(
            teachers, pool
        )
        model_concentration = np.interp(
            teacher_time, model_time, frame[pool].to_numpy(dtype=float)
        )
        model_flux = np.interp(
            teacher_time,
            model_time,
            frame[f"d{pool}_dt_effective_flux"].to_numpy(dtype=float),
        )
        concentration_metric = _nrmse(model_concentration, teacher_concentration)
        flux_metric = _net_teacher_metric(model_flux, teacher_flux)
        metrics[f"{pool}_concentration_nrmse"] = float(
            concentration_metric["nrmse"]
        )
        metrics[f"{pool}_teacher_nrmse"] = float(flux_metric["nrmse"])
        metrics[f"{pool}_teacher_sign_agreement"] = float(
            flux_metric["sign_agreement"]
        )
        metrics[f"{pool}_final"] = float(frame[pool].iloc[-1])
    metrics["RU5P_final"] = float(frame["RU5P"].iloc[-1])
    metrics["redox_valid"] = bool(
        metrics["NADP_minimum"] >= -1e-10
        and metrics["NADPH_minimum"] >= -1e-10
        and metrics["NADP_NADPH_max_drift"] <= 1e-9
    )
    metrics["composite_score"] = float(
        metrics["GO6P_teacher_nrmse"]
        + metrics["GO6P_concentration_nrmse"]
        + 0.15
        * (
            metrics["G6P_concentration_nrmse"]
            + metrics["F6P_concentration_nrmse"]
        )
    )
    metrics["GO6P_shape_pass"] = bool(
        metrics["GO6P_teacher_nrmse"] <= 1.0
        and metrics["GO6P_concentration_nrmse"] <= 0.5
        and metrics["GO6P_teacher_sign_agreement"] >= 0.8
    )
    return metrics


def _case_label(background: str, gl6p: float) -> str:
    return f"{background}__GL6P_{gl6p:.3e}"


def _decision(
    metrics: Sequence[Mapping[str, Any]], ridge_rows: Sequence[Mapping[str, Any]]
) -> tuple[str, str, dict[str, str], str | None]:
    best_by_background: dict[str, str] = {}
    for background in (BACKGROUND_CURRENT, BACKGROUND_HISTORICAL):
        candidates = [row for row in metrics if row["background"] == background]
        best = min(candidates, key=lambda row: float(row["composite_score"]))
        best_by_background[background] = str(best["candidate"])
    robust_gl6p: list[float] = []
    for gl6p in REPLAY_GL6P:
        pair = [
            row
            for row in metrics
            if np.isclose(float(row["GL6P_initial"]), gl6p, rtol=0.0, atol=1e-15)
        ]
        if len(pair) == 2 and all(
            bool(row["GO6P_shape_pass"]) and bool(row["redox_valid"])
            for row in pair
        ):
            robust_gl6p.append(float(gl6p))
    ridge_vmax = np.asarray(
        [float(row["required_vmax_V6PGD"]) for row in ridge_rows], dtype=float
    )
    ridge_span = float(np.max(ridge_vmax) / max(np.min(ridge_vmax), 1e-30))
    if robust_gl6p:
        return (
            "retain a conditional GL6P-V6PGD ridge, but do not calibrate V6PGD alone",
            f"J1-J2 dynamics retain {len(robust_gl6p)} cross-background GO6P-compatible ridge point(s), while the required V6PGD capacity spans {ridge_span:.1f}-fold. The data constrain a coupled ridge rather than a unique kinetic constant.",
            best_by_background,
            f"GL6P(0)={robust_gl6p[0]:.6g} mM",
        )
    return (
        "replace the generic latent initialization before further PPP kinetic learning",
        f"No teacher-matched ridge point preserves GO6P shape in both latent-pool backgrounds, and the required V6PGD capacity spans {ridge_span:.1f}-fold. A transferable V6PGD constant is not identifiable without an initialization layer.",
        best_by_background,
        None,
    )


def _plot_map(
    *,
    gl6p_grid: np.ndarray,
    vmax_grid: np.ndarray,
    residual_grid: np.ndarray,
    ridge_rows: Sequence[Mapping[str, Any]],
    replay_rows: Sequence[Mapping[str, Any]],
    out_path: Path,
) -> None:
    fig, axis = plt.subplots(figsize=(9.5, 6.4), constrained_layout=True)
    scale = max(float(np.nanmax(np.abs(residual_grid))), 1e-3)
    mesh = axis.pcolormesh(
        vmax_grid,
        gl6p_grid,
        residual_grid,
        shading="auto",
        cmap="coolwarm",
        norm=SymLogNorm(linthresh=1e-3, vmin=-scale, vmax=scale),
    )
    ridge_gl6p = [float(row["GL6P_initial"]) for row in ridge_rows]
    ridge_vmax = [float(row["required_vmax_V6PGD"]) for row in ridge_rows]
    axis.plot(ridge_vmax, ridge_gl6p, color="#111827", linewidth=2.4, label="Exact J1 teacher ridge")
    axis.scatter(
        [float(row["required_vmax_V6PGD"]) for row in replay_rows],
        [float(row["GL6P_initial"]) for row in replay_rows],
        color="#facc15",
        edgecolor="#111827",
        s=62,
        zorder=5,
        label="J1-J2 replay points",
    )
    axis.set_xscale("log")
    axis.set_yscale("log")
    axis.set_xlabel("vmax_V6PGD")
    axis.set_ylabel("GL6P initial concentration (mM)")
    axis.set_title("J1 residual: model dGO6P/dt minus Brodbar teacher")
    axis.legend(frameon=False)
    colorbar = fig.colorbar(mesh, ax=axis)
    colorbar.set_label("Teacher residual (mM/day)")
    fig.savefig(out_path, dpi=190)
    plt.close(fig)


def _plot_replays(
    *,
    frames: Mapping[str, pd.DataFrame],
    metrics: Sequence[Mapping[str, Any]],
    teachers: Mapping[str, Any],
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), constrained_layout=True)
    color_map = plt.get_cmap("viridis")
    color_norm = LogNorm(vmin=min(REPLAY_GL6P), vmax=max(REPLAY_GL6P))
    teacher_time, teacher_concentration, teacher_flux = _window_teacher(
        teachers, "GO6P"
    )
    for column, background in enumerate(
        (BACKGROUND_CURRENT, BACKGROUND_HISTORICAL)
    ):
        concentration_axis = axes[0, column]
        flux_axis = axes[1, column]
        for row in metrics:
            if row["background"] != background:
                continue
            gl6p = float(row["GL6P_initial"])
            frame = frames[str(row["candidate"])]
            color = color_map(color_norm(gl6p))
            concentration_axis.plot(
                frame["time_day"], frame["GO6P"], color=color, linewidth=1.6
            )
            flux_axis.plot(
                frame["time_day"],
                frame["dGO6P_dt_effective_flux"],
                color=color,
                linewidth=1.8,
            )
        concentration_axis.plot(
            teacher_time,
            teacher_concentration,
            color="#111827",
            linestyle="--",
            linewidth=2.2,
            label="Brodbar PCHIP",
        )
        flux_axis.plot(
            teacher_time,
            teacher_flux,
            color="#111827",
            linestyle="--",
            linewidth=2.2,
            label="Brodbar teacher",
        )
        concentration_axis.set_title(f"GO6P concentration: {background}")
        flux_axis.set_title(f"GO6P net flux: {background}")
        concentration_axis.set_ylabel("mM")
        flux_axis.set_ylabel("mM/day")
        flux_axis.set_xlabel("Time (day)")
        for axis in (concentration_axis, flux_axis):
            axis.grid(alpha=0.22)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=2, frameon=False)
    colorbar = fig.colorbar(
        plt.cm.ScalarMappable(norm=color_norm, cmap=color_map),
        ax=axes,
        location="bottom",
        shrink=0.65,
        pad=0.08,
    )
    colorbar.set_label("GL6P initial concentration (mM)")
    fig.suptitle("Teacher-matched GL6P(0)-V6PGD ridge replays")
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    lines = [
        "# GL6P(0)-V6PGD identifiability map",
        "",
        "## Contract",
        "",
        "- Fixed diagnostic grid and exact J1 balance; no optimization or promotion.",
        f"- GL6P range: `{summary['gl6p_grid'][0]:.6g} .. {summary['gl6p_grid'][-1]:.6g}` mM.",
        f"- V6PGD capacity range: `{summary['vmax_grid'][0]:.6g} .. {summary['vmax_grid'][-1]:.6g}`.",
        f"- J1 teacher: `{summary['teacher_dGO6P_initial']:.6g}` mM/day.",
        f"- Maximum ten-pool replay closure error: `{summary['max_pointwise_closure_error']:.3e}` mM/day.",
        "",
        "## Ridge replays",
        "",
        "| Background | GL6P(0) | Required vmax V6PGD | GO6P concentration nRMSE | GO6P teacher nRMSE | Sign agreement | Composite score |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary["replay_metrics"]:
        lines.append(
            f"| `{row['background']}` | {row['GL6P_initial']:.6g} | {row['vmax_V6PGD']:.6g} | "
            f"{row['GO6P_concentration_nrmse']:.4f} | {row['GO6P_teacher_nrmse']:.4f} | "
            f"{100 * row['GO6P_teacher_sign_agreement']:.1f}% | {row['composite_score']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"**`{summary['decision']}`**",
            "",
            str(summary["decision_rationale"]),
            "",
            f"Best by background: `{json.dumps(summary['best_by_background'], sort_keys=True)}`.",
            f"Cross-background compatible region: `{summary['cross_background_compatible_region']}`.",
            "",
            "No kinetic or initial-condition artifact was promoted.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_map(
    *,
    out_dir: Path,
    seed_params_path: Path,
    gl6p_grid_points: int,
    vmax_grid_points: int,
    timepoints: int,
    teacher_dense_points: int,
    method: str,
    rtol: float,
    atol: float,
    closure_tolerance: float,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    seed_params = _load_params(seed_params_path)
    constants = _kinetic_constants(seed_params)
    current_x0 = np.asarray(load_initial_conditions(), dtype=float)
    historical_x0, historical_changes = _historical_latent_ppp_state(
        current_x0, _historical_values()
    )
    exp_time, exp_curves = _all_experimental_curves(46.0)
    teachers = _build_net_flux_teachers(
        exp_time, exp_curves, dense_points=teacher_dense_points
    )
    teacher_time, _, teacher_flux = _window_teacher(teachers, "GO6P")
    teacher_initial = float(teacher_flux[0])
    go6p_initial = float(current_x0[GO6P_INDEX])
    nadp_initial = float(current_x0[NADP_INDEX])
    nadph_initial = float(current_x0[NADPH_INDEX])

    gl6p_grid = np.geomspace(REPLAY_GL6P[0], REPLAY_GL6P[-1], int(gl6p_grid_points))
    replay_ridge = [
        {
            "GL6P_initial": float(gl6p),
            "required_vmax_V6PGD": _required_vmax_v6pgd(
                gl6p=float(gl6p),
                teacher_flux=teacher_initial,
                go6p=go6p_initial,
                nadp=nadp_initial,
                nadph=nadph_initial,
                constants=constants,
            ),
        }
        for gl6p in REPLAY_GL6P
    ]
    replay_vmax = np.asarray(
        [float(row["required_vmax_V6PGD"]) for row in replay_ridge], dtype=float
    )
    vmax_grid = np.geomspace(
        max(float(np.min(replay_vmax)) * 0.5, 1e-4),
        float(np.max(replay_vmax)) * 1.2,
        int(vmax_grid_points),
    )
    map_rows, ridge_rows, residual_grid = _dense_map(
        gl6p_values=gl6p_grid,
        vmax_values=vmax_grid,
        teacher_flux=teacher_initial,
        go6p=go6p_initial,
        nadp=nadp_initial,
        nadph=nadph_initial,
        constants=constants,
    )

    backgrounds = {
        BACKGROUND_CURRENT: current_x0,
        BACKGROUND_HISTORICAL: historical_x0,
    }
    t_eval = np.linspace(1.0, 2.0, int(timepoints))
    frames: dict[str, pd.DataFrame] = {}
    replay_metrics: list[dict[str, Any]] = []
    case_contracts: list[dict[str, Any]] = []
    closure_by_case: dict[str, dict[str, float]] = {}
    for background, background_x0 in backgrounds.items():
        for replay in replay_ridge:
            gl6p = float(replay["GL6P_initial"])
            vmax_v6pgd = float(replay["required_vmax_V6PGD"])
            label = _case_label(background, gl6p)
            x0 = np.asarray(background_x0, dtype=float).copy()
            x0[GL6P_INDEX] = gl6p
            params = dict(seed_params)
            params["vmax_V6PGD"] = vmax_v6pgd
            print(f"[gl6p-v6pgd-map] simulating {label}", flush=True)
            sol, fluxes, derivatives = _simulate_and_track(
                params=params,
                t_eval=t_eval,
                method=method,
                rtol=rtol,
                atol=atol,
                x0_override=x0,
            )
            frame, closure = _build_timeseries(
                label=label,
                sol=sol,
                fluxes=fluxes,
                derivatives=derivatives,
                closure_tolerance=closure_tolerance,
            )
            frame["NADP"] = np.asarray(sol.y[NADP_INDEX, :], dtype=float)
            frame["NADPH"] = np.asarray(sol.y[NADPH_INDEX, :], dtype=float)
            frames[label] = frame
            closure_by_case[label] = closure
            replay_metrics.append(
                _case_metrics(
                    label=label,
                    background=background,
                    gl6p=gl6p,
                    vmax_v6pgd=vmax_v6pgd,
                    frame=frame,
                    teachers=teachers,
                )
            )
            state_changes = ["GL6P"]
            if background == BACKGROUND_HISTORICAL:
                state_changes = sorted(
                    set(state_changes)
                    | {str(change["pool"]) for change in historical_changes}
                )
            case_contracts.append(
                {
                    "candidate": label,
                    "background": background,
                    "changed_kinetic_constants": ["vmax_V6PGD"],
                    "changed_initial_states_relative_to_current": state_changes,
                    "GL6P_initial": gl6p,
                    "vmax_V6PGD": vmax_v6pgd,
                }
            )

    decision, rationale, best_by_background, compatible_region = _decision(
        replay_metrics, ridge_rows
    )
    max_closure = max(
        value for case in closure_by_case.values() for value in case.values()
    )
    map_path = out_dir / "gl6p_v6pgd_initial_rate_map.csv"
    ridge_path = out_dir / "gl6p_v6pgd_teacher_ridge.csv"
    metrics_path = out_dir / "gl6p_v6pgd_replay_metrics.csv"
    timeseries_path = out_dir / "gl6p_v6pgd_replay_timeseries.csv"
    map_plot_path = out_dir / "gl6p_v6pgd_identifiability_map.png"
    replay_plot_path = out_dir / "gl6p_v6pgd_ridge_replays.png"
    pd.DataFrame(map_rows).to_csv(map_path, index=False)
    pd.DataFrame(ridge_rows).to_csv(ridge_path, index=False)
    pd.DataFrame(replay_metrics).to_csv(metrics_path, index=False)
    pd.concat(frames.values(), ignore_index=True).to_csv(timeseries_path, index=False)
    _plot_map(
        gl6p_grid=gl6p_grid,
        vmax_grid=vmax_grid,
        residual_grid=residual_grid,
        ridge_rows=ridge_rows,
        replay_rows=replay_ridge,
        out_path=map_plot_path,
    )
    _plot_replays(
        frames=frames,
        metrics=replay_metrics,
        teachers=teachers,
        out_path=replay_plot_path,
    )
    ridge_vmax = np.asarray(
        [float(row["required_vmax_V6PGD"]) for row in ridge_rows], dtype=float
    )
    summary = {
        "contract_type": "gl6p_v6pgd_identifiability_map",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "optimization_performed": False,
        "parameters_promoted": False,
        "initial_conditions_promoted": False,
        "seed_params_path": str(seed_params_path),
        "teacher_dGO6P_initial": teacher_initial,
        "teacher_time_window": [float(teacher_time[0]), float(teacher_time[-1])],
        "kinetic_constants": constants,
        "gl6p_grid": gl6p_grid.tolist(),
        "vmax_grid": vmax_grid.tolist(),
        "replay_gl6p": list(REPLAY_GL6P),
        "ridge_vmax_min": float(np.min(ridge_vmax)),
        "ridge_vmax_max": float(np.max(ridge_vmax)),
        "ridge_vmax_fold_span": float(
            np.max(ridge_vmax) / max(np.min(ridge_vmax), 1e-30)
        ),
        "case_contracts": case_contracts,
        "closure_by_case": closure_by_case,
        "max_pointwise_closure_error": max_closure,
        "ridge_rows": ridge_rows,
        "replay_metrics": replay_metrics,
        "decision": decision,
        "decision_rationale": rationale,
        "best_by_background": best_by_background,
        "cross_background_compatible_region": compatible_region,
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "report": str(out_dir / "decision_report.md"),
            "initial_rate_map": str(map_path),
            "teacher_ridge": str(ridge_path),
            "replay_metrics": str(metrics_path),
            "replay_timeseries": str(timeseries_path),
            "identifiability_plot": str(map_plot_path),
            "replay_plot": str(replay_plot_path),
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
                "ridge_vmax_fold_span": summary["ridge_vmax_fold_span"],
                "best_by_background": best_by_background,
                "cross_background_compatible_region": compatible_region,
                "max_closure": max_closure,
            },
            indent=2,
        ),
        flush=True,
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Map GL6P(0)-V6PGD identifiability")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--seed-params", type=Path, default=DEFAULT_SEED_PARAMS)
    parser.add_argument("--gl6p-grid-points", type=int, default=61)
    parser.add_argument("--vmax-grid-points", type=int, default=81)
    parser.add_argument("--timepoints", type=int, default=241)
    parser.add_argument("--teacher-dense-points", type=int, default=9001)
    parser.add_argument("--method", default="LSODA")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    parser.add_argument("--closure-tolerance", type=float, default=1e-12)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_map(
        out_dir=args.out_dir,
        seed_params_path=args.seed_params,
        gl6p_grid_points=args.gl6p_grid_points,
        vmax_grid_points=args.vmax_grid_points,
        timepoints=args.timepoints,
        teacher_dense_points=args.teacher_dense_points,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
        closure_tolerance=args.closure_tolerance,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
