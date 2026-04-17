'use client'

const PATHWAY_GROUPS: Record<string, string[]> = {
  'Glycolysis': ['VHK', 'VPGI', 'VPFK', 'VFDPA', 'VTPI', 'VGAPDH', 'VPGK', 'VPGM', 'VENOPGM', 'VPK', 'VLDH'],
  'Pentose Phosphate': ['VG6PDH', 'VPGLS', 'V6PGD', 'VR5PI', 'VR5PE', 'VTKL1', 'VTKL2', 'VTAL'],
  '2,3-BPG Shunt': ['VDPGM', 'V23DPGP'],
  'Transport': ['VEGLC', 'VELAC', 'VEPYR'],
  'Glutathione': ['VGSR', 'VGPX', 'VGLUCYS', 'VGSS'],
  'Nucleotide': ['VAK', 'VAPRT', 'VADA', 'VAMPD1', 'VPRPPASE'],
  'Amino Acid': ['VGLNS', 'VGDH', 'VASPTA', 'VALATA'],
}

const PATHWAY_COLORS: Record<string, string> = {
  'Glycolysis': '#e74c3c',
  'Pentose Phosphate': '#9b59b6',
  '2,3-BPG Shunt': '#f39c12',
  'Transport': '#3498db',
  'Glutathione': '#2ecc71',
  'Nucleotide': '#1abc9c',
  'Amino Acid': '#34495e',
}

export { PATHWAY_GROUPS, PATHWAY_COLORS }

export function FluxBarChart({ fluxes, pathway }: { fluxes: Record<string, number>; pathway: string }) {
  const reactions = PATHWAY_GROUPS[pathway] || []
  const data = reactions.map((rxn) => ({ rxn, flux: fluxes[rxn] ?? 0 })).filter((d) => d.flux !== 0)
  if (data.length === 0) return null

  const maxAbs = Math.max(...data.map((d) => Math.abs(d.flux)), 1)
  const color = PATHWAY_COLORS[pathway] || '#64748b'
  const barH = 24, gap = 4
  const H = data.length * (barH + gap) + 8
  const labelW = 82, chartW = 380, W = labelW + chartW + 64
  const cx = labelW + chartW / 2

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: Math.min(H, 300), fontFamily: 'var(--font-sans, Inter, sans-serif)' }}>
      <line x1={cx} y1={0} x2={cx} y2={H} stroke="currentColor" strokeOpacity={0.08} strokeWidth={1} />
      {data.map((d, i) => {
        const y = 4 + i * (barH + gap)
        const barW = (Math.abs(d.flux) / maxAbs) * (chartW / 2)
        const isNeg = d.flux < 0
        return (
          <g key={d.rxn}>
            <text x={labelW - 6} y={y + barH / 2 + 4} textAnchor="end" fontSize={10} fill="currentColor" fillOpacity={0.6} fontFamily="var(--font-mono, monospace)">
              {d.rxn}
            </text>
            <rect x={isNeg ? cx - barW : cx} y={y} width={barW} height={barH} rx={4} fill={color} fillOpacity={isNeg ? 0.45 : 0.75} />
            <text x={isNeg ? cx - barW - 5 : cx + barW + 5} y={y + barH / 2 + 4} textAnchor={isNeg ? 'end' : 'start'} fontSize={9} fill="currentColor" fillOpacity={0.5}>
              {d.flux.toFixed(1)}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
