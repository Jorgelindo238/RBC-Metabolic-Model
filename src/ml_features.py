"""Fixed-schema feature extraction for Phase B flux-learning.

The feature vector intentionally stays NumPy-only at runtime. Downstream
synthetic-data regressors can rely on the exported schema version and feature
names to guarantee that training and inference see the same layout.
"""

from __future__ import annotations

from typing import Dict, Iterable, Mapping, Sequence, Tuple

import numpy as np

try:  # Support both ``import ml_features`` and ``import src.ml_features``.
    from . import rbc_stoichiometry as rs
except ImportError:  # pragma: no cover - used by script-style imports.
    import rbc_stoichiometry as rs  # type: ignore


FEATURE_VERSION = "phase_b_v1"
EPS = 1e-12

METABOLITE_FEATURES: Tuple[str, ...] = (
    "present",
    "initial",
    "final",
    "mean",
    "minimum",
    "maximum",
    "log10_initial",
    "log10_final",
    "log10_fold_change",
    "max_abs_slope",
    "time_to_half_frac",
    "hill_shape",
)

REACTION_FEATURES: Tuple[str, ...] = (
    "present",
    "mean",
    "mean_abs",
    "maximum",
    "minimum",
    "final",
    "net_change",
    "sign_changes",
    "smoothness",
    "log10_mean_abs",
)

DEFAULT_METABOLITES: Tuple[str, ...] = tuple(sorted(rs.ALL_METABOLITES))
DEFAULT_REACTIONS: Tuple[str, ...] = tuple(
    sorted(reaction for reaction in rs.ALL_REACTIONS if reaction not in rs.ZERO_FLUX_REACTIONS)
)


def _normalize_name(name: str) -> str:
    return str(name).strip().upper()


def _safe_log10(value: float) -> float:
    return float(np.log10(max(abs(float(value)), EPS)))


def _as_time_grid(time_grid: Sequence[float]) -> np.ndarray:
    time = np.asarray([float(t) for t in time_grid], dtype=float)
    if time.ndim != 1 or time.size == 0:
        raise ValueError("time_grid must be a one-dimensional non-empty sequence.")
    if not np.all(np.isfinite(time)):
        raise ValueError("time_grid contains non-finite values.")
    if time.size > 1 and np.any(np.diff(time) <= 0):
        raise ValueError("time_grid must be strictly increasing.")
    return time


def _normalize_series_map(
    data: Mapping[str, Sequence[float] | np.ndarray],
    time: np.ndarray,
    *,
    label: str,
) -> Dict[str, np.ndarray]:
    normalized: Dict[str, np.ndarray] = {}
    for raw_name, raw_values in data.items():
        name = _normalize_name(raw_name)
        if not name:
            continue
        values = np.asarray(raw_values, dtype=float)
        if values.ndim != 1:
            raise ValueError(f"{label} series for {name} must be one-dimensional.")
        if values.size != time.size:
            raise ValueError(f"{label} series for {name} must align with time_grid.")
        if not np.all(np.isfinite(values)):
            continue
        normalized[name] = values
    return normalized


def build_feature_schema(
    *,
    metabolites: Iterable[str] = DEFAULT_METABOLITES,
    reactions: Iterable[str] = DEFAULT_REACTIONS,
) -> Tuple[str, ...]:
    schema = []
    for name in sorted({_normalize_name(met) for met in metabolites if _normalize_name(met)}):
        schema.extend(f"metabolite:{name}:{feature}" for feature in METABOLITE_FEATURES)
    for name in sorted({_normalize_name(rxn) for rxn in reactions if _normalize_name(rxn)}):
        schema.extend(f"reaction:{name}:{feature}" for feature in REACTION_FEATURES)
    return tuple(schema)


FEATURE_SCHEMA: Tuple[str, ...] = build_feature_schema()


def _time_to_half_fraction(values: np.ndarray, time: np.ndarray) -> float:
    if values.size < 2 or time.size < 2:
        return 0.0
    start = float(values[0])
    end = float(values[-1])
    delta = end - start
    if abs(delta) <= EPS:
        return 0.0
    half = start + 0.5 * delta
    if delta > 0:
        hits = np.where(values >= half)[0]
    else:
        hits = np.where(values <= half)[0]
    if hits.size == 0:
        return 1.0
    duration = max(float(time[-1] - time[0]), EPS)
    return float(np.clip((float(time[int(hits[0])]) - float(time[0])) / duration, 0.0, 1.0))


def _hill_shape(values: np.ndarray, time: np.ndarray) -> float:
    if values.size < 3 or time.size < 3:
        return 0.0
    slopes = np.gradient(values, time)
    net_rate = abs(float(values[-1] - values[0])) / max(float(time[-1] - time[0]), EPS)
    return float(np.clip(float(np.max(np.abs(slopes))) / (net_rate + EPS), 0.0, 20.0))


