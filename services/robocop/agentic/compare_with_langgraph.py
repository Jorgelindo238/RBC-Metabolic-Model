"""Compare a DeepAgents supervisor recommendation to the existing
LangGraph bounded-autosearch decision for the same seed/scope.

This is the parity gate from ``AgentOps/CalibrationOps.md`` -
``DeepAgents prototype rules`` and from ``AgentOps/Playbooks.md`` -
``DeepAgents RoBoCop prototype``. The DeepAgents recommendation is
NEVER promoted automatically. This script just emits the comparison so
the operator can read it.

Inputs:

- ``--agentic-result``: path to a ``result.json`` written by
  :mod:`offline_runner`.
- ``--langgraph-decision``: path to an autosearch decision/session
  summary JSON written by ``scripts/run_bounded_autosearch.py`` for the
  same seed.

Output: a JSON report under
``Simulations/robocop_agentic/comparisons/<timestamp>/comparison.json``
with the agreement verdict and a short prose summary.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .tools import AGENTIC_SANDBOX_ROOT, REPO_ROOT


COMPARISONS_ROOT = AGENTIC_SANDBOX_ROOT / "comparisons"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _normalize_decision(value: Optional[str]) -> str:
    if not value:
        return "unknown"
    v = str(value).strip().lower()
    aliases = {
        "keep": "keep",
        "promote": "keep",
        "accept": "keep",
        "discard": "discard",
        "reject": "discard",
        "informative": "informative",
        "needs_review": "informative",
    }
    return aliases.get(v, v)


def _extract_agentic_decision(payload: Dict[str, Any]) -> Optional[str]:
    rec = payload.get("structured_recommendation") or {}
    if isinstance(rec, dict):
        return rec.get("recommendation")
    return None


def _extract_langgraph_decision(payload: Dict[str, Any]) -> Optional[str]:
    # Try several common shapes from scripts/run_bounded_autosearch.py outputs.
    for key in ("decision", "final_decision", "outcome"):
        if isinstance(payload.get(key), str):
            return payload[key]
    history = payload.get("iterations") or payload.get("history")
    if isinstance(history, list) and history:
        last = history[-1]
        if isinstance(last, dict):
            for key in ("decision", "outcome"):
                if isinstance(last.get(key), str):
                    return last[key]
    return None


def compare(agentic_path: Path, langgraph_path: Path, out_dir: Optional[Path] = None) -> Dict[str, Any]:
    agentic_payload = _load_json(agentic_path)
    langgraph_payload = _load_json(langgraph_path)

    agentic_raw = _extract_agentic_decision(agentic_payload)
    langgraph_raw = _extract_langgraph_decision(langgraph_payload)

    agentic = _normalize_decision(agentic_raw)
    langgraph = _normalize_decision(langgraph_raw)

    agree = agentic == langgraph and agentic != "unknown"
    blocker = (
        agentic == "keep"
        and langgraph in {"discard", "informative"}
    )

    summary = {
        "agentic_recommendation": agentic_raw,
        "agentic_normalized": agentic,
        "langgraph_decision": langgraph_raw,
        "langgraph_normalized": langgraph,
        "agreement": agree,
        "blocker_keep_vs_non_keep": blocker,
        "agentic_result_path": str(agentic_path.resolve().relative_to(REPO_ROOT))
            if str(agentic_path.resolve()).startswith(str(REPO_ROOT)) else str(agentic_path),
        "langgraph_decision_path": str(langgraph_path.resolve().relative_to(REPO_ROOT))
            if str(langgraph_path.resolve()).startswith(str(REPO_ROOT)) else str(langgraph_path),
        "rationale": (
            "Agreement passes the parity gate; the DeepAgents prototype "
            "is allowed to graduate only after several agreements on a "
            "fixture set with no keep_vs_non_keep blockers."
            if agree
            else "Disagreement - the DeepAgents recommendation must be "
                 "treated as informative until parity is restored."
        ),
    }

    out_dir = out_dir or (COMPARISONS_ROOT / _utc_stamp())
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "comparison.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    summary["out_dir"] = str(out_dir.relative_to(REPO_ROOT))
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare DeepAgents supervisor recommendation to LangGraph autosearch decision.",
    )
    parser.add_argument("--agentic-result", required=True, help="Path to a result.json from offline_runner.")
    parser.add_argument("--langgraph-decision", required=True, help="Path to a session_*.json or decision JSON from scripts/run_bounded_autosearch.py.")
    parser.add_argument("--out-dir", default=None, help="Optional explicit output dir under Simulations/robocop_agentic/comparisons/.")
    return parser


def main(argv: Optional[list] = None) -> int:
    args = _build_parser().parse_args(argv)
    agentic_path = Path(args.agentic_result).resolve()
    langgraph_path = Path(args.langgraph_decision).resolve()
    if not agentic_path.exists():
        print(f"[robocop-agentic] missing agentic-result: {agentic_path}", file=sys.stderr)
        return 2
    if not langgraph_path.exists():
        print(f"[robocop-agentic] missing langgraph-decision: {langgraph_path}", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir) if args.out_dir else None
    summary = compare(agentic_path, langgraph_path, out_dir=out_dir)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["agreement"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
