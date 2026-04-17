'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { Minus, Plus, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { PathwayVisualizationSelection } from '@/types/research-context'
import type { PathwayNetworkReactionNode, PathwayNetworkState } from '@/types/pathway-network'

interface NetworkGraphProps {
  data: PathwayNetworkState
  selectedEntity?: PathwayVisualizationSelection | null
  onSelectionChange?: (selection: PathwayVisualizationSelection | null) => void
}

interface SelectionModel {
  selectedReactionIndex: number | null
  selectedNodeId: string | null
  connectedNodeIds: Set<string>
  connectedEdgeIndexes: Set<number>
  connectedReactionIndexes: Set<number>
}

type PlotlySelectionPayload = [kind: 'metabolite' | 'reaction', id: string, label: string, pathway: string | null, summary: string]

function buildSelectionFromCustomData(customData: unknown): PathwayVisualizationSelection | null {
  if (!Array.isArray(customData) || customData.length < 5) {
    return null
  }

  const [kind, id, label, pathway, summary] = customData as PlotlySelectionPayload
  if (kind !== 'metabolite' && kind !== 'reaction') {
    return null
  }

  return {
    kind,
    id,
    label,
    pathway,
    summary,
  }
}

function buildNodeLookup(data: PathwayNetworkState) {
  return new Map(data.nodes.map((node) => [node.id, node]))
}

function buildReactionNodes(data: PathwayNetworkState) {
  const nodeLookup = buildNodeLookup(data)
  const fallbackReactionNodes = data.edges
    .map((edge, index) => {
      const source = nodeLookup.get(edge.source)
      const target = nodeLookup.get(edge.target)
      if (!source || !target) {
        return null
      }

      const flux = typeof edge.flux === 'number' ? edge.flux : null
      const magnitude = flux === null ? 0 : Math.abs(flux)

      return {
        id: `reaction::${edge.enzyme}:${edge.source}:${edge.target}:${index}`,
        label: edge.enzyme.replace(/\+/g, ' + '),
        enzyme: edge.enzyme,
        source: edge.source,
        target: edge.target,
        reversible: edge.reversible,
        pathway: edge.pathway ?? undefined,
        x: (source.x + target.x) / 2,
        y: (source.y + target.y) / 2,
        size: 12 + Math.min(magnitude / 20, 8),
        color: edge.color,
        flux,
      } satisfies PathwayNetworkReactionNode
    })
    .filter(Boolean) as PathwayNetworkReactionNode[]

  return data.reactionNodes?.length ? data.reactionNodes : fallbackReactionNodes
}

function buildArrowAnnotations(data: PathwayNetworkState, reactionNodes: PathwayNetworkReactionNode[]) {
  const nodeLookup = buildNodeLookup(data)

  return reactionNodes
    .map((reaction) => {
      if (reaction.reversible) {
        return null
      }

      const source = nodeLookup.get(reaction.source)
      const target = nodeLookup.get(reaction.target)
      if (!source || !target) {
        return null
      }

      const x = reaction.x + (target.x - reaction.x) * 0.42
      const y = reaction.y + (target.y - reaction.y) * 0.42

      return {
        x,
        y,
        ax: x - (target.x - reaction.x) * 0.16,
        ay: y - (target.y - reaction.y) * 0.16,
        xref: 'x',
        yref: 'y',
        axref: 'x',
        ayref: 'y',
        text: '',
        showarrow: true,
        arrowhead: 2,
        arrowsize: 1,
        arrowwidth: 1.3,
        arrowcolor: reaction.color ?? '#94a3b8',
        opacity: 0.85,
      }
    })
    .filter(Boolean)
}

