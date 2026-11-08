"""Explicit C4/folate/redox hypotheses, isolated from historical FLA defaults.

Added pools need declared initial values. New rates need explicit kinetics;
protein detection is not a rate constant or an active redox concentration.
"""

from functools import lru_cache
import math

import numpy as np

from equadiff_brodbar import equadiff_brodbar
from rbc_gem_network import diagnostic_matrix, equadiff_rbc_gem
from reaction_positivity import limit_signed_fluxes

VERSION = "airbc-biochemical-diagnostic-2026.10.06-v1"
MODES = ("historical", "vcse_c4", "folate_split", "vcse_folate")
NEW_POOLS = ("AKB", "MLTHF", "CYB5OX", "CYB5RED", "HBFE3", "HBFE2",
             "TXNOX", "TXNRED", "PRDXRED", "PRDXSO", "PRDXOX")
BRANCHES = {
    "VMTHFR": {"substrates": ("MLTHF", "NADPH"),
               "stoichiometry": {"MLTHF": -1, "NADPH": -1, "MTHF": 1, "NADP": 1}},
    "VCYB5R": {"substrates": ("NADH", "CYB5OX"),
               "stoichiometry": {"NADH": -1, "CYB5OX": -2, "NAD": 1, "CYB5RED": 2}},
    "VMETHB_RED": {"substrates": ("CYB5RED", "HBFE3"),
                   "stoichiometry": {"CYB5RED": -1, "HBFE3": -1, "CYB5OX": 1, "HBFE2": 1}},
    "VTRXR": {"substrates": ("NADPH", "TXNOX"),
              "stoichiometry": {"NADPH": -1, "TXNOX": -1, "NADP": 1, "TXNRED": 1}},
    "VPRDX_PEROX": {"substrates": ("PRDXRED", "H2O2"),
                    "stoichiometry": {"PRDXRED": -1, "H2O2": -1, "PRDXSO": 1}},
    "VPRDX_RESOLVE": {"substrates": ("PRDXSO",),
                      "stoichiometry": {"PRDXSO": -1, "PRDXOX": 1}},
    "VPRDX_REDUCE": {"substrates": ("PRDXOX", "TXNRED"),
                     "stoichiometry": {"PRDXOX": -1, "TXNRED": -1, "PRDXRED": 1, "TXNOX": 1}},
}
REDOX_GROUPS = (("VCYB5R", "VMETHB_RED"),
                ("VTRXR", "VPRDX_PEROX", "VPRDX_RESOLVE", "VPRDX_REDUCE"))


def _number(value, *, positive=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or (value <= 0 if positive else value < 0)):
        raise ValueError("Explicit finite nonnegative value (positive for Km) required")
    return float(value)


def split_enabled(mode):
    return mode in ("folate_split", "vcse_folate")


@lru_cache(maxsize=8, typed=True)
def biochemical_matrix(mode, sam_mode="biochemical_transfer", abc_exports=False):
    if mode not in MODES[1:]:
        raise ValueError("An explicit biochemical diagnostic mode is required")
    if not isinstance(abc_exports, bool):
        raise ValueError("abc_exports must be boolean")
    old_names, old_reactions, old_matrix = diagnostic_matrix("redox_stoichiometry", sam_mode)
    names = list(old_names)
    if split_enabled(mode):
        names[47] = "MTHF"
    names = tuple(names) + NEW_POOLS
    reactions = old_reactions + tuple(BRANCHES)
    matrix = np.zeros((len(names), len(reactions)))
    matrix[:113, :len(old_reactions)] = old_matrix
    if mode in ("vcse_c4", "vcse_folate"):
        column = reactions.index("VCSE")
        matrix[names.index("AKG"), column] = 0
        matrix[names.index("AKB"), column] = 1
    if split_enabled(mode):
        column = reactions.index("VSHMT")
        matrix[names.index("MTHF"), column] = 0
        matrix[names.index("MLTHF"), column] = 1
    if abc_exports:
        for reaction in ("VEGSSG", "VEURT"):
            matrix[names.index("ATP"), reactions.index(reaction)] = -1
            matrix[names.index("ADP"), reactions.index(reaction)] = 1
    for reaction, definition in BRANCHES.items():
        if reaction == "VMTHFR" and not split_enabled(mode):
            continue
        for name, value in definition["stoichiometry"].items():
            matrix[names.index(name), reactions.index(reaction)] = value
    matrix.setflags(write=False)
    return names, reactions, matrix


