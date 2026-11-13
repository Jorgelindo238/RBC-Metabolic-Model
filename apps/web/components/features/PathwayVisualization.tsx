'use client'

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { apiClient } from '@/lib/api-client'
import { useResearchContext } from '@/contexts/ResearchContextProvider'
import { useResearchDataset } from '@/contexts/ResearchDatasetProvider'
import { useLatestResearchSimulationSnapshot } from '@/lib/research-simulation'
import { buildPathwayVisualizationResearchContext } from '@/lib/robocop/research-context-builders'
import {
  getCalibrationStatusLabel,
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
  const compactNodes = compactOverview.map((item, index) => {
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
      x: 5 * Math.cos((2 * Math.PI * index) / compactOverview.length - Math.PI / 2),
      y: 5 * Math.sin((2 * Math.PI * index) / compactOverview.length - Math.PI / 2),
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
  const [pathwayViewMode, setPathwayViewMode] = useState<'compact' | 'full'>('compact')
  const handleGraphSelection = useCallback((selection: PathwayVisualizationSelection | null) => {
    setSelectedEntity(selection)
    const inspector = document.getElementById('time-navigation')
    if (selection && inspector instanceof HTMLDetailsElement) inspector.open = true
  }, [])
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

  const nodeCount = pathwayContext.outputs.networkStats.nodes
  const reactionCount = graphNetwork?.reactionNodes?.length ?? graphNetwork?.edges.length ?? 0
  const datasetLabel = activeDatasetSummary.label
  const calibrationStatusLabel = getCalibrationStatusLabel(pathwayContext)
  const pathwayStatusLabel = getPathwayVisualizationStatusLabel(pathwayContext)
  const pathwayStatusLine = getPathwayVisualizationStatusLine(pathwayContext)
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
  const explorerHeading = pathwayViewMode === 'compact' ? 'RBC compact graph' : 'RBC metabolic map'

  return (
    <div className="grid w-full gap-6">
      <div className="research-toolbar">
        <Button type="button" variant="outline" onClick={() => void loadNetwork()} className="gap-2">
          {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
          {loading ? 'Refreshing...' : 'Refresh network'}
        </Button>
        <span className="research-muted" role="status">{pathwayStatusLabel}</span>
        <span className="research-muted">{formatCount(nodeCount)} {pathwayViewMode === 'compact' ? 'connectors' : 'metabolites'} / {formatCount(reactionCount)} {pathwayViewMode === 'compact' ? 'bridges' : 'reactions'}</span>
      </div>
      <details id="pathway-story" className="research-disclosure">
        <summary>Provenance</summary>
        <dl className="research-review">
          <div><dt>Dataset</dt><dd>{datasetLabel}</dd></div>
          <div><dt>Calibration</dt><dd>{calibrationStatusLabel}</dd></div>
          <div><dt>Playback source</dt><dd>{playbackSourceLabel}</dd></div>
          <div><dt>Network</dt><dd>{pathwayStatusLine}</dd></div>
        </dl>
      </details>

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

      <section id="network-state" className="research-section space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="space-y-1">
            <h2 className="section-heading">{explorerHeading}</h2>
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
          <div className="grid gap-4">
            <div className="research-network-panel">
              <div className="research-toolbar">
                <div className="research-filter-group" role="group" aria-label="Network view">
                  <button type="button" aria-pressed={pathwayViewMode === 'compact'} onClick={() => setPathwayViewMode('compact')}>Compact graph</button>
                  <button type="button" aria-pressed={pathwayViewMode === 'full'} onClick={() => setPathwayViewMode('full')}>Full model map</button>
                </div>
                <span className="research-muted">{playbackAvailable && currentTime !== null ? `Day ${formatPlaybackTime(currentTime)} / frame ${frameIndex + 1}` : 'Static network'}</span>
                <Button type="button" size="icon" variant="outline" title={isPlaying ? 'Pause playback' : 'Play playback'}
                  aria-label={isPlaying ? 'Pause playback' : 'Play playback'} disabled={!playbackAvailable}
                  onClick={() => {
                    if (!playbackAvailable) return
                    if (isPlaying) { setIsPlaying(false); return }
                    setPlaybackIndex((current) => current >= timepoints.length - 1 ? 0 : current)
                    setIsPlaying(true)
                  }}>
                  {isPlaying ? <Pause size={16} /> : <Play size={16} />}
                </Button>
                <Button type="button" size="icon" variant="ghost" title="Restart playback" aria-label="Restart playback"
                  disabled={!playbackAvailable} onClick={() => { setPlaybackIndex(0); setIsPlaying(false) }}><SkipBack size={16} /></Button>
              </div>
              {playbackAvailable ? <Slider aria-label="Simulation frame" min={0} max={Math.max(timepoints.length - 1, 0)} step={1}
                value={[frameIndex]} onValueChange={([value]) => { setPlaybackIndex(value); setIsPlaying(false) }}
                disabled={timepoints.length < 2} /> : null}
              {graphNetwork ? <NetworkGraph data={graphNetwork} selectedEntity={selectedEntity}
                showReactionLabels={pathwayViewMode === 'full'} onSelectionChange={handleGraphSelection} /> : null}
              <div className="flex flex-wrap gap-x-4 gap-y-2">
                {legendItems.map((legend) => <div key={legend.label} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span className="inline-block h-0.5 w-3" style={{ background: legend.color }} />{legend.label}
                </div>)}
              </div>
            </div>

            <details id="time-navigation" className="research-disclosure">
              <summary>Selection & details</summary>
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
            </details>
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
        {!network ? <details id="time-navigation" className="research-disclosure"><summary>Selection & details</summary><p className="research-empty">No network state available</p></details> : null}
      </section>
    </div>
  )
}
