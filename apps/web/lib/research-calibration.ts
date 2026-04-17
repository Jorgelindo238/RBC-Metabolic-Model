import type { ResearchDataMode, ResearchDatasetSummary } from '@/types/research-dataset'
import type { CalibrationTaxonomyResponse } from '@/types/calibration-taxonomy'
import {
  buildCalibrationFitMetrics,
  buildCalibrationParameterChanges,
  buildCalibrationResultSummary,
  buildCalibrationSelectionProvenance,
  type CalibrationDatasetProvenance,
  type CalibrationFitMetrics,
  type CalibrationParameterChange,
  type CalibrationRunStatus,
} from '@/lib/robocop/calibration-provenance'

export const RESEARCH_CALIBRATION_STORAGE_KEY = 'clawblood.research.activeCalibration'
export const RESEARCH_CALIBRATION_CHANGE_EVENT = 'clawblood:research-calibration-change'

export interface ActiveResearchCalibration {
  calibrationId: string
  datasetId: string
  datasetLabel: string
  datasetProvenance: CalibrationDatasetProvenance
  researchDataMode: ResearchDataMode
  selectedParameters: string[]
  selectedParameterFamilies?: string[]
  method: string
  selectedOptimizationStrategy?: string
  optimizationStrategy: string
  strategyLabel?: string
  strategyDescription?: string
  strategyUsed?: string
  isRecommendedSubset?: boolean
  hasAdvancedSelection?: boolean
  canonicalTaxonomySource?: string
  canonicalTaxonomyVersion?: string
  maxIterations: number
  targetMetabolites: string[]
  optimizedParams: Record<string, number>
  initialParams: Record<string, number>
  objectiveValue: number
  iterations: number
  rSquared: number
  baselineLoss?: number
  finalLoss?: number
  improvementPct?: number
  runDurationSeconds?: number
  calibrationStatus: CalibrationRunStatus
  calibrationCompleted: boolean
  calibrationFailed: boolean
  resultSummary?: string
  fitMetrics?: CalibrationFitMetrics
  parameterChanges?: CalibrationParameterChange[]
  initialVsFinalComparison?: CalibrationParameterChange[]
  activatedAt: string
}

export interface CalibrationResultShape {
  optimized_params: Record<string, number>
  initial_params: Record<string, number>
  objective_value: number
  iterations: number
  r_squared: number
  optimization_strategy?: string
  baseline_loss?: number
  final_loss?: number
  improvement_pct?: number
  run_duration_seconds?: number
  calibration_status?: CalibrationRunStatus
  calibration_completed?: boolean
  calibration_failed?: boolean
  result_summary?: string
  research_data_mode?: ResearchDataMode
  active_dataset_id?: string | null
  active_dataset_label?: string | null
}

export function readPersistedResearchCalibration(): ActiveResearchCalibration | null {
  if (typeof window === 'undefined') {
    return null
  }

  try {
    const raw =
      window.localStorage.getItem(RESEARCH_CALIBRATION_STORAGE_KEY) ??
      window.sessionStorage.getItem(RESEARCH_CALIBRATION_STORAGE_KEY)
    return raw ? (JSON.parse(raw) as ActiveResearchCalibration) : null
  } catch {
    window.localStorage.removeItem(RESEARCH_CALIBRATION_STORAGE_KEY)
    window.sessionStorage.removeItem(RESEARCH_CALIBRATION_STORAGE_KEY)
    return null
  }
}

export function persistResearchCalibration(calibration: ActiveResearchCalibration | null) {
  if (typeof window === 'undefined') {
    return
  }

  try {
    if (calibration) {
      const serialized = JSON.stringify(calibration)
      window.localStorage.setItem(RESEARCH_CALIBRATION_STORAGE_KEY, serialized)
      window.sessionStorage.setItem(RESEARCH_CALIBRATION_STORAGE_KEY, serialized)
    } else {
      window.localStorage.removeItem(RESEARCH_CALIBRATION_STORAGE_KEY)
      window.sessionStorage.removeItem(RESEARCH_CALIBRATION_STORAGE_KEY)
    }
  } catch {
    // Ignore storage quota or serialization errors and keep the in-memory state.
  }

  window.dispatchEvent(new Event(RESEARCH_CALIBRATION_CHANGE_EVENT))
}

