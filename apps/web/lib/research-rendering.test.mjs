import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import vm from 'node:vm'
import ts from 'typescript'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

const require = createRequire(import.meta.url)

// Render the real TSX with explicit, isolated dependencies. No database, router,
// browser storage, model or API can execute in these server-rendering tests.
function loadTsx(relativePath, dependencies, extraExport = '') {
  const source = readFileSync(new URL(relativePath, import.meta.url), 'utf8')
  const output = ts.transpileModule(source + extraExport, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
  }).outputText
  const exports = {}
  vm.runInNewContext(output, {
    exports,
    require(id) {
      if (['react', 'react/jsx-runtime', 'lucide-react'].includes(id)) return require(id)
      if (Object.hasOwn(dependencies, id)) return dependencies[id]
      throw new Error(`Unmocked dependency: ${id}`)
    },
  }, { filename: fileURLToPath(new URL(relativePath, import.meta.url)) })
  return exports
}

const { WithInspector } = loadTsx('../components/platform/research/Inspector.tsx', {})
const inactiveFeatures = Object.fromEntries([
  '../features/SimulationWorkspace', '../features/FluxAnalysis', '../features/BagRepository',
  '../features/PathwayVisualization', '../features/QualityForecast', '../features/Alerts',
  '../features/ParameterCalibration', '../features/DataUpload', '../features/SensitivityAnalysis',
  './MonitoringWorkspaceLanding', './ResearchWorkspaceLanding', '@/lib/utils',
].map((id) => [id, {}]))
const { RegistrySurface } = loadTsx('../components/platform/WorkspaceFeatureContent.tsx', {
  ...inactiveFeatures,
  '@/contexts/ResearchContextProvider': { useResearchContext: () => ({ setContext() {} }) },
  '@/lib/robocop/research-context-builders': { buildCalibrationRegistryResearchContext: () => ({}) },
  './research/Inspector': { WithInspector },
  'next/link': ({ href, children, ...props }) => React.createElement('a', { href, ...props }, children),
}, '\nexport { RegistrySurface }\n')

function registry(props = {}) {
  return renderToStaticMarkup(React.createElement(RegistrySurface, { access: null, detail: null, runs: [], ...props }))
}

test('empty Results has no filters, counters or fabricated rows', () => {
  const html = registry()
  assert.match(html, /No calibration runs recorded yet/)
  assert.ok(!html.includes('Run outcome filter'))
  assert.ok(!html.includes('registry-table'))
  assert.ok(!html.includes('registry-summary'))
})

test('unavailable Results is explicit and offers Retry instead of zero runs', () => {
  const html = registry({ runsError: 'QA fixture: registry unreachable' })
  assert.match(html, /registry-error/)
  assert.match(html, /Retry/)
  assert.match(html, /not an empty registry/)
  assert.ok(!html.includes('registry-empty'))
})

test('populated Results preserves exact score and distinguishes completion from validation', () => {
  const html = registry({ runs: [{
    runId: 'qa-render-only', label: 'QA rendering fixture', benchmarkStatus: 'keep',
    completionStatus: 'completed', aggregateScore: 0.123456789, meanFinalLoss: 2.3456789,
    caseCount: 3, runTimestampUtc: '2026-11-13T00:00:00Z',
  }] })
  assert.match(html, /registry-table/)
  assert.match(html, /Completed \(unverified\)/)
  assert.match(html, /title="0.123456789"/)
  assert.match(html, /QA rendering fixture/)
  assert.ok(!html.includes('%'))
  assert.ok(!html.includes('registry-empty'))
})

const Surface = () => null
function loadFeaturePage(response) {
  return loadTsx('../components/platform/PlatformFeaturePage.tsx', {
    './FeatureSelectionEmptyState': { FeatureSelectionEmptyState: () => null },
    './WorkspaceFeatureSurface': { WorkspaceFeatureSurface: Surface },
    '../ui/StatusStates.js': { DatabaseUnreachableState: () => null, ErrorState: () => null },
    '../../lib/api/calibration-runs.mjs': {
      getCalibrationRunsForServerRequest: async () => response,
      getCalibrationRunByIdForServerRequest: async () => { throw new Error('No detail should be fetched') },
    },
    '../../lib/monitoring-alerts': {},
    '../../lib/platform-navigation.ts': {
      getPlatformFeatureSelection: () => ({ feature: { id: 'calibration-registry' }, subsection: null }),
      getPlatformWorkspaceLabel: () => 'Research',
    },
  }).PlatformFeaturePage
}

for (const response of [
  { data: [], missingCredentials: false, error: 'QA fixture: read failed' },
  { data: [], missingCredentials: true, error: null },
]) {
  test(`Results retains its Research shell for ${response.missingCredentials ? 'missing configuration' : 'read errors'}`, async () => {
    const Page = loadFeaturePage(response)
    const element = await Page({ featureId: 'calibration-registry' })
    assert.equal(element.props.children.type, Surface)
    assert.equal(element.props.children.props.runsError, response.error ?? 'Run registry is not configured.')
  })
}
