"""Offline runner for the RoBoCop DeepAgents supervisor prototype.

Usage:

    python -m services.robocop.agentic.offline_runner \\
        --goal "Triage Phase 5b purine_transport best params" \\
        --session-path Simulations/brodbar/calibration/purine_phase5b_bordbar_ic/best_params.json

The script:

1. Builds the supervisor graph via :func:`build_robocop_deep_agent`.
2. Sends a single user turn that combines the campaign goal with a
   pointer to the seed session and the standard JSON output contract.
3. Captures the final assistant message + the structured recommendation
   (if the model emitted JSON).
4. Writes the full result under
   ``Simulations/robocop_agentic/runs/<timestamp>/result.json``.

The runner intentionally does NOT compare to the LangGraph runner -
that is handled by :mod:`compare_with_langgraph`.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .robocop_deep_agent import (
    DeepAgentsNotInstalledError,
    build_robocop_deep_agent,
)
from .tools import AGENTIC_SANDBOX_ROOT, REPO_ROOT


RUNS_ROOT = AGENTIC_SANDBOX_ROOT / "runs"


def _load_dotenv_if_available() -> None:
    """Best-effort load of ``<repo>/.env`` so OPENAI_API_KEY / LANGSMITH_*
    env vars stored there reach the supervisor without manual export.

    No-op if ``python-dotenv`` is not installed or ``.env`` is missing.
    Already-set environment variables are NOT overridden.
    """

    try:
        from dotenv import load_dotenv  # type: ignore[import-not-found]
    except ImportError:
        return
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _build_user_message(
    goal: str,
    session_path: Optional[str],
    eval_summary_path: Optional[str],
    trajectories_csv_path: Optional[str],
    extra: Optional[str],
) -> str:
    parts = [
        f"Campaign goal: {goal.strip()}",
    ]
    if session_path:
        parts.append(
            "Seed session memory (read with the read_session_memory tool, "
            f"path is repo-relative): {session_path}"
        )
    if eval_summary_path or trajectories_csv_path:
        artifact_lines = ["Candidate triage artifacts (use the triage tools):"]
        if eval_summary_path:
            artifact_lines.append(
                f"- eval_summary_path (for run_curve_triage): {eval_summary_path}"
            )
        if trajectories_csv_path:
            artifact_lines.append(
                "- trajectories_csv_path (for run_pure_ode_replay): "
                f"{trajectories_csv_path}"
            )
        if eval_summary_path and trajectories_csv_path:
            artifact_lines.append(
                "- combine via run_combined_triage when both succeed"
            )
        parts.append("\n".join(artifact_lines))
    parts.append(
        "When you are done, your final assistant message MUST be a single "
        "JSON object matching the contract in the system prompt."
    )
    if extra:
        parts.append(f"Extra context from operator:\n{extra.strip()}")
    return "\n\n".join(parts)


def _extract_final_text(result: Dict[str, Any]) -> str:
    messages = result.get("messages") or []
    if not messages:
        return ""
    last = messages[-1]
    content = getattr(last, "content", None)
    if content is None and isinstance(last, dict):
        content = last.get("content")
    if isinstance(content, list):
        # OpenAI tool-calling format: list of content parts
        text_parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text_parts.append(part.get("text", ""))
            elif isinstance(part, str):
                text_parts.append(part)
        return "\n".join(text_parts).strip()
    return (content or "").strip() if isinstance(content, str) else ""


def _try_parse_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    candidate = text.strip()
    if candidate.startswith("```"):
        # strip common ```json fences
        lines = candidate.splitlines()
        if len(lines) >= 2:
            lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            candidate = "\n".join(lines).strip()
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def run_offline_campaign(
    goal: str,
    *,
    session_path: Optional[str] = None,
    eval_summary_path: Optional[str] = None,
    trajectories_csv_path: Optional[str] = None,
    extra_context: Optional[str] = None,
    model: Optional[str] = None,
    out_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run a single offline supervisor invocation and return the result."""

    _load_dotenv_if_available()
    agent = build_robocop_deep_agent(model=model)
    user_message = _build_user_message(
        goal,
        session_path,
        eval_summary_path,
        trajectories_csv_path,
        extra_context,
    )

    invoke_input = {"messages": [{"role": "user", "content": user_message}]}
    raw_result = agent.invoke(invoke_input)

    final_text = _extract_final_text(raw_result if isinstance(raw_result, dict) else {})
    parsed = _try_parse_json(final_text)

    out_dir = out_dir or (RUNS_ROOT / _utc_stamp())
    # Resolve relative paths against REPO_ROOT so result_payload["out_dir"]
    # always reports a repo-relative path on stdout.
    if not out_dir.is_absolute():
        out_dir = (REPO_ROOT / out_dir).resolve()
    else:
        out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    result_payload = {
        "goal": goal,
        "session_path": session_path,
        "model": model,
        "user_message": user_message,
        "final_assistant_text": final_text,
        "structured_recommendation": parsed,
        "comparison_to_langgraph_required": True,
    }
    (out_dir / "result.json").write_text(
        json.dumps(result_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    # Persist the raw message trail for debugging (best-effort string repr).
    try:
        raw_dump = []
        for m in (raw_result.get("messages") if isinstance(raw_result, dict) else []) or []:
            raw_dump.append({
                "type": type(m).__name__,
                "content": getattr(m, "content", m if isinstance(m, dict) else str(m)),
            })
        (out_dir / "messages.json").write_text(
            json.dumps(raw_dump, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001 - best-effort debug artifact
        (out_dir / "messages_error.txt").write_text(repr(exc), encoding="utf-8")

    result_payload["out_dir"] = str(out_dir.relative_to(REPO_ROOT))
    return result_payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Offline runner for the RoBoCop DeepAgents supervisor prototype.",
    )
    parser.add_argument("--goal", required=True, help="Short campaign goal for the supervisor.")
    parser.add_argument(
        "--session-path",
        default=None,
        help="Repo-relative path to a session_*.json or best_params.json under Simulations/.",
    )
    parser.add_argument(
        "--eval-summary",
        default=None,
        help="Repo-relative path to an eval-summary JSON (passed to run_curve_triage).",
    )
    parser.add_argument(
        "--trajectories-csv",
        default=None,
        help="Repo-relative path to a trajectory CSV (passed to run_pure_ode_replay).",
    )
    parser.add_argument(
        "--extra-context",
        default=None,
        help="Optional extra context paragraph passed to the supervisor.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override the model id (default: env ROBOCOP_DEEPAGENT_MODEL or openai:gpt-5.5).",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Optional output dir under Simulations/robocop_agentic/runs/.",
    )
    return parser


def main(argv: Optional[list] = None) -> int:
    args = _build_parser().parse_args(argv)
    out_dir = Path(args.out_dir) if args.out_dir else None
    try:
        result = run_offline_campaign(
            args.goal,
            session_path=args.session_path,
            eval_summary_path=args.eval_summary,
            trajectories_csv_path=args.trajectories_csv,
            extra_context=args.extra_context,
            model=args.model,
            out_dir=out_dir,
        )
    except DeepAgentsNotInstalledError as exc:
        print(f"[robocop-agentic] {exc}", file=sys.stderr)
        return 2
    # ensure_ascii=True keeps the stdout dump safe on Windows shells whose
    # default codec is cp1252; the run_*/result.json file on disk is always
    # written as UTF-8.
    payload = json.dumps(result, indent=2, ensure_ascii=True, default=str)
    try:
        sys.stdout.write(payload + "\n")
    except UnicodeEncodeError:  # pragma: no cover - belt-and-braces
        sys.stdout.buffer.write((payload + "\n").encode("utf-8", errors="replace"))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
