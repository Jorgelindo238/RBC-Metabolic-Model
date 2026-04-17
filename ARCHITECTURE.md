# RBC Metabolic Model - Architecture & Technical Guide

**Version:** 3.0  
**Author:** Jorgelindo da Veiga  
**Basis:** Bordbar et al. (2015) red blood cell metabolic reconstruction

---

## Overview

This repository combines four closely related systems:

1. A **mechanistic ODE model** for RBC metabolism in `src/`
2. A **calibration and benchmark workflow** centered on `src/MM_calibration.py`
3. A **bounded autoresearch orchestration layer** for calibration campaigns
4. A **Next.js + FastAPI research platform** (ClawBlood) in `apps/web/`, `apps/api/`, and `apps/marketing/`

> **Note:** `streamlit_app/` is a legacy interface. Its `core/` modules are still imported by the FastAPI backend via `sys.path`, but the Streamlit UI itself is superseded by the Next.js platform. Streamlit-only files (`app.py`, `pages/`, `.streamlit/`) are gitignored.

The current architecture is optimized for:

- mechanistic simulation of RBC storage physiology
- targeted parameter calibration against Bordbar experimental trajectories
- benchmark-driven calibration triage using policy and manifest files
- bounded agentic exploration of calibration configurations without mutating the scientific core by default
- interactive inspection of concentrations, fluxes, uploads, and pathway views
- Supabase-backed authentication, admin roles, and workspace context for the web platform
- a FastAPI backend that exposes the Python scientific logic to the Next.js frontend without duplicating or patching scientific source files

---

## Repository Structure

