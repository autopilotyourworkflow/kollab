// TEMP: end-to-end relevance check — create Srichand, wait for merge, capture who was sourced.
import { chromium } from "playwright"
const BASE = process.argv[2] || "https://kollab.autopilotyourworkflow.com"
const SHOT = process.argv[3] || null
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, deviceScaleFactor: 2 })
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a)

try {
  await page.goto(BASE + "/app", { waitUntil: "domcontentloaded", timeout: 45000 })
  await page.getByRole("button", { name: /Explore the demo/i }).click()
  await page.getByRole("button", { name: /New shortlist/i }).first().waitFor({ timeout: 45000 })
  await page.goto(BASE + "/app/new", { waitUntil: "domcontentloaded", timeout: 30000 })
  await page.locator('input[placeholder*="client-website"]').first().fill("srichand.co.th")
  await page.getByRole("button", { name: /Analyze brand/i }).click()
  await page.getByRole("button", { name: /Find matching KOLs/i }).waitFor({ timeout: 45000 })
  const scan = page.getByRole("radio", { name: /Scan/i })
  if (await scan.count()) await scan.first().click()
  await page.getByRole("button", { name: /Find matching KOLs/i }).click()
  await page.waitForURL(/\/app\/s\//, { timeout: 30000 })
  log("created; waiting for merge…")

  let outcome = "timeout"
  for (let i = 0; i < 95; i++) {
    await page.waitForTimeout(6000)
    if (await page.getByText("Med. views").count()) { outcome = "merged"; break }
    if (await page.getByText(/No creators yet|No new creators found/i).count()) { outcome = "empty"; break }
    if (await page.getByText(/Run failed|timed out/i).count()) { outcome = "error"; break }
    if (i % 5 === 0) log(`waiting… ${i * 6}s`)
  }

  // capture creator rows: handle + display name/bio for eyeballing relevance
  const rows = await page.evaluate(() => {
    const out = []
    for (const el of document.querySelectorAll("*")) {
      const t = (el.textContent || "").trim()
      if (/^@[\w.]+$/.test(t) && t.length < 40) {
        const row = el.closest("div")
        out.push({ handle: t, ctx: (row?.textContent || "").replace(/\s+/g, " ").slice(0, 90) })
      }
    }
    // dedupe by handle
    const seen = new Set()
    return out.filter((r) => !seen.has(r.handle) && seen.add(r.handle)).slice(0, 10)
  })
  if (SHOT) { await page.screenshot({ path: SHOT }); log("saved", SHOT) }
  log("OUTCOME:", outcome)
  for (const r of rows) log("  ", r.handle, "—", r.ctx)
} catch (e) {
  log("SCRIPT_ERROR:", e.message)
} finally {
  await browser.close()
}
