import type { ResearchSimulationSnapshot } from '@/types/research-simulation'
import type { MonitoringBagRecord, MonitoringRiskBand } from './monitoring-inventory'

export interface MonitoringForecastInput {
  lactate: number
  glucose: number
  alanine: number
  glutathione: number
}

export interface MonitoringForecastPoint {
  label: string
  hours: number
  qualityScore: number
  riskBand: MonitoringRiskBand | 'Critical'
  copy: string
}

export interface MonitoringForecastProjection {
  qualityScore: number
  riskBand: MonitoringRiskBand | 'Critical'
  reviewWindowDays: number
  confidence: number
  driftRate: number
  recommendation: string
  alertSeverity: 'Low' | 'Medium' | 'High' | 'Critical'
  alertSummary: string
  driverSummary: string
  inheritanceNotes: string[]
  snapshotSummary: string
  trajectory: MonitoringForecastPoint[]
}

const TRAJECTORY_MARKERS = [
  { label: '0h', hours: 0 },
  { label: '24h', hours: 24 },
  { label: '72h', hours: 72 },
  { label: '7d', hours: 168 },
  { label: '14d', hours: 336 },
] as const

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

function round(value: number, digits = 2) {
  const factor = 10 ** digits
  return Math.round(value * factor) / factor
}

function getProfileBaseline(bag: MonitoringBagRecord) {
  const riskBase =
    bag.medicalProfile === 'Low risk'
      ? 0.81
      : bag.medicalProfile === 'Watch'
        ? 0.68
        : 0.56

  const statusOffset =
    bag.repositoryStatus === 'Fresh intake'
      ? 0.04
      : bag.repositoryStatus === 'Forecast review'
        ? -0.02
        : bag.repositoryStatus === 'Alert follow-up'
          ? -0.1
          : bag.repositoryStatus === 'Under review'
            ? -0.06
            : 0.03

  return clamp(riskBase + statusOffset, 0.42, 0.9)
}

function getRiskBandFromScore(score: number): MonitoringForecastProjection['riskBand'] {
  if (score >= 0.8) {
    return 'Low risk'
  }

  if (score >= 0.66) {
    return 'Watch'
  }

  if (score >= 0.5) {
    return 'Elevated'
  }

  return 'Critical'
}

function getAlertSeverityFromRisk(riskBand: MonitoringForecastProjection['riskBand']) {
  switch (riskBand) {
    case 'Low risk':
      return 'Low' as const
    case 'Watch':
      return 'Medium' as const
    case 'Elevated':
      return 'High' as const
    case 'Critical':
      return 'Critical' as const
    default:
      return 'Medium' as const
  }
}

function getRecommendation(riskBand: MonitoringForecastProjection['riskBand']) {
  switch (riskBand) {
    case 'Low risk':
      return 'Continue routine monitoring and keep the bag in the standard review cadence.'
    case 'Watch':
      return 'Repeat the biomarker panel within 72 hours and keep the bag in a watch window.'
    case 'Elevated':
      return 'Escalate review, prepare an alert, and consider a tighter storage follow-up.'
    case 'Critical':
      return 'Trigger immediate review and open an alert for intervention.'
    default:
      return 'Keep the bag under observation until the next monitoring readout.'
  }
}

function getDriverSummary(input: MonitoringForecastInput) {
  const pressures = [
    {
      label: 'lactate',
      weight: Math.max(input.lactate - 7.2, 0) * 0.08,
    },
    {
      label: 'glucose',
      weight: Math.max(4.8 - input.glucose, 0) * 0.11,
    },
    {
      label: 'glutathione',
      weight: Math.max(1.8 - input.glutathione, 0) * 0.14,
    },
    {
      label: 'alanine',
      weight: Math.max(input.alanine - 1.1, 0) * 0.04,
    },
  ]

  const sorted = pressures.sort((left, right) => right.weight - left.weight)
  const first = sorted[0]
  const second = sorted[1]

  if (!first || first.weight <= 0) {
    return 'Biomarker panel currently supports a stable quality outlook.'
  }

  if (!second || second.weight <= 0) {
    return `Primary pressure comes from ${first.label}.`
  }

  return `Primary pressure comes from ${first.label}, with ${second.label} trailing behind.`
}

