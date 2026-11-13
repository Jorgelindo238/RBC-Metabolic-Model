// Run with: node --test apps/web/lib/calibration-journey.test.mjs   (written, NOT executed by its author)
// The fixtures below are TEST-ONLY objects; they are never imported by application code.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  draftDataContract,
  focusSummary,
  interpretPersistedCalibration,
  launchGate,
  limitationNotes,
  monitoringRunState,
  preflightView,
  referenceActivation,
  referenceProfileView,
  runProgress,
  speciesList,
  speciesSeries,
} from './calibration-journey.mjs'

const here = dirname(fileURLToPath(import.meta.url))

// TEST-ONLY fixture: shape of /calibration/reference-profiles/{id}, values synthetic.
const TEST_ONLY_PROFILE = Object.freeze({
  schema: 'airbc.reference_profile_view/1',
  profile_id: 'extracellular_release_2026_11_12',
  state: 'available',
  available: true,
  selected_id: 'working_centre',
  activation: { allowed: false, policy: 'forbidden' },
  flags: { activation_allowed: false, biologically_validated: false },
  scope: { unit_status: { status: 'assumed_mM_historical_model_convention' }, geometry: 'H = 0.58 borrowed',
    cohort: 'donor unknown', horizon_days: [1, 15], applicable_dataset: 'not transferable to user datasets' },
  scores: { strict: { worst_channel: 'EINO', worst_normalized_rmse: 633.091,
    focus: { EGLC: { normalized_rmse: 0.168464, J15_residual_mM: 1.359656, slope_predicted_mM_per_day: -0.264488,
      slope_observed_mM_per_day: -0.473636, abs_slope_error: 0.209148 }, ELAC: { normalized_rmse: 0.828752 } } } },
  limitations: ['ATP/ADP absolute J15 targets NOT met'],
  species_by_date: [
    { species: 'EGLC', compartment: 'extracellular', day: 15, observed: 12.0, predicted: 13.0, normalized_residual: 0.4, unit: 'mM (assumed)' },
    { species: 'EGLC', compartment: 'extracellular', day: 4, observed: 15.0, predicted: 14.0, normalized_residual: -0.3, unit: 'mM (assumed)' },
    { species: 'EINO', compartment: 'extracellular', day: 4, observed: 0.0, predicted: 0.01, normalized_residual: null, unit: 'mM (assumed)' },
    { species: 'ATP', compartment: 'intracellular', day: 4, observed: 1.0, predicted: 0.02, normalized_residual: -3, unit: 'mM (assumed)' },
  ],
})

test('draft contract carries only observed facts and lists every unknown as missing', () => {
  const { contract, missing } = draftDataContract('upload-1', { expTime: [1, 4], expData: { EGLC: [10, 9] } })
  assert.equal(contract.schema_version, 'airbc.user_calibration_data/1')
  assert.equal(contract.dataset.subject, null)
  assert.equal(contract.time.unit, null)
  assert.equal(contract.geometry, null)
  assert.equal(contract.initial_state, null)
  assert.deepEqual(contract.channels, [{ name: 'EGLC', compartment: null, kind: null, unit: null, values: [10, 9] }])
  assert.ok(missing.some((m) => m.startsWith('initial_state')) && missing.includes('channels[].unit'))
})

test('preflight keeps data validity, engine compatibility and launch apart', () => {
  const valid = preflightView({ data_valid: true, launch_allowed: false, engine_compatibility: { compatible: false, blocking: [{ code: 'x', path: 'p', message: 'm' }] } })
  assert.equal(valid.state, 'incompatible_engine')
  assert.equal(valid.dataValid, true)
  assert.equal(valid.engineCompatible, false)
  assert.equal(valid.launchAllowed, false)
  const forged = preflightView({ data_valid: true, launch_allowed: true, engine_compatibility: { compatible: false } })
  assert.equal(forged.launchAllowed, false)
  assert.equal(preflightView({ data_valid: false, launch_allowed: false, engine_compatibility: { compatible: false } }).state, 'invalid_data')
  assert.equal(preflightView({ data_valid: 'yes' }).state, 'preflight_unavailable')
  assert.equal(preflightView(null).state, 'not_checked')
})

