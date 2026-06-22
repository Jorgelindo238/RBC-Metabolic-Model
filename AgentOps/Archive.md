# AgentOps Archive

Compact historical record. Do not read this file by default. Use it only when
recovering context for an old decision, scientific run, or branch cleanup.

## 2026-05-05 Phase C aggregate warm-start comparison

Extended the calibration-level Phase C comparator from a single held-out case
to every held-out synthetic validation case.

Updated:
- `scripts/run_phase_c_warmstart_compare.py`
  - added `--all-validation-cases`
  - writes per-case branch artifacts under `cases/*/branches/*`
  - keeps the legacy single-case output shape for existing callers
  - adds an aggregate gate requiring configured case win-rate and mean relative
    improvement before the run can pass
- `qa/test_phase_c_warmstart_compare_script.py`
  - locks aggregate win-rate behavior
  - runs an ODE-backed micro all-validation comparison

Local aggregate comparison:
- command: `python scripts/run_phase_c_warmstart_compare.py --all-validation-cases --out-dir Simulations/auto_param_scope/phase_c_warmstart_compare_all --profile smoke --t-max 2 --timepoints 8 --n-trials 1`
- status: `passed`
- artifact: `Simulations/auto_param_scope/phase_c_warmstart_compare_all/result.json`
- target params: `vmax_VEGLC`, `vmax_VELAC`, `vmax_VLDH`, `vmax_VHK`
- held-out cases: `3`
- passed cases: `3`
- win rate: `1.0`
- mean default/no-ML final loss: `0.05408`
- mean warm-start final loss: `0.00293`
- mean relative improvement: `0.94337`
- observed relative improvement range: `0.86711` to `0.98588`
- decision gate: `aggregate_warmstart_beats_default`

Per-case summary:
- `comparison_00`: default `0.05018`, warm-start `0.00667`, relative
  improvement `0.86711`, seed log MAE `0.04041`
- `comparison_01`: default `0.04880`, warm-start `0.00069`, relative
  improvement `0.98588`, seed log MAE `0.00306`
- `comparison_02`: default `0.06326`, warm-start `0.00145`, relative
  improvement `0.97711`, seed log MAE `0.00489`

Validation:
- `python -m py_compile scripts/run_phase_c_warmstart_compare.py`
- `python -m pytest qa/test_phase_c_warmstart_compare_script.py -q` -> `4 passed`

Interpretation:
- Warm-start now beats default/no-ML across all held-out synthetic cases under
  equal one-trial seed-quality calibration.
- Next gate should use a modest optimizer budget (`n_trials > 1`) before any
  worker/API integration design. Production wiring remains out of scope until
  that aggregate gate is stable and guarded behind a feature flag.

## 2026-05-05 Phase C warm-start calibration comparison

Built the first calibration-level comparator for Phase C warm-start seeding.

Added:
- `scripts/run_phase_c_warmstart_compare.py`
  - trains the offline warm-start ridge model on deterministic synthetic cases
  - holds out one synthetic validation case
  - creates a synthetic ODE dataset for that held-out case
  - runs two identical `MM_calibration.run_calibration` branches:
    `default_no_ml` starts from defaults, `warmstart` starts from the predicted
    seed
  - keeps target params, stage plan, optimizer seed, target data, target scope,
    and `n_trials` identical between branches
- `qa/test_phase_c_warmstart_compare_script.py`
  - validates the warm-start-vs-default loss gate
  - runs an ODE-backed micro comparison and verifies branch artifacts

Local full comparison:
- command: `python scripts/run_phase_c_warmstart_compare.py --out-dir Simulations/auto_param_scope/phase_c_warmstart_compare --profile smoke --t-max 2 --timepoints 8 --n-trials 1`
- status: `passed`
- artifact: `Simulations/auto_param_scope/phase_c_warmstart_compare/result.json`
- target params: `vmax_VEGLC`, `vmax_VELAC`, `vmax_VLDH`, `vmax_VHK`
- default/no-ML final loss: `0.05018`
- warm-start final loss: `0.00667`
- relative improvement: `0.86711`
- warm-start seed log MAE vs true synthetic params: `0.04041`
- decision gate: `warmstart_beats_default`

