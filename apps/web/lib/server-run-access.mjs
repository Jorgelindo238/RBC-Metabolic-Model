function buildAccessDescriptor(mode, overrides = {}) {
  return {
    mode,
    scope: null,
    fallbackMode: null,
    error: null,
    workspaceSelectionRequired: false,
    ...overrides,
  }
}

export function isProductSchemaUnavailableError(error) {
  const message = error?.message || ''
  return /workspace_memberships|workspaces|profiles|column .*workspace_id|column .*created_by_user_id|column .*visibility|column .*active_workspace_id|column .*active_workspace_updated_at|relation .*does not exist|schema cache/i.test(message)
}

export function buildRunScopeFilter(scope) {
  if (!scope) {
    return null
  }

  if (scope.workspaceId) {
    return `visibility.eq.public,workspace_id.eq.${scope.workspaceId},created_by_user_id.eq.${scope.userId}`
  }

  if (scope.userId) {
    return `visibility.eq.public,created_by_user_id.eq.${scope.userId}`
  }

  return null
}

export function resolveServerRunAccess(productContext) {
  if (!productContext || productContext.missingCredentials) {
    return buildAccessDescriptor('credentials_missing')
  }

  if (productContext.authState === 'auth_error') {
    return buildAccessDescriptor('auth_error', {
      error: productContext.authError || 'Failed to verify authenticated user.',
    })
  }

  if (!productContext.isAuthenticated) {
    return buildAccessDescriptor('anonymous_public', {
      fallbackMode: 'public_read_model',
    })
  }

  if (productContext.contextState === 'product_context_error') {
    return buildAccessDescriptor('product_context_error', {
      error: productContext.contextError || 'Failed to resolve researcher workspace context.',
    })
  }

  if (productContext.contextState === 'product_schema_unavailable') {
    return buildAccessDescriptor('transitional_public_fallback', {
      fallbackMode: 'public_read_model',
      error: productContext.contextError || null,
    })
  }

  if (productContext.contextState === 'workspace_selection_required') {
    return buildAccessDescriptor('workspace_selection_required', {
      scope: {
        userId: productContext.user.id,
      },
      workspaceSelectionRequired: true,
      error: productContext.workspaceSelectionError || null,
    })
  }

  if (productContext.contextState === 'workspace_ready' && productContext.activeWorkspace?.id) {
    return buildAccessDescriptor('workspace_member', {
      scope: {
        workspaceId: productContext.activeWorkspace.id,
        userId: productContext.user.id,
      },
    })
  }

  return buildAccessDescriptor('authenticated_personal', {
    scope: {
      userId: productContext.user.id,
    },
  })
}
