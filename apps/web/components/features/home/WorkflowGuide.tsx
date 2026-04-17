'use client'

import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { FlaskConical, Upload, BarChart3, Map, Target, FileCheck } from 'lucide-react'

const STEPS = [
  { step: 1, title: 'Simulate', desc: 'Run a storage-condition simulation across a configurable time horizon', icon: FlaskConical, href: '/?feature=simulation-workspace' },
  { step: 2, title: 'Upload Data', desc: 'Bring your own experimental RBC storage dataset for comparison', icon: Upload, href: '/?feature=data-upload' },
  { step: 3, title: 'Analyse Fluxes', desc: 'Inspect pathway activity and metabolic flux distributions', icon: BarChart3, href: '/?feature=flux-analysis' },
  { step: 4, title: 'View Pathways', desc: 'Explore the metabolic network structure and concentration state', icon: Map, href: '/?feature=pathway-visualization' },
  { step: 5, title: 'Calibrate', desc: 'Optimize kinetic parameters against observed storage data', icon: Target, href: '/?feature=parameter-calibration' },
  { step: 6, title: 'Review Results', desc: 'Compare calibration runs and track improvement over time', icon: FileCheck, href: '/?feature=calibration-registry' },
]

export function WorkflowGuide() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Research Workflow</CardTitle>
        <CardDescription>A suggested sequence for investigating RBC metabolic behavior during storage.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
          {STEPS.map((s) => {
            const Icon = s.icon
            return (
              <a key={s.step} href={s.href} className="group flex items-start gap-3 rounded-xl border border-border/50 bg-muted/30 p-3 transition-colors hover:bg-muted/60 hover:border-primary/30">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Icon className="h-4 w-4" />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-[10px] px-1.5 py-0 font-mono">{s.step}</Badge>
                    <span className="text-sm font-medium text-foreground group-hover:text-primary transition-colors">{s.title}</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{s.desc}</p>
                </div>
              </a>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
