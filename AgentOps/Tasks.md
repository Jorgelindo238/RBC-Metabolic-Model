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

Status: deferred design backlog

Decision:
- DeepAgents may become the RoBoCop campaign supervisor
- it must not replace deterministic scientific tools or acceptance gates
- first prototype should be offline-only and compare recommendations against the existing LangGraph runner

Next:
- after production smoke and current cleanup, create a minimal offline prototype in `services/robocop/agentic/`.

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
