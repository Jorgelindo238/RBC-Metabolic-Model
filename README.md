# airbc - AI-Powered Blood Bag Conservation Platform

<p align="center">
  <img src="apps/web/public/favicon.svg" alt="airbc Logo" width="80" height="80" />
</p>

<p align="center">
  <strong>Research, simulate, calibrate, and monitor red blood cell storage metabolism with RoBoCop-assisted interpretation.</strong>
</p>

<p align="center">
  <a href="https://github.com/Jorgelindo238/RBC-Metabolic-Model"><img src="https://img.shields.io/badge/GitHub-RBC--Metabolic--Model-181717?logo=github" alt="GitHub" /></a>
  <img src="https://img.shields.io/badge/Next.js-15-black?logo=nextdotjs" alt="Next.js 15" />
  <img src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white" alt="React 19" />
  <img src="https://img.shields.io/badge/FastAPI-Python-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Supabase-Auth-3FCF8E?logo=supabase&logoColor=white" alt="Supabase" />
  <img src="https://img.shields.io/badge/Tailwind_CSS-v4-06B6D4?logo=tailwindcss&logoColor=white" alt="Tailwind CSS v4" />
  <img src="https://img.shields.io/badge/TypeScript-5.9-3178C6?logo=typescript" alt="TypeScript" />
  <img src="https://img.shields.io/badge/License-Proprietary-red" alt="License" />
</p>

---

airbc is a research and monitoring platform for studying **red blood cell metabolism during storage**. It helps researchers and blood-banking teams compare simulated trajectories against experimental data, calibrate kinetic parameters, inspect pathway behavior, and interpret results with RoBoCop.

The scientific model is based on the **Bordbar et al. (2015)** whole-cell kinetic reconstruction of RBC metabolism.

<p align="center">
  <a href="https://app.airbc.org/sign-up"><strong>Create account</strong></a> |
  <a href="https://app.airbc.org/sign-in">Sign in</a> |
  <a href="https://airbc.org">Marketing site</a>
</p>

---

## Current Status

