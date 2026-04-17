from __future__ import annotations

from typing import Any

from services.robocop.calibration_state import (
    CalibrationCoordinatorPromptContract,
    CalibrationSubsystemName,
)


CALIBRATION_COORDINATOR_CONTRACT_VERSION = 1

CALIBRATION_SUBSYSTEM_NAMES: list[CalibrationSubsystemName] = [
    "glucose_commitment",
    "extracellular_transport",
    "lower_glycolysis",
    "pyruvate_lactate_outlet",
    "adenylate",
    "purine_salvage",
]

CALIBRATION_SUBSYSTEM_PROPOSAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "agent",
        "hypothesis",
        "reasoning",
        "phase",
        "target_scope",
        "optimization_strategy",
        "target_metabolites",
        "allowed_parameters",
        "expected_gain",
        "risk_metabolites",
        "protect_metabolites",
        "recommendation",
        "seam_status",
        "recommendation_strength",
        "should_run",
    ],
    "properties": {
        "agent": {"type": "string", "enum": CALIBRATION_SUBSYSTEM_NAMES},
        "hypothesis": {"type": "string", "minLength": 1},
        "reasoning": {"type": "string", "minLength": 1},
        "tradeoff_note": {"type": "string"},
        "phase": {"type": "integer", "minimum": 1, "maximum": 3},
        "target_scope": {"type": "string", "minLength": 1},
        "optimization_strategy": {"type": "string", "minLength": 1},
        "target_metabolites": {"type": "array", "items": {"type": "string"}},
        "allowed_parameters": {"type": "array", "items": {"type": "string"}},
        "expected_gain": {"type": "array", "items": {"type": "string"}},
        "risk_metabolites": {"type": "array", "items": {"type": "string"}},
        "protect_metabolites": {"type": "array", "items": {"type": "string"}},
        "conflicts_with": {
            "type": "array",
            "items": {"type": "string", "enum": CALIBRATION_SUBSYSTEM_NAMES},
        },
        "recommendation": {"type": "string", "enum": ["run", "hold", "reject"]},
        "seam_status": {"type": "string", "enum": ["new", "open", "saturated", "dangerous"]},
        "recommendation_strength": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "should_run": {"type": "boolean"},
    },
}

CALIBRATION_STAGE_PLAN_STAGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["name", "phases"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "phases": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "integer", "minimum": 1, "maximum": 3},
        },
        "paramScope": {"type": "string"},
        "targetScope": {"type": "string"},
        "parameterClasses": {"type": "array", "items": {"type": "string"}},
        "identifiabilityLevels": {"type": "array", "items": {"type": "string"}},
        "parameters": {"type": "array", "items": {"type": "string"}},
        "includeParams": {"type": "array", "items": {"type": "string"}},
        "excludeParams": {"type": "array", "items": {"type": "string"}},
        "nTrials": {"type": "integer", "minimum": 1},
        "globalTrials": {"type": "integer", "minimum": 0},
        "seed": {"type": "integer"},
        "atpFocus": {"type": "boolean"},
        "atpFloor": {"type": "number", "minimum": 0.0},
        "adpFloor": {"type": "number", "minimum": 0.0},
        "ampFloor": {"type": "number", "minimum": 0.0},
        "impFloor": {"type": "number", "minimum": 0.0},
        "adenylateTarget": {"type": "number", "minimum": 0.0},
        "atpPenaltyWeight": {"type": "number", "minimum": 0.0},
        "ampPenaltyWeight": {"type": "number", "minimum": 0.0},
        "impPenaltyWeight": {"type": "number", "minimum": 0.0},
        "poolPenaltyWeight": {"type": "number", "minimum": 0.0},
        "curveFitStrength": {"type": "number", "minimum": 0.0},
        "tMax": {"type": "number", "minimum": 0.0},
    },
}

CALIBRATION_STAGE_PLAN_WRITE_REQUEST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["seedParamsPath", "hypothesis", "stages"],
    "properties": {
        "seedParamsPath": {"type": "string", "minLength": 1},
        "hypothesis": {"type": "string", "minLength": 1},
        "targetScope": {"type": "string"},
        "optimizationStrategy": {"type": "string"},
        "protect": {"type": "array", "items": {"type": "string"}},
        "subsystemProposals": {
            "type": "array",
            "items": CALIBRATION_SUBSYSTEM_PROPOSAL_SCHEMA,
        },
        "stages": {
            "type": "array",
            "minItems": 1,
            "items": CALIBRATION_STAGE_PLAN_STAGE_SCHEMA,
        },
        "generatedBy": {"type": "string"},
        "outPath": {"type": "string"},
        "overwrite": {"type": "boolean"},
    },
}

