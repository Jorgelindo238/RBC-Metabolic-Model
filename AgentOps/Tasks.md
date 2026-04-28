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

- Finish the AgentOps simplification:
  - keep `README.md`, `OperatingManual.md`, `Tasks.md`, `Memory.md`, `Playbooks.md`, `CalibrationOps.md`, and `Archive.md`
  - remove superseded AgentOps files after their content is represented
  - update stale references in root docs
  - verify `rg` finds no references to deleted AgentOps filenames
- Then review the diff and commit only if requested by the user.

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