- `marketing` is live at [airbc.org](https://airbc.org)
- `web` is live at [app.airbc.org](https://app.airbc.org)
- `airbc-api` is live at [api.airbc.org](https://api.airbc.org)
- `calibration-api` is hosted on Hetzner at [calibration-api.airbc.org](https://calibration-api.airbc.org)
- Vercel projects for `web`, `marketing`, and `airbc-api` deploy from GitHub `main`

The calibration product surface includes:
- dataset-aware custom-data planning
- report-level curve triage
- pure-ODE replay triage
- combined triage
- `single_run` and `strategy_race` modes
- dataset fingerprint memory
- bounded teacher-flux rescue for supported reactions
- worker-backed long-running calibration jobs

---

## What airbc Does

- **Upload** experimental RBC storage datasets
- **Simulate** metabolite trajectories over configurable storage horizons
- **Calibrate** kinetic parameters against observed curves
- **Compare** custom data against model trajectories
- **Inspect** fluxes and pathway-level behavior
- **Monitor** bag-level quality forecasts and alerts
- **Explain** results through RoBoCop research context

---

## Platform Architecture

```text
apps/
|-- web/                 -> Next.js authenticated research platform
|-- api/                 -> FastAPI scientific API and orchestration adapter
|-- calibration-worker/  -> long-running calibration worker
`-- marketing/           -> public product site

src/                     -> mechanistic ODE model and calibration engine
streamlit_app/core/      -> legacy scientific helper modules still imported by API
services/robocop/        -> RoBoCop triage, orchestration, memory, and policy services
packages/contracts/      -> shared schemas and contract examples
AgentOps/                -> operational cockpit for Codex/RoBoCop work
```

| Layer | Technology | Purpose |
|---|---|---|
| Web | Next.js 15, React 19, Tailwind CSS, shadcn/ui | Authenticated research and monitoring platform |
| API | FastAPI, Python, scipy | Simulation, upload handling, flux/pathway APIs, calibration adapter |
| Worker | FastAPI/uvicorn, Python | Long-running calibration orchestration outside the Vercel request path |
| Auth | Supabase | User accounts, sessions, profiles, roles |
| AI/Ops | RoBoCop, LangGraph, LangSmith, DeepAgents-ready design | Interpretation, triage, bounded campaign orchestration |
| Marketing | Next.js 15 | Public product narrative |

See [ARCHITECTURE.md](ARCHITECTURE.md) for the technical system map and [AgentOps/CalibrationOps.md](AgentOps/CalibrationOps.md) for RoBoCop calibration orchestration.

---

## Main Features

### Research

- Data Upload
- Calibration Registry
- Parameter Calibration
- Simulation
- Flux Analysis
- Pathway Visualization
- RoBoCop research chat

### Monitoring

- Monitoring Overview
- Bag Repository
- Quality Forecast
- Alerts

### Calibration Orchestration

- Dataset-aware planner
- Strategy racing
- Pure-ODE replay
- Combined triage
- Fingerprint memory
- Teacher-flux rescue
- Worker-backed jobs

---

## Quick Start

### Prerequisites

- Node.js 22+
- Python 3.12
- npm

### Install dependencies

```bash
# Web app
cd apps/web
npm install

# Marketing site
cd ../marketing
npm install

# Python dependencies
cd ../../
pip install -r requirements.txt
pip install -r api/requirements.txt
pip install -r apps/calibration-worker/requirements.txt
```

### Configure Supabase

Run `SUPABASE_SETUP.sql` in your Supabase project SQL editor, then promote your account:

```sql
INSERT INTO user_profiles (id, email, full_name, organization, role)
SELECT id, email, raw_user_meta_data->>'full_name', raw_user_meta_data->>'institution', 'admin'
FROM auth.users WHERE email = 'your@email.com';
```

### Run locally

```bash
# API
cd apps/api
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# Calibration worker
cd ../calibration-worker
python -m uvicorn main:app --host 127.0.0.1 --port 8010

# Web
cd ../web
npm run dev

# Marketing
cd ../marketing
npm run dev
```

### Worker wiring

The web app expects:

- `CALIBRATION_API_BASE_URL`
- `CALIBRATION_API_SHARED_SECRET`

The Hetzner worker expects:

- `CALIBRATION_WORKER_SHARED_SECRET`

The Vercel shared secret and worker shared secret must match.

---

## API Surfaces

| Router | Prefix | Key Endpoints |
|---|---|---|
| Simulation | `/simulate` | `POST /` |
| Flux | `/flux` | `POST /estimate`, `POST /timeseries`, `GET /kinetic-params` |
| Pathway | `/pathway` | `GET /network`, `POST /network-state` |
| Sensitivity | `/sensitivity` | `POST /compare` |
| Calibration | `/calibration` | `POST /run`, `POST /jobs`, `GET /jobs/{id}`, `GET /available-parameters` |
| Data | `/data` | `GET /experimental`, `GET /reactions`, `POST /upload`, `POST /map-metabolites` |
| RoBoCop | `/robocop` | `POST /research/chat` |

---

## Scientific Basis

- 113 metabolites tracked across the storage horizon
- roughly 200 reactions spanning the RBC metabolic network
- Bordbar et al. (2015) as the mechanistic basis
- experimental fit and pure-ODE physiological replay both treated as first-class evaluation signals

Reference:

- Bordbar, A., et al. (2015), *Personalized Whole-Cell Kinetic Models of Metabolism*, Cell Systems, 1(4), 283-292

---

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - technical architecture and system boundaries
- [AgentOps/README.md](AgentOps/README.md) - operational cockpit for Codex/RoBoCop work
- [AgentOps/CalibrationOps.md](AgentOps/CalibrationOps.md) - calibration/autoresearch operating contract
- [AgentOps/Playbooks.md](AgentOps/Playbooks.md) - reusable deployment, smoke, and calibration workflows

---

<p align="center">
  <strong>airbc</strong> | Polytechnique Montreal | Jolicoeur Lab | 2026
</p>
