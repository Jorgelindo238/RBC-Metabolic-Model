"""Opt-in successor engine for user calibration data: prepare, validate, run.

Scope of this first version (2026-11-12):

* absolute concentrations in mM only; relative channels are refused;
* a complete initial state declared by the caller, pool by pool, with a
  status (``measured`` or ``latent_declared``) and a source for each pool;
* measured initial values locked to the first observation, bit for bit;
* time origin at the first sample: nothing is computed before it and only
  measured dates after it are scored;
* declared hematocrit passed to the existing phase-aware RHS, so intra- and
  extracellular pools keep distinct volumes;
* one dataset and one donor or declared group per run;
* parameters fixed: no search, no Vmax change, no Km change.

Nothing is loaded implicitly: no reference workbook, no frozen centre, no
default parameter vector, no default solver. The RHS factory and the solver
are explicit arguments of :func:`run`. :func:`default_rhs_factory` and
:func:`default_solver` exist for callers that choose them; they reuse the
existing ``GemCorrectionRHS`` (phase matrix, ``reaction_consistent`` limiter,
clamped pH) without copying the network and without any global patch.

The engine is NOT qualified. ``QUALIFICATION_STATUS`` stays ``not_qualified``
until an independent replay shows that it reproduces a sealed trajectory.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np

ENGINE_VERSION = "fla-user-engine-2026.11.12-v1"
QUALIFICATION_STATUS = "not_qualified"
SCHEMA_VERSION = "airbc.user_calibration_data/1"
PH_STATE = "PHI"
COMPARTMENTS = ("intracellular", "extracellular")
ENTRY_STATUSES = ("measured", "latent_declared")
BACKENDS = ("joint", "full")
_FORBIDDEN_REQUEST_KEYS = ("search", "optimize", "optimization", "params_to_optimize", "t_max", "t_start",
                           "initial_state_override", "teacher", "teacher_forcing")


class EngineContractError(ValueError):
    """The submitted data or engine request is outside the engine's contract."""

    def __init__(self, issues: List[Dict[str, str]]):
        self.issues = issues
        super().__init__("; ".join(f"{i['code']} at {i['path']}" for i in issues))


def _issue(code: str, path: str, message: str) -> Dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PreparedRun:
    identity: Dict[str, str]
    pool_names: Tuple[str, ...]
    compartments: Dict[str, str]
    initial_state: Tuple[float, ...]
    provenance: Dict[str, Dict[str, str]]
    measured_locked: Dict[str, float]
    sample_times: Tuple[float, ...]
    observations: Tuple[Dict[str, Any], ...]
    hematocrit: float
    geometry_provenance: Dict[str, str]
    parameters: Dict[str, Any]
    parameters_source: str
    parameters_sha256: str
    kinetics: Dict[str, Any]
    network_mode: str
    backend: str
    threshold_mM: float
    negative_tolerance_mM: float
    solver_settings: Dict[str, Any]
    fingerprint: str
    engine_version: str = ENGINE_VERSION
    flags: Dict[str, Any] = field(default_factory=lambda: {
        "parameter_search": False, "teacher_forcing": False, "relative_channels": False,
        "donors_merged": False, "implicit_reference_loading": False, "qualification": QUALIFICATION_STATUS})

    @property
    def t0(self) -> float:
        return self.sample_times[0]


def _identity(contract: Mapping[str, Any], issues: List[dict]) -> Dict[str, str]:
    dataset = _mapping(contract.get("dataset"))
    if "subjects" in dataset or "donors" in dataset:
        issues.append(_issue("multiple_subjects_in_one_run", "dataset", "One run is one donor or one declared group."))
    subject = _mapping(dataset.get("subject"))
    identity = {"dataset_id": _text(dataset.get("dataset_id")), "cohort_id": _text(dataset.get("cohort_id")),
                "subject_kind": _text(subject.get("kind")), "subject_id": _text(subject.get("id"))}
    if identity["subject_kind"] not in ("donor", "declared_group"):
        issues.append(_issue("subject_kind_invalid", "dataset.subject.kind", "donor or declared_group required."))
    for key, value in identity.items():
        if not value:
            issues.append(_issue("identity_missing", f"dataset.{key}", f"{key} is required."))
    return identity


