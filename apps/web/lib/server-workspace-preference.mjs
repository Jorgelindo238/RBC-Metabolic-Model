export const ACTIVE_WORKSPACE_PROFILE_FIELDS = 'id, active_workspace_id, active_workspace_updated_at'

export const ACTIVE_WORKSPACE_MEMBERSHIP_SELECT = 'workspace_id, membership_role, membership_status, joined_at, workspace:workspaces(id, slug, name)'

export async function getActiveWorkspaceMemberships(supabase, userId) {
  return supabase
    .from('workspace_memberships')
    .select(ACTIVE_WORKSPACE_MEMBERSHIP_SELECT)
    .eq('user_id', userId)
    .eq('membership_status', 'active')
    .order('joined_at', { ascending: true })
    .limit(5)
}

export async function persistActiveWorkspacePreference(supabase, userId, workspaceId) {
  const now = new Date().toISOString()

  return supabase
    .from('profiles')
    .update({
      active_workspace_id: workspaceId || null,
      active_workspace_updated_at: now,
      updated_at: now,
    })
    .eq('id', userId)
    .select(ACTIVE_WORKSPACE_PROFILE_FIELDS)
    .single()
}
