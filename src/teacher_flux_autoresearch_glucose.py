"""
CPU-only mini-autoresearch loop for extracellular glucose transport (VEGLC).

Workflow:
1. Build an EGLC-only teacher flux dataset from experimental data.
2. Run the ODE once with VEGLC overridden by the teacher flux to recover
   teacher-aligned state trajectories.
3. Fit a small catalog of glucose transport kinetics on CPU against the
   recovered teacher VEGLC flux.
4. Replay the best executable student candidate in the full ODE and keep it
   only if the EGLC curve improves against the promoted seed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.teacher_flux_bridge import (
    _align_states_to_flux_times,
    _detect_time_column,
    _load_sheet1,
    build_teacher_flux_dataset,
    evaluate_teacher_flux_at_time,
    extract_experimental_curve,
    mm,
    write_teacher_override_params,
)


MAIN = ROOT / "src" / "main.py"
DEFAULT_OUT_ROOT = ROOT / "Simulations" / "brodbar" / "hermes" / "teacher_flux" / "glucose_autoresearch"
DEFAULT_SEED = ROOT / "Simulations" / "brodbar" / "calibration" / "hybrid_teacher_flux_global_seed_promoted" / "best_params.json"
MODEL_METABOLITES = ROOT / "Simulations" / "brodbar" / "metabolites" / "all_metabolites.csv"
MODEL_FLUXES = ROOT / "Simulations" / "brodbar" / "fluxes" / "reaction_fluxes.csv"


@dataclass(frozen=True)
class FamilySpec:
    name: str
    executable: bool
    param_names: tuple[str, ...]
    lower_bounds: tuple[float, ...]
    upper_bounds: tuple[float, ...]
    default_guess: tuple[float, ...]
    predictor: Callable[[np.ndarray, dict[str, np.ndarray]], np.ndarray]
    merge_params: Callable[[dict[str, object], np.ndarray], dict[str, object]]


def _run_main_and_capture(params_path: Path, out_dir: Path, label: str) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["python", str(MAIN), "--model", "brodbar", "--load-params", str(params_path)],
        cwd=str(ROOT),
        check=True,
    )
    metabolite_copy = out_dir / f"{label}_all_metabolites.csv"
    flux_copy = out_dir / f"{label}_reaction_fluxes.csv"
    shutil.copy2(MODEL_METABOLITES, metabolite_copy)
    shutil.copy2(MODEL_FLUXES, flux_copy)
    return {"metabolites": metabolite_copy, "fluxes": flux_copy}


def _teacher_flux_from_dataset(dataset_path: Path, flux_time: np.ndarray) -> np.ndarray:
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    return np.asarray(
        [evaluate_teacher_flux_at_time(dataset, "VEGLC", float(t)) for t in flux_time],
        dtype=float,
    )


def _eglc_curve_metrics(state_csv_path: Path) -> dict[str, float]:
    state_df = pd.read_csv(state_csv_path)
    time_col = _detect_time_column(state_df)
    exp_curve = extract_experimental_curve("EGLC")
    exp_time = np.asarray(exp_curve["timepoints"], dtype=float)
    exp_values = np.asarray(exp_curve["values"], dtype=float)
    sim_values = np.interp(exp_time, state_df[time_col].to_numpy(dtype=float), state_df["EGLC"].to_numpy(dtype=float))
    rmse = float(np.sqrt(np.mean((sim_values - exp_values) ** 2)))
    norm = float(max(np.mean(np.abs(exp_values)), 1e-6))
    final_abs_error = float(abs(sim_values[-1] - exp_values[-1]))
    return {
        "eglc_rmse": rmse,
        "eglc_nrmse": rmse / norm,
        "eglc_final_sim": float(sim_values[-1]),
        "eglc_final_exp": float(exp_values[-1]),
        "eglc_final_abs_error": final_abs_error,
        **_global_curve_metrics(state_df, time_col),
    }


def _global_curve_metrics(state_df: pd.DataFrame, time_col: str) -> dict[str, float]:
    exp_time, exp_df = _load_sheet1()
    sim_time = state_df[time_col].to_numpy(dtype=float)
    column_map = {str(col).upper(): str(col) for col in state_df.columns}
    per_metabolite = []

    for _, row in exp_df.iterrows():
        metabolite = str(row["Conc / mM"]).upper()
        sim_column = column_map.get(metabolite)
        if sim_column is None:
            continue
        exp_values = row.iloc[1:].to_numpy(dtype=float)
        sim_values = np.interp(exp_time, sim_time, state_df[sim_column].to_numpy(dtype=float))
        rmse = float(np.sqrt(np.mean((sim_values - exp_values) ** 2)))
        norm = float(max(np.mean(np.abs(exp_values)), 1e-6))
        per_metabolite.append(rmse / norm)

    if not per_metabolite:
        return {"global_nrmse": float("inf"), "global_metabolite_count": 0.0}
    return {
        "global_nrmse": float(np.mean(per_metabolite)),
        "global_metabolite_count": float(len(per_metabolite)),
    }


def _sample_initial_guess(spec: FamilySpec, rng: np.random.Generator) -> np.ndarray:
    guess = []
    for default, lower, upper in zip(spec.default_guess, spec.lower_bounds, spec.upper_bounds):
        span = upper - lower
        if span <= 0:
            guess.append(lower)
            continue
        if lower > 0 and upper / max(lower, 1e-12) >= 20:
            sampled = float(np.exp(rng.uniform(np.log(lower), np.log(upper))))
        else:
            sampled = float(rng.uniform(lower, upper))
        if rng.random() < 0.35:
            sampled = default
        guess.append(sampled)
    return np.asarray(guess, dtype=float)


def _fit_family_with_budget(
    spec: FamilySpec,
    states: dict[str, np.ndarray],
    target_flux: np.ndarray,
    *,
    budget_seconds: float,
    rng_seed: int,
) -> dict[str, object]:
    rng = np.random.default_rng(rng_seed)
    lower = np.asarray(spec.lower_bounds, dtype=float)
    upper = np.asarray(spec.upper_bounds, dtype=float)
    default_guess = np.asarray(spec.default_guess, dtype=float)
    start = time.monotonic()
    attempts = 0
    best_payload: dict[str, object] | None = None

    def residual(params: np.ndarray) -> np.ndarray:
        return spec.predictor(params, states) - target_flux

    while attempts == 0 or time.monotonic() - start < budget_seconds:
        x0 = default_guess if attempts == 0 else _sample_initial_guess(spec, rng)
        attempts += 1
        try:
            result = least_squares(
                residual,
                x0=x0,
                bounds=(lower, upper),
                max_nfev=2500,
            )
        except Exception as exc:
            payload = {
                "success": False,
                "error": str(exc),
                "attempt": attempts,
                "params": [float(x) for x in x0],
            }
            if best_payload is None:
                best_payload = payload
            continue

        predicted = spec.predictor(result.x, states)
        rmse = float(np.sqrt(np.mean((predicted - target_flux) ** 2)))
        norm = float(max(np.mean(np.abs(target_flux)), 1e-6))
        payload = {
            "success": bool(result.success),
            "attempts": attempts,
            "message": result.message,
            "params": [float(x) for x in result.x],
            "teacher_flux_rmse": rmse,
            "teacher_flux_nrmse": rmse / norm,
            "predicted_flux": predicted.tolist(),
        }
        if best_payload is None or payload["teacher_flux_nrmse"] < best_payload.get("teacher_flux_nrmse", float("inf")):
            best_payload = payload

    assert best_payload is not None
    best_payload["family"] = spec.name
    best_payload["budget_seconds"] = budget_seconds
    best_payload["executable"] = spec.executable
    return best_payload


def _family_catalog() -> list[FamilySpec]:
    def mm_bidirectional(params: np.ndarray, states: dict[str, np.ndarray]) -> np.ndarray:
        vmax, km_eglc, km_glc = params
        return vmax * (mm(states["EGLC"], km_eglc) - mm(states["GLC"], km_glc))

    def hybrid_asymmetric(params: np.ndarray, states: dict[str, np.ndarray]) -> np.ndarray:
        vmax, km_eglc, km_glc, h_imp, h_exp, reverse_scale, blend = params
        base_flux = vmax * (mm(states["EGLC"], km_eglc) - mm(states["GLC"], km_glc))
        alt_flux = vmax * (
            mm(states["EGLC"], km_eglc, hill_coef=h_imp)
            - reverse_scale * mm(states["GLC"], km_glc, hill_coef=h_exp)
        )
        blend = float(np.clip(blend, 0.0, 1.0))
        return (1.0 - blend) * base_flux + blend * alt_flux

    def depletion_gate(params: np.ndarray, states: dict[str, np.ndarray]) -> np.ndarray:
        vmax, km_eglc, km_glc, h_imp, h_exp, reverse_scale, gate_km, gate_hill = params
        depletion = mm(states["EGLC"], gate_km, hill_coef=gate_hill)
        return vmax * (
            depletion * mm(states["EGLC"], km_eglc, hill_coef=h_imp)
            - reverse_scale * mm(states["GLC"], km_glc, hill_coef=h_exp)
        )

    def merge_mm(seed_params: dict[str, object], params: np.ndarray) -> dict[str, object]:
        merged = dict(seed_params)
        merged.update(
            {
                "kinetic_family_VEGLC": "mm_bidirectional",
                "vmax_VEGLC": float(params[0]),
                "km_EGLC": float(params[1]),
                "km_GLC_transport": float(params[2]),
                "hybrid_blend_VEGLC": 0.0,
            }
        )
        return merged

    def merge_hybrid(seed_params: dict[str, object], params: np.ndarray) -> dict[str, object]:
        merged = dict(seed_params)
        merged.update(
            {
                "kinetic_family_VEGLC": "hybrid_asymmetric_transport",
                "vmax_VEGLC": float(params[0]),
                "km_EGLC": float(params[1]),
                "km_GLC_transport": float(params[2]),
                "hybrid_import_hill_VEGLC": float(params[3]),
                "hybrid_export_hill_VEGLC": float(params[4]),
                "hybrid_reverse_scale_VEGLC": float(params[5]),
                "hybrid_blend_VEGLC": float(params[6]),
            }
        )
        return merged

    def merge_depletion_gate(seed_params: dict[str, object], params: np.ndarray) -> dict[str, object]:
        merged = dict(seed_params)
        merged.update(
            {
                "kinetic_family_VEGLC": "transport_depletion_gate",
                "vmax_VEGLC": float(params[0]),
                "km_EGLC": float(params[1]),
                "km_GLC_transport": float(params[2]),
                "hybrid_import_hill_VEGLC": float(params[3]),
                "hybrid_export_hill_VEGLC": float(params[4]),
                "hybrid_reverse_scale_VEGLC": float(params[5]),
                "transport_gate_km_VEGLC": float(params[6]),
                "transport_gate_hill_VEGLC": float(params[7]),
                "hybrid_blend_VEGLC": 1.0,
            }
        )
        return merged

    return [
        FamilySpec(
            name="mm_bidirectional",
            executable=True,
            param_names=("vmax_VEGLC", "km_EGLC", "km_GLC_transport"),
            lower_bounds=(0.25, 0.5, 0.1),
            upper_bounds=(4.0, 80.0, 20.0),
            default_guess=(1.0, 25.0, 5.0),
            predictor=mm_bidirectional,
            merge_params=merge_mm,
        ),
        FamilySpec(
            name="hybrid_asymmetric_transport",
            executable=True,
            param_names=(
                "vmax_VEGLC",
                "km_EGLC",
                "km_GLC_transport",
                "hybrid_import_hill_VEGLC",
                "hybrid_export_hill_VEGLC",
                "hybrid_reverse_scale_VEGLC",
                "hybrid_blend_VEGLC",
            ),
            lower_bounds=(0.25, 0.5, 0.1, 0.5, 0.5, 0.0, 0.0),
            upper_bounds=(4.0, 80.0, 20.0, 5.0, 5.0, 3.0, 1.0),
            default_guess=(1.0, 25.0, 5.0, 1.0, 1.0, 1.0, 1.0),
            predictor=hybrid_asymmetric,
            merge_params=merge_hybrid,
        ),
        FamilySpec(
            name="transport_depletion_gate",
            executable=True,
            param_names=(
                "vmax_VEGLC",
                "km_EGLC",
                "km_GLC_transport",
                "import_hill",
                "export_hill",
                "reverse_scale",
                "gate_km",
                "gate_hill",
            ),
            lower_bounds=(0.25, 0.5, 0.1, 0.5, 0.5, 0.0, 0.5, 0.5),
            upper_bounds=(4.0, 80.0, 20.0, 5.0, 5.0, 3.0, 80.0, 5.0),
            default_guess=(1.0, 25.0, 5.0, 1.0, 1.0, 1.0, 10.0, 1.0),
            predictor=depletion_gate,
            merge_params=merge_depletion_gate,
        ),
    ]


def _save_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _plot_flux_leaderboard(
    flux_time: np.ndarray,
    target_flux: np.ndarray,
    candidates: list[dict[str, object]],
    plot_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 5), constrained_layout=True)
    ax.plot(flux_time, target_flux, linewidth=2.5, label="teacher flux")
    for candidate in candidates:
        ax.plot(
            flux_time,
            np.asarray(candidate["predicted_flux"], dtype=float),
            "--",
            label=f"{candidate['family']} ({candidate['teacher_flux_nrmse']:.3f})",
        )
    ax.set_title("VEGLC teacher flux autoresearch leaderboard")
    ax.set_xlabel("time")
    ax.set_ylabel("flux")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)


def _plot_eglc_ode_compare(seed_csv: Path, candidate_csv: Path, plot_path: Path) -> None:
    seed_df = pd.read_csv(seed_csv)
    candidate_df = pd.read_csv(candidate_csv)
    time_col = _detect_time_column(seed_df)
    exp_curve = extract_experimental_curve("EGLC")
    exp_time = np.asarray(exp_curve["timepoints"], dtype=float)
    exp_values = np.asarray(exp_curve["values"], dtype=float)

    fig, ax = plt.subplots(figsize=(10, 5), constrained_layout=True)
    ax.plot(seed_df[time_col], seed_df["EGLC"], label="seed ODE", linewidth=2)
    ax.plot(candidate_df[time_col], candidate_df["EGLC"], label="best student ODE", linewidth=2)
    ax.plot(exp_time, exp_values, "o", label="experimental EGLC")
    ax.set_title("EGLC autoresearch: seed vs best executable student")
    ax.set_xlabel(time_col)
    ax.set_ylabel("EGLC")
    ax.legend()
    ax.grid(alpha=0.3)
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)


def _rank_ode_candidate(candidate: dict[str, object]) -> tuple[float, float, float, float]:
    metrics = candidate["curve_metrics"]
    return (
        float(metrics["eglc_nrmse"]),
        float(metrics["eglc_final_abs_error"]),
        float(metrics["global_nrmse"]),
        float(candidate["teacher_flux_nrmse"]),
    )


def run_glucose_autoresearch(
    *,
    seed_params_path: Path = DEFAULT_SEED,
    out_root: Path = DEFAULT_OUT_ROOT,
    budget_per_family_seconds: float = 45.0,
    rng_seed: int = 29,
    top_k_executable_replays: int = 2,
) -> dict[str, object]:
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    dataset_path = out_root / "teacher_flux_dataset.json"
    teacher_override_params_path = out_root / "teacher_override_params.json"
    teacher_run_dir = out_root / "teacher_run"
    seed_run_dir = out_root / "seed_run"
    candidate_run_dir = out_root / "best_executable_run"
    candidates_dir = out_root / "candidate_params"

    build_teacher_flux_dataset(
        metabolite_names=("EGLC",),
        dense_points=200,
        out_path=dataset_path,
    )
    write_teacher_override_params(
        Path(seed_params_path),
        dataset_path,
        teacher_override_params_path,
        reactions=("VEGLC",),
    )

    seed_outputs = _run_main_and_capture(Path(seed_params_path), seed_run_dir, "seed")
    teacher_outputs = _run_main_and_capture(teacher_override_params_path, teacher_run_dir, "teacher")

    state_df = pd.read_csv(teacher_outputs["metabolites"])
    flux_df = pd.read_csv(teacher_outputs["fluxes"])
    aligned_states = _align_states_to_flux_times(state_df, flux_df, ["GLC", "EGLC"])
    flux_time = aligned_states["time"]
    teacher_flux = _teacher_flux_from_dataset(dataset_path, flux_time)
    seed_curve_metrics = _eglc_curve_metrics(seed_outputs["metabolites"])

    seed_params = json.loads(Path(seed_params_path).read_text(encoding="utf-8"))
    family_results: list[dict[str, object]] = []
    executable_results: list[dict[str, object]] = []

    for index, spec in enumerate(_family_catalog()):
        fitted = _fit_family_with_budget(
            spec,
            aligned_states,
            teacher_flux,
            budget_seconds=budget_per_family_seconds,
            rng_seed=rng_seed + index,
        )
        fitted["param_names"] = list(spec.param_names)
        fitted["merged_params_preview"] = spec.merge_params(seed_params, np.asarray(fitted["params"], dtype=float))

        if spec.executable:
            candidate_params = spec.merge_params(seed_params, np.asarray(fitted["params"], dtype=float))
            candidate_path = candidates_dir / f"{spec.name}_params.json"
            _save_json(candidate_path, candidate_params)
            fitted["candidate_params_path"] = str(candidate_path)
            family_results.append(fitted)
            executable_results.append(fitted)
        else:
            family_results.append(fitted)

    if not executable_results:
        raise RuntimeError("No executable glucose autoresearch candidates were produced")
    replay_count = max(1, int(top_k_executable_replays))
    top_executable_by_teacher = sorted(executable_results, key=lambda item: item["teacher_flux_nrmse"])[:replay_count]
    candidate_ode_evaluations: list[dict[str, object]] = []

    for idx, candidate in enumerate(top_executable_by_teacher, start=1):
        candidate_path = Path(candidate["candidate_params_path"])
        replay_dir = candidate_run_dir / f"{idx:02d}_{candidate['family']}"
        replay_outputs = _run_main_and_capture(candidate_path, replay_dir, candidate["family"])
        replay_metrics = _eglc_curve_metrics(replay_outputs["metabolites"])
        evaluation = {
            "family": candidate["family"],
            "teacher_flux_nrmse": candidate["teacher_flux_nrmse"],
            "teacher_flux_rmse": candidate["teacher_flux_rmse"],
            "candidate_params_path": str(candidate_path),
            "curve_metrics": replay_metrics,
            "run_artifacts": {key: str(value) for key, value in replay_outputs.items()},
        }
        candidate_ode_evaluations.append(evaluation)

    best_executable = min(candidate_ode_evaluations, key=_rank_ode_candidate)
    best_candidate_params_path = Path(best_executable["candidate_params_path"])
    candidate_curve_metrics = best_executable["curve_metrics"]

    decision = "keep" if candidate_curve_metrics["eglc_nrmse"] < seed_curve_metrics["eglc_nrmse"] else "discard"
    improvement = seed_curve_metrics["eglc_nrmse"] - candidate_curve_metrics["eglc_nrmse"]

    summary = {
        "contract_type": "teacher_flux_glucose_autoresearch_report",
        "contract_version": 1,
        "seed_params_path": str(seed_params_path),
        "teacher_dataset_path": str(dataset_path),
        "teacher_override_params_path": str(teacher_override_params_path),
        "budget_per_family_seconds": budget_per_family_seconds,
        "rng_seed": rng_seed,
        "ranking_policy": "ode_eglc_curve_first_then_global_loss",
        "seed_curve_metrics": seed_curve_metrics,
        "candidate_curve_metrics": candidate_curve_metrics,
        "decision": decision,
        "eglc_nrmse_improvement": improvement,
        "teacher_run_artifacts": {key: str(value) for key, value in teacher_outputs.items()},
        "seed_run_artifacts": {key: str(value) for key, value in seed_outputs.items()},
        "top_k_executable_replays": replay_count,
        "candidate_ode_evaluations": candidate_ode_evaluations,
        "best_executable_run_artifacts": best_executable["run_artifacts"],
        "leaderboard": [
            {
                "family": result["family"],
                "teacher_flux_nrmse": result["teacher_flux_nrmse"],
                "teacher_flux_rmse": result["teacher_flux_rmse"],
                "executable": result["executable"],
                "candidate_params_path": result.get("candidate_params_path"),
            }
            for result in sorted(family_results, key=lambda item: item["teacher_flux_nrmse"])
        ],
        "best_teacher_flux_family": top_executable_by_teacher[0]["family"],
        "best_executable_family": best_executable["family"],
        "best_executable_candidate_params_path": str(best_candidate_params_path),
    }

    _save_json(out_root / "autoresearch_report.json", summary)
    _save_json(out_root / "family_results.json", {"families": family_results})
    _plot_flux_leaderboard(
        flux_time,
        teacher_flux,
        sorted(family_results, key=lambda item: item["teacher_flux_nrmse"]),
        out_root / "veglc_teacher_flux_leaderboard.png",
    )
    _plot_eglc_ode_compare(
        seed_outputs["metabolites"],
        Path(best_executable["run_artifacts"]["metabolites"]),
        out_root / "veglc_best_student_vs_seed.png",
    )

    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CPU-only mini-autoresearch loop for extracellular glucose transport")
    parser.add_argument("--seed-params", default=str(DEFAULT_SEED))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--budget-per-family-seconds", type=float, default=45.0)
    parser.add_argument("--rng-seed", type=int, default=29)
    parser.add_argument("--top-k-executable-replays", type=int, default=2)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    report = run_glucose_autoresearch(
        seed_params_path=Path(args.seed_params),
        out_root=Path(args.out_dir),
        budget_per_family_seconds=args.budget_per_family_seconds,
        rng_seed=args.rng_seed,
        top_k_executable_replays=args.top_k_executable_replays,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