```text
Mario_RBC_up/
├── .streamlit/                         # Local Streamlit runtime config
├── AGENTS.md                           # Working rules for AI-assisted development
├── ARCHITECTURE.md                     # This document
├── AUTOSEARCH_ARCHITECTURE.md          # Autosearch runner boundaries and LangGraph implementation
├── CURVE_TRIAGE.md                     # Calibration promotion / triage notes
├── LICENSE
├── README.md
├── apps/                               # Product-plane applications
│   ├── api/                            # FastAPI backend bridging Python science to Next.js
│   │   ├── main.py                     # App entrypoint: sys.path setup, streamlit shim, router registration
│   │   ├── st_shim.py                  # Lightweight fake streamlit module for headless core imports
│   │   └── routers/
│   │       ├── simulation.py           # POST /simulate/
│   │       ├── flux.py                 # POST /flux/estimate, /flux/timeseries, GET /flux/kinetic-params
│   │       ├── pathway.py              # GET /pathway/network, POST /pathway/network-state
│   │       ├── sensitivity.py          # POST /sensitivity/compare
│   │       ├── calibration.py          # POST /calibration/run, GET /calibration/available-parameters
│   │       └── data.py                 # GET /data/experimental, /data/reactions, POST /data/upload, etc.
│   ├── marketing/                      # Future Next.js marketing website
│   └── web/                            # Next.js main application and RoBoCop home
│       ├── components/features/        # Feature components calling FastAPI endpoints
│       │   ├── SimulationWorkspace.tsx
│       │   ├── FluxAnalysis.tsx
│       │   ├── PathwayVisualization.tsx
│       │   ├── SensitivityAnalysis.tsx
│       │   ├── ParameterCalibration.tsx
│       │   └── DataUpload.tsx
│       └── lib/api-client.ts           # Axios wrapper for FastAPI backend
├── package.json                        # Root JS workspace manifest (no apps implemented yet)
├── packages/                           # Future shared JS/TS packages
│   └── contracts/                      # Shared contracts/adapters for bounded backend interfaces
├── pnpm-workspace.yaml                 # JS workspace boundary for apps/* and packages/* only
├── program.md                          # Autoresearch operating rules for calibration campaigns
├── RBC/
│   └── Rxn_RBC.txt                     # Reaction network definition
├── Simulations/                        # Generated outputs, reports, benchmark runs
├── config/                             # Calibration policies and benchmark manifests
│   ├── autoresearch_mutation_policy.yaml
│   ├── generated/                      # Candidate policy / manifest copies for bounded search
│   ├── policy_joint_vmax_km.json
│   ├── policy_km_only.json
│   ├── policy_vmax_only.json
│   ├── policy_vmax_then_km.json
│   ├── policy_staged_full.json
│   ├── policy_core_km_then_purine_transport.json
│   ├── policy_core_mixed_probe.json
│   ├── policy_core_upstream_probe.json
│   ├── rbc_autoresearch_policy.json
│   ├── rbc_calibration_benchmarks.json
│   ├── rbc_calibration_promotion_benchmarks.json
│   ├── rbc_core_km_only_benchmarks.json
│   ├── rbc_core_mixed_probe_benchmarks.json
│   └── rbc_core_upstream_probe_benchmarks.json
├── scripts/
│   ├── run_bounded_autosearch.py       # LangGraph-based bounded autosearch runner
│   ├── run_calibration_eval.py         # Policy/manifest benchmark runner
│   └── run_calibration_job.py          # Stable job-spec adapter delegating to the benchmark runner
├── skills/
│   └── calibration/
│       └── rbc-calibration-campaign/
│           └── SKILL.md                # Repo-local Hermes skill spec for campaign run + triage
├── services/                           # Future non-Next service shells and adapters
│   └── scientific-runtime/             # Reserved integration shell around bounded Python execution
├── src/                                # Core model, CLI, calibration engine
│   ├── main.py                         # Simulation CLI entrypoint
│   ├── MM_calibration.py               # Primary calibration entrypoint
│   ├── equadiff_brodbar.py             # Canonical ODE system and parameter injection
│   ├── curve_fit.py                    # Experimental curve fitting utilities
│   ├── curve_fitting_data.py           # Stored fitted trajectory coefficients
│   ├── parse_initial_conditions.py     # Initial condition loading
│   ├── ph_perturbation.py              # pH perturbation scenarios
│   ├── ph_sensitivity_params.py        # pH-dependent enzyme modulation
│   ├── bohr_effect.py                  # P50 / oxygen transport calculations
│   ├── flux_visualization.py           # Flux tracking and plotting
│   ├── visualization.py                # CLI metabolite plots and PDF export
│   ├── solver.py                       # ODE wrapper used by CLI flow
│   ├── model.py                        # Reaction network loading utilities
│   ├── parse.py                        # RBC reaction parser
│   ├── Data_Bordbar_et_al_exp.xlsx     # Experimental time series
│   ├── Data_Bordbar_et_al_exp_fitted_params.csv
│   └── Initial_conditions_JA_Final.xls
├── streamlit_app/                      # Streamlit web application
│   ├── app.py                          # Home page and custom sidebar navigation
│   ├── .streamlit/
│   ├── core/
│   │   ├── auth.py                     # Supabase authentication manager
│   │   ├── simulation_engine.py        # Streamlit wrapper around src/ model execution
│   │   ├── plotting.py                 # Plotly-based concentration views
│   │   ├── flux_plotting.py            # Flux plotting utilities
│   │   ├── flux_estimator.py           # Experimental flux estimation helpers
│   │   ├── data_loader.py              # Upload validation and ingest
│   │   ├── data_preprocessor.py        # Data cleaning and harmonization
│   │   ├── metabolite_mapper.py        # Column name mapping to model metabolites
│   │   ├── parameter_calibration.py    # In-app calibration helper class
│   │   ├── pathway_visualization.py    # Pathway graph and atlas views
│   │   ├── bohr_plotting.py            # Oxygen affinity visualizations
│   │   ├── sensitivity_engine.py       # Dataset comparison logic
│   │   ├── sensitivity_plotting.py     # Sensitivity plots
│   │   ├── reaction_info_complete.py   # Reaction metadata for UI display
│   │   └── styles.py                   # Shared branding and page styles
│   ├── data/
│   │   └── metabolite_synonyms.json
│   └── pages/
│       ├── 0_Login.py
│       ├── 1_Simulation.py
│       ├── 2_Flux_Analysis.py
│       ├── 3_Sensitivity_Analysis.py
│       ├── 4_Data_Upload.py
│       ├── 5_Parameter_Calibration.py
│       ├── 6_Admin.py
│       └── 7_Pathway_Visualization.py
├── tasks/                              # Active task tracker and lessons learned
│   ├── lessons.md
│   └── todo.md
├── tests/                              # User-kept test data / helper scripts
├── requirements.txt
└── SUPABASE_SETUP.sql                  # Auth and profile schema
```

