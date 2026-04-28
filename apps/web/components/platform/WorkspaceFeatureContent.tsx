'use client'

import { useEffect, useMemo, useState } from 'react'
import { SimulationWorkspace } from '../features/SimulationWorkspace'
import { FluxAnalysis } from '../features/FluxAnalysis'
import { BagRepository } from '../features/BagRepository'
import { PathwayVisualization } from '../features/PathwayVisualization'
import { QualityForecast } from '../features/QualityForecast'
import { Alerts } from '../features/Alerts'
import { ParameterCalibration } from '../features/ParameterCalibration'
import { DataUpload } from '../features/DataUpload'
import { SensitivityAnalysis } from '../features/SensitivityAnalysis'
import { MonitoringWorkspaceLanding } from './MonitoringWorkspaceLanding'
import { ResearchDatasetBanner } from './ResearchDatasetBanner'
import { ResearchDatasetModeChip } from './ResearchDatasetModeChip'
import { ResearchWorkspaceLanding } from './ResearchWorkspaceLanding'
import { cn } from '@/lib/utils'
import { useResearchContext } from '@/contexts/ResearchContextProvider'
import { buildCalibrationRegistryResearchContext } from '@/lib/robocop/research-context-builders'
import type {
  MonitoringAlertWorkflowStateRecord,
  MonitoringAlertWorkflowTransitionRecord,
} from '@/lib/monitoring-alerts'
import Link from 'next/link'
import type { PlatformNavItem } from './platform-shell.types'
import { Button } from '../ui/button'
import { ArrowRight, History } from 'lucide-react'

interface WorkspaceFeatureContentProps {
  access: { mode?: string | null } | null
  detail: any
  detailFields: readonly [string, unknown][]
  feature: PlatformNavItem
  alertsData?: {
    workflowHistory: MonitoringAlertWorkflowTransitionRecord[]
    workflowStates: MonitoringAlertWorkflowStateRecord[]
  }
  runs: any[]
}

function normalizeRegistryStatus(value: unknown) {
  if (typeof value !== 'string' || !value.trim()) {
    return 'unknown'
  }

  return value.trim().toLowerCase().replace(/\s+/g, '_')
}

function getRegistryStatusLabel(status: string) {
  switch (normalizeRegistryStatus(status)) {
    case 'baseline':
      return 'Baseline'
    case 'keep':
      return 'Keep'
    case 'completed':
      return 'Completed'
    case 'discard':
      return 'Discard'
    case 'partial':
      return 'Partial'
    case 'timed_out':
      return 'Timed out'
    case 'crashed':
      return 'Crashed'
    case 'not_comparable':
      return 'Not comparable'
    default:
      return 'Unknown'
  }
}

function getRegistryStatusTone(status: string) {
  switch (normalizeRegistryStatus(status)) {
    case 'baseline':
      return 'border-cyan-400/20 bg-cyan-400/10 text-cyan-100'
    case 'keep':
      return 'border-emerald-400/20 bg-emerald-400/10 text-emerald-100'
    case 'completed':
      return 'border-emerald-400/20 bg-emerald-400/10 text-emerald-100'
    case 'discard':
      return 'border-rose-400/20 bg-rose-400/10 text-rose-100'
    case 'partial':
    case 'not_comparable':
      return 'border-amber-400/20 bg-amber-400/10 text-amber-100'
    case 'timed_out':
      return 'border-orange-400/20 bg-orange-400/10 text-orange-100'
    case 'crashed':
      return 'border-red-400/20 bg-red-400/10 text-red-100'
    default:
      return 'border-slate-400/20 bg-slate-400/10 text-slate-100'
  }
}

function formatNumber(value: unknown, digits = 3) {
  if (value === null || value === undefined || value === '') {
    return '—'
  }

  const numericValue = Number(value)
  if (Number.isNaN(numericValue)) {
    return String(value)
  }

  if (Number.isInteger(numericValue)) {
    return String(numericValue)
  }

  return numericValue.toFixed(digits)
}

