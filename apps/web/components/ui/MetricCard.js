import { createElement as h } from 'react'
import { formatValue } from './format.js'

/**
 * A styled card for prominent numeric or string metrics.
 */
export function MetricCard({ label, value }) {
  return h('article', { className: 'metric-card', key: label }, [
    h('span', { className: 'metric-label', key: 'label' }, label),
    h('strong', { className: 'metric-value', key: 'value' }, formatValue(value)),
  ])
}
