import type {
  CalibrationParameterEntry,
  CalibrationStrategyChoice,
  CalibrationTaxonomyResponse,
} from '@/types/calibration-taxonomy'

export interface CalibrationSelectionProvenance {
  selectedParameters: string[]
  selectedParameterFamilies: string[]
  selectedOptimizationStrategy: string
  strategyLabel: string
  strategyDescription: string
  isRecommendedSubset: boolean
  hasAdvancedSelection: boolean
  canonicalTaxonomySource: string
  canonicalTaxonomyVersion: string
}

export type CalibrationRunStatus = 'setup_only' | 'running' | 'completed' | 'failed'

export interface CalibrationParameterChange {
  param: string
  initial: number
  optimized: number
  change: number
  percentChange: number
}

export interface CalibrationFitMetrics {
  objectiveValue?: number
  baselineLoss?: number
  finalLoss?: number
  improvementPct?: number
  rSquared?: number
  iterations?: number
  runDurationSeconds?: number
  optimizer?: string
}

export interface CalibrationDatasetProvenance {
  researchDataMode?: string
  activeDatasetId?: string | null
  activeDatasetLabel?: string | null
  datasetSource?: 'bordbar_reference' | 'custom_upload'
  datasetApplied?: boolean
  defaultFallbackUsed?: boolean
  datasetFallbackReason?: string | null
  calibrationApplied?: boolean
  calibrationSource?: 'provided' | 'auto_loaded' | 'defaults'
  calibratedParametersActive?: boolean
  latestCalibrationLoaded?: boolean
}

export interface CalibrationResultProvenance {
  calibrationStatus: CalibrationRunStatus
  calibrationCompleted: boolean
  calibrationFailed: boolean
  strategyUsed?: string
  resultSummary?: string
  fitMetrics?: CalibrationFitMetrics
  parameterChanges?: CalibrationParameterChange[]
  initialVsFinalComparison?: CalibrationParameterChange[]
  runDurationSeconds?: number
  datasetProvenance?: CalibrationDatasetProvenance
}

const DEFAULT_TAXONOMY_SOURCE = 'MM_calibration'
const DEFAULT_TAXONOMY_VERSION = 'mm_calibration_v1'

