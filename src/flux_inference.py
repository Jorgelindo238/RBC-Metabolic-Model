"""Online flux inference from uploaded concentration curves.

Phase B of the auto-calibrate-all + ML flux-learning plan.

The module turns user concentration observations into reaction-flux estimates
without changing the calibration worker/API contract. It uses the parsed
stoichiometry from :mod:`rbc_stoichiometry`, PCHIP derivatives for measured
metabolites, singleton stoichiometric balance propagation for directly
identified fluxes, and bounded least-squares for the remaining local system.
"""

from __future__ import annotations

from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple

import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.optimize import lsq_linear

try:  # Support both ``import flux_inference`` and ``import src.flux_inference``.
    from . import rbc_stoichiometry as rs
except ImportError:  # pragma: no cover - used by script-style imports.
    import rbc_stoichiometry as rs  # type: ignore


EPS = 1e-12


def _normalize_name(name: str) -> str:
    return str(name).strip().upper()


def _as_strict_time_grid(exp_time: Sequence[float]) -> np.ndarray:
    time = np.asarray([float(t) for t in exp_time], dtype=float)
    if time.ndim != 1 or time.size < 2:
        raise ValueError("exp_time must contain at least two time points.")
    if not np.all(np.isfinite(time)):
        raise ValueError("exp_time contains non-finite values.")
    order = np.argsort(time)
    sorted_time = time[order]
    if np.any(np.diff(sorted_time) <= 0):
        raise ValueError("exp_time must be strictly increasing after sorting.")
    return sorted_time


def _normalize_curves(
    exp_data: Mapping[str, Sequence[float]],
    exp_time: Sequence[float],
) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    source_time = np.asarray([float(t) for t in exp_time], dtype=float)
    order = np.argsort(source_time)
    time = _as_strict_time_grid(exp_time)

    curves: Dict[str, np.ndarray] = {}
    for raw_name, raw_values in exp_data.items():
        name = _normalize_name(raw_name)
        if not name:
            continue
        values = np.asarray([float(v) for v in raw_values], dtype=float)
        if values.ndim != 1 or values.size != source_time.size:
            raise ValueError(f"Series for {name} must align with exp_time.")
        if not np.all(np.isfinite(values)):
            continue
        curves[name] = values[order]
    if not curves:
        raise ValueError("exp_data did not contain any finite metabolite series.")
    return time, curves


def _interpolate_curves(
    time: np.ndarray,
    curves: Mapping[str, np.ndarray],
    time_grid: Optional[Sequence[float]],
) -> Tuple[np.ndarray, Dict[str, np.ndarray], Dict[str, np.ndarray]]:
    if time_grid is None:
        grid = np.asarray(time, dtype=float)
    else:
        grid = np.asarray([float(t) for t in time_grid], dtype=float)
        if grid.ndim != 1 or grid.size < 2:
            raise ValueError("time_grid must contain at least two points.")
        if not np.all(np.isfinite(grid)):
            raise ValueError("time_grid contains non-finite values.")
        if np.any(np.diff(grid) <= 0):
            raise ValueError("time_grid must be strictly increasing.")

    interpolated: Dict[str, np.ndarray] = {}
    derivatives: Dict[str, np.ndarray] = {}
    for name, values in curves.items():
        pchip = PchipInterpolator(time, values, extrapolate=False)
        interpolated[name] = np.asarray(pchip(grid), dtype=float)
        derivatives[name] = np.asarray(pchip.derivative()(grid), dtype=float)
    return grid, interpolated, derivatives


def _candidate_reactions(
    metabolites: Iterable[str],
    stoichiometry: Mapping[str, Mapping[str, float]],
    reactions: Optional[Iterable[str]],
) -> Tuple[str, ...]:
    measured = {_normalize_name(name) for name in metabolites}
    if reactions is not None:
        selected = {_normalize_name(name) for name in reactions}
    else:
        selected = {
            reaction
            for reaction, coeffs in stoichiometry.items()
            if any(_normalize_name(met) in measured for met in coeffs)
        }
    return tuple(sorted(reaction for reaction in selected if reaction in stoichiometry))


