import Link from 'next/link'
import { ArrowRight } from 'lucide-react'
import { PLATFORM_MODULE_CARDS } from '../../lib/platform-navigation.ts'
import { SidebarIcon } from './SidebarIcons'
import { cn } from '@/lib/utils'

type ModuleCardData = (typeof PLATFORM_MODULE_CARDS)[number]
type ModuleCardEmphasis = 'default' | 'handoff' | 'followup'

function getStatusTone(status: ModuleCardData['status']) {
  switch (status) {
    case 'live':
      return 'border-emerald-400/20 bg-emerald-400/10 text-emerald-100'
    case 'preview':
      return 'border-amber-400/20 bg-amber-400/10 text-amber-100'
    default:
      return 'border-cyan-400/20 bg-cyan-400/10 text-cyan-100'
  }
}

function getCardTheme(card: ModuleCardData, emphasis: ModuleCardEmphasis) {
  if (card.title === 'Calibration Registry' || emphasis === 'handoff') {
    return {
      cardClassName:
        'group relative overflow-hidden rounded-3xl border border-fuchsia-400/25 bg-[linear-gradient(180deg,rgba(34,16,42,0.96),rgba(19,22,28,0.98))] p-5 shadow-[0_18px_48px_-28px_rgba(0,0,0,0.82)] transition-all duration-300 hover:-translate-y-1 hover:border-fuchsia-300/35 hover:shadow-[0_24px_68px_-34px_rgba(232,121,249,0.24)]',
      glowClassName:
        'pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(232,121,249,0.18),transparent_36%),radial-gradient(circle_at_bottom_left,rgba(56,189,248,0.08),transparent_28%)] opacity-0 transition-opacity duration-300 group-hover:opacity-100',
      eyebrowClassName:
        'inline-flex items-center rounded-full border border-fuchsia-300/20 bg-fuchsia-300/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.28em] text-fuchsia-100',
      iconClassName:
        'grid size-11 shrink-0 place-items-center rounded-2xl border border-fuchsia-300/20 bg-fuchsia-300/10 text-fuchsia-100 shadow-[0_10px_30px_-14px_rgba(232,121,249,0.45)]',
      footerLabel: 'Open ledger',
      footerCopy: 'Prepares the active dataset for the next simulation run.',
      accentLabel: 'Calibration handoff',
    }
  }

  if (card.title === 'Simulation' || emphasis === 'followup') {
    return {
      cardClassName:
        'group relative overflow-hidden rounded-3xl border border-cyan-400/25 bg-[linear-gradient(180deg,rgba(17,31,42,0.96),rgba(19,22,28,0.98))] p-5 shadow-[0_18px_48px_-28px_rgba(0,0,0,0.82)] transition-all duration-300 hover:-translate-y-1 hover:border-cyan-300/40 hover:shadow-[0_24px_68px_-34px_rgba(34,211,238,0.24)]',
      glowClassName:
        'pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(56,189,248,0.18),transparent_36%),radial-gradient(circle_at_bottom_left,rgba(232,121,249,0.08),transparent_28%)] opacity-0 transition-opacity duration-300 group-hover:opacity-100',
      eyebrowClassName:
        'inline-flex items-center rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.28em] text-cyan-100',
      iconClassName:
        'grid size-11 shrink-0 place-items-center rounded-2xl border border-cyan-300/20 bg-cyan-300/10 text-cyan-100 shadow-[0_10px_30px_-14px_rgba(56,189,248,0.45)]',
      footerLabel: 'Open simulation',
      footerCopy: 'Consumes the active dataset and shows the run outcome.',
      accentLabel: 'Simulation step',
    }
  }

  return {
    cardClassName:
      'group relative overflow-hidden rounded-3xl border border-white/10 bg-[linear-gradient(180deg,rgba(26,29,35,0.96),rgba(19,22,28,0.98))] p-5 shadow-[0_18px_48px_-28px_rgba(0,0,0,0.82)] transition-all duration-300 hover:-translate-y-1 hover:border-cyan-400/25 hover:shadow-[0_24px_68px_-34px_rgba(34,211,238,0.28)]',
    glowClassName:
      'pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(56,189,248,0.12),transparent_36%),radial-gradient(circle_at_bottom_left,rgba(214,40,57,0.08),transparent_28%)] opacity-0 transition-opacity duration-300 group-hover:opacity-100',
    eyebrowClassName:
      'inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-400',
    iconClassName:
      'grid size-11 shrink-0 place-items-center rounded-2xl border border-white/10 bg-cyan-400/10 text-cyan-100 shadow-[0_10px_30px_-14px_rgba(34,211,238,0.45)]',
    footerLabel: 'Open page',
    footerCopy: null,
    accentLabel: null,
  }
}

