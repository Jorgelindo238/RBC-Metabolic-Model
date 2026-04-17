"""Programmatic curve triage for calibration reports.

Phase 2 (P2) of the improved custom-data calibration pipeline.

This module turns the prose rules in ``CURVE_TRIAGE.md`` into executable
code. Given a ``calibration_report.json`` payload (the dict produced by
``src/MM_calibration.py``), plus the set of metabolites the user actually
measured and the parameters they optimised, it returns a structured
``TriageVerdict`` describing:

* per-metabolite verdicts (``good`` / ``acceptable`` / ``concern`` / ``critical``)
* triage category (physiological anchor / parametric / transport / structural)
* priority tier breakdown
* protected metric status (ATP / ADP / AMP / B23PG coordination)
* discard triggers (ATP collapse, energy-core regression, etc.)
* keep signals (anchors stabilised, adenylate coherent)
* dangerous-compensator activity
* an overall ``keep`` / ``keep_with_caveats`` / ``discard`` / ``needs_review``
  recommendation
* a concrete next-best-experiment suggestion

The module only uses the Python stdlib. It does not import MM_calibration or
touch any solver state. It is safe to run against an arbitrary report dict.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from services.robocop.custom_dataset_planner import (
    ENERGY_ANCHORS,
    EXTRACELLULAR_METABOLITES,
    GLUCOSE_COMMITMENT_ANCHORS,
    LACTATE_OUTLET_ANCHORS,
    PRIORITY_1_METABOLITES,
    PRIORITY_2_METABOLITES,
    PRIORITY_3_METABOLITES,
    PRIORITY_4_METABOLITES,
    REDOX_ANCHORS,
    _dangerous_compensator_reason,
)


# ---------------------------------------------------------------------------
# CURVE_TRIAGE categories
# ---------------------------------------------------------------------------

# Physiological anchors — the curves that summarise whether the storage-lesion
# physiology is being reproduced (CURVE_TRIAGE.md Priority 1).
_PHYSIOLOGICAL_ANCHORS: Set[str] = set(PRIORITY_1_METABOLITES)

# Likely parametric — internal glycolysis + purine intermediates that usually
# reflect local kinetic tuning rather than structural problems.
_LIKELY_PARAMETRIC: Set[str] = (
    PRIORITY_2_METABOLITES
    | {"IMP", "GMP", "HYPX", "URT", "XAN"}
)

# Likely transport / observation-driven — extracellular curves whose mismatch
# often reflects export or observation-model issues.
_LIKELY_TRANSPORT: Set[str] = (
    EXTRACELLULAR_METABOLITES
    | {"INO", "ADE"}
)

# Likely structural — side-metabolism readouts that should be interpreted
# cautiously until anchors are stable.
_LIKELY_STRUCTURAL: Set[str] = {
    "GLU", "GLN", "SER", "SAH", "OXOP", "MAL", "CIT",
}

# ---------------------------------------------------------------------------
# Verdict thresholds
# ---------------------------------------------------------------------------

# Priority 1 anchors use a stricter scale than Priority 2-4.
_PRIORITY_1_THRESHOLDS: Tuple[Tuple[float, str], ...] = (
    (0.25, "good"),
    (0.50, "acceptable"),
    (1.00, "concern"),
)
_PRIORITY_2_4_THRESHOLDS: Tuple[Tuple[float, str], ...] = (
    (0.35, "good"),
    (0.75, "acceptable"),
    (1.50, "concern"),
)

# Protected metric limits — any nRMSE above this on ATP/ADP/AMP/B23PG is
# treated as a hard discard trigger.
_ATP_CRITICAL_NRMSE = 1.0
_ADENYLATE_COHERENCE_SPREAD = 0.6  # max |nRMSE_i - nRMSE_j| across ATP/ADP/AMP


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------

@dataclass
class MetaboliteTriage:
    """Per-metabolite triage outcome."""

    name: str
    priority: int  # 1..4 (0 = unknown)
    category: str  # physiological_anchor / likely_parametric / likely_transport / likely_structural
    nrmse: float
    rmse: Optional[float]
    sim_final: Optional[float]
    exp_final: Optional[float]
    norm_factor: Optional[float]
    verdict: str  # good / acceptable / concern / critical
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProtectedMetricStatus:
    """Status of the ATP / ADP / AMP / B23PG coordination."""

    atp_nrmse: Optional[float]
    adp_nrmse: Optional[float]
    amp_nrmse: Optional[float]
    b23pg_nrmse: Optional[float]
    atp_status: str  # good / acceptable / concern / critical / missing
    adp_status: str
    amp_status: str
    b23pg_status: str
    adenylate_coherent: bool
    adenylate_spread: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TriageVerdict:
    """Overall triage verdict for a calibration report."""

    overall: str  # keep / keep_with_caveats / discard / needs_review
    reason: str
    improvement_pct: Optional[float]
    baseline_loss: Optional[float]
    final_loss: Optional[float]
    priority_breakdown: Dict[int, Dict[str, int]]
    per_metabolite: List[MetaboliteTriage]
    protected_metric_status: ProtectedMetricStatus
    discard_triggers: List[str]
    keep_signals: List[str]
    caveats: List[str]
    dangerous_compensators_active: Dict[str, str]
    next_best_experiment: Optional[str]
    measured_but_missing_from_report: List[str]
    unmeasured_in_report: List[str]
    skipped: bool = False
    skip_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["per_metabolite"] = [entry.to_dict() for entry in self.per_metabolite]
        payload["protected_metric_status"] = self.protected_metric_status.to_dict()
        return payload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize(name: Any) -> str:
    """Uppercase normalisation for metabolite names."""

    if name is None:
        return ""
    return str(name).strip().upper()


def _normalize_list(names: Optional[Iterable[Any]]) -> List[str]:
    """Metabolite-name list normalisation (uppercased, deduped)."""

    if not names:
        return []
    cleaned: List[str] = []
    seen: Set[str] = set()
    for name in names:
        text = _normalize(name)
        if text and text not in seen:
            seen.add(text)
            cleaned.append(text)
    return cleaned


def _normalize_param_list(names: Optional[Iterable[Any]]) -> List[str]:
    """Parameter-name list normalisation that preserves case.

    Parameter identifiers such as ``vmax_VPEP_PASE`` must remain case-sensitive
    so they match the canonical MM_calibration names.
    """

    if not names:
        return []
    cleaned: List[str] = []
    seen: Set[str] = set()
    for name in names:
        if name is None:
            continue
        text = str(name).strip()
        if text and text not in seen:
            seen.add(text)
            cleaned.append(text)
    return cleaned


def _priority_of(name: str) -> int:
    if name in PRIORITY_1_METABOLITES:
        return 1
    if name in PRIORITY_2_METABOLITES:
        return 2
    if name in PRIORITY_3_METABOLITES:
        return 3
    if name in PRIORITY_4_METABOLITES:
        return 4
    return 0


def _category_of(name: str) -> str:
    if name in _PHYSIOLOGICAL_ANCHORS:
        return "physiological_anchor"
    if name in _LIKELY_PARAMETRIC:
        return "likely_parametric"
    if name in _LIKELY_TRANSPORT:
        return "likely_transport"
    if name in _LIKELY_STRUCTURAL:
        return "likely_structural"
    return "uncategorised"


def _classify_verdict(priority: int, nrmse: float) -> str:
    thresholds = _PRIORITY_1_THRESHOLDS if priority == 1 else _PRIORITY_2_4_THRESHOLDS
    for cap, label in thresholds:
        if nrmse <= cap:
            return label
    return "critical"


def _reason_for(name: str, verdict: str, priority: int, category: str) -> str:
    if verdict == "good":
        if category == "physiological_anchor":
            return f"{name} tracks within tolerance and anchors the fit."
        return f"{name} tracks the experimental curve."
    if verdict == "acceptable":
        return (
            f"{name} is close to the experimental trend but has some residual "
            "mismatch."
        )
    if verdict == "concern":
        if priority == 1:
            return (
                f"{name} misses the trend by more than a Priority 1 anchor "
                "should tolerate. Investigate before accepting this run."
            )
        return f"{name} shows a meaningful residual mismatch."
    # critical
    if priority == 1:
        return (
            f"{name} is badly mismatched. As a Priority 1 anchor this alone is "
            "enough to discard the run."
        )
    return f"{name} is badly mismatched. Interpret remaining gains with care."


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_per_metabolite(report: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Accept either ``per_metabolite`` (new contract) or ``metabolite_reports``."""

    payload = report.get("per_metabolite")
    if not payload:
        payload = report.get("metabolite_reports")
    if not payload:
        return []
    if not isinstance(payload, list):
        return []
    return [entry for entry in payload if isinstance(entry, dict)]