def _times(contract: Mapping[str, Any], issues: List[dict]) -> List[float]:
    time = _mapping(contract.get("time"))
    if _text(time.get("unit")) != "day":
        issues.append(_issue("time_unit_invalid", "time.unit", "Days only; no conversion is performed."))
    if not _text(_mapping(time.get("origin")).get("kind")):
        issues.append(_issue("time_origin_missing", "time.origin.kind", "Time origin is required."))
    points = time.get("points")
    if not isinstance(points, list) or len(points) < 2 or not all(_number(v) for v in points):
        issues.append(_issue("time_points_invalid", "time.points", "At least two finite time points are required."))
        return []
    values = [float(v) for v in points]
    if any(b <= a for a, b in zip(values, values[1:])):
        issues.append(_issue("time_points_not_increasing", "time.points", "Strictly increasing times are required."))
        return []
    return values


def _geometry(contract: Mapping[str, Any], issues: List[dict]) -> Tuple[float, Dict[str, str]]:
    geometry = _mapping(contract.get("geometry"))
    h = geometry.get("hematocrit")
    provenance = {"kind": _text(_mapping(geometry.get("provenance")).get("kind")),
                  "source": _text(_mapping(geometry.get("provenance")).get("source"))}
    if not (_number(h) and 0.0 < float(h) < 1.0):
        issues.append(_issue("hematocrit_invalid", "geometry.hematocrit", "A fraction strictly between 0 and 1 is required."))
        h = float("nan")
    if not provenance["kind"] or not provenance["source"]:
        issues.append(_issue("geometry_provenance_missing", "geometry.provenance", "Kind and source are required."))
    return float(h), provenance


def _initial_state(contract, pool_names, compartments, times, issues):
    initial = _mapping(contract.get("initial_state"))
    if _text(initial.get("policy")) != "user_declared_table":
        issues.append(_issue("complete_initial_state_required", "initial_state.policy",
                             "This engine needs every model state declared (policy user_declared_table)."))
        return {}, {}
    if not (_number(initial.get("time")) and times and float(initial["time"]) == times[0]):
        issues.append(_issue("initial_state_not_at_first_sample", "initial_state.time",
                             "The initial state sits at the first sample; nothing is extrapolated before it."))
    values, provenance = {}, {}
    table = initial.get("values")
    if not isinstance(table, list):
        issues.append(_issue("initial_state_table_missing", "initial_state.values", "A table is required."))
        return {}, {}
    for index, raw in enumerate(table):
        row, where = _mapping(raw), f"initial_state.values[{index}]"
        name, compartment = _text(row.get("name")), _text(row.get("compartment"))
        unit, status, source, value = _text(row.get("unit")), _text(row.get("status")), _text(row.get("source")), row.get("value")
        if name not in compartments:
            issues.append(_issue("unknown_state", where, f"{name!r} is not a model state.")); continue
        if name in values:
            issues.append(_issue("state_declared_twice", where, f"{name} is declared twice.")); continue
        if compartment != compartments[name]:
            issues.append(_issue("state_compartment_mismatch", where, f"{name} is {compartments[name]} in the model."))
        expected_unit = "pH" if name == PH_STATE else "mM"
        if unit != expected_unit:
            issues.append(_issue("state_unit_invalid", where, f"{name} needs unit {expected_unit}; no conversion is performed."))
        if status not in ENTRY_STATUSES:
            issues.append(_issue("state_status_invalid", where, f"Expected one of {list(ENTRY_STATUSES)}."))
        if not source:
            issues.append(_issue("state_source_missing", where, "Every initial value states its source."))
        bounds_ok = _number(value) and (0.0 < float(value) < 14.0 if name == PH_STATE else float(value) >= 0.0)
        if not bounds_ok:
            issues.append(_issue("state_value_invalid", where, "Finite non-negative value required (pH in (0, 14)).")); continue
        values[name] = float(value)
        provenance[name] = {"status": status, "source": source}
    missing = [name for name in pool_names if name not in values]
    if missing:
        issues.append(_issue("initial_state_incomplete", "initial_state.values",
                             f"{len(missing)} model states undeclared, e.g. {missing[:5]}; no default is filled in."))
    return values, provenance


