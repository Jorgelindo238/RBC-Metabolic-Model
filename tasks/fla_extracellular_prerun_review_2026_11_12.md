# Claude next instruction: extracellular pre-run corrections

Codex read the delivery and the scoring/cache/application code. Nothing in this
delivery establishes a new numerical result; tests and ODEs are still unexecuted.
Complete this bounded corrective tranche before Codex launches it. Keep the
extracellular release/fallback/application objective; no new energy-first loop.

## 1. Make the declared objective finite at exact agreement

The current `0.5*log(MSE_c/MSE_anchor_c)` raises when a candidate fits a channel
exactly and excludes channels fitted exactly by the anchor. It also gives an
unbounded reward for driving one channel error toward zero. The reference
denominator is constant across candidates: it centres the score but does not
by itself fix these properties. Do not approve this formulation unchanged.

Before any campaign, version the successor objective as `extracellular_first/2`:

    mean_c 0.5 * [log1p(MSE_c) - log1p(MSE_anchor_c)]

MSE remains the SAME dimensionless band-normalized error, same channel weights
and dates. The added1 is an explicit dimensionless utility scale, NOT an assay
variance, uncertainty estimate or fitted parameter. Use stable `log1p`; no
pseudocount in observations/concentrations. Include zero-error anchor/candidate
channels when their band is defined. Undefined-band channels stay reported and
governed by their absolute-error guards. Update the analytic chain-rule gradient
(denominator1+MSE), finite differences, search constraints, selector, verifier,
tests and all descriptions consistently. Improvement threshold is an absolute
change in this registered utility, not a percentage decrease of biological RMSE.
Keep the originally chosen `log1p(0.001)` as declared utility-gain threshold for
this tranche; disclose its meaning and do not change it after seeing results.

## 2. Protect the focus channels, not only the global worst channel

Retain all84 inherited hard guards and reserve. The old additional condition
`RMSE_c <= max(RMSE_fallback)` is a GLOBAL worst-channel non-regression cap;
do not describe it as per-species non-regression. EINO can dominate that cap,
so it does not specifically protect a good EGLC or ELAC fit.

Add predeclared EGLC and ELAC checks against the selected qualified fallback:
each channel's normalized RMSE, absolute J15 residual and absolute J4-J15
secant-slope error must not worsen beyond a fixed solver-comparison allowance.
Derive the allowance formula from the inherited concentration comparison
atol/rtol and the exact error/slope definitions; do not tune it on a candidate.
Report allowances explicitly. Keep mean/worst/dates/all19 channels visible.
These focus protections may reduce the number of feasible seeds; report that
honestly rather than relax them during the campaign.

## 3. Repair provenance and cache qualification

The delivery says the observation archive does not store units, but config
currently says "mM as archived". Distinguish source-confirmed units from the
historical model assumption. Propagate `unit_status` and source references into
the inventory, scores/export labels and release. Never claim mM experimentally
verified from an unlabelled numeric array. Missing uncertainty is not an SD.
The provisional historical comparator can remain inspectable with limitations;
it cannot establish compatibility with arbitrary incoming user datasets.

An unchanged `evaluate` hash plus design is not sufficient to import cached
trajectories if the kernel/RHS/transport/positivity/solver dependencies changed.
Verify a transitive execution-source fingerprint against the actual archived
hash evidence, including observations and solver/profile/context. If the archive
lacks required evidence, mark reuse unqualified and schedule a matched replay
within the declared budget; do not stamp it compatible. Dedupe without losing
the original source receipts. Cache tests must change an imported dependency
while keeping the evaluate wrapper unchanged and prove a cache miss/block.

## 4. Preserve activation policy and deliver for execution

The release explicitly has `activation_allowed:false`. A later explicit UI click
must not override it. Correct the application handoff: provisional profile
preview/selection may be read-only; activation requires a separately eligible
release and engine/data identity checks. Do not implement UI changes now.

Add focused tests for exact-fit candidate/anchor, all-zero band, finite utility
gradient, focus-regression rejection despite improved mean, source-unit status,
dependency drift and refused activation of a provisional artifact. Preserve
tests for restoration feasibility, distinct seed separation, whole-stage budget,
fixed Km/J1, single-vector release, fallback and both validation profiles.

Deliver exact changed files, objective/acceptance equations, test entry points,
resumability/source-hash consequences and unexecuted campaign commands. Verify
that no output campaign already exists before changing this pre-registration;
if one exists, preserve it and make a new version instead. Do not run anything.

Read/Grep/Glob/Edit/Write ONLY: no shell, tests, ODE, optimizer, agents, servers,
installs, commit/push or permission changes. Codex runs tests and the numerical
campaign after review. No more open-ended redesign: once tests pass, execute
the bounded restoration/search/qualification, freeze one verified provisional
extracellular vector (or audited fallback), then return to the application.