CALIBRATION_COORDINATOR_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "active_hypothesis",
        "decision_summary",
        "selected_subsystem_agents",
        "protected_metabolites",
        "subsystem_proposals",
        "stage_plan_request",
    ],
    "properties": {
        "active_hypothesis": {"type": "string", "minLength": 1},
        "decision_summary": {"type": "string", "minLength": 1},
        "selected_subsystem_agents": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "enum": CALIBRATION_SUBSYSTEM_NAMES},
        },
        "rejected_subsystem_agents": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["agent", "reason"],
                "properties": {
                    "agent": {"type": "string", "enum": CALIBRATION_SUBSYSTEM_NAMES},
                    "reason": {"type": "string", "minLength": 1},
                },
            },
        },
        "protected_metabolites": {"type": "array", "items": {"type": "string"}},
        "subsystem_proposals": {
            "type": "array",
            "minItems": 1,
            "items": CALIBRATION_SUBSYSTEM_PROPOSAL_SCHEMA,
        },
        "stage_plan_request": CALIBRATION_STAGE_PLAN_WRITE_REQUEST_SCHEMA,
    },
}

CALIBRATION_ARBITRATION_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "active_hypothesis",
        "decision_summary",
        "selected_subsystem_agents",
        "selected_subsystem_proposals",
        "protected_metabolites",
        "subsystem_proposals",
        "stage_plan_request",
        "arbitration",
    ],
    "properties": {
        "active_hypothesis": {"type": "string", "minLength": 1},
        "decision_summary": {"type": "string", "minLength": 1},
        "selected_subsystem_agents": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "enum": CALIBRATION_SUBSYSTEM_NAMES},
        },
        "selected_subsystem_proposals": {
            "type": "array",
            "minItems": 1,
            "items": CALIBRATION_SUBSYSTEM_PROPOSAL_SCHEMA,
        },
        "rejected_subsystem_agents": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["agent", "reason"],
                "properties": {
                    "agent": {"type": "string", "enum": CALIBRATION_SUBSYSTEM_NAMES},
                    "reason": {"type": "string", "minLength": 1},
                },
            },
        },
        "protected_metabolites": {"type": "array", "items": {"type": "string"}},
        "subsystem_proposals": {
            "type": "array",
            "minItems": 1,
            "items": CALIBRATION_SUBSYSTEM_PROPOSAL_SCHEMA,
        },
        "stage_plan_request": CALIBRATION_STAGE_PLAN_WRITE_REQUEST_SCHEMA,
        "arbitration": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "selected_agents",
                "selected_stage_count",
                "merged_target_scope",
                "merged_optimization_strategy",
                "arbitration_summary",
            ],
            "properties": {
                "selected_agents": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string", "enum": CALIBRATION_SUBSYSTEM_NAMES},
                },
                "selected_hypotheses": {"type": "array", "items": {"type": "string"}},
                "selected_stage_count": {"type": "integer", "minimum": 1},
                "merged_target_scope": {"type": "string", "minLength": 1},
                "merged_optimization_strategy": {"type": "string", "minLength": 1},
                "arbitration_summary": {"type": "string", "minLength": 1},
                "rejected_agents": {"type": "array", "items": {"type": "object"}},
                "compatibility_notes": {"type": "array", "items": {"type": "object"}},
            },
        },
    },
}

CALIBRATION_FLUX_TEACHER_DATASET_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "dataset_path",
        "report_path",
        "ode_csv_path",
        "flux_csv_path",
        "selected_reactions",
        "matched_timepoint_count",
        "top_priority_reactions",
    ],
    "properties": {
        "dataset_path": {"type": "string", "minLength": 1},
        "report_path": {"type": "string", "minLength": 1},
        "ode_csv_path": {"type": "string", "minLength": 1},
        "flux_csv_path": {"type": "string", "minLength": 1},
        "selected_reactions": {"type": "array", "items": {"type": "string"}},
        "matched_timepoint_count": {"type": "integer", "minimum": 1},
        "top_priority_reactions": {"type": "array", "items": {"type": "string"}},
    },
}

