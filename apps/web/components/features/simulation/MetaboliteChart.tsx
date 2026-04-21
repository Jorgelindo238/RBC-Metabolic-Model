'use client'

import { useMemo, useState } from 'react'
import type { SimulationResult } from '@/hooks/use-simulation'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { useResearchDataset } from '@/contexts/ResearchDatasetProvider'
import { ResearchDatasetModeChip } from '@/components/platform/ResearchDatasetModeChip'
import {
  Activity,
  ChevronDown,
  ChevronUp,
  LayoutGrid,
  Minus,
  Sparkles,
  Target,
  TrendingDown,
  TrendingUp,
  X,
} from 'lucide-react'
import { getSimulationKeyMetabolites } from '@/lib/robocop/simulation-context'

const COLORS = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#e67e22', '#34495e']
const DEFAULT_PLOTTED_METABOLITES = ['EGLC', 'ELAC', 'ATP'] as const

type MetaboliteStat = {
  metabolite: string
  initial: number
  final: number
  minimum: number
  maximum: number
  delta: number
  percentChange: number
  direction: 'increasing' | 'decreasing' | 'stable'
  magnitude: 'high' | 'medium' | 'low'
}

type CustomDataTrace = {
  metabolite: string
  points: Array<{ t: number; value: number }>
}

function formatConcentration(value: number) {
  return Number.isInteger(value) ? value.toFixed(0) : value.toFixed(value >= 10 ? 2 : 3).replace(/\.?0+$/, '')
}