def _channels(contract, times, compartments, issues):
    observations = []
    raw = contract.get("channels")
    if not isinstance(raw, list) or not raw:
        issues.append(_issue("channels_missing", "channels", "At least one channel is required."))
        return observations
    seen = set()
    for index, item in enumerate(raw):
        channel, where = _mapping(item), f"channels[{index}]"
        name, compartment = _text(channel.get("name")), _text(channel.get("compartment"))
        if _text(channel.get("kind")) != "absolute":
            issues.append(_issue("relative_channel_blocked", where, "Relative channels are not supported by this engine version.")); continue
        if _text(channel.get("unit")) != "mM":
            issues.append(_issue("channel_unit_not_mM", where, "mM only; no conversion is performed.")); continue
        if name not in compartments or name == PH_STATE:
            issues.append(_issue("channel_unknown_state", where, f"{name!r} is not an observable model pool.")); continue
        if compartment != compartments[name]:
            issues.append(_issue("channel_compartment_mismatch", where, f"{name} is {compartments[name]} in the model.")); continue
        if name in seen:
            issues.append(_issue("channel_duplicated", where, f"{name} observed twice; replicates are not merged here.")); continue
        values = channel.get("values")
        if not isinstance(values, list) or len(values) != len(times) or not all(v is None or (_number(v) and v >= 0) for v in values):
            issues.append(_issue("channel_values_invalid", where, "One finite non-negative value or null per time point.")); continue
        seen.add(name)
        observations.append({"pool": name, "compartment": compartment,
                             "values": [None if v is None else float(v) for v in values]})
    return observations


def _engine_request(request: Mapping[str, Any], issues: List[dict]) -> Dict[str, Any]:
    request = _mapping(request)
    for key in _FORBIDDEN_REQUEST_KEYS:
        if key in request:
            issues.append(_issue("forbidden_request_key", f"engine_request.{key}", "Not part of a fixed-parameter replay."))
    parameters = request.get("parameters")
    if not isinstance(parameters, Mapping) or not parameters:
        issues.append(_issue("parameters_missing", "engine_request.parameters", "A complete parameter vector is required; none is loaded by default."))
        parameters = {}
    for name, value in parameters.items():
        if not (_number(value) or isinstance(value, str)):
            issues.append(_issue("parameter_invalid", f"engine_request.parameters.{name}", "Finite number or string required."))
        if str(name).startswith("kinetic_family_") and str(value).startswith("teacher_curve"):
            issues.append(_issue("teacher_forced_kinetics", f"engine_request.parameters.{name}", "Free ODE only; teacher-forced kinetics refused."))
    if not _text(request.get("parameters_source")):
        issues.append(_issue("parameters_source_missing", "engine_request.parameters_source", "State where the fixed parameters come from."))
    kinetics = request.get("kinetics")
    if not isinstance(kinetics, Mapping) or not kinetics:
        issues.append(_issue("kinetics_missing", "engine_request.kinetics", "Explicit transport kinetics required."))
        kinetics = {}
    backend = _text(request.get("backend"))
    if backend not in BACKENDS:
        issues.append(_issue("backend_invalid", "engine_request.backend", f"Expected one of {list(BACKENDS)}."))
    if not _text(request.get("network_mode")):
        issues.append(_issue("network_mode_missing", "engine_request.network_mode", "Network mode must be explicit."))
    for key in ("threshold_mM", "negative_tolerance_mM"):
        value = request.get(key)
        valid = _number(value) and (float(value) > 0 if key == "threshold_mM" else float(value) <= 0)
        if not valid:
            issues.append(_issue(f"{key}_invalid", f"engine_request.{key}", "Explicit finite value required."))
    solver = request.get("solver")
    if not isinstance(solver, Mapping) or not _text(solver.get("method")) or not all(
            _number(solver.get(k)) and float(solver.get(k)) > 0 for k in ("rtol", "atol")):
        issues.append(_issue("solver_settings_missing", "engine_request.solver", "Explicit method, rtol and atol required; no default recipe."))
        solver = {}
    if isinstance(solver, Mapping) and any(k in solver for k in ("t_span", "t_eval", "y0")):
        issues.append(_issue("solver_controls_time_or_state", "engine_request.solver", "Times and initial state come from the data only."))
    return {"parameters": copy.deepcopy(dict(parameters)), "parameters_source": _text(request.get("parameters_source")),
            "kinetics": copy.deepcopy(dict(kinetics)), "backend": backend, "network_mode": _text(request.get("network_mode")),
            "threshold_mM": request.get("threshold_mM"), "negative_tolerance_mM": request.get("negative_tolerance_mM"),
            "solver": copy.deepcopy(dict(solver))}


