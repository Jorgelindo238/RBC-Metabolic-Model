import Link from 'next/link'
import { ArrowRight, Bell, Clock3, Database, Sparkles, TrendingUp } from 'lucide-react'
import { MONITORING_ITEMS } from '../../lib/platform-navigation.ts'
import { SidebarIcon } from './SidebarIcons'
import { cn } from '@/lib/utils'
import type { NavIconName } from './platform-shell.types'

const MONITORING_SURFACES = MONITORING_ITEMS.filter((item) => item.id !== 'monitoring-overview')
const MONITORING_VISIBLE_PAGES = MONITORING_ITEMS.length

const MONITORING_METRICS = [
  {
    label: 'Visible pages',
    value: String(MONITORING_VISIBLE_PAGES),
    hint: 'Overview plus Bag Repository, Quality Forecast, and Alerts',
  },
  {
    label: 'Operational routes',
    value: String(MONITORING_SURFACES.length),
    hint: 'Inventory, forecast, and triage pages',
  },
  {
    label: 'Review path',
    value: 'Bag → forecast → alerts',
    hint: 'The sequence operators follow from inventory to escalation',
  },
  {
    label: 'Gateway slot',
    value: 'Hermes',
    hint: 'Reserved for future Telegram routing',
  },
] as const

const MONITORING_SURFACE_PREVIEW = [
  {
    title: 'Bag Repository',
    value: 'Inventory ready',
    copy: 'Structured bag records, donor details, storage context, and history snapshots.',
    icon: 'data' as NavIconName,
    tone: 'emerald',
  },
  {
    title: 'Quality Forecast',
    value: 'Forecast ready',
    copy: 'Selected bag context, limited biomarkers, and a projected quality curve drive the next storage window.',
    icon: 'flux' as NavIconName,
    tone: 'cyan',
  },
  {
    title: 'Alerts',
    value: 'Action queue',
    copy: 'Forecast-derived review items, persisted workflow state, and operator actions stay visible for rapid triage.',
    icon: 'prompts' as NavIconName,
    tone: 'rose',
  },
  {
    title: 'Hermes',
    value: 'Future gateway',
    copy: 'Messaging stays hidden until the gateway layer is ready, with Telegram as the first connector.',
    icon: 'robocop' as NavIconName,
    tone: 'violet',
  },
] as const

const MONITORING_BAGS = [
  {
    bagId: 'BAG-1042',
    donorId: 'DON-118',
    entryDate: '2026-03-22',
    age: '28',
    sex: 'F',
    profile: 'Low risk',
    status: 'Fresh intake',
  },
  {
    bagId: 'BAG-1178',
    donorId: 'DON-244',
    entryDate: '2026-03-21',
    age: '41',
    sex: 'M',
    profile: 'Watch',
    status: 'Forecast review',
  },
  {
    bagId: 'BAG-1211',
    donorId: 'DON-301',
    entryDate: '2026-03-20',
    age: '36',
    sex: 'F',
    profile: 'Elevated',
    status: 'Alert follow-up',
  },
] as const

const MONITORING_FORECAST_BANDS = [
  { label: '24h', value: '96%', copy: 'Stable quality band' },
  { label: '72h', value: '91%', copy: 'Early drift visible' },
  { label: '7d', value: '83%', copy: 'Watch trend tightening' },
  { label: '14d', value: '71%', copy: 'Review threshold approaching' },
] as const

const MONITORING_ALERTS = [
  {
    severity: 'High',
    bagId: 'BAG-1211',
    title: 'Projected quality drop',
    copy: 'The forecast suggests a sharp decline beyond the review threshold.',
    action: 'Escalate',
  },
  {
    severity: 'Medium',
    bagId: 'BAG-1178',
    title: 'Lactate trend rising',
    copy: 'The trend warrants a follow-up sample and a tighter watch window.',
    action: 'Review',
  },
  {
    severity: 'Low',
    bagId: 'BAG-1042',
    title: 'Freshness refresh due',
    copy: 'Inventory is healthy, but the check-in cadence should be renewed.',
    action: 'Acknowledge',
  },
] as const

