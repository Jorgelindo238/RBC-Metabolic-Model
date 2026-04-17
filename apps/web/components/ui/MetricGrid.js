import { createElement as h } from 'react'
import { MetricCard } from './MetricCard.js'

/**
 * Render a series of [label, value] pairs as horizontal metric blocks.
 * Filters out items where the value explicitly resolves to null.
 */
export function MetricGrid({ metrics }) {
  if (!metrics || metrics.length === 0) return null

  const validMetrics = metrics.filter(([_, value]) => value !== null)
  if (validMetrics.length === 0) return null

  return h('div', { className: 'metric-grid' },
    validMetrics.map(([label, value]) => h(MetricCard, { label, value, key: label }))
  )
}
