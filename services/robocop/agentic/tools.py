"""Bounded tools for the RoBoCop DeepAgents supervisor.

Every tool here is intentionally narrow. Input paths are validated to
stay inside the repo and inside an explicit allow-list of directories.
No tool may mutate ``src/``, ``config/``, ``api/``, ``apps/``, or any
production calibration artifact.

Two write surfaces exist:

- ``Simulations/robocop_agentic/`` - agentic-only sandbox: recommendations
  ledger, run dirs, comparison reports, and (Path 3 autonomous mode)
  ``campaign_decisions.jsonl``.
- ``Simulations/<run-id>/`` - subprocessed by ``run_bounded_autosearch``
  when allow-mutations mode is enabled. Those artifacts follow the
  shape produced by ``scripts/run_bounded_autosearch.py``.

Heavy dependencies (``langchain_core.tools``, ``deepagents``) are
imported lazily so that ``import services.robocop.agentic.tools`` works
in environments without the optional agentic dependency set in the
root ``requirements.txt`` (e.g. ``qa/robocop`` test runs).

Mutation gating
---------------

Real execution of ``scripts/run_bounded_autosearch.py`` happens only
when the supervisor is built with ``allow_mutations=True`` AND the
campaign has provided a :class:`~services.robocop.agentic.budgets.CampaignBudget`.
The two flags travel through module-level state set by
:func:`set_mutation_context`. The default state is read-only / dry-run.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .budgets import CampaignBudget

# ---------------------------------------------------------------------------
# Repository layout / safety helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
AGENTIC_SANDBOX_ROOT = REPO_ROOT / "Simulations" / "robocop_agentic"
RECOMMENDATIONS_LEDGER = AGENTIC_SANDBOX_ROOT / "recommendations.jsonl"
CAMPAIGN_DECISIONS_LEDGER = AGENTIC_SANDBOX_ROOT / "campaign_decisions.jsonl"
CAMPAIGN_RUNS_ROOT = AGENTIC_SANDBOX_ROOT / "campaign_runs"

# Subprocess hard caps. The agent can pick lower values via spec, but
# never higher. These are independent of the campaign-level
# CampaignBudget caps and serve as a per-tool-call belt and braces.
SUBPROCESS_MAX_ITERATIONS = 3
SUBPROCESS_MAX_LOOP_BUDGET_SECONDS = 1800
SUBPROCESS_HARD_TIMEOUT_SECONDS = SUBPROCESS_MAX_LOOP_BUDGET_SECONDS + 1800

READABLE_ROOTS = (
    REPO_ROOT / "Simulations",
    REPO_ROOT / "AgentOps",
    REPO_ROOT / "config",
)

WRITABLE_ROOTS = (
    AGENTIC_SANDBOX_ROOT,
)


# ---------------------------------------------------------------------------
# Mutation context (set by the autonomous campaign runner only)
# ---------------------------------------------------------------------------

_AGENTIC_ALLOW_MUTATIONS: bool = False
_AGENTIC_BUDGET: Optional[CampaignBudget] = None


def set_mutation_context(
    *,
    allow_mutations: bool,
    budget: Optional[CampaignBudget] = None,
) -> None:
    """Toggle real-execution mode for the autonomous runner.

    Default is OFF. The offline single-shot runner never calls this,
    so its tools stay dry-run as before. Only
    :mod:`scripts.run_agentic_autosearch` (Path 3 autonomous mode)
    flips it on, and only after constructing a
    :class:`CampaignBudget`.
    """

    global _AGENTIC_ALLOW_MUTATIONS, _AGENTIC_BUDGET
    _AGENTIC_ALLOW_MUTATIONS = bool(allow_mutations)
    _AGENTIC_BUDGET = budget


def get_mutation_context() -> Dict[str, Any]:
    return {
        "allow_mutations": _AGENTIC_ALLOW_MUTATIONS,
        "budget": _AGENTIC_BUDGET.to_dict() if _AGENTIC_BUDGET else None,
    }


class ToolPermissionError(RuntimeError):
    """Raised when a tool is asked to read/write outside its allow-list."""


def _resolve_inside(path_str: str, allowed_roots: Sequence[Path]) -> Path:
    """Resolve ``path_str`` and ensure it is under one of ``allowed_roots``."""

    candidate = (REPO_ROOT / path_str).resolve() if not os.path.isabs(path_str) else Path(path_str).resolve()
    for root in allowed_roots:
        try:
            candidate.relative_to(root.resolve())
            return candidate
        except ValueError:
            continue
    allowed = ", ".join(str(r) for r in allowed_roots)
    raise ToolPermissionError(f"Path {candidate} is not inside the allow-list: {allowed}")


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _ensure_sandbox() -> None:
    AGENTIC_SANDBOX_ROOT.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Tool implementations (plain functions, decorated lazily)
# ---------------------------------------------------------------------------

def _impl_read_session_memory(session_path: str) -> Dict[str, Any]:
    """Read a RoBoCop autosearch session summary, best-params JSON,
    or an append-only ``.jsonl`` ledger (e.g. campaign_decisions.jsonl).

    ``session_path`` must be relative to the repo root and live under
    ``Simulations/`` or ``AgentOps/``. For ``.json``: returns ``payload``
    plus a small summary. For ``.jsonl``: returns the most recent N
    records (capped) plus the total count.
    """

    resolved = _resolve_inside(session_path, READABLE_ROOTS)
    if not resolved.exists():
        return {"ok": False, "error": f"file not found: {resolved}"}

    suffix = resolved.suffix.lower()
    if suffix == ".jsonl":
        records: List[Dict[str, Any]] = []
        bad_lines = 0
        with resolved.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    bad_lines += 1
        # Cap returned tail to keep prompt size sane.
        TAIL = 25
        return {
            "ok": True,
            "path": str(resolved.relative_to(REPO_ROOT)),
            "format": "jsonl",
            "total_records": len(records),
            "bad_lines": bad_lines,
            "records_tail": records[-TAIL:],
        }

    if suffix != ".json":
        return {
            "ok": False,
            "error": f"only .json or .jsonl supported here, got {resolved.suffix}",
        }

    payload = _read_json(resolved)
    summary_keys = (
        "session_id",
        "best_loss",
        "best_params_path",
        "decision",
        "iteration",
        "max_iterations",
        "aggregate_score",
        "mean_final_loss",
    )
    if isinstance(payload, dict):
        short_summary = {k: payload.get(k) for k in summary_keys if k in payload}
    else:
        short_summary = {}
    return {
        "ok": True,
        "path": str(resolved.relative_to(REPO_ROOT)),
        "format": "json",
        "summary": short_summary,
        "payload": payload,
    }


def _impl_run_curve_triage(eval_summary_path: str) -> Dict[str, Any]:
    """Run the existing ``curve_triage`` on an eval-summary JSON."""

    from services.robocop.curve_triage import triage_calibration_report  # lazy

    resolved = _resolve_inside(eval_summary_path, READABLE_ROOTS)
    if not resolved.exists():
        return {"ok": False, "error": f"file not found: {resolved}"}
    report = _read_json(resolved)
    verdict = triage_calibration_report(report)
    payload = verdict.to_dict() if hasattr(verdict, "to_dict") else dict(verdict.__dict__)
    return {
        "ok": True,
        "eval_summary_path": str(resolved.relative_to(REPO_ROOT)),
        "verdict": payload,
    }


def _impl_run_pure_ode_replay(trajectories_csv_path: str) -> Dict[str, Any]:
    """Run pure-ODE triage on a trajectory CSV (read-only)."""

    from services.robocop.pure_ode_triage import triage_pure_ode_csv  # lazy

    resolved = _resolve_inside(trajectories_csv_path, READABLE_ROOTS)
    if not resolved.exists():
        return {"ok": False, "error": f"file not found: {resolved}"}
    verdict = triage_pure_ode_csv(resolved)
    payload = verdict.to_dict() if hasattr(verdict, "to_dict") else dict(verdict.__dict__)
    return {
        "ok": True,
        "trajectories_csv_path": str(resolved.relative_to(REPO_ROOT)),
        "verdict": payload,
    }


def _impl_run_combined_triage(
    eval_summary_path: str,
    trajectories_csv_path: str,
) -> Dict[str, Any]:
    """Compose curve triage + pure-ODE triage into a combined verdict."""

    from services.robocop.pure_ode_triage import combine_triage_verdicts  # lazy

    cal = _impl_run_curve_triage(eval_summary_path)
    pure = _impl_run_pure_ode_replay(trajectories_csv_path)
    if not cal.get("ok") or not pure.get("ok"):
        return {"ok": False, "curve": cal, "pure_ode": pure}

    combined = combine_triage_verdicts(cal["verdict"], pure["verdict"])
    payload = combined.to_dict() if hasattr(combined, "to_dict") else dict(combined.__dict__)
    return {
        "ok": True,
        "curve": cal,
        "pure_ode": pure,
        "combined_verdict": payload,
    }


def _impl_run_strategy_race(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Prototype: this tool is a *dry-run* in the offline supervisor.

    It does not launch a real strategy race. It returns the resolved
    plan that would be executed so the supervisor can include it in a
    recommendation. Real execution stays under ``scripts/`` and the
    existing LangGraph runner during the prototype phase.
    """

    return {
        "ok": True,
        "dry_run": True,
        "would_run": "services.robocop.runtime.invoke_bounded_autosearch",
        "spec": spec,
        "note": (
            "Prototype phase: strategy race is not executed by the DeepAgent. "
            "Use scripts/run_bounded_autosearch.py for real execution and "
            "compare_with_langgraph.py for parity checks."
        ),
    }


