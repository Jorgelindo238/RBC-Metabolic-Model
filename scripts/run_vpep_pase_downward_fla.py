"""Narrow Brodbar FLA pass on the ADP-independent PEP phosphatase sink.

The current VEGLC transport hypothesis, VHK capacity, and ATP affinity are
fixed. A mild, reversible intracellular-glucose feedback is applied to VEGLC,
and only ``vmax_VPEP_PASE`` is allowed to move, strictly downward from its
current seed value. The run never overwrites the global calibration.
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
    / "glucose_utilization_vhk_atp_46d_n16_upper5"
    / "candidate_params.json"
)
DEFAULT_OUT_DIR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "vpep_pase_downward_vhk_atp_mild_feedback_46d_n20"
)

for path in (str(ROOT), str(SRC_DIR), str(Path(__file__).resolve().parent)):
    if path not in sys.path:
        sys.path.insert(0, path)

from MM_calibration import (  # noqa: E402
    EXP_TO_MODEL,
    load_experimental_data,
    load_initial_conditions,
    should_use_log_sampling,
)
from equadiff_brodbar import equadiff_brodbar  # noqa: E402
from flux_visualization import FluxTracker  # noqa: E402
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


OPTIMIZED_PARAM = "vmax_VPEP_PASE"
CONCENTRATION_TARGETS = ("EGLC", "ELAC", "GLC", "LAC", "PYR", "ATP", "F6P", "PEP")
SLOPE_TARGETS = ("EGLC", "GLC", "LAC", "ATP")
TEACHER_FLUX_TARGETS = ("VEGLC", "VELAC", "VLDH")
NATIVE_FLUX_TARGETS = ("VHK", "VPFK", "VPK", "VPEP_PASE", "VLDH", "VEGLC", "VELAC")


def _fixed_mild_feedback(
    *,
    strength: float,
    km_glc: float,
    hill: float,
    import_cap: float,
) -> dict[str, Any]:
    if strength < 0.0:
        raise ValueError("VEGLC feedback strength must be non-negative")
    if km_glc <= 0.0 or hill <= 0.0 or import_cap <= 0.0:
        raise ValueError("VEGLC feedback km, hill, and import cap must be positive")
    return {
        "kinetic_family_VEGLC": "transport_depletion_gate_import_feedback",
        "hybrid_blend_VEGLC": 1.0,
        "transport_gate_feedback_strength_VEGLC": float(strength),
        "transport_gate_feedback_km_GLC_VEGLC": float(km_glc),
        "transport_gate_feedback_hill_VEGLC": float(hill),
        "transport_gate_import_cap_VEGLC": float(import_cap),
    }


def _downward_bounds(
    seed_value: float,
    *,
    lower: float,
    upper_ratio: float,
) -> tuple[float, float, float]:
    center = float(seed_value)
    lo = float(lower)
    ratio = float(upper_ratio)
    if not center > 0.0:
        raise ValueError("The VPEP_PASE seed value must be positive")
    if not 0.0 < lo < center:
        raise ValueError("The VPEP_PASE lower bound must be positive and below the seed")
    if not 0.0 < ratio < 1.0:
        raise ValueError("The VPEP_PASE upper ratio must be strictly between zero and one")
    hi = center * ratio
    if not lo < hi < center:
        raise ValueError("The requested bounds do not define a strictly downward search")
    return center, lo, hi


def _extract_targets(t_max: float) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    time_exp, exp_values, name_to_row = load_experimental_data()
    mask = (time_exp >= 1.0 - 1e-9) & (time_exp <= float(t_max) + 1e-9)
    active_time = np.asarray(time_exp[mask], dtype=float)
    curves: dict[str, np.ndarray] = {}
    for name in CONCENTRATION_TARGETS:
        if name not in name_to_row:
            raise KeyError(f"Brodbar experimental target {name!r} is missing")
        curves[name] = np.asarray(exp_values[name_to_row[name], mask], dtype=float)
    return active_time, curves


def _time_mean_abs(values: np.ndarray, timepoints: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    timepoints = np.asarray(timepoints, dtype=float)
    if values.size == 1:
        return float(abs(values[0]))
    return float(np.trapezoid(np.abs(values), timepoints) / (timepoints[-1] - timepoints[0]))


def _native_fluxes(sol: Any, params: Mapping[str, Any], timepoints: np.ndarray) -> dict[str, np.ndarray]:
    tracker = FluxTracker()
    params_dict = dict(params)
    for t in np.asarray(timepoints, dtype=float):
        equadiff_brodbar(
            float(t),
            _state_at(sol, float(t)),
            custom_params=params_dict,
            curve_fit_strength=0.0,
            flux_tracker=tracker,
        )
    return {
        reaction: np.asarray(tracker.fluxes.get(reaction, np.zeros(len(timepoints))), dtype=float)
        for reaction in NATIVE_FLUX_TARGETS
    }


def _routing_metrics(native_flux: Mapping[str, np.ndarray], timepoints: np.ndarray) -> dict[str, float]:
    vpk = _time_mean_abs(native_flux["VPK"], timepoints)
    vpep = _time_mean_abs(native_flux["VPEP_PASE"], timepoints)
    drain = max(vpk + vpep, 1e-12)
    return {
        "VPK_mean_abs_flux": vpk,
        "VPEP_PASE_mean_abs_flux": vpep,
        "PEP_to_VPK_share": vpk / drain,
        "PEP_to_VPEP_PASE_share": vpep / drain,
        "VHK_mean_abs_flux": _time_mean_abs(native_flux["VHK"], timepoints),
        "VPFK_mean_abs_flux": _time_mean_abs(native_flux["VPFK"], timepoints),
    }


class VpepPaseObjective:
    def __init__(
        self,
        *,
        x0: np.ndarray,
        base_seed_params: Mapping[str, Any],
        fixed_feedback_params: Mapping[str, Any],
        exp_time: np.ndarray,
        exp_curves: Mapping[str, np.ndarray],
        teacher_dataset: Mapping[str, Any],
        method: str,
        rtol: float,
        atol: float,
        level_weight: float,
        endpoint_weight: float,
        slope_weight: float,
        flux_weight: float,
        routing_weight: float,
        guard_weight: float,
        regularization_weight: float,
        tracked_param_names: Sequence[str] = (OPTIMIZED_PARAM,),
    ) -> None:
        self.x0 = np.asarray(x0, dtype=float)
        self.base_seed_params = dict(base_seed_params)
        self.fixed_feedback_params = dict(fixed_feedback_params)
        self.tracked_param_names = tuple(tracked_param_names)
        self.exp_time = np.asarray(exp_time, dtype=float)
        self.exp_curves = {name: np.asarray(values, dtype=float) for name, values in exp_curves.items()}
        self.teacher_time = np.asarray(teacher_dataset["dense_timepoints"], dtype=float)
        self.teacher_flux = {
            reaction: np.asarray(teacher_dataset["reaction_flux_curves"][reaction]["dense_values"], dtype=float)
            for reaction in TEACHER_FLUX_TARGETS
        }
        self.method = str(method)
        self.rtol = float(rtol)
        self.atol = float(atol)
        self.level_weight = float(level_weight)
        self.endpoint_weight = float(endpoint_weight)
        self.slope_weight = float(slope_weight)
        self.flux_weight = float(flux_weight)
        self.routing_weight = float(routing_weight)
        self.guard_weight = float(guard_weight)
        self.regularization_weight = float(regularization_weight)
        self.t_eval = np.unique(np.concatenate([self.exp_time, self.teacher_time]))
        self.trials: list[dict[str, Any]] = []
        self.best_payload: dict[str, Any] | None = None
        self.neutral_reference: dict[str, Any] | None = None
        self.mild_reference: dict[str, Any] | None = None

    def build_params(
        self,
        overrides: float | Mapping[str, Any] | None,
        *,
        apply_feedback: bool,
    ) -> dict[str, Any]:
        params = dict(self.base_seed_params)
        if apply_feedback:
            params.update(self.fixed_feedback_params)
        if isinstance(overrides, Mapping):
            for name, value in overrides.items():
                if name not in self.tracked_param_names:
                    raise KeyError(f"Untracked optimization parameter: {name}")
                params[name] = float(value)
        elif overrides is not None:
            if self.tracked_param_names != (OPTIMIZED_PARAM,):
                raise TypeError("Multi-parameter objectives require an override mapping")
            params[OPTIMIZED_PARAM] = float(overrides)
        return params

    def evaluate(
        self,
        overrides: float | Mapping[str, Any] | None,
        *,
        label: str,
        apply_feedback: bool = True,
        record: bool = True,
    ) -> dict[str, Any]:
        start = time.perf_counter()
        params = self.build_params(overrides, apply_feedback=apply_feedback)
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
            payload = {
                "label": label,
                "params": {name: params.get(name) for name in self.tracked_param_names},
                "loss": float("inf"),
                "error": str(exc),
                "elapsed_sec": time.perf_counter() - start,
            }
            for name in self.tracked_param_names:
                payload[name] = params.get(name)
            if record:
                self.trials.append(payload)
            return payload

        sim_exp = {
            name: np.interp(self.exp_time, sol.t, sol.y[EXP_TO_MODEL[name], :])
            for name in CONCENTRATION_TARGETS
        }
        metrics = {name: _nrmse(sim_exp[name], self.exp_curves[name]) for name in CONCENTRATION_TARGETS}
        slope_metrics = {
            name: _slope_nrmse(sim_exp[name], self.exp_curves[name], self.exp_time)
            for name in SLOPE_TARGETS
        }

        level_weights = {
            "EGLC": 5.0,
            "ELAC": 3.0,
            "GLC": 16.0,
            "LAC": 8.0,
            "PYR": 2.0,
            "ATP": 12.0,
            "F6P": 3.0,
            "PEP": 2.0,
        }
        endpoint_weights = {
            "EGLC": 16.0,
            "ELAC": 4.0,
            "GLC": 18.0,
            "LAC": 8.0,
            "PYR": 2.0,
            "ATP": 16.0,
            "F6P": 4.0,
            "PEP": 2.0,
        }
        slope_weights = {"EGLC": 8.0, "GLC": 6.0, "LAC": 4.0, "ATP": 4.0}
        level_loss = float(
            sum(level_weights[name] * metrics[name]["nrmse"] for name in CONCENTRATION_TARGETS)
            / sum(level_weights.values())
        )
        endpoint_loss = float(
            sum(endpoint_weights[name] * metrics[name]["endpoint_error"] for name in CONCENTRATION_TARGETS)
            / sum(endpoint_weights.values())
        )
        slope_loss = float(
            sum(slope_weights[name] * slope_metrics[name] for name in SLOPE_TARGETS)
            / sum(slope_weights.values())
        )

        sim_flux = _sim_fluxes(sol, params, self.teacher_time)
        native_flux = _native_fluxes(sol, params, self.teacher_time)
        routing = _routing_metrics(native_flux, self.teacher_time)
        flux_weights = {"VEGLC": 8.0, "VELAC": 4.0, "VLDH": 4.0}
        flux_details: dict[str, dict[str, float]] = {}
        flux_terms = []
        for reaction in TEACHER_FLUX_TARGETS:
            target = self.teacher_flux[reaction]
            simulated = sim_flux[reaction]
            rmse = float(np.sqrt(np.mean((simulated - target) ** 2)))
            nrmse = rmse / float(max(np.mean(np.abs(target)), 1e-4))
            flux_details[reaction] = {"rmse": rmse, "nrmse": nrmse, "weight": flux_weights[reaction]}
            flux_terms.append(flux_weights[reaction] * nrmse)
        flux_loss = float(sum(flux_terms) / sum(flux_weights.values()))
        routing_loss = float(routing["PEP_to_VPEP_PASE_share"])

        regularization_terms = []
        for name in self.tracked_param_names:
            seed_value = max(float(self.base_seed_params[name]), 1e-12)
            parameter_value = max(float(params[name]), 1e-12)
            regularization_terms.append(math.log(parameter_value / seed_value) ** 2)
        regularization_loss = float(np.mean(regularization_terms)) if regularization_terms else 0.0

        guard_loss = 0.0
        if self.neutral_reference is not None and self.mild_reference is not None:
            neutral = self.neutral_reference
            mild = self.mild_reference
            guard_loss += 60.0 * max(
                0.0,
                metrics["EGLC"]["endpoint_error"]
                - max(0.08, neutral["metrics"]["EGLC"]["endpoint_error"] + 0.03),
            ) ** 2
            guard_loss += 12.0 * max(
                0.0,
                slope_metrics["EGLC"] - neutral["slope_metrics"]["EGLC"] * 1.20,
            ) ** 2
            guard_loss += 12.0 * max(
                0.0,
                metrics["ELAC"]["nrmse"] - neutral["metrics"]["ELAC"]["nrmse"] * 1.08,
            ) ** 2
            guard_loss += 16.0 * max(
                0.0,
                metrics["LAC"]["nrmse"] - mild["metrics"]["LAC"]["nrmse"] * 1.02,
            ) ** 2
            guard_loss += 16.0 * max(
                0.0,
                metrics["ATP"]["nrmse"] - mild["metrics"]["ATP"]["nrmse"],
            ) ** 2
            guard_loss += 20.0 * max(
                0.0,
                metrics["PEP"]["nrmse"] - max(1.0, mild["metrics"]["PEP"]["nrmse"] * 2.0),
            ) ** 2
            for reaction, factor in {"VEGLC": 1.20, "VELAC": 1.10, "VLDH": 1.10}.items():
                guard_loss += 10.0 * max(
                    0.0,
                    flux_details[reaction]["nrmse"]
                    - neutral["teacher_flux_details"][reaction]["nrmse"] * factor,
                ) ** 2

        loss = (
            self.level_weight * level_loss
            + self.endpoint_weight * endpoint_loss
            + self.slope_weight * slope_loss
            + self.flux_weight * flux_loss
            + self.routing_weight * routing_loss
            + self.guard_weight * guard_loss
            + self.regularization_weight * regularization_loss
        )

        payload = {
            "label": label,
            "params": {name: float(params[name]) for name in self.tracked_param_names},
            "loss": float(loss),
            "level_loss": level_loss,
            "endpoint_loss": endpoint_loss,
            "slope_loss": slope_loss,
            "teacher_flux_loss": flux_loss,
            "routing_loss": routing_loss,
            "guard_loss": float(guard_loss),
            "regularization_loss": regularization_loss,
            "metrics": metrics,
            "slope_metrics": slope_metrics,
            "teacher_flux_details": flux_details,
            "routing_metrics": routing,
            "sim_final": {name: float(sim_exp[name][-1]) for name in CONCENTRATION_TARGETS},
            "exp_final": {name: float(self.exp_curves[name][-1]) for name in CONCENTRATION_TARGETS},
            "elapsed_sec": float(time.perf_counter() - start),
            "sol": sol,
            "sim_exp": sim_exp,
            "sim_flux": sim_flux,
            "native_flux": native_flux,
        }
        for name in self.tracked_param_names:
            payload[name] = float(params[name])
        if record:
            self.trials.append(
                {k: v for k, v in payload.items() if k not in {"sol", "sim_exp", "sim_flux", "native_flux"}}
            )
        if apply_feedback and (self.best_payload is None or payload["loss"] < self.best_payload["loss"]):
            self.best_payload = payload
        return payload

    def __call__(self, overrides: float | Mapping[str, Any], *, label: str) -> float:
        return float(self.evaluate(overrides, label=label)["loss"])


def _focused_acceptance(
    neutral: Mapping[str, Any],
    mild: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> tuple[bool, list[str]]:
    accepted = True
    reasons: list[str] = []

    def reject(condition: bool, reason: str) -> None:
        nonlocal accepted
        if condition:
            accepted = False
            reasons.append(reason)

    reject(candidate["loss"] >= mild["loss"], "focused loss did not improve")
    reject(
        candidate["metrics"]["GLC"]["nrmse"] > mild["metrics"]["GLC"]["nrmse"] * 0.95,
        "GLC nRMSE did not improve by at least 5%",
    )
    reject(
        candidate["sim_final"]["ATP"] < mild["sim_final"]["ATP"] * 1.25,
        "ATP endpoint did not increase by at least 25%",
    )
    reject(
        candidate["routing_metrics"]["PEP_to_VPK_share"]
        < mild["routing_metrics"]["PEP_to_VPK_share"] + 0.05,
        "PEP-to-VPK route share did not increase by at least 5 percentage points",
    )
    reject(
        candidate["metrics"]["EGLC"]["endpoint_error"]
        > max(0.08, neutral["metrics"]["EGLC"]["endpoint_error"] + 0.03),
        "EGLC endpoint guard failed",
    )
    reject(
        candidate["slope_metrics"]["EGLC"] > neutral["slope_metrics"]["EGLC"] * 1.20,
        "EGLC slope guard failed",
    )
    reject(
        candidate["metrics"]["ELAC"]["nrmse"] > neutral["metrics"]["ELAC"]["nrmse"] * 1.08,
        "ELAC guard failed",
    )
    reject(
        candidate["metrics"]["LAC"]["nrmse"] > mild["metrics"]["LAC"]["nrmse"] * 1.02,
        "LAC guard failed",
    )
    reject(
        candidate["metrics"]["ATP"]["nrmse"] > mild["metrics"]["ATP"]["nrmse"],
        "ATP nRMSE regressed",
    )
    reject(
        candidate["metrics"]["PEP"]["nrmse"]
        > max(1.0, mild["metrics"]["PEP"]["nrmse"] * 2.0),
        "PEP trajectory guard failed",
    )
    for reaction, factor in {"VEGLC": 1.20, "VELAC": 1.10, "VLDH": 1.10}.items():
        reject(
            candidate["teacher_flux_details"][reaction]["nrmse"]
            > neutral["teacher_flux_details"][reaction]["nrmse"] * factor,
            f"{reaction} teacher-flux guard failed",
        )
    if accepted:
        reasons.append("focused candidate passed concentration, energy-routing, and teacher-flux guards")
    return accepted, reasons


def _clean_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        k: v
        for k, v in payload.items()
        if k not in {"sol", "sim_exp", "sim_flux", "native_flux"}
    }


def _write_metrics(
    neutral: Mapping[str, Any],
    mild: Mapping[str, Any],
    candidate: Mapping[str, Any],
    out_path: Path,
) -> list[dict[str, Any]]:
    rows = []
    for name in CONCENTRATION_TARGETS:
        rows.append(
            {
                "metabolite": name,
                "neutral_nrmse": neutral["metrics"][name]["nrmse"],
                "mild_seed_nrmse": mild["metrics"][name]["nrmse"],
                "candidate_nrmse": candidate["metrics"][name]["nrmse"],
                "candidate_minus_mild_nrmse": candidate["metrics"][name]["nrmse"]
                - mild["metrics"][name]["nrmse"],
                "experimental_final": candidate["exp_final"][name],
                "neutral_final": neutral["sim_final"][name],
                "mild_seed_final": mild["sim_final"][name],
                "candidate_final": candidate["sim_final"][name],
            }
        )
    pd.DataFrame(rows).to_csv(out_path, index=False)
    return rows


def _write_trajectory(
    objective: VpepPaseObjective,
    neutral: Mapping[str, Any],
    mild: Mapping[str, Any],
    candidate: Mapping[str, Any],
    out_path: Path,
) -> None:
    rows: list[dict[str, Any]] = []
    for t in objective.t_eval:
        row: dict[str, Any] = {"time_day": float(t)}
        for name in CONCENTRATION_TARGETS:
            idx = EXP_TO_MODEL[name]
            row[f"neutral_{name}"] = float(np.interp(t, neutral["sol"].t, neutral["sol"].y[idx]))
            row[f"mild_seed_{name}"] = float(np.interp(t, mild["sol"].t, mild["sol"].y[idx]))
            row[f"candidate_{name}"] = float(np.interp(t, candidate["sol"].t, candidate["sol"].y[idx]))
            row[f"experimental_{name}"] = float(np.interp(t, objective.exp_time, objective.exp_curves[name]))
        rows.append(row)
    pd.DataFrame(rows).to_csv(out_path, index=False)


def _plot_result(
    objective: VpepPaseObjective,
    neutral: Mapping[str, Any],
    mild: Mapping[str, Any],
    candidate: Mapping[str, Any],
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(3, 4, figsize=(17, 11), constrained_layout=True)
    axes_flat = axes.flatten()
    for ax, name in zip(axes_flat[:8], CONCENTRATION_TARGETS):
        idx = EXP_TO_MODEL[name]
        ax.plot(neutral["sol"].t, neutral["sol"].y[idx], color="#94a3b8", linewidth=1.5, label="neutral")
        ax.plot(mild["sol"].t, mild["sol"].y[idx], color="#64748b", linewidth=1.9, label="mild seed")
        ax.plot(candidate["sol"].t, candidate["sol"].y[idx], color="#2563eb", linewidth=2.3, label="candidate")
        ax.scatter(objective.exp_time, objective.exp_curves[name], color="#111827", s=20, label="Brodbar")
        ax.set_title(
            f"{name}  {mild['metrics'][name]['nrmse']:.2f}->{candidate['metrics'][name]['nrmse']:.2f}",
            fontsize=10,
        )
        ax.set_xlabel("Time (days)")
        ax.set_ylabel("mM")
        ax.grid(True, alpha=0.25)

    for ax, reaction in zip(axes_flat[8:11], TEACHER_FLUX_TARGETS):
        ax.plot(objective.teacher_time, objective.teacher_flux[reaction], color="#111827", linewidth=2.0, label="teacher")
        ax.plot(objective.teacher_time, mild["sim_flux"][reaction], color="#64748b", linewidth=1.9, label="mild seed")
        ax.plot(objective.teacher_time, candidate["sim_flux"][reaction], color="#2563eb", linewidth=2.3, label="candidate")
        ax.set_title(f"{reaction} teacher flux")
        ax.set_xlabel("Time (days)")
        ax.set_ylabel("mM/day")
        ax.grid(True, alpha=0.25)

    ax = axes_flat[11]
    labels = ["mild seed", "candidate"]
    vpk = [mild["routing_metrics"]["PEP_to_VPK_share"], candidate["routing_metrics"]["PEP_to_VPK_share"]]
    bypass = [
        mild["routing_metrics"]["PEP_to_VPEP_PASE_share"],
        candidate["routing_metrics"]["PEP_to_VPEP_PASE_share"],
    ]
    ax.bar(labels, vpk, color="#16a34a", label="VPK")
    ax.bar(labels, bypass, bottom=vpk, color="#dc2626", label="VPEP_PASE")
    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("Direct PEP route share")
    ax.set_title("PEP routing")
    ax.legend(frameon=False)
    ax.grid(True, axis="y", alpha=0.25)

    handles, labels = axes_flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.965), ncol=4, frameon=False)
    fig.suptitle(
        "Brodbar narrow FLA: downward VPEP_PASE with fixed mild VEGLC feedback",
        y=0.998,
    )
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def run_vpep_pase_downward_fla(
    *,
    out_dir: Path,
    seed_params_path: Path,
    n_trials: int,
    t_max: float,
    teacher_dense_points: int,
    random_seed: int,
    method: str,
    rtol: float,
    atol: float,
    vpep_lower: float,
    vpep_upper_ratio: float,
    feedback_strength: float,
    feedback_km: float,
    feedback_hill: float,
    feedback_cap: float,
    level_weight: float,
    endpoint_weight: float,
    slope_weight: float,
    flux_weight: float,
    routing_weight: float,
    guard_weight: float,
    regularization_weight: float,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base_seed_params = _load_params(Path(seed_params_path))
    fixed_feedback = _fixed_mild_feedback(
        strength=feedback_strength,
        km_glc=feedback_km,
        hill=feedback_hill,
        import_cap=feedback_cap,
    )
    center, lower, upper = _downward_bounds(
        float(base_seed_params[OPTIMIZED_PARAM]),
        lower=vpep_lower,
        upper_ratio=vpep_upper_ratio,
    )
    exp_time, exp_curves = _extract_targets(t_max)
    teacher_path = out_dir / "teacher_flux_dataset_vpep_pase.json"
    teacher_dataset = _build_lactate_teacher_dataset(
        exp_time=exp_time,
        exp_curves=exp_curves,
        dense_points=teacher_dense_points,
        out_path=teacher_path,
    )
    objective = VpepPaseObjective(
        x0=np.asarray(load_initial_conditions(), dtype=float),
        base_seed_params=base_seed_params,
        fixed_feedback_params=fixed_feedback,
        exp_time=exp_time,
        exp_curves=exp_curves,
        teacher_dataset=teacher_dataset,
        method=method,
        rtol=rtol,
        atol=atol,
        level_weight=level_weight,
        endpoint_weight=endpoint_weight,
        slope_weight=slope_weight,
        flux_weight=flux_weight,
        routing_weight=routing_weight,
        guard_weight=guard_weight,
        regularization_weight=regularization_weight,
    )

    print(f"Strict downward {OPTIMIZED_PARAM} bounds: {lower:.6g} .. {upper:.6g} (seed={center:.6g})", flush=True)
    neutral = objective.evaluate(center, label="neutral_vhk_atp_seed", apply_feedback=False)
    mild = objective.evaluate(center, label="fixed_mild_feedback_seed", apply_feedback=True)
    objective.neutral_reference = neutral
    objective.mild_reference = mild
    objective.best_payload = mild
    print(
        f"Neutral: loss={neutral['loss']:.4f}, EGLC_ep={neutral['metrics']['EGLC']['endpoint_error']:.4f}, "
        f"GLC={neutral['metrics']['GLC']['nrmse']:.4f}, ATP={neutral['sim_final']['ATP']:.6g}",
        flush=True,
    )
    print(
        f"Mild seed: loss={mild['loss']:.4f}, EGLC_ep={mild['metrics']['EGLC']['endpoint_error']:.4f}, "
        f"GLC={mild['metrics']['GLC']['nrmse']:.4f}, ATP={mild['sim_final']['ATP']:.6g}, "
        f"VPK_share={mild['routing_metrics']['PEP_to_VPK_share']:.3f}",
        flush=True,
    )

    if HAS_OPTUNA and int(n_trials) > 0:
        sampler = optuna.samplers.TPESampler(
            seed=int(random_seed),
            n_startup_trials=min(6, max(3, int(n_trials) // 4)),
        )
        study = optuna.create_study(direction="minimize", sampler=sampler)
        queued_values = [center * ratio for ratio in (0.5, 0.25, 0.1, 0.05, 0.01)]
        for value in queued_values:
            study.enqueue_trial({OPTIMIZED_PARAM: float(np.clip(value, lower, upper))})

        def optuna_objective(trial: Any) -> float:
            value = trial.suggest_float(
                OPTIMIZED_PARAM,
                lower,
                upper,
                log=should_use_log_sampling(OPTIMIZED_PARAM, lower, upper),
            )
            loss = objective(value, label=f"trial_{trial.number}")
            latest = objective.trials[-1]
            print(
                f"trial {trial.number:03d}: loss={loss:.4f}, {OPTIMIZED_PARAM}={value:.6g}, "
                f"GLC={latest['metrics']['GLC']['nrmse']:.4f}, ATP={latest['sim_final']['ATP']:.6g}, "
                f"EGLC_ep={latest['metrics']['EGLC']['endpoint_error']:.4f}, "
                f"VPK_share={latest['routing_metrics']['PEP_to_VPK_share']:.3f}, "
                f"VEGLC_flux={latest['teacher_flux_details']['VEGLC']['nrmse']:.3f}, "
                f"elapsed={latest['elapsed_sec']:.1f}s",
                flush=True,
            )
            return float(loss)

        study.optimize(optuna_objective, n_trials=int(n_trials), show_progress_bar=False)
    else:
        for i, value in enumerate(np.geomspace(lower, upper, max(2, abs(int(n_trials))))):
            objective(float(value), label=f"grid_{i}")

    best = objective.best_payload or mild
    candidate = objective.evaluate(float(best[OPTIMIZED_PARAM]), label="best_final")
    focused_accepted, acceptance_reasons = _focused_acceptance(neutral, mild, candidate)

    neutral_params = objective.build_params(center, apply_feedback=False)
    mild_params = objective.build_params(center, apply_feedback=True)
    candidate_params = objective.build_params(float(candidate[OPTIMIZED_PARAM]), apply_feedback=True)
    (out_dir / "neutral_seed_params.json").write_text(json.dumps(_jsonable(neutral_params), indent=2), encoding="utf-8")
    (out_dir / "seed_fixed_params.json").write_text(json.dumps(_jsonable(mild_params), indent=2), encoding="utf-8")
    (out_dir / "candidate_params.json").write_text(json.dumps(_jsonable(candidate_params), indent=2), encoding="utf-8")

    trials_path = out_dir / "optimization_trials.csv"
    metrics_path = out_dir / "vpep_pase_metrics.csv"
    trajectory_path = out_dir / "vpep_pase_trajectory.csv"
    plot_path = out_dir / "vpep_pase_downward_fla.png"
    pd.DataFrame(_flatten_trial_rows(objective.trials)).to_csv(trials_path, index=False)
    metric_rows = _write_metrics(neutral, mild, candidate, metrics_path)
    _write_trajectory(objective, neutral, mild, candidate, trajectory_path)
    _plot_result(objective, neutral, mild, candidate, plot_path)

    summary = {
        "contract_type": "vpep_pase_downward_fla_result",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "out_dir": str(out_dir),
        "seed_params_path": str(seed_params_path),
        "fixed_feedback_params": fixed_feedback,
        "fixed_parameters": [
            "all parameters except vmax_VPEP_PASE",
            "vmax_VHK",
            "km_ATP_HK",
            "VEGLC mild feedback family and shape",
        ],
        "optimized_params": [OPTIMIZED_PARAM],
        "search_direction": "decrease_only",
        "bounds": {OPTIMIZED_PARAM: {"seed": center, "lower": lower, "upper": upper}},
        "t_max": float(t_max),
        "n_trials": int(n_trials),
        "teacher_dense_points": int(teacher_dense_points),
        "solver": {"method": method, "rtol": float(rtol), "atol": float(atol)},
        "loss_weights": {
            "level_weight": float(level_weight),
            "endpoint_weight": float(endpoint_weight),
            "slope_weight": float(slope_weight),
            "flux_weight": float(flux_weight),
            "routing_weight": float(routing_weight),
            "guard_weight": float(guard_weight),
            "regularization_weight": float(regularization_weight),
        },
        "neutral_seed": _clean_payload(neutral),
        "fixed_mild_feedback_seed": _clean_payload(mild),
        "best_candidate": _clean_payload(candidate),
        "metric_rows": metric_rows,
        "focused_accepted": bool(focused_accepted),
        "acceptance_reasons": acceptance_reasons,
        "parameters_promoted": False,
        "global_best_overwritten": False,
        "requires_full_panel_replay": True,
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "teacher_dataset": str(teacher_path),
            "neutral_seed_params": str(out_dir / "neutral_seed_params.json"),
            "seed_fixed_params": str(out_dir / "seed_fixed_params.json"),
            "candidate_params": str(out_dir / "candidate_params.json"),
            "trials_csv": str(trials_path),
            "metrics_csv": str(metrics_path),
            "trajectory_csv": str(trajectory_path),
            "plot": str(plot_path),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(_jsonable(summary), indent=2), encoding="utf-8")
    print(json.dumps(_jsonable(summary), indent=2), flush=True)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a decrease-only Brodbar FLA pass on vmax_VPEP_PASE")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--seed-params", type=Path, default=DEFAULT_SEED_PARAMS)
    parser.add_argument("--n-trials", type=int, default=20)
    parser.add_argument("--t-max", type=float, default=46.0)
    parser.add_argument("--teacher-dense-points", type=int, default=96)
    parser.add_argument("--random-seed", type=int, default=804)
    parser.add_argument("--method", default="LSODA")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    parser.add_argument("--vpep-lower", type=float, default=0.01)
    parser.add_argument("--vpep-upper-ratio", type=float, default=0.999)
    parser.add_argument("--feedback-strength", type=float, default=0.10)
    parser.add_argument("--feedback-km", type=float, default=8.54922196746391)
    parser.add_argument("--feedback-hill", type=float, default=0.6928279794535482)
    parser.add_argument("--feedback-cap", type=float, default=5.0)
    parser.add_argument("--level-weight", type=float, default=1.5)
    parser.add_argument("--endpoint-weight", type=float, default=3.5)
    parser.add_argument("--slope-weight", type=float, default=2.0)
    parser.add_argument("--flux-weight", type=float, default=3.0)
    parser.add_argument("--routing-weight", type=float, default=2.0)
    parser.add_argument("--guard-weight", type=float, default=12.0)
    parser.add_argument("--regularization-weight", type=float, default=0.03)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_vpep_pase_downward_fla(
        out_dir=args.out_dir,
        seed_params_path=args.seed_params,
        n_trials=args.n_trials,
        t_max=args.t_max,
        teacher_dense_points=args.teacher_dense_points,
        random_seed=args.random_seed,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
        vpep_lower=args.vpep_lower,
        vpep_upper_ratio=args.vpep_upper_ratio,
        feedback_strength=args.feedback_strength,
        feedback_km=args.feedback_km,
        feedback_hill=args.feedback_hill,
        feedback_cap=args.feedback_cap,
        level_weight=args.level_weight,
        endpoint_weight=args.endpoint_weight,
        slope_weight=args.slope_weight,
        flux_weight=args.flux_weight,
        routing_weight=args.routing_weight,
        guard_weight=args.guard_weight,
        regularization_weight=args.regularization_weight,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
