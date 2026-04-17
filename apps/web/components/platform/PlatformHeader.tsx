'use client'

import type { ProductContextShape } from './platform-shell.types'
import { useSidebar } from './SidebarContext.tsx'

function buildHeaderSummary(productContext: ProductContextShape) {
  if (!productContext?.isAuthenticated) {
    return 'Anonymous session'
  }

  const name = productContext.researcherIdentity?.displayName || 'Researcher'
  const workspace = productContext.activeWorkspace?.name || productContext.activeWorkspace?.slug || null

  if (workspace) {
    return `${name} · ${workspace}`
  }

  if (productContext.workspaceSelectionRequired) {
    return `${name} · Workspace selection required`
  }

  return `${name} · Personal access`
}

function buildWorkspaceBadge(productContext: ProductContextShape) {
  switch (productContext?.workspaceSelectionReason) {
    case 'stored_preference_selected':
      return 'stored preference'
    case 'cookie_fallback_selected':
      return 'cookie fallback'
    case 'single_membership_auto_selected':
    case 'stored_preference_invalid_single_membership_auto_selected':
      return 'auto selected'
    default:
      return productContext?.activeWorkspace?.name || productContext?.activeWorkspace?.slug || null
  }
}

export function PlatformHeader({ productContext }: { productContext: ProductContextShape }) {
  const { openMobile } = useSidebar()
  const workspaceBadge = buildWorkspaceBadge(productContext)

  return (
    <header className="platform-header">
      <div className="platform-header-copy">
        <div className="platform-header-topline">
          <button
            aria-label="Open navigation"
            className="platform-header-mobile-toggle"
            onClick={openMobile}
            type="button"
          >
            <span className="platform-header-mobile-toggle-bars" aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
          </button>
          <p className="platform-header-kicker">Red blood cell storage research</p>
        </div>
        <h2 className="platform-header-title">RBC Metabolic Model</h2>
        <p className="platform-header-subtitle">
          Mechanistic simulation and calibration workspace for studying red blood cell metabolism during storage,
          based on the Bordbar et al. (2015) reconstruction.
        </p>
      </div>
      <div className="platform-header-meta">
        <span className="platform-header-badge">{buildHeaderSummary(productContext)}</span>
        {productContext?.workspaceSelectionRequired ? (
          <span className="platform-header-badge platform-header-badge-warning">choose workspace</span>
        ) : workspaceBadge ? (
          <span className="platform-header-badge platform-header-badge-muted">{workspaceBadge}</span>
        ) : null}
        <span className="platform-header-badge platform-header-badge-muted">
          {productContext?.contextState || 'anonymous'}
        </span>
      </div>
    </header>
  )
}
