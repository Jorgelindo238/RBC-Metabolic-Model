import { createElement as h } from 'react'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { getCalibrationRunByIdForServerRequest } from '../../../lib/api/calibration-runs.mjs'
import { AccessContextBanner } from '../../../components/platform/AccessContextBanner.js'
import { ResearcherContextPanel } from '../../../components/platform/ResearcherContextPanel.js'
import { WorkspaceContextPanel } from '../../../components/platform/WorkspaceContextPanel.js'
import { DatabaseUnreachableState, ErrorState } from '../../../components/ui/StatusStates.js'
import { MetricGrid } from '../../../components/ui/MetricGrid.js'
import { FieldGrid } from '../../../components/ui/FieldGrid.js'
import { formatValue } from '../../../components/ui/format.js'

export default async function Page({ params }) {
  const { runId } = await params
  const response = await getCalibrationRunByIdForServerRequest(runId)
  const { data: detail, error, missingCredentials, productContext, access } = response

  if (missingCredentials) {
    return h(DatabaseUnreachableState, { showBackLink: true })
  }

  if (error) {
    return h(ErrorState, { error, showBackLink: true })
  }

  if (!detail) {
    notFound()
  }

  const summaryFields = [
    ['Recorded at', detail.summary.recordedAt],
    ['Run timestamp (UTC)', detail.summary.runTimestampUtc],
    ['Best case', detail.summary.bestCase],
    ['Worst case', detail.summary.worstCase],
  ]
  const benchmarkFields = [
    ['Benchmark status', detail.summary.benchmarkStatus || detail.summary.status],
    ['Completion status', detail.summary.completionStatus],
    ['Time-aware score', detail.summary.timeAwareScore != null ? Number(detail.summary.timeAwareScore).toFixed(4) : null],
    ['Completed cases', detail.summary.completedCases != null && detail.summary.totalCases != null ? `${detail.summary.completedCases}/${detail.summary.totalCases}` : detail.summary.caseCount],
    ['Coverage ratio', detail.summary.coverageRatio != null ? `${Math.round(Number(detail.summary.coverageRatio) * 100)}%` : null],
    ['Coverage weight ratio', detail.summary.coverageWeightRatio != null ? `${Math.round(Number(detail.summary.coverageWeightRatio) * 100)}%` : null],
    ['Elapsed seconds', detail.summary.elapsedSeconds != null ? `${Number(detail.summary.elapsedSeconds).toFixed(1)}s` : null],
    ['Time budget seconds', detail.summary.timeBudgetSeconds != null ? `${Number(detail.summary.timeBudgetSeconds).toFixed(1)}s` : null],
    ['Case budget seconds', detail.summary.caseTimeBudgetSeconds != null ? `${Number(detail.summary.caseTimeBudgetSeconds).toFixed(1)}s` : null],
    ['Stop reason', detail.summary.stopReason],
  ]
  const scientificFields = [
    ['Policy', detail.scientificContext.policyName],
    ['Manifest', detail.scientificContext.manifestName],
    ['Optimization strategy', detail.scientificContext.optimizationStrategy],
    ['Target scopes', detail.scientificContext.targetScopes],
    ['Param scopes', detail.scientificContext.paramScopes],
  ]
  const productFields = [
    ['Visibility', detail.productContext.visibility],
    ['Run origin', detail.productContext.runOrigin],
    ['Workspace id', detail.productContext.workspaceId],
    ['Created by user', detail.productContext.createdByUserId],
    ['Agent session', detail.productContext.agentSessionId],
  ]
  const metrics = [
    ['Aggregate score', detail.summary.aggregateScore !== null ? Number(detail.summary.aggregateScore).toFixed(4) : null],
    ['Mean final loss', detail.summary.meanFinalLoss !== null ? Number(detail.summary.meanFinalLoss).toFixed(4) : null],
    ['Improvement', detail.summary.meanImprovementPct !== null ? `${Number(detail.summary.meanImprovementPct).toFixed(2)}%` : null],
    ['Case count', detail.summary.caseCount],
  ]

  const artifactFields = [
    ['Completed manifest', detail.artifacts?.refs?.completed_run_manifest_path],
    ['Eval summary', detail.artifacts?.refs?.eval_summary_path],
    ['Policy snapshot', detail.artifacts?.refs?.policy_snapshot_path],
    ['Manifest snapshot', detail.artifacts?.refs?.manifest_snapshot_path],
    ['Case refs', detail.artifacts?.refs?.case_refs?.length],
  ]

  const assistantFields = [
    ['Assistant label', detail.robocopContext?.chatContext?.assistant],
    ['Trace tags', detail.robocopContext?.traceContext?.tags],
  ]

  return h('main', { className: 'page-shell' }, [
    h(AccessContextBanner, { access, productContext, key: 'access-banner' }),
    h('section', { className: 'panel', key: 'header' }, [
      h(Link, { href: '/', className: 'back-link', key: 'back' }, '← Back to research overview'),
      h('p', { className: 'eyebrow', key: 'eyebrow' }, 'Calibration registry detail'),
      h('h1', { className: 'page-title', key: 'title', style: { marginBottom: '16px' } }, formatValue(detail.summary.label)),
      h('div', { style: { display: 'flex', gap: '12px', marginBottom: '24px', flexWrap: 'wrap' }, key: 'meta' }, [
        h('span', { className: `status-pill status-${(detail.summary.status || 'unknown').toLowerCase()}`, key: 'status' }, formatValue(detail.summary.status)),
        h('span', { className: `status-pill status-${(detail.summary.completionStatus || 'unknown').toLowerCase()}`, key: 'completion' }, formatValue(detail.summary.completionStatus)),
        h('span', { style: { color: '#64748b', fontSize: '0.9rem', alignSelf: 'center', fontFamily: 'monospace' }, key: 'id' }, `ID: ${detail.summary.runId}`),
      ]),
      h(MetricGrid, { metrics, key: 'metrics' }),
    ]),
    h('div', { className: 'dashboard-grid', key: 'context-grid' }, [
      h(ResearcherContextPanel, {
        productContext,
        access,
        visibleRunCount: 1,
        key: 'researcher-context',
      }),
      h(WorkspaceContextPanel, {
        productContext,
        redirectTo: `/runs/${encodeURIComponent(runId)}`,
        key: 'workspace-context',
      }),
    ]),
    h('div', { className: 'dashboard-grid', key: 'product-grid' }, [
      h('section', { className: 'panel', key: 'product-context' }, [
        h('div', { className: 'panel-heading', key: 'heading' }, [
          h('h2', { key: 'title' }, 'Product context'),
          h('p', { key: 'copy' }, 'These fields connect the visible run back to researcher identity, workspace scope, and future RoBoCop session context.'),
        ]),
        h(FieldGrid, { fields: productFields, key: 'fields' }),
      ]),
      h('section', { className: 'panel', key: 'workspace-visibility' }, [
        h('div', { className: 'panel-heading', key: 'heading' }, [
          h('h2', { key: 'title' }, 'Workspace visibility'),
          h('p', { key: 'copy' }, 'This detail view remains downstream of the resolved workspace context, personal visibility, and transitional fallback rules.'),          
        ]),
        h(FieldGrid, {
          fields: [
            ['Access mode', access?.mode],
            ['Workspace selection state', productContext?.workspaceSelectionState],
            ['Active workspace', productContext?.activeWorkspace?.name || productContext?.activeWorkspace?.slug],
            ['Selection reason', productContext?.workspaceSelectionReason],
          ],
          key: 'visibility-fields',
        }),
      ]),
    ]),
    h('section', { className: 'panel', key: 'benchmark' }, [
      h('div', { className: 'panel-heading', key: 'heading' }, [
        h('h2', { key: 'title' }, 'Benchmark context'),
        h('p', { key: 'copy' }, 'Grouped metrics and runtime context for this historical calibration record. Lower benchmark scores indicate stronger evidence.'),
      ]),
      h(FieldGrid, { fields: benchmarkFields, key: 'fields' }),
    ]),
    h('section', { className: 'panel', key: 'summary' }, [
      h('div', { className: 'panel-heading', key: 'heading' }, [
        h('h2', { key: 'title' }, 'Summary'),
        h('p', { key: 'copy' }, 'Contract-driven scalar fields for the primary detail header.'),
      ]),
      h(FieldGrid, { fields: summaryFields, key: 'fields' }),
    ]),
    h('section', { className: 'panel', key: 'scientific' }, [
      h('div', { className: 'panel-heading', key: 'heading' }, [
        h('h2', { key: 'title' }, 'Scientific context'),
        h('p', { key: 'copy' }, 'Downstream read of policy/scope context already prepared by the persistence contract.'),
      ]),
      h(FieldGrid, { fields: scientificFields, key: 'fields' }),
    ]),
    h('section', { className: 'panel', key: 'artifacts' }, [
      h('div', { className: 'panel-heading', key: 'heading' }, [
        h('h2', { key: 'title' }, 'Artifacts and RoBoCop context'),
        h('p', { key: 'copy' }, 'Shows where the evidence lives. For interactive calibration chat, open the Parameter Calibration result flow, which feeds RoBoCop the full calibration research context.'),
      ]),
      h(FieldGrid, { fields: artifactFields, key: 'artifact-fields' }),
      h(FieldGrid, { fields: assistantFields, key: 'assistant-fields' }),
      h('div', { className: 'mt-4 flex justify-end', key: 'calibration-link' }, [
        h(Link, { href: '/research/parameter-calibration', className: 'link-button', key: 'link' }, 'Open calibration flow →'),
      ]),
    ]),
  ])
}
