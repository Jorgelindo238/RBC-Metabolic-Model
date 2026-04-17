import { SidebarNavItem } from './SidebarNavItem'
import type { PlatformNavSection } from './platform-shell.types'

interface SidebarSectionProps {
  activeFeatureId?: string | null
  compact: boolean
  onNavigate?: () => void
  section: PlatformNavSection
}

export function SidebarSection({
  activeFeatureId,
  compact,
  onNavigate,
  section,
}: SidebarSectionProps) {
  return (
    <section className="sidebar-section">
      {!compact ? (
        <p className="sidebar-section-label">{section.label}</p>
      ) : (
        <p className="sidebar-section-label sidebar-section-label-compact">{section.label.slice(0, 1)}</p>
      )}
      <div className="sidebar-section-items">
        {section.items.map(item => (
          <SidebarNavItem
            activeFeatureId={activeFeatureId}
            compact={compact}
            item={item}
            key={item.id}
            onNavigate={onNavigate}
          />
        ))}
      </div>
    </section>
  )
}