Validation:
- `python -m py_compile scripts/run_phase_c_warmstart_compare.py`
- `python -m pytest qa/test_phase_c_warmstart_compare_script.py -q` -> `2 passed`
- `python -m pytest qa/test_phase_b_flux_inference.py qa/test_phase_b_flux_smoke_script.py qa/test_phase_c_warmstart_smoke_script.py qa/test_phase_c_warmstart_compare_script.py -q` -> `9 passed`

Interpretation:
- Warm-start now wins at calibration level on one held-out synthetic case under
  an equal one-trial seed-only budget.
- This still stays offline/experimental. Next step: run the same comparison
  across all held-out synthetic validation cases and require aggregate
  superiority before considering any worker/API wiring.

## 2026-05-05 Phase C warm-start scaffold

Started Phase C with an offline, non-production warm-start harness built on the
stable Phase B `phase_b_v1` feature payload.

Added:
- `scripts/run_phase_c_warmstart_smoke.py`
  - generates deterministic synthetic cases from the Brodbar ODE
  - perturbs `vmax_VEGLC`, `vmax_VELAC`, `vmax_VLDH`, and `vmax_VHK`
  - extracts the Phase B `wide` feature vector (`feature_count=244`)
  - trains a pure-NumPy standardized ridge model on log-parameter multipliers
  - emits a serializable model artifact with feature schema, means/scales,
    weights, target means, validation predictions, and gates
- `qa/test_phase_c_warmstart_smoke_script.py`
  - verifies ridge math on a tiny linear fixture
  - runs an ODE-backed micro smoke and checks the JSON contract

Local full smoke:
- command: `python scripts/run_phase_c_warmstart_smoke.py --out-dir Simulations/auto_param_scope/phase_c_warmstart_smoke --profile smoke --t-max 2 --timepoints 8`
- status: `passed`
- artifact: `Simulations/auto_param_scope/phase_c_warmstart_smoke/result.json`
- target params: `vmax_VEGLC`, `vmax_VELAC`, `vmax_VLDH`, `vmax_VHK`
- training cases: `11`
- validation cases: `3`
- validation mean log MAE: `0.01612`
- defaults baseline mean log MAE: `0.12595`
- improvement ratio: `0.12797`
- max abs log error: `0.10985`

Validation:
- `python -m py_compile scripts/run_phase_c_warmstart_smoke.py`
- `python -m pytest qa/test_phase_c_warmstart_smoke_script.py -q` -> `2 passed`
- `python -m pytest qa/test_phase_b_flux_inference.py qa/test_phase_b_flux_smoke_script.py qa/test_phase_c_warmstart_smoke_script.py -q` -> `7 passed`

Interpretation:
- This is a scaffold/gate, not production ML yet.
- The next Phase C step is a calibration-level comparison: apply the predicted
  warm-start seed versus default/no-ML initialization under the same small
  budget and require the warm-start path to beat baseline before any worker/API
  wiring.

## 2026-05-05 Phase B wide flux smoke

Widened the Phase B model-flux smoke conservatively after the direct
`VEGLC`/`VELAC`/`VLDH` gate passed.

Added:
- `scripts/run_phase_b_flux_smoke.py --preset wide`
  - keeps `VEGLC`, `VELAC`, `VLDH`, and `VHK` as the first widened tracked
    reaction panel
  - separates the wide feature metabolite panel from the minimal inference
    metabolite panel so `ATP`/`ADP` cannot create false singleton balances for
    `VHK`
- `--discover-identifiable`
  - scans reactions touching the selected measured metabolite panel
  - compares inferred fluxes against `FluxTracker`
  - promotes only reactions that are singleton-identifiable and pass NRMSE
    tolerance
- `qa/test_phase_b_flux_smoke_script.py`
  - covers direct and wide script contracts
  - verifies `VHK` is discovered and gated in the wide smoke

