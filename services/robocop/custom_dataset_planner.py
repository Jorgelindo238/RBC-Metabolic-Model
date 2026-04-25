"""Dataset-aware calibration planner for custom-data runs.

Phase 1 (P1) of the improved custom-data calibration pipeline.

This module is a pure-Python function library. It does not import MM_calibration
or FastAPI; it takes a user's measured metabolite list + their requested
parameters and returns:

* a ``CustomDataAssessment`` summarising which priority tiers are actually
  measured,
* a ``CustomDataPlan`` with the recommended ``target_scope``,
  ``optimization_strategy``, ``parameter_additions`` (filtered to match the
  measurement coverage), flagged dangerous compensators, and a structured
  stage outline.

The adapter (``apps/api/services/mm_calibration_adapter.py``) is responsible
for consuming this plan and wiring it into ``MM_calibration.run_calibration``.

All data comes from the curve-triage rules summarized in
``AgentOps/CalibrationOps.md`` and the agreed custom-data contract. Nothing in
the scientific core is mutated.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


# ---------------------------------------------------------------------------
# Triage priority tiers (mirrors CalibrationOps protected-anchor ordering)
# ---------------------------------------------------------------------------

PRIORITY_1_METABOLITES: Set[str] = {
    "EGLC", "GLC", "ELAC", "LAC",
    "ATP", "ADP", "AMP",
    "B23PG", "GSH", "GSSG",
}

PRIORITY_2_METABOLITES: Set[str] = {
    "G6P", "F6P", "F16BP", "P2G", "PEP", "PYR",
}

PRIORITY_3_METABOLITES: Set[str] = {
    "IMP", "INO", "HYPX", "XAN", "URT", "GMP", "ADE",
}

PRIORITY_4_METABOLITES: Set[str] = {
    "GLU", "GLN", "SER", "SAH", "OXOP", "MAL", "CIT",
    # secondary extracellular readouts per the low-priority triage tier
    "EXAN", "EURT", "EGLN", "EGLU", "EADE", "EINO", "EHYPX",
    "EMAL", "EFUM", "ECIT", "EOXOP", "ESER", "EARG",
    "EGSH", "EGSSG", "EASN", "EALA", "ECYS", "EMET", "EASP",
    "ENH4", "EPYR", "ECYT",
}

# Functional anchor groupings (used to pick ``target_scope``)
ENERGY_ANCHORS: Set[str] = {"ATP", "ADP", "AMP", "B23PG"}
GLUCOSE_COMMITMENT_ANCHORS: Set[str] = {"EGLC", "GLC"}
LACTATE_OUTLET_ANCHORS: Set[str] = {"ELAC", "LAC", "PYR"}
REDOX_ANCHORS: Set[str] = {"GSH", "GSSG"}

# Extracellular metabolites (shape decides ``glycolysis_extracellular`` scope)
EXTRACELLULAR_METABOLITES: Set[str] = {
    name for name in (
        PRIORITY_1_METABOLITES | PRIORITY_2_METABOLITES
        | PRIORITY_3_METABOLITES | PRIORITY_4_METABOLITES
    ) if name.startswith("E")
}

# ---------------------------------------------------------------------------
# Dangerous compensators (mirrors CalibrationOps compensator guardrails)
# ---------------------------------------------------------------------------

_DANGEROUS_COMPENSATOR_DIRECT: Dict[str, str] = {
    "vmax_VPEP_PASE": (
        "VPEP_PASE provides an ADP-independent escape from PEP to PYR. It can "
        "mask a real VENOPGM or VPK bottleneck. Open it only late and under "
        "tight bounds."
    ),
    "vmax_Vnucleo_GMP": (
        "Vnucleo_GMP opens a guanylate exit and can improve purine loss by "
        "draining GMP. Keep it restricted until the core purine pools behave."
    ),
    "vmax_VGDA": (
        "VGDA pushes guanine toward xanthine and can improve downstream purine "
        "readouts while worsening pool realism. Late-stage knob, not an early "
        "benchmark lever."
    ),
    "vmax_VPHGDH": (
        "VPHGDH can act as a side sink from the P3G region into serine "
        "metabolism. Do not open before core glycolysis is stable."
    ),
    "vmax_VOPLAH": (
        "VOPLAH can clear OXOP and perturb ATP usage in the side glutathione "
        "cycle. Open only after ATP and glutathione anchors are acceptable."
    ),
}

# Secondary VE* exports listed as compensators in CalibrationOps.
_DANGEROUS_EXPORT_VMAXS: Set[str] = {
    "vmax_VEXAN", "vmax_VEURT", "vmax_VEINO", "vmax_VEADE",
    "vmax_VEGLN", "vmax_VEGLU", "vmax_VEOXOP", "vmax_VESER",
    "vmax_VEMAL", "vmax_VEFUM", "vmax_VECIT", "vmax_VEASP",
    "vmax_VEARG", "vmax_VEADO",
}

_DANGEROUS_EXPORT_REASON = (
    "Secondary VE* export terms can lift extracellular curves without fixing "
    "the internal pathway state that produced them. Interpret only after the "
    "corresponding intracellular family is already plausible."
)


def _dangerous_compensator_reason(param_name: str) -> Optional[str]:
    if param_name in _DANGEROUS_COMPENSATOR_DIRECT:
        return _DANGEROUS_COMPENSATOR_DIRECT[param_name]
    if param_name in _DANGEROUS_EXPORT_VMAXS:
        return _DANGEROUS_EXPORT_REASON
    return None


# ---------------------------------------------------------------------------
# Purine-tier parameter additions gated by measurement coverage
# ---------------------------------------------------------------------------

# These are the purine-specific params that ``infer_custom_data_calibration_profile``
# injects even when the user did not measure any purine metabolite. The planner
# strips them in that case.
_PURINE_ADDITIONS_WITHOUT_PURINE_DATA: Set[str] = {
    "vmax_VAMPD1",
    "vmax_VAPRT",
    "vmax_VADSL",
}

# Adenylate interconversion params — always kept because ATP/ADP/AMP coupling
# is the dominant energy-anchor lever even when no purine is measured.
_KEPT_ADENYLATE_ADDITIONS: Set[str] = {
    "vmax_VAK",
    "vmax_VAK_rev",
    "vmax_VAK2",
}


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CustomDataAssessment:
    """What the user actually measured, broken down by triage priority."""

    measured: List[str]
    priority_1_measured: List[str]
    priority_2_measured: List[str]
    priority_3_measured: List[str]
    priority_4_measured: List[str]
    unknown_metabolites: List[str]
    priority_1_coverage: float
    anchors_present: Dict[str, bool]
    extracellular_present: bool
    energy_core_present: bool
    profile_signal: str  # short human-readable summary
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CustomDataStageOutline:
    """A high-level description of the planned stages (shape-only, MM-free)."""

    name: str
    purpose: str
    target_scope: str
    targets: List[str]
    param_filter: Dict[str, List[str]]
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CustomDataPlan:
    """Dataset-aware plan consumed by the adapter."""

    assessment: CustomDataAssessment
    recommended_strategy: str
    target_scope: str
    atp_focus: bool
    parameter_additions: List[str]
    rejected_parameter_additions: Dict[str, str]
    dangerous_compensators_present: Dict[str, str]
    dangerous_compensators_guarded: List[str]
    weight_emphasis: Dict[str, float]
    stage_outline: List[CustomDataStageOutline]
    notes: List[str]
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["stage_outline"] = [stage.to_dict() for stage in self.stage_outline]
        payload["assessment"] = self.assessment.to_dict()
        return payload


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _normalize(names: Optional[Iterable[str]]) -> List[str]:
    """Normalise a metabolite-name list (uppercased, deduped)."""

    if not names:
        return []
    cleaned: List[str] = []
    seen: Set[str] = set()
    for name in names:
        if name is None:
            continue
        text = str(name).strip().upper()
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return cleaned


def _normalize_params(names: Optional[Iterable[str]]) -> List[str]:
    """Normalise a parameter-name list.

    Parameter names are case-sensitive (``vmax_VPEP_PASE``) and must not be
    uppercased; only whitespace and duplicates are removed.
    """

    if not names:
        return []
    cleaned: List[str] = []
    seen: Set[str] = set()
    for name in names:
        if name is None:
            continue
        text = str(name).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return cleaned


def _fraction_measured(measured: Iterable[str], tier: Set[str]) -> float:
    tier_size = len(tier)
    if tier_size == 0:
        return 0.0
    covered = sum(1 for name in measured if name in tier)
    return covered / tier_size


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------

def assess_custom_dataset(
    measured_metabolites: Optional[Sequence[str]],
) -> CustomDataAssessment:
    """Classify a user's measured metabolite list against triage tiers."""

    measured = _normalize(measured_metabolites)
    measured_set = set(measured)

    p1 = sorted(measured_set & PRIORITY_1_METABOLITES)
    p2 = sorted(measured_set & PRIORITY_2_METABOLITES)
    p3 = sorted(measured_set & PRIORITY_3_METABOLITES)
    p4 = sorted(measured_set & PRIORITY_4_METABOLITES)

    known = (
        PRIORITY_1_METABOLITES | PRIORITY_2_METABOLITES
        | PRIORITY_3_METABOLITES | PRIORITY_4_METABOLITES
    )
    unknown = sorted(name for name in measured_set if name not in known)

    anchors_present = {
        "energy": bool(measured_set & ENERGY_ANCHORS),
        "glucose_commitment": bool(measured_set & GLUCOSE_COMMITMENT_ANCHORS),
        "lactate_outlet": bool(measured_set & LACTATE_OUTLET_ANCHORS),
        "redox": bool(measured_set & REDOX_ANCHORS),
    }

    extracellular_present = bool(measured_set & EXTRACELLULAR_METABOLITES)
    energy_core_present = bool(measured_set & ENERGY_ANCHORS)

    warnings: List[str] = []
    if not measured:
        warnings.append(
            "No measured metabolites were provided; the plan will fall back to "
            "broad compatibility defaults and no triage is possible."
        )
    if unknown:
        warnings.append(
            "Some uploaded metabolite names are not recognised by the RBC model: "
            + ", ".join(unknown)
            + ". They will be ignored by the calibration."
        )
    if not p1 and (p2 or p3 or p4):
        warnings.append(
            "No Priority 1 anchor metabolites were measured. Any lower-priority "
            "improvement must be interpreted with care — the physiological "
            "anchors cannot be validated."
        )
    if p3 and not p1:
        warnings.append(
            "Purine metabolites are measured but the energy anchors (ATP / ADP / "
            "AMP) are not. Purine fits will not be promotable without a core "
            "energy dataset."
        )
    if p4 and not p1 and not p2:
        warnings.append(
            "Only side-metabolism targets are measured. CalibrationOps rules "
            "discourage promoting calibrations driven by Priority 4 curves."
        )

    if p1 and p2 and p3:
        profile_signal = "broad_core_and_purine"
    elif p1 and extracellular_present:
        profile_signal = "priority1_extracellular_anchor"
    elif p1 and energy_core_present:
        profile_signal = "priority1_energy_anchor"
    elif p1:
        profile_signal = "priority1_partial"
    elif p2:
        profile_signal = "glycolysis_only"
    elif p3:
        profile_signal = "purine_only"
    elif p4:
        profile_signal = "side_only"
    else:
        profile_signal = "empty"

    return CustomDataAssessment(
        measured=measured,
        priority_1_measured=p1,
        priority_2_measured=p2,
        priority_3_measured=p3,
        priority_4_measured=p4,
        unknown_metabolites=unknown,
        priority_1_coverage=round(_fraction_measured(measured, PRIORITY_1_METABOLITES), 3),
        anchors_present=anchors_present,
        extracellular_present=extracellular_present,
        energy_core_present=energy_core_present,
        profile_signal=profile_signal,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Target scope / strategy selection
# ---------------------------------------------------------------------------

_VALID_USER_STRATEGIES: Set[str] = {
    "legacy",
    "vmax_only",
    "km_only",
    "joint_vmax_km",
    "vmax_then_km",
    "km_then_vmax",
    "staged_full",
    "core_km_then_purine_transport",
}


def _recommend_scope_and_strategy(
    assessment: CustomDataAssessment,
    requested_strategy: Optional[str],
) -> Tuple[str, str, bool, str]:
    """Return ``(target_scope, optimization_strategy, atp_focus, rationale)``."""

    honour_user = (
        requested_strategy is not None
        and requested_strategy in _VALID_USER_STRATEGIES
    )

    if assessment.extracellular_present and assessment.priority_1_measured:
        scope = "glycolysis_extracellular"
        strategy = requested_strategy if honour_user else "vmax_then_km"
        atp_focus = assessment.energy_core_present
        rationale = (
            "Extracellular anchors are measured alongside Priority 1 metabolites, "
            "so we use the full glycolysis_extracellular objective bundle and "
            "stage Vmax before Km to stabilise transport + commitment before "
            "fine affinity tuning."
        )
        return scope, strategy, atp_focus, rationale

    if assessment.energy_core_present:
        scope = "core_glycolysis_energy"
        strategy = requested_strategy if honour_user else "vmax_then_km"
        atp_focus = True
        rationale = (
            "ATP / ADP / AMP are measured but no extracellular anchor is "
            "available, so we anchor on core_glycolysis_energy with ATP-aware "
            "penalties and a Vmax-first stage plan."
        )
        return scope, strategy, atp_focus, rationale

    if assessment.priority_3_measured and not assessment.priority_1_measured:
        scope = "core_glycolysis_energy"
        strategy = (
            requested_strategy if honour_user else "core_km_then_purine_transport"
        )
        atp_focus = False
        rationale = (
            "Only purine metabolites are measured. We still anchor on the "
            "core glycolysis/energy objective bundle (for guardrails) and use "
            "core_km_then_purine_transport so purine transport is only opened "
            "once the glycolysis core is locked."
        )
        return scope, strategy, atp_focus, rationale

    if assessment.priority_2_measured and not assessment.priority_1_measured:
        scope = "glycolysis"
        strategy = requested_strategy if honour_user else "vmax_then_km"
        atp_focus = False
        rationale = (
            "Internal glycolysis intermediates are measured without Priority 1 "
            "anchors, so we constrain calibration to the glycolysis scope with "
            "a Vmax-first pass."
        )
        return scope, strategy, atp_focus, rationale

    if assessment.priority_1_measured:
        scope = "glycolysis_extracellular"
        strategy = requested_strategy if honour_user else "vmax_then_km"
        atp_focus = assessment.energy_core_present
        rationale = (
            "Priority 1 anchors are present. We keep the default "
            "glycolysis_extracellular scope because it hosts the richest "
            "per-metabolite weight profile for energy and transport curves."
        )
        return scope, strategy, atp_focus, rationale

    # Fallback — nothing actionable measured.
    scope = "all"
    strategy = requested_strategy if honour_user else "vmax_then_km"
    rationale = (
        "No recognised Priority 1-4 metabolites are measured. Falling back to "
        "the broad compatibility scope with a Vmax-first pass, but the result "
        "must be interpreted cautiously."
    )
    return scope, strategy, False, rationale


# ---------------------------------------------------------------------------
# Parameter gating + weight emphasis
# ---------------------------------------------------------------------------

def _gate_parameter_additions(
    base_additions: Sequence[str],
    assessment: CustomDataAssessment,
) -> Tuple[List[str], Dict[str, str]]:
    """Filter the MM-recommended purine additions by measurement coverage."""

    kept: List[str] = []
    rejected: Dict[str, str] = {}
    has_purines = bool(assessment.priority_3_measured)

    for name in base_additions:
        if name in _PURINE_ADDITIONS_WITHOUT_PURINE_DATA and not has_purines:
            rejected[name] = (
                f"{name} targets purine turnover but no Priority 3 metabolite "
                "is measured. Removing it prevents silent compensatory fits."
            )
            continue
        if name in _KEPT_ADENYLATE_ADDITIONS and not assessment.energy_core_present:
            # Keep adenylate knobs only if ATP/ADP/AMP measured. Without any
            # energy anchor they just widen the search space.
            rejected[name] = (
                f"{name} is an adenylate interconversion lever but no ATP/ADP/AMP "
                "is measured, so it would only widen the search."
            )
            continue
        if name not in kept:
            kept.append(name)

    return kept, rejected


def _inspect_dangerous_compensators(
    selected_params: Sequence[str],
) -> Tuple[Dict[str, str], List[str]]:
    """Return ``(flagged, guarded_late)`` for the user's chosen parameters."""

    flagged: Dict[str, str] = {}
    guarded: List[str] = []
    for name in selected_params:
        reason = _dangerous_compensator_reason(name)
        if reason is None:
            continue
        flagged[name] = reason
        guarded.append(name)
    return flagged, guarded


def _compute_weight_emphasis(
    measured: Sequence[str],
    target_scope: str,
) -> Dict[str, float]:
    """Approximate the MM_calibration weight that each measured metabolite
    will receive under the chosen ``target_scope``.

    This is a *reporting* mirror of the weight rules that live in
    ``src/MM_calibration.py``. The adapter does not consume it directly — it
    is used by the UI to show the user why each metabolite matters more or
    less under the recommended plan.
    """

    # Mirror ``CRITICAL_WEIGHT_METABOLITES`` + ``HIGH_WEIGHT_METABOLITES`` plus
    # ``TARGET_SCOPE_WEIGHT_OVERRIDES[target_scope]``. Keep in sync whenever
    # those dicts change.
    critical = {
        "ATP": 30.0, "ADP": 30.0, "AMP": 20.0, "IMP": 15.0,
        "B23PG": 8.0, "GSH": 5.0, "GSSG": 5.0, "PEP": 5.0,
        "GLC": 3.0, "LAC": 3.0, "P2G": 3.0,
    }
    high = {"GLC": 2.0, "G6P": 2.0, "LAC": 2.0, "PYR": 2.0, "EGLC": 2.0, "ELAC": 2.0}
    scope_overrides: Dict[str, Dict[str, float]] = {
        "glycolysis_extracellular": {
            "EGLC": 14.0, "ELAC": 9.0, "GLC": 7.0, "G6P": 6.0,
            "ATP": 45.0, "ADP": 45.0, "AMP": 24.0, "IMP": 18.0,
            "LAC": 12.0, "F6P": 4.0, "F16BP": 4.0, "PYR": 12.0,
            "PEP": 10.0, "P2G": 4.0,
        },
        "core_glycolysis_energy": {
            "EGLC": 14.0, "ELAC": 9.0, "GLC": 7.0, "G6P": 6.0,
            "ATP": 45.0, "ADP": 45.0, "AMP": 24.0, "IMP": 18.0,
            "B23PG": 8.0, "LAC": 12.0, "F6P": 4.0, "F16BP": 4.0,
            "P3G": 4.0, "PYR": 12.0, "PEP": 10.0, "P2G": 4.0,
        },
        "glycolysis_energy": {
            "EGLC": 8.0, "ELAC": 8.0, "GLC": 6.0, "G6P": 6.0,
            "ATP": 30.0, "ADP": 30.0, "AMP": 20.0, "IMP": 15.0,
            "LAC": 5.0, "F6P": 4.0, "F16BP": 4.0, "PYR": 4.0,
            "PEP": 3.0, "P2G": 3.0,
        },
        "glycolysis_terminal": {
            "EGLC": 8.0, "ELAC": 8.0, "GLC": 4.0, "LAC": 4.0,
            "PYR": 3.0, "PEP": 3.0, "P2G": 3.0,
        },
    }

    emphasis: Dict[str, float] = {}
    overrides = scope_overrides.get(target_scope, {})
    for name in measured:
        weight = overrides.get(name)
        if weight is None:
            weight = critical.get(name) or high.get(name) or 1.0
        emphasis[name] = float(weight)
    return emphasis


# ---------------------------------------------------------------------------
# Stage outline (shape-only; does not bypass the adapter's stage builder)
# ---------------------------------------------------------------------------

def _build_stage_outline(
    assessment: CustomDataAssessment,
    target_scope: str,
    strategy: str,
) -> List[CustomDataStageOutline]:
    """Build a human-readable outline of the staged calibration.

    The MM-compatible stage list is still produced by the adapter's
    existing ``_build_strategy_stage_plan`` helper. This outline is what the
    UI/API surfaces to the user so they can see which tiers will be touched
    and in what order.
    """

    outline: List[CustomDataStageOutline] = []

    if assessment.priority_1_measured:
        outline.append(
            CustomDataStageOutline(
                name="anchor_priority_1",
                purpose=(
                    "Stabilise Priority 1 physiological anchors — energy core, "
                    "glucose commitment, lactate outlet, redox."
                ),
                target_scope=target_scope,
                targets=list(assessment.priority_1_measured),
                param_filter={
                    "classes": ["vmax", "km"],
                    "identifiability": ["core"],
                },
                notes=[
                    "Keep VPEP_PASE and secondary VE* exports closed in this stage.",
                ],
            )
        )

    if assessment.priority_2_measured:
        outline.append(
            CustomDataStageOutline(
                name="glycolysis_priority_2",
                purpose=(
                    "Refine internal glycolysis intermediates once Priority 1 "
                    "behaviour is credible."
                ),
                target_scope=target_scope,
                targets=list(assessment.priority_2_measured),
                param_filter={
                    "classes": ["vmax", "km"],
                    "identifiability": ["core", "caution"],
                },
                notes=[
                    "Expect VPFK, VFDPA, VENOPGM, VPK to dominate this stage.",
                ],
            )
        )

    if assessment.priority_3_measured:
        outline.append(
            CustomDataStageOutline(
                name="purine_priority_3",
                purpose=(
                    "Open purine salvage / degradation only after the energy core "
                    "is protected."
                ),
                target_scope=target_scope,
                targets=list(assessment.priority_3_measured),
                param_filter={
                    "classes": ["vmax", "km"],
                    "identifiability": ["core", "caution"],
                },
                notes=[
                    "Purine transport compensators (VEXAN, VEURT, VEINO, VEADE) "
                    "must remain in the late/guarded list.",
                ],
            )
        )

    if assessment.priority_4_measured:
        outline.append(
            CustomDataStageOutline(
                name="side_priority_4",
                purpose=(
                    "Interpret side-metabolism curves qualitatively. This stage "
                    "is diagnostic only and cannot drive promotion."
                ),
                target_scope=target_scope,
                targets=list(assessment.priority_4_measured),
                param_filter={
                    "classes": ["vmax", "km"],
                    "identifiability": ["caution", "structural_compensation_risk"],
                },
                notes=[
                    "Any improvement must be checked against Priority 1 anchors "
                    "before acceptance.",
                ],
            )
        )

    if not outline:
        outline.append(
            CustomDataStageOutline(
                name="fallback_broad",
                purpose=(
                    "No recognised priority-tier metabolites were measured. "
                    "Running a single broad-compatibility pass for diagnostic "
                    "purposes only."
                ),
                target_scope=target_scope,
                targets=list(assessment.measured),
                param_filter={"classes": ["vmax", "km"], "identifiability": ["core"]},
                notes=[
                    "Do not promote anything produced by this stage without a "
                    "supplementary Priority 1 dataset.",
                ],
            )
        )

    # Annotate the overall strategy choice at the top of the first stage.
    if outline:
        outline[0].notes.insert(0, f"Optimization strategy: {strategy}.")

    return outline


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

_MM_INFERRED_PURINE_ADDITIONS: Tuple[str, ...] = (
    "vmax_VAK",
    "vmax_VAK_rev",
    "vmax_VAK2",
    "vmax_VAMPD1",
    "vmax_VAPRT",
    "vmax_VADSL",
)


def build_custom_data_plan(
    *,
    measured_metabolites: Optional[Sequence[str]],
    selected_params: Optional[Sequence[str]] = None,
    requested_strategy: Optional[str] = None,
    mm_inferred_additions: Optional[Sequence[str]] = None,
) -> CustomDataPlan:
    """Build a dataset-aware calibration plan for the adapter to consume.

    Parameters
    ----------
    measured_metabolites:
        Names of the metabolites actually present in the user's dataset.
    selected_params:
        Parameters the user asked to optimise. Used for dangerous-compensator
        detection; the plan never silently removes user-selected params, it
        only flags them.
    requested_strategy:
        Optional optimization strategy the user explicitly asked for. If it is
        valid we honour it; otherwise the planner recommends a default.
    mm_inferred_additions:
        Optional override of the purine-style additions that
        ``infer_custom_data_calibration_profile`` would normally inject. Defaults
        to the canonical six-term list used by MM today.
    """

    assessment = assess_custom_dataset(measured_metabolites)
    selected = _normalize_params(selected_params)
    base_additions = list(
        mm_inferred_additions
        if mm_inferred_additions is not None
        else _MM_INFERRED_PURINE_ADDITIONS
    )

    target_scope, strategy, atp_focus, rationale = _recommend_scope_and_strategy(
        assessment, requested_strategy
    )

    kept_additions, rejected_additions = _gate_parameter_additions(
        base_additions, assessment
    )

    dangerous_compensators, guarded = _inspect_dangerous_compensators(selected)

    weight_emphasis = _compute_weight_emphasis(assessment.measured, target_scope)
    stage_outline = _build_stage_outline(assessment, target_scope, strategy)

    notes: List[str] = []
    notes.extend(assessment.warnings)
    if rejected_additions:
        notes.append(
            "Some MM auto-added parameters were dropped because the dataset "
            "does not support them: "
            + ", ".join(sorted(rejected_additions.keys()))
            + "."
        )
    if dangerous_compensators:
        notes.append(
            "Dangerous compensator parameters were selected by the user: "
            + ", ".join(sorted(dangerous_compensators.keys()))
            + ". They are still included, but triage will flag any run where "
            "they dominate the fit."
        )
    if requested_strategy and requested_strategy not in _VALID_USER_STRATEGIES:
        notes.append(
            f"Requested strategy '{requested_strategy}' is not a supported "
            f"optimization strategy. Recommended strategy '{strategy}' is "
            "used instead."
        )

    return CustomDataPlan(
        assessment=assessment,
        recommended_strategy=strategy,
        target_scope=target_scope,
        atp_focus=bool(atp_focus),
        parameter_additions=kept_additions,
        rejected_parameter_additions=rejected_additions,
        dangerous_compensators_present=dangerous_compensators,
        dangerous_compensators_guarded=guarded,
        weight_emphasis=weight_emphasis,
        stage_outline=stage_outline,
        notes=notes,
        rationale=rationale,
    )


__all__ = [
    "PRIORITY_1_METABOLITES",
    "PRIORITY_2_METABOLITES",
    "PRIORITY_3_METABOLITES",
    "PRIORITY_4_METABOLITES",
    "ENERGY_ANCHORS",
    "GLUCOSE_COMMITMENT_ANCHORS",
    "LACTATE_OUTLET_ANCHORS",
    "REDOX_ANCHORS",
    "EXTRACELLULAR_METABOLITES",
    "CustomDataAssessment",
    "CustomDataStageOutline",
    "CustomDataPlan",
    "assess_custom_dataset",
    "build_custom_data_plan",
]
