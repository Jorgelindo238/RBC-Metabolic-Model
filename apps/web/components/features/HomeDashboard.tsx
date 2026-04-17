'use client'

import { WorkflowGuide } from './home/WorkflowGuide'
import { ModelOverview } from './home/ModelOverview'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { BookOpen, ExternalLink } from 'lucide-react'

export function HomeDashboard() {
  return (
    <div className="grid gap-5">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-primary" />
            About This Workspace
          </CardTitle>
          <CardDescription>
            This platform supports research on <strong className="text-foreground">stored red blood cells</strong>, with a focus on
            understanding storage-related metabolic changes and interpreting the biochemical evolution of the blood bag over time.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-border/50 bg-muted/30 p-3">
              <p className="text-xs font-semibold text-foreground mb-1">Scientific basis</p>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Mechanistic ODE model reconstructed from <strong>Bordbar et al. (2015)</strong>, covering glycolysis, pentose phosphate pathway,
                Rapoport-Luebering shunt, glutathione cycling, nucleotide metabolism, and amino acid handling.
              </p>
            </div>
            <div className="rounded-lg border border-border/50 bg-muted/30 p-3">
              <p className="text-xs font-semibold text-foreground mb-1">What you can investigate</p>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Dynamic metabolite trajectories during storage, pathway flux redistribution, parameter sensitivity,
                model-data agreement, and the impact of pH perturbations on RBC metabolism.
              </p>
            </div>
          </div>
          <div className="mt-3 flex items-center gap-3">
            <a href="https://www.cell.com/action/showPdf?pii=S2405-4712%2815%2900149-0" target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline">
              <ExternalLink className="h-3 w-3" /> Bordbar et al. (2015) — Cell Systems
            </a>
            <Badge variant="outline" className="text-[10px]">113 metabolites</Badge>
            <Badge variant="outline" className="text-[10px]">~200 reactions</Badge>
            <Badge variant="outline" className="text-[10px]">42-day horizon</Badge>
          </div>
        </CardContent>
      </Card>

      <WorkflowGuide />
      <ModelOverview />
    </div>
  )
}