const MONITORING_RECENT_ACTIVITY = [
  {
    time: 'Today',
    title: 'Repository refresh',
    copy: 'Latest bag metadata synced into the inventory surface.',
  },
  {
    time: 'Today',
    title: 'Forecast recalculated',
    copy: 'The quality outlook updated for the current storage window.',
  },
  {
    time: 'Today',
    title: 'Alert triage opened',
    copy: 'One high-severity and two watch items are ready for review.',
  },
] as const

function getToneClasses(tone: typeof MONITORING_SURFACE_PREVIEW[number]['tone']) {
  switch (tone) {
    case 'emerald':
      return {
        chip: 'border-emerald-400/20 bg-emerald-400/10 text-emerald-100',
        glow: 'shadow-[0_16px_44px_-26px_rgba(16,185,129,0.35)]',
      }
    case 'cyan':
      return {
        chip: 'border-cyan-400/20 bg-cyan-400/10 text-cyan-100',
        glow: 'shadow-[0_16px_44px_-26px_rgba(34,211,238,0.35)]',
      }
    case 'rose':
      return {
        chip: 'border-rose-400/20 bg-rose-400/10 text-rose-100',
        glow: 'shadow-[0_16px_44px_-26px_rgba(244,63,94,0.35)]',
      }
    case 'violet':
      return {
        chip: 'border-violet-400/20 bg-violet-400/10 text-violet-100',
        glow: 'shadow-[0_16px_44px_-26px_rgba(139,92,246,0.35)]',
      }
    default:
      return {
        chip: 'border-white/10 bg-white/[0.04] text-slate-300',
        glow: 'shadow-[0_16px_44px_-26px_rgba(0,0,0,0.35)]',
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
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 shadow-[0_12px_30px_-22px_rgba(0,0,0,0.78)] backdrop-blur-sm">
      <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">{label}</p>
      <p className="mt-2 text-lg font-semibold tracking-tight text-white">{value}</p>
      <p className="mt-1 text-xs leading-5 text-slate-400">{hint}</p>
    </div>
  )
}

function SurfacePreviewCard({
  title,
  value,
  copy,
  icon,
  tone,
}: {
  title: string
  value: string
  copy: string
  icon: NavIconName
  tone: typeof MONITORING_SURFACE_PREVIEW[number]['tone']
}) {
  const toneClasses = getToneClasses(tone)

  return (
    <article className="rounded-3xl border border-white/10 bg-[linear-gradient(180deg,rgba(26,29,35,0.96),rgba(19,22,28,0.98))] p-5 shadow-[0_18px_48px_-30px_rgba(0,0,0,0.8)]">
      <div className="flex items-start justify-between gap-3">
        <div className="grid gap-2">
          <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">{title}</p>
          <p className="text-2xl font-semibold tracking-tight text-white">{value}</p>
        </div>
        <span className={cn('grid size-11 place-items-center rounded-2xl border', toneClasses.chip, toneClasses.glow)}>
          <SidebarIcon className="size-5" icon={icon} />
        </span>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-400">{copy}</p>
    </article>
  )
}

function BagRow({
  bagId,
  donorId,
  entryDate,
  age,
  sex,
  profile,
  status,
}: typeof MONITORING_BAGS[number]) {
  return (
    <div className="grid gap-3 rounded-2xl border border-white/10 bg-slate-950/55 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="grid gap-1">
          <p className="text-sm font-semibold text-white">{bagId}</p>
          <p className="text-xs text-slate-400">
            {donorId} · {entryDate}
          </p>
        </div>
        <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-300">
          {status}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-3 text-xs text-slate-400">
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
          <p className="uppercase tracking-[0.22em] text-slate-500">Age / Sex</p>
          <p className="mt-1 text-sm font-semibold text-white">
            {age} · {sex}
          </p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
          <p className="uppercase tracking-[0.22em] text-slate-500">Profile</p>
          <p className="mt-1 text-sm font-semibold text-white">{profile}</p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
          <p className="uppercase tracking-[0.22em] text-slate-500">State</p>
          <p className="mt-1 text-sm font-semibold text-white">{status}</p>
        </div>
      </div>
    </div>
  )
}

function ForecastBand({
  label,
  value,
  copy,
  index,
}: typeof MONITORING_FORECAST_BANDS[number] & { index: number }) {
  const barWidth = ['96%', '90%', '80%', '70%'][index] ?? '72%'

  return (
    <div className="grid gap-2 rounded-2xl border border-white/10 bg-slate-950/55 p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">{label}</p>
        <p className="text-lg font-semibold tracking-tight text-white">{value}</p>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-white/5">
        <div
          className="h-full rounded-full bg-[linear-gradient(90deg,rgba(34,211,238,0.95),rgba(56,189,248,0.45))]"
          style={{ width: barWidth }}
        />
      </div>
      <p className="text-sm leading-6 text-slate-400">{copy}</p>
    </div>
  )
}

function AlertRow({
  severity,
  bagId,
  title,
  copy,
  action,
}: typeof MONITORING_ALERTS[number]) {
  const tone =
    severity === 'High'
      ? 'border-rose-400/20 bg-rose-400/10 text-rose-100'
      : severity === 'Medium'
        ? 'border-amber-400/20 bg-amber-400/10 text-amber-100'
        : 'border-cyan-400/20 bg-cyan-400/10 text-cyan-100'

  return (
    <div className="grid gap-3 rounded-2xl border border-white/10 bg-slate-950/55 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="grid gap-1">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">{bagId}</p>
          <p className="text-sm font-semibold text-white">{title}</p>
        </div>
        <span
          className={cn(
            'inline-flex items-center rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em]',
            tone
          )}
        >
          {severity}
        </span>
      </div>
      <p className="text-sm leading-6 text-slate-400">{copy}</p>
      <div className="flex items-center justify-between gap-3 border-t border-white/10 pt-3 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">
        <span>Next step</span>
        <span className="text-cyan-100">{action}</span>
      </div>
    </div>
  )
}

export function MonitoringWorkspaceLanding() {
  return (
    <>
      <section className="hero panel relative overflow-hidden !border-white/10 !bg-[linear-gradient(180deg,rgba(15,23,42,0.97),rgba(15,23,42,0.84))] !shadow-[0_24px_80px_-48px_rgba(8,15,40,0.95)]">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(56,189,248,0.12),transparent_34%),radial-gradient(circle_at_bottom_left,rgba(214,40,57,0.08),transparent_32%)]"
        />
        <div className="relative grid gap-8 xl:grid-cols-[minmax(0,1.18fr)_minmax(360px,0.82fr)]">
          <div className="grid gap-5">
            <div className="flex flex-wrap items-center gap-3">
              <p className="eyebrow">Monitoring mode</p>
              <span className="inline-flex items-center rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-cyan-100">
                Command-center preview
              </span>
            </div>

            <div className="grid gap-3">
              <h1 className="page-title">Monitoring overview</h1>
              <p className="page-copy max-w-3xl">
                A command center for Bag Repository, Quality Forecast, and Alerts across the storage lifecycle, with
                Hermes reserved as the future messaging gateway.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {MONITORING_METRICS.map((metric) => (
                <MetricTile key={metric.label} {...metric} />
              ))}
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              {MONITORING_SURFACE_PREVIEW.map((card) => (
                <SurfacePreviewCard key={card.title} {...card} />
              ))}
            </div>
          </div>

          <aside className="rounded-[2rem] border border-white/10 bg-white/[0.04] p-5 shadow-[0_20px_60px_-34px_rgba(0,0,0,0.78)] backdrop-blur-sm">
            <div className="flex items-center justify-between gap-3">
              <div className="grid gap-1">
                <p className="eyebrow">Command briefing</p>
                <h2 className="text-2xl font-semibold tracking-tight text-white">What this page tracks</h2>
              </div>
              <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">
                Preview
              </span>
            </div>

            <div className="mt-5 grid gap-3">
              <div className="rounded-3xl border border-white/10 bg-slate-950/55 p-4">
                <div className="flex items-center gap-3">
                  <span className="grid size-10 place-items-center rounded-2xl border border-cyan-400/20 bg-cyan-400/10 text-cyan-100">
                    <Database className="size-4" />
                  </span>
                  <div className="grid gap-1">
                    <p className="text-sm font-semibold text-white">Biobank inventory</p>
                    <p className="text-sm leading-6 text-slate-400">
                      Keep bag metadata, storage state, and history snapshots in one place.
                    </p>
                  </div>
                </div>
              </div>

              <div className="rounded-3xl border border-white/10 bg-slate-950/55 p-4">
                <div className="flex items-center gap-3">
                  <span className="grid size-10 place-items-center rounded-2xl border border-emerald-400/20 bg-emerald-400/10 text-emerald-100">
                    <TrendingUp className="size-4" />
                  </span>
                  <div className="grid gap-1">
                    <p className="text-sm font-semibold text-white">Forecast window</p>
                    <p className="text-sm leading-6 text-slate-400">
                      Project degradation and quality drift from a limited monitoring panel.
                    </p>
                  </div>
                </div>
              </div>

              <div className="rounded-3xl border border-white/10 bg-slate-950/55 p-4">
                <div className="flex items-center gap-3">
                  <span className="grid size-10 place-items-center rounded-2xl border border-rose-400/20 bg-rose-400/10 text-rose-100">
                    <Bell className="size-4" />
                  </span>
                  <div className="grid gap-1">
                    <p className="text-sm font-semibold text-white">Alert queue</p>
                    <p className="text-sm leading-6 text-slate-400">
                      Track forecast-derived review items, workflow state, and operator actions for rapid triage.
                    </p>
                  </div>
                </div>
              </div>

              <div className="rounded-3xl border border-violet-400/20 bg-violet-400/10 p-4">
                <div className="flex items-center gap-3">
                  <span className="grid size-10 place-items-center rounded-2xl border border-violet-400/20 bg-violet-400/10 text-violet-100">
                    <Sparkles className="size-4" />
                  </span>
                  <div className="grid gap-1">
                    <p className="text-sm font-semibold text-white">Hermes gateway</p>
                    <p className="text-sm leading-6 text-violet-50/75">
                      Messaging stays hidden until Telegram routing is ready for operators.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-5 grid gap-2">
              <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Active routes</p>
              <div className="flex flex-wrap gap-2">
                {MONITORING_SURFACES.map((surface) => (
                  <Link
                    className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-semibold text-slate-300 transition-colors hover:border-cyan-400/30 hover:bg-cyan-400/10 hover:text-cyan-100"
                    href={surface.href}
                    key={surface.id}
                  >
                    <span className="mr-1.5 inline-flex size-4 items-center justify-center rounded-full border border-white/10 bg-white/[0.04] text-[10px] text-slate-500">
                      {surface.title.slice(0, 1)}
                    </span>
                    {surface.title}
                    <ArrowRight className="ml-1 size-3.5" />
                  </Link>
                ))}
              </div>
            </div>
          </aside>
        </div>
      </section>

      <section className="panel overflow-hidden">
        <div className="mb-5 flex flex-col gap-3 border-b border-white/10 pb-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="grid gap-2">
              <p className="eyebrow">Operational snapshot</p>
              <h2 className="text-2xl font-semibold tracking-tight text-white">What the command center is watching</h2>
            </div>
            <p className="max-w-2xl text-sm leading-6 text-slate-400">
              Seeded preview data shows the intended Monitoring rhythm until live bag feeds and Hermes routing are
              connected.
            </p>
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
          <div className="grid gap-4">
            {MONITORING_BAGS.map((bag) => (
              <BagRow key={bag.bagId} {...bag} />
            ))}
          </div>

          <div className="grid gap-4">
            <div className="rounded-3xl border border-white/10 bg-[linear-gradient(180deg,rgba(26,29,35,0.96),rgba(19,22,28,0.98))] p-5 shadow-[0_18px_48px_-30px_rgba(0,0,0,0.8)]">
              <div className="flex items-center justify-between gap-3">
                <div className="grid gap-1">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Forecast pulse</p>
                  <h3 className="text-xl font-semibold tracking-tight text-white">Quality trajectory</h3>
                </div>
                <span className="inline-flex items-center rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-cyan-100">
                  14-day view
                </span>
              </div>
              <div className="mt-4 grid gap-3">
                {MONITORING_FORECAST_BANDS.map((band, index) => (
                  <ForecastBand key={band.label} index={index} {...band} />
                ))}
              </div>
            </div>

            <div className="rounded-3xl border border-white/10 bg-[linear-gradient(180deg,rgba(26,29,35,0.96),rgba(19,22,28,0.98))] p-5 shadow-[0_18px_48px_-30px_rgba(0,0,0,0.8)]">
              <div className="flex items-center justify-between gap-3">
                <div className="grid gap-1">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Alert queue</p>
                  <h3 className="text-xl font-semibold tracking-tight text-white">Open items</h3>
                </div>
                <span className="inline-flex items-center rounded-full border border-rose-400/20 bg-rose-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-rose-100">
                  3 items
                </span>
              </div>
              <div className="mt-4 grid gap-3">
                {MONITORING_ALERTS.map((alert) => (
                  <AlertRow key={alert.bagId} {...alert} />
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="panel overflow-hidden">
        <div className="mb-5 flex flex-col gap-3 border-b border-white/10 pb-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="grid gap-2">
              <p className="eyebrow">Recent activity</p>
              <h2 className="text-2xl font-semibold tracking-tight text-white">The latest operational trail</h2>
            </div>
            <p className="max-w-2xl text-sm leading-6 text-slate-400">
              Bags, forecasts, and alerts move through the same command center so the team can respond quickly.
            </p>
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
          <div className="grid gap-4">
            {MONITORING_RECENT_ACTIVITY.map((item) => (
              <article
                className="grid gap-3 rounded-3xl border border-white/10 bg-[linear-gradient(180deg,rgba(26,29,35,0.96),rgba(19,22,28,0.98))] p-5 shadow-[0_18px_48px_-30px_rgba(0,0,0,0.8)]"
                key={item.title}
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">{item.time}</p>
                  <Clock3 className="size-4 text-cyan-300" />
                </div>
                <h3 className="text-lg font-semibold tracking-tight text-white">{item.title}</h3>
                <p className="text-sm leading-6 text-slate-400">{item.copy}</p>
              </article>
            ))}
          </div>

          <div className="grid gap-4">
            <article className="rounded-3xl border border-white/10 bg-[linear-gradient(180deg,rgba(26,29,35,0.96),rgba(19,22,28,0.98))] p-5 shadow-[0_18px_48px_-30px_rgba(0,0,0,0.8)]">
              <div className="flex items-center justify-between gap-3">
                <div className="grid gap-1">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Surface tone</p>
                  <h3 className="text-xl font-semibold tracking-tight text-white">Glass console</h3>
                </div>
                <Sparkles className="size-4 text-cyan-300" />
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-400">
                Dark glass cards, compact chips, and clear hierarchy keep bag, forecast, and alert state easy to scan.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-semibold text-slate-300">
                  Bag Repository
                </span>
                <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-semibold text-slate-300">
                  Quality Forecast
                </span>
                <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-semibold text-slate-300">
                  Alerts
                </span>
              </div>
            </article>

            <article className="rounded-3xl border border-violet-400/20 bg-violet-400/10 p-5 shadow-[0_18px_48px_-30px_rgba(0,0,0,0.8)]">
              <div className="flex items-center justify-between gap-3">
                <div className="grid gap-1">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-violet-100/70">Future gateway</p>
                  <h3 className="text-xl font-semibold tracking-tight text-white">Hermes</h3>
                </div>
                <ArrowRight className="size-4 text-violet-100" />
              </div>
              <p className="mt-3 text-sm leading-6 text-violet-50/75">
                Hermes stays hidden from the active sidebar until the messaging gateway is connected, starting with
                Telegram routing for operator alerts.
              </p>
              <div className="mt-4 flex items-center justify-between gap-3 rounded-2xl border border-violet-400/20 bg-violet-400/10 px-4 py-3">
                <span className="text-xs font-semibold uppercase tracking-[0.22em] text-violet-100/80">Reserved</span>
                <span className="text-xs font-semibold text-white">Not yet active</span>
              </div>
            </article>
          </div>
        </div>
      </section>
    </>
  )
}