---

## System Boundaries

## Platform Workspace Boundary

The repository maintains a JS workspace for the product / interface plane:

- `apps/web` for the main Next.js application (live, with 6 interactive feature surfaces)
- `apps/api` for the FastAPI backend bridging Python scientific logic to Next.js (live, 6 routers)
- `apps/marketing` for the future Next.js marketing website
- `packages/contracts` for shared TS contracts and thin adapters around bounded backend interfaces

This workspace is intentionally limited to `apps/*` and `packages/*` through `pnpm-workspace.yaml`.

The Python scientific execution plane remains outside that workspace.

- `src/` remains the scientific execution authority
- `scripts/` remains the orchestration and benchmark boundary layer
- `apps/api` imports directly from `streamlit_app/core/` and `src/` via `sys.path` — it does **not** copy, patch, or redefine scientific logic
- `services/scientific-runtime/` is reserved for future deployment shells or API adapters that call the bounded Python interfaces without becoming the scientific source of truth

This split is designed so Next.js surfaces, Supabase-backed dashboards, LangGraph workflows, LangSmith traces, RoBoCop chat actions, and optional Telegram/OpenClaw bridges all converge on the same bounded execution path instead of bypassing scientific authority.

### 1. Simulation Kernel

The canonical biochemical model lives in `src/equadiff_brodbar.py`.

It is responsible for:

- state vector definition
- reaction-rate equations
- injectable `custom_params`
- pH dynamics and optional pH modulation
- Bohr effect tracking hooks
- flux tracking hooks
- experimental first-value loading for initial conditions

### 2. Calibration Engine

The calibration workflow is centered on `src/MM_calibration.py`.

It provides:

- Optuna-based or fallback optimization
- pathway-scoped target selection
- parameter-scope filtering
- monitor metrics and regression gating
- stage-plan execution for focused campaigns
- structured reports and saved parameter artifacts

Benchmark orchestration sits one layer above it in `scripts/run_calibration_eval.py`.

A stable orchestration adapter now sits one layer above the benchmark harness in `scripts/run_calibration_job.py`.

A stable completed-run artifact contract now sits alongside the emitted benchmark outputs in `scripts/calibration_artifacts.py`.

A stable run registry / persistence contract now sits one layer above the completed-run manifest in `scripts/run_registry.py`.

### 3. Legacy Streamlit Workspace (superseded)

The original Streamlit app in `streamlit_app/` has been fully superseded by the Next.js + FastAPI platform.

**Important:** `streamlit_app/core/` is still a runtime dependency of the FastAPI backend — it is imported via `sys.path` and must not be deleted or gitignored. Only the Streamlit UI files (`app.py`, `pages/`, `.streamlit/`) are gitignored as they are no longer the primary interface.

### 3b. FastAPI Backend (`apps/api`)

The FastAPI backend exposes the Python scientific logic from `streamlit_app/core/` and `src/` to the Next.js frontend over HTTP without copying or patching scientific files.

**Architecture:**

- `main.py` adds `streamlit_app/` and `src/` to `sys.path` so `from core.* import ...` resolves to the original modules
- A lightweight **streamlit shim** (`st_shim.py`) is registered in `sys.modules['streamlit']` before any core import, mocking `st.session_state`, `st.cache_data`, `st.error/info/warning` with harmless no-ops
- numpy arrays are recursively serialized to native Python types for JSON responses

**Routers (6 total):**

