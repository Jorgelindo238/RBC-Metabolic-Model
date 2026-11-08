"""Fast transport-only FLA pass for Brodbar EGLC/ELAC.

This runner is intentionally narrower than ``MM_calibration.run_calibration``:
it optimizes only ``vmax_VEGLC`` and ``vmax_VELAC`` against a direct loss made
of EGLC/ELAC concentration fit, EGLC slope and endpoint penalties, and teacher
flux supervision for VEGLC/VELAC.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
DEFAULT_OUT_DIR = ROOT / "Simulations" / "brodbar" / "hermes" / "transport_only_fla_eglc_elac_46d"
DEFAULT_PARAMS = ROOT / "Simulations" / "brodbar" / "calibration" / "best_params.json"

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
    equadiff_brodbar,
)

try:
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    HAS_OPTUNA = True
except Exception:  # pragma: no cover - optional dependency fallback
    optuna = None
    HAS_OPTUNA = False


TARGETS = ("EGLC", "ELAC")
BASE_PARAM_NAMES = ("vmax_VEGLC", "vmax_VELAC")
VEGLC_FAMILY_CHOICES = (
    "mm_bidirectional",
    "hybrid_asymmetric_transport",
    "transport_depletion_gate",
)
VEGLC_FAMILY_PARAM_NAMES = {
    "mm_bidirectional": BASE_PARAM_NAMES,
    "hybrid_asymmetric_transport": (
        "vmax_VEGLC",
        "km_EGLC",
        "km_GLC_transport",
        "hybrid_import_hill_VEGLC",
        "hybrid_export_hill_VEGLC",
        "hybrid_reverse_scale_VEGLC",
        "vmax_VELAC",
    ),
    "transport_depletion_gate": (
        "vmax_VEGLC",
        "km_EGLC",
        "km_GLC_transport",
        "hybrid_import_hill_VEGLC",
        "hybrid_export_hill_VEGLC",
        "hybrid_reverse_scale_VEGLC",
        "transport_gate_km_VEGLC",
        "transport_gate_hill_VEGLC",
        "vmax_VELAC",
    ),
}


def _optimized_param_names(veglc_family: str, optimize_blend: bool) -> tuple[str, ...]:
    names = list(VEGLC_FAMILY_PARAM_NAMES[veglc_family])
    if optimize_blend and veglc_family != "mm_bidirectional":
        names.insert(1, "hybrid_blend_VEGLC")
    return tuple(dict.fromkeys(names))


def _candidate_fixed_params(veglc_family: str, optimize_blend: bool) -> dict[str, Any]:
    if veglc_family == "mm_bidirectional":
        return {
            "kinetic_family_VEGLC": "mm_bidirectional",
            "hybrid_blend_VEGLC": 0.0,
        }
    fixed = {"kinetic_family_VEGLC": veglc_family}
    if not optimize_blend:
        fixed["hybrid_blend_VEGLC"] = 1.0
    return fixed


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
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(name): (float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else value)
        for name, value in payload.items()
        if isinstance(value, (int, float, str)) and not isinstance(value, bool)
    }


def _extract_brodbar_targets(t_max: float) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    time_exp, exp_values, name_to_row = load_experimental_data()
    mask = (time_exp >= 1.0 - 1e-9) & (time_exp <= float(t_max) + 1e-9)
    active_time = np.asarray(time_exp[mask], dtype=float)
    curves = {}
    for name in TARGETS:
        curves[name] = np.asarray(exp_values[name_to_row[name], mask], dtype=float)
    return active_time, curves


def _local_bounds(
    seed_params: Mapping[str, Any],
    scale: float,
    param_names: tuple[str, ...],
) -> dict[str, tuple[float, float, float]]:
    phase_params = {**PHASE1_PARAMS, **get_phase_params(1, "glycolysis_terminal")}
    out = {}
    for name in param_names:
        default, lo, hi = phase_params[name]
        center = float(seed_params.get(name, default))
        if name.startswith("hybrid_") or name.startswith("transport_gate_"):
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
    params: Mapping[str, float],
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


def _sim_fluxes(sol: Any, params: Mapping[str, float], teacher_time: np.ndarray) -> dict[str, np.ndarray]:
    out = {"VEGLC": [], "VELAC": []}
    for t in teacher_time:
        x = _state_at(sol, float(t))
        out["VEGLC"].append(
            _compute_veglc_flux(
                float(t),
                x,
                dict(params),
                float(params.get("vmax_VEGLC", 1.077)),
                float(params.get("km_EGLC", 49.484)),
                float(params.get("km_GLC_transport", 5.0)),
            )
        )
        out["VELAC"].append(
            _compute_velac_flux(
                float(t),
                x,
                dict(params),
                float(params.get("vmax_VELAC", 0.58)),
                float(params.get("km_LAC", 49.862494)),
            )
        )
    return {name: np.asarray(values, dtype=float) for name, values in out.items()}


class TransportFlaObjective:
    def __init__(
        self,
        *,
        x0: np.ndarray,
        seed_params: Mapping[str, float],
        candidate_fixed_params: Mapping[str, Any],
        tracked_param_names: tuple[str, ...],
        exp_time: np.ndarray,
        exp_curves: Mapping[str, np.ndarray],
        teacher_dataset: Mapping[str, Any],
        method: str,
        rtol: float,
        atol: float,
        level_weight: float,
        eglc_slope_weight: float,
        eglc_endpoint_weight: float,
        elac_endpoint_weight: float,
        teacher_flux_weight: float,
        eglc_teacher_weight: float,
        elac_teacher_weight: float,
        min_eglc_depletion_frac: float,
    ) -> None:
        self.x0 = np.asarray(x0, dtype=float)
        self.seed_params = dict(seed_params)
        self.candidate_fixed_params = dict(candidate_fixed_params)
        self.tracked_param_names = tuple(tracked_param_names)
        self.exp_time = np.asarray(exp_time, dtype=float)
        self.exp_curves = {name: np.asarray(values, dtype=float) for name, values in exp_curves.items()}
        self.teacher_time = np.asarray(teacher_dataset["dense_timepoints"], dtype=float)
        self.teacher_flux = {
            reaction: np.asarray(entry["dense_values"], dtype=float)
            for reaction, entry in teacher_dataset["reaction_flux_curves"].items()
            if reaction in {"VEGLC", "VELAC"}
        }
        self.method = str(method)
        self.rtol = float(rtol)
        self.atol = float(atol)
        self.level_weight = float(level_weight)
        self.eglc_slope_weight = float(eglc_slope_weight)
        self.eglc_endpoint_weight = float(eglc_endpoint_weight)
        self.elac_endpoint_weight = float(elac_endpoint_weight)
        self.teacher_flux_weight = float(teacher_flux_weight)
        self.flux_weights = {"VEGLC": float(eglc_teacher_weight), "VELAC": float(elac_teacher_weight)}
        self.min_eglc_depletion_frac = float(min_eglc_depletion_frac)
        self.t_eval = np.unique(np.concatenate([self.exp_time, self.teacher_time]))
        self.trials: list[dict[str, Any]] = []
        self.best_payload: dict[str, Any] | None = None

    def evaluate(
        self,
        overrides: Mapping[str, Any],
        *,
        label: str,
        apply_candidate_fixed: bool = True,
    ) -> dict[str, Any]:
        start = time.perf_counter()
        params = dict(self.seed_params)
        if apply_candidate_fixed:
            params.update(self.candidate_fixed_params)
        for name, value in overrides.items():
            if isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
                params[name] = float(value)
            else:
                params[name] = value
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
            return {
                "label": label,
                "params": {
                    name: params.get(name)
                    for name in tuple(dict.fromkeys(self.tracked_param_names + tuple(self.candidate_fixed_params)))
                },
                "loss": float("inf"),
                "accepted_gate": False,
                "error": str(exc),
                "elapsed_sec": time.perf_counter() - start,
            }

        sim_exp = {}
        for name in TARGETS:
            idx = EXP_TO_MODEL[name]
            sim_exp[name] = np.interp(self.exp_time, sol.t, sol.y[idx, :])

        level_terms = []
        for name, weight in (("EGLC", 3.0), ("ELAC", 1.5)):
            exp_values = self.exp_curves[name]
            rmse = float(np.sqrt(np.mean((sim_exp[name] - exp_values) ** 2)))
            norm = float(max(np.mean(np.abs(exp_values)), 0.01))
            level_terms.append(weight * rmse / norm)
        level_loss = float(np.sum(level_terms) / np.sum([3.0, 1.5]))

        exp_eglc_slope = np.diff(self.exp_curves["EGLC"]) / np.diff(self.exp_time)
        sim_eglc_slope = np.diff(sim_exp["EGLC"]) / np.diff(self.exp_time)
        slope_norm = float(max(np.mean(np.abs(exp_eglc_slope)), 1e-3))
        slope_loss = float(np.sqrt(np.mean((sim_eglc_slope - exp_eglc_slope) ** 2)) / slope_norm)

        eglc_endpoint_loss = float(
            abs(sim_exp["EGLC"][-1] - self.exp_curves["EGLC"][-1])
            / max(abs(float(self.exp_curves["EGLC"][-1])), 0.01)
        )
        elac_endpoint_loss = float(
            abs(sim_exp["ELAC"][-1] - self.exp_curves["ELAC"][-1])
            / max(abs(float(self.exp_curves["ELAC"][-1])), 0.01)
        )

        sim_flux = _sim_fluxes(sol, params, self.teacher_time)
        flux_terms = []
        flux_details = {}
        for reaction in ("VEGLC", "VELAC"):
            target_flux = self.teacher_flux[reaction]
            rmse = float(np.sqrt(np.mean((sim_flux[reaction] - target_flux) ** 2)))
            norm = float(max(np.mean(np.abs(target_flux)), 1e-4))
            nrmse = rmse / norm
            flux_terms.append(self.flux_weights[reaction] * nrmse)
            flux_details[reaction] = {"rmse": rmse, "nrmse": nrmse, "weight": self.flux_weights[reaction]}
        flux_loss = float(np.sum(flux_terms) / max(np.sum(list(self.flux_weights.values())), 1e-9))

        eglc_depletion_frac = float(
            (self.exp_curves["EGLC"][0] - sim_exp["EGLC"][-1]) / max(self.exp_curves["EGLC"][0], 1e-9)
        )
        accepted_gate = bool(eglc_depletion_frac >= self.min_eglc_depletion_frac)

        loss = (
            self.level_weight * level_loss
            + self.eglc_slope_weight * slope_loss
            + self.eglc_endpoint_weight * eglc_endpoint_loss
            + self.elac_endpoint_weight * elac_endpoint_loss
            + self.teacher_flux_weight * flux_loss
        )
        payload = {
            "label": label,
            "params": {
                name: params.get(name)
                for name in tuple(dict.fromkeys(self.tracked_param_names + tuple(self.candidate_fixed_params)))
            },
            "loss": float(loss),
            "level_loss": float(level_loss),
            "eglc_slope_loss": float(slope_loss),
            "eglc_endpoint_loss": float(eglc_endpoint_loss),
            "elac_endpoint_loss": float(elac_endpoint_loss),
            "teacher_flux_loss": float(flux_loss),
            "teacher_flux_details": flux_details,
            "eglc_depletion_frac": eglc_depletion_frac,
            "accepted_gate": accepted_gate,
            "sim_final": {name: float(sim_exp[name][-1]) for name in TARGETS},
            "exp_final": {name: float(self.exp_curves[name][-1]) for name in TARGETS},
            "elapsed_sec": float(time.perf_counter() - start),
            "sol": sol,
            "sim_exp": sim_exp,
            "sim_flux": sim_flux,
        }
        for name in self.tracked_param_names:
            payload[name] = params.get(name)
        for name in self.candidate_fixed_params:
            payload[name] = params.get(name)
        self.trials.append({k: v for k, v in payload.items() if k not in {"sol", "sim_exp", "sim_flux"}})
        if self.best_payload is None or payload["loss"] < self.best_payload["loss"]:
            self.best_payload = payload
        return payload

    def __call__(self, overrides: Mapping[str, float], *, label: str = "trial") -> float:
        payload = self.evaluate(overrides, label=label, apply_candidate_fixed=True)
        if not np.isfinite(payload["loss"]):
            return float("inf")
        if not payload["accepted_gate"]:
            return float(payload["loss"] + 1e3)
        return float(payload["loss"])


def _plot_result(
    *,
    baseline: Mapping[str, Any],
    best: Mapping[str, Any],
    objective: TransportFlaObjective,
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
    for ax, name in zip(axes[0], TARGETS):
        idx = EXP_TO_MODEL[name]
        ax.plot(baseline["sol"].t, baseline["sol"].y[idx, :], color="#64748b", linewidth=2, label="baseline")
        ax.plot(best["sol"].t, best["sol"].y[idx, :], color="#2563eb", linewidth=2.5, label="best FLA")
        ax.scatter(objective.exp_time, objective.exp_curves[name], color="#111827", s=28, label="Brodbar")
        ax.set_title(f"{name} concentration")
        ax.set_xlabel("Time (days)")
        ax.set_ylabel("mM")
        ax.grid(True, alpha=0.25)
    for ax, reaction in zip(axes[1], ("VEGLC", "VELAC")):
        ax.plot(objective.teacher_time, objective.teacher_flux[reaction], color="#111827", linewidth=2.5, label="teacher flux")
        ax.plot(objective.teacher_time, baseline["sim_flux"][reaction], color="#64748b", linewidth=2, label="baseline ODE")
        ax.plot(objective.teacher_time, best["sim_flux"][reaction], color="#2563eb", linewidth=2.5, label="best FLA")
        ax.set_title(f"{reaction} flux")
        ax.set_xlabel("Time (days)")
        ax.set_ylabel("mM/day")
        ax.grid(True, alpha=0.25)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", frameon=False)
    fig.suptitle("Brodbar transport-only FLA: EGLC/ELAC concentration and teacher flux")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def run_transport_only_fla(
    *,
    out_dir: Path,
    params_path: Path,
    veglc_family: str,
    optimize_blend: bool,
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
    eglc_slope_weight: float,
    eglc_endpoint_weight: float,
    elac_endpoint_weight: float,
    teacher_flux_weight: float,
    eglc_teacher_weight: float,
    elac_teacher_weight: float,
    min_eglc_depletion_frac: float,
) -> dict[str, Any]:
    if veglc_family not in VEGLC_FAMILY_CHOICES:
        raise ValueError(f"Unsupported VEGLC family: {veglc_family}")

    param_names = _optimized_param_names(veglc_family, optimize_blend)
    fixed_candidate_params = _candidate_fixed_params(veglc_family, optimize_blend)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    teacher_path = out_dir / "teacher_flux_dataset_eglc_elac.json"
    teacher_dataset = build_bordbar_extracellular_teacher_flux_dataset(
        metabolite_names=TARGETS,
        dense_points=int(teacher_dense_points),
        out_path=teacher_path,
        dataset_label="teacher_flux_brodbar_eglc_elac_transport_only_fla",
    )
    exp_time, exp_curves = _extract_brodbar_targets(t_max)
    seed_params = _load_params(Path(params_path))
    x0 = np.asarray(load_initial_conditions(), dtype=float)

    objective = TransportFlaObjective(
        x0=x0,
        seed_params=seed_params,
        candidate_fixed_params=fixed_candidate_params,
        tracked_param_names=param_names,
        exp_time=exp_time,
        exp_curves=exp_curves,
        teacher_dataset=teacher_dataset,
        method=method,
        rtol=rtol,
        atol=atol,
        level_weight=level_weight,
        eglc_slope_weight=eglc_slope_weight,
        eglc_endpoint_weight=eglc_endpoint_weight,
        elac_endpoint_weight=elac_endpoint_weight,
        teacher_flux_weight=teacher_flux_weight,
        eglc_teacher_weight=eglc_teacher_weight,
        elac_teacher_weight=elac_teacher_weight,
        min_eglc_depletion_frac=min_eglc_depletion_frac,
    )

    bounds = _local_bounds(seed_params, local_bound_scale, param_names)
    print(f"VEGLC kinetic family candidate: {veglc_family}", flush=True)
    if fixed_candidate_params:
        print(f"Fixed reversible toggles: {fixed_candidate_params}", flush=True)
    print("Transport-only FLA bounds:")
    for name, (center, lo, hi) in bounds.items():
        print(f"  {name}: {lo:.6g} .. {hi:.6g} (center={center:.6g})", flush=True)

    baseline = objective.evaluate(
        {name: float(bounds[name][0]) for name in BASE_PARAM_NAMES if name in bounds},
        label="baseline_current",
        apply_candidate_fixed=False,
    )
    print(
        f"Current baseline loss={baseline['loss']:.4f}, EGLC endpoint={baseline['eglc_endpoint_loss']:.4f}, "
        f"slope={baseline['eglc_slope_loss']:.4f}, flux={baseline['teacher_flux_loss']:.4f}, "
        f"depletion={baseline['eglc_depletion_frac']:.3%}",
        flush=True,
    )
    family_seed = objective.evaluate(
        {name: float(bounds[name][0]) for name in param_names},
        label=f"{veglc_family}_seed",
        apply_candidate_fixed=True,
    )
    print(
        f"Family seed loss={family_seed['loss']:.4f}, EGLC endpoint={family_seed['eglc_endpoint_loss']:.4f}, "
        f"slope={family_seed['eglc_slope_loss']:.4f}, flux={family_seed['teacher_flux_loss']:.4f}, "
        f"depletion={family_seed['eglc_depletion_frac']:.3%}",
        flush=True,
    )
    objective.best_payload = family_seed

    trial_rows = []
    if HAS_OPTUNA and int(n_trials) > 0:
        sampler = optuna.samplers.TPESampler(
            seed=int(seed),
            n_startup_trials=min(4, max(1, int(n_trials) // 3)),
            multivariate=True,
        )
        study = optuna.create_study(direction="minimize", sampler=sampler)
        study.enqueue_trial({name: float(bounds[name][0]) for name in param_names})
        for multiplier in (0.5, 1.5):
            queued = {}
            for name, (_, lo, hi) in bounds.items():
                center = float(bounds[name][0])
                if name.startswith("hybrid_") or name.startswith("transport_gate_"):
                    queued[name] = center
                else:
                    queued[name] = float(np.clip(center * multiplier, lo, hi))
            study.enqueue_trial(queued)

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
            param_text = ", ".join(
                f"{name}={float(overrides[name]):.6g}"
                for name in param_names
                if isinstance(overrides.get(name), (int, float, np.integer, np.floating))
            )
            print(
                f"trial {trial.number:03d}: loss={latest.get('loss', loss):.4f}, "
                f"gate={latest.get('accepted_gate')}, "
                f"{param_text}, "
                f"elapsed={latest.get('elapsed_sec', float('nan')):.1f}s",
                flush=True,
            )
            return float(loss)

        study.optimize(optuna_objective, n_trials=int(n_trials), show_progress_bar=False)
        trial_rows = list(objective.trials)
    else:
        multipliers = np.linspace(1.0 / local_bound_scale, local_bound_scale, max(2, int(n_trials)))
        for i, multiplier in enumerate(multipliers):
            overrides = {}
            for name, (_, lo, hi) in bounds.items():
                overrides[name] = float(np.clip(float(seed_params[name]) * multiplier, lo, hi))
            objective(overrides, label=f"grid_{i}")
        trial_rows = list(objective.trials)

    best = objective.best_payload or baseline
    best_params = dict(seed_params)
    best_params.update(fixed_candidate_params)
    best_params.update(best["params"])
    accepted = bool(best["loss"] <= baseline["loss"] and best["accepted_gate"])
    promoted_params = best_params if accepted else dict(seed_params)

    if int(global_trials) > 0:
        # Lightweight local refinement around the best trial. This keeps the
        # run deterministic and avoids a second full optimizer setup.
        center = best["params"]
        for i in range(int(global_trials)):
            scale = 1.0 + (i + 1) * 0.10
            for direction in (-1.0, 1.0):
                overrides = {}
                for name, (_, lo, hi) in bounds.items():
                    candidate = float(center[name]) * (1.0 + direction * (scale - 1.0))
                    overrides[name] = float(np.clip(candidate, lo, hi))
                objective(overrides, label=f"local_refine_{i}_{'up' if direction > 0 else 'down'}")
        best = objective.best_payload or best
        best_params = dict(seed_params)
        best_params.update(fixed_candidate_params)
        best_params.update(best["params"])
        accepted = bool(best["loss"] <= baseline["loss"] and best["accepted_gate"])
        promoted_params = best_params if accepted else dict(seed_params)
        trial_rows = list(objective.trials)

    final_best = objective.evaluate(best["params"], label="best_final", apply_candidate_fixed=True)
    (out_dir / "seed_params.json").write_text(json.dumps(_jsonable(seed_params), indent=2), encoding="utf-8")
    if accepted:
        (out_dir / "best_params.json").write_text(json.dumps(_jsonable(best_params), indent=2), encoding="utf-8")
    (out_dir / "candidate_params.json").write_text(json.dumps(_jsonable(best_params), indent=2), encoding="utf-8")
    (out_dir / "promoted_or_seed_params.json").write_text(
        json.dumps(_jsonable(promoted_params), indent=2),
        encoding="utf-8",
    )

    pd.DataFrame(trial_rows).drop(columns=["teacher_flux_details"], errors="ignore").to_csv(
        out_dir / "optimization_trials.csv",
        index=False,
    )
    t = final_best["sol"].t
    traj = pd.DataFrame({"Time (days)": t})
    for name in TARGETS:
        traj[name] = final_best["sol"].y[EXP_TO_MODEL[name], :]
    full_final_params = dict(seed_params)
    full_final_params.update(fixed_candidate_params)
    full_final_params.update(final_best["params"])
    flux_at_sol_time = _sim_fluxes(final_best["sol"], full_final_params, t)
    traj["VEGLC"] = flux_at_sol_time["VEGLC"]
    traj["VELAC"] = flux_at_sol_time["VELAC"]
    traj.to_csv(out_dir / "best_trajectory_eglc_elac.csv", index=False)

    plot_path = out_dir / "transport_only_fla_eglc_elac.png"
    _plot_result(baseline=baseline, best=final_best, objective=objective, out_path=plot_path)

    summary = {
        "contract_type": "transport_only_fla_eglc_elac_result",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "out_dir": str(out_dir),
        "params_path": str(params_path),
        "teacher_dataset_path": str(teacher_path),
        "targets": list(TARGETS),
        "veglc_family": str(veglc_family),
        "fixed_candidate_params": dict(fixed_candidate_params),
        "optimized_params": list(param_names),
        "t_max": float(t_max),
        "n_trials": int(n_trials),
        "global_trials": int(global_trials),
        "method": method,
        "rtol": float(rtol),
        "atol": float(atol),
        "local_bound_scale": float(local_bound_scale),
        "loss_weights": {
            "level_weight": float(level_weight),
            "eglc_slope_weight": float(eglc_slope_weight),
            "eglc_endpoint_weight": float(eglc_endpoint_weight),
            "elac_endpoint_weight": float(elac_endpoint_weight),
            "teacher_flux_weight": float(teacher_flux_weight),
            "eglc_teacher_weight": float(eglc_teacher_weight),
            "elac_teacher_weight": float(elac_teacher_weight),
        },
        "min_eglc_depletion_frac": float(min_eglc_depletion_frac),
        "baseline": {k: v for k, v in baseline.items() if k not in {"sol", "sim_exp", "sim_flux"}},
        "family_seed": {k: v for k, v in family_seed.items() if k not in {"sol", "sim_exp", "sim_flux"}},
        "best_candidate": {k: v for k, v in final_best.items() if k not in {"sol", "sim_exp", "sim_flux"}},
        "accepted": bool(accepted),
        "acceptance_reason": (
            "candidate improved direct FLA loss and passed EGLC depletion gate"
            if accepted
            else "candidate was not promoted because it did not improve direct FLA loss or failed the EGLC depletion gate"
        ),
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "seed_params": str(out_dir / "seed_params.json"),
            "candidate_params": str(out_dir / "candidate_params.json"),
            "promoted_or_seed_params": str(out_dir / "promoted_or_seed_params.json"),
            "best_params": str(out_dir / "best_params.json") if accepted else None,
            "trials_csv": str(out_dir / "optimization_trials.csv"),
            "trajectory_csv": str(out_dir / "best_trajectory_eglc_elac.csv"),
            "plot": str(plot_path),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(_jsonable(summary), indent=2), encoding="utf-8")
    print(json.dumps(_jsonable(summary), indent=2), flush=True)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run fast Brodbar transport-only FLA for EGLC/ELAC")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--params", type=Path, default=DEFAULT_PARAMS)
    parser.add_argument(
        "--veglc-family",
        choices=VEGLC_FAMILY_CHOICES,
        default="mm_bidirectional",
        help="VEGLC kinetic family to activate only for this candidate run.",
    )
    parser.add_argument(
        "--optimize-blend",
        action="store_true",
        help="Optimize hybrid_blend_VEGLC instead of fixing it to 1.0 for hybrid families.",
    )
    parser.add_argument("--n-trials", type=int, default=12)
    parser.add_argument("--global-trials", type=int, default=3)
    parser.add_argument("--t-max", type=float, default=46.0)
    parser.add_argument("--teacher-dense-points", type=int, default=80)
    parser.add_argument("--local-bound-scale", type=float, default=4.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--method", default="LSODA")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    parser.add_argument("--level-weight", type=float, default=1.0)
    parser.add_argument("--eglc-slope-weight", type=float, default=3.0)
    parser.add_argument("--eglc-endpoint-weight", type=float, default=8.0)
    parser.add_argument("--elac-endpoint-weight", type=float, default=1.5)
    parser.add_argument("--teacher-flux-weight", type=float, default=3.0)
    parser.add_argument("--eglc-teacher-weight", type=float, default=8.0)
    parser.add_argument("--elac-teacher-weight", type=float, default=3.0)
    parser.add_argument("--min-eglc-depletion-frac", type=float, default=0.05)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    run_transport_only_fla(
        out_dir=args.out_dir,
        params_path=args.params,
        veglc_family=args.veglc_family,
        optimize_blend=bool(args.optimize_blend),
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
        eglc_slope_weight=args.eglc_slope_weight,
        eglc_endpoint_weight=args.eglc_endpoint_weight,
        elac_endpoint_weight=args.elac_endpoint_weight,
        teacher_flux_weight=args.teacher_flux_weight,
        eglc_teacher_weight=args.eglc_teacher_weight,
        elac_teacher_weight=args.elac_teacher_weight,
        min_eglc_depletion_frac=args.min_eglc_depletion_frac,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
