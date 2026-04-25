# AgentOps Archive

Compact historical record. Do not read this file by default. Use it only when
recovering context for an old decision, scientific run, or branch cleanup.

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
