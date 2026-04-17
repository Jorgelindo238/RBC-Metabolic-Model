import { FeatureSelectionEmptyState } from './FeatureSelectionEmptyState'
import { FeatureSubsectionGrid } from './FeatureSubsectionGrid'
import { WorkspaceFeatureContent } from './WorkspaceFeatureContent'
import { HomeDashboard } from '../features/HomeDashboard'
import { StatCards } from '../features/home/StatCards'
import type {
  MonitoringAlertWorkflowStateRecord,
  MonitoringAlertWorkflowTransitionRecord,
} from '@/lib/monitoring-alerts'
import { ArrowRight, Layers3 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { PlatformNavItem, PlatformNavSubsection, ProductContextShape } from './platform-shell.types'

interface WorkspaceFeatureSurfaceProps {
  access: { mode?: string | null } | null
  detail: any
  detailFields: readonly [string, unknown][]
  feature: PlatformNavItem | null
  alertsData?: {
    workflowHistory: MonitoringAlertWorkflowTransitionRecord[]
    workflowStates: MonitoringAlertWorkflowStateRecord[]
  }
  productContext: ProductContextShape
  runs: any[]
  subsection: PlatformNavSubsection | null
  workspaceLabel: string
}

function getFeatureSurfaceTheme(featureId: string) {
  switch (featureId) {
    case 'home':
      return {
        contextLabel: 'Where to begin',
        contextCopy: 'Use this home page to jump into the main research and assistant routes.',
        focusLabel: 'Quick start',
        focusFallbackTitle: 'Research home',
        focusCopy: 'Open the overview cards below to move into the live tools.',
      }
    case 'home-robocop':
      return {
        contextLabel: 'Assistant home',
        contextCopy: 'Use this page to orient yourself around RoBoCop, traces, and future guided workflows.',
        focusLabel: 'Assistant scope',
        focusFallbackTitle: 'RoBoCop home',
        focusCopy: 'Use the section cards to understand how the agent layer fits into the platform.',
      }
    case 'research-overview':
      return {
        contextLabel: 'What this page organizes',
        contextCopy: 'Use this overview to orient yourself before opening a focused analysis page.',
        focusLabel: 'Active view',
        focusFallbackTitle: 'Research map',
        focusCopy: 'A quick map of the live research surfaces and their roles.',
      }
    case 'simulation-workspace':
      return {
        contextLabel: 'What you can tune',
        contextCopy: 'Adjust the scenario, solver, and storage horizon before reading the trajectories.',
        focusLabel: 'Active scenario',
        focusFallbackTitle: 'Storage scenario',
        focusCopy: 'The controls that shape the current run.',
      }
    case 'data-upload':
      return {
        contextLabel: 'What you can validate',
        contextCopy: 'Check how incoming series map onto model metabolites and readiness checks.',
        focusLabel: 'Import stage',
        focusFallbackTitle: 'Dataset intake',
        focusCopy: 'Use the upload path to prepare data for comparison or calibration.',
      }
    case 'flux-analysis':
      return {
        contextLabel: 'What you can inspect',
        contextCopy: 'Read pathway activity by subsystem before comparing it to reference estimates.',
        focusLabel: 'Pathway lens',
        focusFallbackTitle: 'Flux overview',
        focusCopy: 'Move through grouped flux views, reaction detail, and comparisons.',
      }
    case 'sensitivity-analysis':
      return {
        contextLabel: 'What you can compare',
        contextCopy: 'Compare model output against data and isolate the largest fit gaps.',
        focusLabel: 'Fit check',
        focusFallbackTitle: 'Sensitivity view',
        focusCopy: 'Use the section cards to review dataset alignment and model quality.',
      }
    case 'pathway-visualization':
      return {
        contextLabel: 'What you can trace',
        contextCopy: 'Follow the network map and concentration state as storage evolves.',
        focusLabel: 'Network map',
        focusFallbackTitle: 'Pathway map',
        focusCopy: 'Use the sections to move between the graph, the state, and the summary.',
      }
    case 'parameter-calibration':
      return {
        contextLabel: 'What you can search',
        contextCopy: 'Look for parameter settings that bring the model closer to the observed curves.',
        focusLabel: 'Tuning lane',
        focusFallbackTitle: 'Calibration steps',
        focusCopy: 'Move from parameter selection into optimization and result review.',
      }
    case 'calibration-registry':
      return {
        contextLabel: 'What this ledger shows',
        contextCopy: 'Review the newest visible calibration record, compare benchmark outcomes, and open the artifact trail when you need provenance.',
        focusLabel: 'Ledger view',
        focusFallbackTitle: 'Latest record',
        focusCopy: 'Use the sections to inspect the summary, comparison lanes, and artifact evidence.',
      }
    case 'monitoring-overview':
      return {
        contextLabel: 'What this page scans',
        contextCopy: 'Survey the visible Monitoring pages: Bag Repository, Quality Forecast, and Alerts, with Hermes reserved as the future messaging gateway.',
        focusLabel: 'Operational view',
        focusFallbackTitle: 'Monitoring map',
        focusCopy: 'Use the sections to move from the overview into the active operational routes.',
      }
    case 'monitoring-robocop':
      return {
        contextLabel: 'What Hermes will read',
        contextCopy: 'This future gateway will route operator messages, alerts, and Telegram handoffs into Monitoring.',
        focusLabel: 'Messaging lens',
        focusFallbackTitle: 'Hermes gateway',
        focusCopy: 'Keep the discussion tied to the operational signal and the planned messaging flow.',
      }
    case 'bag-repo':
      return {
        contextLabel: 'What you can inventory',
        contextCopy: 'Scan bag records, donor metadata, and state snapshots without leaving the monitoring context.',
        focusLabel: 'Bag repository',
        focusFallbackTitle: 'Bag Repository',
        focusCopy: 'Move between the inventory table and the selected bag detail rail.',
      }
    case 'quality-forecast':
      return {
        contextLabel: 'What you can forecast',
        contextCopy: 'Use a selected bag, a constrained biomarker panel, and the latest simulation linkage to forecast quality.',
        focusLabel: 'Forecast lens',
        focusFallbackTitle: 'Quality outlook',
        focusCopy: 'Move from the selected bag to the biomarker panel, then into the trajectory and alert handoff.',
      }
    case 'alerts':
      return {
        contextLabel: 'What you can triage',
        contextCopy: 'Track forecast-derived alerts, persisted workflow state, and operator actions from one page.',
        focusLabel: 'Alert queue',
        focusFallbackTitle: 'Alert queue',
        focusCopy: 'Work through the queue, detail rail, and operator actions in order.',
      }
    default:
      return {
        contextLabel: 'What this page helps you do',
        contextCopy: 'Use the sections below to continue through the workflow.',
        focusLabel: 'Current section',
        focusFallbackTitle: 'Overview',
        focusCopy: 'Use the sections below to continue through the workflow.',
      }
  }
}

function getRouteChipLabel(workspaceLabel: string) {
  switch (workspaceLabel) {
    case 'Home':
      return 'Home route'
    case 'Monitoring':
      return 'Monitoring route'
    case 'RoBoCop':
      return 'Assistant route'
    default:
      return 'Research route'
  }
}

function getFocusChipLabel(workspaceLabel: string) {
  switch (workspaceLabel) {
    case 'Home':
      return 'Home focus'
    case 'Monitoring':
      return 'Operational focus'
    case 'RoBoCop':
      return 'Assistant focus'
    default:
      return 'Analysis focus'
  }
}

export function WorkspaceFeatureSurface({
  access,
  detail,
  detailFields,
  feature,
  alertsData,
  productContext,
  runs,
  subsection,
  workspaceLabel,
}: WorkspaceFeatureSurfaceProps) {
  if (!feature) {
    return <FeatureSelectionEmptyState />
  }

  const selectedSubsection = subsection ?? feature.children?.[0] ?? null
  const isHomeFeature = feature.id === 'home'
  const sectionCount = feature.children?.length ?? 0
  const surfaceTheme = getFeatureSurfaceTheme(feature.id)
  const routeChipLabel = getRouteChipLabel(workspaceLabel)
  const focusChipLabel = getFocusChipLabel(workspaceLabel)

  const statusTone = (() => {
    switch (feature.status) {
      case 'live':
        return 'border-emerald-400/20 bg-emerald-400/10 text-emerald-100'
      case 'preview':
        return 'border-amber-400/20 bg-amber-400/10 text-amber-100'
      default:
        return 'border-cyan-400/20 bg-cyan-400/10 text-cyan-100'
    }
  })()

  return (
    <>
      <section className="panel relative overflow-hidden !border-white/10 !bg-[linear-gradient(180deg,rgba(15,23,42,0.97),rgba(15,23,42,0.84))] !shadow-[0_24px_80px_-48px_rgba(8,15,40,0.95)]">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(56,189,248,0.12),transparent_34%),radial-gradient(circle_at_bottom_left,rgba(214,40,57,0.08),transparent_32%)]"
        />
        <div className="relative grid gap-6 lg:grid-cols-[minmax(0,1.18fr)_minmax(320px,0.82fr)]">
          <div className="grid gap-4">
            <div className="flex flex-wrap items-center gap-3">
              <p className="eyebrow">{selectedSubsection ? selectedSubsection.title : 'Workspace feature'}</p>
              <span className={cn('inline-flex items-center rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em]', statusTone)}>
                {feature.status}
              </span>
            </div>

            <h1 className="page-title">{feature.title}</h1>
            <p className="page-copy max-w-3xl">
              {selectedSubsection?.description ?? feature.description}
            </p>

            <div className="flex flex-wrap gap-2">
              <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-semibold text-slate-300">
                <Layers3 className="mr-1.5 size-3.5 text-cyan-300" />
                {sectionCount} section{sectionCount === 1 ? '' : 's'}
              </span>
              <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-semibold text-slate-300">
                {selectedSubsection?.title ?? 'Overview'}
              </span>
              <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">
                {routeChipLabel}
              </span>
            </div>
          </div>

          <aside className="rounded-3xl border border-white/10 bg-white/[0.04] p-5 shadow-[0_20px_60px_-34px_rgba(0,0,0,0.78)] backdrop-blur-sm">
            <p className="eyebrow">{workspaceLabel} context</p>
            <div className="mt-4 grid gap-3">
              <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">{surfaceTheme.contextLabel}</p>
                <p className="mt-2 text-sm leading-6 text-slate-300">{surfaceTheme.contextCopy}</p>
              </div>

              <div className="grid grid-cols-2 gap-3">
              <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Area</p>
                  <p className="mt-2 text-sm font-semibold text-white">{workspaceLabel}</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Sections</p>
                  <p className="mt-2 text-sm font-semibold text-white">{sectionCount}</p>
                </div>
              </div>

              <div className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-cyan-100/80">{surfaceTheme.focusLabel}</p>
                <p className="mt-2 text-sm font-semibold text-white">{selectedSubsection?.title ?? surfaceTheme.focusFallbackTitle}</p>
                <p className="mt-1 text-sm leading-6 text-cyan-50/75">
                  {selectedSubsection?.description ?? surfaceTheme.focusCopy}
                </p>
                <div className="mt-3 inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-cyan-100">
                  <ArrowRight className="size-3.5" />
                  {focusChipLabel}
                </div>
              </div>
            </div>
          </aside>
        </div>
      </section>

      {isHomeFeature ? <StatCards /> : null}
      <FeatureSubsectionGrid feature={feature} subsection={selectedSubsection} />
      {isHomeFeature ? (
        <HomeDashboard />
      ) : (
        <WorkspaceFeatureContent
          access={access}
          alertsData={alertsData}
          detail={detail}
          detailFields={detailFields}
          feature={feature}
          runs={runs}
        />
      )}
    </>
  )
}
