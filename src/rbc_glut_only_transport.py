"""Opt-in GLUT-only successor; other native reaction laws and history stay intact."""

import numpy as np

from rbc_distinct_volume_transport import equadiff_distinct_volume, glut_import, number, phase_matrix
from reaction_positivity import limit_signed_fluxes

VERSION = "glut-only-free-network-diagnostic-2026.10.27"


def equadiff_glut_only(t, x, *, glucose_kinetics=None, hematocrit, custom_params=None,
                       numerical_audit=None, flux_tracker=None, ph_policy="clamped_diagnostic", **options):
    """Replace only native VEGLC before reaction-consistent flux execution.

    The no-override path delegates exactly to the archived phase-native model.
    GLC/EGLC are always read from the current ODE state, never source curves.
    """
    if ph_policy != "clamped_diagnostic":
        raise ValueError("retain the archived clamped pH diagnostic; no new acid/base model")
    if glucose_kinetics is not None:
        if not isinstance(glucose_kinetics, dict) or set(glucose_kinetics) != {"conductance", "km_i", "km_e"}:
            raise ValueError("only explicit GLUT conductance and two affinities are allowed")
        for key, value in glucose_kinetics.items():
            number(value, positive=key != "conductance")
    if glucose_kinetics is None:
        return equadiff_distinct_volume(t, x, mode="phase_native", hematocrit=hematocrit,
            custom_params=custom_params, numerical_audit=numerical_audit, flux_tracker=flux_tracker,
            ph_policy=ph_policy, **options)
    audit = {}
    derivative = equadiff_distinct_volume(t, x, mode="phase_native", hematocrit=hematocrit,
        custom_params=custom_params, numerical_audit=audit, ph_policy=ph_policy, **options)
    params = {} if custom_params is None else custom_params
    names, reactions, matrix, volumes, rate_volumes = phase_matrix(
        hematocrit, params.get("sam_adenylate_stoichiometry", "biochemical_transfer"))
    gi, ge = (float(x[names.index(pool)]) for pool in ("GLC", "EGLC"))
    # Same nonnegative substrate extension as the archived reversible adapter.
    # No state or derivative is clipped; one availability factor scales the net reaction.
    native = {**audit["raw_fluxes"], "VEGLC": glut_import(max(gi, 0.0), max(ge, 0.0), **glucose_kinetics)}
    raw = np.array([native[r] for r in reactions])
    threshold = options.get("reaction_availability_threshold", .001)
    effective, factors = limit_signed_fluxes(x[:113], raw, matrix, threshold=threshold)
    derivative[:113] = matrix @ effective
    executed = dict(zip(reactions, effective.tolist()))
    if numerical_audit is not None:
        numerical_audit.update({**audit, "version": VERSION, "mode": "phase_glut_only",
            "raw_fluxes": native, "effective_fluxes": executed,
            "availability_factors": dict(zip(reactions, factors.tolist())),
            "raw_derivative": matrix @ raw, "effective_derivative": derivative[:113].copy(),
            "executed_amount_rates_per_L_bag_day": rate_volumes*effective,
            "pool_volume_fractions": volumes.copy(), "reaction_volume_fractions": rate_volumes.copy(),
            "overridden_reactions": ["VEGLC"], "GLC_is_predicted_state": True,
            "GLUT_input_state_min_mM": min(gi, ge), "GLUT_substrate_extension_used": min(gi, ge) < 0,
            "VELAC_law": "unchanged_native", "MCT_activated": False})
    if flux_tracker is not None:
        flux_tracker.add_timepoint(t, executed)
    return derivative