Local wide smoke:
- command: `python scripts/run_phase_b_flux_smoke.py --preset wide --discover-identifiable --out-dir Simulations/auto_param_scope/phase_b_wide_flux_smoke --t-max 7 --timepoints 25`
- status: `passed`
- artifact: `Simulations/auto_param_scope/phase_b_wide_flux_smoke/result.json`
- discovery scanned `38` candidate reactions
- discovery accepted exactly `VEGLC`, `VELAC`, `VLDH`, `VHK`
- `VEGLC` nRMSE vs model flux: `0.00032` (tolerance `0.02`)
- `VELAC` nRMSE vs model flux: `0.00068` (tolerance `0.03`)
- `VLDH` nRMSE vs model flux: `0.01453` (tolerance `0.08`)
- `VHK` nRMSE vs model flux: `0.01689` (tolerance `0.05`)
- feature count: `244`

Validation:
- `python -m pytest qa/test_phase_b_flux_inference.py qa/test_phase_b_flux_smoke_script.py -q` -> `5 passed`
- `python -m pytest qa -q` -> `189 passed`

Interpretation:
- Phase B now has a cautious direct + wide tracked-flux gate.
- The next scientific implementation step is Phase C: offline ML warm-start
  scaffolding on top of the stable `phase_b_v1` feature payload.

## 2026-05-05 Phase B model-flux smoke

Added `scripts/run_phase_b_flux_smoke.py` and QA coverage for the first
model-grounded Phase B gate.

Script contract:
- solve the Brodbar ODE on a fixed grid
- replay solved states through `FluxTracker`
- infer `VEGLC`, `VELAC`, and `VLDH` from simulated `EGLC`, `ELAC`, and `LAC`
- compare inferred fluxes against tracked model fluxes
- write `Simulations/auto_param_scope/phase_b_model_flux_smoke/result.json`

Local full smoke:
- command: `python scripts/run_phase_b_flux_smoke.py --out-dir Simulations/auto_param_scope/phase_b_model_flux_smoke --t-max 7 --timepoints 25`
- status: `passed`
- `VEGLC` nRMSE vs model flux: `0.00032` (tolerance `0.02`)
- `VELAC` nRMSE vs model flux: `0.00068` (tolerance `0.03`)
- `VLDH` nRMSE vs model flux: `0.01453` (tolerance `0.08`)
- feature count: `78`

Validation:
- `python -m py_compile scripts/run_phase_b_flux_smoke.py src/flux_inference.py src/ml_features.py`
- `python -m pytest qa/test_phase_b_flux_inference.py qa/test_phase_b_flux_smoke_script.py -q` -> `4 passed`

Interpretation:
- Phase B first slice is now validated against both Bordbar PCHIP teacher
  derivatives and model-tracked fluxes.
- Next Phase B step is to widen the reaction panel conservatively, preferring
  reactions with identifiable singleton/near-singleton balances.

## 2026-05-05 Phase B flux inference first slice

Started Phase B of the auto-calibrate-all + ML flux-learning workstream.

Added:
- `src/flux_inference.py`
  - `infer_user_fluxes(exp_data, exp_time, stoichiometry)`
  - PCHIP concentration interpolation and derivatives
  - singleton stoichiometric balance propagation for directly identified
    reactions
  - bounded least-squares fallback for remaining local systems
  - confidence metadata per reaction
- `src/ml_features.py`
  - stable `phase_b_v1` feature schema
  - `build_features(...)`
  - `build_feature_payload(...)`
  - explicit zero-presence features for missing metabolites/reactions
- `qa/test_phase_b_flux_inference.py`
  - Bordbar PCHIP teacher anchors:
    `EGLC -> VEGLC`, `ELAC -> VELAC`, `LAC + VELAC -> VLDH`
  - finite stable feature payload checks
  - missing-series behavior checks

Validation:
- `python -m py_compile src/flux_inference.py src/ml_features.py`
- `python -m pytest qa/test_phase_b_flux_inference.py -q` -> `3 passed`

Next:
- add a model-generated ODE/flux-tracker smoke to compare inferred anchor
  fluxes against tracked model fluxes before widening the reaction panel.

## 2026-05-05 final pruned parity green-light

The final canonical-Bordbar parity sweep was rerun on Hetzner from
`origin/dev/next-phase` after the Phase A2 pruning rule landed in default
auto-scope policy.

Command summary:
- `scripts/run_auto_param_scope_parity.py`
- `--dataset canonical-bordbar`
- `--n-trials 50`
- `--t-max 42`
- `--loss-tolerance-pct 0.10`
- `--out-dir Simulations/auto_param_scope/parity_v1_pruned_final`

