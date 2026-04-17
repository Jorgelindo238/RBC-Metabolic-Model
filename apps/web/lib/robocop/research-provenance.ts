import type { ResearchDataMode, ResearchDatasetSummary } from '@/types/research-dataset'
import type {
  CalibrationRegistryResearchContext,
  CalibrationResearchContext,
  FluxAnalysisResearchContext,
  PathwayVisualizationResearchContext,
} from '@/types/research-context'
import { getCalibrationRunStatusLabel, getCalibrationRunStatusLine } from '@/lib/robocop/calibration-provenance'

export type CalibrationSource = 'provided' | 'auto_loaded' | 'defaults'

export interface ResearchProvenanceSnapshot {
  researchDataMode?: ResearchDataMode
  activeDataset?: ResearchDatasetSummary | null
  activeDatasetId?: string | null
  activeDatasetLabel?: string | null
  datasetSource?: 'bordbar_reference' | 'custom_upload'
  datasetApplied?: boolean
  datasetAppliedMetabolites?: string[]
  defaultFallbackUsed?: boolean
  datasetFallbackReason?: string | null
  calibrationApplied?: boolean
  calibrationSource?: CalibrationSource
  calibratedParametersActive?: boolean
  latestCalibrationLoaded?: boolean
}

export function getDatasetModeLabel(provenance: ResearchProvenanceSnapshot) {
  if (provenance.researchDataMode === 'custom_user_data_mode') {
    return provenance.datasetApplied ? 'Custom user data active' : 'Custom data fallback'
  }

  return 'Bordbar fallback active'
}

export function getDatasetStatusLabel(provenance: ResearchProvenanceSnapshot) {
  if (provenance.researchDataMode === 'custom_user_data_mode') {
    return provenance.datasetApplied ? 'Custom data applied' : 'Custom data pending'
  }

  return 'Bordbar reference dataset'
}

export function getDatasetStatusLine(provenance: ResearchProvenanceSnapshot) {
  if (provenance.researchDataMode === 'custom_user_data_mode') {
    const label = provenance.activeDatasetLabel ?? provenance.activeDataset?.label ?? 'active custom dataset'
    if (provenance.datasetApplied) {
      const count = provenance.datasetAppliedMetabolites?.length ?? 0
      return `${label} • ${count} custom metabolites applied`
    }

    return `Custom data mode active • Bordbar fallback used${provenance.datasetFallbackReason ? ` (${provenance.datasetFallbackReason})` : ''}`
  }

  return 'Bordbar reference dataset • default fallback'
}

export function getCalibrationStatusLabel(provenance: ResearchProvenanceSnapshot) {
  if (!provenance.calibrationApplied && !provenance.calibratedParametersActive) {
    return 'Bordbar defaults active'
  }

  if (provenance.calibrationSource === 'provided') {
    return 'Latest calibration applied'
  }

  if (provenance.calibrationSource === 'auto_loaded') {
    return 'Auto-loaded calibration'
  }

  return 'Calibration applied'
}

export function getCalibrationStatusLine(provenance: ResearchProvenanceSnapshot) {
  if (!provenance.calibrationApplied && !provenance.calibratedParametersActive) {
    return 'Default Bordbar ODE parameters were used'
  }

  if (provenance.calibrationSource === 'provided') {
    return 'Latest optimized ODE parameters were injected'
  }

  if (provenance.calibrationSource === 'auto_loaded') {
    return 'Saved calibration parameters were auto-loaded'
  }

  return 'Calibration parameters were applied'
}

export function getSimulationProvenanceSummary(provenance: ResearchProvenanceSnapshot) {
  const datasetPart = provenance.researchDataMode === 'custom_user_data_mode'
    ? provenance.datasetApplied
      ? `Custom user data from ${provenance.activeDatasetLabel ?? provenance.activeDataset?.label ?? 'the active upload'} was applied`
      : `Custom user data mode was active, but the run fell back to Bordbar defaults${provenance.datasetFallbackReason ? ` (${provenance.datasetFallbackReason})` : ''}`
    : 'Bordbar reference dataset was used'

  const calibrationPart = !provenance.calibrationApplied && !provenance.calibratedParametersActive
    ? 'default Bordbar parameters were retained'
    : provenance.calibrationSource === 'provided'
      ? 'the latest calibrated parameters were applied'
      : provenance.calibrationSource === 'auto_loaded'
        ? 'calibrated parameters were auto-loaded'
        : 'calibrated parameters were applied'

  return `${datasetPart} and ${calibrationPart}.`
}

