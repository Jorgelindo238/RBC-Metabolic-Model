from __future__ import annotations

from typing import Any

from services.robocop.calibration_state import (
    CalibrationPhaseDCycleRecord,
    CalibrationSeamMemoryEntry,
    CalibrationSubsystemProposal,
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_explicit_seams(raw: Any) -> list[dict[str, Any]]:
    seams: list[dict[str, Any]] = []
    for item in raw or []:
        if isinstance(item, str):
            text = item.strip()
            if text:
                seams.append({"agent": text, "reason": "explicit_input", "seam_status": "saturated"})
        elif isinstance(item, dict):
            seams.append(dict(item))
    return seams


def derive_cycle_known_saturated_seams(
    seam_memory: list[CalibrationSeamMemoryEntry],
    current_seed_params_path: str,
    explicit: list[dict[str, Any]] | list[str] | None = None,
) -> list[dict[str, Any]]:
    current_seed = _normalize_text(current_seed_params_path)
    result: list[dict[str, Any]] = _normalize_explicit_seams(explicit)
    seen = {
        (
            _normalize_text(item.get("agent")),
            _normalize_text(item.get("reason")),
            _normalize_text(item.get("source_cycle")),
        )
        for item in result
    }

    for entry in seam_memory:
        seam_status = _normalize_text(entry.get("seam_status"))
        if seam_status not in {"saturated", "dangerous"}:
            continue
        applies_to_current_seed = _normalize_text(entry.get("seed_params_path")) == current_seed
        carry_forward = bool(entry.get("carry_forward", False))
        if not applies_to_current_seed and not carry_forward:
            continue
        normalized = {
            "agent": _normalize_text(entry.get("agent")),
            "reason": _normalize_text(entry.get("reason") or entry.get("decision")),
            "seam_status": seam_status,
            "source_cycle": entry.get("cycle_index"),
            "seed_params_path": _normalize_text(entry.get("seed_params_path")),
        }
        key = (
            normalized["agent"],
            normalized["reason"],
            _normalize_text(normalized.get("source_cycle")),
        )
        if normalized["agent"] and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


def _decision_to_memory_status(
    phase_b_result: dict[str, Any],
) -> tuple[str, bool, str]:
    decision = _normalize_text(phase_b_result.get("decision"))
    pure_ode_delta = phase_b_result.get("pureOdeDelta", {}) or {}
    pure_worse = any(
        _normalize_text(item.get("status")) == "worse"
        for item in pure_ode_delta.values()
        if isinstance(item, dict)
    )
    meaningful_gain = bool((phase_b_result.get("fitSummary") or {}).get("meaningful_improvement"))

    if decision == "promote":
        return "open", False, "candidate_promoted"
    if decision == "discard":
        if pure_worse:
            return "dangerous", True, "pure_ode_regression"
        return "saturated", False, "no_usable_gain"
    if decision == "informative":
        if pure_worse:
            return "dangerous", True, "informative_but_regressive"
        if meaningful_gain:
            return "saturated", False, "informative_same_seed_do_not_repeat_immediately"
        return "saturated", False, "informative_without_promotion"
    return "saturated", False, "unknown_decision"


def build_phase_d_seam_memory_entries(
    *,
    cycle_index: int,
    seed_params_path: str,
    selected_proposals: list[CalibrationSubsystemProposal],
    stage_plan_path: str,
    phase_b_result: dict[str, Any],
) -> list[CalibrationSeamMemoryEntry]:
    seam_status, carry_forward, reason = _decision_to_memory_status(phase_b_result)
    fit_absolute_gain = _safe_float((phase_b_result.get("fitSummary") or {}).get("absolute_gain"), default=None)
    pure_ode_flags = {
        name: item.get("status")
        for name, item in (phase_b_result.get("pureOdeDelta") or {}).items()
        if isinstance(item, dict)
    }
    entries: list[CalibrationSeamMemoryEntry] = []
    for proposal in selected_proposals:
        entries.append(
            {
                "cycle_index": int(cycle_index),
                "agent": proposal.get("agent"),
                "hypothesis": _normalize_text(proposal.get("hypothesis")),
                "seed_params_path": _normalize_text(seed_params_path),
                "stage_plan_path": _normalize_text(stage_plan_path),
                "decision": _normalize_text(phase_b_result.get("decision")),
                "seam_status": seam_status,
                "reason": reason,
                "carry_forward": carry_forward,
                "fit_absolute_gain": fit_absolute_gain,
                "pure_ode_flags": pure_ode_flags,
            }
        )
    return entries


def build_phase_d_cycle_record(
    *,
    cycle_index: int,
    seed_params_path: str,
    seed_report_path: str,
    seed_ode_csv_path: str,
    known_saturated_seams: list[dict[str, Any]],
    selected_agents: list[str],
    stage_plan_path: str,
    phase_b_result: dict[str, Any],
) -> CalibrationPhaseDCycleRecord:
    return {
        "cycle_index": int(cycle_index),
        "seed_params_path": _normalize_text(seed_params_path),
        "seed_report_path": _normalize_text(seed_report_path),
        "seed_ode_csv_path": _normalize_text(seed_ode_csv_path),
        "known_saturated_seams": known_saturated_seams,
        "selected_agents": [str(agent) for agent in selected_agents],
        "stage_plan_path": _normalize_text(stage_plan_path),
        "phase_b_decision": _normalize_text(phase_b_result.get("decision")),
        "phase_b_reason": _normalize_text(phase_b_result.get("reason")),
        "phase_b_decision_path": _normalize_text(phase_b_result.get("decisionPath")),
        "promoted_seed": _normalize_text(phase_b_result.get("decision")) == "promote",
    }


def should_advance_seed(phase_b_result: dict[str, Any]) -> bool:
    if _normalize_text(phase_b_result.get("decision")) != "promote":
        return False
    candidate = phase_b_result.get("candidateArtifacts") or {}
    return all(
        _normalize_text(candidate.get(key))
        for key in ("paramsPath", "reportPath", "odeCsvPath")
    )
