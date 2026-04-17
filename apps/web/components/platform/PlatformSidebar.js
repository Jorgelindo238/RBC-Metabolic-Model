import { createElement as h } from 'react'
import Link from 'next/link'
import { PLATFORM_NAV_SECTIONS } from '../../lib/platform-navigation.mjs'

function renderNavItem(item) {
  if (item.href) {
    return h(Link, { href: item.href, className: 'platform-nav-link', key: item.title }, [
      h('span', { className: 'platform-nav-link-title', key: 'title' }, item.title),
      h('span', { className: `platform-status-chip status-${item.status}`, key: 'status' }, item.status),
    ])
  }

  return h('div', { className: 'platform-nav-link platform-nav-link-muted', key: item.title }, [
    h('span', { className: 'platform-nav-link-title', key: 'title' }, item.title),
    h('span', { className: `platform-status-chip status-${item.status}`, key: 'status' }, item.status),
  ])
}

function buildWorkspaceSummary(productContext) {
  if (!productContext?.isAuthenticated) {
    return 'Anonymous public context'
  }

  if (productContext?.workspaceSelectionRequired) {
    return 'Choose an active workspace'
  }

  return productContext?.activeWorkspace?.name || productContext?.activeWorkspace?.slug || 'Personal researcher context'
}

function buildWorkspaceDetail(productContext) {
  if (productContext?.workspaceSelectionRequired) {
    return 'Multiple workspace memberships are available. Select one explicitly before relying on workspace-scoped visibility.'
  }

  switch (productContext?.workspaceSelectionReason) {
    case 'stored_preference_selected':
      return 'Active workspace recovered from your durable stored workspace preference.'
    case 'cookie_fallback_selected':
      return 'Active workspace is using the transitional cookie fallback because no durable preference is stored yet.'
    case 'single_membership_auto_selected':
      return 'Only one active workspace membership exists, so the server selected it automatically.'
    case 'stored_preference_invalid_single_membership_auto_selected':
      return 'The stored preference is no longer valid, but the server recovered safely because only one active membership remains.'
    default:
      return productContext?.activeWorkspace?.id
        ? `Selection reason: ${productContext?.workspaceSelectionReason || 'workspace_selected'}`
        : 'No active workspace is currently selected for this request.'
  }
}

export function PlatformSidebar({ productContext }) {
  return h('aside', { className: 'platform-sidebar' }, [
    h('div', { className: 'platform-brand', key: 'brand' }, [
      h('p', { className: 'platform-brand-kicker', key: 'kicker' }, 'RoBoCop'),
      h('h1', { className: 'platform-brand-title', key: 'title' }, 'Research Platform'),
      h(
        'p',
        { className: 'platform-brand-copy', key: 'copy' },
        'Supabase-backed researcher identity, bounded scientific execution, and a broader scientific dashboard downstream of Python authority.'
      ),
    ]),
    h('section', { className: 'platform-nav-section', key: 'workspace' }, [
      h('p', { className: 'platform-nav-label', key: 'label' }, 'Active workspace'),
      h('div', { className: 'platform-workspace-summary', key: 'summary' }, [
        h('strong', { className: 'platform-workspace-title', key: 'title' }, buildWorkspaceSummary(productContext)),
        h('p', { className: 'platform-sidebar-note', key: 'copy' }, buildWorkspaceDetail(productContext)),
      ]),
      productContext?.workspaceSelectionRequired
        ? h(Link, { href: '/', className: 'workspace-select-link', key: 'action' }, 'Select active workspace')
        : null,
    ]),
    ...PLATFORM_NAV_SECTIONS.map(section => h('section', { className: 'platform-nav-section', key: section.label }, [
      h('p', { className: 'platform-nav-label', key: 'label' }, section.label),
      h('div', { className: 'platform-nav-list', key: 'items' }, section.items.map(renderNavItem)),
    ])),
    h('section', { className: 'platform-sidebar-footer', key: 'footer' }, [
      h('p', { className: 'platform-nav-label', key: 'label' }, 'Platform posture'),
      h(
        'p',
        { className: 'platform-sidebar-note', key: 'copy' },
        'Calibration is one module in the platform. Scientific truth remains in the Python execution and artifact boundaries.'
      ),
    ]),
  ])
}
