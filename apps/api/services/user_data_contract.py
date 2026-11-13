"""Versioned contract and preflight for user calibration data.

Pure validation: no calibration core, ODE, solver or file access. Two answers
are kept apart on purpose:

* ``data_valid``: the submitted dataset is well formed and fully declared.
* ``engine_compatibility``: whether the current calibration engine can honour
  what was declared. It cannot yet: the engine loads its own initial state
  (``MM_calibration.load_initial_conditions()`` takes no data argument), has
  no compartment volumes on the request path and no relative-observation
  model. A valid dataset therefore does NOT make the engine compatible, and
  the contractual path stays blocked until those gaps are closed.

Nothing here converts a relative series to mM, merges donors, or substitutes a
reference dataset for a user-declared initial state.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional

SCHEMA_VERSION = "airbc.user_calibration_data/1"
ENGINE_NAME = "MM_calibration_web_adapter"

COMPARTMENTS = ("intracellular", "extracellular")
CHANNEL_KINDS = ("absolute", "relative")
ABSOLUTE_UNITS = ("mM", "uM", "nM")
RELATIVE_UNITS = ("relative", "fold_change", "peak_area", "arbitrary")
ENGINE_ABSOLUTE_UNIT = "mM"
SUBJECT_KINDS = ("donor", "declared_group")
TIME_UNITS = ("day",)
TIME_ORIGINS = ("collection", "storage_start", "first_sample", "other")
GEOMETRY_PROVENANCE = ("measured_this_dataset", "measured_other_source", "borrowed", "assumed")
INITIAL_STATE_POLICIES = ("user_measured_at_first_time", "user_declared_table")
FORBIDDEN_INITIAL_STATE_POLICIES = ("bordbar_reference", "reference_dataset", "engine_default")
UNMEASURED_POOL_POLICIES = ("declared_latent_contract", "undeclared")
NORMALIZATION_BASES = ("first_point", "internal_standard", "total_signal", "other")

LEGACY_PATH_LIMITS = (
    "no data contract was supplied: values are read as intracellular-or-extracellular mM by pool name only",
    "the engine initial state comes from its built-in reference loader, not from the submitted first time point",
    "no hematocrit or compartment volume is applied to the submitted data",
    "relative series are not distinguished from absolute concentrations",
    "donor, cohort and time origin are not recorded",
)


def _issue(code: str, path: str, message: str) -> Dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _check_dataset(payload: Mapping[str, Any], errors: List[dict]) -> Dict[str, Any]:
    dataset = _mapping(payload.get("dataset"))
    if not dataset:
        errors.append(_issue("dataset_missing", "dataset", "Dataset identity block is required."))
    for field in ("dataset_id", "cohort_id"):
        if not _text(dataset.get(field)):
            errors.append(_issue("dataset_identity_missing", f"dataset.{field}", f"{field} is required."))
    if "subjects" in dataset or "donors" in dataset:
        errors.append(_issue("multiple_subjects_in_one_payload", "dataset",
                             "One payload describes one donor or one declared group; submit donors separately."))
    subject = _mapping(dataset.get("subject"))
    kind = _text(subject.get("kind"))
    if kind not in SUBJECT_KINDS:
        errors.append(_issue("subject_kind_invalid", "dataset.subject.kind", f"Expected one of {list(SUBJECT_KINDS)}."))
    if not _text(subject.get("id")):
        errors.append(_issue("subject_id_missing", "dataset.subject.id", "Donor or group identifier is required."))
    if kind == "declared_group":
        group = _mapping(subject.get("group_definition"))
        if not _text(group.get("description")) or not _text(group.get("pooling_method")):
            errors.append(_issue("group_definition_missing", "dataset.subject.group_definition",
                                 "A declared group needs a description and the pooling method used upstream."))
        members = group.get("n_subjects")
        if not (isinstance(members, int) and not isinstance(members, bool) and members >= 1):
            errors.append(_issue("group_size_missing", "dataset.subject.group_definition.n_subjects",
                                 "A declared group states how many subjects it pools."))
    return {"dataset_id": _text(dataset.get("dataset_id")), "cohort_id": _text(dataset.get("cohort_id")),
            "subject_kind": kind, "subject_id": _text(subject.get("id"))}


def _check_time(payload: Mapping[str, Any], errors: List[dict]) -> List[float]:
    time = _mapping(payload.get("time"))
    if _text(time.get("unit")) not in TIME_UNITS:
        errors.append(_issue("time_unit_invalid", "time.unit", f"Expected one of {list(TIME_UNITS)}; no conversion is performed."))
    origin = _mapping(time.get("origin"))
    if _text(origin.get("kind")) not in TIME_ORIGINS:
        errors.append(_issue("time_origin_missing", "time.origin.kind", f"Expected one of {list(TIME_ORIGINS)}."))
    if not _text(origin.get("description")):
        errors.append(_issue("time_origin_undescribed", "time.origin.description",
                             "State what time zero is (for example day of collection)."))
    points = time.get("points")
    if not isinstance(points, list) or not points:
        errors.append(_issue("time_points_missing", "time.points", "At least one time point is required."))
        return []
    if not all(_finite(value) for value in points):
        errors.append(_issue("time_points_not_finite", "time.points", "Every time point must be a finite number."))
        return []
    values = [float(value) for value in points]
    if any(later <= earlier for earlier, later in zip(values, values[1:])):
        errors.append(_issue("time_points_not_increasing", "time.points", "Time points must be strictly increasing."))
    return values


def _check_geometry(payload: Mapping[str, Any], errors: List[dict]) -> None:
    geometry = _mapping(payload.get("geometry"))
    hematocrit = geometry.get("hematocrit")
    if not (_finite(hematocrit) and 0.0 < float(hematocrit) < 1.0):
        errors.append(_issue("hematocrit_invalid", "geometry.hematocrit", "Hematocrit must be a fraction strictly between 0 and 1."))
    provenance = _mapping(geometry.get("provenance"))
    if _text(provenance.get("kind")) not in GEOMETRY_PROVENANCE:
        errors.append(_issue("geometry_provenance_missing", "geometry.provenance.kind", f"Expected one of {list(GEOMETRY_PROVENANCE)}."))
    if not _text(provenance.get("source")):
        errors.append(_issue("geometry_source_missing", "geometry.provenance.source", "State where the hematocrit comes from."))


def _check_initial_state(payload: Mapping[str, Any], times: List[float], errors: List[dict]) -> None:
    initial = _mapping(payload.get("initial_state"))
    policy = _text(initial.get("policy"))
    if policy in FORBIDDEN_INITIAL_STATE_POLICIES:
        errors.append(_issue("initial_state_replaced_by_reference", "initial_state.policy",
                             "A user dataset cannot take its initial state from a reference dataset or an engine default."))
    elif policy not in INITIAL_STATE_POLICIES:
        errors.append(_issue("initial_state_policy_invalid", "initial_state.policy", f"Expected one of {list(INITIAL_STATE_POLICIES)}."))
    declared_time = initial.get("time")
    if not _finite(declared_time):
        errors.append(_issue("initial_state_time_missing", "initial_state.time", "State the time of the initial state."))
    elif times and float(declared_time) != times[0]:
        errors.append(_issue("initial_state_time_mismatch", "initial_state.time",
                             "The initial state must sit at the first time point; no back-extrapolation is performed."))
    if _text(initial.get("unmeasured_pools_policy")) not in UNMEASURED_POOL_POLICIES:
        errors.append(_issue("unmeasured_pools_policy_missing", "initial_state.unmeasured_pools_policy",
                             f"Expected one of {list(UNMEASURED_POOL_POLICIES)}."))
    if policy == "user_declared_table":
        table = initial.get("values")
        if not isinstance(table, list) or not table:
            errors.append(_issue("initial_state_table_missing", "initial_state.values", "A declared table needs at least one entry."))
        else:
            for index, row in enumerate(table):
                row = _mapping(row)
                where = f"initial_state.values[{index}]"
                if (not _text(row.get("name")) or _text(row.get("compartment")) not in COMPARTMENTS
                        or _text(row.get("unit")) not in ABSOLUTE_UNITS or not _finite(row.get("value"))
                        or float(row.get("value")) < 0 or not _text(row.get("source"))):
                    errors.append(_issue("initial_state_entry_invalid", where,
                                         "Each entry needs name, compartment, absolute unit, non-negative value and source."))


def _check_channel(channel: Mapping[str, Any], index: int, n_times: int, errors: List[dict]) -> Optional[Dict[str, Any]]:
    where = f"channels[{index}]"
    name, compartment, kind, unit = (_text(channel.get(k)) for k in ("name", "compartment", "kind", "unit"))
    ok = True
    if not name:
        errors.append(_issue("channel_name_missing", where + ".name", "Channel name is required.")); ok = False
    if compartment not in COMPARTMENTS:
        errors.append(_issue("channel_compartment_missing", where + ".compartment", f"Expected one of {list(COMPARTMENTS)}.")); ok = False
    if kind not in CHANNEL_KINDS:
        errors.append(_issue("channel_kind_missing", where + ".kind", f"Expected one of {list(CHANNEL_KINDS)}.")); ok = False
    if kind == "absolute" and unit not in ABSOLUTE_UNITS:
        errors.append(_issue("channel_unit_invalid", where + ".unit", f"Absolute channels use one of {list(ABSOLUTE_UNITS)}.")); ok = False
    if kind == "relative" and unit not in RELATIVE_UNITS:
        errors.append(_issue("relative_channel_with_absolute_unit", where + ".unit",
                             f"Relative channels use one of {list(RELATIVE_UNITS)}; a relative series is never read as a concentration."))
        ok = False
    values = channel.get("values")
    if not isinstance(values, list) or len(values) != n_times:
        errors.append(_issue("channel_length_mismatch", where + ".values", "One value per time point is required (null for a missing value)."))
        return None
    if not all(value is None or _finite(value) for value in values):
        errors.append(_issue("channel_value_not_finite", where + ".values", "Values must be finite numbers or null.")); ok = False
    elif any(value is not None and float(value) < 0 for value in values):
        errors.append(_issue("channel_value_negative", where + ".values", "Values must be non-negative.")); ok = False
    if all(value is None for value in values):
        errors.append(_issue("channel_empty", where + ".values", "A channel needs at least one observed value.")); ok = False
    anchored = False
    if kind == "relative":
        normalization = _mapping(channel.get("normalization"))
        if _text(normalization.get("basis")) not in NORMALIZATION_BASES or not _text(normalization.get("description")):
            errors.append(_issue("relative_normalization_missing", where + ".normalization",
                                 f"State the normalization basis ({list(NORMALIZATION_BASES)}) and describe it.")); ok = False
        anchor = channel.get("anchor")
        if anchor is not None:
            anchor = _mapping(anchor)
            if (not _finite(anchor.get("value")) or float(anchor.get("value")) <= 0 or _text(anchor.get("unit")) not in ABSOLUTE_UNITS
                    or not _finite(anchor.get("time")) or not _text(anchor.get("source"))):
                errors.append(_issue("relative_anchor_invalid", where + ".anchor",
                                     "An anchor needs a positive value, an absolute unit, its time and its source.")); ok = False
            else:
                anchored = True
    elif channel.get("anchor") is not None or channel.get("normalization") is not None:
        errors.append(_issue("absolute_channel_with_relative_fields", where, "Absolute channels carry no anchor or normalization.")); ok = False
    if not ok:
        return None
    return {"name": name, "compartment": compartment, "kind": kind, "unit": unit, "anchored": anchored,
            "observed": sum(value is not None for value in values), "values": list(values)}


def _engine_compatibility(channels: List[Dict[str, Any]], data_valid: bool) -> Dict[str, Any]:
    blocking = [
        _issue("engine_initial_state_ignores_user_data", "initial_state",
               "The engine loads its own initial state and cannot take the declared one."),
        _issue("engine_no_compartment_volumes", "geometry",
               "The request path carries no hematocrit or compartment volume into the engine."),
        _issue("engine_time_origin_not_bound", "time",
               "The engine does not bind its start time or horizon to the declared time origin."),
    ]
    for index, channel in enumerate(channels):
        where = f"channels[{index}]"
        if channel["kind"] == "relative":
            code = "engine_no_relative_observation_model" if channel["anchored"] else "relative_without_anchor_not_fittable_as_concentration"
            blocking.append(_issue(code, where, "The engine has no relative-observation model; no conversion to mM is performed."))
        elif channel["unit"] != ENGINE_ABSOLUTE_UNIT:
            blocking.append(_issue("engine_requires_mM_no_conversion_performed", where,
                                   f"The engine reads {ENGINE_ABSOLUTE_UNIT} only and this preflight converts nothing."))
    if not data_valid:
        blocking.insert(0, _issue("data_invalid", "", "The dataset itself is not valid."))
    return {"engine": ENGINE_NAME, "compatible": False, "blocking": blocking}


def preflight(payload: Any) -> Dict[str, Any]:
    """Validate a user dataset against the versioned contract. Never raises on bad data."""
    errors: List[dict] = []
    warnings: List[dict] = []
    if not isinstance(payload, Mapping):
        errors.append(_issue("payload_not_an_object", "", "The data contract must be an object."))
        payload = {}
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(_issue("schema_version_unsupported", "schema_version", f"Expected {SCHEMA_VERSION!r}."))
    identity = _check_dataset(payload, errors)
    times = _check_time(payload, errors)
    _check_geometry(payload, errors)
    _check_initial_state(payload, times, errors)
    raw_channels = payload.get("channels")
    channels: List[Dict[str, Any]] = []
    if not isinstance(raw_channels, list) or not raw_channels:
        errors.append(_issue("channels_missing", "channels", "At least one observation channel is required."))
        raw_channels = []
    seen: Dict[tuple, int] = {}
    for index, raw in enumerate(raw_channels):
        if not isinstance(raw, Mapping):
            errors.append(_issue("channel_not_an_object", f"channels[{index}]", "Each channel must be an object."))
            continue
        channel = _check_channel(raw, index, len(times), errors)
        key = (_text(raw.get("name")).upper(), _text(raw.get("compartment")))
        if all(key) and key in seen:
            errors.append(_issue("channel_duplicated", f"channels[{index}]",
                                 f"Same pool and compartment as channels[{seen[key]}]; replicates or donors are not merged here."))
        elif all(key):
            seen[key] = index
        if channel is not None:
            channels.append(channel)
    for i, first in enumerate(channels):
        for second in channels[i+1:]:
            if first["values"] == second["values"]:
                warnings.append(_issue("identical_series", "channels",
                                       f"{first['name']} ({first['compartment']}) and {second['name']} ({second['compartment']}) "
                                       "have identical values; they may not be independent measurements."))
    for index, channel in enumerate(channels):
        if channel["kind"] == "relative" and not channel["anchored"]:
            warnings.append(_issue("relative_without_anchor", f"channels[{index}]",
                                   "Relative series without an absolute anchor: usable for shape only."))
    if _text(_mapping(payload.get("initial_state")).get("unmeasured_pools_policy")) == "undeclared":
        warnings.append(_issue("unmeasured_pools_undeclared", "initial_state.unmeasured_pools_policy",
                               "Unmeasured pools have no declared convention."))
    data_valid = not errors
    compatibility = _engine_compatibility(channels if data_valid else [], data_valid)
    return {
        "schema_version": SCHEMA_VERSION,
        "data_valid": data_valid,
        "errors": errors,
        "warnings": warnings,
        "dataset_identity": identity,
        "time_points": times,
        "channels": [{k: v for k, v in channel.items() if k != "values"} for channel in channels],
        "engine_compatibility": compatibility,
        "launch_allowed": bool(data_valid and compatibility["compatible"]),
        "conversions_performed": [],
        "donors_merged": False,
        "initial_state_substituted": False,
    }


def legacy_path_notice() -> Dict[str, Any]:
    """What a calibration run without a data contract does not guarantee."""
    return {"status": "legacy_no_data_contract", "schema_version": None, "limits": list(LEGACY_PATH_LIMITS)}