Result:
- status: `completed`
- `decision_gate`: `green_light_phase_a`
- auto-scope param count: `91`
- curated-profile param count: `6`
- auto-scope final loss: `7.0872`
- curated-profile final loss: `12.7488`
- auto loss delta vs curated: `-44.4%`
- scope Jaccard: `0.0659`
- pure-ODE status: both branches `collapsed`
- protected anchors worse than curated: none

Protected-anchor details:
- `EGLC`: good in both branches.
- `ELAC`: good in both branches.
- `LAC`: tracked in both branches.
- `AMP`: auto good, curated critical.
- `ATP`, `ADP`, `B23PG`, `GSH`: critical in both branches.

Artifacts copied locally:
- `Simulations/auto_param_scope/parity_v1_pruned_final_result.json`
- `Simulations/auto_param_scope/parity_v1_pruned_final_run.log`

Interpretation:
- Phase 0 + Phase A/A2 are now closed for the default auto-scope policy.
- The conservative 91-param default scope keeps the same final loss as the
  full gated auto-scope run while dropping seven low-sensitivity regulation
  params from automatic selection.
- Pure-ODE energy/redox collapse remains a downstream scientific rescue topic,
  not a blocker for the auto-scope policy.
- Next implementation phase is Phase B: online flux inference and fixed-length
  feature extraction.

## 2026-05-05 Phase A2 broad pruning result

Phase A2 compact and broad pruning validations ran on Hetzner from
`origin/dev/next-phase`.

Compact result:
- `sensitive_only` (2 params): rejected, final loss `15.2925`
- `near_threshold` (13 params): rejected, final loss `14.5531`
- `core_plus_sensitive` (25 params): rejected, final loss `12.0202`

Broad result:
- `drop_low_regulation` (91 params): `accept_pruned_scope`, final loss
  `7.0872`
- `drop_low_caution_transport` (88 params): `needs_review`, final loss
  `8.1238`
- recommended candidate: `drop_low_regulation`

Implemented default auto-scope pruning:
- `AUTO_PARAM_SCOPE_PRUNED_REGULATION_PARAMS` in `src/MM_calibration.py`
- excluded by default:
  - `alpha_F16BP_PK`
  - `ka_F16BP_PK`
  - `ki_ATP_PK`
  - `ki_PYR_PK`
  - `km_ADP_ATP`
  - `km_NADH_NAD`
  - `km_NAD_NADH`
- manual explicit `params_to_optimize` selections remain allowed

Validation:
- `python -m py_compile src/MM_calibration.py`
- `python -m pytest qa/test_auto_param_scope.py qa/test_auto_param_scope_pruning_validation.py -q` -> `52 passed`

Follow-up completed:
- final parity with default pruned auto-scope (`91` params) returned
  `green_light_phase_a`; see the 2026-05-05 final pruned parity entry above.

## 2026-05-05 Phase A complete and A2 pruning harness scaffold

Full Phase A sensitivity probe completed on Hetzner and artifacts were copied
locally:
- `Simulations/auto_param_scope/sensitivity_v1_full_result.json`
- `Simulations/auto_param_scope/sensitivity_v1_full_run.log`
- `Simulations/auto_param_scope/sensitivity_v1_full_baseline_params.json`

Phase A result:
- status: `completed`
- baseline final loss: `7.0872`
- baseline `EGLC` gate: pass, depletion `5.89%` vs required `5%`
- probed params: `98/98`
- classifications:
  - `keep_high_sensitivity`: 1 (`vmax_VAMPD1`, effect `4.31%`)
  - `keep_moderate_sensitivity`: 1 (`vmax_Vnucleo2`, effect `0.57%`)
  - `candidate_prune_low_sensitivity`: 96
  - guarded/review params: 0

Interpretation:
- Do not directly prune 96 params from production. The Phase A probe is local
  around an optimized baseline; parameters can be locally flat after helping
  the optimizer reach that basin.
- Move to Phase A2: rerun calibrations with pruned include-lists and keep the
  `EGLC` depletion gate active.

Added `scripts/run_auto_param_scope_pruning_validation.py` as the Phase A2
ablation harness.

