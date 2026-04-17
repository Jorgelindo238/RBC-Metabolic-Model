export interface PathwayNetworkNode {
  id: string
  label?: string
  pathway?: string
  x: number
  y: number
  compartment?: string
  concentration?: number
  size?: number
  color?: string
}

export interface PathwayNetworkEdge {
  source: string
  target: string
  enzyme: string
  reversible: boolean
  color: string
  pathway?: string
  flux?: number | null
}

export interface PathwayNetworkReactionNode {
  id: string
  label: string
  enzyme: string
  source: string
  target: string
  reversible: boolean
  pathway?: string
  x: number
  y: number
  size?: number
  color?: string
  flux?: number | null
}

export interface PathwayNetworkLegendItem {
  label: string
  color: string
}

export interface PathwayCompactOverviewItem {
  pathway: string
  color: string
  nodeCount: number
  connectorMetabolite: string | null
  bridgePathways: string[]
  bridgeSummary: string
  topMetabolites: string[]
}

export interface PathwayNetworkStats {
  nodes: number
  edges: number
  reactions: number
  pathways: number
}

export interface PathwayNetworkState {
  registryVersion: string
  sourceOfTruth: string
  title: string
  legend: PathwayNetworkLegendItem[]
  stats: PathwayNetworkStats
  dominantPathway?: string | null
  pathwayGroups: Record<string, string[]>
  compactOverview?: PathwayCompactOverviewItem[]
  nodes: PathwayNetworkNode[]
  edges: PathwayNetworkEdge[]
  reactionNodes?: PathwayNetworkReactionNode[]
}