function formatPercent(value: number) {
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}%`
}

function getDirectionTone(direction: MetaboliteStat['direction']) {
  switch (direction) {
    case 'increasing':
      return {
        icon: TrendingUp,
        ring: 'border-emerald-400/20 bg-emerald-400/10 text-emerald-100',
        accent: 'text-emerald-200',
      }
    case 'decreasing':
      return {
        icon: TrendingDown,
        ring: 'border-rose-400/20 bg-rose-400/10 text-rose-100',
        accent: 'text-rose-200',
      }
    default:
      return {
        icon: Minus,
        ring: 'border-slate-400/20 bg-slate-400/10 text-slate-100',
        accent: 'text-slate-200',
      }
  }
}

function MetricTile({
  label,
  value,
  hint,
}: {
  label: string
  value: string
  hint: string
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 px-3 py-3 shadow-inner shadow-black/10 backdrop-blur-sm">
      <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">{label}</p>
      <p className="mt-2 text-lg font-semibold text-white">{value}</p>
      <p className="mt-1 text-[11px] leading-4 text-slate-400">{hint}</p>
    </div>
  )
}

function FocusCard({ stat }: { stat: MetaboliteStat }) {
  const tone = getDirectionTone(stat.direction)
  const Icon = tone.icon

  return (
    <div className={cn('rounded-2xl border p-4 shadow-inner shadow-black/10', tone.ring)}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-white">{stat.metabolite}</p>
          <p className="mt-1 text-xs text-slate-300">
            {stat.direction} • {stat.magnitude} change
          </p>
        </div>
        <div className={cn('grid size-9 shrink-0 place-items-center rounded-xl ring-1', tone.ring)}>
          <Icon className="size-4" />
        </div>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
        <div className="rounded-xl border border-white/10 bg-slate-950/55 px-3 py-2">
          <p className="text-slate-400">Start</p>
          <p className="mt-1 font-semibold text-white">{formatConcentration(stat.initial)}</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-slate-950/55 px-3 py-2">
          <p className="text-slate-400">Final</p>
          <p className="mt-1 font-semibold text-white">{formatConcentration(stat.final)}</p>
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between text-xs">
        <span className="text-slate-400">Range</span>
        <span className="font-semibold text-white">
          {formatConcentration(stat.minimum)} → {formatConcentration(stat.maximum)}
        </span>
      </div>
      <div className="mt-3 flex items-center justify-between text-xs">
        <span className="text-slate-400">Change</span>
        <span className={cn('font-semibold', tone.accent)}>{formatPercent(stat.percentChange)}</span>
      </div>
    </div>
  )
}

interface MetaboliteChartProps {
  result: SimulationResult
  selectedMetabolites: string[]
  onSelectionChange: (metabolites: string[]) => void
}

export function MetaboliteChart({ result, selectedMetabolites, onSelectionChange }: MetaboliteChartProps) {
  const [showAll, setShowAll] = useState(false)
  const { activeCalibration, activeDataset, activeDatasetSummary, researchDataMode } = useResearchDataset()

  const nameToIdx: Record<string, number> = {}
  result.metabolite_names.forEach((name, idx) => {
    nameToIdx[name] = idx
  })

  const appliedCalibration =
    activeCalibration &&
    activeCalibration.datasetId === activeDatasetSummary.datasetId &&
    activeCalibration.researchDataMode === researchDataMode

  const calibrationChipLabel = appliedCalibration
    ? 'Latest calibration applied'
    : researchDataMode === 'custom_user_data_mode'
      ? 'Calibration required before simulation'
      : 'Bordbar defaults active'

  const calibrationChipClasses = appliedCalibration
    ? 'border-violet-400/20 bg-violet-400/10 text-violet-100'
    : researchDataMode === 'custom_user_data_mode'
      ? 'border-amber-400/20 bg-amber-400/10 text-amber-100'
      : 'border-white/10 bg-white/5 text-slate-300'

  const keyMetabolites = getSimulationKeyMetabolites(result.metabolite_names)
  const plotted = selectedMetabolites.filter((metabolite) => metabolite in nameToIdx)

  const customDataTraces = useMemo<CustomDataTrace[]>(() => {
    if (researchDataMode !== 'custom_user_data_mode' || !activeDataset) {
      return []
    }

    return plotted.flatMap((metabolite) => {
      const series = activeDataset.mappedSeriesByMetabolite[metabolite]
      if (!series?.length) {
        return []
      }

      const points = activeDataset.timePoints.flatMap((timePoint, index) => {
        const t = Number(timePoint)
        const value = Number(series[index])
        return Number.isFinite(t) && Number.isFinite(value) ? [{ t, value }] : []
      })

      return points.length ? [{ metabolite, points }] : []
    })
  }, [activeDataset, plotted, researchDataMode])

  const customDataPointCount = customDataTraces.reduce((count, trace) => count + trace.points.length, 0)
  const customDataMetaboliteCount = customDataTraces.length
  const allTimes = [
    ...result.t,
    ...customDataTraces.flatMap((trace) => trace.points.map((point) => point.t)),
  ]
  const tMin = allTimes.length > 0 ? Math.min(...allTimes) : 0
  const tMax = allTimes.length > 0 ? Math.max(...allTimes) : tMin
  const storageDays = tMax.toFixed(0)

  let globalMax = 0
  plotted.forEach((metabolite) => {
    const idx = nameToIdx[metabolite]
    result.x.forEach((row) => {
      if (row[idx] > globalMax) {
        globalMax = row[idx]
      }
    })
  })
  customDataTraces.forEach((trace) => {
    trace.points.forEach((point) => {
      if (point.value > globalMax) {
        globalMax = point.value
      }
    })
  })
  if (globalMax === 0) {
    globalMax = 1
  }

  const timeSpan = Math.max(tMax - tMin, 1)
  const W = 760
  const H = 360
  const pad = { top: 24, right: 112, bottom: 48, left: 64 }
  const plotW = W - pad.left - pad.right
  const plotH = H - pad.top - pad.bottom
  const scaleX = (t: number) => pad.left + ((t - tMin) / timeSpan) * plotW
  const scaleY = (v: number) => pad.top + plotH - (v / globalMax) * plotH

  const plottedStats: MetaboliteStat[] = plotted.map((metabolite) => {
    const idx = nameToIdx[metabolite]
    const series = result.x.map((row) => row[idx])
    const initial = series[0] ?? 0
    const final = series[series.length - 1] ?? initial
    const minimum = series.length > 0 ? Math.min(...series) : initial
    const maximum = series.length > 0 ? Math.max(...series) : final
    const delta = final - initial
    const percentChange = initial !== 0 ? (delta / initial) * 100 : 0

    let direction: MetaboliteStat['direction']
    let magnitude: MetaboliteStat['magnitude']

    if (Math.abs(percentChange) < 5) {
      direction = 'stable'
    } else if (delta > 0) {
      direction = 'increasing'
    } else {
      direction = 'decreasing'
    }

    if (Math.abs(percentChange) > 50) {
      magnitude = 'high'
    } else if (Math.abs(percentChange) > 20) {
      magnitude = 'medium'
    } else {
      magnitude = 'low'
    }

    return {
      metabolite,
      initial,
      final,
      minimum,
      maximum,
      delta,
      percentChange,
      direction,
      magnitude,
    }
  })

  const toggleMetabolite = (metabolite: string) => {
    if (selectedMetabolites.includes(metabolite)) {
      onSelectionChange(selectedMetabolites.filter((item) => item !== metabolite))
      return
    }

    onSelectionChange([...selectedMetabolites, metabolite])
  }

  const clearSelection = () => onSelectionChange([])
  const selectKeyMetabolites = () => onSelectionChange(keyMetabolites)
  const selectDefaultMetabolites = () => {
    const available = new Set(result.metabolite_names)
    onSelectionChange(DEFAULT_PLOTTED_METABOLITES.filter((metabolite) => available.has(metabolite)))
  }

  return (
    <section className="relative overflow-hidden rounded-[1.75rem] border border-white/10 bg-slate-950/80 shadow-[0_24px_90px_-40px_rgba(8,15,40,0.92)]">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(56,189,248,0.12),transparent_34%),radial-gradient(circle_at_bottom_left,rgba(16,185,129,0.1),transparent_30%)]"
      />
      <div className="relative p-4 sm:p-5 lg:p-6">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div className="max-w-3xl">
            <Badge
              variant="secondary"
              className="inline-flex rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.28em] text-cyan-100"
            >
              Trajectory Studio
            </Badge>
            <h3 className="mt-3 text-2xl font-semibold tracking-tight text-white sm:text-3xl">
              Metabolite Trajectories
            </h3>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              Key metabolite concentrations over the {storageDays}-day storage horizon. Pin the traces RoBoCop should
              emphasize, or expand the full metabolite catalog to reframe the plot.
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <ResearchDatasetModeChip className="shrink-0" />
              <Badge variant="outline" className={cn('rounded-full', calibrationChipClasses)}>
                {calibrationChipLabel}
              </Badge>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:min-w-[18rem]">
            <MetricTile label="Days" value={`${storageDays}d`} hint="Storage horizon" />
            <MetricTile label="Focused" value={`${selectedMetabolites.length}`} hint="Active traces" />
            <MetricTile label="Key" value={`${keyMetabolites.length}`} hint="Auto-picked" />
            <MetricTile label="Total" value={`${result.n_metabolites}`} hint="Available" />
            <MetricTile
              label="Observed"
              value={`${customDataMetaboliteCount}`}
              hint={customDataPointCount ? `${customDataPointCount} custom pts` : 'No overlay'}
            />
          </div>
        </div>

        <div className="mt-5 grid gap-4">
          <div className="rounded-3xl border border-white/10 bg-white/5 p-4 shadow-inner shadow-black/20 backdrop-blur-sm">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">
                  <Target className="size-3.5 text-cyan-300" />
                  Plot Focus
                </p>
                <p className="mt-2 text-sm text-slate-300">
                  Select the metabolites that RoBoCop should prioritize in the chart and follow-up analysis.
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="xs"
                  className="rounded-full border-white/10 bg-slate-950/40 px-3 text-slate-200 hover:bg-white/10"
                  onClick={selectDefaultMetabolites}
                >
                  <Sparkles className="size-3" />
                  EGLC · ELAC · ATP
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="xs"
                  className="rounded-full border-white/10 bg-slate-950/40 px-3 text-slate-200 hover:bg-white/10"
                  onClick={selectKeyMetabolites}
                >
                  Key set
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="xs"
                  className="rounded-full border-white/10 bg-slate-950/40 px-3 text-slate-200 hover:bg-white/10"
                  onClick={clearSelection}
                  disabled={selectedMetabolites.length === 0}
                >
                  Clear
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="xs"
                  className="rounded-full border-white/10 bg-slate-950/40 px-3 text-slate-200 hover:bg-white/10"
                  onClick={() => setShowAll((prev) => !prev)}
                >
                  <LayoutGrid className="size-3" />
                  {showAll ? 'Hide all' : `Show all (${result.metabolite_names.length})`}
                  {showAll ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
                </Button>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              {selectedMetabolites.length > 0 ? (
                selectedMetabolites.map((metabolite) => {
                  const selected = selectedMetabolites.includes(metabolite)
                  const idx = nameToIdx[metabolite] ?? 0

                  return (
                    <Button
                      key={metabolite}
                      type="button"
                      variant="outline"
                      size="xs"
                      onClick={() => toggleMetabolite(metabolite)}
                      className={cn(
                        'h-8 rounded-full border-white/10 px-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-200 hover:bg-white/10',
                        selected && 'border-cyan-400/30 bg-cyan-400/15 text-cyan-50'
                      )}
                    >
                      <span
                        className={cn('size-2 rounded-full', selected ? 'bg-cyan-200' : 'bg-slate-500')}
                        style={{ boxShadow: selected ? `0 0 0 3px ${COLORS[idx % COLORS.length]}22` : undefined }}
                      />
                      {metabolite}
                      <X className="size-3" />
                    </Button>
                  )
                })
              ) : (
                <div className="rounded-2xl border border-dashed border-white/10 bg-slate-950/40 px-4 py-3 text-sm text-slate-400">
                  No metabolites selected. Use the key set or choose individual traces to reveal the chart.
                </div>
              )}
            </div>

            {showAll && (
              <div className="mt-4 rounded-2xl border border-white/10 bg-slate-950/60 p-3">
                <div className="max-h-40 overflow-y-auto pr-1">
                  <div className="flex flex-wrap gap-2">
                    {result.metabolite_names.map((metabolite) => {
                      const selected = selectedMetabolites.includes(metabolite)
                      const idx = nameToIdx[metabolite] ?? 0

                      return (
                        <Button
                          key={metabolite}
                          type="button"
                          variant="outline"
                          size="xs"
                          onClick={() => toggleMetabolite(metabolite)}
                          className={cn(
                            'h-8 rounded-full border-white/10 bg-slate-950/30 px-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-200 hover:bg-white/10',
                            selected && 'border-cyan-400/30 bg-cyan-400/15 text-cyan-50'
                          )}
                        >
                          <span
                            className={cn('size-2 rounded-full', selected ? 'bg-cyan-200' : 'bg-slate-500')}
                            style={{ boxShadow: `0 0 0 3px ${COLORS[idx % COLORS.length]}14` }}
                          />
                          {metabolite}
                        </Button>
                      )
                    })}
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="rounded-3xl border border-white/10 bg-[linear-gradient(180deg,rgba(2,6,23,0.95),rgba(15,23,42,0.82))] p-4 shadow-[0_20px_80px_-40px_rgba(14,165,233,0.45)] sm:p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Chart Stage</p>
                <p className="mt-1 text-sm text-slate-300">
                  {plotted.length > 0
                    ? `${plotted.length} simulated trace${plotted.length === 1 ? '' : 's'} in view`
                    : 'No traces selected'}
                </p>
              </div>
              <div className="flex flex-wrap justify-end gap-2">
                <Badge variant="outline" className="rounded-full border-white/10 bg-white/5 text-slate-300">
                  {keyMetabolites.length} key metabolites
                </Badge>
                {researchDataMode === 'custom_user_data_mode' ? (
                  <Badge
                    variant="outline"
                    className="rounded-full border-emerald-300/20 bg-emerald-300/10 text-emerald-100"
                  >
                    {customDataPointCount
                      ? `${customDataMetaboliteCount} observed overlay${customDataMetaboliteCount === 1 ? '' : 's'}`
                      : 'No selected custom overlay'}
                  </Badge>
                ) : null}
              </div>
            </div>

            <div className="mt-4">
              {plotted.length === 0 ? (
                <div className="flex min-h-[300px] flex-col items-center justify-center rounded-3xl border border-dashed border-white/10 bg-white/[0.03] px-6 text-center">
                  <Activity className="size-10 text-cyan-300/70" />
                  <p className="mt-4 text-sm font-medium text-white">No metabolites are selected.</p>
                  <p className="mt-2 max-w-lg text-sm leading-6 text-slate-400">
                    Pick a few trajectories or restore the key metabolite set to reveal the chart.
                  </p>
                  <div className="mt-5 flex flex-wrap justify-center gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="rounded-full border-cyan-400/20 bg-cyan-400/10 text-cyan-50 hover:bg-cyan-400/15"
                      onClick={selectDefaultMetabolites}
                    >
                      <Sparkles className="size-3.5" />
                      EGLC · ELAC · ATP
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="rounded-full border-white/10 bg-slate-950/40 text-slate-200 hover:bg-white/10"
                      onClick={() => setShowAll(true)}
                    >
                      <LayoutGrid className="size-3.5" />
                      Show All
                    </Button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="mb-3 flex flex-wrap gap-2">
                    {plotted.map((metabolite, index) => {
                      const color = COLORS[index % COLORS.length]
                      const hasCustomTrace = customDataTraces.some((trace) => trace.metabolite === metabolite)

                      return (
                        <div
                          key={`legend-${metabolite}`}
                          className="flex items-center gap-2 rounded-full border border-white/10 bg-slate-950/55 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-200"
                        >
                          <span className="inline-flex items-center gap-1.5">
                            <span className="h-0.5 w-5 rounded-full" style={{ backgroundColor: color }} />
                            {metabolite} sim
                          </span>
                          {hasCustomTrace ? (
                            <span className="inline-flex items-center gap-1.5 text-emerald-100">
                              <svg width="24" height="8" viewBox="0 0 24 8" aria-hidden="true">
                                <line x1="1" y1="4" x2="23" y2="4" stroke={color} strokeWidth="1.8" strokeDasharray="4 3" />
                                <circle cx="12" cy="4" r="3" fill="rgb(2 6 23)" stroke={color} strokeWidth="1.5" />
                              </svg>
                              custom
                            </span>
                          ) : null}
                        </div>
                      )
                    })}
                  </div>
                  <svg
                    viewBox={`0 0 ${W} ${H}`}
                    className="h-[360px] w-full overflow-visible"
                    style={{ fontFamily: 'var(--font-sans, Inter, sans-serif)' }}
                    role="img"
                    aria-label="Metabolite concentration trajectories"
                  >
                    <defs>
                      <linearGradient id="sim-chart-glow" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(56, 189, 248, 0.15)" />
                        <stop offset="100%" stopColor="rgba(16, 185, 129, 0.08)" />
                      </linearGradient>
                    </defs>

                    <rect x={pad.left} y={pad.top} width={plotW} height={plotH} rx="18" fill="url(#sim-chart-glow)" fillOpacity={0.12} />

                    {[0, 0.25, 0.5, 0.75, 1].map((frac) => {
                      const y = pad.top + plotH * (1 - frac)
                      return (
                        <g key={frac}>
                          <line
                            x1={pad.left}
                            y1={y}
                            x2={pad.left + plotW}
                            y2={y}
                            stroke="currentColor"
                            strokeOpacity={0.08}
                          />
                          <text x={pad.left - 10} y={y + 3} textAnchor="end" fontSize={10} fill="currentColor" fillOpacity={0.45}>
                            {(globalMax * frac).toFixed(1)}
                          </text>
                        </g>
                      )
                    })}

                    {[0, 0.25, 0.5, 0.75, 1].map((frac) => {
                      const t = tMin + (tMax - tMin) * frac
                      return (
                        <text
                          key={frac}
                          x={scaleX(t)}
                          y={pad.top + plotH + 22}
                          textAnchor="middle"
                          fontSize={10}
                          fill="currentColor"
                          fillOpacity={0.45}
                        >
                          {t.toFixed(0)}d
                        </text>
                      )
                    })}

                    <text x={pad.left + plotW / 2} y={H - 8} textAnchor="middle" fontSize={11} fill="currentColor" fillOpacity={0.5}>
                      Time (days)
                    </text>
                    <text
                      x={16}
                      y={pad.top + plotH / 2}
                      textAnchor="middle"
                      fontSize={11}
                      fill="currentColor"
                      fillOpacity={0.5}
                      transform={`rotate(-90, 16, ${pad.top + plotH / 2})`}
                    >
                      Conc (mM)
                    </text>

                    {customDataTraces.map((trace) => {
                      const color = COLORS[plotted.indexOf(trace.metabolite) % COLORS.length] ?? COLORS[0]
                      const pts = trace.points.map((point) => `${scaleX(point.t)},${scaleY(point.value)}`).join(' ')

                      return (
                        <g key={`custom-${trace.metabolite}`}>
                          {trace.points.length > 1 ? (
                            <polyline
                              points={pts}
                              fill="none"
                              stroke={color}
                              strokeWidth={1.8}
                              strokeDasharray="6 6"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              opacity={0.74}
                            />
                          ) : null}
                          {trace.points.map((point) => (
                            <circle
                              key={`${trace.metabolite}-${point.t}-${point.value}`}
                              cx={scaleX(point.t)}
                              cy={scaleY(point.value)}
                              r={4.2}
                              fill="rgba(2, 6, 23, 0.95)"
                              stroke={color}
                              strokeWidth={2.2}
                            />
                          ))}
                        </g>
                      )
                    })}

                    {plotted.map((metabolite, index) => {
                      const idx = nameToIdx[metabolite]
                      const color = COLORS[index % COLORS.length]
                      const pts = result.t.map((t, i) => `${scaleX(t)},${scaleY(result.x[i][idx])}`).join(' ')
                      const lastX = scaleX(result.t[result.t.length - 1] ?? tMin)
                      const lastY = scaleY(result.x[result.x.length - 1][idx])

                      return (
                        <g key={metabolite}>
                          <polyline
                            points={pts}
                            fill="none"
                            stroke={color}
                            strokeWidth={2.6}
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                          <circle cx={lastX} cy={lastY} r={4.6} fill={color} />
                          <text x={lastX + 8} y={lastY + 4} fontSize={10} fill={color} fontWeight={700}>
                            {metabolite}
                          </text>
                        </g>
                      )
                    })}
                  </svg>
                </>
              )}
            </div>

            {customDataPointCount > 0 ? (
              <div className="mt-3 flex flex-wrap items-center gap-3 rounded-2xl border border-emerald-300/15 bg-emerald-300/[0.06] px-4 py-3 text-xs text-emerald-50/80">
                <span className="inline-flex items-center gap-2 font-semibold text-emerald-100">
                  <span className="size-2 rounded-full border border-emerald-100 bg-slate-950" />
                  Observed custom data
                </span>
                <span>
                  Hollow dashed traces show uploaded measurements for the selected metabolites; solid traces are model
                  simulation output.
                </span>
              </div>
            ) : researchDataMode === 'custom_user_data_mode' && plotted.length > 0 ? (
              <div className="mt-3 rounded-2xl border border-amber-300/15 bg-amber-300/[0.06] px-4 py-3 text-xs text-amber-50/80">
                The active custom dataset has no mapped observations for the selected metabolites. Select a mapped
                metabolite to compare observed points against the simulation.
              </div>
            ) : null}

            {plottedStats.length > 0 && (
              <div className="mt-5">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Trace Snapshot</p>
                    <p className="mt-1 text-sm text-slate-400">Quick readout for the visible trajectories.</p>
                  </div>
                  <Badge variant="outline" className="rounded-full border-white/10 bg-white/5 text-slate-300">
                    {plottedStats.length} active
                  </Badge>
                </div>

                <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {plottedStats.slice(0, 3).map((stat) => (
                    <FocusCard key={stat.metabolite} stat={stat} />
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
