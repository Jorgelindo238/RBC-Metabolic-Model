"""DeepAgents-based RoBoCop supervisor (offline prototype).

This module is intentionally conservative:

- It is OFF by default. Importing it has no side effects.
- Calling :func:`build_robocop_deep_agent` requires the optional
  ``deepagents`` and ``langchain-openai`` packages, both pinned in
  the root ``requirements.txt`` (under the agentic section).
  Production deployment manifests (``api/requirements.txt``,
  ``apps/calibration-worker/requirements.txt``, etc.) intentionally
  do NOT pull from the root file, so the agentic stack remains
  isolated from production runtime images.
- The returned agent is a compiled LangGraph graph (per the deepagents
  README). Caller code is responsible for invoking it with a bounded
  message payload.
- It must NOT be imported by web, API, worker, or production
  calibration paths. See ``services/robocop/agentic/README.md`` and
  ``AgentOps/CalibrationOps.md``.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from .budgets import CampaignBudget
from .prompts import (
    AUTONOMOUS_CAMPAIGN_PROMPT_SUFFIX,
    SUPERVISOR_SYSTEM_PROMPT,
)
from .subagents import build_subagents
from .tools import build_tool_registry, set_mutation_context


DEFAULT_MODEL_ID = "openai:gpt-5.5"
DEFAULT_AGENT_NAME = "robocop-supervisor"


class DeepAgentsNotInstalledError(RuntimeError):
    """Raised when ``deepagents`` is not importable.

    Install the agentic dependency set from the repo root:

    ``pip install -r requirements.txt``
    """


def _resolve_model_identifier(override: Optional[str] = None) -> str:
    """Pick the model id to pass to :func:`deepagents.create_deep_agent`."""

    if override:
        return override
    env_value = os.environ.get("ROBOCOP_DEEPAGENT_MODEL", "").strip()
    if env_value:
        return env_value
    return DEFAULT_MODEL_ID


def build_robocop_deep_agent(
    *,
    model: Optional[str] = None,
    name: str = DEFAULT_AGENT_NAME,
    extra_tools: Optional[list] = None,
    extra_subagents: Optional[list] = None,
    system_prompt_suffix: Optional[str] = None,
    allow_mutations: bool = False,
    budget: Optional[CampaignBudget] = None,
) -> Any:
    """Build the RoBoCop supervisor agent (compiled LangGraph graph).

    Parameters
    ----------
    model:
        Optional override of the model identifier. Defaults to the
        ``ROBOCOP_DEEPAGENT_MODEL`` env var, otherwise
        :data:`DEFAULT_MODEL_ID` (``openai:gpt-5.5``).
    name:
        Optional graph name; surfaces in LangSmith metadata as
        ``lc_agent_name``.
    extra_tools:
        Optional additional LangChain tools appended to the registry.
        Use sparingly - keep the bounded contract.
    extra_subagents:
        Optional additional ``SubAgent`` dicts.
    system_prompt_suffix:
        Optional extra context appended to the supervisor prompt
        (e.g. "current campaign goal: ..."). Hard rules in
        :data:`SUPERVISOR_SYSTEM_PROMPT` always come first.

    Returns
    -------
    A compiled LangGraph graph supporting ``.invoke`` and ``.stream``.
    """

    try:
        from deepagents import create_deep_agent  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - depends on optional install
        raise DeepAgentsNotInstalledError(
            "deepagents is not installed. Run "
            "`pip install -r requirements.txt` from the repo root."
        ) from exc

    # Configure mutation context BEFORE constructing the tool registry
    # so the subprocess tool sees the correct allow_mutations + budget.
    set_mutation_context(allow_mutations=allow_mutations, budget=budget)

    tools = build_tool_registry()
    if extra_tools:
        tools = tools + list(extra_tools)

    subagents = build_subagents(tools)
    if extra_subagents:
        subagents = subagents + list(extra_subagents)

    prompt = SUPERVISOR_SYSTEM_PROMPT
    if allow_mutations:
        prompt = f"{prompt}\n\n{AUTONOMOUS_CAMPAIGN_PROMPT_SUFFIX.strip()}\n"
    if system_prompt_suffix:
        prompt = f"{prompt}\n\n# Campaign-specific context\n\n{system_prompt_suffix.strip()}\n"

    model_id = _resolve_model_identifier(model)

    agent = create_deep_agent(
        model=model_id,
        tools=tools,
        system_prompt=prompt,
        subagents=subagents,
        name=name,
    )
    return agent
