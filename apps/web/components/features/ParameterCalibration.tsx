'use client'

import { useState, useCallback, useEffect, useMemo } from 'react'
import { apiClient } from '@/lib/api-client'
import { useResearchContext } from '@/contexts/ResearchContextProvider'
import { buildCalibrationResearchContext } from '@/lib/robocop/research-context-builders'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Loader2, Target, AlertCircle, CheckCircle2, ChevronDown, ChevronUp } from 'lucide-react'
import { useResearchDataset } from '@/contexts/ResearchDatasetProvider'
import { buildCalibrationExperimentPayload, summarizeResearchDataset } from '@/lib/research-dataset'
import { buildActiveResearchCalibration } from '@/lib/research-calibration'
import {
  buildCalibrationSelectionProvenance,
  getCalibrationRunStatusLabel,
  getCalibrationRunStatusLine,
  getCalibrationSelectionModeLabel,
  type CalibrationRunStatus,
} from '@/lib/robocop/calibration-provenance'
import type {
  CalibrationParameterEntry,
  CalibrationTaxonomyResponse,
} from '@/types/calibration-taxonomy'

interface CalibrationResult {
  success: boolean
  message: string
  optimized_params: Record<string, number>
  all_optimized_params?: Record<string, number>
  initial_params: Record<string, number>
  objective_value: number
  iterations: number
  r_squared: number
  confidence_intervals: Record<string, [number, number]>
  sensitivity: Record<string, number>
  optimization_strategy?: string
  baseline_loss?: number
  final_loss?: number
  improvement_pct?: number
  run_duration_seconds?: number
  calibration_status?: CalibrationRunStatus
  calibration_completed?: boolean
  calibration_failed?: boolean
  result_summary?: string
  custom_data_plan?: {
    recommended_strategy?: string
    target_scope?: string
    notes?: string[]
    rationale?: string[]
    dangerous_compensators_present?: string[]
    parameter_additions?: string[]
  } | null
  triage?: {
    overall?: string
    reason?: string
    discard_triggers?: string[]
    keep_signals?: string[]
    caveats?: string[]
    next_best_experiment?: string | null
  } | null
  pure_ode_triage?: {
    overall?: string
    reason?: string
    recommendation?: string
    skipped?: boolean
    skip_reason?: string | null
    collapse_signals?: string[]
    concern_signals?: string[]
    healthy_signals?: string[]
    caveats?: string[]
  } | null
  combined_triage?: {
    overall?: string
    reason?: string
    recommendation?: string
    discard_triggers?: string[]
    caveats?: string[]
  } | null
  orchestration?: {
    mode?: string
    winner_strategy?: string
    winner_verdict?: string
    strategies_considered?: string[]
    memory_hits?: string[]
    runs?: Array<{
      strategy: string
      verdict?: string
      final_loss?: number
      improvement_pct?: number
      r_squared?: number
      result_summary?: string
    }>
    teacher_flux_rescue?: {
      status?: string
      reason?: string
      reactions?: string[]
      distillation?: {
        recommended_params_path?: string | null
      } | null
    } | null
  } | null
}

interface CalibrationJobCreateResponse {
  jobId: string
  status: string
  createdAt: string
}

interface CalibrationJobRecord {
  jobId: string
  status: string
  createdAt: string
  updatedAt: string
  result: CalibrationResult | null
  error?: string | null
}

const CALIBRATION_JOB_POLL_INTERVAL_MS = 2500
const CALIBRATION_JOB_MAX_WAIT_MS = 2 * 60 * 60 * 1000
const CALIBRATION_JOB_MAX_POLL_ATTEMPTS = Math.ceil(
  CALIBRATION_JOB_MAX_WAIT_MS / CALIBRATION_JOB_POLL_INTERVAL_MS
)

function triageBadgeVariant(
  verdict?: string
): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (verdict === 'healthy' || verdict === 'keep') {
    return 'default'
  }
  if (verdict === 'compromised' || verdict === 'keep_with_caveats' || verdict === 'needs_review') {
    return 'secondary'
  }
  if (verdict === 'collapsed' || verdict === 'discard') {
    return 'destructive'
  }
  return 'outline'
}

function ParamToggleGroup({
  title,
  params,
  selected,
  toggle,
}: {
  title: string
  params: string[]
  selected: string[]
  toggle: (p: string) => void
}) {
  return (
    <div className="space-y-2">
      <Label className="text-[11px] uppercase tracking-[0.3em] text-muted-foreground">{title}</Label>
      <div className="flex flex-wrap gap-1.5">
        {params.length ? (
          params.map((p) => (
            <Badge
              key={p}
              variant={selected.includes(p) ? 'default' : 'outline'}
              className="cursor-pointer font-mono text-[10px] uppercase tracking-[0.08em]"
              onClick={() => toggle(p)}
            >
              {p}
            </Badge>
          ))
        ) : (
          <span className="text-xs text-muted-foreground">None available</span>
        )}
      </div>
    </div>
  )
}

