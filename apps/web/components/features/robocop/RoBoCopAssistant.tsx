'use client'

import { useState } from 'react'
import type { RoBoCopInterpretation, SimulationContext } from '@/types/robocop-context'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'
import {
  getCalibrationStatusLabel,
  getCalibrationStatusLine,
  getDatasetModeLabel,
  getDatasetStatusLine,
  getDatasetStatusLabel,
} from '@/lib/robocop/research-provenance'
import {
  Loader2,
  Brain,
  TrendingUp,
  AlertTriangle,
  Sparkles,
  Clock3,
  FlaskConical,
  Gauge,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  ArrowRight,
  CheckCircle2,
} from 'lucide-react'

interface RoBoCopAssistantProps {
  interpretation: RoBoCopInterpretation | null
  analysisContext?: SimulationContext | null
  loading?: boolean
  error?: string | null
  onRefresh?: () => void
  className?: string
}

const confidenceTone = {
  high: {
    icon: TrendingUp,
    badge: 'border-emerald-400/20 bg-emerald-400/10 text-emerald-200',
    accent: 'text-emerald-300',
  },
  medium: {
    icon: Brain,
    badge: 'border-amber-400/20 bg-amber-400/10 text-amber-200',
    accent: 'text-amber-200',
  },
  low: {
    icon: AlertTriangle,
    badge: 'border-rose-400/20 bg-rose-400/10 text-rose-200',
    accent: 'text-rose-200',
  },
} as const

function MetricCard({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: typeof Brain
  label: string
  value: string
  hint: string
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4 shadow-inner shadow-black/10">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.3em] text-slate-400">{label}</p>
          <p className="mt-2 text-lg font-semibold text-white">{value}</p>
          <p className="mt-1 text-xs leading-5 text-slate-400">{hint}</p>
        </div>
        <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-cyan-400/10 text-cyan-200 ring-1 ring-cyan-400/20">
          <Icon className="size-4" />
        </div>
      </div>
    </div>
  )
}

