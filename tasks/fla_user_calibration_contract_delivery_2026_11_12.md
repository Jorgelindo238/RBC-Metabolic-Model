# User-calibration contract: delivery note for lots A, B and C

Date 2026-11-12. Mandate of that day, three ordered lots. Tools used: file
reading, text search, file writing and editing only. No shell, no code
execution, no ODE, no optimization, no server, no commit.

NOTHING BELOW HAS BEEN EXECUTED. Every test listed is written and not run.
No claim is made that user-data calibration is validated.

## Lot A: latent inventory contract

- `config/fla_latent_inventory_contract_2026_11_12.json`
- `tasks/fla_latent_inventory_contract_2026_11_12.md`

ADO, EADO, RIB, PRPP: exact J1 value 1.0 mM in their own phase, latent,
convention, provenance unresolved, no justified bound, no change in the
reference state. R5P (context): 1.6110905450195272 mM, from an August
diagnostic initialization that was not promoted; not a generic value.
Blockage recorded in the note: workbooks and `.npz` files cannot be opened
with the permitted tools, and the loader was not re-executed.

## Lot B: strict Vmax-only at the entry points

New file:

- `apps/api/services/vmax_only_contract.py`: separate validation layer, no
  import of the calibration core. Resolves the contract, refuses strategy
  conflicts, refuses caller-selected non-Vmax parameters, filters derived
  ones and reports them, checks the stage plan, audits parameters before
  and after with exact equality.

Edited files:

- `apps/api/services/mm_calibration_adapter.py`: contract resolved first in
  `run_web_calibration` and `_run_single_web_calibration` (conflict -> 400);
  under fixed Km the auto-scope result and profile/planner additions are
  reduced to Vmax names and the dropped names returned; strategy forced to
  `vmax_only`; stage plan built before the core and checked; post-run audit;
  a changed non-Vmax parameter marks the result failed. New response
  fields: `parameter_contract`, `parameter_contract_requested_by`,
  `fixed_km`, `fixed_km_dropped_params`, `fixed_km_audit`. The stage plan is
  now built just before the temporary directory instead of inside the core
  call; for the historical path the plan is the same object as before.
- `apps/api/services/custom_calibration_orchestrator.py`: the pre-existing
  partial changes are kept as found (`_requires_fixed_km`, race restricted
  to `vmax_only`, zero loss preserved, teacher rescue skipped). Added:
  `parameter_contract` also triggers fixed Km, no strategy-memory write
  under fixed Km, `fixed_km` and `strategy_memory_used` in the orchestration
  block.
- `apps/api/routers/calibration.py`: optional `parameter_contract` field.

`src/MM_calibration.py` is not touched.

Tests written, NOT executed:

- `qa/robocop/test_vmax_only_contract.py` (new, pure).
- `qa/robocop/test_strategy_orchestrator.py`: three tests added; existing
  ones unchanged.
- `qa/test_auto_param_scope.py`: class `TestFixedKmEntryPoints` appended;
  the calibration core is stubbed.

Historical path: selected when no fixed-Km request is made; identified in
the response as `legacy_unconstrained`; it may still optimise Km and
regulation parameters and its default strategy is still `vmax_then_km`.

## Lot C: versioned data contract and preflight

New files:

- `config/user_calibration_data_schema_v1.json`: JSON Schema,
  `airbc.user_calibration_data/1`.
- `apps/api/services/user_data_contract.py`: pure preflight. Returns
  `data_valid` and, separately, `engine_compatibility`; `launch_allowed` is
  their conjunction.

Edited file:

- `apps/api/routers/calibration.py`: optional `data_contract` field;
  `POST /calibration/preflight` (runs nothing); `/calibration/run` with a
  data contract returns 400 when the data are invalid and 409 when the data
  are valid but the engine cannot honour them; without a data contract the
  historical path runs and the response carries `data_contract` =
  `legacy_no_data_contract` with its limits.

Engine compatibility is reported false for every dataset, with the reasons
(`engine_initial_state_ignores_user_data`, `engine_no_compartment_volumes`,
`engine_time_origin_not_bound`, and per channel the relative or non-mM
codes). The contractual path is therefore blocked on purpose. The preflight
performs no unit conversion, no relative-to-mM conversion, no donor merge
and no substitution of the initial state.

Tests written, NOT executed:

- `qa/test_user_data_contract.py` (new, pure).
- `qa/test_calibration_preflight_api.py` (new; router handlers called
  directly, core stubbed).

No frontend change.

## Corrections to the review of 2026-11-11

- The qualified Radau recipe is opt-in. `solver_method = "RK45"` as the web
  default is not a defect to fix by promotion; nothing is changed here.
- Invariance to a x10 scaling is required only of a relative observation
  that is properly normalized. The tests reflect that: scaling a relative
  series changes no preflight verdict, and an absolute series in another
  unit is reported, not normalized away.
- An identical series is not proof of a biological alias. The preflight
  emits a warning worded "may not be independent" and nothing more.
- A fingerprint collision is not by itself proof of a leak between
  accounts. Strategy memory is disabled under fixed Km for contract
  reasons; the historical race is unchanged and its cross-dataset
  behaviour remains a risk to confirm.
- Every "fails" verdict of that review that was not tested remains a risk
  to confirm, not an established failure.

## Remaining risks

- Nothing was run: import paths, pydantic behaviour of `model_copy` with
  the new fields, and the stubbed-core tests may need adjustment.
- The post-run audit compares against `mm.DEFAULT_PARAM_VALUES` merged with
  the request's initial parameters. If the core legitimately returns other
  defaults, the audit will report differences; only a changed non-Vmax
  parameter or a non-Vmax name in the optimised set fails the run, other
  findings are reported in `fixed_km_audit`.
- Auto-scope under fixed Km keeps whatever Vmax names it derives,
  including transport Vmax; whether that scope is wanted is not decided
  here.
- The fixed-Km contract does not bind `base_params`: a caller can still
  supply different Km values as fixed inputs. That is a fixed-input
  question, not an optimisation one, and is not addressed.
- The teacher-flux rescue stays available on the historical path.
- The historical path still ignores compartments, units, hematocrit,
  donors and the user's first time point as initial state; the notice says
  so but does not prevent the run.
- The web client was not changed: it does not send either contract field
  and still marks any returned calibration as applied.
- The 409 gate makes the contractual path unusable until the engine work
  below is done. This is intended.

## Next slice (not started)

1. Run the tests listed above and fix what they reveal.
2. Engine successor module (not an edit of the hash-frozen core) that takes
   a declared initial state, compartment volumes and a time origin; only
   then let `engine_compatibility` become true for absolute mM datasets.
3. A relative-observation model with an explicit scale parameter per
   channel before any relative channel becomes runnable.
4. Web client: send the contracts, show verdict and limits, stop marking
   failed or legacy runs as applied.
5. Re-execute the loader with its provenance map to close the lot A
   blockage.
