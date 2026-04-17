export interface CalibrationPhaseBound {
  phase: number
  default_value: number
  lower_bound: number
  upper_bound: number
}

export interface CalibrationParameterEntry {
  name: string
  default_value: number
  classes: string[]
  identifiability: string
  phase_bounds: CalibrationPhaseBound[]
  recommended: boolean
  suggested_bounds: CalibrationPhaseBound
}

export interface CalibrationTaxonomySection {
  vmax_params: string[]
  km_params: string[]
}

export interface CalibrationStrategyChoice {
  value: string
  label: string
  description: string
  recommended: boolean
}

export interface CalibrationTaxonomyResponse {
  source: string
  taxonomy_version: string
  recommended: CalibrationTaxonomySection
  strategy_choices: CalibrationStrategyChoice[]
  strategy_default: string
  canonical: {
    vmax: CalibrationParameterEntry[]
    km: CalibrationParameterEntry[]
  }
  grouped_by_identifiability: {
    vmax: Record<string, string[]>
    km: Record<string, string[]>
  }
  class_counts: Record<string, number>
  identifiability_counts: Record<string, number>
  optimization_strategy_choices: string[]
  vmax_params: string[]
  km_params: string[]
  metabolite_names: string[]
}