export function getSimulationProvenanceObservations(provenance: ResearchProvenanceSnapshot) {
  const observations: string[] = []

  observations.push(`Data mode: ${provenance.researchDataMode === 'custom_user_data_mode' ? 'custom user data' : 'Bordbar default'}`)

  if (provenance.activeDatasetLabel || provenance.activeDataset?.label) {
    observations.push(`Active dataset: ${provenance.activeDatasetLabel ?? provenance.activeDataset?.label}`)
  }

  if (provenance.datasetApplied) {
    observations.push(`Applied ${provenance.datasetAppliedMetabolites?.length ?? 0} mapped metabolites from the uploaded dataset`)
  } else if (provenance.defaultFallbackUsed || provenance.datasetFallbackReason) {
    observations.push(`Fallback used${provenance.datasetFallbackReason ? `: ${provenance.datasetFallbackReason}` : ''}`)
  }

  if (provenance.calibrationApplied || provenance.calibratedParametersActive) {
    if (provenance.calibrationSource === 'provided') {
      observations.push('Latest calibration parameters were applied')
    } else if (provenance.calibrationSource === 'auto_loaded') {
      observations.push('Calibration parameters were auto-loaded')
    } else {
      observations.push('Calibration parameters were active')
    }
  } else {
    observations.push('Default Bordbar parameters were retained')
  }

  return observations
}

export function getFluxAnalysisStatusLabel(provenance: FluxAnalysisResearchContext) {
  if (provenance.fluxFailed) {
    return 'Flux estimation failed'
  }

  if (provenance.fluxCompleted || provenance.fluxResultAvailable) {
    return 'Flux result ready'
  }

  if (provenance.fluxStatus === 'running') {
    return 'Flux estimation running'
  }

  return 'Flux setup ready'
}

export function getFluxAnalysisStatusLine(provenance: FluxAnalysisResearchContext) {
  if (provenance.resultSummary) {
    return provenance.resultSummary
  }

  if (provenance.fluxStatus === 'running') {
    return 'Flux estimation is running on the current provenance snapshot.'
  }

  if (provenance.fluxFailed) {
    return `Flux estimation failed${provenance.fluxError ? `: ${provenance.fluxError}` : ''}`
  }

  const appliedCount = provenance.datasetAppliedMetabolites?.length ?? 0
  if (provenance.researchDataMode === 'custom_user_data_mode') {
    if (provenance.datasetApplied) {
      return `${provenance.activeDatasetLabel ?? provenance.activeDataset?.label ?? 'Custom data'} • ${appliedCount} concentration overrides applied`
    }
    return `Custom data mode active • Bordbar fallback used${provenance.datasetFallbackReason ? ` (${provenance.datasetFallbackReason})` : ''}`
  }

  return 'Bordbar reference snapshot • default flux estimation'
}

export function getFluxAnalysisProvenanceSummary(provenance: FluxAnalysisResearchContext) {
  const dataPart =
    provenance.researchDataMode === 'custom_user_data_mode'
      ? provenance.datasetApplied
        ? `Custom user data from ${provenance.activeDatasetLabel ?? provenance.activeDataset?.label ?? 'the active upload'}`
        : `Custom user data mode with Bordbar fallback${provenance.datasetFallbackReason ? ` (${provenance.datasetFallbackReason})` : ''}`
      : 'Bordbar reference data'

  const calibrationPart =
    provenance.calibrationApplied || provenance.calibratedParametersActive
      ? provenance.calibrationSource === 'provided'
        ? 'Latest calibration applied'
        : provenance.calibrationSource === 'auto_loaded'
          ? 'Auto-loaded calibration active'
          : 'Calibration applied'
      : 'Default Bordbar calibration'

  const fluxPart =
    provenance.fluxStatus === 'completed'
      ? `Dominant pathway ${provenance.summary.dominantPathway}`
      : provenance.fluxStatus === 'running'
        ? 'Flux estimation running'
        : provenance.fluxStatus === 'failed'
          ? 'Flux estimation failed'
          : 'Flux setup ready'

  const pathwayPart =
    provenance.inputs.selectedPathway && provenance.inputs.selectedPathway !== 'all'
      ? `Viewing ${provenance.inputs.selectedPathway}`
      : 'All pathways visible'

  const resultPart = provenance.resultSummary ?? getFluxAnalysisStatusLine(provenance)

  return `${dataPart} • ${calibrationPart} • ${fluxPart} • ${pathwayPart} • ${resultPart}`
}