def _stoichiometry_matrix(
    metabolites: Sequence[str],
    reactions: Sequence[str],
    stoichiometry: Mapping[str, Mapping[str, float]],
) -> np.ndarray:
    matrix = np.zeros((len(metabolites), len(reactions)), dtype=float)
    for col, reaction in enumerate(reactions):
        coeffs = stoichiometry.get(reaction, {})
        for row, metabolite in enumerate(metabolites):
            matrix[row, col] = float(coeffs.get(metabolite, 0.0))
    return matrix


def _nonnegative_reactions(
    reactions: Sequence[str],
    reversible_reactions: Optional[Iterable[str]],
    enforce_nonnegative: bool,
) -> Dict[str, bool]:
    reversible = {_normalize_name(name) for name in (reversible_reactions or [])}
    return {
        reaction: bool(enforce_nonnegative and reaction not in reversible)
        for reaction in reactions
    }


def _clip_if_needed(values: np.ndarray, reaction: str, nonnegative: Mapping[str, bool]) -> np.ndarray:
    if nonnegative.get(reaction, False):
        return np.maximum(values, 0.0)
    return values


def _propagate_singletons(
    *,
    metabolites: Sequence[str],
    reactions: Sequence[str],
    s_matrix: np.ndarray,
    dcdt: np.ndarray,
    nonnegative: Mapping[str, bool],
) -> Tuple[Dict[str, np.ndarray], Dict[str, str], Tuple[str, ...]]:
    """Resolve fluxes that are identifiable from one remaining balance row.

    Example: ``dxdt[EGLC] = -VEGLC`` resolves VEGLC directly. Once ``VELAC``
    is resolved from ``dxdt[ELAC] = VELAC``, ``dxdt[LAC] = VLDH - VELAC``
    resolves VLDH. The propagation is purely structural and works for any
    row that becomes a singleton.
    """

    unresolved = set(reactions)
    resolved: Dict[str, np.ndarray] = {}
    methods: Dict[str, str] = {}
    index_by_reaction = {reaction: idx for idx, reaction in enumerate(reactions)}

    changed = True
    while changed:
        changed = False
        for row, _metabolite in enumerate(metabolites):
            unresolved_here = [
                reaction
                for reaction in unresolved
                if abs(float(s_matrix[row, index_by_reaction[reaction]])) > EPS
            ]
            if len(unresolved_here) != 1:
                continue
            reaction = unresolved_here[0]
            col = index_by_reaction[reaction]
            coeff = float(s_matrix[row, col])
            fixed = np.zeros(dcdt.shape[1], dtype=float)
            for fixed_reaction, values in resolved.items():
                fixed_col = index_by_reaction[fixed_reaction]
                fixed += float(s_matrix[row, fixed_col]) * values
            values = (dcdt[row, :] - fixed) / coeff
            resolved[reaction] = _clip_if_needed(values, reaction, nonnegative)
            methods[reaction] = "stoichiometric_singleton"
            unresolved.remove(reaction)
            changed = True

    return resolved, methods, tuple(sorted(unresolved))