function ModuleCard({
  card,
  emphasis = 'default',
}: {
  card: ModuleCardData
  emphasis?: ModuleCardEmphasis
}) {
  const theme = getCardTheme(card, emphasis)

  const content = (
    <div className="relative flex h-full flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <span className={theme.eyebrowClassName}>{card.eyebrow}</span>
        <span
          className={cn(
            'inline-flex items-center rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em]',
            getStatusTone(card.status)
          )}
        >
          {card.status}
        </span>
      </div>

      <div className="flex items-start gap-3">
        <span className={theme.iconClassName}>
          <SidebarIcon className="h-5 w-5" icon={card.icon} />
        </span>
        <div className="min-w-0">
          <h3 className="text-xl font-semibold tracking-tight text-white">{card.title}</h3>
          <p className="mt-1 text-sm leading-6 text-slate-400">{card.description}</p>
        </div>
      </div>

      {theme.footerCopy ? (
        <div className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">{theme.accentLabel}</p>
          <p className="mt-2 text-sm leading-6 text-slate-300">{theme.footerCopy}</p>
        </div>
      ) : null}

      <div className="mt-auto flex items-center justify-between gap-3 border-t border-white/10 pt-4 text-xs uppercase tracking-[0.28em] text-slate-500">
        <span>{theme.footerLabel}</span>
        <span className="inline-flex items-center gap-1 text-cyan-100 transition-transform duration-200 group-hover:translate-x-0.5">
          <ArrowRight className="size-3.5" />
        </span>
      </div>
    </div>
  )

  return (
    <Link className={theme.cardClassName} href={card.href ?? '#'}>
      <div aria-hidden="true" className={theme.glowClassName} />
      {content}
    </Link>
  )
}

function HandoffBridge() {
  return (
    <div className="flex items-center justify-between gap-4 rounded-3xl border border-fuchsia-400/20 bg-[linear-gradient(90deg,rgba(31,19,42,0.92),rgba(15,23,42,0.92))] px-5 py-4 shadow-[0_18px_48px_-30px_rgba(0,0,0,0.82)]">
      <div className="grid gap-1">
        <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-fuchsia-100/80">Calibration to simulation</p>
        <p className="text-sm font-semibold text-white">Lock the dataset in Calibration Registry, then open Simulation.</p>
        <p className="text-sm leading-6 text-slate-400">
          This is the handoff point where evidence becomes the next run.
        </p>
      </div>
      <ArrowRight className="size-5 shrink-0 text-cyan-100" />
    </div>
  )
}

export function ModuleCards() {
  const calibrationRegistryCard = PLATFORM_MODULE_CARDS.find((card) => card.title === 'Calibration Registry')
  const simulationCard = PLATFORM_MODULE_CARDS.find((card) => card.title === 'Simulation')
  const remainingCards = PLATFORM_MODULE_CARDS.filter(
    (card) => card.title !== 'Calibration Registry' && card.title !== 'Simulation'
  )

  return (
    <div className="grid gap-5">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(220px,0.42fr)_minmax(0,1fr)]">
        {calibrationRegistryCard ? <ModuleCard card={calibrationRegistryCard} emphasis="handoff" /> : null}
        <HandoffBridge />
        {simulationCard ? <ModuleCard card={simulationCard} emphasis="followup" /> : null}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {remainingCards.map((card) => (
          <ModuleCard card={card} key={card.title} />
        ))}
      </div>
    </div>
  )
}