function formatRunCaseLabel(run: any) {
  if (
    run?.completedCases !== null &&
    run?.completedCases !== undefined &&
    run?.totalCases !== null &&
    run?.totalCases !== undefined
  ) {
    return `${run.completedCases}/${run.totalCases}`
  }

  if (run?.caseCount !== null && run?.caseCount !== undefined) {
    return String(run.caseCount)
  }

  return '—'
}

function sortRegistryRuns(left: any, right: any) {
  const leftScore = Number(left?.aggregateScore ?? Number.POSITIVE_INFINITY)
  const rightScore = Number(right?.aggregateScore ?? Number.POSITIVE_INFINITY)

  if (leftScore !== rightScore) {
    return leftScore - rightScore
  }

  const leftRecorded = new Date(left?.runTimestampUtc || left?.recordedAt || 0).getTime()
  const rightRecorded = new Date(right?.runTimestampUtc || right?.recordedAt || 0).getTime()

  return rightRecorded - leftRecorded
}

type RegistryFilterKey = 'all' | 'baseline' | 'keep' | 'discard' | 'other'

const REGISTRY_FILTERS: { key: RegistryFilterKey; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'baseline', label: 'Baseline' },
  { key: 'keep', label: 'Keep' },
  { key: 'discard', label: 'Discard' },
  { key: 'other', label: 'Other' },
]

function matchesRegistryFilter(run: any, filter: RegistryFilterKey) {
  if (filter === 'all') {
    return true
  }

  const status = normalizeRegistryStatus(run?.benchmarkStatus ?? run?.status)

  if (filter === 'other') {
    return status !== 'baseline' && status !== 'keep' && status !== 'discard'
  }

  return status === filter
}

function RegistryMetricTile({
  label,
  value,
  note,
  tone = 'neutral',
}: {
  label: string
  value: string
  note: string
  tone?: 'neutral' | 'accent' | 'cyan' | 'emerald'
}) {
  const toneClass =
    tone === 'accent'
      ? 'border-red-400/25 bg-red-400/[0.08] shadow-[0_22px_60px_-42px_rgba(239,68,68,0.9)]'
      : tone === 'cyan'
        ? 'border-cyan-300/20 bg-cyan-300/[0.08]'
        : tone === 'emerald'
          ? 'border-emerald-300/20 bg-emerald-300/[0.08]'
          : 'border-white/10 bg-white/[0.035]'

  return (
    <div className={cn('rounded-3xl border p-4 backdrop-blur-sm', toneClass)}>
      <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">{label}</p>
      <p className="mt-3 text-2xl font-semibold tracking-tight text-white">{value}</p>
      <p className="mt-1 text-xs leading-5 text-slate-400">{note}</p>
    </div>
  )
}

function RegistryLedgerRow({ run, isLead = false }: { run: any; isLead?: boolean }) {
  const benchmarkStatus = run?.benchmarkStatus ?? run?.status ?? 'unknown'
  const completionStatus = run?.completionStatus ?? 'unknown'
  const score = formatNumber(run?.aggregateScore)
  const finalLoss = formatNumber(run?.meanFinalLoss)
  const label = run?.label ?? run?.runId ?? 'Calibration run'
  const scope = [run?.targetScope, run?.paramScope].filter(Boolean).join(' · ')
  const recorded = run?.runTimestampUtc ?? run?.recordedAt

  return (
    <div className={cn(
      'group grid gap-4 border-t border-white/10 px-1 py-4 transition-colors duration-200 hover:bg-white/[0.025] md:grid-cols-[minmax(0,1.6fr)_0.7fr_0.7fr_0.6fr_auto] md:items-center md:px-3',
      isLead && 'bg-red-400/[0.04]'
    )}>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className={cn('inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em]', getRegistryStatusTone(benchmarkStatus))}>
            {getRegistryStatusLabel(benchmarkStatus)}
          </span>
          {isLead ? (
            <span className="inline-flex items-center rounded-full border border-red-300/30 bg-red-400/15 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-red-100">
              Latest
            </span>
          ) : null}
          <span className="truncate text-sm font-semibold text-white">{label}</span>
        </div>
        <p className="mt-1 truncate text-xs leading-5 text-slate-500">
          {scope || run?.policyName || 'Scope not recorded'}
        </p>
      </div>
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-600 md:hidden">Score</p>
        <p className="font-mono text-sm text-slate-100">{score}</p>
      </div>
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-600 md:hidden">Final loss</p>
        <p className="font-mono text-sm text-slate-300">{finalLoss}</p>
      </div>
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-600 md:hidden">Cases</p>
        <p className="font-mono text-sm text-slate-300">{formatRunCaseLabel(run)}</p>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 md:justify-end">
        <span className="text-xs text-slate-500">{recorded ? String(recorded).slice(0, 10) : getRegistryStatusLabel(completionStatus)}</span>
        <Link
          className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.035] px-3 py-1.5 text-xs font-semibold text-slate-300 transition-colors hover:border-red-300/30 hover:bg-red-400/10 hover:text-white"
          href={`/runs/${run.runId}`}
        >
          Inspect
          <ArrowRight className="size-3" />
        </Link>
      </div>
    </div>
  )
}

