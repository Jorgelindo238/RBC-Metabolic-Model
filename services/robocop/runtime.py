from __future__ import annotations

from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from services.robocop.trace_context import (
    build_node_trace_metadata,
    build_node_trace_tags,
    build_state_snapshot,
    build_trace_metadata,
    build_trace_tags,
)
from services.robocop.tracing import get_langsmith_trace_status, trace_block


class RoBoCopState(TypedDict, total=False):
    workflow_type: str
    workflow_name: str
    orchestration_runtime: str
    base_policy_path: str
    base_manifest_path: str
    mutation_policy_path: str
    dry_run: bool
    time_budget_seconds: float | None
    case_time_budget_seconds: float | None
    timeout_policy: str | None
    candidate_id: str
    candidate_policy_path: str
    candidate_manifest_path: str
    job_spec_path: str
    run_dir: str
    job_payload: dict[str, Any]
    execution_command: list[str]
    evaluator_status: str
    evaluator_returncode: int | None
    evaluator_error: str | None
    eval_summary_path: str
    completed_run_manifest_path: str
    aggregate_score: float | None
    time_aware_score: float | None
    mean_final_loss: float | None
    benchmark_status: str
    completion_status: str
    elapsed_seconds: float | None
    coverage_ratio: float | None
    coverage_weight_ratio: float | None
    completed_cases: int | None
    total_cases: int | None
    timed_out: bool | None
    crashed: bool | None
    benchmark_summary: dict[str, Any]
    artifact_refs: dict[str, Any]
    mutation_significance: dict[str, Any]
    decision_record_path: str
    local_decision_path: str | None
    orchestrator_decision: str
    decision_policy: dict[str, Any]
    decision_inputs: dict[str, Any]
    decision_reason: str
    decision_category: str
    decision: str
    reason: str
    mutation_summary: str
    iteration: int
    trace_status: dict[str, Any]


NodeHandler = Callable[[RoBoCopState], dict[str, Any]]


def load_request_context(state: RoBoCopState) -> dict[str, Any]:
    return {
        "workflow_type": state.get("workflow_type") or "bounded_autosearch",
        "workflow_name": state.get("workflow_name") or "RoBoCop Bounded Autosearch",
        "orchestration_runtime": "robocop_langgraph_v1",
        "trace_status": get_langsmith_trace_status(),
    }


def _merge_trace_state(run_tree: Any, state: RoBoCopState, node_name: str | None = None) -> None:
    metadata = build_node_trace_metadata(node_name, state) if node_name else build_trace_metadata(state)
    tags = build_node_trace_tags(node_name, state) if node_name else build_trace_tags(state)
    if hasattr(run_tree, "metadata") and isinstance(run_tree.metadata, dict):
        run_tree.metadata.update(metadata)
    if hasattr(run_tree, "tags") and isinstance(run_tree.tags, list):
        for tag in tags:
            if tag not in run_tree.tags:
                run_tree.tags.append(tag)


def make_traced_node(node_name: str, handler: NodeHandler) -> NodeHandler:
    def _node(state: RoBoCopState) -> dict[str, Any]:
        metadata = build_node_trace_metadata(node_name, state)
        with trace_block(
            name=f"robocop.{node_name}",
            run_type="chain",
            inputs=build_state_snapshot(state),
            tags=build_node_trace_tags(node_name, state),
            metadata=metadata,
        ) as run_tree:
            updates = handler(state) or {}
            next_state = state | updates
            _merge_trace_state(run_tree, next_state, node_name)
            run_tree.end(outputs={"state_updates": build_state_snapshot(next_state)})
            return updates

    return _node


def build_bounded_autosearch_graph(handlers: dict[str, NodeHandler]):
    workflow = StateGraph(RoBoCopState)
    workflow.add_node("load_request_context", make_traced_node("load_request_context", load_request_context))
    workflow.add_node("propose_candidate", make_traced_node("propose_candidate", handlers["propose_candidate"]))
    workflow.add_node("evaluate_candidate", make_traced_node("evaluate_candidate", handlers["evaluate_candidate"]))
    workflow.add_node("derive_decision", make_traced_node("derive_decision", handlers["derive_decision"]))
    workflow.add_node("archive_result", make_traced_node("archive_result", handlers["archive_result"]))
    workflow.add_edge(START, "load_request_context")
    workflow.add_edge("load_request_context", "propose_candidate")
    workflow.add_edge("propose_candidate", "evaluate_candidate")
    workflow.add_edge("evaluate_candidate", "derive_decision")
    workflow.add_edge("derive_decision", "archive_result")
    workflow.add_edge("archive_result", END)
    return workflow.compile()


def invoke_bounded_autosearch(initial_state: RoBoCopState, handlers: dict[str, NodeHandler]) -> RoBoCopState:
    graph = build_bounded_autosearch_graph(handlers)
    with trace_block(
        name=initial_state.get("workflow_name") or "RoBoCop Bounded Autosearch",
        run_type="chain",
        inputs=build_state_snapshot(initial_state),
        tags=build_trace_tags(initial_state),
        metadata=build_trace_metadata(initial_state),
    ) as run_tree:
        final_state = graph.invoke(initial_state)
        _merge_trace_state(run_tree, final_state)
        run_tree.end(outputs={"final_state": build_state_snapshot(final_state)})
        return final_state