def prepare(data_contract: Any, engine_request: Any, *, pool_names: Sequence[str],
            compartments: Mapping[str, str]) -> PreparedRun:
    """Build an immutable run description, or raise :class:`EngineContractError` listing every issue.

    ``pool_names`` is the full model state order and ``compartments`` maps
    each state to intracellular or extracellular. Both are required: the
    engine does not guess the model layout.
    """
    issues: List[dict] = []
    names = tuple(str(n) for n in (pool_names or ()))
    layout = {str(k): str(v) for k, v in _mapping(compartments).items()}
    if not names or len(set(names)) != len(names) or set(names) != set(layout) or not set(layout.values()) <= set(COMPARTMENTS):
        raise EngineContractError([_issue("model_layout_invalid", "pool_names", "Unique names, each with a known compartment.")])
    contract = _mapping(data_contract)
    if contract.get("schema_version") != SCHEMA_VERSION:
        issues.append(_issue("schema_version_unsupported", "schema_version", f"Expected {SCHEMA_VERSION!r}."))
    identity = _identity(contract, issues)
    times = _times(contract, issues)
    hematocrit, geometry_provenance = _geometry(contract, issues)
    values, provenance = _initial_state(contract, names, layout, times, issues)
    observations = _channels(contract, times, layout, issues)
    request = _engine_request(engine_request, issues)
    locked: Dict[str, float] = {}
    observed_at_t0 = {o["pool"]: o["values"][0] for o in observations if times and o["values"][0] is not None}
    for name, first in observed_at_t0.items():
        if name not in values:
            continue
        if provenance[name]["status"] != "measured":
            issues.append(_issue("observed_state_not_marked_measured", f"initial_state.{name}",
                                 "A state observed at the first sample must be declared measured."))
        elif values[name] != first:
            issues.append(_issue("measured_initial_value_mismatch", f"initial_state.{name}",
                                 f"Declared {values[name]!r} but observed {first!r} at the first sample; no reconciliation is done."))
        else:
            locked[name] = first
    for name, entry in provenance.items():
        if entry["status"] == "measured" and name not in observed_at_t0:
            issues.append(_issue("measured_without_observation", f"initial_state.{name}",
                                 "A state declared measured needs an observation at the first sample in this dataset."))
    if not any(any(v is not None for v in o["values"][1:]) for o in observations):
        issues.append(_issue("nothing_to_score", "channels", "No observation after the first sample."))
    if issues:
        raise EngineContractError(issues)
    fingerprint = _canonical_sha256({"identity": identity, "times": times, "observations": observations,
                                     "initial": [values[n] for n in names], "hematocrit": hematocrit,
                                     "parameters": request["parameters"]})
    return PreparedRun(
        identity=identity, pool_names=names, compartments=layout,
        initial_state=tuple(values[n] for n in names), provenance=provenance, measured_locked=locked,
        sample_times=tuple(times), observations=tuple(observations), hematocrit=hematocrit,
        geometry_provenance=geometry_provenance, parameters=request["parameters"],
        parameters_source=request["parameters_source"], parameters_sha256=_canonical_sha256(request["parameters"]),
        kinetics=request["kinetics"], network_mode=request["network_mode"], backend=request["backend"],
        threshold_mM=float(request["threshold_mM"]), negative_tolerance_mM=float(request["negative_tolerance_mM"]),
        solver_settings=request["solver"], fingerprint=fingerprint)


