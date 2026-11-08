"""Bounded Vmax search only: no model, data, or filesystem access on import/run."""

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
import math
from numbers import Integral, Real
import re

import numpy as np
from scipy.optimize import minimize
from scipy.stats import qmc


_PAIRS = (("vmax_VAK", "vmax_VAK_rev"), ("vmax_VNDPK", "vmax_VNDPK_rev"))
_SCORES = ("adenylate_loss", "other_loss", "max_guard_excess")
_GATES = ("valid", "scores_valid", "guard_pass", "feasible", "failure")


def _finite(value):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        return None
    try:
        value = float(value)
    except OverflowError:
        return None
    return value if math.isfinite(value) else None


def _vector(values, size, label):
    if isinstance(values, (str, bytes, Mapping)):
        raise ValueError(f"{label} must be a numeric vector")
    try:
        vector = tuple(_finite(value) for value in values)
    except TypeError as exc:
        raise ValueError(f"{label} must be a numeric vector") from exc
    if len(vector) != size or any(value is None for value in vector):
        raise ValueError(f"{label} must have {size} finite numeric entries")
    return vector


def _factor(log_factor):
    try:
        factor = math.exp(log_factor)
    except OverflowError as exc:
        raise ValueError("log factor must exponentiate to a finite positive factor") from exc
    if factor == 0:
        raise ValueError("log factor must exponentiate to a finite positive factor")
    return factor


def _names(mapping, label):
    if not isinstance(mapping, Mapping) or not mapping:
        raise ValueError(f"{label} must be a nonempty ordered mapping")
    names = tuple(mapping)
    if any(not isinstance(name, str) or not name.strip() for name in names):
        raise ValueError(f"{label} names must be nonempty strings")
    return names


def inject_vmax_only(
    base_parameters: Mapping, groups: Mapping[str, Sequence[str]], log_factors: Sequence[float]
) -> dict:
    """Return a new parameter dict, scaling only explicit named AIRBC capacities.

    Group iteration order defines the vector order. Selected keys must already
    exist in the resolved base and follow the AIRBC ``vmax_`` convention. AK and
    NDPK pairs must be selected together in one group or left entirely alone.
    No defaults are inserted. Unselected entries and exact zero capacities are
    copied unchanged. Bounds/absolute capacity caps are registered by the caller.
    """
    names = _names(groups, "groups")
    factors = tuple(map(_factor, _vector(log_factors, len(names), "log_factors")))
    if not isinstance(base_parameters, Mapping):
        raise ValueError("base_parameters must be a mapping of resolved parameters")
    owners, updates = {}, {}
    for group, factor in zip(names, factors):
        members = groups[group]
        if isinstance(members, (str, bytes)) or not isinstance(members, Sequence) or not members:
            raise ValueError(f"group {group!r} must name at least one capacity in a sequence")
        for key in members:
            if not isinstance(key, str) or re.fullmatch(r"vmax_[A-Za-z][A-Za-z0-9_]*", key) is None:
                raise ValueError(f"not an AIRBC Vmax key: {key!r}")
            if key in owners:
                raise ValueError(f"Vmax key is listed more than once: {key}")
            if key not in base_parameters:
                raise ValueError(f"unresolved base Vmax: {key}")
            original = base_parameters[key]
            value = _finite(original)
            if value is None or value < 0:
                raise ValueError(f"invalid base Vmax: {key}")
            owners[key] = group
            if value != 0 and factor != 1:
                scaled = value * factor
                if not math.isfinite(scaled) or scaled <= 0:
                    raise ValueError(f"scaling would overflow or close a positive Vmax: {key}")
                updates[key] = scaled
    for forward, reverse in _PAIRS:
        if owners.get(forward) != owners.get(reverse):
            raise ValueError(f"{forward} and {reverse} must be in the same group")
    return {**base_parameters, **updates}


