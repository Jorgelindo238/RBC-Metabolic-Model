import { createElement as h } from 'react'
import Link from 'next/link'
import { formatValue } from './format.js'

function formatNumericValue(value, digits = 3) {
  if (value === null || value === undefined || value === '') {
    return '—'
  }

  const numericValue = Number(value)
  if (Number.isNaN(numericValue)) {
    return formatValue(value)
  }

  if (Number.isInteger(numericValue)) {
    return String(numericValue)
  }

  return numericValue.toFixed(digits)
}

function formatPercentValue(value, digits = 1) {
  if (value === null || value === undefined || value === '') {
    return '—'
  }

  const numericValue = Number(value)
  if (Number.isNaN(numericValue)) {
    return formatValue(value)
  }

  return `${numericValue >= 0 ? '+' : ''}${numericValue.toFixed(digits)}%`
}

function formatDurationValue(value) {
  if (value === null || value === undefined || value === '') {
    return '—'
  }

  const numericValue = Number(value)
  if (Number.isNaN(numericValue)) {
    return formatValue(value)
  }

  if (numericValue >= 60) {
    return `${numericValue.toFixed(1)}s`
  }

  return `${numericValue.toFixed(2)}s`
}

function normalizeStatusLabel(value) {
  if (!value) {
    return 'Unknown'
  }

  return String(value).replace(/_/g, ' ')
}

function getBenchmarkTone(status) {
  switch (String(status || '').toLowerCase()) {
    case 'baseline':
      return 'border-cyan-400/20 bg-cyan-400/10 text-cyan-100'
    case 'keep':
      return 'border-emerald-400/20 bg-emerald-400/10 text-emerald-100'
    case 'discard':
      return 'border-rose-400/20 bg-rose-400/10 text-rose-100'
    case 'not_comparable':
    case 'partial':
      return 'border-amber-400/20 bg-amber-400/10 text-amber-100'
    case 'timed_out':
      return 'border-orange-400/20 bg-orange-400/10 text-orange-100'
    case 'crashed':
      return 'border-red-400/20 bg-red-400/10 text-red-100'
    default:
      return 'border-slate-400/20 bg-slate-400/10 text-slate-100'
  }
}

function getCompletionTone(status) {
  switch (String(status || '').toLowerCase()) {
    case 'completed':
      return 'border-emerald-400/20 bg-emerald-400/10 text-emerald-100'
    case 'partial':
      return 'border-amber-400/20 bg-amber-400/10 text-amber-100'
    case 'timed_out':
      return 'border-orange-400/20 bg-orange-400/10 text-orange-100'
    case 'crashed':
      return 'border-rose-400/20 bg-rose-400/10 text-rose-100'
    default:
      return 'border-slate-400/20 bg-slate-400/10 text-slate-100'
  }
}

export function RunCard({ run }) {
  const benchmarkStatus = run.benchmarkStatus || run.status || 'unknown'
  const completionStatus = run.completionStatus || 'completed'
  const scopeLabel = [run.targetScope, run.paramScope].filter(Boolean).join(' · ')
  const caseLabel = run.completedCases != null && run.totalCases != null
    ? `${run.completedCases}/${run.totalCases} cases`
    : run.caseCount != null
      ? `${run.caseCount} cases`
      : '—'
  const coverageLabel = run.coverageRatio != null
    ? `${Math.round(Number(run.coverageRatio) * 100)}% coverage`
    : null

  const metricTiles = [
    [
      'Benchmark score',
      formatNumericValue(run.aggregateScore),
      'Lower is better',
    ],
    [
      'Mean final loss',
      formatNumericValue(run.meanFinalLoss),
      'Benchmark loss',
    ],
    [
      'Time-aware score',
      formatNumericValue(run.timeAwareScore),
      'Balances runtime and coverage',
    ],
    [
      'Cases',
      caseLabel,
      coverageLabel || 'Visible evidence set',
    ],
  ]

  const metaChips = [
    run.optimizationStrategy,
    scopeLabel || null,
    run.timeAwareScore != null ? `Time-aware ${formatNumericValue(run.timeAwareScore)}` : null,
    run.meanImprovementPct != null ? `Improvement ${formatPercentValue(run.meanImprovementPct)}` : null,
    run.elapsedSeconds != null ? `Runtime ${formatDurationValue(run.elapsedSeconds)}` : null,
  ].filter(Boolean)

  const provenanceLine = [
    `Status ${normalizeStatusLabel(completionStatus)}`,
    `Benchmark ${normalizeStatusLabel(benchmarkStatus)}`,
    run.optimizationStrategy || null,
    run.meanImprovementPct != null ? `Improvement ${formatPercentValue(run.meanImprovementPct)}` : null,
  ].filter(Boolean).join(' · ')

  return h('article', { className: 'rounded-3xl border border-white/10 bg-slate-950/70 p-5 shadow-[0_24px_60px_-36px_rgba(0,0,0,0.78)] backdrop-blur-sm' }, [
    h('div', { className: 'flex flex-wrap items-start justify-between gap-4', key: 'header' }, [
      h('div', { className: 'min-w-0 flex-1', key: 'title-group' }, [
        h('div', { className: 'flex flex-wrap items-center gap-3', key: 'labels' }, [
          h('strong', { className: 'truncate text-lg font-semibold text-white', key: 'label' }, formatValue(run.label)),
          h('span', { className: 'rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-400', key: 'id' }, formatValue(run.runId)),
        ]),
        h('p', { className: 'mt-2 text-sm leading-6 text-slate-400', key: 'copy' }, `${formatValue(run.policyName)} · ${scopeLabel || 'Scope not recorded'}`),
        h('p', { className: 'mt-2 text-xs leading-5 text-cyan-100/70', key: 'provenance' }, provenanceLine),
      ]),
      h('div', { className: 'flex flex-wrap gap-2', key: 'status-group' }, [
        h('span', { className: `inline-flex items-center rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] ${getBenchmarkTone(benchmarkStatus)}`, key: 'benchmark' }, normalizeStatusLabel(benchmarkStatus)),
        h('span', { className: `inline-flex items-center rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] ${getCompletionTone(completionStatus)}`, key: 'completion' }, normalizeStatusLabel(completionStatus)),
      ]),
    ]),
    h('div', { className: 'mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4', key: 'metrics' }, metricTiles.map(([label, value, note]) => (
      h('div', { className: 'rounded-2xl border border-white/10 bg-white/[0.03] p-4', key: label }, [
        h('p', { className: 'text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500', key: 'label' }, label),
        h('p', { className: 'mt-2 text-lg font-semibold text-white', key: 'value' }, value),
        h('p', { className: 'mt-1 text-xs leading-5 text-slate-400', key: 'note' }, note),
      ])
    ))),
    h('div', { className: 'mt-4 flex flex-wrap gap-2', key: 'chips' }, metaChips.map((chip) => (
      h('span', { className: 'inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs font-medium text-slate-300', key: chip }, chip)
    ))),
    h('div', { className: 'mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-4', key: 'actions' }, [
      h('div', { className: 'text-xs leading-5 text-slate-400', key: 'meta' }, [
        `Recorded ${formatValue(run.runTimestampUtc || run.recordedAt)} · `,
        `Visibility ${formatValue(run.productContext?.visibility)} · `,
        `Origin ${formatValue(run.productContext?.runOrigin)}`,
      ]),
      h(Link, { href: `/runs/${run.runId}`, className: 'link-button', key: `link-${run.runId}` }, 'Inspect run details →'),
    ]),
  ])
}
