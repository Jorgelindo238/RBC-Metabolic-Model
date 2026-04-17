'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { AlertTriangle, ArrowRight, Bell, CheckCircle2, Clock3, FlaskConical, Gauge, ShieldAlert, TrendingUp } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { useLatestResearchSimulationSnapshot } from '@/lib/research-simulation'
import { useMonitoringBagInventory } from '@/lib/monitoring-inventory-store'
import { getMonitoringBagStatusTone } from '@/lib/monitoring-inventory'
import {
  buildMonitoringAlertQueue,
  fetchMonitoringAlertWorkflowHistoryFromApi,
  fetchMonitoringAlertWorkflowStatesFromApi,
  mergeMonitoringAlertWorkflowStates,
  getMonitoringAlertSeverityTone,
  getMonitoringAlertWorkflowTone,
  type MonitoringAlertViewRecord,
  type MonitoringAlertWorkflowTransitionRecord,
  type MonitoringAlertWorkflowStateRecord,
  type MonitoringAlertWorkflowStatus,
  updateMonitoringAlertWorkflowStateOnApi,
} from '@/lib/monitoring-alerts'

interface AlertsProps {
  initialWorkflowStates?: MonitoringAlertWorkflowStateRecord[]
  initialWorkflowHistory?: MonitoringAlertWorkflowTransitionRecord[]
}

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

function formatUtcTimestamp(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return `${date.toISOString().slice(0, 16).replace('T', ' ')} UTC`
}

function QueueRow({
  alert,
  active,
  onSelect,
}: {
  alert: MonitoringAlertViewRecord
  active: boolean
  onSelect: (alertId: string) => void
}) {
  return (
    <button
      className={cn(
        'grid gap-3 rounded-2xl border p-4 text-left transition-colors',
        active
          ? 'border-cyan-400/30 bg-cyan-400/10 text-cyan-50'
          : 'border-white/10 bg-slate-950/55 text-slate-300 hover:border-white/20 hover:bg-white/[0.06]'
      )}
      type="button"
      onClick={() => onSelect(alert.alertId)}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid gap-1">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">{alert.bagId}</p>
          <p className="text-sm font-semibold text-white">{alert.summary}</p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <Badge className={cn('rounded-full border px-3 py-1 text-[10px] uppercase tracking-[0.22em]', getMonitoringAlertSeverityTone(alert.severity))} variant="outline">
            {alert.severity}
          </Badge>
          <Badge className={cn('rounded-full border px-3 py-1 text-[10px] uppercase tracking-[0.22em]', getMonitoringAlertWorkflowTone(alert.operationalStatus))} variant="outline">
            {alert.operationalStatus}
          </Badge>
        </div>
      </div>

      <div className="grid gap-2 md:grid-cols-3">
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">Quality score</p>
          <p className="mt-1 text-sm font-semibold text-white">{Math.round(alert.qualityScore * 100)}%</p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">Confidence</p>
          <p className="mt-1 text-sm font-semibold text-white">{Math.round(alert.confidence * 100)}%</p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">Review window</p>
          <p className="mt-1 text-sm font-semibold text-white">{alert.reviewWindowDays} days</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-3 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">
        <span>{alert.repositoryStatus}</span>
        <span>{alert.source}</span>
      </div>
    </button>
  )
}

function WorkflowActionButton({
  label,
  nextStatus,
  selected,
  onClick,
  tone,
  disabled,
}: {
  label: string
  nextStatus: MonitoringAlertWorkflowStatus
  selected: boolean
  onClick: (status: MonitoringAlertWorkflowStatus) => void
  tone: 'neutral' | 'success' | 'warning' | 'danger'
  disabled: boolean
}) {
  const toneClass =
    tone === 'success'
      ? 'border-emerald-400/20 bg-emerald-400/10 text-emerald-100 hover:bg-emerald-400/15'
      : tone === 'warning'
        ? 'border-amber-400/20 bg-amber-400/10 text-amber-100 hover:bg-amber-400/15'
        : tone === 'danger'
          ? 'border-rose-400/20 bg-rose-400/10 text-rose-100 hover:bg-rose-400/15'
          : 'border-white/10 bg-white/[0.04] text-slate-200 hover:bg-white/[0.06]'

  return (
    <Button
      className={cn(
        'h-10 rounded-full border px-4 text-xs font-semibold',
        toneClass,
        selected && 'ring-1 ring-cyan-300/60',
        disabled && 'cursor-not-allowed opacity-70'
      )}
      disabled={disabled}
      onClick={() => onClick(nextStatus)}
      type="button"
      variant="ghost"
    >
      {label}
    </Button>
  )
}

