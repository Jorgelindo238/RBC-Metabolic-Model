"""Thin adapter from the web calibration route to the canonical MM calibration core."""

from __future__ import annotations

from copy import deepcopy
import json
import logging
from functools import lru_cache
import tempfile
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import HTTPException

import MM_calibration as mm
from services.pure_ode_runtime import run_pure_ode_rerun

def _load_robocop_modules():
    """Load the top-level ``services/robocop`` planner + triage modules.

    The FastAPI app registers ``apps/api/`` on ``sys.path`` before the project
    root, so the import name ``services`` resolves to ``apps/api/services/``
    (this file's own package). That shadows the project-root ``services/``
    namespace where ``robocop/`` actually lives. Rather than mutate
    ``sys.path`` globally — which would break ``services.openai_service`` used
    elsewhere in this app — we resolve the two modules by absolute path via
    ``importlib``. The loaded modules are registered under alternate names in
    ``sys.modules`` so their ``from services.robocop.custom_dataset_planner``
    import works inside ``curve_triage.py``.
    """

    import importlib.util
    import sys

    project_root = Path(__file__).resolve().parents[3]
    planner_path = project_root / "services" / "robocop" / "custom_dataset_planner.py"
    triage_path = project_root / "services" / "robocop" / "curve_triage.py"
    pure_ode_triage_path = project_root / "services" / "robocop" / "pure_ode_triage.py"
    if not planner_path.exists() or not triage_path.exists() or not pure_ode_triage_path.exists():
        return None

    def _load(module_name: str, file_path: Path):
        spec = importlib.util.spec_from_file_location(module_name, str(file_path))
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to build spec for {file_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    planner_alias = "robocop_tools.custom_dataset_planner"
    triage_alias = "robocop_tools.curve_triage"

    # Expose the planner under the name the triage module imports from it.
    planner_module = _load(planner_alias, planner_path)
    sys.modules["services.robocop.custom_dataset_planner"] = planner_module
    triage_module = _load(triage_alias, triage_path)
    sys.modules["services.robocop.curve_triage"] = triage_module

    pure_ode_triage_alias = "robocop_tools.pure_ode_triage"
    pure_ode_triage_module = _load(pure_ode_triage_alias, pure_ode_triage_path)
    sys.modules["services.robocop.pure_ode_triage"] = pure_ode_triage_module

    return planner_module, triage_module, pure_ode_triage_module


try:
    _planner_module, _triage_module, _pure_ode_triage_module = _load_robocop_modules() or (None, None, None)
    if _planner_module is None or _triage_module is None or _pure_ode_triage_module is None:
        raise ImportError("robocop planner / triage modules could not be located")
    CustomDataPlan = getattr(_planner_module, "CustomDataPlan")
    build_custom_data_plan = getattr(_planner_module, "build_custom_data_plan")
    TriageVerdict = getattr(_triage_module, "TriageVerdict")
    skipped_triage = getattr(_triage_module, "skipped_triage")
    triage_calibration_report = getattr(_triage_module, "triage_calibration_report")
    skipped_pure_ode_triage = getattr(_pure_ode_triage_module, "skipped_pure_ode_triage")
    triage_pure_ode_csv = getattr(_pure_ode_triage_module, "triage_pure_ode_csv")
    combine_triage_verdicts = getattr(_pure_ode_triage_module, "combine_triage_verdicts")
    _ROBOCOP_PLANNER_AVAILABLE = True
    _ROBOCOP_IMPORT_ERROR = ""
except Exception:  # pragma: no cover - defensive fallback
    CustomDataPlan = None  # type: ignore[assignment]
    TriageVerdict = None  # type: ignore[assignment]
    build_custom_data_plan = None  # type: ignore[assignment]
    skipped_triage = None  # type: ignore[assignment]
    triage_calibration_report = None  # type: ignore[assignment]
    skipped_pure_ode_triage = None  # type: ignore[assignment]
    triage_pure_ode_csv = None  # type: ignore[assignment]
    combine_triage_verdicts = None  # type: ignore[assignment]
    _ROBOCOP_PLANNER_AVAILABLE = False
    _ROBOCOP_IMPORT_ERROR = traceback.format_exc()

_logger = logging.getLogger(__name__)
if not _ROBOCOP_PLANNER_AVAILABLE:
    _logger.warning(
        "RoBoCop calibration planner/triage unavailable; falling back to legacy "
        "MM profile. Import error:\n%s",
        _ROBOCOP_IMPORT_ERROR,
    )

DEFAULT_WEB_OPTIMIZATION_STRATEGY = "vmax_then_km"
STRATEGY_LABELS = {
    "legacy": "Legacy compatibility",
    "vmax_only": "Vmax only",
    "km_only": "Km only",
    "core_km_then_purine_transport": "Core Km then purine transport",
    "vmax_then_km": "Vmax then Km",
    "km_then_vmax": "Km then Vmax",
    "joint_vmax_km": "Joint Vmax + Km",
    "staged_full": "Staged full",
}
STRATEGY_DESCRIPTIONS = {
    "legacy": "Single-stage compatibility mode for manual selections.",
    "vmax_only": "Optimize only the selected Vmax parameters.",
    "km_only": "Optimize only the selected Km parameters.",
    "core_km_then_purine_transport": "Anchor core Km parameters, then refine purine transport.",
    "vmax_then_km": "Recommended default for monitoring-aligned custom data: optimize selected Vmax parameters first, then selected Km parameters.",
    "km_then_vmax": "Optimize selected Km parameters first, then selected Vmax parameters.",
    "joint_vmax_km": "Optimize the selected Vmax and Km parameters together.",
    "staged_full": "Multi-stage calibration across the canonical core and caution tiers.",
}


def _to_native(obj: Any):
    """Recursively convert numpy values to JSON-safe Python native types."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_native(i) for i in obj]
    return obj


def _normalize_names(names: List[str]) -> List[str]:
    if names is None:
        return []
    return [str(name).strip() for name in names if str(name).strip()]


def _build_experimental_payload(request) -> dict:
    metabolite_names = _normalize_names(list(request.exp_data.keys()))
    values = [request.exp_data[name] for name in request.exp_data.keys()]
    return {
        "metabolites": metabolite_names,
        "time_points": list(request.exp_time),
        "values": values,
    }


def _build_initial_params(request) -> Dict[str, float]:
    params: Dict[str, float] = {}
    if request.base_params:
        params.update({str(name): float(value) for name, value in request.base_params.items()})
    for name, bounds in request.params_to_optimize.items():
        if bounds:
            params[str(name)] = float(bounds[0])
    return params


def _strategy_label(value: str) -> str:
    return STRATEGY_LABELS.get(value, value.replace("_", " ").title())


def _strategy_description(value: str) -> str:
    return STRATEGY_DESCRIPTIONS.get(value, "")


def _build_strategy_choices() -> list[dict]:
    ordered_values = [
        DEFAULT_WEB_OPTIMIZATION_STRATEGY,
        *sorted(
            value
            for value in mm.OPTIMIZATION_STRATEGY_CHOICES
            if value != DEFAULT_WEB_OPTIMIZATION_STRATEGY
        ),
    ]
    return [
        {
            "value": value,
            "label": _strategy_label(value),
            "description": _strategy_description(value),
            "recommended": value == DEFAULT_WEB_OPTIMIZATION_STRATEGY,
        }
        for value in ordered_values
    ]


def _resolve_requested_strategy(request) -> str:
    candidate = (
        getattr(request, "optimization_strategy", None)
        or getattr(request, "method", None)
        or DEFAULT_WEB_OPTIMIZATION_STRATEGY
    )
    if candidate in mm.OPTIMIZATION_STRATEGY_CHOICES:
        return candidate
    if candidate in {"differential_evolution", "minimize", "least_squares"}:
        return "legacy"
    return DEFAULT_WEB_OPTIMIZATION_STRATEGY if candidate == "joint_vmax_km" else "legacy"


def _stage_selection_matches(stage: dict, param_name: str) -> bool:
    include_params = set(_normalize_names(stage.get("include_params")) or [])
    exclude_params = set(_normalize_names(stage.get("exclude_params")) or [])
    allowed_classes = set(_normalize_names(stage.get("parameter_classes")) or [])
    allowed_ident = set(_normalize_names(stage.get("identifiability_levels")) or [])

    if param_name in exclude_params:
        return False
    if include_params and param_name not in include_params:
        return False
    if allowed_classes and not (set(mm.get_parameter_classes(param_name)) & allowed_classes):
        return False
    if allowed_ident and mm.get_parameter_identifiability(param_name) not in allowed_ident:
        return False
    return True


def _build_strategy_stage_plan(
    selected_params: List[str],
    optimization_strategy: str,
    max_iterations: int,
) -> List[dict]:
    selected_params = [name for name in selected_params if name]
    if not selected_params:
        raise HTTPException(status_code=400, detail="Select at least one parameter to optimise.")

    if optimization_strategy == "legacy":
        return [
            {
                "name": "legacy",
                "phases": [1, 2, 3],
                "param_scope": "all",
                "target_scope": "all",
                "include_params": selected_params,
                "exclude_params": None,
                "n_trials": max(1, max_iterations),
                "global_trials": 0,
                "seed": 42,
                "atp_focus": False,
                "atp_floor": 0.15,
                "adp_floor": 0.05,
                "amp_floor": 0.04,
                "imp_floor": 0.02,
                "adenylate_target": 0.65,
                "atp_penalty_weight": 10.0,
                "amp_penalty_weight": 6.0,
                "imp_penalty_weight": 5.0,
                "pool_penalty_weight": 12.0,
                "curve_fit_strength": 0.0,
            }
        ]

    raw_template = mm.OPTIMIZATION_STRATEGY_TEMPLATES.get(optimization_strategy)
    if raw_template is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported optimization strategy requested: {optimization_strategy}",
        )

    resolved_stages: List[dict] = []
    for raw_stage in raw_template:
        stage = deepcopy(raw_stage)
        stage_selected = [name for name in selected_params if _stage_selection_matches(stage, name)]
        if not stage_selected:
            continue
        stage["include_params"] = stage_selected
        stage["exclude_params"] = None
        stage["n_trials"] = 1
        stage["global_trials"] = 0
        stage.setdefault("seed", 42)
        resolved_stages.append(stage)

    if not resolved_stages:
        raise HTTPException(
            status_code=400,
            detail=(
                "The selected parameters do not overlap with the chosen optimization strategy."
            ),
        )

    per_stage_trials = max(1, max_iterations // len(resolved_stages))
    for stage in resolved_stages:
        stage["n_trials"] = per_stage_trials

    return resolved_stages


@lru_cache(maxsize=1)
def _build_parameter_inventory() -> dict:
    taxonomy = mm.build_parameter_taxonomy()
    canonical_names = set(taxonomy["classes"].get(mm.PARAM_CLASS_VMAX, [])) | set(
        taxonomy["classes"].get(mm.PARAM_CLASS_KM, [])
    )
    recommended_names = {
        name
        for name in mm.IDENTIFIABLE_CORE_PARAM_NAMES
        if name in canonical_names and (
            name.startswith("vmax_") or name.startswith("km_")
        )
    }

    entries: Dict[str, Dict[str, Any]] = {}
    for phase_num, phase_params in mm.PHASE_MAP.items():
      for name, (default, lower, upper) in phase_params.items():
            if name not in canonical_names:
                continue
            entry = entries.setdefault(
                name,
                {
                    "name": name,
                    "default_value": float(mm.DEFAULT_PARAM_VALUES.get(name, default)),
                    "classes": sorted(mm.get_parameter_classes(name)),
                    "identifiability": mm.get_parameter_identifiability(name),
                    "phase_bounds": [],
                    "recommended": name in recommended_names,
                },
            )
            entry["phase_bounds"].append(
                {
                    "phase": int(phase_num),
                    "default_value": float(default),
                    "lower_bound": float(lower),
                    "upper_bound": float(upper),
                }
            )

    for entry in entries.values():
        entry["phase_bounds"].sort(key=lambda item: item["phase"])
        if entry["phase_bounds"]:
            suggested = entry["phase_bounds"][0]
            entry["suggested_bounds"] = {
                "default_value": suggested["default_value"],
                "lower_bound": suggested["lower_bound"],
                "upper_bound": suggested["upper_bound"],
            }
        else:
            entry["suggested_bounds"] = {
                "default_value": entry["default_value"],
                "lower_bound": entry["default_value"],
                "upper_bound": entry["default_value"],
            }

    canonical_vmax = sorted(
        [entries[name] for name in taxonomy["classes"].get(mm.PARAM_CLASS_VMAX, []) if name in entries],
        key=lambda item: item["name"],
    )
    canonical_km = sorted(
        [entries[name] for name in taxonomy["classes"].get(mm.PARAM_CLASS_KM, []) if name in entries],
        key=lambda item: item["name"],
    )
    recommended_vmax = [entry["name"] for entry in canonical_vmax if entry["recommended"]]
    recommended_km = [entry["name"] for entry in canonical_km if entry["recommended"]]

    grouped_by_identifiability = {
        "vmax": {
            mm.IDENTIFIABLE_CORE: [entry["name"] for entry in canonical_vmax if entry["identifiability"] == mm.IDENTIFIABLE_CORE],
            mm.IDENTIFIABLE_CAUTION: [entry["name"] for entry in canonical_vmax if entry["identifiability"] == mm.IDENTIFIABLE_CAUTION],
            mm.STRUCTURAL_COMPENSATION_RISK: [entry["name"] for entry in canonical_vmax if entry["identifiability"] == mm.STRUCTURAL_COMPENSATION_RISK],
        },
        "km": {
            mm.IDENTIFIABLE_CORE: [entry["name"] for entry in canonical_km if entry["identifiability"] == mm.IDENTIFIABLE_CORE],
            mm.IDENTIFIABLE_CAUTION: [entry["name"] for entry in canonical_km if entry["identifiability"] == mm.IDENTIFIABLE_CAUTION],
            mm.STRUCTURAL_COMPENSATION_RISK: [entry["name"] for entry in canonical_km if entry["identifiability"] == mm.STRUCTURAL_COMPENSATION_RISK],
        },
    }

    return _to_native(
        {
            "source": "MM_calibration",
            "taxonomy_version": "mm_calibration_v1",
            "recommended": {
                "vmax_params": recommended_vmax,
                "km_params": recommended_km,
            },
            "strategy_choices": _build_strategy_choices(),
            "strategy_default": DEFAULT_WEB_OPTIMIZATION_STRATEGY,
            "canonical": {
                "vmax": canonical_vmax,
                "km": canonical_km,
            },
            "grouped_by_identifiability": grouped_by_identifiability,
            "class_counts": {name: len(values) for name, values in taxonomy["classes"].items()},
            "identifiability_counts": {
                name: len(values) for name, values in taxonomy["identifiability"].items()
            },
            "optimization_strategy_choices": sorted(mm.OPTIMIZATION_STRATEGY_CHOICES),
            "vmax_params": recommended_vmax,
            "km_params": recommended_km,
            "metabolite_names": sorted(mm.BRODBAR_METABOLITE_MAP.keys()),
        }
    )


def get_web_calibration_taxonomy() -> dict:
    return _build_parameter_inventory()


def _compute_r_squared(
    *,
    experimental_payload: dict,
    target_metabolites: List[str],
    params: Dict[str, float],
    t_max: float,
) -> float:
    time_exp, exp_values, name_to_row = mm.load_experimental_data(experimental_payload)
    x0 = mm.load_initial_conditions()
    objective = mm.build_objective(
        x0,
        time_exp,
        exp_values,
        name_to_row,
        t_max=t_max,
        target_scope="all",
        target_names=target_metabolites,
    )
    sol = objective._cached_solve(params, mode="report")
    if not sol.success:
        return 0.0

    y = np.maximum(sol.y, 0.0)
    predicted = y[objective.target_indices][:, objective.report_exp_indices]
    observed = objective.target_exp
    if predicted.size == 0 or observed.size == 0:
        return 0.0

    ss_res = float(np.sum((observed - predicted) ** 2))
    ss_tot = float(np.sum((observed - float(np.mean(observed))) ** 2))
    if ss_tot <= 1e-12:
        return 1.0

    return float(max(-1.0, min(1.0, 1.0 - (ss_res / ss_tot))))


def _build_custom_data_plan_safely(
    *,
    measured_metabolites: List[str],
    user_selected_params: List[str],
    requested_strategy: Optional[str],
    profile_additions_candidates: List[str],
):
    """Run the dataset-aware planner and return ``(plan_dict, plan_obj)``.

    Returns ``(None, None)`` if the planner is unavailable or raises — the
    legacy ``infer_custom_data_calibration_profile`` flow then takes over.
    """

    if not _ROBOCOP_PLANNER_AVAILABLE:
        return None, None
    try:
        plan = build_custom_data_plan(
            measured_metabolites=measured_metabolites,
            selected_params=user_selected_params,
            requested_strategy=requested_strategy,
            mm_inferred_additions=profile_additions_candidates or None,
        )
    except Exception:  # pragma: no cover - defensive fallback
        _logger.exception("custom_dataset_planner.build_custom_data_plan failed")
        return None, None
    try:
        return plan.to_dict(), plan
    except Exception:  # pragma: no cover - defensive fallback
        _logger.exception("custom_dataset_planner.to_dict failed")
        return None, plan


def _triage_report_safely(
    report_payload: Dict[str, Any],
    *,
    measured_metabolites: List[str],
    user_selected_params: List[str],
):
    """Run programmatic curve triage. Never raises up the call stack."""

    if not _ROBOCOP_PLANNER_AVAILABLE:
        return None
    try:
        verdict = triage_calibration_report(
            report_payload,
            measured_metabolites=measured_metabolites,
            optimized_params=user_selected_params,
        )
        return verdict.to_dict()
    except Exception:  # pragma: no cover - defensive fallback
        _logger.exception("curve_triage.triage_calibration_report failed")
        try:
            return skipped_triage("triage raised unexpectedly").to_dict()
        except Exception:
            return None


def _build_pure_ode_triage_safely(
    *,
    request: Any,
    params: Dict[str, float],
    output_dir: Path,
) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, str | None]]]:
    """Run an isolated pure-ODE replay and score it via the RoBoCop triage."""

    if not _ROBOCOP_PLANNER_AVAILABLE:
        return None, None
    try:
        if not bool(getattr(request, "rerun_pure_ode", False)):
            return (
                skipped_pure_ode_triage(
                    "Pure ODE rerun was disabled for this calibration request. "
                    "Set rerun_pure_ode=true to score the calibrated candidate."
                ).to_dict(),
                None,
            )

        rerun_payload = run_pure_ode_rerun(
            request=request,
            custom_params=params,
            output_dir=output_dir,
        )
        if not rerun_payload.get("success"):
            return (
                skipped_pure_ode_triage(
                    "Pure ODE rerun failed for this calibration candidate: "
                    + str(rerun_payload.get("error") or "unknown error")
                ).to_dict(),
                None,
            )

        artifacts = rerun_payload.get("artifacts") or {}
        metabolites_csv = artifacts.get("all_metabolites_csv")
        if not metabolites_csv:
            return (
                skipped_pure_ode_triage(
                    "Pure ODE rerun completed, but all_metabolites.csv was not produced."
                ).to_dict(),
                _to_native(artifacts),
            )
        verdict = triage_pure_ode_csv(metabolites_csv).to_dict()
        return verdict, _to_native(artifacts)
    except Exception:  # pragma: no cover - defensive fallback
        _logger.exception("pure_ode_triage replay failed")
        try:
            return (
                skipped_pure_ode_triage("pure_ode_triage replay raised unexpectedly").to_dict(),
                None,
            )
        except Exception:
            return None, None


def _build_combined_triage_safely(
    calibration_triage: Optional[Dict[str, Any]],
    pure_ode_triage: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Combine curve-triage + pure-ODE triage once a real pure-ODE verdict exists."""

    if not _ROBOCOP_PLANNER_AVAILABLE or calibration_triage is None or pure_ode_triage is None:
        return None
    if bool(pure_ode_triage.get("skipped")):
        return None
    try:
        return combine_triage_verdicts(calibration_triage, pure_ode_triage).to_dict()
    except Exception:  # pragma: no cover - defensive fallback
        _logger.exception("pure_ode_triage.combine_triage_verdicts failed")
        return None


def _run_single_web_calibration(request) -> dict:
    user_selected_params = list(request.params_to_optimize.keys())
    selected_params = list(user_selected_params)
    allowed_params = set(mm.build_parameter_taxonomy()["classes"].get(mm.PARAM_CLASS_VMAX, [])) | set(
        mm.build_parameter_taxonomy()["classes"].get(mm.PARAM_CLASS_KM, [])
    )
    unknown_params = [name for name in selected_params if name not in allowed_params]
    if unknown_params:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported calibration parameters requested: "
                + ", ".join(sorted(unknown_params))
            ),
        )

    target_metabolites = _normalize_names(request.target_metabolites) or _normalize_names(list(request.exp_data.keys()))
    experimental_payload = _build_experimental_payload(request)
    initial_params = _build_initial_params(request)
    calibration_profile = mm.infer_custom_data_calibration_profile(target_metabolites)
    explicit_strategy = getattr(request, "optimization_strategy", None) or getattr(request, "method", None)
    profile_addition_candidates = [
        name
        for name in calibration_profile.get("parameter_additions", [])
        if name not in selected_params
    ]

    # Phase 1: dataset-aware plan. Guarded so any planner bug never breaks calibration.
    custom_data_plan_dict, custom_data_plan_obj = _build_custom_data_plan_safely(
        measured_metabolites=target_metabolites,
        user_selected_params=user_selected_params,
        requested_strategy=explicit_strategy,
        profile_additions_candidates=profile_addition_candidates,
    )

    if custom_data_plan_obj is not None:
        planner_additions = [
            name
            for name in custom_data_plan_obj.parameter_additions
            if name in profile_addition_candidates
        ]
        profile_additions = planner_additions
    else:
        profile_additions = profile_addition_candidates

    if profile_additions:
        selected_params = list(dict.fromkeys(selected_params + profile_additions))

    optimization_strategy = _resolve_requested_strategy(request)
    if explicit_strategy is None:
        if custom_data_plan_obj is not None:
            optimization_strategy = custom_data_plan_obj.recommended_strategy
        else:
            optimization_strategy = calibration_profile["optimization_strategy"]

    if custom_data_plan_obj is not None and explicit_strategy is None:
        target_scope = custom_data_plan_obj.target_scope
        atp_focus = bool(custom_data_plan_obj.atp_focus)
    else:
        target_scope = calibration_profile["target_scope"]
        atp_focus = bool(calibration_profile["atp_focus"])
    atp_floor = float(calibration_profile["atp_floor"])
    adp_floor = float(calibration_profile["adp_floor"])
    amp_floor = float(calibration_profile["amp_floor"])
    imp_floor = float(calibration_profile["imp_floor"])
    adenylate_target = float(calibration_profile["adenylate_target"])
    atp_penalty_weight = float(calibration_profile["atp_penalty_weight"])
    amp_penalty_weight = float(calibration_profile["amp_penalty_weight"])
    imp_penalty_weight = float(calibration_profile["imp_penalty_weight"])
    pool_penalty_weight = float(calibration_profile["pool_penalty_weight"])
    curve_fit_strength = float(calibration_profile["curve_fit_strength"])
    research_data_mode = (
        getattr(request, "research_data_mode", None)
        or (
            "custom_user_data_mode"
            if getattr(request, "active_dataset_id", None)
            and getattr(request, "active_dataset_id", None) != "bordbar-reference"
            else "default_bordbar_mode"
        )
    )
    active_dataset_id = getattr(request, "active_dataset_id", None)
    active_dataset_label = getattr(request, "active_dataset_label", None)

    with tempfile.TemporaryDirectory(prefix="mm_web_calibration_") as tmp_dir:
        out_dir = Path(tmp_dir)
        load_params_path = None
        if initial_params:
            load_params_path = out_dir / "load_params.json"
            load_params_path.write_text(json.dumps(initial_params, indent=2), encoding="utf-8")

        try:
            current_params, final_loss = mm.run_calibration(
                phases=[1, 2, 3],
                n_trials=max(1, request.max_iterations),
                global_trials=0,
                load_params=str(load_params_path) if load_params_path is not None else None,
                target_scope=target_scope,
                param_scope="all",
                generate_plots=False,
                seed=42,
                t_max=request.t_max,
                atp_focus=atp_focus,
                atp_floor=atp_floor,
                adp_floor=adp_floor,
                amp_floor=amp_floor,
                imp_floor=imp_floor,
                adenylate_target=adenylate_target,
                atp_penalty_weight=atp_penalty_weight,
                amp_penalty_weight=amp_penalty_weight,
                imp_penalty_weight=imp_penalty_weight,
                pool_penalty_weight=pool_penalty_weight,
                curve_fit_strength=curve_fit_strength,
                out_dir=out_dir,
                optimization_strategy=optimization_strategy,
                stage_plan=_build_strategy_stage_plan(
                    selected_params,
                    optimization_strategy,
                    request.max_iterations,
                ),
                target_metabolites=target_metabolites,
                experimental_data=experimental_payload,
                research_data_mode=research_data_mode,
                active_dataset_id=active_dataset_id,
                active_dataset_label=active_dataset_label,
            )
        except Exception:
            traceback.print_exc()
            raise

        report_path = out_dir / "calibration_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))

        # Phase 2: programmatic curve triage. Guarded so any triage bug never
        # breaks the happy path of returning the calibration result.
        triage_verdict = _triage_report_safely(
            report,
            measured_metabolites=target_metabolites,
            user_selected_params=user_selected_params,
        )
        pure_ode_triage_verdict, pure_ode_artifacts = _build_pure_ode_triage_safely(
            request=request,
            params=current_params,
            output_dir=out_dir / "pure_ode_rerun",
        )
        combined_triage_verdict = _build_combined_triage_safely(
            triage_verdict,
            pure_ode_triage_verdict,
        )

        phase_elapsed_seconds = []
        for phase in (report.get("phases") or {}).values():
            if isinstance(phase, dict):
                elapsed_s = phase.get("elapsed_s")
                if isinstance(elapsed_s, (int, float)):
                    phase_elapsed_seconds.append(float(elapsed_s))
        run_duration_seconds = max(phase_elapsed_seconds) if phase_elapsed_seconds else None

        filtered_optimized = {
            name: float(current_params.get(name, initial_params.get(name, 0.0)))
            for name in selected_params
        }
        filtered_initial = {
            name: float(initial_params.get(name, filtered_optimized.get(name, 0.0)))
            for name in selected_params
        }
        r_squared = _compute_r_squared(
            experimental_payload=experimental_payload,
            target_metabolites=target_metabolites,
            params=current_params,
            t_max=request.t_max,
        )

        improvement_pct = float(report.get("improvement_pct", 0.0))
        baseline_loss = report.get("baseline_loss")
        final_loss = float(report.get("final_loss", final_loss))
        result_summary = (
            f"Completed calibration on {_strategy_label(optimization_strategy)}"
            f" with R² {r_squared:.3f}, improvement {improvement_pct:.1f}%"
            + (f", baseline loss {float(baseline_loss):.4f}" if isinstance(baseline_loss, (int, float)) else "")
            + f", final loss {final_loss:.4f}."
        )
        message = (
            f"MM_calibration complete on "
            f"{'custom user data' if report.get('data_mode') == 'custom_user_data_mode' else 'Bordbar reference'}"
            f" using {_strategy_label(optimization_strategy)}"
            f": final loss {final_loss:.4f}, "
            f"improvement {improvement_pct:.1f}%."
        )

        return _to_native(
            {
                "success": True,
                "message": message,
                "optimization_strategy": optimization_strategy,
                "optimized_params": filtered_optimized,
                "all_optimized_params": {str(name): float(value) for name, value in current_params.items()},
                "initial_params": filtered_initial,
                "objective_value": final_loss,
                "iterations": int(request.max_iterations),
                "r_squared": r_squared,
                "confidence_intervals": {},
                "sensitivity": {},
                "baseline_loss": float(baseline_loss) if isinstance(baseline_loss, (int, float)) else None,
                "final_loss": final_loss,
                "improvement_pct": improvement_pct,
                "run_duration_seconds": run_duration_seconds,
                "calibration_profile": calibration_profile["profile_name"],
                "calibration_profile_rationale": calibration_profile["rationale"],
                "calibration_profile_signals": calibration_profile["signals"],
                "calibration_profile_parameter_additions": profile_additions,
                "calibration_status": "completed",
                "calibration_completed": True,
                "calibration_failed": False,
                "result_summary": result_summary,
                "research_data_mode": research_data_mode,
                "active_dataset_id": active_dataset_id,
                "active_dataset_label": active_dataset_label,
                "custom_data_plan": custom_data_plan_dict,
                "triage": triage_verdict,
                "pure_ode_triage": pure_ode_triage_verdict,
                "pure_ode_artifacts": pure_ode_artifacts,
                "combined_triage": combined_triage_verdict,
            }
        )


def run_web_calibration(request, *, allow_orchestration: bool = True) -> dict:
    orchestration_mode = str(getattr(request, "orchestration_mode", "single_run") or "single_run").strip().lower()
    if allow_orchestration and orchestration_mode == "strategy_race":
        from services.custom_calibration_orchestrator import run_strategy_race_calibration

        return run_strategy_race_calibration(
            request,
            single_run_callable=_run_single_web_calibration,
        )
    return _run_single_web_calibration(request)
