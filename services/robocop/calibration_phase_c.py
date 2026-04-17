from __future__ import annotations

from typing import Any

from services.robocop.calibration_phase_a import coordinate_phase_a
from services.robocop.calibration_prompts import build_calibration_coordinator_user_prompt
from services.robocop.calibration_state import (
    CalibrationArbitrationRecord,
    CalibrationSubsystemProposal,
    HermesCalibrationState,
)


DEFAULT_MAX_SELECTED_AGENTS = 2
DEFAULT_MIN_SUPPORT_STRENGTH = 0.25


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _proposal_params(proposal: CalibrationSubsystemProposal) -> set[str]:
    return {str(item).strip() for item in proposal.get("allowed_parameters") or [] if str(item).strip()}


def _merge_optimization_strategy(strategies: list[str]) -> str | None:
    normalized = {_normalize_text(strategy) for strategy in strategies if _normalize_text(strategy)}
    if not normalized:
        return "vmax_then_km"
    if len(normalized) == 1:
        return next(iter(normalized))
    if normalized <= {"vmax_only", "km_only", "vmax_then_km"}:
        if "vmax_then_km" in normalized or normalized == {"vmax_only", "km_only"}:
            return "vmax_then_km"
        if "vmax_only" in normalized:
            return "vmax_only"
        if "km_only" in normalized:
            return "km_only"
    return None


