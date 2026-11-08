"""Run a narrow, guarded Brodbar FLA pass for ``km_NADH_NAD`` only.

The mild-feedback seed is replayed with ``km_ATP_HK`` reset to and locked at
its seed value. The single open parameter probes the VLDH redox affinity while
concentrations, teacher fluxes, ATP, and the full Brodbar panel remain guarded.
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
DEFAULT_OUT_DIR = ROOT / "Simulations" / "brodbar" / "hermes" / "km_nadh_nad_narrow_mild_feedback_46d"

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from MM_calibration import EXP_TO_MODEL, load_initial_conditions, should_use_log_sampling  # noqa: E402
from evaluate_brodbar_candidate_full_panel import run_evaluation as run_full_panel  # noqa: E402
from run_glucose_utilization_fla import (  # noqa: E402
    HAS_OPTUNA,
    _build_lactate_teacher_dataset,
    _extract_brodbar_targets,
    _flatten_trial_rows,
    _jsonable,
    _local_bounds,
    optuna,
)
from run_km_atp_hk_narrow_fla import (  # noqa: E402
    EXTRA_TARGETS,
    GUARD_CONCENTRATIONS,
    GUARD_FLUXES,
    TARGET_WEIGHTS,
    GuardedKmAtpHkObjective,
    _final_value,
    _full_experimental_curves,
    _panel_acceptance,
)


PARAMETER = "km_NADH_NAD"
LOCKED_PARAMETER = "km_ATP_HK"
CORE_TARGETS = ("EGLC", "ELAC", "GLC", "LAC", "PYR")


class GuardedKmNadhNadObjective(GuardedKmAtpHkObjective):
    """Reuse the guarded objective while opening only the VLDH redox affinity."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.base.tracked_param_names = (PARAMETER,)


def _validate_fixed_param_lock(
    seed_params: Mapping[str, Any],
    candidate_params: Mapping[str, Any],
) -> float:
    seed_value = float(seed_params[LOCKED_PARAMETER])
    candidate_value = float(candidate_params[LOCKED_PARAMETER])
    if not math.isclose(candidate_value, seed_value, rel_tol=0.0, abs_tol=1e-15):
        raise RuntimeError(
            f"{LOCKED_PARAMETER} lock failed: seed={seed_value:.17g}, candidate={candidate_value:.17g}"
        )
    return seed_value


