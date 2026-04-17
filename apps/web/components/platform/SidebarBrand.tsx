'use client'

import type { MouseEventHandler } from 'react'
import { cn } from '@/lib/utils'
import { SidebarLogo } from './SidebarLogo'
import { ChevronLeft, ChevronRight, X } from 'lucide-react'

interface SidebarBrandProps {
  compact: boolean
  onCloseMobile?: MouseEventHandler<HTMLButtonElement>
  onToggleCompact: MouseEventHandler<HTMLButtonElement>
  showMobileClose?: boolean
}

export function SidebarBrand({ compact, onCloseMobile, onToggleCompact, showMobileClose = false }: SidebarBrandProps) {
  return (
    <div className={cn('flex items-center gap-3', compact ? 'justify-center p-2' : 'justify-between px-2 py-3')}>
      <div className="flex items-center gap-2.5 min-w-0">
        <div className="flex items-center justify-center shrink-0 rounded-xl bg-white p-1.5 shadow-sm">
          <SidebarLogo className={compact ? 'h-7 w-7' : 'h-8 w-8'} />
        </div>
        {!compact && (
          <h1 className="m-0 text-[0.92rem] font-bold tracking-[-0.02em] text-[#e2e5ea] whitespace-nowrap">
            RoBoCop
          </h1>
        )}
      </div>
      <div className={cn('flex items-center gap-1 shrink-0', compact && 'hidden')}>
        <button
          aria-label={compact ? 'Expand sidebar' : 'Collapse sidebar'}
          className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-[rgba(255,255,255,0.08)] bg-transparent text-[#6b7280] transition-colors hover:bg-[rgba(255,255,255,0.06)] hover:text-[#e2e5ea]"
          onClick={onToggleCompact}
          type="button"
        >
          {compact ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
        </button>
        {showMobileClose && (
          <button
            aria-label="Close navigation"
            className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-[rgba(255,255,255,0.08)] bg-transparent text-[#6b7280] transition-colors hover:bg-[rgba(255,255,255,0.06)] hover:text-[#e2e5ea]"
            onClick={onCloseMobile}
            type="button"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
    </div>
  )
}
