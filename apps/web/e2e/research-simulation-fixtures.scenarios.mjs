// UI-only response fixtures. The browser intercepts every simulation request;
// nothing reaches the ODE, and each viewport uses disposable browser storage.
import { chromium } from 'playwright'
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const BASE = process.env.BASE_URL ?? 'http://127.0.0.1:3100'
const DIR = join(tmpdir(), 'airbc-research-redesign')
await mkdir(DIR, { recursive: true })
const result = {
  success: true, duration: 0.01, t: [1, 4, 15],
  metabolite_names: ['EGLC', 'ELAC', 'ATP', 'ADP', 'AMP', 'GLC', 'PEP'],
  x: [[25, 3, 1, 0.3, 0.1, 1.1, 0.15], [24, 4, 0.8, 0.4, 0.2, 1.1, 0.1], [22, 6, 0.6, 0.5, 0.3, 1.1, 0.05]],
  n_points: 3, n_metabolites: 7, solver: 'QA fixture (not integrated)',
  custom_params_source: 'auto_loaded', dataset_applied: false,
  active_dataset_label: 'QA response fixture; not scientific evidence',
  log: ['[QA] Browser-only fixture. No ODE was executed.'],
}
const browser = await chromium.launch()
try {
  for (const width of [1440, 390, 320]) {
    const context = await browser.newContext({ viewport: { width, height: 900 } })
    let intercepted = 0
    let fail = false
    let release
    let payload
    const errors = []
    await context.route('**/api/**', async (route) => {
      const request = route.request()
      const path = new URL(request.url()).pathname
      if (request.method() === 'POST' && path.startsWith('/api/simulate/')) {
        intercepted++
        payload = request.postDataJSON()
        await new Promise((resolve) => { release = resolve })
        await route.fulfill({ status: fail ? 500 : 200, json: fail ? { detail: 'QA fixture: solver service unavailable' } : result })
      } else if (request.method() === 'POST' && /\/calibration\/(run|start|optimize|jobs)/.test(path)) {
        errors.push('Unexpected calibration request')
        await route.abort()
      } else await route.continue()
    })
    const page = await context.newPage()
    page.setDefaultTimeout(45000)
    page.on('pageerror', (error) => errors.push(error.message))
    page.on('console', (message) => {
      if (message.type() === 'error' && !(fail && message.text().includes('500 (Internal Server Error)'))) errors.push(message.text())
    })
    await page.goto(`${BASE}/research/simulation`, { waitUntil: 'networkidle', timeout: 180000 })
    await page.getByTestId('simulation-empty').waitFor()
    await page.getByRole('button', { name: 'Run Simulation', exact: true }).click()
    await page.getByRole('button', { name: 'Running...', exact: true }).waitFor()
    assert.ok(await page.getByRole('button', { name: 'Running...', exact: true }).isDisabled())
    assert.equal(intercepted, 1)
    assert.equal(payload.solver_method, 'RK45')
    assert.equal(payload.custom_params, null)
    assert.equal(payload.active_dataset, null)
    release()
    await page.getByTestId('simulation-summary').waitFor()
    assert.match(await page.getByTestId('simulation-summary').innerText(), /QA fixture \(not integrated\)/)
    assert.ok(await page.locator('#trajectory-review svg').count() > 0, 'Fixture chart is blank')
    await page.getByRole('button', { name: 'Run details', exact: true }).click()
    await page.getByTestId('simulation-provenance').waitFor()
    assert.match(await page.getByTestId('simulation-provenance').innerText(), /model trajectory, not a biological validation/)
    assert.match(await page.getByTestId('simulation-provenance').innerText(), /Parameters auto-loaded by the engine/)
    await page.keyboard.press('Escape')
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth <= 1), `populated overflow at ${width}`)
    await page.screenshot({ path: join(DIR, `simulation-fixture-${width}.png`), fullPage: false, caret: 'initial' })
    fail = true
    const before = await page.getByRole('slider').first().getAttribute('aria-valuenow')
    await page.getByRole('button', { name: 'Run Simulation', exact: true }).click()
    await page.getByRole('button', { name: 'Running...', exact: true }).waitFor()
    assert.equal(intercepted, 2)
    release()
    await page.getByTestId('simulation-error').waitFor()
    assert.match(await page.getByTestId('simulation-error').innerText(), /QA fixture: solver service unavailable/)
    assert.equal(await page.getByRole('slider').first().getAttribute('aria-valuenow'), before)
    assert.equal(await page.getByTestId('simulation-summary').count(), 0)
    assert.deepEqual(errors, [])
    console.log(`PASS ${width}: intercepted loading, populated chart, provenance and recoverable error; zero ODE calls`)
    await context.close()
  }
} finally {
  await browser.close()
}
