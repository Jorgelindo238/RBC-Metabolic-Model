# Claude: feasible starts, extracellular calibration release, then application

Latest user direction supersedes an ATP-first endless optimization loop:
reconstruct feasible starts, revise strategy as needed, retain the best
extracellular calibration result and return to the application.

Read `.claude/skills/airbc-vmax-calibration/SKILL.md`, current tasks and
`tasks/fla_multistart_vmax_results_2026_11_12.md` first. Confirm this same checkout.
The87-evaluation campaign is COMPLETE and independently verified: two optimized
starts, three seeds outside guards, no new finalist. Do not resume or overwrite it.

## Deliver a bounded successor, not just recommendations

### A. Baseline and objective contract

Prepare a read-only inventory/comparison runner for available sealed candidates,
starting with the corrected and multistart campaigns, their working centre and
candidate35. Discover earlier extracellular/transport campaigns through task
logs and verified manifests. Do not scan every large file blindly or treat
different RHS/volumes/initial states as equivalent. Incompatible historical
candidates can be listed separately; ranking them for release requires matched
replays on the declared target context. Count these replays in the budget.

Use all actually measured extracellular channels from the model's external-pool
registry intersected with source observations, not an ad-hoc name-prefix rule.
GLC/LAC and adenylates remain reported intracellular diagnostics. EGLC/ELAC
remain explicit focus channels. Version the release objective before evaluation:
per-channel normalization, mean AND worst-channel errors, dated errors and
EGLC/ELAC endpoint/slope diagnostics. Prefer existing working scales where valid;
do not call working bands assay SD, infer relative-to-mM conversions or invent
uncertainty. Declare zero-channel handling rather than divide by zero.

Keep historical energy objective/constraints unchanged in their original mode.
The release objective is NOW extracellular-first, explicitly named separately.
Preserve the inherited multidate metabolic safety guards/reserve; report ATP/ADP
absolute targets as unmet rather than making them a release-success claim or
allowing a new intracellular regression. Any excluded/changed guard must be a
visible proposed contract change, not something silently executed.

### B. Actually feasible, distinct seeds

Use qualified starts as anchors and construct bounded joint log-Vmax directions.
Try adaptive backtracking and linearized projection onto the locally feasible
cone using the stored guard Jacobian. If needed implement a Phase-I nonlinear
constraint-violation restoration with the existing SciPy stack. Rank restoration
by violation only; do not manufacture biological losses for invalid ODEs.
Final feasibility still requires the real nonlinear ODE and exact unchanged
guards/reserve. Reuse cached evidence only when the complete simulation context
matches, not merely the parameter vector.

Target three additional feasible starts with a declared minimum normalized
log-space separation from anchors and each other. Do not count negligible
backtracks or duplicates as independent basins. If the feasible region does not
support three within budget, report that and use only actual feasible starts.
SLSQP from infeasible seeds is not required; restoration must precede admission.

### C. Strategy and budget

Vmax only, Km/J1/network/H/transport/threshold/boxes unchanged. Preserve paired
AK/NDPK ratios. Do not rewrite MM_calibration.py, the qualified historical
solver, sealed archives, or previous protocols. Do not repeat the same LP/SLSQP
campaign and expect a different result just by increasing its budget.

Separate restoration from extracellular optimization. Prefer a constrained
method with explicit, consistently scaled residuals and guard Jacobians; use
the existing dependency stack. Diagnose constraint scaling and tolerances, not
only multiplier magnitudes. Reuse the qualified recorded Radau recipe and
numerical failure rules. Register a GLOBAL ceiling of240 new ODE integrations:
at most80 for restoration/matched baseline replays and at most160 for search,
with up to12 additional finalist qualification integrations. Cache/checkpoint
all stages; failed and interrupted attempts must be accounted for separately.
Stop on numerical failure, declared stagnation or budget; no automatic campaign
extension. Do not spend the full budget merely because it exists.

### D. Freeze a coherent extracellular profile and return to the app

Deliver a release-selector/exporter, independent verifier and tests. Select ONE
complete admissible kinetic vector for the stated dataset/context. Do not merge
best curves across candidates. If no new candidate improves the extracellular
comparison, export the best VERIFIED compatible fallback, not a fictitious new
fit. If all available candidates lack qualification, say so and return a blocked
release receipt with its concrete qualification task, not a success flag.

The explicit, versioned profile includes parameter values/source hashes,
observations/cohort/donor status, units, initial-state provenance, phase geometry,
solver, all per-species scores, horizon, guard outcomes and execution receipts.
Name status provisional_extracellular_reference; do not call it a complete
validated RBC calibration. ATP/ADP and latent-pool limits stay prominent.
No global default replacement or automatic activation. Historical J46 has
already been exposed: a free J46 replay can check coverage, not claim holdout.

Write a short application handoff for the next tranche: Data -> Verification ->
Calibration -> Results; dataset-bound explicit profile selection, real progress,
separate numerical/fit/activation states, no fabricated monitoring bags/forecasts,
and no unconditional calibrationApplied=true. Do not redesign UI or run a server
in this implementation tranche. Application delivery must not wait for ATP rescue.

## Execution boundary for this Desktop delegation

Read/Grep/Glob/Edit/Write ONLY. No shell, code/tests/ODE/optimization execution,
agents, package installs, servers, commits/pushes or permission changes. Codex
will review and execute through its own tools. State tests WRITTEN vs RUN.

Deliver runnable successor modules/runners/independent verifier, focused tests
(restoration and separation, whole budget across stages, context-safe caching,
no non-Vmax changes, scoring zero channels, single-vector export and fallback,
full-profile qualification, no automatic activation), preregistered configuration,
exact execution entrypoints and application handoff. Stop after this code tranche
and await Codex review. Do not promise successful global calibration.
