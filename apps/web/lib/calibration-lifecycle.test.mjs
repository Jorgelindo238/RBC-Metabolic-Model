// Shared calibration lifecycle: pure tests for `node --test`.
// Written on 2026-11-12 and NOT executed by their author.

import { test } from 'node:test'
import assert from 'node:assert/strict'

import {
  JOURNEY_STEPS,
  LIFECYCLE_STATES,
  activationDecision,
  classifyCalibrationRecord,
  journeyFor,
  lifecycleLabel,
  monitoringView,
  separateScores,
} from './calibration-lifecycle.mjs'

const IDENTITY = { datasetId: 'lab-a-1', subjectId: 'd07', contractFingerprint: 'abc123' }

function admissibleResult(overrides = {}) {
  return {
    success: true,
    calibration_status: 'completed',
    parameter_contract: 'vmax_only_fixed_km',
    data_contract: { status: 'preflight_passed' },
    final_loss: 1.5,
    baseline_loss: 3.0,
    improvement_pct: 50,
    r_squared: 0.7,
    triage: { overall: 'keep' },
    pure_ode_triage: { overall: 'healthy' },
    combined_triage: { overall: 'keep' },
    ...overrides,
  }
}

test('exactly the seven registered states exist and each has a label', () => {
  assert.deepEqual([...LIFECYCLE_STATES], [
    'invalid_data', 'incompatible_engine', 'ready_for_test', 'running',
    'numerical_failure', 'rejected_candidate', 'admissible_candidate',
  ])
  for (const state of LIFECYCLE_STATES) assert.notEqual(lifecycleLabel(state), 'Unknown')
  assert.equal(lifecycleLabel('something_else'), 'Unknown')
})

test('preflight drives invalid_data, incompatible_engine and ready_for_test', () => {
  assert.equal(classifyCalibrationRecord({ preflight: { data_valid: false } }).state, 'invalid_data')
  assert.equal(classifyCalibrationRecord({ preflight: { data_valid: true, launch_allowed: false } }).state, 'incompatible_engine')
  assert.equal(classifyCalibrationRecord({ preflight: { data_valid: true } }).state, 'incompatible_engine')
  const ready = classifyCalibrationRecord({ preflight: { data_valid: true, launch_allowed: true } })
  assert.equal(ready.state, 'ready_for_test')
  assert.equal(ready.finished, false)
})

test('a blocked preflight wins over any job or result', () => {
  const record = { preflight: { data_valid: true, launch_allowed: false }, job: { status: 'running' }, result: admissibleResult() }
  assert.equal(classifyCalibrationRecord(record).state, 'incompatible_engine')
})

test('an empty record is never ready', () => {
  for (const record of [undefined, null, {}]) {
    const classified = classifyCalibrationRecord(record)
    assert.equal(classified.state, 'invalid_data')
    assert.equal(classified.reason, 'no_record')
  }
})

test('job status gives running or numerical_failure, never success', () => {
  for (const status of ['queued', 'pending', 'running', 'started', 'RUNNING']) {
    assert.equal(classifyCalibrationRecord({ job: { status } }).state, 'running')
  }
  for (const status of ['failed', 'error', 'cancelled', 'timeout']) {
    const classified = classifyCalibrationRecord({ job: { status } })
    assert.equal(classified.state, 'numerical_failure')
    assert.equal(classified.finished, true)
  }
  assert.equal(classifyCalibrationRecord({ job: { status: 'completed' } }).state, 'invalid_data')
})

test('admissible requires completed status, healthy free ODE and a keep combined verdict', () => {
  const classified = classifyCalibrationRecord({ result: admissibleResult() })
  assert.equal(classified.state, 'admissible_candidate')
  assert.equal(classified.finished, true)
  assert.equal(classified.biologicallyValidated, false)
  assert.equal(classified.legacy, false)
  assert.equal(classifyCalibrationRecord({ result: admissibleResult({ combined_triage: { overall: 'keep_with_caveats' } }) }).state,
    'admissible_candidate')
})

test('missing or skipped free-ODE validation is never admissible', () => {
  for (const pure of [undefined, null, { skipped: true, overall: 'healthy' }, { overall: '' }]) {
    const classified = classifyCalibrationRecord({ result: admissibleResult({ pure_ode_triage: pure }) })
    assert.equal(classified.state, 'rejected_candidate')
    assert.match(classified.reason, /^free_ode_/)
  }
})

