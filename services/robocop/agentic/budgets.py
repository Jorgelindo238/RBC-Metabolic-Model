"""Hard budget + kill-switch primitives for the agentic campaign runner.

These are the safety rails that gate the autonomous Path 3 supervisor.
Every mutating tool call (real ``run_strategy_race``, real
``run_pure_ode_replay``) MUST consult a :class:`CampaignBudget` before
executing and MUST respect the kill-switch file.

Kill switch
-----------

If the file ``Simulations/robocop_agentic/STOP`` exists at the start of
any iteration or tool call, the campaign aborts immediately. Operators
can stop a runaway autonomous campaign by simply ``touch``ing that
file - no process kill required.

Budget exhaustion
-----------------

Independent caps:

- ``max_iterations``     - hard ceiling on supervisor turns
- ``max_wall_seconds``   - wall-clock cap from campaign start
- ``max_usd``            - cumulative model-cost cap
- ``max_tool_calls``     - safety against tool-call loops
- ``anchor_drop_pct``    - if any protected anchor regresses by more
                           than this fraction relative to the starting
                           seed, the campaign aborts

Any cap reached returns a :class:`BudgetExceeded` from
:meth:`CampaignBudget.check` so the runner can stop cleanly with a
written reason.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_KILL_SWITCH = REPO_ROOT / "Simulations" / "robocop_agentic" / "STOP"


# ---------------------------------------------------------------------------
# Default ceilings (intentionally conservative)
# ---------------------------------------------------------------------------

DEFAULT_MAX_ITERATIONS = 5
DEFAULT_MAX_WALL_SECONDS = 30 * 60  # 30 minutes
DEFAULT_MAX_USD = 5.0
DEFAULT_MAX_TOOL_CALLS = 60
DEFAULT_ANCHOR_DROP_PCT = 0.25  # 25% regression on any protected anchor


class BudgetExceeded(RuntimeError):
    """Raised / returned when an autonomous campaign hits a hard cap."""


@dataclass
class CampaignBudget:
    """Mutable budget carried by the autonomous runner.

    The runner ticks ``iterations``, ``tool_calls``, and ``usd_spent``
    as the campaign progresses. ``check()`` returns ``None`` when the
    campaign may continue, or a :class:`BudgetExceeded` describing the
    breach (without raising) so the caller can decide whether to log,
    archive, or hard-stop.
    """

    max_iterations: int = DEFAULT_MAX_ITERATIONS
    max_wall_seconds: float = DEFAULT_MAX_WALL_SECONDS
    max_usd: float = DEFAULT_MAX_USD
    max_tool_calls: int = DEFAULT_MAX_TOOL_CALLS
    anchor_drop_pct: float = DEFAULT_ANCHOR_DROP_PCT
    kill_switch_path: Path = field(default_factory=lambda: DEFAULT_KILL_SWITCH)

    started_at: float = field(default_factory=time.time)
    iterations: int = 0
    tool_calls: int = 0
    usd_spent: float = 0.0

    def remaining_seconds(self) -> float:
        return max(0.0, self.max_wall_seconds - (time.time() - self.started_at))

    def remaining_usd(self) -> float:
        return max(0.0, self.max_usd - self.usd_spent)

    def remaining_iterations(self) -> int:
        return max(0, self.max_iterations - self.iterations)

    def kill_switch_active(self) -> bool:
        return self.kill_switch_path.exists()

    def check(self) -> Optional[BudgetExceeded]:
        if self.kill_switch_active():
            return BudgetExceeded(
                f"kill switch present: {self.kill_switch_path}"
            )
        if self.iterations >= self.max_iterations:
            return BudgetExceeded(
                f"max_iterations reached ({self.max_iterations})"
            )
        if (time.time() - self.started_at) >= self.max_wall_seconds:
            return BudgetExceeded(
                f"max_wall_seconds reached ({self.max_wall_seconds:.0f}s)"
            )
        if self.usd_spent >= self.max_usd:
            return BudgetExceeded(
                f"max_usd reached (spent ${self.usd_spent:.4f} of ${self.max_usd:.2f})"
            )
        if self.tool_calls >= self.max_tool_calls:
            return BudgetExceeded(
                f"max_tool_calls reached ({self.max_tool_calls})"
            )
        return None

    def tick_iteration(self) -> None:
        self.iterations += 1

    def tick_tool_call(self) -> None:
        self.tool_calls += 1

    def add_cost_usd(self, amount: float) -> None:
        if amount > 0:
            self.usd_spent += amount

    def to_dict(self) -> dict:
        return {
            "max_iterations": self.max_iterations,
            "max_wall_seconds": self.max_wall_seconds,
            "max_usd": self.max_usd,
            "max_tool_calls": self.max_tool_calls,
            "anchor_drop_pct": self.anchor_drop_pct,
            "kill_switch_path": str(self.kill_switch_path),
            "started_at": self.started_at,
            "iterations": self.iterations,
            "tool_calls": self.tool_calls,
            "usd_spent": round(self.usd_spent, 6),
            "elapsed_seconds": round(time.time() - self.started_at, 2),
        }


def evaluate_anchor_regression(
    seed_anchors: dict,
    candidate_anchors: dict,
    *,
    drop_pct: float = DEFAULT_ANCHOR_DROP_PCT,
) -> Optional[BudgetExceeded]:
    """Return :class:`BudgetExceeded` if any seed anchor regresses by more
    than ``drop_pct`` relative to the starting seed.

    Anchors are compared by relative absolute change. ``seed_anchors``
    and ``candidate_anchors`` are flat ``{metabolite: value}`` dicts;
    keys missing from either side are skipped.
    """

    if not isinstance(seed_anchors, dict) or not isinstance(candidate_anchors, dict):
        return None
    for key, seed_val in seed_anchors.items():
        cand_val = candidate_anchors.get(key)
        if seed_val is None or cand_val is None:
            continue
        try:
            seed_f = float(seed_val)
            cand_f = float(cand_val)
        except (TypeError, ValueError):
            continue
        if seed_f == 0.0:
            continue
        regression = (seed_f - cand_f) / abs(seed_f)
        if regression > drop_pct:
            return BudgetExceeded(
                f"protected anchor {key!r} regressed {regression:.2%} "
                f"(threshold {drop_pct:.2%}); seed={seed_f}, candidate={cand_f}"
            )
    return None