| Router | Prefix | Core Module(s) | Key Endpoints |
|---|---|---|---|
| `simulation.py` | `/simulate` | `core.simulation_engine` | `POST /` |
| `flux.py` | `/flux` | `core.flux_estimator` | `POST /estimate`, `POST /timeseries`, `GET /kinetic-params` |
| `pathway.py` | `/pathway` | `core.pathway_visualization` | `GET /network`, `POST /network-state` |
| `sensitivity.py` | `/sensitivity` | `core.sensitivity_engine` | `POST /compare` |
| `calibration.py` | `/calibration` | `core.parameter_calibration` | `POST /run`, `GET /available-parameters` |
| `data.py` | `/data` | `core.data_loader`, `core.data_preprocessor`, `core.metabolite_mapper`, `core.reaction_info_complete`, `core.flux_estimator` | `GET /experimental`, `GET /initial-conditions`, `GET /reactions`, `POST /upload`, `POST /map-metabolites`, `POST /compare-fluxes`, `POST /export-csv` |

**This backend must not:**

- copy or patch files from `streamlit_app/core/` or `src/`
- redefine ODE logic, calibration scopes, or scientific parameters
- bypass the existing calibration pipeline for benchmark-driven work

### 4. Autoresearch Orchestration Layer

This layer defines the bounded rules for agent-driven calibration search.

It constrains mutation to approved configuration surfaces by default, accepts a structured job spec through `scripts/run_calibration_job.py`, and delegates execution to `scripts/run_calibration_eval.py` over the scientific engine in `src/MM_calibration.py`.

The current implementation uses a LangGraph `StateGraph` in `scripts/run_bounded_autosearch.py` with four sequential nodes (`propose → evaluate → verify → archive`). Every run—dry or real, pass or fail—writes a structured decision record to a persistent append-only JSONL ledger at `Simulations/brodbar/autoresearch/agent_orchestration/autosearch_memory.jsonl`.

See `AUTOSEARCH_ARCHITECTURE.md` for the full state schema, node descriptions, and boundary definitions.

### 5. Product / Interface Plane

The product plane lives in Next.js (`apps/web`) backed by FastAPI (`apps/api`) and remains downstream of the existing scientific and orchestration boundaries.

Its current and planned responsibilities are:

- **Live:** interactive simulation, flux analysis, pathway visualization, sensitivity analysis, parameter calibration, and data upload via FastAPI-backed Next.js feature components
- **Live:** authenticated product UX with Supabase SSR, workspace-aware access, and durable workspace preferences
- **Live:** calibration registry browsing via Supabase-backed reads
- **Planned:** a separate marketing surface in `apps/marketing`
- **Planned:** future RoBoCop prompt-driven actions and explanations inside the main app
- **Planned:** optional secondary chat shells such as Telegram/OpenClaw that reuse the same bounded backend interfaces

This plane must not:

- bypass `scripts/run_calibration_job.py` for run launches
- bypass `completed_run_manifest.json` for completed-run artifact reads
- bypass `calibration_run_registry_record` for lightweight registry/query workflows
- redefine or reimplement scientific logic in JS/TS
- copy or patch Python scientific files — `apps/api` imports them in-place via `sys.path`

---

## Core Runtime Architecture

### Simulation data flow

```text
User input / CLI args
    -> initial condition loading
    -> optional parameter injection from JSON
    -> optional pH perturbation configuration
    -> ODE solve via scipy.solve_ivp
    -> optional flux / Bohr tracking
    -> plotting, export, or downstream comparison
```

### Calibration data flow

```text
Calibration job JSON
    -> scripts/run_calibration_job.py
    -> bounded job-spec validation
    -> policy JSON + benchmark manifest JSON
    -> scripts/run_calibration_eval.py
    -> src/MM_calibration.run_calibration(...)
    -> stage_plan resolution
    -> constrained parameter search
    -> calibration_report.json + best_params.json
    -> aggregate scoring
    -> `eval_summary.json` generation
    -> TSV result accumulation for cross-run comparison
    -> completed_run_manifest.json generation
    -> run_registry_record extraction for persistence/query callers
```

### Streamlit data flow

```text
Streamlit page
    -> streamlit_app/core/* helper module
    -> src/ simulation or calibration logic
    -> session_state persistence
    -> Plotly / tables / downloads / status cards
```

### FastAPI + Next.js data flow

