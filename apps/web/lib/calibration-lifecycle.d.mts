export declare const LIFECYCLE_VERSION: 'calibration-lifecycle/1'

export type LifecycleState =
  | 'invalid_data'
  | 'incompatible_engine'
  | 'ready_for_test'
  | 'running'
  | 'numerical_failure'
  | 'rejected_candidate'
  | 'admissible_candidate'

export declare const LIFECYCLE_STATES: readonly LifecycleState[]

export interface FreeOdeOutcome {
  available: boolean
  verdict: string | null
  reason: string | null
}

export interface ClassifiedRecord {
  version: string
  state: LifecycleState
  reason: string
  finished: boolean
  biologicallyValidated: false
  legacy: boolean
  parameterContract?: string
  dataContractStatus?: string
  freeOde?: FreeOdeOutcome
}

export interface LifecycleRecordInput {
  preflight?: { data_valid?: boolean; launch_allowed?: boolean } | null
  job?: { status?: string; error?: string | null; completed_cases?: number; total_cases?: number } | null
  result?: Record<string, any> | null
  active?: boolean
  activation?: { explicit?: boolean; runIdentity?: RunIdentity; activeIdentity?: RunIdentity }
}

export interface RunIdentity {
  datasetId?: string | null
  subjectId?: string | null
  contractFingerprint?: string | null
}

export interface ActivationDecision {
  allowed: boolean
  reasons: string[]
  biologicallyValidated: false
}

export interface SeparatedScores {
  fit: {
    source: 'calibration_objective'
    finalLoss: number | null
    baselineLoss: number | null
    improvementPct: number | null
    rSquared: number | null
    verdict: string | null
    teacherFluxRescue: 'present' | 'absent'
  }
  freeOde: { source: 'pure_ode_replay' } & FreeOdeOutcome
}

export interface MonitoringView {
  state: LifecycleState
  label: string
  reason: string
  finished: boolean
  biologicallyValidated: false
  active: boolean
  progress: { completed: number; total: number; fraction: number } | null
  scores: SeparatedScores | null
}

export type JourneyStep = 'data' | 'verification' | 'calibration' | 'results'

export declare const JOURNEY_STEPS: readonly JourneyStep[]

export declare function classifyCalibrationRecord(record?: LifecycleRecordInput): ClassifiedRecord
export declare function separateScores(result: Record<string, any> | null | undefined): SeparatedScores
export declare function activationDecision(
  classified: ClassifiedRecord | null | undefined,
  request?: { explicit?: boolean; runIdentity?: RunIdentity | null; activeIdentity?: RunIdentity | null }
): ActivationDecision
export declare function monitoringView(record?: LifecycleRecordInput): MonitoringView
export declare function journeyFor(
  state: LifecycleState | string
): Array<{ step: JourneyStep; status: 'done' | 'current' | 'blocked' | 'pending' }>
export declare function lifecycleLabel(state: LifecycleState | string): string
