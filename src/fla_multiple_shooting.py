"""Reusable contracts for observation-anchored FLA multiple shooting."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping, Sequence

import numpy as np


@dataclass(frozen=True)
class ShootingReset:
    time_day: float
    observed_names: tuple[str, ...]
    jump_values: tuple[float, ...]
    normalized_jump_loss: float

    def to_dict(self) -> dict:
        return asdict(self)


def reset_observed_states(
    state: Sequence[float],
    *,
    observations: Mapping[str, float],
    state_indices: Mapping[str, int],
    scales: Mapping[str, float] | None = None,
    time_day: float,
    nonnegative: bool = True,
) -> tuple[np.ndarray, ShootingReset]:
    """Replace declared observed states and record the prediction discontinuity."""
    result = np.asarray(state, dtype=float).copy()
    if result.ndim != 1 or not result.size or not np.all(np.isfinite(result)):
        raise ValueError("state must be a nonempty finite vector")
    if not np.isfinite(time_day):
        raise ValueError("time_day must be finite")
    names = tuple(sorted(observations))
    jumps = []
    normalized = []
    used_indices = set()
    for name in names:
        if name not in state_indices:
            raise KeyError(f"missing state index for observation {name!r}")
        raw_index = state_indices[name]
        if isinstance(raw_index, bool) or not isinstance(raw_index, (int, np.integer)):
            raise ValueError(f"state index for {name!r} must be an integer")
        index = int(raw_index)
        if index < 0 or index >= result.size:
            raise IndexError(f"state index for {name!r} is outside the state vector")
        if index in used_indices:
            raise ValueError("observations must not reset the same state through aliases")
        used_indices.add(index)
        value = float(observations[name])
        if not np.isfinite(value) or (nonnegative and value < 0.0):
            raise ValueError(f"invalid observation for {name!r}: {value}")
        jump = value - float(result[index])
        scale = float(scales[name]) if scales is not None and name in scales else max(abs(value), 0.01)
        if not np.isfinite(scale) or scale <= 0.0:
            raise ValueError(f"scale for {name!r} must be finite and positive")
        scale = max(scale, 0.01)
        result[index] = value
        jumps.append(jump)
        normalized.append(jump / scale)
    loss = float(np.mean(np.square(normalized))) if normalized else 0.0
    return result, ShootingReset(
        time_day=float(time_day),
        observed_names=names,
        jump_values=tuple(float(value) for value in jumps),
        normalized_jump_loss=loss,
    )


def endpoint_nrmse(
    predicted: Sequence[float],
    observed: Sequence[float],
    *,
    scale: float,
) -> float:
    predicted_array = np.asarray(predicted, dtype=float)
    observed_array = np.asarray(observed, dtype=float)
    if predicted_array.shape != observed_array.shape or predicted_array.size == 0:
        raise ValueError("predicted and observed endpoint arrays must be nonempty and aligned")
    if not np.all(np.isfinite(predicted_array)) or not np.all(np.isfinite(observed_array)):
        raise ValueError("endpoint values must be finite")
    if not np.isfinite(scale) or scale <= 0.0:
        raise ValueError("scale must be finite and positive")
    return float(
        np.sqrt(np.mean((predicted_array - observed_array) ** 2))
        / max(abs(float(scale)), 0.01)
    )


def forward_chaining_splits(
    measurement_times: Sequence[float], *, minimum_training_intervals: int = 3
) -> tuple[tuple[tuple[float, float], tuple[float, float]], ...]:
    """Return expanding train windows and the immediately following holdout interval."""
    if type(minimum_training_intervals) is not int or minimum_training_intervals < 1:
        raise ValueError("minimum_training_intervals must be a positive integer")
    time = np.asarray(measurement_times, dtype=float)
    if time.ndim != 1 or time.size < minimum_training_intervals + 2:
        raise ValueError("insufficient measurement times for forward chaining")
    if np.any(~np.isfinite(time)) or np.any(np.diff(time) <= 0.0):
        raise ValueError("measurement times must be finite and strictly increasing")
    result = []
    for holdout_start_index in range(minimum_training_intervals, time.size - 1):
        result.append(
            (
                (float(time[0]), float(time[holdout_start_index])),
                (
                    float(time[holdout_start_index]),
                    float(time[holdout_start_index + 1]),
                ),
            )
        )
    return tuple(result)


def duration_above_threshold(
    time: Sequence[float], values: Sequence[float], *, threshold: float,
) -> float:
    """Elapsed duration above a threshold on one continuous, piecewise-linear trace.

    Call separately for each shooting segment; never integrate across a reset.
    This is a state-availability diagnostic, not a sensitivity measurement.
    """
    t = np.asarray(time, dtype=float)
    y = np.asarray(values, dtype=float)
    if t.ndim != 1 or t.size < 2 or y.shape != t.shape:
        raise ValueError("time and values must be aligned vectors with at least two points")
    if (not np.all(np.isfinite(t)) or not np.all(np.isfinite(y))
            or not np.isfinite(threshold) or np.any(np.diff(t) <= 0.0)):
        raise ValueError("values must be finite and time strictly increasing")
    left, right = y[:-1] >= threshold, y[1:] >= threshold
    fraction = (left & right).astype(float)
    crossing = left != right
    crossing_position = (threshold - y[:-1][crossing]) / np.diff(y)[crossing]
    fraction[crossing] = np.where(left[crossing], crossing_position, 1.0 - crossing_position)
    return float(np.sum(np.diff(t) * fraction))
