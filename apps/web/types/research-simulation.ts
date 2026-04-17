import type { SimulationParams, SimulationResult } from '@/hooks/use-simulation'

export const RESEARCH_SIMULATION_STORAGE_KEY = 'clawblood.research.latestSimulation'
export const RESEARCH_SIMULATION_CHANGE_EVENT = 'clawblood:research-simulation-change'

export type ResearchSimulationSnapshotResult = Pick<
  SimulationResult,
  | 'success'
  | 't'
  | 'x'
  | 'metabolite_names'
  | 'n_points'
  | 'n_metabolites'
  | 'solver'
  | 'duration'
  | 'custom_params_source'
  | 'log'
  | 'research_data_mode'
  | 'active_dataset_id'
  | 'active_dataset_label'
  | 'dataset_applied'
  | 'dataset_fallback_reason'
  | 'dataset_applied_metabolites'
  | 'flux_data'
>

export interface ResearchSimulationSnapshot {
  snapshotId: string
  capturedAt: string
  params: SimulationParams
  result: ResearchSimulationSnapshotResult
}
