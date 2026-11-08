"""Opt-in phase-aware citrate/arginine branches; no invented kinetic defaults."""

import copy
import numpy as np

from fla_joint_calibration import JointRHS
from equadiff_brodbar import MAX_DERIVATIVE
from reaction_positivity import limit_signed_fluxes

BRANCHES = {
    "VACLY": {"gem_id": "ACITL", "gene": "ACLY", "substrates": ("CIT", "ATP", "COA"),
        "stoichiometry": {"CIT": -1., "ATP": -1., "COA": -1., "ACCOA": 1., "OAA": 1., "ADP": 1.}},
    "VARGN": {"gem_id": "ARGN", "gene": "ARG1", "substrates": ("ARG",),
        "stoichiometry": {"ARG": -1., "ORN": 1., "UREA": 1.}},
}


def branch_rates(state, names, kinetics):
    if not isinstance(kinetics, dict) or set(kinetics)-set(BRANCHES): raise ValueError("unknown coverage branch")
    x = np.asarray(state, float)
    if x.shape not in ((len(names),), (len(names)+1,)) or not np.all(np.isfinite(x)):
        raise ValueError("finite aligned branch state required")
    result = {r: 0. for r in BRANCHES}
    for reaction, params in kinetics.items():
        required = {"vmax"}|{"km_"+p for p in BRANCHES[reaction]["substrates"]}
        if not isinstance(params, dict) or set(params) != required: raise ValueError("explicit vmax and substrate Km required")
        for key, value in params.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value) or (value < 0 if key == "vmax" else value <= 0):
                raise ValueError("nonnegative capacity and positive Km required")
        rate = params["vmax"]
        for p in BRANCHES[reaction]["substrates"]:
            concentration = max(float(x[names.index(p)]), 0.)
            rate *= concentration/(params["km_"+p]+concentration)
        result[reaction] = float(rate)
    return result


def extend_matrix(names, reactions, matrix, *, enabled):
    if len(set(enabled)) != len(enabled) or set(enabled)-set(BRANCHES): raise ValueError("unique known branches required")
    if set(enabled)&set(reactions): raise ValueError("branch already present; do not duplicate capacity")
    columns = []
    for r in enabled:
        column = np.zeros(len(names))
        for p, value in BRANCHES[r]["stoichiometry"].items(): column[names.index(p)] = value
        columns.append(column)
    return tuple(reactions)+tuple(enabled), np.column_stack([matrix, *columns]) if columns else np.array(matrix, copy=True)


class CoverageRHS:
    """Adds only declared reactions, retaining native OPLAH/transport/IC policies."""

    def __init__(self, parameters, glucose_kinetics, *, branch_kinetics=None, hematocrit=.58, threshold=.001):
        self.native = JointRHS(parameters, glucose_kinetics, hematocrit=hematocrit, threshold=threshold)
        self.names = self.native.names
        self.branch_kinetics = copy.deepcopy({} if branch_kinetics is None else branch_kinetics)
        branch_rates(np.ones(len(self.names)), self.names, self.branch_kinetics)
        self.enabled = tuple(r for r in BRANCHES if r in self.branch_kinetics and self.branch_kinetics[r]["vmax"] > 0)
        self.reactions, self.matrix = extend_matrix(self.names, self.native.reactions, self.native.matrix, enabled=self.enabled)
        self.threshold = threshold
        self.jacobian_sparsity = self.native.jacobian_sparsity.copy()
        for r in self.enabled:
            affected = [self.names.index(p) for p in BRANCHES[r]["stoichiometry"]]
            dependencies = [self.names.index(p) for p in BRANCHES[r]["substrates"]]
            self.jacobian_sparsity[np.ix_(affected, dependencies)] = True

    def rates(self, t, state):
        raw, executed, factors = self.native.rates(t, state)
        if not self.enabled: return raw, executed, factors
        additions = branch_rates(state, self.names, self.branch_kinetics)
        raw = np.r_[raw, [additions[r] for r in self.enabled]]
        executed, factors = limit_signed_fluxes(np.asarray(state)[:113], raw, self.matrix, threshold=self.threshold)
        return raw, executed, factors

    def __call__(self, t, state):
        if not self.enabled: return self.native(t, state)
        _, executed, _ = self.rates(t, state)
        derivative = np.r_[self.matrix@executed, 0.]
        if not np.all(np.isfinite(derivative)) or np.max(np.abs(derivative[:113])) > MAX_DERIVATIVE:
            raise ValueError("invalid coverage derivative; no clipping")
        return derivative