# ---------------------------------------------------------------------------
# Protected metric assessment
# ---------------------------------------------------------------------------

def _build_protected_status(
    per_metabolite_by_name: Mapping[str, MetaboliteTriage],
) -> Tuple[ProtectedMetricStatus, List[str]]:
    """Return ``(status, discard_triggers)`` based on the adenylate panel."""

    discard_triggers: List[str] = []

    def _lookup(name: str) -> Tuple[Optional[float], str]:
        entry = per_metabolite_by_name.get(name)
        if entry is None:
            return None, "missing"
        return entry.nrmse, entry.verdict

    atp_nrmse, atp_status = _lookup("ATP")
    adp_nrmse, adp_status = _lookup("ADP")
    amp_nrmse, amp_status = _lookup("AMP")
    b23pg_nrmse, b23pg_status = _lookup("B23PG")

    adenylate = [
        value for value in (atp_nrmse, adp_nrmse, amp_nrmse) if value is not None
    ]
    if len(adenylate) >= 2:
        spread = float(max(adenylate) - min(adenylate))
    else:
        spread = None
    adenylate_coherent = (
        spread is not None and spread <= _ADENYLATE_COHERENCE_SPREAD
    )

    # Discard trigger: ATP critical — this is the strongest rule in CURVE_TRIAGE.
    if atp_nrmse is not None and atp_nrmse > _ATP_CRITICAL_NRMSE:
        discard_triggers.append(
            f"ATP nRMSE={atp_nrmse:.3f} exceeds critical threshold "
            f"{_ATP_CRITICAL_NRMSE}: energy anchor collapsed."
        )
    # Discard trigger: ADP or AMP critical while ATP is 'good' — adenylate
    # incoherence can hide real energy-pool drift.
    if atp_nrmse is not None and atp_nrmse <= 0.25:
        for label, value in (("ADP", adp_nrmse), ("AMP", amp_nrmse)):
            if value is not None and value > _ATP_CRITICAL_NRMSE:
                discard_triggers.append(
                    f"{label} nRMSE={value:.3f} collapsed while ATP looks healthy; "
                    "adenylate pool is incoherent."
                )
    # Adenylate spread warning is a caveat (handled by caller), not a trigger.

    status = ProtectedMetricStatus(
        atp_nrmse=atp_nrmse,
        adp_nrmse=adp_nrmse,
        amp_nrmse=amp_nrmse,
        b23pg_nrmse=b23pg_nrmse,
        atp_status=atp_status,
        adp_status=adp_status,
        amp_status=amp_status,
        b23pg_status=b23pg_status,
        adenylate_coherent=adenylate_coherent,
        adenylate_spread=spread,
    )
    return status, discard_triggers


