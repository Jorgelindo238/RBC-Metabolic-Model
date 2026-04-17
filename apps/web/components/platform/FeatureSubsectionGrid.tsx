import { cn } from '@/lib/utils'
import type { PlatformNavItem, PlatformNavSubsection } from './platform-shell.types'

function getFeatureSectionTheme(featureId: string) {
  switch (featureId) {
    case 'home':
      return {
        eyebrow: 'Home routes',
        title: 'Fast entry points',
        copy: 'Jump from the home page into research, RoBoCop, or calibration without extra clicks.',
      }
    case 'home-robocop':
      return {
        eyebrow: 'Assistant routes',
        title: 'RoBoCop entry points',
        copy: 'Use the home page cards to move between traces, guidance, and future assistant workflows.',
      }
    case 'research-overview':
      return {
        eyebrow: 'Research map',
        title: 'Pages at a glance',
        copy: 'Move between the live research routes and the analysis they contain.',
      }
    case 'simulation-workspace':
      return {
        eyebrow: 'Simulation controls',
        title: 'Run setup',
        copy: 'Move through the scenario, solver, and trajectory review in order.',
      }
    case 'data-upload':
      return {
        eyebrow: 'Import stages',
        title: 'Intake path',
        copy: 'Step through parsing, mapping, and readiness checks before analysis.',
      }
    case 'flux-analysis':
      return {
        eyebrow: 'Pathway breakdown',
        title: 'Flux layers',
        copy: 'Read grouped pathway views, reaction detail, and comparison notes.',
      }
    case 'sensitivity-analysis':
      return {
        eyebrow: 'Fit diagnostics',
        title: 'Comparison view',
        copy: 'Review dataset alignment and model quality side by side.',
      }
    case 'pathway-visualization':
      return {
        eyebrow: 'Network layers',
        title: 'Pathway map',
        copy: 'Trace the graph, the concentration state, and the summary panels.',
      }
    case 'parameter-calibration':
      return {
        eyebrow: 'Calibration steps',
        title: 'Tuning path',
        copy: 'Move from parameter choice into optimization and result review.',
      }
    case 'calibration-registry':
      return {
        eyebrow: 'Registry sections',
        title: 'Lead run view',
        copy: 'Inspect the summary, the registry history, and the artifact trail.',
      }
    case 'monitoring-overview':
      return {
        eyebrow: 'Monitoring routes',
        title: 'Active surfaces',
        copy: 'Move from the overview into Bag Repository, Quality Forecast, and Alerts while Hermes remains hidden as the future gateway.',
      }
    case 'monitoring-robocop':
      return {
        eyebrow: 'Messaging sections',
        title: 'Hermes preview',
        copy: 'Read the routing brief, Telegram handoff, and planned alert path for Monitoring.',
      }
    case 'bag-repo':
      return {
        eyebrow: 'Inventory layers',
        title: 'Repository view',
        copy: 'Move from the inventory table into the selected bag detail rail, then into the forecast handoff.',
      }
    case 'quality-forecast':
      return {
        eyebrow: 'Forecast layers',
        title: 'Predictive monitoring',
        copy: 'Move from the selected bag into the biomarker panel, the trajectory, and the alert handoff.',
      }
    case 'alerts':
      return {
        eyebrow: 'Alert sections',
        title: 'Triage path',
        copy: 'Scan the queue, the detail rail, and the operator action flow in sequence.',
      }
    default:
      return {
        eyebrow: 'Page sections',
        title: 'Module overview',
        copy: 'The live sections below show how to move through the workflow.',
      }
  }
}

export function FeatureSubsectionGrid({
  feature,
  subsection,
}: {
  feature: PlatformNavItem
  subsection: PlatformNavSubsection | null
}) {
  if (!feature.children?.length) {
    return null
  }

  const sectionTheme = getFeatureSectionTheme(feature.id)

  return (
    <section className="panel overflow-hidden border-white/10 bg-[linear-gradient(180deg,rgba(26,29,35,0.96),rgba(19,22,28,0.98))]">
      <div className="mb-5 flex flex-col gap-3 border-b border-white/10 pb-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="grid gap-2">
            <p className="eyebrow">{sectionTheme.eyebrow}</p>
            <h2 className="text-2xl font-semibold tracking-tight text-white">{sectionTheme.title}</h2>
          </div>
          <p className="max-w-2xl text-sm leading-6 text-slate-400">
            {sectionTheme.copy}
          </p>
        </div>
      </div>

      <div className="grid gap-4 pt-5 md:grid-cols-2 xl:grid-cols-3">
        {feature.children.map((item, index) => {
          const isActive = subsection?.id === item.id

          return (
            <article
              className={cn(
                'group relative overflow-hidden rounded-3xl border p-5 shadow-[0_14px_40px_-28px_rgba(0,0,0,0.75)] transition-all duration-300',
                isActive
                  ? 'border-cyan-400/25 bg-cyan-400/[0.08] shadow-[0_20px_60px_-34px_rgba(34,211,238,0.24)]'
                  : 'border-white/10 bg-white/[0.035] hover:-translate-y-0.5 hover:border-white/20 hover:bg-white/[0.05]'
              )}
              key={item.id}
            >
              <div
                aria-hidden="true"
                className={cn(
                  'pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(56,189,248,0.12),transparent_36%),radial-gradient(circle_at_bottom_left,rgba(214,40,57,0.08),transparent_28%)] opacity-0 transition-opacity duration-300 group-hover:opacity-100',
                  isActive && 'opacity-100'
                )}
              />
              <div className="relative flex h-full flex-col gap-4">
                <div className="flex items-center justify-between gap-3">
                  <span className="inline-flex size-9 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.04] text-[11px] font-semibold text-slate-300">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  {isActive ? (
                    <span className="inline-flex items-center rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-cyan-100">
                      Current focus
                    </span>
                  ) : (
                    <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">
                      Explore
                    </span>
                  )}
                </div>

                <div className="grid gap-2">
                  <strong className="text-lg font-semibold tracking-tight text-white">{item.title}</strong>
                  <p className="text-sm leading-6 text-slate-400">{item.description}</p>
                </div>

                <div className="mt-auto flex items-center gap-3 pt-2 text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                  <span className={cn('h-px flex-1', isActive ? 'bg-cyan-300/40' : 'bg-white/10')} />
                  {isActive ? 'Active section' : 'Reference section'}
                </div>
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}
