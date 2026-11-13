'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AlertCircle, CheckCircle2, CircleDashed, Database, FileCheck, Loader2, Lock, ShieldAlert, XCircle } from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { cn } from '@/lib/utils'
import {
  draftDataContract,
  focusSummary,
  launchGate,
  limitationNotes,
  preflightView,
  referenceActivation,
  referenceProfileView,
  speciesList,
  speciesSeries,
  type PreflightView,
  type ReferenceProfileView,
} from '@/lib/calibration-journey.mjs'

interface CalibrationJourneyProps {
  datasetId: string | null
  datasetLabel: string
  isUserDataset: boolean
  experiment: { expTime?: number[]; expData?: Record<string, number[]> } | null
}

type StepStatus = 'done' | 'current' | 'blocked' | 'pending'

function fmt(value: number | null | undefined, digits = 4) {
  return typeof value === 'number' && Number.isFinite(value) ? value.toPrecision(digits) : '—'
}

function StepChip({ label, status }: { label: string; status: StepStatus }) {
  const Icon = status === 'done' ? CheckCircle2 : status === 'blocked' ? XCircle : CircleDashed
  return (
    <li
      className={cn(
        'flex min-w-0 items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold',
        status === 'done' && 'border-emerald-400/30 text-emerald-200',
        status === 'current' && 'border-cyan-400/40 text-cyan-100',
        status === 'blocked' && 'border-rose-400/30 text-rose-200',
        status === 'pending' && 'border-white/10 text-slate-400'
      )}
      data-step-status={status}
    >
      <Icon className="size-3.5 shrink-0" />
      <span className="truncate">{label}</span>
    </li>
  )
}

function Answer({ label, value }: { label: string; value: boolean | null }) {
  return (
    <div className="rounded-xl border border-white/10 p-3" data-answer={label}>
      <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">{label}</p>
      <p className={cn('mt-1 text-sm font-semibold', value === true ? 'text-emerald-300' : value === false ? 'text-rose-300' : 'text-slate-400')}>
        {value === true ? 'Yes' : value === false ? 'No' : 'Not checked'}
      </p>
    </div>
  )
}

function SeriesChart({ points, unit }: { points: ReturnType<typeof speciesSeries>; unit: string | null }) {
  const values = points.flatMap((p) => [p.observed, p.predicted]).filter((v): v is number => v !== null)
  if (!points.length || !values.length) return <p className="text-sm text-muted-foreground">No dated values.</p>
  const days = points.map((p) => p.day)
  const [x0, x1] = [Math.min(...days), Math.max(...days)]
  const [y0, y1] = [Math.min(...values), Math.max(...values)]
  const sx = (d: number) => 24 + ((d - x0) / Math.max(x1 - x0, 1e-12)) * 272
  const sy = (v: number) => 112 - ((v - y0) / Math.max(y1 - y0, 1e-12)) * 96
  const line = (key: 'observed' | 'predicted') =>
    points.filter((p) => p[key] !== null).map((p) => `${sx(p.day)},${sy(p[key] as number)}`).join(' ')
  return (
    <figure className="grid gap-2">
      <svg viewBox="0 0 320 128" className="h-40 w-full" role="img" aria-label="Observed versus predicted by day">
        <polyline points={line('observed')} fill="none" stroke="currentColor" className="text-emerald-300" strokeWidth={2} />
        <polyline points={line('predicted')} fill="none" stroke="currentColor" className="text-cyan-300" strokeWidth={2} strokeDasharray="5 4" />
        {points.map((p) => (
          <text key={p.day} x={sx(p.day)} y={126} textAnchor="middle" className="fill-slate-400 text-[9px]">J{p.day}</text>
        ))}
      </svg>
      <figcaption className="text-xs text-muted-foreground">
        Solid: observed · dashed: predicted ({unit ?? 'unit not stated'}). Range {fmt(y0)}–{fmt(y1)}.
      </figcaption>
    </figure>
  )
}