def _json_safe(value, depth=0):
    # Retain non-finite diagnostic evidence without emitting nonstandard JSON.
    if depth >= 40:
        return {"truncated": "diagnostic nesting limit"}
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        if (finite := _finite(value)) is not None:
            return finite
        return "nan" if value != value else ("inf" if value > 0 else "-inf")
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item, depth + 1) for key, item in value.items()}
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist(), depth + 1)
    if isinstance(value, (list, tuple)):
        return [_json_safe(item, depth + 1) for item in value]
    return {"unsupported_type": type(value).__name__}


def _score(evaluate, vector):
    result, error = None, None
    valid = False
    scores = dict.fromkeys(_SCORES)
    try:
        raw = evaluate(vector)
        result = _json_safe(raw)
        if not isinstance(raw, Mapping):
            error = {"kind": "invalid_return", "message": "expected a score mapping"}
        else:
            flag = raw.get("valid")
            valid = isinstance(flag, (bool, np.bool_)) and bool(flag)
            scores = {name: _finite(raw.get(name)) for name in _SCORES}
            if not isinstance(flag, (bool, np.bool_)):
                error = {"kind": "invalid_return", "message": "valid must be a boolean"}
            elif not valid:
                error = {"kind": "invalid_evaluation", "message": "callback reported valid=False"}
            elif any(value is None for value in scores.values()):
                missing = [name for name, value in scores.items() if value is None]
                error = {"kind": "invalid_scores", "message": f"missing/nonfinite scores: {', '.join(missing)}"}
    except Exception as exc:
        error = {"kind": "exception", "type": type(exc).__name__, "message": str(exc)}
    guard = scores["max_guard_excess"]
    guard_pass = guard is not None and guard <= 0
    return {
        **scores, "valid": valid, "scores_valid": all(v is not None for v in scores.values()),
        "guard_pass": guard_pass, "feasible": error is None and guard_pass,
        "failure": error, "callback_result": result,
    }


def _rank(row, primary="adenylate_loss"):
    secondary = "other_loss" if primary == "adenylate_loss" else "adenylate_loss"
    if row["feasible"]:
        return (0, row[primary], row[secondary], row["evaluation_id"])
    return (1, row["max_guard_excess"], row[primary], row[secondary], row["evaluation_id"])


def _merit(row, primary, guard_aware):
    # Disjoint bands guide SciPy without trading guard violations against losses.
    if row["failure"] is not None:
        return 4.0
    if row["feasible"] or not guard_aware:
        return math.atan(row[primary]) / math.pi + 0.5
    return 2.0 + math.atan(row["max_guard_excess"]) / math.pi


def _pareto(ranked):
    # Already sorted by adenylates, then other loss. Preserve exact objective ties.
    front = []
    best_other, best_adenylate = math.inf, math.inf
    for row in ranked:
        adenylate, other = row["adenylate_loss"], row["other_loss"]
        if other < best_other or (other == best_other and adenylate == best_adenylate):
            front.append(row)
            best_other, best_adenylate = other, adenylate
    return front