export function getFluxAnalysisObservations(provenance: FluxAnalysisResearchContext) {
  const observations: string[] = []

  observations.push(
    `Data mode: ${provenance.researchDataMode === 'custom_user_data_mode' ? 'custom user data' : 'Bordbar default'}`
  )

  if (provenance.activeDatasetLabel || provenance.activeDataset?.label) {
    observations.push(`Active dataset: ${provenance.activeDatasetLabel ?? provenance.activeDataset?.label}`)
  }

  if (provenance.datasetApplied) {
    observations.push(`Applied ${provenance.datasetAppliedMetabolites?.length ?? 0} mapped concentration overrides`)
  } else if (provenance.defaultFallbackUsed || provenance.datasetFallbackReason) {
    observations.push(`Fallback used${provenance.datasetFallbackReason ? `: ${provenance.datasetFallbackReason}` : ''}`)
  }

  if (provenance.calibrationApplied || provenance.calibratedParametersActive) {
    observations.push(
      provenance.calibrationSource === 'provided'
        ? 'Latest calibration parameters were applied'
        : provenance.calibrationSource === 'auto_loaded'
          ? 'Calibration parameters were auto-loaded'
          : 'Calibration parameters were active'
    )
  } else {
    observations.push('Default Bordbar parameters were retained')
  }

  observations.push(`Flux status: ${getFluxAnalysisStatusLabel(provenance)}`)

  if (provenance.inputs.selectedPathway && provenance.inputs.selectedPathway !== 'all') {
    observations.push(`Selected pathway filter: ${provenance.inputs.selectedPathway}`)
  } else {
    observations.push('Selected pathway filter: all pathways')
  }

  if (provenance.summary.dominantPathway) {
    observations.push(`Dominant pathway: ${provenance.summary.dominantPathway}`)
  }

  if (provenance.outputs.topFluxes.length > 0) {
    const top = provenance.outputs.topFluxes.slice(0, 3).map((signal) => `${signal.reaction} ${signal.flux >= 0 ? '+' : ''}${signal.flux.toExponential(2)}`)
    observations.push(`Top flux signals: ${top.join(', ')}`)
  }

  observations.push(`Total flux: ${provenance.outputs.totalFlux.toExponential(2)}`)

  if (provenance.resultSummary) {
    observations.push(`Result summary: ${provenance.resultSummary}`)
  }

  return observations
}

export function getPathwayVisualizationStatusLabel(provenance: PathwayVisualizationResearchContext) {
  if (provenance.pathwayFailed) {
    return 'Pathway map failed'
  }

  if (provenance.pathwayCompleted || provenance.pathwayResultAvailable) {
    return provenance.playbackReady ? 'Pathway replay ready' : 'Pathway map ready'
  }

  if (provenance.pathwayStatus === 'running') {
    return 'Pathway map loading'
  }

  return 'Pathway map ready'
}

export function getPathwayVisualizationStatusLine(provenance: PathwayVisualizationResearchContext) {
  if (provenance.selectedTimepointSummary) {
    return provenance.selectedTimepointSummary
  }

  if (provenance.resultSummary) {
    return provenance.resultSummary
  }

  if (provenance.pathwayStatus === 'running') {
    return 'Pathway visualization is loading the current network snapshot.'
  }

  if (provenance.pathwayFailed) {
    return `Pathway visualization failed${provenance.pathwayError ? `: ${provenance.pathwayError}` : ''}`
  }

  const { nodes, reactions, pathways } = provenance.outputs.networkStats
  if (provenance.pathwayResultAvailable) {
    return `Pathway network ready with ${nodes} metabolites, ${reactions} reactions, and ${pathways.length} pathway groups.`
  }

  return `Pathway network ready with ${nodes} metabolites, ${reactions} reactions, and ${pathways.length} pathway groups.`
}