def _impl_run_teacher_flux_rescue(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Prototype: dry-run wrapper around teacher-flux rescue."""

    return {
        "ok": True,
        "dry_run": True,
        "would_run": "services.robocop.teacher_flux_sandbox.run_glucose_teacher_autoresearch",
        "spec": spec,
        "note": (
            "Prototype phase: teacher-flux rescue is not executed by the "
            "DeepAgent. The wrapper exists to plan, not to mutate parameters."
        ),
    }


def _impl_summarize_campaign(session_path: str) -> Dict[str, Any]:
    """Compact human-readable summary of a session_*.json payload."""

    info = _impl_read_session_memory(session_path)
    if not info.get("ok"):
        return info
    payload = info["payload"]
    iterations = payload.get("iterations") or payload.get("history") or []
    last_iter = iterations[-1] if isinstance(iterations, list) and iterations else None
    return {
        "ok": True,
        "path": info["path"],
        "session_id": payload.get("session_id"),
        "iteration_count": len(iterations) if isinstance(iterations, list) else None,
        "last_decision": (last_iter or {}).get("decision") if isinstance(last_iter, dict) else None,
        "best_loss": payload.get("best_loss"),
        "best_params_path": payload.get("best_params_path"),
        "summary": info["summary"],
    }


def _impl_append_recommendation(record: Dict[str, Any]) -> Dict[str, Any]:
    """Append a single recommendation record to the agentic-only ledger.

    Validates the schema enforced by the supervisor system prompt and
    refuses to write incomplete records. The ledger lives under
    ``Simulations/robocop_agentic/recommendations.jsonl`` and is never
    used by the production calibration pipeline.
    """

    required = (
        "session_id",
        "recommendation",
        "rationale",
        "supporting_artifacts",
    )
    missing = [k for k in required if k not in record]
    if missing:
        return {"ok": False, "error": f"missing required fields: {missing}"}
    if record["recommendation"] not in ("keep", "informative", "discard"):
        return {"ok": False, "error": "recommendation must be keep|informative|discard"}

    record = dict(record)
    record.setdefault("comparison_to_langgraph_required", True)
    record["written_at_utc"] = datetime.now(timezone.utc).isoformat()

    _ensure_sandbox()
    with RECOMMENDATIONS_LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    try:
        ledger_display = str(RECOMMENDATIONS_LEDGER.relative_to(REPO_ROOT))
    except ValueError:
        ledger_display = str(RECOMMENDATIONS_LEDGER)
    return {
        "ok": True,
        "ledger_path": ledger_display,
        "record": record,
    }


# ---------------------------------------------------------------------------
# Path 3 autonomous: real subprocess execution + campaign-decisions ledger
# ---------------------------------------------------------------------------


def _impl_run_bounded_autosearch_subprocess(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Subprocess ``scripts/run_bounded_autosearch.py`` with bounded args.

    ``spec`` must include:
      - ``base_policy`` (str, repo-relative path under config/ or Simulations/)
      - ``base_manifest`` (str, repo-relative path under config/ or Simulations/)
      - ``max_iterations`` (int <= SUBPROCESS_MAX_ITERATIONS)
      - ``loop_budget_seconds`` (int <= SUBPROCESS_MAX_LOOP_BUDGET_SECONDS)

    Optional:
      - ``mutation_policy`` (str, default config/autoresearch_mutation_policy.yaml)
      - ``stop_on_keep`` (bool, default True)
      - ``dry_run`` (bool, default False - if True, --dry-run is forwarded)
      - ``rationale`` (str) - operator-readable reason recorded in the result

    Returns a dict with ``ok``, ``stdout`` (truncated tail), ``stderr``
    (truncated tail), ``returncode``, ``elapsed_seconds``, and the
    ``spec_used`` after clamping to caps. The autonomous runner then
    reads the produced session_*.json from
    ``Simulations/autoresearch/sessions/`` to inspect the result.

    Refused unless :func:`set_mutation_context` was called with
    ``allow_mutations=True``. Refused immediately if the campaign
    :class:`CampaignBudget` reports a kill switch or exhaustion.
    """

    if not _AGENTIC_ALLOW_MUTATIONS:
        return {
            "ok": False,
            "error": (
                "real subprocess execution is disabled in this supervisor "
                "build (allow_mutations is False). Use run_strategy_race for "
                "a dry-run plan, or rebuild the supervisor via "
                "scripts.run_agentic_autosearch with explicit allow-mutations."
            ),
        }
    if _AGENTIC_BUDGET is not None:
        breach = _AGENTIC_BUDGET.check()
        if breach is not None:
            return {"ok": False, "error": f"budget refused: {breach}"}
        _AGENTIC_BUDGET.tick_tool_call()

    if not isinstance(spec, dict):
        return {"ok": False, "error": "spec must be a dict"}
    base_policy = spec.get("base_policy")
    base_manifest = spec.get("base_manifest")
    if not (isinstance(base_policy, str) and isinstance(base_manifest, str)):
        return {"ok": False, "error": "spec must include base_policy + base_manifest"}

    try:
        base_policy_resolved = _resolve_inside(base_policy, READABLE_ROOTS)
        base_manifest_resolved = _resolve_inside(base_manifest, READABLE_ROOTS)
    except ToolPermissionError as exc:
        return {"ok": False, "error": str(exc)}

    if not base_policy_resolved.exists():
        return {"ok": False, "error": f"base_policy not found: {base_policy_resolved}"}
    if not base_manifest_resolved.exists():
        return {"ok": False, "error": f"base_manifest not found: {base_manifest_resolved}"}

    max_iters = int(spec.get("max_iterations", 1))
    max_iters = max(1, min(max_iters, SUBPROCESS_MAX_ITERATIONS))
    loop_budget = int(spec.get("loop_budget_seconds", 600))
    loop_budget = max(60, min(loop_budget, SUBPROCESS_MAX_LOOP_BUDGET_SECONDS))
    stop_on_keep = bool(spec.get("stop_on_keep", True))
    dry_run = bool(spec.get("dry_run", False))
    mutation_policy = spec.get("mutation_policy")

    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_bounded_autosearch.py"),
        "--base-policy", str(base_policy_resolved),
        "--base-manifest", str(base_manifest_resolved),
        "--max-iterations", str(max_iters),
        "--loop-budget-seconds", str(loop_budget),
    ]
    if stop_on_keep:
        cmd.append("--stop-on-keep")
    if dry_run:
        cmd.append("--dry-run")
    if isinstance(mutation_policy, str):
        try:
            mp_resolved = _resolve_inside(mutation_policy, READABLE_ROOTS)
        except ToolPermissionError as exc:
            return {"ok": False, "error": str(exc)}
        cmd.extend(["--mutation-policy", str(mp_resolved)])

    spec_used = {
        "base_policy": str(base_policy_resolved.relative_to(REPO_ROOT)),
        "base_manifest": str(base_manifest_resolved.relative_to(REPO_ROOT)),
        "max_iterations": max_iters,
        "loop_budget_seconds": loop_budget,
        "stop_on_keep": stop_on_keep,
        "dry_run": dry_run,
        "mutation_policy": mutation_policy,
    }

    started = datetime.now(timezone.utc)
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_HARD_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "error": f"subprocess timed out after {SUBPROCESS_HARD_TIMEOUT_SECONDS}s",
            "spec_used": spec_used,
            "stdout_tail": (exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-2000:] if isinstance(exc.stderr, str) else "",
        }
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()

    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "elapsed_seconds": round(elapsed, 2),
        "stdout_tail": (proc.stdout or "")[-2000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
        "spec_used": spec_used,
        "rationale": spec.get("rationale"),
    }


