import type { 
  ResearchContext,
  SimulationResearchContext,
  SimulationMetaboliteProfile,
  CalibrationResearchContext,
  FluxAnalysisSignal,
  CalibrationRegistryComparisonGroup,
  CalibrationRegistryLeadRecord,
  CalibrationRegistryResearchContext,
  FluxAnalysisResearchContext,
  PathwayPlaybackMetaboliteShift,
  PathwayPlaybackSignal,
  PathwayVisualizationSelection,
  SensitivityResearchContext,
  PathwayVisualizationResearchContext,
  DataUploadResearchContext
} from '@/types/research-context'
import type { ResearchDatasetSummary } from '@/types/research-dataset'
import type { CalibrationTaxonomyResponse } from '@/types/calibration-taxonomy'
import type { ResearchSimulationSnapshot } from '@/types/research-simulation'
import type { PathwayCompactOverviewItem } from '@/types/pathway-network'
import type { ActiveResearchCalibration } from '@/lib/research-calibration'
import type { SimulationResult, SimulationParams } from '@/hooks/use-simulation'
import { getSimulationKeyMetabolites } from './simulation-context'
import { PATHWAY_GROUPS } from '@/components/features/flux/FluxBarChart'
import {
  buildCalibrationDatasetProvenance,
  buildCalibrationFitMetrics,
  buildCalibrationParameterChanges,
  buildCalibrationResultSummary,
  buildCalibrationSelectionProvenance,
  type CalibrationRunStatus,
} from './calibration-provenance'

// Simulation context builder (reusing existing logic)
export function buildSimulationResearchContext(
  result: SimulationResult,
  params: SimulationParams,
  selectedMetabolites?: string[],
  activeDataset?: ResearchDatasetSummary,
  activeCalibration?: ActiveResearchCalibration | null
): SimulationResearchContext {
  const tStart = result.t[0]
  const tEnd = result.t[result.t.length - 1]
  const resolvedCalibrationSource = result.custom_params_source ?? (activeCalibration ? 'auto_loaded' : 'defaults')
  
  const metaboliteProfiles = buildMetaboliteProfiles(result)
  const notableTrends = analyzeTrends(result)
  const finalValues = Object.fromEntries(
    metaboliteProfiles.map((profile) => [profile.metabolite, profile.final])
  )
  const selectedTrajectories = selectedMetabolites && selectedMetabolites.length > 0 
    ? Object.fromEntries(selectedMetabolites.map(m => {
        const idx = result.metabolite_names.indexOf(m)
        return idx !== -1 ? [m, result.t.map((_, i) => result.x[i][idx])] : [m, []]
      }))
    : undefined
  
  return {
    moduleType: 'simulation',
    moduleTitle: 'Simulation',
    timestamp: new Date().toISOString(),
    success: result.success,
    researchDataMode: result.research_data_mode ?? activeDataset?.mode ?? 'default_bordbar_mode',
    activeDataset,
    activeDatasetId: activeDataset?.datasetId ?? result.active_dataset_id ?? null,
    activeDatasetLabel: activeDataset?.label ?? result.active_dataset_label ?? null,
    datasetSource: activeDataset?.source ?? (result.research_data_mode === 'custom_user_data_mode' ? 'custom_upload' : 'bordbar_reference'),
    datasetApplied: result.dataset_applied ?? false,
    defaultFallbackUsed: !(result.dataset_applied ?? false) || (result.research_data_mode ?? activeDataset?.mode) !== 'custom_user_data_mode',
    datasetFallbackReason: result.dataset_fallback_reason ?? null,
    datasetAppliedMetabolites: result.dataset_applied_metabolites ?? [],
    calibrationApplied: resolvedCalibrationSource !== 'defaults',
    calibrationSource: resolvedCalibrationSource,
    calibratedParametersActive: resolvedCalibrationSource !== 'defaults',
    latestCalibrationLoaded: resolvedCalibrationSource !== 'defaults',
    customParamsSource: resolvedCalibrationSource,
    parameters: {
      t_max: params.t_max,
      curve_fit_strength: params.curve_fit_strength,
      solver_method: params.solver_method,
      ph_perturbation_type: params.ph_perturbation_type,
      ph_severity: params.ph_severity,
      ph_duration: params.ph_duration,
    },
    outputs: {
      timeRange: {
        start: tStart,
        end: tEnd,
        n_points: result.n_points,
      },
      metabolites: {
        total: result.n_metabolites,
        names: result.metabolite_names,
        keyMetabolites: getSimulationKeyMetabolites(result.metabolite_names),
        finalValues,
        profiles: metaboliteProfiles,
      },
      trajectories: selectedTrajectories,
    },
    summary: {
      duration: result.duration,
      solver: result.solver,
      notableTrends,
    },
    selectedMetabolites: selectedMetabolites && selectedMetabolites.length > 0 ? selectedMetabolites : undefined,
  }
}

function buildMetaboliteProfiles(result: SimulationResult): SimulationMetaboliteProfile[] {
  if (!result.success || result.t.length === 0) {
    return []
  }

  return result.metabolite_names.map((metabolite, idx) => {
    const series = result.x.map((row) => row[idx])
    const initial = series[0] ?? 0
    const final = series[series.length - 1] ?? initial
    const minimum = series.length > 0 ? Math.min(...series) : initial
    const maximum = series.length > 0 ? Math.max(...series) : final
    const delta = final - initial
    const percentChange = initial !== 0 ? (delta / initial) * 100 : 0

    let direction: SimulationMetaboliteProfile['direction']
    let magnitude: SimulationMetaboliteProfile['magnitude']

    if (Math.abs(percentChange) < 5) {
      direction = 'stable'
    } else if (delta > 0) {
      direction = 'increasing'
    } else {
      direction = 'decreasing'
    }

    if (Math.abs(percentChange) > 50) {
      magnitude = 'high'
    } else if (Math.abs(percentChange) > 20) {
      magnitude = 'medium'
    } else {
      magnitude = 'low'
    }

    return {
      metabolite,
      initial,
      final,
      minimum,
      maximum,
      delta,
      percentChange,
      direction,
      magnitude,
    }
  })
}

// Calibration context builder
interface CalibrationResult {
  success: boolean
  message: string
  optimized_params: Record<string, number>
  initial_params: Record<string, number>
  objective_value: number
  iterations: number
  r_squared: number
  confidence_intervals: Record<string, [number, number]>
  sensitivity: Record<string, number>
  research_data_mode?: 'default_bordbar_mode' | 'custom_user_data_mode'
  active_dataset_id?: string | null
  active_dataset_label?: string | null
  dataset_applied?: boolean
  dataset_fallback_reason?: string | null
  dataset_applied_metabolites?: string[]
  calibrationResultAvailable?: boolean
  optimization_strategy?: string
  baseline_loss?: number
  final_loss?: number
  improvement_pct?: number
  run_duration_seconds?: number
  calibration_status?: CalibrationRunStatus
  calibration_completed?: boolean
  calibration_failed?: boolean
  result_summary?: string
}

