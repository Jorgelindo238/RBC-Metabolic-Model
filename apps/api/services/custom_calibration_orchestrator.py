"""Worker-side orchestration for custom-data calibration campaigns."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List

from services.teacher_flux_generic import run_teacher_flux_rescue


_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parents[3]
_MEMORY_PATH = (
    _PROJECT_ROOT
    / "Simulations"
    / "custom_data"
    / "autoresearch"
    / "custom_calibration_strategy_memory.jsonl"
)

_DEFAULT_STRATEGY_ORDER = [
    "vmax_then_km",
    "km_then_vmax",
    "joint_vmax_km",
    "staged_full",
    "core_km_then_purine_transport",
    "vmax_only",
    "km_only",
]

_VERDICT_RANK = {
    "keep": 4,
    "healthy": 4,
    "keep_with_caveats": 3,
    "compromised": 2,
    "needs_review": 2,
    "acceptable": 2,
    "discard": 1,
    "collapsed": 1,
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _request_copy(request: Any, **updates: Any) -> Any:
    if hasattr(request, "model_copy"):
        return request.model_copy(update=updates)
    cloned = deepcopy(request)
    for key, value in updates.items():
        setattr(cloned, key, value)
    return cloned


def _normalize_metabolites(values: Iterable[Any]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for value in values:
        normalized = str(value).strip().upper()
        if normalized and normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)
    return ordered


def _bucket_time_window(exp_time: Iterable[float]) -> str:
    points = [float(value) for value in exp_time]
    if len(points) < 2:
        return "single_point"
    horizon = max(points) - min(points)
    if horizon <= 7.0:
        return "short"
    if horizon <= 21.0:
        return "medium"
    return "long"


def _bucket_density(exp_time: Iterable[float]) -> str:
    count = len([float(value) for value in exp_time])
    if count <= 4:
        return "sparse"
    if count <= 8:
        return "moderate"
    return "dense"


def _bucket_noise(exp_data: Dict[str, List[float]]) -> str:
    scores: List[float] = []
    for series in exp_data.values():
        if len(series) < 3:
            continue
        values = [float(item) for item in series]
        level = max(sum(abs(item) for item in values) / max(len(values), 1), 1e-6)
        curvature = [abs(values[idx + 2] - 2 * values[idx + 1] + values[idx]) for idx in range(len(values) - 2)]
        if curvature:
            scores.append(sum(curvature) / len(curvature) / level)
    score = sum(scores) / len(scores) if scores else 0.0
    if score < 0.05:
        return "low"
    if score < 0.15:
        return "medium"
    return "high"


def build_dataset_fingerprint(request: Any) -> dict[str, Any]:
    measured_metabolites = _normalize_metabolites(
        list(getattr(request, "target_metabolites", None) or list((getattr(request, "exp_data", {}) or {}).keys()))
    )
    time_window_bucket = _bucket_time_window(getattr(request, "exp_time", []) or [])
    density_bucket = _bucket_density(getattr(request, "exp_time", []) or [])
    noise_bucket = _bucket_noise(getattr(request, "exp_data", {}) or {})
    canonical = {
        "measured_metabolites": measured_metabolites,
        "time_window_bucket": time_window_bucket,
        "density_bucket": density_bucket,
        "noise_bucket": noise_bucket,
    }
    digest = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return {
        **canonical,
        "fingerprint": digest,
    }


def _read_strategy_memory() -> List[dict[str, Any]]:
    if not _MEMORY_PATH.exists():
        return []
    entries: List[dict[str, Any]] = []
    for line in _MEMORY_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _append_strategy_memory(entry: dict[str, Any]) -> None:
    _MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _MEMORY_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\n")


def _memory_hits_for_fingerprint(dataset_fingerprint: str) -> List[dict[str, Any]]:
    return [
        entry
        for entry in _read_strategy_memory()
        if str(entry.get("fingerprint", "")) == dataset_fingerprint
    ]


def _build_strategy_candidates(request: Any, dataset_fingerprint: dict[str, Any]) -> tuple[List[str], List[str]]:
    requested_strategy = str(getattr(request, "optimization_strategy", "") or "").strip()
    memory_hits = []
    if bool(getattr(request, "enable_strategy_memory", True)):
        memory_hits = [
            str(entry.get("winning_strategy"))
            for entry in _memory_hits_for_fingerprint(dataset_fingerprint["fingerprint"])
            if str(entry.get("winning_strategy", "")).strip()
        ]

    ordered = []
    for candidate in [requested_strategy, *memory_hits, *_DEFAULT_STRATEGY_ORDER]:
        candidate = str(candidate).strip()
        if candidate and candidate not in ordered:
            ordered.append(candidate)

    budget = getattr(request, "strategy_race_budget", None)
    max_candidates = int(budget) if isinstance(budget, int) and budget > 0 else 4
    return ordered[:max_candidates], memory_hits


def _extract_verdict(result: dict[str, Any]) -> str:
    combined = result.get("combined_triage") or {}
    triage = result.get("triage") or {}
    pure = result.get("pure_ode_triage") or {}
    return str(
        combined.get("overall")
        or triage.get("overall")
        or pure.get("overall")
        or "needs_review"
    ).strip()


def _candidate_sort_key(result: dict[str, Any]) -> tuple[int, float, float]:
    verdict = _extract_verdict(result).lower()
    verdict_rank = _VERDICT_RANK.get(verdict, 0)
    final_loss = float(result.get("final_loss") or result.get("objective_value") or 1e9)
    improvement = float(result.get("improvement_pct") or 0.0)
    return (verdict_rank, -final_loss, improvement)


def _build_run_summary(strategy: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "strategy": strategy,
        "success": bool(result.get("success")),
        "verdict": _extract_verdict(result),
        "combined_triage": result.get("combined_triage"),
        "triage": result.get("triage"),
        "pure_ode_triage": result.get("pure_ode_triage"),
        "final_loss": result.get("final_loss"),
        "baseline_loss": result.get("baseline_loss"),
        "improvement_pct": result.get("improvement_pct"),
        "r_squared": result.get("r_squared"),
        "result_summary": result.get("result_summary"),
    }


def run_strategy_race_calibration(
    request: Any,
    *,
    single_run_callable: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    dataset_fingerprint = build_dataset_fingerprint(request)
    strategies, memory_hits = _build_strategy_candidates(request, dataset_fingerprint)
    runs: List[dict[str, Any]] = []
    results: List[tuple[str, dict[str, Any]]] = []

    for strategy in strategies:
        strategy_request = _request_copy(
            request,
            optimization_strategy=strategy,
            method=strategy,
            orchestration_mode="single_run",
            rerun_pure_ode=True,
        )
        result = single_run_callable(strategy_request)
        runs.append(_build_run_summary(strategy, result))
        results.append((strategy, result))

    if not results:
        raise RuntimeError("Strategy race produced no candidates.")

    winning_strategy, winning_result = max(results, key=lambda item: _candidate_sort_key(item[1]))

    teacher_flux_rescue = None
    if bool(getattr(request, "enable_teacher_flux_rescue", False)):
        winning_verdict = _extract_verdict(winning_result).lower()
        if winning_verdict in {"discard", "needs_review", "compromised"}:
            teacher_flux_rescue = run_teacher_flux_rescue(
                request=request,
                params={
                    str(name): float(value)
                    for name, value in (
                        winning_result.get("all_optimized_params")
                        or winning_result.get("optimized_params")
                        or {}
                    ).items()
                },
                output_dir=_PROJECT_ROOT / "Simulations" / "custom_data" / "teacher_flux" / dataset_fingerprint["fingerprint"],
            )

    accepted_verdict = _extract_verdict(winning_result).lower()
    if accepted_verdict in {"keep", "keep_with_caveats"}:
        _append_strategy_memory(
            {
                "timestamp": _utc_now_iso(),
                "fingerprint": dataset_fingerprint["fingerprint"],
                "measured_metabolites": dataset_fingerprint["measured_metabolites"],
                "time_window_bucket": dataset_fingerprint["time_window_bucket"],
                "density_bucket": dataset_fingerprint["density_bucket"],
                "noise_bucket": dataset_fingerprint["noise_bucket"],
                "winning_strategy": winning_strategy,
                "verdict": accepted_verdict,
                "final_loss": winning_result.get("final_loss"),
                "improvement_pct": winning_result.get("improvement_pct"),
            }
        )

    orchestration = {
        "mode": "strategy_race",
        "dataset_fingerprint": dataset_fingerprint,
        "memory_hits": memory_hits,
        "strategies_considered": strategies,
        "winner_strategy": winning_strategy,
        "winner_verdict": _extract_verdict(winning_result),
        "runs": runs,
        "teacher_flux_rescue": teacher_flux_rescue,
    }
    merged = dict(winning_result)
    merged["optimization_strategy"] = winning_strategy
    merged["orchestration"] = orchestration
    merged["result_summary"] = (
        f"Strategy race selected {winning_strategy} with verdict "
        f"{_extract_verdict(winning_result)} across {len(strategies)} candidate strategies."
    )
    return merged
