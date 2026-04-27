"""Token + USD accounting for autonomous DeepAgents campaigns.

The autonomous runner needs to know:

- how many tokens each supervisor turn used,
- the USD-equivalent cost per turn,
- a running campaign total, so the :class:`CampaignBudget` from
  :mod:`services.robocop.agentic.budgets` can stop the loop when the
  ``max_usd`` cap is hit.

The accounting is *best-effort*. If LangChain's callback system or
the model's usage metadata is not available for a given provider /
model, the run still completes and the cost is reported as 0.0 - the
budget cap is then advisory only.

Pricing
-------

Pricing is provider-specific and changes often. We keep a small
hard-coded table below for the OpenAI models we use today; unknown
models fall back to ``UNKNOWN_PRICE`` (which is conservatively non-zero
so unknown traffic still tickles the USD cap eventually).

Update ``MODEL_PRICING`` when OpenAI re-prices, when a new model id is
adopted, or when adding another provider.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# USD per 1M tokens. Keys match ``openai:<id>`` and bare ``<id>`` forms.
# Values are conservative defaults; replace with provider-published
# numbers when you ship to production.
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    # gpt-5.5 (current default)
    "openai:gpt-5.5": {"input": 5.0, "output": 15.0},
    "gpt-5.5": {"input": 5.0, "output": 15.0},
    # gpt-5.4
    "openai:gpt-5.4": {"input": 5.0, "output": 15.0},
    "gpt-5.4": {"input": 5.0, "output": 15.0},
    # gpt-4o-mini fallback
    "openai:gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}

UNKNOWN_INPUT_PRICE = 5.0   # USD per 1M tokens
UNKNOWN_OUTPUT_PRICE = 15.0


@dataclass
class TurnUsage:
    """Per-turn token + cost breakdown."""

    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    usd: float = 0.0
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "usd": round(self.usd, 6),
        }


def _normalize_model_id(model: str) -> str:
    if not isinstance(model, str):
        return ""
    return model.strip()


def estimate_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Best-effort USD estimate for a single turn."""

    norm = _normalize_model_id(model)
    pricing = MODEL_PRICING.get(norm)
    if pricing is None and ":" in norm:
        # try the bare suffix: "openai:gpt-5.5" -> "gpt-5.5"
        pricing = MODEL_PRICING.get(norm.split(":", 1)[1])
    if pricing is None:
        in_price = UNKNOWN_INPUT_PRICE
        out_price = UNKNOWN_OUTPUT_PRICE
    else:
        in_price = pricing["input"]
        out_price = pricing["output"]
    return (prompt_tokens * in_price + completion_tokens * out_price) / 1_000_000


def extract_usage_from_result(
    result: Any,
    *,
    fallback_model: str = "",
) -> Optional[TurnUsage]:
    """Best-effort token usage extraction from a deepagents/LangGraph result.

    Looks for ``usage_metadata`` on each AIMessage in ``result["messages"]``
    (the shape LangChain has used since 0.3.x). Returns a single
    :class:`TurnUsage` aggregating all AIMessage usage from the turn,
    or ``None`` if no usage data can be found.
    """

    if not isinstance(result, dict):
        return None
    messages = result.get("messages") or []
    prompt = 0
    completion = 0
    total = 0
    model_id = fallback_model
    raw_blocks: List[Dict[str, Any]] = []
    for msg in messages:
        usage = getattr(msg, "usage_metadata", None)
        if usage is None and isinstance(msg, dict):
            usage = msg.get("usage_metadata")
        if not isinstance(usage, dict):
            continue
        raw_blocks.append(dict(usage))
        prompt += int(usage.get("input_tokens", 0) or 0)
        completion += int(usage.get("output_tokens", 0) or 0)
        total += int(usage.get("total_tokens", 0) or (prompt + completion))
        meta = getattr(msg, "response_metadata", None)
        if isinstance(meta, dict):
            mn = meta.get("model_name") or meta.get("model")
            if isinstance(mn, str) and mn:
                model_id = mn
    if total == 0 and prompt == 0 and completion == 0:
        return None
    if total == 0:
        total = prompt + completion
    usd = estimate_usd(model_id, prompt, completion)
    return TurnUsage(
        model=model_id or fallback_model,
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
        usd=usd,
        raw={"per_message": raw_blocks},
    )
