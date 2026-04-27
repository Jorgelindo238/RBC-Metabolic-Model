"""Lightweight smoke tests for the offline DeepAgents supervisor package.

These tests must NOT require the optional ``deepagents`` install. They
only verify that:

- the package imports without side effects;
- the tool registry builds and exposes the expected tool names;
- the subagent ACL is consistent with the registered tool list;
- ``append_recommendation`` enforces its required-field schema and
  refuses bad input;
- read-only tools refuse paths outside the allow-list.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.robocop.agentic import tools as agentic_tools  # noqa: E402
from services.robocop.agentic.tools import (  # noqa: E402
    REPO_ROOT,
    SUBAGENT_TOOL_ACL,
    ToolPermissionError,
    _impl_append_recommendation,
    _impl_read_session_memory,
    build_tool_registry,
)


EXPECTED_TOOL_NAMES = {
    "read_session_memory",
    "run_curve_triage",
    "run_pure_ode_replay",
    "run_combined_triage",
    "run_strategy_race",
    "run_teacher_flux_rescue",
    "summarize_campaign",
    "append_recommendation",
    # Path 3 autonomous-mode additions:
    "run_bounded_autosearch_subprocess",
    "append_campaign_decision",
}


def test_tool_registry_exposes_expected_tools() -> None:
    registry = build_tool_registry()
    names = {getattr(t, "name", None) for t in registry}
    assert names == EXPECTED_TOOL_NAMES


def test_subagent_acl_references_only_real_tools() -> None:
    flat_acl = set().union(*SUBAGENT_TOOL_ACL.values())
    assert flat_acl.issubset(EXPECTED_TOOL_NAMES)


def test_subagent_acl_excludes_mutating_tools_from_triage_and_planner() -> None:
    forbidden_for_planner = {
        "run_curve_triage",
        "run_pure_ode_replay",
        "run_combined_triage",
        "run_strategy_race",
        "run_teacher_flux_rescue",
        "append_recommendation",
    }
    forbidden_for_triage = {
        "run_strategy_race",
        "run_teacher_flux_rescue",
        "append_recommendation",
    }
    forbidden_for_archivist = {
        "run_curve_triage",
        "run_pure_ode_replay",
        "run_combined_triage",
        "run_strategy_race",
        "run_teacher_flux_rescue",
    }
    assert SUBAGENT_TOOL_ACL["planner"].isdisjoint(forbidden_for_planner)
    assert SUBAGENT_TOOL_ACL["triage_analyst"].isdisjoint(forbidden_for_triage)
    assert SUBAGENT_TOOL_ACL["archivist"].isdisjoint(forbidden_for_archivist)


def test_read_session_memory_rejects_paths_outside_allowlist() -> None:
    with pytest.raises(ToolPermissionError):
        _impl_read_session_memory("src/MM_calibration.py")
    with pytest.raises(ToolPermissionError):
        _impl_read_session_memory("../etc/passwd")


def test_append_recommendation_rejects_missing_fields(tmp_path, monkeypatch) -> None:
    sandbox = tmp_path / "robocop_agentic"
    monkeypatch.setattr(agentic_tools, "AGENTIC_SANDBOX_ROOT", sandbox)
    monkeypatch.setattr(
        agentic_tools,
        "RECOMMENDATIONS_LEDGER",
        sandbox / "recommendations.jsonl",
    )

    bad = _impl_append_recommendation({"recommendation": "keep"})
    assert bad["ok"] is False
    assert "session_id" in bad["error"]


def test_append_recommendation_rejects_bad_decision(tmp_path, monkeypatch) -> None:
    sandbox = tmp_path / "robocop_agentic"
    monkeypatch.setattr(agentic_tools, "AGENTIC_SANDBOX_ROOT", sandbox)
    monkeypatch.setattr(
        agentic_tools,
        "RECOMMENDATIONS_LEDGER",
        sandbox / "recommendations.jsonl",
    )

    bad = _impl_append_recommendation(
        {
            "session_id": "test",
            "recommendation": "promote",  # not in allowed set
            "rationale": "x",
            "supporting_artifacts": [],
        }
    )
    assert bad["ok"] is False
    assert "keep|informative|discard" in bad["error"]


def test_append_recommendation_writes_to_sandbox_only(tmp_path, monkeypatch) -> None:
    sandbox = tmp_path / "robocop_agentic"
    ledger = sandbox / "recommendations.jsonl"
    monkeypatch.setattr(agentic_tools, "AGENTIC_SANDBOX_ROOT", sandbox)
    monkeypatch.setattr(agentic_tools, "RECOMMENDATIONS_LEDGER", ledger)

    record = {
        "session_id": "smoke-1",
        "recommendation": "informative",
        "rationale": "smoke test",
        "supporting_artifacts": ["Simulations/foo.json"],
    }
    out = _impl_append_recommendation(record)
    assert out["ok"] is True
    # Comparison flag must be auto-injected by the tool.
    assert out["record"]["comparison_to_langgraph_required"] is True
    # Ledger written and contains exactly one line of valid JSON.
    lines = ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["session_id"] == "smoke-1"
    assert parsed["recommendation"] == "informative"


def test_repo_root_resolves_to_repository() -> None:
    # Sanity check that the safety helpers anchor to the repo root.
    assert (REPO_ROOT / "AgentOps").is_dir()
    assert (REPO_ROOT / "services" / "robocop" / "agentic").is_dir()


def test_default_sandbox_path_is_repo_relative() -> None:
    expected = REPO_ROOT / "Simulations" / "robocop_agentic"
    assert agentic_tools.AGENTIC_SANDBOX_ROOT == expected
