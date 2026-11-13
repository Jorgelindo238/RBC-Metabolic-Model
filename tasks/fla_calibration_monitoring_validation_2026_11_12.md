# Calibration / Monitoring: Codex implementation review and local QA

Date2026-11-12. User requested continuation WITHOUT Claude. No agents or Claude
calls used. No scientific calibration, ODE, default/initial-state change or
archive modification. Existing dirty changes preserved. No commit/push/deploy.

## Completed corrections

- Monitoring now actually calls the existing scoped server-side run reader.
  Previously only the registry route loaded runs, leaving Monitoring always empty.
  Missing credentials/API failures propagate to the overview. Failed loading
  displays Unknown counters, not fabricated zero counts or demonstration bags.
  Worker completionStatus takes precedence over benchmark status.
- Calibration and Monitoring bypass the bulky route-introduction panels and
  start on their work surfaces. Existing navigation/framework retained.
- Registry API checks proof chain, selected identity and provisional scope;
  malformed display fields or unreadable artifacts fail closed. Added tests for
  malformed payloads and attempted biological/default promotion flags.
- Preflight resets on dataset changes and ignores stale asynchronous replies.
  Reference service errors have an explicit unavailable state. A sparse upload
  carries no guessed units, donor, geometry or initial-state table.
- Calibration/registry/pathway context builders no longer infer activation from
  execution completion. Simulation and Flux refuse automatic parameter reuse
  from inactive persisted records. Unreadable historical storage is not deleted
  during read. Legacy history remains inspectable, not automatically active.
- Provisional reference remains read-only and non-activatable. Real EGLC/ELAC,
  per-species/date tables, EINO zero-band points and disclosed limitations are
  served from the actual verified artifact. No profile is applied to an upload.

## Executed checks

-135 Python tests pass: reference API, calibration preflight, auto parameter
  scope and Vmax-only contracts. Last run17.18s.
-38 Node tests pass: journey/lifecycle, legacy activation and run-source wiring.
-TypeScript `--noEmit --incremental false` passes. `git diff --check` passes.
-Six Playwright scenarios pass at1440x900 and390x844:
  calibration reference, sparse-upload preflight, monitoring overview.
-Real local proxy->FastAPI reference fetch returns available working_centre;
  artifact receipt/scope/assumed-unit/activation fields are preserved.
-Species selector EGLC->EINO->EGLC exercised; zero-band values shown without
  normalization. Activation remains disabled after attempted interaction.
-Test-only localStorage upload sent through the REAL preflight endpoint with
  initial_state:null and geometry:null; data_valid:false, launch_allowed:false,
  missing fields rendered and launch disabled. No solver/job endpoint triggered.
-Meaningful pages rendered without a framework error overlay or page exceptions.
  Horizontal-overflow checks pass. Screenshots reviewed and retained outside
  the repo under `C:/WINDOWS/TEMP/airbc-calibration-monitoring/`.

Browser plugin was not listed; used the installed Playwright dependency.
The initial30s cold-build navigation timeout was insufficient; after warming
and explicit180s navigation timeout all six interaction scenarios passed.
A test assertion initially expected the wrong zero-band label and was corrected
to the actual cell label, with a render wait rather than a string race.

## Environment and outstanding gates

Web dev server: http://127.0.0.1:3100
FastAPI: http://127.0.0.1:8010
Local proxy points to this backend; no deployment or persistent env-file edits.

The existing Supabase run read fails with TypeError:fetch failed in this local
environment. A separate health-connectivity check using the existing local env
confirmed URL and anon key are configured but the hostname fails DNS resolution
with ENOTFOUND. No credential values were printed and no env files changed.
This does not establish whether the URL is mistyped, obsolete or temporarily
unresolvable. The server emits that error into the dev console. It is explicitly
reported by QA as an ENVIRONMENT condition, and tests require Monitoring to
render unavailable/Unknown when it occurs. It is not hidden, counted as a
successful database read or represented as an empty registry. Reading populated
remote runs/ownership was not verified. No auth policies or credentials changed.

Contractual new-dataset launches remain blocked: engine qualification and full
input metadata are still incomplete. Relative observations are not converted
to mM. The retained legacy calibration path remains visibly labelled and is
not certified by these tests; no legacy scientific run was executed. General
calibration UX is not a claim of automatic fitting for arbitrary raw uploads.

Reference scope stays historical table/J1-J15 only, donor unknown, borrowed H,
assumed model units, ATP/ADP unmet and EINO poorly fitted. No activation allowed.

Next: diagnose the run-registry connectivity/configuration without changing
authentication, and separately qualify the user-engine shifted time origin
before enabling new contractual calibration. Do not resume scientific refitting
automatically. Full repository suite, production build/deploy and authenticated
remote-account end-to-end tests were not run.