```text
Next.js feature component (client)
    -> axios POST/GET to http://localhost:8000
    -> apps/api/routers/*.py
    -> streamlit_app/core/* (imported via sys.path, streamlit shim active)
    -> src/* ODE and calibration logic (imported via sys.path)
    -> numpy→native serialization
    -> JSON response to Next.js
    -> SVG/table/chart rendering in browser
```

### Autoresearch data flow

```text
program.md + autoresearch_mutation_policy.yaml
    -> scripts/run_bounded_autosearch.py (LangGraph StateGraph)
    -> node_propose: config/generated/ candidate policy and manifest creation
    -> node_evaluate: subprocess to scripts/run_calibration_job.py
    -> node_verify: read eval_summary.json, apply keep/discard threshold
    -> node_archive: append decision record to autosearch_memory.jsonl
                     + write local autosearch_decision.json (real runs only)
```

---

## Model Specifications

### Canonical state dimensions

The **current canonical constants** are defined in `src/equadiff_brodbar.py`:

- **Base metabolites:** `113`
- **Dynamic intracellular pH (`pHi`) index:** `113`
- **Dynamic extracellular pH (`pHe`) index:** `114`
- **Total state variables:** `115`

This reflects the expanded model state used by the current Brodbar implementation, including additional extracellular / side-pool species beyond the older 108-state version.

### Important note on stale counts

Some older docstrings and comments still refer to older metabolite counts.
- Some older docstrings and CLI text in the repository still mention `108` or `114` metabolites. Those strings are historical and do **not** represent the current canonical model constants.

For architecture and implementation decisions, the authoritative source is:

- `NUM_BASE_METABOLITES = 113`
- `NUM_TOTAL_METABOLITES = 115`

from `src/equadiff_brodbar.py`.

### Experimental data coverage

The repository uses Bordbar experimental time-series data from:

- `src/Data_Bordbar_et_al_exp.xlsx`

The current calibration mapping in `src/MM_calibration.py` supports a broad metabolite set spanning:

- glycolysis and extracellular anchors
- adenylates and purine-related metabolites
- amino acid / redox / side-pathway metabolites
- newly represented extracellular species such as `EOXOP`, `ESER`, `EARG`, `EGSSG`, `EGSH`, and `EASN`

### Simulation horizon

Typical storage-condition runs span up to **42 days**, with shorter horizons also used in targeted calibration campaigns.

---

## Major Biological / Numerical Subsystems

### Glycolysis and related energy coupling

The model explicitly represents:

- glucose uptake and entry into glycolysis
- upper glycolysis (`GLC`, `G6P`, `F6P`, `F16BP`)
- lower glycolysis (`P3G`, `P2G`, `PEP`, `PYR`, `LAC`)
- adenylate coupling (`ATP`, `ADP`, `AMP`)
- Rapoport-Luebering shunt behavior via `B23PG`

Recent calibration work has focused heavily on:

- `core_glycolysis_energy`
- lower-glycolysis probe scopes
- upstream HK/PFK gate probes

### Pentose phosphate and redox behavior

The model includes PPP and redox-related terms linked to:

- `G6P`
- NAD / NADH
- NADP / NADPH
- `GSH` / `GSSG`

These pools are important both biologically and numerically, especially for conservation checks and long-horizon stability.

### pH dynamics

The pH subsystem supports:

- dynamic intracellular pH (`pHi`)
- dynamic extracellular pH (`pHe`)
- optional perturbation scenarios through `src/ph_perturbation.py`
- enzyme modulation through `src/ph_sensitivity_params.py`

Core transport / buffering constants are defined in `src/equadiff_brodbar.py`:

- `K_DIFF_H`
- `K_NHE`
- `K_AE1`
- `BETA_BUFFER`

### Bohr effect tracking

`src/bohr_effect.py` computes oxygen-affinity-related outputs such as:

- `P50`
- arterial / venous saturation
- oxygen extraction fraction
- oxygen content metrics

This subsystem is optionally activated during simulation and tracked alongside the ODE solution.

---

## Parameter Injection and Configuration Model

The simulation kernel accepts a `custom_params` dictionary.

This allows runtime injection of calibrated or experimental parameter sets without mutating the base model code.

Typical sources are:

