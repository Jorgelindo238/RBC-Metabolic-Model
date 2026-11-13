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
import { ArrowRight } from 'lucide-react'
import { WithInspector } from './research/Inspector'

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
  runsError?: string | null
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


function completionLabel(run: any) {
  const status = normalizeRegistryStatus(run?.completionStatus)
  // Completion is neither numerical/biological validation nor activation.
  return status === 'completed' ? 'Completed (unverified)' : status === 'unknown' ? '—' : getRegistryStatusLabel(status)
}

function RegistrySurface({ access, detail, runs, runsError }: Omit<WorkspaceFeatureContentProps, 'feature' | 'detailFields'>) {
  const { setContext } = useResearchContext()
  const registryContext = useMemo(() => buildCalibrationRegistryResearchContext(detail, runs), [detail, runs])
  const [filter, setFilter] = useState<RegistryFilterKey>('all')
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const leadRunId = detail?.summary?.runId ?? null
  const totalCompleted = runs.filter(run => normalizeRegistryStatus(run?.completionStatus) === 'completed').length
  const filteredRuns = useMemo(() => runs.filter(run => matchesRegistryFilter(run, filter)).sort(sortRegistryRuns), [runs, filter])
  const selectedRun = runs.find((run) => run?.runId === selectedRunId) ?? null

  useEffect(() => {
    setContext(registryContext)
    return () => setContext(null)
  }, [registryContext, setContext])

  if (runsError) {
    return <div role="alert" className="grid gap-2" data-testid="registry-error">
      <p className="text-sm text-destructive"><strong>Results registry unavailable.</strong> {runsError}</p>
      <p className="r-legend">This is not an empty registry: the records could not be read.</p>
      <div><button type="button" className="research-text-link" onClick={() => window.location.reload()}>Retry</button></div>
    </div>
  }

  if (!runs.length) {
    return <p className="research-empty" id="latest-record" data-testid="registry-empty">
      {access?.mode === 'workspace_selection_required'
        ? 'No visible records: workspace selection pending.'
        : 'No calibration runs recorded yet.'}
      <Link className="research-text-link inline-flex items-center gap-1" href="/research/parameter-calibration">Calibration <ArrowRight size={14} /></Link>
    </p>
  }

  const evidenceRun = selectedRun ?? (leadRunId ? runs.find((run) => run?.runId === leadRunId) ?? null : null)
  const evidenceIsLead = Boolean(evidenceRun && evidenceRun.runId === leadRunId)
  const inspector = evidenceRun ? (
    <dl className="research-review" data-testid="registry-evidence">
      <div><dt>Run</dt><dd>{evidenceRun.label ?? evidenceRun.runId}</dd></div>
      <div><dt>Verdict</dt><dd>{getRegistryStatusLabel(evidenceRun.benchmarkStatus ?? evidenceRun.status)}</dd></div>
      <div><dt>Completion</dt><dd>{completionLabel(evidenceRun)}</dd></div>
      <div><dt>Score</dt><dd className="r-num" title={String(evidenceRun.aggregateScore ?? '')}>{formatNumber(evidenceRun.aggregateScore)}</dd></div>
      <div><dt>Mean final loss</dt><dd className="r-num" title={String(evidenceRun.meanFinalLoss ?? '')}>{formatNumber(evidenceRun.meanFinalLoss)}</dd></div>
      <div><dt>Cases</dt><dd className="r-num">{formatRunCaseLabel(evidenceRun)}</dd></div>
      <div><dt>Scope</dt><dd>{[evidenceRun.targetScope, evidenceRun.paramScope].filter(Boolean).join(' · ') || evidenceRun.policyName || 'Not recorded'}</dd></div>
      <div><dt>Strategy</dt><dd>{evidenceRun.optimizationStrategy ?? 'Not recorded'}</dd></div>
      {evidenceIsLead ? <div><dt>Manifest</dt><dd className="break-all">{detail?.artifacts?.manifestPath ?? 'Not recorded'}</dd></div> : null}
      <div><dt>Biological validation</dt><dd>Not established by registry completion</dd></div>
      <div><dt>Evidence</dt><dd><Link className="research-text-link" href={`/runs/${evidenceRun.runId}`}>Inspect run</Link></dd></div>
    </dl>
  ) : <p className="research-muted">Select a run to see its evidence.</p>

  return <WithInspector title="Run evidence" anchorId="artifact-trace" inspector={inspector}
    open={inspectorOpen} onOpenChange={setInspectorOpen}>
    <div className="grid gap-4">
      <p className="r-legend" id="latest-record" data-testid="registry-summary">
        <span className="r-num">{runs.length}</span> recorded run{runs.length === 1 ? '' : 's'} · <span className="r-num">{totalCompleted}</span> completed (unverified)
      </p>
      <section id="benchmark-ledger" className="grid gap-3" aria-label="Runs">
        <div className="research-filter-group w-fit" role="group" aria-label="Run outcome filter">
          {REGISTRY_FILTERS.map(({ key, label }) => <button key={key} onClick={() => setFilter(key)} type="button" aria-pressed={filter === key}>{label}</button>)}
        </div>
        {filteredRuns.length ? <div className="r-table-scroll">
          <table className="w-full min-w-[640px] text-left text-[13px]" data-testid="registry-table">
            <thead className="text-[12px] text-[color:var(--r-text-2)]">
              <tr className="border-b border-[color:var(--r-line)]">
                <th className="py-2 pr-3 font-normal">Run</th>
                <th className="py-2 pr-3 font-normal">Verdict</th>
                <th className="py-2 pr-3 font-normal">Completion</th>
                <th className="py-2 pr-3 text-right font-normal">Score</th>
                <th className="py-2 pr-3 text-right font-normal">Final loss</th>
                <th className="py-2 pr-3 text-right font-normal">Cases</th>
                <th className="py-2 font-normal">Recorded</th>
              </tr>
            </thead>
            <tbody>
              {filteredRuns.map((run: any) => {
                const recorded = run?.runTimestampUtc ?? run?.recordedAt
                return <tr key={run.runId} className="border-b border-[color:var(--r-line)]" aria-selected={run.runId === selectedRunId}>
                  <td className="py-2 pr-3">
                    <button type="button" className="research-text-link text-left" aria-pressed={run.runId === selectedRunId}
                      onClick={() => { setSelectedRunId(run.runId); setInspectorOpen(true) }}>
                      {run.label ?? run.runId}
                    </button>
                    {run.runId === leadRunId ? <span className="ml-2 r-legend">latest</span> : null}
                  </td>
                  <td className="py-2 pr-3">{getRegistryStatusLabel(run.benchmarkStatus ?? run.status)}</td>
                  <td className="py-2 pr-3">{completionLabel(run)}</td>
                  <td className="r-num py-2 pr-3 text-right" title={String(run.aggregateScore ?? '')}>{formatNumber(run.aggregateScore)}</td>
                  <td className="r-num py-2 pr-3 text-right" title={String(run.meanFinalLoss ?? '')}>{formatNumber(run.meanFinalLoss)}</td>
                  <td className="r-num py-2 pr-3 text-right">{formatRunCaseLabel(run)}</td>
                  <td className="py-2 whitespace-nowrap">{recorded ? String(recorded).slice(0, 10) : '—'}</td>
                </tr>
              })}
            </tbody>
          </table>
        </div> : <p className="research-empty">No records match this filter.</p>}
      </section>
    </div>
  </WithInspector>
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
  runsError,
}: WorkspaceFeatureContentProps) {
  if (feature.id === 'research-overview') {
    return <ResearchWorkspaceLanding />
  }

  if (feature.id === 'monitoring-overview') {
    return <MonitoringWorkspaceLanding runs={Array.isArray(runs) ? runs : []} error={runsError} />
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
    return <RegistrySurface access={access} detail={detail} runs={runs} runsError={runsError} />
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
