# Frozen-flux J1-J4 energy feasibility diagnostic

Use the sealed VSAM/PGK half-step original replays at both tolerances. No new
ODE, initial-state, parameter or source adjustment. Reconstruct three daily
raw/executed extent ledgers and all113 concentration balances. Compare actual
J1/J4 ATP, ADP and AMP and derived H=ATP+0.5*ADP and total adenylates A. H is a
linear diagnostic, not an independent measurement or thermodynamic energy.

Reconstruct the PGK availability factor from consuming pools B13PG and ADP at
Gauss nodes. Attribute raw-minus-executed PGK to the limiting pool, splitting
ties equally. The raw envelope is a frozen-state diagnostic, not recoverable
production or a proposed relaxation of positivity.

LP variables are daily nonnegative deviations along PGK-up, NDPK-forward-down
and PRPPASe-down. All other flux extents and the archived negative component
of NDPK stay fixed. Demand reductions cannot exceed the integral of positive
net rate (not the unobservable gross forward rate). Scenarios: fixed, PGK up
to archived raw, two demands down, combined, and combined with the PGK raw
ceiling removed. The last is deliberately optimistic, not a kinetic scenario.

Predict hypothetical daily endpoints by adding cumulative stoichiometric
deviations to the archived ODE states; preserve all nonnegative stocks at
J2/J3/J4. The unchanged baseline quadrature residual remains an audit error,
not a free source. Daily endpoint feasibility does not imply an admissible
trajectory inside an interval. At J4, minimize the maximum ATP/ADP/AMP residual
in the existing working bands (absolute part from J4/J8/J11/J15, relative part
from J4). Also maximize H with stocks only and with additional off-target
guards. Off-target guards reuse the previous 1% allowance on squared working
residual, now evaluated on J4 only, on50 canonical nonadenylate channels.
B13PG and P2G remain recorded source aliases, not independent constraints.
Glucose/lactate extents are frozen, preserving their balances but not fixing
the pre-existing observation mismatch. Latent PRPP/GTP and other stocks are
model-conditional, not measured constraints. No invented assay variance.

Check primal/dual witnesses and derive ADP and H upper bounds independently
from the relevant matrix rows and nonnegative stocks. Admit no kinetic lever
unless a nonbaseline scenario fits the joint adenylates within unit bands at
both tolerances while preserving the off-target and stock constraints. Such
a pass would still require kinetic justification and a separate free replay.

Read the existing source-verified Yurkovich 4C extracts, keep actual storage
times and sheet-specific replicate blocks. Compare descriptive J1-to-J4
changes per channel within each sheet; no ATP cross-sheet join, energy charge,
cross-cohort scaling, absolute anchor, or training import. ATP endo/exo and
free/total identity remain unresolved.
