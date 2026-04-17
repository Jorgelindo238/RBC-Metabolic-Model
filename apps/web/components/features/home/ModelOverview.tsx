'use client'

import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

const PATHWAYS = [
  { name: 'Glycolysis', reactions: 11, color: '#e74c3c', pct: 85 },
  { name: 'Pentose Phosphate', reactions: 8, color: '#9b59b6', pct: 62 },
  { name: '2,3-BPG Shunt', reactions: 2, color: '#f39c12', pct: 25 },
  { name: 'Glutathione', reactions: 4, color: '#2ecc71', pct: 40 },
  { name: 'Nucleotide', reactions: 5, color: '#1abc9c', pct: 48 },
  { name: 'Transport', reactions: 3, color: '#3498db', pct: 35 },
  { name: 'Amino Acid', reactions: 4, color: '#34495e', pct: 38 },
]

const KEY_METABOLITES = [
  { name: 'GLC', desc: 'Glucose', trend: 'decline' },
  { name: 'LAC', desc: 'Lactate', trend: 'rise' },
  { name: 'ATP', desc: 'Energy currency', trend: 'decline' },
  { name: 'B23PG', desc: '2,3-BPG', trend: 'decline' },
  { name: 'GSH', desc: 'Glutathione', trend: 'decline' },
  { name: 'NADH', desc: 'Redox cofactor', trend: 'stable' },
]

export function ModelOverview() {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Pathway Coverage</CardTitle>
          <CardDescription>Major RBC metabolic subsystems in the model.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2.5">
          {PATHWAYS.map((p) => (
            <div key={p.name} className="flex items-center gap-3">
              <span className="w-[7rem] text-xs font-medium text-muted-foreground truncate">{p.name}</span>
              <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                <div className="h-full rounded-full" style={{ width: `${p.pct}%`, background: p.color, opacity: 0.7 }} />
              </div>
              <Badge variant="secondary" className="font-mono text-[10px] w-6 justify-center">{p.reactions}</Badge>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Key Storage Metabolites</CardTitle>
          <CardDescription>Primary indicators tracked during RBC storage.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-2">
            {KEY_METABOLITES.map((m) => (
              <div key={m.name} className="flex items-center gap-2.5 rounded-lg border border-border/50 bg-muted/30 p-2.5">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                  <span className="text-xs font-bold text-primary">{m.name}</span>
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-medium text-foreground">{m.desc}</p>
                  <p className="text-[10px] text-muted-foreground">
                    {m.trend === 'decline' ? '↓ Declines during storage' : m.trend === 'rise' ? '↑ Accumulates during storage' : '~ Relatively stable'}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
