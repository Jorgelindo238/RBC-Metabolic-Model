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
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import { Label } from '@/components/ui/label'
import { Loader2, Play, AlertCircle } from 'lucide-react'
import { WithInspector } from '@/components/platform/research/Inspector'
import { useResearchDataset } from '@/contexts/ResearchDatasetProvider'
import { buildSimulationDatasetPayload, summarizeResearchDataset } from '@/lib/research-dataset'
import { buildResearchSimulationSnapshot, persistLatestResearchSimulationSnapshot } from '@/lib/research-simulation'
import type { SimulationRequestMetadata } from '@/hooks/use-simulation'

const DEFAULT_PLOTTED_METABOLITES = ['EGLC', 'ELAC', 'ATP'] as const

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
  const defaultPlottedMetabolites = useMemo(() => {
    if (!result?.success) {
      return []
    }

    const available = new Set(result.metabolite_names)
    return DEFAULT_PLOTTED_METABOLITES.filter((metabolite) => available.has(metabolite))
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
    if (!activeCalibration || activeCalibration.datasetProvenance.calibratedParametersActive !== true) {
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
    setSelectedMetabolites(defaultPlottedMetabolites)
    setRobocopLoading(true)
    setRobocopError(null)

    try {
      persistLatestResearchSimulationSnapshot(buildResearchSimulationSnapshot(result, resultParamsRef.current))
    } catch (snapshotErr) {
      console.warn('Failed to persist latest simulation snapshot', snapshotErr)
    }

    try {
      const interpretationContext = buildSimulationContext(result, params, defaultPlottedMetabolites, resolvedDatasetSummary, activeCalibration)
      setRobocopContext(interpretationContext)
      const research = buildSimulationResearchContext(result, params, defaultPlottedMetabolites, resolvedDatasetSummary, activeCalibration)
      setContext(research)
      setRobocopInterpretation(generateSimulationInterpretation(interpretationContext))
    } catch (err: unknown) {
      setRobocopError(err instanceof Error ? err.message : 'Failed to generate analysis')
    } finally {
      setRobocopLoading(false)
    }
  }, [activeCalibration, defaultPlottedMetabolites, params, result, resolvedDatasetSummary, setContext])

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

  const customMode = resolvedResearchDataMode === 'custom_user_data_mode'
  const paramLabel = (value: number) => (Number.isFinite(value) ? String(value) : '—')
  const requestedParameterSource = activeCalibrationParams
    ? 'Explicitly active calibration parameters for this dataset'
    : 'Bordbar default parameters (no active calibration)'
  const reportedParameterSource = result?.custom_params_source === 'provided'
    ? 'Parameters provided in the request'
    : result?.custom_params_source === 'auto_loaded'
      ? 'Parameters auto-loaded by the engine'
      : result?.custom_params_source === 'defaults'
        ? 'Bordbar default parameters'
        : 'Not reported by the engine'

  const inspector = (
    <dl className="research-review" data-testid="simulation-provenance">
      <div><dt>Dataset context</dt><dd>{resolvedDatasetSummary.label} ({customMode ? 'uploaded data' : 'reference data'})</dd></div>
      <div><dt>Requested parameters</dt><dd>{requestedParameterSource}</dd></div>
      {result?.success ? <div><dt>Engine parameters</dt><dd>{reportedParameterSource}</dd></div> : null}
      <div><dt>Upload in the request</dt><dd>{customMode
        ? 'Sent as context. It counts as applied to the ODE only if the result reports it.'
        : 'None'}</dd></div>
      {result?.success ? <>
        <div><dt>Dataset applied by the engine</dt><dd>{result.dataset_applied
          ? `Yes: ${result.active_dataset_label ?? resolvedDatasetSummary.label}` : 'No'}</dd></div>
        {result.custom_params_source ? <div><dt>Parameter source reported</dt><dd>{result.custom_params_source}</dd></div> : null}
        {result.dataset_fallback_reason ? <div><dt>Fallback reason</dt><dd>{result.dataset_fallback_reason}</dd></div> : null}
        <div><dt>Solver</dt><dd>{result.solver}</dd></div>
        <div><dt>Output</dt><dd>{result.n_points} points · {result.n_metabolites} metabolites · {result.duration.toFixed(1)} s runtime</dd></div>
      </> : <div><dt>Result</dt><dd>No run in this session</dd></div>}
      <div><dt>Note</dt><dd>A completed run is a model trajectory, not a biological validation.</dd></div>
    </dl>
  )

  return (
    <WithInspector title="Run details" anchorId="simulation-details" inspector={inspector}>
      <div className="r-split" data-testid="research-simulation">
        <section id="scenario-setup" className="r-settings" aria-label="Run settings">
          <h2>Run settings</h2>
          <div className="grid gap-2">
            <div className="flex items-center justify-between gap-3">
              <Label id="sim-duration-label">Storage duration</Label>
              <span className="r-num text-[13px]">{paramLabel(params.t_max)} days</span>
            </div>
            <Slider aria-labelledby="sim-duration-label" min={2} max={60} step={1} value={[params.t_max]}
              onValueChange={([v]) => updateParam('t_max', v)} />
          </div>
          <div className="grid gap-2">
            <div className="flex items-center justify-between gap-3">
              <Label id="sim-fit-label">Curve fit strength</Label>
              <span className="r-num text-[13px]">{params.curve_fit_strength.toFixed(2)}</span>
            </div>
            <Slider aria-labelledby="sim-fit-label" min={0} max={1} step={0.05} value={[params.curve_fit_strength]}
              onValueChange={([v]) => updateParam('curve_fit_strength', v)} />
          </div>
          <div className="grid gap-2">
            <Label>pH perturbation</Label>
            <Select value={params.ph_perturbation_type} onValueChange={(v) => updateParam('ph_perturbation_type', v)}>
              <SelectTrigger className="w-full" aria-label="pH perturbation"><SelectValue /></SelectTrigger>
              <SelectContent>
                {['None', 'Acidosis', 'Alkalosis', 'Step', 'Ramp'].map((v) => (
                  <SelectItem key={v} value={v}>{v}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {params.ph_perturbation_type !== 'None' && (
            <>
              <div className="grid gap-2">
                <Label>pH severity</Label>
                <Select value={params.ph_severity} onValueChange={(v) => updateParam('ph_severity', v)}>
                  <SelectTrigger className="w-full" aria-label="pH severity"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {['Mild', 'Moderate', 'Severe'].map((v) => (
                      <SelectItem key={v} value={v}>{v}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <div className="flex items-center justify-between gap-3">
                  <Label id="sim-ph-duration-label">pH duration</Label>
                  <span className="r-num text-[13px]">{params.ph_duration} hrs</span>
                </div>
                <Slider aria-labelledby="sim-ph-duration-label" min={1} max={24} step={0.5} value={[params.ph_duration]}
                  onValueChange={([v]) => updateParam('ph_duration', v)} />
              </div>
            </>
          )}
          <details className="research-disclosure">
            <summary>Solver</summary>
            <div className="grid gap-2">
              <Label>ODE solver</Label>
              <Select value={params.solver_method} onValueChange={(v) => updateParam('solver_method', v)}>
                <SelectTrigger className="w-full" aria-label="ODE solver"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="RK45">RK45</SelectItem>
                  <SelectItem value="BDF">BDF (stiff)</SelectItem>
                  <SelectItem value="LSODA">LSODA (auto)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </details>
          <p className="r-legend">
            Requested parameters: {activeCalibrationParams ? 'active calibration' : 'Bordbar defaults'}
            {customMode ? ' · upload sent as context' : ''}
          </p>
          <Button onClick={() => run(simulationRequestMetadata)} disabled={loading} className="r-primary gap-2">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            {loading ? 'Running...' : 'Run Simulation'}
          </Button>
        </section>

        <section id="trajectory-review" className="grid gap-4" aria-label="Trajectories and log" aria-busy={loading}>
          <h2>Trajectories</h2>
          {loading ? (
            <p className="research-empty" role="status"><Loader2 className="h-4 w-4 animate-spin" />
              Running the model. The solver reports no progress, so none is shown.</p>
          ) : null}
          {error ? (
            <div role="alert" className="grid gap-1" data-testid="simulation-error">
              <p className="flex items-center gap-2 text-sm font-medium text-destructive"><AlertCircle className="h-4 w-4 shrink-0" />Simulation error</p>
              <p className="font-mono text-xs whitespace-pre-wrap text-destructive/80">{error}</p>
              <p className="r-legend">Settings are kept; adjust them and run again.</p>
            </div>
          ) : null}
          {!result && !loading && !error ? <p className="research-empty" data-testid="simulation-empty">No simulation yet. Choose settings and run the model.</p> : null}
          {result?.success ? (
            <>
              <p className="r-legend" data-testid="simulation-summary">
                Completed in {result.duration.toFixed(1)} s · {result.n_points} points · {result.n_metabolites} metabolites · {result.solver}
                {' · '}{result.dataset_applied ? 'dataset applied by the engine' : 'reference inputs'}
              </p>
              <MetaboliteChart
                result={result}
                selectedMetabolites={selectedMetabolites}
                onSelectionChange={setSelectedMetabolites}
              />
              <details className="research-disclosure">
                <summary>Run log ({result.log?.length ?? 0})</summary>
                {result.log?.length ? (
                  <ol className="grid max-h-[28rem] gap-1 overflow-y-auto text-[13px]">
                    {result.log.map((msg, i) => {
                      const { tag, body } = parseLogLine(msg)
                      return (
                        <li key={i} className="flex gap-3 border-b border-white/5 py-1.5">
                          {tag ? <span className="shrink-0 font-mono text-xs text-[color:var(--r-text-3)]">{tag}</span> : null}
                          <span className="min-w-0 break-words">{body}</span>
                        </li>
                      )
                    })}
                  </ol>
                ) : (
                  <p className="research-muted">No log output was returned for this run.</p>
                )}
              </details>
              <details className="research-disclosure">
                <summary>Interpretation</summary>
                <RoBoCopAssistant
                  interpretation={robocopInterpretation}
                  analysisContext={robocopContext}
                  loading={robocopLoading}
                  error={robocopError}
                  onRefresh={() => run(simulationRequestMetadata)}
                />
              </details>
            </>
          ) : null}
        </section>
      </div>
    </WithInspector>
  )
}
