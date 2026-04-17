import { getSupabase, hasSupabaseCredentials } from '../supabase.mjs'
import { buildCalibrationRunProductContext } from '../product-context.mjs'
import { getServerProductContext } from '../server-product-context.mjs'
import { buildRunScopeFilter, resolveServerRunAccess } from '../server-run-access.mjs'

const CALIBRATION_RUNS_LIST_SELECT = `
  run_id, canonical_run_label, registry_recorded_at, run_timestamp_utc, status,
  benchmark_status, completion_status, time_aware_score, case_count, completed_cases,
  total_cases, elapsed_seconds, time_budget_seconds, case_time_budget_seconds,
  coverage_ratio, coverage_weight_ratio, stop_reason, job_name, hypothesis,
  job_version, campaign, policy_name, manifest_name, optimization_strategy,
  target_scope, param_scope, aggregate_score, mean_final_loss, mean_improvement_pct,
  best_case, worst_case, tags, workspace_id, created_by_user_id, visibility, run_origin
`

const LEGACY_CALIBRATION_RUNS_LIST_SELECT = `
  run_id, canonical_run_label, registry_recorded_at, run_timestamp_utc, status, 
  policy_name, manifest_name, optimization_strategy, target_scope, param_scope, 
  aggregate_score, mean_final_loss, mean_improvement_pct, best_case, worst_case, tags
`

async function queryCalibrationRunsList(supabase, scope = null) {
  let query = supabase
    .from('calibration_runs')
    .select(CALIBRATION_RUNS_LIST_SELECT)

  if (scope) {
    query = query.or(buildRunScopeFilter(scope))
  }

  return query
    .order('run_timestamp_utc', { ascending: false })
    .limit(50)
}

async function queryLegacyCalibrationRunsList(supabase, scope = null) {
  let query = supabase
    .from('calibration_runs')
    .select(LEGACY_CALIBRATION_RUNS_LIST_SELECT)

  if (scope) {
    query = query.or(buildRunScopeFilter(scope))
  }

  return query
    .order('run_timestamp_utc', { ascending: false })
    .limit(50)
}

function shouldFallbackToLegacyCalibrationRuns(error) {
  const message = String(error?.message || error || '').toLowerCase()
  return message.includes('does not exist') || message.includes('column')
}

async function queryCalibrationRunDetail(supabase, runId, scope = null) {
  let query = supabase
    .from('calibration_runs')
    .select('*')
    .eq('run_id', runId)

  if (scope) {
    query = query.or(buildRunScopeFilter(scope))
  }

  return query.single()
}

/**
 * Domain projection: Builds a list item view model from a raw row
 */
export function buildCalibrationRunListItem(row) {
  if (!row) return null
  return {
    runId: row.run_id,
    label: row.canonical_run_label,
    recordedAt: row.registry_recorded_at,
    runTimestampUtc: row.run_timestamp_utc,
    status: row.status,
    benchmarkStatus: row.benchmark_status,
    completionStatus: row.completion_status,
    timeAwareScore: row.time_aware_score,
    caseCount: row.case_count,
    completedCases: row.completed_cases,
    totalCases: row.total_cases,
    elapsedSeconds: row.elapsed_seconds,
    timeBudgetSeconds: row.time_budget_seconds,
    caseTimeBudgetSeconds: row.case_time_budget_seconds,
    coverageRatio: row.coverage_ratio,
    coverageWeightRatio: row.coverage_weight_ratio,
    stopReason: row.stop_reason,
    jobName: row.job_name,
    hypothesis: row.hypothesis,
    jobVersion: row.job_version,
    campaign: row.campaign,
    policyName: row.policy_name,
    manifestName: row.manifest_name,
    optimizationStrategy: row.optimization_strategy,
    targetScope: row.target_scope,
    paramScope: row.param_scope,
    aggregateScore: row.aggregate_score,
    meanFinalLoss: row.mean_final_loss,
    meanImprovementPct: row.mean_improvement_pct,
    bestCase: row.best_case,
    worstCase: row.worst_case,
    tags: row.tags || [],
    productContext: buildCalibrationRunProductContext(row),
  }
}

/**
 * Domain projection: Builds a detailed view model from a raw row
 */
export function buildCalibrationRunDetailViewModel(row) {
  if (!row) return null
  return {
    summary: {
      runId: row.run_id,
      label: row.canonical_run_label,
      status: row.status,
      benchmarkStatus: row.benchmark_status,
      completionStatus: row.completion_status,
      recordedAt: row.registry_recorded_at,
      runTimestampUtc: row.run_timestamp_utc,
      aggregateScore: row.aggregate_score,
      meanFinalLoss: row.mean_final_loss,
      meanImprovementPct: row.mean_improvement_pct,
      bestCase: row.best_case,
      worstCase: row.worst_case,
      caseCount: row.case_count,
      timeAwareScore: row.time_aware_score,
      completedCases: row.completed_cases,
      totalCases: row.total_cases,
      elapsedSeconds: row.elapsed_seconds,
      timeBudgetSeconds: row.time_budget_seconds,
      caseTimeBudgetSeconds: row.case_time_budget_seconds,
      coverageRatio: row.coverage_ratio,
      coverageWeightRatio: row.coverage_weight_ratio,
      stopReason: row.stop_reason,
      jobName: row.job_name,
      hypothesis: row.hypothesis,
      jobVersion: row.job_version,
      campaign: row.campaign,
    },
    scientificContext: {
      policyName: row.policy_name,
      manifestName: row.manifest_name,
      optimizationStrategy: row.optimization_strategy,
      targetScope: row.target_scope,
      paramScope: row.param_scope,
      parameterClasses: row.parameter_classes,
      targetScopes: row.target_scopes,
      paramScopes: row.param_scopes,
    },
    artifacts: {
      manifestPath: row.artifact_manifest_path,
      refs: row.artifact_refs,
    },
    productContext: buildCalibrationRunProductContext(row),
    robocopContext: {
      traceContext: row.trace_context || {},
      chatContext: row.chat_context || {},
    },
  }
}

