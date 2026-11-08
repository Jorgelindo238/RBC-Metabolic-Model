"""Profile native ATP/ADP/redox controls before the next FLA optimization.

This is a diagnostic-only replay. It does not optimize or promote parameters.
The saved ODE parameters are replayed through the native FluxTracker, while
the ATP/ADP and NAD(H) occupancy factors are reconstructed from the same
Michaelis-Menten terms used by ``equadiff_brodbar``.
"""

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

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
SCRIPT_DIR = ROOT / "scripts"
DEFAULT_OUT_DIR = ROOT / "output" / "fla_energy_redox_control_profile"

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from equadiff_brodbar import BRODBAR_METABOLITE_MAP  # noqa: E402
from profile_glycolysis_flux_bottlenecks import (  # noqa: E402
    _experimental_curves,
    _jsonable,
    _load_params,
    _simulate_and_track,
    _time_mean,
)


DEFAULT_CANDIDATES = {
    "mild_seed": (
        ROOT
        / "Simulations"
        / "brodbar"
        / "hermes"
        / "vpep_vpk_coupled_mild_feedback_46d_n20"
        / "seed_fixed_params.json"
    ),
    "coupled_rejected": (
        ROOT
        / "Simulations"
        / "brodbar"
        / "hermes"
        / "vpep_vpk_coupled_mild_feedback_46d_n20"
        / "candidate_params.json"
    ),
}

STATE = {
    name: int(BRODBAR_METABOLITE_MAP[name])
    for name in ("GLC", "G6P", "F6P", "F16BP", "PEP", "PYR", "ATP", "ADP", "NAD", "NADH")
}

DEFAULTS = {
    "km_GLC_HK": 0.05,
    "km_ATP_HK": 0.5,
    "km_F6P": 0.207,
    "km_ATP_PFK": 0.1,
    "km_PEP": 0.175,
    "km_ADP_ATP": 1.0,
    "ki_ATP_PK": 2.5,
    "ki_PYR_PK": 1.0,
    "ka_F16BP_PK": 0.005,
    "n_F16BP_PK": 2.0,
    "alpha_F16BP_PK": 10.0,
    "km_PYR": 0.697,
    "km_NADH_NAD": 1.0,
    "km_NAD_NADH": 1.0,
}

VMAX = {
    "VHK": 0.267472,
    "VPFK": 0.391893,
    "VPGK": 4.690379,
    "VPK": 0.936322,
    "VLDH": 0.284952,
    "VPEP_PASE": 0.1,
    "VEGLC": 1.077,
    "VELAC": 0.58,
}

ATP_PRODUCTION = ("VPGK", "VPK", "VAK")
ATP_CONSUMPTION = (
    "VHK",
    "VPFK",
    "VAK2",
    "VGLNS",
    "VGLUCYS",
    "VGSS",
    "VSAM",
    "VRKa",
    "VPRPPASe",
    "VGMPS",
    "VGMPK",
    "VNDPK",
    "VOPLAH",
)


def _parse_candidates(specs: Sequence[str] | None) -> dict[str, Path]:
    if not specs:
        return dict(DEFAULT_CANDIDATES)
    candidates: dict[str, Path] = {}
    for spec in specs:
        if "=" not in spec:
            raise ValueError(f"Candidate must use label=path syntax: {spec!r}")
        label, raw_path = spec.split("=", 1)
        path = Path(raw_path.strip())
        candidates[label.strip()] = path if path.is_absolute() else ROOT / path
    return candidates


def _param(params: Mapping[str, Any], name: str) -> float:
    return float(params.get(name, DEFAULTS[name]))


def _vmax(params: Mapping[str, Any], reaction: str) -> float:
    return float(params.get(f"vmax_{reaction}", VMAX[reaction]))


def _mm(values: np.ndarray, km: float) -> np.ndarray:
    values = np.maximum(np.asarray(values, dtype=float), 0.0)
    return values / (float(km) + values + 1e-30)


