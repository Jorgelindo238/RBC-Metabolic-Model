import Link from 'next/link'
import { Activity, ArrowRight, Inbox } from 'lucide-react'
import { MONITORING_ITEMS } from '../../lib/platform-navigation.ts'
import { monitoringRunState } from '@/lib/calibration-journey.mjs'
import { cn } from '@/lib/utils'

// No seeded bags, forecasts, alerts or activity: this overview only shows records
// that actually exist (calibration runs passed in by the workspace) or an empty state.
// Bag inventory, forecasts and alerts live on their own pages, backed by their APIs.

const MONITORING_SURFACES = MONITORING_ITEMS.filter((item) => item.id !== 'monitoring-overview')

export interface MonitoringRunRecord {
  runId?: string
  label?: string | null
  status?: string | null
  completionStatus?: string | null
  completedCases?: number | null
  totalCases?: number | null
  runTimestampUtc?: string | null
  stopReason?: string | null
}

function MetricTile({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3" data-metric={label}>
      <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">{label}</p>
      <p className="mt-2 text-lg font-semibold tracking-tight text-white">{value}</p>
    </div>
  )
}

function RunRow({ run }: { run: MonitoringRunRecord }) {
  const view = monitoringRunState(run)
  const progress = view.progress
  return (
    <div className="grid gap-3 rounded-2xl border border-white/10 bg-slate-950/55 p-4" data-run-state={view.state}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="grid min-w-0 gap-1">
          <p className="truncate text-sm font-semibold text-white">{run.label || run.runId || 'Unnamed run'}</p>
          <p className="truncate text-xs text-slate-400">{run.runTimestampUtc ?? 'time not recorded'}</p>
        </div>
        <span
          className={cn(
            'inline-flex items-center rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em]',
            view.state === 'running' && 'border-cyan-400/20 bg-cyan-400/10 text-cyan-100',
            view.state === 'failed' && 'border-rose-400/20 bg-rose-400/10 text-rose-100',
            view.state === 'cancelled' && 'border-amber-400/20 bg-amber-400/10 text-amber-100',
            (view.state === 'finished_unverified' || view.state === 'unknown') && 'border-white/10 bg-white/[0.04] text-slate-300'
          )}
        >
          {view.label}
        </span>
      </div>
      {progress?.mode === 'determinate' ? (
        <div className="grid gap-1" data-progress="determinate">
          <div className="h-2 overflow-hidden rounded-full bg-white/5">
            <div className="h-full rounded-full bg-cyan-400/80" style={{ width: `${Math.round(progress.fraction * 100)}%` }} />
          </div>
          <p className="text-xs text-slate-400">{progress.completed} / {progress.total} cases (worker counters)</p>
        </div>
      ) : null}
      {progress?.mode === 'indeterminate' ? (
        <p className="flex items-center gap-2 text-xs text-slate-400" data-progress="indeterminate">
          <Activity className="size-3.5 animate-pulse" /> Running; the worker reports no case counters, so progress is unknown.
        </p>
      ) : null}
      {run.stopReason ? <p className="break-words text-xs text-slate-500">Stop reason: {run.stopReason}</p> : null}
    </div>
  )
}

export function MonitoringWorkspaceLanding({ runs = [], error = null }: { runs?: MonitoringRunRecord[]; error?: string | null }) {
  const states = runs.map((run) => monitoringRunState(run).state)
  const count = (state: string) => states.filter((s) => s === state).length
  return (
    <>
      <section className="panel overflow-hidden">
        <div className="grid gap-3">
          <p className="eyebrow">Monitoring</p>
          <h1 className="page-title">Monitoring overview</h1>
          <p className="page-copy max-w-3xl">
            Real calibration runs and their worker states. A finished run is not a biological validation and is never
            activated automatically.
          </p>
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricTile label="Runs" value={error ? 'Unknown' : runs.length} />
          <MetricTile label="Running" value={error ? 'Unknown' : count('running')} />
          <MetricTile label="Failed or cancelled" value={error ? 'Unknown' : count('failed') + count('cancelled')} />
          <MetricTile label="Finished (unverified)" value={error ? 'Unknown' : count('finished_unverified')} />
        </div>
        <div className="mt-5 flex flex-wrap gap-2">
          {MONITORING_SURFACES.map((surface) => (
            <Link
              className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-semibold text-slate-300 hover:border-cyan-400/30 hover:text-cyan-100"
              href={surface.href}
              key={surface.id}
            >
              {surface.title}
              <ArrowRight className="ml-1 size-3.5" />
            </Link>
          ))}
        </div>
      </section>

      <section className="panel overflow-hidden" data-testid="monitoring-runs">
        {error ? (
          <p className="text-sm text-rose-200" data-testid="monitoring-error">Runs could not be loaded: {error}</p>
        ) : runs.length === 0 ? (
          <div className="flex items-start gap-3" data-testid="monitoring-empty">
            <Inbox className="size-5 shrink-0 text-slate-400" />
            <div className="grid gap-1">
              <p className="text-sm font-semibold text-white">No calibration runs recorded yet</p>
              <p className="text-sm text-slate-400">
                Nothing is simulated here. Bag inventory, forecasts and alerts appear on their own pages when records exist.
              </p>
            </div>
          </div>
        ) : (
          <div className="grid gap-3">
            {runs.map((run, index) => (
              <RunRow key={run.runId ?? index} run={run} />
            ))}
          </div>
        )}
      </section>
    </>
  )
}
