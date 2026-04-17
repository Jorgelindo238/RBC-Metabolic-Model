import type {
  ActiveResearchDataset,
  CalibrationExperimentPayload,
  MappingResponseShape,
  ResearchDatasetSummary,
  SimulationDatasetPayload,
  UploadResponseShape,
} from '@/types/research-dataset'

export const RESEARCH_DATASET_STORAGE_KEY = 'clawblood.research.activeDataset'
export const RESEARCH_DATASET_CHANGE_EVENT = 'clawblood:research-dataset-change'

export function readPersistedResearchDataset(): ActiveResearchDataset | null {
  if (typeof window === 'undefined') {
    return null
  }

  try {
    const raw = window.localStorage.getItem(RESEARCH_DATASET_STORAGE_KEY) ?? window.sessionStorage.getItem(RESEARCH_DATASET_STORAGE_KEY)
    return raw ? (JSON.parse(raw) as ActiveResearchDataset) : null
  } catch {
    window.localStorage.removeItem(RESEARCH_DATASET_STORAGE_KEY)
    window.sessionStorage.removeItem(RESEARCH_DATASET_STORAGE_KEY)
    return null
  }
}

export function persistResearchDataset(dataset: ActiveResearchDataset | null) {
  if (typeof window === 'undefined') {
    return
  }

  try {
    if (dataset) {
      const serialized = JSON.stringify(dataset)
      window.localStorage.setItem(RESEARCH_DATASET_STORAGE_KEY, serialized)
      window.sessionStorage.setItem(RESEARCH_DATASET_STORAGE_KEY, serialized)
    } else {
      window.localStorage.removeItem(RESEARCH_DATASET_STORAGE_KEY)
      window.sessionStorage.removeItem(RESEARCH_DATASET_STORAGE_KEY)
    }
  } catch {
    // Ignore storage quota or serialization errors and keep the in-memory state.
  }

  window.dispatchEvent(new Event(RESEARCH_DATASET_CHANGE_EVENT))
}

export function subscribeToResearchDatasetChanges(onStoreChange: () => void) {
  if (typeof window === 'undefined') {
    return () => {}
  }

  const handleChange = () => onStoreChange()

  window.addEventListener('storage', handleChange)
  window.addEventListener(RESEARCH_DATASET_CHANGE_EVENT, handleChange)

  return () => {
    window.removeEventListener('storage', handleChange)
    window.removeEventListener(RESEARCH_DATASET_CHANGE_EVENT, handleChange)
  }
}

function buildRawSeriesByColumn(uploadResult: UploadResponseShape) {
  return uploadResult.metabolites.reduce((acc, metabolite, index) => {
    const series = uploadResult.values[index] ?? []
    acc[metabolite] = series.map((value) => Number(value))
    return acc
  }, {} as Record<string, number[]>)
}

export function buildActiveResearchDataset(
  uploadResult: UploadResponseShape,
  mappingResult?: MappingResponseShape
): ActiveResearchDataset {
  const rawSeriesByColumn = buildRawSeriesByColumn(uploadResult)
  const mappings = mappingResult?.mappings ?? {}
  const mappedSeriesByMetabolite: Record<string, number[]> = {}

  for (const [column, mapping] of Object.entries(mappings)) {
    const series = rawSeriesByColumn[column]
    if (!series) {
      continue
    }

    if (!mappedSeriesByMetabolite[mapping.metabolite]) {
      mappedSeriesByMetabolite[mapping.metabolite] = series
    }
  }

  const mappedMetabolites = Object.keys(mappedSeriesByMetabolite)
  const datasetId =
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `${uploadResult.filename}-${Date.now()}`

  return {
    datasetId,
    source: 'custom_upload',
    mode: 'custom_user_data_mode',
    label: uploadResult.filename,
    fileName: uploadResult.filename,
    timePointCount: uploadResult.time_points.length,
    metaboliteCount: uploadResult.metabolites.length,
    mappedMetaboliteCount: mappedMetabolites.length,
    timePoints: uploadResult.time_points.map((value) => Number(value)),
    rawColumns: uploadResult.metabolites,
    rawSeriesByColumn,
    mappedMetabolites,
    mappedSeriesByMetabolite,
    mappings,
    preview: uploadResult.preview,
    activatedAt: new Date().toISOString(),
  }
}

export function summarizeResearchDataset(
  dataset: ActiveResearchDataset | null
): ResearchDatasetSummary {
  if (!dataset) {
    return {
      datasetId: 'bordbar-reference',
      source: 'bordbar_reference',
      mode: 'default_bordbar_mode',
      label: 'Bordbar reference dataset',
      fileName: undefined,
      timePointCount: 0,
      metaboliteCount: 0,
      mappedMetaboliteCount: 0,
    }
  }

  return {
    datasetId: dataset.datasetId,
    source: dataset.source,
    mode: dataset.mode,
    label: dataset.label,
    fileName: dataset.fileName,
    timePointCount: dataset.timePointCount,
    metaboliteCount: dataset.metaboliteCount,
    mappedMetaboliteCount: dataset.mappedMetaboliteCount,
  }
}

export function buildCalibrationExperimentPayload(
  dataset: ActiveResearchDataset
): CalibrationExperimentPayload {
  return {
    targetMetabolites: dataset.mappedMetabolites,
    expTime: dataset.timePoints,
    expData: dataset.mappedMetabolites.reduce((acc, metabolite) => {
      const series = dataset.mappedSeriesByMetabolite[metabolite]
      if (series) {
        acc[metabolite] = series
      }
      return acc
    }, {} as Record<string, number[]>),
  }
}

export function buildSimulationDatasetPayload(
  dataset: ActiveResearchDataset
): SimulationDatasetPayload {
  return {
    dataset_id: dataset.datasetId,
    source: dataset.source,
    mode: dataset.mode,
    label: dataset.label,
    file_name: dataset.fileName,
    time_points: dataset.timePoints.map((value) => Number(value)),
    mapped_metabolites: dataset.mappedMetabolites,
    mapped_series_by_metabolite: dataset.mappedMetabolites.reduce((acc, metabolite) => {
      const series = dataset.mappedSeriesByMetabolite[metabolite]
      if (series) {
        acc[metabolite] = series.map((value) => Number(value))
      }
      return acc
    }, {} as Record<string, number[]>),
  }
}
