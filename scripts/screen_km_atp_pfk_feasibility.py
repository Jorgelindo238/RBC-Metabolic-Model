"""Screen downward ``km_ATP_PFK`` perturbations before any FLA optimization.

The screen replays a few directed points sequentially and stops immediately
when ATP or PEP violates the existing hard guards. It is diagnostic only and
cannot promote parameters.
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
DEFAULT_OUT_DIR = ROOT / "Simulations" / "brodbar" / "hermes" / "km_atp_pfk_feasibility_mild_feedback_46d"

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from MM_calibration import EXP_TO_MODEL, PHASE1_PARAMS, load_initial_conditions  # noqa: E402
from run_glucose_utilization_fla import (  # noqa: E402
    _build_lactate_teacher_dataset,
    _extract_brodbar_targets,
    _flatten_trial_rows,
    _jsonable,
)
from run_km_atp_hk_narrow_fla import (  # noqa: E402
    EXTRA_TARGETS,
    GUARD_CONCENTRATIONS,
    GUARD_FLUXES,
    GuardedKmAtpHkObjective,
    _full_experimental_curves,
)


PARAMETER = "km_ATP_PFK"
LOCKED_PARAMETERS = ("km_ATP_HK", "km_NADH_NAD")
DEFAULT_MULTIPLIERS = (0.90, 0.75, 0.50)
PLOT_TARGETS = ("EGLC", "ELAC", "GLC", "LAC", "PYR", "ATP", "PEP", "G6P")


class GuardedKmAtpPfkObjective(GuardedKmAtpHkObjective):
    """Reuse the guarded concentration/flux objective with one PFK lever."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.base.tracked_param_names = (PARAMETER,)


def _directed_values(center: float, multipliers: Sequence[float]) -> list[float]:
    lower = float(PHASE1_PARAMS[PARAMETER][1])
    values: list[float] = []
    previous = float(center)
    for multiplier in multipliers:
        value = max(lower, float(center) * float(multiplier))
        if not 0.0 < value < previous:
            raise ValueError("km_ATP_PFK feasibility points must be strictly decreasing")
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


