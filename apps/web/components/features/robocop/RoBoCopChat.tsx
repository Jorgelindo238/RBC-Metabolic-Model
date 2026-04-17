'use client'

import { useState, useRef, useEffect } from 'react'
import type { KeyboardEvent } from 'react'
import type { ResearchContext, RoBoCopChatState, RoBoCopChatMessage } from '@/types/research-context'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import {
  getCalibrationRegistryObservations,
  getCalibrationRegistryProvenanceSummary,
  getCalibrationRegistryStatusLabel,
  getCalibrationRegistryStatusLine,
  getFluxAnalysisObservations,
  getFluxAnalysisProvenanceSummary,
  getFluxAnalysisStatusLabel,
  getFluxAnalysisStatusLine,
  getPathwayVisualizationObservations,
  getPathwayVisualizationProvenanceSummary,
  getPathwayVisualizationStatusLabel,
  getPathwayVisualizationStatusLine,
  getCalibrationProvenanceSummary,
  getCalibrationStrategyLabel,
  getCalibrationStatusLabel,
  getDatasetModeLabel,
  getDatasetStatusLine,
  getSimulationProvenanceSummary,
} from '@/lib/robocop/research-provenance'
import {
  getCalibrationRunStatusLabel,
  getCalibrationRunStatusLine,
} from '@/lib/robocop/calibration-provenance'
import { Loader2, Brain, Send, X, Sparkles, MessageCircle } from 'lucide-react'

interface RoBoCopChatProps {
  context: ResearchContext | null
  onSendMessage?: (message: string) => Promise<string>
  className?: string
}

function getQuickPrompts(context: ResearchContext) {
  switch (context.moduleType) {
    case 'simulation': {
      const focusMetabolites = context.selectedMetabolites?.slice(0, 2) ?? []
      return [
        'Summarize the strongest stress signals in this run.',
        focusMetabolites.length > 0
          ? `What stands out about ${focusMetabolites.join(' and ')}?`
          : 'Is this using my uploaded data or Bordbar?',
        'Was the latest calibration applied?',
      ]
    }
    case 'calibration':
      if (context.calibrationStatus === 'running') {
        return [
          'What parameters are currently selected?',
          `What does ${getCalibrationStrategyLabel(context)} optimize?`,
          'Is the calibration still running?',
        ]
      }
      if (context.calibrationStatus === 'failed') {
        const errorDetail = context.calibrationError ? ` Error detail: ${context.calibrationError}` : ''
        return [
          'Why did this calibration fail?',
          'What should I inspect next?',
          `How can I recover from the failed run?${errorDetail}`,
        ]
      }
      if (context.calibrationStatus !== 'completed') {
        return [
          'What parameters are currently selected?',
          `What does ${getCalibrationStrategyLabel(context)} optimize?`,
          context.researchDataMode === 'custom_user_data_mode'
            ? 'Is this using my uploaded data or Bordbar?'
            : 'Is this using Bordbar reference data?',
        ]
      }
      return [
        'Summarize calibration quality and the completed result.',
        `What does ${getCalibrationStrategyLabel(context)} imply?`,
        'Which parameter family changed the most?',
        'What should I inspect next?',
      ]
    case 'calibration-registry':
      return [
        'Summarize this historical calibration record.',
        'How do the comparison lanes differ?',
        'Which historical run looks strongest?',
      ]
    case 'flux-analysis':
      if (context.fluxStatus === 'running') {
        return [
          'What provenance is already available for this flux run?',
          'Which pathway is likely to dominate once the result lands?',
          context.researchDataMode === 'custom_user_data_mode'
            ? 'Is my uploaded dataset active here?'
            : 'Is this using Bordbar reference data?',
        ]
      }
      if (context.fluxStatus === 'failed') {
        return [
          'Why did flux estimation fail?',
          'What should I inspect next?',
          context.researchDataMode === 'custom_user_data_mode'
            ? 'Is my uploaded dataset still active?'
            : 'How can I rerun this on Bordbar defaults?',
        ]
      }
      if (context.fluxStatus !== 'completed') {
        return [
          context.researchDataMode === 'custom_user_data_mode'
            ? 'Is my uploaded data active for this flux setup?'
            : 'Is this using Bordbar reference data?',
          'Which pathways should I watch most closely?',
          'Was the latest calibration applied?',
        ]
      }
      return [
        'Which fluxes dominate here?',
        'What pathways look most active?',
        context.researchDataMode === 'custom_user_data_mode'
          ? 'Was this influenced by my uploaded dataset?'
          : 'What does Bordbar tell us here?',
        'What does the completed result suggest?',
      ]
    case 'sensitivity-analysis':
      return [
        'Which metabolites are the most sensitive?',
        'Where does the model fit break down?',
        'Summarize the main validation gaps.',
      ]
    case 'pathway-visualization':
      if (context.playbackReady && context.playbackFrameIndex !== null) {
        const frameLabel = `frame ${context.playbackFrameIndex + 1}/${context.playbackFrameCount}${context.playbackTimepoint !== null ? ` at t=${context.playbackTimepoint.toFixed(2)} days` : ''}`
        return [
          `What does ${frameLabel} represent?`,
          context.dominantPathway
            ? `What is happening in ${context.dominantPathway} at this replay state?`
            : 'Which pathway is most active at this replay state?',
          context.topAccumulatingMetabolites?.length
            ? 'Which metabolites are accumulating here?'
            : 'What is changing most in this replay?',
          context.researchDataMode === 'custom_user_data_mode'
            ? 'Is this replay coming from my uploaded data or Bordbar?'
            : 'Is this replay using Bordbar reference data?',
        ]
      }
      return [
        'Summarize the current pathway map provenance.',
        'Which pathways look most represented?',
        'What stands out in the network topology?',
      ]
    case 'data-upload':
      return [
        'Summarize the data quality and mappings.',
        'Which columns need review?',
        'What should I validate next?',
      ]
    default:
      return [
        'Summarize the main takeaways.',
        'What should I look at next?',
        'Explain this result in plain language.',
      ]
  }
}

