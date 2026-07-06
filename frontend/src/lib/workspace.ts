/** The Shortlists workspace — a client-side (localStorage) store of every campaign.
 *
 * This is what powers the Dashboard (a home of shortlist cards) and accumulation
 * (each shortlist grows across runs, dedup by handle, with approve/reject decisions
 * persisted). It lives in the browser — same pattern as the saved brief / run plan —
 * so it works on the static demo with no backend, and a live run just appends real
 * creators to the same list. On first load it seeds one shortlist from the bundled
 * demo fixtures so the Dashboard is never empty. */

import type { ClientBrief, HitlStatus, Kol, OverlapPair, RiskLevel, Tier } from "./types"
import {
  client as demoBrief,
  kols as demoKols,
  summary as demoSummary,
  cost as demoCost,
  commenterOverlap as demoOverlap,
} from "../data/kols"

export interface Decision {
  status: HitlStatus
  reason?: string
}

export interface RunCost {
  usd: number
  seconds: number
  cacheHitRate: number
}

export interface ShortlistEntry {
  id: string
  brief: ClientBrief
  kols: Kol[]
  decisions: Record<string, Decision> // by kol.id — persisted HITL
  screened: number
  runs: number
  source: "fixtures" | "api"
  cost: RunCost
  /** Commenter-overlap pairs across this shortlist (dedup helper). */
  commenterOverlap: OverlapPair[]
  createdAt: number
  updatedAt: number
}

interface Workspace {
  shortlists: ShortlistEntry[]
}

const KEY = "kollab-workspace"
const SEED_ID = "demo-glow-lab"

function newId(): string {
  try {
    return crypto.randomUUID()
  } catch {
    return `sl-${Date.now()}-${Math.floor(Math.random() * 1e6)}`
  }
}

/** recommended = clear + fit≥70; flagged = any risk. Recomputed from the live list
 *  so the card counts can never drift from the rows. */
export function counts(kols: Kol[]): { recommended: number; flagged: number } {
  return {
    recommended: kols.filter((k) => k.risk.level === "clear" && k.fitScore >= 70).length,
    flagged: kols.filter((k) => k.risk.level !== "clear").length,
  }
}

function seedEntry(): ShortlistEntry {
  const now = Date.now()
  return {
    id: SEED_ID,
    brief: demoBrief,
    kols: demoKols,
    decisions: Object.fromEntries(demoKols.map((k) => [k.id, { status: k.hitl }])),
    screened: demoSummary.screened,
    runs: 1,
    source: "fixtures",
    cost: demoCost,
    commenterOverlap: demoOverlap,
    createdAt: now,
    updatedAt: now,
  }
}

function read(): Workspace {
  try {
    const raw = localStorage.getItem(KEY)
    if (raw) {
      const w = JSON.parse(raw) as Workspace
      if (Array.isArray(w?.shortlists)) {
        // migrate entries saved before commenterOverlap existed
        for (const s of w.shortlists) if (!Array.isArray(s.commenterOverlap)) s.commenterOverlap = []
        return w
      }
    }
  } catch {
    /* corrupt/unavailable — fall through to a fresh seeded workspace */
  }
  const seeded: Workspace = { shortlists: [seedEntry()] }
  write(seeded)
  return seeded
}

function write(w: Workspace): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(w))
  } catch {
    /* storage full/unavailable — in-memory callers still got their result */
  }
}

/** All shortlists, most-recently-updated first. */
export function listShortlists(): ShortlistEntry[] {
  return [...read().shortlists].sort((a, b) => b.updatedAt - a.updatedAt)
}

export function getEntry(id: string): ShortlistEntry | null {
  return read().shortlists.find((s) => s.id === id) ?? null
}

/** Create a new shortlist from a brief + its first batch of results. */
export function createEntry(
  brief: ClientBrief,
  kols: Kol[],
  opts: { source?: "fixtures" | "api"; screened?: number; cost?: RunCost; commenterOverlap?: OverlapPair[] } = {},
): ShortlistEntry {
  const now = Date.now()
  const entry: ShortlistEntry = {
    id: newId(),
    brief,
    kols,
    decisions: Object.fromEntries(kols.map((k) => [k.id, { status: k.hitl }])),
    screened: opts.screened ?? kols.length,
    runs: 1,
    source: opts.source ?? "fixtures",
    cost: opts.cost ?? { usd: 0, seconds: 0, cacheHitRate: 0 },
    commenterOverlap: opts.commenterOverlap ?? [],
    createdAt: now,
    updatedAt: now,
  }
  const w = read()
  w.shortlists.push(entry)
  write(w)
  return entry
}