Candidate scopes:
- `sensitive_only`: 2 params (`vmax_VAMPD1`, `vmax_Vnucleo2`)
- `near_threshold`: 13 params
- `top_k`: 12 params
- `core_plus_sensitive`: 25 params
- `drop_low_regulation`: 91 params
- `drop_low_caution_transport`: 88 params

Validation:
- `python -m py_compile scripts/run_auto_param_scope_pruning_validation.py`
- `python -m pytest qa/test_auto_param_scope_pruning_validation.py -q` -> `5 passed`
- `python -m pytest qa/test_auto_param_scope.py qa/test_auto_param_scope_sensitivity.py qa/test_auto_param_scope_pruning_validation.py -q` -> `54 passed`
- dry-run wrote `Simulations/auto_param_scope/pruning_v1_dry/result.json`
- smoke calibration wrote `Simulations/auto_param_scope/pruning_v1_smoke/result.json`
  and correctly rejected `sensitive_only` when the `EGLC` gate failed

Next:
- run the first A2 Hetzner sweep from `AgentOps/Tasks.md` with
  `sensitive_only,near_threshold,core_plus_sensitive`
- if a compact pruned scope is accepted, implement it behind a conservative
  gate and rerun parity
- if compact scopes fail, run the broad ablations
  `drop_low_regulation,drop_low_caution_transport`

## 2026-05-04 Phase A sensitivity harness scaffold

Added `scripts/run_auto_param_scope_sensitivity.py` as the Phase A harness
after the gated parity sweep returned `green_light_phase_a`.

Harness contract:
- dataset loader reuses the parity harness semantics (`canonical-bordbar`,
  JSON, or CSV)
- `--baseline-mode auto-defaults` probes around auto-scope initial values for
  quick smoke checks
- `--baseline-mode calibrate` first regenerates a gated auto-scope calibration
  baseline through the product-plane adapter, then probes around the optimized
  parameter set
- one-at-a-time up/down perturbations are bounded by `DEFAULT_PARAM_BOUNDS`
- classifications: low-sensitivity prune candidates, high/moderate keeps,
  EGLC-gate-sensitive guarded keeps, loss-regression guarded keeps, and
  unstable review params
- output artifact: `result.json`; baseline params: `baseline_params.json`

Validation:
- `python -m py_compile scripts/run_auto_param_scope_sensitivity.py`
- `python -m pytest qa/test_auto_param_scope_sensitivity.py -q` -> `5 passed`
- `python -m pytest qa/test_auto_param_scope.py qa/test_auto_param_scope_sensitivity.py -q` -> `49 passed`
- local smoke with `--baseline-mode auto-defaults --t-max 2 --max-params 2`
  wrote `Simulations/auto_param_scope/sensitivity_v1_smoke/result.json`.

Next:
- run the full Hetzner command from `AgentOps/Tasks.md` using
  `--baseline-mode calibrate --baseline-n-trials 50 --t-max 42`
- use the resulting `recommended_pruned_params`, `guarded_params`, and
  `top_sensitive_params` to decide the Phase A pruning rule.

## 2026-05-04 gated parity sweep green-light

Full canonical-Bordbar parity sweep was rerun on Hetzner from
`origin/dev/next-phase` commit `8f5475e` after the EGLC-depletion gate patch:

```bash
python scripts/run_auto_param_scope_parity.py \
  --dataset canonical-bordbar \
  --n-trials 50 \
  --t-max 42 \
  --loss-tolerance-pct 0.10 \
  --out-dir Simulations/auto_param_scope/parity_v1_full_gate
```

Result:
- `decision_gate`: `green_light_phase_a`
- auto-scope final loss: `7.0872`
- curated-profile final loss: `12.7488`
- auto loss delta vs curated: `-44.4%`
- scope Jaccard: `0.0612` (`98` auto params vs `6` curated params)
- pure-ODE status: both branches `collapsed`
- auto-scope critical count: 5
- curated-profile critical count: 7
- protected anchors worse than curated: none

Protected-anchor details:
- `EGLC`: auto `good`, depleted `5.9%`; curated `good`, depleted `7.0%`.
- `ELAC`: good in both branches.
- `LAC`: tracked/rising in both branches.
- `AMP`: auto good, curated critical.
- `ATP`, `ADP`, `B23PG`, `GSH`: critical in both branches.

