'use client'

import { useEffect, useMemo } from 'react'
import { FieldGrid } from '../ui/FieldGrid.js'
import { MetricGrid } from '../ui/MetricGrid.js'
import { RunCard } from '../ui/RunCard.js'
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

function getRegistryStatusCopy(status: string) {
  switch (normalizeRegistryStatus(status)) {
    case 'baseline':
      return 'Reference record for the current benchmark manifest.'
    case 'keep':
      return 'Improved enough to keep in the historical ledger.'
    case 'completed':
      return 'Finished the full manifest and registry projection.'
    case 'discard':
      return 'Rejected against the current benchmark rules.'
    case 'partial':
      return 'Only part of the manifest completed before stopping.'
    case 'timed_out':
      return 'Stopped after a time budget or case budget limit.'
    case 'crashed':
      return 'Run aborted before the full ledger could complete.'
    default:
      return 'Visible but not directly comparable with the current benchmark set.'
  }
}

function formatRatio(value: unknown) {
  if (value === null || value === undefined || value === '') {
    return null
  }

  const numericValue = Number(value)
  if (Number.isNaN(numericValue)) {
    return String(value)
  }

  return `${Math.round(numericValue * 100)}%`
}

function formatSeconds(value: unknown) {
  if (value === null || value === undefined || value === '') {
    return null
  }

  const numericValue = Number(value)
  if (Number.isNaN(numericValue)) {
    return String(value)
  }

  return `${numericValue.toFixed(1)}s`
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

function groupRegistryRuns(runs: any[]) {
  const grouped = new Map<string, any>()
  const preferredOrder = ['baseline', 'keep', 'discard', 'partial', 'timed_out', 'crashed', 'not_comparable', 'unknown']

  for (const run of runs) {
    const statusKey = normalizeRegistryStatus(run?.benchmarkStatus ?? run?.status)
    const groupKey = preferredOrder.includes(statusKey) ? statusKey : 'unknown'

    if (!grouped.has(groupKey)) {
      grouped.set(groupKey, {
        key: groupKey,
        label: getRegistryStatusLabel(groupKey),
        copy: getRegistryStatusCopy(groupKey),
        runs: [],
      })
    }

    grouped.get(groupKey).runs.push(run)
  }

  return preferredOrder
    .map((key) => grouped.get(key))
    .filter(Boolean)
    .map((group) => ({
      ...group,
      runs: group.runs.sort(sortRegistryRuns),
    }))
}

function RegistrySurface({ access, detail, detailFields, runs }: Omit<WorkspaceFeatureContentProps, 'feature'>) {
  const { setContext } = useResearchContext()
  const registryContext = useMemo(() => buildCalibrationRegistryResearchContext(detail, runs), [detail, runs])
  const groupedRuns = groupRegistryRuns(runs)
  const latestBenchmarkStatus = detail?.summary?.benchmarkStatus ?? detail?.summary?.status ?? 'unknown'
  const latestCompletionStatus = detail?.summary?.completionStatus ?? 'unknown'
  const latestCoverage = formatRatio(detail?.summary?.coverageRatio)
  const latestWeightCoverage = formatRatio(detail?.summary?.coverageWeightRatio)
  const latestElapsed = formatSeconds(detail?.summary?.elapsedSeconds)
  const totalCompleted = runs.filter(run => normalizeRegistryStatus(run?.completionStatus) === 'completed').length
  const totalBenchmarked = runs.filter(run => normalizeRegistryStatus(run?.benchmarkStatus ?? run?.status) !== 'unknown').length

  useEffect(() => {
    setContext(registryContext)
    return () => setContext(null)
  }, [registryContext, setContext])

  return (
    <>
      <section className="panel overflow-hidden border-white/10 bg-[linear-gradient(180deg,rgba(15,23,42,0.97),rgba(15,23,42,0.82))] shadow-[0_24px_80px_-48px_rgba(8,15,40,0.95)]">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.18fr)_minmax(320px,0.82fr)]">
          <div className="grid gap-4">
            <div className="flex flex-wrap items-center gap-3">
              <p className="eyebrow">Historical ledger</p>
              <span className={cn('inline-flex items-center rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em]', getRegistryStatusTone(latestBenchmarkStatus))}>
                {getRegistryStatusLabel(latestBenchmarkStatus)}
              </span>
            </div>

            <div className="grid gap-2">
              <h1 className="page-title">Calibration Registry</h1>
              <p className="page-copy max-w-3xl">
                Review the newest visible record, compare benchmark outcomes, and trace every result back to its
                manifest, report, and registry row. This page is a ledger of evidence, not a live calibration queue.
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              <ResearchDatasetModeChip />
              <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-semibold text-slate-300">
                {runs.length} visible records
              </span>
              <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-semibold text-slate-300">
                {totalCompleted} completed
              </span>
              <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-semibold text-slate-300">
                {totalBenchmarked} benchmarked
              </span>
              {latestCoverage ? (
                <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-semibold text-slate-300">
                  {latestCoverage} coverage
                </span>
              ) : null}
              {latestWeightCoverage ? (
                <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-semibold text-slate-300">
                  {latestWeightCoverage} weighted coverage
                </span>
              ) : null}
              {latestElapsed ? (
                <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-semibold text-slate-300">
                  {latestElapsed} elapsed
                </span>
              ) : null}
            </div>

            <ResearchDatasetBanner className="max-w-3xl" />
          </div>

          <aside className="rounded-3xl border border-white/10 bg-white/[0.04] p-5 shadow-[0_20px_60px_-34px_rgba(0,0,0,0.78)] backdrop-blur-sm">
            <p className="eyebrow">Latest record</p>
            <div className="mt-4 grid gap-3">
              <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">What this preview shows</p>
                <p className="mt-2 text-sm leading-6 text-slate-300">
                  The newest visible calibration record, its score, and the provenance that anchors the result.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Benchmark</p>
                  <p className="mt-2 text-sm font-semibold text-white">{getRegistryStatusLabel(latestBenchmarkStatus)}</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Completion</p>
                  <p className="mt-2 text-sm font-semibold text-white">{getRegistryStatusLabel(latestCompletionStatus)}</p>
                </div>
              </div>

              <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-cyan-100/80">
                  Comparison axis
                </p>
                <p className="mt-2 text-sm font-semibold text-white">
                  Lower benchmark scores represent stronger evidence against the manifest.
                </p>
                <p className="mt-1 text-sm leading-6 text-cyan-50/75">
                  Use the grouped ledger below to compare baseline, keep, and discard outcomes without treating them
                  like active jobs.
                </p>
              </div>

              <div className="rounded-2xl border border-fuchsia-400/20 bg-fuchsia-400/10 p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-fuchsia-100/80">
                  Calibration handoff
                </p>
                <p className="mt-2 text-sm font-semibold text-white">
                  Open the calibration workspace to run the active dataset before simulation.
                </p>
                <p className="mt-1 text-sm leading-6 text-fuchsia-50/75">
                  The registry keeps the evidence trail here. The actual run starts in the calibration workspace and
                  then feeds the simulation flow.
                </p>
                <div className="mt-4">
                  <Button
                    asChild
                    className="h-9 rounded-full border border-fuchsia-300/30 bg-fuchsia-300/15 px-4 text-xs font-semibold text-white hover:bg-fuchsia-300/22"
                    variant="ghost"
                  >
                    <Link href="/research/parameter-calibration">Run calibration</Link>
                  </Button>
                </div>
              </div>

              <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                  Registry comparison
                </p>
                <p className="mt-2 text-sm font-semibold text-white">
                  {registryContext.registryComparison.comparisonSummary}
                </p>
                <p className="mt-1 text-sm leading-6 text-slate-300">
                  {registryContext.registryComparison.leadRecord?.label ?? registryContext.registryComparison.leadRecord?.runId ?? 'Lead record'} is the visible anchor for this comparison set.
                </p>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {registryContext.registryComparison.groups.slice(0, 3).map((group) => (
                    <span
                      key={group.key}
                      className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-300"
                    >
                      {group.label} · {group.count}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </aside>
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <h2>Latest record snapshot</h2>
          <p>This is the most recent visible record, not a live execution slot. It surfaces the benchmark result and the fields that anchor it.</p>
        </div>
        {detail ? (
          <>
            <MetricGrid
              metrics={[
                ['Aggregate score', detail.summary.aggregateScore],
                ['Mean final loss', detail.summary.meanFinalLoss],
                ['Time-aware score', detail.summary.timeAwareScore ?? null],
                ['Case count', detail.summary.caseCount],
              ]}
            />
            <FieldGrid fields={detailFields} />
          </>
        ) : (
          <div className="empty-note">
            {access?.mode === 'workspace_selection_required'
              ? 'Select an active workspace to enable workspace-scoped browsing. Until then, this ledger only reflects personal and public visibility.'
              : access?.mode === 'authenticated_personal'
                ? 'No calibration records are currently visible for your personal researcher scope.'
                : 'No calibration records are currently visible for this researcher context.'}
          </div>
        )}
      </section>

      <section className="panel">
        <div className="panel-heading flex flex-wrap items-center justify-between gap-4">
          <div className="grid gap-1">
            <h2>Benchmark ledger</h2>
            <p>Grouped by benchmark status so comparisons stay compact, historical, and evidence-first.</p>
          </div>
          <Button asChild className="h-9 rounded-full px-4 text-xs font-semibold" size="sm" variant="outline">
            <Link href="/research/parameter-calibration">Run calibration</Link>
          </Button>
        </div>
        {groupedRuns.length ? (
          <div className="grid gap-5">
            {groupedRuns.map(group => {
              const groupBestScore = group.runs.reduce((best: number | null, run: any) => {
                if (run.aggregateScore === null || run.aggregateScore === undefined) {
                  return best
                }

                const score = Number(run.aggregateScore)
                if (Number.isNaN(score)) {
                  return best
                }

                return best === null ? score : Math.min(best, score)
              }, null)
              const completedCount = group.runs.filter((run: any) => normalizeRegistryStatus(run.completionStatus) === 'completed').length

              return (
                <div className="rounded-3xl border border-white/10 bg-slate-950/55 p-5 shadow-[0_20px_60px_-34px_rgba(0,0,0,0.72)] backdrop-blur-sm" key={group.key}>
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-3">
                        <p className="eyebrow">{group.label}</p>
                        <span className={cn('inline-flex items-center rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em]', getRegistryStatusTone(group.key))}>
                          {group.runs.length} runs
                        </span>
                      </div>
                      <h3 className="mt-2 text-xl font-semibold tracking-tight text-white">Comparison lane</h3>
                      <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">{group.copy}</p>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-semibold text-slate-300">
                        {completedCount}/{group.runs.length} completed
                      </span>
                      {groupBestScore !== null ? (
                        <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-semibold text-slate-300">
                          Best {groupBestScore.toFixed(3)}
                        </span>
                      ) : null}
                    </div>
                  </div>

                  <div className="mt-5 grid gap-4">
                    {group.runs.map((run: any) => <RunCard key={run.runId} run={run} />)}
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <div className="empty-note">No calibration records are currently visible in this ledger view.</div>
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
    return <RegistrySurface access={access} detail={detail} detailFields={detailFields} runs={runs} />
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
