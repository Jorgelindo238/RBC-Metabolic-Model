'use client'

import Link from 'next/link'
import { Database, RotateCcw } from 'lucide-react'
import { useResearchDataset } from '@/contexts/ResearchDatasetProvider'

export function ResearchDatasetBanner({ className = '' }: { className?: string }) {
  const { activeDatasetSummary: data, researchDataMode, clearActiveDataset } = useResearchDataset()
  const custom = researchDataMode === 'custom_user_data_mode'
  return (
    <div className={`research-dataset ${className}`} data-testid="research-dataset">
      <Database size={15} aria-hidden="true" />
      <span className="research-dataset-name">{data.label}</span>
      <span className="research-muted">{custom ? 'Uploaded data' : 'Reference data'}</span>
      {custom ? <span className="research-muted">{data.timePointCount} dates / {data.mappedMetaboliteCount} mapped</span> : null}
      <Link href="/research/data-upload">Change source</Link>
      {custom ? <button type="button" onClick={clearActiveDataset} className="research-icon-button"
        title="Return to Bordbar reference" aria-label="Return to Bordbar reference"><RotateCcw size={15} /></button> : null}
    </div>
  )
}