function generateFallbackResponse(message: string, context: ResearchContext): string {
  const insights: string[] = []
  const moduleTitle = context.moduleTitle

  switch (context.moduleType) {
    case 'simulation':
      insights.push(`Provenance: ${getSimulationProvenanceSummary(context)}`)
      insights.push(`Dataset state: ${getDatasetModeLabel(context)}`)
      insights.push(getDatasetStatusLine(context))
      insights.push(getCalibrationStatusLabel(context))
      if (context.summary.notableTrends?.length) {
        const trends = context.summary.notableTrends
          .filter((trend) => trend.magnitude === 'high')
          .map((trend) => `${trend.metabolite} shows ${trend.direction} trend`)
        if (trends.length > 0) {
          insights.push(`Notable: ${trends.join(', ')}`)
        }
      }
      if (context.selectedMetabolites?.length) {
        insights.push(`Selected metabolites: ${context.selectedMetabolites.slice(0, 5).join(', ')}`)
      }
      if (context.researchDataMode === 'custom_user_data_mode') {
        insights.push(
          context.datasetApplied
            ? `Simulation was seeded from the active custom dataset${context.activeDataset?.label ? ` (${context.activeDataset.label})` : ''}`
            : `Custom dataset mode was active, but the run fell back to Bordbar defaults${context.datasetFallbackReason ? `: ${context.datasetFallbackReason}` : ''}`
        )
      } else {
        insights.push('Simulation used the Bordbar default reference flow')
      }
      insights.push(
        `Simulation ran for ${context.outputs.timeRange.end} days using ${context.parameters.solver_method} solver`
      )
      break

    case 'calibration':
      insights.push(`Provenance: ${getCalibrationProvenanceSummary(context)}`)
      insights.push(getCalibrationRunStatusLine(context.calibrationStatus, context.resultSummary, context.fitMetrics))
      insights.push(
        context.calibrationStatus === 'completed'
          ? `Optimized ${context.inputs.selectedParameters.length} parameters using ${getCalibrationStrategyLabel(context)}`
          : context.calibrationStatus === 'running'
            ? `Calibration is running with ${context.inputs.selectedParameters.length} selected parameters`
            : context.calibrationStatus === 'failed'
              ? `Calibration failed after selecting ${context.inputs.selectedParameters.length} parameters`
              : `Calibration setup ready with ${context.inputs.selectedParameters.length} selected parameters`
      )
      if (context.inputs.selectedParameterFamilies.length > 0) {
        insights.push(`Parameter families: ${context.inputs.selectedParameterFamilies.join(', ')}`)
      }
      if (context.calibrationStatus === 'completed') {
        if (context.fitMetrics?.rSquared !== undefined) {
          insights.push(`Achieved R² of ${context.fitMetrics.rSquared.toFixed(3)}`)
        } else {
          insights.push(`Achieved R² of ${context.outputs.rSquared.toFixed(3)}`)
        }
        if (context.resultSummary) {
          insights.push(context.resultSummary)
        }
      } else if (context.calibrationStatus === 'running') {
        insights.push('The run is still in progress, so only the setup context is available.')
      } else if (context.calibrationStatus === 'failed') {
        insights.push('The completed result is unavailable because the calibration failed.')
        if (context.calibrationError) {
          insights.push(`Failure detail: ${context.calibrationError}`)
        }
      }
      insights.push(
        context.researchDataMode === 'custom_user_data_mode'
          ? 'Calibration used the active uploaded dataset'
          : 'Calibration used the Bordbar reference dataset'
      )
      break

    case 'calibration-registry':
      insights.push(`Provenance: ${getCalibrationRegistryProvenanceSummary(context)}`)
      insights.push(getCalibrationRegistryStatusLine(context))
      insights.push(...getCalibrationRegistryObservations(context))
      break

    case 'flux-analysis':
      insights.push(`Provenance: ${getFluxAnalysisProvenanceSummary(context)}`)
      insights.push(getFluxAnalysisStatusLine(context))
      insights.push(...getFluxAnalysisObservations(context))
      if (context.fluxStatus === 'completed') {
        insights.push(`Estimated fluxes across ${Object.keys(context.outputs.fluxes).length} reactions`)
        insights.push(`Dominant pathway: ${context.summary.dominantPathway}`)
      } else if (context.fluxStatus === 'running') {
        insights.push('Flux estimation is still running, so only the setup context is available so far.')
      } else if (context.fluxStatus === 'failed') {
        insights.push('Flux estimation failed before a completed result was produced.')
      } else {
        insights.push('Flux result is not available yet; this is the current setup state.')
      }
      break

    case 'sensitivity-analysis':
      insights.push(`Compared ${context.outputs.metaboliteComparison.length} metabolites`)
      insights.push(`Overall fit: ${context.summary.overallFit}`)
      break

    case 'pathway-visualization':
      insights.push(`Provenance: ${getPathwayVisualizationProvenanceSummary(context)}`)
      insights.push(getPathwayVisualizationStatusLine(context))
      insights.push(...getPathwayVisualizationObservations(context))
      if (context.pathwayResultAvailable) {
        insights.push(`Visualized ${context.outputs.networkStats.nodes} nodes and ${context.outputs.networkStats.edges} edges`)
        if (context.summary.keyPathways.length > 0) {
          insights.push(`Key pathways: ${context.summary.keyPathways.slice(0, 3).join(', ')}`)
        }
      } else if (context.pathwayStatus === 'running') {
        insights.push('The pathway map is still loading, so only the setup context is available so far.')
      } else if (context.pathwayFailed) {
        insights.push('The pathway map failed before a completed result was produced.')
        if (context.pathwayError) {
          insights.push(`Failure detail: ${context.pathwayError}`)
        }
      } else {
        insights.push('The pathway map result is not available yet; this is the current setup state.')
      }
      break

    case 'data-upload':
      insights.push(`Parsed ${context.outputs.nRows} rows across ${context.outputs.columns.length} columns`)
      insights.push(`Mapped ${context.summary.mappedColumns} columns with ${context.summary.unmappedColumns} still unmapped`)
      break

    default:
      insights.push(`Analyzing ${moduleTitle} results`)
  }

  return `Based on the ${moduleTitle} analysis:\n\n${insights.join('\n')}\n\nWhat specific aspect would you like to explore further?`
}