def build_initial_state(historical, *, mode, added_initial, folate_partition=None):
    """Keep all old pools except an explicitly declared partition of latent METTHF.

    HBFE3/HBFE2 are mM heme sites, not Hb tetramers. CYB5/PRDX/TXN pools
    are available redox sites on the same volume basis, not bulk proteomics.
    """
    names, _, _ = biochemical_matrix(mode)
    old = np.asarray(historical, dtype=float)
    if old.shape != (114,) or not np.all(np.isfinite(old)) or np.any(old[:113] < 0):
        raise ValueError("A finite nonnegative historical 113-pool + pHi state is required")
    required = set(NEW_POOLS) - {"MLTHF"}
    if not isinstance(added_initial, dict) or set(added_initial) != required:
        raise ValueError("Every added C4 and redox pool must have an explicit initial value")
    result = np.r_[old[:113], np.zeros(len(NEW_POOLS)), old[-1]]
    for name, value in added_initial.items():
        result[names.index(name)] = _number(value)
    if split_enabled(mode):
        if not isinstance(folate_partition, dict) or set(folate_partition) != {"MTHF", "MLTHF"}:
            raise ValueError("Explicit MTHF/MLTHF partition required; no alias or automatic split")
        methyl, methylene = (_number(folate_partition[key]) for key in ("MTHF", "MLTHF"))
        if not math.isclose(methyl + methylene, old[47], rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("The conditional split must preserve the old latent folate total")
        result[47], result[names.index("MLTHF")] = methyl, methylene
    elif folate_partition is not None:
        raise ValueError("Folate partition requires a split-folate mode")
    return result


def extension_rates(states, names, kinetics=None):
    kinetics = {} if kinetics is None else kinetics
    if not isinstance(kinetics, dict) or set(kinetics).difference(BRANCHES):
        raise ValueError("Unknown biochemical branch")
    if "VMTHFR" in kinetics and "MTHF" not in names:
        raise ValueError("MTHFR requires explicitly separated folates")
    for group in REDOX_GROUPS:
        if set(group).intersection(kinetics) and not set(group).issubset(kinetics):
            raise ValueError("Redox modules require the complete acceptor/regeneration chain")
    values = np.asarray(states, dtype=float)
    if values.shape != (len(names),) or not np.all(np.isfinite(values)):
        raise ValueError("Finite states must match the extended pool registry")
    rates = {name: 0.0 for name in BRANCHES}
    for reaction, parameters in kinetics.items():
        substrates = BRANCHES[reaction]["substrates"]
        if not isinstance(parameters, dict) or set(parameters) != {"vmax", *("km_" + s for s in substrates)}:
            raise ValueError("Explicit vmax and every substrate Km are required")
        rate = _number(parameters["vmax"])
        for substrate in substrates:
            km = _number(parameters["km_" + substrate], positive=True)
            concentration = max(float(values[names.index(substrate)]), 0)
            rate *= concentration / (km + concentration)
        rates[reaction] = rate
    return rates


def equadiff_biochemical(t, x, *, network_mode="historical", extension_kinetics=None,
                         oplah_policy="retained", abc_exports=False, custom_params=None,
                         numerical_audit=None, flux_tracker=None, **ode_options):
    """Evaluate an opt-in extended network; OPLAH is never deleted by default."""
    if network_mode not in MODES or oplah_policy not in ("retained", "diagnostic_off"):
        raise ValueError("Unknown biochemical mode or OPLAH policy")
    if network_mode == "historical":
        if extension_kinetics or oplah_policy != "retained" or abc_exports is not False:
            raise ValueError("Historical mode forbids network changes")
        return equadiff_brodbar(t, x, custom_params=custom_params, numerical_audit=numerical_audit,
                               flux_tracker=flux_tracker, **ode_options)
    if ode_options.get("positivity_policy", "reaction_consistent") != "reaction_consistent":
        raise ValueError("Biochemical diagnostics require reaction_consistent positivity")
    if ode_options.get("curve_fit_strength", 0.0) != 0:
        raise ValueError("Observation forcing is forbidden")
    params = {} if custom_params is None else custom_params
    names, reactions, matrix = biochemical_matrix(network_mode, params.get(
        "sam_adenylate_stoichiometry", "biochemical_transfer"), abc_exports)
    states = np.asarray(x, dtype=float)
    if states.shape != (len(names) + 1,) or not np.all(np.isfinite(states)):
        raise ValueError("Explicit extended concentrations + trailing pHi required")
    added = extension_rates(states[:-1], names, extension_kinetics)
    historical_state = np.r_[states[:113], states[-1]]
    options = {**ode_options, "positivity_policy": "reaction_consistent", "curve_fit_strength": 0.0}
    audit = {}
    old_derivative = equadiff_rbc_gem(t, historical_state, network_mode="redox_stoichiometry",
                                    custom_params=custom_params, numerical_audit=audit, **options)
    native = {**audit["raw_fluxes"], **added}
    if oplah_policy == "diagnostic_off":
        native["VOPLAH"] = 0.0
    # The historical rate is conditional on its unvalidated Km; enforce true zero methyl substrate.
    if split_enabled(network_mode) and states[47] <= 0:
        native["VMESE"] = 0.0
    raw = np.array([native[reaction] for reaction in reactions])
    effective, factors = limit_signed_fluxes(states[:-1], raw, matrix,
                                            threshold=audit["availability_threshold_mM"])
    derivative = np.r_[matrix @ effective, old_derivative[-1]]
    effective_dict = dict(zip(reactions, effective.tolist()))
    if numerical_audit is not None:
        numerical_audit.update({"version": VERSION, "network_mode": network_mode,
                                "oplah_policy": oplah_policy, "abc_exports": abc_exports,
                                "raw_fluxes": native, "effective_fluxes": effective_dict,
                                "availability_factors": dict(zip(reactions, factors.tolist())),
                                "raw_derivative": matrix @ raw, "effective_derivative": matrix @ effective,
                                "availability_threshold_mM": audit["availability_threshold_mM"],
                                "new_branches_enabled": sorted(extension_kinetics or {}),
                                "pH_extension_protons_modeled": False, "biological_promotion": False})
    if flux_tracker is not None:
        flux_tracker.add_timepoint(t, {**effective_dict, "pHi": float(states[-1])})
    return derivative