def _smoothness(values: np.ndarray) -> float:
    if values.size < 3:
        return 1.0
    first = np.diff(values)
    second = np.diff(first)
    scale = float(np.nanmedian(np.abs(first))) + EPS
    roughness = float(np.nanmedian(np.abs(second))) / scale
    return float(np.clip(1.0 / (1.0 + roughness), 0.0, 1.0))


def _metabolite_features(values: np.ndarray | None, time: np.ndarray) -> Tuple[float, ...]:
    if values is None or values.size == 0:
        return tuple(0.0 for _ in METABOLITE_FEATURES)
    slopes = np.gradient(values, time) if values.size > 1 else np.zeros_like(values)
    initial = float(values[0])
    final = float(values[-1])
    return (
        1.0,
        initial,
        final,
        float(np.mean(values)),
        float(np.min(values)),
        float(np.max(values)),
        _safe_log10(initial),
        _safe_log10(final),
        float(np.log10((max(final, 0.0) + EPS) / (max(initial, 0.0) + EPS))),
        float(np.max(np.abs(slopes))) if slopes.size else 0.0,
        _time_to_half_fraction(values, time),
        _hill_shape(values, time),
    )


def _reaction_features(values: np.ndarray | None) -> Tuple[float, ...]:
    if values is None or values.size == 0:
        return tuple(0.0 for _ in REACTION_FEATURES)
    signs = np.sign(values)
    sign_changes = float(np.sum(np.diff(signs) != 0)) if signs.size > 1 else 0.0
    mean_abs = float(np.mean(np.abs(values)))
    return (
        1.0,
        float(np.mean(values)),
        mean_abs,
        float(np.max(values)),
        float(np.min(values)),
        float(values[-1]),
        float(values[-1] - values[0]),
        sign_changes,
        _smoothness(values),
        _safe_log10(mean_abs),
    )


def build_features(
    curves: Mapping[str, Sequence[float] | np.ndarray],
    fluxes: Mapping[str, Sequence[float] | np.ndarray],
    time_grid: Sequence[float],
    *,
    metabolites: Iterable[str] = DEFAULT_METABOLITES,
    reactions: Iterable[str] = DEFAULT_REACTIONS,
) -> np.ndarray:
    """Return a fixed-order feature vector for concentration and flux curves."""

    time = _as_time_grid(time_grid)
    curve_map = _normalize_series_map(curves, time, label="curve")
    flux_map = _normalize_series_map(fluxes, time, label="flux")

    values = []
    for name in sorted({_normalize_name(met) for met in metabolites if _normalize_name(met)}):
        values.extend(_metabolite_features(curve_map.get(name), time))
    for name in sorted({_normalize_name(rxn) for rxn in reactions if _normalize_name(rxn)}):
        values.extend(_reaction_features(flux_map.get(name)))

    vector = np.asarray(values, dtype=float)
    return np.nan_to_num(vector, nan=0.0, posinf=0.0, neginf=0.0)


def build_feature_payload(
    curves: Mapping[str, Sequence[float] | np.ndarray],
    fluxes: Mapping[str, Sequence[float] | np.ndarray],
    time_grid: Sequence[float],
    *,
    metabolites: Iterable[str] = DEFAULT_METABOLITES,
    reactions: Iterable[str] = DEFAULT_REACTIONS,
) -> Dict[str, object]:
    """Return values plus schema metadata for artifact/debug usage."""

    metabolite_tuple = tuple(sorted({_normalize_name(met) for met in metabolites if _normalize_name(met)}))
    reaction_tuple = tuple(sorted({_normalize_name(rxn) for rxn in reactions if _normalize_name(rxn)}))
    schema = build_feature_schema(metabolites=metabolite_tuple, reactions=reaction_tuple)
    vector = build_features(
        curves,
        fluxes,
        time_grid,
        metabolites=metabolite_tuple,
        reactions=reaction_tuple,
    )
    return {
        "contract_type": "phase_b_feature_vector",
        "contract_version": 1,
        "feature_version": FEATURE_VERSION,
        "schema": schema,
        "values": vector,
        "metadata": {
            "feature_count": int(vector.size),
            "metabolite_count": len(metabolite_tuple),
            "reaction_count": len(reaction_tuple),
            "metabolite_features": METABOLITE_FEATURES,
            "reaction_features": REACTION_FEATURES,
        },
    }


__all__ = [
    "FEATURE_SCHEMA",
    "FEATURE_VERSION",
    "METABOLITE_FEATURES",
    "REACTION_FEATURES",
    "DEFAULT_METABOLITES",
    "DEFAULT_REACTIONS",
    "build_feature_payload",
    "build_feature_schema",
    "build_features",
]
