from __future__ import annotations

from typing import Any


def _append_tag(tags: list[str], value: str | None) -> None:
    if value and value not in tags:
        tags.append(value)


def _compact(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if value is not None and value != ""
    }


def build_trace_metadata(state: dict[str, Any]) -> dict[str, Any]:
    return _compact(
        {
            "workflow_type": state.get("workflow_type") or "bounded_autosearch",
            "workflow_name": state.get("workflow_name"),
            "orchestration_runtime": state.get("orchestration_runtime"),
            "candidate_id": state.get("candidate_id"),
            "iteration": state.get("iteration"),
            "base_policy_path": state.get("base_policy_path"),
            "base_manifest_path": state.get("base_manifest_path"),
            "candidate_policy_path": state.get("candidate_policy_path"),
            "candidate_manifest_path": state.get("candidate_manifest_path"),
            "job_spec_path": state.get("job_spec_path"),
            "run_dir": state.get("run_dir"),
            "eval_summary_path": state.get("eval_summary_path"),
            "completed_run_manifest_path": state.get("completed_run_manifest_path"),
            "decision_record_path": state.get("decision_record_path"),
            "local_decision_path": state.get("local_decision_path"),
            "mutation_summary": state.get("mutation_summary"),
            "evaluator_status": state.get("evaluator_status"),
            "evaluator_returncode": state.get("evaluator_returncode"),
            "benchmark_status": state.get("benchmark_status"),
            "completion_status": state.get("completion_status"),
            "decision_category": state.get("decision_category"),
            "decision_outcome": state.get("orchestrator_decision"),
            "time_budget_seconds": state.get("time_budget_seconds"),
            "case_time_budget_seconds": state.get("case_time_budget_seconds"),
            "timeout_policy": state.get("timeout_policy"),
            "elapsed_seconds": state.get("elapsed_seconds"),
            "completed_cases": state.get("completed_cases"),
            "total_cases": state.get("total_cases"),
            "coverage_ratio": state.get("coverage_ratio"),
            "coverage_weight_ratio": state.get("coverage_weight_ratio"),
            "time_aware_score": state.get("time_aware_score"),
        }
    )


def build_trace_tags(state: dict[str, Any]) -> list[str]:
    tags = [
        "robocop",
        state.get("workflow_type") or "bounded_autosearch",
        "dry_run" if state.get("dry_run") else "real_run",
    ]
    for optional_tag in (
        state.get("completion_status"),
        state.get("benchmark_status"),
        state.get("decision_category"),
    ):
        if optional_tag:
            tags.append(str(optional_tag))
    return tags


def build_node_trace_metadata(node_name: str, state: dict[str, Any]) -> dict[str, Any]:
    metadata = build_trace_metadata(state)
    metadata["node_name"] = node_name
    if node_name == "load_request_context":
        metadata.update(
            _compact(
                {
                    "trace_enabled": (state.get("trace_status") or {}).get("enabled"),
                    "trace_reason": (state.get("trace_status") or {}).get("reason"),
                }
            )
        )
    elif node_name == "propose_candidate":
        mutation_significance = state.get("mutation_significance") or {}
        metadata.update(
            _compact(
                {
                    "mutation_field": mutation_significance.get("changed_field"),
                    "mutation_applied": mutation_significance.get("mutation_applied"),
                }
            )
        )
    elif node_name == "evaluate_candidate":
        metadata.update(
            _compact(
                {
                    "execution_command": state.get("execution_command"),
                }
            )
        )
    elif node_name == "derive_decision":
        metadata.update(
            _compact(
                {
                    "aggregate_score": state.get("aggregate_score"),
                    "mean_final_loss": state.get("mean_final_loss"),
                }
            )
        )
    elif node_name == "archive_result":
        metadata.update(
            _compact(
                {
                    "decision_record_path": state.get("decision_record_path"),
                    "local_decision_path": state.get("local_decision_path"),
                }
            )
        )
    return metadata


def build_node_trace_tags(node_name: str, state: dict[str, Any]) -> list[str]:
    tags = build_trace_tags(state)
    _append_tag(tags, f"node:{node_name}")
    if node_name == "evaluate_candidate":
        _append_tag(tags, f"evaluator:{state.get('evaluator_status')}" if state.get("evaluator_status") else None)
    if node_name == "derive_decision":
        _append_tag(tags, f"decision:{state.get('decision_category')}" if state.get("decision_category") else None)
        _append_tag(tags, f"benchmark:{state.get('benchmark_status')}" if state.get("benchmark_status") else None)
    if node_name == "archive_result":
        _append_tag(tags, f"archive:{state.get('orchestrator_decision')}" if state.get("orchestrator_decision") else None)
    return tags


def build_state_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    return _compact(
        {
            **build_trace_metadata(state),
            "trace_status": state.get("trace_status"),
            "execution_command": state.get("execution_command"),
            "artifact_refs": state.get("artifact_refs"),
        }
    )
