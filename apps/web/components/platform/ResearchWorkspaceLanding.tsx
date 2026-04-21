import Link from 'next/link'
import { ArrowRight } from 'lucide-react'
import { PLATFORM_MODULE_CARDS } from '../../lib/platform-navigation.ts'

const PRIMARY_FLOW = [
  'Upload data',
  'Check calibration',
  'Run simulation',
  'Read flux and pathways',
] as const

const LIVE_MODULES = PLATFORM_MODULE_CARDS.filter((card) => card.status === 'live')

export function ResearchWorkspaceLanding() {
  return (
    <div className="grid gap-6">
      <section className="rounded-[2rem] border border-white/10 bg-[linear-gradient(180deg,rgba(15,23,42,0.96),rgba(15,23,42,0.82))] p-6 shadow-[0_24px_80px_-52px_rgba(8,15,40,0.95)]">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl space-y-3">
            <p className="eyebrow">Research overview</p>
            <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">RBC research workspace</h1>
            <p className="text-base leading-7 text-slate-400">
              A simple route map for moving from custom data to simulation, calibration, flux, and pathway review.
            </p>
          </div>
          <Link
            href="/research/data-upload"
            className="inline-flex items-center justify-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-400/10 px-4 py-2 text-sm font-semibold text-cyan-50 transition hover:bg-cyan-400/15"
          >
            Start with data upload
            <ArrowRight className="size-4" />
          </Link>
        </div>
      </section>

      <section className="rounded-[2rem] border border-white/10 bg-white/[0.03] p-5">
        <div className="grid gap-3 md:grid-cols-4">
          {PRIMARY_FLOW.map((step, index) => (
            <div key={step} className="flex items-center gap-3 rounded-2xl border border-white/10 bg-slate-950/55 p-4">
              <span className="grid size-8 shrink-0 place-items-center rounded-full border border-white/10 bg-white/[0.04] text-xs font-semibold text-slate-300">
                {index + 1}
              </span>
              <p className="text-sm font-semibold text-white">{step}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-[2rem] border border-white/10 bg-white/[0.03] p-5">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="eyebrow">Live tools</p>
            <h2 className="text-2xl font-semibold tracking-tight text-white">Open a focused page</h2>
          </div>
          <p className="max-w-xl text-sm leading-6 text-slate-400">
            Each page keeps one job: prepare data, run the model, inspect evidence, or interpret the network.
          </p>
        </div>

        <div className="divide-y divide-white/10 overflow-hidden rounded-3xl border border-white/10 bg-slate-950/45">
          {LIVE_MODULES.map((module) => (
            <Link
              key={module.title}
              href={module.href ?? '/research'}
              className="group grid gap-3 px-5 py-4 transition hover:bg-white/[0.04] md:grid-cols-[220px_1fr_auto] md:items-center"
            >
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">{module.eyebrow}</p>
                <p className="mt-1 text-base font-semibold text-white">{module.title}</p>
              </div>
              <p className="text-sm leading-6 text-slate-400">{module.description}</p>
              <span className="inline-flex items-center gap-2 text-sm font-semibold text-cyan-100 opacity-80 transition group-hover:opacity-100">
                Open
                <ArrowRight className="size-4" />
              </span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}
