'use client'

import { Database } from 'lucide-react'
import { useResearchDataset } from '@/contexts/ResearchDatasetProvider'
import { cn } from '@/lib/utils'

export function ResearchDatasetModeChip({ className }: { className?: string }) {
  const { activeDatasetSummary, researchDataMode } = useResearchDataset()
  const isCustom = researchDataMode === 'custom_user_data_mode'

  return (
    <span
      className={cn(
        'inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold shadow-sm',
        isCustom
          ? 'border-emerald-400/20 bg-emerald-400/10 text-emerald-100'
          : 'border-cyan-400/20 bg-cyan-400/10 text-cyan-100',
        className
      )}
      title={activeDatasetSummary.label}
    >
      <Database className={cn('h-3.5 w-3.5', isCustom ? 'text-emerald-200' : 'text-cyan-200')} />
      <span>{isCustom ? 'Custom user data active' : 'Bordbar fallback active'}</span>
    </span>
  )
}