export function buildCalibrationResearchContext(
  result: CalibrationResult | null,
  selectedParams: string[],
  optimizationStrategy: string,
  maxIter: number,
  targetMets: string[],
  activeDataset?: ResearchDatasetSummary,
  taxonomy?: CalibrationTaxonomyResponse | null,
  activeCalibration?: ActiveResearchCalibration | null,
  calibrationStatus?: CalibrationRunStatus,
  calibrationError?: string | null
): CalibrationResearchContext {
  const resolvedSelectedParams =
    selectedParams.length > 0 ? selectedParams : activeCalibration?.selectedParameters ?? selectedParams
  const resolvedOptimizationStrategy =
    optimizationStrategy || activeCalibration?.selectedOptimizationStrategy || activeCalibration?.optimizationStrategy || optimizationStrategy
  const provenance = buildCalibrationSelectionProvenance(resolvedSelectedParams, resolvedOptimizationStrategy, taxonomy)
  const resolvedResult: CalibrationResult | null =
    result ??
    (activeCalibration
      ? {
          success: true,
          message: 'Loaded saved calibration result',
          optimized_params: { ...activeCalibration.optimizedParams },
          initial_params: { ...activeCalibration.initialParams },
          objective_value: activeCalibration.objectiveValue,
          iterations: activeCalibration.iterations,
          r_squared: activeCalibration.rSquared,
          confidence_intervals: {},
          sensitivity: {},
          optimization_strategy: activeCalibration.optimizationStrategy ?? resolvedOptimizationStrategy,
          research_data_mode: activeCalibration.researchDataMode,
          active_dataset_id: activeCalibration.datasetId,
          active_dataset_label: activeCalibration.datasetLabel,
          dataset_applied: activeCalibration.researchDataMode === 'custom_user_data_mode',
          dataset_fallback_reason: null,
          dataset_applied_metabolites: [],
          baseline_loss: activeCalibration.baselineLoss,
          final_loss: activeCalibration.finalLoss,
          improvement_pct: activeCalibration.improvementPct,
          run_duration_seconds: activeCalibration.runDurationSeconds,
          calibration_status: activeCalibration.calibrationStatus,
          calibration_completed: activeCalibration.calibrationCompleted,
          calibration_failed: activeCalibration.calibrationFailed,
          result_summary: activeCalibration.resultSummary,
        }
      : null)
  const resolvedCalibrationStatus: CalibrationRunStatus =
    calibrationStatus ??
    resolvedResult?.calibration_status ??
    activeCalibration?.calibrationStatus ??
    (calibrationError ? 'failed' : result || activeCalibration?.calibrationCompleted ? 'completed' : 'setup_only')
  const calibrationApplied = resolvedCalibrationStatus === 'completed' || Boolean(activeCalibration?.calibrationCompleted)
  const calibrationSource = result ? 'provided' : activeCalibration ? 'auto_loaded' : 'defaults'
  const resolvedTargetMetabolites = result ? targetMets : activeCalibration?.targetMetabolites ?? targetMets
  const parameterChanges =
    resolvedResult && resolvedCalibrationStatus === 'completed'
      ? buildCalibrationParameterChanges(resolvedResult.optimized_params, resolvedResult.initial_params)
      : activeCalibration?.parameterChanges ?? []
  const fitMetrics =
    resolvedResult && resolvedCalibrationStatus === 'completed'
      ? buildCalibrationFitMetrics({
          objectiveValue: resolvedResult.objective_value,
          baselineLoss: resolvedResult.baseline_loss,
          finalLoss: resolvedResult.final_loss ?? resolvedResult.objective_value,
          improvementPct: resolvedResult.improvement_pct,
          rSquared: resolvedResult.r_squared,
          iterations: resolvedResult.iterations,
          runDurationSeconds: resolvedResult.run_duration_seconds,
          optimizer: resolvedResult.optimization_strategy ?? resolvedOptimizationStrategy,
        })
      : activeCalibration?.fitMetrics
  const resultSummary =
    activeCalibration?.resultSummary ??
    buildCalibrationResultSummary({
      status: resolvedCalibrationStatus,
      strategyLabel: provenance.strategyLabel,
      datasetLabel: activeDataset?.label ?? activeCalibration?.datasetLabel ?? null,
      fitMetrics,
      parameterChanges,
      failureDetail: calibrationError,
    }) ??
    resolvedResult?.result_summary
  const datasetProvenance = buildCalibrationDatasetProvenance({
    researchDataMode: resolvedResult?.research_data_mode ?? activeDataset?.mode ?? 'default_bordbar_mode',
    activeDatasetId: activeDataset?.datasetId ?? resolvedResult?.active_dataset_id ?? null,
    activeDatasetLabel: activeDataset?.label ?? resolvedResult?.active_dataset_label ?? null,
    datasetSource:
      activeDataset?.source ??
      (resolvedResult?.research_data_mode === 'custom_user_data_mode' ? 'custom_upload' : 'bordbar_reference'),
    datasetApplied: resolvedResult?.dataset_applied ?? Boolean(activeDataset),
    defaultFallbackUsed:
      !(resolvedResult?.dataset_applied ?? Boolean(activeDataset)) ||
      (resolvedResult?.research_data_mode ?? activeDataset?.mode) !== 'custom_user_data_mode',
    datasetFallbackReason: resolvedResult?.dataset_fallback_reason ?? null,
    calibrationApplied,
    calibrationSource,
    calibratedParametersActive: calibrationApplied,
    latestCalibrationLoaded: calibrationApplied,
  })
  const topChanges = parameterChanges.slice(0, 5).map((change) => ({
    param: change.param,
    change: change.change,
    percentChange: change.percentChange,
  }))

  return {
    moduleType: 'calibration',
    moduleTitle: 'Parameter Calibration',
    timestamp: new Date().toISOString(),
    success: resolvedResult?.success ?? false,
    calibrationResultAvailable: Boolean(resolvedResult),
    researchDataMode: resolvedResult?.research_data_mode ?? activeDataset?.mode ?? 'default_bordbar_mode',
    activeDataset,
    activeDatasetId: activeDataset?.datasetId ?? resolvedResult?.active_dataset_id ?? null,
    activeDatasetLabel: activeDataset?.label ?? resolvedResult?.active_dataset_label ?? null,
    datasetSource: activeDataset?.source ?? (resolvedResult?.research_data_mode === 'custom_user_data_mode' ? 'custom_upload' : 'bordbar_reference'),
    datasetApplied:
      resolvedResult?.dataset_applied ?? activeDataset?.mode === 'custom_user_data_mode',
    defaultFallbackUsed:
      !(resolvedResult?.dataset_applied ?? activeDataset?.mode === 'custom_user_data_mode') ||
      (resolvedResult?.research_data_mode ?? activeDataset?.mode) !== 'custom_user_data_mode',
    datasetFallbackReason: resolvedResult?.dataset_fallback_reason ?? null,
    datasetAppliedMetabolites: resolvedResult?.dataset_applied_metabolites ?? [],
    calibrationApplied,
    calibrationSource,
    calibratedParametersActive: calibrationApplied,
    latestCalibrationLoaded: calibrationApplied,
    customParamsSource: calibrationSource,
    datasetProvenance,
    calibrationStatus: resolvedCalibrationStatus,
    calibrationCompleted: resolvedCalibrationStatus === 'completed',
    calibrationFailed: resolvedCalibrationStatus === 'failed',
    calibrationError,
    resultSummary,
    runDurationSeconds: fitMetrics?.runDurationSeconds ?? activeCalibration?.runDurationSeconds,
    fitMetrics,
    parameterChanges,
    initialVsFinalComparison: parameterChanges,
    strategyUsed: resolvedResult?.optimization_strategy ?? activeCalibration?.strategyUsed ?? resolvedOptimizationStrategy,
    inputs: {
      selectedParameters: resolvedSelectedParams,
      selectedParameterFamilies: provenance.selectedParameterFamilies,
      selectedOptimizationStrategy: provenance.selectedOptimizationStrategy,
      optimizationStrategy: resolvedOptimizationStrategy,
      strategyLabel: provenance.strategyLabel,
      strategyDescription: provenance.strategyDescription,
      isRecommendedSubset: provenance.isRecommendedSubset,
      hasAdvancedSelection: provenance.hasAdvancedSelection,
      canonicalTaxonomySource: provenance.canonicalTaxonomySource,
      canonicalTaxonomyVersion: provenance.canonicalTaxonomyVersion,
      method: resolvedOptimizationStrategy,
      maxIterations: maxIter,
      targetMetabolites: resolvedTargetMetabolites,
    },
    outputs: {
      optimizedParameters: resolvedResult?.optimized_params ?? {},
      initialParameters: resolvedResult?.initial_params ?? {},
      objectiveValue: resolvedResult?.objective_value ?? 0,
      iterations: resolvedResult?.iterations ?? 0,
      rSquared: resolvedResult?.r_squared ?? 0,
      confidenceIntervals: resolvedResult?.confidence_intervals ?? {},
      sensitivity: resolvedResult?.sensitivity ?? {},
    },
    summary: {
      convergence: resolvedCalibrationStatus === 'completed',
      improvement: fitMetrics?.improvementPct ?? 0,
      topChanges,
    },
  }
}

function normalizeRegistryStatus(value: unknown) {
  if (typeof value !== 'string' || !value.trim()) {
    return 'unknown'
  }

  return value.trim().toLowerCase().replace(/\s+/g, '_')
}