def _solve_remaining_fluxes(
    *,
    reactions: Sequence[str],
    unresolved: Sequence[str],
    s_matrix: np.ndarray,
    dcdt: np.ndarray,
    resolved: Dict[str, np.ndarray],
    methods: Dict[str, str],
    nonnegative: Mapping[str, bool],
) -> None:
    if not unresolved:
        return

    index_by_reaction = {reaction: idx for idx, reaction in enumerate(reactions)}
    unresolved_indices = [index_by_reaction[reaction] for reaction in unresolved]
    fixed_indices = [index_by_reaction[reaction] for reaction in resolved]
    a_matrix = s_matrix[:, unresolved_indices]

    lower = np.asarray(
        [0.0 if nonnegative.get(reaction, False) else -np.inf for reaction in unresolved],
        dtype=float,
    )
    upper = np.full(len(unresolved), np.inf, dtype=float)

    fixed_matrix = s_matrix[:, fixed_indices] if fixed_indices else np.zeros((s_matrix.shape[0], 0), dtype=float)
    fixed_values = (
        np.vstack([resolved[reaction] for reaction in resolved]).T
        if resolved
        else np.zeros((dcdt.shape[1], 0), dtype=float)
    )

    solved = {reaction: np.zeros(dcdt.shape[1], dtype=float) for reaction in unresolved}
    for time_idx in range(dcdt.shape[1]):
        rhs = dcdt[:, time_idx].copy()
        if fixed_values.size:
            rhs -= fixed_matrix @ fixed_values[time_idx, :]
        try:
            result = lsq_linear(
                a_matrix,
                rhs,
                bounds=(lower, upper),
                lsmr_tol="auto",
                max_iter=200,
            )
            values = np.asarray(result.x, dtype=float)
        except Exception:
            values = np.linalg.lstsq(a_matrix, rhs, rcond=None)[0]
            values = np.maximum(values, lower)
        for idx, reaction in enumerate(unresolved):
            solved[reaction][time_idx] = values[idx]

    for reaction, values in solved.items():
        resolved[reaction] = _clip_if_needed(values, reaction, nonnegative)
        methods[reaction] = "bounded_lstsq"


def _smoothness_score(values: np.ndarray) -> float:
    if values.size < 3:
        return 1.0
    first = np.diff(values)
    second = np.diff(first)
    scale = float(np.nanmedian(np.abs(first))) + EPS
    roughness = float(np.nanmedian(np.abs(second))) / scale
    return float(np.clip(1.0 / (1.0 + roughness), 0.0, 1.0))


def _fit_diagnostics(s_matrix: np.ndarray, flux_matrix: np.ndarray, dcdt: np.ndarray) -> Dict[str, float]:
    predicted = s_matrix @ flux_matrix
    residual = predicted - dcdt
    rmse = float(np.sqrt(np.mean(residual ** 2)))
    norm = float(max(np.sqrt(np.mean(dcdt ** 2)), EPS))
    centered = dcdt - float(np.mean(dcdt))
    ss_tot = float(np.sum(centered ** 2))
    ss_res = float(np.sum(residual ** 2))
    if ss_tot <= EPS:
        r2 = 1.0 if ss_res <= EPS else 0.0
    else:
        r2 = 1.0 - ss_res / ss_tot
    rank = int(np.linalg.matrix_rank(s_matrix)) if s_matrix.size else 0
    return {
        "balance_rmse": rmse,
        "balance_nrmse": float(rmse / norm),
        "balance_r2": float(np.clip(r2, -1.0, 1.0)),
        "stoichiometry_rank": float(rank),
        "metabolite_equations": float(s_matrix.shape[0]),
        "reaction_unknowns": float(s_matrix.shape[1]),
        "rank_fraction": float(rank / max(s_matrix.shape[1], 1)),
    }


def _confidence_payload(
    *,
    reaction: str,
    values: np.ndarray,
    method: str,
    diagnostics: Mapping[str, float],
) -> Dict[str, float | str]:
    smoothness = _smoothness_score(values)
    r2_component = float(np.clip((float(diagnostics.get("balance_r2", 0.0)) + 1.0) / 2.0, 0.0, 1.0))
    rank_component = float(np.clip(float(diagnostics.get("rank_fraction", 0.0)), 0.0, 1.0))
    if method == "stoichiometric_singleton":
        base = 0.92
        score = base * (0.85 + 0.15 * smoothness)
    else:
        base = 0.35 + 0.35 * r2_component + 0.20 * rank_component
        score = base * (0.75 + 0.25 * smoothness)
    return {
        "method": method,
        "confidence": float(np.clip(score, 0.0, 1.0)),
        "smoothness": smoothness,
        "mean_abs_flux": float(np.mean(np.abs(values))) if values.size else 0.0,
        "max_abs_flux": float(np.max(np.abs(values))) if values.size else 0.0,
        "reaction": reaction,
    }