def _factor_timeseries(sol: Any, fluxes: Mapping[str, np.ndarray], params: Mapping[str, Any]) -> pd.DataFrame:
    x = np.maximum(np.asarray(sol.y, dtype=float), 0.0)
    glc, g6p, f6p, f16bp = (x[STATE[name]] for name in ("GLC", "G6P", "F6P", "F16BP"))
    pep, pyr = x[STATE["PEP"]], x[STATE["PYR"]]
    atp = np.maximum(x[STATE["ATP"]], 1e-6)
    adp = np.maximum(x[STATE["ADP"]], 1e-6)
    nad = np.maximum(x[STATE["NAD"]], 1e-6)
    nadh = np.maximum(x[STATE["NADH"]], 1e-6)
    adp_atp = adp / (atp + 1e-6)
    nadh_nad = nadh / (nad + 1e-6)
    nad_nadh = nad / (nadh + 1e-6)

    f16bp_activation = 1.0 + _param(params, "alpha_F16BP_PK") * (
        f16bp ** _param(params, "n_F16BP_PK")
        / (_param(params, "ka_F16BP_PK") ** _param(params, "n_F16BP_PK") + f16bp ** _param(params, "n_F16BP_PK") + 1e-30)
    )
    factors: dict[str, np.ndarray] = {
        "VHK_GLC_occupancy": _mm(glc, _param(params, "km_GLC_HK")),
        "VHK_ATP_occupancy": _mm(atp, _param(params, "km_ATP_HK")),
        "VPFK_F6P_occupancy": _mm(f6p, _param(params, "km_F6P")),
        "VPFK_ATP_occupancy": _mm(atp, _param(params, "km_ATP_PFK")),
        "VPGK_ADP_ATP_drive": _mm(adp_atp, _param(params, "km_ADP_ATP")),
        "VPK_PEP_occupancy": _mm(pep, _param(params, "km_PEP")),
        "VPK_ADP_ATP_drive": _mm(adp_atp, _param(params, "km_ADP_ATP")),
        "VPK_F16BP_activation": f16bp_activation,
        "VPK_ATP_inhibition": 1.0 / (1.0 + atp / _param(params, "ki_ATP_PK")),
        "VPK_PYR_inhibition": 1.0 / (1.0 + pyr / _param(params, "ki_PYR_PK")),
        "VLDH_PYR_occupancy": _mm(pyr, _param(params, "km_PYR")),
        "VLDH_NADH_NAD_drive": _mm(nadh_nad, _param(params, "km_NADH_NAD")),
        "VGAPDH_NAD_NADH_drive": _mm(nad_nadh, _param(params, "km_NAD_NADH")),
        "pool_ADP_ATP_ratio": adp_atp,
        "pool_NADH_NAD_ratio": nadh_nad,
        "pool_NAD_NADH_ratio": nad_nadh,
    }
    for reaction in ("VHK", "VPFK", "VPGK", "VPK", "VLDH", "VPEP_PASE", "VEGLC", "VELAC"):
        values = np.asarray(fluxes[reaction], dtype=float)
        factors[f"{reaction}_vmax_utilization"] = np.abs(values) / max(_vmax(params, reaction), 1e-30)

    production = sum(np.asarray(fluxes[name], dtype=float) for name in ATP_PRODUCTION)
    consumption = sum(np.asarray(fluxes[name], dtype=float) for name in ATP_CONSUMPTION)
    factors["ATP_production_flux"] = production
    factors["ATP_consumption_flux"] = consumption
    factors["ATP_net_flux"] = production - consumption
    factors["glycolysis_ATP_net_flux"] = (
        np.asarray(fluxes["VPGK"], dtype=float)
        + np.asarray(fluxes["VPK"], dtype=float)
        - np.asarray(fluxes["VHK"], dtype=float)
        - np.asarray(fluxes["VPFK"], dtype=float)
    )
    factors["ATP_pool"] = x[STATE["ATP"]]
    factors["ADP_pool"] = x[STATE["ADP"]]
    factors["NAD_pool"] = x[STATE["NAD"]]
    factors["NADH_pool"] = x[STATE["NADH"]]

    frame = pd.DataFrame({"time_day": np.asarray(sol.t, dtype=float)})
    for name, values in factors.items():
        frame[name] = np.asarray(values, dtype=float)
    return frame


def _summary_rows(candidate: str, factors: pd.DataFrame) -> pd.DataFrame:
    time = factors["time_day"].to_numpy(dtype=float)
    windows = {
        "early_1_2d": (time >= 1.0) & (time <= 2.0),
        "mid_10_20d": (time >= 10.0) & (time <= 20.0),
        "late_40_46d": time >= 40.0,
    }
    excluded = {"time_day", "candidate", "params_path"}
    rows: list[dict[str, Any]] = []
    for metric in [column for column in factors.columns if column not in excluded]:
        values = factors[metric].to_numpy(dtype=float)
        row: dict[str, Any] = {
            "candidate": candidate,
            "metric": metric,
            "overall_mean": _time_mean(values, time),
            "min": float(np.min(values)),
            "max": float(np.max(values)),
            "endpoint": float(values[-1]),
        }
        for window_name, mask in windows.items():
            row[window_name] = _time_mean(values, time, mask)
        rows.append(row)
    return pd.DataFrame(rows)