function formatRegistryPercent(value: unknown) {
  if (value === null || value === undefined || value === '') {
    return null
  }

  const numericValue = Number(value)
  if (Number.isNaN(numericValue)) {
    return null
  }

  return `${numericValue >= 0 ? '+' : ''}${numericValue.toFixed(1)}%`
}

function groupCalibrationRegistryRuns(runs: any[]): CalibrationRegistryComparisonGroup[] {
  const grouped = new Map<string, {
    label: string
    runs: any[]
  }>()
  const preferredOrder = ['baseline', 'keep', 'discard', 'partial', 'timed_out', 'crashed', 'not_comparable', 'unknown']

  for (const run of runs) {
    const key = normalizeRegistryStatus(run?.benchmarkStatus ?? run?.status)
    const groupKey = preferredOrder.includes(key) ? key : 'unknown'
    const label = groupKey === 'unknown'
      ? 'Unknown'
      : groupKey.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())

    if (!grouped.has(groupKey)) {
      grouped.set(groupKey, { label, runs: [] })
    }

    grouped.get(groupKey)!.runs.push(run)
  }

  return preferredOrder
    .map((key) => {
      const group = grouped.get(key)
      if (!group) {
        return null
      }

      const scores = group.runs
        .map((run) => Number(run?.aggregateScore))
        .filter((value) => !Number.isNaN(value))
      const meanFinalLosses = group.runs
        .map((run) => Number(run?.meanFinalLoss))
        .filter((value) => !Number.isNaN(value))
      const meanImprovements = group.runs
        .map((run) => Number(run?.meanImprovementPct))
        .filter((value) => !Number.isNaN(value))
      const bestScore = scores.length > 0 ? Math.min(...scores) : null
      const meanFinalLoss = meanFinalLosses.length > 0 ? meanFinalLosses.reduce((sum, value) => sum + value, 0) / meanFinalLosses.length : null
      const meanImprovementPct = meanImprovements.length > 0 ? meanImprovements.reduce((sum, value) => sum + value, 0) / meanImprovements.length : null
      const completedCount = group.runs.filter((run) => normalizeRegistryStatus(run?.completionStatus) === 'completed').length

      const summaryParts = [`${group.runs.length} runs`]
      if (bestScore !== null) {
        summaryParts.push(`best score ${bestScore.toFixed(3)}`)
      }
      if (meanFinalLoss !== null) {
        summaryParts.push(`mean loss ${meanFinalLoss.toFixed(3)}`)
      }
      if (meanImprovementPct !== null) {
        summaryParts.push(`mean improvement ${formatRegistryPercent(meanImprovementPct)}`)
      }

      return {
        key,
        label: group.label,
        count: group.runs.length,
        completedCount,
        bestScore,
        meanFinalLoss,
        meanImprovementPct,
        summaryLine: summaryParts.join(' • '),
      }
    })
    .filter(Boolean) as CalibrationRegistryComparisonGroup[]
}

function buildCalibrationRegistryResultSummary(options: {
  status: string
  strategyLabel: string
  aggregateScore: number | null
  meanFinalLoss: number | null
  meanImprovementPct: number | null
  timeAwareScore: number | null
  benchmarkStatus: string
}) {
  const fragments: string[] = []
  fragments.push(`${options.benchmarkStatus} ledger`)
  fragments.push(options.strategyLabel)
  if (options.aggregateScore !== null) {
    fragments.push(`score ${options.aggregateScore.toFixed(3)}`)
  }
  if (options.meanFinalLoss !== null) {
    fragments.push(`mean loss ${options.meanFinalLoss.toFixed(3)}`)
  }
  if (options.meanImprovementPct !== null) {
    fragments.push(`${options.meanImprovementPct.toFixed(1)}% improvement`)
  }
  if (options.timeAwareScore !== null) {
    fragments.push(`time-aware ${options.timeAwareScore.toFixed(3)}`)
  }

  const statusPrefix = options.status === 'completed'
    ? 'Completed benchmark result'
    : options.status === 'failed'
      ? 'Historical benchmark failed'
      : options.status === 'running'
        ? 'Historical benchmark still running'
        : 'Historical benchmark record'

  return `${statusPrefix} • ${fragments.filter(Boolean).join(' • ')}`
}

export function buildCalibrationRegistryResearchContext(
  detail: any,
  runs: any[]
): CalibrationRegistryResearchContext {
  const summary = detail?.summary ?? {}
  const scientificContext = detail?.scientificContext ?? {}
  const benchmarkStatus = normalizeRegistryStatus(summary.benchmarkStatus ?? summary.status)
  const completionStatus = normalizeRegistryStatus(summary.completionStatus ?? summary.status)
  const strategyValue = scientificContext.optimizationStrategy ?? 'unknown'
  const selectionProvenance = buildCalibrationSelectionProvenance([], strategyValue, null)
  const registryComparisonGroups = groupCalibrationRegistryRuns(runs)
  const leadRecord: CalibrationRegistryLeadRecord | null = detail
    ? {
        runId: summary.runId ?? null,
        label: summary.label ?? null,
        benchmarkStatus: summary.benchmarkStatus ?? summary.status ?? null,
        completionStatus: summary.completionStatus ?? null,
        optimizationStrategy: scientificContext.optimizationStrategy ?? null,
        targetScope: scientificContext.targetScope ?? null,
        paramScope: scientificContext.paramScope ?? null,
        aggregateScore: typeof summary.aggregateScore === 'number' ? summary.aggregateScore : null,
        meanFinalLoss: typeof summary.meanFinalLoss === 'number' ? summary.meanFinalLoss : null,
        meanImprovementPct: typeof summary.meanImprovementPct === 'number' ? summary.meanImprovementPct : null,
        timeAwareScore: typeof summary.timeAwareScore === 'number' ? summary.timeAwareScore : null,
        elapsedSeconds: typeof summary.elapsedSeconds === 'number' ? summary.elapsedSeconds : null,
        caseCount: typeof summary.caseCount === 'number' ? summary.caseCount : null,
      }
    : null

  const registryResultSummary = detail
    ? buildCalibrationRegistryResultSummary({
        status: completionStatus,
        strategyLabel: selectionProvenance.strategyLabel,
        aggregateScore: typeof summary.aggregateScore === 'number' ? summary.aggregateScore : null,
        meanFinalLoss: typeof summary.meanFinalLoss === 'number' ? summary.meanFinalLoss : null,
        meanImprovementPct: typeof summary.meanImprovementPct === 'number' ? summary.meanImprovementPct : null,
        timeAwareScore: typeof summary.timeAwareScore === 'number' ? summary.timeAwareScore : null,
        benchmarkStatus,
      })
    : undefined

  return {
    moduleType: 'calibration-registry',
    moduleTitle: 'Calibration Registry',
    timestamp: new Date().toISOString(),
    success: Boolean(detail),
    researchDataMode: 'default_bordbar_mode',
    datasetSource: 'bordbar_reference',
    datasetApplied: false,
    defaultFallbackUsed: true,
    calibrationApplied: completionStatus === 'completed',
    calibrationSource: 'defaults',
    calibratedParametersActive: completionStatus === 'completed',
    latestCalibrationLoaded: completionStatus === 'completed',
    calibrationResultAvailable: Boolean(detail),
    calibrationStatus: completionStatus === 'completed' ? 'completed' : completionStatus === 'running' ? 'running' : completionStatus === 'failed' ? 'failed' : 'setup_only',
    calibrationCompleted: completionStatus === 'completed',
    calibrationFailed: completionStatus === 'failed',
    registryStatus: benchmarkStatus,
    registryCompleted: completionStatus === 'completed',
    registryFailed: completionStatus === 'failed',
    resultSummary: registryResultSummary,
    runDurationSeconds: typeof summary.elapsedSeconds === 'number' ? summary.elapsedSeconds : undefined,
    fitMetrics: {
      objectiveValue: typeof summary.aggregateScore === 'number' ? summary.aggregateScore : undefined,
      baselineLoss: typeof summary.meanFinalLoss === 'number' ? summary.meanFinalLoss : undefined,
      finalLoss: typeof summary.meanFinalLoss === 'number' ? summary.meanFinalLoss : undefined,
      improvementPct: typeof summary.meanImprovementPct === 'number' ? summary.meanImprovementPct : undefined,
      iterations: typeof summary.caseCount === 'number' ? summary.caseCount : undefined,
      runDurationSeconds: typeof summary.elapsedSeconds === 'number' ? summary.elapsedSeconds : undefined,
      optimizer: scientificContext.optimizationStrategy,
    },
    parameterChanges: [],
    initialVsFinalComparison: [],
    strategyUsed: scientificContext.optimizationStrategy ?? strategyValue,
    registryComparison: {
      visibleRuns: runs.length,
      groups: registryComparisonGroups,
      leadRecord,
      comparisonSummary: registryComparisonGroups.length
        ? registryComparisonGroups.map((group) => `${group.label}: ${group.summaryLine}`).join(' • ')
        : 'No comparable history available yet.',
    },
    inputs: {
      selectedOptimizationStrategy: strategyValue,
      strategyLabel: selectionProvenance.strategyLabel,
      strategyDescription: selectionProvenance.strategyDescription,
      canonicalTaxonomySource: selectionProvenance.canonicalTaxonomySource,
      canonicalTaxonomyVersion: selectionProvenance.canonicalTaxonomyVersion,
    },
    outputs: {
      aggregateScore: typeof summary.aggregateScore === 'number' ? summary.aggregateScore : null,
      meanFinalLoss: typeof summary.meanFinalLoss === 'number' ? summary.meanFinalLoss : null,
      meanImprovementPct: typeof summary.meanImprovementPct === 'number' ? summary.meanImprovementPct : null,
      timeAwareScore: typeof summary.timeAwareScore === 'number' ? summary.timeAwareScore : null,
      bestCase: summary.bestCase ?? null,
      worstCase: summary.worstCase ?? null,
      caseCount: typeof summary.caseCount === 'number' ? summary.caseCount : null,
      completedCases: typeof summary.completedCases === 'number' ? summary.completedCases : null,
      totalCases: typeof summary.totalCases === 'number' ? summary.totalCases : null,
      elapsedSeconds: typeof summary.elapsedSeconds === 'number' ? summary.elapsedSeconds : null,
    },
    summary: {
      benchmarkStatus,
      topComparisons: registryComparisonGroups.slice(0, 3).map((group) => group.summaryLine),
      comparisonLane: registryComparisonGroups[0]?.label ?? null,
    },
  }
}

