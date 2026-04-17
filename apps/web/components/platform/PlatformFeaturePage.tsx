import { FeatureSelectionEmptyState } from './FeatureSelectionEmptyState'
import { WorkspaceFeatureSurface } from './WorkspaceFeatureSurface'
import { DatabaseUnreachableState, ErrorState } from '../ui/StatusStates.js'
import { getCalibrationRunByIdForServerRequest, getCalibrationRunsForServerRequest } from '../../lib/api/calibration-runs.mjs'
import {
  fetchMonitoringAlertWorkflowHistoryFromApi,
  fetchMonitoringAlertWorkflowStatesFromApi,
} from '../../lib/monitoring-alerts'
import { getPlatformFeatureSelection, getPlatformWorkspaceLabel } from '../../lib/platform-navigation.ts'

function buildDetailFields(detail: any): [string, unknown][] {
  if (!detail) {
    return []
  }

  return [
    ['Benchmark status', detail.summary.benchmarkStatus || detail.summary.status],
    ['Completion status', detail.summary.completionStatus],
    ['Time-aware score', detail.summary.timeAwareScore != null ? Number(detail.summary.timeAwareScore).toFixed(4) : null],
    ['Completed cases', detail.summary.completedCases != null && detail.summary.totalCases != null ? `${detail.summary.completedCases}/${detail.summary.totalCases}` : detail.summary.caseCount],
    ['Coverage ratio', detail.summary.coverageRatio != null ? `${Math.round(Number(detail.summary.coverageRatio) * 100)}%` : null],
    ['Coverage weight', detail.summary.coverageWeightRatio != null ? `${Math.round(Number(detail.summary.coverageWeightRatio) * 100)}%` : null],
    ['Elapsed seconds', detail.summary.elapsedSeconds != null ? `${Number(detail.summary.elapsedSeconds).toFixed(1)}s` : null],
    ['Time budget seconds', detail.summary.timeBudgetSeconds != null ? `${Number(detail.summary.timeBudgetSeconds).toFixed(1)}s` : null],
    ['Case budget seconds', detail.summary.caseTimeBudgetSeconds != null ? `${Number(detail.summary.caseTimeBudgetSeconds).toFixed(1)}s` : null],
    ['Stop reason', detail.summary.stopReason],
    ['Optimization strategy', detail.scientificContext.optimizationStrategy],
    ['Result summary', detail.summary.aggregateScore != null
      ? `${detail.summary.benchmarkStatus || detail.summary.status} • ${detail.summary.completionStatus || 'unknown'} • score ${Number(detail.summary.aggregateScore).toFixed(3)} • mean loss ${detail.summary.meanFinalLoss != null ? Number(detail.summary.meanFinalLoss).toFixed(3) : '—'} • ${detail.summary.meanImprovementPct != null ? Number(detail.summary.meanImprovementPct).toFixed(1) + '%' : '—'} improvement`
      : null],
    ['Best case', detail.summary.bestCase],
    ['Worst case', detail.summary.worstCase],
    ['Visibility', detail.productContext.visibility],
    ['Run origin', detail.productContext.runOrigin],
    ['Artifact manifest', detail.artifacts.manifestPath],
  ]
}

async function loadRegistryData() {
  const response = await getCalibrationRunsForServerRequest()
  const { access, data: runs, error, missingCredentials, productContext } = response

  if (missingCredentials || error) {
    return {
      access,
      detail: null,
      error,
      missingCredentials,
      productContext,
      runs: runs ?? [],
    }
  }

  const leadRun = runs?.[0] ?? null
  const detailResponse = leadRun ? await getCalibrationRunByIdForServerRequest(leadRun.runId) : null

  return {
    access,
    detail: detailResponse?.data ?? null,
    error: null,
    missingCredentials: false,
    productContext,
    runs: runs ?? [],
  }
}

async function loadAlertsData() {
  try {
    const [workflowStates, workflowHistory] = await Promise.all([
      fetchMonitoringAlertWorkflowStatesFromApi(),
      fetchMonitoringAlertWorkflowHistoryFromApi(50),
    ])

    return {
      workflowStates,
      workflowHistory,
    }
  } catch {
    return {
      workflowStates: [],
      workflowHistory: [],
    }
  }
}

export async function PlatformFeaturePage({
  featureId,
  subsectionId = null,
}: {
  featureId?: string | null
  subsectionId?: string | null
}) {
  const { feature, subsection } = getPlatformFeatureSelection(featureId, subsectionId)

  if (!feature) {
    return (
      <main className="page-shell">
        <FeatureSelectionEmptyState />
      </main>
    )
  }

  const registryData = feature.id === 'calibration-registry'
    ? await loadRegistryData()
    : {
        access: null,
        detail: null,
        error: null,
        missingCredentials: false,
        productContext: {},
        runs: [],
      }
  const alertsData = feature.id === 'alerts'
    ? await loadAlertsData()
    : {
        workflowStates: [],
        workflowHistory: [],
      }

  if (registryData.missingCredentials) {
    return <DatabaseUnreachableState />
  }

  if (registryData.error) {
    return <ErrorState error={registryData.error} />
  }

  return (
    <main className="page-shell">
      <WorkspaceFeatureSurface
        access={registryData.access}
        detail={registryData.detail}
        detailFields={buildDetailFields(registryData.detail)}
        feature={feature}
        alertsData={alertsData}
        productContext={registryData.productContext}
        runs={registryData.runs}
        subsection={subsection}
        workspaceLabel={getPlatformWorkspaceLabel(feature.id)}
      />
    </main>
  )
}