- `Simulations/brodbar/calibration/best_params.json`
- benchmark-specific `best_params.json` files inside autoresearch run directories

Both the CLI and the Streamlit simulation engine support loading parameter files automatically when desired.

---

## Calibration Architecture

### Primary entrypoint

The primary calibration engine is:

- `src/MM_calibration.py`

This is the authoritative calibration implementation for current work.

### Responsibilities of `MM_calibration.py`

It defines:

- experimental-to-model mapping
- target scopes
- target weights
- endpoint weighting
- monitor regression limits
- parameter classes (`vmax`, `km`, regulation, transport, etc.)
- identifiability groupings
- phase parameter dictionaries
- parameter-scope selection logic
- explicit stage-plan resolution
- optimization execution and reporting

### Benchmark harness

`scripts/run_calibration_eval.py` wraps `run_calibration(...)` and adds:

- policy loading
- benchmark manifest loading
- guardrail enforcement
- multi-case benchmark execution
- aggregate scoring
- `eval_summary.json` generation
- TSV result accumulation for cross-run comparison

`scripts/run_calibration_job.py` adds a stable outer boundary for external orchestrators:

- structured job-spec loading
- bounded path validation for policy and manifest inputs
- optional dry-run validation
- delegation to `scripts/run_calibration_eval.py`
- structured JSON result payloads for callers
- normalized completed-run artifact manifests for successful benchmark runs

`scripts/calibration_artifacts.py` adds a stable output boundary for completed runs:

- reads authoritative run outputs instead of changing calibration behavior
- resolves top-level input/output artifacts from a completed run directory
- normalizes case-level summaries plus artifact pointers for downstream consumers
- writes `completed_run_manifest.json` into the run directory for machine callers

`scripts/run_registry.py` adds a stable persistence boundary above the artifact manifest:

- extracts a compact registry-ready subset from `completed_run_manifest.json`
- keeps queryable summary fields separate from larger artifact references
- preserves artifact paths for Supabase rows, LangGraph state, LangSmith metadata, and future RoBoCop chat/figure workflows
- leaves scientific files on disk as the authoritative artifact source of truth

### Configuration model

The calibration system is driven by JSON configuration instead of hard-coded campaign logic.

#### Policy files in `config/`

Policies define:

- baseline run arguments
- optimization strategy
- stage plan
- guardrails
- allowed mutation space for exploratory evaluation

#### Manifest files in `config/`

Benchmark manifests define:

- benchmark cases
- per-case overrides
- scoring weights
- robustness scoring rules
- discard penalties and endpoint weighting

### Current focused calibration policies

The repository now includes focused policy/manifest pairs for targeted investigation, including:

- `policy_core_km_then_purine_transport.json`
- `rbc_core_km_only_benchmarks.json`
- `policy_core_mixed_probe.json`
- `rbc_core_mixed_probe_benchmarks.json`
- `policy_core_upstream_probe.json`
- `rbc_core_upstream_probe_benchmarks.json`

These focused campaigns are intended to test specific mechanistic hypotheses before widening scope.

### Recent focused-scope additions

Recent calibration work added an explicit upstream hexose-phosphate gate probe:

- **param scope:** `core_upstream_glycolysis_probe`
- **target scope:** `core_glycolysis_energy`

It was introduced to test whether the remaining `G6P / AMP / PYR` mismatch is driven by upstream gate control rather than by lower-glycolysis pacing alone.

### Agentic orchestration layer

The autoresearch orchestration layer is a thin layer that governs how an agent may explore the calibration surface.

It is made of:

 - `program.md` - the campaign charter defining objective, experiment loop, required reporting, keep/discard logic, and promotion rules
 - `config/autoresearch_mutation_policy.yaml` - a strict mutation contract defining approved templates, mutable fields, approval-required fields, immutable paths, and rejection triggers
 - `config/generated/` - the intended workspace for candidate policy and manifest copies created during bounded search
 - `skills/calibration/rbc-calibration-campaign/SKILL.md` - a repo-local Hermes skill spec describing how to run and triage RBC calibration campaigns
 - `scripts/run_calibration_job.py` - a stable machine-callable adapter that validates job specs and forwards bounded runs to the fixed evaluator
 - `scripts/run_bounded_autosearch.py` - LangGraph-based state machine implementing the bounded search loop with four nodes: `propose`, `evaluate`, `verify`, `archive`
 - `Simulations/brodbar/autoresearch/agent_orchestration/autosearch_memory.jsonl` - append-only global memory ledger recording every search decision
 - `AUTOSEARCH_ARCHITECTURE.md` - detailed boundary definitions, state schema, node descriptions, and CLI usage

 This layer does **not** replace `src/MM_calibration.py` or `scripts/run_calibration_eval.py`.

