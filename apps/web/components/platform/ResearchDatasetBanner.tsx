'use client'

import Link from 'next/link'
import { Database } from 'lucide-react'
import { useResearchDataset } from '@/contexts/ResearchDatasetProvider'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

function DatasetStat({
  label,
  value,
}: {
  label: string
  value: string
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">{label}</p>
      <p className="mt-2 text-sm font-semibold text-white">{value}</p>
    </div>
  )
}

export function ResearchDatasetBanner({ className }: { className?: string }) {
  const { activeDatasetSummary, researchDataMode } = useResearchDataset()
  const isCustom = researchDataMode === 'custom_user_data_mode'

  return (
    <section
      className={cn(
        'rounded-3xl border border-white/10 bg-slate-950/55 p-4 shadow-[0_18px_50px_-32px_rgba(0,0,0,0.75)] backdrop-blur-sm',
        className
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="eyebrow">Active research dataset</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className="flex min-w-0 items-center gap-2 text-sm font-semibold text-white">
              <Database className={cn('h-4 w-4', isCustom ? 'text-emerald-300' : 'text-cyan-300')} />
              <span className="truncate">{activeDatasetSummary.label}</span>
            </span>
            <Badge variant={isCustom ? 'default' : 'secondary'} className="rounded-full">
              {isCustom ? 'Custom user data' : 'Bordbar default'}
            </Badge>
            <span className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-300">
              {isCustom ? 'Active' : 'Fallback'}
            </span>
          </div>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
            {isCustom
              ? 'Calibration and simulation are now reading from the uploaded research dataset.'
              : 'No upload has been activated yet, so the Bordbar reference dataset remains the active fallback.'}
          </p>
        </div>

        <Button
          asChild
          className="h-9 rounded-full border border-white/10 bg-white/[0.04] px-4 text-xs font-semibold text-white hover:bg-white/[0.08]"
          variant="ghost"
        >
          <Link href="/research/data-upload">Open Data Upload</Link>
        </Button>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <DatasetStat
          label="Mode"
          value={isCustom ? 'Custom user data' : 'Bordbar default'}
        />
        <DatasetStat
          label="Time points"
          value={activeDatasetSummary.timePointCount > 0 ? String(activeDatasetSummary.timePointCount) : '—'}
        />
        <DatasetStat
          label="Mapped metabolites"
          value={activeDatasetSummary.mappedMetaboliteCount > 0 ? String(activeDatasetSummary.mappedMetaboliteCount) : '—'}
        />
      </div>
    </section>
  )
}
