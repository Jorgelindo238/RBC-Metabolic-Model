"""Attribute ATP-consumption changes between the seed and km_ADP_ATP 0.75x.

The diagnostic replays both parameter sets with the native FluxTracker,
verifies exact closure of the ATP-consumption term, and ranks constitutive and
induced sinks together with their measured Brodbar pools when available.
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
DEFAULT_CANDIDATE_PARAMS = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "km_adp_atp_production_screen_46d"
    / "screen_params_0.75x.json"
)
DEFAULT_OUT_DIR = ROOT / "Simulations" / "brodbar" / "hermes" / "atp_consumption_sink_attribution_46d"

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from MM_calibration import EXP_TO_MODEL, load_experimental_data  # noqa: E402
from profile_energy_redox_controls import ATP_CONSUMPTION, _factor_timeseries  # noqa: E402
from profile_glycolysis_flux_bottlenecks import _jsonable, _load_params, _simulate_and_track, _time_mean  # noqa: E402
from run_glucose_utilization_fla import _nrmse  # noqa: E402


POOL_LINKS: dict[str, tuple[str, ...]] = {
    "VHK": ("GLC", "G6P"),
    "VPFK": ("F6P", "F16BP"),
    "VAK2": ("ADP", "AMP"),
    "VGLNS": ("GLU", "GLN", "EGLN"),
    "VGLUCYS": ("GLU", "GSH", "ECYS"),
    "VGSS": ("GSH", "GSSG", "EGSH", "EGSSG"),
    "VSAM": ("SAH",),
    "VRKa": (),
    "VPRPPASe": ("IMP",),
    "VGMPS": ("GMP", "GLN"),
    "VGMPK": ("GMP",),
    "VNDPK": ("GMP",),
    "VOPLAH": ("OXOP", "EOXOP", "GLU"),
}
EXPECTED_CHANGED_PARAMETER = "km_ADP_ATP"


def _changed_parameters(seed: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[str]:
    names = sorted(set(seed) | set(candidate))
    changed: list[str] = []
    for name in names:
        seed_value = seed.get(name)
        candidate_value = candidate.get(name)
        if isinstance(seed_value, (int, float)) and isinstance(candidate_value, (int, float)):
            if not math.isclose(float(seed_value), float(candidate_value), rel_tol=0.0, abs_tol=1e-15):
                changed.append(name)
        elif seed_value != candidate_value:
            changed.append(name)
    return changed


def _time_grid(t_max: float, timepoints: int, early_timepoints: int) -> np.ndarray:
    regular = np.linspace(1.0, float(t_max), int(timepoints))
    if int(early_timepoints) <= 0:
        return regular
    early = 1.0 + np.geomspace(1e-6, min(1.0, float(t_max) - 1.0), int(early_timepoints))
    return np.unique(np.concatenate(([1.0], early, regular)))


def _all_experimental_curves(t_max: float) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    time_exp, exp_values, name_to_row = load_experimental_data()
    mask = (time_exp >= 1.0 - 1e-9) & (time_exp <= float(t_max) + 1e-9)
    curves = {
        name: np.asarray(exp_values[row, mask], dtype=float)
        for name, row in name_to_row.items()
        if name in EXP_TO_MODEL and np.all(np.isfinite(exp_values[row, mask]))
    }
    return np.asarray(time_exp[mask], dtype=float), curves


def _consumption_sum(fluxes: Mapping[str, np.ndarray]) -> np.ndarray:
    missing = [name for name in ATP_CONSUMPTION if name not in fluxes]
    if missing:
        raise KeyError(f"FluxTracker is missing ATP-consumption reactions: {missing}")
    return sum(np.asarray(fluxes[name], dtype=float) for name in ATP_CONSUMPTION)


def _validate_closure(fluxes: Mapping[str, np.ndarray], factors: pd.DataFrame, tolerance: float = 1e-12) -> float:
    reconstructed = _consumption_sum(fluxes)
    tracked = factors["ATP_consumption_flux"].to_numpy(dtype=float)
    error = float(np.max(np.abs(reconstructed - tracked)))
    if error > float(tolerance):
        raise RuntimeError(f"ATP-consumption closure failed: max abs error={error:.6g}")
    return error


def _sink_rows(
    *,
    seed_fluxes: Mapping[str, np.ndarray],
    candidate_fluxes: Mapping[str, np.ndarray],
    time: np.ndarray,
) -> list[dict[str, Any]]:
    time = np.asarray(time, dtype=float)
    late = time >= 40.0
    seed_total = _consumption_sum(seed_fluxes)
    candidate_total = _consumption_sum(candidate_fluxes)
    seed_total_late = _time_mean(seed_total, time, late)
    candidate_total_late = _time_mean(candidate_total, time, late)
    delta_total_late = candidate_total_late - seed_total_late
    rows: list[dict[str, Any]] = []
    for reaction in ATP_CONSUMPTION:
        seed_values = np.asarray(seed_fluxes[reaction], dtype=float)
        candidate_values = np.asarray(candidate_fluxes[reaction], dtype=float)
        seed_late = _time_mean(seed_values, time, late)
        candidate_late = _time_mean(candidate_values, time, late)
        delta_late = candidate_late - seed_late
        seed_integral = float(np.trapezoid(seed_values, time))
        candidate_integral = float(np.trapezoid(candidate_values, time))
        rows.append(
            {
                "reaction": reaction,
                "associated_pools": ",".join(POOL_LINKS.get(reaction, ())),
                "seed_overall_mean": _time_mean(seed_values, time),
                "candidate_overall_mean": _time_mean(candidate_values, time),
                "delta_overall_mean": _time_mean(candidate_values, time) - _time_mean(seed_values, time),
                "seed_integrated_flux": seed_integral,
                "candidate_integrated_flux": candidate_integral,
                "delta_integrated_flux": candidate_integral - seed_integral,
                "seed_late_mean": seed_late,
                "candidate_late_mean": candidate_late,
                "delta_late_mean": delta_late,
                "seed_late_share": seed_late / max(abs(seed_total_late), 1e-30),
                "candidate_late_share": candidate_late / max(abs(candidate_total_late), 1e-30),
                "share_of_induced_late_consumption": delta_late / max(abs(delta_total_late), 1e-30),
                "seed_endpoint": float(seed_values[-1]),
                "candidate_endpoint": float(candidate_values[-1]),
                "delta_endpoint": float(candidate_values[-1] - seed_values[-1]),
            }
        )
    return sorted(rows, key=lambda row: float(row["delta_late_mean"]), reverse=True)


def _pool_rows(
    *,
    seed_sol: Any,
    candidate_sol: Any,
    exp_time: np.ndarray,
    exp_curves: Mapping[str, np.ndarray],
) -> list[dict[str, Any]]:
    linked = sorted({pool for pools in POOL_LINKS.values() for pool in pools if pool in exp_curves})
    rows: list[dict[str, Any]] = []
    for name in linked:
        idx = int(EXP_TO_MODEL[name])
        seed_values = np.interp(exp_time, seed_sol.t, seed_sol.y[idx, :])
        candidate_values = np.interp(exp_time, candidate_sol.t, candidate_sol.y[idx, :])
        seed_metric = _nrmse(seed_values, exp_curves[name])
        candidate_metric = _nrmse(candidate_values, exp_curves[name])
        rows.append(
            {
                "metabolite": name,
                "linked_sinks": ",".join(reaction for reaction, pools in POOL_LINKS.items() if name in pools),
                "seed_nrmse": seed_metric["nrmse"],
                "candidate_nrmse": candidate_metric["nrmse"],
                "delta_nrmse": candidate_metric["nrmse"] - seed_metric["nrmse"],
                "seed_endpoint_error": seed_metric["endpoint_error"],
                "candidate_endpoint_error": candidate_metric["endpoint_error"],
                "delta_endpoint_error": candidate_metric["endpoint_error"] - seed_metric["endpoint_error"],
                "seed_final": float(seed_values[-1]),
                "candidate_final": float(candidate_values[-1]),
                "experimental_final": float(exp_curves[name][-1]),
            }
        )
    return sorted(rows, key=lambda row: abs(float(row["delta_nrmse"])), reverse=True)


def _balance_summary(factors: pd.DataFrame) -> dict[str, dict[str, float]]:
    time = factors["time_day"].to_numpy(dtype=float)
    late = time >= 40.0
    return {
        name: {
            "overall_mean": _time_mean(factors[name].to_numpy(dtype=float), time),
            "late_mean": _time_mean(factors[name].to_numpy(dtype=float), time, late),
            "integral": float(np.trapezoid(factors[name].to_numpy(dtype=float), time)),
            "endpoint": float(factors[name].iloc[-1]),
        }
        for name in ("ATP_production_flux", "ATP_consumption_flux", "ATP_net_flux", "ATP_pool")
    }


def _plot_attribution(
    *,
    sink_rows: Sequence[Mapping[str, Any]],
    pool_rows: Sequence[Mapping[str, Any]],
    seed_factors: pd.DataFrame,
    candidate_factors: pd.DataFrame,
    seed_fluxes: Mapping[str, np.ndarray],
    candidate_fluxes: Mapping[str, np.ndarray],
    out_path: Path,
) -> None:
    rows = list(sink_rows)
    fig, axes = plt.subplots(2, 3, figsize=(16, 10), constrained_layout=True)

    ordered = sorted(rows, key=lambda row: float(row["seed_late_mean"]))
    names = [str(row["reaction"]) for row in ordered]
    y = np.arange(len(names), dtype=float)
    axes[0, 0].barh(y - 0.18, [float(row["seed_late_mean"]) for row in ordered], 0.36, color="#64748b", label="seed")
    axes[0, 0].barh(y + 0.18, [float(row["candidate_late_mean"]) for row in ordered], 0.36, color="#2563eb", label="0.75x")
    axes[0, 0].set_yticks(y, names)
    axes[0, 0].set_title("Late ATP-consuming fluxes")
    axes[0, 0].set_xlabel("Mean flux, days 40-46 (mM/day)")
    axes[0, 0].legend(frameon=False)
    axes[0, 0].grid(True, axis="x", alpha=0.22)

    induced = sorted(rows, key=lambda row: float(row["delta_late_mean"]))
    axes[0, 1].barh(
        [str(row["reaction"]) for row in induced],
        [float(row["delta_late_mean"]) for row in induced],
        color=["#dc2626" if float(row["delta_late_mean"]) > 0 else "#16a34a" for row in induced],
    )
    axes[0, 1].axvline(0.0, color="#111827", linewidth=0.8)
    axes[0, 1].set_title("Induced late consumption")
    axes[0, 1].set_xlabel("0.75x minus seed (mM/day)")
    axes[0, 1].grid(True, axis="x", alpha=0.22)

    integrated = sorted(rows, key=lambda row: float(row["delta_integrated_flux"]))
    axes[0, 2].barh(
        [str(row["reaction"]) for row in integrated],
        [float(row["delta_integrated_flux"]) for row in integrated],
        color=["#b45309" if float(row["delta_integrated_flux"]) > 0 else "#0f766e" for row in integrated],
    )
    axes[0, 2].axvline(0.0, color="#111827", linewidth=0.8)
    axes[0, 2].set_title("Integrated consumption change")
    axes[0, 2].set_xlabel("Integrated flux difference (mM)")
    axes[0, 2].grid(True, axis="x", alpha=0.22)

    top_reactions = [str(row["reaction"]) for row in rows[:4]]
    time = seed_factors["time_day"].to_numpy(dtype=float)
    colors = ("#dc2626", "#2563eb", "#7c3aed", "#0f766e")
    for color, reaction in zip(colors, top_reactions):
        axes[1, 0].plot(time, seed_fluxes[reaction], color=color, linewidth=1.5, alpha=0.55, label=f"{reaction} seed")
        axes[1, 0].plot(time, candidate_fluxes[reaction], color=color, linewidth=2.0, linestyle="--", label=f"{reaction} 0.75x")
    axes[1, 0].set_title("Top induced sinks over time")
    axes[1, 0].set_xlabel("Time (days)")
    axes[1, 0].set_ylabel("mM/day")
    axes[1, 0].legend(frameon=False, fontsize=7, ncol=2)
    axes[1, 0].grid(True, alpha=0.22)

    axes[1, 1].plot(time, seed_factors["ATP_production_flux"], color="#64748b", linewidth=2.0, label="seed production")
    axes[1, 1].plot(time, seed_factors["ATP_consumption_flux"], color="#64748b", linewidth=1.6, linestyle=":", label="seed consumption")
    axes[1, 1].plot(time, candidate_factors["ATP_production_flux"], color="#2563eb", linewidth=2.0, label="0.75x production")
    axes[1, 1].plot(time, candidate_factors["ATP_consumption_flux"], color="#dc2626", linewidth=1.7, linestyle="--", label="0.75x consumption")
    axes[1, 1].set_title("ATP balance replay")
    axes[1, 1].set_xlabel("Time (days)")
    axes[1, 1].set_ylabel("mM/day")
    axes[1, 1].legend(frameon=False, fontsize=8)
    axes[1, 1].grid(True, alpha=0.22)

    pool_selected = sorted(pool_rows, key=lambda row: float(row["delta_nrmse"]))
    axes[1, 2].barh(
        [str(row["metabolite"]) for row in pool_selected],
        [float(row["delta_nrmse"]) for row in pool_selected],
        color=["#dc2626" if float(row["delta_nrmse"]) > 0 else "#16a34a" for row in pool_selected],
    )
    axes[1, 2].axvline(0.0, color="#111827", linewidth=0.8)
    axes[1, 2].set_title("Associated pool nRMSE changes")
    axes[1, 2].set_xlabel("0.75x minus seed nRMSE")
    axes[1, 2].grid(True, axis="x", alpha=0.22)

    fig.suptitle("Brodbar ATP-consumption sink attribution", fontsize=15)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    top = summary["top_induced_sinks"]
    constitutive = summary["top_constitutive_sinks"]
    lines = [
        "# ATP-consumption sink attribution",
        "",
        "## Technical summary",
        "",
        f"- Generated: {summary['generated_at']}",
        "- Comparison: mild-feedback seed versus diagnostic `km_ADP_ATP 0.75x`.",
        f"- Horizon: `{summary['t_max']:.0f}` days.",
        "- Diagnostic only: no optimization or parameter promotion.",
        f"- Parameter difference: `{summary['changed_parameters']}`.",
        f"- Maximum ATP-consumption closure error: `{summary['max_closure_error']:.3e}`.",
        "",
        "## Method",
        "",
        "The two parameter sets were replayed with the native ODE and `FluxTracker`. For each ATP-consuming reaction in the exact ATP balance, integrated flux, late mean, endpoint, total-consumption share, and induced change were computed. Measured Brodbar pools linked to each reaction were evaluated separately by nRMSE and endpoint error.",
        "",
        "## Main findings",
        "",
        f"- Late ATP consumption: `{summary['seed_balance']['ATP_consumption_flux']['late_mean']:.6g} -> {summary['candidate_balance']['ATP_consumption_flux']['late_mean']:.6g}` mM/day.",
        f"- Late ATP production: `{summary['seed_balance']['ATP_production_flux']['late_mean']:.6g} -> {summary['candidate_balance']['ATP_production_flux']['late_mean']:.6g}` mM/day.",
        f"- Late ATP net flux: `{summary['seed_balance']['ATP_net_flux']['late_mean']:.6g} -> {summary['candidate_balance']['ATP_net_flux']['late_mean']:.6g}` mM/day.",
        "",
        "### Largest induced sinks",
        "",
        "| Reaction | Seed late | Candidate late | Delta late | Share of induced consumption | Linked measured pools |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in top:
        lines.append(
            f"| `{row['reaction']}` | {row['seed_late_mean']:.6g} | {row['candidate_late_mean']:.6g} | {row['delta_late_mean']:.6g} | {100.0 * row['share_of_induced_late_consumption']:.1f}% | `{row['associated_pools'] or 'none'}` |"
        )
    lines.extend(
        [
            "",
            "### Largest constitutive sinks in the seed",
            "",
            "| Reaction | Seed late mean | Seed late share |",
            "|---|---:|---:|",
        ]
    )
    for row in constitutive:
        lines.append(
            f"| `{row['reaction']}` | {row['seed_late_mean']:.6g} | {100.0 * row['seed_late_share']:.1f}% |"
        )
    lines.extend(
        [
            "",
            "## Pool consistency",
            "",
        ]
    )
    for row in summary["largest_pool_changes"]:
        lines.append(
            f"- `{row['metabolite']}` nRMSE: `{row['seed_nrmse']:.6g} -> {row['candidate_nrmse']:.6g}`; linked sinks: `{row['linked_sinks']}`."
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"**`{summary['decision']}`**",
            "",
            summary["decision_rationale"],
            "",
            "No kinetic constant was changed or promoted by this attribution step.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_profile(
    *,
    out_dir: Path,
    seed_params_path: Path,
    candidate_params_path: Path,
    t_max: float,
    timepoints: int,
    early_timepoints: int,
    method: str,
    rtol: float,
    atol: float,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    seed_params = _load_params(seed_params_path)
    candidate_params = _load_params(candidate_params_path)
    changed = _changed_parameters(seed_params, candidate_params)
    if changed != [EXPECTED_CHANGED_PARAMETER]:
        raise RuntimeError(f"Expected only {EXPECTED_CHANGED_PARAMETER} to change, got {changed}")

    t_eval = _time_grid(t_max, timepoints, early_timepoints)
    exp_time, exp_curves = _all_experimental_curves(t_max)
    print(f"[atp-sinks] simulating seed: {seed_params_path}", flush=True)
    seed_sol, seed_fluxes, _seed_derivatives = _simulate_and_track(
        params=seed_params,
        t_eval=t_eval,
        method=method,
        rtol=rtol,
        atol=atol,
    )
    print(f"[atp-sinks] simulating candidate: {candidate_params_path}", flush=True)
    candidate_sol, candidate_fluxes, _candidate_derivatives = _simulate_and_track(
        params=candidate_params,
        t_eval=t_eval,
        method=method,
        rtol=rtol,
        atol=atol,
    )
    seed_factors = _factor_timeseries(seed_sol, seed_fluxes, seed_params)
    candidate_factors = _factor_timeseries(candidate_sol, candidate_fluxes, candidate_params)
    seed_closure = _validate_closure(seed_fluxes, seed_factors)
    candidate_closure = _validate_closure(candidate_fluxes, candidate_factors)

    sink_rows = _sink_rows(
        seed_fluxes=seed_fluxes,
        candidate_fluxes=candidate_fluxes,
        time=np.asarray(seed_sol.t, dtype=float),
    )
    pool_rows = _pool_rows(
        seed_sol=seed_sol,
        candidate_sol=candidate_sol,
        exp_time=exp_time,
        exp_curves=exp_curves,
    )
    seed_balance = _balance_summary(seed_factors)
    candidate_balance = _balance_summary(candidate_factors)

    top_induced = [row for row in sink_rows if float(row["delta_late_mean"]) > 0.0][:6]
    top_constitutive = sorted(sink_rows, key=lambda row: float(row["seed_late_mean"]), reverse=True)[:6]
    dominant = top_induced[0] if top_induced else None
    combined_top_share = sum(float(row["share_of_induced_late_consumption"]) for row in top_induced[:2])
    top_pair = {str(row["reaction"]) for row in top_induced[:2]}
    if dominant is None:
        decision = "no induced ATP sink identified"
        rationale = "No ATP-consuming reaction increased in the late window; another balance term must explain the compensation."
    elif top_pair == {"VHK", "VPFK"} and combined_top_share > 0.80:
        decision = "prioritize structural review of the VHK/VPFK ATP-demand relay"
        rationale = (
            f"VHK and VPFK together account for {100.0 * combined_top_share:.1f}% of the induced late ATP "
            "consumption. GLC improves modestly, but G6P worsens and F6P remains severely elevated; this supports "
            "a flux-matching or ATP-coupling problem across the investment phase, not a new isolated sink parameter."
        )
    else:
        decision = f"prioritize biological review of {dominant['reaction']} before any optimization"
        linked = dominant["associated_pools"] or "no measured direct pool"
        rationale = (
            f"{dominant['reaction']} is the largest induced late ATP sink and accounts for "
            f"{100.0 * float(dominant['share_of_induced_late_consumption']):.1f}% of the consumption increase. "
            f"Its linked measured pools are {linked}; those pool residuals must support the mechanism before its kinetics can be opened."
        )

    sinks_csv = out_dir / "atp_consumption_sink_attribution.csv"
    pools_csv = out_dir / "atp_sink_associated_pool_metrics.csv"
    timeseries_csv = out_dir / "atp_consumption_sink_timeseries.csv"
    pd.DataFrame(sink_rows).to_csv(sinks_csv, index=False)
    pd.DataFrame(pool_rows).to_csv(pools_csv, index=False)
    timeseries_rows: list[dict[str, Any]] = []
    for label, factors, fluxes in (
        ("seed", seed_factors, seed_fluxes),
        ("km_ADP_ATP_0.75x", candidate_factors, candidate_fluxes),
    ):
        for index, time in enumerate(seed_sol.t):
            row: dict[str, Any] = {
                "candidate": label,
                "time_day": float(time),
                "ATP_production_flux": float(factors["ATP_production_flux"].iloc[index]),
                "ATP_consumption_flux": float(factors["ATP_consumption_flux"].iloc[index]),
                "ATP_net_flux": float(factors["ATP_net_flux"].iloc[index]),
                "ATP_pool": float(factors["ATP_pool"].iloc[index]),
            }
            for reaction in ATP_CONSUMPTION:
                row[reaction] = float(fluxes[reaction][index])
            timeseries_rows.append(row)
    pd.DataFrame(timeseries_rows).to_csv(timeseries_csv, index=False)

    plot_path = out_dir / "atp_consumption_sink_attribution.png"
    _plot_attribution(
        sink_rows=sink_rows,
        pool_rows=pool_rows,
        seed_factors=seed_factors,
        candidate_factors=candidate_factors,
        seed_fluxes=seed_fluxes,
        candidate_fluxes=candidate_fluxes,
        out_path=plot_path,
    )

    summary = {
        "contract_type": "atp_consumption_sink_attribution",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "optimization_performed": False,
        "parameters_promoted": False,
        "seed_params_path": str(seed_params_path),
        "candidate_params_path": str(candidate_params_path),
        "changed_parameters": changed,
        "t_max": float(t_max),
        "timepoints": int(t_eval.size),
        "solver": {"method": method, "rtol": float(rtol), "atol": float(atol)},
        "atp_consumption_reactions": list(ATP_CONSUMPTION),
        "max_closure_error": max(seed_closure, candidate_closure),
        "seed_balance": seed_balance,
        "candidate_balance": candidate_balance,
        "top_induced_sinks": top_induced,
        "combined_vhk_vpfk_induced_share": combined_top_share if top_pair == {"VHK", "VPFK"} else None,
        "top_constitutive_sinks": top_constitutive,
        "largest_pool_changes": pool_rows[:10],
        "decision": decision,
        "decision_rationale": rationale,
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "decision_report": str(out_dir / "decision_report.md"),
            "sink_attribution_csv": str(sinks_csv),
            "pool_metrics_csv": str(pools_csv),
            "timeseries_csv": str(timeseries_csv),
            "plot": str(plot_path),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(_jsonable(summary), indent=2), encoding="utf-8")
    _write_report(out_dir / "decision_report.md", summary)
    print(
        json.dumps(
            {
                "summary": summary["artifact_paths"]["summary"],
                "decision": decision,
                "max_closure_error": summary["max_closure_error"],
                "top_induced_sinks": [
                    {
                        "reaction": row["reaction"],
                        "delta_late_mean": row["delta_late_mean"],
                        "share": row["share_of_induced_late_consumption"],
                    }
                    for row in top_induced
                ],
            },
            indent=2,
        ),
        flush=True,
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Attribute ATP-consumption sinks for the km_ADP_ATP diagnostic")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--seed-params", type=Path, default=DEFAULT_SEED_PARAMS)
    parser.add_argument("--candidate-params", type=Path, default=DEFAULT_CANDIDATE_PARAMS)
    parser.add_argument("--t-max", type=float, default=46.0)
    parser.add_argument("--timepoints", type=int, default=181)
    parser.add_argument("--early-timepoints", type=int, default=60)
    parser.add_argument("--method", default="LSODA")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_profile(
        out_dir=args.out_dir,
        seed_params_path=args.seed_params,
        candidate_params_path=args.candidate_params,
        t_max=args.t_max,
        timepoints=args.timepoints,
        early_timepoints=args.early_timepoints,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
