/**
 * Research Module Context Contracts for RoBoCop Chat
 * 
 * Each Research page provides a context object for RoBoCop interpretation.
 * This creates a clean seam for LLM-based chat across all Research modules.
 */

import type { ResearchDataMode, ResearchDatasetSummary } from '@/types/research-dataset'
import type { PathwayCompactOverviewItem } from '@/types/pathway-network'
import type {
  CalibrationDatasetProvenance,
  CalibrationFitMetrics,
  CalibrationParameterChange,
  CalibrationRunStatus,
} from '@/lib/robocop/calibration-provenance'

export interface BaseResearchContext {
  moduleType: 'simulation' | 'calibration' | 'calibration-registry' | 'flux-analysis' | 'sensitivity-analysis' | 'pathway-visualization' | 'data-upload'
  moduleTitle: string
  timestamp: string
  success: boolean
  researchDataMode?: ResearchDataMode
  activeDataset?: ResearchDatasetSummary
  activeDatasetId?: string | null
  activeDatasetLabel?: string | null
  datasetSource?: 'bordbar_reference' | 'custom_upload'
  datasetApplied?: boolean
  defaultFallbackUsed?: boolean
  datasetFallbackReason?: string | null
  datasetAppliedMetabolites?: string[]
  calibrationApplied?: boolean
  calibrationSource?: 'provided' | 'auto_loaded' | 'defaults'
  calibratedParametersActive?: boolean
  latestCalibrationLoaded?: boolean
  customParamsSource?: 'provided' | 'defaults' | 'auto_loaded'
  workspaceContext?: {
    userId?: string
    sessionId?: string
  }
}

export interface SimulationResearchContext extends BaseResearchContext {
  moduleType: 'simulation'
  selectedMetabolites?: string[]
  parameters: {
    t_max: number
    curve_fit_strength: number
    solver_method: string
    ph_perturbation_type: string
    ph_severity?: string
    ph_duration?: number
  }
  outputs: {
    timeRange: {
      start: number
      end: number
      n_points: number
    }
    metabolites: {
      total: number
      names: string[]
      keyMetabolites: string[]
      finalValues: Record<string, number>
      profiles: SimulationMetaboliteProfile[]
    }
    trajectories?: Record<string, number[]> // Optional: focused time series for the plotted metabolites
  }
  summary: {
    duration: number
    solver: string
    notableTrends?: {
      metabolite: string
      direction: 'increasing' | 'decreasing' | 'stable'
      magnitude: 'high' | 'medium' | 'low'
    }[]
  }
}

export interface SimulationMetaboliteProfile {
  metabolite: string
  initial: number
  final: number
  minimum: number
  maximum: number
  delta: number
  percentChange: number
  direction: 'increasing' | 'decreasing' | 'stable'
  magnitude: 'high' | 'medium' | 'low'
}

export interface CalibrationResearchContext extends BaseResearchContext {
  moduleType: 'calibration'
  calibrationResultAvailable: boolean
  calibrationStatus: CalibrationRunStatus
  calibrationCompleted: boolean
  calibrationFailed: boolean
  calibrationError?: string | null
  resultSummary?: string
  runDurationSeconds?: number
  fitMetrics?: CalibrationFitMetrics
  parameterChanges?: CalibrationParameterChange[]
  initialVsFinalComparison?: CalibrationParameterChange[]
  strategyUsed?: string
  datasetProvenance?: CalibrationDatasetProvenance
  inputs: {
    selectedParameters: string[]
    selectedParameterFamilies: string[]
    selectedOptimizationStrategy: string
    optimizationStrategy: string
    strategyLabel: string
    strategyDescription?: string
    isRecommendedSubset: boolean
    hasAdvancedSelection: boolean
    canonicalTaxonomySource: string
    canonicalTaxonomyVersion: string
    method?: string
    maxIterations: number
    targetMetabolites: string[]
  }
  outputs: {
    optimizedParameters: Record<string, number>
    initialParameters: Record<string, number>
    objectiveValue: number
    iterations: number
    rSquared: number
    confidenceIntervals: Record<string, [number, number]>
    sensitivity: Record<string, number>
  }
  summary: {
    convergence: boolean
    improvement: number // percent improvement in objective
    topChanges: { param: string; change: number; percentChange: number }[]
  }
}

