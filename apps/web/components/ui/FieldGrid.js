import { createElement as h } from 'react'
import { FieldRow } from './FieldRow.js'

/**
 * A dictionary list grid mapping over pairs of [label, value].
 */
export function FieldGrid({ fields }) {
  if (!fields || fields.length === 0) return null

  return h('dl', { className: 'field-grid' }, 
    fields.map(([label, value]) => h(FieldRow, { label, value, key: label }))
  )
}