def _hard_stop_reasons(seed: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if float(candidate["sim_final"]["ATP"]) < float(seed["sim_final"]["ATP"]) * 0.95:
        reasons.append("ATP endpoint below 95% of seed")

    seed_pep = seed["energy_metrics"]["PEP"]
    candidate_pep = candidate["energy_metrics"]["PEP"]
    if float(candidate_pep["nrmse"]) > float(seed_pep["nrmse"]) * 1.05 + 0.01:
        reasons.append("PEP nRMSE exceeded the hard guard")
    if float(candidate_pep["endpoint_error"]) > float(seed_pep["endpoint_error"]) * 1.10 + 0.01:
        reasons.append("PEP endpoint error exceeded the hard guard")
    return reasons


def _is_promising(seed: Mapping[str, Any], candidate: Mapping[str, Any]) -> bool:
    if _hard_stop_reasons(seed, candidate) or candidate.get("guard_violations"):
        return False
    direct_gain = any(
        float(candidate["metrics"].get(name, candidate["energy_metrics"].get(name))["nrmse"])
        < float(seed["metrics"].get(name, seed["energy_metrics"].get(name))["nrmse"]) * 0.99
        for name in ("GLC", "G6P", "LAC")
    )
    return float(candidate["loss"]) < float(seed["loss"]) and direct_gain


def _metric(payload: Mapping[str, Any], name: str) -> Mapping[str, float]:
    return payload["metrics"].get(name, payload["energy_metrics"].get(name, {}))


def _plot_screen(
    *,
    seed: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    objective: GuardedKmAtpPfkObjective,
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(3, 4, figsize=(15, 11))
    colors = ("#2563eb", "#7c3aed", "#dc2626")
    for ax, name in zip(axes.flat[:8], PLOT_TARGETS):
        idx = int(EXP_TO_MODEL[name])
        ax.plot(seed["sol"].t, seed["sol"].y[idx, :], color="#64748b", linewidth=2.0, label="seed")
        for color, candidate in zip(colors, candidates):
            multiplier = float(candidate["params"][PARAMETER]) / float(seed["params"][PARAMETER])
            ax.plot(
                candidate["sol"].t,
                candidate["sol"].y[idx, :],
                color=color,
                linewidth=1.9,
                linestyle="--",
                label=f"{multiplier:.2f}x",
            )
        ax.scatter(objective.exp_time, objective.exp_curves[name], color="#111827", s=18, zorder=3, label="Brodbar")
        ax.set_title(name)
        ax.set_xlabel("Time (days)")
        ax.set_ylabel("mM")
        ax.grid(True, alpha=0.22)

    for ax, reaction in zip(axes.flat[8:11], GUARD_FLUXES):
        target = objective.teacher_dataset["reaction_flux_curves"][reaction]
        ax.plot(objective.base.teacher_time, target["dense_values"], color="#111827", linewidth=2.0, label="teacher")
        ax.plot(objective.base.teacher_time, seed["sim_flux"][reaction], color="#64748b", linewidth=2.0, label="seed")
        for color, candidate in zip(colors, candidates):
            multiplier = float(candidate["params"][PARAMETER]) / float(seed["params"][PARAMETER])
            ax.plot(
                objective.base.teacher_time,
                candidate["sim_flux"][reaction],
                color=color,
                linewidth=1.9,
                linestyle="--",
                label=f"{multiplier:.2f}x",
            )
        ax.set_title(f"{reaction} flux")
        ax.set_xlabel("Time (days)")
        ax.set_ylabel("mM/day")
        ax.grid(True, alpha=0.22)

    ax = axes.flat[11]
    x_labels = ["seed"] + [f"{float(c['params'][PARAMETER]) / float(seed['params'][PARAMETER]):.2f}x" for c in candidates]
    atp_values = [float(seed["sim_final"]["ATP"])] + [float(c["sim_final"]["ATP"]) for c in candidates]
    pep_values = [float(seed["energy_metrics"]["PEP"]["nrmse"])] + [
        float(c["energy_metrics"]["PEP"]["nrmse"]) for c in candidates
    ]
    x = np.arange(len(x_labels), dtype=float)
    ax.plot(x, atp_values, color="#0f766e", marker="o", linewidth=2.0, label="ATP endpoint")
    ax.set_xticks(x, x_labels)
    ax.set_ylabel("ATP endpoint (mM)", color="#0f766e")
    ax.tick_params(axis="y", labelcolor="#0f766e")
    ax2 = ax.twinx()
    ax2.plot(x, pep_values, color="#b91c1c", marker="s", linewidth=2.0, label="PEP nRMSE")
    ax2.set_ylabel("PEP nRMSE", color="#b91c1c")
    ax2.tick_params(axis="y", labelcolor="#b91c1c")
    ax.set_title("Hard-guard dose response")
    ax.grid(True, alpha=0.22)

    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.965), ncol=max(3, len(handles)), frameon=False)
    fig.suptitle("Brodbar feasibility screen: km_ATP_PFK downward only", fontsize=15, y=0.995)
    fig.subplots_adjust(top=0.89, hspace=0.34, wspace=0.30)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    seed = summary["seed"]
    lines = [
        "# Directed `km_ATP_PFK` feasibility screen",
        "",
        "## Technical summary",
        "",
        f"- Generated: {summary['generated_at']}",
        "- Dataset: Brodbar control concentrations and derived teacher fluxes.",
        f"- Horizon: `{summary['t_max']:.0f}` days.",
        "- Diagnostic only: no Optuna optimization and no parameter promotion.",
        f"- Seed `km_ATP_PFK`: `{seed['params'][PARAMETER]:.12g}`.",
        f"- Locked `km_ATP_HK`: `{summary['locked_params']['km_ATP_HK']:.12g}`.",
        f"- Locked `km_NADH_NAD`: `{summary['locked_params']['km_NADH_NAD']:.12g}`.",
        "",
        "## Method",
        "",
        "Downward `km_ATP_PFK` perturbations were replayed sequentially through the complete ODE. A point was stopped before any stronger perturbation when ATP fell below 95% of the seed endpoint or when PEP exceeded its existing nRMSE or endpoint guard. All concentration and teacher-flux guards from the preceding mono-parameter passes remained active.",
        "",
        "## Results",
        "",
    ]
    for point in summary["evaluated_points"]:
        lines.extend(
            [
                f"### `{point['multiplier']:.2f}x` seed",
                "",
                f"- `km_ATP_PFK = {point['value']:.12g}`.",
                f"- Focused loss: `{seed['loss']:.6g} -> {point['loss']:.6g}`.",
                f"- ATP endpoint: `{seed['sim_final']['ATP']:.6g} -> {point['atp_endpoint']:.6g}` mM.",
                f"- PEP nRMSE: `{_metric(seed, 'PEP')['nrmse']:.6g} -> {point['pep_nrmse']:.6g}`.",
                f"- G6P nRMSE: `{_metric(seed, 'G6P')['nrmse']:.6g} -> {point['g6p_nrmse']:.6g}`.",
                f"- GLC nRMSE: `{_metric(seed, 'GLC')['nrmse']:.6g} -> {point['glc_nrmse']:.6g}`.",
                f"- Hard stop: `{point['hard_stop']}` ({'; '.join(point['hard_stop_reasons']) or 'none'}).",
                f"- All guard violations: `{'; '.join(point['guard_violations']) or 'none'}`.",
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
            "No full-panel replay was required because this screen cannot promote parameters. The full panel remains mandatory if a later optimization produces a focused candidate.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_screen(
    *,
    out_dir: Path,
    seed_params_path: Path,
    multipliers: Sequence[float],
    t_max: float,
    teacher_dense_points: int,
    method: str,
    rtol: float,
    atol: float,
    energy_weight: float,
    energy_endpoint_weight: float,
    guard_weight: float,
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

    exp_time, base_curves = _extract_brodbar_targets(t_max)
    full_time, full_curves = _full_experimental_curves(t_max)
    if not np.allclose(exp_time, full_time):
        raise RuntimeError("Brodbar target time grids are inconsistent")
    teacher_path = out_dir / "teacher_flux_dataset_km_atp_pfk.json"
    teacher_dataset = _build_lactate_teacher_dataset(
        exp_time=exp_time,
        exp_curves=base_curves,
        dense_points=teacher_dense_points,
        out_path=teacher_path,
    )

    objective = GuardedKmAtpPfkObjective(
        x0=np.asarray(load_initial_conditions(), dtype=float),
        seed_params=seed_params,
        exp_time=exp_time,
        exp_curves=full_curves,
        teacher_dataset=teacher_dataset,
        method=method,
        rtol=rtol,
        atol=atol,
        energy_weight=energy_weight,
        energy_endpoint_weight=energy_endpoint_weight,
        guard_weight=guard_weight,
    )
    print(f"{PARAMETER} seed: {center:.17g}", flush=True)
    print(
        ", ".join(f"{name} locked: {float(seed_params[name]):.17g}" for name in LOCKED_PARAMETERS),
        flush=True,
    )
    print(f"directed values: {', '.join(f'{value:.9g}' for value in values)}", flush=True)

    seed_eval = objective.evaluate({PARAMETER: center}, label="mild_feedback_seed")
    objective.seed_reference = seed_eval
    objective.base.seed_guard_reference = seed_eval
    objective.best_payload = seed_eval

    candidate_payloads: list[dict[str, Any]] = []
    point_summaries: list[dict[str, Any]] = []
    stopped_early = False
    for index, (multiplier, value) in enumerate(zip(multipliers, values)):
        payload = objective.evaluate({PARAMETER: value}, label=f"screen_{index}_{multiplier:.2f}x")
        candidate_params = dict(seed_params)
        candidate_params[PARAMETER] = value
        _validate_locks(seed_params, candidate_params)
        hard_reasons = _hard_stop_reasons(seed_eval, payload)
        hard_stop = bool(hard_reasons)
        promising = _is_promising(seed_eval, payload)
        point = {
            "multiplier": float(multiplier),
            "value": float(value),
            "loss": float(payload["loss"]),
            "atp_endpoint": float(payload["sim_final"]["ATP"]),
            "pep_nrmse": float(payload["energy_metrics"]["PEP"]["nrmse"]),
            "pep_endpoint_error": float(payload["energy_metrics"]["PEP"]["endpoint_error"]),
            "g6p_nrmse": float(payload["energy_metrics"]["G6P"]["nrmse"]),
            "glc_nrmse": float(payload["metrics"]["GLC"]["nrmse"]),
            "lac_nrmse": float(payload["metrics"]["LAC"]["nrmse"]),
            "guard_violations": list(payload.get("guard_violations", [])),
            "hard_stop": hard_stop,
            "hard_stop_reasons": hard_reasons,
            "promising": promising,
        }
        point_summaries.append(point)
        candidate_payloads.append(payload)
        print(
            f"point {multiplier:.2f}x: loss={payload['loss']:.5f}, ATP={point['atp_endpoint']:.6g}, "
            f"PEP={point['pep_nrmse']:.4f}, G6P={point['g6p_nrmse']:.4f}, "
            f"GLC={point['glc_nrmse']:.4f}, hard_stop={','.join(hard_reasons) or 'none'}, "
            f"guards={','.join(point['guard_violations']) or 'none'}",
            flush=True,
        )
        if hard_stop:
            stopped_early = index < len(values) - 1
            break

    promising_points = [point for point in point_summaries if point["promising"]]
    if any(point["hard_stop"] for point in point_summaries):
        decision = "abort km_ATP_PFK hypothesis before optimization"
        rationale = "A downward perturbation crossed an ATP or PEP hard guard, so stronger points and Optuna are not justified."
    elif promising_points:
        decision = "proceed to a narrow km_ATP_PFK optimization"
        rationale = "At least one downward point improved the focused objective and a direct glycolysis target without violating guards."
    elif any(point["guard_violations"] for point in point_summaries):
        decision = "do not optimize km_ATP_PFK"
        rationale = (
            "The mild point did not provide a sufficient direct glycolysis gain, while stronger downward points "
            "violated the G6P guard and worsened GLC despite higher ATP."
        )
    else:
        decision = "do not optimize km_ATP_PFK"
        rationale = "The screened points did not provide a sufficient guarded direct glycolysis benefit."

    seed_path = out_dir / "seed_params.json"
    retained_path = out_dir / "retained_seed_params.json"
    seed_path.write_text(json.dumps(_jsonable(seed_params), indent=2), encoding="utf-8")
    retained_path.write_text(json.dumps(_jsonable(seed_params), indent=2), encoding="utf-8")
    for point, payload in zip(point_summaries, candidate_payloads):
        params = dict(seed_params)
        params[PARAMETER] = float(payload["params"][PARAMETER])
        point_path = out_dir / f"screen_params_{point['multiplier']:.2f}x.json"
        point_path.write_text(json.dumps(_jsonable(params), indent=2), encoding="utf-8")
        point["params_path"] = str(point_path)

    trials_csv = out_dir / "screen_trials.csv"
    pd.DataFrame(_flatten_trial_rows(objective.trials)).to_csv(trials_csv, index=False)
    metrics_rows: list[dict[str, Any]] = []
    for point, payload in zip(point_summaries, candidate_payloads):
        for name in PLOT_TARGETS:
            seed_metric = _metric(seed_eval, name)
            candidate_metric = _metric(payload, name)
            metrics_rows.append(
                {
                    "multiplier": point["multiplier"],
                    "parameter_value": point["value"],
                    "metabolite": name,
                    "seed_nrmse": seed_metric["nrmse"],
                    "candidate_nrmse": candidate_metric["nrmse"],
                    "delta_nrmse": candidate_metric["nrmse"] - seed_metric["nrmse"],
                    "seed_endpoint_error": seed_metric["endpoint_error"],
                    "candidate_endpoint_error": candidate_metric["endpoint_error"],
                }
            )
        for reaction in GUARD_FLUXES:
            seed_flux = seed_eval["teacher_flux_details"][reaction]
            candidate_flux = payload["teacher_flux_details"][reaction]
            metrics_rows.append(
                {
                    "multiplier": point["multiplier"],
                    "parameter_value": point["value"],
                    "metabolite": reaction,
                    "seed_nrmse": seed_flux["nrmse"],
                    "candidate_nrmse": candidate_flux["nrmse"],
                    "delta_nrmse": candidate_flux["nrmse"] - seed_flux["nrmse"],
                    "seed_endpoint_error": np.nan,
                    "candidate_endpoint_error": np.nan,
                }
            )
    metrics_csv = out_dir / "screen_metrics.csv"
    pd.DataFrame(metrics_rows).to_csv(metrics_csv, index=False)

    plot_path = out_dir / "km_atp_pfk_feasibility_screen.png"
    _plot_screen(seed=seed_eval, candidates=candidate_payloads, objective=objective, out_path=plot_path)

    locked_params = _validate_locks(seed_params, seed_params)
    summary = {
        "contract_type": "km_atp_pfk_directed_feasibility_screen",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "optimization_performed": False,
        "parameters_promoted": False,
        "seed_params_path": str(seed_params_path),
        "screened_parameter": PARAMETER,
        "locked_params": locked_params,
        "planned_multipliers": [float(value) for value in multipliers],
        "planned_values": values,
        "t_max": float(t_max),
        "teacher_dense_points": int(teacher_dense_points),
        "solver": {"method": method, "rtol": float(rtol), "atol": float(atol)},
        "hard_guards": ["ATP endpoint floor", "PEP nRMSE", "PEP endpoint error"],
        "all_guarded_targets": list(GUARD_CONCENTRATIONS),
        "all_guarded_fluxes": list(GUARD_FLUXES),
        "stopped_early": stopped_early,
        "evaluated_point_count": len(point_summaries),
        "evaluated_points": point_summaries,
        "promising_point_count": len(promising_points),
        "decision": decision,
        "decision_rationale": rationale,
        "seed": {key: value for key, value in seed_eval.items() if key not in {"sol", "sim_exp", "sim_flux"}},
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "decision_report": str(out_dir / "decision_report.md"),
            "seed_params": str(seed_path),
            "retained_seed_params": str(retained_path),
            "teacher_dataset": str(teacher_path),
            "trials_csv": str(trials_csv),
            "metrics_csv": str(metrics_csv),
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
    parser = argparse.ArgumentParser(description="Screen downward km_ATP_PFK feasibility with hard ATP/PEP stops")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--seed-params", type=Path, default=DEFAULT_SEED_PARAMS)
    parser.add_argument("--multipliers", default=",".join(str(value) for value in DEFAULT_MULTIPLIERS))
    parser.add_argument("--t-max", type=float, default=46.0)
    parser.add_argument("--teacher-dense-points", type=int, default=96)
    parser.add_argument("--method", default="LSODA")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    parser.add_argument("--energy-weight", type=float, default=3.0)
    parser.add_argument("--energy-endpoint-weight", type=float, default=4.0)
    parser.add_argument("--guard-weight", type=float, default=20.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_screen(
        out_dir=args.out_dir,
        seed_params_path=args.seed_params,
        multipliers=_parse_multipliers(args.multipliers),
        t_max=args.t_max,
        teacher_dense_points=args.teacher_dense_points,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
        energy_weight=args.energy_weight,
        energy_endpoint_weight=args.energy_endpoint_weight,
        guard_weight=args.guard_weight,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
