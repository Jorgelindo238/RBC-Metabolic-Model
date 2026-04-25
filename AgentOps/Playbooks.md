# AgentOps Playbooks

Reusable workflows for recurring work. Use these as operational recipes, not as
policy documents.

## Production deploy smoke

Use when deploying `web`, `marketing`, or `airbc-api`.

Flow:
1. Confirm the Vercel project is GitHub-backed to `Jorgelindo238/RBC-Metabolic-Model`.
2. Confirm the latest deployment uses the intended `main` commit.
3. Check build status is `READY`.
4. Smoke the public domain.
5. Smoke the key feature path touched by the change.

Validation:
- Vercel deployment commit matches GitHub `main`
- domain resolves to the expected project
- page/API route responds successfully
- no obvious auth/config regression

## Calibration worker smoke

Use when changing worker code, worker env, nginx, systemd, or Vercel calibration proxy.

Flow:
1. On Hetzner, source `/opt/airbc/app/apps/calibration-worker/.env`.
2. Confirm local worker health on `127.0.0.1:8010`.
3. Confirm secret-protected route returns `200` with the secret.
4. Confirm the same route returns `401` without the secret.
5. Confirm nginx/domain route works through `calibration-api.airbc.org`.
6. Confirm Vercel `web` has matching `CALIBRATION_API_BASE_URL` and `CALIBRATION_API_SHARED_SECRET`.

Validation:
- `/` returns worker health
- `/calibration/available-parameters` returns `200` with secret
- unauthorized request returns `401`
- web Calibration Registry loads parameters

## Authenticated UI smoke

Use when a feature requires `app.airbc.org` auth.

Flow:
1. Open the app and let the user sign in if needed.
2. Avoid claiming validation before the session is authenticated.
3. Navigate through the real route.
4. Exercise the exact user-facing flow.
5. Watch browser console and network failures.

Validation:
- route renders after auth
- primary action works
- visible labels match expected state
- no relevant console/runtime errors

## Simulation custom-data smoke

Use after changes to Data Upload, Simulation, calibration fallback messaging, or chart overlays.

Flow:
1. Upload a CSV with at least `EGLC`, `ELAC`, and `ATP`.
2. Confirm active dataset is visible.
3. Run Simulation.
4. Confirm default plotted metabolites are `EGLC`, `ELAC`, and `ATP`.
5. Confirm simulation lines are solid.
6. Confirm custom data appears as points/dashed overlays with distinct legend labels.

Validation:
- simulation succeeds
- `Bordbar defaults active - calibration optional` appears when no matching calibration is active
- custom overlays are visible and distinguishable

## RoBoCop calibration campaign

Use for bounded scientific/autoresearch work.

Flow:
1. Read `CalibrationOps.md`.
2. Identify seed, target observables, allowed parameter scope, and promotion gate.
3. Run a bounded calibration or worker campaign.
4. Run pure-ODE replay when candidate quality matters.
5. Apply curve triage and combined triage.
6. Archive keep/discard decision with artifact paths.

Validation:
- calibration artifact exists
- fit metrics are readable
- pure-ODE artifacts exist if promotion is considered
- protected metabolites did not regress beyond the accepted gate
- decision record is written

## LangSmith trace validation

Use when changing LangGraph, DeepAgents, or tracing metadata.

Flow:
1. Confirm tracing env is present.
2. Run a small graph/campaign.
3. Verify root trace exists.
4. Verify node/tool traces exist.
5. Verify metadata contains candidate id, run dir, decision, and verdict fields.

Validation:
- trace exists
- trace hierarchy is useful, not only present
- metadata can support later debugging

## Scientific workspace redesign

Use for Research UI surfaces such as Calibration Registry, Flux Analysis, Simulation, or Pathway Visualization.

Flow:
1. Preserve existing data contracts.
2. Establish a clear hero/status/provenance hierarchy.
3. Keep RoBoCop discreet and contextual.
4. Use full available width when the current layout wastes space.
5. Validate the page with real or representative data.

Validation:
- build/typecheck passes
- page renders on desktop and mobile widths when feasible
- scientific context remains truthful
- assistant context still matches the result state

## DeepAgents RoBoCop prototype

Use when beginning the deferred DeepAgents integration.

Flow:
1. Keep the first prototype offline-only.
2. Wrap existing deterministic RoBoCop actions as safe tools.
3. Give DeepAgents planning, delegation, memory, and explanation responsibilities.
4. Keep keep/discard scientific verdicts grounded in existing triage and pure-ODE tools.
5. Compare its recommendation to the current LangGraph runner before promoting.

Validation:
- no production web path depends on the prototype
- no free-form scientific file mutation is allowed
- LangSmith captures the agent plan, tool calls, and final recommendation
- the result is comparable to the existing bounded runner
