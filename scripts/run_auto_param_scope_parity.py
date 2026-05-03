"""Run auto-param-scope vs curated-profile calibration parity sweep.

This harness exercises the product-plane calibration adapter twice on the same
dataset and seed context:

* auto branch: empty params_to_optimize + auto_param_scope=True
* curated branch: empty params_to_optimize + auto_param_scope=False

It writes one comparison artifact to:

    Simulations/auto_param_scope/parity_v1/result.json

The script is intentionally small and adapter-driven so it validates the same
request semantics used by the web/worker path instead of duplicating Phase 0
selection logic.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
API_DIR = ROOT / "apps" / "api"
DEFAULT_OUT_DIR = ROOT / "Simulations" / "auto_param_scope" / "parity_v1"
DEFAULT_PROTECTED_ANCHORS = ("ATP", "ADP", "AMP", "B23PG", "GSH", "EGLC", "ELAC", "LAC")


def _configure_imports() -> None:
    """Make the script import the same modules the API adapter uses."""

    for path in (str(ROOT), str(SRC_DIR), str(API_DIR)):
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


def _load_base_params(path: Optional[Path]) -> Optional[Dict[str, float]]:
    if path is None:
        return None
    payload = _read_json(path)
    return {str(name): float(value) for name, value in payload.items()}


def _canonical_bordbar_dataset() -> Tuple[List[str], List[float], Dict[str, List[float]]]:
    import MM_calibration as mm

    time_exp, exp_values, name_to_row = mm.load_experimental_data()
    metabolites = list(name_to_row.keys())
    exp_data = {
        name: [float(v) for v in exp_values[row_idx, :]]
        for name, row_idx in name_to_row.items()
    }
    return metabolites, [float(t) for t in time_exp], exp_data


def _dataset_from_json(path: Path) -> Tuple[List[str], List[float], Dict[str, List[float]]]:
    payload = _read_json(path)
    if "exp_data" in payload:
        exp_data = {
            str(name).strip().upper(): [float(v) for v in values]
            for name, values in payload["exp_data"].items()
        }
        exp_time = [float(t) for t in payload.get("exp_time") or payload.get("time_points") or []]
        target_metabolites = [
            str(name).strip().upper()
            for name in payload.get("target_metabolites") or exp_data.keys()
        ]
        return target_metabolites, exp_time, exp_data

    metabolites = [str(name).strip().upper() for name in payload["metabolites"]]
    exp_time = [float(t) for t in payload["time_points"]]
    values = payload["values"]
    exp_data = {
        name: [float(v) for v in row]
        for name, row in zip(metabolites, values)
    }
    return metabolites, exp_time, exp_data


def _dataset_from_csv(path: Path) -> Tuple[List[str], List[float], Dict[str, List[float]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"CSV dataset has no header: {path}")
        fieldnames = [str(name).strip() for name in reader.fieldnames]
        time_col = next(
            (
                name
                for name in fieldnames
                if name.strip().lower() in {"time", "day", "days", "t", "storage_day"}
            ),
            fieldnames[0],
        )
        metabolite_cols = [name for name in fieldnames if name != time_col]
        exp_time: List[float] = []
        exp_data: Dict[str, List[float]] = {name.strip().upper(): [] for name in metabolite_cols}
        for row in reader:
            exp_time.append(float(row[time_col]))
            for name in metabolite_cols:
                exp_data[name.strip().upper()].append(float(row[name]))
    return list(exp_data.keys()), exp_time, exp_data


def load_dataset(dataset: str) -> Tuple[str, List[str], List[float], Dict[str, List[float]]]:
    if dataset in {"canonical-bordbar", "bordbar", "default"}:
        metabolites, exp_time, exp_data = _canonical_bordbar_dataset()
        return "canonical-bordbar", metabolites, exp_time, exp_data

    path = Path(dataset).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"Dataset path not found: {path}")
    if path.suffix.lower() == ".json":
        metabolites, exp_time, exp_data = _dataset_from_json(path)
    elif path.suffix.lower() == ".csv":
        metabolites, exp_time, exp_data = _dataset_from_csv(path)
    else:
        raise ValueError("Dataset must be canonical-bordbar, a .json file, or a .csv file.")
    return str(path), metabolites, exp_time, exp_data


def _make_request(
    *,
    target_metabolites: Sequence[str],
    exp_time: Sequence[float],
    exp_data: Mapping[str, Sequence[float]],
    auto_param_scope: bool,
    max_iterations: int,
    t_max: float,
    rerun_pure_ode: bool,
    base_params: Optional[Dict[str, float]],
    dataset_id: str,
    dataset_label: str,
) -> SimpleNamespace:
    return SimpleNamespace(
        target_metabolites=[str(name).strip().upper() for name in target_metabolites],
        exp_time=[float(t) for t in exp_time],
        exp_data={
            str(name).strip().upper(): [float(v) for v in values]
            for name, values in exp_data.items()
        },
        params_to_optimize={},
        auto_param_scope=auto_param_scope,
        base_params=base_params,
        optimization_strategy=None,
        method=None,
        max_iterations=int(max_iterations),
        t_max=float(t_max),
        solver_method="RK45",
        research_data_mode="custom_user_data_mode",
        active_dataset_id=dataset_id,
        active_dataset_label=dataset_label,
        rerun_pure_ode=bool(rerun_pure_ode),
        orchestration_mode="single_run",
        enable_strategy_memory=False,
        enable_teacher_flux_rescue=False,
        strategy_race_budget=None,
    )


def _state_severity(state: Optional[str]) -> int:
    return {
        "good": 0,
        "healthy": 0,
        "acceptable": 0,
        "available": 0,
        "tracked": 0,
        "concern": 1,
        "compromised": 1,
        "needs_review": 2,
        "critical": 3,
        "collapsed": 3,
        "missing": 4,
        "skipped": 4,
        None: 4,
    }.get(str(state).lower(), 2)


def _extract_anchor_survival(
    pure_ode_triage: Optional[Mapping[str, Any]],
    anchors: Sequence[str],
) -> Dict[str, Dict[str, Any]]:
    if not pure_ode_triage:
        return {
            name: {"state": "missing", "source": "pure_ode_triage", "available": False}
            for name in anchors
        }
    if pure_ode_triage.get("skipped"):
        return {
            name: {
                "state": "skipped",
                "source": "pure_ode_triage",
                "available": False,
                "skip_reason": pure_ode_triage.get("skip_reason"),
            }
            for name in anchors
        }

    protected = pure_ode_triage.get("protected_floor_status") or {}
    extracellular = pure_ode_triage.get("extracellular_anchor_status") or {}
    per_metabolite = {
        str(entry.get("name")).upper(): entry
        for entry in pure_ode_triage.get("per_metabolite") or []
        if isinstance(entry, Mapping) and entry.get("name")
    }

    out: Dict[str, Dict[str, Any]] = {}
    for raw_name in anchors:
        name = str(raw_name).strip().upper()
        if name in protected:
            item = dict(protected[name])
            out[name] = {
                "state": item.get("state"),
                "source": "protected_floor_status",
                "available": item.get("state") != "missing",
                "final_value": item.get("final_value"),
                "min_value": item.get("min_value"),
                "rationale": item.get("rationale"),
            }
        elif name in extracellular:
            item = dict(extracellular[name])
            out[name] = {
                "state": item.get("state"),
                "source": "extracellular_anchor_status",
                "available": item.get("state") != "missing",
                "start": item.get("start"),
                "end": item.get("end"),
                "pct_delta": item.get("pct_delta"),
                "rationale": item.get("rationale"),
            }
        elif name in per_metabolite:
            item = dict(per_metabolite[name])
            out[name] = {
                "state": "tracked" if item.get("available", False) else "missing",
                "source": "per_metabolite",
                "available": bool(item.get("available", False)),
                "start": item.get("start"),
                "end": item.get("end"),
                "min_value": item.get("min_value"),
                "max_value": item.get("max_value"),
                "pct_delta": item.get("pct_delta"),
                "shape": item.get("shape"),
            }
        else:
            out[name] = {"state": "missing", "source": "not_reported", "available": False}
    return out


def _summarize_branch(name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    optimized_params = payload.get("optimized_params") or {}
    auto_params = payload.get("auto_param_scope_params") or []
    pure_ode = payload.get("pure_ode_triage")
    combined = payload.get("combined_triage")
    triage = payload.get("triage")
    protected_survival = _extract_anchor_survival(pure_ode, DEFAULT_PROTECTED_ANCHORS)

    return {
        "branch": name,
        "success": bool(payload.get("success")),
        "message": payload.get("message"),
        "calibration_profile": payload.get("calibration_profile"),
        "optimization_strategy": payload.get("optimization_strategy"),
        "final_loss": payload.get("final_loss"),
        "objective_value": payload.get("objective_value"),
        "baseline_loss": payload.get("baseline_loss"),
        "improvement_pct": payload.get("improvement_pct"),
        "r_squared": payload.get("r_squared"),
        "auto_param_scope_applied": bool(payload.get("auto_param_scope_applied")),
        "auto_param_scope_params": list(auto_params),
        "optimized_param_count": len(optimized_params),
        "optimized_param_names": sorted(str(name) for name in optimized_params.keys()),
        "pure_ode_overall": pure_ode.get("overall") if isinstance(pure_ode, Mapping) else None,
        "pure_ode_reason": pure_ode.get("reason") if isinstance(pure_ode, Mapping) else None,
        "combined_triage_overall": combined.get("overall") if isinstance(combined, Mapping) else None,
        "curve_triage_overall": triage.get("overall") if isinstance(triage, Mapping) else None,
        "protected_survival": protected_survival,
    }


def _dry_run_branch_summaries(
    target_metabolites: Sequence[str],
    *,
    base_params: Optional[Dict[str, float]],
) -> Dict[str, Dict[str, Any]]:
    """Build structural branch summaries without running ODE calibration."""

    import MM_calibration as mm

    auto_with_bounds = mm.auto_scope_with_bounds(target_metabolites, base_params=base_params)
    calibration_profile = mm.infer_custom_data_calibration_profile(target_metabolites)
    curated_names = sorted(str(name) for name in calibration_profile.get("parameter_additions", []))

    skipped_survival = {
        name: {
            "state": "skipped",
            "source": "dry_run",
            "available": False,
            "skip_reason": "Dry-run scope check does not execute calibration or pure-ODE replay.",
        }
        for name in DEFAULT_PROTECTED_ANCHORS
    }

    return {
        "auto_scope": {
            "branch": "auto_scope",
            "success": True,
            "message": "Dry-run scope derivation only; calibration was not executed.",
            "calibration_profile": calibration_profile.get("profile_name"),
            "optimization_strategy": calibration_profile.get("optimization_strategy"),
            "final_loss": None,
            "objective_value": None,
            "baseline_loss": None,
            "improvement_pct": None,
            "r_squared": None,
            "auto_param_scope_applied": True,
            "auto_param_scope_params": sorted(auto_with_bounds.keys()),
            "optimized_param_count": len(auto_with_bounds),
            "optimized_param_names": sorted(auto_with_bounds.keys()),
            "pure_ode_overall": "skipped",
            "pure_ode_reason": "Dry-run scope check.",
            "combined_triage_overall": None,
            "curve_triage_overall": None,
            "protected_survival": skipped_survival,
        },
        "curated_profile": {
            "branch": "curated_profile",
            "success": True,
            "message": "Dry-run curated profile derivation only; calibration was not executed.",
            "calibration_profile": calibration_profile.get("profile_name"),
            "optimization_strategy": calibration_profile.get("optimization_strategy"),
            "final_loss": None,
            "objective_value": None,
            "baseline_loss": None,
            "improvement_pct": None,
            "r_squared": None,
            "auto_param_scope_applied": False,
            "auto_param_scope_params": [],
            "optimized_param_count": len(curated_names),
            "optimized_param_names": curated_names,
            "pure_ode_overall": "skipped",
            "pure_ode_reason": "Dry-run scope check.",
            "combined_triage_overall": None,
            "curve_triage_overall": None,
            "protected_survival": skipped_survival,
        },
    }


def _compare_branches(
    auto_summary: Mapping[str, Any],
    curated_summary: Mapping[str, Any],
    *,
    loss_tolerance_pct: float,
) -> Dict[str, Any]:
    auto_names = set(auto_summary.get("optimized_param_names") or [])
    curated_names = set(curated_summary.get("optimized_param_names") or [])
    union = auto_names | curated_names
    intersection = auto_names & curated_names

    auto_loss = auto_summary.get("final_loss")
    curated_loss = curated_summary.get("final_loss")
    loss_delta = None
    loss_delta_pct = None
    loss_within_tolerance = False
    if isinstance(auto_loss, (int, float)) and isinstance(curated_loss, (int, float)):
        loss_delta = float(auto_loss) - float(curated_loss)
        denom = max(abs(float(curated_loss)), 1e-12)
        loss_delta_pct = loss_delta / denom
        loss_within_tolerance = loss_delta_pct <= float(loss_tolerance_pct)

    anchor_comparison: Dict[str, Any] = {}
    auto_worse_anchors: List[str] = []
    for anchor in DEFAULT_PROTECTED_ANCHORS:
        auto_state = (
            (auto_summary.get("protected_survival") or {}).get(anchor, {}).get("state")
        )
        curated_state = (
            (curated_summary.get("protected_survival") or {}).get(anchor, {}).get("state")
        )
        auto_severity = _state_severity(auto_state)
        curated_severity = _state_severity(curated_state)
        is_worse = auto_severity > curated_severity
        if is_worse:
            auto_worse_anchors.append(anchor)
        anchor_comparison[anchor] = {
            "auto_state": auto_state,
            "curated_state": curated_state,
            "auto_severity": auto_severity,
            "curated_severity": curated_severity,
            "auto_worse": is_worse,
        }

    if auto_worse_anchors:
        decision = "root_cause_phase0"
    elif loss_within_tolerance:
        decision = "green_light_phase_a"
    else:
        decision = "needs_review"

    return {
        "loss_tolerance_pct": float(loss_tolerance_pct),
        "final_loss_auto_minus_curated": loss_delta,
        "final_loss_delta_pct_of_curated": loss_delta_pct,
        "auto_loss_within_tolerance": bool(loss_within_tolerance),
        "auto_optimized_param_count": len(auto_names),
        "curated_optimized_param_count": len(curated_names),
        "scope_intersection_count": len(intersection),
        "scope_union_count": len(union),
        "scope_jaccard": (len(intersection) / len(union)) if union else 1.0,
        "auto_only_params": sorted(auto_names - curated_names),
        "curated_only_params": sorted(curated_names - auto_names),
        "protected_anchor_comparison": anchor_comparison,
        "auto_worse_protected_anchors": auto_worse_anchors,
        "decision_gate": decision,
    }


@dataclass(frozen=True)
class BranchConfig:
    name: str
    auto_param_scope: bool


def run_branch(
    branch: BranchConfig,
    *,
    target_metabolites: Sequence[str],
    exp_time: Sequence[float],
    exp_data: Mapping[str, Sequence[float]],
    n_trials: int,
    t_max: float,
    rerun_pure_ode: bool,
    base_params: Optional[Dict[str, float]],
    dataset_id: str,
    dataset_label: str,
) -> Dict[str, Any]:
    from services.mm_calibration_adapter import run_web_calibration

    request = _make_request(
        target_metabolites=target_metabolites,
        exp_time=exp_time,
        exp_data=exp_data,
        auto_param_scope=branch.auto_param_scope,
        max_iterations=n_trials,
        t_max=t_max,
        rerun_pure_ode=rerun_pure_ode,
        base_params=base_params,
        dataset_id=dataset_id,
        dataset_label=dataset_label,
    )
    return run_web_calibration(request, allow_orchestration=False)


def write_result(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_to_jsonable(payload), indent=2, sort_keys=True), encoding="utf-8")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run auto-param-scope vs curated-profile calibration parity sweep."
    )
    parser.add_argument(
        "--dataset",
        default="canonical-bordbar",
        help="canonical-bordbar, a JSON payload path, or a CSV with a time column.",
    )
    parser.add_argument("--n-trials", type=int, default=1, help="Trials per branch for smoke/full run.")
    parser.add_argument("--t-max", type=float, default=42.0, help="Calibration horizon in days; must be > 1.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Output directory for result.json.",
    )
    parser.add_argument(
        "--base-params",
        type=Path,
        default=None,
        help="Optional JSON parameter seed used as base_params for both branches.",
    )
    parser.add_argument(
        "--loss-tolerance-pct",
        type=float,
        default=0.05,
        help="Allowed fractional auto-vs-curated final-loss regression. 0.05 = 5%%.",
    )
    parser.add_argument(
        "--skip-pure-ode",
        action="store_true",
        help="Skip pure-ODE replay for a faster structural smoke. Result marks anchors as skipped.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only derive and compare scopes; do not execute calibration.",
    )
    parser.add_argument(
        "--fail-on-red",
        action="store_true",
        help="Exit non-zero when the decision gate is not green_light_phase_a.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    _configure_imports()
    args = parse_args(argv)
    result_path = Path(args.out_dir) / "result.json"

    dataset_source, target_metabolites, exp_time, exp_data = load_dataset(str(args.dataset))
    base_params = _load_base_params(args.base_params)
    dataset_id = "auto-param-scope-parity-" + Path(str(dataset_source)).stem.replace(" ", "-").lower()
    dataset_label = f"Auto-param-scope parity: {dataset_source}"
    rerun_pure_ode = not bool(args.skip_pure_ode)

    result: Dict[str, Any] = {
        "schema_version": "auto_param_scope_parity_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "source": dataset_source,
            "target_metabolite_count": len(target_metabolites),
            "target_metabolites": list(target_metabolites),
            "timepoint_count": len(exp_time),
            "time_range": [min(exp_time), max(exp_time)] if exp_time else None,
        },
        "settings": {
            "n_trials": int(args.n_trials),
            "t_max": float(args.t_max),
            "rerun_pure_ode": bool(rerun_pure_ode),
            "dry_run": bool(args.dry_run),
            "base_params_path": str(args.base_params) if args.base_params else None,
            "loss_tolerance_pct": float(args.loss_tolerance_pct),
        },
        "branches": {},
        "comparison": None,
        "status": "running",
    }
    write_result(result_path, result)

    branch_configs = (
        BranchConfig("auto_scope", True),
        BranchConfig("curated_profile", False),
    )

    try:
        if args.dry_run:
            result["branches"] = _dry_run_branch_summaries(
                target_metabolites,
                base_params=base_params,
            )
            result["comparison"] = _compare_branches(
                result["branches"]["auto_scope"],
                result["branches"]["curated_profile"],
                loss_tolerance_pct=float(args.loss_tolerance_pct),
            )
            result["status"] = "completed"
            result["comparison"]["decision_gate"] = "dry_run_scope_only"
            write_result(result_path, result)
            print(f"[parity] dry-run wrote {result_path}")
            return 0

        for branch in branch_configs:
            print(f"[parity] running {branch.name} (auto_param_scope={branch.auto_param_scope})...")
            payload = run_branch(
                branch,
                target_metabolites=target_metabolites,
                exp_time=exp_time,
                exp_data=exp_data,
                n_trials=max(1, int(args.n_trials)),
                t_max=float(args.t_max),
                rerun_pure_ode=rerun_pure_ode,
                base_params=base_params,
                dataset_id=dataset_id,
                dataset_label=dataset_label,
            )
            result["branches"][branch.name] = _summarize_branch(branch.name, payload)
            write_result(result_path, result)

        result["comparison"] = _compare_branches(
            result["branches"]["auto_scope"],
            result["branches"]["curated_profile"],
            loss_tolerance_pct=float(args.loss_tolerance_pct),
        )
        result["status"] = "completed"
        write_result(result_path, result)

        decision = result["comparison"]["decision_gate"]
        print(f"[parity] wrote {result_path}")
        print(f"[parity] decision_gate={decision}")
        if args.fail_on_red and decision != "green_light_phase_a":
            return 2
        return 0
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = str(exc)
        result["traceback"] = traceback.format_exc()
        write_result(result_path, result)
        print(f"[parity] failed; partial artifact written to {result_path}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