The new gate rejected the Km-stage fit-improving candidate that would have
flattened `EGLC`:
- candidate `EGLC 25.3400 -> 25.1227`, depletion `0.9%`
- required depletion `>=5.0%`

Interpretation:
- Phase 0 parity is green. Auto-scope keeps a large fit advantage without
  making any protected anchor worse than curated.
- Pure-ODE survival is still globally collapsed for both branches; ATP/ADP,
  B23PG, and GSH remain downstream scientific rescue targets.
- Phase A sensitivity probing is now unblocked.

Artifacts copied locally:
- `Simulations/auto_param_scope/parity_v1_full_gate_result.json`
- `Simulations/auto_param_scope/parity_v1_full_gate_run.log`

## 2026-05-04 Phase 0 EGLC-depletion gate patch

After the 2026-05-03 parity sweep returned `root_cause_phase0`, the
scientific issue was narrowed to one protected anchor: auto-scope fit was much
better than curated, but pure-ODE `EGLC` depletion was only `0.9%` instead of
the expected `>=5%`.

Patch:
- `src/MM_calibration.py` now records initial/final extracellular diagnostics
  in monitor metrics and supports `min_eglc_depletion_frac` in candidate
  acceptance.
- `apps/api/services/mm_calibration_adapter.py` enables a 5% EGLC-depletion
  gate automatically for Phase 0 auto-scope requests that include `EGLC`.
- Manual curated-profile and explicit-parameter runs remain unchanged unless a
  caller explicitly supplies the gate in a stage plan.
- Regression coverage was added in `qa/test_auto_param_scope.py`.

Validation:
- `python -m py_compile src/MM_calibration.py apps/api/services/mm_calibration_adapter.py`
- `python -m pytest qa/test_auto_param_scope.py -q` -> `44 passed`
- `python -m pytest qa/api/test_pure_ode_runtime.py -q` -> `1 passed`
- `python -m pytest qa -q` -> `171 passed`
- dry-run smoke wrote
  `Simulations/auto_param_scope/parity_v1_dry_gate_smoke/result.json`.

Follow-up completed:
- the full gated Hetzner sweep returned `green_light_phase_a`; see the
  2026-05-04 gated parity sweep green-light entry above.

## 2026-05-03 auto-param-scope parity sweep

Full canonical-Bordbar parity sweep ran on the Hetzner worker from
`origin/dev/next-phase` commit `268d077`:

```bash
python scripts/run_auto_param_scope_parity.py \
  --dataset canonical-bordbar \
  --n-trials 50 \
  --t-max 42 \
  --loss-tolerance-pct 0.10 \
  --out-dir Simulations/auto_param_scope/parity_v1_full
```

Result:
- `decision_gate`: `root_cause_phase0`
- auto-scope final loss: `6.8191`
- curated-profile final loss: `12.7488`
- auto loss delta vs curated: `-46.5%`
- scope Jaccard: `0.0612` (`98` auto params vs `6` curated params)
- pure-ODE status: both branches `collapsed`
- auto-scope reduced pure-ODE critical count from 7 to 5
- root-cause trigger: `EGLC` only (`auto=concern`, `curated=good`)

Protected-anchor details:
- `EGLC`: auto depleted only `0.9%` in pure-ODE replay, below the expected
  `5%` depletion threshold; curated depleted `7.0%`.
- `ELAC`: good in both branches.
- `LAC`: tracked/rising in both branches.
- `ATP`, `ADP`, `B23PG`, `GSH`: critical in both branches.
- `AMP`: auto good, curated critical.

Interpretation:
- Phase 0 is not loss-limited; auto-scope fits the Bordbar panel much better
  than the curated branch at this budget.
- The blocker is glucose-side physiology. Auto-scope keeps extracellular
  glucose too flat during pure-ODE replay, likely via transport/commitment
  degrees of freedom (`vmax_VEGLC`, `km_EGLC`, `km_GLC_transport`,
  `vmax_VHK`, `vmax_VPFK`, `vmax_VPK`, lower-glycolysis companions).

Follow-up:
- Do not start Phase A yet.
- Add an EGLC-preservation/root-cause probe or gate, then rerun the same
  parity harness.
