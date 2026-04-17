'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import {
  ArrowRight,
  Bell,
  CalendarRange,
  Droplets,
  FlaskConical,
  Gauge,
  ShieldAlert,
  Sparkles,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'
import { useLatestResearchSimulationSnapshot } from '@/lib/research-simulation'
import { getMonitoringBagRiskTone, getMonitoringBagStatusTone, type MonitoringBagRecord } from '@/lib/monitoring-inventory'
import { buildMonitoringForecastProjection, type MonitoringForecastInput, type MonitoringForecastProjection } from '@/lib/monitoring-forecast'
import { useMonitoringBagInventory } from '@/lib/monitoring-inventory-store'

function MetricTile({
  label,
  value,
  hint,
  icon: Icon,
}: {
  label: string
  value: string
  hint: string
  icon: typeof Gauge
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 shadow-[0_12px_30px_-22px_rgba(0,0,0,0.78)] backdrop-blur-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="grid gap-1">
          <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">{label}</p>
          <p className="mt-1 text-lg font-semibold tracking-tight text-white">{value}</p>
        </div>
        <span className="grid size-9 place-items-center rounded-2xl border border-white/10 bg-white/[0.04] text-cyan-100">
          <Icon className="size-4" />
        </span>
      </div>
      <p className="mt-2 text-xs leading-5 text-slate-400">{hint}</p>
    </div>
  )
}

function DetailField({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/55 p-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">{label}</p>
      <p className="mt-2 text-sm font-semibold text-white">{value}</p>
    </div>
  )
}

function BagSelector({
  bag,
  active,
  onSelect,
}: {
  bag: MonitoringBagRecord
  active: boolean
  onSelect: (bagId: string) => void
}) {
  return (
    <button
      className={cn(
        'grid min-w-[150px] gap-1.5 rounded-2xl border px-4 py-3 text-left transition-colors',
        active
          ? 'border-cyan-400/30 bg-cyan-400/10 text-cyan-100'
          : 'border-white/10 bg-white/[0.04] text-slate-300 hover:border-white/20 hover:bg-white/[0.06]'
      )}
      type="button"
      onClick={() => onSelect(bag.bagId)}
    >
      <span className="text-sm font-semibold">{bag.bagId}</span>
      <span className="text-[11px] uppercase tracking-[0.22em] text-slate-500">{bag.repositoryStatus}</span>
      <span className="text-xs text-slate-400">
        {bag.medicalProfile} · {bag.entryDate}
      </span>
    </button>
  )
}

function ForecastTrajectory({ projection }: { projection: MonitoringForecastProjection }) {
  const width = 640
  const height = 280
  const marginX = 52
  const marginY = 42
  const plotWidth = width - marginX * 2
  const plotHeight = height - marginY * 2
  const points = projection.trajectory.map((point, index) => {
    const x = marginX + (plotWidth * index) / Math.max(projection.trajectory.length - 1, 1)
    const y = marginY + plotHeight * (1 - point.qualityScore)
    return { ...point, x, y }
  })
  const path = points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ')
  const firstPoint = points[0]
  const lastPoint = points[points.length - 1]
  const area = `${path} L ${lastPoint?.x ?? marginX} ${height - marginY} L ${firstPoint?.x ?? marginX} ${height - marginY} Z`
  const thresholdY = marginY + plotHeight * (1 - 0.58)
  const lineTone =
    projection.riskBand === 'Low risk'
      ? 'rgba(34,197,94,0.95)'
      : projection.riskBand === 'Watch'
        ? 'rgba(56,189,248,0.95)'
        : projection.riskBand === 'Elevated'
          ? 'rgba(251,191,36,0.95)'
          : 'rgba(244,63,94,0.95)'
  const fillTone =
    projection.riskBand === 'Low risk'
      ? 'rgba(34,197,94,0.16)'
      : projection.riskBand === 'Watch'
        ? 'rgba(56,189,248,0.16)'
        : projection.riskBand === 'Elevated'
          ? 'rgba(251,191,36,0.16)'
          : 'rgba(244,63,94,0.16)'

  return (
    <div className="grid gap-4 rounded-3xl border border-white/10 bg-slate-950/55 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid gap-1">
          <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Projected trajectory</p>
          <h3 className="text-xl font-semibold tracking-tight text-white">Quality outlook over 14 days</h3>
        </div>
        <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-300">
          {projection.alertSummary}
        </span>
      </div>

      <div className="rounded-3xl border border-white/10 bg-[linear-gradient(180deg,rgba(15,23,42,0.9),rgba(15,23,42,0.7))] p-3">
        <svg className="h-[280px] w-full" viewBox={`0 0 ${width} ${height}`}>
          <defs>
            <linearGradient id="quality-trajectory-line" x1="0%" x2="100%" y1="0%" y2="0%">
              <stop offset="0%" stopColor={lineTone} />
              <stop offset="100%" stopColor="rgba(34,211,238,0.72)" />
            </linearGradient>
            <linearGradient id="quality-trajectory-fill" x1="0%" x2="0%" y1="0%" y2="100%">
              <stop offset="0%" stopColor={fillTone} />
              <stop offset="100%" stopColor="rgba(15,23,42,0.02)" />
            </linearGradient>
          </defs>
          <line stroke="rgba(251,191,36,0.35)" strokeDasharray="5 6" strokeWidth="1.2" x1={marginX} x2={width - marginX} y1={thresholdY} y2={thresholdY} />
          <text fill="rgba(251,191,36,0.7)" fontSize="10" fontWeight="700" x={width - marginX + 8} y={thresholdY + 3}>
            Review threshold
          </text>
          <path d={area} fill="url(#quality-trajectory-fill)" />
          <path d={path} fill="none" stroke="url(#quality-trajectory-line)" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" />
          {points.map((point) => (
            <g key={point.label}>
              <circle cx={point.x} cy={point.y} fill="rgba(15,23,42,0.9)" r="8" />
              <circle cx={point.x} cy={point.y} fill={lineTone} r="4.4" />
              <text fill="rgba(255,255,255,0.9)" fontSize="10" fontWeight="700" textAnchor="middle" x={point.x} y={point.y - 14}>
                {Math.round(point.qualityScore * 100)}%
              </text>
              <text fill="rgba(148,163,184,0.7)" fontSize="10" fontWeight="600" textAnchor="middle" x={point.x} y={height - 12}>
                {point.label}
              </text>
            </g>
          ))}
        </svg>
      </div>
    </div>
  )
}

