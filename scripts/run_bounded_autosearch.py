import os
import sys
import json
import yaml
import random
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict, Optional, Dict, Any

# Scientific and orchestration boundaries
SCIENTIFIC_FROZEN_DIR = Path("src")
BOUNDED_GENERATED_DIR = Path("config/generated")
BOUNDED_GENERATED_DIR.mkdir(parents=True, exist_ok=True)
run_calibration_job_script = Path("scripts/run_calibration_job.py")
AUTORESEARCH_MEMORY_DIR = Path("Simulations/brodbar/autoresearch/agent_orchestration")
AUTORESEARCH_RECORDS_DIR = AUTORESEARCH_MEMORY_DIR / "records"
AUTORESEARCH_SESSIONS_DIR = AUTORESEARCH_MEMORY_DIR / "sessions"
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from services.robocop.runtime import build_bounded_autosearch_graph, invoke_bounded_autosearch
    from services.robocop.tracing import get_langsmith_trace_status
except ImportError:
    print(
        "RoBoCop runtime dependencies are required. Install `langgraph`, `langchain-core`, "
        "and optional `langsmith` support before running bounded autosearch."
    )
    sys.exit(1)

# Bounded candidate generator (RoBoCop Mutation Agent)
try:
    from services.robocop.mutation.candidate_generator import propose_mutation, load_memory
    _USE_GENERATOR = True
except ImportError:
    _USE_GENERATOR = False

AUTORESEARCH_DECISION_CONTRACT_VERSION = 3
DECISION_POLICY_NAME = "bounded_autosearch_mvp_feasibility"
DECISION_POLICY_VERSION = 3
MAX_KEEP_AGGREGATE_SCORE = 50.0
REQUIRED_ARTIFACT_REF_KEYS = ("eval_summary_path", "completed_run_manifest_path", "case_refs")

class SearchState(TypedDict, total=False):
    workflow_type: str
    workflow_name: str
    orchestration_runtime: str
    trace_status: Dict[str, Any]
    base_policy_path: str
    base_manifest_path: str
    mutation_policy_path: str
    dry_run: bool
    time_budget_seconds: Optional[float]
    case_time_budget_seconds: Optional[float]
    timeout_policy: Optional[str]
    candidate_id: Optional[str]
    candidate_policy_path: Optional[str]
    candidate_manifest_path: Optional[str]
    job_spec_path: Optional[str]
    run_dir: Optional[str]
    job_payload: Optional[Dict[str, Any]]
    execution_command: Optional[list[str]]
    evaluator_status: Optional[str]
    evaluator_returncode: Optional[int]
    evaluator_error: Optional[str]
    eval_summary_path: Optional[str]
    completed_run_manifest_path: Optional[str]
    aggregate_score: Optional[float]
    time_aware_score: Optional[float]
    mean_final_loss: Optional[float]
    benchmark_status: Optional[str]
    completion_status: Optional[str]
    elapsed_seconds: Optional[float]
    coverage_ratio: Optional[float]
    coverage_weight_ratio: Optional[float]
    completed_cases: Optional[int]
    total_cases: Optional[int]
    timed_out: Optional[bool]
    crashed: Optional[bool]
    benchmark_summary: Optional[Dict[str, Any]]
    artifact_refs: Optional[Dict[str, Any]]
    mutation_significance: Optional[Dict[str, Any]]
    decision_record_path: Optional[str]
    local_decision_path: Optional[str]
    orchestrator_decision: Optional[str]
    decision_policy: Optional[Dict[str, Any]]
    decision_inputs: Optional[Dict[str, Any]]
    decision_reason: Optional[str]
    decision_category: Optional[str]
    decision: Optional[str]
    reason: Optional[str]
    mutation_summary: Optional[str]
    iteration: int