def search_vmax(
    evaluate: Callable[[tuple[float, ...]], Mapping],
    bounds: Mapping[str, Sequence[float]],
    *,
    budget: int,
    seed: int = 0,
    starts: Sequence[Sequence[float]] = (),
    explore_infeasible: bool = False,
    on_probe: Callable[[dict], None] | None = None,
) -> dict:
    """Search natural-log factor bounds in mapping order; equal bounds fix a group.

    ``evaluate(vector)`` must be deterministic in one frozen context. One call
    must represent one actual free-ODE attempt (including failed attempts; no
    internal caching, retries, or batches if budgeting integrations). Its mapping
    must include boolean ``valid`` and finite ``adenylate_loss``, ``other_loss``,
    and ``max_guard_excess`` to qualify for ranking. The guard must be <= 0 to be
    feasible. All losses are minimized. Extra diagnostics should be JSON/NumPy
    data; nonfinite numbers are recorded as strings in ``callback_result``.

    ``starts`` are optional log vectors probed after the clipped zero vector.
    With ``explore_infeasible=True`` and room for two local simplexes, reserve
    one refinement for adenylate loss alone, seeded by the best scoreable
    adenylate result regardless of guard. Retain guard-aware refinement and
    prefer a violating start for guard restoration when one exists. Reporting
    applies identical hard gates to all stages, including this exploration.

    ``on_probe(row)`` receives an independent JSON-safe row after every probe,
    including cache hits (linked by evaluation_id). Hook exceptions propagate.
    The caller can append rows as checkpoints; this does not resume optimizer state.

    Budget caps callback invocations, not optimizer probes. The search tries to
    spend the budget unless the box/design runs out of distinct points. Returned
    rankings include only actual, scoreable evaluations, never interpolations.
    """
    names = _names(bounds, "bounds")
    limits = tuple(_vector(bounds[name], 2, f"bounds for {name}") for name in names)
    if any(lo > hi for lo, hi in limits):
        raise ValueError("lower log bounds must not exceed upper log bounds")
    for lo, hi in limits:
        _factor(lo)
        _factor(hi)
    if isinstance(budget, bool) or not isinstance(budget, Integral) or budget < 1:
        raise ValueError("budget must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, Integral) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if not isinstance(explore_infeasible, bool):
        raise ValueError("explore_infeasible must be a boolean")
    if not callable(evaluate) or (on_probe is not None and not callable(on_probe)):
        raise ValueError("evaluate and any on_probe hook must be callable")
    budget, seed = int(budget), int(seed)
    supplied = tuple(_vector(start, len(names), "start") for start in starts)
    if any(not all(lo <= v <= hi for v, (lo, hi) in zip(x, limits)) for x in supplied):
        raise ValueError("all starts must be inside the log bounds")
    lower, upper = np.asarray(limits).T
    anchor = tuple(map(float, np.clip(0.0, lower, upper)))
    if len(set((anchor, *supplied))) > budget:
        raise ValueError("budget is smaller than the number of distinct required starts")
    active = lower < upper
    dimension = int(active.sum())
    lo, hi = lower[active], upper[active]
    width = hi - lo
    trace, evaluations, cache, refinements = [], [], {}, []
    cache_hits = 0

    def probe(vector, stage):
        nonlocal cache_hits
        if vector in cache:
            cache_hits += 1
            source = "cache"
            observed = cache[vector]
        else:
            if len(evaluations) >= budget:
                raise RuntimeError("internal search error: evaluation budget exceeded")
            source = "evaluation"
            observed = _score(evaluate, vector)
        row = {
            "probe_id": len(trace) + 1, "stage": stage, "source": source,
            "evaluation_id": len(evaluations) + 1 if source == "evaluation" else observed["evaluation_id"],
            "log_factors": list(vector), **{key: observed[key] for key in (*_SCORES, *_GATES)},
        }
        if source == "evaluation":
            row["callback_result"] = observed["callback_result"]
            evaluations.append(row)
            cache[vector] = row
        trace.append(row)
        if on_probe is not None:
            on_probe(deepcopy(row))
        return row

    def encode(vector):
        return (np.asarray(vector)[active] - lo) / width

    def decode(unit):
        vector = lower.copy()
        vector[active] = np.clip(lo + unit * width, lo, hi)
        return tuple(map(float, vector))

    probe(anchor, "anchor")
    for vector in supplied:
        probe(vector, "supplied_start")
    if dimension and len(evaluations) < budget:
        sampler = qmc.LatinHypercube(dimension, seed=seed)
        explore = max(0, budget // 3 - len(evaluations))
        near = explore // 3
        center = encode(anchor)
        near_lo, near_hi = np.maximum(0, center - 0.2), np.minimum(1, center + 0.2)
        for unit in sampler.random(explore - near):
            probe(decode(unit), "global_exploration")
        for unit in sampler.random(near):
            probe(decode(near_lo + unit * (near_hi - near_lo)), "near_anchor_exploration")

        remaining = budget - len(evaluations)
        viable = [row for row in evaluations if row["failure"] is None]
        slots = min(3, max(1, remaining // (2 * (dimension + 1))))
        guarded = ("adenylate_loss", 0.04, "guarded")
        modes = (guarded, ("other_loss", 0.08, "guarded"), ("adenylate_loss", 0.12, "guarded"))
        exploratory = explore_infeasible and bool(viable) and remaining >= 2 * (dimension + 1)
        if exploratory:
            unconstrained = ("adenylate_loss", 0.12, "adenylate_only")
            restoration = ("other_loss", 0.08, "guard_restoration")
            modes = (guarded, unconstrained, restoration) if slots == 3 else (restoration, unconstrained)
        else:
            modes = modes[:min(slots, len(viable))]
        used = set()
        for index, (primary, step, policy) in enumerate(modes):
            quota = (budget - len(evaluations)) // (len(modes) - index)
            if quota < dimension + 1:
                break
            if exploratory:
                viable = [row for row in evaluations if row["failure"] is None]
            if policy == "adenylate_only":
                start = min(viable, key=lambda row: (row["adenylate_loss"], row["other_loss"], row["evaluation_id"]))
            else:
                violating = [row for row in viable if not row["feasible"]] if policy == "guard_restoration" else []
                if not violating:
                    policy = "guarded"
                unused = [row for row in viable if row["evaluation_id"] not in used]
                start = min(violating or unused or viable, key=lambda row: _rank(row, primary))
            used.add(start["evaluation_id"])
            vector = tuple(start["log_factors"])
            unit = encode(vector)
            simplex = np.tile(unit, (dimension + 1, 1))
            axis = np.arange(dimension)
            simplex[axis + 1, axis] += np.where(unit <= 0.5, step, -step)
            stage = f"refinement_{index + 1}"
            first_probe, first_evaluation = len(trace), len(evaluations)

            def objective(point):
                # Preserve the exact seed cache key across the affine roundtrip.
                log_vector = vector if np.array_equal(point, unit) else decode(point)
                return _merit(probe(log_vector, stage), primary, policy != "adenylate_only")

            outcome = minimize(
                objective, unit, method="Nelder-Mead", bounds=[(0.0, 1.0)] * dimension,
                options={"initial_simplex": simplex, "adaptive": dimension > 1,
                         "maxfev": quota, "xatol": 1e-3, "fatol": 1e-8},
            )
            refinements.append({
                "stage": stage, "primary": primary, "policy": policy, "start_evaluation_id": start["evaluation_id"],
                "start_log_factors": list(vector), "probes": len(trace) - first_probe,
                "actual_evaluations": len(evaluations) - first_evaluation,
                "optimizer_success": bool(outcome.success), "optimizer_message": str(outcome.message),
            })

        # Use real budget left over from cache hits, local convergence or invalid starts.
        if len(evaluations) < budget:
            for unit in sampler.random(budget):
                probe(decode(unit), "fill_exploration")
                if len(evaluations) == budget:
                    break

    feasible = sorted((row for row in evaluations if row["feasible"]), key=_rank)
    infeasible = sorted((row for row in evaluations if not row["feasible"] and row["failure"] is None), key=_rank)
    return {
        "group_order": list(names), "log_bounds": [list(pair) for pair in limits], "seed": seed,
        "explore_infeasible": explore_infeasible,
        "budget": budget, "actual_evaluations": len(evaluations), "probes": len(trace), "cache_hits": cache_hits,
        "stop_reason": "budget_exhausted" if len(evaluations) == budget else
                       ("fixed_box" if not dimension else "design_exhausted"),
        "gate_policy": {"valid": True, "finite_scores": list(_SCORES), "max_guard_excess_lte": 0.0},
        "failed_evaluations": sum(row["failure"] is not None for row in evaluations),
        "trace": trace, "refinements": refinements, "ranked_feasible": feasible, "ranked_infeasible": infeasible,
        "best_feasible": feasible[0] if feasible else None, "pareto_feasible": _pareto(feasible),
    }
