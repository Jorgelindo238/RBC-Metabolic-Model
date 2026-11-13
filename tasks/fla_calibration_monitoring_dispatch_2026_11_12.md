# Claude implementation: Calibration / Monitoring return to application

User authorization: launch Claude for the next Calibration/Monitoring stage.
This is application implementation, not a new optimization or model change.

## Verified scientific handoff

Read `tasks/fla_extracellular_release_results_2026_11_12.md`,
`tasks/fla_application_return_handoff_2026_11_12.md` and the current task header.
The extracellular /2 campaign is COMPLETE, not pending:51 module/verifier tests,
38 valid ODEs, no new finalist; selected working_centre fallback. Independent
receipt passes1,162,575 supports,56 Jacobian columns and17 exported Vmax values.

Frozen artifact:
`output/extracellular_release_2026_11_12/release/provisional_extracellular_reference.json`.
Receipt:
`output/extracellular_release_verification_2026_11_12/verification.json`.
Same campaign's manifest binds the release; the receipt binds that manifest.

It is a READ-ONLY provisional comparator for one archived table, horizonJ1-J15,
not a general calibrated model. ATP/ADP unmet, EINO poorly fitted, units assumed
historical mM, H0.58 borrowed, donor unknown. activation_allowed:false and
default_replacement:false are prohibitions, not flags an explicit click can
override. No newly authorized ODEs, experiments or solver promotion.

## Bounded deliverables

### 1. Read-only verified profile registry and API

Inspect existing FastAPI router/service/auth conventions first. Add a small
allowlisted reference registry, not arbitrary filesystem access or uploads of
scientific archives. Verify the receipt->manifest->release hash chain and the
receipt's verified result and selected identity before returning a profile.
Do not execute Python verifier scripts or an ODE in an API request. Present
missing, corrupt, blocked and unsupported artifacts as explicit unavailable
states; no fallback to invented success or parameters. Keep ignored output/
artifacts outside Git; a clean installation without them must work with a
clear empty state. Do not copy raw experimental workbooks into the frontend.

Return schema-versioned display data, per-species/date residuals, profile scope,
unit status and receipt fingerprint. Preserve the real contract field names;
use explicit adapters for existing frontend identities if needed. Do not expose
absolute local source paths, secrets or unrestricted file reads. Use existing
auth/ownership patterns; no authentication changes, public deployment or new
database dependency. Reference profiles and user datasets are distinct objects.

### 2. Data -> Verification -> Calibration -> Results

Use existing routes, components, state stores, styles and lucide icons. Avoid
an application-wide navigation rewrite or marketing layout. The default screen
must remain a usable work surface. Preserve current language conventions.

Wire upload/current research data to `/calibration/preflight` using the actual
versioned contract. Display data_valid separately from engine_compatibility and
launch_allowed. Show missing units, subject/provenance and initial-state fields
as missing; never silently substitute Bordbar initial state or assume a donor.
Do not invent a complete initial state from a sparse upload.

Launch buttons must respect preflight and server restrictions. New contractual
datasets remain blocked while the engine cannot honor them. Relative data may
be retained/inspected as declared data but must not be converted to mM or launched
in the absolute-only engine. This stage must not falsely promise automatic
calibration for every raw/relative dataset. Any retained legacy path must be
explicitly labelled and must not masquerade as the safe contractual path.

Offer the verified provisional profile in a read-only reference view, clearly
separate from an upload and an active user calibration. Preview is allowed;
activation is absent/disabled with the reason, even with matching identities.
Do not use the historical profile on a new dataset implicitly. The reference
view can remain available when a new-dataset calibration is blocked.

Results: actual species/date values and chart/table using existing chart helpers,
explicit EGLC/ELAC residuals/slope diagnostics, fit/free-ODE verdict separation,
and compact ATP/ADP/EINO/units/geometry limitations. Do not claim every channel
fits well, or display a fabricated overall biological-validity percentage.

### 3. Truthful common state and monitoring

Reuse `apps/web/lib/calibration-lifecycle.mjs` and its types. Distinguish execution
completion, numerical validity, guard admissibility, biological validity and
activation. Respect explicit artifact prohibition AND identity checks. Remove
the unconditional calibrationApplied:true in research-calibration.ts. Historical
persisted flags without verifiable activation are legacy/unverified, not active;
retain the user's history, do not delete records or silently grant eligibility.

Replace static demonstration bags/forecast percentages in
MonitoringWorkspaceLanding.tsx with actual available records or an empty state.
Progress comes from real worker completed/total counters only. If unavailable,
show an indeterminate running state, not a simulated progress clock. Missing or
failed API/data, cancellation, failure and empty history need honest states.
Do not create background jobs, fake donors, fictional predictions or cron tasks.

### 4. Tests and reviewable delivery

Add focused API/service tests for registry proof-chain tampering, missing local
archive, blocked release, allowlist/path rejection and scope/units preservation.
Add frontend pure/component tests using existing tooling for preflight blocking,
real progress, unknown legacy activation, hard prohibition of provisional-profile
activation, dataset/donor/context/contract mismatch and absence of fabricated bags.
Keep lifecycle tests. Add deterministic UI fixtures marked test-only, never
production records. Supply browser-test scenarios for desktop/mobile and overflow.

Deliver exact paths, data/identity mappings, tests WRITTEN vs actually RUN, and
remaining engine limitations. Do not call the UI ready merely because it compiles.
Codex will run tests, TypeScript, real browser checks and dev servers afterward.

## Tools boundary for this Desktop delegation

Read/Grep/Glob/Edit/Write ONLY. No shell/code/tests/ODE/optimizer execution,
servers, agents, package installation, commit/push, deployment, authentication
or permission changes. Do not modify sealed scientific scripts/artifacts,
constants, initial state, Km or model defaults. No redesign beyond the existing
Calibration/Monitoring ownership boundary. Stop at this implementation tranche
and wait for Codex review. Do not restart scientific calibration to fill the UI.
