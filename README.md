# airbc - AI-Powered Blood Bag Conservation Platform

<p align="center">
  <img src="apps/web/public/favicon.svg" alt="airbc Logo" width="80" height="80" />
</p>

<p align="center">
  <strong>Monitor and interpret blood bag conservation in real time with RoBoCop-assisted alerting</strong>
</p>

<p align="center">
  <a href="https://github.com/Jorgelindo238/RBC-Metabolic-Model"><img src="https://img.shields.io/badge/GitHub-RBC--Metabolic--Model-181717?logo=github" alt="GitHub" /></a>
  <img src="https://img.shields.io/badge/Next.js-15-black?logo=nextdotjs" alt="Next.js 15" />
  <img src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white" alt="React 19" />
  <img src="https://img.shields.io/badge/FastAPI-Python-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Supabase-Auth-3FCF8E?logo=supabase&logoColor=white" alt="Supabase" />
  <img src="https://img.shields.io/badge/Tailwind_CSS-v4-06B6D4?logo=tailwindcss&logoColor=white" alt="Tailwind CSS v4" />
  <img src="https://img.shields.io/badge/TypeScript-5.9-3178C6?logo=typescript&logoColor=white" alt="TypeScript" />
  <img src="https://img.shields.io/badge/License-Proprietary-red" alt="License" />
</p>

---

airbc is a research platform for studying **red blood cell metabolism during storage**. It helps researchers and blood banking teams track glucose depletion, ATP decline, and metabolic drift throughout the storage period, then compare simulated trajectories against experimental data and calibration outcomes.

Built on the **Bordbar et al. (2015)** whole-cell kinetic reconstruction of RBC metabolism.

<p align="center">
  <a href="https://app.airbc.org/sign-up"><strong>Create free account</strong></a> ·
  <a href="https://app.airbc.org/sign-in">Sign in</a> ·
  <a href="https://calendar.google.com/calendar/appointments">Schedule a demo</a>
</p>

---

## Current Platform Status

- `marketing` is live at [airbc.org](https://airbc.org)
- `web` is live at [app.airbc.org](https://app.airbc.org)
- the calibration UI now includes:
  - dataset-aware planning
  - calibration-report triage
  - pure-ODE triage
  - combined triage wiring
  - `single_run` and `strategy_race` modes
  - dataset fingerprint memory
  - bounded teacher-flux rescue for supported reactions
- the production calibration proxy is **not fully active yet**
  - `web` still needs a live worker behind `CALIBRATION_API_BASE_URL`
  - `web` still needs `CALIBRATION_API_SHARED_SECRET`

The next infrastructure milestone is to connect the future Hetzner calibration worker to those two environment variables.

---

## What airbc Does

- **Simulate** dynamic RBC metabolic behavior over configurable storage horizons
- **Monitor** glucose, ATP, lactate, 2,3-BPG, glutathione, and the broader metabolite panel
- **Alert** on meaningful metabolic shifts with RoBoCop-assisted summaries
- **Compare** model predictions against custom experimental storage data
- **Calibrate** enzyme kinetic parameters against observed trajectories
- **Plan** custom-data calibration campaigns with dataset-aware stage planning
- **Triage** calibration results with report-level and pure-ODE physiological checks
- **Orchestrate** best-of-N custom-data strategy racing with bounded worker-side logic
- **Visualize** pathway-level metabolic network structure and flux distributions

---

## Platform Architecture

```text
apps/
|-- web/                 -> Next.js 15 authenticated research platform (app.airbc.org)
|-- api/                 -> FastAPI scientific backend and orchestration adapter
|-- calibration-worker/  -> worker process for long-running calibration jobs
`-- marketing/           -> marketing homepage (airbc.org)

src/                     -> mechanistic ODE model and calibration engine
streamlit_app/core/      -> shared Python scientific modules imported by the API
services/robocop/        -> RoBoCop runtime, triage logic, and orchestration policy
```

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | Next.js 15, React 19, shadcn/ui, Tailwind CSS v4 | Authenticated researcher platform |
| API | FastAPI, Python, scipy | Scientific simulation, upload handling, and calibration adapter |
| Worker | Python, uvicorn | Long-running calibration orchestration outside the web request path |
| Auth | Supabase | User profiles, roles, and workspace context |
| AI | RoBoCop / Hermes-assisted orchestration | Interpretation, triage, and bounded campaign planning |
| Marketing | Next.js 15 | Product homepage at airbc.org |

---

## Features

### Research Platform (`apps/web`)

- **Simulation Workspace** - run storage-condition ODE simulations with pH perturbations
- **Flux Analysis** - Michaelis-Menten flux estimation across pathway groups
- **Pathway Visualization** - KEGG-style SVG network graph and state overlays
- **Sensitivity Analysis** - compare datasets with per-metabolite validation metrics
- **Parameter Calibration** - run `single_run` or `strategy_race` calibration flows
- **Data Upload** - upload CSV or Excel experimental data with metabolite mapping
- **RoBoCop Assistant** - grounded simulation interpretation and research chat
- **Calibration Registry** - browse stored calibration runs and benchmark outcomes
- **Admin Dashboard** - user management, role control, and platform statistics

### Calibration Orchestration

- **Dataset-aware planner** - builds custom-data stage guidance before calibration
- **Curve triage** - classifies fit gains as keep, caveat, discard, or review
- **Pure-ODE replay** - reruns a physiological replay after fitting
- **Combined triage** - merges calibration and pure-ODE verdicts
- **Strategy racing** - compares bounded strategies on the same dataset
- **Fingerprint memory** - warm-starts similar panels from prior successful runs
- **Teacher-flux rescue** - bounded rescue path for supported reactions

### Authentication

- Google OAuth sign-in
- Email/password sign-in and sign-up
- Researcher profiles
- Admin role system with Supabase-backed permissions
- Session middleware and protected routes

### Marketing Site (`apps/marketing`)

- Homepage and product narrative for airbc
- Direct sign-in/sign-up links to `app.airbc.org`
- Product positioning for simulation, monitoring, and AI-assisted review

---

## Quick Start

### Prerequisites

- Node.js 22+
- Python 3.12+
- npm

### 1. Install dependencies

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

### 2. Set up Supabase

Run `SUPABASE_SETUP.sql` in your Supabase project SQL Editor, then promote your account:

```sql
INSERT INTO user_profiles (id, email, full_name, organization, role)
SELECT id, email, raw_user_meta_data->>'full_name', raw_user_meta_data->>'institution', 'admin'
FROM auth.users WHERE email = 'your@email.com';
```

### 3. Run the platform locally

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

### 4. Worker wiring

For the full calibration surface, the web deployment expects:

- `CALIBRATION_API_BASE_URL`
- `CALIBRATION_API_SHARED_SECRET`

Without those, `/api/calibration/*` on the web app will intentionally return a guarded `503`.

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

- **113 metabolites** tracked across the storage horizon
- **~200 reactions** spanning the RBC metabolic network
- **Bordbar et al. (2015)** as the mechanistic basis
- experimental fit and physiological replay both treated as first-class evaluation signals

Reference:

- Bordbar, A., et al. (2015), *Personalized Whole-Cell Kinetic Models of Metabolism*, Cell Systems, 1(4), 283-292

---

## Repository Structure

See [ARCHITECTURE.md](ARCHITECTURE.md) for the technical architecture and [HERMES_CALIBRATION_V1.md](HERMES_CALIBRATION_V1.md) for the bounded orchestration loop.

---

<p align="center">
  <strong>airbc</strong> · Polytechnique Montreal · Jolicoeur Lab · 2026
</p>
