'use client'

import { useState, useCallback, useEffect, useMemo } from 'react'
import type { ActiveResearchDataset } from '@/types/research-dataset'
import { apiClient } from '@/lib/api-client'
import { PATHWAY_COLORS, PATHWAY_GROUPS } from './flux/FluxBarChart'
import { Button } from '@/components/ui/button'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { Loader2, BarChart3, AlertCircle } from 'lucide-react'
import { WithInspector } from '@/components/platform/research/Inspector'
import { useResearchContext } from '@/contexts/ResearchContextProvider'
import { useResearchDataset } from '@/contexts/ResearchDatasetProvider'
import { summarizeResearchDataset } from '@/lib/research-dataset'
import { buildFluxAnalysisResearchContext } from '@/lib/robocop/research-context-builders'
import {
  getCalibrationStatusLabel,
  getFluxAnalysisProvenanceSummary,
  getFluxAnalysisStatusLabel,
  getFluxAnalysisStatusLine,
} from '@/lib/robocop/research-provenance'

const DEFAULT_FLUX_CONCENTRATIONS: Record<string, number> = {
  GLC: 5.0,
  G6P: 0.05,
  F6P: 0.015,
  F16BP: 0.003,
  DHCP: 0.01,
  GA3P: 0.005,
  B13PG: 0.0005,
  P3G: 0.06,
  P2G: 0.01,
  PEP: 0.015,
  PYR: 0.07,
  LAC: 2.0,
  ATP: 1.5,
  ADP: 0.4,
  AMP: 0.05,
  NAD: 0.05,
  NADH: 0.001,
  NADP: 0.003,
  NADPH: 0.05,
  B23PG: 4.5,
  GSH: 3.0,
  GSSG: 0.003,
  GL6P: 0.01,
  RU5P: 0.02,
  R5P: 0.01,
  X5P: 0.01,
  S7P: 0.01,
  E4P: 0.005,
  GO6P: 0.01,
}


function buildFluxConcentrationSnapshot(dataset: ActiveResearchDataset | null) {
  const concentrations = { ...DEFAULT_FLUX_CONCENTRATIONS }
  if (!dataset || dataset.mode !== 'custom_user_data_mode') {
    return {
      concentrations,
      source: 'bordbar_reference' as const,
      appliedMetabolites: [] as string[],
      fallbackReason: null as string | null,
    }
  }

  const appliedMetabolites: string[] = []
  for (const metabolite of Object.keys(concentrations)) {
    const series = dataset.mappedSeriesByMetabolite[metabolite]
    if (!series || series.length === 0) {
      continue
    }

    const lastValue = Number(series[series.length - 1])
    if (Number.isFinite(lastValue)) {
      concentrations[metabolite] = lastValue
      appliedMetabolites.push(metabolite)
    }
  }

  return {
    concentrations,
    source: 'custom_upload' as const,
    appliedMetabolites,
    fallbackReason:
      appliedMetabolites.length > 0
        ? null
        : 'Custom data mode active but no flux-model concentrations were mapped',
  }
}

function formatFluxValue(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—'
  }

  const absValue = Math.abs(value)
  if (absValue >= 100 || absValue < 0.01) {
    return value.toExponential(2)
  }

  return value.toFixed(3)
}

/**
 * Pathway flux rows: fixed-size text (never scaled down with the viewport), height grows with the
 * number of reactions, bars centred on zero so signs stay visible. Display formatting only:
 * the exact value returned by the API stays available in the title attribute.
 */
