import { getServerAuthContext } from './server-auth.mjs'
import { isProductSchemaUnavailableError } from './server-run-access.mjs'
import { resolveServerWorkspaceContext } from './server-workspace-context.mjs'
import { getActiveWorkspaceMemberships } from './server-workspace-preference.mjs'

export async function getServerProductContext() {
  const authContext = await getServerAuthContext()

  if (authContext.missingCredentials) {
    return {
      ...authContext,
      profile: null,
      workspaceMembership: null,
      workspaceMemberships: [],
      availableWorkspaces: [],
      workspaceCount: 0,
      requestedWorkspaceId: null,
      storedWorkspacePreferenceId: null,
      storedWorkspacePreferenceUpdatedAt: null,
      storedWorkspacePreferenceState: 'no_stored_preference',
      storedWorkspacePreferenceValid: false,
      storedWorkspacePreferenceError: null,
      activeWorkspace: null,
      hasWorkspaceContext: false,
      contextError: null,
      contextState: 'credentials_missing',
      workspaceSelectionState: 'no_workspace',
      workspaceSelectionReason: 'credentials_missing',
      workspaceSelectionRequired: false,
      workspaceSelectionError: null,
      researcherIdentity: null,
    }
  }

  if (!authContext.isAuthenticated) {
    return {
      ...authContext,
      profile: null,
      workspaceMembership: null,
      workspaceMemberships: [],
      availableWorkspaces: [],
      workspaceCount: 0,
      requestedWorkspaceId: null,
      storedWorkspacePreferenceId: null,
      storedWorkspacePreferenceUpdatedAt: null,
      storedWorkspacePreferenceState: 'no_stored_preference',
      storedWorkspacePreferenceValid: false,
      storedWorkspacePreferenceError: null,
      activeWorkspace: null,
      hasWorkspaceContext: false,
      contextError: authContext.authError,
      contextState: authContext.authState,
      workspaceSelectionState: 'no_workspace',
      workspaceSelectionReason: authContext.authState,
      workspaceSelectionRequired: false,
      workspaceSelectionError: null,
      researcherIdentity: null,
    }
  }

  const { data: profile, error: profileError } = await authContext.supabase
    .from('profiles')
    .select('id, email, display_name, organization_name, active_workspace_id, active_workspace_updated_at')
    .eq('id', authContext.user.id)
    .maybeSingle()

  if (profileError) {
    return {
      ...authContext,
      profile: null,
      workspaceMembership: null,
      workspaceMemberships: [],
      availableWorkspaces: [],
      workspaceCount: 0,
      requestedWorkspaceId: null,
      storedWorkspacePreferenceId: null,
      storedWorkspacePreferenceUpdatedAt: null,
      storedWorkspacePreferenceState: 'no_stored_preference',
      storedWorkspacePreferenceValid: false,
      storedWorkspacePreferenceError: null,
      activeWorkspace: null,
      hasWorkspaceContext: false,
      contextError: profileError.message,
      contextState: isProductSchemaUnavailableError(profileError) ? 'product_schema_unavailable' : 'product_context_error',
      workspaceSelectionState: 'no_workspace',
      workspaceSelectionReason: 'profile_unavailable',
      workspaceSelectionRequired: false,
      workspaceSelectionError: null,
      researcherIdentity: {
        email: authContext.user.email ?? null,
        displayName: authContext.user.user_metadata?.full_name ?? authContext.user.email ?? 'Researcher',
        organizationName: null,
      },
    }
  }

  const { data: memberships, error: membershipError } = await getActiveWorkspaceMemberships(authContext.supabase, authContext.user.id)

  if (membershipError) {
    return {
      ...authContext,
      profile: profile ?? null,
      workspaceMembership: null,
      workspaceMemberships: [],
      availableWorkspaces: [],
      workspaceCount: 0,
      requestedWorkspaceId: null,
      storedWorkspacePreferenceId: profile?.active_workspace_id ?? null,
      storedWorkspacePreferenceUpdatedAt: profile?.active_workspace_updated_at ?? null,
      storedWorkspacePreferenceState: 'no_stored_preference',
      storedWorkspacePreferenceValid: false,
      storedWorkspacePreferenceError: null,
      activeWorkspace: null,
      hasWorkspaceContext: false,
      contextError: membershipError.message,
      contextState: isProductSchemaUnavailableError(membershipError) ? 'product_schema_unavailable' : 'product_context_error',
      workspaceSelectionState: 'no_workspace',
      workspaceSelectionReason: 'memberships_unavailable',
      workspaceSelectionRequired: false,
      workspaceSelectionError: null,
      researcherIdentity: {
        email: profile?.email ?? authContext.user.email ?? null,
        displayName: profile?.display_name ?? authContext.user.user_metadata?.full_name ?? authContext.user.email ?? 'Researcher',
        organizationName: profile?.organization_name ?? null,
      },
    }
  }

  const workspaceMemberships = memberships || []
  const workspaceContext = await resolveServerWorkspaceContext(workspaceMemberships, {
    storedWorkspacePreferenceId: profile?.active_workspace_id ?? null,
    storedWorkspacePreferenceUpdatedAt: profile?.active_workspace_updated_at ?? null,
  })

  let isAdmin = false
  try {
    const { data: adminCheck } = await authContext.supabase.rpc('is_admin')
    isAdmin = adminCheck === true
  } catch {}

  return {
    ...authContext,
    isAdmin,
    profile: profile ?? null,
    workspaceMembership: workspaceContext.activeWorkspaceMembership,
    workspaceMemberships,
    availableWorkspaces: workspaceContext.availableWorkspaces,
    workspaceCount: workspaceContext.workspaceCount,
    requestedWorkspaceId: workspaceContext.requestedWorkspaceId,
    storedWorkspacePreferenceId: workspaceContext.storedWorkspacePreferenceId,
    storedWorkspacePreferenceUpdatedAt: workspaceContext.storedWorkspacePreferenceUpdatedAt,
    storedWorkspacePreferenceState: workspaceContext.storedWorkspacePreferenceState,
    storedWorkspacePreferenceValid: workspaceContext.storedWorkspacePreferenceValid,
    storedWorkspacePreferenceError: workspaceContext.storedWorkspacePreferenceError,
    activeWorkspace: workspaceContext.activeWorkspace,
    isAuthenticated: true,
    hasWorkspaceContext: Boolean(workspaceContext.activeWorkspace),
    contextError: workspaceContext.workspaceSelectionError,
    contextState:
      workspaceContext.workspaceSelectionState === 'workspace_selected'
        ? 'workspace_ready'
        : workspaceContext.workspaceSelectionState === 'workspace_selection_required'
          ? 'workspace_selection_required'
          : 'no_workspace_membership',
    workspaceSelectionState: workspaceContext.workspaceSelectionState,
    workspaceSelectionReason: workspaceContext.workspaceSelectionReason,
    workspaceSelectionRequired: workspaceContext.workspaceSelectionRequired,
    workspaceSelectionError: workspaceContext.workspaceSelectionError,
    researcherIdentity: {
      email: profile?.email ?? authContext.user.email ?? null,
      displayName: profile?.display_name ?? authContext.user.user_metadata?.full_name ?? authContext.user.email ?? 'Researcher',
      organizationName: profile?.organization_name ?? null,
    },
  }
}