CALIBRATION_HYBRID_MODEL_PROPOSAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "reaction",
        "priority_score",
        "target_metabolites",
        "required_state_inputs",
        "candidate_families",
        "selected_family",
        "existing_param_scope",
        "available_hybrid_parameters",
        "rationale",
        "teacher_signal",
        "recommended_teacher_objective",
        "recommended_student_objective",
    ],
    "properties": {
        "reaction": {"type": "string", "minLength": 1},
        "priority_score": {"type": "number", "minimum": 0.0},
        "target_metabolites": {"type": "array", "items": {"type": "string"}},
        "required_state_inputs": {"type": "array", "items": {"type": "string"}},
        "candidate_families": {"type": "array", "items": {"type": "string"}},
        "selected_family": {"type": "string", "minLength": 1},
        "existing_param_scope": {"type": "string", "minLength": 1},
        "available_hybrid_parameters": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string", "minLength": 1},
        "teacher_signal": {"type": "object"},
        "recommended_teacher_objective": {"type": "object"},
        "recommended_student_objective": {"type": "object"},
    },
}

CALIBRATION_FLUX_LEARNING_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "dataset",
        "proposals",
        "recommended_stage_plan_request",
        "system_hypothesis",
    ],
    "properties": {
        "dataset": CALIBRATION_FLUX_TEACHER_DATASET_SCHEMA,
        "proposals": {
            "type": "array",
            "minItems": 1,
            "items": CALIBRATION_HYBRID_MODEL_PROPOSAL_SCHEMA,
        },
        "recommended_stage_plan_request": CALIBRATION_STAGE_PLAN_WRITE_REQUEST_SCHEMA,
        "system_hypothesis": {"type": "string", "minLength": 1},
    },
}

COORDINATOR_SYSTEM_PROMPT = """You are the Hermes calibration coordinator for the RoBoCop Research workflow.

Your job is to choose exactly one bounded next calibration experiment around MM_calibration.py.

Rules:
- Fit quality against experimental curves is the primary objective.
- Pure ODE behavior from main.py is the second gate.
- Penalties, runtime, and convenience are only guardrails.
- Do not modify src/equadiff_brodbar.py, the scientific core of src/MM_calibration.py, or benchmark data.
- Treat known saturated seams as evidence, not as invitations to retry the same basin.
- Prefer one narrow seam over a broad retune.
- Protect explicitly named metabolites when proposing the next experiment.

You must return structured JSON matching the coordinator response schema.
The chosen stage plan must be executable by MM_calibration.py through --stage-plan-file.
Write only a bounded plan. Do not execute it.
"""

ARBITER_SYSTEM_PROMPT = """You are the Hermes calibration arbiter for the RoBoCop Research workflow.

Your job is to review subsystem proposals, reject saturated or conflicting seams,
select the smallest compatible coalition that still opens a new scientific basin,
and return a bounded multi-stage plan.

Rules:
- Fit quality against experimental curves is the primary objective.
- Pure ODE behavior from main.py is the second gate.
- Penalties, runtime, and convenience are only guardrails.
- Prefer one or two compatible subsystem seams over a broad retune.
- Do not merge proposals that conflict on protected metabolites or obvious seam ownership.
- Keep the scientific core untouched and write only bounded orchestration payloads.

You must return structured JSON matching the arbitration response schema.
The chosen stage plan must remain executable by MM_calibration.py through --stage-plan-file.
"""

FLUX_LEARNING_SYSTEM_PROMPT = """You are the Hermes teacher-student flux-learning coordinator for the RoBoCop Research workflow.

Your job is to learn from real ODE states plus reaction flux traces, then propose a hybrid mechanistic model.

Rules:
- Use pure curve fitting only as the teacher.
- Do not treat the pure-fitting teacher as the final production model.
- Distill teacher signals into interpretable hybrid Michaelis-Menten families.
- Prefer a small number of high-pressure reactions over a broad uncontrolled rewrite.
- Keep the proposal executable by MM_calibration.py through a bounded hybrid stage plan.
- Treat ATP, ADP, EGLC, PYR, PEP, and LAC as priority biological readouts.

You must return structured JSON matching the flux-learning response schema.
"""


