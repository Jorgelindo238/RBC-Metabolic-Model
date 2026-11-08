"""Screen ``km_ADP_ATP`` as an ATP-production lever before optimization.

Each directed replay uses the native FluxTracker to measure VPGK, VPK, VAK,
and the exact ATP production/consumption balance. The screen stops when an ATP
gain is transferred into guarded glycolytic pools or teacher fluxes.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
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
DEFAULT_OUT_DIR = ROOT / "Simulations" / "brodbar" / "hermes" / "km_adp_atp_production_screen_46d"

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from MM_calibration import EXP_TO_MODEL, PHASE1_PARAMS  # noqa: E402
from profile_energy_redox_controls import _factor_timeseries  # noqa: E402
from profile_glycolysis_flux_bottlenecks import (  # noqa: E402
    _experimental_curves,
    _jsonable,
    _simulate_and_track,
    _time_mean,
)
from run_glucose_utilization_fla import (  # noqa: E402
    _build_lactate_teacher_dataset,
    _nrmse,
)


PARAMETER = "km_ADP_ATP"
LOCKED_PARAMETERS = (
    "km_ATP_HK",
    "km_ATP_PFK",
    "km_NADH_NAD",
    "vmax_VPGK",
    "vmax_VPK",
)
DEFAULT_MULTIPLIERS = (0.90, 0.75, 0.50)
METABOLITE_TARGETS = ("EGLC", "ELAC", "GLC", "LAC", "G6P", "PEP", "P3G", "P2G", "PYR", "ATP")
TRANSFER_TARGETS = ("GLC", "LAC", "G6P", "PEP", "P3G", "P2G", "PYR", "EGLC", "ELAC")
TEACHER_FLUXES = ("VEGLC", "VELAC", "VLDH")
NATIVE_FLUXES = ("VPGK", "VPK", "VAK")
BALANCE_COLUMNS = (
    "ATP_production_flux",
    "ATP_consumption_flux",
    "ATP_net_flux",
    "glycolysis_ATP_net_flux",
    "VPGK_ADP_ATP_drive",
    "ATP_pool",
    "ADP_pool",
)


def _directed_values(center: float, multipliers: Sequence[float]) -> list[float]:
    lower = float(PHASE1_PARAMS[PARAMETER][1])
    values: list[float] = []
    previous = float(center)
    for multiplier in multipliers:
        value = max(lower, float(center) * float(multiplier))
        if not 0.0 < value < previous:
            raise ValueError("km_ADP_ATP feasibility points must be strictly decreasing")
        values.append(value)
        previous = value
    return values


def _validate_locks(seed_params: Mapping[str, Any], candidate_params: Mapping[str, Any]) -> dict[str, float]:
    locked: dict[str, float] = {}
    for name in LOCKED_PARAMETERS:
        seed_value = float(seed_params[name])
        candidate_value = float(candidate_params[name])
        if not math.isclose(candidate_value, seed_value, rel_tol=0.0, abs_tol=1e-15):
            raise RuntimeError(
                f"{name} lock failed: seed={seed_value:.17g}, candidate={candidate_value:.17g}"
            )
        locked[name] = seed_value
    return locked


def _build_time_grid(t_max: float, timepoints: int, early_timepoints: int) -> np.ndarray:
    regular = np.linspace(1.0, float(t_max), int(timepoints))
    if int(early_timepoints) <= 0:
        return regular
    early = 1.0 + np.geomspace(1e-6, min(1.0, float(t_max) - 1.0), int(early_timepoints))
    return np.unique(np.concatenate(([1.0], early, regular)))


def _concentration_metrics(
    sol: Any,
    exp_time: np.ndarray,
    exp_curves: Mapping[str, np.ndarray],
) -> dict[str, dict[str, float]]:
    metrics: dict[str, dict[str, float]] = {}
    for name in METABOLITE_TARGETS:
        simulated = np.interp(exp_time, sol.t, sol.y[int(EXP_TO_MODEL[name]), :])
        metrics[name] = _nrmse(simulated, np.asarray(exp_curves[name], dtype=float))
        metrics[name]["final_value"] = float(simulated[-1])
    return metrics


def _teacher_flux_metrics(
    *,
    sol: Any,
    fluxes: Mapping[str, np.ndarray],
    teacher_dataset: Mapping[str, Any],
) -> dict[str, dict[str, float]]:
    if "dense_timepoints" not in teacher_dataset:
        raise KeyError("Teacher-flux dataset is missing dense_timepoints")
    teacher_time = np.asarray(teacher_dataset["dense_timepoints"], dtype=float)
    if teacher_time.ndim != 1 or teacher_time.size < 2:
        raise ValueError("Teacher-flux dense_timepoints must be a one-dimensional grid")
    details: dict[str, dict[str, float]] = {}
    for reaction in TEACHER_FLUXES:
        target = np.asarray(teacher_dataset["reaction_flux_curves"][reaction]["dense_values"], dtype=float)
        simulated = np.interp(teacher_time, sol.t, np.asarray(fluxes[reaction], dtype=float))
        rmse = float(np.sqrt(np.mean((simulated - target) ** 2)))
        norm = float(max(np.mean(np.abs(target)), 1e-4))
        details[reaction] = {"rmse": rmse, "nrmse": rmse / norm, "target_mean_abs": norm}
    return details


def _balance_summary(frame: pd.DataFrame) -> dict[str, dict[str, float]]:
    time = frame["time_day"].to_numpy(dtype=float)
    late = time >= 40.0
    columns = (*NATIVE_FLUXES, *BALANCE_COLUMNS)
    return {
        name: {
            "overall_mean": _time_mean(frame[name].to_numpy(dtype=float), time),
            "late_mean": _time_mean(frame[name].to_numpy(dtype=float), time, late),
            "endpoint": float(frame[name].iloc[-1]),
        }
        for name in columns
    }


def _transfer_guard_reasons(seed: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if float(candidate["concentration_metrics"]["ATP"]["final_value"]) < float(
        seed["concentration_metrics"]["ATP"]["final_value"]
    ) * 0.95:
        reasons.append("ATP endpoint below 95% of seed")

    for name in TRANSFER_TARGETS:
        seed_metric = seed["concentration_metrics"][name]
        candidate_metric = candidate["concentration_metrics"][name]
        relative_tolerance = 1.02 if name in {"GLC", "LAC"} else 1.05
        if float(candidate_metric["nrmse"]) > float(seed_metric["nrmse"]) * relative_tolerance + 0.01:
            reasons.append(f"{name} nRMSE transfer guard")
        if float(candidate_metric["endpoint_error"]) > float(seed_metric["endpoint_error"]) * 1.10 + 0.01:
            reasons.append(f"{name} endpoint transfer guard")

    for reaction in TEACHER_FLUXES:
        seed_metric = seed["teacher_flux_metrics"][reaction]
        candidate_metric = candidate["teacher_flux_metrics"][reaction]
        if float(candidate_metric["nrmse"]) > float(seed_metric["nrmse"]) * 1.08 + 0.01:
            reasons.append(f"{reaction} teacher-flux transfer guard")
    return sorted(set(reasons))


def _is_promising(seed: Mapping[str, Any], candidate: Mapping[str, Any]) -> bool:
    if candidate.get("guard_reasons"):
        return False
    seed_production = float(seed["balance_summary"]["ATP_production_flux"]["late_mean"])
    candidate_production = float(candidate["balance_summary"]["ATP_production_flux"]["late_mean"])
    production_gain = candidate_production > seed_production * 1.02
    direct_gain = any(
        float(candidate["concentration_metrics"][name]["nrmse"])
        < float(seed["concentration_metrics"][name]["nrmse"]) * 0.99
        for name in ("GLC", "LAC")
    )
    return production_gain and direct_gain


def _simulate_payload(
    *,
    label: str,
    params: Mapping[str, Any],
    t_eval: np.ndarray,
    exp_time: np.ndarray,
    exp_curves: Mapping[str, np.ndarray],
    teacher_dataset: Mapping[str, Any],
    method: str,
    rtol: float,
    atol: float,
) -> dict[str, Any]:
    sol, fluxes, _derivatives = _simulate_and_track(
        params=params,
        t_eval=t_eval,
        method=method,
        rtol=rtol,
        atol=atol,
    )
    factors = _factor_timeseries(sol, fluxes, params)
    for reaction in NATIVE_FLUXES:
        factors[reaction] = np.asarray(fluxes[reaction], dtype=float)
    return {
        "label": label,
        "params": {PARAMETER: float(params[PARAMETER])},
        "sol": sol,
        "fluxes": fluxes,
        "factors": factors,
        "concentration_metrics": _concentration_metrics(sol, exp_time, exp_curves),
        "teacher_flux_metrics": _teacher_flux_metrics(sol=sol, fluxes=fluxes, teacher_dataset=teacher_dataset),
        "balance_summary": _balance_summary(factors),
    }


def _plot_screen(
    *,
    seed: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    exp_time: np.ndarray,
    exp_curves: Mapping[str, np.ndarray],
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(3, 4, figsize=(15, 11))
    colors = ("#2563eb", "#7c3aed", "#dc2626")
    concentration_panels = ("GLC", "LAC", "G6P", "PEP", "P3G", "P2G", "PYR")
    for ax, name in zip(axes.flat[:7], concentration_panels):
        idx = int(EXP_TO_MODEL[name])
        ax.plot(seed["sol"].t, seed["sol"].y[idx, :], color="#64748b", linewidth=2.0, label="seed")
        for color, candidate in zip(colors, candidates):
            multiplier = float(candidate["params"][PARAMETER]) / float(seed["params"][PARAMETER])
            ax.plot(candidate["sol"].t, candidate["sol"].y[idx, :], color=color, linewidth=1.9, linestyle="--", label=f"{multiplier:.2f}x")
        ax.scatter(exp_time, exp_curves[name], color="#111827", s=18, zorder=3, label="Brodbar")
        ax.set_title(name)
        ax.set_xlabel("Time (days)")
        ax.set_ylabel("mM")
        ax.grid(True, alpha=0.22)

    ax = axes.flat[7]
    ax.plot(seed["factors"]["time_day"], seed["factors"]["ATP_pool"], color="#64748b", linewidth=2.0, label="seed")
    for color, candidate in zip(colors, candidates):
        multiplier = float(candidate["params"][PARAMETER]) / float(seed["params"][PARAMETER])
        ax.plot(candidate["factors"]["time_day"], candidate["factors"]["ATP_pool"], color=color, linewidth=1.9, linestyle="--", label=f"{multiplier:.2f}x")
    ax.scatter(exp_time, exp_curves["ATP"], color="#111827", s=18, zorder=3, label="Brodbar")
    ax.set_title("ATP pool")
    ax.set_xlabel("Time (days)")
    ax.set_ylabel("mM")
    ax.grid(True, alpha=0.22)

    for ax, reaction in zip(axes.flat[8:10], ("VPGK", "VPK")):
        ax.plot(seed["sol"].t, seed["fluxes"][reaction], color="#64748b", linewidth=2.0, label="seed")
        for color, candidate in zip(colors, candidates):
            multiplier = float(candidate["params"][PARAMETER]) / float(seed["params"][PARAMETER])
            ax.plot(candidate["sol"].t, candidate["fluxes"][reaction], color=color, linewidth=1.9, linestyle="--", label=f"{multiplier:.2f}x")
        ax.set_title(f"Native {reaction}")
        ax.set_xlabel("Time (days)")
        ax.set_ylabel("mM/day")
        ax.grid(True, alpha=0.22)

    ax = axes.flat[10]
    ax.plot(seed["factors"]["time_day"], seed["factors"]["ATP_production_flux"], color="#64748b", linewidth=2.0, label="seed production")
    ax.plot(seed["factors"]["time_day"], seed["factors"]["ATP_consumption_flux"], color="#64748b", linewidth=1.5, linestyle=":", label="seed consumption")
    for color, candidate in zip(colors, candidates):
        multiplier = float(candidate["params"][PARAMETER]) / float(seed["params"][PARAMETER])
        ax.plot(candidate["factors"]["time_day"], candidate["factors"]["ATP_production_flux"], color=color, linewidth=1.9, linestyle="--", label=f"{multiplier:.2f}x production")
        ax.plot(candidate["factors"]["time_day"], candidate["factors"]["ATP_consumption_flux"], color=color, linewidth=1.2, linestyle=":")
    ax.set_title("ATP production vs consumption")
    ax.set_xlabel("Time (days)")
    ax.set_ylabel("mM/day")
    ax.grid(True, alpha=0.22)

    ax = axes.flat[11]
    labels = ["seed"] + [f"{float(c['params'][PARAMETER]) / float(seed['params'][PARAMETER]):.2f}x" for c in candidates]
    payloads = [seed, *candidates]
    production = [float(p["balance_summary"]["ATP_production_flux"]["late_mean"]) for p in payloads]
    net = [float(p["balance_summary"]["ATP_net_flux"]["late_mean"]) for p in payloads]
    x = np.arange(len(labels), dtype=float)
    width = 0.36
    ax.bar(x - width / 2, production, width, color="#0f766e", label="late production")
    ax.bar(x + width / 2, net, width, color="#b91c1c", label="late net")
    ax.axhline(0.0, color="#111827", linewidth=0.8)
    ax.set_xticks(x, labels)
    ax.set_title("Late ATP balance, days 40-46")
    ax.set_ylabel("mM/day")
    ax.grid(True, axis="y", alpha=0.22)
    ax.legend(frameon=False, fontsize=8)

    handles, labels_legend = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels_legend, loc="upper center", bbox_to_anchor=(0.5, 0.965), ncol=max(3, len(handles)), frameon=False)
    fig.suptitle("Brodbar ATP-production screen: km_ADP_ATP downward only", fontsize=15, y=0.995)
    fig.subplots_adjust(top=0.89, hspace=0.34, wspace=0.36)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    seed = summary["seed"]
    lines = [
        "# Directed `km_ADP_ATP` ATP-production screen",
        "",
        "## Technical summary",
        "",
        f"- Generated: {summary['generated_at']}",
        "- Dataset: Brodbar concentrations, derived teacher fluxes, and native ODE flux tracking.",
        f"- Horizon: `{summary['t_max']:.0f}` days.",
        "- Diagnostic only: no optimization, full-panel promotion, or global parameter overwrite.",
        f"- Seed `km_ADP_ATP`: `{seed['params'][PARAMETER]:.12g}`.",
        "",
        "## Method",
        "",
        "Each downward perturbation was replayed through the complete ODE. Native `VPGK`, `VPK`, and `VAK` fluxes were recorded with `FluxTracker`. ATP production was calculated as `VPGK + VPK + VAK`; ATP consumption used the exact reaction sum from the ATP ODE. Candidate evaluation stopped when a gain was transferred into guarded glycolytic concentrations or teacher fluxes.",
        "",
        "## Results",
        "",
    ]
    for point in summary["evaluated_points"]:
        lines.extend(
            [
                f"### `{point['multiplier']:.2f}x` seed",
                "",
                f"- `km_ADP_ATP = {point['value']:.12g}`.",
                f"- Late ATP production: `{point['seed_late_atp_production']:.6g} -> {point['late_atp_production']:.6g}` mM/day.",
                f"- Late ATP consumption: `{point['seed_late_atp_consumption']:.6g} -> {point['late_atp_consumption']:.6g}` mM/day.",
                f"- Late ATP net flux: `{point['seed_late_atp_net']:.6g} -> {point['late_atp_net']:.6g}` mM/day.",
                f"- ATP endpoint: `{point['seed_atp_endpoint']:.6g} -> {point['atp_endpoint']:.6g}` mM.",
                f"- VPGK late mean: `{point['seed_vpgk_late']:.6g} -> {point['vpgk_late']:.6g}` mM/day.",
                f"- VPK late mean: `{point['seed_vpk_late']:.6g} -> {point['vpk_late']:.6g}` mM/day.",
                f"- GLC nRMSE: `{point['seed_glc_nrmse']:.6g} -> {point['glc_nrmse']:.6g}`.",
                f"- PEP/P3G/P2G nRMSE: `{point['pep_nrmse']:.6g}` / `{point['p3g_nrmse']:.6g}` / `{point['p2g_nrmse']:.6g}`.",
                f"- Transfer guards: `{'; '.join(point['guard_reasons']) or 'none'}`.",
                "",
            ]
        )
    lines.extend(
        [
            "## Decision",
            "",
            f"**`{summary['decision']}`**",
            "",
            summary["decision_rationale"],
            "",
            "No parameter was promoted. A full Brodbar-panel replay remains mandatory before any future candidate can be retained.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_screen(
    *,
    out_dir: Path,
    seed_params_path: Path,
    multipliers: Sequence[float],
    t_max: float,
    timepoints: int,
    early_timepoints: int,
    teacher_dense_points: int,
    method: str,
    rtol: float,
    atol: float,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_params = json.loads(Path(seed_params_path).read_text(encoding="utf-8"))
    seed_params = {
        key: value
        for key, value in raw_params.items()
        if not isinstance(value, bool) and isinstance(value, (int, float, str))
    }
    required = {PARAMETER, *LOCKED_PARAMETERS}
    if missing := sorted(required.difference(seed_params)):
        raise KeyError(f"Seed is missing required parameters: {missing}")
    center = float(seed_params[PARAMETER])
    values = _directed_values(center, multipliers)
    locked = _validate_locks(seed_params, seed_params)

    t_eval = _build_time_grid(t_max, timepoints, early_timepoints)
    exp_time, exp_curves = _experimental_curves(t_max)
    missing_targets = sorted(set(METABOLITE_TARGETS).difference(exp_curves))
    if missing_targets:
        raise KeyError(f"Missing Brodbar concentration targets: {missing_targets}")
    teacher_dataset = _build_lactate_teacher_dataset(
        exp_time=exp_time,
        exp_curves={name: exp_curves[name] for name in ("EGLC", "ELAC", "GLC", "LAC", "PYR")},
        dense_points=teacher_dense_points,
        out_path=out_dir / "teacher_flux_dataset_km_adp_atp.json",
    )

    print(f"{PARAMETER} seed: {center:.17g}", flush=True)
    print(", ".join(f"{name} locked: {locked[name]:.17g}" for name in LOCKED_PARAMETERS), flush=True)
    print(f"directed values: {', '.join(f'{value:.9g}' for value in values)}", flush=True)
    seed_payload = _simulate_payload(
        label="mild_feedback_seed",
        params=seed_params,
        t_eval=t_eval,
        exp_time=exp_time,
        exp_curves=exp_curves,
        teacher_dataset=teacher_dataset,
        method=method,
        rtol=rtol,
        atol=atol,
    )

    candidates: list[dict[str, Any]] = []
    point_summaries: list[dict[str, Any]] = []
    stopped_early = False
    for index, (multiplier, value) in enumerate(zip(multipliers, values)):
        params = dict(seed_params)
        params[PARAMETER] = float(value)
        _validate_locks(seed_params, params)
        candidate = _simulate_payload(
            label=f"screen_{multiplier:.2f}x",
            params=params,
            t_eval=t_eval,
            exp_time=exp_time,
            exp_curves=exp_curves,
            teacher_dataset=teacher_dataset,
            method=method,
            rtol=rtol,
            atol=atol,
        )
        candidate["guard_reasons"] = _transfer_guard_reasons(seed_payload, candidate)
        candidate["promising"] = _is_promising(seed_payload, candidate)
        candidates.append(candidate)

        seed_balance = seed_payload["balance_summary"]
        balance = candidate["balance_summary"]
        seed_metrics = seed_payload["concentration_metrics"]
        metrics = candidate["concentration_metrics"]
        point = {
            "multiplier": float(multiplier),
            "value": float(value),
            "guard_reasons": candidate["guard_reasons"],
            "promising": bool(candidate["promising"]),
            "seed_late_atp_production": float(seed_balance["ATP_production_flux"]["late_mean"]),
            "late_atp_production": float(balance["ATP_production_flux"]["late_mean"]),
            "seed_late_atp_consumption": float(seed_balance["ATP_consumption_flux"]["late_mean"]),
            "late_atp_consumption": float(balance["ATP_consumption_flux"]["late_mean"]),
            "seed_late_atp_net": float(seed_balance["ATP_net_flux"]["late_mean"]),
            "late_atp_net": float(balance["ATP_net_flux"]["late_mean"]),
            "seed_atp_endpoint": float(seed_metrics["ATP"]["final_value"]),
            "atp_endpoint": float(metrics["ATP"]["final_value"]),
            "seed_vpgk_late": float(seed_balance["VPGK"]["late_mean"]),
            "vpgk_late": float(balance["VPGK"]["late_mean"]),
            "seed_vpk_late": float(seed_balance["VPK"]["late_mean"]),
            "vpk_late": float(balance["VPK"]["late_mean"]),
            "seed_glc_nrmse": float(seed_metrics["GLC"]["nrmse"]),
            "glc_nrmse": float(metrics["GLC"]["nrmse"]),
            "lac_nrmse": float(metrics["LAC"]["nrmse"]),
            "g6p_nrmse": float(metrics["G6P"]["nrmse"]),
            "pep_nrmse": float(metrics["PEP"]["nrmse"]),
            "p3g_nrmse": float(metrics["P3G"]["nrmse"]),
            "p2g_nrmse": float(metrics["P2G"]["nrmse"]),
            "pyr_nrmse": float(metrics["PYR"]["nrmse"]),
        }
        point_summaries.append(point)
        print(
            f"point {multiplier:.2f}x: ATPprod_late={point['late_atp_production']:.6g}, "
            f"ATPnet_late={point['late_atp_net']:.6g}, ATPend={point['atp_endpoint']:.6g}, "
            f"VPGK={point['vpgk_late']:.6g}, VPK={point['vpk_late']:.6g}, "
            f"GLC={point['glc_nrmse']:.4f}, PEP={point['pep_nrmse']:.4f}, "
            f"guards={','.join(point['guard_reasons']) or 'none'}",
            flush=True,
        )
        if candidate["guard_reasons"]:
            stopped_early = index < len(values) - 1
            break

    promising_points = [point for point in point_summaries if point["promising"]]
    if promising_points:
        decision = "proceed to a narrow km_ADP_ATP optimization"
        rationale = "At least one point increased late ATP production and improved a direct glucose/lactate target without transferring error into guarded pools or teacher fluxes."
    elif any(point["guard_reasons"] for point in point_summaries):
        decision = "abort km_ADP_ATP before optimization"
        guarded_point = next(point for point in point_summaries if point["guard_reasons"])
        production_gain = 100.0 * (
            guarded_point["late_atp_production"] / guarded_point["seed_late_atp_production"] - 1.0
        )
        consumption_gain = 100.0 * (
            guarded_point["late_atp_consumption"] / guarded_point["seed_late_atp_consumption"] - 1.0
        )
        rationale = (
            f"At {guarded_point['multiplier']:.2f}x, late ATP production increased by {production_gain:.1f}% "
            f"but consumption increased by {consumption_gain:.1f}% and the net flux became more negative; "
            f"{', '.join(guarded_point['guard_reasons'])} also failed. Stronger perturbations are not justified."
        )
    else:
        decision = "do not optimize km_ADP_ATP"
        rationale = "The screened points remained guarded but did not jointly improve ATP production and the direct glucose/lactate phenotype."

    seed_path = out_dir / "seed_params.json"
    retained_path = out_dir / "retained_seed_params.json"
    seed_path.write_text(json.dumps(_jsonable(seed_params), indent=2), encoding="utf-8")
    retained_path.write_text(json.dumps(_jsonable(seed_params), indent=2), encoding="utf-8")
    for point, candidate in zip(point_summaries, candidates):
        params = dict(seed_params)
        params[PARAMETER] = float(candidate["params"][PARAMETER])
        point_path = out_dir / f"screen_params_{point['multiplier']:.2f}x.json"
        point_path.write_text(json.dumps(_jsonable(params), indent=2), encoding="utf-8")
        point["params_path"] = str(point_path)

    metric_rows: list[dict[str, Any]] = []
    for point, candidate in zip(point_summaries, candidates):
        for name in METABOLITE_TARGETS:
            seed_metric = seed_payload["concentration_metrics"][name]
            metric = candidate["concentration_metrics"][name]
            metric_rows.append(
                {
                    "multiplier": point["multiplier"],
                    "parameter_value": point["value"],
                    "target_type": "concentration",
                    "target": name,
                    "seed_nrmse": seed_metric["nrmse"],
                    "candidate_nrmse": metric["nrmse"],
                    "delta_nrmse": metric["nrmse"] - seed_metric["nrmse"],
                    "seed_endpoint_error": seed_metric["endpoint_error"],
                    "candidate_endpoint_error": metric["endpoint_error"],
                }
            )
        for reaction in TEACHER_FLUXES:
            seed_metric = seed_payload["teacher_flux_metrics"][reaction]
            metric = candidate["teacher_flux_metrics"][reaction]
            metric_rows.append(
                {
                    "multiplier": point["multiplier"],
                    "parameter_value": point["value"],
                    "target_type": "teacher_flux",
                    "target": reaction,
                    "seed_nrmse": seed_metric["nrmse"],
                    "candidate_nrmse": metric["nrmse"],
                    "delta_nrmse": metric["nrmse"] - seed_metric["nrmse"],
                    "seed_endpoint_error": np.nan,
                    "candidate_endpoint_error": np.nan,
                }
            )
    metrics_csv = out_dir / "screen_metrics.csv"
    pd.DataFrame(metric_rows).to_csv(metrics_csv, index=False)

    frames: list[pd.DataFrame] = []
    for payload in (seed_payload, *candidates):
        frame = payload["factors"].copy()
        frame["candidate"] = payload["label"]
        frame[PARAMETER] = float(payload["params"][PARAMETER])
        frames.append(frame)
    flux_csv = out_dir / "native_flux_and_atp_balance.csv"
    pd.concat(frames, ignore_index=True).to_csv(flux_csv, index=False)

    plot_path = out_dir / "km_adp_atp_production_screen.png"
    _plot_screen(
        seed=seed_payload,
        candidates=candidates,
        exp_time=exp_time,
        exp_curves=exp_curves,
        out_path=plot_path,
    )

    summary = {
        "contract_type": "km_adp_atp_directed_production_screen",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "optimization_performed": False,
        "parameters_promoted": False,
        "seed_params_path": str(seed_params_path),
        "screened_parameter": PARAMETER,
        "locked_params": locked,
        "planned_multipliers": [float(value) for value in multipliers],
        "planned_values": values,
        "t_max": float(t_max),
        "timepoints": int(t_eval.size),
        "teacher_dense_points": int(teacher_dense_points),
        "solver": {"method": method, "rtol": float(rtol), "atol": float(atol)},
        "native_fluxes": list(NATIVE_FLUXES),
        "atp_balance_columns": list(BALANCE_COLUMNS),
        "transfer_guard_targets": list(TRANSFER_TARGETS),
        "teacher_flux_guards": list(TEACHER_FLUXES),
        "stopped_early": stopped_early,
        "evaluated_point_count": len(point_summaries),
        "evaluated_points": point_summaries,
        "promising_point_count": len(promising_points),
        "decision": decision,
        "decision_rationale": rationale,
        "seed": {
            "params": seed_payload["params"],
            "concentration_metrics": seed_payload["concentration_metrics"],
            "teacher_flux_metrics": seed_payload["teacher_flux_metrics"],
            "balance_summary": seed_payload["balance_summary"],
        },
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "decision_report": str(out_dir / "decision_report.md"),
            "seed_params": str(seed_path),
            "retained_seed_params": str(retained_path),
            "teacher_dataset": str(out_dir / "teacher_flux_dataset_km_adp_atp.json"),
            "metrics_csv": str(metrics_csv),
            "native_flux_and_balance_csv": str(flux_csv),
            "plot": str(plot_path),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(_jsonable(summary), indent=2), encoding="utf-8")
    _write_report(out_dir / "decision_report.md", summary)
    print(json.dumps(_jsonable(summary), indent=2), flush=True)
    return summary


def _parse_multipliers(raw: str) -> tuple[float, ...]:
    return tuple(float(value.strip()) for value in raw.split(",") if value.strip())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Screen km_ADP_ATP with native ATP-production flux tracking")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--seed-params", type=Path, default=DEFAULT_SEED_PARAMS)
    parser.add_argument("--multipliers", default=",".join(str(value) for value in DEFAULT_MULTIPLIERS))
    parser.add_argument("--t-max", type=float, default=46.0)
    parser.add_argument("--timepoints", type=int, default=181)
    parser.add_argument("--early-timepoints", type=int, default=60)
    parser.add_argument("--teacher-dense-points", type=int, default=96)
    parser.add_argument("--method", default="LSODA")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_screen(
        out_dir=args.out_dir,
        seed_params_path=args.seed_params,
        multipliers=_parse_multipliers(args.multipliers),
        t_max=args.t_max,
        timepoints=args.timepoints,
        early_timepoints=args.early_timepoints,
        teacher_dense_points=args.teacher_dense_points,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
