// Screenshot helper for visual self-verification.
// Usage: node scripts/shot.mjs <url> <outfile> [width] [height] [fullPage]
import { chromium } from "playwright"

const [, , url, out, w = "1440", h = "900", full = "true", clickText, extraWait = "0", fill] = process.argv
if (!url || !out) {
  console.error("usage: node scripts/shot.mjs <url> <outfile> [w] [h] [fullPage]")
  process.exit(1)
}

const browser = await chromium.launch()
const page = await browser.newPage({
  viewport: { width: Number(w), height: Number(h) },
  deviceScaleFactor: 2,
})
const errors = []
page.on("console", (m) => m.type() === "error" && errors.push(m.text()))
page.on("pageerror", (e) => errors.push(String(e)))

await page.goto(url, { waitUntil: "networkidle", timeout: 30000 })
await page.waitForTimeout(1200) // let fonts + entrance animations settle
if (fill) {
  await page.locator('input:not([placeholder*="Search"])').first().fill(fill)
  await page.waitForTimeout(250)
}
if (clickText) {
  for (const t of clickText.split("||")) {
    await page.getByText(t, { exact: false }).first().click()
    await page.waitForTimeout(400)
  }
}
if (Number(extraWait) > 0) await page.waitForTimeout(Number(extraWait))
await page.screenshot({ path: out, fullPage: full === "true" })
await browser.close()

if (errors.length) {
  console.log("CONSOLE_ERRORS:\n" + errors.join("\n"))
} else {
  console.log("OK no console errors")
}
console.log("saved " + out)
