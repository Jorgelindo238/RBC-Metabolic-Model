import { chromium } from 'playwright'
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const BASE = process.env.BASE_URL ?? 'http://127.0.0.1:3100'
const DIR = join(tmpdir(), 'airbc-research-redesign')
await mkdir(DIR, { recursive: true })
const ROUTES = [
  ['', 'Research'], ['data-upload', 'Data Upload'], ['parameter-calibration', 'Calibration'],
  ['simulation', 'Simulation'], ['flux-analysis', 'Flux Analysis'],
  ['pathway-visualization', 'Pathway Map'], ['calibration-registry', 'Results'],
]
const errors = []

// Shared inspector: opens with focus inside, no page overflow, Escape closes and returns focus to its trigger.
async function checkInspector(page, title, testId, device, slug) {
  const trigger = page.getByRole('button', { name: title, exact: true })
  await trigger.click()
  const aside = page.getByRole('complementary', { name: title })
  await aside.waitFor()
  await page.getByTestId(testId).waitFor()
  assert.ok(await aside.evaluate((node) => node.contains(document.activeElement)), `${device}/${slug}: focus not moved into ${title}`)
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth <= 1), `${device}/${slug}: overflow with ${title} open`)
  await page.keyboard.press('Escape')
  await aside.waitFor({ state: 'detached' })
  assert.ok(await trigger.evaluate((node) => node === document.activeElement), `${device}/${slug}: focus not returned after Escape`)
}

// Values must be fully readable: no text cut by its box.
async function assertNoClippedValues(page, selector, label) {
  const clipped = await page.locator(selector).evaluateAll((nodes) =>
    nodes.filter((node) => node.scrollWidth > node.clientWidth + 1).map((node) => node.textContent))
  assert.deepEqual(clipped, [], `${label}: clipped values`)
}

