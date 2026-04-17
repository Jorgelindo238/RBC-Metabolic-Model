from __future__ import annotations

from typing import Any, Literal, TypedDict


CalibrationPriorityGroup = Literal["extracellular", "energy", "glycolysis", "pyruvate_axis", "glucose_axis"]
CalibrationPromotionStatus = Literal["seed", "informative", "promote", "discard"]
CalibrationSubsystemName = Literal[
    "coordinator",
    "glucose_commitment",
    "extracellular_transport",
    "lower_glycolysis",
    "pyruvate_lactate_outlet",
    "adenylate",
    "purine_salvage",
]
CalibrationProposalDecision = Literal["run", "hold", "reject"]
CalibrationSeamStatus = Literal["new", "open", "saturated", "dangerous"]
CalibrationStagePlanStatus = Literal["draft", "ready_for_review", "ready_for_manual_run"]
CalibrationHybridFamilyName = Literal[
    "reversible_transport_gate",
    "substrate_hill_backpressure",
    "reversible_export_gate",
    "product_hill_export",
    "redox_backpressure_hill",
    "reversible_redox_gate",
    "substrate_hill_energy_backpressure",
    "energy_gate_mm_blend",
    "substrate_hill_product_backpressure",
    "product_gate_mm_blend",
]


class CalibrationArtifactRefs(TypedDict, total=False):
    report_path: str
    run_dir: str
    best_params_path: str
    results_tsv_path: str
    main_ode_csv_path: str
    main_ode_pdf_path: str


class CalibrationSubsystemProposal(TypedDict, total=False):
    agent: CalibrationSubsystemName
    hypothesis: str
    reasoning: str
    tradeoff_note: str
    phase: int
    target_scope: str
    optimization_strategy: str
    target_metabolites: list[str]
    allowed_parameters: list[str]
    expected_gain: list[str]
    risk_metabolites: list[str]
    protect_metabolites: list[str]
    conflicts_with: list[CalibrationSubsystemName]
    recommendation: CalibrationProposalDecision
    seam_status: CalibrationSeamStatus
    recommendation_strength: float
    should_run: bool


class CalibrationDecisionRecord(TypedDict, total=False):
    decision: str
    decision_reason: str
    promotion_status: CalibrationPromotionStatus
    fit_delta: float | None
    pure_ode_delta: dict[str, Any]
    protected_metabolite_status: dict[str, Any]


class CalibrationArbitrationRecord(TypedDict, total=False):
    selected_agents: list[CalibrationSubsystemName]
    selected_hypotheses: list[str]
    selected_stage_count: int
    merged_target_scope: str
    merged_optimization_strategy: str
    arbitration_summary: str
    rejected_agents: list[dict[str, Any]]
    compatibility_notes: list[dict[str, Any]]


class CalibrationSeamMemoryEntry(TypedDict, total=False):
    cycle_index: int
    agent: CalibrationSubsystemName
    hypothesis: str
    seed_params_path: str
    stage_plan_path: str
    decision: str
    seam_status: CalibrationSeamStatus
    reason: str
    carry_forward: bool
    fit_absolute_gain: float | None
    pure_ode_flags: dict[str, Any]


class CalibrationPhaseDCycleRecord(TypedDict, total=False):
    cycle_index: int
    seed_params_path: str
    seed_report_path: str
    seed_ode_csv_path: str
    known_saturated_seams: list[dict[str, Any]]
    selected_agents: list[CalibrationSubsystemName]
    stage_plan_path: str
    phase_b_decision: str
    phase_b_reason: str
    phase_b_decision_path: str
    promoted_seed: bool


class CalibrationStagePlanStage(TypedDict, total=False):
    name: str
    phases: list[int]
    param_scope: str
    target_scope: str
    parameter_classes: list[str] | None
    identifiability_levels: list[str] | None
    include_params: list[str] | None
    exclude_params: list[str] | None
    n_trials: int
    global_trials: int
    seed: int
    atp_focus: bool
    atp_floor: float
    adp_floor: float
    amp_floor: float
    imp_floor: float
    adenylate_target: float
    atp_penalty_weight: float
    amp_penalty_weight: float
    imp_penalty_weight: float
    pool_penalty_weight: float
    curve_fit_strength: float


class CalibrationStagePlanDocument(TypedDict, total=False):
    contract_type: str
    contract_version: int
    status: CalibrationStagePlanStatus
    generated_at: str
    generated_by: str
    seed_params_path: str
    active_hypothesis: str
    target_scope: str
    optimization_strategy: str
    protect: list[str]
    subsystem_proposals: list[CalibrationSubsystemProposal]
    stage_plan: list[CalibrationStagePlanStage]
    manual_run_hint: dict[str, Any]


class FluxTeacherDatasetArtifact(TypedDict, total=False):
    dataset_path: str
    report_path: str
    ode_csv_path: str
    flux_csv_path: str
    selected_reactions: list[str]
    matched_timepoint_count: int
    top_priority_reactions: list[str]


class HybridFluxProposal(TypedDict, total=False):
    reaction: str
    priority_score: float
    target_metabolites: list[str]
    required_state_inputs: list[str]
    candidate_families: list[CalibrationHybridFamilyName]
    selected_family: CalibrationHybridFamilyName
    existing_param_scope: str
    available_hybrid_parameters: list[str]
    rationale: str
    teacher_signal: dict[str, Any]
    recommended_teacher_objective: dict[str, Any]
    recommended_student_objective: dict[str, Any]


class CalibrationCoordinatorPromptContract(TypedDict, total=False):
    contract_type: str
    contract_version: int
    role: str
    objective_hierarchy: list[str]
    required_tools: list[str]
    guarded_paths: list[str]
    output_schema: dict[str, Any]
    system_prompt: str


class HermesCalibrationState(TypedDict, total=False):
    workflow_type: str
    workflow_name: str
    orchestration_runtime: str
    trace_status: dict[str, Any]
    seed_params_path: str
    seed_report_path: str
    seed_main_ode_csv_path: str
    seed_artifacts: CalibrationArtifactRefs
    active_hypothesis: str
    target_scope: str
    optimization_strategy: str
    priority_groups: list[CalibrationPriorityGroup]
    protected_metabolites: list[str]
    known_saturated_seams: list[dict[str, Any]]
    subsystem_proposals: list[CalibrationSubsystemProposal]
    selected_subsystem_agents: list[CalibrationSubsystemName]
    rejected_subsystem_agents: list[dict[str, Any]]
    arbitration: CalibrationArbitrationRecord
    candidate_stage_plan_path: str
    candidate_run_dir: str
    candidate_report_path: str
    candidate_main_ode_csv_path: str
    candidate_phase_b_decision_path: str
    candidate_artifacts: CalibrationArtifactRefs
    flux_teacher_dataset: FluxTeacherDatasetArtifact
    hybrid_model_proposals: list[HybridFluxProposal]
    hybrid_model_proposal_path: str
    comparison_summary: dict[str, Any]
    decision: str
    decision_reason: str
    promotion_status: CalibrationPromotionStatus
    decision_record: CalibrationDecisionRecord
