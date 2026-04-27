"""Subagent definitions for the RoBoCop DeepAgents supervisor.

Each subagent is a plain dict matching the deepagents ``SubAgent`` spec
(see https://docs.langchain.com/oss/python/deepagents/subagents). The
``tools`` field is an explicit allow-list - subagents do NOT inherit
the supervisor's tool list by default when ``tools`` is provided.

ACL is sourced from :data:`services.robocop.agentic.tools.SUBAGENT_TOOL_ACL`.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .prompts import (
    ARCHIVIST_PROMPT,
    PLANNER_PROMPT,
    TRIAGE_ANALYST_PROMPT,
)
from .tools import SUBAGENT_TOOL_ACL


def _filter_tools(tools: List[Any], allowed_names: set) -> List[Any]:
    """Return only the LangChain tools whose ``name`` attribute is allowed."""

    out: List[Any] = []
    for tool_obj in tools:
        name = getattr(tool_obj, "name", None)
        if name in allowed_names:
            out.append(tool_obj)
    return out


def build_subagents(supervisor_tools: List[Any]) -> List[Dict[str, Any]]:
    """Build the supervisor's subagent list from the registered tools.

    Each subagent receives only the tools it is allowed to call by
    :data:`SUBAGENT_TOOL_ACL`. The supervisor itself retains the full
    tool list and dispatches to subagents via the built-in ``task`` tool.
    """

    planner_tools = _filter_tools(supervisor_tools, SUBAGENT_TOOL_ACL["planner"])
    triage_tools = _filter_tools(supervisor_tools, SUBAGENT_TOOL_ACL["triage_analyst"])
    archivist_tools = _filter_tools(supervisor_tools, SUBAGENT_TOOL_ACL["archivist"])

    return [
        {
            "name": "planner",
            "description": (
                "Use to draft a short ordered plan of bounded tool calls for "
                "the next campaign step. Read-only; cannot execute calibration "
                "or write any artifact."
            ),
            "system_prompt": PLANNER_PROMPT,
            "tools": planner_tools,
        },
        {
            "name": "triage_analyst",
            "description": (
                "Use to evaluate a candidate's eval-summary JSON and "
                "trajectory CSV against protected anchors via curve_triage, "
                "pure_ode_replay, and combined_triage. Returns a verdict."
            ),
            "system_prompt": TRIAGE_ANALYST_PROMPT,
            "tools": triage_tools,
        },
        {
            "name": "archivist",
            "description": (
                "Use to write the final recommendation record to the "
                "agentic-only ledger via append_recommendation. Cannot "
                "trigger triage or execution."
            ),
            "system_prompt": ARCHIVIST_PROMPT,
            "tools": archivist_tools,
        },
    ]
