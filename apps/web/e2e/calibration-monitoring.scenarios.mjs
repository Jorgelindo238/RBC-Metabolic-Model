// Browser scenarios for Calibration / Monitoring (written, NOT executed by its author).
// Codex runs them against a dev server it starts itself:
//   BASE_URL=http://127.0.0.1:3000 node apps/web/e2e/calibration-monitoring.scenarios.mjs
// Uses the existing `playwright` dependency; no new package, no fixture injected in production:
// the reference profile shown is whatever the API really returns (available, missing, blocked...).
import { chromium } from 'playwright'
import { mkdir } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const BASE_URL = process.env.BASE_URL ?? 'http://127.0.0.1:3000'
const REQUIRE_LIVE_REGISTRY = process.env.REQUIRE_LIVE_REGISTRY === '1'
const SCREEN_DIR = process.env.SCREEN_DIR ?? join(tmpdir(), 'airbc-calibration-monitoring')
await mkdir(SCREEN_DIR, { recursive: true })
const VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'mobile', width: 390, height: 844 },
]

function check(condition, message) {
  if (!condition) throw new Error(message)
}

async function noHorizontalOverflow(page, label) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  check(overflow <= 1, `${label}: horizontal overflow of ${overflow}px`)
}

async function calibrationScenario(page, viewport) {
  await page.goto(`${BASE_URL}/research/parameter-calibration`, { waitUntil: 'networkidle' })
  const journey = page.getByTestId('calibration-journey')
  await journey.waitFor()
  for (const step of ['Data', 'Verification', 'Calibration', 'Results']) {
    check(await journey.getByText(step, { exact: true }).isVisible(), `${viewport.name}: step ${step} missing`)
  }
  const reference = page.getByTestId('reference-profile')
  await reference.waitFor()
  await page.waitForFunction(() => !document.querySelector('[data-testid="reference-profile"]')?.textContent?.includes('Loading registry'))
  const activate = page.getByTestId('reference-activate')
  if (await activate.count()) {
    check(await activate.isDisabled(), `${viewport.name}: reference activation is enabled`)
    await activate.click({ force: true }).catch(() => {})
    check(await activate.isDisabled(), `${viewport.name}: activation became enabled after a click`)
    check((await reference.textContent()).includes('Preview only'), 'preview label missing')
    check((await page.getByTestId('reference-limitations').textContent()).includes('ATP/ADP'), 'ATP/ADP limitation missing')
    const species = page.locator('#reference-species')
    await species.selectOption('EINO')
    await page.waitForFunction(() => document.querySelector('#reference-species')?.value === 'EINO')
    await page.getByRole('cell', { name: 'zero band', exact: true }).first().waitFor()
    await species.selectOption('EGLC')
  } else {
    // Clean installation without local archives: an explicit unavailable state, not an error page.
    const unavailable = page.getByTestId('reference-unavailable')
    check((await unavailable.count()) === 1, `${viewport.name}: neither a profile nor an unavailable state`)
  }
  const contractLaunch = page.getByTestId('contract-launch')
  if (await contractLaunch.count()) check(await contractLaunch.isDisabled(), 'contractual launch enabled without a qualified engine')
  check((await page.getByTestId('legacy-path-label').textContent()).includes('Legacy path'), 'legacy path not labelled')
  await noHorizontalOverflow(page, `${viewport.name} calibration`)
  await page.screenshot({ path: join(SCREEN_DIR, `calibration-${viewport.name}.png`), fullPage: true })
}

