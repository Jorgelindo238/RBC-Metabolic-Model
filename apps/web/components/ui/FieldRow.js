import { createElement as h } from 'react'
import { formatValue } from './format.js'

/**
 * A standard label/value row for dictionary lists.
 */
export function FieldRow({ label, value }) {
  return h('div', { className: 'field-row', key: label }, [
    h('dt', { className: 'field-label', key: 'label' }, label),
    h('dd', { className: 'field-value', key: 'value' }, formatValue(value)),
  ])
}