function extractContextReferences(message: string, context: ResearchContext): string[] {
  const refs: string[] = []
  const lowerMessage = message.toLowerCase()

  if (context.moduleType === 'simulation') {
    if (lowerMessage.includes('trend') || lowerMessage.includes('change')) {
      refs.push('notableTrends')
    }
    if (lowerMessage.includes('metabolite')) {
      refs.push('metabolites')
    }
    if (lowerMessage.includes('parameter')) {
      refs.push('parameters')
    }
    if (
      lowerMessage.includes('bordbar') ||
      lowerMessage.includes('custom') ||
      lowerMessage.includes('dataset') ||
      lowerMessage.includes('data') ||
      lowerMessage.includes('calibration') ||
      lowerMessage.includes('applied') ||
      lowerMessage.includes('loaded') ||
      lowerMessage.includes('provenance')
    ) {
      refs.push('provenance')
    }
  }

  if (context.moduleType === 'calibration') {
    if (lowerMessage.includes('r²') || lowerMessage.includes('r2') || lowerMessage.includes('fit')) {
      refs.push('fitQuality')
    }
    if (lowerMessage.includes('parameter')) {
      refs.push('parameters')
    }
    if (lowerMessage.includes('strategy') || lowerMessage.includes('method')) {
      refs.push('inputs.selectedOptimizationStrategy')
      refs.push('inputs.strategyLabel')
    }
    if (lowerMessage.includes('completed') || lowerMessage.includes('running') || lowerMessage.includes('failed')) {
      refs.push('calibrationStatus')
      refs.push('resultSummary')
    }
    if (lowerMessage.includes('improvement') || lowerMessage.includes('loss') || lowerMessage.includes('change')) {
      refs.push('fitMetrics')
      refs.push('parameterChanges')
    }
    if (lowerMessage.includes('family') || lowerMessage.includes('taxonomy')) {
      refs.push('inputs.selectedParameterFamilies')
      refs.push('inputs.canonicalTaxonomySource')
    }
    if (lowerMessage.includes('fail') || lowerMessage.includes('error')) {
      refs.push('calibrationError')
    }
    if (
      lowerMessage.includes('bordbar') ||
      lowerMessage.includes('custom') ||
      lowerMessage.includes('dataset') ||
      lowerMessage.includes('data') ||
      lowerMessage.includes('provenance') ||
      lowerMessage.includes('applied')
    ) {
      refs.push('provenance')
    }
  }

  if (context.moduleType === 'calibration-registry') {
    if (lowerMessage.includes('history') || lowerMessage.includes('ledger') || lowerMessage.includes('comparison')) {
      refs.push('registryComparison')
    }
    if (lowerMessage.includes('result') || lowerMessage.includes('score') || lowerMessage.includes('loss')) {
      refs.push('registryResultSummary')
      refs.push('summary')
    }
    if (lowerMessage.includes('strategy')) {
      refs.push('inputs.selectedOptimizationStrategy')
      refs.push('inputs.strategyLabel')
    }
    if (lowerMessage.includes('provenance') || lowerMessage.includes('record')) {
      refs.push('registryComparison')
      refs.push('provenance')
    }
  }

  if (context.moduleType === 'flux-analysis') {
    if (lowerMessage.includes('pathway')) {
      refs.push('summary.dominantPathway')
      refs.push('outputs.pathwayFluxTotals')
    }
    if (lowerMessage.includes('flux')) {
      refs.push('outputs.fluxes')
      refs.push('outputs.topFluxes')
      refs.push('summary.topReactions')
    }
    if (
      lowerMessage.includes('bordbar') ||
      lowerMessage.includes('custom') ||
      lowerMessage.includes('dataset') ||
      lowerMessage.includes('data') ||
      lowerMessage.includes('calibration') ||
      lowerMessage.includes('applied') ||
      lowerMessage.includes('loaded') ||
      lowerMessage.includes('provenance') ||
      lowerMessage.includes('fallback')
    ) {
      refs.push('researchDataMode')
      refs.push('datasetApplied')
      refs.push('calibrationApplied')
      refs.push('calibrationSource')
      refs.push('fluxStatus')
    }
    if (lowerMessage.includes('result') || lowerMessage.includes('summary') || lowerMessage.includes('interpret')) {
      refs.push('fluxStatus')
      refs.push('resultSummary')
      refs.push('summary')
    }
  }

  if (context.moduleType === 'sensitivity-analysis') {
    if (lowerMessage.includes('error') || lowerMessage.includes('fit')) {
      refs.push('validationMetrics')
    }
    if (lowerMessage.includes('metabolite')) {
      refs.push('metabolites')
    }
  }

  if (context.moduleType === 'pathway-visualization') {
    if (lowerMessage.includes('pathway')) {
      refs.push('summary.keyPathways')
      refs.push('outputs.networkStats')
    }
    if (
      lowerMessage.includes('bordbar') ||
      lowerMessage.includes('custom') ||
      lowerMessage.includes('dataset') ||
      lowerMessage.includes('data') ||
      lowerMessage.includes('calibration') ||
      lowerMessage.includes('applied') ||
      lowerMessage.includes('loaded') ||
      lowerMessage.includes('provenance')
    ) {
      refs.push('researchDataMode')
      refs.push('datasetApplied')
      refs.push('calibrationApplied')
      refs.push('calibrationSource')
    }
    if (lowerMessage.includes('result') || lowerMessage.includes('summary') || lowerMessage.includes('interpret')) {
      refs.push('pathwayStatus')
      refs.push('resultSummary')
      refs.push('summary')
    }
  }

  if (context.moduleType === 'data-upload') {
    if (lowerMessage.includes('column') || lowerMessage.includes('mapping')) {
      refs.push('mappings')
    }
    if (lowerMessage.includes('quality') || lowerMessage.includes('data')) {
      refs.push('dataQuality')
    }
  }

  return refs
}

