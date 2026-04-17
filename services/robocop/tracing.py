from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator

try:
    import langsmith as ls
    from langsmith import tracing_context
except ImportError:
    ls = None
    tracing_context = None

_TRUE_VALUES = {"1", "true", "yes", "on"}


class _NoOpTrace:
    def __init__(self, metadata: dict[str, Any] | None = None, tags: list[str] | None = None):
        self.metadata = dict(metadata or {})
        self.tags = list(tags or [])

    def end(self, outputs: dict[str, Any] | None = None):
        return None


def _is_truthy(value: str | None) -> bool:
    return bool(value and value.strip().lower() in _TRUE_VALUES)


def get_langsmith_trace_status() -> dict[str, Any]:
    if ls is None or tracing_context is None:
        return {
            "enabled": False,
            "project": None,
            "endpoint": None,
            "reason": "langsmith_not_installed",
        }
    tracing_enabled = _is_truthy(os.getenv("LANGSMITH_TRACING")) or _is_truthy(
        os.getenv("LANGCHAIN_TRACING_V2")
    )
    if not tracing_enabled:
        return {
            "enabled": False,
            "project": os.getenv("LANGSMITH_PROJECT") or os.getenv("LANGCHAIN_PROJECT"),
            "endpoint": os.getenv("LANGSMITH_ENDPOINT") or os.getenv("LANGCHAIN_ENDPOINT"),
            "reason": "env_disabled",
        }
    if not os.getenv("LANGSMITH_API_KEY"):
        return {
            "enabled": False,
            "project": os.getenv("LANGSMITH_PROJECT") or os.getenv("LANGCHAIN_PROJECT"),
            "endpoint": os.getenv("LANGSMITH_ENDPOINT") or os.getenv("LANGCHAIN_ENDPOINT"),
            "reason": "missing_api_key",
        }
    return {
        "enabled": True,
        "project": os.getenv("LANGSMITH_PROJECT") or os.getenv("LANGCHAIN_PROJECT") or "robocop",
        "endpoint": os.getenv("LANGSMITH_ENDPOINT") or os.getenv("LANGCHAIN_ENDPOINT"),
        "reason": "configured",
    }


@contextmanager
def trace_block(
    *,
    name: str,
    run_type: str,
    inputs: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Iterator[Any]:
    status = get_langsmith_trace_status()
    if not status["enabled"] or ls is None or tracing_context is None:
        yield _NoOpTrace(metadata=metadata, tags=tags)
        return
    with tracing_context(enabled=True):
        with ls.trace(
            name=name,
            run_type=run_type,
            project_name=status["project"],
            inputs=inputs or {},
            tags=list(tags or []),
            metadata=dict(metadata or {}),
        ) as run_tree:
            yield run_tree
