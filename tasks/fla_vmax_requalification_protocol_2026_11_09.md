# Historical-threshold control and rejected-Vmax requalification

Use a fresh successor; all old sealed or partial archives stay untouched.
Keep exact55 Sheet1 J1, latent states, every Km, geometry, network, pH,
transport and availability threshold 1e-3 mM unchanged. Use the qualified
optional Radau/bounded-fine-Jacobian recipe, not a new default. Require
the tested SciPy 1.17.1 runtime. No fitting, new parameter proposal,
clipping, source rescaling, state reset, teacher forcing or ATP injection.

Freeze the registry BEFORE replay. Include only valid=false concentration
failures in the three specified recent same-network archives: 9 temporal,
5 absolute-target and 2 PGK/NDPK points. Verify all source hashes, cohort,
initial states, baseline parameters, kinetic families, bounds, groups and
observations match. Preserve their literal log vectors. Deduplicate by
actual complete parameter dictionaries, not rounded vector values. Do not
include metabolic rejections or incomplete coarse runtime cases. Register
at most16 unique candidates, with every original occurrence retained.

Step 1: two unchanged controls (fixed half-step reference and last admitted
working center), both solver profiles, both native/full and compiled/joint
backends: eight integrations. Require all concentration/flux/numerical
gates, paired-profile comparisons, agreement with all four historical full
controls, and full versus joint agreement. Use inherited and focused
concentration/executed-integral criteria. The working center must still
pass the unchanged original metabolic/dated-gain/reserve contract. The
fixed reference is not required to improve relative to itself.

Step 2 may execute ONLY after this certificate passes. Replay the sixteen
existing vectors in both profiles, using the certified compiled backend.
Verify the native raw/executed rate projections at the registered nine
quadrature checkpoints in EVERY replay. Check every daily executed balance
and quadrature convergence. Same 14 groups/17 Vmax and original boxes;
every Km and nontarget parameter remains literal. At most32 candidate
replays, total40 new integrations, no automatic search or fit-based retry.

Step 3: score actual J4/J8/J11/J15 against the original observations.
The PRIMARY guard reference stays the old historical full control at the
corresponding legacy profile; do not recompute caps from the new solver.
Keep all original canonical MSE, zero-band, adenylate-log, critical
PEP/G6P/F6P/AMP point caps, minimum dated gain and safety-reserve checks.
Aliases retain their original status. A numerically completed zero or
nonpositive adenylate is not given a pseudocount; its observation-domain
failure is explicit and cannot be called an admissible fit.

Classify each unique candidate as numerical_failure, metabolic_guard_failure,
or admissible_under_relative_guards. Report absolute ATP/ADP J15 target
attainment separately. Never label relative admission as biological rescue.
Rank only admitted existing candidates by worst-profile absolute target gap,
then worst dated ratio. No output vector becomes a production default.

Verify the registry, all40-or-fewer outcomes, original parameter identity,
concentration supports, executed balances, quadrature, native rate checks,
source values, guard calculations and classifications independently. Keep
failed trajectories quarantined with species/time/minima. No J46 run.
