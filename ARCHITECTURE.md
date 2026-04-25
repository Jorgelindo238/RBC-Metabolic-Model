# airbc Architecture

Technical system map for the RBC metabolic model, the airbc product platform,
and RoBoCop calibration orchestration.

## Purpose

This file explains how the repository is wired. It is intentionally more
technical than `README.md` and less operational than `AgentOps/`.

Use:
- `README.md` for product overview and quick start
- `ARCHITECTURE.md` for system boundaries and runtime flow
- `AgentOps/README.md` for Codex/RoBoCop operating context
- `AgentOps/CalibrationOps.md` for calibration/autoresearch rules

## Active Systems

```text
apps/web
  Next.js authenticated research and monitoring platform

apps/api
  FastAPI bridge from web to Python scientific/runtime logic

apps/calibration-worker
  FastAPI/uvicorn worker for long-running calibration jobs

apps/marketing
  Next.js public marketing site

src
  mechanistic ODE model, CLI simulation, calibration engine

streamlit_app/core
  legacy scientific helper modules still imported by apps/api

services/robocop
  RoBoCop planning, triage, pure-ODE validation, memory, and orchestration helpers

scripts
  benchmark, calibration-job, artifact, registry, and bounded autosearch CLIs

packages/contracts
  JSON schemas and generated contract examples

AgentOps
  operational cockpit for Codex and RoBoCop work
```

## System Boundaries

### Scientific Core

The mechanistic model lives in `src/`.

Important files:
- `src/equadiff_brodbar.py`: canonical ODE system and parameter injection
- `src/MM_calibration.py`: canonical calibration engine and strategy surface
- `src/main.py`: official pure-ODE replay path
- `src/solver.py`: ODE execution wrapper
- `src/model.py` and `src/parse.py`: reaction/model loading helpers

Rules:
- do not duplicate ODE logic in JS/TS
- do not casually edit `equadiff_brodbar.py`
- promotion-quality calibration candidates must survive pure-ODE replay
- generated outputs should not become the source of truth

### API Boundary

`apps/api` exposes scientific capabilities to the web app.

Responsibilities:
- route registration
- request/response validation
- JSON-safe serialization of scientific outputs
- import bridge into `src/` and `streamlit_app/core/`
- calibration adapter calls into the canonical `src/MM_calibration.py` path

The API must not:
- redefine the ODE
- copy scientific logic
- bypass calibration artifacts or registry contracts when reading completed runs

### Calibration Worker Boundary

`apps/calibration-worker` exists because long-running calibration campaigns do
not belong on the synchronous Vercel request path.

Responsibilities:
- secret-protected worker API
- async custom-data calibration jobs
- strategy race execution
- dataset fingerprint memory
- pure-ODE replay hooks
- bounded teacher-flux rescue for supported reactions

Production wiring:
- public worker domain: `calibration-api.airbc.org`
- web env: `CALIBRATION_API_BASE_URL`
- web env: `CALIBRATION_API_SHARED_SECRET`
- worker env: `CALIBRATION_WORKER_SHARED_SECRET`

The web shared secret and worker shared secret must match.

### Product Boundary

`apps/web` is the authenticated product surface.

Research surfaces:
- Overview
- Data Upload
- Calibration Registry
- Parameter Calibration
- Simulation
- Flux Analysis
- Pathway Visualization

Monitoring surfaces:
- Overview
- Bag Repository
- Quality Forecast
- Alerts

The product plane may present, compare, and explain scientific results. It must
not become a separate scientific implementation.

### RoBoCop Boundary

RoBoCop is the product-facing assistant and the internal orchestration identity.

Current RoBoCop capabilities:
- research context building
- grounded chat/interpretation
- calibration planner
- curve triage
- pure-ODE triage
- combined verdicts
- strategy-race orchestration
- teacher-flux rescue for supported reactions
- memory/ledger integration

Future direction:
- DeepAgents may become the offline campaign supervisor
- LangGraph remains the durable runtime/state-machine layer
- LangSmith remains the traceability/audit layer
- deterministic tools remain the scientific authority

See `AgentOps/CalibrationOps.md`.

## Runtime Flows

### Web Simulation Flow

```text
User input / active dataset
  -> apps/web Simulation workspace
  -> apps/api /simulate
  -> streamlit_app/core simulation bridge
  -> src ODE execution
  -> JSON-safe result
  -> chart + RoBoCop context
```

Custom data behavior:
- active custom data can seed mapped first-timepoint values
- Bordbar/default data remains fallback
- chart defaults are `EGLC`, `ELAC`, and `ATP`
- custom observations should render distinctly from simulation trajectories

### Calibration Flow

