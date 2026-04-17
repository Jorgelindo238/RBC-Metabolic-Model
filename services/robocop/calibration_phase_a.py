from __future__ import annotations

from typing import Any

from services.robocop.calibration_prompts import build_calibration_coordinator_user_prompt
from services.robocop.calibration_state import (
    CalibrationSubsystemProposal,
    HermesCalibrationState,
)


DEFAULT_PRIORITY_GROUPS = ["extracellular", "energy", "pyruvate_axis"]
DEFAULT_PROTECTED_METABOLITES = ["ATP", "ADP", "EGLC", "ELAC", "LAC"]

SUBSYSTEM_KEYWORDS: dict[str, list[str]] = {
    "glucose_commitment": ["hexose", "glucose_shape", "upstream_hexose", "glucose_side"],
    "extracellular_transport": ["eglc", "extracellular", "transport", "glucose_side_followup"],
    "lower_glycolysis": ["lower_glyco", "lower_glycolysis", "pgm", "23dpg", "buffered"],
    "pyruvate_lactate_outlet": ["elac_recovery", "elac_rebalance", "downstream_recovery", "pyr", "lac", "ldh"],
    "adenylate": ["adenylate", "vak", "hybrid_long_horizon_phase2_only"],
    "purine_salvage": ["purine", "imph", "ampd", "ndpk"],
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _row_by_name(group_metrics: dict[str, list[dict[str, Any]]], group: str, name: str) -> dict[str, Any] | None:
    for row in group_metrics.get(group, []):
        if str(row.get("name", "")).upper() == name.upper():
            return row
    return None


def _ode_row(pure_ode: dict[str, Any], group: str, name: str) -> dict[str, Any] | None:
    return pure_ode.get("groups", {}).get(group, {}).get(name)


def _normalize_saturated_input(raw: Any) -> list[dict[str, Any]]:
    seams: list[dict[str, Any]] = []
    for item in raw or []:
        if isinstance(item, str):
            text = item.strip()
            if text:
                seams.append({"agent": text, "reason": "explicit_input", "seam_status": "saturated"})
        elif isinstance(item, dict):
            seams.append(dict(item))
    return seams


def infer_saturated_seams(candidate_history: dict[str, Any], explicit: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    saturated = _normalize_saturated_input(explicit)
    seen = {(entry.get("agent"), entry.get("reason")) for entry in saturated}

    for run in candidate_history.get("runs", []):
        run_dir = str(run.get("runDir", "")).lower()
        report_path = str(run.get("reportPath", "")).lower()
        run_text = f"{run_dir} {report_path}"
        improvement = _safe_float(run.get("improvement_pct"), default=0.0)
        if improvement > 0.05:
            continue
        for agent, keywords in SUBSYSTEM_KEYWORDS.items():
            if any(keyword in run_text for keyword in keywords):
                key = (agent, "history_saturated")
                if key in seen:
                    continue
                seen.add(key)
                saturated.append(
                    {
                        "agent": agent,
                        "reason": "history_saturated",
                        "source_run": run.get("runDir") or run.get("reportPath"),
                        "improvement_pct": improvement,
                        "seam_status": "saturated",
                    }
                )
    return saturated


def _is_saturated(agent: str, saturated: list[dict[str, Any]]) -> bool:
    for seam in saturated:
        if str(seam.get("agent", "")).strip().lower() == agent.lower():
            return True
    return False


def _proposal(
    *,
    agent: str,
    hypothesis: str,
    reasoning: str,
    tradeoff_note: str,
    phase: int,
    target_scope: str,
    optimization_strategy: str,
    target_metabolites: list[str],
    allowed_parameters: list[str],
    expected_gain: list[str],
    risk_metabolites: list[str],
    protect_metabolites: list[str],
    conflicts_with: list[str],
    strength: float,
    saturated: bool,
) -> CalibrationSubsystemProposal:
    return {
        "agent": agent,
        "hypothesis": hypothesis,
        "reasoning": reasoning,
        "tradeoff_note": tradeoff_note,
        "phase": phase,
        "target_scope": target_scope,
        "optimization_strategy": optimization_strategy,
        "target_metabolites": target_metabolites,
        "allowed_parameters": allowed_parameters,
        "expected_gain": expected_gain,
        "risk_metabolites": risk_metabolites,
        "protect_metabolites": protect_metabolites,
        "conflicts_with": conflicts_with,
        "recommendation": "hold" if saturated else "run",
        "seam_status": "saturated" if saturated else "open",
        "recommendation_strength": max(0.0, min(1.0, strength)),
        "should_run": not saturated,
    }


def assemble_subsystem_proposals(
    artifact_summary: dict[str, Any],
    trajectory_summary: dict[str, Any],
    known_saturated_seams: list[dict[str, Any]],
    protected_metabolites: list[str],
) -> list[CalibrationSubsystemProposal]:
    group_metrics = artifact_summary.get("group_metrics", {})
    pure_ode = trajectory_summary if trajectory_summary.get("available") else artifact_summary.get("pure_ode", {}) or {}

    eglc_row = _row_by_name(group_metrics, "extracellular", "EGLC") or {}
    elac_row = _row_by_name(group_metrics, "extracellular", "ELAC") or {}
    atp_row = _row_by_name(group_metrics, "energy", "ATP") or {}
    adp_row = _row_by_name(group_metrics, "energy", "ADP") or {}
    amp_row = _row_by_name(group_metrics, "energy", "AMP") or {}
    imp_row = _row_by_name(group_metrics, "energy", "IMP") or {}
    glc_row = _row_by_name(group_metrics, "extracellular", "GLC") or _row_by_name(group_metrics, "glucose_axis", "GLC") or {}
    lac_row = _row_by_name(group_metrics, "extracellular", "LAC") or _row_by_name(group_metrics, "pyruvate_axis", "LAC") or {}
    pyr_row = _row_by_name(group_metrics, "pyruvate_axis", "PYR") or {}
    pep_row = _row_by_name(group_metrics, "pyruvate_axis", "PEP") or {}
    g6p_row = _row_by_name(group_metrics, "glucose_axis", "G6P") or {}
    f6p_row = _row_by_name(group_metrics, "glucose_axis", "F6P") or {}

    eglc_ode = _ode_row(pure_ode, "extracellular", "EGLC") or {}
    elac_ode = _ode_row(pure_ode, "extracellular", "ELAC") or {}
    atp_ode = _ode_row(pure_ode, "energy", "ATP") or {}
    adp_ode = _ode_row(pure_ode, "energy", "ADP") or {}
    amp_ode = _ode_row(pure_ode, "energy", "AMP") or {}
    imp_ode = _ode_row(pure_ode, "energy", "IMP") or {}
    pyr_ode = _ode_row(pure_ode, "pyruvate_axis", "PYR") or {}
    lac_ode = _ode_row(pure_ode, "pyruvate_axis", "LAC") or {}

    eglc_shallow = _safe_float(eglc_ode.get("pct_delta"), 0.0) > -15.0
    atp_collapse = atp_ode.get("shape") == "collapse"
    adp_collapse = adp_ode.get("shape") == "collapse"
    amp_rising = amp_ode.get("shape") == "rising"
    imp_collapse = imp_ode.get("shape") == "collapse"
    pyr_spike = (
        _safe_float(pyr_ode.get("max"), 0.0)
        > 1.5 * max(_safe_float(pyr_ode.get("end"), 0.0), 1e-9)
    )
    lac_falling = lac_ode.get("shape") == "falling"
    elac_soft = _safe_float(elac_row.get("nrmse")) > 0.2 or elac_ode.get("shape") != "rising"

    proposals: list[CalibrationSubsystemProposal] = []

    proposals.append(
        _proposal(
            agent="adenylate",
            hypothesis="Adenylate exchange is still letting ATP and ADP collapse in the pure ODE.",
            reasoning=(
                "ATP/ADP collapse is still present in the pure ODE, so the next bounded move should reopen "
                "adenylate coupling rather than another nearby glucose seam."
            ),
            tradeoff_note="Could soften glucose or PYR/LAC gains if the adenylate pool is overcompensated.",
            phase=2,
            target_scope="core_glycolysis_energy",
            optimization_strategy="vmax_then_km",
            target_metabolites=["ATP", "ADP", "AMP", "IMP"],
            allowed_parameters=["vmax_VAK", "vmax_VAK2", "vmax_VAK_rev", "km_ADP_ATP"],
            expected_gain=["retain_ATP", "retain_ADP", "reduce_AMP_overaccumulation"],
            risk_metabolites=["EGLC", "ELAC", "PYR"],
            protect_metabolites=protected_metabolites,
            conflicts_with=[],
            strength=0.35 + (0.28 if atp_collapse else 0.0) + (0.25 if adp_collapse else 0.0) + min(0.12, _safe_float(atp_row.get("nrmse")) / 5.0),
            saturated=_is_saturated("adenylate", known_saturated_seams),
        )
    )

    proposals.append(
        _proposal(
            agent="purine_salvage",
            hypothesis="Purine salvage imbalance is amplifying AMP/IMP drift and destabilizing the energy quartet.",
            reasoning=(
                "AMP rise or IMP collapse suggests the purine seam may still be distorting the energy block "
                "even when the glucose-side fit is strong."
            ),
            tradeoff_note="Can improve AMP/IMP while leaving ATP/ADP unchanged if adenylate exchange is the dominant bottleneck.",
            phase=2,
            target_scope="core_glycolysis_energy",
            optimization_strategy="vmax_only",
            target_metabolites=["AMP", "IMP", "ATP", "ADP"],
            allowed_parameters=["vmax_VAMPD1", "vmax_VIMPH", "vmax_VNDPK", "vmax_VNDPK_rev"],
            expected_gain=["reduce_AMP_accumulation", "retain_IMP", "stabilize_purine_pool"],
            risk_metabolites=["ATP", "ADP"],
            protect_metabolites=protected_metabolites,
            conflicts_with=[],
            strength=0.18 + (0.2 if amp_rising else 0.0) + (0.18 if imp_collapse else 0.0) + min(0.12, _safe_float(amp_row.get("nrmse")) / 8.0),
            saturated=_is_saturated("purine_salvage", known_saturated_seams),
        )
    )

    proposals.append(
        _proposal(
            agent="extracellular_transport",
            hypothesis="Extracellular transport remains the most direct lever on the shallow EGLC and underpowered ELAC trajectories.",
            reasoning=(
                "EGLC is still shallow in the pure ODE or ELAC remains soft, so the transport seam is still a plausible "
                "way to preserve directionality while sharpening extracellular shape."
            ),
            tradeoff_note="This seam may reproduce a previously saturated glucose basin if the current seed already contains the useful transport move.",
            phase=1,
            target_scope="glycolysis_extracellular",
            optimization_strategy="vmax_then_km",
            target_metabolites=["EGLC", "ELAC", "GLC", "LAC"],
            allowed_parameters=["vmax_VEGLC", "vmax_VELAC", "km_EGLC", "km_GLC_transport", "km_LAC"],
            expected_gain=["steeper_EGLC", "stronger_ELAC_export"],
            risk_metabolites=["ATP", "PYR", "LAC"],
            protect_metabolites=protected_metabolites,
            conflicts_with=["glucose_commitment", "pyruvate_lactate_outlet"],
            strength=0.18 + (0.16 if eglc_shallow else 0.0) + min(0.16, _safe_float(eglc_row.get("nrmse"))) + min(0.12, _safe_float(elac_row.get("nrmse")) / 2.0),
            saturated=_is_saturated("extracellular_transport", known_saturated_seams),
        )
    )

    proposals.append(
        _proposal(
            agent="glucose_commitment",
            hypothesis="Upstream glucose commitment is still shaping the late EGLC plateau through HK/PFK framing.",
            reasoning=(
                "If EGLC remains shallow while glucose-axis intermediates are still off-target, the next bounded seam "
                "is the glucose commitment / hexose framing pocket."
            ),
            tradeoff_note="Can improve glucose draw while making ELAC or ATP worse if the commitment step over-pulls carbon.",
            phase=1,
            target_scope="glycolysis_extracellular",
            optimization_strategy="km_only",
            target_metabolites=["EGLC", "GLC", "G6P", "F6P"],
            allowed_parameters=["vmax_VHK", "vmax_VPFK", "km_GLC_HK", "km_G6P", "km_F6P"],
            expected_gain=["steeper_EGLC", "better_hexose_shape"],
            risk_metabolites=["ATP", "ELAC"],
            protect_metabolites=protected_metabolites,
            conflicts_with=["extracellular_transport"],
            strength=0.16 + (0.14 if eglc_shallow else 0.0) + min(0.1, _safe_float(glc_row.get("nrmse")) / 4.0) + min(0.08, _safe_float(g6p_row.get("nrmse")) / 6.0) + min(0.08, _safe_float(f6p_row.get("nrmse")) / 6.0),
            saturated=_is_saturated("glucose_commitment", known_saturated_seams),
        )
    )

    proposals.append(
        _proposal(
            agent="lower_glycolysis",
            hypothesis="Lower glycolysis still controls the coupled P3G/PEP/PYR tension that feeds ATP and extracellular lactate behavior.",
            reasoning=(
                "If PYR or PEP remain structurally strained, a lower-glycolysis seam can sometimes open a new fit basin "
                "after the glucose-side seams have saturated."
            ),
            tradeoff_note="Historically this seam can improve ATP and extracellular anchors while breaking PEP/PYR if it is too free.",
            phase=1,
            target_scope="glycolysis_extracellular",
            optimization_strategy="vmax_only",
            target_metabolites=["P3G", "P2G", "PEP", "PYR", "B23PG"],
            allowed_parameters=["vmax_VPGM", "vmax_VENOPGM", "vmax_VDPGM", "vmax_V23DPGP", "vmax_VPK"],
            expected_gain=["reduce_PYR_spike", "stabilize_lower_glycolysis", "support_ATP"],
            risk_metabolites=["PEP", "ELAC", "B23PG"],
            protect_metabolites=protected_metabolites,
            conflicts_with=["pyruvate_lactate_outlet"],
            strength=0.14 + (0.18 if pyr_spike else 0.0) + min(0.14, _safe_float(pyr_row.get("nrmse")) / 4.0) + min(0.08, _safe_float(pep_row.get("nrmse")) / 4.0),
            saturated=_is_saturated("lower_glycolysis", known_saturated_seams),
        )
    )

    proposals.append(
        _proposal(
            agent="pyruvate_lactate_outlet",
            hypothesis="The PYR/LAC outlet seam is still shaping the long-horizon pyruvate rebound and lactate loss.",
            reasoning=(
                "If PYR spikes transiently or LAC falls late, the LDH/outlet seam is the most direct narrow recovery set."
            ),
            tradeoff_note="This seam often saturates quickly once the lower-glycolysis block is already tuned.",
            phase=1,
            target_scope="glycolysis_extracellular",
            optimization_strategy="vmax_then_km",
            target_metabolites=["PYR", "LAC", "ELAC", "PEP"],
            allowed_parameters=["vmax_VLDH", "km_PYR", "km_LAC", "km_PEP"],
            expected_gain=["reduce_PYR_spike", "retain_LAC_accumulation", "recover_ELAC"],
            risk_metabolites=["EGLC", "ATP"],
            protect_metabolites=protected_metabolites,
            conflicts_with=["lower_glycolysis", "extracellular_transport"],
            strength=0.16 + (0.16 if pyr_spike else 0.0) + (0.12 if lac_falling else 0.0) + (0.06 if elac_soft else 0.0) + min(0.08, _safe_float(lac_row.get("nrmse")) / 4.0),
            saturated=_is_saturated("pyruvate_lactate_outlet", known_saturated_seams),
        )
    )

    proposals.sort(key=lambda item: float(item.get("recommendation_strength", 0.0)), reverse=True)
    return proposals


def choose_proposal(proposals: list[CalibrationSubsystemProposal]) -> tuple[CalibrationSubsystemProposal, list[dict[str, str]]]:
    runnable = [proposal for proposal in proposals if proposal.get("should_run")]
    selected = runnable[0] if runnable else proposals[0]

    rejected = []
    for proposal in proposals:
        if proposal is selected:
            continue
        reason = "Lower recommendation strength than the selected seam."
        if not proposal.get("should_run"):
            reason = "Proposal is currently marked saturated and is held back for manual review."
        rejected.append({"agent": str(proposal.get("agent")), "reason": reason})
    return selected, rejected


def build_stage_plan_request(
    selected: CalibrationSubsystemProposal,
    subsystem_proposals: list[CalibrationSubsystemProposal],
    state: HermesCalibrationState,
    args: dict[str, Any],
) -> dict[str, Any]:
    target_scope = str(selected.get("target_scope") or state.get("target_scope") or "glycolysis_extracellular")
    optimization_strategy = str(selected.get("optimization_strategy") or state.get("optimization_strategy") or "vmax_then_km")
    phase = int(selected.get("phase") or 1)
    hypothesis = str(selected.get("hypothesis") or state.get("active_hypothesis") or "Bounded calibration follow-up")
    protected_metabolites = [str(item) for item in state.get("protected_metabolites") or DEFAULT_PROTECTED_METABOLITES]
    comparison_summary = state.get("comparison_summary", {})
    seed = int(args.get("seed", comparison_summary.get("seed") or 29))
    n_trials = int(args.get("nTrials", 8))
    global_trials = int(args.get("globalTrials", 0))
    stage_name = str(args.get("stageName") or f"phase{phase}_{selected['agent']}")
    t_max = float(args.get("tMax", comparison_summary.get("t_max") or 42.0))
    curve_fit_strength = float(args.get("curveFitStrength", comparison_summary.get("curve_fit_strength") or 0.1))

    param_scope = "all" if phase == 2 else str(args.get("paramScope") or target_scope)
    stage = {
        "name": stage_name,
        "phases": [phase],
        "paramScope": param_scope,
        "targetScope": target_scope,
        "parameters": list(selected.get("allowed_parameters") or []),
        "nTrials": n_trials,
        "globalTrials": global_trials,
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

    return {
        "seedParamsPath": state["seed_params_path"],
        "hypothesis": hypothesis,
        "targetScope": target_scope,
        "optimizationStrategy": optimization_strategy,
        "protect": protected_metabolites,
        "subsystemProposals": subsystem_proposals,
        "stages": [stage],
        "generatedBy": str(args.get("generatedBy") or "hermes_phase_a_coordinator"),
        "outPath": args.get("outPath"),
        "overwrite": bool(args.get("overwrite", False)),
    }


def build_phase_a_state(
    artifact_summary: dict[str, Any],
    trajectory_summary: dict[str, Any],
    known_saturated_seams: list[dict[str, Any]],
    protected_metabolites: list[str],
    priority_groups: list[str],
) -> HermesCalibrationState:
    source = artifact_summary.get("source", {})
    run = artifact_summary.get("run", {})
    return {
        "workflow_type": "hermes_calibration_phase_a",
        "workflow_name": "Hermes Calibration Phase A",
        "orchestration_runtime": "hermes_calibration_phase_a_v1",
        "seed_params_path": str(source.get("bestParamsPath") or ""),
        "seed_report_path": str(source.get("reportPath") or ""),
        "seed_main_ode_csv_path": str((trajectory_summary or {}).get("csvPath") or source.get("odeCsvPath") or ""),
        "seed_artifacts": {
            "report_path": str(source.get("reportPath") or ""),
            "run_dir": str(source.get("runDir") or ""),
            "best_params_path": str(source.get("bestParamsPath") or ""),
            "results_tsv_path": str(source.get("resultsTsvPath") or ""),
            "main_ode_csv_path": str((trajectory_summary or {}).get("csvPath") or source.get("odeCsvPath") or ""),
        },
        "target_scope": str(run.get("target_scope") or ""),
        "optimization_strategy": str(run.get("optimization_strategy") or ""),
        "priority_groups": priority_groups,
        "protected_metabolites": protected_metabolites,
        "known_saturated_seams": known_saturated_seams,
        "comparison_summary": {
            "seed": run.get("seed"),
            "t_max": run.get("t_max"),
            "curve_fit_strength": run.get("curve_fit_strength"),
            "baseline_loss": artifact_summary.get("objective", {}).get("baseline_loss"),
            "final_loss": artifact_summary.get("objective", {}).get("final_loss"),
            "improvement_pct": artifact_summary.get("objective", {}).get("improvement_pct"),
        },
        "promotion_status": "seed",
    }


def coordinate_phase_a(
    artifact_summary: dict[str, Any],
    trajectory_summary: dict[str, Any],
    candidate_history: dict[str, Any],
    args: dict[str, Any],
) -> dict[str, Any]:
    priority_groups = [str(item) for item in args.get("priorityGroups") or DEFAULT_PRIORITY_GROUPS]
    protected_metabolites = [str(item) for item in args.get("protectedMetabolites") or DEFAULT_PROTECTED_METABOLITES]
    known_saturated_seams = infer_saturated_seams(
        candidate_history=candidate_history,
        explicit=args.get("knownSaturatedSeams"),
    )
    state = build_phase_a_state(
        artifact_summary=artifact_summary,
        trajectory_summary=trajectory_summary,
        known_saturated_seams=known_saturated_seams,
        protected_metabolites=protected_metabolites,
        priority_groups=priority_groups,
    )
    proposals = assemble_subsystem_proposals(
        artifact_summary=artifact_summary,
        trajectory_summary=trajectory_summary,
        known_saturated_seams=known_saturated_seams,
        protected_metabolites=protected_metabolites,
    )
    selected, rejected = choose_proposal(proposals)
    state["subsystem_proposals"] = proposals
    state["active_hypothesis"] = str(selected.get("hypothesis") or "")

    stage_plan_request = build_stage_plan_request(
        selected=selected,
        subsystem_proposals=proposals,
        state=state,
        args=args,
    )

    decision_summary = (
        f"Selected {selected['agent']} as the next bounded seam because it currently has the strongest "
        f"fit-first / pure-ODE signal while avoiding already saturated pockets."
    )

    coordinator_payload = {
        "active_hypothesis": state["active_hypothesis"],
        "decision_summary": decision_summary,
        "selected_subsystem_agents": [selected["agent"]],
        "rejected_subsystem_agents": rejected,
        "protected_metabolites": protected_metabolites,
        "subsystem_proposals": proposals,
        "stage_plan_request": stage_plan_request,
    }

    return {
        "state": state,
        "known_saturated_seams": known_saturated_seams,
        "artifact_summary": artifact_summary,
        "trajectory_summary": trajectory_summary,
        "candidate_history": candidate_history,
        "coordinator_user_prompt": build_calibration_coordinator_user_prompt(state),
        "coordinator_payload": coordinator_payload,
        "selected_proposal": selected,
    }