test('launch gate blocks the contractual path and labels the legacy one', () => {
  const gate = launchGate(preflightView({ data_valid: true, launch_allowed: false, engine_compatibility: { compatible: false } }))
  assert.equal(gate.contractLaunchAllowed, false)
  assert.match(gate.reason, /engine/)
  assert.match(gate.legacyLabel, /Legacy path/)
  assert.match(launchGate(null).reason, /preflight/)
})

test('reference profile: unexpected, missing and blocked payloads are unavailable states', () => {
  assert.equal(referenceProfileView(null).available, false)
  assert.equal(referenceProfileView({ schema: 'other' }).state, 'unavailable')
  const blocked = referenceProfileView({ schema: 'airbc.reference_profile_view/1', state: 'blocked', available: false, reason: 'drift', next_task: 'requalify' })
  assert.equal(blocked.state, 'blocked')
  assert.equal(blocked.nextTask, 'requalify')
  assert.equal(referenceProfileView(TEST_ONLY_PROFILE).available, true)
})

test('provisional profile activation is refused even after an explicit click with matching identities', () => {
  const identity = { datasetId: 'd', subjectId: 's', contractFingerprint: 'c' }
  const decision = referenceActivation(referenceProfileView(TEST_ONLY_PROFILE), { explicit: true, runIdentity: identity, activeIdentity: identity })
  assert.equal(decision.allowed, false)
  assert.deepEqual(decision.reasons, ['activation_forbidden_by_artifact'])
})

test('a hypothetically eligible artifact still needs identity match and an explicit action', () => {
  const eligible = { ...TEST_ONLY_PROFILE, activation: { allowed: true }, flags: { activation_allowed: true } }
  const identity = { datasetId: 'd', subjectId: 's', contractFingerprint: 'c' }
  assert.equal(referenceActivation(eligible, { explicit: true, runIdentity: identity, activeIdentity: identity }).allowed, true)
  for (const key of ['datasetId', 'subjectId', 'contractFingerprint']) {
    const other = { ...identity, [key]: 'other' }
    assert.equal(referenceActivation(eligible, { explicit: true, runIdentity: identity, activeIdentity: other }).allowed, false)
  }
  assert.equal(referenceActivation(eligible, { explicit: false, runIdentity: identity, activeIdentity: identity }).allowed, false)
})

test('species series come from the single profile, sorted, with zero-band points kept unnormalized', () => {
  const series = speciesSeries(TEST_ONLY_PROFILE, 'EGLC')
  assert.deepEqual(series.map((p) => p.day), [4, 15])
  assert.equal(series[0].residual, -1)
  assert.equal(speciesSeries(TEST_ONLY_PROFILE, 'EINO')[0].normalizedResidual, null)
  assert.deepEqual(speciesList(TEST_ONLY_PROFILE, 'extracellular'), ['EGLC', 'EINO'])
})

test('focus diagnostics and limitations are factual, with no global validity score', () => {
  const [eglc, elac] = focusSummary(TEST_ONLY_PROFILE)
  assert.equal(eglc.normalizedRmse, 0.168464)
  assert.equal(eglc.slopeObserved, -0.473636)
  assert.equal(elac.j15Residual, null)
  const notes = limitationNotes(TEST_ONLY_PROFILE)
  assert.ok(notes.some((n) => n.includes('ATP/ADP')))
  assert.ok(notes.some((n) => n.includes('EINO')))
  assert.ok(notes.some((n) => n.includes('assumed_mM')))
  assert.ok(!notes.some((n) => /validat(ed|ion) (score|percentage)|%/.test(n)))
})

test('progress is determinate only from real counters', () => {
  assert.deepEqual(runProgress({ completedCases: 3, totalCases: 12 }), { mode: 'determinate', completed: 3, total: 12, fraction: 0.25 })
  assert.deepEqual(runProgress({ completedCases: null, totalCases: 12 }), { mode: 'indeterminate' })
  assert.deepEqual(runProgress({ completedCases: 13, totalCases: 12 }), { mode: 'indeterminate' })
  assert.deepEqual(runProgress({ completedCases: 0, totalCases: 0 }), { mode: 'indeterminate' })
  assert.equal(monitoringRunState({ status: 'running' }).progress.mode, 'indeterminate')
  assert.equal(monitoringRunState({ status: 'completed', completedCases: 5, totalCases: 5 }).progress, null)
})