export function RoBoCopChat({ context, onSendMessage, className }: RoBoCopChatProps) {
  const [chatState, setChatState] = useState<RoBoCopChatState>({
    messages: [],
    isLoading: false,
  })
  const [isOpen, setIsOpen] = useState(false)
  const [inputValue, setInputValue] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [chatState.messages])

  if (!context) {
    return null
  }

  const quickPrompts = getQuickPrompts(context)
  const selectedCount =
    context.moduleType === 'simulation'
      ? context.selectedMetabolites?.length ?? 0
      : context.moduleType === 'calibration'
        ? context.inputs.selectedParameters?.length ?? 0
        : context.moduleType === 'flux-analysis'
          ? context.inputs.appliedConcentrationMetabolites?.length ?? 0
          : context.moduleType === 'calibration-registry'
            ? context.registryComparison.visibleRuns
            : context.moduleType === 'pathway-visualization'
              ? context.outputs.networkStats.pathways.length
            : 0
  const contextLabel = `${context.moduleTitle} • ${context.moduleType}`
  const selectedLabel =
      context.moduleType === 'calibration'
        ? 'parameters'
        : context.moduleType === 'flux-analysis'
          ? 'applied'
          : context.moduleType === 'calibration-registry'
            ? 'runs'
            : context.moduleType === 'pathway-visualization'
              ? 'pathways'
              : 'selected'
  const datasetStatusLabel = getDatasetModeLabel(context)
  const datasetStatusLine = getDatasetStatusLine(context)
  const calibrationStatusLabel =
    context.moduleType === 'calibration'
      ? getCalibrationRunStatusLabel(context.calibrationStatus)
      : context.moduleType === 'calibration-registry'
        ? getCalibrationRegistryStatusLabel(context)
      : getCalibrationStatusLabel(context)
  const calibrationProvenanceSummary =
    context.moduleType === 'calibration'
      ? getCalibrationProvenanceSummary(context)
      : context.moduleType === 'calibration-registry'
        ? getCalibrationRegistryProvenanceSummary(context)
        : null
  const fluxProvenanceSummary =
    context.moduleType === 'flux-analysis'
      ? getFluxAnalysisProvenanceSummary(context)
      : null

  const handleSendMessage = async (messageText = inputValue) => {
    const trimmedMessage = messageText.trim()

    if (!trimmedMessage || chatState.isLoading) return

    const userMessage: RoBoCopChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: trimmedMessage,
      timestamp: new Date().toISOString(),
    }

    setChatState((previous) => ({
      ...previous,
      messages: [...previous.messages, userMessage],
      isLoading: true,
      error: undefined,
    }))
    setInputValue('')

    try {
      const response = (await onSendMessage?.(trimmedMessage)) || generateFallbackResponse(trimmedMessage, context)

      const assistantMessage: RoBoCopChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response,
        timestamp: new Date().toISOString(),
        contextReferences: extractContextReferences(trimmedMessage, context),
      }

      setChatState((previous) => ({
        ...previous,
        messages: [...previous.messages, assistantMessage],
        isLoading: false,
      }))
    } catch (error) {
      setChatState((previous) => ({
        ...previous,
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to send message',
      }))
    }
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault()
      void handleSendMessage()
    }
  }

  return (
    <div className={cn('fixed bottom-6 right-6 z-50 w-[min(100vw-1.5rem,28rem)]', className)}>
      {isOpen ? (
        <div className="relative flex h-[min(82vh,42rem)] flex-col overflow-hidden rounded-[28px] border border-white/10 bg-slate-950/95 text-slate-50 shadow-[0_30px_90px_rgba(15,23,42,0.45)] backdrop-blur-xl">
          <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-cyan-400 via-sky-500 to-emerald-400" />
          <div className="pointer-events-none absolute -right-20 -top-16 h-52 w-52 rounded-full bg-cyan-500/12 blur-3xl" />
          <div className="pointer-events-none absolute -left-16 bottom-0 h-52 w-52 rounded-full bg-emerald-500/10 blur-3xl" />

          <div className="relative flex items-start justify-between gap-4 border-b border-white/10 px-5 py-4">
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <div className="grid size-10 place-items-center rounded-2xl bg-white/10 ring-1 ring-white/10">
                  <Brain className="size-5 text-cyan-300" />
                </div>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-sm font-semibold text-white">RoBoCop</h3>
                    <Badge variant="outline" className="border-white/10 bg-white/5 text-slate-200">
                      {context.moduleTitle}
                    </Badge>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Badge variant="outline" className="border-cyan-400/20 bg-cyan-400/10 text-cyan-200">
                      {contextLabel}
                    </Badge>
                    <Badge
                      variant="outline"
                      className={
                        context.researchDataMode === 'custom_user_data_mode'
                          ? context.datasetApplied
                            ? 'border-emerald-400/20 bg-emerald-400/10 text-emerald-200'
                            : 'border-amber-400/20 bg-amber-400/10 text-amber-200'
                          : 'border-white/10 bg-white/5 text-slate-300'
                      }
                    >
                      {datasetStatusLabel}
                    </Badge>
                    <Badge
                      variant="outline"
                      className={
                        context.calibrationApplied || context.calibratedParametersActive
                          ? 'border-violet-400/20 bg-violet-400/10 text-violet-200'
                          : 'border-white/10 bg-white/5 text-slate-300'
                      }
                    >
                      {calibrationStatusLabel}
                    </Badge>
                    {selectedCount > 0 && (
                      <Badge variant="outline" className="border-emerald-400/20 bg-emerald-400/10 text-emerald-200">
                        {selectedCount} {selectedLabel}
                      </Badge>
                    )}
                    {context.moduleType === 'calibration' && context.calibrationResultAvailable && context.outputs.rSquared != null && (
                      <Badge variant="outline" className="border-sky-400/20 bg-sky-400/10 text-sky-200">
                        R² {context.outputs.rSquared.toFixed(3)}
                      </Badge>
                    )}
                    {context.moduleType === 'calibration' && context.calibrationResultAvailable && context.summary.improvement != null && (
                      <Badge variant="outline" className="border-emerald-400/20 bg-emerald-400/10 text-emerald-200">
                        {context.summary.improvement.toFixed(1)}% improvement
                      </Badge>
                    )}
                  </div>
                  <p className="text-xs text-slate-400">
                    {context.moduleType === 'calibration'
                      ? context.calibrationResultAvailable
                        ? 'Grounded replies about the latest calibration result'
                        : 'Grounded replies about the current calibration setup'
                      : context.moduleType === 'calibration-registry'
                        ? 'Grounded replies about the calibration ledger and comparison lanes'
                        : context.moduleType === 'flux-analysis'
                          ? context.fluxResultAvailable
                            ? 'Grounded replies about the latest flux result'
                            : 'Grounded replies about the current flux setup'
                          : context.moduleType === 'pathway-visualization'
                            ? context.pathwayResultAvailable
                              ? 'Grounded replies about the current pathway map'
                              : 'Grounded replies about the pathway setup'
                      : 'Grounded replies about the current research context'}
                  </p>
                  {calibrationProvenanceSummary && (
                    <p className="mt-2 max-w-[38rem] text-xs leading-5 text-slate-400">
                      {calibrationProvenanceSummary}
                    </p>
                  )}
                  {fluxProvenanceSummary && (
                    <p className="mt-2 max-w-[38rem] text-xs leading-5 text-slate-400">
                      {fluxProvenanceSummary}
                    </p>
                  )}
                </div>
              </div>
            </div>

            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => setIsOpen(false)}
              className="text-slate-300 hover:bg-white/10 hover:text-white"
            >
              <X className="size-4" />
            </Button>
          </div>

          <div className="relative flex-1 overflow-y-auto px-4 py-4">
            <div className="space-y-4">
              {chatState.messages.length === 0 && (
                <div className="rounded-3xl border border-white/10 bg-white/5 p-5 shadow-inner shadow-black/10">
                  <div className="grid size-12 place-items-center rounded-2xl bg-gradient-to-br from-cyan-400/20 to-blue-500/20 text-cyan-200">
                    <Sparkles className="size-5" />
                  </div>
                  <p className="mt-4 text-base font-medium text-white">
                    Ask RoBoCop anything about this result
                  </p>
                  <p className="mt-2 text-sm leading-6 text-slate-300">
                    The assistant stays grounded in the current research module, with responses tied to the live context. Use the prompt chips below to get started.
                  </p>
                </div>
              )}

              {chatState.messages.map((message) => (
                <div key={message.id} className={cn('flex gap-3', message.role === 'user' ? 'justify-end' : 'justify-start')}>
                  {message.role === 'assistant' && (
                    <div className="grid size-8 shrink-0 place-items-center rounded-2xl bg-white/10 text-cyan-200 ring-1 ring-white/10">
                      <Brain className="size-4" />
                    </div>
                  )}

                  <div
                    className={cn(
                      'max-w-[82%] rounded-3xl px-4 py-3 text-sm leading-6 shadow-lg',
                      message.role === 'user'
                        ? 'bg-gradient-to-br from-cyan-400 to-blue-500 text-slate-950'
                        : 'border border-white/10 bg-white/5 text-slate-100'
                    )}
                  >
                    <p className="whitespace-pre-wrap">{message.content}</p>

                    {message.contextReferences && message.contextReferences.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {message.contextReferences.map((reference) => (
                          <Badge
                            key={reference}
                            variant="outline"
                            className="border-white/10 bg-white/5 text-[10px] uppercase tracking-[0.24em] text-slate-300"
                          >
                            {reference}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>

                  {message.role === 'user' && (
                    <div className="grid size-8 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-cyan-400 to-blue-500 text-slate-950 ring-1 ring-cyan-300/30">
                      <MessageCircle className="size-4" />
                    </div>
                  )}
                </div>
              ))}

              {chatState.isLoading && (
                <div className="flex justify-start gap-3">
                  <div className="grid size-8 shrink-0 place-items-center rounded-2xl bg-white/10 text-cyan-200 ring-1 ring-white/10">
                    <Brain className="size-4" />
                  </div>
                  <div className="rounded-3xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-200">
                    <Loader2 className="size-4 animate-spin text-cyan-300" />
                  </div>
                </div>
              )}

              {chatState.error && (
                <div className="flex justify-center">
                  <div className="rounded-2xl border border-rose-400/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
                    Error: {chatState.error}
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          </div>

          <div className="relative border-t border-white/10 bg-slate-950/95 p-4">
              {quickPrompts.length > 0 && (
                <div className="mb-2.5 flex flex-wrap gap-1.5">
                {quickPrompts.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => {
                      setInputValue(prompt)
                      inputRef.current?.focus()
                    }}
                    className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] leading-4 text-slate-200 transition hover:border-cyan-400/20 hover:bg-white/10"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            )}

              <div className="rounded-2xl border border-white/10 bg-white/5 p-2 shadow-inner shadow-black/10">
                <div className="flex items-end gap-2">
                <Input
                  ref={inputRef}
                  value={inputValue}
                  onChange={(event) => setInputValue(event.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={`Ask about ${context.moduleTitle}...`}
                  disabled={chatState.isLoading}
                  className="border-0 bg-transparent px-3 text-slate-50 placeholder:text-slate-400 shadow-none focus-visible:ring-0"
                />
                <Button
                  size="icon-sm"
                  onClick={() => {
                    void handleSendMessage()
                  }}
                  disabled={chatState.isLoading || !inputValue.trim()}
                  className="size-10 rounded-xl bg-gradient-to-br from-cyan-400 to-blue-500 text-slate-950 shadow-lg hover:from-cyan-300 hover:to-blue-400"
                >
                  {chatState.isLoading ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
                </Button>
              </div>

              <div className="mt-2 flex items-center justify-between gap-3 px-1 text-[11px] text-slate-400">
                <span>Press Enter to send</span>
                <span>
              {context.moduleType === 'simulation'
                    ? 'Grounded in the latest run'
                      : context.moduleType === 'calibration'
                        ? context.calibrationResultAvailable
                          ? 'Grounded in the latest calibration result'
                          : 'Grounded in the current calibration setup'
                      : context.moduleType === 'calibration-registry'
                        ? 'Grounded in the latest registry record'
                        : context.moduleType === 'flux-analysis'
                          ? context.fluxResultAvailable
                            ? 'Grounded in the latest flux result'
                            : 'Grounded in the current flux setup'
                          : context.moduleType === 'pathway-visualization'
                            ? context.pathwayResultAvailable
                              ? 'Grounded in the current pathway map'
                              : 'Grounded in the pathway setup'
                      : 'Context-aware response'}
                </span>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <Button
          onClick={() => setIsOpen(true)}
          className="group flex items-center gap-3 rounded-full border border-white/10 bg-slate-950/95 px-4 py-3 text-slate-50 shadow-[0_18px_50px_rgba(15,23,42,0.35)] backdrop-blur-xl transition-transform hover:-translate-y-0.5 hover:bg-slate-900"
        >
          <span className="relative grid size-10 place-items-center rounded-full bg-gradient-to-br from-cyan-400 to-blue-500 text-slate-950 shadow-lg">
            <Brain className="size-5" />
            <span className="absolute inset-0 rounded-full bg-cyan-300/40 opacity-0 transition-opacity group-hover:opacity-80" />
          </span>

          <span className="flex flex-col items-start leading-tight">
            <span className="text-sm font-semibold text-white">Ask RoBoCop</span>
            <span className="text-xs text-slate-400">Research-module chat</span>
          </span>

          <Badge variant="outline" className="border-white/10 bg-white/5 text-slate-200">
            {context.moduleTitle}
          </Badge>
        </Button>
      )}
    </div>
  )
}
