"""Path 3 autonomous DeepAgents-driven calibration campaign runner.

This script ships ALONGSIDE ``scripts/run_bounded_autosearch.py``. It
does NOT replace it.

- ``scripts/run_bounded_autosearch.py`` remains the deterministic
  source-of-truth runner. Its behavior, mutation policy, decision
  policy, and ``autosearch_decisions.jsonl`` ledger are unchanged.
- ``scripts/run_agentic_autosearch.py`` (this file) drives a bounded
  autonomous campaign by invoking the DeepAgents supervisor in a loop.
  Each iteration the supervisor plans a scope, subprocesses the
  deterministic runner via the ``run_bounded_autosearch_subprocess``
  tool, runs triage on the result, and writes a verdict to
  ``Simulations/robocop_agentic/campaign_decisions.jsonl`` (the agentic
  ledger - separate from the canonical decisions ledger).

Operators can stop a runaway campaign at any time by ``touch``ing
``Simulations/robocop_agentic/STOP``. Hard caps in
:class:`services.robocop.agentic.budgets.CampaignBudget` enforce
iteration / wall-clock / USD / tool-call ceilings.

Usage
-----

::

    python -m scripts.run_agentic_autosearch ^
      --campaign-id phase6_purine_amp_repair ^
      --base-policy   config/<seed_policy>.json ^
      --base-manifest config/<seed_manifest>.json ^
      --max-iterations 3 ^
      --max-wall-seconds 1800 ^
      --max-usd 3.00

The supervisor inherits ``ROBOCOP_DEEPAGENT_MODEL`` (default
``openai:gpt-5.5``) and the same ``.env`` loading as
``services.robocop.agentic.offline_runner``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.robocop.agentic.budgets import (  # noqa: E402
    BudgetExceeded,
    CampaignBudget,
    DEFAULT_KILL_SWITCH,
)
from services.robocop.agentic.cost import (  # noqa: E402
    extract_usage_from_result,
)
from services.robocop.agentic.offline_runner import (  # noqa: E402
    _load_dotenv_if_available,
)
from services.robocop.agentic.robocop_deep_agent import (  # noqa: E402
    DeepAgentsNotInstalledError,
    build_robocop_deep_agent,
)
from services.robocop.agentic.tools import (  # noqa: E402
    AGENTIC_SANDBOX_ROOT,
    CAMPAIGN_DECISIONS_LEDGER,
    CAMPAIGN_RUNS_ROOT,
    set_mutation_context,
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe_print(line: str) -> None:
    """ASCII-safe stdout writer (Windows cp1252 friendly)."""

    try:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
    except UnicodeEncodeError:
        sys.stdout.buffer.write((line + "\n").encode("utf-8", errors="replace"))


def _build_iteration_message(
    campaign_id: str,
    iteration: int,
    base_policy: str,
    base_manifest: str,
    budget: CampaignBudget,
    seed_session_path: Optional[str],
    extra: Optional[str],
    prior_decisions_count: int,
) -> str:
    parts = [
        f"# Autonomous campaign iteration {iteration}/{budget.max_iterations}",
        f"campaign_id: {campaign_id}",
        f"base_policy: {base_policy}",
        f"base_manifest: {base_manifest}",
        f"budget remaining: iterations={budget.remaining_iterations()} "
        f"seconds={budget.remaining_seconds():.0f} usd={budget.remaining_usd():.4f}",
    ]
    if prior_decisions_count == 0:
        parts.append(
            "Prior campaign memory: NONE. This is the first iteration "
            "for this campaign. Skip read_session_memory on the campaign "
            "ledger and proceed directly to planning + subprocess."
        )
    else:
        parts.append(
            f"Prior campaign memory: {prior_decisions_count} decisions in "
            "Simulations/robocop_agentic/campaign_decisions.jsonl. Read "
            "with read_session_memory before planning."
        )
    if seed_session_path:
        parts.append(
            "Seed best_params.json (optional read with read_session_memory): "
            f"{seed_session_path}"
        )
    else:
        parts.append(
            "No --seed-session-path was provided. Use base_policy as the "
            "seed reference and skip seed best_params.json reads."
        )
    parts.append(
        "Follow the iteration contract from the system prompt exactly. "
        "End your turn with append_campaign_decision and a final JSON "
        "object summarizing the iteration."
    )
    if extra:
        parts.append(f"Operator note:\n{extra.strip()}")
    return "\n\n".join(parts)


def _count_prior_decisions(campaign_id: str) -> int:
    if not CAMPAIGN_DECISIONS_LEDGER.exists():
        return 0
    try:
        n = 0
        with CAMPAIGN_DECISIONS_LEDGER.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("campaign_id") == campaign_id:
                    n += 1
        return n
    except OSError:
        return 0


def _extract_final_text(result: Dict[str, Any]) -> str:
    msgs = result.get("messages") or [] if isinstance(result, dict) else []
    if not msgs:
        return ""
    last = msgs[-1]
    content = getattr(last, "content", None)
    if content is None and isinstance(last, dict):
        content = last.get("content")
    if isinstance(content, list):
        bits = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                bits.append(part.get("text", ""))
            elif isinstance(part, str):
                bits.append(part)
        return "\n".join(bits).strip()
    return (content or "").strip() if isinstance(content, str) else ""


def _try_parse_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    candidate = text.strip()
    if candidate.startswith("```"):
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


def run_autonomous_campaign(
    *,
    campaign_id: str,
    base_policy: str,
    base_manifest: str,
    seed_session_path: Optional[str],
    budget: CampaignBudget,
    model: Optional[str] = None,
    extra_context: Optional[str] = None,
) -> Dict[str, Any]:
    _load_dotenv_if_available()

    campaign_dir = CAMPAIGN_RUNS_ROOT / f"{campaign_id}_{_utc_stamp()}"
    campaign_dir.mkdir(parents=True, exist_ok=True)

    iteration_records: list = []
    stop_reason: Optional[str] = None

    set_mutation_context(allow_mutations=True, budget=budget)
    agent = build_robocop_deep_agent(
        model=model,
        allow_mutations=True,
        budget=budget,
    )

    while True:
        breach = budget.check()
        if breach is not None:
            stop_reason = str(breach)
            _safe_print(f"[campaign] stopping: {stop_reason}")
            break

        # ``budget.iterations`` is the count of COMPLETED iterations.
        # The one we are about to start is iterations + 1. We tick AFTER
        # the agent returns so that tool calls made inside this turn see
        # iterations < max_iterations and are allowed.
        iteration_idx = budget.iterations + 1
        _safe_print(
            f"[campaign] iteration {iteration_idx}/{budget.max_iterations} "
            f"(elapsed {budget.to_dict()['elapsed_seconds']}s, "
            f"usd {budget.usd_spent:.4f})"
        )

        prior_decisions = _count_prior_decisions(campaign_id)
        user_message = _build_iteration_message(
            campaign_id=campaign_id,
            iteration=iteration_idx,
            base_policy=base_policy,
            base_manifest=base_manifest,
            budget=budget,
            seed_session_path=seed_session_path,
            extra=extra_context,
            prior_decisions_count=prior_decisions,
        )
        invoke_input = {
            "messages": [{"role": "user", "content": user_message}],
        }

        try:
            raw_result = agent.invoke(invoke_input)
        except Exception as exc:  # noqa: BLE001 - surface, do not crash campaign
            stop_reason = f"agent.invoke raised {type(exc).__name__}: {exc}"
            _safe_print(f"[campaign] iteration error: {stop_reason}")
            break

        # Tick AFTER the agent finishes so the in-turn tool calls saw
        # an unsaturated iteration count.
        budget.tick_iteration()

        usage = extract_usage_from_result(raw_result, fallback_model=str(model or ""))
        if usage is not None:
            budget.add_cost_usd(usage.usd)

        final_text = _extract_final_text(
            raw_result if isinstance(raw_result, dict) else {}
        )
        parsed = _try_parse_json(final_text)

        iter_dir = campaign_dir / f"iter_{iteration_idx:03d}_{_utc_stamp()}"
        iter_dir.mkdir(parents=True, exist_ok=True)
        (iter_dir / "result.json").write_text(
            json.dumps(
                {
                    "campaign_id": campaign_id,
                    "iteration": iteration_idx,
                    "user_message": user_message,
                    "final_assistant_text": final_text,
                    "structured_recommendation": parsed,
                    "usage": usage.to_dict() if usage else None,
                    "budget_state": budget.to_dict(),
                },
                indent=2,
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )
        try:
            raw_dump = []
            for m in (raw_result.get("messages") if isinstance(raw_result, dict) else []) or []:
                raw_dump.append(
                    {
                        "type": type(m).__name__,
                        "content": getattr(m, "content", m if isinstance(m, dict) else str(m)),
                    }
                )
            (iter_dir / "messages.json").write_text(
                json.dumps(raw_dump, indent=2, ensure_ascii=True, default=str),
                encoding="utf-8",
            )
        except Exception as dump_exc:  # noqa: BLE001
            (iter_dir / "messages_error.txt").write_text(repr(dump_exc), encoding="utf-8")

        iteration_records.append(
            {
                "iteration": iteration_idx,
                "structured_recommendation": parsed,
                "usd_spent_so_far": round(budget.usd_spent, 6),
                "iter_dir": str(iter_dir.relative_to(REPO_ROOT)),
            }
        )

        if parsed and parsed.get("recommendation") == "keep":
            stop_reason = "supervisor recommendation=keep; stop_on_keep"
            _safe_print(f"[campaign] stopping after iteration {iteration_idx}: {stop_reason}")
            break

    summary = {
        "campaign_id": campaign_id,
        "base_policy": base_policy,
        "base_manifest": base_manifest,
        "model": model,
        "stop_reason": stop_reason,
        "budget_final": budget.to_dict(),
        "iterations": iteration_records,
        "campaign_dir": str(campaign_dir.relative_to(REPO_ROOT)),
        "campaign_decisions_ledger": str(
            CAMPAIGN_DECISIONS_LEDGER.relative_to(REPO_ROOT)
        ),
    }
    (campaign_dir / "campaign_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    return summary


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Path 3 autonomous DeepAgents-driven calibration campaign.",
    )
    p.add_argument("--campaign-id", required=True,
                   help="Operator-readable campaign id (used for run dir + ledger entries).")
    p.add_argument("--base-policy", required=True,
                   help="Repo-relative path to seed policy JSON.")
    p.add_argument("--base-manifest", required=True,
                   help="Repo-relative path to seed manifest JSON.")
    p.add_argument("--seed-session-path", default=None,
                   help="Optional repo-relative path to a seed best_params.json.")
    p.add_argument("--max-iterations", type=int, default=3,
                   help="Hard cap on supervisor turns (default 3).")
    p.add_argument("--max-wall-seconds", type=int, default=1800,
                   help="Hard cap on campaign wall-clock seconds (default 1800).")
    p.add_argument("--max-usd", type=float, default=3.0,
                   help="Hard cap on cumulative model-cost USD (default 3.0).")
    p.add_argument("--max-tool-calls", type=int, default=60,
                   help="Hard cap on cumulative tool calls (default 60).")
    p.add_argument("--anchor-drop-pct", type=float, default=0.25,
                   help="Protected anchor regression threshold (default 0.25).")
    p.add_argument("--kill-switch", default=str(DEFAULT_KILL_SWITCH),
                   help=f"Kill switch file (default {DEFAULT_KILL_SWITCH}).")
    p.add_argument("--model", default=None,
                   help="Model override (default env ROBOCOP_DEEPAGENT_MODEL or openai:gpt-5.5).")
    p.add_argument("--extra-context", default=None,
                   help="Optional operator paragraph appended to every iteration.")
    return p


def main(argv: Optional[list] = None) -> int:
    args = _build_parser().parse_args(argv)
    budget = CampaignBudget(
        max_iterations=max(1, int(args.max_iterations)),
        max_wall_seconds=max(60, float(args.max_wall_seconds)),
        max_usd=max(0.01, float(args.max_usd)),
        max_tool_calls=max(1, int(args.max_tool_calls)),
        anchor_drop_pct=max(0.0, float(args.anchor_drop_pct)),
        kill_switch_path=Path(args.kill_switch),
    )

    try:
        summary = run_autonomous_campaign(
            campaign_id=args.campaign_id,
            base_policy=args.base_policy,
            base_manifest=args.base_manifest,
            seed_session_path=args.seed_session_path,
            budget=budget,
            model=args.model,
            extra_context=args.extra_context,
        )
    except DeepAgentsNotInstalledError as exc:
        print(f"[robocop-agentic] {exc}", file=sys.stderr)
        return 2
    except BudgetExceeded as exc:
        print(f"[robocop-agentic] budget refused before start: {exc}", file=sys.stderr)
        return 3

    payload = json.dumps(summary, indent=2, ensure_ascii=True, default=str)
    _safe_print(payload)
    if summary.get("stop_reason") and "max_iterations" not in str(summary["stop_reason"]):
        # Non-clean stop = signal to operator
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