function humanizeLabel(value: string) {
  return value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function normalizeName(value: string) {
  return value.trim().toLowerCase()
}

function buildEntryLookup(taxonomy?: CalibrationTaxonomyResponse | null) {
  const lookup = new Map<string, CalibrationParameterEntry>()
  for (const entry of taxonomy?.canonical?.vmax ?? []) {
    lookup.set(normalizeName(entry.name), entry)
  }
  for (const entry of taxonomy?.canonical?.km ?? []) {
    lookup.set(normalizeName(entry.name), entry)
  }
  return lookup
}

function sortFamilies(families: string[]) {
  const order = new Map([
    ['Vmax', 0],
    ['Km', 1],
  ])

  return [...new Set(families)].sort((left, right) => {
    const leftOrder = order.get(left) ?? 10
    const rightOrder = order.get(right) ?? 10
    return leftOrder - rightOrder || left.localeCompare(right)
  })
}

export function getCalibrationStrategyChoice(
  taxonomy?: CalibrationTaxonomyResponse | null,
  value?: string | null
): CalibrationStrategyChoice | null {
  if (!taxonomy || !value) {
    return null
  }

  return taxonomy.strategy_choices.find((choice) => choice.value === value) ?? null
}

export function getCalibrationSelectedParameterFamilies(
  selectedParameters: string[],
  taxonomy?: CalibrationTaxonomyResponse | null
) {
  const entryLookup = buildEntryLookup(taxonomy)
  const families: string[] = []

  for (const parameter of selectedParameters) {
    const normalized = normalizeName(parameter)
    const entry = entryLookup.get(normalized)

    if (normalized.startsWith('vmax_')) {
      families.push('Vmax')
      continue
    }

    if (normalized.startsWith('km_')) {
      families.push('Km')
      continue
    }

    const taxonomyClass = entry?.classes?.find((item) => item !== 'vmax' && item !== 'km')
    if (taxonomyClass) {
      families.push(humanizeLabel(taxonomyClass))
      continue
    }

    if (entry?.classes?.includes('vmax')) {
      families.push('Vmax')
      continue
    }

    if (entry?.classes?.includes('km')) {
      families.push('Km')
    }
  }

  return sortFamilies(families)
}

export function buildCalibrationSelectionProvenance(
  selectedParameters: string[],
  optimizationStrategy: string,
  taxonomy?: CalibrationTaxonomyResponse | null
): CalibrationSelectionProvenance {
  const strategyChoice = getCalibrationStrategyChoice(taxonomy, optimizationStrategy)
  const recommended = new Set([
    ...(taxonomy?.recommended?.vmax_params ?? []),
    ...(taxonomy?.recommended?.km_params ?? []),
  ].map((value) => normalizeName(value)))

  const normalizedSelections = selectedParameters.map((value) => normalizeName(value))
  const hasSelection = normalizedSelections.length > 0
  const isRecommendedSubset = hasSelection && normalizedSelections.every((value) => recommended.has(value))
  const hasAdvancedSelection = normalizedSelections.some((value) => !recommended.has(value))

  return {
    selectedParameters: [...selectedParameters],
    selectedParameterFamilies: getCalibrationSelectedParameterFamilies(selectedParameters, taxonomy),
    selectedOptimizationStrategy: optimizationStrategy,
    strategyLabel: strategyChoice?.label ?? humanizeLabel(optimizationStrategy),
    strategyDescription: strategyChoice?.description ?? '',
    isRecommendedSubset,
    hasAdvancedSelection,
    canonicalTaxonomySource: taxonomy?.source ?? DEFAULT_TAXONOMY_SOURCE,
    canonicalTaxonomyVersion: taxonomy?.taxonomy_version ?? DEFAULT_TAXONOMY_VERSION,
  }
}

export function getCalibrationSelectionModeLabel(
  provenance: Pick<CalibrationSelectionProvenance, 'isRecommendedSubset' | 'hasAdvancedSelection'>
) {
  if (provenance.isRecommendedSubset) {
    return 'Recommended subset'
  }

  if (provenance.hasAdvancedSelection) {
    return 'Advanced canonical inventory'
  }

  return 'Canonical selection'
}

export function getCalibrationSelectionSummary(
  provenance: CalibrationSelectionProvenance,
  resultAvailable: boolean
) {
  const familyLabel = provenance.selectedParameterFamilies.length
    ? provenance.selectedParameterFamilies.join(' and ')
    : 'canonical Vmax/Km parameters'
  const modeLabel = getCalibrationSelectionModeLabel(provenance)
  const resultLabel = resultAvailable ? 'result available' : 'setup only'

  return [
    provenance.canonicalTaxonomySource,
    provenance.canonicalTaxonomyVersion,
    familyLabel,
    provenance.strategyLabel,
    modeLabel,
    resultLabel,
  ]
    .filter(Boolean)
    .join(' • ')
}

export function buildCalibrationParameterChanges(
  optimizedParameters?: Record<string, number> | null,
  initialParameters?: Record<string, number> | null
) {
  if (!optimizedParameters || !initialParameters) {
    return []
  }

  const changes: CalibrationParameterChange[] = []

  for (const [param, optimized] of Object.entries(optimizedParameters)) {
    const initial = initialParameters[param]
    if (typeof optimized !== 'number' || typeof initial !== 'number' || initial === 0) {
      continue
    }

    const change = optimized - initial
    changes.push({
      param,
      initial,
      optimized,
      change,
      percentChange: (change / initial) * 100,
    })
  }

  return changes.sort((left, right) => Math.abs(right.percentChange) - Math.abs(left.percentChange))
}

export function buildCalibrationFitMetrics(options: {
  objectiveValue?: number | null
  baselineLoss?: number | null
  finalLoss?: number | null
  improvementPct?: number | null
  rSquared?: number | null
  iterations?: number | null
  runDurationSeconds?: number | null
  optimizer?: string | null
}): CalibrationFitMetrics | undefined {
  const fitMetrics: CalibrationFitMetrics = {}

  if (typeof options.objectiveValue === 'number') {
    fitMetrics.objectiveValue = options.objectiveValue
  }
  if (typeof options.baselineLoss === 'number') {
    fitMetrics.baselineLoss = options.baselineLoss
  }
  if (typeof options.finalLoss === 'number') {
    fitMetrics.finalLoss = options.finalLoss
  }
  if (typeof options.improvementPct === 'number') {
    fitMetrics.improvementPct = options.improvementPct
  }
  if (typeof options.rSquared === 'number') {
    fitMetrics.rSquared = options.rSquared
  }
  if (typeof options.iterations === 'number') {
    fitMetrics.iterations = options.iterations
  }
  if (typeof options.runDurationSeconds === 'number') {
    fitMetrics.runDurationSeconds = options.runDurationSeconds
  }
  if (typeof options.optimizer === 'string' && options.optimizer.trim()) {
    fitMetrics.optimizer = options.optimizer
  }

  return Object.keys(fitMetrics).length > 0 ? fitMetrics : undefined
}

export function getCalibrationRunStatusLabel(status?: CalibrationRunStatus | null) {
  switch (status) {
    case 'running':
      return 'Calibration running'
    case 'completed':
      return 'Calibration result ready'
    case 'failed':
      return 'Calibration failed'
    default:
      return 'Calibration setup ready'
  }
}

export function getCalibrationRunStatusLine(
  status?: CalibrationRunStatus | null,
  resultSummary?: string | null,
  fitMetrics?: CalibrationFitMetrics | null
) {
  if (status === 'running') {
    return 'Calibration is currently running.'
  }

  if (status === 'failed') {
    return 'Calibration failed before producing a completed result.'
  }

  if (status === 'completed') {
    if (resultSummary) {
      return resultSummary
    }

    const fragments: string[] = []
    if (typeof fitMetrics?.rSquared === 'number') {
      fragments.push(`R² ${fitMetrics.rSquared.toFixed(3)}`)
    }
    if (typeof fitMetrics?.improvementPct === 'number') {
      fragments.push(`${fitMetrics.improvementPct.toFixed(1)}% improvement`)
    }
    if (typeof fitMetrics?.finalLoss === 'number') {
      fragments.push(`final loss ${fitMetrics.finalLoss.toFixed(4)}`)
    }
    if (fragments.length > 0) {
      return `Calibration completed with ${fragments.join(' • ')}.`
    }
    return 'Calibration completed successfully.'
  }

  return 'Calibration setup is ready, but no result has been produced yet.'
}

export function buildCalibrationResultSummary(options: {
  status?: CalibrationRunStatus | null
  strategyLabel?: string | null
  datasetLabel?: string | null
  fitMetrics?: CalibrationFitMetrics | null
  parameterChanges?: CalibrationParameterChange[] | null
  failureDetail?: string | null
}): string | undefined {
  const status = options.status ?? 'setup_only'

  if (status === 'running') {
    return 'Calibration is currently running.'
  }

  if (status === 'failed') {
    return options.failureDetail
      ? `Calibration failed before a completed result was produced. Failure detail: ${options.failureDetail}`
      : 'Calibration failed before a completed result was produced.'
  }

  if (status !== 'completed') {
    return undefined
  }

  const fragments: string[] = []
  if (options.datasetLabel) {
    fragments.push(`dataset ${options.datasetLabel}`)
  }
  if (options.strategyLabel) {
    fragments.push(options.strategyLabel)
  }
  if (typeof options.fitMetrics?.rSquared === 'number') {
    fragments.push(`R² ${options.fitMetrics.rSquared.toFixed(3)}`)
  }
  if (typeof options.fitMetrics?.improvementPct === 'number') {
    fragments.push(`${options.fitMetrics.improvementPct.toFixed(1)}% improvement`)
  }

  const summaryPrefix = fragments.length > 0 ? `Completed on ${fragments.join(' • ')}` : 'Calibration completed'
  const topChange = options.parameterChanges?.[0]
  if (topChange) {
    return `${summaryPrefix}. Largest shift: ${topChange.param} ${topChange.percentChange >= 0 ? '+' : ''}${topChange.percentChange.toFixed(1)}%.`
  }

  return `${summaryPrefix}.`
}

export function buildCalibrationDatasetProvenance(options: CalibrationDatasetProvenance): CalibrationDatasetProvenance {
  return {
    researchDataMode: options.researchDataMode,
    activeDatasetId: options.activeDatasetId ?? null,
    activeDatasetLabel: options.activeDatasetLabel ?? null,
    datasetSource: options.datasetSource ?? (options.researchDataMode === 'custom_user_data_mode' ? 'custom_upload' : 'bordbar_reference'),
    datasetApplied: Boolean(options.datasetApplied),
    defaultFallbackUsed: Boolean(options.defaultFallbackUsed),
    datasetFallbackReason: options.datasetFallbackReason ?? null,
    calibrationApplied: Boolean(options.calibrationApplied),
    calibrationSource: options.calibrationSource ?? 'defaults',
    calibratedParametersActive: Boolean(options.calibratedParametersActive),
    latestCalibrationLoaded: Boolean(options.latestCalibrationLoaded),
  }
}
