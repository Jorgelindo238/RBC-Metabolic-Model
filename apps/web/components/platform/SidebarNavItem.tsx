import Link from 'next/link'
import { SidebarIcon } from './SidebarIcons'
import type { PlatformNavItem } from './platform-shell.types'

interface SidebarNavItemProps {
  activeFeatureId?: string | null
  compact: boolean
  item: PlatformNavItem
  onNavigate?: () => void
}

export function SidebarNavItem({
  activeFeatureId,
  compact,
  item,
  onNavigate,
}: SidebarNavItemProps) {
  const isActive = activeFeatureId === item.id
  const className = [
    'sidebar-nav-item',
    isActive ? 'sidebar-nav-item-active' : '',
    compact ? 'sidebar-nav-item-compact' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <Link className={className} href={item.href} onClick={onNavigate} title={item.title}>
      <span className="sidebar-nav-item-leading">
        <SidebarIcon icon={item.icon} className="sidebar-nav-icon" />
      </span>
      {!compact ? (
        <>
          <span className="sidebar-nav-item-copy">
            <span className="sidebar-nav-item-title">{item.title}</span>
          </span>
          <span className="sidebar-nav-trailing">
            {item.badgeCount != null ? (
              <span className="sidebar-nav-count">{item.badgeCount}</span>
            ) : item.badgeText ? (
              <span className="sidebar-nav-inline-badge">{item.badgeText}</span>
            ) : null}
          </span>
        </>
      ) : null}
    </Link>
  )
}
