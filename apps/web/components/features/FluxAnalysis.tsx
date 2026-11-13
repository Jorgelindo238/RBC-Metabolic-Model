'use client'

import { useState, useCallback, useEffect, useMemo } from 'react'
import type { ActiveResearchDataset } from '@/types/research-dataset'
import { apiClient } from '@/lib/api-client'
import { FluxBarChart, PATHWAY_GROUPS } from './flux/FluxBarChart'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Loader2, BarChart3, AlertCircle, Sparkles } from 'lucide-react'
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
import { cn } from '@/lib/utils'

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

function FluxPathwayCard({
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
    .map((reaction) => ({
      reaction,
      flux: fluxes[reaction] ?? 0,
    }))
    .filter((signal) => signal.flux !== 0)
    .sort((left, right) => Math.abs(right.flux) - Math.abs(left.flux))

  const topSignal = reactionSignals[0]
  const isDominant = pathway === dominantPathway

  return (
    <Card
      className={cn(
        'h-full overflow-hidden border-white/10 bg-slate-950/70 shadow-[0_20px_60px_-34px_rgba(8,15,40,0.8)]',
        isDominant && 'border-cyan-400/25 bg-[linear-gradient(180deg,rgba(8,32,43,0.96),rgba(15,23,42,0.84))]'
      )}
    >
      <CardHeader className="border-b border-white/10 bg-white/[0.03] px-5 py-4">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="grid size-8 place-items-center rounded-2xl border border-white/10 bg-white/5 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-200">
                {String(rank).padStart(2, '0')}
              </span>
              <Badge
                variant="outline"
                className={cn(
                  'border-white/10 bg-white/[0.04] text-[10px] uppercase tracking-[0.22em] text-slate-200',
                  isDominant && 'border-cyan-400/20 bg-cyan-400/10 text-cyan-100'
                )}
              >
                {isDominant ? 'Dominant pathway' : rank <= 3 ? 'Top pathway' : 'Comparison lane'}
              </Badge>
            </div>
            <CardTitle className="text-xl text-white">{pathway}</CardTitle>
            <CardDescription className="text-slate-400">
              {reactionSignals.length} non-zero reactions · {reactions.length} modeled reactions
            </CardDescription>
          </div>

          <div className="text-right">
            <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">
              Pathway total
            </p>
            <p className="mt-1 text-2xl font-semibold text-white">{formatFluxValue(pathwayTotal)}</p>
            <p className="text-xs text-slate-400">
              {topSignal ? `${topSignal.reaction} is the largest signal` : 'No non-zero reaction signal'}
            </p>
          </div>
        </div>
      </CardHeader>

      <CardContent className="grid gap-4 px-5 py-4 2xl:grid-cols-[minmax(0,1fr)_260px]">
        <div className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-3">
          {reactionSignals.length > 0 ? (
            <FluxBarChart fluxes={fluxes} pathway={pathway} />
          ) : (
            <div className="flex min-h-[150px] items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/[0.02] px-4 text-sm text-slate-400">
              No non-zero fluxes were detected for this pathway in the current snapshot.
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">
            Pathway readout
          </p>
          <div className="mt-3 space-y-3 text-sm leading-6 text-slate-300">
            <p>
              {topSignal
                ? `${topSignal.reaction} is currently the largest reaction-level signal in this pathway.`
                : 'No reaction-level signal is active in this pathway snapshot.'}
            </p>
            <p>
              {reactionSignals.length} active signal{reactionSignals.length === 1 ? '' : 's'} across{' '}
              {reactions.length} modeled reaction{reactions.length === 1 ? '' : 's'}.
            </p>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {topSignal && (
              <Badge variant="outline" className="border-white/10 bg-white/[0.04] text-slate-200">
                {topSignal.reaction} {formatFluxValue(topSignal.flux)}
              </Badge>
            )}
            {isDominant && (
              <Badge variant="outline" className="border-cyan-400/20 bg-cyan-400/10 text-cyan-100">
                Highest pathway total
              </Badge>
            )}
            <Badge variant="outline" className="border-white/10 bg-white/[0.04] text-slate-300">
              {reactions.length} modeled reactions
            </Badge>
          </div>
        </div>
      </CardContent>
    </Card>
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
  const pathwayCountLabel = `${visiblePathwayEntries.length} pathway${visiblePathwayEntries.length === 1 ? '' : 's'}`
  const reactionCount = fluxContext.fluxResultAvailable ? Object.keys(fluxContext.outputs.fluxes).length : 0
  const pathwayExplorerGridClassName = cn(
    'grid gap-4',
    selectedPathway === 'all' && visiblePathwayEntries.length > 1 ? '2xl:grid-cols-2' : 'grid-cols-1'
  )

  return (
    <div className="grid w-full gap-6">
      <section id="pathway-activity" className="research-section">
        <div className="research-toolbar">
          <Button onClick={estimate} disabled={loading} variant="outline" className="gap-2">
            {loading ? <Loader2 size={16} className="animate-spin" /> : <BarChart3 size={16} />}
            {loading ? 'Estimating...' : 'Re-estimate'}
          </Button>
          <Select value={selectedPathway} onValueChange={setSelectedPathway}>
            <SelectTrigger className="w-[190px]" aria-label="Pathway filter"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All pathways</SelectItem>
              {pathwayKeys.map((pathway) => <SelectItem key={pathway} value={pathway}>{pathway}</SelectItem>)}
            </SelectContent>
          </Select>
          <span className="research-muted" role="status">{fluxStatusLabel}</span>
        </div>
        <dl className="research-metrics">
          <div><dt>Dominant pathway</dt><dd>{fluxContext.fluxResultAvailable && dominantPathway !== 'unknown' ? dominantPathway : '-'}</dd></div>
          <div><dt>Total flux</dt><dd>{fluxContext.fluxResultAvailable ? formatFluxValue(fluxContext.outputs.totalFlux) : '-'}</dd></div>
          <div><dt>Reactions</dt><dd>{fluxContext.fluxResultAvailable ? reactionCount : '-'}</dd></div>
        </dl>
      </section>
      <details id="comparison-view" className="research-disclosure">
        <summary>Provenance</summary>
        <dl className="research-review">
          <div><dt>Dataset</dt><dd>{resolvedDatasetSummary.label}</dd></div>
          <div><dt>Calibration</dt><dd>{calibrationStatusLabel}</dd></div>
          <div><dt>Concentrations applied</dt><dd>{appliedCount} / {totalConcentrations}</dd></div>
          <div><dt>Source</dt><dd>{fluxProvenanceSummary}</dd></div>
        </dl>
        <p className="research-muted mt-3">{fluxSnapshot.fallbackReason ?? fluxStatusLine}</p>
      </details>

      {error && (
        <Card className="border-destructive/40 bg-destructive/5 shadow-sm">
          <CardContent className="flex items-start gap-3 pt-6">
            <AlertCircle className="h-5 w-5 shrink-0 text-destructive" />
            <div className="space-y-1">
              <p className="text-sm font-semibold text-destructive">Flux estimation error</p>
              <p className="text-sm text-destructive/90">{error}</p>
            </div>
          </CardContent>
        </Card>
      )}

      <section id="reaction-tracing" className="research-section space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="space-y-1">
            <h2 className="section-heading">Pathway fluxes</h2>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="rounded-full border-white/10 bg-white/[0.04] text-slate-200">
              {pathwayCountLabel}
            </Badge>
            <Badge variant="outline" className="rounded-full border-white/10 bg-white/[0.04] text-slate-200">
              Ranked by pathway flux total
            </Badge>
          </div>
        </div>

        {loading && !fluxes ? (
          <Card className="border-white/10 bg-slate-950/60">
            <CardContent className="flex flex-col items-center justify-center gap-3 py-16 text-center">
              <Loader2 className="h-6 w-6 animate-spin text-cyan-300" />
              <p className="text-sm font-medium text-white">Estimating fluxes...</p>
              <p className="max-w-md text-sm leading-6 text-slate-400">
                The pathway explorer will populate once the current flux snapshot completes.
              </p>
            </CardContent>
          </Card>
        ) : fluxes ? (
          <div className={pathwayExplorerGridClassName}>
            {visiblePathwayEntries.map(([pathway, pathwayTotal], index) => (
              <FluxPathwayCard
                key={pathway}
                pathway={pathway}
                rank={index + 1}
                fluxes={fluxes}
                pathwayTotal={pathwayTotal}
                dominantPathway={dominantPathway}
              />
            ))}
          </div>
        ) : (
          <Card className="border-dashed border-white/10 bg-slate-950/50">
            <CardContent className="flex flex-col items-center justify-center gap-3 py-16 text-center">
              <Sparkles className="h-6 w-6 text-cyan-300" />
              <p className="text-sm font-medium text-white">No completed flux result yet</p>
              <p className="max-w-md text-sm leading-6 text-slate-400">
                Re-estimate the current snapshot to populate the pathway explorer with grouped flux results.
              </p>
            </CardContent>
          </Card>
        )}
      </section>
    </div>
  )
}
