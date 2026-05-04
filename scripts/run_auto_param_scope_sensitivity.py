"""Phase A auto-param-scope sensitivity probe.

This harness runs after the Phase 0 parity gate is green. It estimates local
one-at-a-time sensitivity for the broad auto-scope parameter set and writes a
compact artifact:

    Simulations/auto_param_scope/sensitivity_v1/result.json

Two baseline modes are supported:

* ``auto-defaults``: fast smoke path, probes around auto-scope initial values.
* ``calibrate``: Hetzner/full path, first regenerates a gated auto-scope
  calibration baseline, then probes around the optimized parameter set.

The probe is intentionally deterministic and conservative. Low-effect
parameters are recommended for pruning; dangerous parameters are retained but
flagged for guarded/staged handling.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import traceback
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
SRC_DIR = ROOT / "src"
API_DIR = ROOT / "apps" / "api"
DEFAULT_OUT_DIR = ROOT / "Simulations" / "auto_param_scope" / "sensitivity_v1"
DEFAULT_EGLC_MIN_DEPLETION_FRAC = 0.05
DEFAULT_PROTECTED_METRICS = (
    "target",
    "glycolysis_energy",
    "nucleotide_purine",
    "amino_redox_side",
    "extracellular",
    "glycolysis",
    "endpoint_nrmse",
    "eglc_depletion_frac",
    "initial_EGLC",
    "final_EGLC",
    "final_ELAC",
    "final_ATP",
    "final_ADP",
    "final_AMP",
    "final_LAC",
)


def _configure_imports() -> None:
    for path in (str(ROOT), str(SCRIPT_DIR), str(SRC_DIR), str(API_DIR)):
        if path not in sys.path:
            sys.path.insert(0, path)


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_params(path: Optional[Path]) -> Optional[Dict[str, float]]:
    if path is None:
        return None
    payload = _read_json(path)
    return {str(name): float(value) for name, value in payload.items()}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_to_jsonable(dict(payload)), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _normalize_names(values: Optional[Iterable[str]]) -> Optional[List[str]]:
    if values is None:
        return None
    out = []
    for value in values:
        name = str(value).strip()
        if name:
            out.append(name)
    return out


def _experimental_payload(
    target_metabolites: Sequence[str],
    exp_time: Sequence[float],
    exp_data: Mapping[str, Sequence[float]],
) -> Dict[str, Any]:
    names = [str(name).strip().upper() for name in target_metabolites]
    return {
        "metabolites": names,
        "time_points": [float(t) for t in exp_time],
        "values": [
            [float(v) for v in exp_data[name]]
            for name in names
            if name in exp_data
        ],
    }


def _metric_subset(metrics: Mapping[str, Any]) -> Dict[str, Optional[float]]:
    out: Dict[str, Optional[float]] = {}
    for key in DEFAULT_PROTECTED_METRICS:
        value = metrics.get(key)
        out[key] = float(value) if _is_number(value) else None
    return out


def _eglc_gate(metrics: Mapping[str, Any], min_depletion_frac: float) -> Dict[str, Any]:
    depletion = metrics.get("eglc_depletion_frac")
    initial = metrics.get("initial_EGLC")
    final = metrics.get("final_EGLC")
    if not _is_number(depletion):
        return {
            "state": "missing",
            "ok": None,
            "required_depletion_frac": float(min_depletion_frac),
            "depletion_frac": None,
            "initial_EGLC": float(initial) if _is_number(initial) else None,
            "final_EGLC": float(final) if _is_number(final) else None,
        }
    depletion_f = float(depletion)
    ok = depletion_f + 1e-12 >= float(min_depletion_frac)
    return {
        "state": "pass" if ok else "fail",
        "ok": ok,
        "required_depletion_frac": float(min_depletion_frac),
        "depletion_frac": depletion_f,
        "initial_EGLC": float(initial) if _is_number(initial) else None,
        "final_EGLC": float(final) if _is_number(final) else None,
    }


def _parameter_phase(mm: Any, param_name: str) -> Optional[int]:
    for phase_num, phase_params in mm.PHASE_MAP.items():
        if param_name in phase_params:
            return int(phase_num)
    return None


def _perturbation_values(
    baseline_value: float,
    lower_bound: float,
    upper_bound: float,
    *,
    step_frac: float,
) -> Dict[str, Dict[str, float]]:
    baseline = min(max(float(baseline_value), float(lower_bound)), float(upper_bound))
    span = float(upper_bound) - float(lower_bound)
    if span <= 0.0:
        return {}
    delta = abs(baseline) * float(step_frac)
    if delta <= 1e-12:
        delta = span * float(step_frac)
    out: Dict[str, Dict[str, float]] = {}
    for direction, raw_value in (
        ("down", baseline - delta),
        ("up", baseline + delta),
    ):
        value = min(max(raw_value, float(lower_bound)), float(upper_bound))
        if abs(value - baseline) <= 1e-12:
            continue
        out[direction] = {
            "value": value,
            "absolute_step": value - baseline,
            "relative_step": (value - baseline) / max(abs(baseline), 1e-12),
        }
    return out


def _classify_probe(
    *,
    baseline_loss: float,
    perturbations: Mapping[str, Mapping[str, Any]],
    low_effect_frac: float,
    high_effect_frac: float,
    danger_regression_frac: float,
) -> Tuple[str, str]:
    losses = [
        p.get("target_loss")
        for p in perturbations.values()
        if _is_number(p.get("target_loss"))
    ]
    if not losses:
        return "unstable_invalid_eval", "No finite perturbation loss was available."

    gate_failures = [
        name
        for name, p in perturbations.items()
        if (p.get("eglc_gate") or {}).get("state") == "fail"
    ]
    if gate_failures:
        return (
            "dangerous_eglc_gate_sensitive",
            "At least one perturbation violates the EGLC depletion gate.",
        )

    baseline = max(abs(float(baseline_loss)), 1e-12)
    deltas = [float(loss) - float(baseline_loss) for loss in losses]
    max_abs_delta = max(abs(delta) for delta in deltas)
    max_regression = max(0.0, max(deltas))
    effect_frac = max_abs_delta / baseline
    regression_frac = max_regression / baseline

    if regression_frac >= float(danger_regression_frac):
        return (
            "dangerous_loss_regression",
            f"At least one perturbation regresses target loss by {regression_frac:.2%}.",
        )
    if effect_frac <= float(low_effect_frac):
        return (
            "candidate_prune_low_sensitivity",
            f"Maximum local target-loss effect is only {effect_frac:.2%}.",
        )
    if effect_frac >= float(high_effect_frac):
        return (
            "keep_high_sensitivity",
            f"Maximum local target-loss effect is {effect_frac:.2%}.",
        )
    return (
        "keep_moderate_sensitivity",
        f"Maximum local target-loss effect is {effect_frac:.2%}.",
    )


def _recommendation_for_classification(classification: str) -> str:
    if classification == "candidate_prune_low_sensitivity":
        return "prune_candidate"
    if classification.startswith("dangerous_"):
        return "keep_guarded"
    if classification.startswith("unstable_"):
        return "review"
    return "keep"


@dataclass(frozen=True)
class Baseline:
    mode: str
    params: Dict[str, float]
    auto_scope_params: List[str]
    source: str
    calibration_payload: Optional[Dict[str, Any]] = None


def _build_baseline(
    *,
    mode: str,
    target_metabolites: Sequence[str],
    exp_time: Sequence[float],
    exp_data: Mapping[str, Sequence[float]],
    base_params: Optional[Dict[str, float]],
    t_max: float,
    baseline_n_trials: int,
) -> Baseline:
    import MM_calibration as mm

    if mode == "calibrate":
        import run_auto_param_scope_parity as parity

        dataset_label = "Auto-param-scope sensitivity baseline"
        payload = parity.run_branch(
            parity.BranchConfig("auto_scope", True),
            target_metabolites=target_metabolites,
            exp_time=exp_time,
            exp_data=exp_data,
            n_trials=max(1, int(baseline_n_trials)),
            t_max=float(t_max),
            rerun_pure_ode=False,
            base_params=base_params,
            dataset_id="auto-param-scope-sensitivity-baseline",
            dataset_label=dataset_label,
        )
        params = {
            str(name): float(value)
            for name, value in (payload.get("all_optimized_params") or {}).items()
        }
        auto_scope_params = [str(name) for name in payload.get("auto_param_scope_params") or []]
        if not params or not auto_scope_params:
            raise RuntimeError("Calibrated baseline did not return optimized params and auto-scope params.")
        return Baseline(
            mode=mode,
            params=params,
            auto_scope_params=sorted(auto_scope_params),
            source="adapter_gated_auto_scope_calibration",
            calibration_payload={
                "final_loss": payload.get("final_loss"),
                "baseline_loss": payload.get("baseline_loss"),
                "improvement_pct": payload.get("improvement_pct"),
                "auto_param_scope_eglc_gate_applied": payload.get("auto_param_scope_eglc_gate_applied"),
                "auto_param_scope_eglc_min_depletion_frac": payload.get("auto_param_scope_eglc_min_depletion_frac"),
            },
        )

    scoped = mm.auto_scope_with_bounds(target_metabolites, base_params=base_params)
    params = {name: float(bounds[0]) for name, bounds in scoped.items()}
    return Baseline(
        mode=mode,
        params=params,
        auto_scope_params=sorted(scoped.keys()),
        source="auto_scope_initial_values",
    )


def _build_objective_context(
    *,
    target_metabolites: Sequence[str],
    exp_time: Sequence[float],
    exp_data: Mapping[str, Sequence[float]],
    t_max: float,
) -> Tuple[Any, Dict[str, Any], Dict[str, Any]]:
    import MM_calibration as mm

    experimental_data = _experimental_payload(target_metabolites, exp_time, exp_data)
    time_exp, exp_values, name_to_row = mm.load_experimental_data(experimental_data)
    x0 = mm.load_initial_conditions()
    profile = mm.infer_custom_data_calibration_profile(target_metabolites)
    bundle = mm.build_objective_bundle(
        x0,
        time_exp,
        exp_values,
        name_to_row,
        target_scope=profile["target_scope"],
        t_max=float(t_max),
        atp_focus=bool(profile["atp_focus"]),
        atp_floor=float(profile["atp_floor"]),
        adp_floor=float(profile["adp_floor"]),
        amp_floor=float(profile["amp_floor"]),
        imp_floor=float(profile["imp_floor"]),
        adenylate_target=float(profile["adenylate_target"]),
        atp_penalty_weight=float(profile["atp_penalty_weight"]),
        amp_penalty_weight=float(profile["amp_penalty_weight"]),
        imp_penalty_weight=float(profile["imp_penalty_weight"]),
        pool_penalty_weight=float(profile["pool_penalty_weight"]),
        curve_fit_strength=float(profile["curve_fit_strength"]),
        target_names=target_metabolites,
    )
    return mm, profile, bundle


def _probe_parameter(
    *,
    mm: Any,
    bundle: Mapping[str, Any],
    param_name: str,
    baseline_params: Mapping[str, float],
    bounds: Tuple[float, float, float],
    baseline_metrics: Mapping[str, Any],
    step_frac: float,
    min_eglc_depletion_frac: float,
    low_effect_frac: float,
    high_effect_frac: float,
    danger_regression_frac: float,
) -> Dict[str, Any]:
    _, lower_bound, upper_bound = bounds
    baseline_value = float(baseline_params.get(param_name, bounds[0]))
    perturbation_specs = _perturbation_values(
        baseline_value,
        float(lower_bound),
        float(upper_bound),
        step_frac=float(step_frac),
    )
    perturbations: Dict[str, Any] = {}
    baseline_loss = float(baseline_metrics["target"])

    for direction, spec in perturbation_specs.items():
        candidate_params = dict(baseline_params)
        candidate_params[param_name] = float(spec["value"])
        metrics = mm.evaluate_monitor_metrics(
            bundle["primary"],
            bundle["monitor_objectives"],
            candidate_params,
        )
        target_loss = metrics.get("target")
        loss_delta = (
            float(target_loss) - baseline_loss
            if _is_number(target_loss)
            else None
        )
        perturbations[direction] = {
            "value": float(spec["value"]),
            "absolute_step": float(spec["absolute_step"]),
            "relative_step": float(spec["relative_step"]),
            "target_loss": float(target_loss) if _is_number(target_loss) else None,
            "target_loss_delta": loss_delta,
            "metrics": _metric_subset(metrics),
            "eglc_gate": _eglc_gate(metrics, float(min_eglc_depletion_frac)),
        }

    classification, rationale = _classify_probe(
        baseline_loss=baseline_loss,
        perturbations=perturbations,
        low_effect_frac=float(low_effect_frac),
        high_effect_frac=float(high_effect_frac),
        danger_regression_frac=float(danger_regression_frac),
    )
    finite_deltas = [
        float(p["target_loss_delta"])
        for p in perturbations.values()
        if _is_number(p.get("target_loss_delta"))
    ]
    max_abs_delta = max((abs(delta) for delta in finite_deltas), default=None)
    best_delta = min(finite_deltas) if finite_deltas else None
    worst_delta = max(finite_deltas) if finite_deltas else None
    effect_frac = (
        max_abs_delta / max(abs(baseline_loss), 1e-12)
        if max_abs_delta is not None
        else None
    )

    return {
        "name": param_name,
        "phase": _parameter_phase(mm, param_name),
        "classes": sorted(mm.get_parameter_classes(param_name)),
        "identifiability": mm.get_parameter_identifiability(param_name),
        "baseline_value": baseline_value,
        "lower_bound": float(lower_bound),
        "upper_bound": float(upper_bound),
        "perturbations": perturbations,
        "max_abs_target_loss_delta": max_abs_delta,
        "effect_frac_of_baseline_loss": effect_frac,
        "best_target_loss_delta": best_delta,
        "worst_target_loss_delta": worst_delta,
        "classification": classification,
        "recommendation": _recommendation_for_classification(classification),
        "rationale": rationale,
    }


def _summarize_probes(probes: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    counts = Counter(str(probe.get("classification")) for probe in probes)
    recommended_pruned = [
        str(probe["name"])
        for probe in probes
        if probe.get("recommendation") == "prune_candidate"
    ]
    kept = [
        str(probe["name"])
        for probe in probes
        if probe.get("recommendation") in {"keep", "keep_guarded"}
    ]
    guarded = [
        str(probe["name"])
        for probe in probes
        if probe.get("recommendation") == "keep_guarded"
    ]
    review = [
        str(probe["name"])
        for probe in probes
        if probe.get("recommendation") == "review"
    ]
    sorted_by_effect = sorted(
        probes,
        key=lambda item: (
            -1.0
            if item.get("effect_frac_of_baseline_loss") is None
            else -float(item.get("effect_frac_of_baseline_loss"))
        ),
    )
    return {
        "classification_counts": dict(sorted(counts.items())),
        "recommended_pruned_params": sorted(recommended_pruned),
        "recommended_kept_params": sorted(kept),
        "guarded_params": sorted(guarded),
        "review_params": sorted(review),
        "top_sensitive_params": [
            {
                "name": str(probe["name"]),
                "classification": probe.get("classification"),
                "effect_frac_of_baseline_loss": probe.get("effect_frac_of_baseline_loss"),
                "recommendation": probe.get("recommendation"),
            }
            for probe in sorted_by_effect[:20]
        ],
        "recommended_pruned_count": len(recommended_pruned),
        "recommended_kept_count": len(kept),
        "guarded_count": len(guarded),
        "review_count": len(review),
    }


def run_sensitivity_probe(args: argparse.Namespace) -> Dict[str, Any]:
    import run_auto_param_scope_parity as parity

    dataset_source, target_metabolites, exp_time, exp_data = parity.load_dataset(str(args.dataset))
    base_params = _load_params(args.base_params)
    seed_params = _load_params(args.seed_params)
    baseline_seed = seed_params if seed_params is not None else base_params

    mm, profile, bundle = _build_objective_context(
        target_metabolites=target_metabolites,
        exp_time=exp_time,
        exp_data=exp_data,
        t_max=float(args.t_max),
    )
    baseline = _build_baseline(
        mode=str(args.baseline_mode),
        target_metabolites=target_metabolites,
        exp_time=exp_time,
        exp_data=exp_data,
        base_params=baseline_seed,
        t_max=float(args.t_max),
        baseline_n_trials=int(args.baseline_n_trials),
    )

    auto_bounds = mm.auto_scope_with_bounds(target_metabolites, base_params=baseline.params)
    selected_params = _normalize_names(args.params.split(",")) if args.params else list(baseline.auto_scope_params)
    selected_params = [name for name in selected_params if name in auto_bounds]
    selected_params = sorted(dict.fromkeys(selected_params))
    if args.max_params is not None:
        selected_params = selected_params[: max(0, int(args.max_params))]
    if not selected_params:
        raise ValueError("No parameters selected for sensitivity probing.")

    baseline_metrics = mm.evaluate_monitor_metrics(
        bundle["primary"],
        bundle["monitor_objectives"],
        baseline.params,
    )
    baseline_loss = baseline_metrics.get("target")
    if not _is_number(baseline_loss):
        raise RuntimeError("Baseline objective evaluation did not produce a finite target loss.")

    probes: List[Dict[str, Any]] = []
    for index, param_name in enumerate(selected_params, start=1):
        print(f"[sensitivity] probing {index}/{len(selected_params)} {param_name}")
        probes.append(
            _probe_parameter(
                mm=mm,
                bundle=bundle,
                param_name=param_name,
                baseline_params=baseline.params,
                bounds=auto_bounds[param_name],
                baseline_metrics=baseline_metrics,
                step_frac=float(args.step_frac),
                min_eglc_depletion_frac=float(args.eglc_min_depletion_frac),
                low_effect_frac=float(args.low_effect_frac),
                high_effect_frac=float(args.high_effect_frac),
                danger_regression_frac=float(args.danger_regression_frac),
            )
        )

    summary = _summarize_probes(probes)
    baseline_params_path = Path(args.out_dir) / "baseline_params.json"
    _write_json(baseline_params_path, baseline.params)
    return {
        "schema_version": "auto_param_scope_sensitivity_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
        "dataset": {
            "source": dataset_source,
            "target_metabolite_count": len(target_metabolites),
            "target_metabolites": list(target_metabolites),
            "timepoint_count": len(exp_time),
            "time_range": [min(exp_time), max(exp_time)] if exp_time else None,
        },
        "settings": {
            "baseline_mode": str(args.baseline_mode),
            "baseline_n_trials": int(args.baseline_n_trials),
            "t_max": float(args.t_max),
            "step_frac": float(args.step_frac),
            "eglc_min_depletion_frac": float(args.eglc_min_depletion_frac),
            "low_effect_frac": float(args.low_effect_frac),
            "high_effect_frac": float(args.high_effect_frac),
            "danger_regression_frac": float(args.danger_regression_frac),
            "max_params": args.max_params,
            "params": args.params,
            "base_params_path": str(args.base_params) if args.base_params else None,
            "seed_params_path": str(args.seed_params) if args.seed_params else None,
        },
        "calibration_profile": profile,
        "baseline": {
            "mode": baseline.mode,
            "source": baseline.source,
            "target_loss": float(baseline_loss),
            "metrics": _metric_subset(baseline_metrics),
            "eglc_gate": _eglc_gate(baseline_metrics, float(args.eglc_min_depletion_frac)),
            "param_count": len(baseline.auto_scope_params),
            "probed_param_count": len(selected_params),
            "baseline_params_path": str(baseline_params_path),
            "calibration_payload": baseline.calibration_payload,
        },
        "summary": summary,
        "probes": probes,
    }


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Phase A local sensitivity probe for auto-param-scope."
    )
    parser.add_argument(
        "--dataset",
        default="canonical-bordbar",
        help="canonical-bordbar, a JSON payload path, or a CSV with a time column.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Output directory for result.json and baseline_params.json.",
    )
    parser.add_argument("--t-max", type=float, default=42.0)
    parser.add_argument(
        "--baseline-mode",
        choices=("auto-defaults", "calibrate"),
        default="auto-defaults",
        help="Probe around auto-scope initial values or first regenerate a calibrated gated baseline.",
    )
    parser.add_argument(
        "--baseline-n-trials",
        type=int,
        default=50,
        help="Calibration budget used only when --baseline-mode calibrate.",
    )
    parser.add_argument("--base-params", type=Path, default=None)
    parser.add_argument("--seed-params", type=Path, default=None)
    parser.add_argument(
        "--params",
        default=None,
        help="Optional comma-separated subset of parameter names to probe.",
    )
    parser.add_argument(
        "--max-params",
        type=int,
        default=None,
        help="Optional cap for smoke tests; probes sorted parameter names first.",
    )
    parser.add_argument("--step-frac", type=float, default=0.05)
    parser.add_argument("--eglc-min-depletion-frac", type=float, default=DEFAULT_EGLC_MIN_DEPLETION_FRAC)
    parser.add_argument("--low-effect-frac", type=float, default=0.005)
    parser.add_argument("--high-effect-frac", type=float, default=0.02)
    parser.add_argument("--danger-regression-frac", type=float, default=0.10)
    parser.add_argument(
        "--fail-on-unstable",
        action="store_true",
        help="Exit non-zero if any probe is unstable or needs review.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    _configure_imports()
    args = parse_args(argv)
    result_path = Path(args.out_dir) / "result.json"
    partial: Dict[str, Any] = {
        "schema_version": "auto_param_scope_sensitivity_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "running",
    }
    _write_json(result_path, partial)
    try:
        result = run_sensitivity_probe(args)
        _write_json(result_path, result)
        print(f"[sensitivity] wrote {result_path}")
        print(f"[sensitivity] probed {result['baseline']['probed_param_count']} params")
        print(
            "[sensitivity] classification_counts="
            + json.dumps(result["summary"]["classification_counts"], sort_keys=True)
        )
        if args.fail_on_unstable and result["summary"]["review_count"]:
            return 2
        return 0
    except Exception as exc:
        partial["status"] = "failed"
        partial["error"] = str(exc)
        partial["traceback"] = traceback.format_exc()
        _write_json(result_path, partial)
        print(f"[sensitivity] failed; partial artifact written to {result_path}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