def _rank_controls(summary: pd.DataFrame, candidate: str) -> pd.DataFrame:
    frame = summary[summary["candidate"] == candidate].copy()
    controls = {
        "km_ATP_HK": "VHK_ATP_occupancy",
        "km_ATP_PFK": "VPFK_ATP_occupancy",
        "ki_ATP_PK": "VPK_ATP_inhibition",
        "km_NADH_NAD": "VLDH_NADH_NAD_drive",
    }
    rows: list[dict[str, Any]] = []
    for parameter, metric in controls.items():
        metric_row = frame[frame["metric"] == metric].iloc[0]
        if parameter == "ki_ATP_PK":
            limitation = 1.0 - float(metric_row["late_40_46d"])
            direction = "increase ki_ATP_PK" if limitation > 0.5 else "do not open"
        else:
            limitation = 1.0 - min(float(metric_row["late_40_46d"]), 1.0)
            direction = f"decrease {parameter}" if limitation > 0.5 else f"do not open {parameter}"
        rows.append(
            {
                "candidate": candidate,
                "parameter": parameter,
                "factor": metric,
                "late_factor": float(metric_row["late_40_46d"]),
                "endpoint_factor": float(metric_row["endpoint"]),
                "limitation_score": limitation,
                "suggested_direction": direction,
            }
        )
    return pd.DataFrame(rows).sort_values("limitation_score", ascending=False).reset_index(drop=True)


