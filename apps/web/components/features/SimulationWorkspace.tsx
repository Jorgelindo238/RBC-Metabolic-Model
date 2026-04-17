'use client'

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { RoBoCopInterpretation, SimulationContext } from '@/types/robocop-context'
import type { SimulationParams, SimulationResult } from '@/hooks/use-simulation'
import { useSimulation } from '@/hooks/use-simulation'
import { MetaboliteChart } from './simulation/MetaboliteChart'
import { RoBoCopAssistant } from './robocop/RoBoCopAssistant'
import { buildSimulationContext, getSimulationKeyMetabolites } from '@/lib/robocop/simulation-context'
import { generateSimulationInterpretation } from '@/lib/robocop/interpretation-service'
import { buildSimulationResearchContext } from '@/lib/robocop/research-context-builders'
import { useResearchContext } from '@/contexts/ResearchContextProvider'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Loader2, Play, AlertCircle, CheckCircle2, Terminal } from 'lucide-react'
import { useResearchDataset } from '@/contexts/ResearchDatasetProvider'
import { buildSimulationDatasetPayload, summarizeResearchDataset } from '@/lib/research-dataset'
import { buildResearchSimulationSnapshot, persistLatestResearchSimulationSnapshot } from '@/lib/research-simulation'
import type { SimulationRequestMetadata } from '@/hooks/use-simulation'

function parseLogLine(message: string) {
  const match = message.match(/^\[(.*?)\]\s*(.*)$/)
  return {
    tag: match?.[1],
    body: match?.[2] ?? message,
  }
}