def infer_user_fluxes(
    exp_data: Mapping[str, Sequence[float]],
    exp_time: Sequence[float],
    stoichiometry: Optional[Mapping[str, Mapping[str, float]]] = None,
    *,
    time_grid: Optional[Sequence[float]] = None,
    reactions: Optional[Iterable[str]] = None,
    enforce_nonnegative: bool = True,
    reversible_reactions: Optional[Iterable[str]] = None,
) -> Dict[str, object]:
    """Infer per-reaction flux curves from measured concentration curves.

    Parameters
    ----------
    exp_data:
        Mapping of metabolite name to concentration series.
    exp_time:
        Time points aligned with every series in ``exp_data``.
    stoichiometry:
        Optional ``{reaction: {metabolite: coefficient}}`` map. Defaults to
        ``rbc_stoichiometry.STOICHIOMETRY``.
    time_grid:
        Optional strictly-increasing evaluation grid. Defaults to ``exp_time``.
    reactions:
        Optional reaction include-list. Defaults to every reaction touching at
        least one measured metabolite.
    enforce_nonnegative:
        If true, reactions not listed in ``reversible_reactions`` are bounded
        at zero during singleton propagation and least-squares solving.

    Returns
    -------
    dict
        JSON-friendly metadata plus NumPy arrays under ``curves``,
        ``derivatives`` and ``fluxes`` for downstream feature extraction.
    """

    active_stoichiometry = {
        _normalize_name(reaction): {_normalize_name(met): float(coeff) for met, coeff in coeffs.items()}
        for reaction, coeffs in (stoichiometry or rs.STOICHIOMETRY).items()
    }
    source_time, source_curves = _normalize_curves(exp_data, exp_time)
    grid, curves, derivatives = _interpolate_curves(source_time, source_curves, time_grid)
    metabolites = tuple(sorted(curves))
    reaction_names = _candidate_reactions(metabolites, active_stoichiometry, reactions)
    if not reaction_names:
        raise ValueError("No stoichiometric reactions touch the measured metabolites.")

    s_matrix = _stoichiometry_matrix(metabolites, reaction_names, active_stoichiometry)
    dcdt = np.vstack([derivatives[name] for name in metabolites])
    nonnegative = _nonnegative_reactions(reaction_names, reversible_reactions, enforce_nonnegative)

    resolved, methods, unresolved = _propagate_singletons(
        metabolites=metabolites,
        reactions=reaction_names,
        s_matrix=s_matrix,
        dcdt=dcdt,
        nonnegative=nonnegative,
    )
    _solve_remaining_fluxes(
        reactions=reaction_names,
        unresolved=unresolved,
        s_matrix=s_matrix,
        dcdt=dcdt,
        resolved=resolved,
        methods=methods,
        nonnegative=nonnegative,
    )

    fluxes = {reaction: np.asarray(resolved[reaction], dtype=float) for reaction in reaction_names}
    flux_matrix = np.vstack([fluxes[reaction] for reaction in reaction_names])
    diagnostics = _fit_diagnostics(s_matrix, flux_matrix, dcdt)
    confidence = {
        reaction: _confidence_payload(
            reaction=reaction,
            values=fluxes[reaction],
            method=methods.get(reaction, "bounded_lstsq"),
            diagnostics=diagnostics,
        )
        for reaction in reaction_names
    }

    return {
        "contract_type": "phase_b_flux_inference",
        "contract_version": 1,
        "time": grid,
        "metabolites": metabolites,
        "reactions": reaction_names,
        "curves": curves,
        "derivatives": derivatives,
        "fluxes": fluxes,
        "confidence": confidence,
        "diagnostics": diagnostics,
    }


__all__ = ["infer_user_fluxes"]