function FluxPathwayRows({
  pathway,
  rank,
  fluxes,
  pathwayTotal,
  dominantPathway,
}: {
  pathway: string
  rank: number
  fluxes: Record<string, number>
  pathwayTotal: number
  dominantPathway: string
}) {
  const reactions = PATHWAY_GROUPS[pathway] ?? []
  const reactionSignals = reactions
    .map((reaction) => ({ reaction, flux: fluxes[reaction] ?? 0 }))
    .filter((signal) => signal.flux !== 0)
  const ranked = [...reactionSignals].sort((left, right) => Math.abs(right.flux) - Math.abs(left.flux))
  const topSignal = ranked[0]
  const maxAbs = Math.max(...reactionSignals.map((signal) => Math.abs(signal.flux)), Number.MIN_VALUE)
  const color = PATHWAY_COLORS[pathway] ?? '#64748b'
  const isDominant = pathway === dominantPathway

  return (
    <section className="grid gap-2 border-b border-[color:var(--r-line)] pb-4" aria-label={`${pathway} fluxes`} data-pathway={pathway}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 className="text-[14px] font-semibold">
          <span className="r-num mr-2 text-[color:var(--r-text-3)]">{rank}</span>{pathway}
          {isDominant ? <span className="ml-2 text-[12px] font-normal text-[color:var(--r-text-2)]">largest total</span> : null}
        </h3>
        <p className="r-num text-[13px]" title={String(pathwayTotal)}>Total {formatFluxValue(pathwayTotal)}</p>
      </div>
      <p className="r-legend">
        {reactionSignals.length} non-zero of {reactions.length} modeled reactions
        {topSignal ? ` · largest |flux|: ${topSignal.reaction} ${formatFluxValue(topSignal.flux)}` : ''}
      </p>
      {reactionSignals.length > 0 ? (
        <ol className="grid gap-1" aria-label={`${pathway} reaction fluxes`}>
          {reactionSignals.map(({ reaction, flux }) => {
            const share = `${(Math.abs(flux) / maxAbs) * 100}%`
            return (
              <li key={reaction} className="grid grid-cols-[minmax(64px,96px)_minmax(0,1fr)_minmax(64px,auto)] items-center gap-2 text-[12px]"
                data-reaction={reaction}>
                <span className="truncate font-mono" title={reaction}>{reaction}</span>
                <span className="grid h-3 grid-cols-2" aria-hidden="true">
                  <span className="flex justify-end border-r border-[color:var(--r-line-strong)]">
                    {flux < 0 ? <span className="h-full rounded-l-sm" style={{ width: share, background: color, opacity: 0.55 }} /> : null}
                  </span>
                  <span className="flex">
                    {flux > 0 ? <span className="h-full rounded-r-sm" style={{ width: share, background: color, opacity: 0.85 }} /> : null}
                  </span>
                </span>
                <span className="r-num text-right" title={String(flux)}>{formatFluxValue(flux)}</span>
              </li>
            )
          })}
        </ol>
      ) : (
        <p className="research-muted">No non-zero flux for this pathway in the current snapshot.</p>
      )}
    </section>
  )
}

