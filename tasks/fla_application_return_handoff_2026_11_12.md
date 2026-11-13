# Return to the application: handoff for the next tranche

Date 2026-11-12. Planning note only; no UI change, server or redesign in this tranche. Application work must NOT wait for an ATP rescue.

## What the application can rely on

- **Release artifact:** after Codex runs and verifies `scripts/run_extracellular_release.py`, `output/extracellular_release_2026_11_12/release/provisional_extracellular_reference.json` holds ONE vector.
  - Its status is `provisional_extracellular_reference`, or `blocked_no_qualified_candidate`.
  - It carries dataset/context fingerprints, all per-species scores and its limitations.
- **Activation is forbidden:** `activation_allowed: false` is a PROHIBITION, not a default. An explicit user click must NOT override it (`activation_permitted()` in `src/fla_extracellular_release.py` refuses it). `default_replacement: false`.
  - The provisional profile may be previewed or selected read-only, for the archived dataset it names only (its `observations_sha256`).
  - Activation needs a different, separately eligible release (`activation_allowed: true` with an `eligibility` block), plus matching dataset, engine-context and contract identity checks, plus an explicit action.
- **Units:** the release states `unit_status: assumed_mM_historical_model_convention`. The source archive records no unit, so the UI must label values "mM (assumed)", not as source-verified.
- **Not transferable:** the provisional comparator cannot establish compatibility with any incoming user dataset.
- **Shared lifecycle layer:** `apps/web/lib/calibration-lifecycle.mjs` already separates the numerical, fit, admissibility and activation states, and requires explicit, identity-matched activation.

## Journey: Data → Verification → Calibration → Results

1. **Data:** upload, then `POST /calibration/preflight` (schema `airbc.user_calibration_data/1`).
   - Show data validity and engine compatibility separately.
   - Absolute mM only; relative channels are refused.
   - One donor per run.
2. **Verification:** show the observation registry (which channels are extracellular, zero-band points, unit status) and the engine compatibility, which stays false until the user-engine qualification is extended.
3. **Calibration:** reachable only from `ready_for_test`.
   - For the archived reference dataset only, show the provisional extracellular profile as a read-only preview, never activatable; do not offer a new fit.
   - Progress comes only from real job counters (`completed_cases`/`total_cases`).
4. **Results:**
   - fit and free-ODE scores side by side, never merged;
   - extracellular per-species/per-date table and EGLC/ELAC diagnostics;
   - ATP/ADP shown as UNMET;
   - an activation control shown only for a release whose `activation_allowed` is true and whose eligibility matches the dataset, donor, engine context and contract fingerprint; for this provisional release it is absent or disabled, with the reason.

## Concrete defects to fix next (seen in code, not fixed here)

- **`apps/web/lib/research-calibration.ts`:** stamps `calibrationApplied: true` unconditionally. Derive it from an explicit activation decision instead.
- **`apps/web/components/platform/MonitoringWorkspaceLanding.tsx` (about lines 65-100):** static demonstration bags and forecast percentages. Replace them with `monitoringView` output or an empty state.
- **The web client:** sends no data contract to `/calibration/run`, and there is no explicit activation control (`ParameterCalibration.tsx` only shows a notice).
- **Profile registry:** none exists for the API to list released profiles. A read-only endpoint serving the verified release JSON, with its receipt hash, is enough.

## Tests to require in that tranche

- No unconditional `calibrationApplied`.
- No progress without real counters.
- No activation on a dataset/donor/contract mismatch.
- No activation of an `activation_allowed: false` release, even after an explicit click.
- Assumed units are labelled as assumed.
- A blocked release renders as blocked.
- Monitoring shows no fabricated bags.
- The `node --test` lifecycle tests stay green.

## Out of scope

ATP/ADP energy calibration, latent-stock measurement, the observation-contract decision, per-donor validation and relative-observation models. Each is a separate, explicitly authorized task.
