"""Phase A2 validation harness for auto-param-scope pruning.

Phase A local sensitivity can overstate pruning safety: a parameter may be
locally flat around a good baseline while still being useful during the search.
This harness validates candidate pruned scopes by rerunning calibration with
explicit include lists, then comparing each candidate against the full gated
auto-scope baseline recorded by the Phase A sensitivity artifact.

Default artifact:

    Simulations/auto_param_scope/pruning_v1/result.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
SRC_DIR = ROOT / "src"
API_DIR = ROOT / "apps" / "api"
DEFAULT_OUT_DIR = ROOT / "Simulations" / "auto_param_scope" / "pruning_v1"
DEFAULT_SENSITIVITY_RESULT = (
    ROOT / "Simulations" / "auto_param_scope" / "sensitivity_v1_full" / "result.json"
)
DEFAULT_EGLC_MIN_DEPLETION_FRAC = 0.05
DEFAULT_PROTECTED_TOKENS = (
    "EGLC",
    "ELAC",
    "LAC",
    "GLC",
    "ATP",
    "ADP",
    "AMP",
    "B23PG",
    "GSH",
)
DEFAULT_CANDIDATES = (
    "sensitive_only",
    "near_threshold",
    "top_k",
    "core_plus_sensitive",
    "drop_low_regulation",
    "drop_low_caution_transport",
)


def _configure_imports() -> None:
    for path in (str(ROOT), str(SCRIPT_DIR), str(SRC_DIR), str(API_DIR)):
        if path not in sys.path:
            sys.path.insert(0, path)


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
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


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_to_jsonable(dict(payload)), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _normalize_csv(values: Optional[str]) -> Optional[List[str]]:
    if values is None:
        return None
    out: List[str] = []
    for value in str(values).split(","):
        item = value.strip()
        if item:
            out.append(item)
    return out


def _load_base_params(path: Optional[Path]) -> Optional[Dict[str, float]]:
    if path is None:
        return None
    payload = _read_json(path)
    return {str(name): float(value) for name, value in payload.items()}


def _probe_name(probe: Mapping[str, Any]) -> str:
    return str(probe.get("name") or "").strip()


def _probe_effect(probe: Mapping[str, Any]) -> float:
    value = probe.get("effect_frac_of_baseline_loss")
    return float(value) if _is_number(value) else -1.0


def _probe_classes(probe: Mapping[str, Any]) -> Set[str]:
    return {str(value) for value in (probe.get("classes") or [])}


def _is_low_sensitivity(probe: Mapping[str, Any]) -> bool:
    return str(probe.get("classification")) == "candidate_prune_low_sensitivity"


def _is_keep(probe: Mapping[str, Any]) -> bool:
    return str(probe.get("recommendation")) in {"keep", "keep_guarded"}


def _matches_protected_token(name: str, protected_tokens: Sequence[str]) -> bool:
    upper = name.upper()
    return any(str(token).upper() in upper for token in protected_tokens)


def _sorted_unique(names: Iterable[str]) -> List[str]:
    return sorted(dict.fromkeys(str(name) for name in names if str(name).strip()))


def _build_candidate_scopes(
    sensitivity_result: Mapping[str, Any],
    *,
    requested_candidates: Sequence[str],
    near_effect_frac: float,
    top_k: int,
    protected_tokens: Sequence[str],
    include_full_reference: bool,
) -> Dict[str, Dict[str, Any]]:
    probes = [
        dict(probe)
        for probe in (sensitivity_result.get("probes") or [])
        if _probe_name(probe)
    ]
    if not probes:
        raise ValueError("Sensitivity artifact has no probes.")

    all_names = _sorted_unique(_probe_name(probe) for probe in probes)
    kept = {_probe_name(probe) for probe in probes if _is_keep(probe)}
    near = {
        _probe_name(probe)
        for probe in probes
        if _is_keep(probe) or _probe_effect(probe) >= float(near_effect_frac)
    }
    top = {
        _probe_name(probe)
        for probe in sorted(probes, key=_probe_effect, reverse=True)[: max(1, int(top_k))]
    }
    core_plus_sensitive = {
        _probe_name(probe)
        for probe in probes
        if (
            _is_keep(probe)
            or str(probe.get("identifiability")) == "core"
            or _matches_protected_token(_probe_name(probe), protected_tokens)
        )
    }
    drop_low_regulation = {
        _probe_name(probe)
        for probe in probes
        if not (_is_low_sensitivity(probe) and "regulation" in _probe_classes(probe))
    }
    drop_low_caution_transport = {
        _probe_name(probe)
        for probe in probes
        if not (
            _is_low_sensitivity(probe)
            and str(probe.get("identifiability")) == "caution"
            and "transport" in _probe_classes(probe)
        )
    }

    builders: Dict[str, Set[str]] = {
        "sensitive_only": kept,
        "near_threshold": near,
        "top_k": top,
        "core_plus_sensitive": core_plus_sensitive,
        "drop_low_regulation": drop_low_regulation,
        "drop_low_caution_transport": drop_low_caution_transport,
    }
    if include_full_reference:
        builders = {"full_auto_scope_reference": set(all_names), **builders}

    out: Dict[str, Dict[str, Any]] = {}
    for candidate_name in requested_candidates:
        if candidate_name not in builders:
            raise ValueError(
                f"Unknown candidate '{candidate_name}'. Choices: {', '.join(sorted(builders))}"
            )
        params = _sorted_unique(builders[candidate_name])
        if not params:
            continue
        out[candidate_name] = {
            "name": candidate_name,
            "params": params,
            "param_count": len(params),
            "dropped_params": _sorted_unique(set(all_names) - set(params)),
        }
    return out


def _candidate_decision(
    *,
    final_loss: Optional[float],
    reference_loss: float,
    eglc_gate: Mapping[str, Any],
    loss_tolerance_pct: float,
    review_loss_tolerance_pct: float,
) -> Dict[str, Any]:
    if not _is_number(final_loss):
        return {
            "decision": "failed",
            "reason": "Candidate did not produce a finite final loss.",
            "loss_delta": None,
            "loss_delta_pct_of_reference": None,
        }

    loss_delta = float(final_loss) - float(reference_loss)
    loss_delta_pct = loss_delta / max(abs(float(reference_loss)), 1e-12)
    if eglc_gate.get("state") == "fail":
        return {
            "decision": "reject_pruned_scope",
            "reason": "Candidate violates the EGLC depletion gate.",
            "loss_delta": loss_delta,
            "loss_delta_pct_of_reference": loss_delta_pct,
        }
    if eglc_gate.get("state") == "missing":
        return {
            "decision": "needs_review",
            "reason": "Candidate has no EGLC depletion signal to gate.",
            "loss_delta": loss_delta,
            "loss_delta_pct_of_reference": loss_delta_pct,
        }
    if loss_delta_pct <= float(loss_tolerance_pct):
        return {
            "decision": "accept_pruned_scope",
            "reason": "Candidate stays within the configured full-scope loss tolerance.",
            "loss_delta": loss_delta,
            "loss_delta_pct_of_reference": loss_delta_pct,
        }
    if loss_delta_pct <= float(review_loss_tolerance_pct):
        return {
            "decision": "needs_review",
            "reason": "Candidate exceeds the green tolerance but is within review tolerance.",
            "loss_delta": loss_delta,
            "loss_delta_pct_of_reference": loss_delta_pct,
        }
    return {
        "decision": "reject_pruned_scope",
        "reason": "Candidate regresses too far from the full gated auto-scope baseline.",
        "loss_delta": loss_delta,
        "loss_delta_pct_of_reference": loss_delta_pct,
    }


def _recommend_candidate(results: Sequence[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    accepted = [
        dict(result)
        for result in results
        if result.get("decision") == "accept_pruned_scope"
    ]
    if not accepted:
        return None
    accepted.sort(
        key=lambda item: (
            int(item.get("param_count") or 10**9),
            float(item.get("final_loss") or 10**9),
            str(item.get("name")),
        )
    )
    winner = accepted[0]
    return {
        "name": winner.get("name"),
        "param_count": winner.get("param_count"),
        "final_loss": winner.get("final_loss"),
        "loss_delta_pct_of_reference": winner.get("loss_delta_pct_of_reference"),
        "params": winner.get("params"),
    }


def _metric_subset(metrics: Mapping[str, Any]) -> Dict[str, Optional[float]]:
    keys = (
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
    return {
        key: (float(metrics[key]) if _is_number(metrics.get(key)) else None)
        for key in keys
    }


def _auto_scope_initial_params(
    mm: Any,
    target_metabolites: Sequence[str],
    *,
    base_params: Optional[Mapping[str, float]],
) -> Dict[str, float]:
    scoped = mm.auto_scope_with_bounds(target_metabolites, base_params=base_params)
    return {name: float(bounds[0]) for name, bounds in scoped.items()}


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


def _run_candidate_calibration(
    *,
    mm: Any,
    adapter: Any,
    candidate: Mapping[str, Any],
    target_metabolites: Sequence[str],
    exp_time: Sequence[float],
    exp_data: Mapping[str, Sequence[float]],
    initial_params: Mapping[str, float],
    profile: Mapping[str, Any],
    out_dir: Path,
    n_trials: int,
    t_max: float,
    eglc_min_depletion_frac: float,
) -> Dict[str, Any]:
    selected_params = list(candidate["params"])
    candidate_dir = out_dir / "candidates" / str(candidate["name"])
    candidate_dir.mkdir(parents=True, exist_ok=True)

    load_params_path = candidate_dir / "load_params.json"
    _write_json(load_params_path, initial_params)
    stage_plan = adapter._build_strategy_stage_plan(
        selected_params,
        str(profile["optimization_strategy"]),
        int(n_trials),
        protect_eglc_depletion=True,
        eglc_min_depletion_frac=float(eglc_min_depletion_frac),
    )
    _write_json(candidate_dir / "stage_plan.json", {"stage_plan": stage_plan})

    current_params, final_loss, _trajectory_csv_path = mm.run_calibration(
        phases=[1, 2, 3],
        n_trials=max(1, int(n_trials)),
        global_trials=0,
        load_params=str(load_params_path),
        target_scope=str(profile["target_scope"]),
        param_scope="all",
        generate_plots=False,
        seed=42,
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
        out_dir=candidate_dir,
        optimization_strategy=str(profile["optimization_strategy"]),
        stage_plan=stage_plan,
        target_metabolites=target_metabolites,
        experimental_data=_experimental_payload(target_metabolites, exp_time, exp_data),
        research_data_mode="custom_user_data_mode",
        active_dataset_id="auto-param-scope-pruning-validation",
        active_dataset_label="Auto-param-scope pruning validation",
    )

    report_path = candidate_dir / "calibration_report.json"
    report = _read_json(report_path)
    metrics = report.get("monitor_metrics") or {}
    eglc_gate = _eglc_gate_from_metrics(metrics, float(eglc_min_depletion_frac))
    stage_selected_params = _sorted_unique(
        name
        for stage in report.get("resolved_stage_plan") or []
        for name in (stage.get("selected_param_names") or [])
    )

    return {
        "name": candidate["name"],
        "params": list(candidate["params"]),
        "param_count": int(candidate["param_count"]),
        "dropped_param_count": len(candidate.get("dropped_params") or []),
        "dropped_params": list(candidate.get("dropped_params") or []),
        "stage_optimized_param_count": len(stage_selected_params),
        "stage_optimized_params": stage_selected_params,
        "final_loss": float(final_loss),
        "baseline_loss": report.get("baseline_loss"),
        "improvement_pct": report.get("improvement_pct"),
        "metrics": _metric_subset(metrics),
        "eglc_gate": eglc_gate,
        "report_path": str(report_path),
        "best_params_path": str(candidate_dir / "best_params.json"),
        "all_optimized_param_count": len(current_params),
    }


def _eglc_gate_from_metrics(metrics: Mapping[str, Any], min_depletion_frac: float) -> Dict[str, Any]:
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


def run_pruning_validation(args: argparse.Namespace) -> Dict[str, Any]:
    import MM_calibration as mm
    import run_auto_param_scope_parity as parity
    from services import mm_calibration_adapter as adapter

    sensitivity_path = Path(args.sensitivity_result)
    if not sensitivity_path.is_absolute():
        sensitivity_path = ROOT / sensitivity_path
    sensitivity_result = _read_json(sensitivity_path)

    dataset_source, target_metabolites, exp_time, exp_data = parity.load_dataset(str(args.dataset))
    profile = mm.infer_custom_data_calibration_profile(target_metabolites)
    base_params = _load_base_params(args.base_params)
    initial_params = _auto_scope_initial_params(
        mm,
        target_metabolites,
        base_params=base_params,
    )

    requested_candidates = _normalize_csv(args.candidates) or list(DEFAULT_CANDIDATES)
    if args.include_full_reference and "full_auto_scope_reference" not in requested_candidates:
        requested_candidates = ["full_auto_scope_reference", *requested_candidates]
    if args.max_candidates is not None:
        requested_candidates = requested_candidates[: max(0, int(args.max_candidates))]
    candidate_scopes = _build_candidate_scopes(
        sensitivity_result,
        requested_candidates=requested_candidates,
        near_effect_frac=float(args.near_effect_frac),
        top_k=int(args.top_k),
        protected_tokens=_normalize_csv(args.protected_tokens) or list(DEFAULT_PROTECTED_TOKENS),
        include_full_reference=bool(args.include_full_reference),
    )

    reference_loss = (sensitivity_result.get("baseline") or {}).get("target_loss")
    if not _is_number(reference_loss):
        raise ValueError("Sensitivity artifact baseline.target_loss is missing or non-finite.")
    reference_loss_f = float(reference_loss)

    result: Dict[str, Any] = {
        "schema_version": "auto_param_scope_pruning_validation_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "dataset": {
            "source": dataset_source,
            "target_metabolite_count": len(target_metabolites),
            "target_metabolites": list(target_metabolites),
            "timepoint_count": len(exp_time),
            "time_range": [min(exp_time), max(exp_time)] if exp_time else None,
        },
        "settings": {
            "sensitivity_result_path": str(sensitivity_path),
            "n_trials": int(args.n_trials),
            "t_max": float(args.t_max),
            "eglc_min_depletion_frac": float(args.eglc_min_depletion_frac),
            "loss_tolerance_pct": float(args.loss_tolerance_pct),
            "review_loss_tolerance_pct": float(args.review_loss_tolerance_pct),
            "near_effect_frac": float(args.near_effect_frac),
            "top_k": int(args.top_k),
            "candidates": list(candidate_scopes.keys()),
            "base_params_path": str(args.base_params) if args.base_params else None,
            "dry_run": bool(args.dry_run),
        },
        "reference": {
            "source": "phase_a_sensitivity_baseline",
            "target_loss": reference_loss_f,
            "eglc_gate": (sensitivity_result.get("baseline") or {}).get("eglc_gate"),
            "param_count": (sensitivity_result.get("baseline") or {}).get("param_count"),
        },
        "candidate_scopes": candidate_scopes,
        "candidates": [],
        "summary": None,
    }

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    result_path = out_dir / "result.json"
    _write_json(result_path, result)

    if args.dry_run:
        result["status"] = "completed"
        result["summary"] = _summarize_candidate_results([])
        _write_json(result_path, result)
        return result

    candidate_results: List[Dict[str, Any]] = []
    for index, candidate in enumerate(candidate_scopes.values(), start=1):
        print(
            f"[pruning] candidate {index}/{len(candidate_scopes)} "
            f"{candidate['name']} ({candidate['param_count']} params)"
        )
        try:
            candidate_result = _run_candidate_calibration(
                mm=mm,
                adapter=adapter,
                candidate=candidate,
                target_metabolites=target_metabolites,
                exp_time=exp_time,
                exp_data=exp_data,
                initial_params=initial_params,
                profile=profile,
                out_dir=out_dir,
                n_trials=int(args.n_trials),
                t_max=float(args.t_max),
                eglc_min_depletion_frac=float(args.eglc_min_depletion_frac),
            )
            decision = _candidate_decision(
                final_loss=candidate_result.get("final_loss"),
                reference_loss=reference_loss_f,
                eglc_gate=candidate_result.get("eglc_gate") or {},
                loss_tolerance_pct=float(args.loss_tolerance_pct),
                review_loss_tolerance_pct=float(args.review_loss_tolerance_pct),
            )
            candidate_result.update(decision)
        except Exception as exc:
            candidate_result = {
                "name": candidate["name"],
                "params": list(candidate["params"]),
                "param_count": int(candidate["param_count"]),
                "decision": "failed",
                "reason": str(exc),
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
            print(f"[pruning] candidate {candidate['name']} failed: {exc}", file=sys.stderr)
        candidate_results.append(candidate_result)
        result["candidates"] = candidate_results
        result["summary"] = _summarize_candidate_results(candidate_results)
        _write_json(result_path, result)

    result["status"] = "completed"
    result["summary"] = _summarize_candidate_results(candidate_results)
    _write_json(result_path, result)
    return result


def _summarize_candidate_results(results: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    counts = Counter(str(result.get("decision")) for result in results)
    accepted = [result for result in results if result.get("decision") == "accept_pruned_scope"]
    rejected = [result for result in results if result.get("decision") == "reject_pruned_scope"]
    review = [result for result in results if result.get("decision") == "needs_review"]
    failed = [result for result in results if result.get("decision") == "failed"]
    best_loss = sorted(
        [
            result
            for result in results
            if _is_number(result.get("final_loss"))
        ],
        key=lambda item: float(item.get("final_loss")),
    )
    return {
        "decision_counts": dict(sorted(counts.items())),
        "accepted_candidates": [str(result.get("name")) for result in accepted],
        "rejected_candidates": [str(result.get("name")) for result in rejected],
        "review_candidates": [str(result.get("name")) for result in review],
        "failed_candidates": [str(result.get("name")) for result in failed],
        "recommended_candidate": _recommend_candidate(results),
        "best_loss_candidate": (
            {
                "name": best_loss[0].get("name"),
                "param_count": best_loss[0].get("param_count"),
                "final_loss": best_loss[0].get("final_loss"),
                "decision": best_loss[0].get("decision"),
            }
            if best_loss
            else None
        ),
    }


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate Phase A auto-param-scope pruning candidates."
    )
    parser.add_argument(
        "--dataset",
        default="canonical-bordbar",
        help="canonical-bordbar, a JSON payload path, or a CSV with a time column.",
    )
    parser.add_argument(
        "--sensitivity-result",
        type=Path,
        default=DEFAULT_SENSITIVITY_RESULT,
        help="Phase A sensitivity result.json used to derive candidate scopes.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Output directory for result.json and candidate artifacts.",
    )
    parser.add_argument("--n-trials", type=int, default=20)
    parser.add_argument("--t-max", type=float, default=42.0)
    parser.add_argument("--base-params", type=Path, default=None)
    parser.add_argument("--eglc-min-depletion-frac", type=float, default=DEFAULT_EGLC_MIN_DEPLETION_FRAC)
    parser.add_argument("--loss-tolerance-pct", type=float, default=0.10)
    parser.add_argument("--review-loss-tolerance-pct", type=float, default=0.25)
    parser.add_argument("--near-effect-frac", type=float, default=0.001)
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument(
        "--candidates",
        default=",".join(DEFAULT_CANDIDATES),
        help="Comma-separated candidate builders to run.",
    )
    parser.add_argument(
        "--protected-tokens",
        default=",".join(DEFAULT_PROTECTED_TOKENS),
        help="Comma-separated name tokens retained by core_plus_sensitive.",
    )
    parser.add_argument(
        "--include-full-reference",
        action="store_true",
        help="Also rerun the full 98-param auto scope as an internal reference.",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=None,
        help="Optional candidate cap for smoke tests.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only derive candidate scopes; do not run calibration.",
    )
    parser.add_argument(
        "--fail-on-no-accepted",
        action="store_true",
        help="Exit non-zero if no candidate reaches accept_pruned_scope.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    _configure_imports()
    args = parse_args(argv)
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    result_path = out_dir / "result.json"
    partial = {
        "schema_version": "auto_param_scope_pruning_validation_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "running",
    }
    _write_json(result_path, partial)
    try:
        result = run_pruning_validation(args)
        _write_json(result_path, result)
        print(f"[pruning] wrote {result_path}")
        print("[pruning] decision_counts=" + json.dumps(result["summary"]["decision_counts"], sort_keys=True))
        recommended = result["summary"].get("recommended_candidate")
        if recommended:
            print(
                "[pruning] recommended="
                + str(recommended.get("name"))
                + f" ({recommended.get('param_count')} params)"
            )
        elif args.fail_on_no_accepted:
            return 2
        return 0
    except Exception as exc:
        partial["status"] = "failed"
        partial["error"] = str(exc)
        partial["traceback"] = traceback.format_exc()
        _write_json(result_path, partial)
        print(f"[pruning] failed; partial artifact written to {result_path}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