// Flux Analysis context builder
type FluxAnalysisStatus = 'setup_only' | 'running' | 'completed' | 'failed'
type FluxConcentrationSource = 'bordbar_reference' | 'custom_upload'

interface FluxResult {
  fluxes?: Record<string, number> | null
}

interface FluxAnalysisOptions {
  selectedPathway?: string
  fluxStatus?: FluxAnalysisStatus
  fluxError?: string | null
  appliedConcentrationMetabolites?: string[]
  concentrationSource?: FluxConcentrationSource
  concentrationFallbackReason?: string | null
  calibrationApplied?: boolean
  calibrationSource?: 'provided' | 'auto_loaded' | 'defaults'
  latestSimulationSnapshot?: ResearchSimulationSnapshot | null
}

function buildFluxSignalList(
  entries: Array<[string, number]>,
  pathwayGroups: Record<string, string[]>
): FluxAnalysisSignal[] {
  return entries.map(([reaction, flux]) => ({
    reaction,
    flux,
    pathway:
      Object.entries(pathwayGroups).find(([, reactions]) => reactions.includes(reaction))?.[0] ?? 'other',
  }))
}

function buildFluxStatusLine(
  status: FluxAnalysisStatus,
  datasetLabel: string,
  selectedPathway: string,
  appliedCount: number,
  fallbackReason?: string | null,
  fluxError?: string | null
) {
  const pathwayLabel = selectedPathway && selectedPathway !== 'all' ? ` while viewing ${selectedPathway}` : ''

  if (status === 'completed') {
    return `${datasetLabel}${pathwayLabel} • ${appliedCount} concentration overrides applied`
  }

  if (status === 'running') {
    return `${datasetLabel}${pathwayLabel} • flux estimation is running`
  }

  if (status === 'failed') {
    return `Flux estimation failed${fluxError ? `: ${fluxError}` : ''}`
  }

  if (appliedCount > 0) {
    return `${datasetLabel}${pathwayLabel} • setup ready with ${appliedCount} concentration overrides`
  }

  return `Flux setup ready${fallbackReason ? ` • ${fallbackReason}` : ''}`
}

