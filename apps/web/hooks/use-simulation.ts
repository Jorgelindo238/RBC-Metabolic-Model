'use client'

import { useState, useCallback } from 'react'
import { apiClient } from '@/lib/api-client'
import type { ResearchDataMode, SimulationDatasetPayload } from '@/types/research-dataset'
import { buildResearchSimulationSnapshot, persistLatestResearchSimulationSnapshot } from '@/lib/research-simulation'

export interface SimulationParams {
  t_max: number
  curve_fit_strength: number
  solver_method: string
  rtol: number
  atol: number
  ph_perturbation_type: string
  ph_severity: string
  ph_target: number
  ph_duration: number
}

export interface SimulationRequestMetadata {
  research_data_mode?: ResearchDataMode
  active_dataset_id?: string
  active_dataset_label?: string
  active_dataset?: SimulationDatasetPayload | null
  custom_params?: Record<string, number> | null
}

export const DEFAULT_PARAMS: SimulationParams = {
  t_max: 42,
  curve_fit_strength: 0.0,
  solver_method: 'RK45',
  rtol: 1e-6,
  atol: 1e-8,
  ph_perturbation_type: 'None',
  ph_severity: 'Moderate',
  ph_target: 7.0,
  ph_duration: 6.0,
}

export interface SimulationResult {
  success: boolean
  duration: number
  t: number[]
  x: number[][]
  metabolite_names: string[]
  n_points: number
  n_metabolites: number
  solver: string
  custom_params_source?: 'provided' | 'defaults' | 'auto_loaded'
  log: string[]
  research_data_mode?: ResearchDataMode
  active_dataset_id?: string | null
  active_dataset_label?: string | null
  dataset_applied?: boolean
  dataset_fallback_reason?: string | null
  dataset_applied_metabolites?: string[]
  flux_data?: {
    times: number[]
    fluxes: Record<string, number[]>
  } | null
  experimental_data?: {
    source?: string
    time: number[]
    metabolites: string[]
    values: number[][]
  }
  reference_data?: {
    source?: string
    time: number[]
    metabolites: string[]
    values: number[][]
  }
}

export function useSimulation() {
  const [params, setParams] = useState<SimulationParams>(DEFAULT_PARAMS)
  const [result, setResult] = useState<SimulationResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const updateParam = useCallback(
    <K extends keyof SimulationParams>(key: K, value: SimulationParams[K]) => {
      setParams((prev) => ({ ...prev, [key]: value }))
    },
    []
  )

  const run = useCallback(async (metadata: SimulationRequestMetadata = {}) => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await apiClient.post<SimulationResult>('/simulate/', { ...params, ...metadata })
      setResult(res.data)
      persistLatestResearchSimulationSnapshot(buildResearchSimulationSnapshot(res.data, params))
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Simulation failed')
    } finally {
      setLoading(false)
    }
  }, [params])

  return { params, updateParam, result, loading, error, run }
}
