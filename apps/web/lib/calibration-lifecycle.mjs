// Shared calibration lifecycle for the Calibration and Monitoring views.
//
// Pure functions, no network, no storage, no React. Every state is derived
// from what the API actually returned; nothing here invents progress or
// success. Three facts are kept apart on purpose:
//   finished               the execution ended (any outcome);
//   biologicallyValidated  never true here: no biological validation exists;
//   active                 only after an explicit, allowed activation.

export const LIFECYCLE_VERSION = 'calibration-lifecycle/1'

export const LIFECYCLE_STATES = Object.freeze([
  'invalid_data',
  'incompatible_engine',
  'ready_for_test',
  'running',
  'numerical_failure',
  'rejected_candidate',
  'admissible_candidate',
])

const STATE_LABELS = Object.freeze({
  invalid_data: 'Data invalid',
  incompatible_engine: 'Engine cannot use these data yet',
  ready_for_test: 'Ready for a test run',
  running: 'Running',
  numerical_failure: 'Execution failed',
  rejected_candidate: 'Candidate rejected',
  admissible_candidate: 'Candidate admissible (not biologically validated)',
})

const RUNNING_JOB_STATUSES = new Set(['queued', 'pending', 'running', 'started'])
const FAILED_JOB_STATUSES = new Set(['failed', 'error', 'cancelled', 'timeout'])
const KEEP_VERDICTS = new Set(['keep', 'keep_with_caveats'])
const HEALTHY_FREE_ODE = new Set(['healthy', 'keep', 'keep_with_caveats'])
const FINISHED_STATES = new Set(['numerical_failure', 'rejected_candidate', 'admissible_candidate'])

function text(value) {
  return typeof value === 'string' ? value.trim().toLowerCase() : ''
}

function finiteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function freeOdeOutcome(result) {
  const pure = result?.pure_ode_triage
  if (!pure || typeof pure !== 'object') return { available: false, verdict: null, reason: 'free_ode_validation_missing' }
  if (pure.skipped) return { available: false, verdict: null, reason: 'free_ode_validation_skipped' }
  const verdict = text(pure.overall)
  if (!verdict) return { available: false, verdict: null, reason: 'free_ode_verdict_missing' }
  return { available: true, verdict, reason: null }
}

function contractOf(result) {
  const parameterContract = text(result?.parameter_contract) || 'unknown'
  const dataContractStatus = text(result?.data_contract?.status)
  const legacy = parameterContract !== 'vmax_only_fixed_km' || dataContractStatus !== 'preflight_passed'
  return { parameterContract, dataContractStatus: dataContractStatus || 'absent', legacy }
}

/**
 * Classify one calibration record. Input fields are all optional:
 *   preflight  report of POST /calibration/preflight
 *   job        { status, error } of a worker job
 *   result     body returned by /calibration/run or a finished job
 * Returns { state, reason, finished, biologicallyValidated, legacy, ... }.
 */
export function classifyCalibrationRecord(record = {}) {
  const { preflight, job, result } = record || {}
  const base = { version: LIFECYCLE_VERSION, biologicallyValidated: false }

  if (preflight && preflight.data_valid === false) {
    return { ...base, state: 'invalid_data', reason: 'preflight_reported_invalid_data', finished: false, legacy: false }
  }
  if (preflight && preflight.data_valid === true && preflight.launch_allowed !== true) {
    return { ...base, state: 'incompatible_engine', reason: 'engine_compatibility_false', finished: false, legacy: false }
  }

  const jobStatus = text(job?.status)
  if (!result) {
    if (RUNNING_JOB_STATUSES.has(jobStatus)) {
      return { ...base, state: 'running', reason: `job_${jobStatus}`, finished: false, legacy: false }
    }
    if (FAILED_JOB_STATUSES.has(jobStatus)) {
      return { ...base, state: 'numerical_failure', reason: `job_${jobStatus}`, finished: true, legacy: false }
    }
    if (preflight && preflight.launch_allowed === true) {
      return { ...base, state: 'ready_for_test', reason: 'preflight_passed', finished: false, legacy: false }
    }
    // No preflight, no job, no result: nothing is known, nothing is ready.
    return { ...base, state: 'invalid_data', reason: 'no_record', finished: false, legacy: true }
  }

  const contract = contractOf(result)
  const free = freeOdeOutcome(result)
  const common = { ...base, finished: true, legacy: contract.legacy, parameterContract: contract.parameterContract,
    dataContractStatus: contract.dataContractStatus, freeOde: free }

  const status = text(result.calibration_status)
  if (result.success === false || result.calibration_failed === true || status === 'failed') {
    const breach = Boolean(result.fixed_km_audit && (Object.keys(result.fixed_km_audit.changed_non_vmax || {}).length
      || (result.fixed_km_audit.non_vmax_in_optimized_set || []).length))
    return breach
      ? { ...common, state: 'rejected_candidate', reason: 'fixed_km_contract_violated' }
      : { ...common, state: 'numerical_failure', reason: 'execution_reported_failure' }
  }
  if (status !== 'completed') {
    return { ...common, state: 'rejected_candidate', reason: `unrecognized_calibration_status_${status}` }
  }
  if (!free.available) {
    return { ...common, state: 'rejected_candidate', reason: free.reason }
  }
  if (!HEALTHY_FREE_ODE.has(free.verdict)) {
    return { ...common, state: 'rejected_candidate', reason: `free_ode_${free.verdict}` }
  }
  const combined = text(result.combined_triage?.overall)
  if (!combined) {
    return { ...common, state: 'rejected_candidate', reason: 'combined_verdict_missing' }
  }
  if (!KEEP_VERDICTS.has(combined)) {
    return { ...common, state: 'rejected_candidate', reason: `combined_${combined}` }
  }
  return { ...common, state: 'admissible_candidate', reason: `combined_${combined}_free_ode_${free.verdict}` }
}

