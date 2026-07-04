import { chromium } from "playwright"

const base = "http://localhost:5178"
const out = process.env.OUT_DIR
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 2 })
const errs = []
p.on("pageerror", (e) => errs.push("page: " + String(e)))
p.on("console", (m) => m.type() === "error" && errs.push("console: " + m.text()))

// 1) shortlist: banner derives, chips, footnote source
await p.goto(base + "/app", { waitUntil: "networkidle" })
await p.waitForTimeout(1000)
const banner = await p.locator("text=failed authenticity vetting").first().innerText().catch(() => "MISSING")
const source = await p.locator("text=bundled fixtures").count()
console.log("banner:", banner.slice(0, 60), "| source-chip(fixtures):", source > 0 ? "shown" : "none")
await p.screenshot({ path: out + "/v-shortlist.png", fullPage: true })

// 2) flagged tab
await p.getByText("Flagged", { exact: false }).first().click()
await p.waitForTimeout(600)
const flaggedRows = await p.locator("text=@mimin.glowyskin").count()
console.log("flagged view shows mimin:", flaggedRows > 0 ? "YES" : "NO")

// 3) unknown URL -> draft badge
await p.goto(base + "/app/new", { waitUntil: "networkidle" })
await p.locator("input").first().fill("nike.com")
await p.getByText("Analyze brand").click()
await p.waitForTimeout(2400)
const draftBadge = await p.locator("text=draft brief").count()
console.log("unknown URL draft badge:", draftBadge > 0 ? "YES" : "NO")
await p.screenshot({ path: out + "/v-draft-brief.png" })

// 4) edit brief -> run -> shortlist shows edits
await p.getByLabel("Remove Affordable actives").click()
await p.getByText("Add", { exact: false }).last().click()
await p.getByLabel("New content pillar").fill("Dermatologist-approved")
await p.keyboard.press("Enter")
await p.waitForTimeout(300)
await p.getByText("Find matching KOLs").click()
await p.waitForTimeout(800)
const runUrl = p.url()
console.log("on run screen:", runUrl.endsWith("/app/run") ? "YES" : runUrl)
await p.waitForTimeout(9000)
const backUrl = p.url()
const editedPillar = await p.locator("text=Dermatologist-approved").count()
const editedTag = await p.locator("text=brief edited").count()
console.log("auto-navigated to shortlist:", backUrl.endsWith("/app") ? "YES" : backUrl)
console.log("edited pillar visible:", editedPillar > 0 ? "YES" : "NO", "| 'brief edited' tag:", editedTag > 0 ? "YES" : "NO")
await p.screenshot({ path: out + "/v-edited-brief.png", fullPage: false })

// 5) fail mode retry clears param
await p.goto(base + "/app/run?fail=1", { waitUntil: "networkidle" })
await p.waitForTimeout(6500)
const failed = await p.locator("text=Vetting step failed").count()
await p.getByText("Retry").click()
await p.waitForTimeout(400)
const cleared = !p.url().includes("fail=1")
console.log("fail mode errored:", failed > 0 ? "YES" : "NO", "| retry cleared param:", cleared ? "YES" : "NO")

// 6) export copy-link
await p.goto(base + "/app", { waitUntil: "networkidle" })
await p.waitForTimeout(800)
await p.context().grantPermissions(["clipboard-read", "clipboard-write"])
await p.getByText("Export", { exact: true }).first().click()
await p.waitForTimeout(500)
await p.getByText("Copy link").click()
await p.waitForTimeout(300)
const clip = await p.evaluate(() => navigator.clipboard.readText()).catch(() => "unreadable")
console.log("copied link:", clip)

// 7) mobile search + drawer inert
await p.setViewportSize({ width: 390, height: 844 })
await p.goto(base + "/app", { waitUntil: "networkidle" })
await p.waitForTimeout(800)
const mobileSearch = await p.getByLabel("Search KOLs and signals").count()
console.log("mobile search present:", mobileSearch > 0 ? "YES" : "NO")
await p.screenshot({ path: out + "/v-mobile.png", fullPage: false })

await b.close()
console.log(errs.length ? "ERRORS:\n" + errs.join("\n") : "NO page/console errors")