const browser = await chromium.launch()
try {
  for (const [device, width, height] of [['desktop', 1440, 1000], ['mobile', 390, 844], ['small-mobile', 320, 844]]) {
    const context = await browser.newContext({ viewport: { width, height } })
    const page = await context.newPage()
    page.setDefaultNavigationTimeout(180000)
    page.setDefaultTimeout(45000)
    page.on('pageerror', (error) => errors.push(`${device}: ${error.message}`))
    page.on('console', (message) => { if (message.type() === 'error') errors.push(`${device}: ${message.text()}`) })
    page.on('request', (request) => {
      if (request.method() === 'POST' && /\/api\/(simulate|simulation\/run|calibration\/(run|start|optimize|jobs))/.test(request.url())) {
        errors.push('Unexpected scientific execution: ' + request.url())
      }
    })
    for (const [slug, title] of ROUTES) {
      await page.goto(`${BASE}/research${slug ? '/' + slug : ''}`, { waitUntil: 'networkidle' })
      const work = page.getByTestId('research-workspace')
      await work.waitFor()
      assert.equal(await page.locator('h1').count(), 1, `${slug}: duplicate page title`)
      assert.equal(await page.locator('h1').innerText(), title)
      assert.equal(await work.locator('.feature-subsection-grid').count(), 0)
      const links = await page.getByRole('navigation', { name: 'Page sections' }).getByRole('link').all()
      for (const link of links) {
        const hash = await link.getAttribute('href')
        assert.equal(await page.locator(hash).count(), 1, `${slug}: missing section ${hash}`)
      }
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth <= 1), `${device}/${slug}: overflow`)
      if (slug === 'data-upload') {
        const box = await page.getByLabel('Experimental data file').boundingBox()
        assert.ok(box && box.y < 420, 'File input is pushed below the primary screen')
        // No empty sections before a file is imported.
        assert.equal(await page.locator('#validation-alignment').count(), 0)
        assert.equal(await page.locator('#data-readiness').count(), 0)
        assert.equal(await page.getByRole('navigation', { name: 'Page sections' }).count(), 0)
      }
      if (slug === 'parameter-calibration') {
        await page.waitForFunction(() => {
          const profile = document.querySelector('[data-testid="reference-profile"]')
          return profile && !profile.textContent.includes('Loading registry')
        })
        // Real segmented views: one panel visible at a time, keyboard reachable.
        const tabs = page.getByRole('tablist', { name: 'Calibration views' })
        for (const tab of await tabs.getByRole('tab').all()) {
          const panelId = await tab.getAttribute('aria-controls')
          assert.ok(panelId, 'Tab has no associated panel')
          assert.equal(await page.locator(`#${panelId}`).getAttribute('aria-labelledby'), await tab.getAttribute('id'))
        }
        assert.ok(await page.locator('#legacy-calibration').isHidden())
        await tabs.getByRole('tab', { name: 'Legacy', exact: true }).click()
        assert.ok(await page.locator('#legacy-calibration').isVisible())
        assert.ok(await page.getByTestId('reference-profile').isHidden())
        await page.keyboard.press('ArrowLeft')
        assert.equal(await tabs.getByRole('tab', { name: 'Reference', exact: true }).getAttribute('aria-selected'), 'true')
        assert.ok(await page.getByTestId('reference-profile').isVisible())
        await page.keyboard.press('Home')
        assert.ok(await page.getByRole('tabpanel', { name: 'Your data', exact: true }).isVisible())
        await page.keyboard.press('End')
        assert.ok(await page.getByRole('tabpanel', { name: 'Legacy', exact: true }).isVisible())
        await page.evaluate(() => { window.location.hash = 'reference-profile' })
        await page.getByRole('tabpanel', { name: 'Reference', exact: true }).waitFor()
        const inspectorTrigger = page.getByRole('button', { name: 'Reference details', exact: true })
        if (await inspectorTrigger.count()) {
          await inspectorTrigger.click()
          const inspector = page.getByRole('complementary', { name: 'Reference details', exact: true })
          await inspector.waitFor()
          assert.ok(await inspector.evaluate((element) => element === document.activeElement), 'Inspector does not receive focus')
          assert.equal(await inspectorTrigger.getAttribute('aria-controls'), await inspector.getAttribute('id'))
          assert.ok(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth <= 1), `${device}: inspector overflow`)
          await page.screenshot({ path: join(DIR, `inspector-${device}.png`), fullPage: false, caret: 'initial' })
          await page.keyboard.press('Escape')
          assert.equal(await inspector.count(), 0)
          assert.ok(await inspectorTrigger.evaluate((element) => element === document.activeElement), 'Escape does not return focus')
          await inspectorTrigger.click()
          await page.getByRole('button', { name: 'Close Reference details', exact: true }).click()
          assert.ok(await inspectorTrigger.evaluate((element) => element === document.activeElement), 'Close does not return focus')
        }
        // The reference has no activation control at all.
        assert.equal(await page.getByTestId('reference-activate').count(), 0)
        assert.equal(await page.getByTestId('reference-profile').getByRole('button', { name: /activate/i }).count(), 0)
      }
      if (slug === 'simulation') {
        // Settings and empty result only; Run Simulation is never clicked.
        await page.getByTestId('simulation-empty').waitFor()
        assert.ok(await page.getByRole('button', { name: 'Run Simulation' }).isEnabled())
        const slider = page.getByRole('slider').first()
        const before = await slider.getAttribute('aria-valuenow')
        await slider.focus()
        await page.keyboard.press('ArrowRight')
        assert.notEqual(await slider.getAttribute('aria-valuenow'), before)
        await checkInspector(page, 'Run details', 'simulation-provenance', device, slug)
      }
      if (slug === 'flux-analysis') {
        await page.getByRole('button', { name: 'Re-estimate', exact: true }).waitFor({ timeout: 90000 })
        await page.locator('[data-reaction]').first().waitFor({ timeout: 90000 })
        assert.equal(await page.getByTestId('flux-error').count(), 0)
        await assertNoClippedValues(page, '[data-testid="research-flux"] .r-num', `${device}/${slug}`)
        await page.getByRole('combobox', { name: 'Pathway filter' }).click()
        await page.getByRole('option', { name: 'Glycolysis', exact: true }).click()
        assert.equal(await page.getByRole('combobox', { name: 'Pathway filter' }).innerText(), 'Glycolysis')
        assert.equal(await page.locator('[data-pathway]').count(), 1)
        await assertNoClippedValues(page, '[data-testid="research-flux"] .r-num', `${device}/${slug} filtered`)
        await checkInspector(page, 'Flux details', 'flux-provenance', device, slug)
      }
      if (slug === 'pathway-visualization') {
        await page.getByRole('button', { name: 'Refresh network', exact: true }).waitFor({ timeout: 90000 })
        assert.equal(await page.getByTestId('pathway-error').count(), 0)
        // Without a simulation trajectory there is no playback control at all.
        assert.equal(await page.getByRole('button', { name: 'Play playback' }).count(), 0)
        assert.match(await page.getByTestId('pathway-mode-note').innerText(), /display-only/)
        await page.getByRole('button', { name: 'Compact graph', exact: true }).click()
        await page.waitForFunction(() => {
          const points = document.querySelectorAll('.js-plotly-plot .scatterlayer .point').length
          return points > 0 && points < 50
        })
        await page.locator('.js-plotly-plot .main-svg').first().waitFor({ timeout: 60000 })
        assert.ok(await page.locator('.js-plotly-plot .scatterlayer .point').count() > 0, 'Network is blank')
        await page.getByRole('button', { name: 'Full model map', exact: true }).click()
        assert.equal(await page.getByRole('button', { name: 'Full model map', exact: true }).getAttribute('aria-pressed'), 'true')
        await page.waitForFunction(() => document.querySelectorAll('.js-plotly-plot .scatterlayer .point').length > 50)
        assert.ok(await page.locator('.js-plotly-plot .scatterlayer .point').count() > 0, 'Full network is blank')
        await page.getByRole('button', { name: 'Compact graph', exact: true }).click()
        await page.waitForFunction(() => {
          const points = document.querySelectorAll('.js-plotly-plot .scatterlayer .point').length
          return points > 0 && points < 50
        })
        await checkInspector(page, 'Pathway details', 'pathway-inspector', device, slug)
        const plot = page.locator('.js-plotly-plot')
        const initialRange = await plot.evaluate((node) => [...node.layout.xaxis.range])
        await page.getByRole('button', { name: 'Zoom in', exact: true }).click()
        await page.waitForFunction((span) => {
          const range = document.querySelector('.js-plotly-plot')?.layout?.xaxis?.range
          return range && range[1] - range[0] < span
        }, initialRange[1] - initialRange[0])
        await page.getByRole('button', { name: 'Reset zoom', exact: true }).click()
        await page.waitForFunction((expected) => {
          const range = document.querySelector('.js-plotly-plot')?.layout?.xaxis?.range
          return range && Math.abs(range[0] - expected[0]) < 1e-8 && Math.abs(range[1] - expected[1]) < 1e-8
        }, initialRange)
        // Real pointer selection, not an injected Plotly event or an inspector-button shortcut.
        const point = page.locator('.scatterlayer .trace.scatter').filter({ has: page.locator('.point') }).last().locator('.point').first()
        await point.scrollIntoViewIfNeeded()
        const pointBox = await point.boundingBox()
        assert.ok(pointBox, 'Selected node has no rendered position')
        // Plotly handles pointer events on its drag layer above the SVG markers.
        await page.mouse.click(pointBox.x + pointBox.width / 2, pointBox.y + pointBox.height / 2)
        await page.getByTestId('pathway-selection').waitFor()
        assert.ok(await page.getByRole('complementary', { name: 'Pathway details' }).isVisible())
        await page.keyboard.press('Escape')
        assert.ok(await page.getByRole('button', { name: 'Pathway details', exact: true }).evaluate((node) => node === document.activeElement))
      }
      if (slug === 'calibration-registry') {
        const empty = page.getByTestId('registry-empty')
        const failed = page.getByTestId('registry-error')
        if (await empty.count()) {
          // Real empty registry: one sentence, no counters, filters or empty sections.
          assert.match(await empty.innerText(), /No calibration runs recorded yet|workspace selection pending/)
          assert.equal(await page.getByRole('group', { name: 'Run outcome filter' }).count(), 0)
          assert.equal(await page.getByTestId('registry-table').count(), 0)
        } else if (await failed.count()) {
          assert.ok(process.env.REQUIRE_LIVE_REGISTRY !== '1', 'Registry unavailable: ' + await failed.innerText())
        } else {
          const filters = page.getByRole('group', { name: 'Run outcome filter' })
          await filters.getByRole('button', { name: 'Keep', exact: true }).click()
          assert.equal(await filters.getByRole('button', { name: 'Keep', exact: true }).getAttribute('aria-pressed'), 'true')
          assert.ok(!/%/.test(await page.getByTestId('registry-table').innerText()), 'progress percentage shown')
        }
      }
      await page.evaluate(() => scrollTo(0, 0))
      const chatLauncher = page.getByRole('button', { name: 'Ask RoBoCop', exact: true })
      if (width <= 640 && await chatLauncher.count()) {
        const chatBox = await chatLauncher.boundingBox()
        const workBox = await work.boundingBox()
        assert.ok(chatBox && workBox && chatBox.y + chatBox.height <= workBox.y, `${device}/${slug}: chat launcher overlaps the workspace`)
      }
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth <= 1), `${device}/${slug}: loaded-state overflow`)
      await page.screenshot({ path: join(DIR, `after-${slug || 'overview'}-${device}.png`), fullPage: true, caret: 'initial' })
      console.log(`PASS ${device} ${slug || 'overview'}`)
    }

    for (const [alias, view] of [['target-scope', 'Your data'], ['parameter-scope', 'Legacy'], ['benchmark-review', 'Reference']]) {
      await page.goto(`${BASE}/research/parameter-calibration?subsection=${alias}`, { waitUntil: 'networkidle' })
      await page.getByRole('tabpanel', { name: view, exact: true }).waitFor()
      assert.equal(await page.getByRole('tab', { name: view, exact: true }).getAttribute('aria-selected'), 'true')
    }
    console.log(`PASS ${device} historical calibration links`)

    // Test-only CSV parsed by the real API, not a seeded production record.
    await page.goto(`${BASE}/research/data-upload`, { waitUntil: 'networkidle' })
    await page.getByLabel('Experimental data file').setInputFiles({
      name: 'qa-research-only.csv', mimeType: 'text/csv',
      buffer: Buffer.from('Time_days,EGLC,ELAC\n1,23.123456789,4.25\n4,22,5\n8,20,7\n'),
    })
    const mapped = page.waitForResponse((r) => r.url().includes('/data/map-metabolites') && r.request().method() === 'POST')
    await page.getByRole('button', { name: 'Upload & parse' }).click()
    assert.ok((await mapped).ok(), 'Mapping API failed')
    await page.getByRole('cell', { name: '23.123456789', exact: true }).waitFor()
    await page.getByTestId('research-dataset').getByText('Uploaded data', { exact: true }).waitFor()
    const stored = await page.evaluate(() => JSON.parse(localStorage.getItem('clawblood.research.activeDataset')))
    assert.equal(stored.mappedSeriesByMetabolite.EGLC[0], 23.123456789)
    assert.equal(stored.timePoints[0], 1)
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth <= 1), `${device}: imported-state overflow`)
    await page.locator('#validation-alignment').waitFor()
    await page.locator('#data-readiness').waitFor()
    assert.ok(await page.getByTestId('upload-missing-fields').isVisible())
    await page.screenshot({ path: join(DIR, `imported-${device}.png`), fullPage: true, caret: 'initial' })
    await page.locator('#data-readiness').getByRole('link', { name: 'Calibration' }).click()
    // With an upload, Calibration opens on "Your data"; no contractual launch control exists.
    await page.getByTestId('contract-launch-status').waitFor()
    assert.equal(await page.getByTestId('contract-launch').count(), 0)
    assert.equal(await page.getByTestId('preflight-answers').getByText('Not checked', { exact: true }).count(), 3)
    await page.getByRole('button', { name: 'Return to Bordbar reference' }).click()
    await page.waitForFunction(() => localStorage.getItem('clawblood.research.activeDataset') === null)
    if (device !== 'desktop') {
      await page.getByRole('button', { name: 'Open navigation', exact: true }).click()
      await page.locator('aside').getByRole('link', { name: 'Data Upload', exact: true }).click()
      await page.getByTestId('research-data-upload').waitFor()
    }
    console.log(`PASS ${device} real upload -> mapping -> calibration gate -> reference reset`)
    await context.close()
  }
  assert.deepEqual(errors, [], 'Browser errors or unexpected scientific execution')
} catch (error) {
  for (const failure of errors) console.error(failure)
  throw error
} finally {
  await browser.close()
}