export function getPathwayVisualizationProvenanceSummary(provenance: PathwayVisualizationResearchContext) {
  const datasetLabel = provenance.activeDatasetLabel ?? provenance.activeDataset?.label
  const dataPart =
    provenance.researchDataMode === 'custom_user_data_mode'
      ? `Custom user data active${datasetLabel ? ` (${datasetLabel})` : ''}`
      : 'Bordbar reference context'
  const viewModePart = provenance.pathwayViewMode === 'compact' ? 'Compact graph' : 'Full model map'
  const calibrationPart =
    provenance.calibrationApplied || provenance.calibratedParametersActive
      ? provenance.calibrationSource === 'provided'
        ? 'Latest calibration active'
        : provenance.calibrationSource === 'auto_loaded'
          ? 'Auto-loaded calibration active'
          : 'Calibration active'
      : 'Default Bordbar calibration'
  const networkPart =
      provenance.pathwayResultAvailable
      ? `${provenance.outputs.networkStats.nodes} metabolites • ${provenance.outputs.networkStats.reactions} reactions`
      : provenance.pathwayStatus === 'running'
        ? 'Pathway network loading'
        : 'Pathway network ready'
  const playbackPart =
    provenance.playbackReady && provenance.playbackFrameIndex !== null
      ? `Frame ${provenance.playbackFrameIndex + 1}/${provenance.playbackFrameCount}${provenance.playbackTimepoint !== null ? ` at t=${provenance.playbackTimepoint.toFixed(2)} days` : ''}`
      : 'Static network snapshot'
  const selectionPart = provenance.selectedEntitySummary ? `Selected ${provenance.selectedEntitySummary}` : null

  return `${dataPart} • ${calibrationPart} • ${viewModePart} • ${networkPart} • ${playbackPart}${selectionPart ? ` • ${selectionPart}` : ''}`
}

export function getPathwayVisualizationObservations(provenance: PathwayVisualizationResearchContext) {
  const observations: string[] = []

  observations.push(
    `Data mode: ${provenance.researchDataMode === 'custom_user_data_mode' ? 'custom user data' : 'Bordbar default'}`
  )

  if (provenance.activeDatasetLabel || provenance.activeDataset?.label) {
    observations.push(`Active dataset: ${provenance.activeDatasetLabel ?? provenance.activeDataset?.label}`)
  }

  observations.push(
    provenance.calibrationApplied || provenance.calibratedParametersActive
      ? provenance.calibrationSource === 'provided'
        ? 'Latest calibration active'
        : provenance.calibrationSource === 'auto_loaded'
          ? 'Auto-loaded calibration active'
          : 'Calibration active'
      : 'Default Bordbar calibration'
  )

  observations.push(`Pathway state: ${getPathwayVisualizationStatusLabel(provenance)}`)
  observations.push(`View mode: ${provenance.pathwayViewMode === 'compact' ? 'Compact graph' : 'Full model map'}`)

  if (provenance.playbackReady && provenance.playbackFrameIndex !== null) {
    const frameSummary = `Playback frame ${provenance.playbackFrameIndex + 1}/${provenance.playbackFrameCount}`
    const timeSummary = provenance.playbackTimepoint !== null ? `t=${provenance.playbackTimepoint.toFixed(2)} days` : null
    observations.push([frameSummary, timeSummary].filter(Boolean).join(' • '))
  } else if (provenance.pathwayStatus === 'running') {
    observations.push('Playback is still loading')
  } else {
    observations.push('Static network snapshot')
  }

  if (provenance.replaySource) {
    observations.push(`Replay source: ${provenance.replaySource}`)
  }

  if (provenance.selectedEntitySummary) {
    observations.push(`Selected: ${provenance.selectedEntitySummary}`)
  }

  if (provenance.networkStateSummary) {
    observations.push(provenance.networkStateSummary)
  }

  if (provenance.dominantPathway) {
    observations.push(`Dominant pathway: ${provenance.dominantPathway}`)
  }

  if (provenance.dominantSignal) {
    const value = provenance.dominantSignal.value
    observations.push(
      `Dominant signal: ${provenance.dominantSignal.label} ${value >= 0 ? '+' : ''}${value.toExponential(2)}${
        provenance.dominantSignal.pathway ? ` (${provenance.dominantSignal.pathway})` : ''
      }`
    )
  }

  if (provenance.topAccumulatingMetabolites?.length) {
    observations.push(
      `Accumulating: ${provenance.topAccumulatingMetabolites
        .slice(0, 3)
        .map((shift) => `${shift.metabolite} ${shift.delta >= 0 ? '+' : ''}${shift.delta.toExponential(2)}`)
        .join(', ')}`
    )
  }

  if (provenance.topDepletingMetabolites?.length) {
    observations.push(
      `Depleting: ${provenance.topDepletingMetabolites
        .slice(0, 3)
        .map((shift) => `${shift.metabolite} ${shift.delta.toExponential(2)}`)
        .join(', ')}`
    )
  }

  if (provenance.summary.keyPathways.length > 0) {
    observations.push(`Key pathways: ${provenance.summary.keyPathways.join(', ')}`)
  }

  observations.push(
    `Network size: ${provenance.outputs.networkStats.nodes} metabolites, ${provenance.outputs.networkStats.reactions} reactions`
  )

  if (provenance.resultSummary) {
    observations.push(`Result summary: ${provenance.resultSummary}`)
  }

  return observations
}

