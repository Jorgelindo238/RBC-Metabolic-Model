import { createElement as h } from 'react'
import { FieldGrid } from '../ui/FieldGrid.js'
import { MetricGrid } from '../ui/MetricGrid.js'

function buildWorkspaceSelectionHref({ workspaceId, redirectTo }) {
  const params = new URLSearchParams()
  if (workspaceId) {
    params.set('workspaceId', workspaceId)
  }
  params.set('redirectTo', redirectTo || '/')
  return `/workspace/select?${params.toString()}`
}

function describeSelectionReason(productContext) {
  switch (productContext?.workspaceSelectionReason) {
    case 'stored_preference_selected':
      return 'The active workspace comes from the durable workspace preference stored in the product layer for this researcher.'
    case 'cookie_fallback_selected':
      return 'The active workspace is using the transitional cookie-backed fallback because no durable stored preference is currently available.'
    case 'single_membership_auto_selected':
      return 'Only one active workspace membership exists, so the server selected it automatically.'
    case 'stored_preference_invalid_single_membership_auto_selected':
      return 'The stored workspace preference is no longer valid, but only one active workspace membership remains, so the server recovered safely by auto-selecting it.'
    case 'multiple_memberships_require_selection':
      return 'Multiple active workspace memberships exist. The platform requires an explicit workspace choice before using workspace-scoped visibility.'
    case 'stored_preference_not_available':
      return 'The stored workspace preference no longer matches an active workspace membership, so a new explicit selection is required.'
    case 'no_active_membership':
      return 'No active workspace memberships are available for this authenticated researcher.'
    default:
      return 'Workspace context is being resolved on the server from active memberships, durable stored preference state, and bounded transitional fallback behavior.'
  }
}

function WorkspaceOption({ option, activeWorkspaceId, redirectTo }) {
  const isActive = option.workspace?.id && option.workspace.id === activeWorkspaceId

  return h('div', { className: `workspace-option${isActive ? ' workspace-option-active' : ''}` }, [
    h('div', { className: 'workspace-option-copy', key: 'copy' }, [
      h('strong', { className: 'workspace-option-title', key: 'title' }, option.workspace?.name || option.workspace?.slug || option.workspaceId),
      h('p', { className: 'workspace-option-meta', key: 'meta' }, `${option.membershipRole || 'member'} · ${option.workspace?.slug || option.workspaceId}`),
    ]),
    isActive
      ? h('span', { className: 'platform-status-chip status-live', key: 'status' }, 'active')
      : h('a', {
          className: 'workspace-select-link',
          href: buildWorkspaceSelectionHref({ workspaceId: option.workspaceId, redirectTo }),
          key: 'action',
        }, 'Select workspace'),
  ])
}

export function WorkspaceContextPanel({ productContext, redirectTo = '/' }) {
  const availableWorkspaces = productContext?.availableWorkspaces || []
  const activeWorkspaceId = productContext?.activeWorkspace?.id || null

  const metrics = [
    ['Workspace count', productContext?.workspaceCount || 0],
    ['Stored preference', productContext?.storedWorkspacePreferenceState || 'unknown'],
    ['Selection state', productContext?.workspaceSelectionState || 'unknown'],
    ['Selection required', productContext?.workspaceSelectionRequired ? 'yes' : 'no'],
  ]

  const fields = [
    ['Active workspace', productContext?.activeWorkspace?.name || productContext?.activeWorkspace?.slug],
    ['Stored workspace id', productContext?.storedWorkspacePreferenceId],
    ['Stored preference updated', productContext?.storedWorkspacePreferenceUpdatedAt],
    ['Cookie transport id', productContext?.requestedWorkspaceId],
    ['Selection reason', productContext?.workspaceSelectionReason],
    ['Stored preference error', productContext?.storedWorkspacePreferenceError],
    ['Selection error', productContext?.workspaceSelectionError],
  ]

  return h('section', { className: 'panel' }, [
    h('div', { className: 'panel-heading', key: 'heading' }, [
      h('h2', { key: 'title' }, 'Workspace context'),
      h('p', { key: 'copy' }, describeSelectionReason(productContext)),
    ]),
    h(MetricGrid, { metrics, key: 'metrics' }),
    h(FieldGrid, { fields, key: 'fields' }),
    availableWorkspaces.length
      ? h('div', { className: 'workspace-option-list', key: 'options' }, availableWorkspaces.map(option => h(WorkspaceOption, {
          option,
          activeWorkspaceId,
          redirectTo,
          key: option.workspaceId,
        })))
      : null,
    availableWorkspaces.length > 1 && activeWorkspaceId
      ? h('div', { className: 'workspace-option-actions', key: 'clear' }, [
          h('a', {
            className: 'workspace-clear-link',
            href: buildWorkspaceSelectionHref({ workspaceId: null, redirectTo }),
            key: 'link',
          }, 'Clear workspace selection'),
        ])
      : null,
  ])
}
