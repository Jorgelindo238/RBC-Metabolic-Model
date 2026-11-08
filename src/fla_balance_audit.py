"""Stoichiometric observability and numerical accounting for fixed-parameter FLA."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np


def balance_matrix(
    pools: Sequence[str], reactions: Sequence[str],
    stoichiometry: Mapping[str, Mapping[str, float]],
) -> np.ndarray:
    if not pools or not reactions or len(set(pools)) != len(pools) or len(set(reactions)) != len(reactions):
        raise ValueError("pool and reaction names must be nonempty and unique")
    values = np.asarray([
        [stoichiometry.get(reaction, {}).get(pool, 0.0) for reaction in reactions]
        for pool in pools
    ], dtype=float)
    if not np.all(np.isfinite(values)):
        raise ValueError("stoichiometric coefficients must be finite")
    return values


def constraint_observability(matrix: np.ndarray, *, relative_tolerance: float = 1e-10) -> dict:
    """Which individual fluxes are fixed by A v = b, without kinetic priors?"""
    a = np.asarray(matrix, dtype=float)
    if a.ndim != 2 or not a.shape[0] or not a.shape[1] or not np.all(np.isfinite(a)):
        raise ValueError("constraint matrix must be nonempty, finite and two-dimensional")
    if not np.isfinite(relative_tolerance) or not 0.0 < relative_tolerance < 1.0:
        raise ValueError("relative_tolerance must lie between zero and one")
    _, singular_values, vh = np.linalg.svd(a, full_matrices=True)
    cutoff = singular_values[0] * relative_tolerance
    rank = int(np.count_nonzero(singular_values > cutoff))
    null_basis = vh[rank:].T
    freedom = np.linalg.norm(null_basis, axis=1)
    return {
        "rank": rank,
        "reaction_count": a.shape[1],
        "nullity": a.shape[1] - rank,
        "singular_values": singular_values.tolist(),
        "individually_identifiable_columns": np.flatnonzero(freedom <= relative_tolerance).tolist(),
        "null_basis": null_basis,
    }


def numerical_components(
    *, states: np.ndarray, fluxes: np.ndarray, executed: np.ndarray,
    matrix: np.ndarray, minimum_concentration: float,
    damping_threshold: float, maximum_derivative: float,
) -> dict[str, np.ndarray]:
    """Separate the raw balance, state-wise damping, clipping and unexplained RHS.

    Fluxes must be replayed at these original states with the native input floor.
    The concentration-floor displacement is not a rate or a material source.
    """
    x, v, f, a = (np.asarray(item, dtype=float) for item in (states, fluxes, executed, matrix))
    if (x.ndim != 2 or v.ndim != 2 or a.ndim != 2 or f.shape != x.shape
            or a.shape != (x.shape[0], v.shape[0]) or v.shape[1] != x.shape[1]):
        raise ValueError("state, flux, derivative and matrix dimensions must align")
    if any(not np.all(np.isfinite(item)) for item in (x, v, f, a)):
        raise ValueError("numerical audit inputs must be finite; sanitization cannot be hidden")
    if (not np.isfinite(minimum_concentration) or minimum_concentration <= 0.0
            or not np.isfinite(damping_threshold) or damping_threshold <= minimum_concentration
            or not np.isfinite(maximum_derivative) or maximum_derivative <= 0.0):
        raise ValueError("invalid numerical floor, threshold or derivative bound")
    floored = np.maximum(x, minimum_concentration)
    raw = a @ v
    mask = (floored < damping_threshold) & (raw < 0.0)
    damped = raw.copy()
    damped[mask] *= floored[mask] / damping_threshold
    effective = np.clip(damped, -maximum_derivative, maximum_derivative)
    return {
        "raw": raw,
        "damping": damped - raw,
        "clipping": effective - damped,
        "effective": effective,
        "unexplained": f - effective,
        "total_correction": f - raw,
        "input_floor_displacement": floored - x,
    }


@dataclass(frozen=True)
class QuadratureGrid:
    nodes: np.ndarray
    weights: np.ndarray
    interval_indices: np.ndarray
    boundaries: np.ndarray


def accepted_step_quadrature(
    accepted_time: Sequence[float], boundaries: Sequence[float], *, order: int,
) -> QuadratureGrid:
    """Gauss-Legendre cells split at accepted solver steps and audit boundaries."""
    time = np.asarray(accepted_time, dtype=float)
    cuts = np.asarray(boundaries, dtype=float)
    for label, values in (("accepted_time", time), ("boundaries", cuts)):
        if (values.ndim != 1 or values.size < 2 or not np.all(np.isfinite(values))
                or np.any(np.diff(values) <= 0.0)):
            raise ValueError(f"{label} must be finite and strictly increasing")
    if cuts[0] != time[0] or cuts[-1] != time[-1]:
        raise ValueError("audit boundaries must span the accepted solution exactly")
    if type(order) is not int or order < 2:
        raise ValueError("quadrature order must be an integer of at least two")
    partitions = np.unique(np.concatenate([time, cuts]))
    local_nodes, local_weights = np.polynomial.legendre.leggauss(order)
    half_width = np.diff(partitions) / 2.0
    midpoint = partitions[:-1] + half_width
    nodes = (midpoint[:, None] + half_width[:, None] * local_nodes).ravel()
    weights = (half_width[:, None] * local_weights).ravel()
    intervals = np.searchsorted(cuts, nodes, side="right") - 1
    return QuadratureGrid(nodes, weights, intervals, cuts)


def integrate_intervals(values: np.ndarray, grid: QuadratureGrid) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 2 or array.shape[1] != grid.nodes.size or not np.all(np.isfinite(array)):
        raise ValueError("integrands must be finite and align with quadrature nodes")
    return np.column_stack([
        array[:, grid.interval_indices == index] @ grid.weights[grid.interval_indices == index]
        for index in range(grid.boundaries.size - 1)
    ])
