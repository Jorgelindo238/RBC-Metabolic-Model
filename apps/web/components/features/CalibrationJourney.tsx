'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { FileCheck, Loader2, Lock } from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { StatusLine, answerTone } from '@/components/platform/research/StatusLine'
import { WithInspector } from '@/components/platform/research/Inspector'
import {
  draftDataContract,
  focusSummary,
  launchGate,
  limitationNotes,
  preflightView,
  referenceProfileView,
  speciesList,
  speciesSeries,
  type PreflightView,
  type ReferenceProfileView,
} from '@/lib/calibration-journey.mjs'

export type CalibrationView = 'data' | 'reference' | 'legacy'

interface CalibrationJourneyProps {
  view: CalibrationView
  datasetId: string | null
  datasetLabel: string
  isUserDataset: boolean
  experiment: { expTime?: number[]; expData?: Record<string, number[]> } | null
}

/** Summary display only (4 significant digits); the full stored value is kept in the title attribute. */
function Num({ value }: { value: number | null | undefined }) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return <>—</>
  return <span className="r-num" title={String(value)}>{value.toPrecision(4)}</span>
}

function answer(value: boolean | null) {
  return value === true ? 'Yes' : value === false ? 'No' : 'Not checked'
}

/** Deduplicated limitations in three plain groups; nothing is dropped. */
function groupLimitations(notes: string[]) {
  const seen = new Set<string>()
  const groups: Record<'Energy' | 'Fit' | 'Data provenance', string[]> = { Energy: [], Fit: [], 'Data provenance': [] }
  for (const note of notes) {
    const key = note.trim().toLowerCase().replace(/[.\s]+$/, '')
    if (seen.has(key)) continue
    seen.add(key)
    const group = /atp|adp|adenylate|latent/i.test(note) ? 'Energy' : /channel|band|rmse|fit/i.test(note) ? 'Fit' : 'Data provenance'
    groups[group].push(note)
  }
  return groups
}

function SeriesChart({ points, unit }: { points: ReturnType<typeof speciesSeries>; unit: string | null }) {
  const values = points.flatMap((p) => [p.observed, p.predicted]).filter((v): v is number => v !== null)
  if (!points.length || !values.length) return <p className="research-muted">No dated values.</p>
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
        <polyline points={line('observed')} fill="none" stroke="var(--r-ok)" strokeWidth={2} />
        <polyline points={line('predicted')} fill="none" stroke="var(--r-accent)" strokeWidth={2} strokeDasharray="5 4" />
        {points.map((p) => (
          <text key={p.day} x={sx(p.day)} y={126} textAnchor="middle" fill="var(--r-text-3)" fontSize={9}>J{p.day}</text>
        ))}
      </svg>
      <figcaption className="research-muted">Solid: observed · dashed: predicted ({unit ?? 'unit not stated'}).</figcaption>
    </figure>
  )
}