- Green path is `green_light_phase_a` or `needs_review` with no protected
  anchor worse than curated.

## 2026-04-23 AgentOps alignment checkpoint

- Branch cleanup aligned the repo around a clean `main` base.
- The local `hermes-agent/` checkout was removed.
- Telegram alerting stayed native, outbound-only, and RoBoCop-owned.
- Legacy `Hermes` names in Python symbols or artifact paths are technical debt, not an active dependency.

## 2026-04-17 custom-data calibration orchestration

Delivered the P3a-P7 custom-data calibration stack:
- true pure-ODE replay after fitting
- `combined_triage`
- worker `strategy_race`
- dataset fingerprint memory
- bounded teacher-flux rescue
- richer Calibration page orchestration UI
- minimal RL triage environment

Validated:
- `qa/robocop` passed with 90 tests at the time
- local web production build passed
- Calibration page deployed to `app.airbc.org`

Remaining blocker at that checkpoint:
- production web needed the live worker configured through `CALIBRATION_API_BASE_URL` and `CALIBRATION_API_SHARED_SECRET`

## Research data mode milestones

- Upload parsing is not dataset activation.
- One active Research dataset should drive Data Upload, Calibration, Simulation, Flux Analysis, Pathway Visualization, and RoBoCop context.
- Simulation can seed from the active upload while Bordbar/default behavior remains fallback.
- Calibration Registry gained visible handoff to the calibration workspace.
- Calibration and Simulation now carry active-dataset and calibration provenance.
- Custom data should be visibly plotted against simulation outputs when present.

## Calibration result awareness

- RoBoCop learned to distinguish setup-only, running, completed, failed, and historical registry states.
- Completed calibration runs are explained using strategy, fit quality, data provenance, and result payloads.
- Setup provenance and result interpretation should remain distinct.

## Flux Analysis milestones

- Flux Analysis now uses provenance-aware, result-grounded RoBoCop context.
- The page was redesigned into a fuller scientific workspace with hero, provenance snapshot, summary metrics, and ranked pathway explorer.
- RoBoCop remains secondary and contextual.

## Pathway Visualization milestones

- Pathway Visualization is a structural network map, not a flux result.
- It should use a canonical metabolite/reaction graph rather than a decorative subset.
- Replay should read the latest simulation snapshot.
- Compact/full modes should share the same provenance context.
- Next refinements should prioritize interaction, label offsets, selection details, and graph readability.

## Monitoring milestones

- Monitoring visible core: Overview, Bag Repository, Quality Forecast, Alerts.
- Bag Repository should be a real biobank inventory workspace, not CRUD decoration.
- Quality Forecast should be constrained Monitoring prediction, not full Research Simulation.
- Alerts should separate biological severity from operator workflow status.
- Alert workflow state moved toward backend persistence with transition history.
- Supabase provisioning requires a real Supabase access token or remote DB password; service-role JWT is not a management token.

## Calibration run memory

High-value scientific conclusions:
- A better calibration score can still fail the full pure ODE.
- ATP/ADP collapse is the key recurring promotion blocker.
- Glucose-side seams can saturate; if multiple follow-ups reproduce the same seed, move on.
- Lower-glycolysis rescue can improve ATP and extracellular anchors while breaking PEP/PYR.
- Coupled buffering can rescue PEP while moving distortion downstream.
- Phase-2 purine seams can open new basins after glucose saturation.
- Long-horizon adenylate improvements remain informative but not stable defaults if pure ODE energy collapses.
- Hybrid kinetics should enter as neutral wrappers with identity defaults and mechanistic meaning.

## Historical Hermes note

Earlier documents used `Hermes` to describe the internal agentic orchestration
layer. The active direction is now RoBoCop-owned orchestration, with DeepAgents
as a possible future campaign supervisor. Legacy names in code or artifact paths
should be migrated only deliberately and with tests.

## Branch / repo hygiene memory

- Keep root docs minimal.
- Keep credentials, Vercel local state, build artifacts, logs, caches, SQLite runtime data, and generated scientific outputs out of Git.
- Python 3.14 migration is deferred until the scientific dependency stack is updated beyond the old `numpy<2.0.0` blocker.
