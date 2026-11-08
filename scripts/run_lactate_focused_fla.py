"""Lactate-focused FLA pass after the Brodbar VEGLC transport gate candidate.

This runner keeps the glucose transport hypothesis isolated and optimizes a
narrow lactate/redox seam: VELAC plus VLDH.  It builds a direct VELAC teacher
flux from extracellular lactate and an indirect VLDH teacher flux from the
experimental LAC balance:

    dLAC/dt = VLDH - VELAC  =>  VLDH_teacher = dLAC_exp/dt + VELAC_teacher

The objective also keeps explicit guardrails on EGLC, GLC, and LAC so this pass
cannot silently improve ELAC by breaking the internal glucose/lactate state.
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
from scipy.integrate import solve_ivp
from scipy.interpolate import PchipInterpolator


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
DEFAULT_SEED_PARAMS = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "transport_gate_eglc_elac_46d_n32_endpoint16"
    / "best_params.json"
)
DEFAULT_GLOBAL_BASELINE_PARAMS = ROOT / "Simulations" / "brodbar" / "calibration" / "best_params.json"
DEFAULT_OUT_DIR = ROOT / "Simulations" / "brodbar" / "hermes" / "lactate_focused_velac_vldh_46d"

for path in (str(ROOT), str(SRC_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from extracellular_teacher_flux import build_bordbar_extracellular_teacher_flux_dataset  # noqa: E402
from MM_calibration import (  # noqa: E402
    EXP_TO_MODEL,
    PHASE1_PARAMS,
    get_phase_params,
    load_experimental_data,
    load_initial_conditions,
    should_use_log_sampling,
)
from equadiff_brodbar import (  # noqa: E402
    _compute_veglc_flux,
    _compute_velac_flux,
    _compute_vldh_flux,
    equadiff_brodbar,
)

try:
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    HAS_OPTUNA = True
except Exception:  # pragma: no cover - optional dependency fallback
    optuna = None
    HAS_OPTUNA = False


TARGETS = ("EGLC", "ELAC", "GLC", "LAC", "PYR")
FLUX_TARGETS = ("VELAC", "VLDH")
OPTIMIZED_PARAM_NAMES = (
    "vmax_VELAC",
    "km_LAC",
    "hybrid_blend_VELAC",
    "hybrid_efflux_hill_VELAC",
    "hybrid_backpressure_hill_VELAC",
    "hybrid_backpressure_scale_VELAC",
    "hybrid_km_ELAC",
    "hybrid_lac_retention_strength_VELAC",
    "hybrid_lac_retention_hill_VELAC",
    "hybrid_lac_retention_km_scale_VELAC",
    "vmax_VLDH",
    "km_PYR",
    "km_NADH_NAD",
    "km_NAD_NADH",
    "hybrid_blend_VLDH",
    "hybrid_forward_hill_VLDH",
    "hybrid_reverse_hill_VLDH",
    "hybrid_reverse_scale_VLDH",
)
FIXED_LACTATE_FAMILIES = {
    "kinetic_family_VELAC": "hybrid_reversible_transport",
    "kinetic_family_VLDH": "hybrid_reversible_redox",
}


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return [_jsonable(v) for v in value.tolist()]
    if isinstance(value, (np.integer, np.floating)):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Path):
        return str(value)
    return value


def _load_params(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    out: dict[str, Any] = {}
    for name, value in payload.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            out[str(name)] = float(value)
        elif isinstance(value, str):
            out[str(name)] = value
    return out


def _extract_brodbar_targets(t_max: float) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    time_exp, exp_values, name_to_row = load_experimental_data()
    mask = (time_exp >= 1.0 - 1e-9) & (time_exp <= float(t_max) + 1e-9)
    active_time = np.asarray(time_exp[mask], dtype=float)
    curves: dict[str, np.ndarray] = {}
    for name in TARGETS:
        if name not in name_to_row:
            raise KeyError(f"Brodbar experimental target {name!r} is missing.")
        curves[name] = np.asarray(exp_values[name_to_row[name], mask], dtype=float)
    return active_time, curves


def _build_lactate_teacher_dataset(
    *,
    exp_time: np.ndarray,
    exp_curves: Mapping[str, np.ndarray],
    dense_points: int,
    out_path: Path,
) -> dict[str, Any]:
    extracellular_dataset = build_bordbar_extracellular_teacher_flux_dataset(
        metabolite_names=("EGLC", "ELAC"),
        dense_points=int(dense_points),
        dataset_label="teacher_flux_brodbar_lactate_focused_fla",
        out_path=None,
    )
    dense_time = np.asarray(extracellular_dataset["dense_timepoints"], dtype=float)
    lac_pchip = PchipInterpolator(exp_time, np.asarray(exp_curves["LAC"], dtype=float))
    lac_dense = np.asarray(lac_pchip(dense_time), dtype=float)
    lac_derivative = np.asarray(lac_pchip.derivative()(dense_time), dtype=float)
    velac_teacher = np.asarray(
        extracellular_dataset["reaction_flux_curves"]["VELAC"]["dense_values"],
        dtype=float,
    )
    vldh_teacher = lac_derivative + velac_teacher

    payload = {
        **extracellular_dataset,
        "contract_type": "teacher_flux_dataset",
        "contract_version": 1,
        "dataset_label": "teacher_flux_brodbar_lactate_focused_fla",
        "lactate_balance_equation": "dLAC/dt = VLDH - VELAC",
    }
    payload["teacher_curves"] = dict(payload.get("teacher_curves", {}))
    payload["teacher_curves"]["LAC"] = {
        "source": "experimental_pchip",
        "timepoints": np.asarray(exp_time, dtype=float).tolist(),
        "values": np.asarray(exp_curves["LAC"], dtype=float).tolist(),
        "dense_values": lac_dense.tolist(),
        "dense_derivative": lac_derivative.tolist(),
    }
    payload["reaction_flux_curves"] = dict(payload.get("reaction_flux_curves", {}))
    payload["reaction_flux_curves"]["VLDH"] = {
        "source_metabolite": "LAC",
        "source": "intracellular_lactate_balance_pchip_derivative",
        "equation": "VLDH = dLAC/dt + VELAC_teacher",
        "dense_values": vldh_teacher.tolist(),
        "expected_nonnegative": True,
        "diagnostics": {
            "mean_abs_flux": float(np.mean(np.abs(vldh_teacher))),
            "max_abs_flux": float(np.max(np.abs(vldh_teacher))),
            "min_flux": float(np.min(vldh_teacher)),
            "max_flux": float(np.max(vldh_teacher)),
        },
    }
    payload["teacher_target_weights"] = dict(payload.get("teacher_target_weights", {}))
    payload["teacher_target_weights"]["LAC_balance_VLDH"] = 1.0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(_jsonable(payload), indent=2), encoding="utf-8")
    return payload


def _local_bounds(
    seed_params: Mapping[str, Any],
    param_names: Sequence[str],
    scale: float,
) -> dict[str, tuple[float, float, float]]:
    phase_params = {**PHASE1_PARAMS, **get_phase_params(1, "glycolysis_terminal")}
    out: dict[str, tuple[float, float, float]] = {}
    for name in param_names:
        if name not in phase_params:
            raise KeyError(f"No phase bounds found for {name!r}")
        default, lo, hi = phase_params[name]
        center = float(seed_params.get(name, default))
        if name.startswith("hybrid_"):
            local_lo = float(lo)
            local_hi = float(hi)
        else:
            local_lo = max(float(lo), center / max(float(scale), 1.0))
            local_hi = min(float(hi), center * max(float(scale), 1.0))
        if local_lo >= local_hi:
            local_lo, local_hi = float(lo), float(hi)
        out[name] = (center, local_lo, local_hi)
    return out


def _simulate(
    *,
    x0: np.ndarray,
    params: Mapping[str, Any],
    t_eval: np.ndarray,
    method: str,
    rtol: float,
    atol: float,
) -> Any:
    t_eval = np.asarray(t_eval, dtype=float)
    sol = solve_ivp(
        lambda t, y: equadiff_brodbar(
            t,
            y,
            custom_params=dict(params),
            curve_fit_strength=0.0,
        ),
        (float(t_eval[0]), float(t_eval[-1])),
        np.asarray(x0, dtype=float),
        method=method,
        t_eval=t_eval,
        rtol=float(rtol),
        atol=float(atol),
    )
    if not sol.success:
        raise RuntimeError(sol.message)
    sol.y[:] = np.maximum(sol.y, 0.0)
    return sol


def _state_at(sol: Any, t: float) -> np.ndarray:
    return np.asarray([np.interp(float(t), sol.t, row) for row in sol.y], dtype=float)


def _sim_fluxes(sol: Any, params: Mapping[str, Any], teacher_time: np.ndarray) -> dict[str, np.ndarray]:
    out = {"VEGLC": [], "VELAC": [], "VLDH": []}
    params_dict = dict(params)
    for t in teacher_time:
        x = _state_at(sol, float(t))
        out["VEGLC"].append(
            _compute_veglc_flux(
                float(t),
                x,
                params_dict,
                float(params_dict.get("vmax_VEGLC", 1.077)),
                float(params_dict.get("km_EGLC", 49.484)),
                float(params_dict.get("km_GLC_transport", 5.0)),
            )
        )
        out["VELAC"].append(
            _compute_velac_flux(
                float(t),
                x,
                params_dict,
                float(params_dict.get("vmax_VELAC", 0.58)),
                float(params_dict.get("km_LAC", 49.862494)),
            )
        )
        out["VLDH"].append(
            _compute_vldh_flux(
                x,
                params_dict,
                float(t),
                1.0,
                float(params_dict.get("vmax_VLDH", 0.284952)),
                float(params_dict.get("km_PYR", 0.697)),
                float(params_dict.get("km_LAC", 49.862494)),
                float(params_dict.get("km_NADH_NAD", 1.0)),
                float(params_dict.get("km_NAD_NADH", 1.0)),
                max(float(x[75]), 1e-6),
                max(float(x[76]), 1e-6),
            )
        )
    return {name: np.asarray(values, dtype=float) for name, values in out.items()}


def _nrmse(sim_values: np.ndarray, exp_values: np.ndarray) -> dict[str, float]:
    sim = np.asarray(sim_values, dtype=float)
    exp = np.asarray(exp_values, dtype=float)
    rmse = float(np.sqrt(np.mean((sim - exp) ** 2)))
    norm = float(max(np.mean(np.abs(exp)), 0.01))
    endpoint_error = float(abs(sim[-1] - exp[-1]) / max(abs(float(exp[-1])), 0.01))
    return {"rmse": rmse, "nrmse": rmse / norm, "endpoint_error": endpoint_error}


def _slope_nrmse(sim_values: np.ndarray, exp_values: np.ndarray, time: np.ndarray) -> float:
    sim_slope = np.diff(np.asarray(sim_values, dtype=float)) / np.diff(time)
    exp_slope = np.diff(np.asarray(exp_values, dtype=float)) / np.diff(time)
    norm = float(max(np.mean(np.abs(exp_slope)), 1e-3))
    return float(np.sqrt(np.mean((sim_slope - exp_slope) ** 2)) / norm)


class LactateFocusedObjective:
    def __init__(
        self,
        *,
        x0: np.ndarray,
        seed_params: Mapping[str, Any],
        fixed_family_params: Mapping[str, Any],
        tracked_param_names: Sequence[str],
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
        guard_weight: float,
        regularization_weight: float,
    ) -> None:
        self.x0 = np.asarray(x0, dtype=float)
        self.seed_params = dict(seed_params)
        self.fixed_family_params = dict(fixed_family_params)
        self.tracked_param_names = tuple(tracked_param_names)
        self.exp_time = np.asarray(exp_time, dtype=float)
        self.exp_curves = {name: np.asarray(values, dtype=float) for name, values in exp_curves.items()}
        self.teacher_time = np.asarray(teacher_dataset["dense_timepoints"], dtype=float)
        self.teacher_flux = {
            reaction: np.asarray(teacher_dataset["reaction_flux_curves"][reaction]["dense_values"], dtype=float)
            for reaction in FLUX_TARGETS
        }
        self.method = str(method)
        self.rtol = float(rtol)
        self.atol = float(atol)
        self.level_weight = float(level_weight)
        self.endpoint_weight = float(endpoint_weight)
        self.slope_weight = float(slope_weight)
        self.flux_weight = float(flux_weight)
        self.guard_weight = float(guard_weight)
        self.regularization_weight = float(regularization_weight)
        self.t_eval = np.unique(np.concatenate([self.exp_time, self.teacher_time]))
        self.trials: list[dict[str, Any]] = []
        self.best_payload: dict[str, Any] | None = None
        self.seed_guard_reference: dict[str, Any] | None = None

    def _build_params(self, overrides: Mapping[str, Any], *, apply_fixed_families: bool) -> dict[str, Any]:
        params = dict(self.seed_params)
        if apply_fixed_families:
            params.update(self.fixed_family_params)
        for name, value in overrides.items():
            if isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
                params[name] = float(value)
            else:
                params[name] = value
        return params

    def _param_regularization(self, params: Mapping[str, Any]) -> float:
        terms = []
        for name in self.tracked_param_names:
            value = params.get(name)
            seed = self.seed_params.get(name, PHASE1_PARAMS.get(name, (1.0,))[0])
            if not isinstance(value, (int, float, np.integer, np.floating)):
                continue
            if not isinstance(seed, (int, float, np.integer, np.floating)):
                continue
            value_f = max(float(value), 1e-9)
            seed_f = max(float(seed), 1e-9)
            if name.startswith("hybrid_blend"):
                terms.append((value_f - seed_f) ** 2)
            else:
                terms.append(math.log(value_f / seed_f) ** 2)
        return float(np.mean(terms)) if terms else 0.0

    def evaluate(
        self,
        overrides: Mapping[str, Any],
        *,
        label: str,
        apply_fixed_families: bool = True,
        record: bool = True,
    ) -> dict[str, Any]:
        start = time.perf_counter()
        params = self._build_params(overrides, apply_fixed_families=apply_fixed_families)
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
            if record:
                self.trials.append(payload)
            return payload

        sim_exp = {
            name: np.interp(self.exp_time, sol.t, sol.y[EXP_TO_MODEL[name], :])
            for name in TARGETS
        }
        metrics = {
            name: _nrmse(sim_exp[name], self.exp_curves[name])
            for name in TARGETS
        }
        slope_metrics = {
            name: _slope_nrmse(sim_exp[name], self.exp_curves[name], self.exp_time)
            for name in ("EGLC", "ELAC", "LAC")
        }

        level_weights = {"EGLC": 1.5, "ELAC": 3.0, "GLC": 4.0, "LAC": 5.0, "PYR": 1.0}
        endpoint_weights = {"EGLC": 6.0, "ELAC": 5.0, "GLC": 3.0, "LAC": 5.0, "PYR": 1.0}
        slope_weights = {"EGLC": 2.0, "ELAC": 2.0, "LAC": 3.0}
        level_loss = float(
            sum(level_weights[name] * metrics[name]["nrmse"] for name in TARGETS)
            / sum(level_weights.values())
        )
        endpoint_loss = float(
            sum(endpoint_weights[name] * metrics[name]["endpoint_error"] for name in TARGETS)
            / sum(endpoint_weights.values())
        )
        slope_loss = float(
            sum(slope_weights[name] * slope_metrics[name] for name in slope_metrics)
            / sum(slope_weights.values())
        )

        sim_flux = _sim_fluxes(sol, params, self.teacher_time)
        flux_details = {}
        flux_loss_terms = []
        flux_weights = {"VELAC": 4.0, "VLDH": 4.0}
        for reaction in FLUX_TARGETS:
            target = self.teacher_flux[reaction]
            sim = sim_flux[reaction]
            rmse = float(np.sqrt(np.mean((sim - target) ** 2)))
            norm = float(max(np.mean(np.abs(target)), 1e-4))
            nrmse = rmse / norm
            flux_loss_terms.append(flux_weights[reaction] * nrmse)
            flux_details[reaction] = {"rmse": rmse, "nrmse": nrmse, "weight": flux_weights[reaction]}
        flux_loss = float(sum(flux_loss_terms) / sum(flux_weights.values()))

        regularization_loss = self._param_regularization(params)
        guard_loss = 0.0
        if self.seed_guard_reference is not None:
            seed_metrics = self.seed_guard_reference["metrics"]
            guard_loss += max(0.0, metrics["EGLC"]["endpoint_error"] - seed_metrics["EGLC"]["endpoint_error"] - 0.02) ** 2
            guard_loss += max(0.0, metrics["GLC"]["nrmse"] - seed_metrics["GLC"]["nrmse"] * 1.05) ** 2
            guard_loss += max(0.0, metrics["LAC"]["nrmse"] - seed_metrics["LAC"]["nrmse"] * 1.05) ** 2
            guard_loss += max(0.0, metrics["PYR"]["nrmse"] - seed_metrics["PYR"]["nrmse"] * 1.10) ** 2

        loss = (
            self.level_weight * level_loss
            + self.endpoint_weight * endpoint_loss
            + self.slope_weight * slope_loss
            + self.flux_weight * flux_loss
            + self.guard_weight * guard_loss
            + self.regularization_weight * regularization_loss
        )

        payload = {
            "label": label,
            "params": {name: params.get(name) for name in self.tracked_param_names},
            "fixed_family_params": {
                name: params.get(name)
                for name in self.fixed_family_params
            },
            "loss": float(loss),
            "level_loss": level_loss,
            "endpoint_loss": endpoint_loss,
            "slope_loss": slope_loss,
            "teacher_flux_loss": flux_loss,
            "guard_loss": float(guard_loss),
            "regularization_loss": regularization_loss,
            "metrics": metrics,
            "slope_metrics": slope_metrics,
            "teacher_flux_details": flux_details,
            "sim_final": {name: float(sim_exp[name][-1]) for name in TARGETS},
            "exp_final": {name: float(self.exp_curves[name][-1]) for name in TARGETS},
            "elapsed_sec": float(time.perf_counter() - start),
            "sol": sol,
            "sim_exp": sim_exp,
            "sim_flux": sim_flux,
        }
        for name in self.tracked_param_names:
            payload[name] = params.get(name)
        if record:
            self.trials.append({k: v for k, v in payload.items() if k not in {"sol", "sim_exp", "sim_flux"}})
        if self.best_payload is None or payload["loss"] < self.best_payload["loss"]:
            self.best_payload = payload
        return payload

    def __call__(self, overrides: Mapping[str, Any], *, label: str = "trial") -> float:
        payload = self.evaluate(overrides, label=label, apply_fixed_families=True)
        return float(payload["loss"])


def _flatten_trial_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        flat: dict[str, Any] = {}
        for key, value in row.items():
            if key in {"metrics", "slope_metrics", "teacher_flux_details", "fixed_family_params", "params"}:
                continue
            flat[key] = value
        metrics = row.get("metrics", {})
        if isinstance(metrics, Mapping):
            for metabolite, metric_values in metrics.items():
                if not isinstance(metric_values, Mapping):
                    continue
                for metric_name, metric_value in metric_values.items():
                    flat[f"{metabolite}_{metric_name}"] = metric_value
        flux_details = row.get("teacher_flux_details", {})
        if isinstance(flux_details, Mapping):
            for reaction, detail_values in flux_details.items():
                if isinstance(detail_values, Mapping):
                    flat[f"{reaction}_flux_nrmse"] = detail_values.get("nrmse")
        out.append(flat)
    return out


def _metrics_table(
    *,
    seed: Mapping[str, Any],
    best: Mapping[str, Any],
    global_baseline: Mapping[str, Any] | None,
    out_path: Path,
) -> list[dict[str, Any]]:
    rows = []
    for name in TARGETS:
        seed_metric = seed["metrics"][name]
        best_metric = best["metrics"][name]
        row = {
            "metabolite": name,
            "seed_nrmse": seed_metric["nrmse"],
            "candidate_nrmse": best_metric["nrmse"],
            "delta_nrmse": best_metric["nrmse"] - seed_metric["nrmse"],
            "seed_endpoint_error": seed_metric["endpoint_error"],
            "candidate_endpoint_error": best_metric["endpoint_error"],
            "delta_endpoint_error": best_metric["endpoint_error"] - seed_metric["endpoint_error"],
            "exp_final": best["exp_final"][name],
            "seed_final": seed["sim_final"][name],
            "candidate_final": best["sim_final"][name],
        }
        if global_baseline is not None and "metrics" in global_baseline:
            row["global_baseline_nrmse"] = global_baseline["metrics"][name]["nrmse"]
            row["global_baseline_final"] = global_baseline["sim_final"][name]
        rows.append(row)
    pd.DataFrame(rows).to_csv(out_path, index=False)
    return rows


def _write_trajectory(
    *,
    best: Mapping[str, Any],
    seed: Mapping[str, Any],
    exp_time: np.ndarray,
    exp_curves: Mapping[str, np.ndarray],
    out_path: Path,
) -> None:
    dense_time = np.asarray(best["sol"].t, dtype=float)
    rows: list[dict[str, Any]] = []
    for t in dense_time:
        row: dict[str, Any] = {"time_day": float(t)}
        for name in TARGETS:
            idx = EXP_TO_MODEL[name]
            row[f"seed_{name}"] = float(np.interp(t, seed["sol"].t, seed["sol"].y[idx, :]))
            row[f"candidate_{name}"] = float(np.interp(t, best["sol"].t, best["sol"].y[idx, :]))
            row[f"exp_{name}"] = float(np.interp(t, exp_time, exp_curves[name]))
        for reaction in ("VEGLC", "VELAC", "VLDH"):
            row[f"seed_{reaction}"] = float(np.interp(t, seed["sim_flux_time"], seed["sim_flux_dense"][reaction]))
            row[f"candidate_{reaction}"] = float(np.interp(t, best["sim_flux_time"], best["sim_flux_dense"][reaction]))
        rows.append(row)
    pd.DataFrame(rows).to_csv(out_path, index=False)


def _plot_result(
    *,
    seed: Mapping[str, Any],
    best: Mapping[str, Any],
    global_baseline: Mapping[str, Any] | None,
    objective: LactateFocusedObjective,
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(3, 3, figsize=(15, 11), constrained_layout=True)
    axes_flat = axes.flatten()
    concentration_targets = ("EGLC", "ELAC", "GLC", "LAC", "PYR")
    for ax, name in zip(axes_flat[:5], concentration_targets):
        idx = EXP_TO_MODEL[name]
        if global_baseline is not None and "sol" in global_baseline:
            ax.plot(
                global_baseline["sol"].t,
                global_baseline["sol"].y[idx, :],
                color="#94a3b8",
                linewidth=1.6,
                label="global baseline",
            )
        ax.plot(seed["sol"].t, seed["sol"].y[idx, :], color="#64748b", linewidth=2.0, label="VEGLC seed")
        ax.plot(best["sol"].t, best["sol"].y[idx, :], color="#2563eb", linewidth=2.4, label="lactate FLA")
        ax.scatter(objective.exp_time, objective.exp_curves[name], color="#111827", s=24, label="Brodbar")
        delta = best["metrics"][name]["nrmse"] - seed["metrics"][name]["nrmse"]
        ax.set_title(f"{name}  {seed['metrics'][name]['nrmse']:.2f}->{best['metrics'][name]['nrmse']:.2f}  d={delta:+.2f}")
        ax.set_xlabel("Time (days)")
        ax.set_ylabel("mM")
        ax.grid(True, alpha=0.25)

    for ax, reaction in zip(axes_flat[5:7], FLUX_TARGETS):
        ax.plot(
            objective.teacher_time,
            objective.teacher_flux[reaction],
            color="#111827",
            linewidth=2.2,
            label="teacher flux",
        )
        ax.plot(
            objective.teacher_time,
            seed["sim_flux"][reaction],
            color="#64748b",
            linewidth=2.0,
            label="VEGLC seed ODE",
        )
        ax.plot(
            objective.teacher_time,
            best["sim_flux"][reaction],
            color="#2563eb",
            linewidth=2.4,
            label="lactate FLA ODE",
        )
        ax.set_title(f"{reaction} flux")
        ax.set_xlabel("Time (days)")
        ax.set_ylabel("mM/day")
        ax.grid(True, alpha=0.25)

    ax = axes_flat[7]
    metabolites = list(TARGETS)
    deltas = [best["metrics"][name]["nrmse"] - seed["metrics"][name]["nrmse"] for name in metabolites]
    colors = ["#16a34a" if value < 0 else "#dc2626" for value in deltas]
    ax.barh(metabolites, deltas, color=colors)
    ax.axvline(0, color="#111827", linewidth=1.0)
    ax.set_title("Candidate minus seed nRMSE")
    ax.set_xlabel("delta nRMSE")
    ax.grid(True, axis="x", alpha=0.25)

    ax = axes_flat[8]
    flux_names = list(FLUX_TARGETS)
    seed_flux = [seed["teacher_flux_details"][name]["nrmse"] for name in flux_names]
    best_flux = [best["teacher_flux_details"][name]["nrmse"] for name in flux_names]
    x = np.arange(len(flux_names))
    ax.bar(x - 0.18, seed_flux, width=0.36, color="#64748b", label="seed")
    ax.bar(x + 0.18, best_flux, width=0.36, color="#2563eb", label="candidate")
    ax.set_xticks(x, flux_names)
    ax.set_title("Teacher flux nRMSE")
    ax.set_ylabel("nRMSE")
    ax.grid(True, axis="y", alpha=0.25)

    handles, labels = axes_flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False)
    fig.suptitle("Brodbar lactate-focused FLA: VELAC + VLDH after VEGLC transport gate")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _acceptance(seed: Mapping[str, Any], best: Mapping[str, Any]) -> tuple[bool, list[str]]:
    reasons = []
    accepted = True
    if not float(best["loss"]) < float(seed["loss"]):
        accepted = False
        reasons.append("candidate did not improve the focused lactate loss")
    if best["metrics"]["EGLC"]["endpoint_error"] > max(0.10, seed["metrics"]["EGLC"]["endpoint_error"] + 0.03):
        accepted = False
        reasons.append("EGLC endpoint guard failed")
    if best["metrics"]["ELAC"]["endpoint_error"] >= seed["metrics"]["ELAC"]["endpoint_error"]:
        accepted = False
        reasons.append("ELAC endpoint did not improve")
    if best["metrics"]["LAC"]["nrmse"] > seed["metrics"]["LAC"]["nrmse"] * 1.05:
        accepted = False
        reasons.append("internal LAC nRMSE regressed beyond the guard")
    if best["metrics"]["GLC"]["nrmse"] > seed["metrics"]["GLC"]["nrmse"] * 1.05:
        accepted = False
        reasons.append("internal GLC nRMSE regressed beyond the guard")
    if accepted:
        reasons.append("candidate improved the focused loss while preserving EGLC, GLC, and LAC guards")
    return accepted, reasons


def run_lactate_focused_fla(
    *,
    out_dir: Path,
    seed_params_path: Path,
    global_baseline_params_path: Path | None,
    n_trials: int,
    global_trials: int,
    t_max: float,
    teacher_dense_points: int,
    local_bound_scale: float,
    seed: int,
    method: str,
    rtol: float,
    atol: float,
    level_weight: float,
    endpoint_weight: float,
    slope_weight: float,
    flux_weight: float,
    guard_weight: float,
    regularization_weight: float,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    seed_params = _load_params(Path(seed_params_path))
    global_baseline_params = _load_params(Path(global_baseline_params_path)) if global_baseline_params_path else None
    exp_time, exp_curves = _extract_brodbar_targets(t_max)
    teacher_path = out_dir / "teacher_flux_dataset_lactate_focus.json"
    teacher_dataset = _build_lactate_teacher_dataset(
        exp_time=exp_time,
        exp_curves=exp_curves,
        dense_points=teacher_dense_points,
        out_path=teacher_path,
    )
    x0 = np.asarray(load_initial_conditions(), dtype=float)
    objective = LactateFocusedObjective(
        x0=x0,
        seed_params=seed_params,
        fixed_family_params=FIXED_LACTATE_FAMILIES,
        tracked_param_names=OPTIMIZED_PARAM_NAMES,
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
        guard_weight=guard_weight,
        regularization_weight=regularization_weight,
    )
    bounds = _local_bounds(seed_params, OPTIMIZED_PARAM_NAMES, local_bound_scale)
    print("Lactate-focused FLA bounds:", flush=True)
    for name, (center, lo, hi) in bounds.items():
        print(f"  {name}: {lo:.6g} .. {hi:.6g} (center={center:.6g})", flush=True)

    global_baseline = None
    if global_baseline_params is not None:
        saved_seed = objective.seed_params
        objective.seed_params = global_baseline_params
        global_baseline = objective.evaluate(
            {},
            label="global_baseline",
            apply_fixed_families=False,
            record=False,
        )
        objective.seed_params = saved_seed

    seed_eval = objective.evaluate(
        {name: float(bounds[name][0]) for name in OPTIMIZED_PARAM_NAMES},
        label="veglc_transport_gate_seed",
        apply_fixed_families=True,
    )
    objective.seed_guard_reference = seed_eval
    objective.best_payload = seed_eval
    print(
        f"Seed loss={seed_eval['loss']:.4f}, ELAC endpoint={seed_eval['metrics']['ELAC']['endpoint_error']:.4f}, "
        f"LAC nRMSE={seed_eval['metrics']['LAC']['nrmse']:.4f}, "
        f"GLC nRMSE={seed_eval['metrics']['GLC']['nrmse']:.4f}",
        flush=True,
    )

    if HAS_OPTUNA and int(n_trials) > 0:
        sampler = optuna.samplers.TPESampler(
            seed=int(seed),
            n_startup_trials=min(8, max(2, int(n_trials) // 3)),
            multivariate=True,
        )
        study = optuna.create_study(direction="minimize", sampler=sampler)
        center_trial = {name: float(bounds[name][0]) for name in OPTIMIZED_PARAM_NAMES}
        study.enqueue_trial(center_trial)
        hybrid_seed = dict(center_trial)
        hybrid_seed.update(
            {
                "hybrid_blend_VELAC": 1.0,
                "hybrid_blend_VLDH": 1.0,
                "hybrid_lac_retention_strength_VELAC": 0.5,
            }
        )
        study.enqueue_trial(hybrid_seed)
        fast_lactate = dict(center_trial)
        fast_lactate.update(
            {
                "vmax_VELAC": float(np.clip(center_trial["vmax_VELAC"] * 2.0, bounds["vmax_VELAC"][1], bounds["vmax_VELAC"][2])),
                "vmax_VLDH": float(np.clip(center_trial["vmax_VLDH"] * 2.0, bounds["vmax_VLDH"][1], bounds["vmax_VLDH"][2])),
                "hybrid_blend_VELAC": 0.75,
                "hybrid_blend_VLDH": 0.75,
            }
        )
        study.enqueue_trial(fast_lactate)

        def optuna_objective(trial: Any) -> float:
            overrides = {}
            for name, (_, lo, hi) in bounds.items():
                overrides[name] = trial.suggest_float(
                    name,
                    float(lo),
                    float(hi),
                    log=should_use_log_sampling(name, float(lo), float(hi)),
                )
            loss = objective(overrides, label=f"trial_{trial.number}")
            latest = objective.trials[-1] if objective.trials else {}
            latest_metrics = latest.get("metrics", {}) if isinstance(latest.get("metrics"), Mapping) else {}
            latest_flux = (
                latest.get("teacher_flux_details", {})
                if isinstance(latest.get("teacher_flux_details"), Mapping)
                else {}
            )
            print(
                f"trial {trial.number:03d}: loss={latest.get('loss', loss):.4f}, "
                f"ELAC_ep={latest_metrics.get('ELAC', {}).get('endpoint_error', float('nan')):.4f}, "
                f"LAC={latest_metrics.get('LAC', {}).get('nrmse', float('nan')):.4f}, "
                f"GLC={latest_metrics.get('GLC', {}).get('nrmse', float('nan')):.4f}, "
                f"VELAC_flux={latest_flux.get('VELAC', {}).get('nrmse', float('nan')):.4f}, "
                f"VLDH_flux={latest_flux.get('VLDH', {}).get('nrmse', float('nan')):.4f}, "
                f"elapsed={latest.get('elapsed_sec', float('nan')):.1f}s",
                flush=True,
            )
            return float(loss)

        study.optimize(optuna_objective, n_trials=int(n_trials), show_progress_bar=False)
    else:
        multipliers = np.linspace(1.0 / local_bound_scale, local_bound_scale, max(2, int(n_trials)))
        for i, multiplier in enumerate(multipliers):
            overrides = {}
            for name, (_, lo, hi) in bounds.items():
                center = float(bounds[name][0])
                if name.startswith("hybrid_"):
                    overrides[name] = center
                else:
                    overrides[name] = float(np.clip(center * multiplier, lo, hi))
            objective(overrides, label=f"grid_{i}")

    if int(global_trials) > 0 and objective.best_payload is not None:
        center = dict(objective.best_payload["params"])
        for i in range(int(global_trials)):
            scale = 1.0 + (i + 1) * 0.08
            for direction in (-1.0, 1.0):
                overrides = {}
                for name, (_, lo, hi) in bounds.items():
                    value = center[name]
                    if name.startswith("hybrid_blend"):
                        candidate = float(value) + direction * 0.08 * (i + 1)
                    elif name.startswith("hybrid_"):
                        candidate = float(value)
                    else:
                        candidate = float(value) * (1.0 + direction * (scale - 1.0))
                    overrides[name] = float(np.clip(candidate, lo, hi))
                objective(overrides, label=f"local_refine_{i}_{'up' if direction > 0 else 'down'}")

    best = objective.best_payload or seed_eval
    best_final = objective.evaluate(best["params"], label="best_final", apply_fixed_families=True)
    for payload in (seed_eval, best_final):
        dense_flux = _sim_fluxes(payload["sol"], {**seed_params, **FIXED_LACTATE_FAMILIES, **payload["params"]}, payload["sol"].t)
        payload["sim_flux_time"] = np.asarray(payload["sol"].t, dtype=float)
        payload["sim_flux_dense"] = dense_flux

    accepted, acceptance_reasons = _acceptance(seed_eval, best_final)
    candidate_params = dict(seed_params)
    candidate_params.update(FIXED_LACTATE_FAMILIES)
    candidate_params.update(best_final["params"])
    promoted_or_seed_params = candidate_params if accepted else dict(seed_params)

    (out_dir / "seed_params.json").write_text(json.dumps(_jsonable(seed_params), indent=2), encoding="utf-8")
    (out_dir / "candidate_params.json").write_text(json.dumps(_jsonable(candidate_params), indent=2), encoding="utf-8")
    (out_dir / "promoted_or_seed_params.json").write_text(
        json.dumps(_jsonable(promoted_or_seed_params), indent=2),
        encoding="utf-8",
    )
    if accepted:
        (out_dir / "best_params.json").write_text(json.dumps(_jsonable(candidate_params), indent=2), encoding="utf-8")

    trials_csv = out_dir / "optimization_trials.csv"
    pd.DataFrame(_flatten_trial_rows(objective.trials)).to_csv(trials_csv, index=False)
    metrics_csv = out_dir / "lactate_focus_metrics.csv"
    metric_rows = _metrics_table(
        seed=seed_eval,
        best=best_final,
        global_baseline=global_baseline,
        out_path=metrics_csv,
    )
    trajectory_csv = out_dir / "best_trajectory_lactate_focus.csv"
    _write_trajectory(
        best=best_final,
        seed=seed_eval,
        exp_time=exp_time,
        exp_curves=exp_curves,
        out_path=trajectory_csv,
    )
    plot_path = out_dir / "lactate_focused_fla.png"
    _plot_result(
        seed=seed_eval,
        best=best_final,
        global_baseline=global_baseline,
        objective=objective,
        out_path=plot_path,
    )

    summary = {
        "contract_type": "lactate_focused_fla_result",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "out_dir": str(out_dir),
        "seed_params_path": str(seed_params_path),
        "global_baseline_params_path": str(global_baseline_params_path) if global_baseline_params_path else None,
        "teacher_dataset_path": str(teacher_path),
        "optimized_params": list(OPTIMIZED_PARAM_NAMES),
        "fixed_family_params": dict(FIXED_LACTATE_FAMILIES),
        "targets": list(TARGETS),
        "flux_targets": list(FLUX_TARGETS),
        "t_max": float(t_max),
        "n_trials": int(n_trials),
        "global_trials": int(global_trials),
        "method": method,
        "rtol": float(rtol),
        "atol": float(atol),
        "local_bound_scale": float(local_bound_scale),
        "loss_weights": {
            "level_weight": float(level_weight),
            "endpoint_weight": float(endpoint_weight),
            "slope_weight": float(slope_weight),
            "flux_weight": float(flux_weight),
            "guard_weight": float(guard_weight),
            "regularization_weight": float(regularization_weight),
        },
        "global_baseline": (
            {k: v for k, v in global_baseline.items() if k not in {"sol", "sim_exp", "sim_flux"}}
            if global_baseline is not None
            else None
        ),
        "seed": {k: v for k, v in seed_eval.items() if k not in {"sol", "sim_exp", "sim_flux", "sim_flux_time", "sim_flux_dense"}},
        "best_candidate": {
            k: v
            for k, v in best_final.items()
            if k not in {"sol", "sim_exp", "sim_flux", "sim_flux_time", "sim_flux_dense"}
        },
        "metric_rows": metric_rows,
        "accepted": bool(accepted),
        "acceptance_reasons": acceptance_reasons,
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "teacher_dataset": str(teacher_path),
            "seed_params": str(out_dir / "seed_params.json"),
            "candidate_params": str(out_dir / "candidate_params.json"),
            "promoted_or_seed_params": str(out_dir / "promoted_or_seed_params.json"),
            "best_params": str(out_dir / "best_params.json") if accepted else None,
            "trials_csv": str(trials_csv),
            "metrics_csv": str(metrics_csv),
            "trajectory_csv": str(trajectory_csv),
            "plot": str(plot_path),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(_jsonable(summary), indent=2), encoding="utf-8")
    print(json.dumps(_jsonable(summary), indent=2), flush=True)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Brodbar lactate-focused FLA for VELAC/VLDH")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--seed-params", type=Path, default=DEFAULT_SEED_PARAMS)
    parser.add_argument("--global-baseline-params", type=Path, default=DEFAULT_GLOBAL_BASELINE_PARAMS)
    parser.add_argument("--n-trials", type=int, default=36)
    parser.add_argument("--global-trials", type=int, default=4)
    parser.add_argument("--t-max", type=float, default=46.0)
    parser.add_argument("--teacher-dense-points", type=int, default=96)
    parser.add_argument("--local-bound-scale", type=float, default=4.0)
    parser.add_argument("--seed", type=int, default=122)
    parser.add_argument("--method", default="LSODA")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    parser.add_argument("--level-weight", type=float, default=1.0)
    parser.add_argument("--endpoint-weight", type=float, default=2.0)
    parser.add_argument("--slope-weight", type=float, default=1.5)
    parser.add_argument("--flux-weight", type=float, default=3.0)
    parser.add_argument("--guard-weight", type=float, default=3.0)
    parser.add_argument("--regularization-weight", type=float, default=0.20)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    run_lactate_focused_fla(
        out_dir=args.out_dir,
        seed_params_path=args.seed_params,
        global_baseline_params_path=args.global_baseline_params,
        n_trials=args.n_trials,
        global_trials=args.global_trials,
        t_max=args.t_max,
        teacher_dense_points=args.teacher_dense_points,
        local_bound_scale=args.local_bound_scale,
        seed=args.seed,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
        level_weight=args.level_weight,
        endpoint_weight=args.endpoint_weight,
        slope_weight=args.slope_weight,
        flux_weight=args.flux_weight,
        guard_weight=args.guard_weight,
        regularization_weight=args.regularization_weight,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
