import { NextResponse } from 'next/server'
import { getServerAuthContext } from '../../../lib/server-auth.mjs'
import { isProductSchemaUnavailableError } from '../../../lib/server-run-access.mjs'
import { getActiveWorkspaceMemberships, persistActiveWorkspacePreference } from '../../../lib/server-workspace-preference.mjs'
import { ACTIVE_WORKSPACE_COOKIE } from '../../../lib/server-workspace-context.mjs'

function normalizeRedirectPath(redirectTo) {
  if (!redirectTo || !redirectTo.startsWith('/') || redirectTo.startsWith('//')) {
    return '/'
  }

  return redirectTo
}

function applyWorkspaceCookie(response, requestUrl, workspaceId) {
  if (workspaceId) {
    response.cookies.set({
      name: ACTIVE_WORKSPACE_COOKIE,
      value: workspaceId,
      path: '/',
      httpOnly: true,
      sameSite: 'lax',
      secure: requestUrl.protocol === 'https:',
      maxAge: 60 * 60 * 24 * 30,
    })
    return
  }

  response.cookies.delete(ACTIVE_WORKSPACE_COOKIE)
}

function hasWorkspaceMembership(workspaceId, memberships) {
  return (memberships || []).some(membership => {
    const membershipWorkspaceId = membership.workspace_id ?? membership.workspace?.id ?? null
    return membershipWorkspaceId === workspaceId
  })
}

export async function GET(request) {
  const requestUrl = new URL(request.url)
  const workspaceId = requestUrl.searchParams.get('workspaceId')
  const redirectTo = normalizeRedirectPath(requestUrl.searchParams.get('redirectTo'))
  const response = NextResponse.redirect(new URL(redirectTo, request.url))
  const authContext = await getServerAuthContext()

  if (!authContext?.isAuthenticated || !authContext?.supabase) {
    applyWorkspaceCookie(response, requestUrl, workspaceId)
    return response
  }

  if (!workspaceId) {
    const { error } = await persistActiveWorkspacePreference(authContext.supabase, authContext.user.id, null)
    if (!error || isProductSchemaUnavailableError(error)) {
      applyWorkspaceCookie(response, requestUrl, null)
      return response
    }

    applyWorkspaceCookie(response, requestUrl, null)
    return response
  }

  const { data: memberships, error: membershipError } = await getActiveWorkspaceMemberships(
    authContext.supabase,
    authContext.user.id
  )

  if (!membershipError && !hasWorkspaceMembership(workspaceId, memberships || [])) {
    applyWorkspaceCookie(response, requestUrl, null)
    return response
  }

  const { error: updateError } = await persistActiveWorkspacePreference(
    authContext.supabase,
    authContext.user.id,
    workspaceId
  )

  if (updateError && !isProductSchemaUnavailableError(updateError) && !membershipError) {
    applyWorkspaceCookie(response, requestUrl, workspaceId)
    return response
  }

  applyWorkspaceCookie(response, requestUrl, workspaceId)
  return response
}