def _plot(factor_frames: Mapping[str, pd.DataFrame], out_path: Path) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(12, 13), sharex=True)
    colors = {"mild_seed": "#1f4e79", "coupled_rejected": "#b23a48"}
    ratio_axis = axes[0].twinx()
    for label, frame in factor_frames.items():
        time = frame["time_day"]
        color = colors.get(label, None)
        axes[0].plot(time, frame["ATP_pool"], label=f"{label}: ATP", color=color, linewidth=2.0)
        axes[0].plot(time, frame["ADP_pool"], label=f"{label}: ADP", color=color, linestyle="--", linewidth=1.5)
        ratio_axis.plot(time, frame["pool_ADP_ATP_ratio"], label=f"{label}: ADP/ATP", color=color, linestyle=":", linewidth=1.4)
        axes[1].plot(time, frame["VHK_ATP_occupancy"], label=f"{label}: HK ATP", color=color, linewidth=2.0)
        axes[1].plot(time, frame["VPFK_ATP_occupancy"], label=f"{label}: PFK ATP", color=color, linestyle="--", linewidth=1.5)
        axes[1].plot(time, frame["VPK_ATP_inhibition"], label=f"{label}: PK ATP inhibition", color=color, linestyle=":", linewidth=1.4)
        axes[1].plot(time, frame["VLDH_NADH_NAD_drive"], label=f"{label}: LDH NADH/NAD", color=color, linestyle="-.", linewidth=1.4)
        axes[2].plot(time, frame["ATP_production_flux"], label=f"{label}: ATP production", color=color, linewidth=2.0)
        axes[2].plot(time, frame["ATP_consumption_flux"], label=f"{label}: ATP consumption", color=color, linestyle="--", linewidth=1.5)

    axes[0].set_ylabel("ATP / ADP pool (mM)")
    ratio_axis.set_ylabel("ADP/ATP ratio")
    axes[0].set_title("ATP/ADP pool trajectory")
    axes[1].set_ylabel("Factor")
    axes[1].set_title("Native ATP and redox controls")
    axes[1].axhline(0.25, color="#666666", linewidth=0.9, linestyle=":")
    axes[2].set_ylabel("Flux")
    axes[2].set_xlabel("Time (day)")
    axes[2].set_title("ATP production versus consumption")
    first_handles, first_labels = axes[0].get_legend_handles_labels()
    ratio_handles, ratio_labels = ratio_axis.get_legend_handles_labels()
    axes[0].legend(first_handles + ratio_handles, first_labels + ratio_labels, ncol=2, fontsize=8, loc="best")
    for axis in axes[1:]:
        axis.grid(True, alpha=0.2)
        axis.legend(ncol=2, fontsize=8, loc="best")
    axes[0].grid(True, alpha=0.2)
    fig.suptitle("FLA diagnostic: energy/redox controls before optimization", fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_late_controls(ranking: pd.DataFrame, out_path: Path) -> None:
    pivot = ranking.pivot(index="parameter", columns="candidate", values="late_factor")
    ax = pivot.plot(kind="bar", figsize=(11, 6), color=["#1f4e79", "#b23a48"], rot=0)
    ax.axhline(0.25, color="#666666", linewidth=1.0, linestyle=":")
    ax.set_ylabel("Late factor, mean over days 40-46")
    ax.set_xlabel("")
    ax.set_title("Candidate comparison of native control factors")
    ax.grid(True, axis="y", alpha=0.2)
    ax.set_yscale("log")
    ax.legend(title="Candidate")
    fig = ax.get_figure()
    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _write_report(
    path: Path,
    *,
    reference: str,
    control_ranking: pd.DataFrame,
    summary: pd.DataFrame,
    t_max: float,
) -> None:
    reference_rank = control_ranking[control_ranking["candidate"] == reference].copy()
    reference_rank = reference_rank.sort_values("limitation_score", ascending=False)
    top = reference_rank.iloc[0]
    atp_row = summary[(summary["candidate"] == reference) & (summary["metric"] == "ATP_pool")].iloc[0]
    nadh_row = summary[(summary["candidate"] == reference) & (summary["metric"] == "NADH_pool")].iloc[0]
    lines = [
        "# Diagnostic ATP/ADP/redox controls before FLA optimization",
        "",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        f"- Replay horizon: {t_max:g} days",
        f"- Reference candidate: `{reference}`",
        "- Diagnostic only: no Optuna optimization, parameter promotion, or overwrite.",
        "",
        "## Method",
        "",
        "The saved parameter sets were replayed through the native ODE and `FluxTracker`. The factors below are reconstructed from the same terms used in `equadiff_brodbar`: substrate occupancy, ATP substrate occupancy, ADP/ATP drive, PK ATP inhibition, PK product inhibition, and LDH NADH/NAD drive. The late window is days 40-46.",
        "",
        "The ATP balance is decomposed as:",
        "",
        "`dATP/dt = (VPGK + VPK + VAK) - (VHK + VPFK + VAK2 + VGLNS + VGLUCYS + VGSS + VSAM + VRKa + VPRPPASe + VGMPS + VGMPK + VNDPK + VOPLAH)`. ",
        "",
        "## Reference findings",
        "",
        f"- ATP endpoint: `{atp_row['endpoint']:.6g}` mM; late mean: `{atp_row['late_40_46d']:.6g}` mM.",
        f"- NADH endpoint: `{nadh_row['endpoint']:.6g}` mM; late mean: `{nadh_row['late_40_46d']:.6g}` mM.",
        f"- Strongest late control limitation by factor score: `{top['parameter']}` with factor `{top['late_factor']:.6g}` and suggested direction `{top['suggested_direction']}`.",
        "",
        "| Parameter | Native factor | Late factor | Endpoint factor | Suggested direction |",
        "|---|---|---:|---:|---|",
    ]
    for _, row in reference_rank.iterrows():
        lines.append(
            f"| `{row['parameter']}` | `{row['factor']}` | {row['late_factor']:.6g} | {row['endpoint_factor']:.6g} | {row['suggested_direction']} |"
        )
    lines.extend(
        [
            "",
            "## Decision before optimization",
            "",
            "A factor below 0.25 is treated as a strong local restriction. The next FLA pass should open only the highest-ranked biologically interpretable lever from the reference table, while keeping the alternative controls fixed. If the top result is an ATP occupancy factor, the pass must retain PEP/G6P and ATP guards because increasing ATP affinity can increase ATP demand before it restores throughput. If the LDH redox factor is also low, it is recorded as a coupled diagnostic risk rather than opened simultaneously.",
            "",
            "Required non-inferiority guards for the next pass: `EGLC`, `GLC`, `LAC`, `ELAC`, `ATP`, `PEP`, `G6P`, `VEGLC`, `VELAC`, `VLDH`, plus the full 55-metabolite Brodbar panel.",
            "",
            "## Artifacts",
            "",
            "- `energy_redox_control_profile.png`",
            "- `energy_redox_late_controls.png`",
            "- `energy_redox_timeseries.csv`",
            "- `energy_redox_summary.csv`",
            "- `energy_redox_control_ranking.csv`",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_profile(
    *,
    out_dir: Path,
    candidate_specs: Sequence[str] | None,
    reference_candidate: str,
    t_max: float,
    timepoints: int,
    early_timepoints: int,
    early_window: float,
    method: str,
    rtol: float,
    atol: float,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    candidates = _parse_candidates(candidate_specs)
    if reference_candidate not in candidates:
        raise KeyError(f"Reference candidate {reference_candidate!r} is not in {sorted(candidates)}")
    for path in candidates.values():
        if not path.exists():
            raise FileNotFoundError(path)

    regular_time = np.linspace(1.0, float(t_max), int(timepoints))
    early_span = min(max(float(early_window), 0.0), max(float(t_max) - 1.0, 0.0))
    if int(early_timepoints) > 0 and early_span > 0.0:
        early_offsets = np.geomspace(1e-6, early_span, int(early_timepoints))
        t_eval = np.unique(np.concatenate(([1.0], 1.0 + early_offsets, regular_time)))
    else:
        t_eval = regular_time

    frames: dict[str, pd.DataFrame] = {}
    summary_frames: list[pd.DataFrame] = []
    for label, source_path in candidates.items():
        print(f"[energy-redox-profile] simulating {label}: {source_path}", flush=True)
        params = _load_params(source_path)
        sol, fluxes, _derivatives = _simulate_and_track(
            params=params,
            t_eval=t_eval,
            method=method,
            rtol=rtol,
            atol=atol,
        )
        frame = _factor_timeseries(sol, fluxes, params)
        for reaction in ("VHK", "VPFK", "VPGK", "VPK", "VLDH", "VPEP_PASE", "VEGLC", "VELAC"):
            frame[reaction] = np.asarray(fluxes[reaction], dtype=float)
        frame["candidate"] = label
        frame["params_path"] = str(source_path)
        frames[label] = frame
        summary_frames.append(_summary_rows(label, frame))

    summary = pd.concat(summary_frames, ignore_index=True)
    ranking = pd.concat(
        [_rank_controls(summary, label) for label in candidates], ignore_index=True
    )
    paths = {
        "timeseries_csv": out_dir / "energy_redox_timeseries.csv",
        "summary_csv": out_dir / "energy_redox_summary.csv",
        "ranking_csv": out_dir / "energy_redox_control_ranking.csv",
        "profile_png": out_dir / "energy_redox_control_profile.png",
        "late_controls_png": out_dir / "energy_redox_late_controls.png",
        "report_md": out_dir / "energy_redox_control_report.md",
        "summary_json": out_dir / "summary.json",
    }
    pd.concat(frames.values(), ignore_index=True).to_csv(paths["timeseries_csv"], index=False)
    summary.to_csv(paths["summary_csv"], index=False)
    ranking.to_csv(paths["ranking_csv"], index=False)
    _plot(frames, paths["profile_png"])
    _plot_late_controls(ranking, paths["late_controls_png"])
    _write_report(
        paths["report_md"],
        reference=reference_candidate,
        control_ranking=ranking,
        summary=summary,
        t_max=t_max,
    )
    reference_top = ranking[ranking["candidate"] == reference_candidate].sort_values(
        "limitation_score", ascending=False
    ).iloc[0]
    result = {
        "contract_type": "fla_energy_redox_control_profile",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "optimization_performed": False,
        "parameters_promoted": False,
        "t_max": float(t_max),
        "timepoints": int(t_eval.size),
        "reference_candidate": reference_candidate,
        "candidate_params": {label: str(path) for label, path in candidates.items()},
        "top_reference_control": _jsonable(reference_top.to_dict()),
        "guardrails": ["EGLC", "GLC", "LAC", "ELAC", "ATP", "PEP", "G6P", "VEGLC", "VELAC", "VLDH", "full_55_metabolite_panel"],
        "artifact_paths": {name: str(path) for name, path in paths.items()},
    }
    paths["summary_json"].write_text(json.dumps(_jsonable(result), indent=2), encoding="utf-8")
    print(json.dumps(_jsonable(result), indent=2), flush=True)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Profile native ATP/ADP/redox controls before FLA optimization.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--candidate", action="append", dest="candidate_specs")
    parser.add_argument("--reference-candidate", default="mild_seed")
    parser.add_argument("--t-max", type=float, default=46.0)
    parser.add_argument("--timepoints", type=int, default=181)
    parser.add_argument("--early-timepoints", type=int, default=80)
    parser.add_argument("--early-window", type=float, default=1.0)
    parser.add_argument("--method", default="LSODA")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_profile(
        out_dir=args.out_dir,
        candidate_specs=args.candidate_specs,
        reference_candidate=args.reference_candidate,
        t_max=args.t_max,
        timepoints=args.timepoints,
        early_timepoints=args.early_timepoints,
        early_window=args.early_window,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
    )


if __name__ == "__main__":
    main()
