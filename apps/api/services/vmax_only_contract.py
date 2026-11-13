"""Strict Vmax-only (fixed Km) contract for web calibration requests.

Separate validation layer: it does not import the calibration core, the ODE
or any solver, and it does not modify ``MM_calibration``. The adapter calls it
before and after the core so that no strategy alias, strategy memory,
auto-scope expansion or profile addition can reopen Km, regulation or hybrid
parameters once a fixed-Km calibration was requested.

The historical path stays available and is identified explicitly as
``legacy_unconstrained``; nothing here changes its behaviour.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

FIXED_KM_CONTRACT = "vmax_only_fixed_km"
LEGACY_CONTRACT = "legacy_unconstrained"
FIXED_KM_STRATEGY = "vmax_only"

_FIXED_ALIASES = {FIXED_KM_CONTRACT, FIXED_KM_STRATEGY}
_LEGACY_ALIASES = {LEGACY_CONTRACT, "legacy"}
_STRATEGY_FIELDS = ("optimization_strategy", "method")
# Classes that a fixed-Km calibration must never optimise, even for a name
# that also carries the vmax class.
_FORBIDDEN_CLASSES = frozenset({"km", "regulation", "hybrid"})
_FORBIDDEN_PREFIXES = ("km_", "ki_", "ka_", "alpha_", "n_", "hybrid_")

Classifier = Optional[Callable[[str], Iterable[str]]]


class StrategyConflict(ValueError):
    """The request names incompatible strategies or an unknown contract."""


class FixedKmViolation(ValueError):
    """A fixed-Km request would optimise, or did change, a non-Vmax parameter."""


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def resolve_parameter_contract(request: Any) -> Dict[str, Any]:
    """Decide which parameter contract a request asks for, or refuse it.

    Fixed Km is requested by ``parameter_contract`` or by naming ``vmax_only``
    in either strategy field. Any other strategy named next to it, or an
    explicit legacy contract next to it, is a conflict and is refused rather
    than resolved by precedence.
    """
    contract = _norm(getattr(request, "parameter_contract", None))
    if contract and contract not in _FIXED_ALIASES | _LEGACY_ALIASES:
        raise StrategyConflict(f"Unknown parameter_contract {contract!r}.")
    named = {field: _norm(getattr(request, field, None)) for field in _STRATEGY_FIELDS}
    named = {field: value for field, value in named.items() if value}
    by_contract = contract in _FIXED_ALIASES
    by_strategy = sorted(field for field, value in named.items() if value == FIXED_KM_STRATEGY)
    if not by_contract and not by_strategy:
        return {"contract": LEGACY_CONTRACT, "fixed_km": False, "requested_by": [], "strategy": None}
    if contract in _LEGACY_ALIASES:
        raise StrategyConflict(
            "parameter_contract is legacy but a strategy field requests vmax_only; "
            "state one contract."
        )
    others = {field: value for field, value in named.items() if value != FIXED_KM_STRATEGY}
    if others:
        listed = ", ".join(f"{field}={value}" for field, value in sorted(others.items()))
        raise StrategyConflict(
            f"Fixed-Km (vmax_only) calibration conflicts with {listed}; "
            "remove the other strategy or do not request fixed Km."
        )
    requested_by = (["parameter_contract"] if by_contract else []) + by_strategy
    return {"contract": FIXED_KM_CONTRACT, "fixed_km": True, "requested_by": requested_by, "strategy": FIXED_KM_STRATEGY}


def is_vmax_only_parameter(name: Any, classify: Classifier = None) -> bool:
    """True only for a Vmax parameter that carries no Km, regulation or hybrid class."""
    text = str(name or "").strip()
    if not text.startswith("vmax_") or text.startswith(_FORBIDDEN_PREFIXES):
        return False
    if classify is None:
        return True
    classes = {str(item) for item in classify(text)}
    return "vmax" in classes and not (classes & _FORBIDDEN_CLASSES)


def partition_parameters(names: Iterable[Any], classify: Classifier = None) -> Tuple[List[str], List[str]]:
    """Split names into (allowed under fixed Km, refused), order preserved, duplicates dropped."""
    allowed: List[str] = []
    refused: List[str] = []
    for raw in names or []:
        name = str(raw).strip()
        if not name or name in allowed or name in refused:
            continue
        (allowed if is_vmax_only_parameter(name, classify) else refused).append(name)
    return allowed, refused


def require_vmax_only_selection(names: Iterable[Any], classify: Classifier = None, *, origin: str) -> List[str]:
    """Caller-selected parameters: any non-Vmax name is a refusal, never a silent drop."""
    allowed, refused = partition_parameters(names, classify)
    if refused:
        raise FixedKmViolation(
            f"Fixed-Km calibration refuses non-Vmax parameters from {origin}: " + ", ".join(sorted(refused))
        )
    return allowed


def filter_derived_parameters(names: Iterable[Any], classify: Classifier = None) -> Tuple[List[str], List[str]]:
    """Derived parameters (auto-scope, profile or planner additions): keep Vmax, report the rest."""
    return partition_parameters(names, classify)


def assert_stage_plan_vmax_only(stage_plan: Iterable[Mapping[str, Any]], classify: Classifier = None) -> None:
    """Last check before the core runs: every stage optimises Vmax parameters only."""
    stages = list(stage_plan or [])
    if not stages:
        raise FixedKmViolation("Fixed-Km calibration has no stage to run.")
    for stage in stages:
        label = str(stage.get("name", "?"))
        included = [str(name) for name in (stage.get("include_params") or [])]
        if not included:
            raise FixedKmViolation(f"Stage {label} has no explicit parameter list under fixed Km.")
        _, refused = partition_parameters(included, classify)
        if refused:
            raise FixedKmViolation(f"Stage {label} would optimise non-Vmax parameters: " + ", ".join(sorted(refused)))
        classes = {str(item) for item in (stage.get("parameter_classes") or [])}
        if classes - {"vmax"}:
            raise FixedKmViolation(f"Stage {label} opens parameter classes {sorted(classes - {'vmax'})}.")


def audit_fixed_parameters(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    optimized: Iterable[Any],
    classify: Classifier = None,
) -> Dict[str, Any]:
    """Compare parameters before and after a fixed-Km run. Exact equality, no tolerance.

    Every parameter outside ``optimized`` must be unchanged; non-Vmax changes
    break the contract, and Vmax changes outside the optimised set are
    reported separately. A parameter without a reference value cannot be
    verified and is listed, not assumed unchanged.
    """
    selected = {str(name) for name in optimized or []}
    changed_non_vmax: Dict[str, List[float]] = {}
    changed_unselected_vmax: Dict[str, List[float]] = {}
    missing: List[str] = []
    checked = 0
    for name in sorted(str(key) for key in after):
        if name in selected:
            continue
        if not isinstance(after[name], (int, float)) or isinstance(after[name], bool):
            continue
        if name not in before:
            missing.append(name)
            continue
        checked += 1
        old, new = float(before[name]), float(after[name])
        if old == new:
            continue
        target = changed_unselected_vmax if is_vmax_only_parameter(name, classify) else changed_non_vmax
        target[name] = [old, new]
    refused_selected = partition_parameters(selected, classify)[1]
    verified = not changed_non_vmax and not changed_unselected_vmax and not refused_selected and not missing
    return {
        "verified": bool(verified),
        "checked": checked,
        "changed_non_vmax": changed_non_vmax,
        "changed_unselected_vmax": changed_unselected_vmax,
        "non_vmax_in_optimized_set": sorted(refused_selected),
        "without_reference": missing,
    }


def fixed_km_request(request: Any) -> Any:
    """Copy of a fixed-Km request with both strategy fields set and strategy memory off.

    The caller's request object is not modified.
    """
    updates = {
        "optimization_strategy": FIXED_KM_STRATEGY,
        "method": FIXED_KM_STRATEGY,
        "parameter_contract": FIXED_KM_CONTRACT,
        "enable_strategy_memory": False,
    }
    if hasattr(request, "model_copy"):
        return request.model_copy(update=updates)
    cloned = deepcopy(request)
    for key, value in updates.items():
        setattr(cloned, key, value)
    return cloned
