# Successor engine, lifecycle layer and R5P trace: delivery for review

Date 2026-11-12, second tranche of the day. File tools only: no shell, no
execution, no ODE, no optimization, no server, no commit. Codex executes
the tests. NOTHING written in this tranche has been executed.

## 0. Tests of the previous tranche (as reported by Codex)

Codex reported running `qa/robocop/test_vmax_only_contract.py`,
`qa/test_user_data_contract.py`, `qa/test_calibration_preflight_api.py`,
`qa/robocop/test_strategy_orchestrator.py` and `qa/test_auto_param_scope.py`:
213 passed in 28.59 s, exit 0. I did not run them and have not seen the
output. These are software tests of request contracts, a preflight and a
stubbed core; none integrates the model, and none is a biological or
calibration result.

## 1. R5P(0) transfer trace

`tasks/fla_r5p_transfer_trace_2026_11_12.md`, and two fields added to the R5P
entry of `config/fla_latent_inventory_contract_2026_11_12.json`
(`transfer_trace`, `roles`). Value unchanged.

R5P = 1.6110905450195272 comes from the unpromoted 2026-08-11 candidate
`constrained_balanced_teacher__v6pgd_0.9000x` and was carried unchanged
through five scripts into the 2026-10-06 frozen state, then into every
campaign since. It is a historical comparator, not an eligible biological
initialization; its biological provenance is not resolved.

## 2. Successor engine (opt-in)

New: `src/fla_user_engine.py`. Not wired into the API. `src/MM_calibration.py`
untouched.

- `prepare(data_contract, engine_request, pool_names=..., compartments=...)`
  returns an immutable `PreparedRun` or raises `EngineContractError` with
  every issue. Requires: complete initial state (policy
  `user_declared_table`, every model state declared with status
  `measured` or `latent_declared` and a source; nothing filled by
  default); measured values equal to the first observation bit for bit;
  initial time = first sample; days only; hematocrit with provenance; one
  dataset and one donor or declared group; absolute mM channels only
  (relative refused, no unit conversion); compartments checked against the
  model layout; explicit parameters with their source, kinetics, network
  mode, backend, threshold, negative tolerance and solver settings. Search
  keys, horizon keys and teacher-forced kinetics are refused.
- `validate(prepared)` re-checks the invariants, never raises.
- `run(prepared, rhs_factory=..., solver=...)`: both arguments mandatory.
  Integrates from the first to the last sample with `t_eval` = sample
  dates only; refuses earlier times, a changed first state, changed
  parameters; scores only observed dates after the first sample; returns
  `completed_unqualified`, `numerical_failure`, `contract_violation` or
  `invalid_prepared`. Always `biologically_validated: false`,
  `activation_allowed: false`, `qualification: not_qualified`.
- `default_model_layout`, `default_rhs_factory` (existing
  `GemCorrectionRHS`: phase matrix, `reaction_consistent` limiter, clamped
  pH, declared hematocrit) and `default_solver` (`solve_ivp`, caller
  settings only) are explicit opt-ins, imported lazily. No network copy, no
  global patch. The qualified Radau + bounded-Jacobian recipe is not
  hard-wired; it stays opt-in.
- `bag_amounts` converts to mmol per L of bag with H and 1 - H.

`apps/api/services/user_data_contract.py` is unchanged:
`engine_compatibility` stays false.

Tests, NOT executed: `qa/test_fla_user_engine.py` (injected fake RHS and
Euler solver; no model ODE). Covers: complete state and measured lock,
refusals listed above, donor separation, explicit factory/solver, declared
geometry and an equal parameter copy reaching the RHS, first-sample
identity, conservation of bag amounts under a phase-scaled transport,
nothing before t0, scoring only at observed dates, contract violations and
numerical failures reported, module-level imports limited to the standard
library and numpy.

## 3. Shared lifecycle layer (Calibration / Monitoring)

New: `apps/web/lib/calibration-lifecycle.mjs` and its types
`calibration-lifecycle.d.mts`. Pure functions:

- `classifyCalibrationRecord({preflight, job, result})` -> one of
  `invalid_data`, `incompatible_engine`, `ready_for_test`, `running`,
  `numerical_failure`, `rejected_candidate`, `admissible_candidate`, with
  `finished`, `biologicallyValidated` (always false) and `legacy`.
  Admissible needs a completed run, a non-skipped healthy free-ODE verdict
  and a keep combined verdict; a fit-side keep alone is rejected.
- `activationDecision(classified, {explicit, runIdentity, activeIdentity})`
  allows activation only for an admissible, non-legacy candidate, by an
  explicit user action, with dataset, donor and contract fingerprint all
  known and equal.
- `separateScores(result)`: fit/teacher side and free-ODE side, never
  merged.
