import type { SimulationResult, SimulationParams } from '@/hooks/use-simulation'
import type { SimulationContext } from '@/types/robocop-context'
import type { ResearchDatasetSummary } from '@/types/research-dataset'
import type { ActiveResearchCalibration } from '@/lib/research-calibration'

export const SIMULATION_KEY_METABOLITES = ['GLC', 'LAC', 'ATP', 'ADP', 'B23PG', 'NADH', 'GSH', 'PYR'] as const

export function getSimulationKeyMetabolites(metaboliteNames: readonly string[]) {
  return SIMULATION_KEY_METABOLITES.filter(metabolite => metaboliteNames.includes(metabolite))
}

/**
 * Build a RoBoCop context from simulation results
 */
export function buildSimulationContext(
  result: SimulationResult,
  params: SimulationParams,
  selectedMetabolites?: string[],
  activeDataset?: ResearchDatasetSummary,
  activeCalibration?: ActiveResearchCalibration | null
): SimulationContext {
  // Calculate basic statistics
  const tStart = result.t[0]
  const tEnd = result.t[result.t.length - 1]
  const resolvedCalibrationSource = result.custom_params_source ?? (activeCalibration ? 'auto_loaded' : 'defaults')
  
  // Identify notable trends
  const notableTrends = analyzeTrends(result)
  
  return {
    moduleId: 'simulation',
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
    timeRange: {
      start: tStart,
      end: tEnd,
      n_points: result.n_points,
    },
    metabolites: {
      total: result.n_metabolites,
      names: result.metabolite_names,
      keyMetabolites: getSimulationKeyMetabolites(result.metabolite_names),
    },
    summary: {
      duration: result.duration,
      solver: result.solver,
      notableTrends,
    },
    selectedMetabolites,
  }
}

/**
 * Analyze metabolite trends from simulation results
 */
function analyzeTrends(result: SimulationResult) {
  const trends: SimulationContext['summary']['notableTrends'] = []
  
  if (!result.success || result.t.length < 2) return trends
  
  const keyMetabs = getSimulationKeyMetabolites(result.metabolite_names)
  
  for (const metabolite of keyMetabs) {
    const idx = result.metabolite_names.indexOf(metabolite)
    if (idx === -1) continue
    
    const startVal = result.x[0][idx]
    const endVal = result.x[result.x.length - 1][idx]
    const change = endVal - startVal
    const percentChange = startVal !== 0 ? (change / startVal) * 100 : 0
    
    let direction: 'increasing' | 'decreasing' | 'stable'
    let magnitude: 'high' | 'medium' | 'low'
    
    // Determine direction
    if (Math.abs(percentChange) < 5) {
      direction = 'stable'
    } else if (change > 0) {
      direction = 'increasing'
    } else {
      direction = 'decreasing'
    }
    
    // Determine magnitude
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
