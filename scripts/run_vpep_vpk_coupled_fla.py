"""Constrained two-parameter Brodbar FLA pass on PEP utilization.

This is the follow-up to the rejected decrease-only VPEP_PASE pass. Mild
VEGLC feedback, VHK capacity, and HK ATP affinity stay fixed. Only the
ADP-independent PEP sink decreases and the ATP-producing VPK capacity rises.
The candidate is still diagnostic until it passes the full Brodbar panel.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
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
DEFAULT_SEED_PARAMS = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "vpep_pase_downward_vhk_atp_mild_feedback_46d_n20"
    / "seed_fixed_params.json"
)
DEFAULT_OUT_DIR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "vpep_vpk_coupled_mild_feedback_46d_n20"
)

for path in (str(ROOT), str(SRC_DIR), str(Path(__file__).resolve().parent)):
    if path not in sys.path:
        sys.path.insert(0, path)

from MM_calibration import EXP_TO_MODEL, load_experimental_data, load_initial_conditions, should_use_log_sampling  # noqa: E402
from run_lactate_focused_fla import (  # noqa: E402
    HAS_OPTUNA,
    _build_lactate_teacher_dataset,
    _flatten_trial_rows,
    _jsonable,
    _load_params,
    _nrmse,
    _sim_fluxes,
    _simulate,
    _slope_nrmse,
    _state_at,
    optuna,
)
from run_vpep_pase_downward_fla import (  # noqa: E402
    NATIVE_FLUX_TARGETS,
    TEACHER_FLUX_TARGETS,
    _extract_targets,
    _fixed_mild_feedback,
    _native_fluxes,
    _routing_metrics,
)


PARAM_VPEP = "vmax_VPEP_PASE"
PARAM_VPK = "vmax_VPK"
TARGETS = ("EGLC", "ELAC", "GLC", "G6P", "LAC", "PYR", "ATP", "F6P", "PEP")
SLOPE_TARGETS = ("EGLC", "GLC", "LAC", "ATP")


def _extract_targets_with_g6p(t_max: float) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    time_exp, curves = _extract_targets(t_max)
    raw_time, raw_values, name_to_row = load_experimental_data()
    mask = (raw_time >= 1.0 - 1e-9) & (raw_time <= float(t_max) + 1e-9)
    if "G6P" not in name_to_row:
        raise KeyError("Brodbar experimental target 'G6P' is missing")
    curves["G6P"] = np.asarray(raw_values[name_to_row["G6P"], mask], dtype=float)
    return time_exp, curves


def _directed_bounds(
    seed_params: Mapping[str, Any],
    *,
    vpep_lower: float,
    vpep_upper_ratio: float,
    vpk_upper: float,
) -> dict[str, tuple[float, float, float]]:
    vpep_seed = float(seed_params[PARAM_VPEP])
    vpk_seed = float(seed_params[PARAM_VPK])
    vpep_upper = vpep_seed * float(vpep_upper_ratio)
    vpk_hi = min(float(vpk_upper), vpk_seed * 5.0)
    if not 0.0 < float(vpep_lower) < vpep_upper < vpep_seed:
        raise ValueError("VPEP bounds must define a strictly downward search")
    if not vpk_seed < vpk_hi:
        raise ValueError("VPK upper bound must be above the seed")
    return {
        PARAM_VPEP: (vpep_seed, float(vpep_lower), vpep_upper),
        PARAM_VPK: (vpk_seed, vpk_seed, vpk_hi),
    }


def _time_mean_abs(values: np.ndarray, timepoints: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    timepoints = np.asarray(timepoints, dtype=float)
    return float(np.trapezoid(np.abs(values), timepoints) / (timepoints[-1] - timepoints[0]))


class CoupledObjective:
    def __init__(
        self,
        *,
        seed_params: Mapping[str, Any],
        fixed_feedback: Mapping[str, Any],
        x0: np.ndarray,
        exp_time: np.ndarray,
        exp_curves: Mapping[str, np.ndarray],
        teacher_dataset: Mapping[str, Any],
        method: str,
        rtol: float,
        atol: float,
        guard_weight: float,
    ) -> None:
        self.seed_params = dict(seed_params)
        self.fixed_feedback = dict(fixed_feedback)
        self.x0 = np.asarray(x0, dtype=float)
        self.exp_time = np.asarray(exp_time, dtype=float)
        self.exp_curves = {name: np.asarray(values, dtype=float) for name, values in exp_curves.items()}
        self.teacher_time = np.asarray(teacher_dataset["dense_timepoints"], dtype=float)
        self.teacher_flux = {
            name: np.asarray(teacher_dataset["reaction_flux_curves"][name]["dense_values"], dtype=float)
            for name in TEACHER_FLUX_TARGETS
        }
        self.method = method
        self.rtol = float(rtol)
        self.atol = float(atol)
        self.guard_weight = float(guard_weight)
        self.t_eval = np.unique(np.concatenate([self.exp_time, self.teacher_time]))
        self.neutral: dict[str, Any] | None = None
        self.seed: dict[str, Any] | None = None
        self.best: dict[str, Any] | None = None
        self.trials: list[dict[str, Any]] = []

    def _params(self, overrides: Mapping[str, Any], *, feedback: bool) -> dict[str, Any]:
        params = dict(self.seed_params)
        if feedback:
            params.update(self.fixed_feedback)
        params.update({name: float(value) for name, value in overrides.items()})
        return params

    def evaluate(
        self,
        overrides: Mapping[str, Any],
        *,
        label: str,
        feedback: bool = True,
        record: bool = True,
    ) -> dict[str, Any]:
        start = time.perf_counter()
        params = self._params(overrides, feedback=feedback)
        try:
            sol = _simulate(
                x0=self.x0,
                params=params,
                t_eval=self.t_eval,
                method=self.method,
                rtol=self.rtol,
                atol=self.atol,
            )
        except Exception as exc:
            payload = {"label": label, "loss": float("inf"), "error": str(exc), "elapsed_sec": time.perf_counter() - start}
            if record:
                self.trials.append(payload)
            return payload

        sim_exp = {
            name: np.interp(self.exp_time, sol.t, sol.y[EXP_TO_MODEL[name]])
            for name in TARGETS
        }
        metrics = {name: _nrmse(sim_exp[name], self.exp_curves[name]) for name in TARGETS}
        slopes = {name: _slope_nrmse(sim_exp[name], self.exp_curves[name], self.exp_time) for name in SLOPE_TARGETS}
        level_weights = {"EGLC": 5, "ELAC": 3, "GLC": 16, "G6P": 5, "LAC": 8, "PYR": 2, "ATP": 14, "F6P": 5, "PEP": 5}
        endpoint_weights = {"EGLC": 16, "ELAC": 4, "GLC": 18, "G6P": 5, "LAC": 8, "PYR": 2, "ATP": 18, "F6P": 5, "PEP": 5}
        slope_weights = {"EGLC": 8, "GLC": 6, "LAC": 4, "ATP": 4}
        level_loss = float(sum(level_weights[n] * metrics[n]["nrmse"] for n in TARGETS) / sum(level_weights.values()))
        endpoint_loss = float(sum(endpoint_weights[n] * metrics[n]["endpoint_error"] for n in TARGETS) / sum(endpoint_weights.values()))
        slope_loss = float(sum(slope_weights[n] * slopes[n] for n in SLOPE_TARGETS) / sum(slope_weights.values()))

        sim_flux = _sim_fluxes(sol, params, self.teacher_time)
        native = _native_fluxes(sol, params, self.teacher_time)
        routing = _routing_metrics(native, self.teacher_time)
        flux_weights = {"VEGLC": 8.0, "VELAC": 4.0, "VLDH": 4.0}
        flux_details: dict[str, dict[str, float]] = {}
        flux_loss_terms = []
        for reaction in TEACHER_FLUX_TARGETS:
            target = self.teacher_flux[reaction]
            rmse = float(np.sqrt(np.mean((sim_flux[reaction] - target) ** 2)))
            nrmse = rmse / float(max(np.mean(np.abs(target)), 1e-4))
            flux_details[reaction] = {"rmse": rmse, "nrmse": nrmse}
            flux_loss_terms.append(flux_weights[reaction] * nrmse)
        flux_loss = float(sum(flux_loss_terms) / sum(flux_weights.values()))
        routing_loss = float(routing["PEP_to_VPEP_PASE_share"])
        regularization = float(
            math.log(max(float(params[PARAM_VPEP]), 1e-12) / float(self.seed_params[PARAM_VPEP])) ** 2
            + math.log(max(float(params[PARAM_VPK]), 1e-12) / float(self.seed_params[PARAM_VPK])) ** 2
        )

        guard_loss = 0.0
        if self.neutral is not None and self.seed is not None:
            neutral = self.neutral
            seed = self.seed
            guard_loss += 70.0 * max(0.0, metrics["EGLC"]["endpoint_error"] - max(0.08, neutral["metrics"]["EGLC"]["endpoint_error"] + 0.03)) ** 2
            guard_loss += 14.0 * max(0.0, slopes["EGLC"] - neutral["slopes"]["EGLC"] * 1.20) ** 2
            guard_loss += 14.0 * max(0.0, metrics["PEP"]["nrmse"] - max(1.0, seed["metrics"]["PEP"]["nrmse"] * 2.0)) ** 2
            guard_loss += 14.0 * max(0.0, metrics["G6P"]["nrmse"] - seed["metrics"]["G6P"]["nrmse"] * 1.10) ** 2
            guard_loss += 14.0 * max(0.0, metrics["LAC"]["nrmse"] - seed["metrics"]["LAC"]["nrmse"] * 1.05) ** 2
            guard_loss += 14.0 * max(0.0, metrics["ELAC"]["nrmse"] - neutral["metrics"]["ELAC"]["nrmse"] * 1.08) ** 2
            for reaction, factor in {"VEGLC": 1.20, "VELAC": 1.10, "VLDH": 1.10}.items():
                guard_loss += 10.0 * max(0.0, flux_details[reaction]["nrmse"] - neutral["teacher_flux_details"][reaction]["nrmse"] * factor) ** 2

        loss = (
            1.4 * level_loss
            + 3.5 * endpoint_loss
            + 2.0 * slope_loss
            + 3.0 * flux_loss
            + 2.0 * routing_loss
            + self.guard_weight * guard_loss
            + 0.025 * regularization
        )
        payload = {
            "label": label,
            "params": {PARAM_VPEP: params[PARAM_VPEP], PARAM_VPK: params[PARAM_VPK]},
            "loss": float(loss),
            "level_loss": level_loss,
            "endpoint_loss": endpoint_loss,
            "slope_loss": slope_loss,
            "teacher_flux_loss": flux_loss,
            "routing_loss": routing_loss,
            "guard_loss": float(guard_loss),
            "regularization_loss": regularization,
            "metrics": metrics,
            "slopes": slopes,
            "teacher_flux_details": flux_details,
            "routing_metrics": routing,
            "sim_final": {name: float(sim_exp[name][-1]) for name in TARGETS},
            "exp_final": {name: float(self.exp_curves[name][-1]) for name in TARGETS},
            "elapsed_sec": float(time.perf_counter() - start),
            "sol": sol,
            "sim_exp": sim_exp,
            "sim_flux": sim_flux,
            "native_flux": native,
        }
        if record:
            self.trials.append({k: v for k, v in payload.items() if k not in {"sol", "sim_exp", "sim_flux", "native_flux"}})
        if feedback and (self.best is None or payload["loss"] < self.best["loss"]):
            self.best = payload
        return payload

    def __call__(self, overrides: Mapping[str, Any], *, label: str) -> float:
        return float(self.evaluate(overrides, label=label)["loss"])


def _acceptance(neutral: Mapping[str, Any], seed: Mapping[str, Any], candidate: Mapping[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    checks = [
        (candidate["loss"] < seed["loss"], "coupled loss did not improve"),
        (candidate["metrics"]["GLC"]["nrmse"] <= seed["metrics"]["GLC"]["nrmse"] * 0.95, "GLC nRMSE did not improve by 5%"),
        (candidate["sim_final"]["ATP"] >= seed["sim_final"]["ATP"] * 1.25, "ATP endpoint did not improve by 25%"),
        (candidate["routing_metrics"]["PEP_to_VPK_share"] >= seed["routing_metrics"]["PEP_to_VPK_share"] + 0.05, "PEP-to-VPK share did not improve by 5 points"),
        (candidate["metrics"]["PEP"]["nrmse"] <= max(1.0, seed["metrics"]["PEP"]["nrmse"] * 2.0), "PEP trajectory guard failed"),
        (candidate["metrics"]["G6P"]["nrmse"] <= seed["metrics"]["G6P"]["nrmse"] * 1.10, "G6P guard failed"),
        (candidate["metrics"]["EGLC"]["endpoint_error"] <= max(0.08, neutral["metrics"]["EGLC"]["endpoint_error"] + 0.03), "EGLC endpoint guard failed"),
        (candidate["slopes"]["EGLC"] <= neutral["slopes"]["EGLC"] * 1.20, "EGLC slope guard failed"),
        (candidate["metrics"]["ELAC"]["nrmse"] <= neutral["metrics"]["ELAC"]["nrmse"] * 1.08, "ELAC guard failed"),
        (candidate["metrics"]["LAC"]["nrmse"] <= seed["metrics"]["LAC"]["nrmse"] * 1.05, "LAC guard failed"),
    ]
    for passed, reason in checks:
        if not passed:
            reasons.append(reason)
    for reaction, factor in {"VEGLC": 1.20, "VELAC": 1.10, "VLDH": 1.10}.items():
        if candidate["teacher_flux_details"][reaction]["nrmse"] > neutral["teacher_flux_details"][reaction]["nrmse"] * factor:
            reasons.append(f"{reaction} teacher-flux guard failed")
    accepted = not reasons
    if accepted:
        reasons.append("candidate passed coupled routing, trajectory, concentration, and teacher-flux guards")
    return accepted, reasons


def _clean(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k not in {"sol", "sim_exp", "sim_flux", "native_flux"}}


def _write_trajectory(objective: CoupledObjective, seed: Mapping[str, Any], candidate: Mapping[str, Any], path: Path) -> None:
    rows = []
    for t in objective.t_eval:
        row = {"time_day": float(t)}
        for name in TARGETS:
            idx = EXP_TO_MODEL[name]
            row[f"seed_{name}"] = float(np.interp(t, seed["sol"].t, seed["sol"].y[idx]))
            row[f"candidate_{name}"] = float(np.interp(t, candidate["sol"].t, candidate["sol"].y[idx]))
            row[f"experimental_{name}"] = float(np.interp(t, objective.exp_time, objective.exp_curves[name]))
        rows.append(row)
    pd.DataFrame(rows).to_csv(path, index=False)


def _plot(objective: CoupledObjective, seed: Mapping[str, Any], candidate: Mapping[str, Any], path: Path) -> None:
    fig, axes = plt.subplots(3, 4, figsize=(17, 11), constrained_layout=False)
    flat = axes.flatten()
    for ax, name in zip(flat[:9], TARGETS):
        idx = EXP_TO_MODEL[name]
        ax.plot(seed["sol"].t, seed["sol"].y[idx], color="#64748b", linewidth=1.8, label="fixed seed")
        ax.plot(candidate["sol"].t, candidate["sol"].y[idx], color="#2563eb", linewidth=2.2, label="coupled candidate")
        ax.scatter(objective.exp_time, objective.exp_curves[name], color="#111827", s=18, label="Brodbar")
        ax.set_title(f"{name}  {seed['metrics'][name]['nrmse']:.2f}->{candidate['metrics'][name]['nrmse']:.2f}", fontsize=10)
        ax.set_xlabel("Time (days)")
        ax.set_ylabel("mM")
        ax.grid(True, alpha=0.25)
    for ax, reaction in zip(flat[9:12], TEACHER_FLUX_TARGETS):
        ax.plot(objective.teacher_time, objective.teacher_flux[reaction], color="#111827", linewidth=2.0, label="teacher")
        ax.plot(objective.teacher_time, seed["sim_flux"][reaction], color="#64748b", linewidth=1.8, label="seed")
        ax.plot(objective.teacher_time, candidate["sim_flux"][reaction], color="#2563eb", linewidth=2.2, label="candidate")
        ax.set_title(f"{reaction} teacher flux")
        ax.set_xlabel("Time (days)")
        ax.set_ylabel("mM/day")
        ax.grid(True, alpha=0.25)
    handles, labels = flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.955), ncol=3, frameon=False)
    fig.suptitle("Brodbar coupled FLA: VPEP_PASE decrease plus VPK increase", y=0.995)
    fig.subplots_adjust(top=0.86, hspace=0.42, wspace=0.22)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run(
    *,
    out_dir: Path,
    seed_params_path: Path,
    n_trials: int,
    t_max: float,
    teacher_dense_points: int,
    random_seed: int,
    rtol: float,
    atol: float,
    vpep_lower: float,
    vpep_upper_ratio: float,
    vpk_upper: float,
    feedback_strength: float,
    feedback_km: float,
    feedback_hill: float,
    feedback_cap: float,
    guard_weight: float,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    seed_params = _load_params(Path(seed_params_path))
    bounds = _directed_bounds(seed_params, vpep_lower=vpep_lower, vpep_upper_ratio=vpep_upper_ratio, vpk_upper=vpk_upper)
    feedback = _fixed_mild_feedback(strength=feedback_strength, km_glc=feedback_km, hill=feedback_hill, import_cap=feedback_cap)
    exp_time, exp_curves = _extract_targets_with_g6p(t_max)
    teacher_path = out_dir / "teacher_flux_dataset_vpep_vpk.json"
    teacher = _build_lactate_teacher_dataset(exp_time=exp_time, exp_curves=exp_curves, dense_points=teacher_dense_points, out_path=teacher_path)
    objective = CoupledObjective(
        seed_params=seed_params,
        fixed_feedback=feedback,
        x0=np.asarray(load_initial_conditions(), dtype=float),
        exp_time=exp_time,
        exp_curves=exp_curves,
        teacher_dataset=teacher,
        method="LSODA",
        rtol=rtol,
        atol=atol,
        guard_weight=guard_weight,
    )
    center = {name: bounds[name][0] for name in bounds}
    neutral = objective.evaluate(center, label="neutral_seed", feedback=False)
    seed = objective.evaluate(center, label="fixed_mild_feedback_seed", feedback=True)
    objective.neutral = neutral
    objective.seed = seed
    objective.best = seed
    print(f"Bounds: {PARAM_VPEP} {bounds[PARAM_VPEP][1]:.6g}..{bounds[PARAM_VPEP][2]:.6g}; {PARAM_VPK} {bounds[PARAM_VPK][1]:.6g}..{bounds[PARAM_VPK][2]:.6g}", flush=True)
    print(f"Seed: loss={seed['loss']:.4f}, GLC={seed['metrics']['GLC']['nrmse']:.4f}, ATP={seed['sim_final']['ATP']:.6g}, PEP={seed['metrics']['PEP']['nrmse']:.3f}", flush=True)

    if HAS_OPTUNA and int(n_trials) > 0:
        sampler = optuna.samplers.TPESampler(seed=int(random_seed), n_startup_trials=min(8, max(4, int(n_trials) // 3)), multivariate=True)
        study = optuna.create_study(direction="minimize", sampler=sampler)
        anchors = (
            (bounds[PARAM_VPEP][2], bounds[PARAM_VPK][0]),
            (2.25, 1.43),
            (1.50, 2.14),
            (0.90, 2.85),
            (bounds[PARAM_VPEP][1], bounds[PARAM_VPK][2]),
        )
        for vpep, vpk in anchors:
            study.enqueue_trial({PARAM_VPEP: float(np.clip(vpep, bounds[PARAM_VPEP][1], bounds[PARAM_VPEP][2])), PARAM_VPK: float(np.clip(vpk, bounds[PARAM_VPK][1], bounds[PARAM_VPK][2]))})

        def objective_fn(trial: Any) -> float:
            values = {
                PARAM_VPEP: trial.suggest_float(PARAM_VPEP, bounds[PARAM_VPEP][1], bounds[PARAM_VPEP][2], log=should_use_log_sampling(PARAM_VPEP, bounds[PARAM_VPEP][1], bounds[PARAM_VPEP][2])),
                PARAM_VPK: trial.suggest_float(PARAM_VPK, bounds[PARAM_VPK][1], bounds[PARAM_VPK][2], log=should_use_log_sampling(PARAM_VPK, bounds[PARAM_VPK][1], bounds[PARAM_VPK][2])),
            }
            loss = objective(values, label=f"trial_{trial.number}")
            latest = objective.trials[-1]
            print(f"trial {trial.number:03d}: loss={loss:.4f}, VPEP={values[PARAM_VPEP]:.5g}, VPK={values[PARAM_VPK]:.5g}, GLC={latest['metrics']['GLC']['nrmse']:.3f}, ATP={latest['sim_final']['ATP']:.4g}, PEP={latest['metrics']['PEP']['nrmse']:.3f}, VPK_share={latest['routing_metrics']['PEP_to_VPK_share']:.3f}", flush=True)
            return float(loss)

        study.optimize(objective_fn, n_trials=int(n_trials), show_progress_bar=False)
    else:
        for i, ratio in enumerate(np.geomspace(0.1, 0.5, max(2, int(abs(n_trials))))):
            values = {PARAM_VPEP: max(bounds[PARAM_VPEP][1], bounds[PARAM_VPEP][0] * ratio), PARAM_VPK: min(bounds[PARAM_VPK][2], bounds[PARAM_VPK][0] / ratio)}
            objective(values, label=f"grid_{i}")

    best = objective.best or seed
    candidate = objective.evaluate(best["params"], label="best_final")
    accepted, reasons = _acceptance(neutral, seed, candidate)
    candidate_params = dict(seed_params)
    candidate_params.update(feedback)
    candidate_params.update(candidate["params"])
    (out_dir / "seed_fixed_params.json").write_text(json.dumps(_jsonable(objective._params(center, feedback=True)), indent=2), encoding="utf-8")
    (out_dir / "candidate_params.json").write_text(json.dumps(_jsonable(candidate_params), indent=2), encoding="utf-8")
    trials_path = out_dir / "optimization_trials.csv"
    pd.DataFrame(_flatten_trial_rows(objective.trials)).to_csv(trials_path, index=False)
    trajectory_path = out_dir / "vpep_vpk_trajectory.csv"
    _write_trajectory(objective, seed, candidate, trajectory_path)
    plot_path = out_dir / "vpep_vpk_coupled_fla.png"
    _plot(objective, seed, candidate, plot_path)
    summary = {
        "contract_type": "vpep_vpk_coupled_fla_result",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "out_dir": str(out_dir),
        "seed_params_path": str(seed_params_path),
        "fixed_feedback_params": feedback,
        "optimized_params": [PARAM_VPEP, PARAM_VPK],
        "search_directions": {PARAM_VPEP: "decrease_only", PARAM_VPK: "increase_only"},
        "bounds": bounds,
        "t_max": float(t_max),
        "n_trials": int(n_trials),
        "teacher_dense_points": int(teacher_dense_points),
        "solver": {"method": "LSODA", "rtol": float(rtol), "atol": float(atol)},
        "neutral_seed": _clean(neutral),
        "fixed_mild_feedback_seed": _clean(seed),
        "best_candidate": _clean(candidate),
        "focused_accepted": bool(accepted),
        "acceptance_reasons": reasons,
        "parameters_promoted": False,
        "global_best_overwritten": False,
        "requires_full_panel_replay": True,
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "teacher_dataset": str(teacher_path),
            "seed_fixed_params": str(out_dir / "seed_fixed_params.json"),
            "candidate_params": str(out_dir / "candidate_params.json"),
            "trials_csv": str(trials_path),
            "trajectory_csv": str(trajectory_path),
            "plot": str(plot_path),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(_jsonable(summary), indent=2), encoding="utf-8")
    print(json.dumps(_jsonable(summary), indent=2), flush=True)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run coupled VPEP_PASE-down/VPK-up Brodbar FLA")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--seed-params", type=Path, default=DEFAULT_SEED_PARAMS)
    parser.add_argument("--n-trials", type=int, default=20)
    parser.add_argument("--t-max", type=float, default=46.0)
    parser.add_argument("--teacher-dense-points", type=int, default=96)
    parser.add_argument("--random-seed", type=int, default=805)
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    parser.add_argument("--vpep-lower", type=float, default=0.5)
    parser.add_argument("--vpep-upper-ratio", type=float, default=0.5)
    parser.add_argument("--vpk-upper", type=float, default=5.0)
    parser.add_argument("--feedback-strength", type=float, default=0.10)
    parser.add_argument("--feedback-km", type=float, default=8.54922196746391)
    parser.add_argument("--feedback-hill", type=float, default=0.6928279794535482)
    parser.add_argument("--feedback-cap", type=float, default=5.0)
    parser.add_argument("--guard-weight", type=float, default=14.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run(
        out_dir=args.out_dir,
        seed_params_path=args.seed_params,
        n_trials=args.n_trials,
        t_max=args.t_max,
        teacher_dense_points=args.teacher_dense_points,
        random_seed=args.random_seed,
        rtol=args.rtol,
        atol=args.atol,
        vpep_lower=args.vpep_lower,
        vpep_upper_ratio=args.vpep_upper_ratio,
        vpk_upper=args.vpk_upper,
        feedback_strength=args.feedback_strength,
        feedback_km=args.feedback_km,
        feedback_hill=args.feedback_hill,
        feedback_cap=args.feedback_cap,
        guard_weight=args.guard_weight,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
