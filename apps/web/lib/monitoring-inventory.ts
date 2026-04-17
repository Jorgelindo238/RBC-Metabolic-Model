export type MonitoringBagStatus =
  | 'Fresh intake'
  | 'Forecast review'
  | 'Alert follow-up'
  | 'Under review'
  | 'Reserved'

export type MonitoringRiskBand = 'Low risk' | 'Watch' | 'Elevated'

export interface MonitoringBagCreateInput {
  bagId: string
  donorId: string
  entryDate: string
  age: number
  sex: 'F' | 'M'
  medicalProfile: MonitoringRiskBand
  repositoryStatus: MonitoringBagStatus
  storageContext: string
}

export interface MonitoringBagOperationalState {
  qualityState: string
  forecastState: string
  alerts: number
  linkedRuns: number
  monitoringEvents: number
}

export interface MonitoringBagRecord extends MonitoringBagCreateInput, MonitoringBagOperationalState {}

export const MONITORING_BAG_STATUSES: readonly MonitoringBagStatus[] = [
  'Fresh intake',
  'Forecast review',
  'Alert follow-up',
  'Under review',
  'Reserved',
] as const

export const MONITORING_BAG_RECORDS: readonly MonitoringBagRecord[] = [
  {
    bagId: 'BAG-1042',
    donorId: 'DON-118',
    entryDate: '2026-03-22',
    age: 28,
    sex: 'F',
    medicalProfile: 'Low risk',
    repositoryStatus: 'Fresh intake',
    storageContext: 'Cold room A3 · rack 4',
    qualityState: 'Stable',
    forecastState: 'Stable through 72h',
    alerts: 0,
    linkedRuns: 1,
    monitoringEvents: 4,
  },
  {
    bagId: 'BAG-1178',
    donorId: 'DON-244',
    entryDate: '2026-03-21',
    age: 41,
    sex: 'M',
    medicalProfile: 'Watch',
    repositoryStatus: 'Forecast review',
    storageContext: 'Cold room B1 · rack 2',
    qualityState: 'Early drift',
    forecastState: 'Watch 7d curve',
    alerts: 1,
    linkedRuns: 2,
    monitoringEvents: 5,
  },
  {
    bagId: 'BAG-1211',
    donorId: 'DON-301',
    entryDate: '2026-03-20',
    age: 36,
    sex: 'F',
    medicalProfile: 'Elevated',
    repositoryStatus: 'Alert follow-up',
    storageContext: 'Cold room C2 · rack 1',
    qualityState: 'Quality drop projected',
    forecastState: 'Threshold near 14d',
    alerts: 2,
    linkedRuns: 2,
    monitoringEvents: 7,
  },
  {
    bagId: 'BAG-1224',
    donorId: 'DON-322',
    entryDate: '2026-03-19',
    age: 32,
    sex: 'M',
    medicalProfile: 'Low risk',
    repositoryStatus: 'Reserved',
    storageContext: 'Cold room A1 · rack 7',
    qualityState: 'Stable',
    forecastState: 'Stable through 24h',
    alerts: 0,
    linkedRuns: 1,
    monitoringEvents: 2,
  },
  {
    bagId: 'BAG-1250',
    donorId: 'DON-366',
    entryDate: '2026-03-18',
    age: 45,
    sex: 'F',
    medicalProfile: 'Elevated',
    repositoryStatus: 'Under review',
    storageContext: 'Cold room D3 · rack 5',
    qualityState: 'Lactate drift',
    forecastState: 'Short horizon watch',
    alerts: 1,
    linkedRuns: 2,
    monitoringEvents: 6,
  },
  {
    bagId: 'BAG-1288',
    donorId: 'DON-401',
    entryDate: '2026-03-17',
    age: 30,
    sex: 'M',
    medicalProfile: 'Watch',
    repositoryStatus: 'Alert follow-up',
    storageContext: 'Cold room B3 · rack 1',
    qualityState: 'Review due',
    forecastState: 'Projected drop',
    alerts: 1,
    linkedRuns: 1,
    monitoringEvents: 5,
  },
] as const

function toTrimmedString(value: unknown) {
  if (typeof value !== 'string') {
    return null
  }

  const trimmed = value.trim()
  return trimmed ? trimmed : null
}

function normalizeEntryDate(value: unknown) {
  const trimmed = toTrimmedString(value)
  if (!trimmed) {
    return null
  }

  const parsed = new Date(trimmed)
  if (Number.isNaN(parsed.getTime())) {
    return null
  }

  return parsed.toISOString().slice(0, 10)
}

