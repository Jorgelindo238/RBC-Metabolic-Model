'use client'

import { useEffect, useMemo, useState, type FormEvent } from 'react'
import Link from 'next/link'
import {
  Activity,
  ArrowRight,
  CirclePlus,
  Database,
  Filter,
  Search,
  ShieldAlert,
  Sparkles,
  Users,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { cn } from '@/lib/utils'
import {
  MONITORING_BAG_STATUSES as BAG_STATUSES,
  getMonitoringBagRiskTone as getRiskTone,
  getMonitoringBagStatusTone as getStatusTone,
  type MonitoringBagCreateInput,
  type MonitoringBagRecord,
  type MonitoringBagStatus as BagInventoryStatus,
  type MonitoringRiskBand,
} from '@/lib/monitoring-inventory'
import { createMonitoringBagRecord, useMonitoringBagInventory } from '@/lib/monitoring-inventory-store'

const BAG_TABS: readonly { key: 'all' | BagInventoryStatus; label: string }[] = [
  { key: 'all', label: 'All bags' },
  ...BAG_STATUSES.map((status) => ({ key: status, label: status })),
]

const BAG_SEXES = ['F', 'M'] as const

type BagDraft = {
  bagId: string
  donorId: string
  entryDate: string
  age: string
  sex: MonitoringBagRecord['sex']
  medicalProfile: MonitoringRiskBand
  repositoryStatus: BagInventoryStatus
  storageContext: string
}

function createEmptyBagDraft(): BagDraft {
  return {
    bagId: '',
    donorId: '',
    entryDate: new Date().toISOString().slice(0, 10),
    age: '',
    sex: 'F',
    medicalProfile: 'Watch',
    repositoryStatus: 'Fresh intake',
    storageContext: '',
  }
}

function MetricTile({ label, value, hint, icon: Icon }: { label: string; value: string; hint: string; icon: LucideIcon }) {
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

function Head({ text }: { text: string }) {
  return (
    <TableHead className="px-4 py-3 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">
      {text}
    </TableHead>
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

function buildCreateInput(draft: BagDraft): MonitoringBagCreateInput {
  return {
    bagId: draft.bagId.trim().toUpperCase(),
    donorId: draft.donorId.trim().toUpperCase(),
    entryDate: draft.entryDate.trim(),
    age: Number(draft.age),
    sex: draft.sex,
    medicalProfile: draft.medicalProfile,
    repositoryStatus: draft.repositoryStatus,
    storageContext: draft.storageContext.trim(),
  }
}

function validateDraft(draft: BagDraft) {
  if (!draft.bagId.trim() || !draft.donorId.trim() || !draft.entryDate.trim() || !draft.storageContext.trim()) {
    return 'Fill in the bag identity, donor, date, and storage context before adding the record.'
  }

  if (!Number.isFinite(Number(draft.age)) || Number(draft.age) <= 0) {
    return 'Age must be a positive number.'
  }

  return null
}

export function BagRepository() {
  const { bags, createBag } = useMonitoringBagInventory()
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | BagInventoryStatus>('all')
  const [selectedBagId, setSelectedBagId] = useState<string>(bags[0]?.bagId ?? '')
  const [isAddingBag, setIsAddingBag] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [draft, setDraft] = useState<BagDraft>(createEmptyBagDraft)
  const [formError, setFormError] = useState<string | null>(null)
  const [formSuccess, setFormSuccess] = useState<string | null>(null)

  const visibleBags = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    return bags.filter((bag) => {
      const matchesStatus = statusFilter === 'all' ? true : bag.repositoryStatus === statusFilter
      const searchableText = [
        bag.bagId,
        bag.donorId,
        bag.entryDate,
        String(bag.age),
        bag.sex,
        bag.medicalProfile,
        bag.repositoryStatus,
        bag.storageContext,
        bag.qualityState,
        bag.forecastState,
      ]
        .join(' ')
        .toLowerCase()

      return matchesStatus && (!normalizedQuery || searchableText.includes(normalizedQuery))
    })
  }, [bags, query, statusFilter])

  useEffect(() => {
    if (!visibleBags.length) {
      setSelectedBagId('')
      return
    }

    if (!visibleBags.some((bag) => bag.bagId === selectedBagId)) {
      setSelectedBagId(visibleBags[0].bagId)
    }
  }, [selectedBagId, visibleBags])

  const selectedBag = visibleBags.find((bag) => bag.bagId === selectedBagId) ?? visibleBags[0] ?? null
  const donorCount = new Set(bags.map((bag) => bag.donorId)).size
  const watchCount = bags.filter((bag) => bag.medicalProfile !== 'Low risk').length
  const alertCount = bags.reduce((sum, bag) => sum + bag.alerts, 0)
  const forecastWatchCount = bags.filter((bag) => !bag.forecastState.toLowerCase().includes('stable')).length

  function updateDraftField<K extends keyof BagDraft>(field: K, value: BagDraft[K]) {
    setDraft((current) => ({ ...current, [field]: value }))
  }

  function resetAddBagForm() {
    setDraft(createEmptyBagDraft())
    setFormError(null)
    setFormSuccess(null)
  }

  async function handleAddBagSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const draftError = validateDraft(draft)
    if (draftError) {
      setFormError(draftError)
      setFormSuccess(null)
      return
    }

    setIsSaving(true)
    setFormError(null)
    setFormSuccess(null)

    try {
      const createdBag = await createBag(buildCreateInput(draft))
      setSelectedBagId(createdBag.bagId)
      setQuery('')
      setStatusFilter('all')
      setIsAddingBag(false)
      setDraft(createEmptyBagDraft())
      setFormSuccess(`Added ${createdBag.bagId} to the repository.`)
    } catch (error) {
      setFormSuccess(null)
      setFormError(error instanceof Error ? error.message : 'Could not add the bag.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="grid gap-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <MetricTile icon={Database} label="Bags visible" value={String(bags.length)} hint="Structured inventory records ready for selection and review." />
        <MetricTile icon={Users} label="Donors tracked" value={String(donorCount)} hint="One donor trail per monitored bag in the repository." />
        <MetricTile icon={ShieldAlert} label="Watch list" value={String(watchCount)} hint="Bags that need closer quality review or forecast attention." />
        <MetricTile icon={Sparkles} label="Forecast watch" value={String(forecastWatchCount)} hint="Rows with projected drift or threshold pressure ahead." />
        <MetricTile icon={Activity} label="Open alerts" value={String(alertCount)} hint="Alerts already linked to inventory rows in this preview." />
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(340px,0.75fr)]">
        <Card className="border-white/10 bg-[linear-gradient(180deg,rgba(26,29,35,0.96),rgba(19,22,28,0.98))] shadow-[0_18px_48px_-30px_rgba(0,0,0,0.8)]">
          <CardHeader className="space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="grid gap-2">
                <CardTitle className="text-2xl tracking-tight text-white">Inventory table</CardTitle>
                <CardDescription className="max-w-2xl text-slate-400">
                  Inspect bag identity, donor metadata, and monitoring state in one place. Select a row to open the detail rail on the right.
                </CardDescription>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  className="h-9 rounded-full px-4 text-xs font-semibold"
                  onClick={() => {
                    setIsAddingBag((current) => !current)
                    setFormError(null)
                    setFormSuccess(null)
                  }}
                  type="button"
                  variant={isAddingBag ? 'secondary' : 'default'}
                >
                  <CirclePlus className="size-4" />
                  {isAddingBag ? 'Close bag form' : 'Add new bag'}
                </Button>
                <div className="inline-flex items-center rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-cyan-100">
                  <Filter className="mr-1.5 size-3.5" />
                  Repository filter
                </div>
              </div>
            </div>

            <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
              <div className="relative">
                <Search className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-slate-500" />
                <Input
                  className="h-11 rounded-2xl border-white/10 bg-white/[0.04] pl-11 text-slate-100 placeholder:text-slate-500 focus-visible:ring-cyan-400/40"
                  placeholder="Search bag ID, donor ID, date, or medical profile"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </div>

              <div className="flex flex-wrap gap-2">
                {BAG_TABS.map((tab) => {
                  const isActive = statusFilter === tab.key
                  return (
                    <button
                      key={tab.label}
                      type="button"
                      onClick={() => setStatusFilter(tab.key)}
                      className={cn(
                        'inline-flex items-center rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors',
                        isActive
                          ? 'border-cyan-400/30 bg-cyan-400/10 text-cyan-100'
                          : 'border-white/10 bg-white/[0.04] text-slate-400 hover:border-white/20 hover:bg-white/[0.06] hover:text-slate-200'
                      )}
                    >
                      {tab.label}
                    </button>
                  )
                })}
              </div>
            </div>
          </CardHeader>

          <CardContent className="space-y-4">
            {isAddingBag ? (
              <form className="grid gap-4 rounded-3xl border border-cyan-400/20 bg-cyan-400/8 p-5" onSubmit={handleAddBagSubmit}>
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="grid gap-2">
                    <p className="eyebrow">New bag intake</p>
                    <h3 className="text-xl font-semibold tracking-tight text-white">Add a repository record</h3>
                    <p className="max-w-3xl text-sm leading-6 text-slate-400">
                      Enter the core bag identity and storage context. Monitoring will initialize the operational fields server-side so the record can flow into Quality Forecast and Alerts later.
                    </p>
                  </div>
                  <span className="inline-flex items-center rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-cyan-100">
                    Intake fields only
                  </span>
                </div>

                {formError || formSuccess ? (
                  <div
                    className={cn(
                      'rounded-2xl border p-4 text-sm leading-6',
                      formError
                        ? 'border-rose-400/20 bg-rose-400/10 text-rose-100'
                        : 'border-emerald-400/20 bg-emerald-400/10 text-emerald-100'
                    )}
                  >
                    {formError ?? formSuccess}
                  </div>
                ) : null}

                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                  <Field label="Bag ID" id="bag-id" value={draft.bagId} onChange={(value) => updateDraftField('bagId', value)} placeholder="BAG-1301" />
                  <Field label="Donor ID" id="donor-id" value={draft.donorId} onChange={(value) => updateDraftField('donorId', value)} placeholder="DON-500" />
                  <Field label="Entry date" id="entry-date" value={draft.entryDate} onChange={(value) => updateDraftField('entryDate', value)} type="date" />
                  <Field label="Age" id="age" value={draft.age} onChange={(value) => updateDraftField('age', value)} type="number" min="1" placeholder="32" />
                  <SelectField label="Sex" value={draft.sex} onChange={(value) => updateDraftField('sex', value as BagDraft['sex'])} options={BAG_SEXES} />
                  <SelectField label="Medical profile" value={draft.medicalProfile} onChange={(value) => updateDraftField('medicalProfile', value as MonitoringRiskBand)} options={['Low risk', 'Watch', 'Elevated']} />
                  <SelectField label="Repository status" value={draft.repositoryStatus} onChange={(value) => updateDraftField('repositoryStatus', value as BagInventoryStatus)} options={BAG_STATUSES} />
                  <Field className="md:col-span-2 xl:col-span-3" label="Storage context" id="storage-context" value={draft.storageContext} onChange={(value) => updateDraftField('storageContext', value)} placeholder="Cold room B2 · rack 3" />
                </div>

                <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 text-sm leading-6 text-slate-300">
                  Monitoring initializes the operational fields on save: <span className="font-semibold text-white">quality state, forecast state, alerts, linked runs, and monitoring events.</span>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <Button className="rounded-full" disabled={isSaving} type="submit">
                    {isSaving ? 'Adding bag...' : 'Add bag to repository'}
                  </Button>
                  <Button className="rounded-full" onClick={resetAddBagForm} type="button" variant="secondary">
                    Reset form
                  </Button>
                </div>
              </form>
            ) : null}

            {!isAddingBag && formSuccess ? (
              <div className="rounded-2xl border border-emerald-400/20 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-100">
                {formSuccess}
              </div>
            ) : null}

            {visibleBags.length ? (
              <div className="rounded-3xl border border-white/10 bg-slate-950/55">
                <Table>
                  <TableHeader>
                    <TableRow className="border-white/10 hover:bg-transparent">
                      <Head text="Bag" />
                      <Head text="Donor" />
                      <Head text="Entry date" />
                      <Head text="Age / Sex" />
                      <Head text="Medical profile" />
                      <Head text="Repository status" />
                      <Head text="Forecast" />
                      <Head text="Alerts" />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {visibleBags.map((bag) => {
                      const selected = bag.bagId === selectedBagId
                      return (
                        <TableRow
                          key={bag.bagId}
                          aria-selected={selected}
                          role="button"
                          tabIndex={0}
                          className={cn('cursor-pointer border-white/10 transition-colors hover:bg-white/[0.04]', selected && 'bg-cyan-400/[0.08] hover:bg-cyan-400/[0.1]')}
                          onClick={() => setSelectedBagId(bag.bagId)}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter' || event.key === ' ') {
                              event.preventDefault()
                              setSelectedBagId(bag.bagId)
                            }
                          }}
                        >
                          <TableCell className="px-4 py-4">
                            <div className="grid gap-1">
                              <p className="text-sm font-semibold text-white">{bag.bagId}</p>
                              <p className="text-xs text-slate-500">{bag.repositoryStatus}</p>
                            </div>
                          </TableCell>
                          <TableCell className="px-4 py-4 text-sm text-slate-300">{bag.donorId}</TableCell>
                          <TableCell className="px-4 py-4 text-sm text-slate-300">{bag.entryDate}</TableCell>
                          <TableCell className="px-4 py-4 text-sm text-slate-300">{bag.age} · {bag.sex}</TableCell>
                          <TableCell className="px-4 py-4"><Badge className={cn('rounded-full border px-3 py-1 text-[10px] uppercase tracking-[0.22em]', getRiskTone(bag.medicalProfile))} variant="outline">{bag.medicalProfile}</Badge></TableCell>
                          <TableCell className="px-4 py-4"><Badge className={cn('rounded-full border px-3 py-1 text-[10px] uppercase tracking-[0.22em]', getStatusTone(bag.repositoryStatus))} variant="outline">{bag.repositoryStatus}</Badge></TableCell>
                          <TableCell className="px-4 py-4 text-sm text-slate-300">{bag.forecastState}</TableCell>
                          <TableCell className="px-4 py-4 text-sm font-semibold text-white">{bag.alerts}</TableCell>
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <div className="rounded-3xl border border-dashed border-white/10 bg-slate-950/40 p-8 text-center">
                <p className="text-sm font-semibold text-white">No bags match these filters</p>
                <p className="mt-2 text-sm leading-6 text-slate-400">Broaden the search or clear the status filter to return to the full repository view.</p>
                <Button className="mt-4 rounded-full" onClick={() => { setQuery(''); setStatusFilter('all') }} variant="secondary">Reset filters</Button>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="border-white/10 bg-[linear-gradient(180deg,rgba(26,29,35,0.96),rgba(19,22,28,0.98))] shadow-[0_18px_48px_-30px_rgba(0,0,0,0.8)]">
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <div className="grid gap-1">
                <CardTitle className="text-2xl tracking-tight text-white">Selected bag</CardTitle>
                <CardDescription className="text-slate-400">Inventory identity, storage context, and future monitoring slots.</CardDescription>
              </div>
              <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">Detail rail</span>
            </div>
          </CardHeader>

          <CardContent className="grid gap-4">
            {selectedBag ? (
              <>
                <div className="grid gap-3 rounded-3xl border border-white/10 bg-slate-950/55 p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="grid gap-1">
                      <p className="eyebrow">Focused record</p>
                      <h3 className="text-2xl font-semibold tracking-tight text-white">{selectedBag.bagId}</h3>
                      <p className="text-sm text-slate-400">{selectedBag.donorId} · {selectedBag.entryDate}</p>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      <Badge className={cn('rounded-full border px-3 py-1 text-[10px] uppercase tracking-[0.22em]', getStatusTone(selectedBag.repositoryStatus))} variant="outline">{selectedBag.repositoryStatus}</Badge>
                      <Badge className={cn('rounded-full border px-3 py-1 text-[10px] uppercase tracking-[0.22em]', getRiskTone(selectedBag.medicalProfile))} variant="outline">{selectedBag.medicalProfile}</Badge>
                    </div>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <DetailField label="Age / sex" value={`${selectedBag.age} · ${selectedBag.sex}`} />
                    <DetailField label="Medical profile" value={selectedBag.medicalProfile} />
                  </div>

                  <div className="grid gap-3">
                    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Storage context</p>
                      <p className="mt-2 text-sm leading-6 text-slate-200">{selectedBag.storageContext}</p>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                        <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Quality state</p>
                        <p className="mt-2 text-sm font-semibold text-white">{selectedBag.qualityState}</p>
                      </div>
                      <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                        <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Forecast state</p>
                        <p className="mt-2 text-sm font-semibold text-white">{selectedBag.forecastState}</p>
                      </div>
                    </div>
                  </div>

                  <div className="grid gap-3 rounded-2xl border border-white/10 bg-white/[0.03] p-4 sm:grid-cols-3">
                    <div className="grid gap-1"><p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Alerts</p><p className="text-sm font-semibold text-white">{selectedBag.alerts}</p></div>
                    <div className="grid gap-1"><p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Linked runs</p><p className="text-sm font-semibold text-white">{selectedBag.linkedRuns}</p></div>
                    <div className="grid gap-1"><p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Monitoring events</p><p className="text-sm font-semibold text-white">{selectedBag.monitoringEvents}</p></div>
                  </div>
                </div>

                <div className="grid gap-3 rounded-3xl border border-white/10 bg-slate-950/55 p-5">
                  <div className="flex items-center justify-between gap-3">
                    <div className="grid gap-1">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Future-ready fields</p>
                      <h4 className="text-lg font-semibold tracking-tight text-white">Ready for Quality Forecast and Alerts</h4>
                    </div>
                    <Sparkles className="size-4 text-cyan-300" />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {['Repository status', 'Storage context', 'Quality state', 'Linked forecast', 'Linked alerts', 'Run history', 'Monitoring events'].map((field) => (
                      <span key={field} className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-semibold text-slate-300">
                        {field}
                      </span>
                    ))}
                  </div>
                  <p className="text-sm leading-6 text-slate-400">
                    The intake record is ready to feed the forecast and alert pages once live monitoring inputs are connected.
                  </p>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <Button asChild className="h-11 rounded-full">
                    <Link href="/monitoring/quality-forecast">Open Quality Forecast<ArrowRight className="size-4" /></Link>
                  </Button>
                  <Button asChild className="h-11 rounded-full" variant="secondary">
                    <Link href="/monitoring/alerts">Review Alerts<ShieldAlert className="size-4" /></Link>
                  </Button>
                </div>
              </>
            ) : (
              <div className="rounded-3xl border border-dashed border-white/10 bg-slate-950/40 p-8 text-center">
                <p className="text-sm font-semibold text-white">No bag selected</p>
                <p className="mt-2 text-sm leading-6 text-slate-400">Clear the filters or select a row to open the bag detail rail.</p>
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <Card className="border-white/10 bg-[linear-gradient(180deg,rgba(26,29,35,0.96),rgba(19,22,28,0.98))] shadow-[0_18px_48px_-30px_rgba(0,0,0,0.8)]">
          <CardHeader>
            <CardTitle className="text-white">Quality Forecast handoff</CardTitle>
            <CardDescription className="text-slate-400">Move from the repository record into a constrained monitoring projection.</CardDescription>
          </CardHeader>
          <CardContent className="text-sm leading-6 text-slate-400">Bag-level status and storage context will feed the next quality outlook so operators can see the degradation curve before it becomes an alert.</CardContent>
        </Card>
        <Card className="border-white/10 bg-[linear-gradient(180deg,rgba(26,29,35,0.96),rgba(19,22,28,0.98))] shadow-[0_18px_48px_-30px_rgba(0,0,0,0.8)]">
          <CardHeader>
            <CardTitle className="text-white">Alerts linkage</CardTitle>
            <CardDescription className="text-slate-400">Convert forecast pressure into an operational queue.</CardDescription>
          </CardHeader>
          <CardContent className="text-sm leading-6 text-slate-400">Threshold crossings, watch states, and elevated profiles can surface directly from the repository into Alerts when Monitoring becomes live.</CardContent>
        </Card>
        <Card className="border-white/10 bg-[linear-gradient(180deg,rgba(26,29,35,0.96),rgba(19,22,28,0.98))] shadow-[0_18px_48px_-30px_rgba(0,0,0,0.8)]">
          <CardHeader>
            <CardTitle className="text-white">Repository history</CardTitle>
            <CardDescription className="text-slate-400">Leave room for future bag-level runs, events, and provenance.</CardDescription>
          </CardHeader>
          <CardContent className="text-sm leading-6 text-slate-400">This page keeps the inventory structure ready for linked runs, follow-up checks, and future monitoring events without turning into a dead-end CRUD screen.</CardContent>
        </Card>
      </section>
    </div>
  )
}

function Field(props: {
  label: string
  id: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  type?: 'text' | 'number' | 'date'
  min?: string
  className?: string
}) {
  return (
    <div className={cn('grid gap-2', props.className)}>
      <Label className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500" htmlFor={props.id}>
        {props.label}
      </Label>
      <Input
        className="h-11 rounded-2xl border-white/10 bg-white/[0.04] text-slate-100 placeholder:text-slate-500 focus-visible:ring-cyan-400/40"
        id={props.id}
        min={props.min}
        placeholder={props.placeholder}
        type={props.type ?? 'text'}
        value={props.value}
        onChange={(event) => props.onChange(event.target.value)}
      />
    </div>
  )
}

function SelectField(props: {
  label: string
  value: string
  onChange: (value: string) => void
  options: readonly string[]
}) {
  return (
    <div className="grid gap-2">
      <Label className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">{props.label}</Label>
      <Select value={props.value} onValueChange={props.onChange}>
        <SelectTrigger className="h-11 w-full rounded-2xl border-white/10 bg-white/[0.04] text-slate-100 focus:ring-cyan-400/40">
          <SelectValue placeholder={`Select ${props.label.toLowerCase()}`} />
        </SelectTrigger>
        <SelectContent>
          {props.options.map((option) => (
            <SelectItem key={option} value={option}>
              {option}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