```text
apps/web Parameter Calibration
  -> apps/api calibration route handlers
  -> single_run path or worker job path
  -> src/MM_calibration.py
  -> calibration report + best params
  -> optional pure-ODE replay via src/main.py
  -> curve triage + combined triage
  -> UI result + RoBoCop context
```

The worker-backed path should be used for long-running custom-data campaigns.

### Worker Job Flow

```text
apps/web /api/calibration/*
  -> CALIBRATION_API_BASE_URL
  -> calibration-api.airbc.org
  -> nginx
  -> uvicorn worker on 127.0.0.1:8010
  -> apps/calibration-worker/main.py
  -> calibration job execution
```

Secret header:
- web sends the shared secret
- worker validates it
- protected routes return `401` without it

### Bounded Autosearch Flow

```text
AgentOps/CalibrationOps.md + config/autoresearch_mutation_policy.yaml
  -> scripts/run_bounded_autosearch.py
  -> LangGraph StateGraph
  -> propose_candidate
  -> evaluate_candidate
  -> derive_decision
  -> archive_result
  -> autosearch_memory.jsonl
```

This loop mutates bounded policy/manifest/config surfaces. It does not replace
the scientific engine.

## Calibration Architecture

Primary entrypoint:
- `src/MM_calibration.py`

Responsibilities:
- parameter taxonomy
- Vmax/Km/hybrid parameter exposure
- strategy selection
- stage planning
- objective construction
- Optuna/fallback optimization
- report generation
- best-parameter output

Important supporting modules:
- `services/robocop/custom_dataset_planner.py`
- `services/robocop/curve_triage.py`
- `services/robocop/pure_ode_triage.py`
- `apps/api/services/mm_calibration_adapter.py`
- `apps/api/services/custom_calibration_orchestrator.py`
- `apps/api/services/pure_ode_runtime.py`
- `apps/api/services/teacher_flux_generic.py`

Promotion rule:
- fit improvement alone is insufficient
- pure-ODE protected behavior must survive
- artifacts and verdicts must be complete

## Agentic Orchestration

Current runtime:
- LangGraph state machine in `services/robocop/runtime.py`
- CLI runner in `scripts/run_bounded_autosearch.py`
- optional LangSmith tracing through `services/robocop/tracing.py`
- trace metadata helpers in `services/robocop/trace_context.py`

Future DeepAgents role:
- campaign supervisor
- planner
- subagent delegation
- memory/context manager
- explanation layer

DeepAgents should call bounded deterministic tools rather than directly judging
scientific acceptance.

## Contracts and Artifacts

Contract schemas:
- `packages/contracts/schemas/`

Generated examples:
- `config/generated/*.example.json`

Calibration artifacts:
- reports and best params under run-specific output directories
- completed-run manifests
- registry records
- pure-ODE replay CSVs when promotion is considered

Autosearch artifacts:
- `Simulations/brodbar/autoresearch/agent_orchestration/autosearch_memory.jsonl`
- decision records
- session summaries

Runtime/generated scientific outputs should generally remain untracked unless a
specific artifact is intentionally promoted.

## Local Development

Install dependencies:

```bash
cd apps/web && npm install
cd ../marketing && npm install
cd ../../
pip install -r requirements.txt
pip install -r api/requirements.txt
pip install -r apps/calibration-worker/requirements.txt
```

Run services:

```bash
# API
cd apps/api
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# Worker
cd ../calibration-worker
python -m uvicorn main:app --host 127.0.0.1 --port 8010

# Web
cd ../web
npm run dev

# Marketing
cd ../marketing
npm run dev
```

Run scientific CLI:

```bash
python src/main.py --model brodbar
```

Run bounded autosearch:

```bash
python scripts/run_bounded_autosearch.py \
  --base-policy config/policy_vmax_then_km.json \
  --base-manifest config/rbc_calibration_benchmarks.json \
  --max-iterations 3 \
  --timeout-policy continue
```

## Known Caveats

- Python 3.14 migration is deferred; production remains on Python 3.12 for now.
- `streamlit_app/core/` is still imported by the API and must not be deleted.
- `streamlit_app` UI files are legacy and not the active product interface.
- Long-running worker campaigns may need polling/budget tuning.
- Supabase remote provisioning requires a real Supabase access token or DB password.
- Some old Python symbols/artifact paths may still contain `Hermes`; treat this as legacy naming, not an active dependency.

## References

- Bordbar, A., et al. (2015), *Personalized Whole-Cell Kinetic Models of Metabolism*, Cell Systems, 1(4), 283-292.
- `AgentOps/CalibrationOps.md`
- `AgentOps/Playbooks.md`
- `AgentOps/Memory.md`
