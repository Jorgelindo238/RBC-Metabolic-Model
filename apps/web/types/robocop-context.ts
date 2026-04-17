/**
 * RoBoCop Module Context Contracts
 * 
 * Each research module provides a context object for RoBoCop interpretation.
 * This creates a clean seam for future module expansion.
 */

import type { ResearchDataMode, ResearchDatasetSummary } from '@/types/research-dataset'

export interface BaseModuleContext {
  moduleId: 'simulation' | 'calibration' | 'flux-analysis' | 'sensitivity' | 'pathway-visualization'
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
}

export interface SimulationContext extends BaseModuleContext {
  moduleId: 'simulation'
  parameters: {
    t_max: number
    curve_fit_strength: number
    solver_method: string
    ph_perturbation_type: string
    ph_severity?: string
    ph_duration?: number
  }
  timeRange: {
    start: number
    end: number
    n_points: number
  }
  metabolites: {
    total: number
    names: string[]
    keyMetabolites: string[]
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
  selectedMetabolites?: string[] // If user selected specific metabolites
}

export interface FluxAnalysisContext extends BaseModuleContext {
  moduleId: 'flux-analysis'
  fluxStatus: 'setup_only' | 'running' | 'completed' | 'failed'
  fluxResultAvailable: boolean
  fluxCompleted: boolean
  fluxFailed: boolean
  fluxError?: string | null
  resultSummary?: string
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
    topFluxes: { reaction: string; flux: number; pathway: string }[]
    topPositiveFluxes: { reaction: string; flux: number; pathway: string }[]
    topNegativeFluxes: { reaction: string; flux: number; pathway: string }[]
    dominantPathways: string[]
  }
  summary: {
    dominantPathway: string
    topReactions: { reaction: string; flux: number; pathway: string }[]
    fluxDistribution: Record<string, number>
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

export type ModuleContext = SimulationContext | FluxAnalysisContext /* Future: CalibrationContext | ... */

/**
 * RoBoCop interpretation response
 */
export interface RoBoCopInterpretation {
  summary: string
  insights: string[]
  recommendations?: string[]
  confidence: 'high' | 'medium' | 'low'
  grounding: {
    dataSource: string
    keyObservations: string[]
  }
}
