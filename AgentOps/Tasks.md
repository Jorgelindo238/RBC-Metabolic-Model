# AgentOps Tasks

Current active work, blockers, and next actions for the airbc / RoBoCop repository.

## Current objective

Keep the product and scientific stack deployable while preparing RoBoCop for a
cleaner agentic orchestration layer.

Focus areas:
- production web/API/worker reliability
- Research custom-data workflows
- Simulation and calibration smoke tests
- RoBoCop calibration/autoresearch discipline
- AgentOps simplification for future GPT-5.5 high Codex sessions

## Immediate next action

Root-cause **Phase 0 auto-param-scope EGLC preservation** before starting
Phase A. The full canonical-Bordbar parity sweep completed on Hetzner and
the gate returned `root_cause_phase0`.

Full sweep command that produced the result:

```powershell
python scripts/run_auto_param_scope_parity.py `
  --dataset canonical-bordbar `
  --n-trials 50 `
  --t-max 42 `
  --loss-tolerance-pct 0.10 `
  --out-dir Simulations/auto_param_scope/parity_v1_full
```

Full sweep result:
- `decision_gate`: `root_cause_phase0`
- auto-scope final loss: `6.8191`
- curated-profile final loss: `12.7488`
- auto loss delta vs curated: `-46.5%` (auto-scope fits much better)
- scope Jaccard: `0.0612` (`98` auto params vs `6` curated params)
- pure-ODE: both branches `collapsed`
- root-cause trigger: `EGLC` only (`auto=concern`, `curated=good`)

Interpretation:
- This is not a broad loss failure. Auto-scope is fit-superior and reduces
  the pure-ODE critical count from 7 to 5.
- The blocker is glucose-side physiology: auto-scope leaves EGLC nearly flat
  in pure-ODE replay (`-0.9%`, expected at least `5%` depletion), while the
  curated branch depletes EGLC by `7.0%`.

Next implementation target:
- Add an EGLC-preservation/root-cause probe before Phase A. Candidate fixes:
  - constrain or stage glucose transport/commitment params
    (`vmax_VEGLC`, `km_EGLC`, `km_GLC_transport`, `vmax_VHK`,
    `vmax_VPFK`, `vmax_VPK`, lower-glycolysis companions)
  - add a pure-ODE EGLC depletion gate to candidate acceptance before
    promoting auto-scope results
  - run a targeted rescue sweep that keeps the auto-scope fit gain while
    requiring EGLC depletion >= 5%

Do not start Phase A until the same parity harness returns either
`green_light_phase_a` or `needs_review` with no protected anchor worse than
curated.

Historical acceptance criteria (encoded in the harness):
- `decision_gate == "green_light_phase_a"` → start Phase A (sensitivity
  probe of the plan).
- `decision_gate == "root_cause_phase0"` → fix Phase 0 (likely:
  regulation-param identifiability gap, ki_/ka_ defaults too
  aggressive, or kernel mis-tuned) before any Phase A work.
- `decision_gate == "needs_review"` → inspect
  `final_loss_delta_pct_of_curated` and `protected_anchor_comparison`;
  small loss gap with equal-or-better anchors can be promoted to green
  by widening tolerance after manual review.

Archive summary added in `AgentOps/Archive.md` under the
2026-05-03 parity-sweep entry.

### Status of the parity-sweep harness

Landed and smoke-tested (2026-05-03):
- `scripts/run_auto_param_scope_parity.py` (NEW): adapter-driven
  (`run_web_calibration`), no duplicated Phase 0 logic. Three-state
  decision gate. Dry-run mode for scope-only checks.
- Smoke at `--n-trials 1` against the canonical Bordbar dataset wrote
  `Simulations/auto_param_scope/parity_v1/result.json` (status
  `completed`, decision `needs_review`).
- Smoke is signal-poor for the Phase 0 verdict because both branches
  report `improvement_pct=0.0` — at `n_trials=1` the optimiser barely
  runs, so the 19.88% loss gap is a starting-defaults delta (auto-scope
  injects 92 extra `PHASE_MAP` defaults vs curated's 6), not an
  optimisation-quality delta. AMP is good-vs-critical but at this
  budget that's noise.
- The smoke validated the gate end-to-end and surfaced one real bug,
  fixed in the same session.
- Full Hetzner sweep at `--n-trials 50` completed with
  `decision_gate=root_cause_phase0`; see `Archive.md` for the summary.

### Bug fix shipped alongside the harness

`apps/api/services/pure_ode_runtime.py`: `_write_all_metabolites_csv`
and `_write_reaction_fluxes_csv` were using `... or []` truthiness on
values that the simulation engine sometimes returned as numpy arrays,
which raised `ValueError: The truth value of an array with more than
one element is ambiguous.` whenever the parity script ran the pure-ODE
replay. Replaced with a `_sequence_values(...)` helper that tolerates
None / `np.ndarray` / strings / arbitrary iterables; also added the
`apps/api` directory to `sys.path` so script-driven callers resolve
`services.*` the same way the FastAPI process does. Full qa suite
stays green at 167/167 after adding the regression test. Consistent
with Memory rule 17.

### Follow-ups (small, non-blocking)

- Done: add a regression test under `qa/api/` that drives
  `_write_all_metabolites_csv` and `_write_reaction_fluxes_csv` with
  numpy-array inputs so the truthiness bug cannot silently reappear.
- Repair the pre-existing `PHASE2_PARAMS["vmax_VAMPD1"] = (0.538065,
  0.001, 0.1)` default-out-of-bounds defect once a real campaign needs
  it. Auto-scope clipping makes runtime safe for now.

### Closed (kept for cockpit context)

Previous "AgentOps simplification" close-out is complete:
- only the 7 target files (`README`, `OperatingManual`, `Tasks`,
  `Memory`, `Playbooks`, `CalibrationOps`, `Archive`) live under
  `AgentOps/`
- repo-wide `rg AgentOps/\w+\.md` finds 38 references across 14 files;
  every single one resolves to a surviving file (no stale links)

## Active workstreams

### Production deployment and smoke

Status: active

Goal:
- keep `web`, `marketing`, and `airbc-api` deployed from GitHub `main`
- keep the calibration worker reachable through `calibration-api.airbc.org`

Current state:
- `web`, `marketing`, and `airbc-api` are GitHub-backed to `Jorgelindo238/RBC-Metabolic-Model`
- `web` production deploy previously picked up commit `46220e77`
- Hetzner worker local and nginx smoke tests reached the worker successfully
- Vercel calibration secret was corrected after an empty env value caused parameter loading failures

Next:
- rerun targeted production smoke:
  - Calibration Registry parameter load
  - custom CSV upload
  - Simulation with `EGLC`, `ELAC`, `ATP`
  - custom-data chart overlays
  - worker proxy with secret

### Simulation custom-data UX

Status: recently fixed; needs production smoke

Current state:
- confusing `Calibration required before simulation` messaging was replaced with `Bordbar defaults active - calibration optional`
- local authenticated smoke verified the improved label and custom-data simulation flow
- chart defaults should stay `EGLC`, `ELAC`, and `ATP`
- custom data should appear as points/dashed overlays distinct from solid simulation lines

Next:
- verify the same behavior on `app.airbc.org` after sign-in.

### Research page polish

Status: active product refinement

Current state:
- Calibration Registry was redesigned with the current stack and branding
- Flux Analysis was redesigned to use the full available workspace
- Pathway Visualization has been simplified and needs continued readability/interaction refinement
- Overview should be rebuilt as a minimalist, simple Research landing view

Next:
- after smoke tests, continue with the minimal Overview rebuild.

### Calibration worker / custom-data orchestration

Status: implemented; production validation remains important

Current state:
- custom-data planner, triage, pure-ODE triage, strategy racing, fingerprint memory, worker execution, and teacher-flux rescue exist
- Calibration UI exposes worker race, pure-ODE replay, and teacher-flux rescue options
- worker timeout behavior has been observed from the UI and may need budget/polling tuning

Next:
- capture one successful small worker job through the production web path
- if timeout persists, inspect worker logs and web polling budget before changing algorithms.

### RoBoCop calibration / scientific backend

Status: strong baseline; next campaign deferred until product smoke is stable

Current state:
- bounded LangGraph autosearch supports multi-iteration sessions
- Phase A-D calibration orchestration and seam memory exist
- Phase E guarded edit loop exists for `src/MM_calibration.py`
- pure-ODE validation remains the scientific promotion gate
- hybrid kinetics are planned as neutral wrappers and small scoped openings

Next:
- run the next real bounded campaign only after production smoke and AgentOps cleanup are stable.

### Auto-calibrate-all + ML flux-learning rollout

Status: Phase 0 complete (paused 2026-04-28). Plan file:
`C:/Users/Jorgelindo/.windsurf/plans/auto-calibrate-all-and-ml-flux-learning-179f0d.md`.

Goal:
- when a user uploads custom data, automatically pick a sensible calibration
  scope from the uploaded metabolites' stoichiometric neighbourhood instead of
  forcing the caller to enumerate `params_to_optimize` by hand
- prepare the structural foundations for later phases (sensitivity pruning,
  flux supervision, ML warmstart, hybrid structure learning).

Phase 0 delivered (2026-04-28):
- `src/rbc_stoichiometry.py` (NEW): source-driven structural parser of
  `src/equadiff_brodbar.py`. Public API: `STOICHIOMETRY`, `REACTION_PARAMS`,
  `REVERSE_INDEX`, `KNOWN_PARAM_UNIVERSE`, `ZERO_FLUX_REACTIONS`,
  `reactions_for_metabolites`, `params_for_reactions`,
  `params_for_metabolites`, `validate_consistency`. Drift in
  `equadiff_brodbar.py` raises at import time (intentional fail-loud).
- `src/MM_calibration.py`: `AUTO_SCOPE_KERNEL` (= `PHASE1_BASE_PARAMS` keys),
  `DEFAULT_PARAM_BOUNDS`, `derive_auto_param_scope(...)`,
  `auto_scope_with_bounds(...)`.
- `apps/api/routers/calibration.py`: `params_to_optimize` defaults to `{}`,
  new tri-state `auto_param_scope: Optional[bool]` field.
- `apps/api/services/mm_calibration_adapter.py`:
  `_resolve_auto_param_scope_decision`, `_maybe_apply_auto_param_scope`,
  env kill switch `AIRBC_DISABLE_AUTO_PARAM_SCOPE`. Wired before the strict
  allow-list check; allow-list now also admits `PARAM_CLASS_REGULATION`.
  Response payload exposes `auto_param_scope_applied` and
  `auto_param_scope_params`.
- `qa/test_auto_param_scope.py`: 40 regression tests covering parser
  invariants, scope reachability, tri-state, env kill switch, bounds
  clipping, allow-list integration. Full qa suite stays green at 166
  passing.

Phase 0 deferred / explicitly out of scope:
- Sensitivity-based pruning of "degenerate at canonical IC" parameters
  (deferred to Phase E of the plan).
- Hybrid structure parameters (`hybrid_*`, `kinetic_family_*`,
  `transport_gate_*`) (deferred to Phase F).
- Numerical parity benchmark of auto-scope vs the curated calibration
  profile on the canonical Bordbar dataset (the structural anchor test in
  `TestAutoParamScope0c` is in place; the full optimisation parity belongs
  to a Phase A validation sweep).

Pre-existing data defect surfaced (not fixed):
- `PHASE2_PARAMS["vmax_VAMPD1"] = (0.538065, 0.001, 0.1)` — registered
  default exceeds the upper bound. The auto-scope wrapper clips initial
  seeds, so runtime is safe; track separately if a future calibration
  campaign needs the default repaired.

Parity-sweep harness landed (2026-05-03):
- `scripts/run_auto_param_scope_parity.py` runs both branches through the
  adapter (`run_web_calibration`) and emits a single JSON artifact with
  scope diff, loss delta, protected-anchor severity comparison, and a
  three-state decision gate (`green_light_phase_a` /
  `root_cause_phase0` / `needs_review`). Smoke at `--n-trials 1` wrote
  `Simulations/auto_param_scope/parity_v1/result.json` (status
  `completed`, decision `needs_review`). Smoke is signal-poor for the
  Phase 0 verdict because `improvement_pct=0.0` on both branches at
  this budget; full Hetzner sweep at `--n-trials 50` is the gate.
- Surfaced and fixed `apps/api/services/pure_ode_runtime.py`
  truthiness-on-numpy-array bug in the same session.

Next when work resumes (Phase A and beyond):
- Run the full Hetzner parity sweep (see "Immediate next action" above)
  and capture the verdict in `Archive.md`.
- Phase A: sensitivity probe for canonical-IC degenerate parameters; prune
  before passing to the optimiser. Gated on a green Hetzner sweep.
- Phase B onwards: per the plan file (flux-supervision targets, ML warmstart,
  hybrid structure-learning).

### DeepAgents RoBoCop supervisor

Status: offline prototype landed

Decision:
- DeepAgents is now wired as a candidate RoBoCop campaign supervisor
- it does not replace deterministic scientific tools or acceptance gates
- recommendations stay advisory until the parity gate against the existing LangGraph runner agrees on a fixture set

Current state:
- `services/robocop/agentic/` hosts the offline prototype (DeepAgents harness wired through `deepagents.create_deep_agent`)
- 8 bounded tools in `services/robocop/agentic/tools.py`; mutating tools (`run_strategy_race`, `run_teacher_flux_rescue`) are dry-run wrappers in this phase
- 3 subagents (`planner`, `triage_analyst`, `archivist`) with explicit per-subagent tool ACLs
- `services/robocop/agentic/offline_runner.py` runs a single supervisor turn and writes a result JSON under `Simulations/robocop_agentic/runs/`
- `services/robocop/agentic/compare_with_langgraph.py` is the parity gate against `scripts/run_bounded_autosearch.py` decisions
- optional dependencies pinned in the root `requirements.txt` under the "RoBoCop Agentic Supervisor" section; the production deployment manifests (`api/requirements.txt`, `apps/calibration-worker/requirements.txt`, etc.) do not pull from root, so the agentic stack stays out of web/API/worker images
- `qa/robocop/test_agentic_package.py` covers tool registry, ACLs, sandbox-only writes, and path-allow-list refusal
- `qa/conftest.py` was added to fix a pre-existing namespace-package shadow that previously hid `services.robocop.messaging` from the qa suite

First live offline campaign (2026-04-27):
- model: `openai:gpt-5.4` via `init_chat_model`
- inputs: Phase 5b best params + calibration report + all_metabolites.csv
- supervisor recommendation: `discard`, grounded in `run_curve_triage` (loss 4.9776 -> 4.3115 but AMP critical nRMSE 2.142, ATP/ADP concerns), `run_pure_ode_replay` (ADP / B23PG / GSH floor breaches), and `run_combined_triage` overall discard
- artifacts: `Simulations/robocop_agentic/runs/<utc>/result.json` + `messages.json`, ledger entry in `Simulations/robocop_agentic/recommendations.jsonl`
- the verdict matches the protected-anchor rules from `AgentOps/CalibrationOps.md` and the Phase 5b memory ("AMP regression", "purine seam needs pure-ODE survival").

Default model swap (2026-04-27): `openai:gpt-5.5` is now the agentic default (via `DEFAULT_MODEL_ID` in `services/robocop/agentic/robocop_deep_agent.py`). Live access verified with the same OpenAI key used for gpt-5.4.

Path 3 autonomous campaign runner (2026-04-27):
- new sibling script `scripts/run_agentic_autosearch.py` ships ALONGSIDE `scripts/run_bounded_autosearch.py`; the deterministic runner is unchanged.
- supervisor built with `allow_mutations=True` exposes two extra tools:
  - `run_bounded_autosearch_subprocess(spec)` - executes `scripts/run_bounded_autosearch.py` as a subprocess with hard caps clamped (max_iterations<=3, loop_budget_seconds<=1800), gated on a `CampaignBudget` from `services/robocop/agentic/budgets.py`.
  - `append_campaign_decision(record)` - writes to a NEW `Simulations/robocop_agentic/campaign_decisions.jsonl` ledger. The canonical `autosearch_decisions.jsonl` is never written by the agent.
- safety surface: kill-switch file `Simulations/robocop_agentic/STOP`, USD cap, wall-clock cap, iteration cap, tool-call cap, anchor-regression threshold (`services/robocop/agentic/budgets.py`).
- best-effort token+USD accounting: `services/robocop/agentic/cost.py`. Pricing table covers gpt-5.4 / gpt-5.5 / gpt-4o-mini.
- 18 new safety tests in `qa/robocop/test_agentic_autonomous.py` (mutation-gating, kill-switch, budget caps, ledger schema, anchor regression, ACL non-leak). qa total: 126 passing.

Trajectory CSV plumbing (2026-04-28, branch `dev/next-phase`, commits `5609a541` + `6bddee10`):
- `run_calibration()` in `src/MM_calibration.py` accepts `dump_trajectories=True` and writes `<run_dir>/<case>/metabolites/all_metabolites.csv` (200 timepoints x model state count, columns named via `BRODBAR_METABOLITE_MAP`; auxiliary states like `PHI` get `state_i` names).
- The flag is plumbed through `scripts/run_calibration_eval.py` (`--dump-trajectories`), `scripts/run_calibration_job.py`, and `scripts/run_bounded_autosearch.py` (always `True` in the emitted job spec). `eval_summary.json` now carries `trajectory_csv_path` per case.
- `apps/api/services/mm_calibration_adapter.py` was updated for the new 3-tuple return signature.
- This unblocks `services/robocop/pure_ode_triage` (`pure_ode_replay`) from real autosearch runs - the supervisor can now apply the protected-anchor survival gate to deterministic-runner artifacts.
- `services/robocop/agentic/tools.py::SUBPROCESS_HARD_TIMEOUT_SECONDS` was bumped from 3600 to 7200 because the canonical Bordbar manifest at policy-default `n_trials` routinely exceeds 60 min. Inner `loop_budget_seconds` (<= 1800) still caps the multi-iteration session.

Path 3 real smoke `path3_real_smoke_v1` (2026-04-28, before the timeout bump):
- iteration 1/1, wall 3664s, USD $0.30, tool calls 1
- subprocess hit the 3600s outer timeout, returned `ok=false`, no artifacts
- agent correctly REFUSED triage (no trajectory CSV, no calibration report) and emitted `informative` verdict with the correct open question ("why did the bounded subprocess exceed the outer 3600s timeout despite loop_budget_seconds=1788?")
- ledger entry written cleanly to `Simulations/robocop_agentic/campaign_decisions.jsonl` with full structured `triage_verdicts` showing explicit `skipped` reasons per tool
- this validated the FAILURE path of the Path 3 contract; the HAPPY path on real artifacts is still unobserved.

Next future-session work (not blocking):
- Re-run the real Path 3 campaign with the 7200s timeout to observe the FULL HAPPY PATH end-to-end (successful subprocess -> trajectory CSV -> `pure_ode_replay` -> curve triage -> promotion gate). Suggested args: `--campaign-id path3_real_smoke_v2 --max-iterations 1 --max-wall-seconds 9000 --max-usd 2.0 --max-tool-calls 30`.
- Open scientific question: revoke or formally qualify Phase 4 lactate_balance "current best" status. Deterministic re-evaluation via `triage_pure_ode_csv` on `Simulations/brodbar_phase4_lac_bordbar/metabolites/all_metabolites.csv` reports overall=COLLAPSED with 3 critical floor breaches (B23PG 0.0088 mM vs floor 1.5; GSH 0.0158 mM vs floor 0.5; ADP below 0.05 mM floor). Phase 4 was promoted on aggregate-fit improvement BEFORE the pure-ODE survival gate became a promotion requirement, so under current rules it would NOT be promoted. Operator decision required: (a) qualify the durable memory entry as "best aggregate fit to date, does not survive pure-ODE gate", or (b) redo Phase 4 calibration under the stricter gate.
- Run `compare_with_langgraph.py` against an existing autosearch decision JSON for the same Phase 5b seed and capture the parity report.
- After several agreements with no `keep` vs non-`keep` blockers, consider widening the operator-allowed budget caps and exposing the runner as a scheduled job.

### Python 3.14 migration

Status: deferred

Current finding:
- Python 3.14 is blocked by the old `numpy<2.0.0` constraint causing source compilation risk

Decision:
- keep production on Python 3.12 for now
- revisit on a dedicated migration branch

Validation plan when reopened:
- update root/API/worker requirements
- clean Python 3.14 install
- `py_compile` API/worker/scientific entrypoints
- `qa/robocop`
- compare at least one calibration/simulation output against Python 3.12 baseline

## Current blockers

- Authenticated browser smoke depends on an active user session.
- Long-running calibration worker campaigns may exceed the current web polling timeout.
- Supabase remote provisioning still requires a real Supabase management token or database password if schema work resumes.

## Validation checklist before closing major work

- Relevant type check or build
- Relevant API/worker route smoke
- Browser smoke for UI behavior
- Production domain/deployment check when prod is touched
- Scientific artifact and pure-ODE validation when calibration candidates are promoted
- AgentOps docs updated only when active state, durable memory, or archive history changes

## Notes

- Keep this file short and active.
- Do not use this file as a notebook or architecture manual.
- Historical milestones belong in `Archive.md`.
- Durable rules belong in `Memory.md`.
