import { createElement as h } from 'react'

function buildHeaderSummary(productContext) {
  if (!productContext?.isAuthenticated) {
    return 'Anonymous session'
  }

  const name = productContext.researcherIdentity?.displayName || 'Researcher'
  const workspace = productContext.activeWorkspace?.name || productContext.activeWorkspace?.slug || null

  if (workspace) {
    return `${name} · ${workspace}`
  }

  if (productContext?.workspaceSelectionRequired) {
    return `${name} · Workspace selection required`
  }

  return `${name} · Personal access`
}

function buildWorkspaceBadge(productContext) {
  if (productContext?.workspaceSelectionReason === 'stored_preference_selected') {
    return 'stored preference'
  }

  if (productContext?.workspaceSelectionReason === 'cookie_fallback_selected') {
    return 'cookie fallback'
  }

  if (productContext?.workspaceSelectionReason === 'single_membership_auto_selected'
    || productContext?.workspaceSelectionReason === 'stored_preference_invalid_single_membership_auto_selected') {
    return 'auto selected'
  }

  return productContext?.activeWorkspace?.name || productContext?.activeWorkspace?.slug || null
}

export function PlatformHeader({ productContext }) {
  return h('header', { className: 'platform-header' }, [
    h('div', { className: 'platform-header-copy', key: 'copy' }, [
      h('p', { className: 'platform-header-kicker', key: 'kicker' }, 'Research workspace'),
      h('h2', { className: 'platform-header-title', key: 'title' }, 'RoBoCop Scientific Platform'),
      h(
        'p',
        { className: 'platform-header-subtitle', key: 'subtitle' },
        'A broader researcher surface for calibration evidence, future simulation workflows, pathway interpretation, and Supabase-backed scientific context.'
      ),
    ]),
    h('div', { className: 'platform-header-meta', key: 'meta' }, [
      h('span', { className: 'platform-header-badge', key: 'summary' }, buildHeaderSummary(productContext)),
      productContext?.workspaceSelectionRequired
        ? h('span', { className: 'platform-header-badge platform-header-badge-warning', key: 'workspace' }, 'choose workspace')
        : buildWorkspaceBadge(productContext)
          ? h('span', { className: 'platform-header-badge platform-header-badge-muted', key: 'workspace' }, buildWorkspaceBadge(productContext))
          : null,
      h('span', { className: 'platform-header-badge platform-header-badge-muted', key: 'mode' }, productContext?.contextState || 'anonymous'),
    ].filter(Boolean)),
  ])
}