export function getCalibrationStrategyLabel(provenance: CalibrationResearchContext) {
  return (
    provenance.inputs.strategyLabel ||
    provenance.inputs.selectedOptimizationStrategy ||
    provenance.inputs.optimizationStrategy ||
    'unknown strategy'
  )
}

export function getCalibrationSelectionModeLabel(provenance: CalibrationResearchContext) {
  if (provenance.inputs.isRecommendedSubset) {
    return 'Recommended subset'
  }

  if (provenance.inputs.hasAdvancedSelection) {
    return 'Advanced canonical inventory'
  }

  return 'Canonical selection'
}

export function getCalibrationProvenanceSummary(provenance: CalibrationResearchContext) {
  const dataPart =
    provenance.researchDataMode === 'custom_user_data_mode'
      ? provenance.datasetApplied
        ? `Custom user data from ${provenance.activeDatasetLabel ?? provenance.activeDataset?.label ?? 'the active upload'}`
        : `Custom user data mode with Bordbar fallback${provenance.datasetFallbackReason ? ` (${provenance.datasetFallbackReason})` : ''}`
      : 'Bordbar reference data'
  const calibrationPart =
    provenance.calibrationApplied || provenance.calibratedParametersActive
      ? provenance.calibrationSource === 'provided'
        ? 'Latest calibration applied'
        : provenance.calibrationSource === 'auto_loaded'
          ? 'Auto-loaded calibration active'
          : 'Calibration applied'
      : 'Default Bordbar calibration'
  const familyPart = provenance.inputs.selectedParameterFamilies.length
    ? provenance.inputs.selectedParameterFamilies.join(' and ')
    : 'canonical Vmax/Km parameters'
  const strategyPart = getCalibrationStrategyLabel(provenance)
  const selectionPart = getCalibrationSelectionModeLabel(provenance)
  const statusPart = getCalibrationRunStatusLabel(provenance.calibrationStatus)
  const resultPart = provenance.resultSummary ?? getCalibrationRunStatusLine(provenance.calibrationStatus, provenance.resultSummary, provenance.fitMetrics)

  return `${dataPart} • ${calibrationPart} • ${familyPart} • ${strategyPart} • ${selectionPart} • ${statusPart} • ${resultPart}`
}

