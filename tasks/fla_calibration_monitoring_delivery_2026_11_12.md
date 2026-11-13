# Calibration / Monitoring application tranche: delivery for Codex review

Date 2026-11-12. This applies `tasks/fla_calibration_monitoring_dispatch_2026_11_12.md`. Read/Grep/Glob/Edit/Write only. NOTHING executed: no test, TypeScript build, server, browser, ODE, install, commit or push. The UI is NOT validated.

Untouched: no scientific archive, source, constant, Km/J1 or solver default was changed; no auth or middleware change; no new dependency.

## Files

API (FastAPI, existing conventions):

- `apps/api/services/reference_profiles.py` (new): read-only allowlisted registry.
  - The id must match `^[a-z0-9_]{1,64}$` AND be in `REGISTRY`; locations are relative and confined to the project root (`AIRBC_REFERENCE_ROOT` overrides the root for tests or deployments).
  - Proof chain:
    1. the receipt must have `verified: true`;
    2. `source_manifest_sha256` equals the sha256 of the campaign manifest;
    3. the manifest entry for the release equals the sha256 of the release file;
    4. receipt `selected_id`/`release_status` equal the release's;
    5. the release must carry `activation_allowed: false`;
    6. the objective must be `extracellular_first/2`.
  - States: `available`, `missing` (clean install, artifacts kept out of Git), `corrupt`, `blocked` (blocked receipt with its next task), `unsupported`, `unknown_profile`. Any failed check gives an explicit state, never an invented profile.
  - The view (`airbc.reference_profile_view/1`) carries scope, unit status, scores (strict/ultrastrict), EGLC/ELAC focus, per-species/date rows, Vmax values, limitations and receipt fingerprints. No paths. Activation is always reported as forbidden.
  - No verifier, ODE or subprocess runs; stdlib only.
- `apps/api/routers/calibration.py` (edited): adds `GET /calibration/reference-profiles` and `GET /calibration/reference-profiles/{profile_id}` (404 for non-allowlisted ids, without echoing the input). These routes have no auth of their own, like the other calibration routes. In production the web middleware's existing Supabase session check covers `/api/calibration/*`, unchanged.

Web (existing Next components, Tailwind, lucide):

- `apps/web/lib/calibration-journey.mjs` + `.d.mts` (new): pure helpers.
  - `draftDataContract`: only observed facts; unknown fields stay null and are listed as missing.
  - `preflightView` keeps `data_valid`, engine compatibility and launch apart; it cannot be forged into a launch.
  - `launchGate`.
  - Reference profile: `referenceProfileView`; `referenceActivation`, where the artifact prohibition wins over a click and identity match, and an eligible artifact would still need an identity match plus an explicit action through `calibration-lifecycle.activationDecision`; `speciesSeries`, `speciesList`, `focusSummary`, `limitationNotes`.
  - Monitoring: `monitoringRunState` (finished ≠ validated) and `runProgress` (determinate only from real counters, else indeterminate).
  - `interpretPersistedCalibration`.
- `apps/web/components/features/CalibrationJourney.tsx` (new):
  - **Steps:** Data → Verification → Calibration → Results.
  - **Preflight:** on the active upload, `POST /calibration/preflight` with the draft contract, showing three separate answers and the reported issues.
  - **Contractual launch:** disabled with its reason. No qualified contractual worker is wired in this version, so it stays disabled even if a preflight ever allowed it.
  - **Reference profile:** a read-only card with all real API states, "Preview only · never active", a disabled Activate button with its reason, the EGLC/ELAC table, a species selector with an inline SVG of observed vs predicted plus a dated table (zero-band points shown as such), the fit/qualification wording, and the limitations.
- `apps/web/components/features/ParameterCalibration.tsx` (edited): renders `CalibrationJourney` above the existing selection. The existing run button is now labelled "Legacy path without a data contract: results are unverified and never activated automatically". Its behaviour is unchanged otherwise, including the earlier `explicit:false` non-activation.
- `apps/web/lib/research-calibration.ts` (edited):
  - `calibrationApplied` and `calibratedParametersActive` are now false for new records, with `activationStatus: 'not_activated'`.
  - Persisted records pass through `interpretPersistedCalibration`: old "applied" flags become `activationStatus: 'legacy_unverified'` with `legacyFlags` kept as history. Nothing is deleted and no eligibility is granted.
