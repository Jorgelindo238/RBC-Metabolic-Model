// Data -> Verification -> Calibration -> Results: pure helpers, no network, no storage.
//
// Truthfulness rules encoded here:
//  - a draft data contract only carries what the dataset actually contains;
//    unknown units, subject, time origin, geometry and initial state stay null
//    and are listed as missing (no Bordbar substitution, no donor guess, no
//    relative -> mM conversion);
//  - data validity, engine compatibility and launch permission are separate;
//  - a reference profile is a read-only comparator; activation_allowed:false
//    is a prohibition that no click or identity match overrides;
//  - progress is shown only from real completed/total counters;
//  - persisted legacy "applied" flags are history, not verified activation.

import { activationDecision } from './calibration-lifecycle.mjs'

export const CONTRACT_SCHEMA = 'airbc.user_calibration_data/1'
export const REFERENCE_VIEW_SCHEMA = 'airbc.reference_profile_view/1'
export const FOCUS_CHANNELS = Object.freeze(['EGLC', 'ELAC'])

export const DRAFT_MISSING_FIELDS = Object.freeze([
  'dataset.cohort_id',
  'dataset.subject (donor or declared group)',
  'time.unit',
  'time.origin',
  'geometry.hematocrit and its provenance',
  'initial_state (measured or declared values; nothing is substituted)',
  'channels[].compartment',
  'channels[].kind (absolute or relative)',
  'channels[].unit',
])

