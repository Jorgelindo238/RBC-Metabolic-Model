/**
 * Formats a value for display in the UI.
 * Handles arrays, nulls, and basic strings cleanly.
 */
export function formatValue(value) {
  if (Array.isArray(value)) {
    return value.length ? value.join(', ') : '—'
  }

  if (value === null || value === undefined || value === '') {
    return '—'
  }

  return String(value)
}