export function buildFluxAnalysisResearchContext(
  result: FluxResult | null,
  concentrations: Record<string, number>,
  activeDataset?: ResearchDatasetSummary,
  options: FluxAnalysisOptions = {}
): FluxAnalysisResearchContext {
  const pathwayGroups = PATHWAY_GROUPS
  const fluxes = result?.fluxes ?? {}
  const fluxStatus: FluxAnalysisStatus =
    options.fluxStatus ?? (Object.keys(fluxes).length > 0 ? 'completed' : 'setup_only')

  const pathwayFluxTotals = Object.entries(pathwayGroups).reduce((acc, [pathway, reactions]) => {
    const flux = reactions
      .map((reaction) => fluxes[reaction] ?? 0)
      .reduce((sum, value) => sum + Math.abs(value), 0)
    acc[pathway] = flux
    return acc
  }, {} as Record<string, number>)

  const dominantPathways = Object.entries(pathwayFluxTotals)
    .sort(([, a], [, b]) => b - a)
    .map(([pathway]) => pathway)

  const dominantPathway = dominantPathways[0] ?? 'unknown'

  const allFluxEntries = Object.entries(fluxes)
  const topFluxEntries = [...allFluxEntries].sort(([, left], [, right]) => Math.abs(right) - Math.abs(left)).slice(0, 5)
  const topPositiveEntries = [...allFluxEntries]
    .filter(([, flux]) => flux > 0)
    .sort(([, left], [, right]) => right - left)
    .slice(0, 3)
  const topNegativeEntries = [...allFluxEntries]
    .filter(([, flux]) => flux < 0)
    .sort(([, left], [, right]) => left - right)
    .slice(0, 3)

  const topFluxes = buildFluxSignalList(topFluxEntries, pathwayGroups)
  const topPositiveFluxes = buildFluxSignalList(topPositiveEntries, pathwayGroups)
  const topNegativeFluxes = buildFluxSignalList(topNegativeEntries, pathwayGroups)
  const totalFlux = allFluxEntries.reduce((sum, [, flux]) => sum + Math.abs(flux), 0)
  const appliedConcentrationMetabolites = options.appliedConcentrationMetabolites ?? []
  const concentrationSource = options.concentrationSource ?? 'bordbar_reference'
  const concentrationFallbackReason = options.concentrationFallbackReason ?? null
  const selectedPathway = options.selectedPathway ?? 'all'
  const calibrationApplied = options.calibrationApplied ?? false
  const calibrationSource = options.calibrationSource ?? (calibrationApplied ? 'auto_loaded' : 'defaults')
  const datasetApplied = activeDataset?.mode === 'custom_user_data_mode' && appliedConcentrationMetabolites.length > 0
  const datasetFallbackReason =
    activeDataset?.mode === 'custom_user_data_mode' && !datasetApplied
      ? concentrationFallbackReason ?? 'Custom data mode active but no flux-model concentrations were mapped'
      : concentrationFallbackReason
  const fluxResultAvailable = fluxStatus === 'completed'
  const playbackTimepoints = options.latestSimulationSnapshot?.result.t ?? []
  const playbackCurrentIndex = playbackTimepoints.length > 0 ? playbackTimepoints.length - 1 : null
  const playbackCurrentTime = playbackCurrentIndex !== null ? playbackTimepoints[playbackCurrentIndex] ?? null : null
  const playbackSourceLabel =
    options.latestSimulationSnapshot?.result.active_dataset_label ??
    activeDataset?.label ??
    null
  const playbackFluxes = options.latestSimulationSnapshot?.result.flux_data?.fluxes ?? null
  const playbackFluxAware = Boolean(playbackFluxes && Object.keys(playbackFluxes).length > 0)
  const playbackState = {
    topAccumulatingMetabolites: [] as PathwayPlaybackMetaboliteShift[],
    topDepletingMetabolites: [] as PathwayPlaybackMetaboliteShift[],
  }
  const dominantSignal = topFluxes[0]
    ? {
        label: topFluxes[0].reaction,
        value: topFluxes[0].flux,
        pathway: topFluxes[0].pathway,
      }
    : null
  const networkStateSummary = `${Object.keys(pathwayGroups).length} pathways • ${Object.keys(fluxes).length} reactions`
  const selectedTimepointSummary =
    playbackCurrentIndex !== null
      ? [
          `Frame ${playbackCurrentIndex + 1}/${playbackTimepoints.length}${playbackCurrentTime !== null ? ` at t=${playbackCurrentTime.toFixed(2)} days` : ''}`,
          dominantPathway ? `dominant pathway ${dominantPathway}` : null,
          dominantSignal ? `dominant signal ${dominantSignal.label} ${dominantSignal.value >= 0 ? '+' : ''}${dominantSignal.value.toExponential(2)}` : null,
        ]
          .filter(Boolean)
          .join(' • ')
      : null
  const resultSummary = buildFluxResultSummary({
    fluxStatus,
    datasetLabel: activeDataset?.label ?? 'Bordbar reference dataset',
    researchDataMode: activeDataset?.mode ?? 'default_bordbar_mode',
    selectedPathway,
    appliedCount: appliedConcentrationMetabolites.length,
    datasetApplied,
    datasetFallbackReason,
    calibrationApplied,
    calibrationSource,
    dominantPathway,
    topFluxes,
    totalFlux,
    fluxError: options.fluxError ?? null,
  })

  const keySignals: string[] = []
  keySignals.push(
    (activeDataset?.mode ?? 'default_bordbar_mode') === 'custom_user_data_mode'
      ? datasetApplied
        ? `Custom user data from ${activeDataset.label} is active`
        : `Custom user data mode active${datasetFallbackReason ? ` (${datasetFallbackReason})` : ''}`
      : 'Bordbar reference data is active'
  )
    keySignals.push(
      calibrationApplied
        ? calibrationSource === 'provided'
          ? 'Latest calibration parameters were applied'
          : calibrationSource === 'auto_loaded'
          ? 'Calibration parameters were auto-loaded'
          : 'Calibration parameters were active'
      : 'Default Bordbar parameters were retained'
  )
  if (selectedPathway && selectedPathway !== 'all') {
    keySignals.push(`Current filter: ${selectedPathway}`)
  }
  if (fluxResultAvailable) {
    keySignals.push(`Dominant pathway: ${dominantPathway}`)
    if (topFluxes[0]) {
      keySignals.push(`Top reaction: ${topFluxes[0].reaction} ${topFluxes[0].flux.toExponential(2)}`)
    }
    if (playbackCurrentIndex !== null && playbackCurrentTime !== null) {
      keySignals.push(`Playback frame ${playbackCurrentIndex + 1}/${playbackTimepoints.length} at t=${playbackCurrentTime.toFixed(2)} days`)
    }
    if (dominantSignal) {
      keySignals.push(
        `Dominant signal: ${dominantSignal.label} ${dominantSignal.value >= 0 ? '+' : ''}${dominantSignal.value.toExponential(2)}`
      )
    }
    if (playbackState.topAccumulatingMetabolites[0]) {
      const top = playbackState.topAccumulatingMetabolites[0]
      keySignals.push(`Accumulating: ${top.metabolite} ${top.delta >= 0 ? '+' : ''}${top.delta.toExponential(2)}`)
    }
    if (playbackState.topDepletingMetabolites[0]) {
      const top = playbackState.topDepletingMetabolites[0]
      keySignals.push(`Depleting: ${top.metabolite} ${top.delta.toExponential(2)}`)
    }
  } else if (fluxStatus === 'running') {
    keySignals.push('Flux estimation is running')
  } else if (fluxStatus === 'failed') {
    keySignals.push(`Flux estimation failed${options.fluxError ? `: ${options.fluxError}` : ''}`)
  } else {
    keySignals.push('Flux result not yet available')
  }

  return {
    moduleType: 'flux-analysis',
    moduleTitle: 'Flux Analysis',
    timestamp: new Date().toISOString(),
    success: fluxResultAvailable,
    researchDataMode: activeDataset?.mode ?? 'default_bordbar_mode',
    activeDataset,
    activeDatasetId: activeDataset?.datasetId ?? null,
    activeDatasetLabel: activeDataset?.label ?? null,
    datasetSource: concentrationSource,
    datasetApplied,
    defaultFallbackUsed: !datasetApplied,
    datasetFallbackReason,
    datasetAppliedMetabolites: appliedConcentrationMetabolites,
    calibrationApplied,
    calibrationSource,
    calibratedParametersActive: calibrationApplied,
    latestCalibrationLoaded: calibrationApplied,
    playbackReady: playbackCurrentIndex !== null,
    playbackFrameIndex: playbackCurrentIndex,
    playbackFrameCount: playbackTimepoints.length,
    playbackTimepoint: playbackCurrentTime,
    networkStateSummary,
    dominantPathway,
    dominantSignal,
    topAccumulatingMetabolites: playbackState.topAccumulatingMetabolites,
    topDepletingMetabolites: playbackState.topDepletingMetabolites,
    selectedTimepointSummary,
    replaySource: playbackSourceLabel,
    fluxStatus,
    fluxResultAvailable,
    fluxCompleted: fluxResultAvailable,
    fluxFailed: fluxStatus === 'failed',
    fluxError: options.fluxError ?? null,
    resultSummary,
    inputs: {
      concentrations,
      selectedPathway,
      concentrationSource,
      appliedConcentrationMetabolites,
      totalConcentrations: Object.keys(concentrations).length,
    },
    outputs: {
      fluxes,
      pathwayGroups,
      pathwayFluxTotals,
      totalFlux,
      topFluxes,
      topPositiveFluxes,
      topNegativeFluxes,
      dominantPathways,
    },
    summary: {
      dominantPathway,
      topReactions: topFluxes,
      fluxDistribution: pathwayFluxTotals,
      keySignals,
    },
  }
}

function buildFluxResultSummary(options: {
  fluxStatus: FluxAnalysisStatus
  datasetLabel: string
  researchDataMode: 'default_bordbar_mode' | 'custom_user_data_mode'
  selectedPathway: string
  appliedCount: number
  datasetApplied: boolean
  datasetFallbackReason?: string | null
  calibrationApplied: boolean
  calibrationSource: 'provided' | 'auto_loaded' | 'defaults'
  dominantPathway: string
  topFluxes: FluxAnalysisSignal[]
  totalFlux: number
  fluxError?: string | null
}) {
  const calibrationPart = options.calibrationApplied
    ? options.calibrationSource === 'provided'
      ? 'latest calibration applied'
      : options.calibrationSource === 'auto_loaded'
        ? 'calibration auto-loaded'
        : 'calibration active'
    : 'default Bordbar calibration'

  const pathwayPart = options.selectedPathway && options.selectedPathway !== 'all'
    ? `viewing ${options.selectedPathway}`
    : 'all pathways visible'

  const topSignal = options.topFluxes[0]
    ? `${options.topFluxes[0].reaction} ${options.topFluxes[0].flux.toExponential(2)}`
    : 'no dominant reaction yet'

  const datasetPart =
    options.researchDataMode === 'custom_user_data_mode'
      ? options.datasetApplied
        ? `custom user data from ${options.datasetLabel}`
        : `custom user data mode with Bordbar fallback${options.datasetFallbackReason ? ` (${options.datasetFallbackReason})` : ''}`
      : 'Bordbar reference data'

  if (options.fluxStatus === 'completed') {
    return `Flux analysis completed on ${datasetPart} with ${calibrationPart}; ${pathwayPart}; dominant pathway ${options.dominantPathway}; top signal ${topSignal}; total flux ${options.totalFlux.toExponential(2)}.`
  }

  if (options.fluxStatus === 'running') {
    return `Flux estimation is running on ${datasetPart} with ${calibrationPart}; ${pathwayPart}; ${options.appliedCount} concentration overrides queued.`
  }

  if (options.fluxStatus === 'failed') {
    return `Flux estimation failed on ${datasetPart} with ${calibrationPart}${options.fluxError ? `: ${options.fluxError}` : ''}`
  }

  return `Flux setup ready on ${datasetPart} with ${calibrationPart}; ${pathwayPart}; ${options.appliedCount} concentration overrides prepared.`
}