def validate(prepared: PreparedRun) -> Dict[str, Any]:
    """Re-check the invariants of a prepared run. Never raises."""
    checks = {}
    x0 = dict(zip(prepared.pool_names, prepared.initial_state))
    checks["complete_state"] = len(prepared.initial_state) == len(prepared.pool_names) and set(prepared.provenance) == set(prepared.pool_names)
    checks["measured_locked"] = all(x0.get(n) == v and prepared.provenance[n]["status"] == "measured" for n, v in prepared.measured_locked.items())
    checks["time_origin_first_sample"] = list(prepared.sample_times) == sorted(set(prepared.sample_times)) and len(prepared.sample_times) >= 2
    checks["parameters_unchanged"] = _canonical_sha256(prepared.parameters) == prepared.parameters_sha256
    checks["geometry"] = 0.0 < prepared.hematocrit < 1.0
    checks["absolute_mM_only"] = all(o["compartment"] == prepared.compartments[o["pool"]] for o in prepared.observations)
    checks["no_search"] = not prepared.flags["parameter_search"] and not prepared.flags["teacher_forcing"]
    return {"valid": all(checks.values()), "checks": checks, "engine_version": prepared.engine_version}


def bag_amounts(states: Any, pool_names: Sequence[str], compartments: Mapping[str, str], hematocrit: float) -> np.ndarray:
    """Amounts per L of bag: intracellular mM x H, extracellular mM x (1 - H). pH rows are zero."""
    x = np.asarray(states, dtype=float)
    weights = np.array([0.0 if n == PH_STATE else (hematocrit if compartments[n] == "intracellular" else 1.0 - hematocrit)
                        for n in pool_names])
    return x * (weights[:, None] if x.ndim == 2 else weights)