export function QualityForecast() {
  const { bags } = useMonitoringBagInventory()
  const snapshot = useLatestResearchSimulationSnapshot()
  const [selectedBagId, setSelectedBagId] = useState(() => bags[0]?.bagId ?? '')
  const [lastRefreshedAt, setLastRefreshedAt] = useState(() => new Date())
  const [input, setInput] = useState<MonitoringForecastInput>({
    lactate: 8.4,
    glucose: 4.6,
    alanine: 1.2,
    glutathione: 1.45,
  })

  const selectedBag = bags.find((bag) => bag.bagId === selectedBagId) ?? bags[0]

  useEffect(() => {
    if (!bags.length) {
      setSelectedBagId('')
      return
    }

    if (!bags.some((bag) => bag.bagId === selectedBagId)) {
      setSelectedBagId(bags[0].bagId)
    }
  }, [bags, selectedBagId])

  const projection = useMemo(() => buildMonitoringForecastProjection(selectedBag, input, snapshot), [input, selectedBag, snapshot])
  const researchModeLabel = snapshot
    ? snapshot.result.dataset_applied
      ? `Simulation snapshot linked: ${snapshot.result.active_dataset_label ?? 'active dataset'}`
      : snapshot.result.research_data_mode === 'custom_user_data_mode'
        ? 'Custom user data linked'
        : 'Bordbar defaults linked'
    : 'No active simulation snapshot'
  const snapshotLabel = snapshot?.result.dataset_applied
    ? `Replay from ${snapshot.result.active_dataset_label ?? 'active dataset'}`
    : snapshot
      ? `Replay from ${snapshot.result.research_data_mode === 'custom_user_data_mode' ? 'custom user data' : 'Bordbar defaults'}`
      : 'No active simulation snapshot'
  const qualityScore = Math.round(projection.qualityScore * 100)
  const confidenceScore = Math.round(projection.confidence * 100)

  if (!selectedBag) {
    return (
      <div className="grid gap-6">
        <section className="panel !border-white/10 !bg-[linear-gradient(180deg,rgba(15,23,42,0.97),rgba(15,23,42,0.84))]">
          <p className="eyebrow">Predictive monitoring</p>
          <h1 className="page-title">Quality Forecast</h1>
          <p className="page-copy max-w-3xl">No monitored bags are available yet. Add a bag in Bag Repository to begin forecasting.</p>
        </section>
      </div>
    )
  }

  return (
    <div className="grid gap-6">
      <section className="panel relative overflow-hidden !border-white/10 !bg-[linear-gradient(180deg,rgba(15,23,42,0.97),rgba(15,23,42,0.84))] !shadow-[0_24px_80px_-48px_rgba(8,15,40,0.95)]">
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(56,189,248,0.12),transparent_34%),radial-gradient(circle_at_bottom_left,rgba(214,40,57,0.08),transparent_32%)]" />
        <div className="relative grid gap-6 xl:grid-cols-[minmax(0,1.18fr)_minmax(360px,0.82fr)]">
          <div className="grid gap-5">
            <div className="flex flex-wrap items-center gap-3">
              <p className="eyebrow">Predictive monitoring</p>
              <span className="inline-flex items-center rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-cyan-100">
                Simulation-inherited projection
              </span>
            </div>
            <div className="grid gap-3">
              <h1 className="page-title">Quality Forecast</h1>
              <p className="page-copy max-w-3xl">Forecast bag quality from a constrained extracellular panel, then hand the result to Alerts without exposing the full Research simulation workspace.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-slate-300" variant="outline">{selectedBag.bagId}</Badge>
              <Badge className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-slate-300" variant="outline">{selectedBag.repositoryStatus}</Badge>
              <Badge className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-slate-300" variant="outline">{researchModeLabel}</Badge>
              <Badge className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-slate-300" variant="outline">{snapshotLabel}</Badge>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <MetricTile icon={Gauge} label="Quality score" value={`${qualityScore}%`} hint="Higher means the bag still sits in a stable operating window." />
              <MetricTile icon={ShieldAlert} label="Risk band" value={projection.riskBand} hint="The band determines whether the bag stays in watch mode or moves toward escalation." />
              <MetricTile icon={CalendarRange} label="Review window" value={`${projection.reviewWindowDays} days`} hint="Approximate time before a stronger review is recommended." />
              <MetricTile icon={Sparkles} label="Confidence" value={`${confidenceScore}%`} hint="Confidence rises when a live simulation snapshot is linked to the forecast." />
              <MetricTile icon={Bell} label="Alert state" value={projection.alertSeverity} hint="The alert posture that feeds Monitoring Alerts." />
            </div>
          </div>

          <aside className="rounded-[2rem] border border-white/10 bg-white/[0.04] p-5 shadow-[0_20px_60px_-34px_rgba(0,0,0,0.78)] backdrop-blur-sm">
            <div className="flex items-center justify-between gap-3">
              <div className="grid gap-1">
                <p className="eyebrow">Forecast summary</p>
                <h2 className="text-2xl font-semibold tracking-tight text-white">Operational outlook</h2>
              </div>
              <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">Preview</span>
            </div>
            <div className="mt-5 grid gap-3">
              <div className="rounded-3xl border border-white/10 bg-slate-950/55 p-4">
                <div className="flex items-center gap-3">
                  <span className={cn('grid size-10 place-items-center rounded-2xl border', getMonitoringBagRiskTone(selectedBag.medicalProfile))}>
                    <Gauge className="size-4" />
                  </span>
                  <div className="grid gap-1">
                    <p className="text-sm font-semibold text-white">Selected bag</p>
                    <p className="text-sm leading-6 text-slate-400">{selectedBag.donorId} · {selectedBag.medicalProfile} · {selectedBag.storageContext}</p>
                  </div>
                </div>
              </div>
              <div className="rounded-3xl border border-white/10 bg-slate-950/55 p-4">
                <div className="flex items-center gap-3">
                  <span className="grid size-10 place-items-center rounded-2xl border border-cyan-400/20 bg-cyan-400/10 text-cyan-100"><Droplets className="size-4" /></span>
                  <div className="grid gap-1">
                    <p className="text-sm font-semibold text-white">Monitoring panel</p>
                    <p className="text-sm leading-6 text-slate-400">Limited extracellular markers drive this forecast instead of the full Research simulation stack.</p>
                  </div>
                </div>
              </div>
              <div className="rounded-3xl border border-violet-400/20 bg-violet-400/10 p-4">
                <div className="flex items-center gap-3">
                  <span className="grid size-10 place-items-center rounded-2xl border border-violet-400/20 bg-violet-400/10 text-violet-100"><FlaskConical className="size-4" /></span>
                  <div className="grid gap-1">
                    <p className="text-sm font-semibold text-white">Research inheritance</p>
                    <p className="text-sm leading-6 text-violet-50/75">Uses selected Simulation-derived trend shaping, but keeps the forecast constrained to Monitoring.</p>
                  </div>
                </div>
              </div>
            </div>
            <div className="mt-5 rounded-3xl border border-white/10 bg-slate-950/55 p-4">
              <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Bag selector</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {bags.map((bag) => (
                  <BagSelector key={bag.bagId} bag={bag} active={bag.bagId === selectedBag.bagId} onSelect={setSelectedBagId} />
                ))}
              </div>
            </div>
          </aside>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.14fr)_minmax(340px,0.86fr)]">
        <div className="grid gap-6">
          <Card className="border-white/10 bg-[linear-gradient(180deg,rgba(26,29,35,0.96),rgba(19,22,28,0.98))] shadow-[0_18px_48px_-30px_rgba(0,0,0,0.8)]">
            <CardHeader className="space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="grid gap-2">
                  <CardTitle className="text-2xl tracking-tight text-white">Selected bag context</CardTitle>
                  <CardDescription className="max-w-2xl text-slate-400">Keep the forecast anchored to one repository record so the projection stays operational.</CardDescription>
                </div>
                <div className="inline-flex items-center rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-cyan-100">Repository-linked</div>
              </div>
            </CardHeader>
            <CardContent className="grid gap-4">
              <div className="grid gap-4 rounded-3xl border border-white/10 bg-slate-950/55 p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="grid gap-1">
                    <p className="eyebrow">Active record</p>
                    <h3 className="text-2xl font-semibold tracking-tight text-white">{selectedBag.bagId}</h3>
                    <p className="text-sm text-slate-400">{selectedBag.donorId} · {selectedBag.entryDate}</p>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <Badge className={cn('rounded-full border px-3 py-1 text-[10px] uppercase tracking-[0.22em]', getMonitoringBagStatusTone(selectedBag.repositoryStatus))} variant="outline">
                      {selectedBag.repositoryStatus}
                    </Badge>
                    <Badge className={cn('rounded-full border px-3 py-1 text-[10px] uppercase tracking-[0.22em]', getMonitoringBagRiskTone(selectedBag.medicalProfile))} variant="outline">
                      {selectedBag.medicalProfile}
                    </Badge>
                  </div>
                </div>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  <DetailField label="Age / sex" value={`${selectedBag.age} · ${selectedBag.sex}`} />
                  <DetailField label="Storage context" value={selectedBag.storageContext} />
                  <DetailField label="Current quality" value={selectedBag.qualityState} />
                </div>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  <DetailField label="Forecast state" value={selectedBag.forecastState} />
                  <DetailField label="Linked runs" value={String(selectedBag.linkedRuns)} />
                  <DetailField label="Monitoring events" value={String(selectedBag.monitoringEvents)} />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-white/10 bg-[linear-gradient(180deg,rgba(26,29,35,0.96),rgba(19,22,28,0.98))] shadow-[0_18px_48px_-30px_rgba(0,0,0,0.8)]">
            <CardHeader className="space-y-2">
              <CardTitle className="text-2xl tracking-tight text-white">Extracellular monitoring panel</CardTitle>
              <CardDescription className="max-w-2xl text-slate-400">Enter a limited biomarker panel. This forecast uses selected Research-derived trend shaping, but it does not expose the full metabolic workspace.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-cyan-100">Monitoring-only</span>
                <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-300">Selected Simulation heuristics</span>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                {([
                  ['Lactate', 'lactate', input.lactate, 'Higher lactate shortens the stability window.'],
                  ['Glucose', 'glucose', input.glucose, 'Lower glucose tightens the decline curve.'],
                  ['Alanine', 'alanine', input.alanine, 'A selected amino-acid marker for the outlook.'],
                  ['Glutathione', 'glutathione', input.glutathione, 'Lower reserves weaken the stability band.'],
                ] as const).map(([label, key, value, copy]) => (
                  <div key={label} className="grid gap-2 rounded-2xl border border-white/10 bg-slate-950/55 p-4">
                    <Label className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">{label}</Label>
                    <Input className="h-11 rounded-2xl border-white/10 bg-white/[0.04] text-slate-100" min="0" step="0.1" type="number" value={value} onChange={(event) => setInput((current) => ({ ...current, [key]: Number(event.target.value) }))} />
                    <p className="text-xs leading-5 text-slate-400">{copy}</p>
                  </div>
                ))}
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <Button className="rounded-full" onClick={() => setLastRefreshedAt(new Date())} type="button">
                  Recalculate forecast
                  <ArrowRight className="size-4" />
                </Button>
                <p className="text-xs text-slate-400">Last refreshed {lastRefreshedAt.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}.</p>
              </div>
            </CardContent>
          </Card>

          <ForecastTrajectory projection={projection} />
        </div>

        <div className="grid gap-6">
          <Card className="border-white/10 bg-[linear-gradient(180deg,rgba(26,29,35,0.96),rgba(19,22,28,0.98))] shadow-[0_18px_48px_-30px_rgba(0,0,0,0.8)]">
            <CardHeader>
              <div className="flex items-center justify-between gap-3">
                <div className="grid gap-1">
                  <CardTitle className="text-2xl tracking-tight text-white">Forecast result</CardTitle>
                  <CardDescription className="text-slate-400">A compact summary of the likely bag-state trajectory.</CardDescription>
                </div>
                <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">Result-ready</span>
              </div>
            </CardHeader>
            <CardContent className="grid gap-4">
              <div className="rounded-3xl border border-white/10 bg-slate-950/55 p-5">
                <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Quality score</p>
                <p className="text-4xl font-semibold tracking-tight text-white">{qualityScore}%</p>
                <p className="mt-1 text-sm leading-6 text-slate-400">{selectedBag.bagId} is projected to stay in the {projection.riskBand.toLowerCase()} band for the next {projection.reviewWindowDays} days.</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Badge className={cn('rounded-full border px-3 py-1 text-[10px] uppercase tracking-[0.22em]', getMonitoringBagRiskTone(selectedBag.medicalProfile))} variant="outline">{projection.riskBand}</Badge>
                  <Badge className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[10px] uppercase tracking-[0.22em] text-slate-300" variant="outline">{projection.alertSeverity} alert posture</Badge>
                </div>
              </div>
              <div className="grid gap-3 rounded-3xl border border-white/10 bg-white/[0.04] p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Primary drivers</p>
                  <Droplets className="size-4 text-cyan-300" />
                </div>
                <p className="text-sm leading-6 text-slate-300">{projection.driverSummary}</p>
                <div className="grid gap-2 rounded-2xl border border-white/10 bg-slate-950/55 p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Projection note</p>
                  <p className="text-sm leading-6 text-slate-200">{projection.recommendation}</p>
                </div>
              </div>
              <div className="grid gap-3 rounded-3xl border border-violet-400/20 bg-violet-400/10 p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-violet-100/80">Simulation linkage</p>
                  <FlaskConical className="size-4 text-violet-100" />
                </div>
                <p className="text-sm leading-6 text-violet-50/80">{projection.snapshotSummary}</p>
              </div>
            </CardContent>
          </Card>

          <Card className="border-white/10 bg-[linear-gradient(180deg,rgba(26,29,35,0.96),rgba(19,22,28,0.98))] shadow-[0_18px_48px_-30px_rgba(0,0,0,0.8)]">
            <CardHeader>
              <div className="flex items-center justify-between gap-3">
                <div className="grid gap-1">
                  <CardTitle className="text-2xl tracking-tight text-white">Alert handoff</CardTitle>
                  <CardDescription className="text-slate-400">Forecast pressure can flow directly into the Alerts page when the projection tightens.</CardDescription>
                </div>
                <Bell className="size-4 text-rose-300" />
              </div>
            </CardHeader>
            <CardContent className="grid gap-3">
              <div className="rounded-3xl border border-white/10 bg-slate-950/55 p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Alert summary</p>
                <p className="mt-2 text-sm font-semibold text-white">{projection.alertSummary}</p>
                <p className="mt-1 text-sm leading-6 text-slate-400">If the curve drops below the watch band, Monitoring can hand the record off to Alerts for triage.</p>
              </div>
              <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Next action</p>
                <p className="mt-2 text-sm font-semibold text-white">{projection.recommendation}</p>
              </div>
              <Button asChild className="h-11 rounded-full">
                <Link href="/monitoring/alerts">
                  Open Alerts
                  <ShieldAlert className="size-4" />
                </Link>
              </Button>
            </CardContent>
          </Card>

          <Card className="border-white/10 bg-[linear-gradient(180deg,rgba(26,29,35,0.96),rgba(19,22,28,0.98))] shadow-[0_18px_48px_-30px_rgba(0,0,0,0.8)]">
            <CardHeader>
              <CardTitle className="text-white">Monitoring fit</CardTitle>
              <CardDescription className="text-slate-400">What this page inherits from Research, and what it intentionally leaves out.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Inherited from Research</p>
                <p className="mt-2 text-sm leading-6 text-slate-300">Selected trend shaping, snapshot-aware provenance, and concentration-to-quality mapping stay available for Monitoring.</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Intentionally excluded</p>
                <p className="mt-2 text-sm leading-6 text-slate-300">Full metabolome controls, parameter calibration, and solver settings remain in Research.</p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
