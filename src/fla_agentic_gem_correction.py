"""Opt-in RBC-GEM 1.3.0 projections for the existing free, phase-aware ODE."""

import numpy as np

from fla_joint_calibration import JointRHS, rate_dependencies
from rbc_distinct_volume_transport import phase_matrix
from rbc_glut_only_transport import equadiff_glut_only
from reaction_positivity import limit_signed_fluxes, rbc_reaction_matrix


GEM_COMMIT = "43fd381d9eb8a8a4079629012362312960e1c009"
MODES = {
    "native": (),
    "catalase": ("VH2O2",),
    "redox": ("VH2O2", "VXAO", "VXAO2"),
    "redox_gssg_abc": ("VH2O2", "VXAO", "VXAO2", "VEGSSG"),
}

# Complete reduced columns, before phase scaling. CAT is expressed per H2O2
# consumed, preserving the meaning of the native peroxide disappearance rate.
_COLUMNS = {
    "VH2O2": ("CAT", {"H2O2": -1, "O2": 1}, {"H2O2": -1, "O2": .5}),
    "VXAO": ("XAO2", {"HYPX": -1, "XAN": 1, "H2O2": 1},
             {"HYPX": -1, "XAN": 1, "H2O2": 1, "O2": -1}),
    "VXAO2": ("XAO", {"XAN": -1, "URT": 1},
              {"XAN": -1, "URT": 1, "H2O2": 1, "O2": -1}),
    "VEGSSG": ("GTHOXABCte", {"GSSG": -1, "EGSSG": 1},
               {"GSSG": -1, "EGSSG": 1, "ATP": -1, "ADP": 1}),
}


class GemCorrectionRHS(JointRHS):
    """Same JointRHS contract; no parameter, state, or transport-law overrides.

    ``backend='joint'`` uses the existing fast rate extraction. ``'full'``
    obtains raw rates from the original ``equadiff_glut_only`` audit. Both
    execute the selected phase matrix with the native signed limiter and
    clamped pH. ``mode='native'`` is exact rollback to the selected backend.

    XAO and ABC options are conditional projections of existing rates, not
    new O2/MgATP kinetics. The limiter prevents substrate-negative execution;
    it is not a binding law. No branch or pool is added or removed.
    """

    def __init__(self, parameters, kinetics, *, mode="native", backend="joint",
                 hematocrit=.58, threshold=.001):
        if mode not in MODES:
            raise ValueError("unknown GEM correction mode")
        if backend not in ("joint", "full"):
            raise ValueError("GEM correction backend must be 'joint' or 'full'")
        super().__init__(parameters, kinetics, hematocrit=hematocrit, threshold=threshold)
        self.mode, self.backend, self.hematocrit = mode, backend, hematocrit
        sam_mode = self.parameters.get("sam_adenylate_stoichiometry", "biochemical_transfer")
        _, _, _, _, self.rate_volumes = phase_matrix(hematocrit, sam_mode)
        self.corrected_reactions = MODES[mode]
        self._forward_columns = [self.reactions.index(r) for r in self.corrected_reactions]
        if not self.corrected_reactions:
            return

        _, _, native_chemical = rbc_reaction_matrix(sam_mode)
        matrix = self.matrix.copy()
        dependencies = rate_dependencies(self.reactions)
        for reaction, j in zip(self.corrected_reactions, self._forward_columns):
            gem_id, before, after = _COLUMNS[reaction]
            if not np.array_equal(native_chemical[:, j], [before.get(p, 0) for p in self.names]):
                raise ValueError(f"native {reaction} changed; re-audit the {gem_id} projection")
            column = np.array([after.get(p, 0) for p in self.names])
            matrix[:, j] = column * self.rate_volumes[j] / self.volumes
            rows = np.flatnonzero(column)
            columns = sorted(dependencies[j] | set(rows))
            self.jacobian_sparsity[np.ix_(rows, columns)] = True
        matrix.setflags(write=False)
        self.matrix = matrix

    def _full(self, t, x, audit=None):
        return equadiff_glut_only(
            t, x, custom_params=self.parameters, glucose_kinetics=self.kinetics,
            hematocrit=self.hematocrit, numerical_audit=audit,
            ph_policy="clamped_diagnostic", positivity_policy="reaction_consistent",
            reaction_availability_threshold=self.threshold, curve_fit_strength=0.,
        )

    def rates(self, t, x):
        """Return aligned raw, executed and availability vectors (native rate basis)."""
        if self.backend == "joint":
            raw, executed, factors = super().rates(t, x)
        else:
            audit = {}
            self._full(t, x, audit)
            raw = np.array([audit["raw_fluxes"][r] for r in self.reactions])
            if not self.corrected_reactions:
                executed = np.array([audit["effective_fluxes"][r] for r in self.reactions])
                factors = np.array([audit["availability_factors"][r] for r in self.reactions])
                return raw, executed, factors
            executed, factors = limit_signed_fluxes(
                x[:len(self.names)], raw, self.matrix, threshold=self.threshold,
            )
        if np.any(raw[self._forward_columns] < 0.):
            raise ValueError("negative raw rate for an irreversible GEM correction")
        return raw, executed, factors

    def __call__(self, t, x):
        if self.backend == "full" and not self.corrected_reactions:
            return self._full(t, x)
        return super().__call__(t, x)