export function SimulationWorkspace() {
  const { params, updateParam, result, loading, error, run } = useSimulation()
  const { setContext } = useResearchContext()
  const { activeDataset, activeDatasetSummary, researchDataMode, activeCalibration } = useResearchDataset()
  const [selectedMetabolites, setSelectedMetabolites] = useState<string[]>([])
  const [robocopContext, setRobocopContext] = useState<SimulationContext | null>(null)
  const [robocopInterpretation, setRobocopInterpretation] = useState<RoBoCopInterpretation | null>(null)
  const [robocopLoading, setRobocopLoading] = useState(false)
  const [robocopError, setRobocopError] = useState<string | null>(null)
  const activeResultRef = useRef<SimulationResult | null>(null)
  const resultParamsRef = useRef<SimulationParams>(params)
  const suppressSelectionContextRef = useRef(false)
  const keyMetabolites = useMemo(() => {
    if (!result?.success) {
      return []
    }

    return getSimulationKeyMetabolites(result.metabolite_names)
  }, [result])

  const resolvedDataset = activeDataset
  const resolvedDatasetSummary = useMemo(() => summarizeResearchDataset(resolvedDataset), [resolvedDataset])
  const resolvedResearchDataMode = researchDataMode

  const activeSimulationDataset = useMemo(() => {
    if (resolvedResearchDataMode !== 'custom_user_data_mode' || !resolvedDataset) {
      return null
    }

    return buildSimulationDatasetPayload(resolvedDataset)
  }, [resolvedDataset, resolvedResearchDataMode])

  const activeCalibrationParams = useMemo(() => {
    if (!activeCalibration) {
      return null
    }

    if (activeCalibration.datasetId !== resolvedDatasetSummary.datasetId) {
      return null
    }

    if (activeCalibration.researchDataMode !== resolvedResearchDataMode) {
      return null
    }

    return activeCalibration.optimizedParams
  }, [activeCalibration, resolvedDatasetSummary.datasetId, resolvedResearchDataMode])

  const simulationRequestMetadata = useMemo<SimulationRequestMetadata>(() => {
    return {
      research_data_mode: resolvedResearchDataMode,
      active_dataset_id: resolvedDatasetSummary.datasetId,
      active_dataset_label: resolvedDatasetSummary.label,
      active_dataset: activeSimulationDataset,
      custom_params: activeCalibrationParams,
    }
  }, [
    activeCalibrationParams,
    activeSimulationDataset,
    resolvedDatasetSummary.datasetId,
    resolvedDatasetSummary.label,
    resolvedResearchDataMode,
  ])

  useEffect(() => {
    return () => {
      setContext(null)
    }
  }, [setContext])

  // Generate RoBoCop interpretation when a fresh simulation result arrives.
  useLayoutEffect(() => {
    if (!result?.success) {
      activeResultRef.current = null
      resultParamsRef.current = params
      suppressSelectionContextRef.current = false
      setSelectedMetabolites([])
      setRobocopContext(null)
      setRobocopInterpretation(null)
      setRobocopLoading(false)
      setRobocopError(null)
      setContext(null)
      return
    }

    if (activeResultRef.current === result) {
      return
    }

    activeResultRef.current = result
    resultParamsRef.current = params
    suppressSelectionContextRef.current = true
    setSelectedMetabolites(keyMetabolites)
    setRobocopLoading(true)
    setRobocopError(null)

    try {
      persistLatestResearchSimulationSnapshot(buildResearchSimulationSnapshot(result, resultParamsRef.current))
    } catch (snapshotErr) {
      console.warn('Failed to persist latest simulation snapshot', snapshotErr)
    }

    try {
      const interpretationContext = buildSimulationContext(result, params, keyMetabolites, resolvedDatasetSummary, activeCalibration)
      setRobocopContext(interpretationContext)
      const research = buildSimulationResearchContext(result, params, keyMetabolites, resolvedDatasetSummary, activeCalibration)
      setContext(research)
      setRobocopInterpretation(generateSimulationInterpretation(interpretationContext))
    } catch (err: unknown) {
      setRobocopError(err instanceof Error ? err.message : 'Failed to generate analysis')
    } finally {
      setRobocopLoading(false)
    }
  }, [activeCalibration, keyMetabolites, params, result, resolvedDatasetSummary, setContext])

  useLayoutEffect(() => {
    if (!result?.success || activeResultRef.current !== result) {
      return
    }

    if (suppressSelectionContextRef.current) {
      suppressSelectionContextRef.current = false
      return
    }

    const selection = selectedMetabolites.length > 0 ? selectedMetabolites : undefined
    const activeParams = resultParamsRef.current

    if (!activeParams) {
      return
    }

    const selectionContext = buildSimulationContext(result, activeParams, selection, resolvedDatasetSummary, activeCalibration)

    setRobocopContext(selectionContext)
    setRobocopInterpretation(generateSimulationInterpretation(selectionContext))
    setContext(buildSimulationResearchContext(result, activeParams, selection, resolvedDatasetSummary, activeCalibration))
  }, [activeCalibration, resolvedDatasetSummary, result, selectedMetabolites, setContext])

  return (
    <div className="relative isolate grid gap-5">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-72 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.12),transparent_42%),radial-gradient(circle_at_top_right,rgba(16,185,129,0.08),transparent_38%)]"
      />
        <Card>
          <CardHeader>
            <CardTitle>Simulation Controls</CardTitle>
            <CardDescription>Configure a storage-condition simulation to follow how RBC metabolite concentrations evolve over time. The model integrates ~200 reactions across glycolysis, PPP, nucleotide metabolism, and redox pathways.</CardDescription>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Badge
                variant={resolvedResearchDataMode === 'custom_user_data_mode' ? 'default' : 'secondary'}
                className="rounded-full"
              >
                {resolvedDatasetSummary.label}
              </Badge>
              {activeCalibrationParams ? (
                <Badge variant="default" className="rounded-full">
                  Calibrated ODE parameters active
                </Badge>
              ) : resolvedResearchDataMode === 'custom_user_data_mode' ? (
                <Badge variant="secondary" className="rounded-full">
                  Calibration required before simulation
                </Badge>
              ) : (
                <Badge variant="secondary" className="rounded-full">
                  Bordbar defaults active
                </Badge>
              )}
            </div>
          </CardHeader>
        <CardContent className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Storage Duration</Label>
              <Badge variant="secondary" className="font-mono text-[11px]">{params.t_max} days</Badge>
            </div>
            <Slider min={1} max={60} step={1} value={[params.t_max]} onValueChange={([v]) => updateParam('t_max', v)} />
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Curve Fit Strength</Label>
              <Badge variant="secondary" className="font-mono text-[11px]">{params.curve_fit_strength.toFixed(2)}</Badge>
            </div>
            <Slider min={0} max={1} step={0.05} value={[params.curve_fit_strength]} onValueChange={([v]) => updateParam('curve_fit_strength', v)} />
          </div>
          <div className="space-y-2">
            <Label>ODE Solver</Label>
            <Select value={params.solver_method} onValueChange={(v) => updateParam('solver_method', v)}>
              <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="RK45">RK45</SelectItem>
                <SelectItem value="BDF">BDF (stiff)</SelectItem>
                <SelectItem value="LSODA">LSODA (auto)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>pH Perturbation</Label>
            <Select value={params.ph_perturbation_type} onValueChange={(v) => updateParam('ph_perturbation_type', v)}>
              <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                {['None', 'Acidosis', 'Alkalosis', 'Step', 'Ramp'].map((v) => (
                  <SelectItem key={v} value={v}>{v}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {params.ph_perturbation_type !== 'None' && (
            <>
              <div className="space-y-2">
                <Label>pH Severity</Label>
                <Select value={params.ph_severity} onValueChange={(v) => updateParam('ph_severity', v)}>
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {['Mild', 'Moderate', 'Severe'].map((v) => (
                      <SelectItem key={v} value={v}>{v}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>pH Duration</Label>
                  <Badge variant="secondary" className="font-mono text-[11px]">{params.ph_duration} hrs</Badge>
                </div>
                <Slider min={1} max={24} step={0.5} value={[params.ph_duration]} onValueChange={([v]) => updateParam('ph_duration', v)} />
              </div>
            </>
          )}
        </CardContent>
        <CardFooter className="flex items-center gap-3 border-t pt-5">
          <Button
            onClick={() => run(simulationRequestMetadata)}
            disabled={loading}
            className="gap-2"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            {loading ? 'Running...' : 'Run Simulation'}
          </Button>
          {result?.success && (
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className="gap-1.5 text-emerald-600 border-emerald-200 bg-emerald-50">
                <CheckCircle2 className="h-3 w-3" />
                {result.duration.toFixed(1)}s — {result.n_points} pts, {result.n_metabolites} metabolites
              </Badge>
                <Badge
                  variant={result.dataset_applied ? 'default' : 'secondary'}
                  className="rounded-full"
                >
                  {result.dataset_applied
                  ? `Dataset applied: ${result.active_dataset_label ?? resolvedDatasetSummary.label}`
                  : resolvedResearchDataMode === 'custom_user_data_mode'
                    ? 'Custom mode pending dataset application'
                    : 'Bordbar default mode'}
                </Badge>
                {result.custom_params_source && (
                  <Badge
                    variant="outline"
                    className="rounded-full border-violet-300/20 bg-violet-400/10 text-violet-100"
                  >
                    {result.custom_params_source === 'provided'
                      ? 'Latest calibration parameters applied'
                      : result.custom_params_source === 'auto_loaded'
                        ? 'Auto-loaded calibration parameters'
                        : 'Default Bordbar parameters'}
                  </Badge>
                )}
              {result.dataset_fallback_reason && (
                <Badge variant="outline" className="rounded-full border-amber-200 bg-amber-50 text-amber-700">
                  {result.dataset_fallback_reason}
                </Badge>
              )}
            </div>
          )}
        </CardFooter>
      </Card>

      {error && (
        <Card className="border-destructive/40 bg-destructive/5">
          <CardContent className="flex items-start gap-3 pt-6">
            <AlertCircle className="h-5 w-5 text-destructive shrink-0" />
            <div>
              <p className="text-sm font-medium text-destructive">Simulation Error</p>
              <p className="text-xs text-destructive/70 mt-1 font-mono whitespace-pre-wrap">{error}</p>
            </div>
          </CardContent>
        </Card>
      )}

      {result?.success && (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.62fr)_minmax(320px,0.88fr)]">
          <MetaboliteChart
            result={result}
            selectedMetabolites={selectedMetabolites}
            onSelectionChange={setSelectedMetabolites}
          />

          <Card className="overflow-hidden border-white/10 bg-slate-950/70 shadow-2xl shadow-cyan-500/5">
            <CardHeader className="relative overflow-hidden border-b border-white/10 bg-[linear-gradient(180deg,rgba(15,23,42,0.96),rgba(15,23,42,0.8))] px-4 py-4 sm:px-5">
              <div
                aria-hidden="true"
                className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(34,211,238,0.12),transparent_35%),radial-gradient(circle_at_bottom_left,rgba(16,185,129,0.08),transparent_30%)]"
              />
              <div className="relative flex flex-col gap-3">
                <div className="flex items-center gap-2">
                  <Terminal className="h-4 w-4 text-cyan-300" />
                  <CardTitle className="text-white">Simulation Log</CardTitle>
                </div>
                <CardDescription className="max-w-xl text-slate-400">
                  Runtime milestones from the latest simulation run.
                </CardDescription>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline" className="rounded-full border-white/10 bg-white/5 text-slate-300">
                    {result.duration.toFixed(1)}s runtime
                  </Badge>
                  <Badge variant="outline" className="rounded-full border-white/10 bg-white/5 text-slate-300">
                    {result.solver}
                  </Badge>
                  <Badge variant="outline" className="rounded-full border-white/10 bg-white/5 text-slate-300">
                    {result.n_points} points
                  </Badge>
                  <Badge variant="outline" className="rounded-full border-white/10 bg-white/5 text-slate-300">
                    {params.ph_perturbation_type === 'None'
                      ? 'Baseline pH'
                      : `${params.ph_perturbation_type} · ${params.ph_severity}`}
                  </Badge>
                </div>
              </div>
            </CardHeader>
            <CardContent className="px-4 py-4 sm:px-5">
              <div className="max-h-[32rem] overflow-y-auto rounded-2xl border border-white/10 bg-slate-950/60 p-3">
                <div className="space-y-2">
                  {result.log?.length ? (
                    result.log.map((msg, i) => {
                      const { tag, body } = parseLogLine(msg)

                      return (
                        <div
                          key={i}
                          className="flex gap-3 rounded-xl border border-white/5 bg-white/[0.03] px-3 py-2.5"
                        >
                          <div className="mt-1 size-2 shrink-0 rounded-full bg-cyan-400/80 shadow-[0_0_0_4px_rgba(34,211,238,0.08)]" />
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              {tag && (
                                <span className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.22em] text-cyan-100">
                                  {tag}
                                </span>
                              )}
                              <p className="text-sm leading-6 text-slate-200">{body}</p>
                            </div>
                          </div>
                        </div>
                      )
                    })
                  ) : (
                    <p className="text-sm text-slate-400">No log output was returned for this run.</p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          <RoBoCopAssistant
            interpretation={robocopInterpretation}
            analysisContext={robocopContext}
            loading={robocopLoading}
            error={robocopError}
            onRefresh={() => run(simulationRequestMetadata)}
          />
        </div>
      )}
    </div>
  )
}
