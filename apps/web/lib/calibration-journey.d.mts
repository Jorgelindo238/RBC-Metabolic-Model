export declare const CONTRACT_SCHEMA: 'airbc.user_calibration_data/1'
export declare const REFERENCE_VIEW_SCHEMA: 'airbc.reference_profile_view/1'
export declare const FOCUS_CHANNELS: readonly string[]
export declare const DRAFT_MISSING_FIELDS: readonly string[]

export interface DraftContract {
  contract: Record<string, any>
  missing: string[]
}

export type PreflightState = 'not_checked' | 'preflight_unavailable' | 'invalid_data' | 'incompatible_engine' | 'ready_for_test'

export interface PreflightView {
  state: PreflightState
  dataValid: boolean | null
  engineCompatible: boolean | null
  launchAllowed: boolean
  errors?: Array<{ code: string; path: string; message: string }>
  warnings?: Array<{ code: string; path: string; message: string }>
  blocking?: Array<{ code: string; path: string; message: string }>
  engine?: string | null
  conversionsPerformed?: unknown[]
  initialStateSubstituted?: boolean
  donorsMerged?: boolean
}

export interface ReferenceProfileView {
  state: string
  available: boolean
  reason?: string | null
  releaseStatus?: string | null
  nextTask?: string | null
  [key: string]: any
}

export interface SeriesPoint {
  day: number
  observed: number | null
  predicted: number | null
  residual: number | null
  normalizedResidual: number | null
  unit: string | null
}

export interface FocusRow {
  channel: string
  normalizedRmse: number | null
  j15Residual: number | null
  slopePredicted: number | null
  slopeObserved: number | null
  slopeError: number | null
}

export type RunProgress = { mode: 'determinate'; completed: number; total: number; fraction: number } | { mode: 'indeterminate' }

export declare function draftDataContract(
  datasetId: string | null | undefined,
  experiment: { expTime?: number[]; expData?: Record<string, number[]> } | null | undefined
): DraftContract
export declare function preflightView(report: Record<string, any> | null | undefined): PreflightView
export declare function launchGate(view: PreflightView | null | undefined): {
  contractLaunchAllowed: boolean
  reason: string | null
  legacyLabel: string
}
export declare function referenceProfileView(payload: Record<string, any> | null | undefined): ReferenceProfileView
export declare function referenceActivation(
  profile: ReferenceProfileView | null | undefined,
  request?: { explicit?: boolean; runIdentity?: Record<string, any>; activeIdentity?: Record<string, any> }
): { allowed: boolean; reasons: string[] }
export declare function speciesSeries(profile: ReferenceProfileView | null | undefined, species: string): SeriesPoint[]
export declare function speciesList(profile: ReferenceProfileView | null | undefined, compartment?: string | null): string[]
export declare function focusSummary(profile: ReferenceProfileView | null | undefined): FocusRow[]
export declare function limitationNotes(profile: ReferenceProfileView | null | undefined): string[]
export declare function monitoringRunState(run: Record<string, any> | null | undefined): {
  state: 'running' | 'failed' | 'cancelled' | 'finished_unverified' | 'unknown'
  label: string
  progress: RunProgress | null
}
export declare function runProgress(run: Record<string, any> | null | undefined): RunProgress
export declare function interpretPersistedCalibration<T extends Record<string, any>>(record: T | null | undefined): (T & {
  activationStatus: 'legacy_unverified' | 'not_activated'
  legacyFlags?: { calibrationApplied: boolean; calibratedParametersActive: boolean }
}) | null