function buildSelectionModel(
  data: PathwayNetworkState,
  reactionNodes: PathwayNetworkReactionNode[],
  selectedEntity?: PathwayVisualizationSelection | null
): SelectionModel {
  const connectedNodeIds = new Set<string>()
  const connectedEdgeIndexes = new Set<number>()
  const connectedReactionIndexes = new Set<number>()
  let selectedReactionIndex: number | null = null
  let selectedNodeId: string | null = null

  if (!selectedEntity) {
    return {
      selectedReactionIndex,
      selectedNodeId,
      connectedNodeIds,
      connectedEdgeIndexes,
      connectedReactionIndexes,
    }
  }

  if (selectedEntity.kind === 'reaction') {
    selectedReactionIndex = reactionNodes.findIndex((reaction) => reaction.id === selectedEntity.id)
    if (selectedReactionIndex !== -1) {
      const reaction = reactionNodes[selectedReactionIndex]
      if (reaction) {
        connectedReactionIndexes.add(selectedReactionIndex)
        connectedEdgeIndexes.add(selectedReactionIndex)
        connectedNodeIds.add(reaction.source)
        connectedNodeIds.add(reaction.target)
      }
    }
  } else {
    selectedNodeId = selectedEntity.id
    connectedNodeIds.add(selectedEntity.id)
    data.edges.forEach((edge, index) => {
      if (edge.source === selectedEntity.id || edge.target === selectedEntity.id) {
        connectedEdgeIndexes.add(index)
        connectedReactionIndexes.add(index)
        connectedNodeIds.add(edge.source)
        connectedNodeIds.add(edge.target)
      }
    })
  }

  return {
    selectedReactionIndex,
    selectedNodeId,
    connectedNodeIds,
    connectedEdgeIndexes,
    connectedReactionIndexes,
  }
}

function buildMetaboliteLabelPosition(node: { x: number; y: number }, xCenter: number, yCenter: number) {
  const xOffset = node.x >= xCenter ? 0.16 : -0.16
  const yOffset = node.y >= yCenter ? 0.14 : -0.14
  return {
    x: node.x + xOffset,
    y: node.y + yOffset,
  }
}

function buildReactionLabelPosition(reaction: PathwayNetworkReactionNode, index: number, xCenter: number, yCenter: number) {
  const source = reaction.source
  const target = reaction.target
  void source
  void target
  const dx = reaction.x - xCenter
  const dy = reaction.y - yCenter
  const len = Math.hypot(dx, dy) || 1
  const perpX = -dy / len
  const perpY = dx / len
  const sign = index % 2 === 0 ? 1 : -1
  const magnitude = 0.18 + Math.min(Math.abs(reaction.flux ?? 0) / 150, 0.08)

  return {
    x: reaction.x + perpX * magnitude * sign,
    y: reaction.y + perpY * magnitude * sign,
  }
}