export function CalibrationJourney({ view, datasetId, datasetLabel, isUserDataset, experiment }: CalibrationJourneyProps) {
  const draft = useMemo(() => (isUserDataset ? draftDataContract(datasetId, experiment) : null), [datasetId, experiment, isUserDataset])
  const [preflight, setPreflight] = useState<PreflightView>(preflightView(null))
  const [checking, setChecking] = useState(false)
  const [preflightError, setPreflightError] = useState<string | null>(null)
  const [reference, setReference] = useState<ReferenceProfileView | null>(null)
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
        if (!cancelled) setReference({ state: 'unavailable', available: false, reason: 'The reference registry is unreachable.' })
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  const gate = launchGate(preflight)
  const issues = [...(preflight.errors ?? []), ...(preflight.blocking ?? [])]
  const extracellular = reference?.available ? speciesList(reference, 'extracellular') : []
  const series = reference?.available ? speciesSeries(reference, species) : []
  const limitations = reference?.available ? groupLimitations(limitationNotes(reference)) : null
  const strict = reference?.available ? reference.scores?.strict : null

  return (
    <div data-testid="calibration-journey">
      <section id="data-verification" role="tabpanel" aria-labelledby="data-verification-tab" hidden={view !== 'data'} tabIndex={0} className="grid gap-4">
        {!isUserDataset || !draft ? (
          <p className="research-muted" data-testid="no-user-dataset">
            No user dataset is active. <Link className="research-text-link" href="/research/data-upload">Import data</Link> to
            check it against the data contract. The reference is a separate, read-only comparator.
          </p>
        ) : (
          <>
            <p className="research-muted break-words">Active upload: {datasetLabel}. Missing fields stay missing; nothing is substituted.</p>
            <div className="grid gap-2" data-testid="preflight-answers">
              <StatusLine tone={answerTone(preflight.dataValid)} label="Data valid" value={answer(preflight.dataValid)} />
              <StatusLine tone={answerTone(preflight.engineCompatible)} label="Engine compatible" value={answer(preflight.engineCompatible)} />
              <StatusLine tone={preflight.state === 'not_checked' ? 'unknown' : answerTone(preflight.launchAllowed)} label="Launch allowed"
                value={preflight.state === 'not_checked' ? 'Not checked' : answer(preflight.launchAllowed)} detail={gate.reason} />
            </div>
            <div className="r-toolbar">
              <Button onClick={checkContract} disabled={checking} className="gap-2">
                {checking ? <Loader2 className="size-4 animate-spin" /> : <FileCheck className="size-4" />}
                Check data contract
              </Button>
              <span className="research-muted">Runs no solver and launches nothing.</span>
            </div>
            {preflightError ? <p role="alert" className="text-sm text-destructive">{preflightError}</p> : null}
            {issues.length ? (
              <ul className="grid gap-1 text-[13px]" data-testid="preflight-issues" aria-label="Contract issues">
                {issues.map((issue, i) => (
                  <li key={`${issue.code}-${i}`} className="break-words research-muted">
                    <span className="font-mono text-xs">{issue.code}</span> · {issue.path} · {issue.message}
                  </li>
                ))}
              </ul>
            ) : null}
            <details className="research-disclosure">
              <summary>Fields the upload does not provide ({draft.missing.length})</summary>
              <ul className="list-disc pl-5 text-[13px] research-muted">
                {draft.missing.map((field) => <li key={field} className="break-words">{field}</li>)}
              </ul>
            </details>
            {/* No launch control exists: a contractual calibration cannot be started in this version. */}
            <p className="research-muted" data-testid="contract-launch-status">
              Contractual calibration: unavailable until the engine is qualified for new datasets.
            </p>
          </>
        )}
      </section>

      <section id="reference-profile" role="tabpanel" aria-labelledby="reference-profile-tab" data-testid="reference-profile"
        hidden={view !== 'reference'} tabIndex={0} className="grid gap-4">
        {!reference ? (
          <p className="research-muted flex items-center gap-2" role="status"><Loader2 className="size-4 animate-spin" /> Loading registry…</p>
        ) : null}
        {reference && !reference.available ? (
          <div className="grid gap-1" data-testid="reference-unavailable" data-state={reference.state}>
            <StatusLine tone="blocked" label="Reference" value={`Unavailable (${reference.state})`} detail={reference.reason ?? 'No details.'} />
            {reference.nextTask ? <p className="research-muted break-words">Next task: {reference.nextTask}</p> : null}
          </div>
        ) : null}
        {reference?.available ? (
          <WithInspector title="Reference details" inspector={
            <dl className="research-review">
              <div><dt>Selected vector</dt><dd>{reference.selected_id} ({reference.selected_kind})</dd></div>
              <div><dt>Improved over fallback</dt><dd>{String(reference.improved_over_fallback)}</dd></div>
              <div><dt>Objective</dt><dd>{reference.objective_version}</dd></div>
              <div><dt>Units</dt><dd>{reference.scope?.unit_status?.status}</dd></div>
              <div><dt>Receipt</dt><dd className="font-mono text-xs break-all">{String(reference.receipt?.receipt_sha256 ?? '')}</dd></div>
              <div><dt>Numerical qualification</dt><dd>{reference.receipt?.fallback_qualification ?? 'this campaign'}</dd></div>
              <div><dt>Scope</dt><dd>{reference.scope?.applicable_dataset}</dd></div>
            </dl>
          }>
            <div className="grid gap-4">
              <p className="break-words">Provisional extracellular reference for one archived table. Not applied to your data; not a validated RBC calibration.</p>
              {/* A fact, not a control: there is deliberately no activation button for this artifact. */}
              <p className="flex items-center gap-2 text-[13px]" data-testid="reference-activation-status">
                <Lock size={14} aria-hidden="true" /> Preview only · cannot be activated (forbidden by the artifact, even with matching identities)
              </p>
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
                        <TableCell><Num value={row.normalizedRmse} /></TableCell>
                        <TableCell><Num value={row.j15Residual} /></TableCell>
                        <TableCell><Num value={row.slopePredicted} /> / <Num value={row.slopeObserved} /></TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              {strict?.worst_channel ? (
                <StatusLine tone="warn" label="Worst channel" value={`${strict.worst_channel}`}
                  detail={`Normalized RMSE ${strict.worst_normalized_rmse}; working bands are not assay SD.`} />
              ) : null}
              <div className="grid gap-3 lg:grid-cols-2">
                <div className="grid gap-2">
                  <label className="research-muted" htmlFor="reference-species">Extracellular species</label>
                  <select id="reference-species" className="h-9 rounded-md border border-white/10 bg-transparent px-2 text-sm"
                    value={species} onChange={(event) => setSpecies(event.target.value)}>
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
                          <TableCell><Num value={p.observed} /></TableCell>
                          <TableCell><Num value={p.predicted} /></TableCell>
                          <TableCell><Num value={p.residual} /></TableCell>
                          <TableCell>{p.normalizedResidual === null ? 'zero band' : <Num value={p.normalizedResidual} />}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
              {limitations ? (
                <div data-testid="reference-limitations" className="grid gap-3">
                  <h2>Limitations</h2>
                  {Object.entries(limitations).filter(([, notes]) => notes.length).map(([group, notes]) => (
                    <div key={group}>
                      <h3 className="research-muted">{group}</h3>
                      <ul className="list-disc pl-5 text-[13px]">
                        {notes.map((note) => <li key={note} className="break-words">{note}</li>)}
                      </ul>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </WithInspector>
        ) : null}
      </section>
    </div>
  )
}
