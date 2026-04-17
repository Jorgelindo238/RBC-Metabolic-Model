'use client'

import { useMemo, useState } from 'react'
import { usePathname, useSearchParams } from 'next/navigation'
import { getActivePlatformFeatureId, PLATFORM_NAV_SECTIONS } from '../../lib/platform-navigation.ts'
import { useSidebar } from './SidebarContext.tsx'
import Link from 'next/link'
import { ShieldCheck } from 'lucide-react'
import { SidebarAccount } from './SidebarAccount'
import { SidebarBrand } from './SidebarBrand'
import { SidebarSearch } from './SidebarSearch'
import { SidebarSection } from './SidebarSection'
import type { PlatformNavSection, ProductContextShape } from './platform-shell.types'

function filterSections(query: string) {
  const normalizedQuery = query.trim().toLowerCase()

  if (!normalizedQuery) {
    return PLATFORM_NAV_SECTIONS
  }

  return PLATFORM_NAV_SECTIONS.reduce<PlatformNavSection[]>((sections, section) => {
    const matchingItems = section.items.filter(item =>
      `${item.title} ${item.description} ${section.label}`.toLowerCase().includes(normalizedQuery)
    )

    if (matchingItems.length) {
      sections.push({ ...section, items: matchingItems })
    }

    return sections
  }, [])
}

export function PlatformSidebar({ productContext }: { productContext: ProductContextShape }) {
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const { closeMobile, compact, expandSidebar, mobileOpen, toggleCompact } = useSidebar()
  const [query, setQuery] = useState('')
  const [shouldFocusSearch, setShouldFocusSearch] = useState(false)
  const visibleSections = useMemo(() => filterSections(query), [query])
  const activeFeatureId = getActivePlatformFeatureId(pathname, searchParams.get('feature'))

  return (
    <>
      {mobileOpen ? (
        <button aria-label="Close navigation overlay" className="platform-sidebar-backdrop" onClick={closeMobile} type="button" />
      ) : null}
      <aside
        className={`platform-sidebar${compact ? ' premium-sidebar-compact' : ''}${
          mobileOpen ? ' premium-sidebar-mobile-open' : ''
        }`}
      >
        <div className="premium-sidebar-top">
          <SidebarBrand
            compact={compact}
            onCloseMobile={closeMobile}
            onToggleCompact={toggleCompact}
            showMobileClose={mobileOpen}
          />
          <SidebarSearch
            compact={compact}
            onAutoFocusHandled={() => setShouldFocusSearch(false)}
            onExpandSearch={() => {
              expandSidebar()
              setShouldFocusSearch(true)
            }}
            onQueryChange={setQuery}
            query={query}
            shouldAutoFocus={shouldFocusSearch}
          />
        </div>
        <div className="premium-sidebar-navigation">
          {visibleSections.length ? (
            visibleSections.map(section => (
              <SidebarSection
                activeFeatureId={activeFeatureId}
                compact={compact}
                key={section.id}
                onNavigate={closeMobile}
                section={section}
              />
            ))
          ) : (
            <div className="sidebar-search-empty">
              <p className="sidebar-search-empty-title">No matching features</p>
              <p className="sidebar-search-empty-copy">Try a module name like calibration, atlas, or data.</p>
            </div>
          )}
        </div>
        <div className="premium-sidebar-footer">
          {productContext?.isAdmin && !compact && (
            <Link
              href="/admin"
              className="flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium text-[#9ca3af] transition-colors hover:bg-[rgba(255,255,255,0.06)] hover:text-[#e2e5ea] mb-2"
            >
              <ShieldCheck className="h-4 w-4 text-[var(--accent)]" />
              Admin Dashboard
            </Link>
          )}
          {!compact ? (
            <p className="sidebar-section-label px-2">MY ACCOUNT</p>
          ) : (
            <p className="sidebar-section-label sidebar-section-label-compact px-2">M</p>
          )}
          <SidebarAccount compact={compact} productContext={productContext} />
        </div>
      </aside>
    </>
  )
}
