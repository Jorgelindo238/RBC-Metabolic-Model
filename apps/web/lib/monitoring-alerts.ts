import type { ResearchSimulationSnapshot } from '@/types/research-simulation'
import {
  buildMonitoringForecastProjection,
  type MonitoringForecastInput,
  type MonitoringForecastProjection,
} from './monitoring-forecast'
import type { MonitoringBagRecord, MonitoringBagStatus } from './monitoring-inventory'

export type MonitoringAlertSeverity = 'Normal' | 'Watch' | 'Elevated' | 'High' | 'Critical'

export type MonitoringAlertWorkflowStatus =
  | 'New'
  | 'Acknowledged'
  | 'In review'
  | 'Escalated'
  | 'Resolved'

export type MonitoringAlertSource = 'forecast' | 'forecast+simulation'

export interface MonitoringAlertForecastSnapshot {
  qualityScore: number
  riskBand: MonitoringForecastProjection['riskBand']
  reviewWindowDays: number
  confidence: number
  driftRate: number
  recommendation: string
  alertSummary: string
  driverSummary: string
  snapshotSummary: string
}

export interface MonitoringAlertRecord {
  alertId: string
  bagId: string
  severity: MonitoringAlertSeverity
  riskBand: MonitoringForecastProjection['riskBand']
  operationalStatus: MonitoringAlertWorkflowStatus
  summary: string
  recommendation: string
  reviewWindowDays: number
  confidence: number
  driftRate: number
  qualityScore: number
  repositoryStatus: MonitoringBagStatus
  triggerSignals: string[]
  source: MonitoringAlertSource
  createdAt: string
  updatedAt: string
  forecastSnapshot: MonitoringAlertForecastSnapshot
}

export interface MonitoringAlertWorkflowStateRecord {
  alertId: string
  bagId: string
  workflowStatus: MonitoringAlertWorkflowStatus
  note: string | null
  createdAt: string
  updatedAt: string
  updatedBy: string | null
}

export interface MonitoringAlertWorkflowTransitionRecord {
  alertId: string
  bagId: string
  previousStatus: MonitoringAlertWorkflowStatus
  nextStatus: MonitoringAlertWorkflowStatus
  changedAt: string
  note: string | null
  updatedBy: string | null
}

export interface MonitoringAlertWorkflowUpdateInput {
  bagId: string
  workflowStatus: MonitoringAlertWorkflowStatus
  note?: string | null
  updatedBy?: string | null
}

export type MonitoringAlertViewRecord = MonitoringAlertRecord & {
  workflowState: MonitoringAlertWorkflowStateRecord
}

const MONITORING_ALERT_API_BASE_URL =
  typeof window !== 'undefined'
    ? '/api'
    : process.env.INTERNAL_WEB_API_BASE_URL || 'http://127.0.0.1:3000/api'

const ALERT_INPUTS_BY_PROFILE: Record<MonitoringBagRecord['medicalProfile'], MonitoringForecastInput> = {
  'Low risk': {
    lactate: 7.1,
    glucose: 5.2,
    alanine: 1.0,
    glutathione: 1.9,
  },
  Watch: {
    lactate: 8.1,
    glucose: 4.7,
    alanine: 1.15,
    glutathione: 1.55,
  },
  Elevated: {
    lactate: 8.9,
    glucose: 4.1,
    alanine: 1.35,
    glutathione: 1.2,
  },
}