export function RoBoCopAssistant({
  interpretation,
  analysisContext,
  loading,
  error,
  onRefresh,
  className,
}: RoBoCopAssistantProps) {
  const [showDetails, setShowDetails] = useState(false)

  if (!interpretation && !loading && !error) {
    return null
  }

  const selectedMetabolites = analysisContext?.selectedMetabolites ?? []
  const focusPreview = selectedMetabolites.slice(0, 5)
  const focusOverflow = Math.max(selectedMetabolites.length - focusPreview.length, 0)
  const confidence = interpretation ? confidenceTone[interpretation.confidence] : confidenceTone.medium
  const ConfidenceIcon = confidence.icon

  const durationValue = analysisContext ? `${analysisContext.summary.duration.toFixed(1)}s` : '—'
  const solverValue = analysisContext?.summary.solver ?? '—'
  const horizonValue = analysisContext ? `${analysisContext.timeRange.end.toFixed(0)}d` : '—'
  const coverageValue = analysisContext
    ? `${analysisContext.metabolites.keyMetabolites.length}/${analysisContext.metabolites.total}`
    : '—'
  const datasetModeLabel = analysisContext ? getDatasetModeLabel(analysisContext) : null
  const datasetStatusLabel = analysisContext ? getDatasetStatusLabel(analysisContext) : null
  const datasetStatusLine = analysisContext ? getDatasetStatusLine(analysisContext) : null
  const calibrationStatusLabel = analysisContext ? getCalibrationStatusLabel(analysisContext) : null
  const datasetLabel = analysisContext?.activeDataset?.label ?? analysisContext?.activeDatasetLabel ?? null

  return (
    <Card
      className={cn(
        'relative overflow-hidden rounded-3xl border-slate-800/80 bg-slate-950 text-slate-50 shadow-[0_30px_90px_rgba(15,23,42,0.35)]',
        className
      )}
    >
      <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-cyan-400 via-sky-500 to-emerald-400" />
      <div className="absolute -right-20 -top-24 h-56 w-56 rounded-full bg-cyan-500/15 blur-3xl" />
      <div className="absolute -left-24 bottom-0 h-56 w-56 rounded-full bg-emerald-500/10 blur-3xl" />

      <CardHeader className="relative border-b border-white/10 px-6 pb-5 pt-6">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div className="space-y-3">
            <div className="flex items-start gap-3">
              <div className="grid size-12 shrink-0 place-items-center rounded-2xl bg-white/10 ring-1 ring-white/10">
                <Brain className="h-6 w-6 text-cyan-300" />
              </div>
              <div className="space-y-1">
                <CardTitle className="text-2xl font-semibold tracking-tight text-white">
                  RoBoCop Analysis
                </CardTitle>
                <CardDescription className="text-sm text-slate-300">
                  Grounded interpretation of the current simulation run
                </CardDescription>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              {interpretation && (
                <Badge
                  variant="outline"
                  className={cn('gap-1.5 border-white/10 bg-white/5 font-medium', confidence.badge)}
                >
                  <ConfidenceIcon className={cn('size-3.5', confidence.accent)} />
                  {interpretation.confidence} confidence
                </Badge>
              )}
              {analysisContext && (
                <Badge
                  variant="outline"
                  className="gap-1.5 border-cyan-400/20 bg-cyan-400/10 text-cyan-200"
                >
                  <Clock3 className="size-3.5" />
                  {analysisContext.timeRange.end.toFixed(0)} day horizon
                </Badge>
              )}
              {analysisContext?.summary.solver && (
                <Badge
                  variant="outline"
                  className="border-white/10 bg-white/5 text-slate-200"
                >
                  {analysisContext.summary.solver}
                </Badge>
              )}
              {datasetStatusLabel && (
                <Badge
                  variant="outline"
                  className={
                    analysisContext?.researchDataMode === 'custom_user_data_mode'
                      ? analysisContext.datasetApplied
                        ? 'border-cyan-400/20 bg-cyan-400/10 text-cyan-200'
                        : 'border-amber-400/20 bg-amber-400/10 text-amber-200'
                      : 'border-white/10 bg-white/5 text-slate-300'
                  }
                  >
                  {datasetModeLabel}
                </Badge>
              )}
              {calibrationStatusLabel && (
                <Badge
                  variant="outline"
                  className={
                    analysisContext?.calibrationApplied
                      ? 'border-violet-400/20 bg-violet-400/10 text-violet-200'
                      : 'border-white/10 bg-white/5 text-slate-300'
                  }
                >
                  {calibrationStatusLabel}
                </Badge>
              )}
              {selectedMetabolites.length > 0 && (
                <Badge
                  variant="outline"
                  className="border-emerald-400/20 bg-emerald-400/10 text-emerald-200"
                >
                  {selectedMetabolites.length} metabolites in focus
                </Badge>
              )}
            </div>
          </div>

          {interpretation && (
            <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 shadow-inner shadow-black/10">
              <div className="flex items-center gap-2">
                <Sparkles className="size-4 text-cyan-300" />
                <span className="text-xs font-medium uppercase tracking-[0.28em] text-slate-400">
                  Analysis mode
                </span>
              </div>
              <p className="mt-2 text-sm font-medium text-white">
                {datasetLabel ?? interpretation.grounding.dataSource}
              </p>
              <p className="mt-1 text-xs leading-5 text-slate-400">
                {datasetStatusLine ??
                  `${analysisContext?.timeRange.n_points ?? '—'} sampled points`}
              </p>
              {analysisContext?.calibrationSource && (
                <p className="mt-1 text-xs leading-5 text-slate-400">
                  {getCalibrationStatusLine(analysisContext)}
                </p>
              )}
            </div>
          )}
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            icon={Clock3}
            label="Duration"
            value={durationValue}
            hint="Wall-clock time for the latest run"
          />
          <MetricCard
            icon={FlaskConical}
            label="Solver"
            value={solverValue}
            hint={`${analysisContext?.timeRange.n_points ?? '—'} sampled time points`}
          />
          <MetricCard
            icon={Gauge}
            label="Horizon"
            value={horizonValue}
            hint="Simulated storage window"
          />
          <MetricCard
            icon={Brain}
            label="Coverage"
            value={coverageValue}
            hint="Key metabolites relative to the full model"
          />
        </div>
      </CardHeader>

      <CardContent className="relative px-6 py-6">
        {loading && (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
            <div className="flex items-center gap-3">
              <Loader2 className="size-4 animate-spin text-cyan-300" />
              <p className="text-sm font-medium text-white">Analyzing simulation...</p>
            </div>
            <div className="mt-4 space-y-3">
              <div className="h-4 w-3/4 rounded-full bg-white/10" />
              <div className="h-4 w-11/12 rounded-full bg-white/10" />
              <div className="h-4 w-2/3 rounded-full bg-white/10" />
            </div>
          </div>
        )}

        {error && (
          <div className="rounded-2xl border border-rose-400/20 bg-rose-500/10 p-5 text-sm text-rose-100">
            <p className="font-medium">Analysis Error</p>
            <p className="mt-1 text-rose-100/80">{error}</p>
          </div>
        )}

        {interpretation && (
          <div className="space-y-6">
            <section className="rounded-2xl border border-white/10 bg-white/5 p-5 shadow-inner shadow-black/10">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="space-y-2">
                  <p className="text-xs font-medium uppercase tracking-[0.35em] text-cyan-300/70">
                    Executive summary
                  </p>
                  <p className="text-base leading-7 text-slate-100 sm:text-lg">
                    {interpretation.summary}
                  </p>
                </div>
                <div className="hidden shrink-0 rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-3 text-cyan-200 md:block">
                  <Sparkles className="size-5" />
                </div>
              </div>

              {focusPreview.length > 0 && (
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <span className="text-[11px] font-medium uppercase tracking-[0.3em] text-slate-400">
                    Focus metabolites
                  </span>
                  {focusPreview.map((metabolite) => (
                    <Badge
                      key={metabolite}
                      variant="outline"
                      className="border-white/10 bg-white/5 text-slate-200"
                    >
                      {metabolite}
                    </Badge>
                  ))}
                  {focusOverflow > 0 && (
                    <Badge
                      variant="outline"
                      className="border-white/10 bg-white/5 text-slate-400"
                    >
                      +{focusOverflow} more
                    </Badge>
                  )}
                </div>
              )}
            </section>

            <div className="grid gap-6 xl:grid-cols-[1.35fr_1fr]">
              <section className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-white">Key insights</p>
                    <p className="text-xs text-slate-400">
                      Signals pulled from the current simulation state
                    </p>
                  </div>
                  <Badge variant="outline" className="border-white/10 bg-white/5 text-slate-200">
                    {interpretation.insights.length} signals
                  </Badge>
                </div>

                <div className="space-y-3">
                  {interpretation.insights.length > 0 ? (
                    interpretation.insights.map((insight, index) => (
                      <div
                        key={`${index}-${insight}`}
                        className="flex gap-3 rounded-2xl border border-white/10 bg-white/5 p-4 shadow-inner shadow-black/10"
                      >
                        <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-cyan-400/10 text-cyan-300 ring-1 ring-cyan-400/20">
                          <ArrowRight className="size-4" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-[11px] font-medium uppercase tracking-[0.28em] text-slate-500">
                            Insight {index + 1}
                          </p>
                          <p className="mt-1 text-sm leading-6 text-slate-200">{insight}</p>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-300">
                      No notable signals were extracted from this run.
                    </div>
                  )}
                </div>
              </section>

              <section className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-medium text-white">Recommended next steps</p>
                  <Badge variant="outline" className="border-emerald-400/20 bg-emerald-400/10 text-emerald-200">
                    {interpretation.recommendations?.length ?? 0}
                  </Badge>
                </div>

                <div className="space-y-3">
                  {(interpretation.recommendations?.length ? interpretation.recommendations : ['No explicit recommendation was generated for this run.']).map(
                    (recommendation, index) => (
                      <div
                        key={`${index}-${recommendation}`}
                        className="flex gap-3 rounded-2xl border border-emerald-400/20 bg-emerald-400/10 p-4 text-emerald-50 shadow-inner shadow-black/10"
                      >
                        <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-emerald-400/15 text-emerald-200 ring-1 ring-emerald-400/20">
                          <CheckCircle2 className="size-4" />
                        </div>
                        <p className="text-sm leading-6 text-emerald-50/90">{recommendation}</p>
                      </div>
                    )
                  )}
                </div>

                <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-4 shadow-inner shadow-black/10">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-xs font-medium uppercase tracking-[0.28em] text-slate-400">
                        Grounding
                      </p>
                      <p className="mt-1 text-sm text-slate-200">{interpretation.grounding.dataSource}</p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowDetails((value) => !value)}
                      className="gap-2 text-slate-300 hover:bg-white/10 hover:text-white"
                    >
                      {showDetails ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
                      {showDetails ? 'Hide details' : 'Show details'}
                    </Button>
                  </div>

                  {showDetails && (
                    <div className="mt-4 space-y-3">
                      <Separator className="bg-white/10" />
                      <div className="grid gap-3 sm:grid-cols-2">
                        <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                          <p className="text-[11px] font-medium uppercase tracking-[0.3em] text-slate-400">
                            Key observations
                          </p>
                          <div className="mt-3 space-y-2">
                            {interpretation.grounding.keyObservations.map((observation, index) => (
                              <div
                                key={`${index}-${observation}`}
                                className="rounded-xl border border-white/10 bg-slate-950/50 px-3 py-2 text-sm leading-5 text-slate-200"
                              >
                                {observation}
                              </div>
                            ))}
                          </div>
                        </div>

                        <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                          <p className="text-[11px] font-medium uppercase tracking-[0.3em] text-slate-400">
                            Context snapshot
                          </p>
                          <dl className="mt-3 space-y-3 text-sm">
                            <div className="flex items-center justify-between gap-3">
                              <dt className="text-slate-400">Duration</dt>
                              <dd className="font-medium text-slate-100">
                                {analysisContext ? `${analysisContext.summary.duration.toFixed(1)}s` : '—'}
                              </dd>
                            </div>
                            <div className="flex items-center justify-between gap-3">
                              <dt className="text-slate-400">Solver</dt>
                              <dd className="font-medium text-slate-100">{solverValue}</dd>
                            </div>
                            <div className="flex items-center justify-between gap-3">
                              <dt className="text-slate-400">Selected focus</dt>
                              <dd className="font-medium text-slate-100">
                                {selectedMetabolites.length || analysisContext?.metabolites.keyMetabolites.length || 0}
                              </dd>
                            </div>
                          </dl>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </section>
            </div>
          </div>
        )}
      </CardContent>

      <CardFooter className="relative flex flex-col gap-3 border-t border-white/10 px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-2">
          {selectedMetabolites.length > 0 ? (
            <>
              <Badge variant="outline" className="border-emerald-400/20 bg-emerald-400/10 text-emerald-200">
                Focused selection
              </Badge>
              {focusPreview.map((metabolite) => (
                <Badge
                  key={metabolite}
                  variant="outline"
                  className="border-white/10 bg-white/5 text-slate-200"
                >
                  {metabolite}
                </Badge>
              ))}
              {focusOverflow > 0 && (
                <Badge variant="outline" className="border-white/10 bg-white/5 text-slate-400">
                  +{focusOverflow} more
                </Badge>
              )}
            </>
          ) : (
            <Badge variant="outline" className="border-white/10 bg-white/5 text-slate-300">
              Using the simulation key metabolite set
            </Badge>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowDetails((value) => !value)}
            className="gap-2 text-slate-300 hover:bg-white/10 hover:text-white"
          >
            {showDetails ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
            {showDetails ? 'Hide details' : 'Show details'}
          </Button>
          {onRefresh && (
            <Button
              variant="outline"
              size="sm"
              onClick={onRefresh}
              className="gap-2 border-cyan-400/20 bg-cyan-400/10 text-cyan-100 hover:bg-cyan-400/20 hover:text-white"
            >
              <RefreshCw className="size-4" />
              Re-run simulation
            </Button>
          )}
        </div>
      </CardFooter>
    </Card>
  )
}
