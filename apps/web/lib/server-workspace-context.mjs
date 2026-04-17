import { cookies } from 'next/headers'

export const ACTIVE_WORKSPACE_COOKIE = 'robocop_active_workspace'

function normalizeWorkspaceRecord(membership) {
  if (!membership) {
    return null
  }

  const workspace = membership.workspace || null

  return {
    workspaceId: membership.workspace_id ?? workspace?.id ?? null,
    membershipRole: membership.membership_role ?? null,
    membershipStatus: membership.membership_status ?? null,
    joinedAt: membership.joined_at ?? null,
    workspace: workspace
      ? {
          id: workspace.id ?? membership.workspace_id ?? null,
          slug: workspace.slug ?? null,
          name: workspace.name ?? null,
        }
      : {
          id: membership.workspace_id ?? null,
          slug: null,
          name: null,
        },
  }
}

function buildWorkspaceOptions(memberships) {
  return (memberships || []).map(membership => normalizeWorkspaceRecord(membership)).filter(Boolean)
}

async function readRequestedWorkspaceId() {
  const cookieStore = await cookies()
  return cookieStore.get(ACTIVE_WORKSPACE_COOKIE)?.value ?? null
}

function buildStoredPreferenceState(storedWorkspacePreferenceId, storedWorkspaceOption, storedWorkspacePreferenceUpdatedAt) {
  if (!storedWorkspacePreferenceId) {
    return {
      storedWorkspacePreferenceId: null,
      storedWorkspacePreferenceUpdatedAt: storedWorkspacePreferenceUpdatedAt ?? null,
      storedWorkspacePreferenceState: 'no_stored_preference',
      storedWorkspacePreferenceValid: false,
      storedWorkspacePreferenceError: null,
    }
  }

  if (storedWorkspaceOption) {
    return {
      storedWorkspacePreferenceId,
      storedWorkspacePreferenceUpdatedAt: storedWorkspacePreferenceUpdatedAt ?? null,
      storedWorkspacePreferenceState: 'stored_preference_valid',
      storedWorkspacePreferenceValid: true,
      storedWorkspacePreferenceError: null,
    }
  }

  return {
    storedWorkspacePreferenceId,
    storedWorkspacePreferenceUpdatedAt: storedWorkspacePreferenceUpdatedAt ?? null,
    storedWorkspacePreferenceState: 'stored_preference_invalid',
    storedWorkspacePreferenceValid: false,
    storedWorkspacePreferenceError: 'The stored workspace preference no longer matches an active workspace membership.',
  }
}

function buildSelectedWorkspaceContext(baseState, selectedWorkspaceOption, workspaceSelectionReason) {
  return {
    ...baseState,
    workspaceSelectionState: 'workspace_selected',
    workspaceSelectionReason,
    workspaceSelectionRequired: false,
    activeWorkspace: selectedWorkspaceOption.workspace,
    activeWorkspaceMembership: selectedWorkspaceOption,
    selectedWorkspaceOption,
    workspaceSelectionError:
      workspaceSelectionReason === 'stored_preference_invalid_single_membership_auto_selected'
        ? baseState.storedWorkspacePreferenceError
        : null,
  }
}

export async function resolveServerWorkspaceContext(workspaceMemberships, options = {}) {
  const workspaceOptions = buildWorkspaceOptions(workspaceMemberships)
  const workspaceCount = workspaceOptions.length
  const requestedWorkspaceId = await readRequestedWorkspaceId()
  const storedWorkspacePreferenceId = options.storedWorkspacePreferenceId ?? null
  const storedWorkspacePreferenceUpdatedAt = options.storedWorkspacePreferenceUpdatedAt ?? null
  const storedWorkspaceOption = storedWorkspacePreferenceId
    ? workspaceOptions.find(option => option.workspaceId === storedWorkspacePreferenceId) || null
    : null
  const storedPreferenceState = buildStoredPreferenceState(
    storedWorkspacePreferenceId,
    storedWorkspaceOption,
    storedWorkspacePreferenceUpdatedAt
  )
  const cookieWorkspaceOption = requestedWorkspaceId
    ? workspaceOptions.find(option => option.workspaceId === requestedWorkspaceId) || null
    : null
  const baseState = {
    workspaceCount,
    requestedWorkspaceId,
    availableWorkspaces: workspaceOptions,
    ...storedPreferenceState,
  }

  if (workspaceCount === 0) {
    return {
      ...baseState,
      workspaceSelectionState: 'no_workspace',
      workspaceSelectionReason: 'no_active_membership',
      workspaceSelectionRequired: false,
      activeWorkspace: null,
      activeWorkspaceMembership: null,
      selectedWorkspaceOption: null,
      workspaceSelectionError: null,
    }
  }

  if (storedWorkspaceOption) {
    return buildSelectedWorkspaceContext(baseState, storedWorkspaceOption, 'stored_preference_selected')
  }

  if (workspaceCount === 1) {
    const selectedWorkspaceOption = workspaceOptions[0]
    return buildSelectedWorkspaceContext(
      baseState,
      selectedWorkspaceOption,
      storedPreferenceState.storedWorkspacePreferenceState === 'stored_preference_invalid'
        ? 'stored_preference_invalid_single_membership_auto_selected'
        : 'single_membership_auto_selected'
    )
  }

  if (storedPreferenceState.storedWorkspacePreferenceState === 'stored_preference_invalid') {
    return {
      ...baseState,
      workspaceSelectionState: 'workspace_selection_required',
      workspaceSelectionReason: 'stored_preference_not_available',
      workspaceSelectionRequired: true,
      activeWorkspace: null,
      activeWorkspaceMembership: null,
      selectedWorkspaceOption: null,
      workspaceSelectionError: storedPreferenceState.storedWorkspacePreferenceError,
    }
  }

  if (!storedWorkspacePreferenceId && cookieWorkspaceOption) {
    return buildSelectedWorkspaceContext(baseState, cookieWorkspaceOption, 'cookie_fallback_selected')
  }

  return {
    ...baseState,
    workspaceSelectionState: 'workspace_selection_required',
    workspaceSelectionReason: 'multiple_memberships_require_selection',
    workspaceSelectionRequired: true,
    activeWorkspace: null,
    activeWorkspaceMembership: null,
    selectedWorkspaceOption: null,
    workspaceSelectionError: null,
  }
}