test('discard, collapsed, compromised and needs_review are rejected', () => {
  for (const [field, value] of [
    ['combined_triage', { overall: 'discard' }],
    ['combined_triage', { overall: 'needs_review' }],
    ['combined_triage', null],
    ['pure_ode_triage', { overall: 'collapsed' }],
    ['pure_ode_triage', { overall: 'compromised' }],
  ]) {
    assert.equal(classifyCalibrationRecord({ result: admissibleResult({ [field]: value }) }).state, 'rejected_candidate')
  }
})

test('a fit-side keep alone never makes a candidate admissible', () => {
  const result = admissibleResult({ triage: { overall: 'keep' }, combined_triage: null, pure_ode_triage: null })
  assert.equal(classifyCalibrationRecord({ result }).state, 'rejected_candidate')
})

test('failures and fixed-Km breaches are told apart', () => {
  assert.equal(classifyCalibrationRecord({ result: admissibleResult({ success: false }) }).state, 'numerical_failure')
  assert.equal(classifyCalibrationRecord({ result: admissibleResult({ calibration_status: 'failed' }) }).state, 'numerical_failure')
  const breach = admissibleResult({ success: false, calibration_failed: true,
    fixed_km_audit: { changed_non_vmax: { km_ATP: [0.5, 0.6] }, non_vmax_in_optimized_set: [] } })
  const classified = classifyCalibrationRecord({ result: breach })
  assert.equal(classified.state, 'rejected_candidate')
  assert.equal(classified.reason, 'fixed_km_contract_violated')
})

test('an unknown calibration_status is rejected rather than read as completed', () => {
  assert.equal(classifyCalibrationRecord({ result: admissibleResult({ calibration_status: 'setup_only' }) }).state, 'rejected_candidate')
})

test('legacy and unknown contracts are flagged legacy', () => {
  for (const overrides of [
    { parameter_contract: 'legacy_unconstrained' },
    { parameter_contract: undefined },
    { data_contract: undefined },
    { data_contract: { status: 'legacy_no_data_contract' } },
  ]) {
    assert.equal(classifyCalibrationRecord({ result: admissibleResult(overrides) }).legacy, true)
  }
})

test('activation needs admissible, non-legacy, explicit and identical identity', () => {
  const classified = classifyCalibrationRecord({ result: admissibleResult() })
  const ok = activationDecision(classified, { explicit: true, runIdentity: IDENTITY, activeIdentity: { ...IDENTITY } })
  assert.deepEqual(ok, { allowed: true, reasons: [], biologicallyValidated: false })

  assert.ok(activationDecision(classified, { explicit: false, runIdentity: IDENTITY, activeIdentity: IDENTITY })
    .reasons.includes('no_explicit_user_action'))
  assert.ok(activationDecision(classified, { runIdentity: IDENTITY, activeIdentity: IDENTITY }).allowed === false)
  for (const key of ['datasetId', 'subjectId', 'contractFingerprint']) {
    const other = activationDecision(classified, { explicit: true, runIdentity: IDENTITY, activeIdentity: { ...IDENTITY, [key]: 'other' } })
    assert.equal(other.allowed, false)
    assert.ok(other.reasons.includes(`${key}_mismatch`))
    const missing = activationDecision(classified, { explicit: true, runIdentity: { ...IDENTITY, [key]: null }, activeIdentity: IDENTITY })
    assert.ok(missing.reasons.includes(`${key}_unknown`))
  }
})

test('no activation for legacy, unknown, discard or unvalidated free ODE even when explicit', () => {
  const request = { explicit: true, runIdentity: IDENTITY, activeIdentity: IDENTITY }
  for (const result of [
    admissibleResult({ parameter_contract: 'legacy_unconstrained' }),
    admissibleResult({ data_contract: { status: 'legacy_no_data_contract' } }),
    admissibleResult({ combined_triage: { overall: 'discard' } }),
    admissibleResult({ pure_ode_triage: { skipped: true } }),
  ]) {
    assert.equal(activationDecision(classifyCalibrationRecord({ result }), request).allowed, false)
  }
  assert.equal(activationDecision(null, request).allowed, false)
  assert.equal(activationDecision(classifyCalibrationRecord({ job: { status: 'running' } }), request).allowed, false)
})

test('fit and free-ODE scores stay separate and are never combined', () => {
  const scores = separateScores(admissibleResult({ orchestration: { teacher_flux_rescue: { status: 'x' } } }))
  assert.deepEqual(Object.keys(scores), ['fit', 'freeOde'])
  assert.equal(scores.fit.source, 'calibration_objective')
  assert.equal(scores.fit.finalLoss, 1.5)
  assert.equal(scores.fit.teacherFluxRescue, 'present')
  assert.equal(scores.freeOde.source, 'pure_ode_replay')
  assert.equal(scores.freeOde.verdict, 'healthy')
  assert.equal('finalLoss' in scores.freeOde, false)
  const zero = separateScores({ final_loss: 0, objective_value: 9 })
  assert.equal(zero.fit.finalLoss, 0)
  assert.equal(separateScores({ final_loss: Number.NaN }).fit.finalLoss, null)
})