// Sensitivity Analysis context builder
interface SensitivityResult {
  metabolite_comparison: { Metabolite: string; Bordbar_Mean: number; Custom_Mean: number; RMSE: number; Percent_Change: number }[]
  top_sensitive_metabolites: { name: string; pct_change: number }[]
  validation_metrics: Record<string, { R2: number; RMSE: number; MAE: number; n_points: number }>
  simulation_summary: { success: boolean; n_metabolites: number; duration: number }
}

export function buildSensitivityResearchContext(
  result: SensitivityResult,
  tMax: number
): SensitivityResearchContext {
  const avgR2 = Object.values(result.validation_metrics)
    .reduce((sum, m) => sum + m.R2, 0) / Object.keys(result.validation_metrics).length

  const overallFit = avgR2 > 0.9 ? 'good' : avgR2 > 0.7 ? 'moderate' : 'poor'

  const mostDiscrepancies = result.metabolite_comparison
    .sort((a, b) => Math.abs(b.Percent_Change) - Math.abs(a.Percent_Change))
    .slice(0, 3)
    .map(m => m.Metabolite)

  const avgError = result.metabolite_comparison
    .reduce((sum, m) => sum + m.RMSE, 0) / result.metabolite_comparison.length

  return {
    moduleType: 'sensitivity-analysis',
    moduleTitle: 'Sensitivity Analysis',
    timestamp: new Date().toISOString(),
    success: result.simulation_summary.success,
    inputs: {
      t_max: tMax,
    },
    outputs: {
      metaboliteComparison: result.metabolite_comparison.map(m => ({
        metabolite: m.Metabolite,
        reference: m.Bordbar_Mean,
        custom: m.Custom_Mean,
        rmse: m.RMSE,
        percentChange: m.Percent_Change,
      })),
      topSensitiveMetabolites: result.top_sensitive_metabolites.map(m => ({
        name: m.name,
        percentChange: m.pct_change
      })),
      validationMetrics: result.validation_metrics,
    },
    summary: {
      overallFit,
      mostDiscrepancies,
      averageError: avgError,
    },
  }
}

// Pathway Visualization context builder
type PathwayVisualizationStatus = 'setup_only' | 'running' | 'completed' | 'failed'

interface PathwayNetworkNode {
  id: string
  label?: string
  pathway?: string
  x?: number
  y?: number
  concentration?: number
  compartment?: string
}

interface PathwayNetworkEdge {
  source: string
  target: string
  pathway?: string
  enzyme?: string
  reversible?: boolean
  color?: string
}

interface PathwayNetworkReactionNode {
  id: string
  label: string
  enzyme: string
  source: string
  target: string
  reversible: boolean
  pathway?: string
  x: number
  y: number
  size?: number
  color?: string
  flux?: number | null
}

interface PathwayNetworkData {
  nodes: PathwayNetworkNode[]
  edges: PathwayNetworkEdge[]
  reactionNodes?: PathwayNetworkReactionNode[]
  compactOverview?: PathwayCompactOverviewItem[]
}

interface PathwayVisualizationOptions {
  activeDataset?: ResearchDatasetSummary | null
  activeCalibration?: ActiveResearchCalibration | null
  pathwayStatus?: PathwayVisualizationStatus
  pathwayError?: string | null
  latestSimulationSnapshot?: ResearchSimulationSnapshot | null
  playbackIndex?: number
  selectedEntity?: PathwayVisualizationSelection | null
  pathwayViewMode?: 'compact' | 'full'
}

function formatReplayTimepoint(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return null
  }

  return Math.abs(value) >= 100 || Math.abs(value) < 0.01 ? value.toExponential(2) : value.toFixed(2)
}

function resolvePathwayReplayMetabolites(
  result: PathwayNetworkData | null,
  snapshot: ResearchSimulationSnapshot | null,
  playbackIndex: number | null
) {
  if (!snapshot || !snapshot.result.success || !snapshot.result.t.length || playbackIndex === null) {
    return {
      topAccumulatingMetabolites: [] as PathwayPlaybackMetaboliteShift[],
      topDepletingMetabolites: [] as PathwayPlaybackMetaboliteShift[],
    }
  }

  const currentIndex = Math.min(Math.max(playbackIndex, 0), snapshot.result.t.length - 1)
  const previousIndex = currentIndex > 0 ? currentIndex - 1 : currentIndex
  const currentRow = snapshot.result.x[currentIndex] ?? snapshot.result.x[snapshot.result.x.length - 1] ?? []
  const previousRow = snapshot.result.x[previousIndex] ?? currentRow
  const nodeIds = new Set(
    (result?.nodes ?? [])
      .flatMap((node) => [node.id, node.label].filter((value): value is string => typeof value === 'string' && value.length > 0))
  )
  const candidateNames = snapshot.result.metabolite_names.filter((name) => nodeIds.size === 0 || nodeIds.has(name))
  const sourceNames = candidateNames.length > 0 ? candidateNames : snapshot.result.metabolite_names

  const shifts = sourceNames
    .map((metabolite) => {
      const metaboliteIndex = snapshot.result.metabolite_names.indexOf(metabolite)
      if (metaboliteIndex === -1) {
        return null
      }

      const current = Number(currentRow[metaboliteIndex] ?? 0)
      const previous = Number(previousRow[metaboliteIndex] ?? current)
      const delta = current - previous
      const percentChange = previous !== 0 ? (delta / previous) * 100 : 0

      return {
        metabolite,
        concentration: current,
        delta,
        percentChange,
      } satisfies PathwayPlaybackMetaboliteShift
    })
    .filter((shift): shift is PathwayPlaybackMetaboliteShift => Boolean(shift))

  const topAccumulatingMetabolites = shifts
    .filter((shift) => shift.delta > 0)
    .sort((left, right) => right.delta - left.delta)
    .slice(0, 3)
  const topDepletingMetabolites = shifts
    .filter((shift) => shift.delta < 0)
    .sort((left, right) => left.delta - right.delta)
    .slice(0, 3)

  return { topAccumulatingMetabolites, topDepletingMetabolites }
}

function resolvePathwayDominantSignal(
  result: PathwayNetworkData | null,
  snapshot: ResearchSimulationSnapshot | null,
  playbackIndex: number | null,
  dominantPathway: string | null
): PathwayPlaybackSignal | null {
  if (!snapshot || !snapshot.result.success || !snapshot.result.flux_data?.fluxes || playbackIndex === null) {
    return null
  }

  const currentIndex = Math.min(Math.max(playbackIndex, 0), snapshot.result.t.length - 1)
  const currentFluxEntries = Object.entries(snapshot.result.flux_data.fluxes)
    .map(([reaction, series]) => {
      const value = series[currentIndex] ?? series[series.length - 1]
      return typeof value === 'number' ? { reaction, value } : null
    })
    .filter((entry): entry is { reaction: string; value: number } => Boolean(entry))

  if (currentFluxEntries.length === 0) {
    return null
  }

  const topFlux = currentFluxEntries.sort((left, right) => Math.abs(right.value) - Math.abs(left.value))[0]
  if (!topFlux) {
    return null
  }

  const matchingEdge = (result?.edges ?? []).find(
    (edge) => edge.enzyme === topFlux.reaction || edge.source === topFlux.reaction || edge.target === topFlux.reaction
  )

  return {
    label: topFlux.reaction,
    value: topFlux.value,
    pathway: matchingEdge?.pathway ?? dominantPathway ?? null,
    direction: topFlux.value >= 0 ? 'increasing' : 'decreasing',
  }
}

function formatPathwayReplayFlux(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return null
  }

  return `${value >= 0 ? '+' : ''}${value.toExponential(2)}`
}

