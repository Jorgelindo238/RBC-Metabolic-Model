'use client'

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { apiClient } from '@/lib/api-client'
import { useResearchContext } from '@/contexts/ResearchContextProvider'
import { useResearchDataset } from '@/contexts/ResearchDatasetProvider'
import { useLatestResearchSimulationSnapshot } from '@/lib/research-simulation'
import { buildPathwayVisualizationResearchContext } from '@/lib/robocop/research-context-builders'
import {
  getCalibrationStatusLabel,
  getDatasetModeLabel,
  getPathwayVisualizationObservations,
  getPathwayVisualizationProvenanceSummary,
  getPathwayVisualizationStatusLabel,
  getPathwayVisualizationStatusLine,
} from '@/lib/robocop/research-provenance'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Slider } from '@/components/ui/slider'
import { AlertCircle, Loader2, Network, Pause, Play, RefreshCw, SkipBack, Sparkles } from 'lucide-react'
import type { PathwayCompactOverviewItem } from '@/types/pathway-network'
import type { PathwayVisualizationSelection } from '@/types/research-context'
import type { PathwayNetworkState } from '@/types/pathway-network'
import type { ResearchSimulationSnapshot } from '@/types/research-simulation'
import { NetworkGraph } from './pathway/NetworkGraph'

const LEGEND = [
  { label: 'Glycolysis', color: '#e74c3c' },
  { label: 'Pentose Phosphate', color: '#9b59b6' },
  { label: 'Rapoport-Luebering', color: '#f39c12' },
  { label: 'Nucleotide Salvage', color: '#1abc9c' },
  { label: 'Energy', color: '#34495e' },
]

function formatCount(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return value.toLocaleString()
}

function formatPlaybackTime(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return Math.abs(value) >= 100 || Math.abs(value) < 0.01 ? value.toExponential(2) : value.toFixed(2)
}

function formatScientificValue(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return Math.abs(value) >= 100 || Math.abs(value) < 0.01 ? value.toExponential(2) : value.toFixed(3)
}

type PathwayReactionPreview = {
  id: string
  label: string
  enzyme: string
  source: string
  target: string
  reversible: boolean
  pathway?: string | null
  flux?: number | null
}

function clampIndex(index: number, totalFrames: number) {
  return totalFrames <= 0 ? 0 : Math.min(Math.max(index, 0), totalFrames - 1)
}

function buildConcentrationPayload(snapshot: ResearchSimulationSnapshot, frameIndex: number) {
  const row = snapshot.result.x[frameIndex] ?? snapshot.result.x[snapshot.result.x.length - 1] ?? []
  return snapshot.result.metabolite_names.reduce((acc, metabolite, index) => {
    acc[metabolite] = Number(row[index] ?? 0)
    return acc
  }, {} as Record<string, number>)
}

function buildFluxPayload(snapshot: ResearchSimulationSnapshot, frameIndex: number) {
  const fluxes = snapshot.result.flux_data?.fluxes
  if (!fluxes) return null
  const payload = Object.entries(fluxes).reduce((acc, [reaction, series]) => {
    const value = series[frameIndex] ?? series[series.length - 1]
    if (typeof value === 'number') acc[reaction] = value
    return acc
  }, {} as Record<string, number>)
  return Object.keys(payload).length > 0 ? payload : null
}

function SignalPill({ children, tone = 'slate' }: { children: string; tone?: 'slate' | 'cyan' | 'emerald' | 'violet' }) {
  const tones = {
    slate: 'border-white/10 bg-white/[0.04] text-slate-300',
    cyan: 'border-cyan-400/20 bg-cyan-400/10 text-cyan-100',
    emerald: 'border-emerald-400/20 bg-emerald-400/10 text-emerald-100',
    violet: 'border-violet-400/20 bg-violet-400/10 text-violet-100',
  } as const

  return <Badge variant="outline" className={`rounded-full text-[10px] uppercase tracking-[0.18em] ${tones[tone]}`}>{children}</Badge>
}

function MetricCard({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 shadow-inner shadow-black/10">
      <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">{label}</p>
      <p className="mt-2 text-xl font-semibold text-white">{value}</p>
      <p className="mt-1 text-xs leading-5 text-slate-400">{hint}</p>
    </div>
  )
}

function SelectionChip({
  label,
  active,
  onClick,
}: {
  label: string
  active: boolean
  onClick: () => void
}) {
  return (
    <Button
      type="button"
      size="sm"
      variant="outline"
      onClick={onClick}
      className={`h-auto rounded-full border px-3 py-1.5 text-[11px] uppercase tracking-[0.16em] ${
        active
          ? 'border-cyan-300/40 bg-cyan-300/15 text-cyan-50 hover:bg-cyan-300/20'
          : 'border-white/10 bg-white/[0.04] text-slate-200 hover:bg-white/[0.08] hover:text-white'
      }`}
    >
      {label}
    </Button>
  )
}