function WorkflowHistoryItem({ record }: { record: MonitoringAlertWorkflowTransitionRecord }) {
  const meta = [record.note, record.updatedBy ? `Updated by ${record.updatedBy}` : null].filter(Boolean).join(' · ')

  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/55 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="grid gap-1">
          <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">
            {formatUtcTimestamp(record.changedAt)}
          </p>
          <p className="text-sm font-semibold text-white">
            {record.previousStatus} → {record.nextStatus}
          </p>
        </div>
        <Badge
          className={cn(
            'rounded-full border px-3 py-1 text-[10px] uppercase tracking-[0.22em]',
            getMonitoringAlertWorkflowTone(record.nextStatus)
          )}
          variant="outline"
        >
          {record.nextStatus}
        </Badge>
      </div>
      {meta ? <p className="mt-2 text-xs leading-5 text-slate-400">{meta}</p> : null}
    </div>
  )
}

export function Alerts({
  initialWorkflowStates = [],
  initialWorkflowHistory = [],
}: AlertsProps) {
  const { bags } = useMonitoringBagInventory()
  const snapshot = useLatestResearchSimulationSnapshot()
  const baseAlerts = useMemo(() => buildMonitoringAlertQueue(bags, snapshot), [bags, snapshot])
  const [workflowStates, setWorkflowStates] = useState<MonitoringAlertWorkflowStateRecord[]>(() => initialWorkflowStates)
  const [workflowHistory, setWorkflowHistory] = useState<MonitoringAlertWorkflowTransitionRecord[]>(() => initialWorkflowHistory)
  const [workflowLoading, setWorkflowLoading] = useState(false)
  const [workflowHistoryLoading, setWorkflowHistoryLoading] = useState(false)
  const [workflowError, setWorkflowError] = useState<string | null>(null)
  const [workflowHistoryError, setWorkflowHistoryError] = useState<string | null>(null)
  const [pendingWorkflowStatus, setPendingWorkflowStatus] = useState<MonitoringAlertWorkflowStatus | null>(null)
  const [selectedAlertId, setSelectedAlertId] = useState(() => baseAlerts[0]?.alertId ?? '')

  useEffect(() => {
    if (initialWorkflowStates.length) {
      setWorkflowStates(initialWorkflowStates)
      return
    }

    let cancelled = false

    const hydrateWorkflowStates = async () => {
      setWorkflowLoading(true)
      setWorkflowError(null)

      try {
        const persistedWorkflowStates = await fetchMonitoringAlertWorkflowStatesFromApi()
        if (!cancelled) {
          setWorkflowStates(persistedWorkflowStates)
        }
      } catch (error) {
        if (!cancelled) {
          setWorkflowError(error instanceof Error ? error.message : 'Failed to load monitoring alert workflow states.')
        }
      } finally {
        if (!cancelled) {
          setWorkflowLoading(false)
        }
      }
    }

    void hydrateWorkflowStates()

    return () => {
      cancelled = true
    }
  }, [initialWorkflowStates])

  useEffect(() => {
    if (initialWorkflowHistory.length) {
      setWorkflowHistory(initialWorkflowHistory)
      return
    }

    let cancelled = false

    const hydrateWorkflowHistory = async () => {
      setWorkflowHistoryLoading(true)
      setWorkflowHistoryError(null)

      try {
        const persistedWorkflowHistory = await fetchMonitoringAlertWorkflowHistoryFromApi(50)
        if (!cancelled) {
          setWorkflowHistory(persistedWorkflowHistory)
        }
      } catch (error) {
        if (!cancelled) {
          setWorkflowHistoryError(error instanceof Error ? error.message : 'Failed to load monitoring alert workflow history.')
        }
      } finally {
        if (!cancelled) {
          setWorkflowHistoryLoading(false)
        }
      }
    }

    void hydrateWorkflowHistory()

    return () => {
      cancelled = true
    }
  }, [initialWorkflowHistory])

  const alerts = useMemo(
    () => mergeMonitoringAlertWorkflowStates(baseAlerts, workflowStates),
    [baseAlerts, workflowStates]
  )
  const selectedAlert = alerts.find((alert) => alert.alertId === selectedAlertId) ?? alerts[0] ?? null
  const selectedBag = selectedAlert ? bags.find((bag) => bag.bagId === selectedAlert.bagId) ?? null : null
  const selectedAlertHistory = useMemo(() => {
    if (!selectedAlert) {
      return []
    }

    return workflowHistory
      .filter((record) => record.bagId === selectedAlert.bagId || record.alertId === selectedAlert.alertId)
      .slice(0, 4)
  }, [selectedAlert, workflowHistory])
  const auditTrail = selectedAlertHistory.length ? selectedAlertHistory : workflowHistory.slice(0, 4)
  const auditTrailLabel = selectedAlertHistory.length ? 'Selected bag trail' : 'Recent queue trail'
  const auditTrailNote = selectedAlertHistory.length
    ? 'Minimal audit trail for the selected bag. This stays separate from the forecast-derived severity.'
    : 'No transitions recorded for this bag yet, so the most recent queue trail is shown.'

  useEffect(() => {
    if (!alerts.length) {
      setSelectedAlertId('')
      return
    }

    if (!alerts.some((alert) => alert.alertId === selectedAlertId)) {
      setSelectedAlertId(alerts[0].alertId)
    }
  }, [alerts, selectedAlertId])

  const totalAlerts = alerts.length
  const highCriticalAlerts = alerts.filter((alert) => alert.severity === 'High' || alert.severity === 'Critical').length
  const elevatedAlerts = alerts.filter((alert) => alert.severity === 'Elevated').length
  const reviewSoonAlerts = alerts.filter((alert) => alert.reviewWindowDays <= 3).length
  const reviewedAlerts = alerts.filter((alert) => alert.operationalStatus === 'Acknowledged' || alert.operationalStatus === 'Resolved').length
  const simulationLinkedAlerts = alerts.filter((alert) => alert.source === 'forecast+simulation').length

  const updateWorkflowStatus = async (status: MonitoringAlertWorkflowStatus) => {
    if (!selectedAlert) {
      return
    }

    setPendingWorkflowStatus(status)
    setWorkflowError(null)

    try {
      const persistedWorkflowState = await updateMonitoringAlertWorkflowStateOnApi({
        bagId: selectedAlert.bagId,
        workflowStatus: status,
      })

      setWorkflowStates((current) => {
        const existingIndex = current.findIndex(
          (record) =>
            record.alertId === persistedWorkflowState.alertId ||
            record.bagId === persistedWorkflowState.bagId
        )

        if (existingIndex === -1) {
          return [persistedWorkflowState, ...current]
        }

        const next = [...current]
        next[existingIndex] = persistedWorkflowState
        return next
      })
    } catch (error) {
      setWorkflowError(error instanceof Error ? error.message : 'Failed to update alert workflow state.')
    } finally {
      setPendingWorkflowStatus(null)
    }
  }

  if (!alerts.length) {
    return (
      <div className="grid gap-6">
        <section className="panel relative overflow-hidden !border-white/10 !bg-[linear-gradient(180deg,rgba(15,23,42,0.97),rgba(15,23,42,0.84))] !shadow-[0_24px_80px_-48px_rgba(8,15,40,0.95)]">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(244,63,94,0.12),transparent_34%),radial-gradient(circle_at_bottom_left,rgba(56,189,248,0.08),transparent_32%)]"
          />
          <div className="relative grid gap-5">
            <div className="flex flex-wrap items-center gap-3">
              <p className="eyebrow">Operational monitoring</p>
              <span className="inline-flex items-center rounded-full border border-rose-400/20 bg-rose-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-rose-100">
                No open alerts
              </span>
            </div>
            <div className="grid gap-3">
              <h1 className="page-title">Alerts</h1>
              <p className="page-copy max-w-3xl">
                Forecast-derived alerting items will appear here once a bag moves into watch, elevated, or high-risk territory.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-slate-300" variant="outline">
                Forecast-derived
              </Badge>
              <Badge className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-slate-300" variant="outline">
                Bag → forecast → alerts
              </Badge>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button asChild className="rounded-full">
                <Link href="/monitoring/quality-forecast">
                  Open Quality Forecast
                  <ArrowRight className="size-4" />
                </Link>
              </Button>
              <Button asChild className="rounded-full" variant="outline">
                <Link href="/monitoring/bag-repo">Open Bag Repository</Link>
              </Button>
            </div>
          </div>
        </section>
      </div>
    )
  }

  return (
    <div className="grid gap-6">
      <section className="panel relative overflow-hidden !border-white/10 !bg-[linear-gradient(180deg,rgba(15,23,42,0.97),rgba(15,23,42,0.84))] !shadow-[0_24px_80px_-48px_rgba(8,15,40,0.95)]">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(244,63,94,0.12),transparent_34%),radial-gradient(circle_at_bottom_left,rgba(56,189,248,0.08),transparent_32%)]"
        />
        <div className="relative grid gap-6 xl:grid-cols-[minmax(0,1.18fr)_minmax(360px,0.82fr)]">
          <div className="grid gap-5">
            <div className="flex flex-wrap items-center gap-3">
              <p className="eyebrow">Operational monitoring</p>
              <span className="inline-flex items-center rounded-full border border-rose-400/20 bg-rose-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-rose-100">
                Forecast-derived triage
              </span>
            </div>
            <div className="grid gap-3">
              <h1 className="page-title">Alerts</h1>
              <p className="page-copy max-w-3xl">
                Turn forecast risk into prioritized review items, then move quickly from the queue into operator action without leaving Monitoring.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-slate-300" variant="outline">
                {totalAlerts} open alerts
              </Badge>
              <Badge className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-slate-300" variant="outline">
                {simulationLinkedAlerts} simulation-linked
              </Badge>
              <Badge className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-slate-300" variant="outline">
                Bag → forecast → alerts
              </Badge>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <MetricTile icon={Bell} label="Total alerts" value={String(totalAlerts)} hint="Forecast-derived queue items ready for review." />
              <MetricTile icon={ShieldAlert} label="High / critical" value={String(highCriticalAlerts)} hint="Items that need the fastest operator attention." />
              <MetricTile icon={AlertTriangle} label="Elevated" value={String(elevatedAlerts)} hint="Bags trending toward tighter review windows." />
              <MetricTile icon={Clock3} label="Needs review soon" value={String(reviewSoonAlerts)} hint="Alerts with a review window of 3 days or less." />
              <MetricTile icon={CheckCircle2} label="Acknowledged / resolved" value={String(reviewedAlerts)} hint="Items already moved through the workflow." />
            </div>
          </div>

          <aside className="rounded-[2rem] border border-white/10 bg-white/[0.04] p-5 shadow-[0_20px_60px_-34px_rgba(0,0,0,0.78)] backdrop-blur-sm">
            <div className="flex items-center justify-between gap-3">
              <div className="grid gap-1">
                <p className="eyebrow">Operational brief</p>
                <h2 className="text-2xl font-semibold tracking-tight text-white">Why the queue matters</h2>
              </div>
              <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">
                Live
              </span>
            </div>

            <div className="mt-5 grid gap-3">
              <div className="rounded-3xl border border-white/10 bg-slate-950/55 p-4">
                <div className="flex items-center gap-3">
                  <span className="grid size-10 place-items-center rounded-2xl border border-rose-400/20 bg-rose-400/10 text-rose-100">
                    <Bell className="size-4" />
                  </span>
                  <div className="grid gap-1">
                    <p className="text-sm font-semibold text-white">Forecast-derived alerts</p>
                    <p className="text-sm leading-6 text-slate-400">
                      Each alert is built from a Monitoring forecast projection and the active bag record.
                    </p>
                  </div>
                </div>
              </div>

              <div className="rounded-3xl border border-white/10 bg-slate-950/55 p-4">
                <div className="flex items-center gap-3">
                  <span className="grid size-10 place-items-center rounded-2xl border border-cyan-400/20 bg-cyan-400/10 text-cyan-100">
                    <TrendingUp className="size-4" />
                  </span>
                  <div className="grid gap-1">
                    <p className="text-sm font-semibold text-white">Severity first</p>
                    <p className="text-sm leading-6 text-slate-400">
                      Biological risk and operator workflow status stay separate so triage stays readable.
                    </p>
                  </div>
                </div>
              </div>

              <div className="rounded-3xl border border-white/10 bg-slate-950/55 p-4">
                <div className="flex items-center gap-3">
                  <span className="grid size-10 place-items-center rounded-2xl border border-violet-400/20 bg-violet-400/10 text-violet-100">
                    <FlaskConical className="size-4" />
                  </span>
                  <div className="grid gap-1">
                    <p className="text-sm font-semibold text-white">Simulation inheritance</p>
                    <p className="text-sm leading-6 text-slate-400">
                      Alerts can inherit a linked simulation snapshot when one is available for the current research context.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-5 flex flex-wrap gap-2">
              <Button asChild className="rounded-full">
                <Link href="/monitoring/quality-forecast">
                  Open Quality Forecast
                  <ArrowRight className="size-4" />
                </Link>
              </Button>
              <Button asChild className="rounded-full" variant="outline">
                <Link href="/monitoring/bag-repo">Open Bag Repository</Link>
              </Button>
            </div>
          </aside>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.14fr)_minmax(360px,0.86fr)]">
        <div className="grid gap-6">
          <Card className="border-white/10 bg-[linear-gradient(180deg,rgba(26,29,35,0.96),rgba(19,22,28,0.98))] shadow-[0_18px_48px_-30px_rgba(0,0,0,0.8)]">
            <CardHeader className="space-y-2">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="grid gap-2">
                  <CardTitle className="text-2xl tracking-tight text-white">Prioritized queue</CardTitle>
                  <CardDescription className="max-w-2xl text-slate-400">
                    Alerts are sorted by severity, urgency, confidence, and drift so the highest-risk bags stay on top.
                  </CardDescription>
                </div>
                <div className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">
                  Forecast queue
                </div>
              </div>
            </CardHeader>
            <CardContent className="grid gap-3">
              {alerts.map((alert) => (
                <QueueRow
                  key={alert.alertId}
                  active={alert.alertId === selectedAlert?.alertId}
                  alert={alert}
                  onSelect={setSelectedAlertId}
                />
              ))}
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-6">
          <Card className="border-white/10 bg-[linear-gradient(180deg,rgba(26,29,35,0.96),rgba(19,22,28,0.98))] shadow-[0_18px_48px_-30px_rgba(0,0,0,0.8)]">
            <CardHeader className="space-y-2">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="grid gap-2">
                  <CardTitle className="text-2xl tracking-tight text-white">Selected alert</CardTitle>
                  <CardDescription className="max-w-2xl text-slate-400">
                    Inspect why the alert fired, then decide whether to acknowledge, review, escalate, or resolve it.
                  </CardDescription>
                </div>
                <Badge className={cn('rounded-full border px-3 py-1 text-[10px] uppercase tracking-[0.22em]', selectedAlert ? getMonitoringAlertSeverityTone(selectedAlert.severity) : 'border-white/10 bg-white/[0.04] text-slate-300')} variant="outline">
                  {selectedAlert ? selectedAlert.severity : 'No selection'}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="grid gap-4">
              {selectedAlert && selectedBag ? (
                <>
                  <div className="grid gap-4 rounded-3xl border border-white/10 bg-slate-950/55 p-5">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="grid gap-1">
                        <p className="eyebrow">Bag context</p>
                        <h3 className="text-2xl font-semibold tracking-tight text-white">{selectedBag.bagId}</h3>
                        <p className="text-sm text-slate-400">
                          {selectedBag.donorId} · {selectedBag.entryDate}
                        </p>
                      </div>
                      <div className="flex flex-col items-end gap-2">
                    <Badge className={cn('rounded-full border px-3 py-1 text-[10px] uppercase tracking-[0.22em]', getMonitoringBagStatusTone(selectedBag.repositoryStatus))} variant="outline">
                      {selectedBag.repositoryStatus}
                    </Badge>
                    <Badge className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[10px] uppercase tracking-[0.22em] text-slate-300" variant="outline">
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

                  <div className="grid gap-3 rounded-3xl border border-white/10 bg-white/[0.04] p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Why it fired</p>
                      <ShieldAlert className="size-4 text-rose-300" />
                    </div>
                    <p className="text-sm leading-6 text-slate-300">{selectedAlert.summary}</p>
                    <div className="flex flex-wrap gap-2">
                      {selectedAlert.triggerSignals.map((signal) => (
                        <span
                          className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-300"
                          key={signal}
                        >
                          {signal}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="grid gap-3 rounded-3xl border border-white/10 bg-white/[0.04] p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Forecast result</p>
                      <span className={cn('inline-flex items-center rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em]', getMonitoringAlertWorkflowTone(selectedAlert.operationalStatus))}>
                        {selectedAlert.operationalStatus}
                      </span>
                    </div>
                    <p className="text-sm leading-6 text-slate-300">{selectedAlert.recommendation}</p>
                    <p className="text-sm leading-6 text-slate-400">{selectedAlert.forecastSnapshot.snapshotSummary}</p>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    <DetailField label="Risk band" value={selectedAlert.riskBand} />
                    <DetailField label="Quality score" value={`${Math.round(selectedAlert.qualityScore * 100)}%`} />
                    <DetailField label="Confidence" value={`${Math.round(selectedAlert.confidence * 100)}%`} />
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    <DetailField label="Drift rate" value={`${(selectedAlert.driftRate * 100).toFixed(1)}% / day`} />
                    <DetailField label="Review window" value={`${selectedAlert.reviewWindowDays} days`} />
                    <DetailField label="Source" value={selectedAlert.source} />
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <DetailField label="Created" value={formatUtcTimestamp(selectedAlert.createdAt)} />
                    <DetailField label="Updated" value={formatUtcTimestamp(selectedAlert.updatedAt)} />
                  </div>
                </>
              ) : (
                <div className="rounded-3xl border border-white/10 bg-slate-950/55 p-5 text-sm leading-6 text-slate-400">
                  No alert is selected. Choose one from the queue to inspect its forecast summary and operator actions.
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="border-white/10 bg-[linear-gradient(180deg,rgba(26,29,35,0.96),rgba(19,22,28,0.98))] shadow-[0_18px_48px_-30px_rgba(0,0,0,0.8)]">
            <CardHeader className="space-y-2">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="grid gap-2">
                  <CardTitle className="text-2xl tracking-tight text-white">Operator actions</CardTitle>
                  <CardDescription className="max-w-2xl text-slate-400">
                    Status changes stay separate from biological risk so the queue remains readable.
                  </CardDescription>
                </div>
                <Clock3 className="size-4 text-cyan-300" />
              </div>
            </CardHeader>
            <CardContent className="grid gap-4">
              {selectedAlert ? (
                <>
                  <div className="flex flex-wrap gap-2">
                    <WorkflowActionButton label="Acknowledge" nextStatus="Acknowledged" selected={selectedAlert.operationalStatus === 'Acknowledged'} onClick={updateWorkflowStatus} tone="neutral" disabled={pendingWorkflowStatus !== null} />
                    <WorkflowActionButton label="Mark in review" nextStatus="In review" selected={selectedAlert.operationalStatus === 'In review'} onClick={updateWorkflowStatus} tone="warning" disabled={pendingWorkflowStatus !== null} />
                    <WorkflowActionButton label="Escalate" nextStatus="Escalated" selected={selectedAlert.operationalStatus === 'Escalated'} onClick={updateWorkflowStatus} tone="danger" disabled={pendingWorkflowStatus !== null} />
                    <WorkflowActionButton label="Resolve" nextStatus="Resolved" selected={selectedAlert.operationalStatus === 'Resolved'} onClick={updateWorkflowStatus} tone="success" disabled={pendingWorkflowStatus !== null} />
                  </div>
                  <div className="rounded-3xl border border-white/10 bg-slate-950/55 p-4">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Current workflow state</p>
                    <p className="mt-2 text-sm font-semibold text-white">{selectedAlert.operationalStatus}</p>
                    <p className="mt-1 text-sm leading-6 text-slate-400">
                      This workflow state persists in the Monitoring backend and reloads with the queue.
                    </p>
                  </div>
                  <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Workflow persistence</p>
                      <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-300">
                        Backend-backed
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-slate-300">
                      Workflow changes are stored in the Monitoring backend and reload with the queue.
                    </p>
                    <p className="mt-1 text-sm leading-6 text-slate-400">
                      Biological risk stays forecast-derived; this layer only manages operator workflow state.
                    </p>
                  </div>
                  <div className="grid gap-3 rounded-3xl border border-white/10 bg-slate-950/55 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Workflow history</p>
                      <Clock3 className="size-4 text-cyan-300" />
                    </div>
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-white">{auditTrailLabel}</p>
                      <Badge className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[10px] uppercase tracking-[0.22em] text-slate-300" variant="outline">
                        {auditTrail.length} entries
                      </Badge>
                    </div>
                    <p className="text-sm leading-6 text-slate-400">{auditTrailNote}</p>
                    {workflowHistoryLoading ? (
                      <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 px-4 py-3 text-sm leading-6 text-cyan-50">
                        Syncing workflow history from the Monitoring backend...
                      </div>
                    ) : workflowHistoryError ? (
                      <div className="rounded-2xl border border-rose-400/20 bg-rose-400/10 px-4 py-3 text-sm leading-6 text-rose-50">
                        {workflowHistoryError}
                      </div>
                    ) : auditTrail.length ? (
                      <div className="grid gap-2">
                        {auditTrail.map((record) => (
                          <WorkflowHistoryItem key={`${record.alertId}-${record.changedAt}`} record={record} />
                        ))}
                      </div>
                    ) : (
                      <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm leading-6 text-slate-400">
                        No workflow transitions recorded yet for this bag.
                      </div>
                    )}
                  </div>
                  {workflowLoading ? (
                    <div className="rounded-3xl border border-cyan-400/20 bg-cyan-400/10 p-4 text-sm leading-6 text-cyan-50">
                      Syncing alert workflow state from the Monitoring backend...
                    </div>
                  ) : null}
                  {workflowError ? (
                    <div className="rounded-3xl border border-rose-400/20 bg-rose-400/10 p-4 text-sm leading-6 text-rose-50">
                      {workflowError}
                    </div>
                  ) : null}
                </>
              ) : (
                <div className="rounded-3xl border border-white/10 bg-slate-950/55 p-5 text-sm leading-6 text-slate-400">
                  Select an alert to expose the operator action surface.
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="border-white/10 bg-[linear-gradient(180deg,rgba(26,29,35,0.96),rgba(19,22,28,0.98))] shadow-[0_18px_48px_-30px_rgba(0,0,0,0.8)]">
            <CardHeader className="space-y-2">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="grid gap-2">
                  <CardTitle className="text-2xl tracking-tight text-white">Handoff links</CardTitle>
                  <CardDescription className="max-w-2xl text-slate-400">
                    Jump back to the inventory record or reopen the forecast that produced the alert.
                  </CardDescription>
                </div>
                <ArrowRight className="size-4 text-cyan-300" />
              </div>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-3">
              <Button asChild className="rounded-full">
                <Link href="/monitoring/bag-repo">Open Bag Repository</Link>
              </Button>
              <Button asChild className="rounded-full" variant="outline">
                <Link href="/monitoring/quality-forecast">Open Quality Forecast</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