function resolvePathwaySelection(
  result: PathwayNetworkData | null,
  selectedEntity: PathwayVisualizationSelection | null | undefined,
  snapshot: ResearchSimulationSnapshot | null,
  playbackIndex: number | null
) {
  if (!selectedEntity) {
    return {
      selectedEntity: null as PathwayVisualizationSelection | null,
      selectedEntitySummary: null as string | null,
    }
  }

  if (selectedEntity.kind === 'metabolite') {
    const node = result?.nodes.find((candidate) => candidate.id === selectedEntity.id)
    const concentration = typeof node?.concentration === 'number' ? node.concentration : null
    return {
      selectedEntity,
      selectedEntitySummary: [
        `Metabolite ${node?.label ?? selectedEntity.label}`,
        node?.pathway ?? selectedEntity.pathway ?? 'Other',
        concentration !== null ? `conc ${concentration.toFixed(3)} mM` : null,
        snapshot && playbackIndex !== null && snapshot.result.t.length > 0
          ? `frame ${Math.min(Math.max(playbackIndex, 0), snapshot.result.t.length - 1) + 1}/${snapshot.result.t.length}`
          : null,
      ]
        .filter(Boolean)
        .join(' • '),
    }
  }

  const reactionNode =
    result?.reactionNodes?.find((candidate) => candidate.id === selectedEntity.id) ??
    result?.reactionNodes?.find((candidate) => candidate.label === selectedEntity.label || candidate.enzyme === selectedEntity.label)
  const flux = formatPathwayReplayFlux(reactionNode?.flux ?? null)

  return {
    selectedEntity,
    selectedEntitySummary: [
      `Reaction ${reactionNode?.label ?? selectedEntity.label}`,
      reactionNode ? `${reactionNode.source} → ${reactionNode.target}` : null,
      reactionNode?.pathway ?? selectedEntity.pathway ?? 'Other',
      flux ? `flux ${flux}` : null,
      reactionNode?.reversible ? 'reversible' : null,
    ]
      .filter(Boolean)
      .join(' • '),
  }
}

function buildPathwayVisualizationResultSummary(options: {
  status: PathwayVisualizationStatus
  datasetLabel: string
  researchDataMode: 'default_bordbar_mode' | 'custom_user_data_mode'
  pathwayViewMode: 'compact' | 'full'
  networkNodes: number
  networkEdges: number
  reactionCount: number
  pathwayCount: number
  dominantPathway: string | null
  calibrationApplied: boolean
  calibrationSource: 'provided' | 'auto_loaded' | 'defaults'
  playbackAvailable: boolean
  playbackIndex: number | null
  playbackTotalFrames: number
  playbackTime: number | null
  playbackSourceLabel: string | null
  selectedEntitySummary?: string | null
  error?: string | null
}) {
  const datasetPart =
    options.researchDataMode === 'custom_user_data_mode'
      ? `custom user data context (${options.datasetLabel})`
      : 'Bordbar reference context'
  const calibrationPart = options.calibrationApplied
    ? options.calibrationSource === 'provided'
      ? 'latest calibration active'
      : options.calibrationSource === 'auto_loaded'
        ? 'auto-loaded calibration active'
        : 'calibration active'
    : 'default Bordbar calibration'
  const networkPart = `${options.networkNodes} metabolites • ${options.reactionCount} reactions • ${options.pathwayCount} pathways`
  const dominantPart = options.dominantPathway ? `Most represented pathway: ${options.dominantPathway}` : 'No dominant pathway yet'
  const viewModePart = options.pathwayViewMode === 'compact' ? 'Compact graph active' : 'Full model map active'
  const playbackPart =
    options.playbackAvailable && options.playbackIndex !== null
      ? `Playback frame ${options.playbackIndex + 1}/${options.playbackTotalFrames}${options.playbackTime !== null ? ` at t=${options.playbackTime.toFixed(2)} days` : ''}${options.playbackSourceLabel ? ` from ${options.playbackSourceLabel}` : ''}`
      : 'Static network snapshot'
  const selectionPart = options.selectedEntitySummary ? `Selected ${options.selectedEntitySummary}` : null

  if (options.status === 'completed') {
    return `Pathway network ready on ${datasetPart} with ${calibrationPart}; ${viewModePart}; ${playbackPart}; ${networkPart}; ${dominantPart}${selectionPart ? `; ${selectionPart}` : ''}.`
  }

  if (options.status === 'running') {
    return `Pathway network is loading on ${datasetPart} with ${calibrationPart}; ${viewModePart}; ${playbackPart}; ${networkPart}${selectionPart ? `; ${selectionPart}` : ''}.`
  }

  if (options.status === 'failed') {
    return `Pathway visualization failed on ${datasetPart} with ${calibrationPart}; ${viewModePart}${options.error ? `: ${options.error}` : ''}`
  }

  return `Pathway visualization is ready on ${datasetPart} with ${calibrationPart}; ${viewModePart}; ${playbackPart}; ${networkPart}${selectionPart ? `; ${selectionPart}` : ''}.`
}

