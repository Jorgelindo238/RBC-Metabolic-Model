"""Reversible RBC-GEM structural diagnostics around the unchanged historical ODE.

No production default, initial condition, or fitted constant is migrated.
New enzyme branches require explicit kinetics and are disabled otherwise.
"""

from functools import lru_cache
import math

import numpy as np

from equadiff_brodbar import NONEG_THRESHOLD, NUM_BASE_METABOLITES, equadiff_brodbar
from reaction_positivity import limit_signed_fluxes, rbc_reaction_matrix


NETWORK_VERSION = "airbc-rbc-gem-diagnostic-2026.10.06-v1"
MODES = ("historical", "redox_stoichiometry", "rbc_gem_core")
BRANCHES = {
    "VARGN": {"gem_id": "ARGN", "stoichiometry": {"ARG": -1, "ORN": 1, "UREA": 1},
              "substrates": ("ARG",)},
    "VXPPT": {"gem_id": "XPPT", "stoichiometry": {"XAN": -1, "PRPP": -1, "XMP": 1},
              "substrates": ("XAN", "PRPP")},
    "VACYP": {"gem_id": "ACYP", "stoichiometry": {"B13PG": -1, "P3G": 1},
              "substrates": ("B13PG",)},
    "VGMPR": {"gem_id": "GMPR", "stoichiometry": {"GMP": -1, "NADPH": -1,
                                                  "IMP": 1, "NADP": 1, "NH4": 1},
              "substrates": ("GMP", "NADPH")},
    "VGSR_NADH": {"gem_id": "GTHOx", "stoichiometry": {"GSSG": -1, "NADH": -1,
                                                        "GSH": 2, "NAD": 1},
                  "substrates": ("GSSG", "NADH")},
}


class _Capture:
    def add_timepoint(self, time, fluxes):
        self.fluxes = dict(fluxes)


@lru_cache(maxsize=4)
def diagnostic_matrix(mode, sam_mode="biochemical_transfer"):
    if mode not in MODES[1:]:
        raise ValueError("diagnostic matrix requires an explicit RBC-GEM mode")
    names, original_reactions, original = rbc_reaction_matrix(sam_mode)
    reactions = original_reactions + tuple(BRANCHES)
    matrix = np.column_stack((original, np.zeros((len(names), len(BRANCHES)))))
    matrix[names.index("O2"), reactions.index("VH2O2")] = 0.5
    for reaction in ("VXAO", "VXAO2"):
        matrix[names.index("O2"), reactions.index(reaction)] = -1.0
        matrix[names.index("H2O2"), reactions.index(reaction)] = 1.0
    if mode == "rbc_gem_core":
        for reaction in ("VEGSSG", "VEURT"):
            matrix[names.index("ATP"), reactions.index(reaction)] = -1.0
            matrix[names.index("ADP"), reactions.index(reaction)] = 1.0
    for reaction, definition in BRANCHES.items():
        for name, value in definition["stoichiometry"].items():
            matrix[names.index(name), reactions.index(reaction)] = value
    matrix.setflags(write=False)
    return names, reactions, matrix


def branch_rates(states, names, kinetics=None):
    kinetics = {} if kinetics is None else kinetics
    if not isinstance(kinetics, dict) or set(kinetics).difference(BRANCHES):
        raise ValueError("unknown RBC-GEM kinetic branch")
    x = np.asarray(states, dtype=float)
    if x.shape != (len(names),) or not np.all(np.isfinite(x)):
        raise ValueError("branch states must be finite and match the pool registry")
    rates = {reaction: 0.0 for reaction in BRANCHES}
    for reaction, parameters in kinetics.items():
        definition = BRANCHES[reaction]
        required = {"vmax"} | {"km_" + name for name in definition["substrates"]}
        if not isinstance(parameters, dict) or set(parameters) != required:
            raise ValueError(f"explicit vmax and substrate Km required for {reaction}")
        for name, value in parameters.items():
            if (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                    or (value < 0 if name == "vmax" else value <= 0)):
                raise ValueError("finite nonnegative vmax and positive Km required")
        rate = float(parameters["vmax"])
        for name in definition["substrates"]:
            value = max(float(x[names.index(name)]), 0.0)
            rate *= value / (parameters["km_" + name] + value)
        rates[reaction] = rate
    return rates


def equadiff_rbc_gem(t, x, *, network_mode="historical", branch_kinetics=None,
                     custom_params=None, numerical_audit=None, flux_tracker=None,
                     **ode_options):
    """Execute a declared structural hypothesis with coherent reaction limiting.

    Historical mode forwards exactly to the old kernel. Redox mode corrects
    only CAT/XAO stoichiometry. Core mode also excludes OPLAH and couples
    GSSG/urate ABC export to ATP. Neither adds an ATP-producing source.
    Water/Pi/PPi remain omitted; this is a reduced-pool diagnostic, not a GEM.
    """
    if network_mode not in MODES:
        raise ValueError("unknown RBC-GEM network mode")
    if network_mode == "historical":
        if branch_kinetics:
            raise ValueError("historical mode forbids added branches")
        return equadiff_brodbar(t, x, custom_params=custom_params, numerical_audit=numerical_audit,
                               flux_tracker=flux_tracker, **ode_options)
    if ode_options.get("positivity_policy", "reaction_consistent") != "reaction_consistent":
        raise ValueError("structural diagnostics require reaction_consistent positivity")
    if ode_options.get("curve_fit_strength", 0.0) != 0.0:
        raise ValueError("structural diagnostics forbid observation forcing")
    params = {} if custom_params is None else custom_params
    sam_mode = params.get("sam_adenylate_stoichiometry", "biochemical_transfer")
    names, reactions, matrix = diagnostic_matrix(network_mode, sam_mode)
    # Validate the new kinetic contract before invoking any trackers.
    added_rates = branch_rates(np.asarray(x)[:NUM_BASE_METABOLITES], names, branch_kinetics)
    options = {**ode_options, "positivity_policy": "reaction_consistent", "curve_fit_strength": 0.0}
    threshold = options.get("reaction_availability_threshold")
    threshold = NONEG_THRESHOLD if threshold is None else threshold
    audit, capture = {}, _Capture()
    derivative = equadiff_brodbar(t, x, custom_params=custom_params, numerical_audit=audit,
                                flux_tracker=capture, **options)
    native = {**audit["raw_fluxes"], **added_rates}
    if network_mode == "rbc_gem_core":
        native["VOPLAH"] = 0.0
    raw = np.asarray([native[name] for name in reactions])
    effective, factors = limit_signed_fluxes(np.asarray(x)[:NUM_BASE_METABOLITES], raw,
                                            matrix, threshold=threshold)
    derivative[:NUM_BASE_METABOLITES] = matrix @ effective
    effective_dict = dict(zip(reactions, effective.tolist()))
    if numerical_audit is not None:
        numerical_audit.update({
            "version": NETWORK_VERSION, "network_mode": network_mode,
            "availability_threshold_mM": float(threshold),
            "raw_fluxes": native, "effective_fluxes": effective_dict,
            "availability_factors": dict(zip(reactions, factors.tolist())),
            "raw_derivative": matrix @ raw, "effective_derivative": matrix @ effective,
            "historical_same_state_raw_fluxes": audit["raw_fluxes"],
            "disabled_reactions": ["VOPLAH"] if network_mode == "rbc_gem_core" else [],
            "new_branches_enabled": sorted(branch_kinetics or {}),
            "biological_promotion": False,
        })
    if flux_tracker is not None:
        flux_tracker.add_timepoint(t, {**capture.fluxes, **effective_dict})
    return derivative
