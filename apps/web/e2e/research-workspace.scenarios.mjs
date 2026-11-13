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
const browser = await chromium.launch()
try {
  for (const [device, width, height] of [['desktop', 1440, 1000], ['mobile', 390, 844]]) {
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
        await page.getByRole('navigation', { name: 'Page sections' }).getByRole('link', { name: 'Metabolite mapping' }).click()
        assert.equal(new URL(page.url()).hash, '#validation-alignment')
      }
      if (slug === 'parameter-calibration') {
        await page.waitForFunction(() => {
          const profile = document.querySelector('[data-testid="reference-profile"]')
          return profile && !profile.textContent.includes('Loading registry')
        })
        assert.equal(await page.locator('#legacy-calibration').getAttribute('open'), null)
        await page.getByRole('navigation', { name: 'Page sections' }).getByRole('link', { name: 'Advanced', exact: true }).click()
        assert.notEqual(await page.locator('#legacy-calibration').getAttribute('open'), null)
        await page.locator('#legacy-calibration > summary').click()
        const activate = page.getByTestId('reference-activate')
        if (await activate.count()) assert.ok(await activate.isDisabled())
      }
      if (slug === 'simulation') {
        const slider = page.getByRole('slider').first()
        const before = await slider.getAttribute('aria-valuenow')
        await slider.focus()
        await page.keyboard.press('ArrowRight')
        assert.notEqual(await slider.getAttribute('aria-valuenow'), before)
      }
      if (slug === 'flux-analysis') {
        await page.getByRole('button', { name: 'Re-estimate', exact: true }).waitFor({ timeout: 90000 })
        assert.equal(await work.getByText('Flux estimation error', { exact: true }).count(), 0)
        await page.getByRole('combobox', { name: 'Pathway filter' }).click()
        await page.getByRole('option', { name: 'Glycolysis', exact: true }).click()
        assert.equal(await page.getByRole('combobox', { name: 'Pathway filter' }).innerText(), 'Glycolysis')
      }
      if (slug === 'pathway-visualization') {
        await page.getByRole('button', { name: 'Refresh network', exact: true }).waitFor({ timeout: 90000 })
        assert.equal(await work.getByText('Pathway visualization error', { exact: true }).count(), 0)
        await page.getByRole('button', { name: 'Compact graph', exact: true }).click()
        await page.waitForFunction(() => {
          const points = document.querySelectorAll('.js-plotly-plot .scatterlayer .point').length
          return points > 0 && points < 50
        })
        await page.locator('.js-plotly-plot .main-svg').first().waitFor({ timeout: 60000 })
        assert.ok(await page.locator('.js-plotly-plot .scatterlayer .point').count() > 0, 'Network is blank')
        await page.getByRole('button', { name: 'Full model map', exact: true }).click()
        assert.equal(await page.getByRole('button', { name: 'Full model map', exact: true }).getAttribute('aria-pressed'), 'true')
        await page.getByRole('button', { name: 'Compact graph', exact: true }).click()
        await page.waitForFunction(() => {
          const points = document.querySelectorAll('.js-plotly-plot .scatterlayer .point').length
          return points > 0 && points < 50
        })
      }
      if (slug === 'calibration-registry') {
        const filters = page.getByRole('group', { name: 'Run outcome filter' })
        await filters.getByRole('button', { name: 'Keep', exact: true }).click()
        assert.equal(await filters.getByRole('button', { name: 'Keep', exact: true }).getAttribute('aria-pressed'), 'true')
      }
      await page.evaluate(() => scrollTo(0, 0))
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth <= 1), `${device}/${slug}: loaded-state overflow`)
      await page.screenshot({ path: join(DIR, `after-${slug || 'overview'}-${device}.png`), fullPage: true, caret: 'initial' })
      console.log(`PASS ${device} ${slug || 'overview'}`)
    }

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
    await page.getByRole('navigation', { name: 'Page sections' }).getByRole('link', { name: 'Review', exact: true }).click()
    assert.equal(new URL(page.url()).hash, '#data-readiness')
    await page.screenshot({ path: join(DIR, `imported-${device}.png`), fullPage: true, caret: 'initial' })
    await page.locator('#data-readiness').getByRole('link', { name: 'Calibration' }).click()
    await page.getByTestId('contract-launch').waitFor()
    assert.ok(await page.getByTestId('contract-launch').isDisabled())
    await page.getByRole('button', { name: 'Return to Bordbar reference' }).click()
    await page.waitForFunction(() => localStorage.getItem('clawblood.research.activeDataset') === null)
    if (device === 'mobile') {
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