function CompactOverviewCard({
  item,
  selected,
  onSelect,
}: {
  item: PathwayCompactOverviewItem
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`group flex h-full flex-col justify-between rounded-2xl border p-4 text-left transition ${
        selected
          ? 'border-cyan-300/40 bg-cyan-300/12 shadow-[0_0_0_1px_rgba(34,211,238,0.15)]'
          : 'border-white/10 bg-slate-950/60 hover:border-white/20 hover:bg-slate-950/80'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="size-2.5 rounded-full" style={{ backgroundColor: item.color }} />
            <p className="text-sm font-semibold text-white">{item.pathway}</p>
          </div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">
            {item.nodeCount} metabolites
          </p>
        </div>
        <Badge
          variant="outline"
          className={`rounded-full border-white/10 text-[10px] uppercase tracking-[0.18em] ${
            selected ? 'bg-cyan-300/15 text-cyan-50' : 'bg-white/[0.04] text-slate-200'
          }`}
        >
          {item.connectorMetabolite ?? 'Hub'}
        </Badge>
      </div>

      <p className="mt-3 text-sm leading-6 text-slate-300">{item.bridgeSummary}</p>

      <div className="mt-3 space-y-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-500">Bridge partners</p>
        <div className="flex flex-wrap gap-1.5">
          {item.bridgePathways.length > 0 ? (
            item.bridgePathways.map((partner) => (
              <Badge
                key={partner}
                variant="outline"
                className="rounded-full border-white/10 bg-white/[0.04] text-[10px] uppercase tracking-[0.18em] text-slate-300"
              >
                {partner}
              </Badge>
            ))
          ) : (
            <Badge
              variant="outline"
              className="rounded-full border-white/10 bg-white/[0.04] text-[10px] uppercase tracking-[0.18em] text-slate-300"
            >
              Internal hub
            </Badge>
          )}
        </div>
      </div>

      <div className="mt-3 space-y-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-500">Top nodes</p>
        <div className="flex flex-wrap gap-1.5">
          {item.topMetabolites.slice(0, 3).map((metabolite) => (
            <Badge
              key={metabolite}
              variant="outline"
              className="rounded-full border-white/10 bg-white/[0.04] text-[10px] uppercase tracking-[0.18em] text-slate-300"
            >
              {metabolite}
            </Badge>
          ))}
        </div>
      </div>

      <p className="mt-4 text-[10px] font-semibold uppercase tracking-[0.24em] text-cyan-200/70">
        {selected ? 'Connector focused' : 'Click to focus connector'}
      </p>
    </button>
  )
}

function buildCompactBridgeGraph(
  network: PathwayNetworkState | null,
  compactOverview: PathwayCompactOverviewItem[]
): PathwayNetworkState | null {
  if (!network || compactOverview.length === 0) {
    return network
  }

  const nodeLookup = new Map(network.nodes.map((node) => [node.id, node]))
  const compactNodes = compactOverview.map((item) => {
    const connectorId = item.connectorMetabolite ?? item.pathway
    const connectorNode =
      nodeLookup.get(connectorId) ??
      network.nodes.find((candidate) => candidate.label === connectorId || candidate.id === connectorId) ??
      null
    const groupMembers = network.pathwayGroups[item.pathway] ?? []
    const memberNodes = groupMembers
      .map((metaboliteId) => nodeLookup.get(metaboliteId))
      .filter((candidate): candidate is NonNullable<typeof candidate> => Boolean(candidate))
    const referenceNode = connectorNode ?? memberNodes[0] ?? null
    const averagedNode = memberNodes.length
      ? {
          x: memberNodes.reduce((sum, node) => sum + node.x, 0) / memberNodes.length,
          y: memberNodes.reduce((sum, node) => sum + node.y, 0) / memberNodes.length,
          compartment: memberNodes[0]?.compartment ?? 'cytosol',
          concentration: memberNodes[0]?.concentration,
        }
      : null
    const baseNode = referenceNode ?? averagedNode

    return {
      id: connectorId,
      label: connectorId,
      pathway: item.pathway,
      x: baseNode?.x ?? 0,
      y: baseNode?.y ?? 0,
      compartment: baseNode?.compartment ?? 'cytosol',
      concentration: baseNode?.concentration ?? connectorNode?.concentration ?? undefined,
      size: Math.max(18, Math.min(24, 15 + item.nodeCount / 3)),
      color: item.color,
    }
  })

  const compactNodeIds = new Set(compactNodes.map((node) => node.id))
  const compactPathwayToNodeId = new Map(compactOverview.map((item) => [item.pathway, item.connectorMetabolite ?? item.pathway]))
  const compactEdges: PathwayNetworkState['edges'] = []
  const seenEdges = new Set<string>()

  for (const item of compactOverview) {
    const sourceId = compactPathwayToNodeId.get(item.pathway)
    if (!sourceId || !compactNodeIds.has(sourceId)) {
      continue
    }

    for (const partnerPathway of item.bridgePathways) {
      const targetId = compactPathwayToNodeId.get(partnerPathway)
      if (!targetId || !compactNodeIds.has(targetId)) {
        continue
      }

      const edgeKey = [sourceId, targetId].sort().join('::')
      if (seenEdges.has(edgeKey)) {
        continue
      }

      seenEdges.add(edgeKey)
      compactEdges.push({
        source: sourceId,
        target: targetId,
        enzyme: item.connectorMetabolite ? `${item.connectorMetabolite} bridge` : `${item.pathway} bridge`,
        reversible: true,
        color: item.color,
        pathway: item.pathway,
        flux: null,
      })
    }
  }

  return {
    ...network,
    title: 'RBC compact pathway atlas',
    stats: {
      nodes: compactNodes.length,
      edges: compactEdges.length,
      reactions: compactEdges.length,
      pathways: compactOverview.length,
    },
    dominantPathway: network.dominantPathway ?? compactOverview[0]?.pathway ?? null,
    pathwayGroups: Object.fromEntries(
      compactOverview.map((item) => [item.pathway, item.connectorMetabolite ? [item.connectorMetabolite] : []])
    ),
    compactOverview,
    nodes: compactNodes,
    edges: compactEdges,
    reactionNodes: undefined,
  }
}

export function PathwayVisualization() {
  const { setContext } = useResearchContext()
  const { activeDatasetSummary, activeCalibration } = useResearchDataset()
  const latestSimulationSnapshot = useLatestResearchSimulationSnapshot()
  const [network, setNetwork] = useState<PathwayNetworkState | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [playbackIndex, setPlaybackIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [selectedEntity, setSelectedEntity] = useState<PathwayVisualizationSelection | null>(null)
  const [pathwayViewMode, setPathwayViewMode] = useState<'compact' | 'full'>('full')
  const requestIdRef = useRef(0)

  const activeSnapshot = latestSimulationSnapshot?.result.success ? latestSimulationSnapshot : null
  const timepoints = activeSnapshot?.result.t ?? []
  const playbackAvailable = timepoints.length > 0
  const frameIndex = playbackAvailable ? clampIndex(playbackIndex, timepoints.length) : 0
  const currentTime = playbackAvailable ? timepoints[frameIndex] ?? null : null
  const playbackSourceLabel = activeSnapshot?.result.active_dataset_label ?? activeDatasetSummary.label
  const playbackFluxAware = Boolean(activeSnapshot?.result.flux_data?.fluxes && Object.keys(activeSnapshot.result.flux_data.fluxes).length > 0)
  const compactOverview = useMemo(() => network?.compactOverview ?? [], [network])
  const graphNetwork = useMemo(
    () => (pathwayViewMode === 'compact' ? buildCompactBridgeGraph(network, compactOverview) : network),
    [compactOverview, network, pathwayViewMode]
  )
  useLayoutEffect(() => {
    if (!playbackAvailable) {
      setPlaybackIndex(0)
      setIsPlaying(false)
      return
    }

    setPlaybackIndex(Math.max(timepoints.length - 1, 0))
    setIsPlaying(false)
  }, [activeSnapshot?.snapshotId, playbackAvailable, timepoints.length])

  useEffect(() => {
    if (!selectedEntity || !graphNetwork) {
      return
    }

    const stillExists =
      selectedEntity.kind === 'metabolite'
        ? graphNetwork.nodes.some((node) => node.id === selectedEntity.id)
        : Boolean(
            (graphNetwork.reactionNodes ?? []).some(
              (reaction) =>
                reaction.id === selectedEntity.id ||
                reaction.label === selectedEntity.id ||
                reaction.enzyme === selectedEntity.id ||
                reaction.label === selectedEntity.label ||
                reaction.enzyme === selectedEntity.label
            ) ||
              graphNetwork.edges.some(
                (edge) =>
                  edge.enzyme === selectedEntity.id ||
                  edge.enzyme === selectedEntity.label ||
                  edge.source === selectedEntity.id ||
                  edge.target === selectedEntity.id
              )
          )

    if (!stillExists) {
      setSelectedEntity(null)
    }
  }, [graphNetwork, selectedEntity])

  const loadNetwork = useCallback(async () => {
    const requestId = ++requestIdRef.current
    setLoading(true)
    setError(null)

    try {
      if (activeSnapshot && playbackAvailable) {
        const concentrations = buildConcentrationPayload(activeSnapshot, frameIndex)
        const fluxes = buildFluxPayload(activeSnapshot, frameIndex)
        const res = await apiClient.post<PathwayNetworkState>('/pathway/network-state', {
          concentrations,
          fluxes: fluxes ?? undefined,
        })
        if (requestId === requestIdRef.current) setNetwork(res.data)
      } else {
        const res = await apiClient.get<PathwayNetworkState>('/pathway/network')
        if (requestId === requestIdRef.current) setNetwork(res.data)
      }
    } catch (err: any) {
      if (requestId === requestIdRef.current) {
        setError(err?.response?.data?.detail || err.message || 'Failed to load network')
      }
    } finally {
      if (requestId === requestIdRef.current) setLoading(false)
    }
  }, [activeSnapshot, frameIndex, playbackAvailable])

  useEffect(() => {
    void loadNetwork()
  }, [loadNetwork])

  useEffect(() => {
    if (!playbackAvailable || !isPlaying || timepoints.length < 2) return
    const timer = window.setInterval(() => {
      setPlaybackIndex((current) => (current >= timepoints.length - 1 ? current : current + 1))
    }, 700)
    return () => window.clearInterval(timer)
  }, [isPlaying, playbackAvailable, timepoints.length])

  useEffect(() => {
    if (playbackAvailable && isPlaying && frameIndex >= timepoints.length - 1) {
      setIsPlaying(false)
    }
  }, [frameIndex, isPlaying, playbackAvailable, timepoints.length])

  const pathwayStatus = loading ? 'running' : error ? 'failed' : network ? 'completed' : 'setup_only'
  const pathwayContext = useMemo(
    () => buildPathwayVisualizationResearchContext(graphNetwork, activeDatasetSummary, activeCalibration, {
      pathwayStatus,
      pathwayError: error,
      latestSimulationSnapshot: activeSnapshot,
      playbackIndex: frameIndex,
      selectedEntity,
      pathwayViewMode,
    }),
    [activeCalibration, activeDatasetSummary, activeSnapshot, error, frameIndex, graphNetwork, pathwayStatus, pathwayViewMode, selectedEntity]
  )

  useEffect(() => {
    setContext(pathwayContext)
    return () => setContext(null)
  }, [pathwayContext, setContext])

  const ranks = useMemo(() => {
    if (!graphNetwork) return []
    const counts = new Map<string, number>()
    for (const node of graphNetwork.nodes) counts.set(node.pathway ?? 'other', (counts.get(node.pathway ?? 'other') ?? 0) + 1)
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([pathway, count]) => ({ pathway, count }))
  }, [graphNetwork])

  const dominantPathway = ranks[0]?.pathway ?? 'unknown'
  const pathwayCount = pathwayContext.outputs.networkStats.pathways.length
  const nodeCount = pathwayContext.outputs.networkStats.nodes
  const reactionCount = network?.reactionNodes?.length ?? network?.edges.length ?? 0
  const datasetLabel = activeDatasetSummary.label
  const datasetModeLabel = getDatasetModeLabel(pathwayContext)
  const calibrationStatusLabel = getCalibrationStatusLabel(pathwayContext)
  const pathwayStatusLabel = getPathwayVisualizationStatusLabel(pathwayContext)
  const pathwayStatusLine = getPathwayVisualizationStatusLine(pathwayContext)
  const resultSummary = pathwayContext.resultSummary ?? getPathwayVisualizationProvenanceSummary(pathwayContext)
  const observations = getPathwayVisualizationObservations(pathwayContext).slice(0, pathwayContext.playbackReady ? 6 : 4)
  const featuredMetabolites = useMemo(() => graphNetwork?.nodes.slice(0, 5) ?? [], [graphNetwork])
  const featuredReactions = useMemo<PathwayReactionPreview[]>(
    () =>
      graphNetwork
        ? (graphNetwork.reactionNodes?.slice(0, 5) ??
            graphNetwork.edges.slice(0, 5).map((edge, index) => ({
              id: `${edge.enzyme}:${edge.source}:${edge.target}:${index}`,
              label: edge.enzyme,
              enzyme: edge.enzyme,
              source: edge.source,
              target: edge.target,
              reversible: edge.reversible ?? false,
              pathway: edge.pathway ?? null,
              flux: typeof edge.flux === 'number' ? edge.flux : null,
            })))
        : [],
    [graphNetwork]
  )
  const selectedEntityDetails = useMemo(() => {
    if (!graphNetwork || !selectedEntity) {
      return null
    }

    if (selectedEntity.kind === 'metabolite') {
      const node = graphNetwork.nodes.find((candidate) => candidate.id === selectedEntity.id)
      if (!node) {
        return null
      }

      return {
        kind: 'metabolite' as const,
        id: node.id,
        label: node.label ?? node.id,
        pathway: node.pathway ?? 'Other',
        summary: pathwayContext.selectedEntitySummary ?? selectedEntity.summary ?? `${node.label ?? node.id} • ${node.pathway ?? 'Other'}`,
        concentration: node.concentration ?? null,
        source: node.compartment ?? 'cytosol',
      }
    }

    const reaction =
      graphNetwork.reactionNodes?.find(
        (candidate) =>
          candidate.id === selectedEntity.id ||
          candidate.id === selectedEntity.label ||
          candidate.label === selectedEntity.id ||
          candidate.label === selectedEntity.label ||
          candidate.enzyme === selectedEntity.id ||
          candidate.enzyme === selectedEntity.label
      ) ??
      graphNetwork.edges.find(
        (candidate) =>
          candidate.enzyme === selectedEntity.id ||
          candidate.enzyme === selectedEntity.label ||
          candidate.source === selectedEntity.id ||
          candidate.target === selectedEntity.id
      )
    if (!reaction) {
      return null
    }

    return {
      kind: 'reaction' as const,
      id: 'id' in reaction ? reaction.id : selectedEntity.id,
      label: 'label' in reaction ? reaction.label : selectedEntity.label,
      pathway: reaction.pathway ?? 'Other',
      summary:
        pathwayContext.selectedEntitySummary ??
        selectedEntity.summary ??
        `${'label' in reaction ? reaction.label : selectedEntity.label} • ${reaction.source} → ${reaction.target}`,
      flux: reaction.flux ?? null,
      source: reaction.source,
      target: reaction.target,
      reversible: reaction.reversible,
    }
  }, [network, pathwayContext.selectedEntitySummary, selectedEntity])

  const legendItems = network?.legend ?? LEGEND
  const networkCardTitle = pathwayViewMode === 'compact' ? 'RBC compact pathway graph' : 'RBC metabolic network'
  const networkCardDescription =
    pathwayViewMode === 'compact'
      ? 'Nine pathway groups reduced to their principal connector metabolites. Use the graph controls to zoom and inspect the bridge map.'
      : 'Plotly-backed pathway map with metabolite circles and reaction diamonds colored by pathway family and scaled by live concentration and flux state.'
  const explorerHeading = pathwayViewMode === 'compact' ? 'RBC compact graph' : 'RBC metabolic map'
  const explorerCopy =
    pathwayViewMode === 'compact'
      ? 'The compact graph keeps one key connector metabolite per pathway group and shows the bridge relations between groups. Zoom in to inspect the reduced map.'
      : 'The graph stays the scientific focus. Playback controls are tucked into the graph panel so the page stays readable.'
  const graphModeBadge = pathwayViewMode === 'compact' ? 'Compact graph' : 'Network graph'

  return (
    <div className="grid gap-6">
      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(330px,0.85fr)]">
        <Card className="overflow-hidden border-white/10 bg-[linear-gradient(180deg,rgba(15,23,42,0.98),rgba(15,23,42,0.86))] shadow-[0_30px_90px_rgba(15,23,42,0.35)]">
          <CardHeader className="space-y-4 border-b border-white/10 px-5 py-5 sm:px-6">
            <div className="flex flex-wrap items-center gap-2">
              <SignalPill tone="cyan">Pathway network</SignalPill>
              <SignalPill tone={datasetModeLabel.includes('Custom') ? 'emerald' : 'slate'}>{datasetLabel}</SignalPill>
              <SignalPill tone={datasetModeLabel.includes('Custom') ? 'emerald' : 'slate'}>{datasetModeLabel}</SignalPill>
              <SignalPill tone={pathwayContext.calibrationApplied ? 'violet' : 'slate'}>{calibrationStatusLabel}</SignalPill>
              <SignalPill tone={pathwayContext.pathwayResultAvailable ? 'emerald' : 'slate'}>{pathwayStatusLabel}</SignalPill>
              <SignalPill tone={pathwayViewMode === 'compact' ? 'violet' : 'slate'}>
                {pathwayViewMode === 'compact' ? 'Compact graph' : 'Full model map'}
              </SignalPill>
            </div>
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="space-y-3">
                <CardTitle className="text-3xl text-white sm:text-4xl">Pathway Visualization</CardTitle>
              <CardDescription className="max-w-3xl text-base leading-7 text-slate-400">
                Inspect the RBC metabolic network as a compact scientific map or switch to the full registry map.
                RoBoCop stays present, but the graph and playback remain the center of gravity.
              </CardDescription>
              </div>
              <Button type="button" variant="outline" onClick={() => void loadNetwork()} className="gap-2 border-white/10 bg-white/[0.04] text-slate-100 hover:bg-white/[0.08]">
                {loading ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
                {loading ? 'Refreshing...' : 'Refresh network'}
              </Button>
            </div>
          </CardHeader>

          <CardContent className="space-y-5 px-5 py-5 sm:px-6">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard label="Metabolites" value={formatCount(nodeCount)} hint="Metabolite nodes in the current map" />
              <MetricCard label="Reactions" value={formatCount(reactionCount)} hint="Enzyme-labeled connections in the current map" />
              <MetricCard label="Pathway groups" value={formatCount(pathwayCount)} hint="Unique pathway labels represented" />
              <MetricCard label="Most represented" value={network ? dominantPathway : '—'} hint={network ? 'Largest pathway group by node count' : 'Waiting for the graph snapshot'} />
            </div>

            <div className="grid gap-4 xl:grid-cols-[minmax(0,1.12fr)_minmax(290px,0.88fr)]">
              <div className="rounded-[28px] border border-white/10 bg-white/[0.03] p-5 shadow-inner shadow-black/10">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-2">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.32em] text-cyan-200/75">Pathway result summary</p>
                    <h2 className="text-xl font-semibold text-white">
                      {network
                        ? pathwayViewMode === 'compact'
                          ? 'Compact graph ready'
                          : 'Network snapshot ready'
                        : 'Pathway network in progress'}
                    </h2>
                  </div>
                  <SignalPill tone={network ? 'emerald' : 'slate'}>{pathwayStatusLabel}</SignalPill>
                </div>

                <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">{resultSummary}</p>

                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Network state</p>
                    <p className="mt-2 text-lg font-semibold text-white">
                      {network
                        ? pathwayViewMode === 'compact'
                          ? 'Compact graph ready'
                          : 'Reaction-labeled map ready'
                        : 'Loading network'}
                    </p>
                    <p className="mt-1 text-sm text-slate-400">{pathwayStatusLine}</p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Playback</p>
                    <p className="mt-2 text-lg font-semibold text-white">{activeSnapshot ? `Frame ${frameIndex + 1}/${timepoints.length}` : 'No simulation snapshot'}</p>
                    <p className="mt-1 text-sm text-slate-400">
                      {activeSnapshot && currentTime !== null ? `t = ${formatPlaybackTime(currentTime)} days` : 'Run Simulation to unlock time playback'}
                    </p>
                  </div>
                </div>

                <div className="mt-4 rounded-2xl border border-white/10 bg-slate-950/60 p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Interpretation cues</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {pathwayContext.summary.keySignals.map((signal) => (
                      <Badge key={signal} variant="outline" className="border-white/10 bg-white/[0.04] text-[10px] uppercase tracking-[0.18em] text-slate-300">
                        {signal}
                      </Badge>
                    ))}
                  </div>
                </div>
              </div>

              <div className="rounded-[28px] border border-white/10 bg-white/[0.04] p-5 shadow-[0_20px_60px_-34px_rgba(0,0,0,0.78)] backdrop-blur-sm">
                <p className="eyebrow">RoBoCop lens</p>
                <div className="mt-4 grid gap-3">
                  <div className="rounded-2xl border border-white/10 bg-slate-950/55 p-4">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Dataset</p>
                    <p className="mt-2 text-sm font-semibold text-white">{datasetLabel}</p>
                    <p className="mt-1 text-sm leading-6 text-slate-300">{datasetModeLabel}</p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-slate-950/55 p-4">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Calibration</p>
                    <p className="mt-2 text-sm font-semibold text-white">{calibrationStatusLabel}</p>
                    <p className="mt-1 text-sm leading-6 text-slate-300">
                      {pathwayContext.calibrationApplied || pathwayContext.calibratedParametersActive
                        ? getCalibrationStatusLabel(pathwayContext)
                        : 'Default Bordbar parameters are still in effect'}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-slate-950/55 p-4">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Network</p>
                    <p className="mt-2 text-sm font-semibold text-white">{pathwayStatusLabel}</p>
                    <p className="mt-1 text-sm leading-6 text-slate-300">{pathwayStatusLine}</p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-slate-950/55 p-4">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">RoBoCop cues</p>
                    <div className="mt-2 space-y-1.5">
                      {observations.map((observation, index) => (
                        <p key={`${index}-${observation}`} className="text-sm leading-6 text-slate-300">{observation}</p>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      {error && (
        <Card className="border-destructive/40 bg-destructive/5 shadow-sm">
          <CardContent className="flex items-start gap-3 pt-6">
            <AlertCircle className="h-5 w-5 shrink-0 text-destructive" />
            <div className="space-y-1">
              <p className="text-sm font-semibold text-destructive">Pathway visualization error</p>
              <p className="text-sm text-destructive/90">{error}</p>
            </div>
          </CardContent>
        </Card>
      )}

      <section className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="space-y-1">
            <p className="eyebrow">Network explorer</p>
            <h2 className="section-heading">{explorerHeading}</h2>
            <p className="section-copy max-w-2xl">{explorerCopy}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="rounded-full border-white/10 bg-white/[0.04] text-slate-200">{network ? `${nodeCount} nodes` : 'Loading'}</Badge>
            <Badge variant="outline" className="rounded-full border-white/10 bg-white/[0.04] text-slate-200">{network ? `${reactionCount} reactions` : 'Waiting for graph snapshot'}</Badge>
          </div>
        </div>

        {loading && !network ? (
          <Card className="border-white/10 bg-slate-950/60">
            <CardContent className="flex flex-col items-center justify-center gap-3 py-16 text-center">
              <Loader2 className="h-6 w-6 animate-spin text-cyan-300" />
              <p className="text-sm font-medium text-white">Loading pathway network...</p>
              <p className="max-w-md text-sm leading-6 text-slate-400">The network explorer will populate once the graph snapshot finishes loading.</p>
            </CardContent>
          </Card>
        ) : network ? (
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(280px,0.8fr)]">
            <Card className="overflow-hidden border-white/10 bg-slate-950/70 shadow-[0_20px_60px_-34px_rgba(8,15,40,0.8)]">
              <CardHeader className="border-b border-white/10 bg-white/[0.03] px-5 py-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <span className="grid size-8 place-items-center rounded-2xl border border-white/10 bg-white/5 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-200">01</span>
                      <Badge variant="outline" className="border-white/10 bg-white/[0.04] text-slate-200">{graphModeBadge}</Badge>
                    </div>
                    <CardTitle className="text-xl text-white">{networkCardTitle}</CardTitle>
                    <CardDescription className="text-slate-400">{networkCardDescription}</CardDescription>
                  </div>
                  <div className="grid size-12 place-items-center rounded-2xl bg-cyan-400/10 text-cyan-200 ring-1 ring-cyan-400/20">
                    <Network className="size-5" />
                  </div>
                </div>
              </CardHeader>

              <CardContent className="space-y-4 px-5 py-4">
                <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="space-y-1">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.32em] text-cyan-200/75">Playback controls</p>
                      <p className="text-sm text-slate-300">{activeSnapshot ? `Frame ${frameIndex + 1}/${timepoints.length}` : 'Static network'}</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => setPathwayViewMode('compact')}
                        className={`gap-2 ${
                          pathwayViewMode === 'compact'
                            ? 'border-cyan-300/40 bg-cyan-300/15 text-cyan-50 hover:bg-cyan-300/20'
                            : 'border-white/10 bg-white/[0.04] text-slate-100 hover:bg-white/[0.08]'
                        }`}
                      >
                        Compact graph
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => setPathwayViewMode('full')}
                        className={`gap-2 ${
                          pathwayViewMode === 'full'
                            ? 'border-cyan-300/40 bg-cyan-300/15 text-cyan-50 hover:bg-cyan-300/20'
                            : 'border-white/10 bg-white/[0.04] text-slate-100 hover:bg-white/[0.08]'
                        }`}
                      >
                        Full model map
                      </Button>
                      <Button type="button" size="sm" variant="outline" onClick={() => {
                        if (!playbackAvailable) return
                        if (isPlaying) { setIsPlaying(false); return }
                        setPlaybackIndex((current) => (current >= timepoints.length - 1 ? 0 : current))
                        setIsPlaying(true)
                      }} disabled={!playbackAvailable} className="gap-2 border-white/10 bg-white/[0.04] text-slate-100 hover:bg-white/[0.08]">
                        {isPlaying ? <Pause className="size-4" /> : <Play className="size-4" />}
                        {isPlaying ? 'Pause' : 'Play'}
                      </Button>
                      <Button type="button" size="sm" variant="ghost" onClick={() => { setPlaybackIndex(0); setIsPlaying(false) }} disabled={!playbackAvailable} className="gap-2 text-slate-300 hover:bg-white/[0.06] hover:text-white">
                        <SkipBack className="size-4" />
                        Restart
                      </Button>
                      <Button type="button" size="sm" variant="outline" onClick={() => void loadNetwork()} className="gap-2 border-white/10 bg-white/[0.04] text-slate-100 hover:bg-white/[0.08]">
                        <RefreshCw className="size-4" />
                        Refresh frame
                      </Button>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-3 sm:grid-cols-3">
                    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Frame</p>
                      <p className="mt-1 text-sm font-semibold text-white">{playbackAvailable ? `${frameIndex + 1}/${timepoints.length}` : 'Static map'}</p>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Time</p>
                      <p className="mt-1 text-sm font-semibold text-white">{playbackAvailable && currentTime !== null ? `${formatPlaybackTime(currentTime)} days` : '—'}</p>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Source</p>
                      <p className="mt-1 truncate text-sm font-semibold text-white">{playbackSourceLabel}</p>
                    </div>
                  </div>

                  <div className="mt-4">
                    <Slider
                      min={0}
                      max={Math.max(timepoints.length - 1, 0)}
                      step={1}
                      value={[playbackAvailable ? frameIndex : 0]}
                      onValueChange={([value]) => { setPlaybackIndex(value); setIsPlaying(false) }}
                      disabled={!playbackAvailable || timepoints.length < 2}
                    />
                    <div className="mt-2 flex items-center justify-between text-[11px] uppercase tracking-[0.2em] text-slate-500">
                      <span>Start</span>
                      <span>{playbackAvailable ? 'Scrub simulation time' : 'Playback locked until a simulation is available'}</span>
                      <span>End</span>
                    </div>
                  </div>

                  <div className="mt-4 flex flex-wrap gap-2">
                    <Badge variant="outline" className="border-white/10 bg-white/[0.04] text-slate-200">{playbackFluxAware ? 'Flux-aware playback' : 'Concentration playback'}</Badge>
                    <Badge variant="outline" className="border-white/10 bg-white/[0.04] text-slate-200">Circles = metabolites</Badge>
                    <Badge variant="outline" className="border-white/10 bg-white/[0.04] text-slate-200">Diamonds = reactions</Badge>
                    <Badge variant="outline" className="border-white/10 bg-white/[0.04] text-slate-200">
                      {activeSnapshot?.capturedAt ? `Captured ${new Date(activeSnapshot.capturedAt).toLocaleString()}` : 'No capture time yet'}
                    </Badge>
                    <Badge variant="outline" className="border-white/10 bg-white/[0.04] text-slate-200">{playbackAvailable ? 'Simulation replay ready' : 'Static network snapshot'}</Badge>
                  </div>
                </div>

                <div className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-3">
                  {graphNetwork ? (
                    <NetworkGraph data={graphNetwork} selectedEntity={selectedEntity} onSelectionChange={setSelectedEntity} />
                  ) : null}
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {legendItems.map((legend) => (
                    <div key={legend.label} className="flex items-center gap-1.5 text-xs text-slate-400">
                      <span className="inline-block h-0.5 w-3 rounded" style={{ background: legend.color }} />
                      {legend.label}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card className="border-white/10 bg-slate-950/70 shadow-[0_20px_60px_-34px_rgba(8,15,40,0.8)]">
              <CardHeader className="border-b border-white/10 bg-white/[0.03] px-5 py-4">
                <div className="flex items-center gap-2">
                  <span className="grid size-8 place-items-center rounded-2xl border border-white/10 bg-white/5 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-200">02</span>
                  <CardTitle className="text-white">Pathway detail</CardTitle>
                </div>
                <CardDescription className="text-slate-400">
                  {pathwayViewMode === 'compact'
                    ? 'Click a bridge node to focus its connector metabolite, or switch to full model for node-level inspection.'
                    : 'Click a metabolite circle, reaction diamond, or edge to inspect the selected entity. The graph stays the scientific focus.'}
                </CardDescription>
              </CardHeader>

              <CardContent className="space-y-4 px-5 py-4">
                <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-cyan-200/75">Selected entity</p>
                      <p className="text-sm font-semibold text-white">
                        {selectedEntityDetails ? selectedEntityDetails.label : 'Nothing selected yet'}
                      </p>
                    </div>
                    {selectedEntityDetails ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => setSelectedEntity(null)}
                        className="rounded-full px-3 text-xs text-slate-300 hover:bg-white/[0.06] hover:text-white"
                      >
                        Clear
                      </Button>
                    ) : (
                      <Badge variant="outline" className="rounded-full border-white/10 bg-white/[0.04] text-slate-300">
                        Click graph
                      </Badge>
                    )}
                  </div>

                  {selectedEntityDetails ? (
                    <div className="mt-3 grid gap-3 sm:grid-cols-2">
                      <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-3">
                        <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Type</p>
                        <p className="mt-1 text-sm font-semibold text-white capitalize">{selectedEntityDetails.kind}</p>
                      </div>
                      <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-3">
                        <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Pathway</p>
                        <p className="mt-1 text-sm font-semibold text-white">{selectedEntityDetails.pathway}</p>
                      </div>
                      {selectedEntityDetails.kind === 'metabolite' ? (
                        <>
                          <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-3">
                            <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Concentration</p>
                            <p className="mt-1 text-sm font-semibold text-white">
                              {formatScientificValue(selectedEntityDetails.concentration)} mM
                            </p>
                          </div>
                          <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-3">
                            <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Compartment</p>
                            <p className="mt-1 text-sm font-semibold text-white">{selectedEntityDetails.source}</p>
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-3">
                            <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Flux</p>
                            <p className="mt-1 text-sm font-semibold text-white">
                              {formatScientificValue(selectedEntityDetails.flux)}
                            </p>
                          </div>
                          <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-3">
                            <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Reaction</p>
                            <p className="mt-1 text-sm font-semibold text-white">
                              {selectedEntityDetails.source} → {selectedEntityDetails.target}
                            </p>
                          </div>
                        </>
                      )}
                    </div>
                  ) : (
                    <p className="mt-3 text-sm leading-6 text-slate-400">
                      Choose a node or reaction to see a compact scientific readout here. The selected entity will be mirrored in RoBoCop as part of the same Pathway context.
                    </p>
                  )}

                  {selectedEntityDetails?.summary ? (
                    <p className="mt-3 text-sm leading-6 text-slate-300">{selectedEntityDetails.summary}</p>
                  ) : null}
                </div>

                <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Quick select</p>
                      <p className="mt-1 text-sm text-slate-300">Pick a visible metabolite or reaction to highlight it in the graph.</p>
                    </div>
                    <Badge variant="outline" className="rounded-full border-white/10 bg-white/[0.04] text-slate-200">
                      {featuredMetabolites.length + featuredReactions.length} targets
                    </Badge>
                  </div>

                  <div className="mt-3 space-y-3">
                    <div className="space-y-2">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-500">Metabolites</p>
                      <div className="flex flex-wrap gap-2">
                        {featuredMetabolites.map((node) => {
                          const label = node.label ?? node.id
                          const active = selectedEntity?.kind === 'metabolite' && selectedEntity.id === node.id
                          return (
                            <SelectionChip
                              key={node.id}
                              label={label}
                              active={active}
                              onClick={() =>
                                setSelectedEntity({
                                  kind: 'metabolite',
                                  id: node.id,
                                  label,
                                  pathway: node.pathway ?? null,
                                  summary: `${label} • ${node.pathway ?? 'Other'}`,
                                })
                              }
                            />
                          )
                        })}
                      </div>
                    </div>

                    <div className="space-y-2">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-500">Reactions</p>
                      <div className="flex flex-wrap gap-2">
                        {featuredReactions.map((reaction) => {
                          const active = selectedEntity?.kind === 'reaction' && selectedEntity.id === reaction.id
                          return (
                            <SelectionChip
                              key={reaction.id}
                              label={reaction.label}
                              active={active}
                              onClick={() =>
                                setSelectedEntity({
                                  kind: 'reaction',
                                  id: reaction.id,
                                  label: reaction.label,
                                  pathway: reaction.pathway ?? null,
                                  summary: `${reaction.label} • ${reaction.source} → ${reaction.target}`,
                                })
                              }
                            />
                          )
                        })}
                      </div>
                    </div>
                  </div>
                </div>

                {pathwayViewMode === 'compact' ? (
                  <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Compact bridge atlas</p>
                        <p className="mt-1 text-sm text-slate-300">One connector metabolite per pathway group</p>
                      </div>
                      <Badge variant="outline" className="rounded-full border-white/10 bg-white/[0.04] text-slate-200">
                        {compactOverview.length} groups
                      </Badge>
                    </div>

                    <div className="mt-3 max-h-[640px] space-y-3 overflow-y-auto pr-1">
                      {compactOverview.map((item) => {
                        const selected =
                          (selectedEntity?.kind === 'metabolite' && selectedEntity.id === item.connectorMetabolite) ||
                          selectedEntity?.pathway === item.pathway

                        return (
                          <CompactOverviewCard
                            key={item.pathway}
                            item={item}
                            selected={selected}
                            onSelect={() => {
                              if (!item.connectorMetabolite) return
                              setSelectedEntity({
                                kind: 'metabolite',
                                id: item.connectorMetabolite,
                                label: item.connectorMetabolite,
                                pathway: item.pathway,
                                summary: item.bridgeSummary,
                              })
                            }}
                          />
                        )
                      })}
                    </div>

                    {compactOverview.length === 0 ? (
                      <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] px-4 py-6 text-sm text-slate-400">
                        No compact pathway graph is available for the current registry snapshot.
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">Pathway groups</p>
                        <p className="mt-1 text-sm text-slate-300">Ranked by node count</p>
                      </div>
                      <Badge variant="outline" className="rounded-full border-white/10 bg-white/[0.04] text-slate-200">
                        {ranks.length} groups
                      </Badge>
                    </div>

                    <div className="mt-3 space-y-3">
                      {ranks.slice(0, 5).map((entry, index) => (
                        <div
                          key={entry.pathway}
                          className={`flex items-center justify-between gap-3 rounded-2xl border px-4 py-3 ${
                            index === 0 ? 'border-cyan-400/20 bg-cyan-400/10' : 'border-white/10 bg-slate-950/55'
                          }`}
                        >
                          <div>
                            <p className="text-sm font-medium text-white">{entry.pathway}</p>
                            <p className="text-xs text-slate-400">{entry.count} nodes represented</p>
                          </div>
                          <Badge
                            variant="outline"
                            className={`rounded-full ${
                              index === 0 ? 'border-cyan-400/20 bg-cyan-400/10 text-cyan-100' : 'border-white/10 bg-white/[0.04] text-slate-200'
                            }`}
                          >
                            {index === 0 ? 'Top group' : `#${index + 1}`}
                          </Badge>
                        </div>
                      ))}
                    </div>

                    {ranks.length === 0 && (
                      <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] px-4 py-6 text-sm text-slate-400">
                        No pathway groups were detected in the current snapshot.
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        ) : (
          <Card className="border-dashed border-white/10 bg-slate-950/50">
            <CardContent className="flex flex-col items-center justify-center gap-3 py-16 text-center">
              <Sparkles className="h-6 w-6 text-cyan-300" />
              <p className="text-sm font-medium text-white">No pathway snapshot yet</p>
              <p className="max-w-md text-sm leading-6 text-slate-400">
                Refresh the network to populate the map and unlock the assistant-ready provenance snapshot.
              </p>
            </CardContent>
          </Card>
        )}
      </section>
    </div>
  )
}