def read_json_if_exists(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with open(path, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def resolve_repo_relative_path(path_value: Optional[str]) -> Optional[Path]:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def find_case_by_name(cases: Any, case_name: Optional[str]) -> Optional[Dict[str, Any]]:
    if not isinstance(cases, list) or not case_name:
        return None
    for case in cases:
        if isinstance(case, dict) and case.get("name") == case_name:
            return case
    return None


def build_case_ref_from_manifest_case(case: Dict[str, Any]) -> Dict[str, Any]:
    artifacts = case.get("artifacts") if isinstance(case.get("artifacts"), dict) else {}
    return {
        "name": case.get("name"),
        "score": case.get("score"),
        "final_loss": case.get("final_loss"),
        "elapsed_seconds": case.get("elapsed_seconds"),
        "case_completion_status": case.get("case_completion_status"),
        "case_time_budget_exceeded": case.get("case_time_budget_exceeded"),
        "report_path": artifacts.get("calibration_report", {}).get("path"),
        "best_params_json_path": artifacts.get("best_params_json", {}).get("path"),
        "results_tsv_path": artifacts.get("results_tsv", {}).get("path"),
    }


def build_manifest_artifact_refs(completed_run_manifest: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(completed_run_manifest, dict):
        return {}
    outputs = completed_run_manifest.get("outputs") if isinstance(completed_run_manifest.get("outputs"), dict) else {}
    summary = outputs.get("summary") if isinstance(outputs.get("summary"), dict) else {}
    cases = outputs.get("cases") if isinstance(outputs.get("cases"), list) else []
    best_case = find_case_by_name(cases, summary.get("best_case"))
    worst_case = find_case_by_name(cases, summary.get("worst_case"))
    refs: Dict[str, Any] = {
        "eval_summary_path": completed_run_manifest.get("artifacts", {}).get("eval_summary", {}).get("path"),
        "policy_snapshot_path": completed_run_manifest.get("inputs", {}).get("policy_snapshot", {}).get("path"),
        "manifest_snapshot_path": completed_run_manifest.get("inputs", {}).get("manifest_snapshot", {}).get("path"),
        "best_case_report_path": best_case.get("artifacts", {}).get("calibration_report", {}).get("path") if isinstance(best_case, dict) else None,
        "worst_case_report_path": worst_case.get("artifacts", {}).get("calibration_report", {}).get("path") if isinstance(worst_case, dict) else None,
        "case_refs": [build_case_ref_from_manifest_case(case) for case in cases if isinstance(case, dict)],
    }
    return {
        key: value
        for key, value in refs.items()
        if value not in (None, "", [])
    }


def build_artifact_refs(job_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    artifact_refs: Dict[str, Any] = {}
    run_registry = job_payload.get("run_registry_record")
    if isinstance(run_registry, dict):
        registry_refs = run_registry.get("artifact_refs")
        if isinstance(registry_refs, dict):
            artifact_refs.update(registry_refs)
    manifest_refs = build_manifest_artifact_refs(job_payload.get("completed_run_manifest"))
    for key, value in manifest_refs.items():
        if artifact_refs.get(key) in (None, "", []):
            artifact_refs[key] = value
    eval_summary_path = job_payload.get("eval_summary_path")
    if eval_summary_path and "eval_summary_path" not in artifact_refs:
        artifact_refs["eval_summary_path"] = eval_summary_path
    completed_run_manifest_path = job_payload.get("completed_run_manifest_path")
    if completed_run_manifest_path and "completed_run_manifest_path" not in artifact_refs:
        artifact_refs["completed_run_manifest_path"] = completed_run_manifest_path
    return artifact_refs or None


def build_benchmark_summary(
    eval_payload: Optional[Dict[str, Any]],
    benchmark_status: Optional[str],
    eval_summary_path: Optional[str],
) -> Dict[str, Any]:
    summary_section = {}
    if isinstance(eval_payload, dict):
        maybe_summary = eval_payload.get("summary")
        if isinstance(maybe_summary, dict):
            summary_section = maybe_summary
    resolved_status = eval_payload.get("status") if isinstance(eval_payload, dict) else benchmark_status
    completion_status = eval_payload.get("completion_status") if isinstance(eval_payload, dict) else None
    if completion_status is None:
        if resolved_status in ("baseline", "keep", "discard"):
            completion_status = "completed"
        else:
            completion_status = resolved_status
    resolved_benchmark_status = (
        eval_payload.get("benchmark_status")
        if isinstance(eval_payload, dict)
        else benchmark_status
    )
    if resolved_benchmark_status is None:
        resolved_benchmark_status = resolved_status if completion_status == "completed" else "not_comparable"
    return {
        "benchmark_status": resolved_benchmark_status,
        "status": resolved_status,
        "completion_status": completion_status,
        "aggregate_score": summary_section.get("aggregate_score"),
        "time_aware_score": summary_section.get("time_aware_score"),
        "score_basis": summary_section.get("score_basis"),
        "mean_final_loss": summary_section.get("mean_final_loss"),
        "mean_improvement_pct": summary_section.get("mean_improvement_pct"),
        "best_case": summary_section.get("best_case"),
        "worst_case": summary_section.get("worst_case"),
        "eval_summary_path": eval_summary_path,
        "eval_summary_present": isinstance(eval_payload, dict),
        "elapsed_seconds": eval_payload.get("elapsed_seconds") if isinstance(eval_payload, dict) else None,
        "time_budget_seconds": eval_payload.get("time_budget_seconds") if isinstance(eval_payload, dict) else None,
        "case_time_budget_seconds": eval_payload.get("case_time_budget_seconds") if isinstance(eval_payload, dict) else None,
        "timeout_policy": eval_payload.get("timeout_policy") if isinstance(eval_payload, dict) else None,
        "completed_cases": eval_payload.get("completed_cases") if isinstance(eval_payload, dict) else None,
        "total_cases": eval_payload.get("total_cases") if isinstance(eval_payload, dict) else None,
        "coverage_ratio": eval_payload.get("coverage_ratio") if isinstance(eval_payload, dict) else None,
        "coverage_weight_ratio": eval_payload.get("coverage_weight_ratio") if isinstance(eval_payload, dict) else None,
        "timed_out": eval_payload.get("timed_out") if isinstance(eval_payload, dict) else None,
        "crashed": eval_payload.get("crashed") if isinstance(eval_payload, dict) else None,
        "stop_reason": eval_payload.get("stop_reason") if isinstance(eval_payload, dict) else None,
        "time_aware_score_components": eval_payload.get("time_aware_score_components") if isinstance(eval_payload, dict) else None,
    }


def build_mutation_significance(
    changed_field: Optional[str],
    previous_value: Any,
    new_value: Any,
    allowed_values: Optional[list[Any]],
    selection_basis: str,
) -> Dict[str, Any]:
    mutation_applied = changed_field is not None and previous_value != new_value
    payload: Dict[str, Any] = {
        "mutation_applied": mutation_applied,
        "changed_field": changed_field,
        "previous_value": previous_value,
        "new_value": new_value,
        "allowed_value_count": len(allowed_values) if isinstance(allowed_values, list) else None,
        "alternative_value_count": len([value for value in allowed_values if value != previous_value]) if isinstance(allowed_values, list) else None,
        "selection_basis": selection_basis,
        "change_kind": "none",
        "absolute_delta": None,
        "relative_delta": None,
    }
    if not mutation_applied:
        return payload
    if isinstance(previous_value, bool) and isinstance(new_value, bool):
        payload["change_kind"] = "boolean_flip"
        return payload
    if (
        isinstance(previous_value, (int, float))
        and not isinstance(previous_value, bool)
        and isinstance(new_value, (int, float))
        and not isinstance(new_value, bool)
    ):
        payload["change_kind"] = "numeric_delta"
        payload["absolute_delta"] = float(new_value) - float(previous_value)
        if float(previous_value) != 0.0:
            payload["relative_delta"] = (float(new_value) - float(previous_value)) / float(previous_value)
        return payload
    payload["change_kind"] = "categorical_change"
    return payload


def build_decision_policy() -> Dict[str, Any]:
    return {
        "policy_name": DECISION_POLICY_NAME,
        "policy_version": DECISION_POLICY_VERSION,
        "keep_metric": "time_aware_score",
        "keep_operator": "<",
        "keep_threshold": MAX_KEEP_AGGREGATE_SCORE,
        "requires_effective_mutation": True,
        "requires_eval_summary": True,
        "required_artifact_refs": list(REQUIRED_ARTIFACT_REF_KEYS),
        "keep_requires_completion_status": "completed",
        "incomplete_statuses": ["partial", "timed_out", "crashed"],
        "incomplete_archive_policy": "archive_as_informative_without_keep",
        "benchmark_status_handling": "preserve_separately_for_audit",
    }


def build_decision_inputs(
    state: SearchState,
    benchmark_summary: Dict[str, Any],
    artifact_refs: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    resolved_artifact_refs = artifact_refs or {}
    mutation_significance = state.get("mutation_significance") or {}
    artifact_checks = {
        "eval_summary_path": bool(resolved_artifact_refs.get("eval_summary_path") or state.get("eval_summary_path")),
        "completed_run_manifest_path": bool(
            resolved_artifact_refs.get("completed_run_manifest_path")
            or state.get("completed_run_manifest_path")
        ),
        "case_refs": isinstance(resolved_artifact_refs.get("case_refs"), list)
        and len(resolved_artifact_refs.get("case_refs") or []) > 0,
    }
    return {
        "evaluator_status": state.get("evaluator_status"),
        "evaluator_returncode": state.get("evaluator_returncode"),
        "evaluator_error": state.get("evaluator_error"),
        "benchmark_status": benchmark_summary.get("benchmark_status") or benchmark_summary.get("status"),
        "completion_status": benchmark_summary.get("completion_status"),
        "aggregate_score": benchmark_summary.get("aggregate_score"),
        "time_aware_score": benchmark_summary.get("time_aware_score"),
        "score_basis": benchmark_summary.get("score_basis"),
        "mean_final_loss": benchmark_summary.get("mean_final_loss"),
        "mean_improvement_pct": benchmark_summary.get("mean_improvement_pct"),
        "best_case": benchmark_summary.get("best_case"),
        "worst_case": benchmark_summary.get("worst_case"),
        "elapsed_seconds": benchmark_summary.get("elapsed_seconds"),
        "time_budget_seconds": benchmark_summary.get("time_budget_seconds"),
        "case_time_budget_seconds": benchmark_summary.get("case_time_budget_seconds"),
        "timeout_policy": benchmark_summary.get("timeout_policy"),
        "completed_cases": benchmark_summary.get("completed_cases"),
        "total_cases": benchmark_summary.get("total_cases"),
        "coverage_ratio": benchmark_summary.get("coverage_ratio"),
        "coverage_weight_ratio": benchmark_summary.get("coverage_weight_ratio"),
        "timed_out": benchmark_summary.get("timed_out"),
        "crashed": benchmark_summary.get("crashed"),
        "stop_reason": benchmark_summary.get("stop_reason"),
        "time_aware_score_components": benchmark_summary.get("time_aware_score_components"),
        "eval_summary_present": benchmark_summary.get("eval_summary_present", False),
        "artifact_refs_complete": all(artifact_checks.values()),
        "artifact_checks": artifact_checks,
        "missing_required_artifacts": [key for key, is_present in artifact_checks.items() if not is_present],
        "mutation_applied": bool(mutation_significance.get("mutation_applied")),
        "mutation_field": mutation_significance.get("changed_field"),
        "mutation_significance": mutation_significance,
        "decision_vs_benchmark_divergent": False,
    }


def build_decision_result(
    state: SearchState,
    benchmark_summary: Dict[str, Any],
    artifact_refs: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    decision_policy = build_decision_policy()
    decision_inputs = build_decision_inputs(state, benchmark_summary, artifact_refs)
    benchmark_status = decision_inputs.get("benchmark_status")
    score = decision_inputs.get("aggregate_score")
    time_aware_score = decision_inputs.get("time_aware_score")
    completion_status = decision_inputs.get("completion_status")
    coverage_ratio = decision_inputs.get("coverage_ratio")
    completed_cases = decision_inputs.get("completed_cases")
    total_cases = decision_inputs.get("total_cases")
    elapsed_seconds = decision_inputs.get("elapsed_seconds")
    decision: str
    reason: str
    decision_category: str

    if state.get("dry_run"):
        if decision_inputs.get("mutation_applied"):
            decision = "Keep"
            decision_category = "dry_run_validated"
            reason = "Dry run validation completed; candidate passed the pre-evaluation mutation gate and benchmark execution was skipped."
        else:
            decision = "Discard"
            decision_category = "dry_run_no_effective_mutation"
            reason = "Dry run validation completed, but candidate would be discarded because no effective mutation was produced."
    elif not decision_inputs.get("mutation_applied"):
        decision = "Discard"
        decision_category = "no_effective_mutation"
        reason = "Candidate was not evaluated because no effective mutation was produced."
    elif not decision_inputs.get("eval_summary_present"):
        decision = "Discard"
        decision_category = "missing_eval_summary"
        reason = "No eval_summary.json produced for this run."
    elif completion_status == "crashed":
        decision = "Discard"
        decision_category = "crashed_failure"
        reason = (
            f"Run crashed after {completed_cases}/{total_cases} cases"
            + (f" in {float(elapsed_seconds):.2f}s" if isinstance(elapsed_seconds, (int, float)) else "")
            + (f"; {decision_inputs.get('stop_reason')}" if decision_inputs.get("stop_reason") else "")
            + "."
        )
    elif completion_status in ("partial", "timed_out"):
        decision = "Discard"
        decision_category = "timed_out_informative" if completion_status == "timed_out" else "partial_informative"
        reason = (
            f"Run {completion_status} after {completed_cases}/{total_cases} cases"
            + (
                f" (coverage {float(coverage_ratio):.2f})"
                if isinstance(coverage_ratio, (int, float))
                else ""
            )
            + (
                f", partial aggregate_score={float(score):.4f}"
                if isinstance(score, (int, float))
                else ""
            )
            + (
                f", time_aware_score={float(time_aware_score):.4f}"
                if isinstance(time_aware_score, (int, float))
                else ""
            )
            + ". Archived as informative but not eligible for Keep."
        )
    elif not decision_inputs.get("artifact_refs_complete"):
        missing_refs = ", ".join(decision_inputs.get("missing_required_artifacts", []))
        decision = "Discard"
        decision_category = "missing_artifact_refs"
        reason = f"Required artifact refs missing from orchestration record: {missing_refs}."
    elif state.get("evaluator_returncode") not in (None, 0):
        decision = "Discard"
        decision_category = "evaluator_failure"
        reason = (
            f"Evaluator process failed (exit {state.get('evaluator_returncode')})"
            + (f": {state.get('evaluator_error')}" if state.get("evaluator_error") else "")
        )
    elif score is None:
        decision = "Discard"
        decision_category = "missing_aggregate_score"
        reason = "No aggregate_score found in summary."
    elif time_aware_score is None:
        decision = "Discard"
        decision_category = "missing_time_aware_score"
        reason = "No time_aware_score found in summary."
    elif float(time_aware_score) < MAX_KEEP_AGGREGATE_SCORE:
        decision = "Keep"
        decision_category = "completed_keep"
        reason = (
            f"Completed full manifest with aggregate score {float(score):.4f} and time-aware score "
            f"{float(time_aware_score):.4f}, below keep threshold {MAX_KEEP_AGGREGATE_SCORE:.1f}; "
            f"benchmark_status={benchmark_status} is preserved separately for audit."
        )
    else:
        decision = "Discard"
        decision_category = "completed_discard"
        reason = (
            f"Completed full manifest but time-aware score {float(time_aware_score):.4f} is above "
            f"keep threshold {MAX_KEEP_AGGREGATE_SCORE:.1f}."
        )

    decision_inputs["decision_vs_benchmark_divergent"] = (
        (benchmark_status == "discard" and decision == "Keep")
        or (benchmark_status == "keep" and decision == "Discard")
    )

    return {
        "aggregate_score": score,
        "time_aware_score": time_aware_score,
        "mean_final_loss": decision_inputs.get("mean_final_loss"),
        "benchmark_status": benchmark_status,
        "completion_status": completion_status,
        "elapsed_seconds": elapsed_seconds,
        "coverage_ratio": coverage_ratio,
        "coverage_weight_ratio": decision_inputs.get("coverage_weight_ratio"),
        "completed_cases": completed_cases,
        "total_cases": total_cases,
        "timed_out": decision_inputs.get("timed_out"),
        "crashed": decision_inputs.get("crashed"),
        "benchmark_summary": benchmark_summary,
        "artifact_refs": artifact_refs,
        "orchestrator_decision": decision,
        "decision_policy": decision_policy,
        "decision_inputs": decision_inputs,
        "decision_reason": reason,
        "decision_category": decision_category,
        "decision": decision,
        "reason": reason,
    }


def node_propose(state: SearchState) -> SearchState:
    """Proposes a bounded mutation to a policy based on the autoresearch mutation policy."""
    print("--- PROPOSE ---")
    
    with open(state["mutation_policy_path"], 'r') as f:
        mutation_policy = yaml.safe_load(f)
        
    with open(state["base_policy_path"], 'r') as f:
        base_policy = json.load(f)
        
    candidate = json.loads(json.dumps(base_policy))  # Deep copy
    
    space = candidate.get("mutation_space", {})
    base_run = candidate.get("base_run", {})
    mutated_field = None
    previous_value = None
    new_value = None
    allowed_values_for_field = None
    selection_basis = "No mutation space defined."

    if space and _USE_GENERATOR:
        # History-aware proposal via bounded candidate generator v2
        memory = load_memory(ROOT / AUTORESEARCH_MEMORY_DIR / "autosearch_memory.jsonl")
        proposal = propose_mutation(base_run, space, memory)
        mutated_field = proposal.field
        previous_value = proposal.previous_value
        new_value = proposal.new_value
        allowed_values_for_field = proposal.allowed_values
        selection_basis = proposal.selection_basis
        if mutated_field is not None:
            if "base_run" not in candidate:
                candidate["base_run"] = {}
            # Apply all mutations (supports multi-field from v2 generator)
            proposed_mutations = proposal.mutations if proposal.mutations else {mutated_field: new_value}
            all_mutations = {
                mf: mv for mf, mv in proposed_mutations.items()
                if base_run.get(mf) != mv
            }
            if not all_mutations:
                print("[Proposer] Generator v2: proposal collapsed to a no-op after filtering unchanged fields.")
                mutated_field = None
                previous_value = None
                new_value = None
                allowed_values_for_field = None
                selection_basis = f"{selection_basis}|collapsed_to_no_op"
                mutation_summary = "No non-trivial mutation applied"
            else:
                old_values = {k: base_run.get(k) for k in all_mutations}
                for mf, mv in all_mutations.items():
                    candidate["base_run"][mf] = mv
                mutated_field = next(iter(all_mutations))
                previous_value = old_values[mutated_field]
                new_value = all_mutations[mutated_field]
                allowed_values_for_field = space.get(mutated_field)
                n = len(all_mutations)
                if n > 1:
                    parts = [f"{k}: {old_values[k]} -> {v}" for k, v in all_mutations.items()]
                    mutation_summary = f"Mutated {n} fields: " + ", ".join(parts)
                    candidate["notes"] = f"Autogenerated multi-field candidate: {', '.join(parts)}."
                    print(f"[Proposer] Generator v2 multi-field ({n} effective): {'; '.join(parts)} ({selection_basis})")
                else:
                    mutation_summary = f"Mutated {mutated_field} from {previous_value} to {new_value}"
                    candidate["notes"] = f"Autogenerated candidate mutating {mutated_field} from {previous_value} to {new_value}."
                    print(f"[Proposer] Generator v2: {mutated_field}: {previous_value} -> {new_value} ({selection_basis})")
        else:
            print("[Proposer] Generator v2: No non-trivial mutation proposed.")
            mutation_summary = "No non-trivial mutation applied"
    elif space:
        # Fallback: original random mutation (used if generator import fails)
        shuffled_keys = list(space.keys())
        random.shuffle(shuffled_keys)
        mutated = False
        for key_to_mutate in shuffled_keys:
            allowed_values = space[key_to_mutate]
            current_value = base_run.get(key_to_mutate)
            candidates_filtered = [v for v in allowed_values if v != current_value]
            if not candidates_filtered:
                continue
            new_value = random.choice(candidates_filtered)
            mutated_field = key_to_mutate
            previous_value = current_value
            allowed_values_for_field = allowed_values
            selection_basis = "Sampled a non-equal value from mutation_space (random fallback)."
            print(f"[Proposer] Random fallback: {key_to_mutate}: {current_value} -> {new_value}")
            if "base_run" not in candidate:
                candidate["base_run"] = {}
            candidate["base_run"][key_to_mutate] = new_value
            candidate["notes"] = f"Autogenerated candidate mutating {key_to_mutate} from {current_value} to {new_value}."
            mutation_summary = f"Mutated {key_to_mutate} from {current_value} to {new_value}"
            mutated = True
            break
        if not mutated:
            print("[Proposer] WARNING: No non-trivial mutation found in mutation_space.")
            mutation_summary = "No non-trivial mutation applied"
            selection_basis = "No non-equal value was available in mutation_space."
    else:
        mutation_summary = "No mutation space defined"
    
    mutation_significance = build_mutation_significance(
        changed_field=mutated_field,
        previous_value=previous_value,
        new_value=new_value,
        allowed_values=allowed_values_for_field,
        selection_basis=selection_basis,
    )
    candidate_id = str(time.time_ns())
    candidate["policy_name"] = f"auto_{candidate.get('policy_name', 'policy')}_{candidate_id}"
    
    candidate_policy_path = BOUNDED_GENERATED_DIR / f"policy_candidate_{candidate_id}.json"
    candidate_manifest_path = BOUNDED_GENERATED_DIR / f"manifest_candidate_{candidate_id}.json"
    
    with open(candidate_policy_path, 'w') as f:
        json.dump(candidate, f, indent=2)
        
    shutil.copy(state["base_manifest_path"], candidate_manifest_path)
    print(f"[System] Candidate policy generated at {candidate_policy_path}")
    
    job_spec = {
        "job_name": f"bounded_search_{candidate_id}",
        "hypothesis": "Test autosearch bounded mutation (LangGraph)",
        "policy_path": str(candidate_policy_path.relative_to(Path(".").resolve()) if candidate_policy_path.is_absolute() else candidate_policy_path),
        "manifest_path": str(candidate_manifest_path.relative_to(Path(".").resolve()) if candidate_manifest_path.is_absolute() else candidate_manifest_path),
        "job_version": 1,
        "tags": ["autosearch", "bounded_search"],
        "metadata": {
            "orchestrator": "bounded_autosearch_v1",
            "candidate_id": candidate_id,
            "base_policy_path": state["base_policy_path"],
            "base_manifest_path": state["base_manifest_path"],
            "mutation_summary": mutation_summary,
        },
        "dump_trajectories": True,
    }
    if state.get("time_budget_seconds") is not None:
        job_spec["time_budget_seconds"] = state.get("time_budget_seconds")
    if state.get("case_time_budget_seconds") is not None:
        job_spec["case_time_budget_seconds"] = state.get("case_time_budget_seconds")
    if state.get("timeout_policy") is not None:
        job_spec["timeout_policy"] = state.get("timeout_policy")
    job_spec_path = BOUNDED_GENERATED_DIR / f"job_candidate_{candidate_id}.json"
    with open(job_spec_path, 'w') as f:
        json.dump(job_spec, f, indent=2)
        
    return {
        "candidate_id": candidate_id,
        "candidate_policy_path": str(candidate_policy_path),
        "candidate_manifest_path": str(candidate_manifest_path),
        "job_spec_path": str(job_spec_path),
        "mutation_summary": mutation_summary,
        "mutation_significance": mutation_significance,
    }

def node_evaluate(state: SearchState) -> SearchState:
    """Delegates execution to the safe job runner without touching scientific frozen code."""
    print("--- EVALUATE ---")
    
    command = [
        sys.executable,
        str(run_calibration_job_script),
        "--job", str(state["job_spec_path"])
    ]
    if state["dry_run"]:
        command.append("--dry-run")

    mutation_significance = state.get("mutation_significance") or {}
    if not state.get("dry_run") and not mutation_significance.get("mutation_applied"):
        print("[Evaluator] Skipping execution because no effective mutation was produced.")
        return {
            "run_dir": None,
            "job_payload": None,
            "execution_command": command,
            "evaluator_status": "skipped_no_effective_mutation",
            "evaluator_returncode": 0,
            "evaluator_error": "Candidate was not evaluated because no effective mutation was produced.",
        }
    
    print(f"[Evaluator] Running: {' '.join(command)}")
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )
    
    # Print stderr for diagnostics (calibration progress goes to stderr)
    if result.stderr:
        # Show last 20 lines of stderr to avoid flooding
        stderr_lines = result.stderr.strip().split('\n')
        start_idx = max(0, len(stderr_lines) - 20)
        tail = [stderr_lines[i] for i in range(start_idx, len(stderr_lines))]
        print(f"[Evaluator] Stderr tail ({len(stderr_lines)} lines total):")
        for line in tail:
            print(f"  {line}")
    
    payload: Optional[Dict[str, Any]] = None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        out_str: str = str(result.stdout) if result.stdout is not None else ""
        out_trunc = out_str[:500]
        print(f"[Evaluator] Warning: stdout was not valid JSON:\n{out_trunc}")
        return {
            "run_dir": None,
            "job_payload": None,
            "execution_command": command,
            "evaluator_status": "invalid_json",
            "evaluator_returncode": result.returncode,
            "evaluator_error": "Evaluator payload was not valid JSON.",
        }

    if result.returncode != 0:
        print(f"[Evaluator] Job failed with return code {result.returncode}")
    else:
        print("[Evaluator] Job succeeded.")

    run_dir = payload.get("run_dir") if isinstance(payload, dict) else None
    if state["dry_run"]:
        run_dir = "DRY_RUN"
    
    print(f"[Evaluator] run_dir: {run_dir}")
    print(f"[Evaluator] status: {payload.get('status') if isinstance(payload, dict) else None}")
    return {
        "run_dir": run_dir,
        "job_payload": payload,
        "execution_command": payload.get("command") if isinstance(payload, dict) else command,
        "evaluator_status": payload.get("status") if isinstance(payload, dict) else None,
        "evaluator_returncode": result.returncode,
        "evaluator_error": (
            payload.get("error")
            or payload.get("artifact_contract_error")
            or payload.get("run_registry_contract_error")
        ) if isinstance(payload, dict) else None,
        "eval_summary_path": payload.get("eval_summary_path") if isinstance(payload, dict) else None,
        "completed_run_manifest_path": payload.get("completed_run_manifest_path") if isinstance(payload, dict) else None,
    }

def node_verify(state: SearchState) -> SearchState:
    """Reads the eval summary and decides Keep or Discard based on strict metrics."""
    print("--- VERIFY ---")

    job_payload = state.get("job_payload") or {}
    artifact_refs = build_artifact_refs(job_payload)

    run_dir = state.get("run_dir")
    benchmark_status_override = None
    if state.get("dry_run"):
        print("[Verifier] Skipping benchmark execution during dry run.")
        benchmark_status_override = "not_run"
    elif state.get("evaluator_returncode") not in (None, 0):
        benchmark_status_override = "not_available"
    if not run_dir or run_dir == "DRY_RUN":
        if benchmark_status_override is None and not state.get("dry_run"):
            benchmark_status_override = "not_available"

    eval_payload = job_payload.get("eval_summary") if isinstance(job_payload, dict) else None
    eval_summary_path = state.get("eval_summary_path")
    if not state.get("dry_run") and run_dir and run_dir != "DRY_RUN" and not isinstance(eval_payload, dict):
        summary_path = Path(str(run_dir)) / "eval_summary.json"
        eval_payload = read_json_if_exists(summary_path)
        if eval_payload is not None:
            eval_summary_path = str(summary_path)
    if benchmark_status_override is None and not isinstance(eval_payload, dict):
        benchmark_status_override = "not_available"

    benchmark_summary = build_benchmark_summary(
        eval_payload=eval_payload,
        benchmark_status=benchmark_status_override,
        eval_summary_path=eval_summary_path,
    )
    score = benchmark_summary.get("aggregate_score")
    loss = benchmark_summary.get("mean_final_loss")
        
    if score is not None:
        print(f"[Verifier] Extracted aggregate_score: {score:.4f} | mean_final_loss: {loss}")

    return build_decision_result(
        state=state,
        benchmark_summary=benchmark_summary,
        artifact_refs=artifact_refs,
    )

def node_archive(state: SearchState) -> SearchState:
    """Archives the result of the search step to a global append-only log."""
    print("--- ARCHIVE ---")
    
    is_dry_run = state.get("dry_run", False)
    orchestrator_decision = state.get("orchestrator_decision") or state.get("decision", "DryRun" if is_dry_run else "Discard")
    decision_reason = state.get("decision_reason") or state.get("reason", "No verification ran (Dry Run)" if is_dry_run else "No reason provided")
    print(f"[Archiver] Decision: {orchestrator_decision} | Reason: {decision_reason}")
    
    run_dir = state.get("run_dir")
    job_payload = state.get("job_payload") or {}
    job_info = job_payload.get("job") if isinstance(job_payload, dict) else None
    if not isinstance(job_info, dict):
        job_info = read_json_if_exists(resolve_repo_relative_path(state.get("job_spec_path")) or Path(""))
    candidate_id = state.get("candidate_id") or Path(str(state.get("candidate_policy_path") or "")).stem.replace("policy_candidate_", "")
    benchmark_summary = state.get("benchmark_summary") or {}
    benchmark_status = state.get("benchmark_status") or benchmark_summary.get("benchmark_status") or benchmark_summary.get("status")
    archive_status = benchmark_summary.get("status") or benchmark_status
    decision_record_path = AUTORESEARCH_RECORDS_DIR / f"decision_{candidate_id}.json"
    local_archive_path = Path(str(run_dir)) / "autosearch_decision.json" if run_dir and run_dir != "DRY_RUN" else None
    
    # 1. Build the unified decision record
    record = {
        "contract_type": "autosearch_decision_record",
        "contract_version": AUTORESEARCH_DECISION_CONTRACT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candidate_id": candidate_id,
        "iteration": state.get("iteration", 1),
        "dry_run": is_dry_run,
        "base_policy_path": state.get("base_policy_path"),
        "base_manifest_path": state.get("base_manifest_path"),
        "candidate_policy_path": state.get("candidate_policy_path"),
        "candidate_manifest_path": state.get("candidate_manifest_path"),
        "job_spec_path": state.get("job_spec_path"),
        "job_name": job_info.get("job_name") if isinstance(job_info, dict) else None,
        "hypothesis": job_info.get("hypothesis") if isinstance(job_info, dict) else None,
        "job_version": job_info.get("job_version") if isinstance(job_info, dict) else None,
        "job_tags": job_info.get("tags") if isinstance(job_info, dict) else None,
        "job_metadata": job_info.get("metadata") if isinstance(job_info, dict) else None,
        "mutation_summary": state.get("mutation_summary"),
        "mutation_significance": state.get("mutation_significance"),
        "execution_command": state.get("execution_command"),
        "evaluator_status": state.get("evaluator_status"),
        "evaluator_returncode": state.get("evaluator_returncode"),
        "evaluator_error": state.get("evaluator_error"),
        "benchmark_status": benchmark_status,
        "orchestrator_decision": orchestrator_decision,
        "decision_policy": state.get("decision_policy"),
        "decision_inputs": state.get("decision_inputs"),
        "decision_reason": decision_reason,
        "decision_category": state.get("decision_category"),
        "decision": orchestrator_decision,
        "reason": decision_reason,
        "run_dir": run_dir,
        "aggregate_score": state.get("aggregate_score"),
        "time_aware_score": benchmark_summary.get("time_aware_score"),
        "mean_final_loss": state.get("mean_final_loss"),
        "mean_improvement_pct": benchmark_summary.get("mean_improvement_pct"),
        "best_case": benchmark_summary.get("best_case"),
        "worst_case": benchmark_summary.get("worst_case"),
        "status": archive_status,
        "completion_status": benchmark_summary.get("completion_status"),
        "elapsed_seconds": benchmark_summary.get("elapsed_seconds"),
        "time_budget_seconds": benchmark_summary.get("time_budget_seconds"),
        "case_time_budget_seconds": benchmark_summary.get("case_time_budget_seconds"),
        "coverage_ratio": benchmark_summary.get("coverage_ratio"),
        "coverage_weight_ratio": benchmark_summary.get("coverage_weight_ratio"),
        "completed_cases": benchmark_summary.get("completed_cases"),
        "total_cases": benchmark_summary.get("total_cases"),
        "timed_out": benchmark_summary.get("timed_out"),
        "crashed": benchmark_summary.get("crashed"),
        "eval_summary_path": benchmark_summary.get("eval_summary_path") or state.get("eval_summary_path"),
        "completed_run_manifest_path": state.get("completed_run_manifest_path"),
        "benchmark_summary": benchmark_summary,
        "artifact_refs": state.get("artifact_refs"),
        "decision_record_path": str(decision_record_path),
        "local_decision_path": str(local_archive_path) if local_archive_path is not None else None,
    }

    # 2. Persist to local candidate run_dir if available and not a dry run
    AUTORESEARCH_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    AUTORESEARCH_RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(decision_record_path, 'w') as f:
            json.dump(record, f, indent=2)
        print(f"[Archiver] Wrote decision record to {decision_record_path}")
    except Exception as e:
        print(f"[Archiver] Error writing decision record: {e}")

    if local_archive_path is not None:
        try:
            with open(local_archive_path, 'w') as f:
                json.dump(record, f, indent=2)
            print(f"[Archiver] Wrote local decision to {local_archive_path}")
        except Exception as e:
            print(f"[Archiver] Error writing local decision: {e}")

    # 3. Append to continuous global memory ledger
    global_memory_path = AUTORESEARCH_MEMORY_DIR / "autosearch_memory.jsonl"
    
    try:
        with open(global_memory_path, 'a') as f:
            f.write(json.dumps(record) + "\n")
        print(f"[Archiver] Appended global decision record to {global_memory_path}")
    except Exception as e:
        print(f"[Archiver] Error appending to global memory: {e}")

    return {
        "decision_record_path": str(decision_record_path),
        "local_decision_path": str(local_archive_path) if local_archive_path is not None else None,
    }


def build_graph():
    return build_bounded_autosearch_graph(
        {
            "propose_candidate": node_propose,
            "evaluate_candidate": node_evaluate,
            "derive_decision": node_verify,
            "archive_result": node_archive,
        }
    )


def normalize_repo_path(path_str: str) -> str:
    path = Path(path_str)
    if path.is_absolute():
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)
    return str(path)


def build_iteration_state(args: argparse.Namespace, base_policy_path: str, base_manifest_path: str, iteration: int) -> SearchState:
    return {
        "workflow_type": "bounded_autosearch",
        "workflow_name": "RoBoCop Bounded Autosearch",
        "base_policy_path": normalize_repo_path(base_policy_path),
        "base_manifest_path": normalize_repo_path(base_manifest_path),
        "mutation_policy_path": normalize_repo_path(args.mutation_policy),
        "dry_run": args.dry_run,
        "time_budget_seconds": args.time_budget_seconds,
        "case_time_budget_seconds": args.case_time_budget_seconds,
        "timeout_policy": args.timeout_policy,
        "iteration": iteration,
    }


def write_session_summary(session_id: str, payload: Dict[str, Any]) -> Path:
    AUTORESEARCH_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    session_path = AUTORESEARCH_SESSIONS_DIR / f"session_{session_id}.json"
    with open(session_path, "w") as f:
        json.dump(payload, f, indent=2)
    return session_path


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Bounded Autosearch Runner (LangGraph)")
    parser.add_argument("--base-policy", required=True, help="Path to base policy JSON")
    parser.add_argument("--base-manifest", required=True, help="Path to benchmark manifest JSON")
    parser.add_argument("--mutation-policy", default="config/autoresearch_mutation_policy.yaml", help="Path to mutation policy YAML")
    parser.add_argument("--dry-run", action="store_true", help="Execute bounding and delegation but don't run scientific evaluation")
    parser.add_argument("--max-iterations", type=int, default=1, help="Maximum number of bounded autosearch iterations to run in this session")
    parser.add_argument("--loop-budget-seconds", type=float, default=None, help="Optional wall-clock budget for the entire multi-iteration session")
    parser.add_argument("--stop-on-keep", action="store_true", help="Stop the session immediately after the first Keep decision")
    parser.add_argument("--time-budget-seconds", type=float, default=None, help="Optional wall-clock budget for the full evaluation")
    parser.add_argument("--case-time-budget-seconds", type=float, default=None, help="Optional wall-clock budget per completed case")
    parser.add_argument("--timeout-policy", choices=["continue", "stop_after_case"], default="stop_after_case", help="How the evaluator should behave when a configured budget is exceeded")
    args = parser.parse_args()
    
    base_policy_path = Path(args.base_policy)
    base_manifest_path = Path(args.base_manifest)
    
    if not base_policy_path.exists() or not base_manifest_path.exists():
        print(f"Error: Base policy or manifest missing.")
        sys.exit(1)
    if args.max_iterations < 1:
        print("Error: --max-iterations must be >= 1")
        sys.exit(1)
    if args.loop_budget_seconds is not None and args.loop_budget_seconds <= 0:
        print("Error: --loop-budget-seconds must be > 0")
        sys.exit(1)
        
    print(f"=== Starting LangGraph Bounded Autosearch ===")
    trace_status = get_langsmith_trace_status()
    if trace_status.get("enabled"):
        print(f"[Trace] LangSmith tracing enabled (project={trace_status.get('project')}).")
    else:
        print(f"[Trace] LangSmith tracing disabled ({trace_status.get('reason')}).")

    session_started = time.time()
    session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + f"_{time.time_ns()}"
    current_base_policy = normalize_repo_path(str(base_policy_path))
    current_base_manifest = normalize_repo_path(str(base_manifest_path))
    iteration_records: list[dict[str, Any]] = []
    kept_iterations = 0
    final_state: SearchState = {}
    stop_reason = "max_iterations_reached"

    for iteration in range(1, args.max_iterations + 1):
        elapsed = time.time() - session_started
        if args.loop_budget_seconds is not None and elapsed >= args.loop_budget_seconds:
            stop_reason = "loop_budget_exhausted"
            print(f"[Session] Loop budget exhausted before iteration {iteration} ({elapsed:.1f}s).")
            break

        print(f"\n=== Autosearch Iteration {iteration}/{args.max_iterations} ===")
        print(f"[Session] Base policy: {current_base_policy}")
        initial_state = build_iteration_state(args, current_base_policy, current_base_manifest, iteration)

        final_state = invoke_bounded_autosearch(
            initial_state,
            {
                "propose_candidate": node_propose,
                "evaluate_candidate": node_evaluate,
                "derive_decision": node_verify,
                "archive_result": node_archive,
            },
        )

        decision = final_state.get("orchestrator_decision") or final_state.get("decision")
        candidate_policy_path = final_state.get("candidate_policy_path")
        candidate_manifest_path = final_state.get("candidate_manifest_path")
        record = {
            "iteration": iteration,
            "base_policy_path": current_base_policy,
            "base_manifest_path": current_base_manifest,
            "candidate_policy_path": candidate_policy_path,
            "candidate_manifest_path": candidate_manifest_path,
            "decision": decision,
            "decision_reason": final_state.get("decision_reason") or final_state.get("reason"),
            "decision_category": final_state.get("decision_category"),
            "aggregate_score": final_state.get("aggregate_score"),
            "time_aware_score": final_state.get("time_aware_score"),
            "mean_final_loss": final_state.get("mean_final_loss"),
            "benchmark_status": final_state.get("benchmark_status"),
            "completion_status": final_state.get("completion_status"),
            "run_dir": final_state.get("run_dir"),
            "mutation_summary": final_state.get("mutation_summary"),
            "decision_record_path": final_state.get("decision_record_path"),
        }
        iteration_records.append(record)

        if decision == "Keep" and candidate_policy_path:
            kept_iterations += 1
            current_base_policy = normalize_repo_path(candidate_policy_path)
            if candidate_manifest_path:
                current_base_manifest = normalize_repo_path(candidate_manifest_path)
            print(f"[Session] Promoted candidate policy for next iteration: {current_base_policy}")
            if args.stop_on_keep:
                stop_reason = "stop_on_keep"
                break

    else:
        stop_reason = "max_iterations_reached"

    session_elapsed = time.time() - session_started
    session_summary = {
        "session_id": session_id,
        "workflow_type": "bounded_autosearch_session",
        "workflow_name": "RoBoCop Bounded Autosearch Session",
        "started_at": datetime.fromtimestamp(session_started, timezone.utc).isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": session_elapsed,
        "dry_run": args.dry_run,
        "max_iterations": args.max_iterations,
        "loop_budget_seconds": args.loop_budget_seconds,
        "time_budget_seconds": args.time_budget_seconds,
        "case_time_budget_seconds": args.case_time_budget_seconds,
        "timeout_policy": args.timeout_policy,
        "stop_on_keep": args.stop_on_keep,
        "stop_reason": stop_reason,
        "iterations_completed": len(iteration_records),
        "kept_iterations": kept_iterations,
        "initial_base_policy_path": normalize_repo_path(str(base_policy_path)),
        "initial_base_manifest_path": normalize_repo_path(str(base_manifest_path)),
        "final_promoted_policy_path": current_base_policy,
        "final_promoted_manifest_path": current_base_manifest,
        "trace_status": trace_status,
        "iterations": iteration_records,
        "final_iteration_state": final_state,
    }
    session_summary_path = write_session_summary(session_id, session_summary)

    print("=== LangGraph Autosearch Loop Complete ===")
    if final_state:
        print(f"Final Decision: {final_state.get('orchestrator_decision') or final_state.get('decision')}")
    print(f"Iterations completed: {len(iteration_records)} | Keeps: {kept_iterations}")
    print(f"Session summary: {session_summary_path}")

if __name__ == "__main__":
    main()