- `monitoringView(record)`: state and label from real fields; progress only
  from real `completed_cases`/`total_cases` while running; never
  validated; active only if admissible and explicitly active.
- `journeyFor(state)`: Data -> Verification -> Calibration -> Results.

Edited: `apps/web/components/features/ParameterCalibration.tsx`. The
automatic `activateCalibration(...)` after every run is replaced by the
decision above with `explicit: false`, so no run is activated
automatically; a one-line notice states the lifecycle state and why it was
not activated. Since today's runs carry no data contract, no run can be
activated from this screen until an explicit, identity-checked activation
control exists. That control is not built (no redesign in this pass).

Tests, NOT executed: `apps/web/lib/calibration-lifecycle.test.mjs`, for
`node --test` (no other runner configured in `apps/web`).

Proposed journey, not implemented: Data (upload + `/calibration/preflight`)
-> Verification (data validity and engine compatibility shown separately)
-> Calibration (only from `ready_for_test`) -> Results (fit and free-ODE
scores side by side, lifecycle state, explicit activation). Existing pages
are kept; each would host one step.

## Closure matrix for a calibration (status as of 2026-11-12)

| Criterion | Where it stands | Status |
| --- | --- | --- |
| ATP and ADP at J15 inside their windows ([0.757, 1.271] and [0.316, 0.585] mM) | Working centre ATP 9.0e-5, ADP 1.8e-6; best fixed-kinetics arm ATP 4.4e-3 | Not met |
| ATP/ADP trajectory J1-J15 | Collapse within days 1-3 in every trajectory | Not met |
| 55 original dated guards with reserve | Working centre passes (it is the reference); every diagnostic arm that moved ATP failed 17-23 guards | Not met for any improving candidate |
| PEP, G6P, F6P pointwise at J4/J8/J11/J15 | Fail in all AK and PEPase arms | Not met |
| AMP multi-date | AMP about 2.5 mM at J4 against 0.54 observed | Not met |
| Numerical convergence (strict/ultrastrict paired, daily closures, quadrature) | Passes for every sealed campaign of 11-09 to 11-11 | Met for those runs only |
| Measured J1 identity | Verified in every sealed campaign; enforced by the successor engine | Met (engine part untested) |
| Free-ODE validation of a candidate | Exists as pure-ODE triage on the web path; no candidate has passed it with guards | Not met |
| Validation per donor | Single curated table, donor unknown, no second donor | Not testable |
| Observation contract (what Sheet1 ATP/ADP/AMP measure) | Unresolved | Open |
| Matched geometry | H = 0.58 borrowed | Open |

## Blockers

Scientific (data or model, not solvable by code):

- early ATP/ADP collapse not explained by any in-box capacity, latent
  stock or PEP split tested so far;
- observation contract of ATP/ADP/AMP; duplicated B13PG/B23PG and P2G/P3G
  rows; borrowed geometry;
- latent stocks (ADO, EADO, RIB, PRPP, R5P) without measured values or
  justified bounds;
- one donor-unknown dataset: no per-donor validation possible.

Software:

- the successor engine is untested and unqualified; `engine_compatibility`
  stays false;
- no relative-observation model;
- the web client sends neither contract and has no explicit activation
  control; `research-calibration.ts` still stamps `calibrationApplied: true`
  when it is called;
- `MonitoringWorkspaceLanding.tsx` still shows static demonstration bags and
  forecast percentages (lines 65-100); they are not derived from any run and
  should be replaced by `monitoringView` output or removed;
- the historical path still runs without data contract and can optimise Km
  unless fixed Km is requested.

## Single next execution: engine qualification replay

One campaign, authorised separately: replay the sealed working-centre
control of `output/vmax_requalification_2026_11_09/` through
`fla_user_engine.run`, strict and ultrastrict (two integrations), with:

- the archived complete initial state declared pool by pool (55 measured
  values as `measured`, every other state as `latent_declared` with source
  "historical comparator", R5P included);
- the archived working-centre parameters, kinetics and network mode;
- the archived solver recipe passed explicitly as the solver (Radau,
  bounded Jacobian, tolerances and `max_step` of each profile);
- comparison of states at J1, J4, J8, J11, J15 with the sealed
  `trajectory_evidence.npz`, within the inherited comparison tolerances
  (1e-5 mM absolute, 1 % relative), by an independent verifier.

Only if both profiles reproduce the sealed trajectory may
`engine_compatibility` be reconsidered, and then only for absolute mM data.
This replay qualifies software; it does not calibrate or validate anything
biologically.

## Not done

No execution, no commit, no change to sealed archives, J1 values,
constants, Km, OPLAH or numerical policies. 213 passing tests and a
simplified journey do not mean the calibration is achieved.
