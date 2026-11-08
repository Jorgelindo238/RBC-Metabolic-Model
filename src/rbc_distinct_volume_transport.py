"""Opt-in phase-volume and reversible-carrier diagnostics; legacy stays intact."""

from functools import lru_cache
import math

import numpy as np

from equadiff_brodbar import equadiff_brodbar
from rbc_gem_audit import EXTERNAL_POOLS
from reaction_positivity import limit_signed_fluxes, rbc_reaction_matrix

VERSION = "distinct-phase-volume-diagnostic-2026.10.06-v1"
EXTERNAL_ONLY = {"VECYT", "VEGSH_deg", "VEGSSG_deg"}
SUPERNATANT_RATES = {"VEGSH_deg", "VEGSSG_deg"}


def number(value, *, positive=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float, np.number))
            or not math.isfinite(value) or (value <= 0 if positive else value < 0)):
        raise ValueError("finite nonnegative numeric value required, positive for scales")
    return float(value)


def volume_fractions(h):
    h = number(h, positive=True)
    if h >= 1:
        raise ValueError("hematocrit must lie strictly between zero and one")
    return h, 1 - h


def glut_import(gi, ge, *, conductance, km_i, km_e):
    gi, ge = number(gi), number(ge)
    k = number(conductance)
    ki, ke = number(km_i, positive=True), number(km_e, positive=True)
    return k * (ge - gi) / (1 + ge / ke + gi / ki)


def mct_export(li, le, *, phi, phe, conductance, km_i, km_e, ph_reference):
    li, le = number(li), number(le)
    ph = [number(p, positive=True) for p in (phi, phe, ph_reference)]
    if any(p > 14 for p in ph):
        raise ValueError("pH outside diagnostic domain")
    hi, he = 10 ** (ph[2] - ph[0]), 10 ** (ph[2] - ph[1])
    k = number(conductance)
    ki, ke = number(km_i, positive=True), number(km_e, positive=True)
    return k * (li * hi - le * he) / (1 + li / ki + le / ke)


@lru_cache(maxsize=8)
def phase_matrix(h, sam_mode="biochemical_transfer"):
    vi, ve = volume_fractions(h)
    names, reactions, s = rbc_reaction_matrix(sam_mode)
    volumes = np.array([ve if p in EXTERNAL_POOLS else vi for p in names])
    ext_only = {r for j, r in enumerate(reactions)
                if np.any(s[:, j]) and all(p in EXTERNAL_POOLS for p, coefficient in zip(names, s[:, j]) if coefficient)}
    if ext_only != EXTERNAL_ONLY:
        raise ValueError("external-only rate registry changed; declare its volume basis")
    # Reaction extents are cell-normalized except explicit extracellular-only processes.
    # VECYT is membrane transport from a buffered intracellular CYT, not fluid degradation.
    rate_volumes = np.array([ve if r in SUPERNATANT_RATES else vi for r in reactions])
    a = s * rate_volumes[None, :] / volumes[:, None]
    for value in (volumes, rate_volumes, a):
        value.setflags(write=False)
    return names, reactions, a, volumes, rate_volumes


def reversible_rates(x, kinetics, *, phe):
    if not isinstance(kinetics, dict) or set(kinetics) != {"glucose", "lactate", "ph_reference"}:
        raise ValueError("explicit glucose/lactate kinetics and pH reference required")
    for key in ("glucose", "lactate"):
        if not isinstance(kinetics[key], dict) or set(kinetics[key]) != {"conductance", "km_i", "km_e"}:
            raise ValueError("explicit conductance and two Km required")
    return {
        "VEGLC": glut_import(max(x[0], 0), max(x[85], 0), **kinetics["glucose"]),
        "VELAC": mct_export(max(x[19], 0), max(x[87], 0), phi=x[113], phe=phe,
                            ph_reference=kinetics["ph_reference"], **kinetics["lactate"]),
    }


def equadiff_distinct_volume(t, x, *, mode="historical", hematocrit=None,
                            transport_kinetics=None, phe=None, ph_policy="native",
                            custom_params=None, numerical_audit=None, flux_tracker=None,
                            **ode_options):
    """All 113 pool balances share a declared extent basis in phase modes.

    Only constant geometry is supported. Clamped pH represents a diagnostic
    buffer reservoir; its proton exchange is a ledger, not a free pH prediction.
    No source-observation conversion, fitting, or default migration occurs here.
    """
    if mode not in ("historical", "phase_native", "phase_glut_mct") or ph_policy not in ("native", "clamped_diagnostic"):
        raise ValueError("unknown diagnostic mode or pH policy")
    if mode == "historical":
        if hematocrit is not None or transport_kinetics is not None or phe is not None:
            raise ValueError("historical replay forbids new geometry or carrier inputs")
        d = equadiff_brodbar(t, x, custom_params=custom_params, numerical_audit=numerical_audit,
                            flux_tracker=flux_tracker, **ode_options)
        if ph_policy == "clamped_diagnostic":
            d[113] = 0
        return d
    if np.shape(x) != (114,) or not np.all(np.isfinite(x)):
        raise ValueError("114 finite historical state coordinates required")
    if ode_options.get("positivity_policy", "reaction_consistent") != "reaction_consistent" or ode_options.get("curve_fit_strength", 0) != 0:
        raise ValueError("phase diagnostics require unforced reaction_consistent execution")
    if ph_policy != "clamped_diagnostic":
        raise ValueError("phase transport currently requires an explicit clamped pH diagnostic")
    if mode == "phase_glut_mct":
        carriers = reversible_rates(x, transport_kinetics, phe=phe)
    else:
        if transport_kinetics is not None or phe is not None:
            raise ValueError("native transport forbids unused new carrier parameters")
        carriers = {}
    params = {} if custom_params is None else custom_params
    if any(key.startswith("kinetic_family_") and value == "teacher_curve" for key, value in params.items()):
        raise ValueError("phase diagnostics forbid teacher-forced carrier rates")
    names, reactions, matrix, volumes, rate_volumes = phase_matrix(
        hematocrit, params.get("sam_adenylate_stoichiometry", "biochemical_transfer"))
    old_audit = {}
    options = {**ode_options, "positivity_policy": "reaction_consistent", "curve_fit_strength": 0}
    derivative = equadiff_brodbar(t, x, custom_params=params, numerical_audit=old_audit, **options)
    native = {**old_audit["raw_fluxes"], **carriers}
    raw = np.array([native[r] for r in reactions])
    effective, factors = limit_signed_fluxes(x[:113], raw, matrix,
                                            threshold=old_audit["availability_threshold_mM"])
    derivative[:113] = matrix @ effective
    derivative[113] = 0
    executed = dict(zip(reactions, effective.tolist()))
    if numerical_audit is not None:
        numerical_audit.update({"version": VERSION, "mode": mode, "hematocrit": hematocrit,
            "raw_fluxes": native, "effective_fluxes": executed,
            "availability_factors": dict(zip(reactions, factors.tolist())),
            "raw_derivative": matrix @ raw, "effective_derivative": derivative[:113].copy(),
            "pool_volume_fractions": volumes.copy(), "reaction_volume_fractions": rate_volumes.copy(),
            "executed_amount_rates_per_L_bag_day": rate_volumes * effective,
            "MCT_proton_export_per_L_bag_day": hematocrit * executed["VELAC"] if carriers else None,
            "pH_policy": ph_policy, "free_pH_prediction": False,
            "source_normalization_verified": False, "biological_promotion": False})
    if flux_tracker is not None:
        flux_tracker.add_timepoint(t, executed)
    return derivative
