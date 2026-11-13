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
import { AlertCircle, Loader2, Network, Pause, Play, RefreshCw, SkipBack } from 'lucide-react'
import { WithInspector } from '@/components/platform/research/Inspector'
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
  const [inspectorOpen, setInspectorOpen] = useState(false)
  // A graph selection opens the shared inspector (single place for details).
  const handleGraphSelection = useCallback((selection: PathwayVisualizationSelection | null) => {
    setSelectedEntity(selection)
    if (selection) setInspectorOpen(true)
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
  const graphNodeCount = graphNetwork?.nodes?.length ?? 0

  const inspector = (
    <div className="grid gap-5" data-testid="pathway-inspector">
      <section className="grid gap-2" aria-label="Selection">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-[13px] font-semibold">Selection</h3>
          {selectedEntityDetails ? (
            <Button type="button" size="sm" variant="ghost" onClick={() => setSelectedEntity(null)}>Clear</Button>
          ) : null}
        </div>
        {selectedEntityDetails ? (
          <dl className="research-review" data-testid="pathway-selection">
            <div><dt>Name</dt><dd>{selectedEntityDetails.label}</dd></div>
            <div><dt>Type</dt><dd className="capitalize">{selectedEntityDetails.kind}</dd></div>
            <div><dt>Pathway</dt><dd>{selectedEntityDetails.pathway}</dd></div>
            {selectedEntityDetails.kind === 'metabolite' ? <>
              <div><dt>Concentration</dt><dd className="r-num" title={String(selectedEntityDetails.concentration ?? '')}>{formatScientificValue(selectedEntityDetails.concentration)} mM</dd></div>
              <div><dt>Compartment</dt><dd>{selectedEntityDetails.source}</dd></div>
            </> : <>
              <div><dt>Flux</dt><dd className="r-num" title={String(selectedEntityDetails.flux ?? '')}>{formatScientificValue(selectedEntityDetails.flux)}</dd></div>
              <div><dt>Reaction</dt><dd>{selectedEntityDetails.source} → {selectedEntityDetails.target}</dd></div>
            </>}
            {selectedEntityDetails.summary ? <div><dt>Summary</dt><dd>{selectedEntityDetails.summary}</dd></div> : null}
          </dl>
        ) : (
          <p className="research-muted">Click a node or reaction in the graph, or use quick select below.</p>
        )}
      </section>

      <section className="grid gap-2" aria-label="Quick select">
        <h3 className="text-[13px] font-semibold">Quick select</h3>
        <p className="r-legend">Metabolites</p>
        <div className="flex flex-wrap gap-2">
          {featuredMetabolites.map((node) => {
            const label = node.label ?? node.id
            return (
              <SelectionChip key={node.id} label={label}
                active={selectedEntity?.kind === 'metabolite' && selectedEntity.id === node.id}
                onClick={() => setSelectedEntity({ kind: 'metabolite', id: node.id, label, pathway: node.pathway ?? null,
                  summary: `${label} • ${node.pathway ?? 'Other'}` })} />
            )
          })}
        </div>
        <p className="r-legend">Reactions</p>
        <div className="flex flex-wrap gap-2">
          {featuredReactions.map((reaction) => (
            <SelectionChip key={reaction.id} label={reaction.label}
              active={selectedEntity?.kind === 'reaction' && selectedEntity.id === reaction.id}
              onClick={() => setSelectedEntity({ kind: 'reaction', id: reaction.id, label: reaction.label,
                pathway: reaction.pathway ?? null, summary: `${reaction.label} • ${reaction.source} → ${reaction.target}` })} />
          ))}
        </div>
      </section>

      {pathwayViewMode === 'compact' ? (
        <section className="grid gap-2" aria-label="Compact bridge atlas">
          <h3 className="text-[13px] font-semibold">Compact bridge atlas</h3>
          <p className="r-legend">One connector metabolite per pathway group; display grouping only.</p>
          <div className="grid max-h-[480px] gap-2 overflow-y-auto pr-1">
            {compactOverview.map((item) => (
              <CompactOverviewCard key={item.pathway} item={item}
                selected={(selectedEntity?.kind === 'metabolite' && selectedEntity.id === item.connectorMetabolite)
                  || selectedEntity?.pathway === item.pathway}
                onSelect={() => {
                  if (!item.connectorMetabolite) return
                  setSelectedEntity({ kind: 'metabolite', id: item.connectorMetabolite, label: item.connectorMetabolite,
                    pathway: item.pathway, summary: item.bridgeSummary })
                }} />
            ))}
          </div>
          {compactOverview.length === 0 ? <p className="research-muted">No compact grouping in the current registry snapshot.</p> : null}
        </section>
      ) : (
        <section className="grid gap-2" aria-label="Pathway groups">
          <h3 className="text-[13px] font-semibold">Pathway groups</h3>
          <ol className="grid gap-1 text-[13px]">
            {ranks.map((entry) => (
              <li key={entry.pathway} className="flex justify-between gap-3 border-b border-[color:var(--r-line)] py-1">
                <span>{entry.pathway}</span><span className="r-num research-muted">{entry.count} nodes</span>
              </li>
            ))}
          </ol>
          {ranks.length === 0 ? <p className="research-muted">No pathway groups in the current snapshot.</p> : null}
        </section>
      )}

      <section className="grid gap-2" aria-label="Provenance">
        <h3 className="text-[13px] font-semibold">Provenance</h3>
        <dl className="research-review">
          <div><dt>Dataset</dt><dd>{datasetLabel}</dd></div>
          <div><dt>Calibration</dt><dd>{calibrationStatusLabel}</dd></div>
          <div><dt>Playback source</dt><dd>{playbackAvailable ? playbackSourceLabel : 'No simulation trajectory in this session'}</dd></div>
          <div><dt>Network</dt><dd>{pathwayStatusLine}</dd></div>
          <div><dt>Layout</dt><dd>Display layout only; positions carry no kinetic meaning.</dd></div>
        </dl>
      </section>
    </div>
  )

  return (
    <WithInspector title="Pathway details" anchorId="pathway-story" inspector={inspector}
      open={inspectorOpen} onOpenChange={setInspectorOpen}>
      <div className="grid w-full gap-4" data-testid="research-pathway">
        <div className="research-toolbar">
          <Button type="button" variant="outline" onClick={() => void loadNetwork()} className="gap-2" disabled={loading}>
            {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            {loading ? 'Refreshing...' : 'Refresh network'}
          </Button>
          <span className="research-muted" role="status">{pathwayStatusLabel}</span>
          {network ? (
            <span className="research-muted r-num">
              {formatCount(nodeCount)} {pathwayViewMode === 'compact' ? 'connectors' : 'metabolites'} / {formatCount(reactionCount)} {pathwayViewMode === 'compact' ? 'bridges' : 'reactions'}
            </span>
          ) : null}
        </div>

        {error ? (
          <p role="alert" className="flex items-start gap-2 text-sm text-destructive" data-testid="pathway-error">
            <AlertCircle size={16} className="mt-0.5 shrink-0" />
            <span className="min-w-0 break-words"><strong>Pathway visualization error.</strong> {error} Use Refresh network to retry.</span>
          </p>
        ) : null}

        <section id="network-state" className="grid gap-3" aria-label="Network" aria-busy={loading}>
          <h2>{explorerHeading}</h2>
          {loading && !network ? (
            <p className="research-empty" role="status"><Loader2 size={16} className="animate-spin" />Loading pathway network...</p>
          ) : network ? (
            <div className="research-network-panel">
              <div id="time-navigation" className="research-toolbar">
                <div className="research-filter-group" role="group" aria-label="Network view">
                  <button type="button" aria-pressed={pathwayViewMode === 'compact'} onClick={() => setPathwayViewMode('compact')}>Compact graph</button>
                  <button type="button" aria-pressed={pathwayViewMode === 'full'} onClick={() => setPathwayViewMode('full')}>Full model map</button>
                </div>
                {playbackAvailable ? (
                  <>
                    <Button type="button" size="icon" variant="outline" title={isPlaying ? 'Pause playback' : 'Play playback'}
                      aria-label={isPlaying ? 'Pause playback' : 'Play playback'}
                      onClick={() => {
                        if (isPlaying) { setIsPlaying(false); return }
                        setPlaybackIndex((current) => current >= timepoints.length - 1 ? 0 : current)
                        setIsPlaying(true)
                      }}>
                      {isPlaying ? <Pause size={16} /> : <Play size={16} />}
                    </Button>
                    <Button type="button" size="icon" variant="ghost" title="Restart playback" aria-label="Restart playback"
                      onClick={() => { setPlaybackIndex(0); setIsPlaying(false) }}><SkipBack size={16} /></Button>
                    <span className="research-muted r-num">Day {formatPlaybackTime(currentTime)} / frame {frameIndex + 1} of {timepoints.length}</span>
                  </>
                ) : null}
              </div>
              {playbackAvailable ? <Slider aria-label="Simulation frame" min={0} max={Math.max(timepoints.length - 1, 0)} step={1}
                value={[frameIndex]} onValueChange={([value]) => { setPlaybackIndex(value); setIsPlaying(false) }}
                disabled={timepoints.length < 2} /> : null}
              <p className="r-legend" data-testid="pathway-mode-note">
                {playbackAvailable
                  ? `Playback of the latest simulation trajectory${playbackFluxAware ? ' with its fluxes' : ''}.`
                  : 'Static network: no simulation trajectory in this session, so there is no playback.'}
                {pathwayViewMode === 'compact'
                  ? ' Compact view: connectors and bridges are display-only groupings, not kinetic reactions.'
                  : ' Full view: model metabolites and reactions as returned by the pathway registry.'}
              </p>
              {graphNetwork && graphNodeCount > 0 ? (
                <NetworkGraph data={graphNetwork} selectedEntity={selectedEntity}
                  showReactionLabels={pathwayViewMode === 'full'} onSelectionChange={handleGraphSelection} />
              ) : (
                <p className="research-empty" data-testid="pathway-graph-empty">
                  No nodes are available for the {pathwayViewMode === 'compact' ? 'compact' : 'full'} view of this snapshot.
                </p>
              )}
              <ul className="flex flex-wrap gap-x-4 gap-y-2" aria-label="Pathway colours">
                {legendItems.map((legend) => <li key={legend.label} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span className="inline-block h-0.5 w-3" style={{ background: legend.color }} aria-hidden="true" />{legend.label}
                </li>)}
              </ul>
            </div>
          ) : !error ? (
            <p className="research-empty" data-testid="pathway-empty">No pathway snapshot yet. Use Refresh network.</p>
          ) : null}
        </section>
      </div>
    </WithInspector>
  )
}