export function FluxAnalysis() {
  const { setContext } = useResearchContext()
  const { activeDataset, researchDataMode, activeCalibration } = useResearchDataset()
  const resolvedDatasetSummary = useMemo(() => summarizeResearchDataset(activeDataset), [activeDataset])
  const fluxSnapshot = useMemo(() => buildFluxConcentrationSnapshot(activeDataset), [activeDataset])
  const activeCalibrationParams = useMemo(() => {
    if (!activeCalibration?.calibrationCompleted || activeCalibration.datasetProvenance.calibratedParametersActive !== true) {
      return null
    }

    if (activeCalibration.datasetId !== resolvedDatasetSummary.datasetId) {
      return null
    }

    if (activeCalibration.researchDataMode !== researchDataMode) {
      return null
    }

    return activeCalibration.optimizedParams
  }, [activeCalibration, researchDataMode, resolvedDatasetSummary.datasetId])

  const [fluxes, setFluxes] = useState<Record<string, number> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedPathway, setSelectedPathway] = useState('all')

  const estimate = useCallback(async () => {
    setLoading(true)
    setError(null)
    setFluxes(null)

    try {
      const res = await apiClient.post<{ fluxes: Record<string, number> }>('/flux/estimate', {
        concentrations: fluxSnapshot.concentrations,
        custom_params: activeCalibrationParams ?? undefined,
      })
      setFluxes(res.data.fluxes)
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Flux estimation failed')
    } finally {
      setLoading(false)
    }
  }, [activeCalibrationParams, fluxSnapshot.concentrations])

  useEffect(() => {
    void estimate()
  }, [estimate])

  const fluxStatus = loading ? 'running' : error ? 'failed' : fluxes ? 'completed' : 'setup_only'
  const fluxContext = useMemo(
    () =>
      buildFluxAnalysisResearchContext(
        fluxes ? { fluxes } : null,
        fluxSnapshot.concentrations,
        resolvedDatasetSummary,
        {
          selectedPathway,
          fluxStatus,
          fluxError: error,
          appliedConcentrationMetabolites: fluxSnapshot.appliedMetabolites,
          concentrationSource: fluxSnapshot.source,
          concentrationFallbackReason: fluxSnapshot.fallbackReason,
          calibrationApplied: Boolean(activeCalibrationParams),
          calibrationSource: activeCalibrationParams ? 'auto_loaded' : 'defaults',
        }
      ),
    [
      activeCalibrationParams,
      error,
      fluxSnapshot.appliedMetabolites,
      fluxSnapshot.concentrations,
      fluxSnapshot.fallbackReason,
      fluxSnapshot.source,
      fluxStatus,
      fluxes,
      resolvedDatasetSummary,
      selectedPathway,
    ]
  )

  useEffect(() => {
    setContext(fluxContext)
    return () => setContext(null)
  }, [fluxContext, setContext])

  const pathwayKeys = Object.keys(PATHWAY_GROUPS)
  const dominantPathway = fluxContext.summary.dominantPathway
  const appliedCount = fluxContext.datasetAppliedMetabolites?.length ?? 0
  const totalConcentrations = fluxContext.inputs.totalConcentrations
  const fluxStatusLabel = getFluxAnalysisStatusLabel(fluxContext)
  const fluxStatusLine = getFluxAnalysisStatusLine(fluxContext)
  const fluxProvenanceSummary = getFluxAnalysisProvenanceSummary(fluxContext)
  const calibrationStatusLabel = getCalibrationStatusLabel(fluxContext)
  const sortedPathwayEntries = useMemo(
    () =>
      Object.entries(fluxContext.outputs.pathwayFluxTotals).sort(([, left], [, right]) => right - left),
    [fluxContext.outputs.pathwayFluxTotals]
  )
  const visiblePathwayEntries =
    selectedPathway === 'all'
      ? sortedPathwayEntries
      : sortedPathwayEntries.filter(([pathway]) => pathway === selectedPathway)
  const reactionCount = fluxContext.fluxResultAvailable ? Object.keys(fluxContext.outputs.fluxes).length : 0

  const inspector = (
    <dl className="research-review" data-testid="flux-provenance">
      <div><dt>What these values are</dt><dd>Model rate estimates returned by the flux service for one concentration snapshot. Not measured fluxes, not a simulated trajectory, not a biological validation.</dd></div>
      <div><dt>Concentration snapshot</dt><dd>{fluxSnapshot.source === 'custom_upload'
        ? 'Last value of each mapped upload series; other pools use reference defaults'
        : 'Reference default concentrations'}</dd></div>
      <div><dt>Concentrations from upload</dt><dd>{appliedCount} / {totalConcentrations}</dd></div>
      <div><dt>Dataset</dt><dd>{resolvedDatasetSummary.label}</dd></div>
      <div><dt>Calibration</dt><dd>{calibrationStatusLabel}</dd></div>
      <div><dt>Source</dt><dd>{fluxProvenanceSummary}</dd></div>
      <div><dt>Status</dt><dd>{fluxSnapshot.fallbackReason ?? fluxStatusLine}</dd></div>
      <div><dt>Units</dt><dd>As returned by the API; no conversion is applied for display.</dd></div>
    </dl>
  )

  return (
    <WithInspector title="Flux details" anchorId="comparison-view" inspector={inspector}>
      <div className="grid w-full gap-6" data-testid="research-flux">
        <section id="pathway-activity" className="grid gap-4" aria-label="Snapshot">
          <div className="research-toolbar">
            <Button onClick={estimate} disabled={loading} className="r-primary gap-2">
              {loading ? <Loader2 size={16} className="animate-spin" /> : <BarChart3 size={16} />}
              {loading ? 'Estimating...' : 'Re-estimate'}
            </Button>
            <Select value={selectedPathway} onValueChange={setSelectedPathway}>
              <SelectTrigger className="w-[190px] max-w-full" aria-label="Pathway filter"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All pathways</SelectItem>
                {pathwayKeys.map((pathway) => <SelectItem key={pathway} value={pathway}>{pathway}</SelectItem>)}
              </SelectContent>
            </Select>
            <span className="research-muted" role="status">{fluxStatusLabel}</span>
          </div>
          {error ? (
            <p role="alert" className="flex items-start gap-2 text-sm text-destructive" data-testid="flux-error">
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              <span className="min-w-0 break-words"><strong>Flux estimation error.</strong> {error} Use Re-estimate to retry.</span>
            </p>
          ) : null}
          {fluxContext.fluxResultAvailable ? (
            <dl className="r-metrics" data-testid="flux-summary">
              <div><dt>Dominant pathway</dt><dd>{dominantPathway !== 'unknown' ? dominantPathway : '—'}</dd></div>
              <div><dt>Total flux</dt><dd className="r-num" title={String(fluxContext.outputs.totalFlux)}>{formatFluxValue(fluxContext.outputs.totalFlux)}</dd></div>
              <div><dt>Reactions</dt><dd className="r-num">{reactionCount}</dd></div>
              <div><dt>Pathways shown</dt><dd className="r-num">{visiblePathwayEntries.length}</dd></div>
            </dl>
          ) : null}
        </section>

        <section id="reaction-tracing" className="grid gap-4" aria-label="Pathway fluxes" aria-busy={loading}>
          <div className="grid gap-1">
            <h2>Pathway fluxes</h2>
            <p className="r-legend">Ranked by pathway total. Bars are centred on zero: left is negative, right is positive. Hover a value for its exact number.</p>
          </div>
          {loading && !fluxes ? (
            <p className="research-empty" role="status"><Loader2 size={16} className="animate-spin" />Estimating fluxes...</p>
          ) : fluxes ? (
            <div className="grid gap-4">
              {visiblePathwayEntries.map(([pathway, pathwayTotal], index) => (
                <FluxPathwayRows
                  key={pathway}
                  pathway={pathway}
                  rank={index + 1}
                  fluxes={fluxes}
                  pathwayTotal={pathwayTotal}
                  dominantPathway={dominantPathway}
                />
              ))}
            </div>
          ) : !error ? (
            <p className="research-empty" data-testid="flux-empty">No flux result yet. Use Re-estimate.</p>
          ) : null}
        </section>
      </div>
    </WithInspector>
  )
}
