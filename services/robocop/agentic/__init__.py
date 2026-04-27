"""RoBoCop agentic supervisor package.

This package hosts the offline-only DeepAgents-based RoBoCop campaign
supervisor prototype. It must not be imported by web, API, or worker
production paths. See ``services/robocop/agentic/README.md`` and
``AgentOps/CalibrationOps.md`` for the operating contract.

Intentionally light at import time: the heavy ``deepagents`` /
``langchain`` imports live inside ``robocop_deep_agent`` so that simply
importing this package (e.g. for tests) does not require the optional
agentic dependency set in the root ``requirements.txt``.
"""

from __future__ import annotations

__all__ = [
    "build_robocop_deep_agent",
    "run_offline_campaign",
]


def build_robocop_deep_agent(*args, **kwargs):
    """Lazy re-export of :func:`robocop_deep_agent.build_robocop_deep_agent`."""

    from .robocop_deep_agent import build_robocop_deep_agent as _impl

    return _impl(*args, **kwargs)


def run_offline_campaign(*args, **kwargs):
    """Lazy re-export of :func:`offline_runner.run_offline_campaign`."""

    from .offline_runner import run_offline_campaign as _impl

    return _impl(*args, **kwargs)