By default, this orchestration layer is **config-only**:

- committed policy templates in `config/` are treated as read-only inputs
- generated candidates should be created under `config/generated/`
- scientific source files, data files, and prior benchmark artifacts remain immutable unless the human explicitly opens a wider mutation scope

---

## CLI Architecture

### Main simulation CLI

`src/main.py` is the user-facing simulation CLI.

It handles:

- model selection
- parameter file loading
- curve-fit strength selection
- pH perturbation arguments
- simulation execution
- plot/PDF generation

Typical usage:

```bash
python src/main.py --curve-fit 1.0
python src/main.py --curve-fit 1.0 --ph-perturbation acidosis --ph-severity severe
python src/main.py --curve-fit 1.0 --ph-perturbation ramp --ph-target 6.9 --ph-duration 8
```

### Output locations

Standard CLI outputs are written under:

```text
Simulations/brodbar/
├── metabolites/
├── fluxes/
├── ph_analysis/
├── bohr_effect/
└── calibration/
```

Focused benchmark campaigns additionally create timestamped run directories under:

```text
Simulations/brodbar/autoresearch/
```

The persistent autosearch memory ledger is written to:

```text
Simulations/brodbar/autoresearch/agent_orchestration/autosearch_memory.jsonl
```

Candidate configuration files produced for bounded agentic search are kept separately under:

```text
config/generated/
```

This separation keeps mutable search inputs distinct from immutable benchmark outputs and reports.

---

## Streamlit Application Architecture

### Navigation model

The Streamlit workspace uses **custom button-based navigation** in `streamlit_app/app.py` with `st.switch_page(...)`.

The current sidebar shows:

- Home
- Login when unauthenticated
- Simulation
- Flux Analysis
- Parameter Calibration
- Pathway Visualization
- Data Upload
- Admin for admin users

### Sensitivity page status

`streamlit_app/pages/3_Sensitivity_Analysis.py` still exists in the repository, but it is **intentionally not linked in the main sidebar navigation**.

This is an architectural choice, not a deleted feature.

### Streamlit page map

- `0_Login.py` - authentication and account access
- `1_Simulation.py` - simulation controls and execution
- `2_Flux_Analysis.py` - reaction-level and pathway-level flux inspection
- `3_Sensitivity_Analysis.py` - retained page file, currently hidden from primary nav
- `4_Data_Upload.py` - upload, validation, and metabolite mapping
- `5_Parameter_Calibration.py` - exploratory in-app calibration workspace
- `6_Admin.py` - operational/admin functions for authorized users
- `7_Pathway_Visualization.py` - pathway graph / atlas views

### Important architectural distinction

There are **two calibration layers** in the repository:

### 1. Research / benchmark calibration

- implemented in `src/MM_calibration.py`
- used for reproducible benchmark campaigns
- saves JSON reports and benchmark artifacts

### 2. In-app exploratory calibration

- implemented in `streamlit_app/core/parameter_calibration.py`
- designed for interactive use inside the UI
- uses local optimization helpers for exploratory fitting

These two systems are related conceptually but are not the same implementation.

### Streamlit backend modules

Key modules in `streamlit_app/core/`:

- `simulation_engine.py` - bridge from UI controls to `src/` simulation execution
- `auth.py` - Supabase auth and profile lookup
- `data_loader.py` - upload validation and parsing
- `data_preprocessor.py` - uploaded dataset cleanup
- `metabolite_mapper.py` - column-to-model mapping
- `plotting.py` - Plotly concentration plotting
- `flux_plotting.py` - UI-facing flux visualizations
- `pathway_visualization.py` - metabolic atlas/pathway graph rendering
- `styles.py` - shared branded page styles and header rendering

