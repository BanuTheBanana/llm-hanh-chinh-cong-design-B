// Read DEV privately; exercise the real browser without exporting traces or text.
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const require = createRequire(path.join(root, 'web/package.json'))
const { chromium } = require('@playwright/test')
let browser
let step = 'setup'
try {
  const fixturePath = path.resolve(process.argv[2] ?? '')
  let cases
  if (path.basename(fixturePath) === 'scenario_dev.jsonl') {
    const rows = (await readFile(fixturePath, 'utf8')).split(/\r?\n/).filter(Boolean).map(JSON.parse)
    if (!rows.length || rows.some(item => item.split !== 'DEV'
        || item.review?.status !== 'APPROVED')) throw new Error('Approved DEV only')
    cases = ['required_documents', 'fees'].map(field => rows.find(item =>
      !item.is_multiturn && item.expected_status === 'ANSWER' && item.field_expected === field))
      .map(item => ({
        query: item.question,
        status: item.expected_status,
        fragmentIds: item.gold_fragment_ids,
      }))
  } else {
    const privateRoot = path.join(root, 'evaluation/reports') + path.sep
    if (!fixturePath.startsWith(privateRoot)) throw new Error('Private fixture required')
    const fixture = JSON.parse(await readFile(fixturePath, 'utf8'))
    if (fixture.split !== 'DEV') throw new Error('DEV only')
    cases = ['required_documents', 'fees'].map(field => fixture.cases.find(item =>
      item.plan.status === 'ANSWER' && item.plan.requested_fields.length === 1
      && item.plan.requested_fields[0] === field))
      .map(item => ({
        query: item.bundle.query,
        status: item.plan.status,
        fragmentIds: item.plan.claims.flatMap(claim => claim.evidence_ids),
      }))
  }
  if (cases.some(item => !item)) throw new Error('Fixture missing')
  browser = await chromium.launch({ headless: true })
  const page = await browser.newPage()
  step = 'login'
  await page.goto('http://localhost:3004')
  await page.getByText('G4 / KIỂM CHỨNG EVIDENCE', { exact: true }).waitFor()
  await page.getByLabel('Tên hiển thị').fill('G4 browser smoke')
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
  await page.locator('button.new-conversation').click()
  for (const item of cases) {
    step = 'send-and-verify'
    await page.getByPlaceholder('Viết tin nhắn kiểm thử...').fill(item.query)
    const responsePromise = page.waitForResponse(response =>
      response.request().method() === 'POST' && response.url().endsWith('/messages'),
    { timeout: 90_000 })
    await page.getByRole('button', { name: 'Gửi', exact: true }).click()
    const response = await responsePromise
    if (!response.ok()) throw new Error('Message failed')
    const result = (await response.json()).assistant_message
    if (result.grounding.status !== item.status
        || result.grounding.verification.plan_version !== 'g4-answer-plan-v1') {
      throw new Error('Grounding invalid')
    }
    const cited = result.grounding.sources.map(source => source.fragment_id).sort()
    if (JSON.stringify(cited) !== JSON.stringify([...item.fragmentIds].sort())) {
      throw new Error('Citations invalid')
    }
    // Assertion stays in browser; never interpolate source text into errors/logs.
    await page.waitForFunction(expected => document.body.innerText.includes(expected),
      result.content, { timeout: 15_000 })
    item.renderedAnswer = result.content
  }
  step = 'reload-history'
  await page.reload()
  await page.getByText('Đã đối chiếu nguồn', { exact: true }).nth(1).waitFor()
  for (const item of cases) {
    await page.waitForFunction(expected => document.body.innerText.includes(expected),
      item.renderedAnswer)
  }
  console.log('PASS: real Chromium login, 2 DEV sends, grounded text, citations and reload history.')
} catch {
  console.error(`FAIL: G4 browser smoke at ${step}; private content withheld.`)
  process.exitCode = 2
} finally {
  await browser?.close()
}