const ALERT_INPUTS_BY_STATUS: Partial<Record<MonitoringBagStatus, MonitoringForecastInput>> = {
  'Fresh intake': {
    lactate: 7.2,
    glucose: 5.0,
    alanine: 1.0,
    glutathione: 1.85,
  },
  'Forecast review': {
    lactate: 8.2,
    glucose: 4.6,
    alanine: 1.15,
    glutathione: 1.55,
  },
  'Alert follow-up': {
    lactate: 8.8,
    glucose: 4.0,
    alanine: 1.35,
    glutathione: 1.2,
  },
  'Under review': {
    lactate: 8.4,
    glucose: 4.3,
    alanine: 1.25,
    glutathione: 1.35,
  },
  Reserved: {
    lactate: 7.4,
    glucose: 4.9,
    alanine: 1.0,
    glutathione: 1.85,
  },
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

function toTrimmedString(value: unknown) {
  if (typeof value !== 'string') {
    return null
  }

  const trimmed = value.trim()
  return trimmed ? trimmed : null
}

function toPercent(value: number) {
  return `${Math.round(value * 100)}%`
}

function normalizeWorkflowStatus(value: unknown): MonitoringAlertWorkflowStatus | null {
  if (
    value === 'New' ||
    value === 'Acknowledged' ||
    value === 'In review' ||
    value === 'Escalated' ||
    value === 'Resolved'
  ) {
    return value
  }

  return null
}

function normalizeTimestamp(value: unknown, fallback: string) {
  const trimmed = toTrimmedString(value)
  return trimmed ?? fallback
}

function readErrorMessage(payload: unknown, fallback: string) {
  if (typeof payload === 'string' && payload.trim()) {
    return payload.trim()
  }

  if (!payload || typeof payload !== 'object') {
    return fallback
  }

  const candidate = payload as { detail?: unknown; message?: unknown }

  if (typeof candidate.detail === 'string' && candidate.detail.trim()) {
    return candidate.detail.trim()
  }

  if (typeof candidate.message === 'string' && candidate.message.trim()) {
    return candidate.message.trim()
  }

  try {
    return JSON.stringify(payload)
  } catch {
    return fallback
  }
}

function getAlertInputForBag(bag: MonitoringBagRecord): MonitoringForecastInput {
  return {
    ...ALERT_INPUTS_BY_PROFILE[bag.medicalProfile],
    ...(ALERT_INPUTS_BY_STATUS[bag.repositoryStatus] ?? {}),
  }
}

function cloneWorkflowState(record: MonitoringAlertWorkflowStateRecord): MonitoringAlertWorkflowStateRecord {
  return { ...record }
}

function buildDefaultWorkflowState(alert: MonitoringAlertRecord): MonitoringAlertWorkflowStateRecord {
  return {
    alertId: alert.alertId,
    bagId: alert.bagId,
    workflowStatus: alert.operationalStatus,
    note: null,
    createdAt: alert.createdAt,
    updatedAt: alert.updatedAt,
    updatedBy: null,
  }
}

function getSeverityOrder(severity: MonitoringAlertSeverity) {
  switch (severity) {
    case 'Critical':
      return 4
    case 'High':
      return 3
    case 'Elevated':
      return 2
    case 'Watch':
      return 1
    default:
      return 0
  }
}

function getSeverityFromProjection(projection: MonitoringForecastProjection): MonitoringAlertSeverity {
  if (projection.riskBand === 'Critical' || projection.qualityScore <= 0.38 || projection.reviewWindowDays <= 1) {
    return 'Critical'
  }

  if (
    projection.alertSeverity === 'High' ||
    projection.qualityScore <= 0.48 ||
    projection.reviewWindowDays <= 2 ||
    projection.driftRate >= 0.075
  ) {
    return 'High'
  }

  if (projection.riskBand === 'Elevated' || projection.reviewWindowDays <= 4 || projection.driftRate >= 0.055) {
    return 'Elevated'
  }

  if (projection.riskBand === 'Watch' || projection.reviewWindowDays <= 7) {
    return 'Watch'
  }

  return 'Normal'
}

function getAlertTone(severity: MonitoringAlertSeverity) {
  switch (severity) {
    case 'Normal':
      return 'border-white/10 bg-white/[0.04] text-slate-300'
    case 'Watch':
      return 'border-cyan-400/20 bg-cyan-400/10 text-cyan-100'
    case 'Elevated':
      return 'border-amber-400/20 bg-amber-400/10 text-amber-100'
    case 'High':
      return 'border-rose-400/20 bg-rose-400/10 text-rose-100'
    case 'Critical':
      return 'border-red-400/20 bg-red-400/10 text-red-100'
    default:
      return 'border-white/10 bg-white/[0.04] text-slate-300'
  }
}

function getWorkflowTone(status: MonitoringAlertWorkflowStatus) {
  switch (status) {
    case 'New':
      return 'border-white/10 bg-white/[0.04] text-slate-300'
    case 'Acknowledged':
      return 'border-cyan-400/20 bg-cyan-400/10 text-cyan-100'
    case 'In review':
      return 'border-amber-400/20 bg-amber-400/10 text-amber-100'
    case 'Escalated':
      return 'border-rose-400/20 bg-rose-400/10 text-rose-100'
    case 'Resolved':
      return 'border-emerald-400/20 bg-emerald-400/10 text-emerald-100'
    default:
      return 'border-white/10 bg-white/[0.04] text-slate-300'
  }
}

function buildTriggerSignals(
  bag: MonitoringBagRecord,
  projection: MonitoringForecastProjection
): string[] {
  const signals = [
    projection.driverSummary,
    `Review window: ${projection.reviewWindowDays} day${projection.reviewWindowDays === 1 ? '' : 's'}`,
    `Confidence: ${toPercent(projection.confidence)}`,
  ]

  if (projection.driftRate >= 0.055) {
    signals.push(`Drift rate: ${(projection.driftRate * 100).toFixed(1)}% per day`)
  }

  signals.push(`Repository status: ${bag.repositoryStatus}`)
  signals.push(projection.snapshotSummary)

  return signals
}

function buildForecastSnapshot(projection: MonitoringForecastProjection): MonitoringAlertForecastSnapshot {
  return {
    qualityScore: roundToTwo(projection.qualityScore),
    riskBand: projection.riskBand,
    reviewWindowDays: projection.reviewWindowDays,
    confidence: roundToTwo(projection.confidence),
    driftRate: roundToTwo(projection.driftRate),
    recommendation: projection.recommendation,
    alertSummary: projection.alertSummary,
    driverSummary: projection.driverSummary,
    snapshotSummary: projection.snapshotSummary,
  }
}

export function normalizeMonitoringAlertWorkflowStateRecord(
  value: unknown
): MonitoringAlertWorkflowStateRecord | null {
  if (!value || typeof value !== 'object') {
    return null
  }

  const candidate = value as Record<string, unknown>
  const bagId = toTrimmedString(candidate.bagId)
  const alertId = toTrimmedString(candidate.alertId) ?? (bagId ? `ALERT-${bagId}` : null)
  const workflowStatus = normalizeWorkflowStatus(candidate.workflowStatus ?? candidate.status)
  const note = toTrimmedString(candidate.note)
  const createdAt = normalizeTimestamp(candidate.createdAt, normalizeTimestamp(candidate.updatedAt, new Date().toISOString()))
  const updatedAt = normalizeTimestamp(candidate.updatedAt, createdAt)
  const updatedBy = toTrimmedString(candidate.updatedBy)

  if (!bagId || !alertId || !workflowStatus) {
    return null
  }

  return {
    alertId: alertId.toUpperCase(),
    bagId: bagId.toUpperCase(),
    workflowStatus,
    note,
    createdAt,
    updatedAt,
    updatedBy,
  }
}

export function normalizeMonitoringAlertWorkflowTransitionRecord(
  value: unknown
): MonitoringAlertWorkflowTransitionRecord | null {
  if (!value || typeof value !== 'object') {
    return null
  }

  const candidate = value as Record<string, unknown>
  const bagId = toTrimmedString(candidate.bagId)
  const alertId = toTrimmedString(candidate.alertId) ?? (bagId ? `ALERT-${bagId}` : null)
  const previousStatus = normalizeWorkflowStatus(candidate.previousStatus)
  const nextStatus = normalizeWorkflowStatus(candidate.nextStatus)
  const changedAt = normalizeTimestamp(candidate.changedAt, new Date().toISOString())
  const note = toTrimmedString(candidate.note)
  const updatedBy = toTrimmedString(candidate.updatedBy)

  if (!bagId || !alertId || !previousStatus || !nextStatus) {
    return null
  }

  return {
    alertId: alertId.toUpperCase(),
    bagId: bagId.toUpperCase(),
    previousStatus,
    nextStatus,
    changedAt,
    note,
    updatedBy,
  }
}

export function normalizeMonitoringAlertWorkflowStateRecords(records: unknown) {
  if (!Array.isArray(records)) {
    return []
  }

  return records.map(normalizeMonitoringAlertWorkflowStateRecord).filter(Boolean) as MonitoringAlertWorkflowStateRecord[]
}

export function normalizeMonitoringAlertWorkflowTransitionRecords(records: unknown) {
  if (!Array.isArray(records)) {
    return []
  }

  return records
    .map(normalizeMonitoringAlertWorkflowTransitionRecord)
    .filter(Boolean) as MonitoringAlertWorkflowTransitionRecord[]
}

export function mergeMonitoringAlertWorkflowStates(
  alerts: MonitoringAlertRecord[],
  workflowStates: MonitoringAlertWorkflowStateRecord[]
): MonitoringAlertViewRecord[] {
  const stateByBagId = new Map<string, MonitoringAlertWorkflowStateRecord>()
  const stateByAlertId = new Map<string, MonitoringAlertWorkflowStateRecord>()

  for (const workflowState of workflowStates) {
    stateByBagId.set(workflowState.bagId.toUpperCase(), workflowState)
    stateByAlertId.set(workflowState.alertId.toUpperCase(), workflowState)
  }

  return alerts.map((alert) => {
    const workflowState =
      stateByBagId.get(alert.bagId.toUpperCase()) ??
      stateByAlertId.get(alert.alertId.toUpperCase()) ??
      buildDefaultWorkflowState(alert)

    return {
      ...alert,
      operationalStatus: workflowState.workflowStatus,
      updatedAt: workflowState.updatedAt,
      workflowState: cloneWorkflowState(workflowState),
    }
  })
}

function roundToTwo(value: number) {
  return Math.round(value * 100) / 100
}

function buildCreatedAt(entryDate: string, severity: MonitoringAlertSeverity) {
  const base = new Date(`${entryDate}T12:00:00Z`)
  const offsetHours = getSeverityOrder(severity) * 3
  return new Date(base.getTime() + offsetHours * 60 * 60 * 1000).toISOString()
}

function buildAlertSummary(bag: MonitoringBagRecord, projection: MonitoringForecastProjection, severity: MonitoringAlertSeverity) {
  if (severity === 'Critical') {
    return `${bag.bagId} is in immediate review territory with a ${projection.reviewWindowDays}-day window.`
  }

  if (severity === 'High') {
    return `${bag.bagId} is pushing into high-priority review with a ${projection.reviewWindowDays}-day window.`
  }

  if (severity === 'Elevated') {
    return `${bag.bagId} is trending upward in urgency and should be reviewed within ${projection.reviewWindowDays} days.`
  }

  return `${bag.bagId} should stay on the watch queue for the next ${projection.reviewWindowDays} days.`
}

function buildAlertWorkflowApiUrl(path: string) {
  return `${MONITORING_ALERT_API_BASE_URL}${path}`
}

export async function fetchMonitoringAlertWorkflowStatesFromApi() {
  const response = await fetch(buildAlertWorkflowApiUrl('/monitoring/alerts/workflow-states'), {
    cache: 'no-store',
  })

  if (!response.ok) {
    let payload: unknown = null
    try {
      payload = await response.json()
    } catch {
      payload = null
    }

    throw new Error(readErrorMessage(payload, `Failed to load monitoring alert workflow states (${response.status})`))
  }

  const payload = await response.json()
  return normalizeMonitoringAlertWorkflowStateRecords(payload)
}

export async function fetchMonitoringAlertWorkflowHistoryFromApi(limit = 50) {
  const safeLimit = Math.max(1, Math.floor(limit))
  const response = await fetch(
    buildAlertWorkflowApiUrl(`/monitoring/alerts/workflow-history?limit=${encodeURIComponent(String(safeLimit))}`),
    {
      cache: 'no-store',
    }
  )

  if (!response.ok) {
    let payload: unknown = null
    try {
      payload = await response.json()
    } catch {
      payload = null
    }

    throw new Error(readErrorMessage(payload, `Failed to load monitoring alert workflow history (${response.status})`))
  }

  const payload = await response.json()
  return normalizeMonitoringAlertWorkflowTransitionRecords(payload)
}

export async function updateMonitoringAlertWorkflowStateOnApi(input: MonitoringAlertWorkflowUpdateInput) {
  const bagId = toTrimmedString(input.bagId)
  if (!bagId) {
    throw new Error('bagId is required.')
  }

  const response = await fetch(buildAlertWorkflowApiUrl(`/monitoring/alerts/${encodeURIComponent(bagId)}/workflow`), {
    body: JSON.stringify({
      workflowStatus: input.workflowStatus,
      note: input.note ?? null,
      updatedBy: input.updatedBy ?? null,
    }),
    headers: {
      'Content-Type': 'application/json',
    },
    method: 'PUT',
  })

  if (!response.ok) {
    let payload: unknown = null
    try {
      payload = await response.json()
    } catch {
      payload = null
    }

    throw new Error(
      readErrorMessage(payload, `Failed to update monitoring alert workflow state (${response.status})`)
    )
  }

  const payload = await response.json()
  const workflowState = normalizeMonitoringAlertWorkflowStateRecord(payload)

  if (!workflowState) {
    throw new Error('The monitoring API returned an invalid alert workflow record.')
  }

  return workflowState
}

export function buildMonitoringAlertQueue(
  bags: MonitoringBagRecord[],
  snapshot: ResearchSimulationSnapshot | null
): MonitoringAlertRecord[] {
  return bags
    .map((bag) => {
      const projection = buildMonitoringForecastProjection(bag, getAlertInputForBag(bag), snapshot)
      const severity = getSeverityFromProjection(projection)

      if (severity === 'Normal') {
        return null
      }

      const createdAt = buildCreatedAt(bag.entryDate, severity)
      const snapshotSummary = buildForecastSnapshot(projection)

      return {
        alertId: `ALERT-${bag.bagId}`,
        bagId: bag.bagId,
        severity,
        riskBand: projection.riskBand,
        operationalStatus: 'New' as const,
        summary: buildAlertSummary(bag, projection, severity),
        recommendation: projection.recommendation,
        reviewWindowDays: projection.reviewWindowDays,
        confidence: projection.confidence,
        driftRate: projection.driftRate,
        qualityScore: projection.qualityScore,
        repositoryStatus: bag.repositoryStatus,
        triggerSignals: buildTriggerSignals(bag, projection),
        source: snapshot ? 'forecast+simulation' : 'forecast',
        createdAt,
        updatedAt: createdAt,
        forecastSnapshot: snapshotSummary,
      } satisfies MonitoringAlertRecord
    })
    .filter(Boolean)
    .map((item) => item as MonitoringAlertRecord)
    .sort((left, right) => {
      const severityDelta = getSeverityOrder(right.severity) - getSeverityOrder(left.severity)
      if (severityDelta !== 0) {
        return severityDelta
      }

      if (left.reviewWindowDays !== right.reviewWindowDays) {
        return left.reviewWindowDays - right.reviewWindowDays
      }

      if (left.confidence !== right.confidence) {
        return right.confidence - left.confidence
      }

      return right.driftRate - left.driftRate
    })
}

export function getMonitoringAlertSeverityTone(severity: MonitoringAlertSeverity) {
  return getAlertTone(severity)
}

export function getMonitoringAlertWorkflowTone(status: MonitoringAlertWorkflowStatus) {
  return getWorkflowTone(status)
}
