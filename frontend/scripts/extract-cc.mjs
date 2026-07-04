// Design-language extraction rig for convertcake.com (reference-only).
// Outputs to frontend/.impeccable/reference/convertcake/ (gitignored — reference
// material stays local; we reimplement the design language in our own code).
//
// Usage: node scripts/extract-cc.mjs
import { chromium } from "playwright"
import { mkdirSync, writeFileSync } from "node:fs"
import { join } from "node:path"

const BASE = "https://convertcake.com"
const OUT = ".impeccable/reference/convertcake"
mkdirSync(OUT, { recursive: true })
mkdirSync(join(OUT, "shots"), { recursive: true })
mkdirSync(join(OUT, "css"), { recursive: true })

const slug = (u) =>
  (new URL(u).pathname.replace(/\/$/, "") || "home").replace(/[^\w-]+/g, "_").replace(/^_/, "") || "home"

/* ── in-page extraction ─────────────────────────────────────────────────── */
function extractInPage() {
  const tally = (m, k) => k && (m[k] = (m[k] || 0) + 1)
  const vis = (el) => {
    const r = el.getBoundingClientRect()
    return r.width > 2 && r.height > 2
  }
  const colors = {}, bgs = {}, fonts = {}, radii = {}, shadows = {}, trans = {}
  const els = Array.from(document.querySelectorAll("body *")).filter(vis).slice(0, 5000)
  for (const el of els) {
    const cs = getComputedStyle(el)
    tally(colors, cs.color)
    if (cs.backgroundColor && cs.backgroundColor !== "rgba(0, 0, 0, 0)") tally(bgs, cs.backgroundColor)
    tally(fonts, cs.fontFamily.split(",")[0].trim().replace(/["']/g, ""))
    if (cs.borderRadius !== "0px") tally(radii, cs.borderRadius)
    if (cs.boxShadow !== "none") tally(shadows, cs.boxShadow)
    if (parseFloat(cs.transitionDuration) > 0)
      tally(trans, `${cs.transitionDuration} ${cs.transitionTimingFunction}`)
  }
  const pick = (sel) => {
    const el = Array.from(document.querySelectorAll(sel)).find(vis)
    if (!el) return null
    const cs = getComputedStyle(el)
    return {
      sample: (el.textContent || "").trim().slice(0, 70),
      fontFamily: cs.fontFamily.split(",")[0].replace(/["']/g, "").trim(),
      fontSize: cs.fontSize, fontWeight: cs.fontWeight, lineHeight: cs.lineHeight,
      letterSpacing: cs.letterSpacing, textTransform: cs.textTransform,
      color: cs.color, background: cs.backgroundColor,
    }
  }
  const roles = {}
  for (const sel of ["h1", "h2", "h3", "h4", "p", "nav a", "footer", "input, textarea"]) roles[sel] = pick(sel)

  // CTA/button anatomy — sample distinct filled buttons/links
  const seen = new Set()
  const buttons = []
  for (const el of Array.from(document.querySelectorAll("a, button")).filter(vis)) {
    const cs = getComputedStyle(el)
    const txt = (el.textContent || "").trim()
    if (!txt || txt.length > 42) continue
    if (cs.backgroundColor === "rgba(0, 0, 0, 0)" && cs.borderStyle === "none") continue
    const key = `${cs.backgroundColor}|${cs.borderRadius}|${cs.border}`
    if (seen.has(key)) continue
    seen.add(key)
    buttons.push({
      text: txt.slice(0, 42), bg: cs.backgroundColor, color: cs.color,
      radius: cs.borderRadius, padding: cs.padding, border: cs.border,
      fontSize: cs.fontSize, fontWeight: cs.fontWeight, shadow: cs.boxShadow,
      transition: `${cs.transitionDuration} ${cs.transitionTimingFunction}`,
    })
    if (buttons.length >= 14) break
  }

  // :root custom properties + keyframes + easing fns from same-origin sheets
  const rootVars = {}, keyframes = new Set(), eases = {}
  for (const sheet of document.styleSheets) {
    let rules
    try { rules = sheet.cssRules } catch { continue }
    if (!rules) continue
    for (const rule of rules) {
      if (rule.selectorText && /(^|,)\s*:root/.test(rule.selectorText)) {
        for (const prop of rule.style) if (prop.startsWith("--")) rootVars[prop] = rule.style.getPropertyValue(prop).trim()
      }
      if (rule.type === CSSRule.KEYFRAMES_RULE) keyframes.add(rule.name)
      if (rule.style) {
        const t = rule.style.transitionTimingFunction
        if (t && t !== "ease") tally(eases, t)
      }
    }
  }

  const logoEl = document.querySelector('img[src*="logo" i], .logo img, header a img, a[href="/"] img')
  const top = (m, n = 18) => Object.entries(m).sort((a, b) => b[1] - a[1]).slice(0, n)

  return {
    title: document.title,
    lang: document.documentElement.lang,
    bodyBg: getComputedStyle(document.body).backgroundColor,
    bodyFont: getComputedStyle(document.body).fontFamily,
    rootFontSize: getComputedStyle(document.documentElement).fontSize,
    colors: top(colors), backgrounds: top(bgs), fonts: top(fonts),
    radii: top(radii, 12), shadows: top(shadows, 8), transitions: top(trans, 12),
    eases: top(eases, 10), keyframes: [...keyframes].slice(0, 40),
    roles, buttons, rootVars,
    logo: logoEl ? logoEl.src : null,
    favicon: (document.querySelector('link[rel*="icon"]') || {}).href || null,
    stylesheets: Array.from(document.styleSheets).map((s) => s.href).filter(Boolean),
  }
}

/* ── crawl ──────────────────────────────────────────────────────────────── */
const browser = await chromium.launch()
const desktop = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const page = await desktop.newPage()
page.setDefaultTimeout(45000)

console.log("visiting homepage…")
await page.goto(BASE + "/", { waitUntil: "networkidle" })
await page.waitForTimeout(1500)

// Discover key pages from the nav
const hrefs = await page.evaluate(() =>
  Array.from(document.querySelectorAll("a[href]")).map((a) => a.href)
)
const sameOrigin = [...new Set(hrefs.filter((h) => h.startsWith("https://convertcake.com")))]
const want = (re) => sameOrigin.find((h) => re.test(h))
const targets = [
  BASE + "/",
  want(/\/about\/?$/),
  want(/\/careers\/?$/),
  want(/influencer/i) || want(/\/services?\//),
  want(/case-stud/i),
  want(/\/blogs?\/?$/),
].filter(Boolean)
console.log("targets:", targets.join("\n  "))

const report = { crawledAt: "2026-07-02", base: BASE, pages: {} }

for (const url of targets) {
  const name = slug(url)
  console.log(`→ ${name}`)
  try {
    await page.goto(url, { waitUntil: "networkidle" })
    await page.waitForTimeout(1800) // let fonts/animations settle
    report.pages[name] = await page.evaluate(extractInPage)
    report.pages[name].url = url
    // desktop full page + hero viewport
    await page.screenshot({ path: join(OUT, "shots", `${name}_desktop_full.png`), fullPage: true })
    await page.screenshot({ path: join(OUT, "shots", `${name}_desktop_hero.png`) })
  } catch (e) {
    console.log(`   FAILED ${name}: ${String(e).slice(0, 120)}`)
  }
}

// mobile pass (homepage + about only — enough to read responsive behavior)
const mobile = await browser.newContext({
  viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true,
})
const mpage = await mobile.newPage()
for (const url of targets.slice(0, 2)) {
  const name = slug(url)
  try {
    await mpage.goto(url, { waitUntil: "networkidle", timeout: 45000 })
    await mpage.waitForTimeout(1500)
    await mpage.screenshot({ path: join(OUT, "shots", `${name}_mobile_full.png`), fullPage: true })
  } catch (e) {
    console.log(`   mobile FAILED ${name}: ${String(e).slice(0, 100)}`)
  }
}

// tablet hero of homepage
const tablet = await browser.newContext({ viewport: { width: 768, height: 1024 } })
const tpage = await tablet.newPage()
try {
  await tpage.goto(BASE + "/", { waitUntil: "networkidle", timeout: 45000 })
  await tpage.waitForTimeout(1200)
  await tpage.screenshot({ path: join(OUT, "shots", "home_tablet_hero.png") })
} catch {}

/* ── download logo + same-origin stylesheets for exact-value mining ─────── */
const home = report.pages["home"] || Object.values(report.pages)[0]
const dl = async (url, file) => {
  try {
    const res = await fetch(url)
    if (!res.ok) return console.log(`   dl ${res.status}: ${url}`)
    writeFileSync(join(OUT, file), Buffer.from(await res.arrayBuffer()))
    console.log(`   saved ${file}`)
  } catch (e) { console.log(`   dl failed: ${String(e).slice(0, 80)}`) }
}
if (home?.logo) await dl(home.logo, "logo" + (home.logo.includes(".svg") ? ".svg" : ".png"))
if (home?.favicon) await dl(home.favicon, "favicon" + (home.favicon.includes(".svg") ? ".svg" : ".ico"))
const sheets = [...new Set(Object.values(report.pages).flatMap((p) => p.stylesheets || []))]
  .filter((h) => h.startsWith("https://convertcake.com")).slice(0, 12)
for (const [i, href] of sheets.entries()) await dl(href, join("css", `sheet_${i}.css`))
report.downloadedSheets = sheets

writeFileSync(join(OUT, "report.json"), JSON.stringify(report, null, 2))
console.log(`\nDONE — report.json + ${Object.keys(report.pages).length} pages extracted → ${OUT}`)
await browser.close()