/** Fit/teacher-side and free-ODE scores, never merged into one number. */
export function separateScores(result) {
  return {
    fit: {
      source: 'calibration_objective',
      finalLoss: finiteNumber(result?.final_loss ?? result?.objective_value),
      baselineLoss: finiteNumber(result?.baseline_loss),
      improvementPct: finiteNumber(result?.improvement_pct),
      rSquared: finiteNumber(result?.r_squared),
      verdict: text(result?.triage?.overall) || null,
      teacherFluxRescue: result?.orchestration?.teacher_flux_rescue ? 'present' : 'absent',
    },
    freeOde: {
      source: 'pure_ode_replay',
      ...freeOdeOutcome(result),
    },
  }
}

function identityOf(value) {
  return {
    datasetId: value?.datasetId ?? value?.dataset_id ?? null,
    subjectId: value?.subjectId ?? value?.subject_id ?? null,
    contractFingerprint: value?.contractFingerprint ?? value?.contract_fingerprint ?? null,
  }
}

/**
 * Decide whether a classified record may become the active calibration.
 * `request.explicit` must be true (a user action); the run identity and the
 * currently active dataset identity must both be known and equal.
 */
export function activationDecision(classified, request = {}) {
  const reasons = []
  if (!classified || classified.state !== 'admissible_candidate') reasons.push(`state_${classified?.state ?? 'unknown'}`)
  if (classified?.legacy !== false) reasons.push('legacy_or_unknown_contract')
  if (request.explicit !== true) reasons.push('no_explicit_user_action')
  const run = identityOf(request.runIdentity)
  const active = identityOf(request.activeIdentity)
  for (const key of ['datasetId', 'subjectId', 'contractFingerprint']) {
    if (!run[key] || !active[key]) reasons.push(`${key}_unknown`)
    else if (run[key] !== active[key]) reasons.push(`${key}_mismatch`)
  }
  return { allowed: reasons.length === 0, reasons, biologicallyValidated: false }
}

/** Monitoring view of a record: real states only, progress only from real counters. */
export function monitoringView(record = {}) {
  const classified = classifyCalibrationRecord(record)
  const completed = finiteNumber(record?.job?.completed_cases ?? record?.job?.completedCases)
  const total = finiteNumber(record?.job?.total_cases ?? record?.job?.totalCases)
  const progress = classified.state === 'running' && completed !== null && total !== null && total > 0 && completed >= 0 && completed <= total
    ? { completed, total, fraction: completed / total }
    : null
  return {
    state: classified.state,
    label: STATE_LABELS[classified.state],
    reason: classified.reason,
    finished: FINISHED_STATES.has(classified.state),
    biologicallyValidated: false,
    active: record?.active === true && activationDecision(classified, {
      explicit: record?.activation?.explicit === true,
      runIdentity: record?.activation?.runIdentity,
      activeIdentity: record?.activation?.activeIdentity,
    }).allowed,
    progress,
    scores: record?.result ? separateScores(record.result) : null,
  }
}

export const JOURNEY_STEPS = Object.freeze(['data', 'verification', 'calibration', 'results'])

const STEP_OF_STATE = Object.freeze({
  invalid_data: ['data', 'blocked'],
  incompatible_engine: ['verification', 'blocked'],
  ready_for_test: ['calibration', 'current'],
  running: ['calibration', 'current'],
  numerical_failure: ['calibration', 'blocked'],
  rejected_candidate: ['results', 'blocked'],
  admissible_candidate: ['results', 'current'],
})

/** Data -> Verification -> Calibration -> Results, derived from the state only. */
export function journeyFor(state) {
  const [step, status] = STEP_OF_STATE[state] ?? ['data', 'blocked']
  const index = JOURNEY_STEPS.indexOf(step)
  return JOURNEY_STEPS.map((name, i) => ({
    step: name,
    status: i < index ? 'done' : i === index ? status : 'pending',
  }))
}

export function lifecycleLabel(state) {
  return STATE_LABELS[state] ?? 'Unknown'
}