export function CalibrationJourney({ datasetId, datasetLabel, isUserDataset, experiment }: CalibrationJourneyProps) {
  const draft = useMemo(() => (isUserDataset ? draftDataContract(datasetId, experiment) : null), [datasetId, experiment, isUserDataset])
  const [preflight, setPreflight] = useState<PreflightView>(preflightView(null))
  const [checking, setChecking] = useState(false)
  const [preflightError, setPreflightError] = useState<string | null>(null)
  const [reference, setReference] = useState<ReferenceProfileView | null>(null)
  const [referenceError, setReferenceError] = useState<string | null>(null)
  const [species, setSpecies] = useState<string>('EGLC')
  const preflightRequest = useRef(0)

  useEffect(() => {
    preflightRequest.current += 1
    setPreflight(preflightView(null))
    setPreflightError(null)
    setChecking(false)
  }, [draft])

  const checkContract = useCallback(async () => {
    if (!draft) return
    const request = ++preflightRequest.current
    setChecking(true)
    setPreflightError(null)
    try {
      const response = await apiClient.post('/calibration/preflight', { data_contract: draft.contract })
      if (request === preflightRequest.current) setPreflight(preflightView(response.data as Record<string, any>))
    } catch {
      if (request === preflightRequest.current) {
        setPreflight(preflightView(null))
        setPreflightError('The preflight service is unreachable; nothing was checked or launched.')
      }
    } finally {
      if (request === preflightRequest.current) setChecking(false)
    }
  }, [draft])

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const list = await apiClient.get('/calibration/reference-profiles')
        const first = (list.data as any)?.profiles?.[0]
        if (!first) {
          if (!cancelled) setReference({ state: 'empty', available: false, reason: 'No reference profile is registered.' })
          return
        }
        const detail = await apiClient.get(`/calibration/reference-profiles/${encodeURIComponent(first.profile_id)}`)
        if (!cancelled) setReference(referenceProfileView(detail.data as Record<string, any>))
      } catch {
        if (!cancelled) {
          setReferenceError('The reference registry is unreachable.')
          setReference({ state: 'unavailable', available: false, reason: 'The reference registry is unreachable.' })
        }
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  const gate = launchGate(preflight)
  const activation = referenceActivation(reference, { explicit: true })
  const extracellular = reference?.available ? speciesList(reference, 'extracellular') : []
  const series = reference?.available ? speciesSeries(reference, species) : []
  const steps: Array<[string, StepStatus]> = [
    ['Data', isUserDataset ? 'done' : 'current'],
    ['Verification', !isUserDataset ? 'pending' : preflight.state === 'not_checked' ? 'current'
      : preflight.dataValid === false ? 'blocked' : 'done'],
    ['Calibration', gate.contractLaunchAllowed ? 'current' : isUserDataset && preflight.state !== 'not_checked' ? 'blocked' : 'pending'],
    ['Results', reference?.available ? 'current' : 'pending'],
  ]

  return (
    <div className="grid gap-5" data-testid="calibration-journey">
      <ol className="flex flex-wrap gap-2" aria-label="Calibration journey">
        {steps.map(([label, status]) => (
          <StepChip key={label} label={label} status={status} />
        ))}
      </ol>

      <Card id="data-verification">
        <CardHeader>
          <CardTitle role="heading" aria-level={2} className="flex items-center gap-2"><Database className="size-4" /> Data and verification</CardTitle>
          <CardDescription className="break-words">
            {isUserDataset
              ? `Active upload: ${datasetLabel}. The contract below carries only what the upload contains; missing fields stay missing.`
              : 'No user dataset is active. Upload data to check it against the versioned contract; the reference profile below is a separate, read-only comparator.'}
          </CardDescription>
        </CardHeader>
        {isUserDataset && draft ? (
          <CardContent className="grid gap-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <Answer label="Data valid" value={preflight.dataValid} />
              <Answer label="Engine compatible" value={preflight.engineCompatible} />
              <Answer label="Launch allowed" value={preflight.state === 'not_checked' ? null : preflight.launchAllowed} />
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Button onClick={checkContract} disabled={checking} variant="secondary" className="gap-2">
                {checking ? <Loader2 className="size-4 animate-spin" /> : <FileCheck className="size-4" />}
                Check data contract
              </Button>
              <span className="text-xs text-muted-foreground">Runs no solver and launches nothing.</span>
            </div>
            {preflightError ? <p className="text-sm text-destructive">{preflightError}</p> : null}
            <details className="rounded-xl border border-white/10 p-3 text-sm">
              <summary className="cursor-pointer font-semibold">Fields the upload does not provide ({draft.missing.length})</summary>
              <ul className="mt-2 list-disc pl-5 text-muted-foreground">
                {draft.missing.map((field) => <li key={field} className="break-words">{field}</li>)}
              </ul>
            </details>
            {[...(preflight.errors ?? []), ...(preflight.blocking ?? [])].length ? (
              <ul className="grid gap-1 text-sm" data-testid="preflight-issues">
                {[...(preflight.errors ?? []), ...(preflight.blocking ?? [])].map((issue, i) => (
                  <li key={`${issue.code}-${i}`} className="break-words text-muted-foreground">
                    <span className="font-mono text-xs text-rose-300">{issue.code}</span> · {issue.path} · {issue.message}
                  </li>
                ))}
              </ul>
            ) : null}
            <div className="flex flex-wrap items-center gap-3 border-t border-white/10 pt-3">
              {/* Disabled in this tranche: even an allowed preflight has no contractual worker wired yet. */}
              <Button disabled className="gap-2" data-testid="contract-launch" aria-disabled="true">
                <Lock className="size-4" /> Launch contractual calibration
              </Button>
              <span className="text-xs text-muted-foreground">
                {gate.reason ?? 'Contractual launches are not wired to a qualified engine in this version.'}
              </span>
            </div>
          </CardContent>
        ) : null}
      </Card>

      <Card id="reference-profile" data-testid="reference-profile">
        <CardHeader>
          <CardTitle role="heading" aria-level={2} className="flex flex-wrap items-center gap-2">
            <ShieldAlert className="size-4" /> Reference profile
            <Badge variant="secondary" className="rounded-full">Preview only · never active</Badge>
          </CardTitle>
          <CardDescription>
            Read-only comparator for one archived table. It is not applied to your data and is not a validated RBC calibration.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          {referenceError ? <p className="text-sm text-destructive">{referenceError}</p> : null}
          {!reference && !referenceError ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" /> Loading registry…</p>
          ) : null}
          {reference && !reference.available ? (
            <div className="flex items-start gap-3 rounded-xl border border-white/10 p-4" data-testid="reference-unavailable" data-state={reference.state}>
              <AlertCircle className="size-5 shrink-0 text-muted-foreground" />
              <div className="grid gap-1 text-sm">
                <p className="font-semibold">Reference unavailable ({reference.state})</p>
                <p className="break-words text-muted-foreground">{reference.reason ?? 'No details.'}</p>
                {reference.nextTask ? <p className="break-words text-muted-foreground">Next task: {reference.nextTask}</p> : null}
              </div>
            </div>
          ) : null}
          {reference?.available ? (
            <>
              <div className="grid gap-2 text-sm sm:grid-cols-2">
                <p className="break-words"><span className="text-muted-foreground">Selected vector:</span> {reference.selected_id} ({reference.selected_kind}); improved over fallback: {String(reference.improved_over_fallback)}</p>
                <p className="break-all"><span className="text-muted-foreground">Receipt:</span> <span className="font-mono text-xs">{String(reference.receipt?.receipt_sha256 ?? '').slice(0, 16)}…</span></p>
                <p className="break-words"><span className="text-muted-foreground">Units:</span> {reference.scope?.unit_status?.status}</p>
                <p className="break-words"><span className="text-muted-foreground">Objective:</span> {reference.objective_version}</p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <Button disabled className="gap-2" data-testid="reference-activate" aria-disabled="true">
                  <Lock className="size-4" /> Activate
                </Button>
                <span className="text-xs text-muted-foreground">
                  {activation.allowed ? '' : 'Activation is forbidden by this artifact (activation_allowed: false), even with matching identities.'}
                </span>
              </div>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Focus</TableHead>
                      <TableHead>Normalized RMSE</TableHead>
                      <TableHead>J15 predicted − observed</TableHead>
                      <TableHead>Slope predicted / observed (per day)</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {focusSummary(reference).map((row) => (
                      <TableRow key={row.channel}>
                        <TableCell className="font-semibold">{row.channel}</TableCell>
                        <TableCell>{fmt(row.normalizedRmse)}</TableCell>
                        <TableCell>{fmt(row.j15Residual)}</TableCell>
                        <TableCell>{fmt(row.slopePredicted)} / {fmt(row.slopeObserved)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <div className="grid gap-2">
                  <label className="text-xs font-semibold text-muted-foreground" htmlFor="reference-species">Extracellular species</label>
                  <select
                    id="reference-species"
                    className="h-9 rounded-md border border-white/10 bg-transparent px-2 text-sm"
                    value={species}
                    onChange={(event) => setSpecies(event.target.value)}
                  >
                    {extracellular.map((name) => <option key={name} value={name}>{name}</option>)}
                  </select>
                  <SeriesChart points={series} unit={series[0]?.unit ?? null} />
                </div>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Day</TableHead>
                        <TableHead>Observed</TableHead>
                        <TableHead>Predicted</TableHead>
                        <TableHead>Residual</TableHead>
                        <TableHead>Normalized</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {series.map((p) => (
                        <TableRow key={p.day}>
                          <TableCell>J{p.day}</TableCell>
                          <TableCell>{fmt(p.observed)}</TableCell>
                          <TableCell>{fmt(p.predicted)}</TableCell>
                          <TableCell>{fmt(p.residual)}</TableCell>
                          <TableCell>{p.normalizedResidual === null ? 'zero band' : fmt(p.normalizedResidual)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
              <div className="grid gap-1 text-xs text-muted-foreground">
                <p>Fit scores: release utility on working bands (not assay SD). Numerical qualification: {reference.receipt?.fallback_qualification ?? 'this campaign'}. No free-ODE biological verdict is implied.</p>
              </div>
              <details className="rounded-xl border border-white/10 p-3 text-sm" open>
                <summary className="cursor-pointer font-semibold">Limitations</summary>
                <ul className="mt-2 list-disc pl-5 text-muted-foreground" data-testid="reference-limitations">
                  {limitationNotes(reference).map((note) => <li key={note} className="break-words">{note}</li>)}
                </ul>
              </details>
            </>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}