export function getCalibrationProvenanceObservations(provenance: CalibrationResearchContext) {
  const observations: string[] = []

  observations.push(
    `Data mode: ${provenance.researchDataMode === 'custom_user_data_mode' ? 'custom user data' : 'Bordbar default'}`
  )

  if (provenance.activeDatasetLabel || provenance.activeDataset?.label) {
    observations.push(`Active dataset: ${provenance.activeDatasetLabel ?? provenance.activeDataset?.label}`)
  }

  if (provenance.inputs.selectedParameters.length > 0) {
    observations.push(`Selected parameters: ${provenance.inputs.selectedParameters.join(', ')}`)
  }

  if (provenance.inputs.selectedParameterFamilies.length > 0) {
    observations.push(`Parameter families: ${provenance.inputs.selectedParameterFamilies.join(', ')}`)
  }

  observations.push(`Calibration state: ${getCalibrationRunStatusLabel(provenance.calibrationStatus)}`)

  if (provenance.calibrationApplied || provenance.calibratedParametersActive) {
    observations.push(
      provenance.calibrationSource === 'provided'
        ? 'Latest calibration parameters were applied'
        : provenance.calibrationSource === 'auto_loaded'
          ? 'Calibration parameters were auto-loaded'
          : 'Calibration parameters were active'
    )
  } else {
    observations.push('Default Bordbar parameters were retained')
  }

  observations.push(`Optimization strategy: ${getCalibrationStrategyLabel(provenance)}`)
  observations.push(`Selection scope: ${getCalibrationSelectionModeLabel(provenance)}`)
  observations.push(
    `Canonical taxonomy: ${provenance.inputs.canonicalTaxonomySource} ${provenance.inputs.canonicalTaxonomyVersion}`
  )

  if (provenance.resultSummary) {
    observations.push(`Result summary: ${provenance.resultSummary}`)
  }

  if (provenance.fitMetrics?.rSquared !== undefined) {
    observations.push(`Fit quality: R² ${provenance.fitMetrics.rSquared.toFixed(3)}`)
  }

  if (provenance.parameterChanges?.length) {
    const topChange = provenance.parameterChanges[0]
    observations.push(
      `Largest shift: ${topChange.param} ${topChange.percentChange >= 0 ? '+' : ''}${topChange.percentChange.toFixed(1)}%`
    )
  } else if (provenance.calibrationResultAvailable) {
    observations.push(`Calibration result: R² ${provenance.outputs.rSquared.toFixed(3)}, ${provenance.outputs.iterations} iterations`)
  } else {
    observations.push('Calibration result not yet available')
  }

  return observations
}

export function getCalibrationRegistryStatusLabel(provenance: CalibrationRegistryResearchContext) {
  if (provenance.registryCompleted) {
    return 'Historical result ready'
  }

  if (provenance.registryFailed) {
    return 'Historical result failed'
  }

  return 'Historical ledger ready'
}

export function getCalibrationRegistryStatusLine(provenance: CalibrationRegistryResearchContext) {
  if (provenance.registryResultSummary) {
    return provenance.registryResultSummary
  }

  return provenance.registryComparison.comparisonSummary
}

export function getCalibrationRegistryProvenanceSummary(provenance: CalibrationRegistryResearchContext) {
  const leadRecord = provenance.registryComparison.leadRecord
  const leadPart = leadRecord?.label ?? leadRecord?.runId ?? 'historical record'
  const strategyPart = provenance.inputs.strategyLabel || provenance.inputs.selectedOptimizationStrategy || 'unknown strategy'
  const statusPart = getCalibrationRegistryStatusLabel(provenance)
  const lanePart = provenance.registryComparison.comparisonSummary

  return `${leadPart} • ${strategyPart} • ${statusPart} • ${lanePart}`
}

export function getCalibrationRegistryObservations(provenance: CalibrationRegistryResearchContext) {
  const observations: string[] = []

  observations.push(`Registry status: ${provenance.registryStatus}`)
  observations.push(`Visible runs: ${provenance.registryComparison.visibleRuns}`)

  if (provenance.registryComparison.leadRecord) {
    const lead = provenance.registryComparison.leadRecord
    observations.push(
      `Lead record: ${lead.label ?? lead.runId ?? 'unknown'} (${lead.benchmarkStatus ?? 'unknown'} / ${lead.completionStatus ?? 'unknown'})`
    )
  }

  observations.push(`Strategy: ${provenance.inputs.strategyLabel || provenance.inputs.selectedOptimizationStrategy || 'unknown strategy'}`)

  if (provenance.registryComparison.groups.length > 0) {
    observations.push(
      `Comparison lanes: ${provenance.registryComparison.groups
        .slice(0, 3)
        .map((group) => `${group.label} (${group.count})`)
        .join(', ')}`
    )
  }

  if (provenance.registryResultSummary) {
    observations.push(`Result summary: ${provenance.registryResultSummary}`)
  }

  return observations
}