function normalizeAge(value: unknown) {
  const numericValue = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(numericValue) && numericValue > 0 ? Math.floor(numericValue) : null
}

function normalizeSex(value: unknown): 'F' | 'M' | null {
  return value === 'F' || value === 'M' ? value : null
}

function normalizeRiskBand(value: unknown): MonitoringRiskBand | null {
  return value === 'Low risk' || value === 'Watch' || value === 'Elevated' ? value : null
}

function normalizeRepositoryStatus(value: unknown): MonitoringBagStatus | null {
  return value === 'Fresh intake' ||
    value === 'Forecast review' ||
    value === 'Alert follow-up' ||
    value === 'Under review' ||
    value === 'Reserved'
    ? value
    : null
}

function normalizeCount(value: unknown, fallback = 0) {
  const numericValue = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(numericValue) && numericValue >= 0 ? Math.floor(numericValue) : fallback
}

function cloneRecord(record: MonitoringBagRecord): MonitoringBagRecord {
  return { ...record }
}

export function normalizeMonitoringBagRecord(value: unknown): MonitoringBagRecord | null {
  if (!value || typeof value !== 'object') {
    return null
  }

  const candidate = value as Record<string, unknown>
  const bagId = toTrimmedString(candidate.bagId)
  const donorId = toTrimmedString(candidate.donorId)
  const entryDate = normalizeEntryDate(candidate.entryDate)
  const age = normalizeAge(candidate.age)
  const sex = normalizeSex(candidate.sex)
  const medicalProfile = normalizeRiskBand(candidate.medicalProfile)
  const repositoryStatus = normalizeRepositoryStatus(candidate.repositoryStatus ?? candidate.status)
  const storageContext = toTrimmedString(candidate.storageContext)
  const qualityState = toTrimmedString(candidate.qualityState) ?? 'Stable'
  const forecastState = toTrimmedString(candidate.forecastState) ?? 'Forecast pending'
  const alerts = normalizeCount(candidate.alerts)
  const linkedRuns = normalizeCount(candidate.linkedRuns)
  const monitoringEvents = normalizeCount(candidate.monitoringEvents ?? candidate.linkedEvents)

  if (!bagId || !donorId || !entryDate || age === null || !sex || !medicalProfile || !repositoryStatus || !storageContext) {
    return null
  }

  return {
    bagId: bagId.toUpperCase(),
    donorId: donorId.toUpperCase(),
    entryDate,
    age,
    sex,
    medicalProfile,
    repositoryStatus,
    storageContext,
    qualityState,
    forecastState,
    alerts,
    linkedRuns,
    monitoringEvents,
  }
}

export function normalizeMonitoringBagRecords(records: unknown) {
  if (!Array.isArray(records)) {
    return MONITORING_BAG_RECORDS.map(cloneRecord)
  }

  const normalized = records.map(normalizeMonitoringBagRecord).filter(Boolean) as MonitoringBagRecord[]
  return normalized.length ? normalized.map(cloneRecord) : MONITORING_BAG_RECORDS.map(cloneRecord)
}

export function getMonitoringBagStatusTone(status: MonitoringBagStatus) {
  switch (status) {
    case 'Fresh intake':
      return 'border-cyan-400/20 bg-cyan-400/10 text-cyan-100'
    case 'Forecast review':
      return 'border-emerald-400/20 bg-emerald-400/10 text-emerald-100'
    case 'Alert follow-up':
      return 'border-rose-400/20 bg-rose-400/10 text-rose-100'
    case 'Under review':
      return 'border-amber-400/20 bg-amber-400/10 text-amber-100'
    case 'Reserved':
      return 'border-white/10 bg-white/[0.04] text-slate-300'
    default:
      return 'border-white/10 bg-white/[0.04] text-slate-300'
  }
}

export function getMonitoringBagRiskTone(risk: MonitoringRiskBand) {
  switch (risk) {
    case 'Low risk':
      return 'border-emerald-400/20 bg-emerald-400/10 text-emerald-100'
    case 'Watch':
      return 'border-amber-400/20 bg-amber-400/10 text-amber-100'
    case 'Elevated':
      return 'border-rose-400/20 bg-rose-400/10 text-rose-100'
    default:
      return 'border-white/10 bg-white/[0.04] text-slate-300'
  }
}

export function getMonitoringBagById(bagId: string) {
  return MONITORING_BAG_RECORDS.find((bag) => bag.bagId === bagId) ?? null
}