- `apps/web/components/platform/MonitoringWorkspaceLanding.tsx` (rewritten):
  - Removed: the demonstration bags, donors, forecast percentages, alerts and activity.
  - Shown: real calibration runs passed by the workspace (`runs`), with honest states (running, failed, cancelled, finished-unverified, unknown) and progress from worker counters only, otherwise "progress unknown".
  - Empty and error states; links to the existing Bag Repository, Forecast and Alerts pages.
- `apps/web/components/platform/WorkspaceFeatureContent.tsx` (edited): passes `runs` to the Monitoring landing.

## Tests written, NOT RUN

- `qa/test_reference_profiles_api.py` (pytest, synthetic artifacts in `tmp_path` only):
  - verified view without paths; scope and units preserved;
  - missing archive → empty state; tampered release; tampered manifest;
  - unverified receipt or identity mismatch; unreadable JSON;
  - blocked release; unsupported objective; activatable release refused;
  - allowlist/path rejection (7 inputs);
  - router list/detail/404; clean install;
  - registry imports nothing that executes.
- `apps/web/lib/calibration-journey.test.mjs` (`node --test`, test-only fixture inline):
  - draft contract without inference;
  - preflight separation, including a forged launch;
  - launch gate and legacy label; unavailable/blocked profiles;
  - provisional activation refused despite a click and matching identities;
  - eligible artifact still needs identity and explicit action (dataset, donor and contract mismatch each refused);
  - single-vector series; factual focus and limitations; real-counter progress; monitoring states;
  - legacy flags become history;
  - source checks: no `calibrationApplied: true`, no fabricated bags or percentages, no enabled activation control.
- `apps/web/e2e/calibration-monitoring.scenarios.mjs` (existing `playwright` dependency): desktop 1440×900 and mobile 390×844.
  - **Calibration page:** journey steps, disabled reference activation even after a forced click, preview label, ATP/ADP limitation (or an explicit unavailable state on a clean install), disabled contractual launch, legacy label, no horizontal overflow.
  - **Monitoring page:** no fabricated content; runs, empty or error state; determinate progress only for running records; no horizontal overflow.
  - Screenshots go to the git-ignored `output/e2e-screens/`.

Commands for Codex:

```text
python -m pytest qa/test_reference_profiles_api.py qa/test_calibration_preflight_api.py -q
node --test apps/web/lib/calibration-journey.test.mjs apps/web/lib/calibration-lifecycle.test.mjs
(cd apps/web && npx tsc --noEmit)
BASE_URL=http://127.0.0.1:3000 node apps/web/e2e/calibration-monitoring.scenarios.mjs
```

## Identity and state mapping

| Concept | Source | UI |
| --- | --- | --- |
| Reference profile | API `reference_profile_view/1`, `kind: reference_profile` | Card "Reference profile", preview only |
| User dataset | Research dataset provider → draft contract | Data and verification card |
| User calibration | Legacy run result / worker job | Existing results; never auto-activated |
| `data_valid` / `engine_compatibility.compatible` / `launch_allowed` | Preflight report | Three separate answers |
| `activation_allowed: false` | Release artifact | Activate disabled; `referenceActivation` refuses |
| Legacy `calibrationApplied: true` | localStorage history | `activationStatus: legacy_unverified`, flags false |
| Run progress | `completedCases` / `totalCases` | Bar only when both are real and consistent; else indeterminate |
| Finished run | worker `status: completed` | "Finished (not a biological validation)" |

## Remaining limits (honest)

- **Engine:** the user engine is not qualified for new contractual datasets; contractual launches stay disabled. The legacy path still exists, labelled.
- **Reference profile:** a single archived table, J1–J15, assumed mM, borrowed H, donor unknown. ATP/ADP unmet; EINO is the worst channel.
- **Monitoring runs:** they come from the existing `runs` prop; if the monitoring route does not load runs, the page shows the honest empty state (Codex should check where `runs` is fetched for `/monitoring`).
- **Other `calibrationApplied` readers:** RoboCoP/pathway components still derive `calibrationApplied` from `calibrationCompleted` in `lib/robocop/research-context-builders.ts`. Out of this tranche's ownership; flagged for review.
- **Naming:** the `activatedAt` field name is legacy (it is the load time) and was not renamed.
- **Unverified integration:** the `apiClient` response shape (`.data`) and TS typing of the `.mjs` import follow existing usage but are not compiled here.
