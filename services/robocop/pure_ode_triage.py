"""Pure-ODE triage for MM_calibration + main.py trajectories.

This module complements :mod:`services.robocop.curve_triage`. Where
``curve_triage`` inspects the *calibration report* (fit quality per metabolite),
``pure_ode_triage`` inspects the *full pure-ODE trajectory* (the
``all_metabolites.csv`` that ``src/main.py --model brodbar`` writes) and asks
the orthogonal question:

    "Regardless of how well the calibration fit the measured points, did the
    model remain physiologically credible across the full horizon?"

The repeated failure pattern this closes (see ``AgentOps/Memory.md`` and
``AgentOps/CalibrationOps.md``) is:

* the calibration objective improves materially,
* but the pure ODE still drives ATP and ADP toward zero by the end of the
  horizon.

In that scenario the fit-first triage would say ``keep``. Pure-ODE triage
overrides that to ``collapsed`` so promotion-gating tools (Hermes Phase B, the
calibration adapter, the web UI) can refuse to advance the run.

Design rules
------------

* **Thresholds mirror ``src/MM_calibration.py``** (``atp_floor``, ``adp_floor``,
  ``amp_floor``, ``imp_floor``, ``adenylate_target``) so a trajectory that the
  optimizer considers penalised is the same trajectory this module considers
  concerning. No invented numbers.
* **Pure stdlib** — ``csv`` is enough to read the trajectories; no pandas
  dependency on the RoBoCop side.
* **Never raises**: the entry points return a structured ``PureOdeVerdict``
  for every input, including empty or malformed CSVs.
* **Dict-serialisable**: every dataclass exposes ``to_dict`` so the verdict
  can ride on JSON payloads (calibration responses, Hermes Phase B decision
  records) alongside the calibration-report triage verdict.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Physiological thresholds
# ---------------------------------------------------------------------------

# Critical floors — mirror the canonical MM_calibration penalty floors exactly.
# Anything that falls to or below this level counts as a *critical* pure-ODE
# regression no matter what the calibration report said.
ATP_CRITICAL_FLOOR = 0.15
ADP_CRITICAL_FLOOR = 0.05
AMP_CRITICAL_FLOOR = 0.04
IMP_CRITICAL_FLOOR = 0.02

# Concern band — a buffer above the critical floor. Tuned conservatively so a
# run that lands just above MM's penalty floor is still flagged for review.
ATP_CONCERN_FLOOR = 0.225
ADP_CONCERN_FLOOR = 0.075
AMP_CONCERN_FLOOR = 0.06
IMP_CONCERN_FLOOR = 0.03

# Ancillary protected metabolites without MM floors — values taken from
# canonical erythrocyte steady-state ranges (Mulquiney & Kuchel 1999,
# Bordbar et al. 2015). Used as concern/critical thresholds for pure-ODE
# health, not as optimizer penalties.
B23PG_CONCERN_FLOOR = 3.0
B23PG_CRITICAL_FLOOR = 1.5
GSH_CONCERN_FLOOR = 1.5
GSH_CRITICAL_FLOOR = 0.5

# Adenylate pool retention — ratio of final pool to initial pool. Mirrors
# MM_calibration's ``adenylate_target``. Below this ratio the adenylate pool
# has drifted materially during the horizon.
ADENYLATE_POOL_TARGET_RATIO = 0.65
ADENYLATE_POOL_CRITICAL_RATIO = 0.40  # below this ratio => pool collapse

# Extracellular anchor shape thresholds (fractional change over horizon).
EGLC_DEPLETION_EXPECTED_PCT = -5.0     # EGLC is expected to fall at least 5%
EGLC_DEPLETION_CRITICAL_PCT = 2.0      # EGLC rising >2% is structurally wrong
ELAC_ACCUMULATION_EXPECTED_PCT = 5.0   # ELAC is expected to rise at least 5%
ELAC_ACCUMULATION_CRITICAL_PCT = -5.0  # ELAC falling >5% is structurally wrong

# Focus set — the short list of metabolites that carry scientific weight in
# triage. Mirrors ``services.robocop.calibration_phase_b.FOCUS_METABOLITES``
# but kept independent so this module has no import cycle with Phase B.
DEFAULT_FOCUS_METABOLITES: Tuple[str, ...] = (
    "ATP", "ADP", "AMP", "IMP",
    "EGLC", "ELAC", "LAC",
    "PYR", "PEP",
    "B23PG", "GSH", "GSSG",
)

# Metabolites that participate in the adenylate pool coherence check.
ADENYLATE_POOL_MEMBERS: Tuple[str, ...] = ("ATP", "ADP", "AMP")

# Overall verdict strings.
VERDICT_HEALTHY = "healthy"
VERDICT_COMPROMISED = "compromised"
VERDICT_COLLAPSED = "collapsed"
VERDICT_NEEDS_REVIEW = "needs_review"

# Single-metabolite state strings.
STATE_GOOD = "good"
STATE_CONCERN = "concern"
STATE_CRITICAL = "critical"
STATE_MISSING = "missing"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class TrajectoryStats:
    """Summary statistics of a single metabolite trajectory."""

    name: str
    available: bool
    start: Optional[float] = None
    end: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    delta: Optional[float] = None
    pct_delta: Optional[float] = None
    shape: str = "flat"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProtectedFloorStatus:
    """Absolute-floor verdict for one protected metabolite."""

    metabolite: str
    final_value: Optional[float]
    min_value: Optional[float]
    critical_floor: float
    concern_floor: float
    state: str
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AdenylatePoolHealth:
    """Coherence of the ATP+ADP+AMP pool across the horizon."""

    atp_end: Optional[float]
    adp_end: Optional[float]
    amp_end: Optional[float]
    pool_start: Optional[float]
    pool_end: Optional[float]
    pool_ratio: Optional[float]
    target_ratio: float
    critical_ratio: float
    coherent: bool
    state: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExtracellularAnchorStatus:
    """Shape-based verdict for extracellular glucose / lactate anchors."""

    metabolite: str
    start: Optional[float]
    end: Optional[float]
    pct_delta: Optional[float]
    expected_direction: str  # "falling" | "rising"
    state: str
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PureOdeVerdict:
    """Complete pure-ODE triage verdict for a single run."""

    overall: str
    reason: str
    csv_path: Optional[str]
    timepoint_count: int
    horizon_days: Optional[float]
    protected_floor_status: Dict[str, ProtectedFloorStatus] = field(default_factory=dict)
    adenylate_pool: Optional[AdenylatePoolHealth] = None
    extracellular_anchor_status: Dict[str, ExtracellularAnchorStatus] = field(default_factory=dict)
    per_metabolite: List[TrajectoryStats] = field(default_factory=list)
    collapse_signals: List[str] = field(default_factory=list)
    concern_signals: List[str] = field(default_factory=list)
    healthy_signals: List[str] = field(default_factory=list)
    caveats: List[str] = field(default_factory=list)
    recommendation: str = ""
    unavailable_metabolites: List[str] = field(default_factory=list)
    skipped: bool = False
    skip_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall": self.overall,
            "reason": self.reason,
            "csv_path": self.csv_path,
            "timepoint_count": self.timepoint_count,
            "horizon_days": self.horizon_days,
            "protected_floor_status": {
                name: status.to_dict() for name, status in self.protected_floor_status.items()
            },
            "adenylate_pool": self.adenylate_pool.to_dict() if self.adenylate_pool else None,
            "extracellular_anchor_status": {
                name: status.to_dict() for name, status in self.extracellular_anchor_status.items()
            },
            "per_metabolite": [entry.to_dict() for entry in self.per_metabolite],
            "collapse_signals": list(self.collapse_signals),
            "concern_signals": list(self.concern_signals),
            "healthy_signals": list(self.healthy_signals),
            "caveats": list(self.caveats),
            "recommendation": self.recommendation,
            "unavailable_metabolites": list(self.unavailable_metabolites),
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
        }


@dataclass
class CombinedVerdict:
    """Merged verdict from calibration-report triage + pure-ODE triage."""

    overall: str
    reason: str
    calibration_triage: Optional[Dict[str, Any]]
    pure_ode_triage: Optional[Dict[str, Any]]
    discard_triggers: List[str] = field(default_factory=list)
    caveats: List[str] = field(default_factory=list)
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall": self.overall,
            "reason": self.reason,
            "discard_triggers": list(self.discard_triggers),
            "caveats": list(self.caveats),
            "recommendation": self.recommendation,
            "calibration_triage": self.calibration_triage,
            "pure_ode_triage": self.pure_ode_triage,
        }


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _finalise_shape(start: float, end: float, min_value: float, max_value: float) -> str:
    """Classify the trajectory shape the same way Phase B does."""

    reference = max(abs(start), 1.0)
    collapse_floor = max(1e-9, 0.05 * max(start, 1e-9))
    if end <= collapse_floor:
        return "collapse"
    delta = end - start
    if delta > 0.05 * reference:
        return "rising"
    if delta < -0.05 * reference:
        return "falling"
    return "flat"


def _compute_trajectory_stats(name: str, values: Sequence[Optional[float]]) -> TrajectoryStats:
    clean = [v for v in values if v is not None]
    if not clean:
        return TrajectoryStats(name=name, available=False)
    start = float(clean[0])
    end = float(clean[-1])
    min_value = float(min(clean))
    max_value = float(max(clean))
    delta = end - start
    pct_delta = (delta / start * 100.0) if abs(start) > 1e-12 else None
    shape = _finalise_shape(start, end, min_value, max_value)
    return TrajectoryStats(
        name=name,
        available=True,
        start=round(start, 6),
        end=round(end, 6),
        min_value=round(min_value, 6),
        max_value=round(max_value, 6),
        delta=round(delta, 6),
        pct_delta=round(pct_delta, 3) if pct_delta is not None else None,
        shape=shape,
    )


def _read_metabolite_trajectories(
    csv_path: Path,
    focus: Iterable[str],
) -> Tuple[Dict[str, List[Optional[float]]], List[float], int]:
    """Read trajectories for ``focus`` metabolites from ``csv_path``."""

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    focus_list = list(focus)
    trajectories: Dict[str, List[Optional[float]]] = {name: [] for name in focus_list}
    times: List[float] = []

    time_col: Optional[str] = None
    if rows:
        first_row_keys = list(rows[0].keys())
        for candidate in ("Time (days)", "time (days)", "time", "Time", "t"):
            if candidate in first_row_keys:
                time_col = candidate
                break

    for row in rows:
        if time_col is not None:
            t_val = _safe_float(row.get(time_col))
            if t_val is not None:
                times.append(t_val)
        for name in focus_list:
            raw = row.get(name)
            if raw is None:
                # Fall back to case-insensitive lookup so a CSV capitalisation
                # quirk does not silently break triage.
                for key in row.keys():
                    if key and key.upper() == name:
                        raw = row.get(key)
                        break
            trajectories[name].append(_safe_float(raw))

    return trajectories, times, len(rows)


# ---------------------------------------------------------------------------
# Floor classification
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _FloorSpec:
    metabolite: str
    critical: float
    concern: float


_DEFAULT_PROTECTED_FLOORS: Tuple[_FloorSpec, ...] = (
    _FloorSpec("ATP", ATP_CRITICAL_FLOOR, ATP_CONCERN_FLOOR),
    _FloorSpec("ADP", ADP_CRITICAL_FLOOR, ADP_CONCERN_FLOOR),
    _FloorSpec("AMP", AMP_CRITICAL_FLOOR, AMP_CONCERN_FLOOR),
    _FloorSpec("IMP", IMP_CRITICAL_FLOOR, IMP_CONCERN_FLOOR),
    _FloorSpec("B23PG", B23PG_CRITICAL_FLOOR, B23PG_CONCERN_FLOOR),
    _FloorSpec("GSH", GSH_CRITICAL_FLOOR, GSH_CONCERN_FLOOR),
)


def _classify_floor(stats: TrajectoryStats, spec: _FloorSpec) -> ProtectedFloorStatus:
    if not stats.available:
        return ProtectedFloorStatus(
            metabolite=spec.metabolite,
            final_value=None,
            min_value=None,
            critical_floor=spec.critical,
            concern_floor=spec.concern,
            state=STATE_MISSING,
            rationale=f"{spec.metabolite} not present in the pure-ODE trajectory CSV.",
        )
    final_value = stats.end
    min_value = stats.min_value
    if final_value is None or min_value is None:
        return ProtectedFloorStatus(
            metabolite=spec.metabolite,
            final_value=final_value,
            min_value=min_value,
            critical_floor=spec.critical,
            concern_floor=spec.concern,
            state=STATE_MISSING,
            rationale=f"{spec.metabolite} trajectory was unreadable.",
        )
    if min_value <= spec.critical:
        state = STATE_CRITICAL
        rationale = (
            f"{spec.metabolite} fell to {min_value:g} mM, at or below the "
            f"critical physiological floor ({spec.critical:g} mM)."
        )
    elif final_value <= spec.critical:
        state = STATE_CRITICAL
        rationale = (
            f"{spec.metabolite} ended at {final_value:g} mM, at or below the "
            f"critical physiological floor ({spec.critical:g} mM)."
        )
    elif final_value <= spec.concern:
        state = STATE_CONCERN
        rationale = (
            f"{spec.metabolite} ended at {final_value:g} mM, below the "
            f"physiological concern level ({spec.concern:g} mM)."
        )
    elif min_value <= spec.concern:
        state = STATE_CONCERN
        rationale = (
            f"{spec.metabolite} transiently reached {min_value:g} mM, below the "
            f"concern level ({spec.concern:g} mM), even though it recovered to "
            f"{final_value:g} mM by the final timepoint."
        )
    else:
        state = STATE_GOOD
        rationale = (
            f"{spec.metabolite} stayed above the concern floor "
            f"({spec.concern:g} mM) throughout the horizon "
            f"(final={final_value:g} mM, min={min_value:g} mM)."
        )
    return ProtectedFloorStatus(
        metabolite=spec.metabolite,
        final_value=final_value,
        min_value=min_value,
        critical_floor=spec.critical,
        concern_floor=spec.concern,
        state=state,
        rationale=rationale,
    )


# ---------------------------------------------------------------------------
# Adenylate pool coherence
# ---------------------------------------------------------------------------

def _adenylate_pool_health(stats_by_name: Dict[str, TrajectoryStats]) -> AdenylatePoolHealth:
    atp = stats_by_name.get("ATP")
    adp = stats_by_name.get("ADP")
    amp = stats_by_name.get("AMP")
    if not (atp and atp.available and adp and adp.available and amp and amp.available):
        return AdenylatePoolHealth(
            atp_end=atp.end if (atp and atp.available) else None,
            adp_end=adp.end if (adp and adp.available) else None,
            amp_end=amp.end if (amp and amp.available) else None,
            pool_start=None,
            pool_end=None,
            pool_ratio=None,
            target_ratio=ADENYLATE_POOL_TARGET_RATIO,
            critical_ratio=ADENYLATE_POOL_CRITICAL_RATIO,
            coherent=False,
            state=STATE_MISSING,
        )
    pool_start = float((atp.start or 0.0) + (adp.start or 0.0) + (amp.start or 0.0))
    pool_end = float((atp.end or 0.0) + (adp.end or 0.0) + (amp.end or 0.0))
    pool_ratio = pool_end / pool_start if pool_start > 1e-12 else None
    if pool_ratio is None:
        state = STATE_MISSING
        coherent = False
    elif pool_ratio < ADENYLATE_POOL_CRITICAL_RATIO:
        state = STATE_CRITICAL
        coherent = False
    elif pool_ratio < ADENYLATE_POOL_TARGET_RATIO:
        state = STATE_CONCERN
        coherent = False
    else:
        state = STATE_GOOD
        coherent = True
    return AdenylatePoolHealth(
        atp_end=atp.end,
        adp_end=adp.end,
        amp_end=amp.end,
        pool_start=round(pool_start, 6),
        pool_end=round(pool_end, 6),
        pool_ratio=round(pool_ratio, 4) if pool_ratio is not None else None,
        target_ratio=ADENYLATE_POOL_TARGET_RATIO,
        critical_ratio=ADENYLATE_POOL_CRITICAL_RATIO,
        coherent=coherent,
        state=state,
    )


# ---------------------------------------------------------------------------
# Extracellular anchor checks
# ---------------------------------------------------------------------------

def _classify_extracellular_anchor(
    name: str,
    stats: Optional[TrajectoryStats],
    *,
    expected_direction: str,
    expected_pct: float,
    critical_pct: float,
) -> ExtracellularAnchorStatus:
    if stats is None or not stats.available:
        return ExtracellularAnchorStatus(
            metabolite=name,
            start=None,
            end=None,
            pct_delta=None,
            expected_direction=expected_direction,
            state=STATE_MISSING,
            rationale=f"{name} not present in the pure-ODE trajectory CSV.",
        )
    pct = stats.pct_delta
    if pct is None:
        return ExtracellularAnchorStatus(
            metabolite=name,
            start=stats.start,
            end=stats.end,
            pct_delta=None,
            expected_direction=expected_direction,
            state=STATE_MISSING,
            rationale=f"{name} initial value was zero; percent change undefined.",
        )
    if expected_direction == "falling":
        if pct >= critical_pct:
            state = STATE_CRITICAL
            rationale = (
                f"{name} rose by {pct:.1f}% over the horizon; extracellular "
                "glucose should deplete, not accumulate."
            )
        elif pct > expected_pct:
            state = STATE_CONCERN
            rationale = (
                f"{name} changed by only {pct:.1f}% over the horizon "
                f"(expected at least {-expected_pct:.1f}% depletion)."
            )
        else:
            state = STATE_GOOD
            rationale = f"{name} depleted by {-pct:.1f}% over the horizon."
    else:  # rising
        if pct <= critical_pct:
            state = STATE_CRITICAL
            rationale = (
                f"{name} fell by {-pct:.1f}% over the horizon; extracellular "
                "lactate should accumulate, not decline."
            )
        elif pct < expected_pct:
            state = STATE_CONCERN
            rationale = (
                f"{name} only rose by {pct:.1f}% over the horizon "
                f"(expected at least {expected_pct:.1f}% accumulation)."
            )
        else:
            state = STATE_GOOD
            rationale = f"{name} accumulated by {pct:.1f}% over the horizon."
    return ExtracellularAnchorStatus(
        metabolite=name,
        start=stats.start,
        end=stats.end,
        pct_delta=pct,
        expected_direction=expected_direction,
        state=state,
        rationale=rationale,
    )


# ---------------------------------------------------------------------------
# Verdict assembly
# ---------------------------------------------------------------------------

def _assemble_verdict(
    *,
    csv_path: Optional[str],
    times: Sequence[float],
    timepoint_count: int,
    stats_by_name: Dict[str, TrajectoryStats],
    focus_metabolites: Sequence[str],
) -> PureOdeVerdict:
    """Turn per-metabolite stats into a PureOdeVerdict."""

    per_metabolite = [stats_by_name[name] for name in focus_metabolites if name in stats_by_name]
    unavailable = [name for name in focus_metabolites if not stats_by_name.get(name, TrajectoryStats(name=name, available=False)).available]

    # Protected floor checks.
    floor_status: Dict[str, ProtectedFloorStatus] = {}
    for spec in _DEFAULT_PROTECTED_FLOORS:
        stats = stats_by_name.get(spec.metabolite, TrajectoryStats(name=spec.metabolite, available=False))
        floor_status[spec.metabolite] = _classify_floor(stats, spec)

    # Adenylate pool coherence.
    adenylate = _adenylate_pool_health(stats_by_name)

    # Extracellular anchors.
    extracellular: Dict[str, ExtracellularAnchorStatus] = {}
    extracellular["EGLC"] = _classify_extracellular_anchor(
        "EGLC",
        stats_by_name.get("EGLC"),
        expected_direction="falling",
        expected_pct=EGLC_DEPLETION_EXPECTED_PCT,
        critical_pct=EGLC_DEPLETION_CRITICAL_PCT,
    )
    extracellular["ELAC"] = _classify_extracellular_anchor(
        "ELAC",
        stats_by_name.get("ELAC"),
        expected_direction="rising",
        expected_pct=ELAC_ACCUMULATION_EXPECTED_PCT,
        critical_pct=ELAC_ACCUMULATION_CRITICAL_PCT,
    )

    # Aggregate signals across all checks.
    collapse_signals: List[str] = []
    concern_signals: List[str] = []
    healthy_signals: List[str] = []

    for status in floor_status.values():
        if status.state == STATE_CRITICAL:
            collapse_signals.append(status.rationale)
        elif status.state == STATE_CONCERN:
            concern_signals.append(status.rationale)
        elif status.state == STATE_GOOD:
            healthy_signals.append(status.rationale)

    if adenylate.state == STATE_CRITICAL:
        collapse_signals.append(
            f"Adenylate pool collapsed: ratio {adenylate.pool_ratio} ≤ critical "
            f"{adenylate.critical_ratio:g}."
        )
    elif adenylate.state == STATE_CONCERN:
        concern_signals.append(
            f"Adenylate pool drifted: ratio {adenylate.pool_ratio} < target "
            f"{adenylate.target_ratio:g}."
        )
    elif adenylate.state == STATE_GOOD:
        healthy_signals.append(
            f"Adenylate pool held: ratio {adenylate.pool_ratio} ≥ target "
            f"{adenylate.target_ratio:g}."
        )

    for status in extracellular.values():
        if status.state == STATE_CRITICAL:
            collapse_signals.append(status.rationale)
        elif status.state == STATE_CONCERN:
            concern_signals.append(status.rationale)
        elif status.state == STATE_GOOD:
            healthy_signals.append(status.rationale)

    # Overall verdict precedence: collapsed > compromised > healthy > needs_review.
    has_critical = bool(collapse_signals)
    has_concern = bool(concern_signals)
    has_any_available = any(
        stats.available for stats in stats_by_name.values()
    )

    if not has_any_available:
        overall = VERDICT_NEEDS_REVIEW
        reason = "No focus metabolites were readable from the trajectory CSV."
        recommendation = (
            "Review the run manually — the pure-ODE CSV does not contain the "
            "focus metabolites required for triage."
        )
    elif has_critical:
        overall = VERDICT_COLLAPSED
        reason = (
            f"{len(collapse_signals)} critical physiological signal(s) detected "
            "in the pure ODE."
        )
        recommendation = (
            "Do not promote this candidate — the pure ODE violated one or more "
            "absolute physiological floors. Rebuild the basin before further "
            "calibration fitting."
        )
    elif has_concern:
        overall = VERDICT_COMPROMISED
        reason = (
            f"{len(concern_signals)} physiological concern signal(s) detected "
            "in the pure ODE."
        )
        recommendation = (
            "Promote with caution — the pure ODE stayed above the absolute "
            "floors but drifted below the physiological concern levels. Treat "
            "as informative, not promotion-ready."
        )
    else:
        overall = VERDICT_HEALTHY
        reason = "All protected floors, the adenylate pool, and extracellular anchors held within physiological ranges."
        recommendation = (
            "Pure-ODE health is acceptable. Combine with the calibration-report "
            "triage to make the final keep/discard decision."
        )

    horizon_days: Optional[float] = None
    if times:
        horizon_days = float(times[-1] - times[0]) if len(times) > 1 else float(times[-1])

    caveats: List[str] = []
    if unavailable:
        caveats.append(
            "The following focus metabolites were not present in the trajectory "
            f"CSV: {', '.join(sorted(unavailable))}."
        )

    return PureOdeVerdict(
        overall=overall,
        reason=reason,
        csv_path=csv_path,
        timepoint_count=timepoint_count,
        horizon_days=horizon_days,
        protected_floor_status=floor_status,
        adenylate_pool=adenylate,
        extracellular_anchor_status=extracellular,
        per_metabolite=per_metabolite,
        collapse_signals=collapse_signals,
        concern_signals=concern_signals,
        healthy_signals=healthy_signals,
        caveats=caveats,
        recommendation=recommendation,
        unavailable_metabolites=unavailable,
    )


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def skipped_pure_ode_triage(reason: str) -> PureOdeVerdict:
    """Emit a ``needs_review`` verdict when pure-ODE triage cannot run."""

    reason_text = str(reason).strip() or "pure-ODE triage skipped"
    return PureOdeVerdict(
        overall=VERDICT_NEEDS_REVIEW,
        reason=reason_text,
        csv_path=None,
        timepoint_count=0,
        horizon_days=None,
        protected_floor_status={},
        adenylate_pool=None,
        extracellular_anchor_status={},
        per_metabolite=[],
        collapse_signals=[],
        concern_signals=[],
        healthy_signals=[],
        caveats=[reason_text],
        recommendation="Review the run manually — pure-ODE triage did not execute.",
        unavailable_metabolites=[],
        skipped=True,
        skip_reason=reason_text,
    )


def triage_pure_ode_trajectories(
    times: Sequence[float],
    trajectories: Dict[str, Sequence[Optional[float]]],
    *,
    focus_metabolites: Optional[Sequence[str]] = None,
    csv_path: Optional[str] = None,
) -> PureOdeVerdict:
    """Pure-ODE triage on in-memory trajectories.

    This is the testing-friendly entry point that bypasses CSV reading. The
    ``trajectories`` mapping may contain metabolites outside ``focus_metabolites``
    without affecting the verdict.
    """

    focus = tuple(focus_metabolites) if focus_metabolites else DEFAULT_FOCUS_METABOLITES
    stats_by_name: Dict[str, TrajectoryStats] = {}
    for name in focus:
        values = trajectories.get(name)
        if values is None:
            # Accept case-insensitive key matches so a caller using lowercase
            # metabolite names still benefits from triage.
            for key in trajectories.keys():
                if str(key).upper() == name:
                    values = trajectories[key]
                    break
        stats_by_name[name] = _compute_trajectory_stats(name, values or [])
    timepoint_count = len(times) if times is not None else 0
    return _assemble_verdict(
        csv_path=csv_path,
        times=times or [],
        timepoint_count=timepoint_count,
        stats_by_name=stats_by_name,
        focus_metabolites=focus,
    )


def triage_pure_ode_csv(
    csv_path: Any,
    *,
    focus_metabolites: Optional[Sequence[str]] = None,
) -> PureOdeVerdict:
    """Pure-ODE triage on a ``main.py --model brodbar`` trajectory CSV.

    Returns a ``needs_review`` verdict — never raises — if the CSV is missing,
    empty, or malformed.
    """

    if csv_path is None:
        return skipped_pure_ode_triage("no pure-ODE CSV path was provided")
    try:
        path = Path(csv_path)
    except TypeError:
        return skipped_pure_ode_triage(f"invalid pure-ODE CSV path: {csv_path!r}")
    if not path.exists() or not path.is_file():
        return skipped_pure_ode_triage(
            f"pure-ODE CSV not found at {path}; run main.py first or pass a valid path."
        )

    focus = tuple(focus_metabolites) if focus_metabolites else DEFAULT_FOCUS_METABOLITES

    try:
        trajectories, times, timepoint_count = _read_metabolite_trajectories(path, focus)
    except Exception as exc:  # pragma: no cover - defensive fallback
        return skipped_pure_ode_triage(
            f"pure-ODE CSV at {path} could not be parsed: {exc}"
        )

    if timepoint_count == 0:
        return skipped_pure_ode_triage(f"pure-ODE CSV at {path} contains no rows.")

    stats_by_name = {
        name: _compute_trajectory_stats(name, trajectories.get(name, []))
        for name in focus
    }
    return _assemble_verdict(
        csv_path=str(path),
        times=times,
        timepoint_count=timepoint_count,
        stats_by_name=stats_by_name,
        focus_metabolites=focus,
    )


# ---------------------------------------------------------------------------
# Combined verdict (calibration-report + pure-ODE)
# ---------------------------------------------------------------------------

# Map the overall strings from curve_triage to a numeric severity so we can
# combine them with the pure-ODE verdict without reaching into that module's
# internals.
_CALIBRATION_SEVERITY = {
    "keep": 0,
    "keep_with_caveats": 1,
    "discard": 3,
    "needs_review": 1,
}

_PURE_ODE_SEVERITY = {
    VERDICT_HEALTHY: 0,
    VERDICT_COMPROMISED: 2,
    VERDICT_COLLAPSED: 3,
    VERDICT_NEEDS_REVIEW: 1,
}


def combine_triage_verdicts(
    calibration_verdict: Optional[Dict[str, Any]],
    pure_ode_verdict: Optional[Dict[str, Any]],
) -> CombinedVerdict:
    """Merge calibration-report triage + pure-ODE triage into one verdict.

    Rules (most severe wins):

    * Pure-ODE ``collapsed`` → combined ``discard`` regardless of calibration.
    * Calibration ``discard`` → combined ``discard``.
    * Pure-ODE ``compromised`` + calibration ``keep`` → combined
      ``keep_with_caveats``.
    * Pure-ODE ``compromised`` + calibration ``keep_with_caveats`` →
      combined ``discard`` (too many warnings accumulated).
    * Pure-ODE ``healthy`` + calibration ``keep`` → combined ``keep``.
    * Otherwise ``needs_review``.
    """

    cal_overall = str((calibration_verdict or {}).get("overall", "")) if calibration_verdict else ""
    pure_overall = str((pure_ode_verdict or {}).get("overall", "")) if pure_ode_verdict else ""

    cal_severity = _CALIBRATION_SEVERITY.get(cal_overall, 1) if calibration_verdict else 1
    pure_severity = _PURE_ODE_SEVERITY.get(pure_overall, 1) if pure_ode_verdict else 1

    discard_triggers: List[str] = []
    caveats: List[str] = []

    if calibration_verdict:
        discard_triggers.extend(str(t) for t in (calibration_verdict.get("discard_triggers") or []))
        caveats.extend(str(c) for c in (calibration_verdict.get("caveats") or []))

    if pure_ode_verdict:
        discard_triggers.extend(str(s) for s in (pure_ode_verdict.get("collapse_signals") or []))
        caveats.extend(str(s) for s in (pure_ode_verdict.get("concern_signals") or []))
        caveats.extend(str(c) for c in (pure_ode_verdict.get("caveats") or []))

    # Derive the final label from the two severities.
    if pure_overall == VERDICT_COLLAPSED:
        overall = "discard"
        reason = (
            "Pure ODE collapsed despite calibration-report classification; "
            "protected physiological floors were violated."
        )
    elif cal_overall == "discard":
        overall = "discard"
        reason = (
            "Calibration-report triage returned discard."
            + (" Pure-ODE triage was also compromised." if pure_overall == VERDICT_COMPROMISED else "")
        )
    elif pure_overall == VERDICT_COMPROMISED and cal_overall == "keep_with_caveats":
        overall = "discard"
        reason = (
            "Calibration-report triage flagged caveats AND the pure ODE drifted "
            "below physiological concern levels — too much accumulated risk to keep."
        )
    elif pure_overall == VERDICT_COMPROMISED and cal_overall == "keep":
        overall = "keep_with_caveats"
        reason = (
            "Calibration fit is acceptable but the pure ODE drifted below "
            "physiological concern levels; treat as informative."
        )
    elif cal_overall == "keep" and pure_overall == VERDICT_HEALTHY:
        overall = "keep"
        reason = "Calibration fit and pure-ODE health both passed."
    elif cal_overall == "keep_with_caveats" and pure_overall == VERDICT_HEALTHY:
        overall = "keep_with_caveats"
        reason = (
            "Pure ODE is healthy but the calibration-report triage raised caveats; "
            "treat as informative."
        )
    elif cal_overall in {"keep", "keep_with_caveats"} and pure_ode_verdict is None:
        overall = "needs_review"
        reason = (
            "Calibration-report triage passed but pure-ODE triage was not "
            "executed; re-run main.py on the candidate and triage the "
            "all_metabolites.csv output before promoting."
        )
    else:
        overall = "needs_review"
        reason = "Insufficient information to combine calibration and pure-ODE triage."

    # If the calibration triage explicitly promoted the run, append a combined
    # recommendation from the pure-ODE side so the operator sees the next step.
    recommendation_parts: List[str] = []
    if pure_ode_verdict and pure_ode_verdict.get("recommendation"):
        recommendation_parts.append(str(pure_ode_verdict["recommendation"]))
    if calibration_verdict and calibration_verdict.get("next_best_experiment"):
        recommendation_parts.append(
            "Next-best experiment: " + str(calibration_verdict["next_best_experiment"])
        )
    recommendation = " ".join(recommendation_parts).strip()

    return CombinedVerdict(
        overall=overall,
        reason=reason,
        calibration_triage=calibration_verdict,
        pure_ode_triage=pure_ode_verdict,
        discard_triggers=discard_triggers,
        caveats=caveats,
        recommendation=recommendation,
    )