function RegistrySurface({ access, detail, runs }: Omit<WorkspaceFeatureContentProps, 'feature' | 'detailFields'>) {
  const { setContext } = useResearchContext()
  const registryContext = useMemo(() => buildCalibrationRegistryResearchContext(detail, runs), [detail, runs])
  const [filter, setFilter] = useState<RegistryFilterKey>('all')

  const latestBenchmarkStatus = detail?.summary?.benchmarkStatus ?? detail?.summary?.status ?? 'unknown'
  const leadRunId = detail?.summary?.runId ?? null
  const totalCompleted = runs.filter(run => normalizeRegistryStatus(run?.completionStatus) === 'completed').length
  const latestAggregateScore = formatNumber(detail?.summary?.aggregateScore)
  const latestFinalLoss = formatNumber(detail?.summary?.meanFinalLoss)

  const filteredRuns = useMemo(
    () => runs.filter(run => matchesRegistryFilter(run, filter)).sort(sortRegistryRuns),
    [runs, filter]
  )

  useEffect(() => {
    setContext(registryContext)
    return () => setContext(null)
  }, [registryContext, setContext])

  return (
    <>
      <section className="panel border-white/10 bg-[linear-gradient(180deg,rgba(20,23,30,0.96),rgba(13,16,22,0.98))]">
        <div className="grid gap-5">
          <div className="flex flex-wrap items-center gap-2">
            <span className={cn('inline-flex items-center rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em]', getRegistryStatusTone(latestBenchmarkStatus))}>
              {getRegistryStatusLabel(latestBenchmarkStatus)}
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-300">
              <History className="size-3" />
              Historical
            </span>
            <ResearchDatasetModeChip />
          </div>

          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="grid gap-2">
              <h1 className="page-title">Calibration Registry</h1>
              <p className="page-copy max-w-2xl">
                Evidence ledger for calibration runs. Lower aggregate scores are stronger evidence against the active manifest.
              </p>
            </div>
            <Button asChild className="h-10 rounded-full bg-red-600 px-5 text-xs font-semibold text-white hover:bg-red-500" size="sm">
              <Link href="/research/parameter-calibration">Run calibration</Link>
            </Button>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <RegistryMetricTile label="Aggregate score" note="Latest visible record" tone="accent" value={latestAggregateScore} />
            <RegistryMetricTile label="Final loss" note="Mean benchmark loss" value={latestFinalLoss} />
            <RegistryMetricTile label="Records" note={`${totalCompleted} of ${runs.length} completed`} tone="emerald" value={String(runs.length)} />
          </div>

          <ResearchDatasetBanner className="max-w-3xl" />
        </div>
      </section>

      <section className="panel overflow-hidden border-white/10 bg-[linear-gradient(180deg,rgba(19,22,28,0.98),rgba(15,17,23,0.96))]">
        <div className="panel-heading flex flex-wrap items-center justify-between gap-4">
          <div className="grid gap-1">
            <h2>Benchmark ledger</h2>
            <p>{filteredRuns.length} {filteredRuns.length === 1 ? 'record' : 'records'}{filter !== 'all' ? ` in "${REGISTRY_FILTERS.find(f => f.key === filter)?.label.toLowerCase()}"` : ''}, sorted by score.</p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {REGISTRY_FILTERS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                type="button"
                className={cn(
                  'inline-flex items-center rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] transition-colors',
                  filter === key
                    ? 'border-red-300/40 bg-red-400/15 text-red-100'
                    : 'border-white/10 bg-white/[0.035] text-slate-400 hover:border-white/20 hover:text-slate-200'
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {filteredRuns.length ? (
          <div className="overflow-hidden rounded-[2rem] border border-white/10 bg-slate-950/50">
            <div className="hidden border-b border-white/10 px-3 py-3 text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-600 md:grid md:grid-cols-[minmax(0,1.6fr)_0.7fr_0.7fr_0.6fr_auto]">
              <span>Run</span>
              <span>Score</span>
              <span>Final loss</span>
              <span>Cases</span>
              <span className="text-right">Detail</span>
            </div>
            <div>
              {filteredRuns.map((run: any) => (
                <RegistryLedgerRow
                  key={run.runId}
                  run={run}
                  isLead={leadRunId !== null && run.runId === leadRunId}
                />
              ))}
            </div>
          </div>
        ) : (
          <div className="empty-note">
            {runs.length === 0
              ? access?.mode === 'workspace_selection_required'
                ? 'Select an active workspace to enable workspace-scoped browsing. Until then, this ledger only reflects personal and public visibility.'
                : access?.mode === 'authenticated_personal'
                  ? 'No calibration records are currently visible for your personal researcher scope.'
                  : 'No calibration records are currently visible for this researcher context.'
              : 'No records match the current filter.'}
          </div>
        )}
      </section>
    </>
  )
}

function getPlaceholderTheme(feature: PlatformNavItem) {
  switch (feature.id) {
    case 'home-robocop':
      return {
        eyebrow: 'Assistant preview',
        title: 'RoBoCop',
        copy: 'A guided assistant surface will bring trace review, orchestration visibility, and operator help into one place.',
        badge: 'Agent layer',
        note: 'When the assistant page arrives, it will sit inside the same shell as the rest of the platform.',
      }
    case 'monitoring-robocop':
      return {
        eyebrow: 'Messaging preview',
        title: 'Hermes gateway',
        copy: 'A future messaging gateway will route Monitoring alerts, operator messages, and Telegram handoffs.',
        badge: 'Future gateway',
        note: 'This route is reserved for Hermes and will stay hidden from the active sidebar until messaging is wired.',
      }
    case 'bag-repo':
      return {
        eyebrow: 'Inventory preview',
        title: 'Bag Repository',
        copy: 'A repository view will surface bag records, donor metadata, and selected bag detail rails in one place.',
        badge: 'Live surface',
        note: 'The repository keeps inventory state visible without leaving Monitoring and leaves room for forecast and alert handoffs.',
      }
    case 'quality-forecast':
      return {
        eyebrow: 'Forecast surface',
        title: 'Quality Forecast',
        copy: 'Forecast storage quality from a limited biomarker panel, then hand the result into Alerts.',
        badge: 'Live surface',
        note: 'This route is ready for monitoring-style projections, selected simulation inheritance, and alert handoff.',
      }
    case 'alerts':
      return {
        eyebrow: 'Triage preview',
        title: 'Triage queue',
        copy: 'An alert queue will collect thresholds, escalations, and review notes in one workflow.',
        badge: 'Preview surface',
        note: 'This page will keep triage state and escalation logic close together.',
      }
    default:
      return {
        eyebrow: 'Feature preview',
        title: feature.title,
        copy: feature.description,
        badge: feature.status === 'live' ? 'Live surface' : 'Preview surface',
        note:
          feature.status === 'planned'
            ? 'This route is reserved for future work, but the shell is already in place so it will feel native when content lands.'
            : 'This route is available now and will keep expanding without changing the page shell.',
      }
  }
}

function PlaceholderSurface({ feature }: { feature: PlatformNavItem }) {
  const sectionCount = feature.children?.length ?? 0
  const surfaceTone =
    feature.status === 'live'
      ? 'border-emerald-400/20 bg-emerald-400/10 text-emerald-100'
      : feature.status === 'preview'
        ? 'border-amber-400/20 bg-amber-400/10 text-amber-100'
        : 'border-cyan-400/20 bg-cyan-400/10 text-cyan-100'
  const theme = getPlaceholderTheme(feature)

  return (
    <section className="panel overflow-hidden border-white/10 bg-[linear-gradient(180deg,rgba(26,29,35,0.96),rgba(19,22,28,0.98))]">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.08fr)_minmax(320px,0.92fr)]">
        <div className="grid gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <p className="eyebrow">{theme.eyebrow}</p>
            <span
              className={cn(
                'inline-flex items-center rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em]',
                surfaceTone
              )}
            >
              {theme.badge}
            </span>
          </div>

          <div className="grid gap-2">
            <h2 className="text-2xl font-semibold tracking-tight text-white">{theme.title}</h2>
            <p className="max-w-3xl text-sm leading-6 text-slate-400">{theme.copy}</p>
          </div>

          <div className="flex flex-wrap gap-2">
            <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-semibold text-slate-300">
              {sectionCount} section{sectionCount === 1 ? '' : 's'}
            </span>
            {feature.children?.slice(0, 3).map(section => (
              <span
                className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-semibold text-slate-300"
                key={section.id}
              >
                {section.title}
              </span>
            ))}
          </div>
        </div>

        <aside className="rounded-3xl border border-white/10 bg-slate-950/50 p-5 shadow-[0_20px_60px_-34px_rgba(0,0,0,0.78)] backdrop-blur-sm">
          <p className="eyebrow">Route notes</p>
          <div className="mt-4 grid gap-3">
            <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
              <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Why this page exists</p>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                {theme.note}
              </p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
              <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Next step</p>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                Use the subsection cards above to move through the focused workflow, then continue into the live
                content below.
              </p>
            </div>
          </div>
        </aside>
      </div>
    </section>
  )
}

export function WorkspaceFeatureContent({
  access,
  detail,
  detailFields,
  alertsData,
  feature,
  runs,
}: WorkspaceFeatureContentProps) {
  if (feature.id === 'research-overview') {
    return <ResearchWorkspaceLanding />
  }

  if (feature.id === 'monitoring-overview') {
    return <MonitoringWorkspaceLanding />
  }

  if (feature.id === 'bag-repo') {
    return <BagRepository />
  }

  if (feature.id === 'quality-forecast') {
    return <QualityForecast />
  }

  if (feature.id === 'alerts') {
    return (
      <Alerts
        initialWorkflowHistory={alertsData?.workflowHistory ?? []}
        initialWorkflowStates={alertsData?.workflowStates ?? []}
      />
    )
  }

  if (feature.id === 'calibration-registry') {
    return <RegistrySurface access={access} detail={detail} runs={runs} />
  }

  if (feature.id === 'simulation-workspace') {
    return <SimulationWorkspace />
  }

  if (feature.id === 'flux-analysis') {
    return <FluxAnalysis />
  }

  if (feature.id === 'pathway-visualization') {
    return <PathwayVisualization />
  }

  if (feature.id === 'parameter-calibration') {
    return <ParameterCalibration />
  }

  if (feature.id === 'data-upload') {
    return <DataUpload />
  }

  if (feature.id === 'sensitivity-analysis') {
    return <SensitivityAnalysis />
  }

  return <PlaceholderSurface feature={feature} />
}