export function NetworkGraph({ data, selectedEntity, onSelectionChange }: NetworkGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [zoomLevel, setZoomLevel] = useState(1)

  const nodeLookup = useMemo(() => buildNodeLookup(data), [data])
  const reactionNodes = useMemo(() => buildReactionNodes(data), [data])
  const selectionModel = useMemo(
    () => buildSelectionModel(data, reactionNodes, selectedEntity),
    [data, reactionNodes, selectedEntity]
  )
  const bounds = useMemo(() => {
    const xs = [...data.nodes.map((node) => node.x), ...reactionNodes.map((node) => node.x)]
    const ys = [...data.nodes.map((node) => node.y), ...reactionNodes.map((node) => node.y)]
    const xMin = Math.min(...xs) - 1
    const xMax = Math.max(...xs) + 1
    const yMin = Math.min(...ys) - 1
    const yMax = Math.max(...ys) + 1
    const xCenter = (xMin + xMax) / 2
    const yCenter = (yMin + yMax) / 2

    return { xMin, xMax, yMin, yMax, xCenter, yCenter }
  }, [data.nodes, reactionNodes])

  const traces = useMemo(() => {
    const edgeTraces = data.edges.map((edge, index) => {
      const source = nodeLookup.get(edge.source)
      const target = nodeLookup.get(edge.target)
      const flux = typeof edge.flux === 'number' ? edge.flux : null
      const fluxMagnitude = flux === null ? 0 : Math.abs(flux)
      const isConnected = selectionModel.connectedEdgeIndexes.has(index)
      const edgeOpacity = selectedEntity ? (isConnected ? 0.9 : 0.12) : flux !== null ? Math.min(0.9, 0.35 + Math.min(fluxMagnitude / 10, 0.55)) : 0.55
      const edgeWidth = selectedEntity ? (isConnected ? 3.2 : 1.1) : flux !== null ? 1.6 + Math.min(fluxMagnitude / 20, 4) : 1.75

      return {
        x: [source?.x ?? null, target?.x ?? null],
        y: [source?.y ?? null, target?.y ?? null],
        type: 'scatter',
        mode: 'lines',
        hoverinfo: 'text',
        text: `${edge.enzyme}<br>${edge.source} → ${edge.target}${flux !== null ? `<br>Flux: ${flux.toExponential(2)}` : ''}`,
        line: {
          color: edge.color,
          width: edgeWidth,
        },
        opacity: edgeOpacity,
        showlegend: false,
      }
    })

    const reactionMarkerTrace = {
      x: reactionNodes.map((node) => node.x),
      y: reactionNodes.map((node) => node.y),
      type: 'scatter',
      mode: 'markers',
      hoverinfo: 'text',
      customdata: reactionNodes.map((node) => [
        'reaction',
        node.id,
        node.label,
        node.pathway ?? null,
        `${node.label} • ${node.source} → ${node.target}`,
      ] satisfies PlotlySelectionPayload),
      text: reactionNodes.map((node) => {
        const flux = typeof node.flux === 'number' ? `${node.flux >= 0 ? '+' : ''}${node.flux.toExponential(2)}` : '—'
        return `${node.label}<br>Source: ${node.source} → ${node.target}<br>Pathway: ${node.pathway ?? 'Other'}<br>Flux: ${flux}`
      }),
      marker: {
        size: reactionNodes.map((node, index) => {
          const selected = selectedEntity?.kind === 'reaction' && selectionModel.selectedReactionIndex === index
          const connected = selectedEntity ? selectionModel.connectedReactionIndexes.has(index) : false
          const base = node.size ?? 12
          return selected ? base * 1.55 : connected ? base * 1.18 : base
        }),
        color: reactionNodes.map((node, index) => {
          const selected = selectedEntity?.kind === 'reaction' && selectionModel.selectedReactionIndex === index
          return selected ? '#f8fafc' : node.color ?? '#64748b'
        }),
        symbol: 'diamond',
        line: {
          color: 'rgba(255,255,255,0.95)',
          width: 1.4,
        },
      },
      showlegend: false,
    }

    const reactionHitboxTrace = {
      x: reactionNodes.map((node) => node.x),
      y: reactionNodes.map((node) => node.y),
      type: 'scatter',
      mode: 'markers',
      hoverinfo: 'skip',
      customdata: reactionNodes.map((node) => [
        'reaction',
        node.id,
        node.label,
        node.pathway ?? null,
        `${node.label} • ${node.source} → ${node.target}`,
      ] satisfies PlotlySelectionPayload),
      marker: {
        size: reactionNodes.map((node) => Math.max((node.size ?? 12) * 2.1, 24)),
        color: 'rgba(255,255,255,0.001)',
        line: {
          color: 'rgba(255,255,255,0.001)',
          width: 0,
        },
      },
      opacity: 0.01,
      showlegend: false,
    }

    const reactionLabelTrace = {
      x: reactionNodes.map((node, index) => buildReactionLabelPosition(node, index, bounds.xCenter, bounds.yCenter).x),
      y: reactionNodes.map((node, index) => buildReactionLabelPosition(node, index, bounds.xCenter, bounds.yCenter).y),
      type: 'scatter',
      mode: 'text',
      customdata: reactionNodes.map((node) => [
        'reaction',
        node.id,
        node.label,
        node.pathway ?? null,
        `${node.label} • ${node.source} → ${node.target}`,
      ] satisfies PlotlySelectionPayload),
      text: reactionNodes.map((node) => node.label),
      textposition: 'middle center',
      hoverinfo: 'skip',
      textfont: {
        size: 9,
        color: 'rgba(255,255,255,0.95)',
        family: 'Arial, sans-serif',
      },
      opacity: selectedEntity ? 0.72 : 0.9,
      cliponaxis: false,
      showlegend: false,
    }

    const metaboliteMarkerTrace = {
      x: data.nodes.map((node) => node.x),
      y: data.nodes.map((node) => node.y),
      type: 'scatter',
      mode: 'markers',
      hoverinfo: 'text',
      customdata: data.nodes.map((node) => [
        'metabolite',
        node.id,
        node.label ?? node.id,
        node.pathway ?? null,
        `${node.label ?? node.id} • ${node.pathway ?? 'Other'}`,
      ] satisfies PlotlySelectionPayload),
      text: data.nodes.map((node) => {
        const concentration = typeof node.concentration === 'number' ? node.concentration.toFixed(3) : '—'
        const pathway = node.pathway ?? 'Other'
        return `${node.label ?? node.id}<br>Pathway: ${pathway}<br>Conc: ${concentration} mM`
      }),
      marker: {
        size: data.nodes.map((node) => {
          const selected = selectedEntity?.kind === 'metabolite' && selectionModel.selectedNodeId === node.id
          const connected = selectedEntity ? selectionModel.connectedNodeIds.has(node.id) : false
          const base = node.size ?? 16
          return selected ? base * 1.42 : connected ? base * 1.12 : base
        }),
        color: data.nodes.map((node) => {
          const selected = selectedEntity?.kind === 'metabolite' && selectionModel.selectedNodeId === node.id
          return selected ? '#ffffff' : node.color ?? '#3498db'
        }),
        line: {
          color: 'rgba(255,255,255,0.9)',
          width: 2,
        },
      },
      showlegend: false,
    }

    const metaboliteHitboxTrace = {
      x: data.nodes.map((node) => node.x),
      y: data.nodes.map((node) => node.y),
      type: 'scatter',
      mode: 'markers',
      hoverinfo: 'skip',
      customdata: data.nodes.map((node) => [
        'metabolite',
        node.id,
        node.label ?? node.id,
        node.pathway ?? null,
        `${node.label ?? node.id} • ${node.pathway ?? 'Other'}`,
      ] satisfies PlotlySelectionPayload),
      marker: {
        size: data.nodes.map((node) => Math.max((node.size ?? 16) * 1.7, 26)),
        color: 'rgba(255,255,255,0.001)',
        line: {
          color: 'rgba(255,255,255,0.001)',
          width: 0,
        },
      },
      opacity: 0.01,
      showlegend: false,
    }

    const metaboliteLabelTrace = {
      x: data.nodes.map((node) => buildMetaboliteLabelPosition(node, bounds.xCenter, bounds.yCenter).x),
      y: data.nodes.map((node) => buildMetaboliteLabelPosition(node, bounds.xCenter, bounds.yCenter).y),
      type: 'scatter',
      mode: 'text',
      customdata: data.nodes.map((node) => [
        'metabolite',
        node.id,
        node.label ?? node.id,
        node.pathway ?? null,
        `${node.label ?? node.id} • ${node.pathway ?? 'Other'}`,
      ] satisfies PlotlySelectionPayload),
      text: data.nodes.map((node) => node.label ?? node.id),
      textposition: 'middle center',
      hoverinfo: 'skip',
      textfont: {
        size: 10,
        color: 'rgba(255,255,255,0.92)',
        family: 'Arial, sans-serif',
      },
      opacity: selectedEntity ? 0.75 : 0.95,
      cliponaxis: false,
      showlegend: false,
    }

    return [
      ...edgeTraces,
      reactionHitboxTrace,
      reactionMarkerTrace,
      reactionLabelTrace,
      metaboliteHitboxTrace,
      metaboliteMarkerTrace,
      metaboliteLabelTrace,
    ]
  }, [bounds, data, nodeLookup, reactionNodes, selectedEntity, selectionModel])

  const layout = useMemo(() => {
    const xSpan = Math.max(bounds.xMax - bounds.xMin, 1)
    const ySpan = Math.max(bounds.yMax - bounds.yMin, 1)
    const zoom = Math.max(zoomLevel, 0.5)
    const xHalf = xSpan / (2 * zoom)
    const yHalf = ySpan / (2 * zoom)

    return {
      margin: { l: 18, r: 18, t: 38, b: 18 },
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'transparent',
      showlegend: false,
      hovermode: 'closest',
      dragmode: 'pan',
      xaxis: {
        range: [bounds.xCenter - xHalf, bounds.xCenter + xHalf],
        visible: false,
        zeroline: false,
        showgrid: false,
        fixedrange: false,
      },
      yaxis: {
        range: [bounds.yCenter - yHalf, bounds.yCenter + yHalf],
        visible: false,
        zeroline: false,
        showgrid: false,
        fixedrange: false,
        scaleanchor: 'x',
        scaleratio: 1,
      },
      annotations: buildArrowAnnotations(data, reactionNodes),
      autosize: true,
    } as const
  }, [bounds, data, reactionNodes, zoomLevel])

  useEffect(() => {
    let active = true
    let plotly: any = null

    const renderPlot = async () => {
      const module = await import('plotly.js-dist-min')
      const Plotly = (module as any).default ?? module
      if (!active || !containerRef.current) {
        return
      }

      plotly = Plotly
      await Plotly.react(containerRef.current, traces as any, layout as any, {
        displayModeBar: false,
        responsive: true,
        scrollZoom: true,
      })

      const gd = containerRef.current as any
      const handleClick = (event: any) => {
        const point = event?.points?.[0]
        if (!point || !onSelectionChange) {
          return
        }

        const edgeCount = data.edges.length
        const customSelection = buildSelectionFromCustomData(point.customdata)
        if (customSelection) {
          onSelectionChange(customSelection)
          return
        }

        if (point.curveNumber < edgeCount) {
          const reaction = reactionNodes[point.curveNumber]
          if (reaction) {
            onSelectionChange({
              kind: 'reaction',
              id: reaction.id,
              label: reaction.label,
              pathway: reaction.pathway ?? null,
              summary: `${reaction.label} • ${reaction.source} → ${reaction.target}`,
            })
          }
        }
      }

      gd.removeAllListeners?.('plotly_click')
      gd.on?.('plotly_click', handleClick)
    }

    void renderPlot()

    return () => {
      active = false
      if (containerRef.current && plotly) {
        try {
          plotly.purge(containerRef.current)
        } catch {
          // Ignore teardown errors during fast refresh.
        }
      }
    }
  }, [data.edges.length, data.nodes, layout, onSelectionChange, reactionNodes, traces])

  return (
    <div className="relative w-full">
      <div className="absolute right-3 top-3 z-10 flex items-center gap-1 rounded-full border border-white/10 bg-slate-950/80 p-1 shadow-lg shadow-black/30 backdrop-blur">
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => setZoomLevel((current) => Math.max(0.6, Number((current / 1.25).toFixed(3))))}
          className="h-8 rounded-full px-3 text-[10px] uppercase tracking-[0.22em] text-slate-200 hover:bg-white/[0.08] hover:text-white"
          aria-label="Zoom out"
        >
          <Minus className="mr-1.5 size-3.5" />
          Zoom out
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => setZoomLevel(1)}
          className="h-8 rounded-full px-3 text-[10px] uppercase tracking-[0.22em] text-slate-200 hover:bg-white/[0.08] hover:text-white"
          aria-label="Reset zoom"
        >
          <RotateCcw className="mr-1.5 size-3.5" />
          Reset
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => setZoomLevel((current) => Math.min(4, Number((current * 1.25).toFixed(3))))}
          className="h-8 rounded-full px-3 text-[10px] uppercase tracking-[0.22em] text-slate-200 hover:bg-white/[0.08] hover:text-white"
          aria-label="Zoom in"
        >
          <Plus className="mr-1.5 size-3.5" />
          Zoom in
        </Button>
      </div>
      <div ref={containerRef} className="min-h-[620px] w-full" />
    </div>
  )
}
