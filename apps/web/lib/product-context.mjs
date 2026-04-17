export const RUN_PRODUCT_CONTEXT_FIELDS = Object.freeze([
  'workspace_id',
  'created_by_user_id',
  'agent_session_id',
  'visibility',
  'run_origin',
])

export function buildCalibrationRunProductContext(row) {
  if (!row) {
    return {
      workspaceId: null,
      createdByUserId: null,
      agentSessionId: null,
      visibility: null,
      runOrigin: null,
    }
  }

  return {
    workspaceId: row.workspace_id ?? null,
    createdByUserId: row.created_by_user_id ?? null,
    agentSessionId: row.agent_session_id ?? null,
    visibility: row.visibility ?? null,
    runOrigin: row.run_origin ?? null,
  }
}