/** Append NEW creators to a shortlist (dedup by handle). Returns the number added —
 *  this is accumulation: a re-run grows the same list, never duplicates it. */
export function appendKols(id: string, incoming: Kol[]): number {
  const w = read()
  const entry = w.shortlists.find((s) => s.id === id)
  if (!entry) return 0
  const have = new Set(entry.kols.map((k) => k.handle.toLowerCase()))
  const fresh = incoming.filter((k) => !have.has(k.handle.toLowerCase()))
  if (!fresh.length) return 0
  entry.kols = [...entry.kols, ...fresh]
  for (const k of fresh) entry.decisions[k.id] ??= { status: k.hitl }
  entry.screened += fresh.length
  entry.runs += 1
  entry.updatedAt = Date.now()
  write(w)
  return fresh.length
}

export function setDecision(id: string, kolId: string, decision: Decision): void {
  const w = read()
  const entry = w.shortlists.find((s) => s.id === id)
  if (!entry) return
  entry.decisions[kolId] = decision.status === "pending" ? { status: "pending" } : decision
  entry.updatedAt = Date.now()
  write(w)
}

export function deleteEntry(id: string): void {
  const w = read()
  w.shortlists = w.shortlists.filter((s) => s.id !== id)
  write(w)
}

/** Flip a shortlist's badge to "live" once real (backend-sourced) creators merged in. */
export function markSourceLive(id: string): void {
  const w = read()
  const entry = w.shortlists.find((s) => s.id === id)
  if (entry && entry.source !== "api") {
    entry.source = "api"
    entry.updatedAt = Date.now()
    write(w)
  }
}

// ── Demo expansion pool ──────────────────────────────────────────────────────
// So accumulation is demonstrable with NO backend: "Add more results" reveals the
// next batch of these synthetic-but-plausible Thai beauty creators (clearly demo
// data, like the rest of the fixtures). Some are flagged, so vetting visibly fires
// on the newly-sourced creators too. A live backend replaces this with real
// expand-run results.

function hue(seed: string): number {
  let h = 0
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) % 360
  return h
}

interface PoolSpec {
  handle: string
  name: string
  followers: number
  er: number
  tier: Tier
  kind: "clean" | "pod" | "bought"
}

const POOL_SPECS: PoolSpec[] = [
  { handle: "@ploy.skinnote", name: "Ploy · Skin Notes", followers: 88_000, er: 7.2, tier: "micro", kind: "clean" },
  { handle: "@mimi.glowdaily", name: "Mimi Glow", followers: 152_000, er: 5.1, tier: "mid", kind: "clean" },
  { handle: "@bee.beautylab", name: "Bee Beauty Lab", followers: 63_000, er: 9.6, tier: "micro", kind: "pod" },
  { handle: "@nam.clinicalskin", name: "Nam · Clinical Skin", followers: 210_000, er: 4.6, tier: "mid", kind: "clean" },
  { handle: "@fahsai.derm", name: "Fahsai Derm", followers: 47_000, er: 8.1, tier: "micro", kind: "clean" },
  { handle: "@earn.viralbeauty", name: "Earn Viral Beauty", followers: 486_000, er: 12.4, tier: "macro", kind: "bought" },
  { handle: "@ing.softglow", name: "Ing Soft Glow", followers: 74_000, er: 6.7, tier: "micro", kind: "clean" },
  { handle: "@tarn.skintruth", name: "Tarn Skin Truth", followers: 129_000, er: 5.9, tier: "mid", kind: "clean" },
]

