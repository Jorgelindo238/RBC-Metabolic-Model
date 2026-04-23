from __future__ import annotations

from html import escape
from typing import Any, Mapping, Optional


def _clean(value: Any, fallback: str = "n/a") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return escape(text if text else fallback)


def _format_float(value: Any, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return _clean(value)


def _format_bool(value: Any) -> str:
    return "true" if bool(value) else "false"


def _shorten(value: Any, limit: int = 280) -> str:
    text = _clean(value)
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def _trim_message(text: str, limit: int = 3900) -> str:
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def build_session_started_message(
    session_id: str,
    *,
    base_policy_path: str,
    base_manifest_path: str,
    max_iterations: int,
    loop_budget_seconds: Optional[float],
    time_budget_seconds: Optional[float],
    case_time_budget_seconds: Optional[float],
    timeout_policy: Optional[str],
    dry_run: bool,
    stop_on_keep: bool,
) -> str:
    message = "\n".join(
        [
            "<b>RoBoCop autosearch started</b>",
            f"session: <code>{_clean(session_id)}</code>",
            f"mode: <code>{'dry_run' if dry_run else 'live'}</code>",
            f"max_iterations: <code>{max_iterations}</code>",
            f"loop_budget_seconds: <code>{_format_float(loop_budget_seconds, digits=1)}</code>",
            f"time_budget_seconds: <code>{_format_float(time_budget_seconds, digits=1)}</code>",
            f"case_time_budget_seconds: <code>{_format_float(case_time_budget_seconds, digits=1)}</code>",
            f"timeout_policy: <code>{_clean(timeout_policy)}</code>",
            f"stop_on_keep: <code>{_format_bool(stop_on_keep)}</code>",
            f"base_policy: <code>{_clean(base_policy_path)}</code>",
            f"base_manifest: <code>{_clean(base_manifest_path)}</code>",
        ]
    )
    return _trim_message(message)


def build_iteration_message(
    session_id: str,
    iteration_record: Mapping[str, Any],
    *,
    max_iterations: Optional[int] = None,
) -> str:
    iteration = iteration_record.get("iteration", "?")
    headline = f"iteration {iteration}"
    if max_iterations is not None:
        headline = f"{headline}/{max_iterations}"
    message = "\n".join(
        [
            f"<b>RoBoCop {headline}</b>",
            f"session: <code>{_clean(session_id)}</code>",
            f"decision: <code>{_clean(iteration_record.get('decision'))}</code>",
            f"decision_category: <code>{_clean(iteration_record.get('decision_category'))}</code>",
            (
                "scores: "
                f"time_aware=<code>{_format_float(iteration_record.get('time_aware_score'))}</code> | "
                f"aggregate=<code>{_format_float(iteration_record.get('aggregate_score'))}</code> | "
                f"loss=<code>{_format_float(iteration_record.get('mean_final_loss'))}</code>"
            ),
            f"completion: <code>{_clean(iteration_record.get('completion_status'))}</code>",
            f"benchmark: <code>{_clean(iteration_record.get('benchmark_status'))}</code>",
            f"mutation: {_shorten(iteration_record.get('mutation_summary'))}",
            f"run_dir: <code>{_clean(iteration_record.get('run_dir'))}</code>",
            f"record: <code>{_clean(iteration_record.get('decision_record_path'))}</code>",
            f"reason: {_shorten(iteration_record.get('decision_reason'), limit=420)}",
        ]
    )
    return _trim_message(message)


def build_session_completed_message(
    session_summary: Mapping[str, Any],
    *,
    session_summary_path: Optional[str] = None,
) -> str:
    final_state = session_summary.get("final_iteration_state")
    final_decision = None
    if isinstance(final_state, Mapping):
        final_decision = final_state.get("orchestrator_decision") or final_state.get("decision")
    message = "\n".join(
        [
            "<b>RoBoCop session complete</b>",
            f"session: <code>{_clean(session_summary.get('session_id'))}</code>",
            f"stop_reason: <code>{_clean(session_summary.get('stop_reason'))}</code>",
            (
                "iterations: "
                f"<code>{_clean(session_summary.get('iterations_completed'))}</code> / "
                f"<code>{_clean(session_summary.get('max_iterations'))}</code>"
            ),
            f"keeps: <code>{_clean(session_summary.get('kept_iterations'))}</code>",
            f"final_decision: <code>{_clean(final_decision)}</code>",
            f"final_policy: <code>{_clean(session_summary.get('final_promoted_policy_path'))}</code>",
            f"final_manifest: <code>{_clean(session_summary.get('final_promoted_manifest_path'))}</code>",
            f"elapsed_seconds: <code>{_format_float(session_summary.get('elapsed_seconds'), digits=1)}</code>",
            f"summary: <code>{_clean(session_summary_path or session_summary.get('session_summary_path'))}</code>",
        ]
    )
    return _trim_message(message)


def build_session_failed_message(
    session_id: str,
    error: BaseException,
    *,
    iteration: Optional[int] = None,
    base_policy_path: Optional[str] = None,
) -> str:
    lines = [
        "<b>RoBoCop session failed</b>",
        f"session: <code>{_clean(session_id)}</code>",
    ]
    if iteration is not None:
        lines.append(f"iteration: <code>{iteration}</code>")
    if base_policy_path:
        lines.append(f"base_policy: <code>{_clean(base_policy_path)}</code>")
    lines.append(f"error: {_shorten(error, limit=700)}")
    return _trim_message("\n".join(lines))
