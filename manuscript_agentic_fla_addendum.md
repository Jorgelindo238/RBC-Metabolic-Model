# Agentic FLA: reduced-network calibration and Vmax optimization

Draft Methods addendum for the AIRBC manuscript. The earlier manuscript is
kept unchanged because it is a protected input of the fixed RBC-GEM audit.
This section describes an executed pilot design, not biological validation.

## Agent responsibilities and acceptance

We extended Flux Learning Analysis (FLA) with a supervised agent workflow for
calibration and enzymatic-capacity optimization. Three specialist agents
worked in parallel: (1) attribution of executed ATP demand and compartmental
balances, (2) curation of the reduced stoichiometric network against pinned
RBC-GEM, and (3) implementation and testing of a bounded Vmax-only search.
The controller registered the numerical experiment and reconciled their
artifacts before integration. Source hashes, signed budgets, explicit column
changes, complete candidate traces and independent replay checks are the
decision evidence. Agents do not accept, deploy or silently rescale models.
The reproducible software runs the resulting specification deterministically;
this does not require an LLM inside the ODE or its objective function.

## From executed balances to proposals

For each stored integration interval we reconstruct raw and actually executed
reaction extents from the accepted-step quadrature. ATP production and demand
are separated by actual reaction sign. We report the ATP, ADP and AMP balances,
total adenylates, and the linear diagnostic H = ATP + 0.5 ADP. Reversible
adenylate kinase can move ATP without directly changing H; transfer to GTP,
ribose phosphorylation, ATP-to-AMP conversion and purine-pool exits are not
treated as interchangeable ATP sinks. A difference between raw and executed
rates at the same state is an availability diagnostic, not free recoverable
ATP or a measured flux. The demand agent's four ranked hypotheses enter as
distinct optimizer starts; they are not hard activity priors. Endogenous flux
teachers are not counted a second time as independent observations.

## Network and parameters

We compare the historical reduced matrix with an opt-in projection from
[RBC-GEM](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1012109)
1.3.0, commit43fd381d9eb8a8a4079629012362312960e1c009. In the pilot the projection
uses normalized catalase stoichiometry, O2/H2O2 couplings in two xanthine
oxidation columns, and ATP/ADP coupling of GSSG export. These are reduced
chemical projections of existing rates, not newly identified binding laws.
The phase factors scale intracellular/extracellular concentration derivatives
from the same executed reaction amount. OPLAH is retained, and additional
branches requiring unknown kinetics or missing states remain closed. The
original rate backend and accelerated rate extraction are checked separately.

For reaction j we use the existing signed rate law and apply one availability
factor to its entire stoichiometric column. Each tested Vmax in group g is
the fixed reference Vmax multiplied by exp(z_g), with a registered log box.
All Km values, zero capacities, J1 states, geometry, transport law, pH and
other numerical settings are fixed within the matched comparison. A common
factor for the AK or NDPK forward/reverse pair preserves their native capacity
ratio; it does not prove thermodynamic consistency. No GEM bound is converted
into a kinetic constant and no extra ATP production term is introduced.

## Search, held-out time points and reproducibility

The first pilot uses the actual J4 source point to target the early energetic
failure. Exact J1 is initialization, not an extra residual. The search combines
seeded Latin-hypercube exploration with bounded local Nelder-Mead refinements.
One refinement follows the adenylate objective even outside the acceptance
region; other starts respect or seek to restore the guards. Each real ODE
attempt, cache lookup and failure is recorded. Reports distinguish the
observed Pareto frontier, smallest measured error, and guard-admissible points.
These finite-budget results do not establish global optimality or identifiability.

Mean squared log residuals of ATP, ADP and AMP are separate from the mean of
nonadenylate working MSEs. Absolute working bands derive only from J1/J4;
the relative term uses the observation being scored. This is engineering
normalization, not assay variance. B13PG/P2G aliases are not independent
residuals; B23PG/P3G nominal rows remain protective checks only. Zero-scale
observations are checked in absolute coordinates rather than adding a
pseudocount. Each finalist is chosen before evaluating J8/J11/J15 and then
replayed freely with original rates at two tolerances. Checks use all55 source
representations, explicit per-pool guards, positivity, signed budgets and
native-rate consistency. The later measurements are historically exposed,
not independent donor validation. Quantitative source and assay uncertainties
remain open, and no production migration follows from this pilot alone.