def _acceptance(seed: Mapping[str, Any], candidate: Mapping[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not float(candidate["loss"]) < float(seed["loss"]):
        reasons.append("focused guarded loss did not improve")

    vldh_improved = (
        float(candidate["teacher_flux_details"]["VLDH"]["nrmse"])
        < float(seed["teacher_flux_details"]["VLDH"]["nrmse"]) * 0.98
    )
    lac_improved = float(candidate["metrics"]["LAC"]["nrmse"]) < float(seed["metrics"]["LAC"]["nrmse"]) * 0.98
    if not (vldh_improved or lac_improved):
        reasons.append("neither VLDH teacher nRMSE nor LAC nRMSE improved by 2%")

    glc_limit = float(seed["metrics"]["GLC"]["nrmse"]) * 1.02 + 0.01
    if float(candidate["metrics"]["GLC"]["nrmse"]) > glc_limit:
        reasons.append("GLC nRMSE regressed beyond the 2% guard")
    if float(candidate["sim_final"]["ATP"]) < float(seed["sim_final"]["ATP"]) * 0.95:
        reasons.append("ATP endpoint floor failed")
    if candidate.get("guard_violations"):
        reasons.extend(candidate["guard_violations"])
    return not reasons, reasons or ["candidate passed focused km_NADH_NAD redox guards"]


def _plot_result(
    *,
    seed: Mapping[str, Any],
    candidate: Mapping[str, Any],
    objective: GuardedKmNadhNadObjective,
    out_path: Path,
) -> None:
    names = ("EGLC", "ELAC", "GLC", "LAC", "PYR", "ATP", "PEP", "G6P")
    fig, axes = plt.subplots(3, 4, figsize=(15, 11))
    for ax, name in zip(axes.flat[:8], names):
        idx = int(EXP_TO_MODEL[name])
        ax.plot(seed["sol"].t, seed["sol"].y[idx, :], color="#64748b", linewidth=1.8, label="seed")
        ax.plot(
            candidate["sol"].t,
            candidate["sol"].y[idx, :],
            color="#2563eb",
            linewidth=2.2,
            linestyle="--",
            label="redox candidate",
        )
        ax.scatter(objective.exp_time, objective.exp_curves[name], color="#111827", s=18, label="Brodbar", zorder=3)
        metric = candidate["metrics"].get(name, candidate["energy_metrics"].get(name, {}))
        ax.set_title(f"{name} nRMSE {metric.get('nrmse', float('nan')):.2f}")
        ax.set_xlabel("Time (days)")
        ax.set_ylabel("mM")
        ax.grid(True, alpha=0.22)

    for ax, reaction in zip(axes.flat[8:11], GUARD_FLUXES):
        target = objective.teacher_dataset["reaction_flux_curves"][reaction]
        ax.plot(objective.base.teacher_time, target["dense_values"], color="#111827", linewidth=2.0, label="teacher")
        ax.plot(objective.base.teacher_time, seed["sim_flux"][reaction], color="#64748b", linewidth=1.8, label="seed")
        ax.plot(
            objective.base.teacher_time,
            candidate["sim_flux"][reaction],
            color="#2563eb",
            linewidth=2.2,
            linestyle="--",
            label="candidate",
        )
        ax.set_title(f"{reaction} flux")
        ax.set_xlabel("Time (days)")
        ax.set_ylabel("mM/day")
        ax.grid(True, alpha=0.22)

    ax = axes.flat[11]
    labels = ["VLDH", "LAC", "ELAC", "GLC", "ATP", "G6P"]
    deltas: list[float] = []
    for name in labels:
        if name == "VLDH":
            seed_metric = seed["teacher_flux_details"][name]
            candidate_metric = candidate["teacher_flux_details"][name]
        else:
            seed_metric = seed["metrics"].get(name, seed["energy_metrics"].get(name, {}))
            candidate_metric = candidate["metrics"].get(name, candidate["energy_metrics"].get(name, {}))
        deltas.append(float(candidate_metric["nrmse"]) - float(seed_metric["nrmse"]))
    ax.barh(labels, deltas, color=["#16a34a" if value < 0 else "#dc2626" for value in deltas])
    ax.axvline(0.0, color="#111827", linewidth=0.9)
    ax.set_title("Candidate minus seed nRMSE")
    ax.grid(True, axis="x", alpha=0.22)

    handles, legend_labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, legend_labels, loc="upper center", bbox_to_anchor=(0.5, 0.965), ncol=3, frameon=False)
    fig.suptitle("Brodbar narrow FLA: km_NADH_NAD only", fontsize=15, y=0.995)
    fig.subplots_adjust(top=0.89, hspace=0.34, wspace=0.28)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _metric(payload: Mapping[str, Any], name: str) -> Mapping[str, float]:
    return payload["metrics"].get(name, payload["energy_metrics"].get(name, {}))


def _write_report(path: Path, *, summary: Mapping[str, Any], panel_manifest: Mapping[str, Any]) -> None:
    seed = summary["seed"]
    candidate = summary["best_candidate"]
    panel = panel_manifest["decision"]
    lines = [
        "# Narrow `km_NADH_NAD` Flux Learning Analysis",
        "",
        "## Technical summary",
        "",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        "- Dataset: Brodbar control concentrations and derived teacher fluxes.",
        "- Horizon: 46 days.",
        "- Open parameter: `km_NADH_NAD` only.",
        f"- Locked `km_ATP_HK`: `{summary['locked_params'][LOCKED_PARAMETER]:.12g}` (mild-feedback seed).",
        f"- Final promotion decision: **`{summary['accepted']}`**.",
        "",
        "## Key findings",
        "",
        f"- `km_NADH_NAD`: `{seed['params'][PARAMETER]:.8g} -> {candidate['params'][PARAMETER]:.8g}`.",
        f"- Focused guarded loss: `{seed['loss']:.6g} -> {candidate['loss']:.6g}`.",
        f"- VLDH teacher nRMSE: `{seed['teacher_flux_details']['VLDH']['nrmse']:.6g} -> {candidate['teacher_flux_details']['VLDH']['nrmse']:.6g}`.",
        f"- LAC nRMSE: `{_metric(seed, 'LAC')['nrmse']:.6g} -> {_metric(candidate, 'LAC')['nrmse']:.6g}`.",
        f"- GLC nRMSE: `{_metric(seed, 'GLC')['nrmse']:.6g} -> {_metric(candidate, 'GLC')['nrmse']:.6g}`.",
        f"- ATP endpoint: `{seed['sim_final']['ATP']:.6g} -> {candidate['sim_final']['ATP']:.6g}` mM.",
        f"- Focused gate: `{summary['focused_accepted']}` ({'; '.join(summary['focused_reasons'])}).",
        "",
        "## Method and metrics",
        "",
        "The experimental extracellular trajectories were converted to dense teacher fluxes. Each trial reinjected one candidate `km_NADH_NAD` value into the ODE and replayed the complete 46-day trajectory. The objective combined concentration level, endpoint, slope, teacher-flux, energy-state, and log-scale regularization terms.",
        "",
        "Strong guards covered `ATP`, `PEP`, `G6P`, `GLC`, `LAC`, `EGLC`, `ELAC`, `VEGLC`, `VELAC`, and `VLDH`. The focused decision additionally required a lower total loss, at least 2% improvement in VLDH teacher nRMSE or LAC nRMSE, no material GLC regression, and preservation of at least 95% of the seed ATP endpoint.",
        "",
        "## Full-panel validation",
        "",
        f"- Mapped metabolites: `{len(panel_manifest['mapped_metabolites'])}`.",
        f"- Mean nRMSE: `{panel['mean_nrmse']['baseline']:.6g} -> {panel['mean_nrmse']['candidate']:.6g}`.",
        f"- Median nRMSE: `{panel['median_nrmse']['baseline']:.6g} -> {panel['median_nrmse']['candidate']:.6g}`.",
        f"- Counts: `{panel['improved_count']}` improved, `{panel['regressed_count']}` regressed, `{panel['similar_count']}` similar.",
        f"- Full-panel gate: `{summary['full_panel_accepted']}` ({'; '.join(summary['full_panel_reasons'])}).",
        "",
        "## Limitations and decision",
        "",
        "This is a mono-parameter local sensitivity test on one experimental condition. Teacher fluxes are inferred from concentration trajectories and therefore inherit interpolation and derivative uncertainty; the full-panel replay tests non-inferiority but not cross-dataset generalization.",
        "",
        f"The candidate is {'promoted inside this run directory' if summary['accepted'] else 'rejected and the seed is retained'}. No parameter file outside this run directory was overwritten. A later hypothesis should only open an additional parameter after interpreting the direction and residuals of this isolated redox test.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_pass(
    *,
    out_dir: Path,
    seed_params_path: Path,
    n_trials: int,
    local_refinements: int,
    t_max: float,
    teacher_dense_points: int,
    local_bound_scale: float,
    random_seed: int,
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
    if PARAMETER not in seed_params or LOCKED_PARAMETER not in seed_params:
        raise KeyError(f"Seed must contain {PARAMETER} and {LOCKED_PARAMETER}")

    exp_time, base_curves = _extract_brodbar_targets(t_max)
    full_time, full_curves = _full_experimental_curves(t_max)
    if not np.allclose(exp_time, full_time):
        raise RuntimeError("Brodbar target time grids are inconsistent")
    teacher_path = out_dir / "teacher_flux_dataset_km_nadh_nad.json"
    teacher_dataset = _build_lactate_teacher_dataset(
        exp_time=exp_time,
        exp_curves=base_curves,
        dense_points=teacher_dense_points,
        out_path=teacher_path,
    )

    objective = GuardedKmNadhNadObjective(
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
    center, lower, upper = _local_bounds(seed_params, (PARAMETER,), local_bound_scale)[PARAMETER]
    print(f"{PARAMETER} narrow bounds: {lower:.8g} .. {upper:.8g} (center={center:.8g})", flush=True)
    print(f"{LOCKED_PARAMETER} locked at seed: {float(seed_params[LOCKED_PARAMETER]):.17g}", flush=True)

    seed_eval = objective.evaluate({PARAMETER: center}, label="mild_feedback_seed")
    objective.seed_reference = seed_eval
    objective.base.seed_guard_reference = seed_eval
    objective.best_payload = seed_eval

    if HAS_OPTUNA and int(n_trials) > 0:
        sampler = optuna.samplers.TPESampler(
            seed=int(random_seed),
            n_startup_trials=min(6, max(2, int(n_trials) // 3)),
        )
        study = optuna.create_study(direction="minimize", sampler=sampler)
        for multiplier in (1.0, 0.5, 0.75, 1.5, 2.0):
            study.enqueue_trial({PARAMETER: float(np.clip(center * multiplier, lower, upper))})

        def optuna_objective(trial: Any) -> float:
            value = trial.suggest_float(
                PARAMETER,
                float(lower),
                float(upper),
                log=should_use_log_sampling(PARAMETER, float(lower), float(upper)),
            )
            payload = objective.evaluate({PARAMETER: value}, label=f"trial_{trial.number}")
            print(
                f"trial {trial.number:03d}: loss={payload['loss']:.5f}, "
                f"VLDH={payload['teacher_flux_details']['VLDH']['nrmse']:.4f}, "
                f"LAC={payload['metrics']['LAC']['nrmse']:.4f}, "
                f"GLC={payload['metrics']['GLC']['nrmse']:.4f}, "
                f"ATP={payload['sim_final']['ATP']:.6g}, {PARAMETER}={value:.7g}, "
                f"guards={','.join(payload['guard_violations']) or 'none'}",
                flush=True,
            )
            return float(payload["loss"])

        study.optimize(optuna_objective, n_trials=int(n_trials), show_progress_bar=False)
    else:
        multipliers = np.geomspace(1.0 / local_bound_scale, local_bound_scale, max(2, int(n_trials)))
        for index, multiplier in enumerate(multipliers):
            objective.evaluate(
                {PARAMETER: float(np.clip(center * multiplier, lower, upper))},
                label=f"grid_{index}",
            )

    if int(local_refinements) > 0 and objective.best_payload is not None:
        best_value = float(objective.best_payload["params"][PARAMETER])
        for index in range(int(local_refinements)):
            delta = 0.10 * (index + 1)
            for multiplier in (1.0 - delta, 1.0 + delta):
                objective.evaluate(
                    {PARAMETER: float(np.clip(best_value * multiplier, lower, upper))},
                    label=f"local_refine_{index}_{multiplier:.2f}",
                )

    best = objective.best_payload or seed_eval
    best_final = objective.evaluate(best["params"], label="best_final")
    candidate_params = dict(seed_params)
    candidate_params[PARAMETER] = float(best_final["params"][PARAMETER])
    locked_value = _validate_fixed_param_lock(seed_params, candidate_params)
    focused_accepted, focused_reasons = _acceptance(seed_eval, best_final)

    seed_path = out_dir / "seed_params.json"
    candidate_path = out_dir / "candidate_params.json"
    promoted_path = out_dir / "promoted_or_seed_params.json"
    seed_path.write_text(json.dumps(_jsonable(seed_params), indent=2), encoding="utf-8")
    candidate_path.write_text(json.dumps(_jsonable(candidate_params), indent=2), encoding="utf-8")

    panel_manifest = run_full_panel(
        baseline_params_path=seed_path,
        candidate_params_path=candidate_path,
        out_dir=out_dir / "full_panel",
        dense_points=240,
        method=method,
        rtol=rtol,
        atol=atol,
    )
    full_panel_accepted, full_panel_reasons = _panel_acceptance(panel_manifest)
    accepted = bool(focused_accepted and full_panel_accepted)
    promoted_params = candidate_params if accepted else dict(seed_params)
    promoted_path.write_text(json.dumps(_jsonable(promoted_params), indent=2), encoding="utf-8")
    best_params_path = out_dir / "best_params.json"
    if accepted:
        best_params_path.write_text(json.dumps(_jsonable(candidate_params), indent=2), encoding="utf-8")
    else:
        best_params_path.unlink(missing_ok=True)

    trials_csv = out_dir / "optimization_trials.csv"
    pd.DataFrame(_flatten_trial_rows(objective.trials)).to_csv(trials_csv, index=False)
    metrics_csv = out_dir / "km_nadh_nad_metrics.csv"
    metric_rows = []
    for name in (*CORE_TARGETS, *EXTRA_TARGETS):
        seed_metric = _metric(seed_eval, name)
        candidate_metric = _metric(best_final, name)
        metric_rows.append(
            {
                "metabolite": name,
                "seed_nrmse": seed_metric["nrmse"],
                "candidate_nrmse": candidate_metric["nrmse"],
                "delta_nrmse": candidate_metric["nrmse"] - seed_metric["nrmse"],
                "seed_endpoint_error": seed_metric["endpoint_error"],
                "candidate_endpoint_error": candidate_metric["endpoint_error"],
                "delta_endpoint_error": candidate_metric["endpoint_error"] - seed_metric["endpoint_error"],
                "seed_final": _final_value(seed_eval, name),
                "candidate_final": _final_value(best_final, name),
                "experimental_final": full_curves[name][-1],
            }
        )
    pd.DataFrame(metric_rows).to_csv(metrics_csv, index=False)

    flux_metrics_csv = out_dir / "km_nadh_nad_flux_metrics.csv"
    flux_rows = []
    for reaction in GUARD_FLUXES:
        seed_flux = seed_eval["teacher_flux_details"][reaction]
        candidate_flux = best_final["teacher_flux_details"][reaction]
        flux_rows.append(
            {
                "reaction": reaction,
                "seed_nrmse": seed_flux["nrmse"],
                "candidate_nrmse": candidate_flux["nrmse"],
                "delta_nrmse": candidate_flux["nrmse"] - seed_flux["nrmse"],
            }
        )
    pd.DataFrame(flux_rows).to_csv(flux_metrics_csv, index=False)

    trajectory_csv = out_dir / "km_nadh_nad_trajectory.csv"
    trajectory_rows = []
    for t in best_final["sol"].t:
        row: dict[str, float] = {"time_day": float(t)}
        for name in (*CORE_TARGETS, *EXTRA_TARGETS):
            idx = int(EXP_TO_MODEL[name])
            row[f"seed_{name}"] = float(np.interp(t, seed_eval["sol"].t, seed_eval["sol"].y[idx, :]))
            row[f"candidate_{name}"] = float(np.interp(t, best_final["sol"].t, best_final["sol"].y[idx, :]))
            row[f"experimental_{name}"] = float(np.interp(t, exp_time, full_curves[name]))
        trajectory_rows.append(row)
    pd.DataFrame(trajectory_rows).to_csv(trajectory_csv, index=False)

    plot_path = out_dir / "km_nadh_nad_narrow_fla.png"
    _plot_result(seed=seed_eval, candidate=best_final, objective=objective, out_path=plot_path)

    summary = {
        "contract_type": "km_nadh_nad_narrow_fla_result",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed_params_path": str(seed_params_path),
        "optimized_params": [PARAMETER],
        "fixed_params": [name for name in seed_params if name != PARAMETER],
        "locked_params": {LOCKED_PARAMETER: locked_value},
        "bounds": {PARAMETER: [center, lower, upper]},
        "t_max": float(t_max),
        "n_trials": int(n_trials),
        "local_refinements": int(local_refinements),
        "teacher_dense_points": int(teacher_dense_points),
        "solver": {"method": method, "rtol": float(rtol), "atol": float(atol)},
        "guarded_targets": list(GUARD_CONCENTRATIONS),
        "guarded_fluxes": list(GUARD_FLUXES),
        "energy_weights": TARGET_WEIGHTS,
        "seed": {key: value for key, value in seed_eval.items() if key not in {"sol", "sim_exp", "sim_flux"}},
        "best_candidate": {key: value for key, value in best_final.items() if key not in {"sol", "sim_exp", "sim_flux"}},
        "focused_accepted": bool(focused_accepted),
        "focused_reasons": focused_reasons,
        "full_panel_accepted": bool(full_panel_accepted),
        "full_panel_reasons": full_panel_reasons,
        "accepted": accepted,
        "parameters_promoted": accepted,
        "full_panel": {"manifest": panel_manifest["manifest_path"], "decision": panel_manifest["decision"]},
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "decision_report": str(out_dir / "decision_report.md"),
            "seed_params": str(seed_path),
            "candidate_params": str(candidate_path),
            "promoted_or_seed_params": str(promoted_path),
            "best_params": str(best_params_path) if accepted else None,
            "teacher_dataset": str(teacher_path),
            "trials_csv": str(trials_csv),
            "metrics_csv": str(metrics_csv),
            "flux_metrics_csv": str(flux_metrics_csv),
            "trajectory_csv": str(trajectory_csv),
            "plot": str(plot_path),
            "full_panel_manifest": panel_manifest["manifest_path"],
            "full_panel_delta_summary": panel_manifest["delta_summary_png"],
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(_jsonable(summary), indent=2), encoding="utf-8")
    _write_report(out_dir / "decision_report.md", summary=summary, panel_manifest=panel_manifest)
    print(json.dumps(_jsonable(summary), indent=2), flush=True)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a narrow guarded FLA pass for km_NADH_NAD only")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--seed-params", type=Path, default=DEFAULT_SEED_PARAMS)
    parser.add_argument("--n-trials", type=int, default=12)
    parser.add_argument("--local-refinements", type=int, default=1)
    parser.add_argument("--t-max", type=float, default=46.0)
    parser.add_argument("--teacher-dense-points", type=int, default=96)
    parser.add_argument("--local-bound-scale", type=float, default=2.0)
    parser.add_argument("--random-seed", type=int, default=523)
    parser.add_argument("--method", default="LSODA")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    parser.add_argument("--energy-weight", type=float, default=3.0)
    parser.add_argument("--energy-endpoint-weight", type=float, default=4.0)
    parser.add_argument("--guard-weight", type=float, default=20.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_pass(
        out_dir=args.out_dir,
        seed_params_path=args.seed_params,
        n_trials=args.n_trials,
        local_refinements=args.local_refinements,
        t_max=args.t_max,
        teacher_dense_points=args.teacher_dense_points,
        local_bound_scale=args.local_bound_scale,
        random_seed=args.random_seed,
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