def _impl_append_campaign_decision(record: Dict[str, Any]) -> Dict[str, Any]:
    """Append an autonomous-campaign decision to the agentic-only ledger.

    Schema (required):
      - ``campaign_id`` (str)
      - ``iteration`` (int)
      - ``decision`` (str, one of ``keep|informative|discard``)
      - ``rationale`` (str)
      - ``supporting_artifacts`` (list[str])

    Optional but recommended:
      - ``triage_verdicts`` (dict)
      - ``protected_anchors_before`` / ``protected_anchors_after``
      - ``budget_state`` (dict, snapshot of CampaignBudget.to_dict())
    """

    required = ("campaign_id", "iteration", "decision", "rationale", "supporting_artifacts")
    missing = [k for k in required if k not in record]
    if missing:
        return {"ok": False, "error": f"missing required fields: {missing}"}
    if record["decision"] not in ("keep", "informative", "discard"):
        return {"ok": False, "error": "decision must be keep|informative|discard"}

    record = dict(record)
    record["written_at_utc"] = datetime.now(timezone.utc).isoformat()
    if _AGENTIC_BUDGET is not None and "budget_state" not in record:
        record["budget_state"] = _AGENTIC_BUDGET.to_dict()

    _ensure_sandbox()
    with CAMPAIGN_DECISIONS_LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    try:
        ledger_display = str(CAMPAIGN_DECISIONS_LEDGER.relative_to(REPO_ROOT))
    except ValueError:
        ledger_display = str(CAMPAIGN_DECISIONS_LEDGER)
    return {
        "ok": True,
        "ledger_path": ledger_display,
        "record": record,
    }