export function subscribeToResearchCalibrationChanges(onStoreChange: () => void) {
  if (typeof window === 'undefined') {
    return () => {}
  }

  const handleChange = () => onStoreChange()

  window.addEventListener('storage', handleChange)
  window.addEventListener(RESEARCH_CALIBRATION_CHANGE_EVENT, handleChange)

  return () => {
    window.removeEventListener('storage', handleChange)
    window.removeEventListener(RESEARCH_CALIBRATION_CHANGE_EVENT, handleChange)
  }
}

export function buildActiveResearchCalibration(
  result: CalibrationResultShape,
  selectedParameters: string[],
  optimizationStrategy: string,
  maxIterations: number,
  targetMetabolites: string[],
  activeDataset: ResearchDatasetSummary | null,
  taxonomy?: CalibrationTaxonomyResponse | null
): ActiveResearchCalibration {
  const datasetId = result.active_dataset_id ?? activeDataset?.datasetId ?? 'bordbar-reference'
  const datasetLabel = result.active_dataset_label ?? activeDataset?.label ?? 'Bordbar reference dataset'
  const researchDataMode = result.research_data_mode ?? activeDataset?.mode ?? 'default_bordbar_mode'
  const provenance = buildCalibrationSelectionProvenance(selectedParameters, optimizationStrategy, taxonomy)
  const datasetProvenance: CalibrationDatasetProvenance = {
    researchDataMode,
    activeDatasetId: datasetId,
    activeDatasetLabel: datasetLabel,
    datasetSource: researchDataMode === 'custom_user_data_mode' ? 'custom_upload' : 'bordbar_reference',
    datasetApplied: researchDataMode === 'custom_user_data_mode',
    defaultFallbackUsed: researchDataMode !== 'custom_user_data_mode',
    datasetFallbackReason: null,
    calibrationApplied: true,
    calibrationSource: 'provided',
    calibratedParametersActive: true,
    latestCalibrationLoaded: true,
  }
  const parameterChanges = buildCalibrationParameterChanges(result.optimized_params, result.initial_params)
  const fitMetrics = buildCalibrationFitMetrics({
    objectiveValue: result.objective_value,
    baselineLoss: result.baseline_loss,
    finalLoss: result.final_loss ?? result.objective_value,
    improvementPct: result.improvement_pct,
    rSquared: result.r_squared,
    iterations: result.iterations,
    runDurationSeconds: result.run_duration_seconds,
    optimizer: result.optimization_strategy ?? optimizationStrategy,
  })
  const calibrationStatus: CalibrationRunStatus =
    result.calibration_status ??
    (result.calibration_completed ? 'completed' : result.calibration_failed ? 'failed' : 'completed')
  const calibrationCompleted = calibrationStatus === 'completed'
  const calibrationFailed = calibrationStatus === 'failed'
  const calibrationId =
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `${datasetId}-${Date.now()}`

  return {
    calibrationId,
    datasetId,
    datasetLabel,
    datasetProvenance,
    researchDataMode,
    selectedParameters: [...selectedParameters],
    selectedParameterFamilies: provenance.selectedParameterFamilies,
    method: optimizationStrategy,
    selectedOptimizationStrategy: optimizationStrategy,
    optimizationStrategy: result.optimization_strategy ?? optimizationStrategy,
    strategyUsed: result.optimization_strategy ?? optimizationStrategy,
    strategyLabel: provenance.strategyLabel,
    strategyDescription: provenance.strategyDescription,
    isRecommendedSubset: provenance.isRecommendedSubset,
    hasAdvancedSelection: provenance.hasAdvancedSelection,
    canonicalTaxonomySource: provenance.canonicalTaxonomySource,
    canonicalTaxonomyVersion: provenance.canonicalTaxonomyVersion,
    maxIterations,
    targetMetabolites: [...targetMetabolites],
    optimizedParams: { ...result.optimized_params },
    initialParams: { ...result.initial_params },
    objectiveValue: result.objective_value,
    iterations: result.iterations,
    rSquared: result.r_squared,
    baselineLoss: result.baseline_loss,
    finalLoss: result.final_loss ?? result.objective_value,
    improvementPct: result.improvement_pct,
    runDurationSeconds: result.run_duration_seconds,
    calibrationStatus,
    calibrationCompleted,
    calibrationFailed,
    resultSummary:
      buildCalibrationResultSummary({
        status: calibrationStatus,
        strategyLabel: provenance.strategyLabel,
        datasetLabel,
        fitMetrics,
        parameterChanges,
      }) ??
      result.result_summary,
    fitMetrics,
    parameterChanges,
    initialVsFinalComparison: parameterChanges,
    activatedAt: new Date().toISOString(),
  }
}
