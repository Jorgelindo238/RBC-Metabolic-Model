"""Opt-in limiting of complete signed reactions, not individual pool derivatives."""

from functools import lru_cache

import numpy as np


REACTION_POSITIVITY_VERSION = "reaction-consistent-v2-explicit-threshold-2026.10.05"


def limit_signed_fluxes(states, fluxes, matrix, *, threshold):
    """Return limited net rates and one availability factor per reaction.

    A positive rate consumes negative columns of S; a negative rate consumes
    positive columns. At a zero boundary, all outgoing net rates vanish.
    This does not reconstruct forward/reverse gross exchange from a net rate.
    """
    x, v, s = (np.asarray(value, dtype=float) for value in (states, fluxes, matrix))
    if x.ndim != 1 or v.ndim != 1 or s.shape != (x.size, v.size):
        raise ValueError("states, signed fluxes and stoichiometry must align")
    if any(not np.all(np.isfinite(value)) for value in (x, v, s)):
        raise ValueError("reaction positivity inputs must be finite")
    if not np.isfinite(threshold) or threshold <= 0.0:
        raise ValueError("availability threshold must be finite and positive")
    availability = np.clip(x / threshold, 0.0, 1.0)
    consuming = ((s < 0.0) & (v > 0.0)) | ((s > 0.0) & (v < 0.0))
    factors = np.min(np.where(consuming, availability[:, None], 1.0), axis=0)
    return v * factors, factors


@lru_cache(maxsize=2)
def rbc_reaction_matrix(sam_mode="biochemical_transfer"):
    # Delay imports until the ODE module is fully initialized.
    from equadiff_brodbar import BRODBAR_METABOLITE_MAP, NUM_BASE_METABOLITES
    from rbc_stoichiometry import STOICHIOMETRY

    if sam_mode not in {"biochemical_transfer", "legacy_amp_coproduct"}:
        raise ValueError("unknown SAM stoichiometric mode")
    names = tuple(name for name, index in sorted(BRODBAR_METABOLITE_MAP.items(), key=lambda item: item[1])
                  if index < NUM_BASE_METABOLITES)
    if len(names) != NUM_BASE_METABOLITES:
        raise ValueError("concentration registry does not span the RBC matrix")
    reactions = tuple(sorted(STOICHIOMETRY))
    matrix = np.asarray([[STOICHIOMETRY[reaction].get(name, 0.0) for reaction in reactions]
                         for name in names], dtype=float)
    if sam_mode == "legacy_amp_coproduct":
        matrix[names.index("AMP"), reactions.index("VSAM")] += 1.0
    matrix.setflags(write=False)
    return names, reactions, matrix


def limit_rbc_reactions(states, native_rates, native_derivative, *, threshold, sam_mode):
    """Check source parity before using the matrix to execute limited reactions."""
    _, reactions, matrix = rbc_reaction_matrix(sam_mode)
    missing = set(reactions).difference(native_rates)
    if missing:
        raise ValueError(f"missing native rates for reaction positivity: {sorted(missing)}")
    raw = np.asarray([native_rates[name] for name in reactions], dtype=float)
    limited, factors = limit_signed_fluxes(states, raw, matrix, threshold=threshold)
    raw_derivative = matrix @ raw
    if not np.allclose(raw_derivative, native_derivative, rtol=1e-12, atol=1e-10):
        raise ValueError("native ODE and reaction positivity matrix disagree")
    return {
        "version": REACTION_POSITIVITY_VERSION,
        "availability_threshold_mM": float(threshold),
        "raw_fluxes": dict(zip(reactions, raw.tolist())),
        "effective_fluxes": dict(zip(reactions, limited.tolist())),
        "availability_factors": dict(zip(reactions, factors.tolist())),
        "raw_derivative": raw_derivative,
        "effective_derivative": matrix @ limited,
    }