test('monitoring states separate finished, failed, cancelled and unknown', () => {
  assert.equal(monitoringRunState({ status: 'completed' }).state, 'finished_unverified')
  assert.match(monitoringRunState({ status: 'completed' }).label, /not a biological validation/)
  assert.equal(monitoringRunState({ status: 'failed' }).state, 'failed')
  assert.equal(monitoringRunState({ status: 'cancelled' }).state, 'cancelled')
  assert.equal(monitoringRunState({ status: 'weird' }).state, 'unknown')
  assert.equal(monitoringRunState(null).state, 'unknown')
})

test('legacy applied flags become history, never verified activation', () => {
  const legacy = { calibrationId: 'x', datasetProvenance: { calibrationApplied: true, calibratedParametersActive: true, activeDatasetId: 'd' } }
  const read = interpretPersistedCalibration(legacy)
  assert.equal(read.activationStatus, 'legacy_unverified')
  assert.equal(read.datasetProvenance.calibrationApplied, false)
  assert.equal(read.datasetProvenance.calibratedParametersActive, false)
  assert.deepEqual(read.legacyFlags, { calibrationApplied: true, calibratedParametersActive: true })
  assert.equal(read.calibrationId, 'x')
  assert.equal(read.datasetProvenance.activeDatasetId, 'd')
  assert.equal(interpretPersistedCalibration({ datasetProvenance: {} }).activationStatus, 'not_activated')
  assert.equal(interpretPersistedCalibration(null), null)
})

test('no unconditional calibrationApplied: true remains in research-calibration.ts', () => {
  const source = readFileSync(join(here, 'research-calibration.ts'), 'utf8')
  assert.ok(!/calibrationApplied:\s*true/.test(source))
  assert.ok(!/calibratedParametersActive:\s*true/.test(source))
})

test('monitoring overview contains no fabricated bags, forecasts or alerts', () => {
  const source = readFileSync(join(here, '..', 'components', 'platform', 'MonitoringWorkspaceLanding.tsx'), 'utf8')
  for (const forbidden of ['BAG-', 'DON-', 'MONITORING_BAGS', 'MONITORING_FORECAST_BANDS', 'MONITORING_ALERTS', "'96%'", 'Seeded preview']) {
    assert.ok(!source.includes(forbidden), `found ${forbidden}`)
  }
  assert.ok(source.includes('monitoringRunState'))
})

test('the reference view renders no activation or contractual launch control at all', () => {
  const source = readFileSync(join(here, '..', 'components', 'features', 'CalibrationJourney.tsx'), 'utf8')
  assert.ok(!source.includes('data-testid="reference-activate"'))
  assert.ok(!source.includes('data-testid="contract-launch"'))
  assert.ok(source.includes('data-testid="reference-activation-status"'))
  assert.ok(source.includes('data-testid="contract-launch-status"'))
  assert.ok(!/>\s*Activate\s*</.test(source))
  assert.ok(!source.includes('activateCalibration'))
})

test('monitoring loads actual registry records and forwards unavailable-source errors', () => {
  const page = readFileSync(join(here, '..', 'components', 'platform', 'PlatformFeaturePage.tsx'), 'utf8')
  assert.match(page, /feature.id === 'calibration-registry' \|\| feature.id === 'monitoring-overview'/)
  assert.match(page, /runsError=/)
})

test('persisted inactive parameters cannot feed simulation or flux automatically', () => {
  for (const name of ['SimulationWorkspace.tsx', 'FluxAnalysis.tsx']) {
    const source = readFileSync(join(here, '..', 'components', 'features', name), 'utf8')
    assert.match(source, /datasetProvenance.calibratedParametersActive !== true/)
  }
})

test('worker completion status takes precedence over a benchmark verdict', () => {
  assert.equal(monitoringRunState({ status: 'healthy', completionStatus: 'running' }).state, 'running')
  assert.equal(monitoringRunState({ status: 'pass', completionStatus: 'failed' }).state, 'failed')
})
