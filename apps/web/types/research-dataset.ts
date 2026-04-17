export type ResearchDataMode = 'default_bordbar_mode' | 'custom_user_data_mode'

export type ResearchDatasetSource = 'bordbar_reference' | 'custom_upload'

export interface ResearchDatasetSummary {
  datasetId: string
  source: ResearchDatasetSource
  mode: ResearchDataMode
  label: string
  fileName?: string
  timePointCount: number
  metaboliteCount: number
  mappedMetaboliteCount: number
}

export interface ActiveResearchDataset extends ResearchDatasetSummary {
  timePoints: number[]
  rawColumns: string[]
  rawSeriesByColumn: Record<string, number[]>
  mappedMetabolites: string[]
  mappedSeriesByMetabolite: Record<string, number[]>
  mappings: Record<string, { metabolite: string; confidence: number }>
  preview: Record<string, unknown>[]
  activatedAt: string
}

export interface UploadResponseShape {
  filename: string
  columns: string[]
  n_rows: number
  format_detected: Record<string, unknown>
  preview: Record<string, unknown>[]
  time_points: number[]
  metabolites: string[]
  values: number[][]
}

export interface MappingResponseShape {
  mappings: Record<string, { metabolite: string; confidence: number }>
  unmapped: string[]
}

export interface SimulationDatasetPayload {
  dataset_id: string
  source: ResearchDatasetSource
  mode: ResearchDataMode
  label: string
  file_name?: string
  time_points: number[]
  mapped_metabolites: string[]
  mapped_series_by_metabolite: Record<string, number[]>
}

export interface CalibrationExperimentPayload {
  targetMetabolites: string[]
  expTime: number[]
  expData: Record<string, number[]>
}