def build_calibration_coordinator_prompt_contract() -> CalibrationCoordinatorPromptContract:
    return {
        "contract_type": "hermes_calibration_coordinator_prompt",
        "contract_version": CALIBRATION_COORDINATOR_CONTRACT_VERSION,
        "role": "system",
        "objective_hierarchy": [
            "improve experimental curve fit on the intended target family",
            "preserve or improve pure ODE behavior from main.py",
            "treat penalties and runtime only as guardrails",
        ],
        "required_tools": [
            "calibration_get_artifact_summary",
            "calibration_get_trajectory_group",
            "calibration_get_candidate_history",
            "calibration_write_stage_plan",
        ],
        "guarded_paths": [
            "src/equadiff_brodbar.py",
            "src/MM_calibration.py",
            "src/main.py",
        ],
        "output_schema": CALIBRATION_COORDINATOR_RESPONSE_SCHEMA,
        "system_prompt": COORDINATOR_SYSTEM_PROMPT,
    }


def build_calibration_arbiter_prompt_contract() -> CalibrationCoordinatorPromptContract:
    return {
        "contract_type": "hermes_calibration_arbiter_prompt",
        "contract_version": CALIBRATION_COORDINATOR_CONTRACT_VERSION,
        "role": "system",
        "objective_hierarchy": [
            "improve experimental curve fit on the intended target family",
            "preserve or improve pure ODE behavior from main.py",
            "treat penalties and runtime only as guardrails",
        ],
        "required_tools": [
            "calibration_get_artifact_summary",
            "calibration_get_trajectory_group",
            "calibration_get_candidate_history",
            "calibration_write_stage_plan",
            "calibration_execute_phase_b",
        ],
        "guarded_paths": [
            "src/equadiff_brodbar.py",
            "src/MM_calibration.py",
            "src/main.py",
        ],
        "output_schema": CALIBRATION_ARBITRATION_RESPONSE_SCHEMA,
        "system_prompt": ARBITER_SYSTEM_PROMPT,
    }


def build_flux_learning_prompt_contract() -> CalibrationCoordinatorPromptContract:
    return {
        "contract_type": "hermes_flux_learning_prompt",
        "contract_version": CALIBRATION_COORDINATOR_CONTRACT_VERSION,
        "role": "system",
        "objective_hierarchy": [
            "learn teacher signals from real state and flux trajectories",
            "distill teacher signals into interpretable hybrid MM families",
            "emit a bounded stage plan for student calibration",
        ],
        "required_tools": [
            "calibration_build_flux_teacher_dataset",
            "calibration_propose_hybrid_model",
            "calibration_write_stage_plan",
        ],
        "guarded_paths": [
            "src/equadiff_brodbar.py",
            "src/MM_calibration.py",
            "src/main.py",
        ],
        "output_schema": CALIBRATION_FLUX_LEARNING_RESPONSE_SCHEMA,
        "system_prompt": FLUX_LEARNING_SYSTEM_PROMPT,
    }


def build_calibration_coordinator_user_prompt(state: dict[str, Any]) -> str:
    seed_path = state.get("seed_params_path") or ""
    seed_report = state.get("seed_report_path") or ""
    ode_csv = state.get("seed_main_ode_csv_path") or ""
    target_scope = state.get("target_scope") or ""
    strategy = state.get("optimization_strategy") or ""
    protected = ", ".join(state.get("protected_metabolites") or [])
    priorities = ", ".join(state.get("priority_groups") or [])
    saturated = state.get("known_saturated_seams") or []
    proposals = state.get("subsystem_proposals") or []

    return (
        "Current calibration state:\n"
        f"- seed params: {seed_path}\n"
        f"- seed report: {seed_report}\n"
        f"- seed pure ODE CSV: {ode_csv}\n"
        f"- target scope: {target_scope}\n"
        f"- optimization strategy: {strategy}\n"
        f"- protected metabolites: {protected}\n"
        f"- priority groups: {priorities}\n"
        f"- known saturated seams: {saturated}\n"
        f"- prior subsystem proposals: {proposals}\n\n"
        "Choose one bounded next experiment, explain why it is the best next seam, "
        "and return only structured JSON matching the coordinator response schema."
    )
