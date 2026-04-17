'use client'

import { useState, useCallback, useEffect, useMemo } from 'react'
import type { ActiveResearchDataset } from '@/types/research-dataset'
import { apiClient } from '@/lib/api-client'
import { FluxBarChart, PATHWAY_GROUPS } from './flux/FluxBarChart'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Loader2, BarChart3, AlertCircle, Sparkles } from 'lucide-react'
import { useResearchContext } from '@/contexts/ResearchContextProvider'
import { useResearchDataset } from '@/contexts/ResearchDatasetProvider'
import { summarizeResearchDataset } from '@/lib/research-dataset'
import { buildFluxAnalysisResearchContext } from '@/lib/robocop/research-context-builders'
import {
  getCalibrationStatusLabel,
  getDatasetModeLabel,
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

function FluxMetricCard({
  label,
  value,
  hint,
}: {
  label: string
  value: string
  hint: string
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4 shadow-inner shadow-black/10">
      <p className="text-[11px] font-medium uppercase tracking-[0.3em] text-slate-400">{label}</p>
      <p className="mt-2 text-lg font-semibold text-white">{value}</p>
      <p className="mt-1 text-xs leading-5 text-slate-400">{hint}</p>
    </div>
  )
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
        'overflow-hidden border-white/10 bg-slate-950/70 shadow-[0_20px_60px_-34px_rgba(8,15,40,0.8)]',
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

      <CardContent className="space-y-4 px-5 py-4">
        <div className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-3">
          {reactionSignals.length > 0 ? (
            <FluxBarChart fluxes={fluxes} pathway={pathway} />
          ) : (
            <div className="flex min-h-[150px] items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/[0.02] px-4 text-sm text-slate-400">
              No non-zero fluxes were detected for this pathway in the current snapshot.
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
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
    if (!activeCalibration?.calibrationCompleted) {
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
  const displayPathways = selectedPathway === 'all' ? pathwayKeys : [selectedPathway]
  const selectedPathwayLabel = selectedPathway === 'all' ? 'All pathways' : selectedPathway
  const dominantPathway = fluxContext.summary.dominantPathway
  const topReaction = fluxContext.outputs.topFluxes[0]
  const appliedCount = fluxContext.datasetAppliedMetabolites?.length ?? 0
  const totalConcentrations = fluxContext.inputs.totalConcentrations
  const fluxModeLabel = getDatasetModeLabel(fluxContext)
  const fluxStatusLabel = getFluxAnalysisStatusLabel(fluxContext)
  const fluxStatusLine = getFluxAnalysisStatusLine(fluxContext)
  const fluxProvenanceSummary = getFluxAnalysisProvenanceSummary(fluxContext)
  const calibrationStatusLabel = getCalibrationStatusLabel(fluxContext)
  const keySignals = fluxContext.summary.keySignals.slice(0, 4)
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

  return (
    <div className="grid gap-6">
      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
        <Card className="relative overflow-hidden border-white/10 bg-[linear-gradient(180deg,rgba(15,23,42,0.98),rgba(15,23,42,0.86))] shadow-[0_30px_90px_rgba(15,23,42,0.35)]">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(34,211,238,0.14),transparent_34%),radial-gradient(circle_at_bottom_left,rgba(16,185,129,0.08),transparent_28%)]"
          />
          <CardHeader className="relative space-y-4 border-b border-white/10 px-5 py-5 sm:px-6">
            <div className="flex flex-wrap items-center gap-2">
              <Badge className="rounded-full border-cyan-400/20 bg-cyan-400/10 text-cyan-100 hover:bg-cyan-400/10">
                Pathway fluxes
              </Badge>
              <Badge
                variant={resolvedDatasetSummary.mode === 'custom_user_data_mode' ? 'default' : 'secondary'}
                className="rounded-full"
              >
                {resolvedDatasetSummary.label}
              </Badge>
              <Badge
                variant="outline"
                className="rounded-full border-white/10 bg-white/[0.04] text-slate-200"
              >
                {fluxModeLabel}
              </Badge>
              <Badge
                variant="outline"
                className="rounded-full border-white/10 bg-white/[0.04] text-slate-200"
              >
                {calibrationStatusLabel}
              </Badge>
              <Badge
                variant="outline"
                className="rounded-full border-white/10 bg-white/[0.04] text-slate-200"
              >
                {fluxStatusLabel}
              </Badge>
            </div>

            <div className="space-y-3">
              <CardTitle className="text-3xl text-white sm:text-4xl">Flux Analysis</CardTitle>
              <CardDescription className="max-w-3xl text-base leading-7 text-slate-400">
                View Michaelis-Menten flux estimates grouped by metabolic subsystem. Custom uploaded data, when
                active, overrides the Bordbar concentration snapshot for mapped metabolites while the remaining
                model concentrations retain their default values.
              </CardDescription>
            </div>
          </CardHeader>

          <CardContent className="relative space-y-5 px-5 py-5 sm:px-6">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <FluxMetricCard
                label="Dominant pathway"
                value={fluxContext.fluxResultAvailable && dominantPathway !== 'unknown' ? dominantPathway : '—'}
                hint={fluxContext.fluxResultAvailable ? 'Largest pathway flux total' : 'Waiting for the next flux estimate'}
              />
              <FluxMetricCard
                label="Total flux"
                value={fluxContext.fluxResultAvailable ? formatFluxValue(fluxContext.outputs.totalFlux) : '—'}
                hint={fluxContext.fluxResultAvailable ? 'Absolute flux magnitude across all reactions' : 'No completed flux result yet'}
              />
              <FluxMetricCard
                label="Top reaction"
                value={fluxContext.fluxResultAvailable && topReaction ? `${topReaction.reaction} ${formatFluxValue(topReaction.flux)}` : '—'}
                hint={fluxContext.fluxResultAvailable ? topReaction?.pathway ?? 'Largest-magnitude reaction' : 'Top signal appears after estimation'}
              />
              <FluxMetricCard
                label="Applied concentrations"
                value={`${appliedCount}/${totalConcentrations}`}
                hint={
                  fluxSnapshot.fallbackReason
                    ? fluxSnapshot.fallbackReason
                    : resolvedDatasetSummary.mode === 'custom_user_data_mode'
                      ? 'Custom dataset values override the Bordbar defaults'
                      : 'Bordbar defaults supply the flux snapshot'
                }
              />
            </div>

            <div className="grid gap-4 xl:grid-cols-[minmax(0,1.12fr)_minmax(290px,0.88fr)]">
              <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-5 shadow-inner shadow-black/10">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-2">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.32em] text-cyan-200/75">
                      Flux result summary
                    </p>
                    <h2 className="text-xl font-semibold text-white">
                      {fluxContext.fluxResultAvailable ? 'Result-ready flux snapshot' : 'Flux setup in progress'}
                    </h2>
                  </div>
                  <Badge
                    variant="outline"
                    className={cn(
                      'rounded-full border-white/10 bg-white/[0.04] text-slate-200',
                      fluxContext.fluxResultAvailable && 'border-emerald-400/20 bg-emerald-400/10 text-emerald-100'
                    )}
                  >
                    {fluxContext.fluxResultAvailable ? 'Ready' : fluxStatusLabel}
                  </Badge>
                </div>

                <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">
                  {fluxProvenanceSummary}
                </p>

                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                      Dominant pathway
                    </p>
                    <p className="mt-2 text-lg font-semibold text-white">
                      {fluxContext.fluxResultAvailable && dominantPathway !== 'unknown' ? dominantPathway : '—'}
                    </p>
                    <p className="mt-1 text-sm text-slate-400">Largest pathway flux total</p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                      Selected pathway
                    </p>
                    <p className="mt-2 text-lg font-semibold text-white">{selectedPathwayLabel}</p>
                    <p className="mt-1 text-sm text-slate-400">Pathway filter applied to the charts</p>
                  </div>
                </div>

                {fluxContext.fluxResultAvailable ? (
                  <div className="mt-4 rounded-2xl border border-white/10 bg-slate-950/60 p-4">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                      Result interpretation
                    </p>
                    <p className="mt-2 text-sm leading-6 text-slate-300">{fluxContext.resultSummary}</p>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {keySignals.map((signal) => (
                        <Badge
                          key={signal}
                          variant="outline"
                          className="border-white/10 bg-white/[0.04] text-[10px] uppercase tracking-[0.18em] text-slate-300"
                        >
                          {signal}
                        </Badge>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="mt-4 rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-4">
                    <p className="text-sm text-slate-300">{fluxStatusLine}</p>
                    <p className="mt-2 text-xs leading-5 text-slate-500">
                      The pathway explorer below will populate once the result is available.
                    </p>
                  </div>
                )}
              </div>

              <div className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5 shadow-[0_20px_60px_-34px_rgba(0,0,0,0.78)] backdrop-blur-sm">
                <p className="eyebrow">Provenance snapshot</p>
                <div className="mt-4 grid gap-3">
                  <div className="rounded-2xl border border-white/10 bg-slate-950/55 p-4">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                      Dataset
                    </p>
                    <p className="mt-2 text-sm font-semibold text-white">{resolvedDatasetSummary.label}</p>
                    <p className="mt-1 text-sm leading-6 text-slate-300">{getDatasetModeLabel(fluxContext)}</p>
                  </div>

                  <div className="rounded-2xl border border-white/10 bg-slate-950/55 p-4">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                      Calibration
                    </p>
                    <p className="mt-2 text-sm font-semibold text-white">{calibrationStatusLabel}</p>
                    <p className="mt-1 text-sm leading-6 text-slate-300">{getCalibrationStatusLabel(fluxContext)}</p>
                  </div>

                  <div className="rounded-2xl border border-white/10 bg-slate-950/55 p-4">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                      Flux state
                    </p>
                    <p className="mt-2 text-sm font-semibold text-white">{fluxStatusLabel}</p>
                    <p className="mt-1 text-sm leading-6 text-slate-300">{fluxStatusLine}</p>
                  </div>

                  <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-4">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-cyan-100/80">
                      Assistant-ready notes
                    </p>
                    <p className="mt-2 text-sm leading-6 text-cyan-50/80">
                      RoBoCop can explain the same provenance snapshot and pathway signal summary without leaving
                      this page.
                    </p>
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  {keySignals.slice(0, 4).map((signal) => (
                    <Badge
                      key={signal}
                      variant="outline"
                      className="border-white/10 bg-white/[0.04] text-[10px] uppercase tracking-[0.18em] text-slate-300"
                    >
                      {signal}
                    </Badge>
                  ))}
                </div>
              </div>
            </div>
          </CardContent>

          <CardFooter className="flex flex-wrap items-center gap-3 border-t border-white/10 px-5 py-4 sm:px-6">
            <Button onClick={estimate} disabled={loading} variant="outline" className="gap-2 border-white/10 bg-white/[0.04] text-slate-100 hover:bg-white/[0.08]">
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <BarChart3 className="h-4 w-4" />}
              {loading ? 'Estimating...' : 'Re-estimate'}
            </Button>
            <Select value={selectedPathway} onValueChange={setSelectedPathway}>
              <SelectTrigger className="w-[190px] border-white/10 bg-slate-950/60">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All pathways</SelectItem>
                {Object.keys(PATHWAY_GROUPS).map((pathway) => (
                  <SelectItem key={pathway} value={pathway}>
                    {pathway}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Badge variant="secondary" className="rounded-full">
              {selectedPathwayLabel}
            </Badge>
            <Badge variant="outline" className="rounded-full border-white/10 bg-white/[0.04] text-slate-200">
              {fluxContext.fluxResultAvailable ? `${reactionCount} reactions` : `${reactionCount}/29 concentrations`}
            </Badge>
            <span className="text-xs text-slate-400">
              RoBoCop stays available for result interpretation.
            </span>
          </CardFooter>
        </Card>
      </section>

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

      <section className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="space-y-1">
            <p className="eyebrow">Pathway explorer</p>
            <h2 className="section-heading">Flux layers</h2>
            <p className="section-copy max-w-2xl">
              Ranked pathway cards make it easier to compare major subsystems, trace reaction-level signals, and spot
              the largest shifts at a glance.
            </p>
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
          <div className="grid gap-4 xl:grid-cols-2">
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