export interface CalibrationRegistryComparisonGroup {
  key: string
  label: string
  count: number
  completedCount: number
  bestScore: number | null
  meanFinalLoss: number | null
  meanImprovementPct: number | null
  summaryLine: string
}

export interface CalibrationRegistryLeadRecord {
  runId: string | null
  label: string | null
  benchmarkStatus: string | null
  completionStatus: string | null
  optimizationStrategy: string | null
  targetScope: string | null
  paramScope: string | null
  aggregateScore: number | null
  meanFinalLoss: number | null
  meanImprovementPct: number | null
  timeAwareScore: number | null
  elapsedSeconds: number | null
  caseCount: number | null
}

export interface CalibrationRegistryResearchContext extends BaseResearchContext {
  moduleType: 'calibration-registry'
  calibrationResultAvailable: boolean
  calibrationStatus: CalibrationRunStatus
  calibrationCompleted: boolean
  calibrationFailed: boolean
  fitMetrics?: CalibrationFitMetrics
  parameterChanges?: CalibrationParameterChange[]
  initialVsFinalComparison?: CalibrationParameterChange[]
  strategyUsed?: string
  runDurationSeconds?: number
  registryStatus: string
  registryCompleted: boolean
  registryFailed: boolean
  registryResultSummary?: string
  resultSummary?: string
  registryComparison: {
    visibleRuns: number
    groups: CalibrationRegistryComparisonGroup[]
    leadRecord: CalibrationRegistryLeadRecord | null
    comparisonSummary: string
  }
  inputs: {
    selectedOptimizationStrategy: string
    strategyLabel: string
    strategyDescription?: string
    canonicalTaxonomySource: string
    canonicalTaxonomyVersion: string
  }
  outputs: {
    aggregateScore: number | null
    meanFinalLoss: number | null
    meanImprovementPct: number | null
    timeAwareScore: number | null
    bestCase: string | null
    worstCase: string | null
    caseCount: number | null
    completedCases: number | null
    totalCases: number | null
    elapsedSeconds: number | null
  }
  summary: {
    benchmarkStatus: string
    topComparisons: string[]
    comparisonLane: string | null
  }
}

export interface FluxAnalysisSignal {
  reaction: string
  flux: number
  pathway: string
}

export interface FluxAnalysisResearchContext extends BaseResearchContext {
  moduleType: 'flux-analysis'
  fluxStatus: 'setup_only' | 'running' | 'completed' | 'failed'
  fluxResultAvailable: boolean
  fluxCompleted: boolean
  fluxFailed: boolean
  fluxError?: string | null
  resultSummary?: string
  playbackReady?: boolean
  playbackFrameIndex?: number | null
  playbackFrameCount?: number
  playbackTimepoint?: number | null
  networkStateSummary?: string | null
  dominantPathway?: string | null
  dominantSignal?: PathwayPlaybackSignal | null
  topAccumulatingMetabolites?: PathwayPlaybackMetaboliteShift[]
  topDepletingMetabolites?: PathwayPlaybackMetaboliteShift[]
  selectedTimepointSummary?: string | null
  replaySource?: string | null
  inputs: {
    concentrations: Record<string, number>
    selectedPathway: string
    concentrationSource: 'bordbar_reference' | 'custom_upload'
    appliedConcentrationMetabolites: string[]
    totalConcentrations: number
  }
  outputs: {
    fluxes: Record<string, number>
    pathwayGroups: Record<string, string[]>
    pathwayFluxTotals: Record<string, number>
    totalFlux: number
    topFluxes: FluxAnalysisSignal[]
    topPositiveFluxes: FluxAnalysisSignal[]
    topNegativeFluxes: FluxAnalysisSignal[]
    dominantPathways: string[]
  }
  summary: {
    dominantPathway: string
    topReactions: FluxAnalysisSignal[]
    fluxDistribution: Record<string, number> // pathway -> total flux
    keySignals: string[]
  }
}

