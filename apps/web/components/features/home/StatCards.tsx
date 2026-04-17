'use client'

import { Card, CardContent } from '@/components/ui/card'
import { FlaskConical, Database, Map, Clock, Beaker, GitBranch } from 'lucide-react'

const STATS = [
  { label: 'Metabolites', value: '113', sub: 'Base state variables', icon: Beaker, color: 'from-blue-600/80 to-blue-800/80', iconBg: 'bg-blue-500/20' },
  { label: 'Reactions', value: '~200', sub: 'Enzyme-catalyzed', icon: GitBranch, color: 'from-emerald-600/80 to-emerald-800/80', iconBg: 'bg-emerald-500/20' },
  { label: 'Storage Horizon', value: '42', sub: 'Days maximum', icon: Clock, color: 'from-amber-600/80 to-amber-800/80', iconBg: 'bg-amber-500/20' },
  { label: 'Pathways', value: '8', sub: 'Metabolic subsystems', icon: Map, color: 'from-rose-600/80 to-rose-800/80', iconBg: 'bg-rose-500/20' },
]

export function StatCards() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {STATS.map((stat) => {
        const Icon = stat.icon
        return (
          <Card key={stat.label} className={`relative overflow-hidden bg-gradient-to-br ${stat.color} border-0`}>
            <CardContent className="pt-5 pb-4">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-3xl font-bold text-white tracking-tight">{stat.value}</p>
                  <p className="text-sm font-medium text-white/90 mt-0.5">{stat.label}</p>
                  <p className="text-xs text-white/60 mt-0.5">{stat.sub}</p>
                </div>
                <div className={`${stat.iconBg} rounded-xl p-2.5`}>
                  <Icon className="h-5 w-5 text-white/80" />
                </div>
              </div>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