def run(prepared: PreparedRun, *, rhs_factory: Callable[..., Any], solver: Callable[..., Any]) -> Dict[str, Any]:
    """One free-ODE replay at fixed parameters from the declared first sample.

    Returns a report; status is ``invalid_prepared``, ``contract_violation``,
    ``numerical_failure`` or ``completed_unqualified``. A completed run is
    neither a calibration nor a biological validation.
    """
    base = {"engine_version": prepared.engine_version, "qualification": QUALIFICATION_STATUS,
            "identity": dict(prepared.identity), "fingerprint": prepared.fingerprint, "free_ode": True,
            "teacher_forcing": False, "parameter_search": False, "relative_channels": False,
            "biologically_validated": False, "activation_allowed": False}
    report = validate(prepared)
    if not report["valid"]:
        return {**base, "status": "invalid_prepared", "validation": report}
    parameters = copy.deepcopy(prepared.parameters)
    try:
        rhs = rhs_factory(parameters=parameters, kinetics=copy.deepcopy(prepared.kinetics), mode=prepared.network_mode,
                          backend=prepared.backend, hematocrit=prepared.hematocrit, threshold=prepared.threshold_mM)
    except (ValueError, KeyError, TypeError) as error:
        return {**base, "status": "contract_violation", "reason": f"RHS refused the declared run: {error}"}
    y0 = np.array(prepared.initial_state, dtype=float)
    times = np.array(prepared.sample_times, dtype=float)
    t_span = (float(times[0]), float(times[-1]))
    try:
        solution = solver(rhs, t_span, y0.copy(), t_eval=times.copy(), **copy.deepcopy(prepared.solver_settings))
    except (ValueError, RuntimeError, FloatingPointError, OverflowError) as error:
        return {**base, "status": "numerical_failure", "reason": f"solver raised: {error}"}
    if _canonical_sha256(parameters) != prepared.parameters_sha256:
        return {**base, "status": "contract_violation", "reason": "parameters changed during the run"}
    if not getattr(solution, "success", False):
        return {**base, "status": "numerical_failure", "reason": str(getattr(solution, "message", "solver failed"))}
    t, y = np.asarray(solution.t, dtype=float), np.asarray(solution.y, dtype=float)
    if not np.array_equal(t, times):
        reason = "solver returned a time before the first sample" if t.size and t.min() < times[0] else "solver did not return exactly the sample dates"
        return {**base, "status": "contract_violation", "reason": reason}
    if y.shape != (len(prepared.pool_names), len(times)) or not np.all(np.isfinite(y)):
        return {**base, "status": "numerical_failure", "reason": "non-finite or misshaped states"}
    if not np.array_equal(y[:, 0], y0):
        return {**base, "status": "contract_violation", "reason": "first-sample state differs from the declared initial state"}
    concentration_rows = [i for i, n in enumerate(prepared.pool_names) if n != PH_STATE]
    minimum = float(y[concentration_rows].min())
    if minimum < prepared.negative_tolerance_mM:
        return {**base, "status": "numerical_failure", "reason": f"negative concentration {minimum!r} below tolerance"}
    residuals, scored = [], 0
    for observation in prepared.observations:
        row = prepared.pool_names.index(observation["pool"])
        for k in range(1, len(times)):
            value = observation["values"][k]
            if value is None:
                continue
            predicted = float(y[row, k])
            residuals.append({"pool": observation["pool"], "compartment": observation["compartment"], "time": float(times[k]),
                              "observed_mM": value, "predicted_mM": predicted, "residual_mM": predicted - value})
            scored += 1
    return {**base, "status": "completed_unqualified", "sample_times": times.tolist(), "earliest_time": float(t.min()),
            "scored_points": scored, "residuals": residuals,
            "sum_squared_residual_mM2": float(sum(r["residual_mM"] ** 2 for r in residuals)),
            "first_sample_identity": True, "parameters_unchanged": True,
            "measured_locked": dict(prepared.measured_locked),
            "states_at_samples": {n: y[i].tolist() for i, n in enumerate(prepared.pool_names)}}


def default_model_layout(sam_mode: str = "biochemical_transfer") -> Tuple[Tuple[str, ...], Dict[str, str]]:
    """Model state order and compartments from the existing registries (explicit opt-in call)."""
    from reaction_positivity import rbc_reaction_matrix
    from rbc_gem_audit import EXTERNAL_POOLS

    names, _, _ = rbc_reaction_matrix(sam_mode)
    layout = {n: ("extracellular" if n in EXTERNAL_POOLS else "intracellular") for n in names}
    layout[PH_STATE] = "intracellular"
    return tuple(names) + (PH_STATE,), layout


def default_rhs_factory(*, parameters, kinetics, mode, backend, hematocrit, threshold):
    """The existing phase-aware RHS, constructed as is (explicit opt-in)."""
    from fla_agentic_gem_correction import GemCorrectionRHS

    return GemCorrectionRHS(parameters, kinetics, mode=mode, backend=backend, hematocrit=hematocrit, threshold=threshold)


def default_solver(rhs, t_span, y0, *, t_eval, **settings):
    """``scipy.integrate.solve_ivp`` with caller-supplied settings only (explicit opt-in)."""
    from scipy.integrate import solve_ivp

    return solve_ivp(rhs, t_span, y0, t_eval=t_eval, **settings)