/**
 * API abstraction: Fetches all calibration runs.
 * Uses a live Supabase connection if configured.
 * @returns {Promise<{data: Array, error: string|null, missingCredentials: boolean}>}
 */
export async function getCalibrationRuns() {
  if (!hasSupabaseCredentials()) {
    return { data: [], error: null, missingCredentials: true }
  }

  const supabase = getSupabase()
  
  if (!supabase) {
    return { data: [], error: 'Supabase client initialization failed', missingCredentials: false }
  }

  const { data, error } = await queryCalibrationRunsList(supabase)

  if (error && shouldFallbackToLegacyCalibrationRuns(error)) {
    const legacyResponse = await queryLegacyCalibrationRunsList(supabase)

    if (legacyResponse.error) {
      console.error('Failed to load legacy calibration_runs fallback from Supabase:', legacyResponse.error.message)
      return { data: [], error: legacyResponse.error.message, missingCredentials: false }
    }

    return {
      data: (legacyResponse.data || []).map(buildCalibrationRunListItem),
      error: null,
      missingCredentials: false,
    }
  }

  if (error) {
    console.error('Failed to load calibration_runs from Supabase:', error.message)
    return { data: [], error: error.message, missingCredentials: false }
  }

  return { 
    data: (data || []).map(buildCalibrationRunListItem), 
    error: null, 
    missingCredentials: false 
  }
}

/**
 * API abstraction: Fetches a calibration run by its ID.
 * Uses a live Supabase connection if configured.
 * @returns {Promise<{data: Object|null, error: string|null, missingCredentials: boolean}>}
 */
export async function getCalibrationRunById(runId) {
  if (!hasSupabaseCredentials()) {
    return { data: null, error: null, missingCredentials: true }
  }

  const supabase = getSupabase()
  
  if (!supabase) {
    return { data: null, error: 'Supabase client initialization failed', missingCredentials: false }
  }

  const { data, error } = await queryCalibrationRunDetail(supabase, runId)

  if (error || !data) {
    console.error(`Failed to load calibration_run ${runId} from Supabase:`, error?.message)
    return { data: null, error: error?.message || 'Run not found', missingCredentials: false }
  }

  return { 
    data: buildCalibrationRunDetailViewModel(data), 
    error: null, 
    missingCredentials: false 
  }
}

export async function getCalibrationRunsForServerRequest() {
  const productContext = await getServerProductContext()
  const access = resolveServerRunAccess(productContext)

  if (access.mode === 'credentials_missing') {
    return { data: [], error: null, missingCredentials: true, productContext, access }
  }

  if (access.mode === 'auth_error' || access.mode === 'product_context_error') {
    return {
      data: [],
      error: access.error || 'Failed to resolve authenticated product context.',
      missingCredentials: false,
      productContext,
      access,
    }
  }

  if (access.mode === 'anonymous_public' || access.mode === 'transitional_public_fallback') {
    const response = await getCalibrationRuns()
    return { ...response, productContext, access }
  }

  const { data, error } = await queryCalibrationRunsList(productContext.supabase, access.scope)

  if (error && shouldFallbackToLegacyCalibrationRuns(error)) {
    const legacyResponse = await queryLegacyCalibrationRunsList(productContext.supabase, access.scope)

    if (legacyResponse.error) {
      return {
        data: [],
        error: legacyResponse.error.message || 'Failed to load calibration runs.',
        missingCredentials: false,
        productContext,
        access,
      }
    }

    return {
      data: (legacyResponse.data || []).map(buildCalibrationRunListItem),
      error: null,
      missingCredentials: false,
      productContext,
      access: {
        ...access,
        mode: 'transitional_public_fallback',
        fallbackMode: 'legacy_read_model',
        error: error.message,
      },
    }
  }

  if (error) {
    return { data: [], error: error.message, missingCredentials: false, productContext, access }
  }

  return {
    data: (data || []).map(buildCalibrationRunListItem),
    error: null,
    missingCredentials: false,
    productContext,
    access,
  }
}

export async function getCalibrationRunByIdForServerRequest(runId) {
  const productContext = await getServerProductContext()
  const access = resolveServerRunAccess(productContext)

  if (access.mode === 'credentials_missing') {
    return { data: null, error: null, missingCredentials: true, productContext, access }
  }

  if (access.mode === 'auth_error' || access.mode === 'product_context_error') {
    return {
      data: null,
      error: access.error || 'Failed to resolve authenticated product context.',
      missingCredentials: false,
      productContext,
      access,
    }
  }

  if (access.mode === 'anonymous_public' || access.mode === 'transitional_public_fallback') {
    const response = await getCalibrationRunById(runId)
    return { ...response, productContext, access }
  }

  const { data, error } = await queryCalibrationRunDetail(productContext.supabase, runId, access.scope)

  if (error && isProductSchemaUnavailableError(error)) {
    const response = await getCalibrationRunById(runId)
    return {
      ...response,
      productContext,
      access: {
        ...access,
        mode: 'transitional_public_fallback',
        fallbackMode: 'public_read_model',
        error: error.message,
      },
    }
  }

  if (error || !data) {
    return {
      data: null,
      error: error?.message || 'Run not found',
      missingCredentials: false,
      productContext,
      access,
    }
  }

  return {
    data: buildCalibrationRunDetailViewModel(data),
    error: null,
    missingCredentials: false,
    productContext,
    access,
  }
}