# ---------------------------------------------------------------------------
# Priority breakdown
# ---------------------------------------------------------------------------

def _empty_verdict_counts() -> Dict[str, int]:
    return {"good": 0, "acceptable": 0, "concern": 0, "critical": 0}


def _priority_breakdown(
    per_metabolite: Sequence[MetaboliteTriage],
) -> Dict[int, Dict[str, int]]:
    breakdown: Dict[int, Dict[str, int]] = {
        1: _empty_verdict_counts(),
        2: _empty_verdict_counts(),
        3: _empty_verdict_counts(),
        4: _empty_verdict_counts(),
    }
    breakdown[0] = _empty_verdict_counts()
    for entry in per_metabolite:
        bucket = breakdown.setdefault(entry.priority, _empty_verdict_counts())
        bucket[entry.verdict] = bucket.get(entry.verdict, 0) + 1
    return breakdown


# ---------------------------------------------------------------------------
# Next-best-experiment
# ---------------------------------------------------------------------------

def _next_best_experiment(
    per_metabolite: Sequence[MetaboliteTriage],
    protected: ProtectedMetricStatus,
    dangerous_active: Mapping[str, str],
) -> Optional[str]:
    critical_p1 = [entry for entry in per_metabolite if entry.priority == 1 and entry.verdict == "critical"]
    concern_p1 = [entry for entry in per_metabolite if entry.priority == 1 and entry.verdict == "concern"]
    critical_p2 = [entry for entry in per_metabolite if entry.priority == 2 and entry.verdict in {"critical", "concern"}]
    critical_p3 = [entry for entry in per_metabolite if entry.priority == 3 and entry.verdict in {"critical", "concern"}]

    if protected.atp_nrmse is not None and protected.atp_nrmse > _ATP_CRITICAL_NRMSE:
        return (
            "Restart on a Vmax-first anchor stage with ATP/ADP/AMP guard rails: "
            "freeze purine exits, tighten vmax_VPFK and vmax_VPGK bounds, and "
            "rerun with atp_focus=True before opening any further stage."
        )
    if critical_p1:
        target_names = ", ".join(entry.name for entry in critical_p1)
        return (
            f"Priority 1 anchors still critical ({target_names}). Rerun the "
            "anchor stage with a narrower Vmax-first search on the controlling "
            "reactions (VEGLC / VHK for glucose, VPK / VLDH for lactate, "
            "VDPGM / V23DPGP for B23PG, VGSR / VGSS for GSH/GSSG)."
        )
    if concern_p1:
        target_names = ", ".join(entry.name for entry in concern_p1)
        return (
            f"Priority 1 anchors improved but still show residual mismatch "
            f"({target_names}). A tightened km_only follow-up on those "
            "reactions is the next best experiment."
        )
    if dangerous_active:
        return (
            "Compensator parameters "
            + ", ".join(sorted(dangerous_active.keys()))
            + " were active. Rerun with them frozen to confirm the fit is not "
            "leaning on them."
        )
    if critical_p2:
        target_names = ", ".join(entry.name for entry in critical_p2)
        return (
            f"Priority 1 anchors are acceptable; open a Priority 2 stage on "
            f"{target_names} using a tightly bounded joint_vmax_km pass."
        )
    if critical_p3:
        target_names = ", ".join(entry.name for entry in critical_p3)
        return (
            f"Priority 1 and 2 are stable; open a core_km_then_purine_transport "
            f"stage focused on {target_names}, keeping VE* exports closed."
        )
    return (
        "All tiers measured show acceptable behaviour. The natural next step is "
        "a promotion benchmark (pure ODE) to confirm the fit is not transient."
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def triage_calibration_report(
    report: Mapping[str, Any],
    *,
    measured_metabolites: Optional[Sequence[str]] = None,
    optimized_params: Optional[Sequence[str]] = None,
) -> TriageVerdict:
    """Run programmatic curve triage on a calibration report payload.

    Parameters
    ----------
    report:
        The parsed ``calibration_report.json`` produced by
        ``src/MM_calibration.py``.
    measured_metabolites:
        Names of the metabolites the user actually uploaded. Used to detect
        mismatches between the request and the report (``measured_but_missing_from_report``,
        ``unmeasured_in_report``).
    optimized_params:
        Names of the parameters the user selected to optimise. Used to flag
        dangerous compensators that were actively tuned during the run.
    """

    per_metabolite_raw = _extract_per_metabolite(report)
    measured_list = _normalize_list(measured_metabolites)
    measured_set = set(measured_list)
    optimized_list = _normalize_param_list(optimized_params)

    per_metabolite: List[MetaboliteTriage] = []
    report_names: Set[str] = set()

    for raw in per_metabolite_raw:
        name = _normalize(raw.get("name"))
        if not name:
            continue
        nrmse = _safe_float(raw.get("nrmse"))
        if nrmse is None:
            continue
        report_names.add(name)
        priority = _priority_of(name)
        category = _category_of(name)
        verdict = _classify_verdict(priority or 2, nrmse)
        per_metabolite.append(
            MetaboliteTriage(
                name=name,
                priority=priority,
                category=category,
                nrmse=nrmse,
                rmse=_safe_float(raw.get("rmse")),
                sim_final=_safe_float(raw.get("sim_final")),
                exp_final=_safe_float(raw.get("exp_final")),
                norm_factor=_safe_float(raw.get("norm_factor")),
                verdict=verdict,
                reason=_reason_for(name, verdict, priority, category),
            )
        )

    per_metabolite.sort(key=lambda item: (-item.nrmse, item.priority, item.name))
    per_metabolite_by_name = {entry.name: entry for entry in per_metabolite}

    baseline_loss = _safe_float(report.get("baseline_loss"))
    final_loss = _safe_float(report.get("final_loss"))
    improvement_pct = _safe_float(report.get("improvement_pct"))

    protected_status, protected_triggers = _build_protected_status(per_metabolite_by_name)

    discard_triggers: List[str] = list(protected_triggers)
    keep_signals: List[str] = []
    caveats: List[str] = []

    priority_breakdown = _priority_breakdown(per_metabolite)

    # Keep signals -----------------------------------------------------------
    p1_counts = priority_breakdown.get(1, _empty_verdict_counts())
    p1_total = sum(p1_counts.values())
    if p1_total > 0 and p1_counts.get("good", 0) >= max(1, (p1_total + 1) // 2):
        keep_signals.append(
            f"{p1_counts['good']}/{p1_total} Priority 1 anchors classified as good."
        )
    if protected_status.adenylate_coherent and protected_status.atp_nrmse is not None:
        keep_signals.append(
            "Adenylate pool is coherent — ATP/ADP/AMP move together."
        )
    if (
        baseline_loss is not None
        and final_loss is not None
        and final_loss < baseline_loss
    ):
        keep_signals.append(
            f"Aggregate loss improved: {baseline_loss:.4f} → {final_loss:.4f}."
        )

    # Additional discard triggers -------------------------------------------
    # (1) Any critical Priority 1 curve is disqualifying on its own.
    critical_p1 = [entry for entry in per_metabolite if entry.priority == 1 and entry.verdict == "critical"]
    for entry in critical_p1:
        discard_triggers.append(
            f"Priority 1 anchor {entry.name} is critical (nRMSE={entry.nrmse:.3f})."
        )

    # (2) Energy-core regression relative to purine wins.
    p3_improvements = [entry for entry in per_metabolite if entry.priority == 3 and entry.verdict == "good"]
    energy_concerns = [
        entry for entry in per_metabolite
        if entry.name in ENERGY_ANCHORS and entry.verdict in {"concern", "critical"}
    ]
    if p3_improvements and energy_concerns:
        discard_triggers.append(
            "Purine curves improved but the energy anchors "
            + ", ".join(entry.name for entry in energy_concerns)
            + " regressed. CURVE_TRIAGE discards this pattern."
        )

    # (3) Side-metabolism wins at the cost of Priority 1 anchors.
    p4_improvements = [entry for entry in per_metabolite if entry.priority == 4 and entry.verdict == "good"]
    if p4_improvements and energy_concerns:
        discard_triggers.append(
            "Priority 4 side curves improved while energy anchors "
            + ", ".join(entry.name for entry in energy_concerns)
            + " regressed. Side-metabolism-driven wins are not promotable."
        )

    # Caveats ---------------------------------------------------------------
    # Extracellular / intracellular disagreement.
    def _entry(name: str) -> Optional[MetaboliteTriage]:
        return per_metabolite_by_name.get(name)

    eglc = _entry("EGLC")
    glc = _entry("GLC")
    if (
        eglc is not None and glc is not None
        and eglc.verdict in {"good", "acceptable"}
        and glc.verdict in {"concern", "critical"}
    ):
        caveats.append(
            "EGLC fits while intracellular GLC is off — likely a transport-only "
            "win hiding an HK/PGI bottleneck."
        )
    elac = _entry("ELAC")
    lac = _entry("LAC")
    pyr = _entry("PYR")
    if (
        elac is not None and lac is not None
        and elac.verdict in {"good", "acceptable"}
        and lac.verdict in {"concern", "critical"}
    ):
        caveats.append(
            "ELAC fits while intracellular LAC is off — consistency check on "
            "VPK / VLDH / VELAC is required before promotion."
        )
    if (
        pyr is not None and pyr.verdict in {"concern", "critical"}
        and lac is not None and lac.verdict in {"good", "acceptable"}
    ):
        caveats.append(
            "LAC looks fine but PYR is off — lower-glycolysis throughput is "
            "suspect (VPK / VLDH balance, VPEP_PASE compensation risk)."
        )

    # Adenylate incoherence caveat.
    if (
        protected_status.adenylate_spread is not None
        and not protected_status.adenylate_coherent
    ):
        caveats.append(
            f"Adenylate panel is incoherent (spread "
            f"{protected_status.adenylate_spread:.3f}). Accept only after "
            "checking that ATP, ADP, and AMP moved consistently."
        )

    # Dangerous compensators active?
    dangerous_active: Dict[str, str] = {}
    for name in optimized_list:
        reason = _dangerous_compensator_reason(name)
        if reason is not None:
            dangerous_active[name] = reason
    if dangerous_active:
        caveats.append(
            "Dangerous compensator parameters were active during the run: "
            + ", ".join(sorted(dangerous_active.keys()))
            + ". Rerun with them frozen if the fit depends on them."
        )

    # Coverage caveats.
    if measured_set:
        missing_from_report = sorted(measured_set - report_names)
        extra_in_report = sorted(report_names - measured_set)
    else:
        missing_from_report = []
        extra_in_report = []
    if missing_from_report:
        caveats.append(
            "The following measured metabolites were not present in the "
            "calibration report and could not be triaged: "
            + ", ".join(missing_from_report)
            + "."
        )

    # Overall verdict -------------------------------------------------------
    if not per_metabolite:
        overall = "needs_review"
        reason = (
            "Calibration report did not include a per-metabolite nRMSE table. "
            "Triage cannot proceed without it."
        )
    elif discard_triggers:
        overall = "discard"
        reason = discard_triggers[0]
    elif caveats and (p1_total == 0 or p1_counts.get("good", 0) < p1_total):
        overall = "keep_with_caveats"
        reason = caveats[0]
    elif p1_total == 0:
        overall = "needs_review"
        reason = (
            "No Priority 1 anchor metabolite was present in the report. "
            "Aggregate score alone is not enough to judge the run."
        )
    elif p1_counts.get("good", 0) == p1_total:
        overall = "keep"
        reason = "All Priority 1 anchors classified as good."
    else:
        overall = "keep_with_caveats"
        reason = (
            "Priority 1 anchors are acceptable overall but not all classified "
            "as good. Review before promotion."
        )

    next_best = _next_best_experiment(per_metabolite, protected_status, dangerous_active)

    return TriageVerdict(
        overall=overall,
        reason=reason,
        improvement_pct=improvement_pct,
        baseline_loss=baseline_loss,
        final_loss=final_loss,
        priority_breakdown=priority_breakdown,
        per_metabolite=per_metabolite,
        protected_metric_status=protected_status,
        discard_triggers=discard_triggers,
        keep_signals=keep_signals,
        caveats=caveats,
        dangerous_compensators_active=dangerous_active,
        next_best_experiment=next_best,
        measured_but_missing_from_report=missing_from_report,
        unmeasured_in_report=extra_in_report,
        skipped=False,
        skip_reason=None,
    )


def skipped_triage(reason: str) -> TriageVerdict:
    """Return a default ``TriageVerdict`` marked as skipped."""

    return TriageVerdict(
        overall="needs_review",
        reason=reason,
        improvement_pct=None,
        baseline_loss=None,
        final_loss=None,
        priority_breakdown={
            0: _empty_verdict_counts(),
            1: _empty_verdict_counts(),
            2: _empty_verdict_counts(),
            3: _empty_verdict_counts(),
            4: _empty_verdict_counts(),
        },
        per_metabolite=[],
        protected_metric_status=ProtectedMetricStatus(
            atp_nrmse=None, adp_nrmse=None, amp_nrmse=None, b23pg_nrmse=None,
            atp_status="missing", adp_status="missing",
            amp_status="missing", b23pg_status="missing",
            adenylate_coherent=False, adenylate_spread=None,
        ),
        discard_triggers=[],
        keep_signals=[],
        caveats=[],
        dangerous_compensators_active={},
        next_best_experiment=None,
        measured_but_missing_from_report=[],
        unmeasured_in_report=[],
        skipped=True,
        skip_reason=reason,
    )


__all__ = [
    "MetaboliteTriage",
    "ProtectedMetricStatus",
    "TriageVerdict",
    "triage_calibration_report",
    "skipped_triage",
]