# ---------------------------------------------------------------------------
# Public tool registry (LangChain StructuredTool factory)
# ---------------------------------------------------------------------------

def build_tool_registry() -> List[Any]:
    """Return the full LangChain tool list for the supervisor.

    Imported lazily so that this module can be inspected/tested without
    the optional ``langchain`` install.
    """

    from langchain_core.tools import tool  # lazy

    @tool
    def read_session_memory(session_path: str) -> Dict[str, Any]:
        """Read a session_*.json or best_params.json under Simulations/. Read-only."""
        return _impl_read_session_memory(session_path)

    @tool
    def run_curve_triage(eval_summary_path: str) -> Dict[str, Any]:
        """Run programmatic curve triage on an eval-summary JSON. Read-only."""
        return _impl_run_curve_triage(eval_summary_path)

    @tool
    def run_pure_ode_replay(trajectories_csv_path: str) -> Dict[str, Any]:
        """Run pure-ODE triage on a trajectory CSV. Read-only."""
        return _impl_run_pure_ode_replay(trajectories_csv_path)

    @tool
    def run_combined_triage(
        eval_summary_path: str,
        trajectories_csv_path: str,
    ) -> Dict[str, Any]:
        """Compose curve triage + pure-ODE triage into a combined verdict. Read-only."""
        return _impl_run_combined_triage(eval_summary_path, trajectories_csv_path)

    @tool
    def run_strategy_race(spec: Dict[str, Any]) -> Dict[str, Any]:
        """Prototype dry-run: returns the plan a real strategy race would run."""
        return _impl_run_strategy_race(spec)

    @tool
    def run_teacher_flux_rescue(spec: Dict[str, Any]) -> Dict[str, Any]:
        """Prototype dry-run: returns the plan a real teacher-flux rescue would run."""
        return _impl_run_teacher_flux_rescue(spec)

    @tool
    def summarize_campaign(session_path: str) -> Dict[str, Any]:
        """Compact summary of a session_*.json payload. Read-only."""
        return _impl_summarize_campaign(session_path)

    @tool
    def append_recommendation(record: Dict[str, Any]) -> Dict[str, Any]:
        """Append a single recommendation to the agentic-only ledger.

        Required fields: session_id, recommendation
        ('keep'|'informative'|'discard'), rationale, supporting_artifacts.
        Writes only under Simulations/robocop_agentic/.
        """
        return _impl_append_recommendation(record)

    @tool
    def run_bounded_autosearch_subprocess(
        base_policy: str,
        base_manifest: str,
        max_iterations: int = 1,
        loop_budget_seconds: int = 600,
        mutation_policy: Optional[str] = None,
        stop_on_keep: bool = True,
        dry_run: bool = False,
        rationale: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Path 3 autonomous: subprocess scripts/run_bounded_autosearch.py.

        Refused unless the supervisor was built with allow_mutations=True.
        Args are clamped to per-call hard caps regardless of input.

        Args:
          base_policy: repo-relative path to seed policy JSON.
          base_manifest: repo-relative path to seed manifest JSON.
          max_iterations: bounded iterations (clamped <= 3).
          loop_budget_seconds: wall-clock cap (clamped <= 1800).
          mutation_policy: optional repo-relative YAML.
          stop_on_keep: stop on first keep verdict (default true).
          dry_run: if true, forwards --dry-run (no scientific eval).
          rationale: operator-readable reason recorded in the result.

        Returns dict with ``ok``, ``returncode``, ``elapsed_seconds``,
        ``stdout_tail``, ``stderr_tail``, and the clamped ``spec_used``.
        """
        return _impl_run_bounded_autosearch_subprocess(
            {
                "base_policy": base_policy,
                "base_manifest": base_manifest,
                "max_iterations": max_iterations,
                "loop_budget_seconds": loop_budget_seconds,
                "mutation_policy": mutation_policy,
                "stop_on_keep": stop_on_keep,
                "dry_run": dry_run,
                "rationale": rationale,
            }
        )

    @tool
    def append_campaign_decision(record: Dict[str, Any]) -> Dict[str, Any]:
        """Path 3 autonomous: append a campaign-level decision to the
        agentic-only ledger Simulations/robocop_agentic/campaign_decisions.jsonl.

        Required fields: campaign_id, iteration, decision
        ('keep'|'informative'|'discard'), rationale, supporting_artifacts.
        """
        return _impl_append_campaign_decision(record)

    return [
        read_session_memory,
        run_curve_triage,
        run_pure_ode_replay,
        run_combined_triage,
        run_strategy_race,
        run_teacher_flux_rescue,
        summarize_campaign,
        append_recommendation,
        run_bounded_autosearch_subprocess,
        append_campaign_decision,
    ]


# Tool name -> set of tool names a subagent is allowed to call. Used by
# subagents.py to construct DeepAgents subagent definitions.
SUBAGENT_TOOL_ACL = {
    "planner": {
        "read_session_memory",
        "summarize_campaign",
    },
    "triage_analyst": {
        "read_session_memory",
        "run_curve_triage",
        "run_pure_ode_replay",
        "run_combined_triage",
    },
    "archivist": {
        "read_session_memory",
        "summarize_campaign",
        "append_recommendation",
        "append_campaign_decision",
    },
}
