import { createElement as h } from 'react'

function getBannerTone(access) {
  if (!access) return 'neutral'
  if (access.mode === 'transitional_public_fallback' || access.mode === 'product_context_error' || access.mode === 'auth_error' || access.mode === 'workspace_selection_required') return 'warning'
  if (access.mode === 'workspace_member') return 'success'
  if (access.mode === 'authenticated_personal') return 'accent'
  return 'neutral'
}

function getBannerTitle(access) {
  switch (access?.mode) {
    case 'workspace_member':
      return 'Workspace-scoped researcher access'
    case 'workspace_selection_required':
      return 'Workspace selection required'
    case 'authenticated_personal':
      return 'Authenticated personal access'
    case 'transitional_public_fallback':
      return 'Transitional public fallback active'
    case 'anonymous_public':
      return 'Anonymous public browse mode'
    case 'credentials_missing':
      return 'Supabase credentials unavailable'
    case 'auth_error':
      return 'Authenticated session verification failed'
    case 'product_context_error':
      return 'Research product context could not be resolved'
    default:
      return 'Research access context'
  }
}

function getBannerCopy(access, productContext) {
  const workspaceName = productContext?.activeWorkspace?.name || productContext?.activeWorkspace?.slug || 'active workspace'
  const preferenceQualifier =
    productContext?.workspaceSelectionReason === 'stored_preference_selected'
      ? 'The active workspace came from your durable stored preference.'
      : productContext?.workspaceSelectionReason === 'cookie_fallback_selected'
        ? 'The active workspace is currently using the transitional cookie fallback because no durable stored preference is available yet.'
        : productContext?.workspaceSelectionReason === 'single_membership_auto_selected'
          ? 'The active workspace was auto-selected because only one membership exists.'
          : productContext?.workspaceSelectionReason === 'stored_preference_invalid_single_membership_auto_selected'
            ? 'The stored preference was no longer valid, so the server recovered with the only remaining active membership.'
            : null

  switch (access?.mode) {
    case 'workspace_member':
      return `${preferenceQualifier ? `${preferenceQualifier} ` : ''}You are viewing runs through workspace membership and run ownership rules for ${workspaceName}. Public runs remain visible under the transitional model.`
    case 'workspace_selection_required':
      return 'Multiple active workspace memberships are available, but no valid durable active-workspace preference is available yet. The app is temporarily narrowing reads to personal and public visibility until a workspace is chosen.'
    case 'authenticated_personal':
      return 'You are signed in without an active workspace membership. The app now narrows reads to your own runs plus explicitly public runs instead of falling back to generic public browsing.'
    case 'transitional_public_fallback':
      return 'The verified SSR boundary is active, but product tables or linkage columns are not fully available in this environment. The app is temporarily using the legacy public read model.'
    case 'anonymous_public':
      return 'No verified researcher session was found. The app is reading only the public run surface.'
    case 'credentials_missing':
      return 'This environment does not have the Supabase credentials required to resolve authenticated researcher context.'
    case 'auth_error':
      return 'The server could not verify the current user with Supabase Auth, so researcher-scoped access could not be applied.'
    case 'product_context_error':
      return 'The user session is valid, but the product-layer context could not be resolved safely enough to continue.'
    default:
      return 'The app is resolving researcher identity, workspace context, and run visibility on the server.'
  }
}

export function AccessContextBanner({ access, productContext }) {
  return h('section', { className: `access-banner tone-${getBannerTone(access)}` }, [
    h('div', { className: 'access-banner-copy', key: 'copy' }, [
      h('p', { className: 'access-banner-kicker', key: 'kicker' }, 'Authenticated product layer'),
      h('h3', { className: 'access-banner-title', key: 'title' }, getBannerTitle(access)),
      h('p', { className: 'access-banner-text', key: 'text' }, getBannerCopy(access, productContext)),
    ]),
    h('div', { className: 'access-banner-meta', key: 'meta' }, [
      h('span', { className: 'access-banner-chip', key: 'mode' }, access?.mode || 'unknown'),
      access?.fallbackMode ? h('span', { className: 'access-banner-chip access-banner-chip-muted', key: 'fallback' }, `fallback: ${access.fallbackMode}`) : null,
    ].filter(Boolean)),
  ])
}
