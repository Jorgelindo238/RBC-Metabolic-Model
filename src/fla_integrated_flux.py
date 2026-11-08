"""Interval-integrated flux teachers for sparse concentration time series."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence

import numpy as np
from scipy.integrate import trapezoid


@dataclass(frozen=True)
class IntegratedFluxTarget:
    start_day: float
    end_day: float
    observed_state_change_mM: float
    known_flux_integral_mM: float
    required_unknown_flux_integral_mM: float
    model_unknown_flux_integral_mM: float
    residual_mM: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def _strict_time(values: Sequence[float], name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or array.size < 2:
        raise ValueError(f"{name} must contain at least two points")
    if not np.all(np.isfinite(array)) or np.any(np.diff(array) <= 0.0):
        raise ValueError(f"{name} must be finite and strictly increasing")
    return array


def _exact_value(time: np.ndarray, values: np.ndarray, target: float) -> float:
    indices = np.flatnonzero(np.isclose(time, float(target), rtol=0.0, atol=1e-10))
    if indices.size != 1:
        raise ValueError(f"window boundary {target:g} is not a unique measured time")
    return float(values[int(indices[0])])


def _window_integral(
    time: np.ndarray, values: np.ndarray, start: float, end: float
) -> float:
    mask = (time >= start - 1e-10) & (time <= end + 1e-10)
    local_time = time[mask]
    local_values = values[mask]
    if local_time.size < 2:
        raise ValueError(f"dense grid does not resolve window {start:g}-{end:g}")
    if not np.isclose(local_time[0], start, rtol=0.0, atol=1e-10):
        raise ValueError(f"dense grid is missing start boundary {start:g}")
    if not np.isclose(local_time[-1], end, rtol=0.0, atol=1e-10):
        raise ValueError(f"dense grid is missing end boundary {end:g}")
    return float(trapezoid(local_values, local_time))


def build_integrated_flux_targets(
    *,
    measurement_time: Sequence[float],
    measurement_values: Sequence[float],
    dense_time: Sequence[float],
    known_rate: Sequence[float],
    model_unknown_rate: Sequence[float],
    unknown_stoichiometric_coefficient: float,
    windows: Sequence[tuple[float, float]],
) -> tuple[IntegratedFluxTarget, ...]:
    """Solve integrated balances for one unknown reaction.

    The state equation is ``dC/dt = known_rate + coefficient*unknown_rate``.
    Window boundaries must be measured directly; no interpolated endpoint is
    accepted as primary flux evidence.
    """
    measurement_time_array = _strict_time(measurement_time, "measurement_time")
    measurement_values_array = np.asarray(measurement_values, dtype=float)
    if measurement_values_array.shape != measurement_time_array.shape:
        raise ValueError("measurement_values must align with measurement_time")
    dense_time_array = _strict_time(dense_time, "dense_time")
    known_rate_array = np.asarray(known_rate, dtype=float)
    model_unknown_array = np.asarray(model_unknown_rate, dtype=float)
    if known_rate_array.shape != dense_time_array.shape:
        raise ValueError("known_rate must align with dense_time")
    if model_unknown_array.shape != dense_time_array.shape:
        raise ValueError("model_unknown_rate must align with dense_time")
    for name, values in (
        ("measurement_values", measurement_values_array),
        ("known_rate", known_rate_array),
        ("model_unknown_rate", model_unknown_array),
    ):
        if not np.all(np.isfinite(values)):
            raise ValueError(f"{name} must contain only finite values")
    coefficient = float(unknown_stoichiometric_coefficient)
    if not np.isfinite(coefficient) or np.isclose(coefficient, 0.0):
        raise ValueError("unknown_stoichiometric_coefficient must be finite and nonzero")

    result: list[IntegratedFluxTarget] = []
    for start, end in windows:
        start = float(start)
        end = float(end)
        if not np.isfinite(start) or not np.isfinite(end) or start >= end:
            raise ValueError(f"invalid window {start:g}-{end:g}")
        observed_change = _exact_value(
            measurement_time_array, measurement_values_array, end
        ) - _exact_value(measurement_time_array, measurement_values_array, start)
        known_integral = _window_integral(
            dense_time_array, known_rate_array, start, end
        )
        model_integral = _window_integral(
            dense_time_array, model_unknown_array, start, end
        )
        required = (observed_change - known_integral) / coefficient
        result.append(
            IntegratedFluxTarget(
                start_day=start,
                end_day=end,
                observed_state_change_mM=observed_change,
                known_flux_integral_mM=known_integral,
                required_unknown_flux_integral_mM=required,
                model_unknown_flux_integral_mM=model_integral,
                residual_mM=model_integral - required,
            )
        )
    return tuple(result)


def integrated_flux_nrmse(
    targets: Sequence[IntegratedFluxTarget], *, scale_floor_mM: float = 0.05
) -> float:
    if not targets:
        raise ValueError("at least one integrated flux target is required")
    if not np.isfinite(scale_floor_mM) or scale_floor_mM <= 0.0:
        raise ValueError("scale_floor_mM must be finite and positive")
    required = np.asarray(
        [target.required_unknown_flux_integral_mM for target in targets], dtype=float
    )
    residual = np.asarray([target.residual_mM for target in targets], dtype=float)
    if not np.all(np.isfinite(required)) or not np.all(np.isfinite(residual)):
        raise ValueError("integrated flux targets must be finite")
    scale = max(float(np.mean(np.abs(required))), float(scale_floor_mM))
    return float(np.sqrt(np.mean(residual**2)) / scale)


def irreversible_teacher_is_feasible(
    targets: Sequence[IntegratedFluxTarget], *, tolerance_mM: float = 1e-8
) -> bool:
    if not np.isfinite(tolerance_mM) or tolerance_mM < 0.0:
        raise ValueError("tolerance_mM must be finite and nonnegative")
    return bool(
        targets
        and all(
            np.isfinite(target.required_unknown_flux_integral_mM)
            and target.required_unknown_flux_integral_mM >= -float(tolerance_mM)
            for target in targets
        )
    )