export function buildPathwayVisualizationResearchContext(
  result: PathwayNetworkData | null,
  activeDataset?: ResearchDatasetSummary | null,
  activeCalibration?: ActiveResearchCalibration | null,
  options: PathwayVisualizationOptions = {}
): PathwayVisualizationResearchContext {
  const pathwayStatus: PathwayVisualizationStatus =
    options.pathwayStatus ?? (result?.nodes?.length ? 'completed' : 'setup_only')
  const pathwayViewMode: 'compact' | 'full' = options.pathwayViewMode ?? 'full'
  const uniquePathways = [...new Set((result?.nodes ?? []).map((node) => node.pathway).filter(Boolean))] as string[]
  const reactionCount = result?.reactionNodes?.length ?? result?.edges.length ?? 0
  const pathwayCounts = uniquePathways.map((pathway) => ({
    pathway,
    count: (result?.nodes ?? []).filter((node) => node.pathway === pathway).length,
  }))
  const dominantPathway = pathwayCounts.sort((left, right) => right.count - left.count)[0]?.pathway ?? null
  const calibrationApplied =
    Boolean(activeCalibration?.calibrationCompleted) &&
    (activeCalibration?.datasetId === activeDataset?.datasetId || !activeCalibration?.datasetId) &&
    (activeCalibration?.researchDataMode ?? activeDataset?.mode) === (activeDataset?.mode ?? 'default_bordbar_mode')
  const calibrationSource: 'provided' | 'auto_loaded' | 'defaults' = calibrationApplied
    ? activeCalibration?.researchDataMode === 'custom_user_data_mode'
      ? 'auto_loaded'
      : 'provided'
    : 'defaults'
  const playbackTimepoints = options.latestSimulationSnapshot?.result.t ?? []
  const playbackAvailable = Boolean(options.latestSimulationSnapshot?.result.success && playbackTimepoints.length > 0)
  const playbackCurrentIndex =
    playbackAvailable && playbackTimepoints.length > 0
      ? Math.min(Math.max(options.playbackIndex ?? playbackTimepoints.length - 1, 0), playbackTimepoints.length - 1)
      : null
  const playbackCurrentTime = playbackCurrentIndex !== null ? playbackTimepoints[playbackCurrentIndex] ?? null : null
  const playbackSourceLabel =
    options.latestSimulationSnapshot?.result.active_dataset_label ??
    activeDataset?.label ??
    null
  const playbackFluxes = options.latestSimulationSnapshot?.result.flux_data?.fluxes ?? null
  const playbackFluxAware = Boolean(playbackFluxes && Object.keys(playbackFluxes).length > 0)
  const playbackState = resolvePathwayReplayMetabolites(result, options.latestSimulationSnapshot ?? null, playbackCurrentIndex)
  const dominantSignal = resolvePathwayDominantSignal(result, options.latestSimulationSnapshot ?? null, playbackCurrentIndex, dominantPathway)
  const selectionState = resolvePathwaySelection(result, options.selectedEntity ?? null, options.latestSimulationSnapshot ?? null, playbackCurrentIndex)
  const networkStateSummary = `${result?.nodes.length ?? 0} metabolites • ${reactionCount} reactions • ${uniquePathways.length} pathways`
  const viewModeLabel = pathwayViewMode === 'compact' ? 'compact graph' : 'full model map'
  const playbackFrameText =
    playbackCurrentIndex !== null
      ? `Frame ${playbackCurrentIndex + 1}/${playbackTimepoints.length}${playbackCurrentTime !== null ? ` at t=${playbackCurrentTime.toFixed(2)} days` : ''}`
      : 'Static network snapshot'
  const selectedTimepointSummary =
    playbackCurrentIndex !== null
      ? [
          playbackFrameText,
          `view mode ${viewModeLabel}`,
          dominantPathway ? `dominant pathway ${dominantPathway}` : null,
          dominantSignal ? `dominant signal ${dominantSignal.label} ${dominantSignal.value >= 0 ? '+' : ''}${dominantSignal.value.toExponential(2)}` : null,
        ]
          .filter(Boolean)
          .join(' • ')
      : null
  const selectedEntitySummary = selectionState.selectedEntitySummary
  const resultSummary = buildPathwayVisualizationResultSummary({
    status: pathwayStatus,
    datasetLabel: activeDataset?.label ?? 'Bordbar reference dataset',
    researchDataMode: activeDataset?.mode ?? 'default_bordbar_mode',
    pathwayViewMode,
    networkNodes: result?.nodes.length ?? 0,
    networkEdges: result?.edges.length ?? 0,
    reactionCount,
    pathwayCount: uniquePathways.length,
    dominantPathway,
    calibrationApplied,
    calibrationSource,
    playbackAvailable,
    playbackIndex: playbackCurrentIndex,
    playbackTotalFrames: playbackTimepoints.length,
    playbackTime: playbackCurrentTime,
    playbackSourceLabel,
    selectedEntitySummary,
    error: options.pathwayError ?? null,
  })
  const keySignals = [
    activeDataset?.mode === 'custom_user_data_mode'
    ? `Custom user data active${activeDataset?.label ? ` (${activeDataset.label})` : ''}`
      : 'Bordbar reference context',
    pathwayViewMode === 'compact' ? 'Compact graph active' : 'Full model map active',
    calibrationApplied
      ? calibrationSource === 'provided'
        ? 'Latest calibration active'
        : calibrationSource === 'auto_loaded'
          ? 'Auto-loaded calibration active'
          : 'Calibration active'
      : 'Default Bordbar calibration',
    playbackAvailable && playbackCurrentIndex !== null
      ? `Playback frame ${playbackCurrentIndex + 1}/${playbackTimepoints.length}${playbackCurrentTime !== null ? ` at t=${playbackCurrentTime.toFixed(2)} days` : ''}`
      : 'Static network snapshot',
    dominantPathway ? `Most represented: ${dominantPathway}` : 'No dominant pathway yet',
    `Network scale: ${result?.nodes.length ?? 0} metabolites • ${reactionCount} reactions`,
  ]
  if (selectedEntitySummary) {
    keySignals.push(`Selected: ${selectedEntitySummary}`)
  }
  if (playbackFluxAware) {
    keySignals.push('Flux projections are available for playback')
  }

  return {
    moduleType: 'pathway-visualization',
    moduleTitle: 'Pathway Visualization',
    timestamp: new Date().toISOString(),
    success: pathwayStatus === 'completed',
    researchDataMode: activeDataset?.mode ?? 'default_bordbar_mode',
    activeDataset: activeDataset ?? undefined,
    activeDatasetId: activeDataset?.datasetId ?? null,
    activeDatasetLabel: activeDataset?.label ?? null,
    datasetSource: activeDataset?.source ?? 'bordbar_reference',
    datasetApplied: activeDataset?.mode === 'custom_user_data_mode',
    defaultFallbackUsed: activeDataset?.mode !== 'custom_user_data_mode',
    calibrationApplied,
    calibrationSource,
    calibratedParametersActive: calibrationApplied,
    latestCalibrationLoaded: calibrationApplied,
    pathwayViewMode,
    pathwayStatus,
    pathwayResultAvailable: pathwayStatus === 'completed',
    pathwayCompleted: pathwayStatus === 'completed',
    pathwayFailed: pathwayStatus === 'failed',
    pathwayError: options.pathwayError ?? null,
    resultSummary,
    compactOverview: result?.compactOverview ?? [],
    playbackReady: playbackAvailable,
    playbackFrameIndex: playbackCurrentIndex,
    playbackFrameCount: playbackTimepoints.length,
    playbackTimepoint: playbackCurrentTime,
    networkStateSummary,
    dominantPathway,
    dominantSignal,
    topAccumulatingMetabolites: playbackState.topAccumulatingMetabolites,
    topDepletingMetabolites: playbackState.topDepletingMetabolites,
    selectedTimepointSummary,
    replaySource: playbackSourceLabel,
    selectedEntity: selectionState.selectedEntity,
    selectedEntitySummary,
    playback: {
      available: playbackAvailable,
      currentIndex: playbackCurrentIndex,
      totalFrames: playbackTimepoints.length,
      currentTime: playbackCurrentTime,
      sourceLabel: playbackSourceLabel,
      capturedAt: options.latestSimulationSnapshot?.capturedAt ?? null,
      fluxAware: playbackFluxAware,
    },
    outputs: {
      networkStats: {
        nodes: result?.nodes.length ?? 0,
        edges: result?.edges.length ?? 0,
        reactions: reactionCount,
        pathways: uniquePathways,
      },
      pathwayRepresentation: 'metabolite-reaction graph',
    },
    summary: {
      complexity:
        (result?.nodes.length ?? 0) > 50 ? 'complex' : (result?.nodes.length ?? 0) > 20 ? 'moderate' : 'simple',
      keyPathways: uniquePathways.slice(0, 3),
      keySignals,
    },
  }
}

// Data Upload context builder
interface UploadResult {
  filename: string
  columns: string[]
  n_rows: number
  format_detected: Record<string, unknown>
  preview: Record<string, unknown>[]
}

interface MappingResult {
  mappings: Record<string, { metabolite: string; confidence: number }>
  unmapped: string[]
}

export function buildDataUploadResearchContext(
  uploadResult: UploadResult,
  mappingResult: MappingResult,
  file: File
): DataUploadResearchContext {
  const mappedColumns = Object.keys(mappingResult.mappings).length
  const totalColumns = uploadResult.columns.length
  
  const dataQuality = mappedColumns / totalColumns > 0.8 ? 'good' : 
                      mappedColumns / totalColumns > 0.5 ? 'moderate' : 'needs review'

  return {
    moduleType: 'data-upload',
    moduleTitle: 'Data Upload',
    timestamp: new Date().toISOString(),
    success: true,
    inputs: {
      filename: file.name,
      fileSize: file.size,
      format: file.name.split('.').pop() || 'unknown',
    },
    outputs: {
      columns: uploadResult.columns,
      nRows: uploadResult.n_rows,
      formatDetected: uploadResult.format_detected,
      preview: uploadResult.preview,
      mappings: mappingResult.mappings,
      unmapped: mappingResult.unmapped,
    },
    summary: {
      dataQuality,
      mappedColumns,
      unmappedColumns: mappingResult.unmapped.length,
    },
  }
}

// Helper function for trend analysis (reused from simulation-context.ts)
function analyzeTrends(result: SimulationResult) {
  const trends: SimulationResearchContext['summary']['notableTrends'] = []
  
  if (!result.success || result.t.length < 2) return trends
  
  const keyMetabs = ['GLC', 'LAC', 'ATP', 'ADP', 'B23PG', 'NADH', 'GSH', 'PYR'].filter(m => result.metabolite_names.includes(m))
  
  for (const metabolite of keyMetabs) {
    const idx = result.metabolite_names.indexOf(metabolite)
    if (idx === -1) continue
    
    const startVal = result.x[0][idx]
    const endVal = result.x[result.x.length - 1][idx]
    const change = endVal - startVal
    const percentChange = startVal !== 0 ? (change / startVal) * 100 : 0
    
    let direction: 'increasing' | 'decreasing' | 'stable'
    let magnitude: 'high' | 'medium' | 'low'
    
    if (Math.abs(percentChange) < 5) {
      direction = 'stable'
    } else if (change > 0) {
      direction = 'increasing'
    } else {
      direction = 'decreasing'
    }
    
    if (Math.abs(percentChange) > 50) {
      magnitude = 'high'
    } else if (Math.abs(percentChange) > 20) {
      magnitude = 'medium'
    } else {
      magnitude = 'low'
    }
    
    trends.push({
      metabolite,
      direction,
      magnitude,
    })
  }
  
  return trends
}