function identifiabilityVariant(level: string): 'default' | 'secondary' | 'destructive' {
  if (level === 'core') {
    return 'default'
  }
  if (level === 'caution') {
    return 'secondary'
  }
  return 'destructive'
}

function phaseSummary(entry: CalibrationParameterEntry) {
  if (!entry.phase_bounds.length) {
    return 'n/a'
  }
  return entry.phase_bounds.map((item) => `P${item.phase}`).join(' · ')
}

function ParameterInventoryTable({
  title,
  description,
  entries,
  selected,
  toggle,
}: {
  title: string
  description: string
  entries: CalibrationParameterEntry[]
  selected: string[]
  toggle: (p: string) => void
}) {
  const sortedEntries = useMemo(
    () =>
      [...entries].sort(
        (a, b) => Number(b.recommended) - Number(a.recommended) || a.name.localeCompare(b.name)
      ),
    [entries]
  )

  return (
    <div className="rounded-2xl border border-border/60 bg-background/40">
      <div className="border-b border-border/60 px-4 py-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h4 className="text-sm font-semibold">{title}</h4>
            <p className="text-xs text-muted-foreground">{description}</p>
          </div>
          <Badge variant="outline" className="font-mono text-[10px] uppercase tracking-[0.12em]">
            {sortedEntries.length} params
          </Badge>
        </div>
      </div>
      <div className="max-h-[420px] overflow-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Parameter</TableHead>
              <TableHead className="text-right">Default</TableHead>
              <TableHead className="text-right">Suggested bounds</TableHead>
              <TableHead>Tag</TableHead>
              <TableHead className="text-right">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedEntries.map((entry) => {
              const isSelected = selected.includes(entry.name)
              const suggested = entry.suggested_bounds
              return (
                <TableRow key={entry.name}>
                  <TableCell>
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs font-medium">{entry.name}</span>
                        {entry.recommended ? (
                          <Badge
                            variant="secondary"
                            className="h-5 rounded-full px-2 font-mono text-[9px] uppercase tracking-[0.12em]"
                          >
                            Recommended
                          </Badge>
                        ) : null}
                      </div>
                      <p className="text-[11px] text-muted-foreground">Phases: {phaseSummary(entry)}</p>
                    </div>
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs">
                    {suggested.default_value.toFixed(4)}
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs">
                    {suggested.lower_bound.toFixed(4)} - {suggested.upper_bound.toFixed(4)}
                  </TableCell>
                  <TableCell>
                    <Badge variant={identifiabilityVariant(entry.identifiability)} className="uppercase">
                      {entry.identifiability}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      size="sm"
                      variant={isSelected ? 'default' : 'outline'}
                      className="h-8 px-3"
                      onClick={() => toggle(entry.name)}
                    >
                      {isSelected ? 'Selected' : 'Add'}
                    </Button>
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

export function ParameterCalibration() {
  const { setContext } = useResearchContext()
  const { activeDataset, activeCalibration, researchDataMode, activateCalibration } = useResearchDataset()
  const resolvedDataset = activeDataset
  const resolvedDatasetSummary = useMemo(() => summarizeResearchDataset(resolvedDataset), [resolvedDataset])
  const resolvedResearchDataMode = researchDataMode
  const [availableParams, setAvailableParams] = useState<CalibrationTaxonomyResponse | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [optimizationStrategy, setOptimizationStrategy] = useState('joint_vmax_km')
  const [maxIter, setMaxIter] = useState(100)
  const [loading, setLoading] = useState(false)
  const [loadingParams, setLoadingParams] = useState(true)
  const [result, setResult] = useState<CalibrationResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showCanonical, setShowCanonical] = useState(false)
  const [targetMetabolites, setTargetMetabolites] = useState<string[]>([])
  const [executionMode, setExecutionMode] = useState<'single_run' | 'strategy_race'>('strategy_race')
  const [rerunPureOde, setRerunPureOde] = useState(true)
  const [enableTeacherFluxRescue, setEnableTeacherFluxRescue] = useState(true)
  const [jobId, setJobId] = useState<string | null>(null)
  const [jobStatus, setJobStatus] = useState<string | null>(null)

  useEffect(() => {
    return () => {
      setContext(null)
    }
  }, [setContext])

  useEffect(() => {
    apiClient
      .get<CalibrationTaxonomyResponse>('/calibration/available-parameters')
      .then((r) => setAvailableParams(r.data))
      .catch(() => setError('Failed to load parameters'))
      .finally(() => setLoadingParams(false))
  }, [])

  useEffect(() => {
    if (!availableParams?.strategy_default) {
      return
    }
    setOptimizationStrategy((current) =>
      current === 'joint_vmax_km' || current === 'differential_evolution'
        ? availableParams.strategy_default
        : current
    )
  }, [availableParams])

  useEffect(() => {
    if (!activeCalibration) {
      return
    }

    setSelected(activeCalibration.selectedParameters ?? [])
    setOptimizationStrategy(
      activeCalibration.selectedOptimizationStrategy ??
        activeCalibration.optimizationStrategy ??
        activeCalibration.method ??
        optimizationStrategy
    )
    setMaxIter(activeCalibration.maxIterations ?? maxIter)
    setTargetMetabolites(activeCalibration.targetMetabolites ?? [])
  }, [activeCalibration])

  const toggle = useCallback(
    (p: string) =>
      setSelected((prev) => (prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p])),
    []
  )

  const canonicalLookup = useMemo(() => {
    const lookup = new Map<string, CalibrationParameterEntry>()
    for (const entry of availableParams?.canonical?.vmax ?? []) {
      lookup.set(entry.name, entry)
    }
    for (const entry of availableParams?.canonical?.km ?? []) {
      lookup.set(entry.name, entry)
    }
    return lookup
  }, [availableParams])

  const selectionPreviewParameters =
    selected.length > 0 ? selected : activeCalibration?.selectedParameters ?? selected
  const selectionPreviewStrategy =
    optimizationStrategy ||
    activeCalibration?.selectedOptimizationStrategy ||
    activeCalibration?.optimizationStrategy ||
    optimizationStrategy

  const selectionProvenance = useMemo(
    () => buildCalibrationSelectionProvenance(selectionPreviewParameters, selectionPreviewStrategy, availableParams),
    [availableParams, selectionPreviewParameters, selectionPreviewStrategy]
  )

  const calibrationStatus = useMemo<CalibrationRunStatus>(() => {
    if (loading) {
      return 'running'
    }

    if (result?.success) {
      return 'completed'
    }

    if (activeCalibration?.calibrationStatus) {
      return activeCalibration.calibrationStatus
    }

    if (activeCalibration?.calibrationCompleted) {
      return 'completed'
    }

    if (activeCalibration?.calibrationFailed) {
      return 'failed'
    }

    if (error) {
      return 'failed'
    }

    return 'setup_only'
  }, [activeCalibration, error, loading, result?.success])

  const recommendedVmax = availableParams?.recommended?.vmax_params ?? availableParams?.vmax_params ?? []
  const recommendedKm = availableParams?.recommended?.km_params ?? availableParams?.km_params ?? []
  const canonicalVmax = availableParams?.canonical?.vmax ?? []
  const canonicalKm = availableParams?.canonical?.km ?? []
  const classCounts = availableParams?.class_counts ?? {}
  const identifiabilityCounts = availableParams?.identifiability_counts ?? {}

  const buildParamBounds = useCallback(
    (paramName: string): [number, number, number] => {
      const entry = canonicalLookup.get(paramName)
      if (entry) {
        const bounds = entry.suggested_bounds
        return [bounds.default_value, bounds.lower_bound, bounds.upper_bound]
      }
      return paramName.startsWith('vmax_') ? [1.0, 0.01, 100.0] : [0.5, 0.001, 50.0]
    },
    [canonicalLookup]
  )

  const calibrationContext = useMemo(
    () =>
      buildCalibrationResearchContext(
        result,
        selected,
        selectionProvenance.selectedOptimizationStrategy,
        maxIter,
        targetMetabolites,
        resolvedDatasetSummary,
        availableParams,
        activeCalibration,
        calibrationStatus,
        error
      ),
    [
      availableParams,
      activeCalibration,
      calibrationStatus,
      error,
      maxIter,
      resolvedDatasetSummary,
      result,
      selected,
      selectionProvenance.selectedOptimizationStrategy,
      targetMetabolites,
    ]
  )

  useEffect(() => {
    setContext(calibrationContext)
  }, [calibrationContext, setContext])

  const run = useCallback(async () => {
    if (!selected.length) {
      setError('Select at least one parameter.')
      return
    }
    setLoading(true)
    setError(null)
    setResult(null)
    setJobId(null)
    setJobStatus(null)
    try {
      let expData: Record<string, number[]> = {}
      let targetMets: string[] = []
      let timePoints: number[] = []

      if (resolvedResearchDataMode === 'custom_user_data_mode' && resolvedDataset) {
        const payload = buildCalibrationExperimentPayload(resolvedDataset)
        if (!payload.targetMetabolites.length) {
          setError('Uploaded dataset has no mapped metabolites available for calibration.')
          setLoading(false)
          return
        }
        expData = payload.expData
        targetMets = payload.targetMetabolites
        timePoints = payload.expTime
      } else {
        const expRes = await apiClient.get('/data/experimental')
        const { metabolites, time_points, values } = expRes.data
        for (let i = 0; i < Math.min(metabolites.length, 10); i++) {
          expData[metabolites[i]] = values[i]
          targetMets.push(metabolites[i])
        }
        timePoints = time_points
      }
      setTargetMetabolites(targetMets)

      const paramsToOpt: Record<string, number[]> = {}
      for (const p of selected) {
        paramsToOpt[p] = buildParamBounds(p)
      }

      const payload = {
        target_metabolites: targetMets,
        exp_time: timePoints,
        exp_data: expData,
        params_to_optimize: paramsToOpt,
        optimization_strategy: optimizationStrategy,
        max_iterations: maxIter,
        t_max: 42,
        research_data_mode: resolvedDatasetSummary.mode,
        active_dataset_id: resolvedDatasetSummary.datasetId,
        active_dataset_label: resolvedDatasetSummary.label,
        rerun_pure_ode: rerunPureOde,
        orchestration_mode: executionMode,
        enable_strategy_memory: executionMode === 'strategy_race',
        enable_teacher_flux_rescue: executionMode === 'strategy_race' ? enableTeacherFluxRescue : false,
      }

      let resolvedResult: CalibrationResult | null = null
      if (executionMode === 'strategy_race') {
        const job = await apiClient.post<CalibrationJobCreateResponse>('/calibration/jobs', payload)
        setJobId(job.data.jobId)
        setJobStatus(job.data.status)

        let attempts = 0
        while (attempts < CALIBRATION_JOB_MAX_POLL_ATTEMPTS) {
          const jobRecord = await apiClient.get<CalibrationJobRecord>(`/calibration/jobs/${job.data.jobId}`)
          setJobStatus(jobRecord.data.status)
          if (jobRecord.data.status === 'completed' && jobRecord.data.result) {
            resolvedResult = jobRecord.data.result
            break
          }
          if (jobRecord.data.status === 'failed') {
            throw new Error(jobRecord.data.error || 'Calibration worker job failed')
          }
          attempts += 1
          await new Promise((resolve) => window.setTimeout(resolve, CALIBRATION_JOB_POLL_INTERVAL_MS))
        }

        if (!resolvedResult) {
          throw new Error(
            `Calibration worker job ${job.data.jobId} is still running after ${Math.round(
              CALIBRATION_JOB_MAX_WAIT_MS / 60000
            )} minutes. The worker may still finish; keep the job ID to inspect it from the server.`
          )
        }
      } else {
        const res = await apiClient.post<CalibrationResult>('/calibration/run', payload)
        resolvedResult = res.data
      }

      setResult(resolvedResult)
      activateCalibration(
        buildActiveResearchCalibration(
          resolvedResult,
          selected,
          optimizationStrategy,
          maxIter,
          targetMets,
          resolvedDatasetSummary,
          availableParams
        )
      )
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Calibration failed')
    } finally {
      setLoading(false)
    }
  }, [
    activateCalibration,
    buildParamBounds,
    enableTeacherFluxRescue,
    executionMode,
    availableParams,
    optimizationStrategy,
    maxIter,
    rerunPureOde,
    resolvedDataset,
    resolvedDatasetSummary,
    resolvedResearchDataMode,
    selected,
  ])

  const canonicalStrategyChoices = availableParams?.optimization_strategy_choices ?? []
  const strategyChoices =
    availableParams?.strategy_choices?.length
      ? availableParams.strategy_choices
      : canonicalStrategyChoices.map((value) => ({
          value,
          label: value.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase()),
          description: '',
          recommended: value === 'joint_vmax_km',
        }))
  const selectedStrategyChoice = strategyChoices.find((choice) => choice.value === optimizationStrategy)
  const identifiabilityRiskCount = identifiabilityCounts.compensation_risk ?? 0
  const selectionModeLabel = getCalibrationSelectionModeLabel(selectionProvenance)
  const calibrationStateLabel = getCalibrationRunStatusLabel(calibrationContext.calibrationStatus)
  const calibrationSummaryLine =
    calibrationContext.resultSummary ??
    getCalibrationRunStatusLine(
      calibrationContext.calibrationStatus,
      calibrationContext.resultSummary ?? null,
      calibrationContext.fitMetrics ?? null
    )

  return (
    <div className="grid gap-5">
      <Card>
        <CardHeader>
          <CardTitle>Parameter Selection</CardTitle>
          <CardDescription>
            Choose enzyme kinetic parameters (Vmax, Km) to optimize against experimental RBC storage data.
            The quick-pick set is derived from the canonical MM_calibration registry, and the advanced view
            exposes the full canonical inventory with phase-specific suggested bounds.
          </CardDescription>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Badge
              variant={resolvedResearchDataMode === 'custom_user_data_mode' ? 'default' : 'secondary'}
              className="rounded-full"
            >
              {resolvedDatasetSummary.label}
            </Badge>
            {availableParams ? (
              <Badge variant="outline" className="rounded-full font-mono text-[10px] uppercase tracking-[0.12em]">
                {availableParams.source} · {availableParams.taxonomy_version}
              </Badge>
            ) : null}
            <Badge variant="outline" className="rounded-full">
              {selectionProvenance.strategyLabel}
            </Badge>
            <Badge variant="outline" className="rounded-full">
              {selectionProvenance.selectedParameterFamilies.length
                ? selectionProvenance.selectedParameterFamilies.join(' · ')
                : 'No families selected'}
            </Badge>
            <Badge
              variant={selectionProvenance.isRecommendedSubset ? 'default' : 'secondary'}
              className="rounded-full"
            >
              {selectionPreviewParameters.length > 0 ? selectionModeLabel : 'No parameters selected'}
            </Badge>
            {calibrationStateLabel ? (
              <Badge variant="outline" className="rounded-full">
                {calibrationStateLabel}
              </Badge>
            ) : null}
            <Badge variant="outline" className="rounded-full">
              {selectionPreviewParameters.length} selected
            </Badge>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            {selectionPreviewParameters.length > 0
              ? `Optimizing ${selectionPreviewParameters.length} parameter${selectionPreviewParameters.length === 1 ? '' : 's'} across ${selectionProvenance.selectedParameterFamilies.join(' and ') || 'canonical Vmax/Km'} with ${selectionProvenance.strategyLabel}.`
              : `Select canonical ${selectionProvenance.selectedParameterFamilies.join(' and ') || 'Vmax/Km'} parameters to start calibration.`}
          </p>
          {calibrationContext.calibrationStatus !== 'setup_only' || calibrationContext.resultSummary ? (
            <div className="mt-4 rounded-2xl border border-border/60 bg-background/60 px-4 py-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline" className="rounded-full">
                  {calibrationStateLabel}
                </Badge>
                {calibrationContext.strategyUsed ? (
                  <Badge variant="secondary" className="rounded-full">
                    {calibrationContext.inputs.strategyLabel ?? calibrationContext.strategyUsed.replace(/_/g, ' ')}
                  </Badge>
                ) : null}
                {typeof calibrationContext.fitMetrics?.rSquared === 'number' ? (
                  <Badge variant="outline" className="rounded-full">
                    R² {calibrationContext.fitMetrics.rSquared.toFixed(3)}
                  </Badge>
                ) : null}
                {typeof calibrationContext.fitMetrics?.improvementPct === 'number' ? (
                  <Badge variant="outline" className="rounded-full">
                    {calibrationContext.fitMetrics.improvementPct.toFixed(1)}% improvement
                  </Badge>
                ) : null}
                {typeof calibrationContext.runDurationSeconds === 'number' ? (
                  <Badge variant="outline" className="rounded-full">
                    {calibrationContext.runDurationSeconds.toFixed(1)}s
                  </Badge>
                ) : null}
              </div>
              <p className="mt-2 text-xs leading-5 text-muted-foreground">{calibrationSummaryLine}</p>
            </div>
          ) : null}
        </CardHeader>
        <CardContent className="space-y-5">
          {loadingParams ? (
            <div className="flex items-center gap-2 py-4 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading canonical parameter taxonomy...
            </div>
          ) : availableParams ? (
            <div className="space-y-4">
              <div className="grid gap-4 lg:grid-cols-[1.08fr_0.92fr]">
                <div className="rounded-2xl border border-border/60 bg-background/40 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">Recommended</p>
                      <h3 className="mt-1 text-sm font-semibold">Default quick-picks</h3>
                    </div>
                    <Badge variant="outline" className="rounded-full font-mono text-[10px] uppercase tracking-[0.12em]">
                      {recommendedVmax.length + recommendedKm.length} ready
                    </Badge>
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Curated from the canonical registry for a fast start.
                  </p>
                  <div className="mt-4 space-y-4">
                    <ParamToggleGroup
                      title={`Recommended Vmax (${recommendedVmax.length})`}
                      params={recommendedVmax}
                      selected={selected}
                      toggle={toggle}
                    />
                    <ParamToggleGroup
                      title={`Recommended Km (${recommendedKm.length})`}
                      params={recommendedKm}
                      selected={selected}
                      toggle={toggle}
                    />
                  </div>
                </div>

                <div className="rounded-2xl border border-border/60 bg-background/40 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">Advanced</p>
                      <h3 className="mt-1 text-sm font-semibold">Canonical inventory</h3>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="gap-2"
                      onClick={() => setShowCanonical((prev) => !prev)}
                    >
                      {showCanonical ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                      {showCanonical ? 'Hide inventory' : 'Show inventory'}
                    </Button>
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Browse every canonical Vmax/Km entry from <span className="font-mono">MM_calibration</span> with phase-specific suggested bounds.
                  </p>
                  <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-5">
                    <div className="rounded-xl border border-border/60 bg-background/60 px-3 py-2">
                      <p className="text-[10px] uppercase tracking-[0.3em] text-muted-foreground">Vmax</p>
                      <p className="mt-1 font-mono text-sm">{classCounts.vmax ?? canonicalVmax.length}</p>
                    </div>
                    <div className="rounded-xl border border-border/60 bg-background/60 px-3 py-2">
                      <p className="text-[10px] uppercase tracking-[0.3em] text-muted-foreground">Km</p>
                      <p className="mt-1 font-mono text-sm">{classCounts.km ?? canonicalKm.length}</p>
                    </div>
                    <div className="rounded-xl border border-border/60 bg-background/60 px-3 py-2">
                      <p className="text-[10px] uppercase tracking-[0.3em] text-muted-foreground">Core</p>
                      <p className="mt-1 font-mono text-sm">{identifiabilityCounts.core ?? 0}</p>
                    </div>
                    <div className="rounded-xl border border-border/60 bg-background/60 px-3 py-2">
                      <p className="text-[10px] uppercase tracking-[0.3em] text-muted-foreground">Caution</p>
                      <p className="mt-1 font-mono text-sm">{identifiabilityCounts.caution ?? 0}</p>
                    </div>
                    <div className="rounded-xl border border-border/60 bg-background/60 px-3 py-2">
                      <p className="text-[10px] uppercase tracking-[0.3em] text-muted-foreground">Risk</p>
                      <p className="mt-1 font-mono text-sm">{identifiabilityRiskCount}</p>
                    </div>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-1.5">
                    {strategyChoices.map((choice) => (
                      <Badge
                        key={choice.value}
                        variant={choice.recommended ? 'default' : 'outline'}
                        className="rounded-full font-mono text-[10px] tracking-[0.08em]"
                      >
                        {choice.label}
                      </Badge>
                    ))}
                  </div>
                  <div className="mt-4 text-sm text-muted-foreground">
                    {showCanonical ? (
                      <span>The full inventory is open below, grouped into Vmax and Km tables.</span>
                    ) : (
                      <span>Open the full inventory to browse every canonical parameter and its suggested bounds.</span>
                    )}
                  </div>
                </div>
              </div>

              {showCanonical ? (
                <div className="grid gap-4 xl:grid-cols-2">
                  <ParameterInventoryTable
                    title="Canonical Vmax"
                    description="All canonical Vmax parameters exposed by MM_calibration."
                    entries={canonicalVmax}
                    selected={selected}
                    toggle={toggle}
                  />
                  <ParameterInventoryTable
                    title="Canonical Km"
                    description="All canonical Km parameters exposed by MM_calibration."
                    entries={canonicalKm}
                    selected={selected}
                    toggle={toggle}
                  />
                </div>
              ) : null}
            </div>
          ) : null}
        </CardContent>
        <CardFooter className="flex flex-wrap items-center gap-3 border-t pt-5">
          <div className="flex min-w-[260px] flex-col gap-1">
            <Label className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
              Optimization Strategy
            </Label>
            <Select value={optimizationStrategy} onValueChange={setOptimizationStrategy}>
              <SelectTrigger className="w-[260px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {strategyChoices.map((choice) => (
                  <SelectItem key={choice.value} value={choice.value}>
                    {choice.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-[11px] text-muted-foreground">
              {selectedStrategyChoice?.description ||
                'Choose the canonical calibration family used by MM_calibration.'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Label className="text-xs shrink-0">Max iter</Label>
            <Input
              type="number"
              value={maxIter}
              onChange={(e) => setMaxIter(parseInt(e.target.value) || 100)}
              className="h-9 w-20"
            />
          </div>
          <div className="flex min-w-[220px] flex-col gap-1">
            <Label className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
              Execution Mode
            </Label>
            <Select
              value={executionMode}
              onValueChange={(value) => setExecutionMode(value as 'single_run' | 'strategy_race')}
            >
              <SelectTrigger className="w-[220px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="single_run">Single run</SelectItem>
                <SelectItem value="strategy_race">Worker strategy race</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-[11px] text-muted-foreground">
              {executionMode === 'strategy_race'
                ? 'Runs multiple strategies in the worker, reuses dataset memory, and can trigger teacher-flux rescue.'
                : 'Runs one calibration immediately in the API path.'}
            </p>
          </div>
          <div className="flex flex-col gap-2 rounded-2xl border border-border/60 bg-background/40 px-3 py-2">
            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              <input
                type="checkbox"
                checked={rerunPureOde}
                onChange={(event) => setRerunPureOde(event.target.checked)}
              />
              Run pure ODE replay
            </label>
            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              <input
                type="checkbox"
                checked={enableTeacherFluxRescue}
                onChange={(event) => setEnableTeacherFluxRescue(event.target.checked)}
                disabled={executionMode !== 'strategy_race'}
              />
              Enable teacher-flux rescue
            </label>
          </div>
          <div className="flex flex-col gap-1">
            <Button onClick={run} disabled={loading || !selected.length} className="gap-2">
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Target className="h-4 w-4" />}
              {loading
                ? executionMode === 'strategy_race'
                  ? 'Running worker campaign...'
                  : 'Calibrating...'
                : executionMode === 'strategy_race'
                  ? `Launch worker race (${selected.length})`
                  : `Calibrate (${selected.length})`}
            </Button>
            {jobId ? (
              <p className="max-w-[320px] break-all font-mono text-[11px] text-muted-foreground">
                Job {jobId} · {jobStatus ?? 'queued'}
              </p>
            ) : null}
          </div>
          </CardFooter>
      </Card>

      {error ? (
        <Card className="border-destructive/40 bg-destructive/5">
          <CardContent className="flex items-start gap-3 pt-6">
            <AlertCircle className="h-5 w-5 shrink-0 text-destructive" />
            <p className="text-sm text-destructive">{error}</p>
          </CardContent>
        </Card>
      ) : null}

      {result ? (
        <Card>
          <CardHeader>
            <CardTitle>Results</CardTitle>
            <CardDescription>
              {result.success ? (
                <span className="flex items-center gap-1.5 text-emerald-600">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  {result.message} — R² = {result.r_squared.toFixed(4)}, {result.iterations} iter
                </span>
              ) : (
                <span className="text-destructive">{result.message}</span>
              )}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            {result.orchestration ? (
              <div className="rounded-2xl border border-border/60 bg-background/40 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline" className="rounded-full">
                    {result.orchestration.mode ?? 'strategy_race'}
                  </Badge>
                  {result.orchestration.winner_strategy ? (
                    <Badge variant="default" className="rounded-full">
                      Winner {result.orchestration.winner_strategy}
                    </Badge>
                  ) : null}
                  {result.orchestration.winner_verdict ? (
                    <Badge variant={triageBadgeVariant(result.orchestration.winner_verdict)} className="rounded-full">
                      {result.orchestration.winner_verdict}
                    </Badge>
                  ) : null}
                </div>
                <p className="mt-3 text-sm text-muted-foreground">
                  Strategy race evaluated {result.orchestration.strategies_considered?.length ?? 0} candidates.
                  {result.orchestration.memory_hits?.length
                    ? ` Warm-started from ${result.orchestration.memory_hits.length} prior memory hit(s).`
                    : ' No prior memory hits were available for this dataset fingerprint.'}
                </p>
                {result.orchestration.runs?.length ? (
                  <div className="mt-3 grid gap-2 md:grid-cols-2">
                    {result.orchestration.runs.map((run) => (
                      <div key={run.strategy} className="rounded-xl border border-border/50 bg-background/60 p-3">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-mono text-xs">{run.strategy}</span>
                          <Badge variant={triageBadgeVariant(run.verdict)} className="rounded-full">
                            {run.verdict ?? 'pending'}
                          </Badge>
                        </div>
                        <p className="mt-2 text-xs text-muted-foreground">
                          Loss {typeof run.final_loss === 'number' ? run.final_loss.toFixed(4) : 'n/a'} · R²{' '}
                          {typeof run.r_squared === 'number' ? run.r_squared.toFixed(3) : 'n/a'}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : null}
                {result.orchestration.teacher_flux_rescue ? (
                  <div className="mt-4 rounded-xl border border-border/50 bg-background/60 p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge
                        variant={result.orchestration.teacher_flux_rescue.status === 'completed' ? 'default' : 'outline'}
                        className="rounded-full"
                      >
                        Teacher-flux {result.orchestration.teacher_flux_rescue.status ?? 'skipped'}
                      </Badge>
                      {result.orchestration.teacher_flux_rescue.reactions?.map((reaction) => (
                        <Badge key={reaction} variant="outline" className="rounded-full">
                          {reaction}
                        </Badge>
                      ))}
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">
                      {result.orchestration.teacher_flux_rescue.reason ??
                        'Teacher-flux rescue artifacts were prepared for the winner.'}
                    </p>
                  </div>
                ) : null}
              </div>
            ) : null}

            {result.custom_data_plan || result.triage ? (
              <div className="rounded-2xl border border-border/60 bg-background/40 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  {result.custom_data_plan?.recommended_strategy ? (
                    <Badge variant="outline" className="rounded-full">
                      Planner {result.custom_data_plan.recommended_strategy}
                    </Badge>
                  ) : null}
                  {result.triage?.overall ? (
                    <Badge variant={triageBadgeVariant(result.triage.overall)} className="rounded-full">
                      Curve triage {result.triage.overall}
                    </Badge>
                  ) : null}
                </div>
                {result.triage?.reason ? (
                  <p className="mt-3 text-sm text-muted-foreground">{result.triage.reason}</p>
                ) : null}
                {result.custom_data_plan?.rationale?.length ? (
                  <ul className="mt-3 space-y-1 text-xs text-muted-foreground">
                    {result.custom_data_plan.rationale.slice(0, 3).map((item) => (
                      <li key={item}>- {item}</li>
                    ))}
                  </ul>
                ) : null}
                {result.triage?.discard_triggers?.length ? (
                  <div className="mt-3">
                    <p className="text-[11px] uppercase tracking-[0.2em] text-destructive">Discard triggers</p>
                    <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
                      {result.triage.discard_triggers.slice(0, 3).map((item) => (
                        <li key={item}>- {item}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : null}

            {result.pure_ode_triage ? (
              <div className="rounded-2xl border border-border/60 bg-background/40 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={triageBadgeVariant(result.pure_ode_triage.overall)} className="rounded-full">
                    Pure ODE {result.pure_ode_triage.overall ?? 'pending'}
                  </Badge>
                  {result.pure_ode_triage.skipped ? (
                    <Badge variant="outline" className="rounded-full">
                      rerun unavailable
                    </Badge>
                  ) : null}
                  {result.combined_triage?.overall ? (
                    <Badge variant={triageBadgeVariant(result.combined_triage.overall)} className="rounded-full">
                      Combined {result.combined_triage.overall}
                    </Badge>
                  ) : null}
                </div>
                <p className="mt-3 text-sm text-muted-foreground">
                  {result.pure_ode_triage.reason ?? 'Pure ODE triage not available.'}
                </p>
                {result.combined_triage?.reason ? (
                  <p className="mt-2 text-sm text-muted-foreground">
                    Combined verdict: {result.combined_triage.reason}
                  </p>
                ) : null}
                {result.pure_ode_triage.recommendation ? (
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">
                    {result.pure_ode_triage.recommendation}
                  </p>
                ) : null}
                {result.pure_ode_triage.collapse_signals?.length ? (
                  <div className="mt-3">
                    <p className="text-[11px] uppercase tracking-[0.2em] text-destructive">Collapse signals</p>
                    <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
                      {result.pure_ode_triage.collapse_signals.slice(0, 3).map((signal) => (
                        <li key={signal}>- {signal}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {result.pure_ode_triage.concern_signals?.length ? (
                  <div className="mt-3">
                    <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">Concern signals</p>
                    <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
                      {result.pure_ode_triage.concern_signals.slice(0, 3).map((signal) => (
                        <li key={signal}>- {signal}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : null}

            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Parameter</TableHead>
                  <TableHead className="text-right">Initial</TableHead>
                  <TableHead className="text-right">Optimised</TableHead>
                  <TableHead className="text-right">Change</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {Object.entries(result.optimized_params).map(([name, val]) => {
                  const init = result.initial_params[name] || 0
                  const pct = init ? ((val - init) / init) * 100 : 0
                  return (
                    <TableRow key={name}>
                      <TableCell className="font-mono text-xs">{name}</TableCell>
                      <TableCell className="text-right font-mono text-xs">{init.toFixed(4)}</TableCell>
                      <TableCell className="text-right font-mono text-xs font-semibold">{val.toFixed(4)}</TableCell>
                      <TableCell
                        className={`text-right font-mono text-xs ${
                          pct > 0 ? 'text-emerald-600' : pct < 0 ? 'text-red-500' : ''
                        }`}
                      >
                        {pct > 0 ? '+' : ''}
                        {pct.toFixed(1)}%
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}