function buildPoolKol(spec: PoolSpec): Kol {
  const medianViews = Math.round(spec.followers * (spec.kind === "bought" ? 0.18 : 0.62))
  const flagged: RiskLevel = spec.kind === "bought" ? "high" : "medium"
  const level: RiskLevel = spec.kind === "clean" ? "clear" : flagged
  const authScore = spec.kind === "clean" ? 82 : spec.kind === "pod" ? 44 : 28
  const topicScore = 78
  const recencyScore = 88
  const fitScore = Math.round(topicScore * 0.45 + authScore * 0.35 + recencyScore * 0.2)

  const signals =
    spec.kind === "pod"
      ? [{
          label: "Comment pod",
          detail: `37 accounts comment across 5 unrelated creators within 12 days`,
          level: "medium" as RiskLevel,
          measuredAgainst: "22 beauty-micro peers (n=22)",
        }]
      : spec.kind === "bought"
        ? [{
            label: "Bought followers",
            detail: `${(medianViews / spec.followers * 100).toFixed(1)}% view-to-follower — far below the cohort's healthy band`,
            level: "high" as RiskLevel,
            measuredAgainst: "19 beauty-macro peers (n=19)",
          }]
        : []

  const whyEn =
    level === "clear"
      ? `${spec.name} is a clean, on-brief fit — skincare content to a Thai audience with healthy engagement (ER ${spec.er}%). Fit ${fitScore}/100.`
      : `${spec.name} looks appealing (${(spec.followers / 1000).toFixed(0)}K followers, ER ${spec.er}%) but Kollab flagged ${signals[0].label.toLowerCase()} — routed to human review, not auto-excluded.`
  const whyTh =
    level === "clear"
      ? `${spec.name} เหมาะกับแบรนด์ คอนเทนต์สกินแคร์ เอนเกจสุขภาพดี (ER ${spec.er}%) คะแนน ${fitScore}/100`
      : `${spec.name} ดูน่าสนใจแต่ Kollab จับสัญญาณ ${signals[0].label} ส่งให้คนรีวิว ไม่ตัดออกอัตโนมัติ`

  // Fair-rate basis (same shape the backend ships) so the Economics tab is consistent
  // for demo-added creators: measured organic reach × the default CPM × authenticity.
  const cpm = 150
  const disc = Math.max(0, Math.min(1, authScore / 100))
  const point = ((medianViews * disc) / 1000) * cpm
  const rateBasis = {
    medianOrganicViews: medianViews,
    cpmThb: cpm,
    authenticity: authScore,
    videosSampled: 20,
    band: { low: Math.round(point * 0.8), high: Math.round(point * 1.2) },
    method: `${medianViews.toLocaleString()} organic views/post × ฿${cpm} CPM (your assumption) × ${authScore}% authenticity — not a market rate card.`,
  }

  return {
    id: `pool-${spec.handle.replace(/[^a-z0-9]/gi, "")}`,
    handle: spec.handle,
    name: spec.name,
    avatar: { initials: spec.name.replace(/[^a-zA-Z]/g, "").slice(0, 2).toUpperCase() || "KK", hue: hue(spec.handle) },
    category: "Skincare & beauty",
    categoryTh: "สกินแคร์ & บิวตี้",
    tier: spec.tier,
    region: "Thailand",
    followers: spec.followers,
    medianViews,
    engagementRate: spec.er,
    lastPostedDaysAgo: 2 + (spec.followers % 5),
    fitScore,
    risk: { level, signals },
    brandSafety: { status: "clear" },
    conflict: { status: "clear" },
    factors: [
      { key: "topic", label: "Topic fit", score: topicScore, weight: 0.45, provenance: "measured",
        rationale: "Captions and hashtags overlap the brief's skincare pillars." },
      { key: "authenticity", label: "Authenticity", score: authScore, weight: 0.35, provenance: "measured",
        rationale: level === "clear" ? "Clean engagement distribution vs the cohort." : "Engagement pattern diverges from the peer baseline — see the flag." },
      { key: "recency", label: "Recency", score: recencyScore, weight: 0.2, provenance: "measured",
        rationale: "Posting consistently in the last two weeks." },
      { key: "audience", label: "Audience match", score: 70, weight: 0, provenance: "inferred",
        rationale: "Advisory only — audience inference needs licensed data; do not quote to client as fact." },
    ],
    whyEn,
    whyTh,
    estRateThb: rateBasis.band,
    rateBasis,
    hitl: "pending",
  }
}

/** Append the next batch of demo creators not already in the shortlist. Returns the
 *  count added (0 when the demo pool is exhausted). */
export function appendDemoBatch(id: string, batch = 4): number {
  const entry = getEntry(id)
  if (!entry) return 0
  const have = new Set(entry.kols.map((k) => k.handle.toLowerCase()))
  const next = POOL_SPECS.filter((s) => !have.has(s.handle.toLowerCase())).slice(0, batch).map(buildPoolKol)
  return appendKols(id, next)
}

/** How many demo creators remain to be revealed for this shortlist. */
export function demoRemaining(id: string): number {
  const entry = getEntry(id)
  if (!entry) return 0
  const have = new Set(entry.kols.map((k) => k.handle.toLowerCase()))
  return POOL_SPECS.filter((s) => !have.has(s.handle.toLowerCase())).length
}
