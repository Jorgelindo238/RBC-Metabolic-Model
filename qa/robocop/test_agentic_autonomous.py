"""Path 3 autonomous-mode safety tests.

These tests must NOT require the optional ``deepagents`` install. They
verify the safety surface around the autonomous runner:

- mutation-context defaults are off and tool refuses execution;
- subprocess tool refuses paths outside the read-only allow-list;
- subprocess tool refuses missing required fields;
- kill switch preempts execution even when allow_mutations=True;
- budget exhaustion preempts execution;
- campaign-decisions ledger schema validation;
- anchor-regression detector flags >threshold drops.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.robocop.agentic import tools as agentic_tools  # noqa: E402
from services.robocop.agentic.budgets import (  # noqa: E402
    BudgetExceeded,
    CampaignBudget,
    DEFAULT_KILL_SWITCH,
    evaluate_anchor_regression,
)
from services.robocop.agentic.cost import (  # noqa: E402
    estimate_usd,
)
from services.robocop.agentic.tools import (  # noqa: E402
    SUBAGENT_TOOL_ACL,
    _impl_append_campaign_decision,
    _impl_run_bounded_autosearch_subprocess,
    set_mutation_context,
)


@pytest.fixture(autouse=True)
def _reset_mutation_context():
    """Every test starts with mutations OFF and budget cleared."""

    set_mutation_context(allow_mutations=False, budget=None)
    yield
    set_mutation_context(allow_mutations=False, budget=None)


# ---------------------------------------------------------------------------
# Mutation gating
# ---------------------------------------------------------------------------


def test_subprocess_tool_refuses_when_mutations_disabled() -> None:
    out = _impl_run_bounded_autosearch_subprocess(
        {
            "base_policy": "config/some_policy.json",
            "base_manifest": "config/some_manifest.json",
            "max_iterations": 1,
            "loop_budget_seconds": 60,
        }
    )
    assert out["ok"] is False
    assert "allow_mutations is False" in out["error"]


def test_subprocess_tool_refuses_when_budget_exhausted() -> None:
    budget = CampaignBudget(
        max_iterations=1,
        max_wall_seconds=60,
        max_usd=1.0,
        max_tool_calls=1,
        kill_switch_path=ROOT / "definitely-not-a-kill-switch",
    )
    budget.iterations = budget.max_iterations  # exhaust
    set_mutation_context(allow_mutations=True, budget=budget)
    out = _impl_run_bounded_autosearch_subprocess(
        {
            "base_policy": "config/x.json",
            "base_manifest": "config/y.json",
            "max_iterations": 1,
            "loop_budget_seconds": 60,
        }
    )
    assert out["ok"] is False
    assert "budget refused" in out["error"]


def test_subprocess_tool_refuses_missing_required_fields() -> None:
    set_mutation_context(allow_mutations=True, budget=CampaignBudget())
    out = _impl_run_bounded_autosearch_subprocess({"max_iterations": 1})
    assert out["ok"] is False
    assert "base_policy" in out["error"]


def test_subprocess_tool_refuses_paths_outside_allowlist(tmp_path) -> None:
    set_mutation_context(allow_mutations=True, budget=CampaignBudget())
    # src/ is intentionally NOT in READABLE_ROOTS for the agentic tools.
    out = _impl_run_bounded_autosearch_subprocess(
        {
            "base_policy": "src/MM_calibration.py",
            "base_manifest": "src/equadiff_brodbar.py",
            "max_iterations": 1,
            "loop_budget_seconds": 60,
        }
    )
    assert out["ok"] is False
    assert "not inside the allow-list" in out["error"]


# ---------------------------------------------------------------------------
# Kill switch
# ---------------------------------------------------------------------------


def test_kill_switch_preempts_execution(tmp_path) -> None:
    kill = tmp_path / "STOP"
    kill.write_text("halt", encoding="utf-8")
    budget = CampaignBudget(kill_switch_path=kill)
    breach = budget.check()
    assert isinstance(breach, BudgetExceeded)
    assert "kill switch present" in str(breach)


def test_kill_switch_default_path_resolves_under_sandbox() -> None:
    assert DEFAULT_KILL_SWITCH.parent.name == "robocop_agentic"
    assert DEFAULT_KILL_SWITCH.name == "STOP"


# ---------------------------------------------------------------------------
# Budget caps
# ---------------------------------------------------------------------------


def test_budget_max_iterations_breach() -> None:
    budget = CampaignBudget(max_iterations=2)
    assert budget.check() is None
    budget.tick_iteration()
    budget.tick_iteration()
    breach = budget.check()
    assert isinstance(breach, BudgetExceeded)
    assert "max_iterations" in str(breach)


def test_budget_usd_cap_breach() -> None:
    budget = CampaignBudget(max_usd=0.10)
    budget.add_cost_usd(0.05)
    assert budget.check() is None
    budget.add_cost_usd(0.10)
    breach = budget.check()
    assert isinstance(breach, BudgetExceeded)
    assert "max_usd" in str(breach)


def test_budget_tool_calls_breach() -> None:
    budget = CampaignBudget(max_tool_calls=1)
    budget.tick_tool_call()
    breach = budget.check()
    assert isinstance(breach, BudgetExceeded)


# ---------------------------------------------------------------------------
# Campaign-decisions ledger
# ---------------------------------------------------------------------------


def test_campaign_decision_rejects_missing_fields(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        agentic_tools, "AGENTIC_SANDBOX_ROOT", tmp_path / "sandbox"
    )
    monkeypatch.setattr(
        agentic_tools,
        "CAMPAIGN_DECISIONS_LEDGER",
        tmp_path / "sandbox" / "campaign_decisions.jsonl",
    )
    out = _impl_append_campaign_decision({"decision": "keep"})
    assert out["ok"] is False
    assert "campaign_id" in out["error"]


def test_campaign_decision_rejects_bad_decision(tmp_path, monkeypatch) -> None:
    sandbox = tmp_path / "sandbox"
    monkeypatch.setattr(agentic_tools, "AGENTIC_SANDBOX_ROOT", sandbox)
    monkeypatch.setattr(
        agentic_tools,
        "CAMPAIGN_DECISIONS_LEDGER",
        sandbox / "campaign_decisions.jsonl",
    )
    out = _impl_append_campaign_decision(
        {
            "campaign_id": "c1",
            "iteration": 1,
            "decision": "promote",  # invalid
            "rationale": "x",
            "supporting_artifacts": [],
        }
    )
    assert out["ok"] is False
    assert "keep|informative|discard" in out["error"]


def test_campaign_decision_writes_to_sandbox(tmp_path, monkeypatch) -> None:
    sandbox = tmp_path / "sandbox"
    ledger = sandbox / "campaign_decisions.jsonl"
    monkeypatch.setattr(agentic_tools, "AGENTIC_SANDBOX_ROOT", sandbox)
    monkeypatch.setattr(agentic_tools, "CAMPAIGN_DECISIONS_LEDGER", ledger)
    out = _impl_append_campaign_decision(
        {
            "campaign_id": "c-test",
            "iteration": 2,
            "decision": "informative",
            "rationale": "test",
            "supporting_artifacts": ["Simulations/foo.json"],
        }
    )
    assert out["ok"] is True
    assert ledger.exists()
    assert ledger.read_text(encoding="utf-8").strip().count("\n") == 0  # exactly 1 line


# ---------------------------------------------------------------------------
# Anchor regression detector
# ---------------------------------------------------------------------------


def test_anchor_regression_flags_large_drop() -> None:
    seed = {"ATP": 2.5, "EGLC": 5.0}
    cand = {"ATP": 1.0, "EGLC": 5.0}  # ATP drops 60%
    breach = evaluate_anchor_regression(seed, cand, drop_pct=0.25)
    assert isinstance(breach, BudgetExceeded)
    assert "ATP" in str(breach)


def test_anchor_regression_passes_small_drop() -> None:
    seed = {"ATP": 2.5, "EGLC": 5.0}
    cand = {"ATP": 2.4, "EGLC": 4.95}
    breach = evaluate_anchor_regression(seed, cand, drop_pct=0.25)
    assert breach is None


def test_anchor_regression_skips_missing_keys() -> None:
    breach = evaluate_anchor_regression({"ATP": 2.5}, {"ADP": 0.3})
    assert breach is None


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


def test_estimate_usd_known_model() -> None:
    usd = estimate_usd("openai:gpt-5.5", 1_000_000, 0)
    assert usd == pytest.approx(5.0)


def test_estimate_usd_unknown_model_uses_fallback() -> None:
    usd = estimate_usd("openai:fake-future", 1_000_000, 0)
    assert usd > 0


# ---------------------------------------------------------------------------
# Subagent ACL still safe
# ---------------------------------------------------------------------------


def test_subagent_acl_does_not_grant_subprocess_to_subagents() -> None:
    forbidden = {"run_bounded_autosearch_subprocess"}
    for role, allowed in SUBAGENT_TOOL_ACL.items():
        assert allowed.isdisjoint(forbidden), (
            f"subagent {role!r} must NOT have run_bounded_autosearch_subprocess; "
            "only the supervisor itself may call it."
        )
