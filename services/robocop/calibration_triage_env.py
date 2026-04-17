"""Minimal RL environment for calibration triage policy experiments.

This is intentionally lightweight: it turns historical calibration verdict
records into a small step-based environment that can later back an Atropos or
other RL training loop without changing the record format again.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List


ACTIONS = ("discard", "keep_with_caveats", "keep", "promote")


def _normalize_verdict(record: Dict[str, Any]) -> str:
    combined = record.get("combined_triage") or {}
    triage = record.get("triage") or {}
    pure_ode = record.get("pure_ode_triage") or {}
    verdict = str(
        combined.get("overall")
        or triage.get("overall")
        or pure_ode.get("overall")
        or "needs_review"
    ).strip().lower()
    if verdict == "healthy":
        return "keep"
    if verdict == "compromised":
        return "keep_with_caveats"
    if verdict == "collapsed":
        return "discard"
    return verdict


def preferred_action(record: Dict[str, Any]) -> str:
    verdict = _normalize_verdict(record)
    improvement = float(record.get("improvement_pct") or 0.0)
    if verdict == "keep" and improvement >= 5.0:
        return "promote"
    if verdict in ACTIONS:
        return verdict
    return "keep_with_caveats"


@dataclass
class StepResult:
    observation: Dict[str, Any]
    reward: float
    terminated: bool
    info: Dict[str, Any]


class CalibrationTriageEnv:
    """Tiny sequential environment over calibration verdict records."""

    def __init__(self, records: Iterable[Dict[str, Any]]):
        self._records: List[Dict[str, Any]] = list(records)
        self._cursor = 0
        self._episode_reward = 0.0

    @property
    def size(self) -> int:
        return len(self._records)

    def reset(self) -> Dict[str, Any]:
        self._cursor = 0
        self._episode_reward = 0.0
        return self._observation_for_current()

    def step(self, action: str) -> StepResult:
        if action not in ACTIONS:
            raise ValueError(f"Unsupported action: {action}")
        if self._cursor >= len(self._records):
            return StepResult(
                observation={"done": True},
                reward=0.0,
                terminated=True,
                info={"message": "environment exhausted"},
            )

        record = self._records[self._cursor]
        target = preferred_action(record)
        reward = self._reward_for_action(action, target)
        self._episode_reward += reward
        self._cursor += 1
        terminated = self._cursor >= len(self._records)

        return StepResult(
            observation=self._observation_for_current(),
            reward=reward,
            terminated=terminated,
            info={
                "target_action": target,
                "verdict": _normalize_verdict(record),
                "episode_reward": self._episode_reward,
            },
        )

    def _observation_for_current(self) -> Dict[str, Any]:
        if self._cursor >= len(self._records):
            return {"done": True}

        record = self._records[self._cursor]
        combined = record.get("combined_triage") or {}
        triage = record.get("triage") or {}
        pure_ode = record.get("pure_ode_triage") or {}
        return {
            "index": self._cursor,
            "combined_overall": combined.get("overall"),
            "curve_overall": triage.get("overall"),
            "pure_ode_overall": pure_ode.get("overall"),
            "improvement_pct": float(record.get("improvement_pct") or 0.0),
            "final_loss": record.get("final_loss"),
            "discard_trigger_count": len((combined.get("discard_triggers") or triage.get("discard_triggers") or [])),
            "collapse_signal_count": len(pure_ode.get("collapse_signals") or []),
            "concern_signal_count": len(pure_ode.get("concern_signals") or []),
        }

    @staticmethod
    def _reward_for_action(action: str, target: str) -> float:
        if action == target:
            return 1.0
        if {action, target} <= {"keep", "promote"}:
            return 0.4
        if {action, target} <= {"discard", "keep_with_caveats"}:
            return 0.2
        return -1.0