### Recent Streamlit UI changes

The current app reflects a more research-oriented branding pass:

- shared header rendering via `render_page_header(...)`
- more consistent page titles and subtitles
- refined burgundy/red theme styling in `streamlit_app/core/styles.py`
- reduced demo-style celebration effects
- `Pathway Visualization` branded in-page as an **RBC Metabolic Atlas**

---

## Authentication and Admin Architecture

The authentication layer is implemented in `streamlit_app/core/auth.py` using Supabase.

### Current behavior

- email/password sign-up
- email/password sign-in
- user profile lookup via `user_profiles`
- admin role lookup
- optional last-login update

### Required configuration

The app expects Supabase credentials in Streamlit secrets:

```toml
[supabase]
url = "https://your-project.supabase.co"
anon_key = "your-anon-key"
```

### Database bootstrap

Schema setup lives in:

- `SUPABASE_SETUP.sql`

---

## Benchmark and Reporting Artifacts

Calibration and benchmark runs commonly emit:

- `best_params.json`
- `best_params.py`
- `calibration_report.json`
- `results.tsv`
- `eval_summary.json`
- `completed_run_manifest.json`
- snapshot copies of policies/manifests

These artifacts are important for:

- comparing campaigns across seeds and horizons
- promotion/discard decisions
- regression analysis
- reproducing accepted parameter sets
- providing one stable machine-readable boundary for dashboards, orchestration, and trace attachment workflows

---

## Current Architectural Conventions

### 1. Minimal focused-scope calibration first

Recent development favors narrow policy-driven probes before wider compensation scopes are opened.

### 2. Policy/manifest driven experimentation

New calibration campaigns should usually be introduced by:

- adding or reusing a `param_scope` in `MM_calibration.py`
- creating a policy JSON
- creating a benchmark manifest JSON
- evaluating the full benchmark before promoting conclusions

### 3. Canonical model constants live in code

When documentation and source text disagree, prefer:

- `src/equadiff_brodbar.py` for state dimensions and ODE structure
- `src/MM_calibration.py` for calibration scopes and targets
- `streamlit_app/app.py` for the live app navigation model

---

## Local Development

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run the Streamlit app

```bash
streamlit run streamlit_app/app.py
```

### Run the FastAPI backend

```bash
cd apps/api
pip install python-multipart  # required for file upload
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### Run the Next.js frontend

```bash
cd apps/web
npm install
npm run dev  # starts on port 3000
```

### Run a simulation from CLI

```bash
python src/main.py --curve-fit 1.0
```

### Run benchmark evaluation

```bash
python scripts/run_calibration_eval.py --policy config/policy_core_upstream_probe.json --manifest config/rbc_core_upstream_probe_benchmarks.json
```

---

## Known Technical Caveats

- Some legacy docstrings and comments still refer to older metabolite counts.
- `streamlit_app/pages/3_Sensitivity_Analysis.py` is retained but not part of the primary Streamlit sidebar path (it is exposed in the Next.js platform via the sensitivity router).
- The Streamlit in-app calibration helper is not a substitute for the benchmark-driven `MM_calibration.py` workflow.
- The FastAPI calibration router (`apps/api/routers/calibration.py`) wraps the in-app `ParameterCalibrator`, not the benchmark-driven `MM_calibration.py`.
- `tests/` contains user-kept data/utilities and should not be treated as disposable cleanup material.
- The `st_shim.py` module in `apps/api/` provides a fake streamlit to allow headless import of `streamlit_app/core/` modules; it is not a full streamlit replacement.

---

## References

1. **Bordbar, A., et al. (2015)** - *Personalized Whole-Cell Kinetic Models of Metabolism* - Cell Systems, 1(4), 283-292
2. **Streamlit Documentation** - [https://docs.streamlit.io](https://docs.streamlit.io)
3. **Supabase Documentation** - [https://supabase.com/docs](https://supabase.com/docs)

---

## License

MIT License - see `LICENSE`

---

**Last Updated:** March 2026