def _compatible_with_selected(
    selected: list[CalibrationSubsystemProposal],
    candidate: CalibrationSubsystemProposal,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not candidate.get("should_run"):
        reasons.append("proposal is not runnable")
        return False, reasons

    candidate_agent = _normalize_text(candidate.get("agent"))
    candidate_target_scope = _normalize_text(candidate.get("target_scope"))
    candidate_phase = int(candidate.get("phase") or 1)
    candidate_strategy = _normalize_text(candidate.get("optimization_strategy"))
    candidate_params = _proposal_params(candidate)

    for item in selected:
        selected_agent = _normalize_text(item.get("agent"))
        selected_target_scope = _normalize_text(item.get("target_scope"))
        selected_phase = int(item.get("phase") or 1)
        selected_strategy = _normalize_text(item.get("optimization_strategy"))
        selected_params = _proposal_params(item)

        if candidate_agent in {str(name).strip() for name in item.get("conflicts_with") or []}:
            reasons.append(f"conflicts with selected agent {selected_agent}")
        if selected_agent in {str(name).strip() for name in candidate.get("conflicts_with") or []}:
            reasons.append(f"selected agent {selected_agent} marks this seam as conflicting")
        if candidate_target_scope != selected_target_scope:
            reasons.append(f"target scope mismatch with {selected_agent}")
        if candidate_phase != selected_phase:
            reasons.append(f"phase mismatch with {selected_agent}")
        if _merge_optimization_strategy([candidate_strategy, selected_strategy]) is None:
            reasons.append(f"optimization strategy mismatch with {selected_agent}")
        overlapping_params = sorted(candidate_params & selected_params)
        if overlapping_params:
            reasons.append(
                f"overlapping parameter ownership with {selected_agent}: {', '.join(overlapping_params)}"
            )

    return not reasons, reasons


def arbitrate_subsystem_proposals(
    proposals: list[CalibrationSubsystemProposal],
    *,
    max_selected_agents: int = DEFAULT_MAX_SELECTED_AGENTS,
    min_support_strength: float = DEFAULT_MIN_SUPPORT_STRENGTH,
) -> tuple[list[CalibrationSubsystemProposal], CalibrationArbitrationRecord]:
    ordered = sorted(
        proposals,
        key=lambda item: _safe_float(item.get("recommendation_strength"), 0.0),
        reverse=True,
    )
    runnable = [proposal for proposal in ordered if proposal.get("should_run")]
    selected: list[CalibrationSubsystemProposal] = []
    rejected_agents: list[dict[str, Any]] = []
    compatibility_notes: list[dict[str, Any]] = []

    if runnable:
        selected.append(runnable[0])
        compatibility_notes.append(
            {
                "agent": runnable[0]["agent"],
                "reason": "selected as the highest-strength runnable subsystem proposal",
            }
        )

    for proposal in runnable[1:]:
        if len(selected) >= max(1, max_selected_agents):
            rejected_agents.append(
                {
                    "agent": str(proposal.get("agent")),
                    "reason": "selection cap reached for the current bounded Phase C bundle",
                }
            )
            continue
        strength = _safe_float(proposal.get("recommendation_strength"), 0.0)
        if strength < min_support_strength:
            rejected_agents.append(
                {
                    "agent": str(proposal.get("agent")),
                    "reason": f"recommendation strength {strength:.3f} is below the current support threshold",
                }
            )
            continue

        compatible, reasons = _compatible_with_selected(selected, proposal)
        if compatible:
            selected.append(proposal)
            compatibility_notes.append(
                {
                    "agent": proposal["agent"],
                    "reason": "selected as a compatible supporting subsystem seam",
                }
            )
        else:
            rejected_agents.append(
                {
                    "agent": str(proposal.get("agent")),
                    "reason": "; ".join(reasons),
                }
            )

    for proposal in ordered:
        if proposal in selected or proposal.get("should_run"):
            continue
        rejected_agents.append(
            {
                "agent": str(proposal.get("agent")),
                "reason": "proposal is held because the seam is already marked saturated or unsafe",
            }
        )

    selected_agents = [str(item.get("agent")) for item in selected]
    merged_target_scope = _normalize_text(selected[0].get("target_scope") if selected else "")
    merged_optimization_strategy = _merge_optimization_strategy(
        [_normalize_text(item.get("optimization_strategy")) for item in selected]
    ) or "vmax_then_km"
    selected_hypotheses = [_normalize_text(item.get("hypothesis")) for item in selected]
    if len(selected) > 1:
        arbitration_summary = (
            f"Selected a bounded coalition of {', '.join(selected_agents)} because they share the same phase/target "
            f"seam and open a stronger basin together than either one alone."
        )
    elif selected:
        arbitration_summary = (
            f"Selected only {selected_agents[0]} because every other runnable subsystem either conflicts with it, "
            f"overlaps the same parameter seam, or falls below the support threshold."
        )
    else:
        arbitration_summary = "No runnable subsystem proposal was available; manual review is required."

    arbitration: CalibrationArbitrationRecord = {
        "selected_agents": selected_agents,
        "selected_hypotheses": selected_hypotheses,
        "selected_stage_count": len(selected),
        "merged_target_scope": merged_target_scope,
        "merged_optimization_strategy": merged_optimization_strategy,
        "arbitration_summary": arbitration_summary,
        "rejected_agents": rejected_agents,
        "compatibility_notes": compatibility_notes,
    }
    return selected, arbitration


def build_phase_c_stage_plan_request(
    selected: list[CalibrationSubsystemProposal],
    state: HermesCalibrationState,
    arbitration: CalibrationArbitrationRecord,
    args: dict[str, Any],
) -> dict[str, Any]:
    protected_metabolites = [str(item) for item in state.get("protected_metabolites") or []]
    comparison_summary = state.get("comparison_summary", {})
    seed = int(args.get("seed", comparison_summary.get("seed") or 29))
    t_max = float(args.get("tMax", comparison_summary.get("t_max") or 42.0))
    curve_fit_strength = float(
        args.get(
            "curveFitStrength",
            comparison_summary.get("curve_fit_strength") or 0.1,
        )
    )
    stages: list[dict[str, Any]] = []
    for proposal in selected:
        phase = int(proposal.get("phase") or 1)
        target_scope = _normalize_text(proposal.get("target_scope") or arbitration.get("merged_target_scope"))
        stage_name = f"phase{phase}_{proposal['agent']}"
        stages.append(
            {
                "name": stage_name,
                "phases": [phase],
                "paramScope": "all" if phase == 2 else str(args.get("paramScope") or target_scope),
                "targetScope": target_scope,
                "parameters": list(proposal.get("allowed_parameters") or []),
                "nTrials": int(args.get("nTrials", 8)),
                "globalTrials": int(args.get("globalTrials", 0)),
                "seed": seed,
                "atpFocus": bool(args.get("atpFocus", True)),
                "atpFloor": float(args.get("atpFloor", 0.15)),
                "adpFloor": float(args.get("adpFloor", 0.05)),
                "ampFloor": float(args.get("ampFloor", 0.04)),
                "impFloor": float(args.get("impFloor", 0.02)),
                "adenylateTarget": float(args.get("adenylateTarget", 0.65)),
                "atpPenaltyWeight": float(args.get("atpPenaltyWeight", 8.0)),
                "ampPenaltyWeight": float(args.get("ampPenaltyWeight", 6.0)),
                "impPenaltyWeight": float(args.get("impPenaltyWeight", 5.0)),
                "poolPenaltyWeight": float(args.get("poolPenaltyWeight", 10.0)),
                "curveFitStrength": curve_fit_strength,
                "tMax": t_max,
            }
        )

    if len(selected) == 1:
        hypothesis = _normalize_text(selected[0].get("hypothesis")) or "Bounded calibration follow-up"
    else:
        hypothesis = " + ".join(_normalize_text(item.get("agent")) for item in selected if item.get("agent"))

    return {
        "seedParamsPath": state["seed_params_path"],
        "hypothesis": hypothesis,
        "targetScope": _normalize_text(arbitration.get("merged_target_scope") or state.get("target_scope")),
        "optimizationStrategy": _normalize_text(
            arbitration.get("merged_optimization_strategy") or state.get("optimization_strategy")
        ),
        "protect": protected_metabolites,
        "subsystemProposals": state.get("subsystem_proposals") or [],
        "stages": stages,
        "generatedBy": str(args.get("generatedBy") or "hermes_phase_c_arbiter"),
        "outPath": args.get("outPath"),
        "overwrite": bool(args.get("overwrite", False)),
    }


def coordinate_phase_c(
    artifact_summary: dict[str, Any],
    trajectory_summary: dict[str, Any],
    candidate_history: dict[str, Any],
    args: dict[str, Any],
) -> dict[str, Any]:
    phase_a_result = coordinate_phase_a(
        artifact_summary=artifact_summary,
        trajectory_summary=trajectory_summary,
        candidate_history=candidate_history,
        args=args,
    )
    state = dict(phase_a_result["state"])
    proposals = list(phase_a_result["coordinator_payload"]["subsystem_proposals"])
    max_selected_agents = int(args.get("maxSelectedAgents", DEFAULT_MAX_SELECTED_AGENTS))
    min_support_strength = float(args.get("minSupportStrength", DEFAULT_MIN_SUPPORT_STRENGTH))

    selected, arbitration = arbitrate_subsystem_proposals(
        proposals,
        max_selected_agents=max_selected_agents,
        min_support_strength=min_support_strength,
    )

    selected_agents = [str(item.get("agent")) for item in selected]
    state["subsystem_proposals"] = proposals
    state["selected_subsystem_agents"] = selected_agents
    state["rejected_subsystem_agents"] = arbitration.get("rejected_agents", [])
    state["arbitration"] = arbitration
    state["active_hypothesis"] = (
        " / ".join(_normalize_text(item.get("hypothesis")) for item in selected if item.get("hypothesis"))
        or str(phase_a_result["state"].get("active_hypothesis") or "")
    )

    stage_plan_request = build_phase_c_stage_plan_request(
        selected=selected,
        state=state,
        arbitration=arbitration,
        args=args,
    )
    decision_summary = str(arbitration.get("arbitration_summary") or "")
    state["decision"] = "ready_for_phase_b"
    state["decision_reason"] = decision_summary

    coordinator_payload = {
        "active_hypothesis": state["active_hypothesis"],
        "decision_summary": decision_summary,
        "selected_subsystem_agents": selected_agents,
        "selected_subsystem_proposals": selected,
        "rejected_subsystem_agents": arbitration.get("rejected_agents", []),
        "protected_metabolites": state.get("protected_metabolites") or [],
        "subsystem_proposals": proposals,
        "stage_plan_request": stage_plan_request,
        "arbitration": arbitration,
        "phase_a_selected_proposal": phase_a_result["selected_proposal"],
    }

    return {
        "state": state,
        "known_saturated_seams": phase_a_result["known_saturated_seams"],
        "artifact_summary": artifact_summary,
        "trajectory_summary": trajectory_summary,
        "candidate_history": candidate_history,
        "coordinator_user_prompt": build_calibration_coordinator_user_prompt(state),
        "coordinator_payload": coordinator_payload,
        "selected_proposals": selected,
        "selected_proposal": selected[0] if selected else phase_a_result["selected_proposal"],
        "phase_a_result": phase_a_result,
    }