function finite(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

/** Draft contract from the active dataset: only observed facts, every unknown left null. */
export function draftDataContract(datasetId, experiment) {
  const points = Array.isArray(experiment?.expTime) ? experiment.expTime.map((t) => finite(t)) : []
  const series = experiment?.expData && typeof experiment.expData === 'object' ? experiment.expData : {}
  return {
    contract: {
      schema_version: CONTRACT_SCHEMA,
      dataset: { dataset_id: datasetId ?? null, cohort_id: null, subject: null },
      time: { unit: null, origin: null, points },
      geometry: null,
      initial_state: null,
      channels: Object.entries(series).map(([name, values]) => ({
        name,
        compartment: null,
        kind: null,
        unit: null,
        values: Array.isArray(values) ? values.map((v) => finite(v)) : [],
      })),
    },
    missing: [...DRAFT_MISSING_FIELDS],
  }
}

/** Interpret a /calibration/preflight report; three answers kept apart. */
export function preflightView(report) {
  if (!report) return { state: 'not_checked', dataValid: null, engineCompatible: null, launchAllowed: false }
  if (typeof report.data_valid !== 'boolean' || typeof report.launch_allowed !== 'boolean'
    || typeof report.engine_compatibility?.compatible !== 'boolean') {
    return { state: 'preflight_unavailable', dataValid: null, engineCompatible: null, launchAllowed: false }
  }
  const dataValid = report.data_valid
  const engineCompatible = report.engine_compatibility.compatible
  const launchAllowed = report.launch_allowed === true && dataValid && engineCompatible
  return {
    state: !dataValid ? 'invalid_data' : !engineCompatible || !launchAllowed ? 'incompatible_engine' : 'ready_for_test',
    dataValid,
    engineCompatible,
    launchAllowed,
    errors: Array.isArray(report.errors) ? report.errors : [],
    warnings: Array.isArray(report.warnings) ? report.warnings : [],
    blocking: Array.isArray(report.engine_compatibility.blocking) ? report.engine_compatibility.blocking : [],
    engine: report.engine_compatibility.engine ?? null,
    conversionsPerformed: Array.isArray(report.conversions_performed) ? report.conversions_performed : [],
    initialStateSubstituted: report.initial_state_substituted === true,
    donorsMerged: report.donors_merged === true,
  }
}

/** Contractual launch follows the preflight; the legacy path is labelled, never presented as the safe path. */
export function launchGate(view) {
  const allowed = view?.launchAllowed === true
  return {
    contractLaunchAllowed: allowed,
    reason: allowed
      ? null
      : view?.state === 'invalid_data'
        ? 'The data contract is invalid; fix the reported fields first.'
        : view?.state === 'incompatible_engine'
          ? 'The engine cannot honour this data contract yet (not qualified for new contractual datasets).'
          : 'Run the preflight check first.',
    legacyLabel: 'Legacy path without a data contract: results are unverified and never activated automatically.',
  }
}

/** Normalise a reference-profile API payload; anything unexpected is an unavailable state. */
export function referenceProfileView(payload) {
  if (!payload || payload.schema !== REFERENCE_VIEW_SCHEMA) {
    return { state: 'unavailable', available: false, reason: 'unexpected or missing response' }
  }
  if (payload.available !== true || payload.state !== 'available') {
    return { state: payload.state ?? 'unavailable', available: false, reason: payload.reason ?? null,
      releaseStatus: payload.release_status ?? null, nextTask: payload.next_task ?? null }
  }
  return { ...payload, available: true }
}

/** A reference profile is never activated: the artifact prohibition wins over any click or identity match. */
export function referenceActivation(profile, request = {}) {
  if (!profile || profile.available !== true) {
    return { allowed: false, reasons: ['profile_unavailable'] }
  }
  if (profile.activation?.allowed !== true || profile.flags?.activation_allowed !== true) {
    return { allowed: false, reasons: ['activation_forbidden_by_artifact'] }
  }
  const decision = activationDecision(
    { state: 'admissible_candidate', legacy: false },
    { explicit: request.explicit, runIdentity: request.runIdentity, activeIdentity: request.activeIdentity },
  )
  return { allowed: decision.allowed, reasons: decision.reasons }
}

/** Observed vs predicted series of one species (single selected vector, no assembly). */
export function speciesSeries(profile, species) {
  const rows = Array.isArray(profile?.species_by_date) ? profile.species_by_date : []
  return rows
    .filter((row) => row.species === species)
    .sort((a, b) => a.day - b.day)
    .map((row) => ({
      day: row.day,
      observed: finite(row.observed),
      predicted: finite(row.predicted),
      residual: finite(row.predicted) !== null && finite(row.observed) !== null ? row.predicted - row.observed : null,
      normalizedResidual: finite(row.normalized_residual),
      unit: row.unit ?? null,
    }))
}

export function speciesList(profile, compartment = null) {
  const rows = Array.isArray(profile?.species_by_date) ? profile.species_by_date : []
  return [...new Set(rows.filter((r) => !compartment || r.compartment === compartment).map((r) => r.species))]
}

/** EGLC/ELAC diagnostics exactly as recorded (strict profile). */
export function focusSummary(profile) {
  const focus = profile?.scores?.strict?.focus ?? {}
  return FOCUS_CHANNELS.map((channel) => {
    const f = focus[channel] ?? {}
    return {
      channel,
      normalizedRmse: finite(f.normalized_rmse),
      j15Residual: finite(f.J15_residual_mM),
      slopePredicted: finite(f.slope_predicted_mM_per_day),
      slopeObserved: finite(f.slope_observed_mM_per_day),
      slopeError: finite(f.abs_slope_error),
    }
  })
}

/** Compact, factual limitations; no global biological-validity score. */
export function limitationNotes(profile) {
  if (!profile?.available) return []
  const notes = []
  const scope = profile.scope ?? {}
  const strict = profile.scores?.strict ?? {}
  for (const item of profile.limitations ?? []) notes.push(item)
  if (strict.worst_channel) {
    notes.push(`Worst extracellular channel: ${strict.worst_channel} (normalized RMSE ${strict.worst_normalized_rmse}); `
      + 'working bands are not assay SD.')
  }
  if (scope.unit_status?.status) notes.push(`Units: ${scope.unit_status.status}.`)
  if (scope.geometry) notes.push(scope.geometry)
  if (scope.cohort) notes.push(scope.cohort)
  if (Array.isArray(scope.horizon_days)) notes.push(`Horizon J${scope.horizon_days[0]}-J${scope.horizon_days[1]} only.`)
  if (scope.applicable_dataset) notes.push(scope.applicable_dataset)
  return notes
}

const RUNNING = new Set(['queued', 'pending', 'running', 'started', 'in_progress'])
const FAILED = new Set(['failed', 'error', 'timeout'])
const CANCELLED = new Set(['cancelled', 'canceled', 'aborted'])
const DONE = new Set(['completed', 'complete', 'finished', 'succeeded', 'success'])

/** Monitoring state of a real run record; completion is not validity. */
export function monitoringRunState(run) {
  if (!run) return { state: 'unknown', label: 'Unknown', progress: null }
  const status = String(run.completionStatus ?? run.status ?? '').toLowerCase()
  const state = RUNNING.has(status) ? 'running' : FAILED.has(status) ? 'failed' : CANCELLED.has(status)
    ? 'cancelled' : DONE.has(status) ? 'finished_unverified' : 'unknown'
  const labels = {
    running: 'Running',
    failed: 'Failed',
    cancelled: 'Cancelled',
    finished_unverified: 'Finished (not a biological validation)',
    unknown: 'Status unknown',
  }
  return { state, label: labels[state], progress: state === 'running' ? runProgress(run) : null }
}

/** Determinate progress only from real counters; otherwise indeterminate. */
export function runProgress(run) {
  const completed = finite(run?.completedCases ?? run?.completed_cases)
  const total = finite(run?.totalCases ?? run?.total_cases)
  if (completed !== null && total !== null && total > 0 && completed >= 0 && completed <= total) {
    return { mode: 'determinate', completed, total, fraction: completed / total }
  }
  return { mode: 'indeterminate' }
}

/** Persisted calibrations: legacy "applied/active" flags become history, never verified activation. */
export function interpretPersistedCalibration(record) {
  if (!record || typeof record !== 'object') return null
  const provenance = record.datasetProvenance ?? {}
  const claimed = Boolean(provenance.calibrationApplied || provenance.calibratedParametersActive)
  return {
    ...record,
    activationStatus: claimed ? 'legacy_unverified' : 'not_activated',
    legacyFlags: record.legacyFlags ?? (claimed ? {
      calibrationApplied: Boolean(provenance.calibrationApplied),
      calibratedParametersActive: Boolean(provenance.calibratedParametersActive),
    } : undefined),
    datasetProvenance: { ...provenance, calibrationApplied: false, calibratedParametersActive: false },
  }
}
