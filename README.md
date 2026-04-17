# 🩸 airbc — AI-Powered Blood Bag Conservation Platform

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

airbc is a research platform for studying **red blood cell metabolism during storage**. It helps researchers and blood banking teams track glucose depletion, ATP decline, and metabolic drift throughout the storage period — and detect quality changes before they become critical.

Built on the **Bordbar et al. (2015)** whole-cell kinetic reconstruction of RBC metabolism.

<p align="center">
  <a href="https://app.airbc.org/sign-up"><strong>Create free account</strong></a> ·
  <a href="https://app.airbc.org/sign-in">Sign in</a> ·
  <a href="https://calendar.google.com/calendar/appointments">Schedule a demo</a>
</p>

---

## What airbc Does

- **Simulate** dynamic RBC metabolic behavior over configurable storage horizons (up to 42 days)
- **Monitor** glucose, ATP, lactate, 2,3-BPG, glutathione, and 113 total metabolites
- **Alert** on meaningful metabolic shifts with RoBoCop AI-assisted summaries
- **Compare** model predictions against your own experimental storage data
- **Calibrate** enzyme kinetic parameters (Vmax, Km) against observed trajectories
- **Visualize** pathway-level metabolic network structure and flux distributions
- **Follow up** through RoBoCop research chat and planned secure messaging workflows

---

## Platform Architecture

```
apps/
├── web/            → Next.js 15 authenticated research platform (app.airbc.org)
├── api/            → FastAPI scientific backend (7 routers, ~200 reactions)
└── marketing/      → Marketing homepage (airbc.org)

src/                → Mechanistic ODE model (equadiff_brodbar.py, 113 metabolites)
streamlit_app/core/ → Python scientific modules (imported by FastAPI via sys.path)
services/robocop/   → RoBoCop runtime, tracing, and bounded mutation orchestration
```

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend** | Next.js 15, React 19, shadcn/ui, Tailwind CSS v4 | Authenticated researcher platform |
| **Backend** | FastAPI, Python, scipy | Scientific ODE simulation and analysis |
| **Auth** | Supabase (Google OAuth + email/password) | User profiles, admin roles, workspaces |
| **AI** | RoBoCop (LangGraph + LangChain) | Grounded research interpretation, chat, and monitoring support |
| **Marketing** | Next.js 15 | Product homepage at airbc.org |

---

## Features

### Research Platform (`apps/web`)
- 🧪 **Simulation Workspace** — run storage-condition ODE simulations with pH perturbations
- 📊 **Flux Analysis** — Michaelis-Menten flux estimation across 7 metabolic pathway groups
- 🗺️ **Pathway Visualization** — KEGG-style SVG network graph (30 metabolites, 20 reactions)
- 📈 **Sensitivity Analysis** — compare datasets, per-metabolite R²/RMSE/MAE validation
- 🎯 **Parameter Calibration** — optimize Vmax/Km with differential evolution, L-BFGS-B, or least squares
- 📤 **Data Upload** — upload CSV/Excel experimental data with auto metabolite mapping
- 🤖 **RoBoCop Assistant** — grounded Simulation interpretation plus research-page chat with OpenAI-backed responses and fallback
- 📋 **Calibration Registry** — browse persisted calibration runs and benchmark outcomes
- 🛡️ **Admin Dashboard** — user management, role control, platform statistics

### Authentication
- Google OAuth sign-in
- Email/password sign-in and sign-up
- Detailed researcher profiles (name, institution, function, department)
- Admin role system with Supabase RPC functions
- Session middleware with route protection

### Marketing Site (`apps/marketing`)
- Premium dark homepage with product mockup
- 4-step workflow (Quantify → Store & Simulate → Monitor & Alert → Act & Follow Up)
- AI + Remote supervision section with messaging preview
- RoBoCop research chat and simulation interpretation are live in the authenticated platform
- CTAs: Create account, Schedule a demo, Sign in

---

## Quick Start

### Prerequisites
- Node.js 22+
- Python 3.12+
- npm

### 1. Install dependencies

```bash
# Web app
cd apps/web && npm install

# Marketing site
cd apps/marketing && npm install

# Python backend
pip install -r requirements.txt
pip install python-multipart
```

### 2. Set up Supabase

Run `SUPABASE_SETUP.sql` in your Supabase project SQL Editor, then promote your account:

```sql
INSERT INTO user_profiles (id, email, full_name, organization, role)
SELECT id, email, raw_user_meta_data->>'full_name', raw_user_meta_data->>'institution', 'admin'
FROM auth.users WHERE email = 'your@email.com';
```

### 3. Run the platform

```bash
# FastAPI backend (port 8000)
cd apps/api && python -m uvicorn main:app --host 0.0.0.0 --port 8000

# Next.js app (port 3000)
cd apps/web && npm run dev

# Marketing site (port 3001)
cd apps/marketing && npm run dev
```

---

## FastAPI Endpoints

| Router | Prefix | Key Endpoints |
|---|---|---|
| Simulation | `/simulate` | `POST /` |
| Flux | `/flux` | `POST /estimate`, `POST /timeseries`, `GET /kinetic-params` |
| Pathway | `/pathway` | `GET /network`, `POST /network-state` |
| Sensitivity | `/sensitivity` | `POST /compare` |
| Calibration | `/calibration` | `POST /run`, `GET /available-parameters` |
| Data | `/data` | `GET /experimental`, `GET /reactions`, `POST /upload`, `POST /map-metabolites` |
| RoBoCop | `/robocop` | `POST /research/chat` |

---

## Scientific Basis

- **113 metabolites** tracked across the full storage window
- **~200 enzyme-catalyzed reactions** spanning 8 metabolic pathways
- **42-day storage horizon** with configurable duration
- **pH perturbation scenarios** — acidosis, alkalosis, step, ramp
- **Bohr effect tracking** — P50, O₂ saturation, oxygen extraction
- Based on: **Bordbar, A., et al. (2015)** — *Personalized Whole-Cell Kinetic Models of Metabolism* — Cell Systems, 1(4), 283–292 — [DOI](https://www.cell.com/cell-systems/fulltext/S2405-4712(15)00149-0)

---

## Repository Structure

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full technical architecture guide.

---

<p align="center">
  <strong>airbc</strong> · Polytechnique Montreal · Jolicoeur Lab — 2026
</p>
