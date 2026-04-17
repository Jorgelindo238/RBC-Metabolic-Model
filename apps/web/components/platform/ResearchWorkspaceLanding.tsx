import { ArrowRight, Sparkles } from 'lucide-react'
import { ModuleCards } from './ModuleCards'
import { PLATFORM_MODULE_CARDS } from '../../lib/platform-navigation.ts'

const RESEARCH_METRICS = [
  {
    label: 'Live research pages',
    value: String(PLATFORM_MODULE_CARDS.filter((card) => card.status === 'live').length),
    hint: 'Open directly from the sidebar',
  },
  {
    label: 'Workspace modules',
    value: String(PLATFORM_MODULE_CARDS.length),
    hint: 'Overview plus focused tools',
  },
  {
    label: 'Default horizon',
    value: '42d',
    hint: 'Standard storage run length',
  },
  {
    label: 'Assistant layer',
    value: 'RoBoCop',
    hint: 'Keeps answers tied to the page',
  },
] as const

const RESEARCH_FLOW = [
  {
    title: 'Prepare the active dataset',
    copy: 'Use Data Upload to stage a custom dataset before it becomes the active research context.',
  },
  {
    title: 'Confirm in Calibration Registry',
    copy: 'Review the ledger, confirm the active dataset, and hand it off to the next run.',
  },
  {
    title: 'Run Simulation',
    copy: 'Open Simulation once the calibration handoff is locked in to inspect trajectories and solver behavior.',
  },
] as const

const STARTER_PATH = [
  {
    title: 'Open a focused page',
    copy: 'Jump straight into a page from the sidebar when you already know the task.',
  },
  {
    title: 'Read the section rhythm',
    copy: 'Start with the hero, then scan the section cards to understand the page at a glance.',
  },
  {
    title: 'Ask RoBoCop in context',
    copy: 'Bring the assistant in once the scientific focus is already on screen.',
  },
] as const

const SNAPSHOT_CARDS = [
  {
    label: 'Working style',
    value: 'Route native',
    copy: 'Each analysis page opens with its own brief instead of a shared dashboard layout.',
  },
  {
    label: 'Visual rhythm',
    value: 'Dark glass',
    copy: 'Thin borders, soft glow, and compact cards keep the overview easy to scan.',
  },
  {
    label: 'Scientific scope',
    value: 'Mechanistic',
    copy: 'The platform stays anchored to RBC storage simulation, validation, and calibration.',
  },
  {
    label: 'Assistant support',
    value: 'Context aware',
    copy: 'RoBoCop follows the active analysis rather than a generic chat state.',
  },
] as const

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

function SnapshotCard({
  label,
  value,
  copy,
}: {
  label: string
  value: string
  copy: string
}) {
  return (
    <article className="rounded-3xl border border-white/10 bg-[linear-gradient(180deg,rgba(26,29,35,0.96),rgba(19,22,28,0.98))] p-5 shadow-[0_18px_48px_-30px_rgba(0,0,0,0.8)]">
      <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-white">{value}</p>
      <p className="mt-3 text-sm leading-6 text-slate-400">{copy}</p>
    </article>
  )
}