function buildTrajectory(
  currentScore: number,
  driftRate: number,
  input: MonitoringForecastInput
): MonitoringForecastPoint[] {
  return TRAJECTORY_MARKERS.map((marker, index) => {
    const horizonFactor = index === 0 ? 0 : marker.hours / 168
    const biomarkerPressure =
      Math.max(input.lactate - 7.2, 0) * 0.01 +
      Math.max(4.8 - input.glucose, 0) * 0.015 +
      Math.max(1.8 - input.glutathione, 0) * 0.012 +
      Math.max(input.alanine - 1.1, 0) * 0.004
    const score = clamp(currentScore - driftRate * horizonFactor - biomarkerPressure * horizonFactor * 0.6, 0.2, 0.96)
    const riskBand = getRiskBandFromScore(score)
    const copy =
      riskBand === 'Low risk'
        ? 'Stable window'
        : riskBand === 'Watch'
          ? 'Watch window'
          : riskBand === 'Elevated'
            ? 'Elevated watch'
            : 'Critical drift'

    return {
      label: marker.label,
      hours: marker.hours,
      qualityScore: round(score, 2),
      riskBand,
      copy,
    }
  })
}

export function buildMonitoringForecastProjection(
  bag: MonitoringBagRecord,
  input: MonitoringForecastInput,
  snapshot: ResearchSimulationSnapshot | null
): MonitoringForecastProjection {
  const baseline = getProfileBaseline(bag)
  const lactatePressure = Math.max(input.lactate - 7.2, 0) * 0.045
  const glucosePressure = Math.max(4.8 - input.glucose, 0) * 0.065
  const glutathionePressure = Math.max(1.8 - input.glutathione, 0) * 0.085
  const alaninePressure = Math.max(input.alanine - 1.1, 0) * 0.018
  const stress = clamp(lactatePressure + glucosePressure + glutathionePressure + alaninePressure, 0, 0.42)
  const confidence = clamp(
    0.78 +
      (snapshot ? 0.08 : -0.04) +
      (snapshot?.result.dataset_applied ? 0.02 : -0.03) +
      (bag.medicalProfile === 'Low risk' ? 0.04 : bag.medicalProfile === 'Watch' ? 0.01 : -0.02),
    0.55,
    0.96
  )
  const qualityScore = clamp(baseline - stress, 0.2, 0.96)
  const driftRate = clamp(0.018 + stress * 0.14 + (bag.repositoryStatus === 'Alert follow-up' ? 0.018 : 0), 0.012, 0.09)
  const riskBand = getRiskBandFromScore(qualityScore)
  const alertSeverity = getAlertSeverityFromRisk(riskBand)
  const trajectory = buildTrajectory(qualityScore, driftRate, input)

  const reviewWindowDays = clamp(Math.round((qualityScore - 0.52) / Math.max(driftRate, 0.01) + 2), 1, 14)

  const inheritanceNotes = [
    snapshot
      ? snapshot.result.dataset_applied
        ? `Latest simulation snapshot linked to ${snapshot.result.active_dataset_label ?? 'the active dataset'}.`
        : `Latest simulation snapshot uses ${snapshot.result.research_data_mode === 'custom_user_data_mode' ? 'custom user data' : 'Bordbar defaults'}.`
      : 'No simulation snapshot linked yet; this forecast uses Monitoring heuristics only.',
    'Selected Research inheritance: storage-window trend shaping and concentration-to-quality mapping.',
    'Excluded from this page: full metabolome controls, parameter calibration, and solver tuning.',
  ]

  const snapshotSummary = snapshot
    ? snapshot.result.dataset_applied
      ? `Simulation replay available from ${snapshot.result.active_dataset_label ?? 'the active dataset'} (${snapshot.result.n_points} sampled points).`
      : `Simulation replay available from ${snapshot.result.research_data_mode === 'custom_user_data_mode' ? 'custom user data' : 'Bordbar defaults'}.`
    : 'No active simulation snapshot is linked to this forecast.'

  return {
    qualityScore,
    riskBand,
    reviewWindowDays,
    confidence,
    driftRate,
    recommendation: getRecommendation(riskBand),
    alertSeverity,
    alertSummary:
      alertSeverity === 'Low'
        ? 'Routine monitoring only'
        : alertSeverity === 'Medium'
          ? 'Watch queue recommended'
          : alertSeverity === 'High'
            ? 'Prepare alert handoff'
            : 'Immediate alert required',
    driverSummary: getDriverSummary(input),
    inheritanceNotes,
    snapshotSummary,
    trajectory,
  }
}
