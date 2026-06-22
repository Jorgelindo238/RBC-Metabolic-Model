"""Compare Phase C warm-start seeding against default/no-ML calibration.

This is the first calibration-level gate after the Phase C warm-start scaffold.
It trains the offline warm-start model on deterministic synthetic cases, then
runs identical mini-calibrations on one or every held-out validation case:

* ``default_no_ml`` starts from default parameter values
* ``warmstart`` starts from the Phase C predicted parameter seed

Both branches use the same stage plan, optimizer seed, target data, and trial
budget. The aggregate mode requires warm-start superiority across held-out
cases before this work can graduate toward worker/API integration. The script
remains offline/experimental and does not touch production contracts.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
SCRIPTS_DIR = ROOT / "scripts"
DEFAULT_OUT_DIR = ROOT / "Simulations" / "auto_param_scope" / "phase_c_warmstart_compare"


def _configure_imports() -> None:
    for path in (str(ROOT), str(SRC_DIR), str(SCRIPTS_DIR)):
        if path not in sys.path:
            sys.path.insert(0, path)


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
    return value


def _read_report(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _loss_comparison(
    *,
    default_loss: float,
    warmstart_loss: float,
    min_relative_improvement: float,
) -> Dict[str, Any]:
    default_loss = float(default_loss)
    warmstart_loss = float(warmstart_loss)
    relative_improvement = (default_loss - warmstart_loss) / max(abs(default_loss), 1e-12)
    passed = bool(relative_improvement >= float(min_relative_improvement))
    return {
        "default_final_loss": default_loss,
        "warmstart_final_loss": warmstart_loss,
        "warmstart_minus_default_loss": warmstart_loss - default_loss,
        "relative_improvement": float(relative_improvement),
        "min_relative_improvement": float(min_relative_improvement),
        "decision_gate": "warmstart_beats_default" if passed else "needs_review",
        "passed": passed,
    }


def _phase_b_synthetic_dataset(
    *,
    params: Mapping[str, float],
    preset: str,
    t_max: float,
    timepoints: int,
    method: str,
    rtol: float,
    atol: float,
) -> Dict[str, Any]:
    import run_phase_b_flux_smoke as phase_b

    selected_metabolites, _inference_metabolites, _selected_reactions = phase_b._resolve_preset(preset)
    sol = phase_b._solve_model(
        t_max=float(t_max),
        timepoints=int(timepoints),
        params=dict(params),
        method=str(method),
        rtol=float(rtol),
        atol=float(atol),
    )
    if not sol.success:
        raise RuntimeError(f"ODE solve failed while building synthetic dataset: {sol.message}")

    time = np.asarray(sol.t, dtype=float)
    states = np.asarray(sol.y, dtype=float)
    curves = phase_b._model_curves(states, selected_metabolites)
    return {
        "metabolites": list(selected_metabolites),
        "time_points": time,
        "values": [curves[name] for name in selected_metabolites],
    }


def _build_stage_plan(
    *,
    target_params: Sequence[str],
    n_trials: int,
    seed: int,
    target_scope: str,
) -> Tuple[Dict[str, Any], ...]:
    return (
        {
            "name": "phase_c_seed_probe",
            "phases": [1],
            "param_scope": "all",
            "parameter_classes": ["vmax"],
            "include_params": list(target_params),
            "target_scope": str(target_scope),
            "n_trials": int(max(1, n_trials)),
            "global_trials": 0,
            "seed": int(seed),
        },
    )


def _run_calibration_branch(
    *,
    branch_name: str,
    seed_params: Mapping[str, float],
    target_params: Sequence[str],
    experimental_data: Mapping[str, Any],
    out_dir: Path,
    n_trials: int,
    t_max: float,
    seed: int,
    target_scope: str,
    target_metabolites: Sequence[str],
) -> Dict[str, Any]:
    import MM_calibration as mm

    branch_dir = Path(out_dir) / "branches" / branch_name
    branch_dir.mkdir(parents=True, exist_ok=True)
    seed_path = branch_dir / "seed_params.json"
    seed_path.write_text(json.dumps(_jsonable(dict(seed_params)), indent=2), encoding="utf-8")

    stage_plan = _build_stage_plan(
        target_params=target_params,
        n_trials=int(n_trials),
        seed=int(seed),
        target_scope=target_scope,
    )
    current_params, final_loss, _trajectory_csv_path = mm.run_calibration(
        phases=[1],
        n_trials=max(1, int(n_trials)),
        global_trials=0,
        load_params=str(seed_path),
        target_scope=str(target_scope),
        param_scope="all",
        generate_plots=False,
        seed=int(seed),
        t_max=float(t_max),
        curve_fit_strength=0.0,
        out_dir=branch_dir,
        optimization_strategy="legacy",
        stage_plan=list(stage_plan),
        target_metabolites=list(target_metabolites),
        experimental_data=experimental_data,
        research_data_mode="custom_user_data_mode",
        active_dataset_id=f"phase-c-warmstart-compare-{branch_name}",
        active_dataset_label=f"Phase C warm-start compare: {branch_name}",
    )
    report = _read_report(branch_dir / "calibration_report.json")
    optimized = {
        name: float(current_params.get(name, seed_params.get(name, 0.0)))
        for name in target_params
    }
    return {
        "branch": branch_name,
        "seed_params": {name: float(seed_params[name]) for name in target_params},
        "optimized_params": optimized,
        "baseline_loss": report.get("baseline_loss"),
        "final_loss": float(report.get("final_loss", final_loss)),
        "improvement_pct": report.get("improvement_pct"),
        "n_trials": int(n_trials),
        "stage_plan": stage_plan,
        "seed_params_path": str(seed_path),
        "report_path": str(branch_dir / "calibration_report.json"),
    }


def _train_warmstart_model(
    *,
    target_params: Sequence[str],
    profile: str,
    preset: str,
    t_max: float,
    timepoints: int,
    method: str,
    rtol: float,
    atol: float,
    regularization: float,
) -> Dict[str, Any]:
    import run_phase_c_warmstart_smoke as phase_c

    defaults, bounds = phase_c._param_defaults_and_bounds(target_params)
    train_factors, validation_factors = phase_c._case_profiles(len(target_params), profile)
    training_cases = [
        phase_c._build_case(
            case_id=f"train_{idx:02d}",
            factors=factors,
            target_params=target_params,
            defaults=defaults,
            bounds=bounds,
            preset=preset,
            t_max=t_max,
            timepoints=timepoints,
            method=method,
            rtol=rtol,
            atol=atol,
        )
        for idx, factors in enumerate(train_factors)
    ]
    x_train = np.vstack([np.asarray(case["feature_payload"]["values"], dtype=float) for case in training_cases])
    y_train = np.vstack([np.asarray(case["true_log_multipliers"], dtype=float) for case in training_cases])
    model = phase_c._fit_standardized_ridge(x_train, y_train, regularization=regularization)
    return {
        "model": model,
        "defaults": defaults,
        "bounds": bounds,
        "training_cases": training_cases,
        "validation_factors": validation_factors,
        "feature_payload": training_cases[0]["feature_payload"],
    }


def _predict_seed_for_case(
    *,
    model: Mapping[str, Any],
    feature_payload: Mapping[str, Any],
    target_params: Sequence[str],
    defaults: Mapping[str, float],
    bounds: Mapping[str, Tuple[float, float, float]],
) -> Dict[str, float]:
    import run_phase_c_warmstart_smoke as phase_c

    features = np.asarray(feature_payload["values"], dtype=float)
    predicted_log = phase_c._predict_log_multipliers(model, features)[0]
    return phase_c._params_from_prediction(predicted_log, target_params, defaults, bounds)


def _warmstart_seed_log_mae(
    *,
    warmstart_seed: Mapping[str, float],
    comparison_case: Mapping[str, Any],
    target_params: Sequence[str],
    defaults: Mapping[str, float],
) -> float:
    predicted_log = np.asarray(
        [
            math.log(float(warmstart_seed[name]) / float(defaults[name]))
            for name in target_params
        ],
        dtype=float,
    )
    true_log = np.asarray(comparison_case["true_log_multipliers"], dtype=float)
    return float(np.mean(np.abs(predicted_log - true_log)))


def _run_case_comparison(
    *,
    case_id: str,
    factor_index: int,
    factors: Sequence[float],
    trained: Mapping[str, Any],
    target_params: Sequence[str],
    preset: str,
    t_max: float,
    timepoints: int,
    method: str,
    rtol: float,
    atol: float,
    out_dir: Path,
    n_trials: int,
    seed: int,
    target_scope: str,
    min_relative_improvement: float,
) -> Dict[str, Any]:
    import run_phase_c_warmstart_smoke as phase_c

    true_params = phase_c._params_from_factors(
        factors,
        target_params,
        trained["defaults"],
        trained["bounds"],
    )
    comparison_case = phase_c._build_case(
        case_id=case_id,
        factors=factors,
        target_params=target_params,
        defaults=trained["defaults"],
        bounds=trained["bounds"],
        preset=preset,
        t_max=t_max,
        timepoints=timepoints,
        method=method,
        rtol=rtol,
        atol=atol,
    )
    warmstart_seed = _predict_seed_for_case(
        model=trained["model"],
        feature_payload=comparison_case["feature_payload"],
        target_params=target_params,
        defaults=trained["defaults"],
        bounds=trained["bounds"],
    )
    default_seed = {name: float(trained["defaults"][name]) for name in target_params}
    experimental_data = _phase_b_synthetic_dataset(
        params=true_params,
        preset=preset,
        t_max=t_max,
        timepoints=timepoints,
        method=method,
        rtol=rtol,
        atol=atol,
    )

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    default_branch = _run_calibration_branch(
        branch_name="default_no_ml",
        seed_params=default_seed,
        target_params=target_params,
        experimental_data=experimental_data,
        out_dir=out_dir,
        n_trials=n_trials,
        t_max=t_max,
        seed=seed,
        target_scope=target_scope,
        target_metabolites=experimental_data["metabolites"],
    )
    warmstart_branch = _run_calibration_branch(
        branch_name="warmstart",
        seed_params=warmstart_seed,
        target_params=target_params,
        experimental_data=experimental_data,
        out_dir=out_dir,
        n_trials=n_trials,
        t_max=t_max,
        seed=seed,
        target_scope=target_scope,
        target_metabolites=experimental_data["metabolites"],
    )
    comparison = _loss_comparison(
        default_loss=float(default_branch["final_loss"]),
        warmstart_loss=float(warmstart_branch["final_loss"]),
        min_relative_improvement=float(min_relative_improvement),
    )
    return {
        "case_id": comparison_case["case_id"],
        "factor_index": int(factor_index),
        "factors": tuple(float(value) for value in factors),
        "true_params": true_params,
        "default_seed": default_seed,
        "warmstart_seed": warmstart_seed,
        "warmstart_seed_log_mae": _warmstart_seed_log_mae(
            warmstart_seed=warmstart_seed,
            comparison_case=comparison_case,
            target_params=target_params,
            defaults=trained["defaults"],
        ),
        "branches": {
            "default_no_ml": default_branch,
            "warmstart": warmstart_branch,
        },
        "comparison": comparison,
        "out_dir": str(out_dir),
    }


def _aggregate_case_comparisons(
    cases: Sequence[Mapping[str, Any]],
    *,
    min_case_win_rate: float,
    min_mean_relative_improvement: float,
) -> Dict[str, Any]:
    if not cases:
        raise ValueError("at least one case comparison is required.")

    improvements = np.asarray(
        [float(case["comparison"]["relative_improvement"]) for case in cases],
        dtype=float,
    )
    default_losses = np.asarray(
        [float(case["comparison"]["default_final_loss"]) for case in cases],
        dtype=float,
    )
    warmstart_losses = np.asarray(
        [float(case["comparison"]["warmstart_final_loss"]) for case in cases],
        dtype=float,
    )
    passed_case_ids = [
        str(case["case_id"])
        for case in cases
        if bool(case["comparison"]["passed"])
    ]
    failed_case_ids = [
        str(case["case_id"])
        for case in cases
        if not bool(case["comparison"]["passed"])
    ]
    case_count = len(cases)
    passed_count = len(passed_case_ids)
    win_rate = passed_count / max(case_count, 1)
    mean_relative_improvement = float(np.mean(improvements))
    passed = (
        win_rate >= float(min_case_win_rate)
        and mean_relative_improvement >= float(min_mean_relative_improvement)
    )
    return {
        "case_count": case_count,
        "passed_case_count": passed_count,
        "failed_case_count": len(failed_case_ids),
        "passed_case_ids": passed_case_ids,
        "failed_case_ids": failed_case_ids,
        "win_rate": float(win_rate),
        "min_case_win_rate": float(min_case_win_rate),
        "mean_relative_improvement": mean_relative_improvement,
        "median_relative_improvement": float(np.median(improvements)),
        "min_relative_improvement_observed": float(np.min(improvements)),
        "max_relative_improvement_observed": float(np.max(improvements)),
        "min_mean_relative_improvement": float(min_mean_relative_improvement),
        "mean_default_final_loss": float(np.mean(default_losses)),
        "mean_warmstart_final_loss": float(np.mean(warmstart_losses)),
        "warmstart_minus_default_mean_loss": float(np.mean(warmstart_losses - default_losses)),
        "all_cases_passed": passed_count == case_count,
        "decision_gate": "aggregate_warmstart_beats_default" if passed else "needs_review",
        "passed": bool(passed),
    }


def run_warmstart_comparison(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    preset: str = "wide",
    profile: str = "smoke",
    target_params: Sequence[str] = ("vmax_VEGLC", "vmax_VELAC", "vmax_VLDH", "vmax_VHK"),
    comparison_case_index: int = 0,
    n_trials: int = 1,
    t_max: float = 2.0,
    timepoints: int = 8,
    method: str = "LSODA",
    rtol: float = 1e-5,
    atol: float = 1e-7,
    seed: int = 42,
    regularization: float = 1.0,
    target_scope: str = "glycolysis_extracellular",
    min_relative_improvement: float = 0.0,
    all_validation_cases: bool = False,
    min_case_win_rate: float = 1.0,
    min_mean_relative_improvement: float = 0.0,
) -> Dict[str, Any]:
    _configure_imports()

    import run_phase_c_warmstart_smoke as phase_c

    target_param_tuple = phase_c._normalize_names(target_params)
    trained = _train_warmstart_model(
        target_params=target_param_tuple,
        profile=profile,
        preset=preset,
        t_max=t_max,
        timepoints=timepoints,
        method=method,
        rtol=rtol,
        atol=atol,
        regularization=regularization,
    )
    validation_factors = tuple(trained["validation_factors"])
    if not validation_factors:
        raise ValueError("profile produced no validation factors.")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if all_validation_cases:
        selected_cases = tuple(enumerate(validation_factors))
    else:
        factor_index = int(comparison_case_index) % len(validation_factors)
        selected_cases = ((factor_index, validation_factors[factor_index]),)

    cases = []
    for factor_index, factors in selected_cases:
        case_id = f"comparison_{factor_index:02d}"
        case_out_dir = out_dir / "cases" / case_id if all_validation_cases else out_dir
        cases.append(
            _run_case_comparison(
                case_id=case_id,
                factor_index=factor_index,
                factors=factors,
                trained=trained,
                target_params=target_param_tuple,
                preset=preset,
                t_max=t_max,
                timepoints=timepoints,
                method=method,
                rtol=rtol,
                atol=atol,
                out_dir=case_out_dir,
                n_trials=n_trials,
                seed=seed,
                target_scope=target_scope,
                min_relative_improvement=min_relative_improvement,
            )
        )

    if all_validation_cases:
        comparison = _aggregate_case_comparisons(
            cases,
            min_case_win_rate=min_case_win_rate,
            min_mean_relative_improvement=min_mean_relative_improvement,
        )
    else:
        comparison = dict(cases[0]["comparison"])

    payload: Dict[str, Any] = {
        "contract_type": "phase_c_warmstart_calibration_compare_result",
        "contract_version": 2,
        "status": "passed" if comparison["passed"] else "failed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "feature_version": trained["feature_payload"]["feature_version"],
        "preset": str(preset).strip().lower(),
        "synthetic_profile": str(profile).strip().lower(),
        "settings": {
            "n_trials": int(n_trials),
            "t_max": float(t_max),
            "timepoints": int(timepoints),
            "method": str(method),
            "rtol": float(rtol),
            "atol": float(atol),
            "seed": int(seed),
            "regularization": float(regularization),
            "target_scope": str(target_scope),
            "all_validation_cases": bool(all_validation_cases),
            "comparison_case_index": int(comparison_case_index),
            "min_relative_improvement": float(min_relative_improvement),
            "min_case_win_rate": float(min_case_win_rate),
            "min_mean_relative_improvement": float(min_mean_relative_improvement),
        },
        "target_params": list(target_param_tuple),
        "model": {
            "kind": trained["model"]["kind"],
            "regularization": trained["model"]["regularization"],
            "training_case_count": len(trained["training_cases"]),
            "feature_count": int(trained["feature_payload"]["metadata"]["feature_count"]),
            "target_params": list(target_param_tuple),
        },
        "cases": cases,
        "comparison": comparison,
    }
    if not all_validation_cases:
        single_case = cases[0]
        payload["synthetic_case"] = {
            "case_id": single_case["case_id"],
            "factor_index": single_case["factor_index"],
            "factors": single_case["factors"],
            "true_params": single_case["true_params"],
            "default_seed": single_case["default_seed"],
            "warmstart_seed": single_case["warmstart_seed"],
            "warmstart_seed_log_mae": single_case["warmstart_seed_log_mae"],
        }
        payload["branches"] = single_case["branches"]

    result_path = out_dir / "result.json"
    payload["out_path"] = str(result_path)
    result_path.write_text(json.dumps(_jsonable(payload), indent=2), encoding="utf-8")
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare Phase C warm-start vs default calibration.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--preset", default="wide")
    parser.add_argument("--profile", choices=("micro", "smoke"), default="smoke")
    parser.add_argument("--target-param", action="append", default=[])
    parser.add_argument("--comparison-case-index", type=int, default=0)
    parser.add_argument("--n-trials", type=int, default=1)
    parser.add_argument("--t-max", type=float, default=2.0)
    parser.add_argument("--timepoints", type=int, default=8)
    parser.add_argument("--method", default="LSODA")
    parser.add_argument("--rtol", type=float, default=1e-5)
    parser.add_argument("--atol", type=float, default=1e-7)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--regularization", type=float, default=1.0)
    parser.add_argument("--target-scope", default="glycolysis_extracellular")
    parser.add_argument("--min-relative-improvement", type=float, default=0.0)
    parser.add_argument("--all-validation-cases", action="store_true")
    parser.add_argument("--min-case-win-rate", type=float, default=1.0)
    parser.add_argument("--min-mean-relative-improvement", type=float, default=0.0)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    target_params = tuple(args.target_param) if args.target_param else (
        "vmax_VEGLC",
        "vmax_VELAC",
        "vmax_VLDH",
        "vmax_VHK",
    )
    payload = run_warmstart_comparison(
        out_dir=args.out_dir,
        preset=args.preset,
        profile=args.profile,
        target_params=target_params,
        comparison_case_index=args.comparison_case_index,
        n_trials=args.n_trials,
        t_max=args.t_max,
        timepoints=args.timepoints,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
        seed=args.seed,
        regularization=args.regularization,
        target_scope=args.target_scope,
        min_relative_improvement=args.min_relative_improvement,
        all_validation_cases=args.all_validation_cases,
        min_case_win_rate=args.min_case_win_rate,
        min_mean_relative_improvement=args.min_mean_relative_improvement,
    )
    comparison = payload["comparison"]
    summary = {
        "status": payload["status"],
        "out_path": payload["out_path"],
        "feature_version": payload["feature_version"],
        "target_params": payload["target_params"],
        "decision_gate": comparison["decision_gate"],
    }
    if args.all_validation_cases:
        summary.update(
            {
                "case_count": comparison["case_count"],
                "passed_case_count": comparison["passed_case_count"],
                "win_rate": comparison["win_rate"],
                "mean_relative_improvement": comparison["mean_relative_improvement"],
                "mean_default_final_loss": comparison["mean_default_final_loss"],
                "mean_warmstart_final_loss": comparison["mean_warmstart_final_loss"],
            }
        )
    else:
        summary.update(
            {
                "default_final_loss": comparison["default_final_loss"],
                "warmstart_final_loss": comparison["warmstart_final_loss"],
                "relative_improvement": comparison["relative_improvement"],
            }
        )
    print(json.dumps(_jsonable(summary), indent=2))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
