import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { buildRunScopeFilter, resolveServerRunAccess } from './server-run-access.mjs'

test('missing workspace schema preserves authenticated personal access', () => {
  const access = resolveServerRunAccess({
    isAuthenticated: true,
    user: { id: 'owner-id' },
    contextState: 'product_schema_unavailable',
    contextError: 'profiles not in schema cache',
  })
  assert.equal(access.mode, 'authenticated_personal')
  assert.deepEqual(access.scope, { userId: 'owner-id' })
  assert.equal(access.fallbackMode, 'workspace_schema_unavailable')
  assert.equal(buildRunScopeFilter(access.scope), 'visibility.eq.public,created_by_user_id.eq.owner-id')
})

test('anonymous callers stay public and authentication errors fail closed', () => {
  assert.equal(resolveServerRunAccess({ isAuthenticated: false }).mode, 'anonymous_public')
  assert.equal(resolveServerRunAccess({ isAuthenticated: false, authState: 'auth_error' }).mode, 'auth_error')
  assert.equal(resolveServerRunAccess({ missingCredentials: true }).mode, 'credentials_missing')
})

test('workspace selection and personal fallback remain scoped', () => {
  const user = { id: 'owner-id' }
  const choosing = resolveServerRunAccess({ isAuthenticated: true, user, contextState: 'workspace_selection_required' })
  assert.equal(choosing.workspaceSelectionRequired, true)
  assert.deepEqual(choosing.scope, { userId: user.id })
  const selected = resolveServerRunAccess({ isAuthenticated: true, user, contextState: 'workspace_ready', activeWorkspace: { id: 'workspace-id' } })
  assert.equal(selected.mode, 'workspace_member')
  assert.deepEqual(selected.scope, { workspaceId: 'workspace-id', userId: user.id })
})

test('registry migration includes every current list column and denies browser writes', () => {
  const migration = readFileSync(new URL('../../../supabase/migrations/20261113005444_calibration_run_registry.sql', import.meta.url), 'utf8')
  const reader = readFileSync(new URL('./api/calibration-runs.mjs', import.meta.url), 'utf8')
  const select = reader.match(/const CALIBRATION_RUNS_LIST_SELECT = `([\s\S]*?)`/)[1]
  for (const column of select.split(',').map((s) => s.trim())) {
    assert.match(migration, new RegExp(`\\b${column}\\s+(?:text|integer|double precision|timestamptz|uuid|jsonb)\\b`))
  }
  assert.match(migration, /enable row level security/)
  assert.match(migration, /revoke all on public\.calibration_runs from public, anon, authenticated/)
  assert.match(migration, /grant select on public\.calibration_runs to anon, authenticated/)
  assert.doesNotMatch(migration, /grant (?:all|insert|update|delete) on public\.calibration_runs to (?:anon|authenticated)/)
  assert.doesNotMatch(migration, /security definer/i)
})