export interface SensitivityResearchContext extends BaseResearchContext {
  moduleType: 'sensitivity-analysis'
  inputs: {
    customTimeSeries?: {
      metabolites: string[]
      timePoints: number[]
      values: number[][]
    }
    t_max: number
  }
  outputs: {
    metaboliteComparison: {
      metabolite: string
      reference: number
      custom: number
      rmse: number
      percentChange: number
    }[]
    topSensitiveMetabolites: {
      name: string
      percentChange: number
    }[]
    validationMetrics: Record<string, {
      R2: number
      RMSE: number
      MAE: number
      n_points: number
    }>
  }
  summary: {
    overallFit: 'good' | 'moderate' | 'poor'
    mostDiscrepancies: string[]
    averageError: number
  }
}

export interface PathwayVisualizationResearchContext extends BaseResearchContext {
  moduleType: 'pathway-visualization'
  pathwayStatus: 'setup_only' | 'running' | 'completed' | 'failed'
  pathwayResultAvailable: boolean
  pathwayCompleted: boolean
  pathwayFailed: boolean
  pathwayError?: string | null
  resultSummary?: string
  pathwayViewMode?: 'compact' | 'full'
  playbackReady: boolean
  playbackFrameIndex: number | null
  playbackFrameCount: number
  playbackTimepoint: number | null
  networkStateSummary?: string | null
  dominantPathway?: string | null
  dominantSignal?: PathwayPlaybackSignal | null
  topAccumulatingMetabolites?: PathwayPlaybackMetaboliteShift[]
  topDepletingMetabolites?: PathwayPlaybackMetaboliteShift[]
  selectedTimepointSummary?: string | null
  replaySource?: string | null
  selectedEntity?: PathwayVisualizationSelection | null
  selectedEntitySummary?: string | null
  compactOverview?: PathwayCompactOverviewItem[]
  playback?: {
    available: boolean
    currentIndex: number | null
    totalFrames: number
    currentTime: number | null
    sourceLabel: string | null
    capturedAt: string | null
    fluxAware: boolean
  }
  outputs: {
    networkStats: {
      nodes: number
      edges: number
      reactions: number
      pathways: string[]
    }
    pathwayRepresentation: string // 'metabolite-reaction graph'
    }
  summary: {
    complexity: 'simple' | 'moderate' | 'complex'
    keyPathways: string[]
    keySignals: string[]
  }
}

export interface PathwayPlaybackSignal {
  label: string
  value: number
  pathway?: string | null
  direction?: 'increasing' | 'decreasing' | 'stable'
}

export interface PathwayPlaybackMetaboliteShift {
  metabolite: string
  concentration: number
  delta: number
  percentChange: number
  pathway?: string | null
}

export interface PathwayVisualizationSelection {
  kind: 'metabolite' | 'reaction'
  id: string
  label: string
  pathway?: string | null
  summary?: string | null
}

export interface DataUploadResearchContext extends BaseResearchContext {
  moduleType: 'data-upload'
  inputs: {
    filename: string
    fileSize: number
    format: string
  }
  outputs: {
    columns: string[]
    nRows: number
    formatDetected: Record<string, unknown>
    preview: Record<string, unknown>[]
    mappings: Record<string, {
      metabolite: string
      confidence: number
    }>
    unmapped: string[]
  }
  summary: {
    dataQuality: 'good' | 'moderate' | 'needs review'
    mappedColumns: number
    unmappedColumns: number
    timeRange?: [number, number]
  }
}

export type ResearchContext = 
  | SimulationResearchContext
  | CalibrationResearchContext
  | CalibrationRegistryResearchContext
  | FluxAnalysisResearchContext
  | SensitivityResearchContext
  | PathwayVisualizationResearchContext
  | DataUploadResearchContext

/**
 * RoBoCop Chat Message Types
 */
export interface RoBoCopChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  contextReferences?: string[] // Which parts of context were referenced
}

export interface RoBoCopChatState {
  messages: RoBoCopChatMessage[]
  isLoading: boolean
  error?: string
}

/**
 * RoBoCop Chat Request/Response
 */
export interface RoBoCopChatRequest {
  context: ResearchContext
  message: string
  conversationHistory?: RoBoCopChatMessage[]
}

export interface RoBoCopChatResponse {
  message: string
  contextReferences: string[]
  confidence: 'high' | 'medium' | 'low'
  suggestedFollowUps?: string[]
}