test('monitoring shows progress only from real counters while running', () => {
  assert.equal(monitoringView({ job: { status: 'running' } }).progress, null)
  assert.deepEqual(monitoringView({ job: { status: 'running', completed_cases: 3, total_cases: 12 } }).progress,
    { completed: 3, total: 12, fraction: 0.25 })
  assert.equal(monitoringView({ job: { status: 'running', completed_cases: 13, total_cases: 12 } }).progress, null)
  assert.equal(monitoringView({ job: { status: 'running', completed_cases: 1, total_cases: 0 } }).progress, null)
  assert.equal(monitoringView({ job: { status: 'failed', completed_cases: 3, total_cases: 12 } }).progress, null)
})

test('monitoring never reports validation and only reports active when admissible and explicitly active', () => {
  const finished = monitoringView({ result: admissibleResult() })
  assert.equal(finished.finished, true)
  assert.equal(finished.biologicallyValidated, false)
  assert.equal(finished.active, false)
  assert.equal(monitoringView({ result: admissibleResult(), active: true }).active, false)
  assert.equal(monitoringView({ result: admissibleResult(), active: true,
    activation: { explicit: true, runIdentity: IDENTITY, activeIdentity: IDENTITY } }).active, true)
  assert.equal(monitoringView({ result: admissibleResult({ combined_triage: { overall: 'discard' } }), active: true }).active, false)
  assert.equal(monitoringView({ job: { status: 'running' } }).finished, false)
  assert.equal(monitoringView({}).scores, null)
})

test('journey Data -> Verification -> Calibration -> Results follows the state', () => {
  assert.deepEqual([...JOURNEY_STEPS], ['data', 'verification', 'calibration', 'results'])
  const statuses = (state) => journeyFor(state).map((s) => s.status)
  assert.deepEqual(statuses('invalid_data'), ['blocked', 'pending', 'pending', 'pending'])
  assert.deepEqual(statuses('incompatible_engine'), ['done', 'blocked', 'pending', 'pending'])
  assert.deepEqual(statuses('ready_for_test'), ['done', 'done', 'current', 'pending'])
  assert.deepEqual(statuses('running'), ['done', 'done', 'current', 'pending'])
  assert.deepEqual(statuses('numerical_failure'), ['done', 'done', 'blocked', 'pending'])
  assert.deepEqual(statuses('rejected_candidate'), ['done', 'done', 'done', 'blocked'])
  assert.deepEqual(statuses('admissible_candidate'), ['done', 'done', 'done', 'current'])
  assert.deepEqual(statuses('not_a_state'), ['blocked', 'pending', 'pending', 'pending'])
})

test('a legacy run of today (no data contract) cannot reach activation', () => {
  const today = admissibleResult({ parameter_contract: 'legacy_unconstrained', data_contract: { status: 'legacy_no_data_contract' } })
  const classified = classifyCalibrationRecord({ result: today })
  const decision = activationDecision(classified, { explicit: true, runIdentity: IDENTITY, activeIdentity: IDENTITY })
  assert.equal(decision.allowed, false)
  assert.ok(decision.reasons.includes('legacy_or_unknown_contract'))
})

test('missing completion and unknown data-contract status fail closed', () => {
  assert.equal(classifyCalibrationRecord({ result: admissibleResult({ calibration_status: undefined }) }).state, 'rejected_candidate')
  for (const status of ['', 'unknown', 'invalid', 'incompatible']) {
    const classified = classifyCalibrationRecord({ result: admissibleResult({ data_contract: { status } }) })
    assert.equal(activationDecision(classified, { explicit: true, runIdentity: IDENTITY, activeIdentity: IDENTITY }).allowed, false)
  }
})

test('monitoring refuses stale identity and legacy activation flags', () => {
  const activation = { explicit: true, runIdentity: IDENTITY, activeIdentity: { ...IDENTITY, subjectId: 'another-donor' } }
  assert.equal(monitoringView({ result: admissibleResult(), active: true, activation }).active, false)
  activation.activeIdentity = IDENTITY
  assert.equal(monitoringView({ result: admissibleResult({ data_contract: undefined }), active: true, activation }).active, false)
})