export function ResearchWorkspaceLanding() {
  return (
    <>
      <section className="hero panel relative overflow-hidden !border-white/10 !bg-[linear-gradient(180deg,rgba(15,23,42,0.97),rgba(15,23,42,0.84))] !shadow-[0_24px_80px_-48px_rgba(8,15,40,0.95)]">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(56,189,248,0.12),transparent_34%),radial-gradient(circle_at_bottom_left,rgba(214,40,57,0.08),transparent_32%)]"
        />
        <div className="relative grid gap-8 lg:grid-cols-[minmax(0,1.18fr)_minmax(320px,0.82fr)]">
          <div className="grid gap-5">
            <div className="flex flex-wrap items-center gap-3">
              <p className="eyebrow">Research mode</p>
              <span className="inline-flex items-center rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-cyan-100">
                Live workspace
              </span>
            </div>

            <div className="grid gap-3">
              <h1 className="page-title">RBC Research overview</h1>
              <p className="page-copy max-w-3xl">
                A route atlas for the research area, connecting data upload, calibration registry, simulation, flux,
                and pathway pages into one scientific flow.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {RESEARCH_METRICS.map((metric) => (
                <MetricTile key={metric.label} {...metric} />
              ))}
            </div>
          </div>

          <aside className="rounded-[2rem] border border-white/10 bg-white/[0.04] p-5 shadow-[0_20px_60px_-34px_rgba(0,0,0,0.78)] backdrop-blur-sm">
            <div className="flex items-center justify-between gap-3">
              <div className="grid gap-1">
                <p className="eyebrow">Recommended flow</p>
                <h2 className="text-2xl font-semibold tracking-tight text-white">Start here</h2>
              </div>
              <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">
                Entry path
              </span>
            </div>

            <div className="mt-5 grid gap-3">
              {RESEARCH_FLOW.map((item, index) => (
                <article
                  className="grid grid-cols-[auto_1fr] gap-3 rounded-3xl border border-white/10 bg-slate-950/50 p-4"
                  key={item.title}
                >
                  <span className="grid size-10 place-items-center rounded-2xl border border-cyan-400/20 bg-cyan-400/10 text-sm font-semibold text-cyan-100">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <div className="grid gap-1">
                    <p className="text-sm font-semibold text-white">{item.title}</p>
                    <p className="text-sm leading-6 text-slate-400">{item.copy}</p>
                  </div>
                </article>
              ))}
            </div>

            <div className="mt-5 flex items-center justify-between rounded-3xl border border-cyan-400/20 bg-cyan-400/10 px-4 py-4">
              <div className="grid gap-1">
                <p className="text-sm font-semibold text-white">Move through the research pages</p>
                <p className="text-xs leading-5 text-cyan-50/75">
                  Each page keeps the same shell while narrowing the scientific lens.
                </p>
              </div>
              <ArrowRight className="size-4 shrink-0 text-cyan-100" />
            </div>
          </aside>
        </div>
      </section>

      <section className="panel overflow-hidden">
        <div className="mb-5 flex flex-col gap-3 border-b border-white/10 pb-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="grid gap-2">
              <p className="eyebrow">Research workflows</p>
              <h2 className="text-2xl font-semibold tracking-tight text-white">Live pages at a glance</h2>
            </div>
            <p className="max-w-2xl text-sm leading-6 text-slate-400">
              Explore the active research surfaces below. Each card opens a focused page with its own scientific
              angle and card theme.
            </p>
          </div>
        </div>
        <ModuleCards />
      </section>

      <section className="panel overflow-hidden">
        <div className="mb-5 flex flex-col gap-3 border-b border-white/10 pb-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="grid gap-2">
              <p className="eyebrow">Research snapshot</p>
              <h2 className="text-2xl font-semibold tracking-tight text-white">What this workspace gives you</h2>
            </div>
            <p className="max-w-2xl text-sm leading-6 text-slate-400">
              A compact summary of the shell, style, and scientific behavior that define the Research area.
            </p>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {SNAPSHOT_CARDS.map((card) => (
            <SnapshotCard key={card.label} {...card} />
          ))}
        </div>
      </section>

    <section className="panel overflow-hidden">
        <div className="mb-5 flex flex-col gap-3 border-b border-white/10 pb-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="grid gap-2">
              <p className="eyebrow">Getting started</p>
              <h2 className="text-2xl font-semibold tracking-tight text-white">A clean path through the research flow</h2>
            </div>
            <p className="max-w-2xl text-sm leading-6 text-slate-400">
              Use this sequence when you want to move from raw simulation output toward interpretation and validation.
            </p>
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-3">
          {STARTER_PATH.map((section, index) => (
            <article
              className="rounded-3xl border border-white/10 bg-[linear-gradient(180deg,rgba(26,29,35,0.96),rgba(19,22,28,0.98))] p-5 shadow-[0_18px_48px_-30px_rgba(0,0,0,0.8)]"
              key={section.title}
            >
              <div className="flex items-center justify-between gap-3">
                <span className="inline-flex size-10 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.04] text-sm font-semibold text-slate-300">
                  {String(index + 1).padStart(2, '0')}
                </span>
                <Sparkles className="size-4 text-cyan-300" />
              </div>
              <h3 className="mt-4 text-lg font-semibold tracking-tight text-white">{section.title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-400">{section.copy}</p>
            </article>
          ))}
        </div>
      </section>
    </>
  )
}