async function preflightScenario(page, viewport) {
  // Isolated browser-test data, never persisted to the application backend.
  await page.evaluate(() => localStorage.setItem('clawblood.research.activeDataset', JSON.stringify({
    datasetId: 'qa-contract-upload', label: 'QA sparse upload', source: 'custom_upload', mode: 'custom_user_data_mode',
    fileName: 'qa.csv', timePointCount: 3, metaboliteCount: 1, mappedMetaboliteCount: 1,
    timePoints: [2, 4, 8], mappedMetabolites: ['EGLC'], mappedSeriesByMetabolite: { EGLC: [25, 24, 22] },
    rawColumns: ['EGLC'], rawSeriesByColumn: { EGLC: [25, 24, 22] }, mappings: {}, preview: [], activatedAt: 'test-only',
  })))
  await page.reload({ waitUntil: 'networkidle' })
  const launch = page.getByTestId('contract-launch')
  await launch.waitFor()
  const response = page.waitForResponse(r => r.url().includes('/calibration/preflight') && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Check data contract' }).click()
  const reply = await response
  check(reply.ok(), 'preflight transport failed')
  const payload = reply.request().postDataJSON()
  check(payload.data_contract.dataset.dataset_id === 'qa-contract-upload', 'wrong dataset in preflight')
  check(payload.data_contract.initial_state === null && payload.data_contract.geometry === null, 'initialization or volume invented')
  const verdict = await reply.json()
  check(verdict.data_valid === false && verdict.launch_allowed === false, 'sparse unlabelled upload incorrectly launchable')
  await page.getByTestId('preflight-issues').waitFor()
  check(await launch.isDisabled(), 'contract launch enabled despite missing metadata')
  await noHorizontalOverflow(page, `${viewport.name} preflight`)
  await page.screenshot({ path: join(SCREEN_DIR, `preflight-${viewport.name}.png`), fullPage: true })
}

async function monitoringScenario(page, viewport) {
  await page.goto(`${BASE_URL}/monitoring`, { waitUntil: 'networkidle' })
  const text = await page.textContent('body')
  for (const forbidden of ['BAG-1042', 'DON-118', '96%', 'Seeded preview']) {
    check(!text.includes(forbidden), `${viewport.name}: fabricated monitoring content "${forbidden}"`)
  }
  const runs = page.getByTestId('monitoring-runs')
  await runs.waitFor()
  const states = await page.locator('[data-run-state]').count()
  const empty = await page.getByTestId('monitoring-empty').count()
  const error = await page.getByTestId('monitoring-error').count()
  if (REQUIRE_LIVE_REGISTRY) check(error === 0, `${viewport.name}: live registry read failed`)
  if (error) check((await page.locator('[data-metric="Runs"]').textContent()).includes('Unknown'), 'unavailable registry misreported as zero runs')
  check(states > 0 || empty === 1 || error === 1, `${viewport.name}: monitoring shows neither runs, empty nor error state`)
  const determinate = await page.locator('[data-progress="determinate"]').count()
  const running = await page.locator('[data-run-state="running"]').count()
  check(determinate <= running, 'determinate progress shown for a non-running record')
  await noHorizontalOverflow(page, `${viewport.name} monitoring`)
  await page.screenshot({ path: join(SCREEN_DIR, `monitoring-${viewport.name}.png`), fullPage: true })
}

const browser = await chromium.launch()
const failures = []
try {
  for (const viewport of VIEWPORTS) {
    const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height } })
    const page = await context.newPage()
    page.setDefaultNavigationTimeout(180000)
    page.setDefaultTimeout(45000)
    page.on('pageerror', error => failures.push(`${viewport.name}: ${error.message}`))
    const registryErrors = []
    page.on('console', message => {
      if (message.type() !== 'error') return
      const text = message.text()
      if (text.includes('Failed to load calibration_runs from Supabase:') && text.includes('TypeError: fetch failed')) {
        registryErrors.push(text)
      } else failures.push(`${viewport.name} console: ${text}`)
    })
    for (const scenario of [calibrationScenario, preflightScenario, monitoringScenario]) {
      try {
        await scenario(page, viewport)
        console.log(`PASS ${viewport.name} ${scenario.name}`)
      } catch (error) {
        failures.push(`${viewport.name} ${scenario.name}: ${error.message}`)
        console.log(`FAIL ${viewport.name} ${scenario.name}: ${error.message}`)
      }
    }
    if (registryErrors.length) {
      if (await page.getByTestId('monitoring-error').count() !== 1) {
        failures.push(`${viewport.name}: registry failure was not rendered explicitly`)
      } else console.log(`ENVIRONMENT ${viewport.name}: Supabase fetch failed; unavailable state verified`)
    }
    await context.close()
  }
} finally {
  await browser.close()
}
if (failures.length) {
  for (const failure of failures) console.error(failure)
  process.exitCode = 1
}
