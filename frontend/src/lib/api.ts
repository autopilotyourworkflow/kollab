import { useEffect, useState } from "react"
import type {
  ClientBrief,
  DeliveryAudit,
  DeliveryReliability,
  DeliveryRow,
  Kol,
  OutreachDraft,
  OverlapPair,
} from "./types"
import {
  kols as fixtureKols,
  client as fixtureClient,
  summary as fixtureSummary,
  cost as fixtureCost,
  commenterOverlap as fixtureOverlap,
} from "../data/kols"
import { authHeaders } from "./credentials"

/** One shortlist payload, whichever source produced it. Shape == the backend's
    ShortlistResponse (camelCase); the bundled fixtures satisfy it too. */
export interface RunCost {
  usd: number
  seconds: number
  cacheHitRate: number
}

export interface ShortlistData {
  brief: ClientBrief
  kols: Kol[]
  screened: number
  recommended: number
  flagged: number
  cost: RunCost
  commenterOverlap: OverlapPair[]
  source: "api" | "fixtures"
}

const fixtureData: ShortlistData = {
  brief: fixtureClient,
  kols: fixtureKols,
  screened: fixtureSummary.screened,
  recommended: fixtureSummary.recommended,
  flagged: fixtureSummary.flagged,
  // backend estimate_cost() on the seed cohort (projected live-pull cost) —
  // read from the same committed payload, so it can't drift from the API.
  cost: fixtureCost,
  commenterOverlap: fixtureOverlap,
  source: "fixtures",
}

function isShortlistPayload(d: unknown): d is Omit<ShortlistData, "source"> {
  const p = d as Record<string, unknown>
  return (
    !!p &&
    Array.isArray(p.kols) &&
    p.kols.length > 0 &&
    typeof (p.kols[0] as Kol)?.fitScore === "number" &&
    typeof (p.kols[0] as Kol)?.risk?.level === "string" &&
    typeof (p.brief as ClientBrief)?.brand === "string" &&
    typeof p.screened === "number"
  )
}

let cached: Promise<ShortlistData> | null = null

/** Fetch the shortlist from the pipeline API; falls back to bundled fixtures on
    any failure so the demo can never dead-end. Result is memoized per session. */
export function getShortlist(): Promise<ShortlistData> {
  cached ??= (async () => {
    try {
      const base = (import.meta.env.VITE_API_URL as string | undefined) ?? ""
      const ctrl = new AbortController()
      const t = window.setTimeout(() => ctrl.abort(), 4000)
      const res = await fetch(`${base}/api/shortlist`, { headers: authHeaders(), signal: ctrl.signal })
      window.clearTimeout(t)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: unknown = await res.json()
      if (!isShortlistPayload(data)) throw new Error("unexpected payload shape")
      const cost = (data as { cost?: RunCost }).cost
      const overlap = (data as { commenterOverlap?: OverlapPair[] }).commenterOverlap
      return {
        ...data,
        cost: typeof cost?.usd === "number" ? cost : fixtureData.cost,
        commenterOverlap: Array.isArray(overlap) ? overlap : [],
        source: "api" as const,
      }
    } catch {
      return fixtureData
    }
  })()
  return cached
}

/** Render-ready hook: fixtures immediately (instant paint), API data when it
    arrives. Both satisfy the identical contract, so the swap is seamless. */
export function useShortlist(): ShortlistData {
  const [data, setData] = useState<ShortlistData>(fixtureData)
  useEffect(() => {
    let alive = true
    getShortlist().then((d) => alive && setData(d))
    return () => {
      alive = false
    }
  }, [])
  return data
}

/** Live expand-run, async: a real scrape takes minutes, so the backend runs it in the
    background (state persisted in Neon) and we drive it from the Run dock — START it
    here, then POLL and CANCEL from the dock. The run keeps going even if the browser
    refreshes or closes; the dock re-attaches by id. */
function apiBase(): string {
  return (import.meta.env.VITE_API_URL as string | undefined) ?? ""
}

/** Kick off an expand run; returns the run id (or null with no backend / on failure). */
export async function startRun(brief: ClientBrief, preset = "standard"): Promise<string | null> {
  const base = apiBase()
  if (!base) return null
  try {
    const { authHeaders } = await import("./credentials")
    const res = await fetch(`${base}/api/runs?preset=${encodeURIComponent(preset)}&expand=1`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify(brief),
    })
    if (!res.ok) return null
    const data = (await res.json()) as { id?: string }
    return data.id ?? null
  } catch {
    return null
  }
}

export interface RunPoll {
  status: "queued" | "running" | "done" | "error" | "cancelled"
  kols?: Kol[]
  error?: string | null
}

/** Poll one run. Returns null on a transient/network miss (the dock keeps trying). */
export async function pollRun(id: string): Promise<RunPoll | null> {
  const base = apiBase()
  if (!base) return null
  try {
    const { authHeaders } = await import("./credentials")
    const res = await fetch(`${base}/api/runs/${id}`, { headers: authHeaders() })
    if (!res.ok) return null
    const job = (await res.json()) as { status: RunPoll["status"]; result?: { kols?: Kol[] }; error?: string | null }
    return { status: job.status, kols: job.result?.kols, error: job.error }
  } catch {
    return null
  }
}

/** Stop a run (and abort its in-flight Apify actor so it stops spending). */
export async function cancelRun(id: string): Promise<void> {
  const base = apiBase()
  if (!base) return
  try {
    const { authHeaders } = await import("./credentials")
    await fetch(`${base}/api/runs/${id}/cancel`, { method: "POST", headers: authHeaders() })
  } catch {
    /* best-effort */
  }
}

/** The account manager's edited brief from /app/new, if any (persisted HITL). */
export interface SavedBrief {
  audience: string
  tone: string
  region: string
  pillars: string[]
}

const BRIEF_KEY = "kollab-brief"

export function loadSavedBrief(): SavedBrief | null {
  try {
    const raw = localStorage.getItem(BRIEF_KEY)
    if (!raw) return null
    const b = JSON.parse(raw) as SavedBrief
    return typeof b?.audience === "string" && Array.isArray(b?.pillars) ? b : null
  } catch {
    return null
  }
}

export function saveBrief(b: SavedBrief): void {
  try {
    localStorage.setItem(BRIEF_KEY, JSON.stringify(b))
  } catch {
    /* storage may be unavailable; the in-page edit still worked */
  }
}

// ── Post-match endpoints (all degrade gracefully with no backend) ────────────

export interface GraphStats {
  backend: string
  durable: boolean
  commenters: number
  creators: number
  edges: number
  pods: number | null
  topPod: { accounts: number; creators: number } | null
  note: string
}

/** The persistent commenter-graph readout (the fraud-recall moat). Null with no backend. */
export async function getGraph(): Promise<GraphStats | null> {
  const base = apiBase()
  if (!base) return null
  try {
    const res = await fetch(`${base}/api/graph`, { headers: authHeaders() })
    if (!res.ok) return null
    return (await res.json()) as GraphStats
  } catch {
    return null
  }
}

/** Re-audit a creator's delivered (paid) post. Null with no backend / on failure. */
export async function reauditPost(handle: string, preAuthenticity: number | null): Promise<DeliveryAudit | null> {
  const base = apiBase()
  if (!base) return null
  try {
    const res = await fetch(`${base}/api/re-audit`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ handle, preAuthenticity }),
    })
    if (!res.ok) return null
    return (await res.json()) as DeliveryAudit
  } catch {
    return null
  }
}

/** Draft outreach to a creator, grounded + citation-validated. Null with no backend. */
export async function generateOutreach(kol: Kol, brief: ClientBrief): Promise<OutreachDraft | null> {
  const base = apiBase()
  if (!base) return null
  try {
    const res = await fetch(`${base}/api/outreach`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ kol, brief }),
    })
    if (!res.ok) return null
    return (await res.json()) as OutreachDraft
  } catch {
    return null
  }
}

export interface DeliveriesPayload {
  handle: string
  deliveries: DeliveryRow[]
  reliability: DeliveryReliability
}

/** List a creator's logged deliveries + reliability from the backend. Null when the
    ledger isn't available (no backend / 503 no-DB) — callers fall back to local storage. */
export async function getDeliveries(handle: string): Promise<DeliveriesPayload | null> {
  const base = apiBase()
  if (!base) return null
  try {
    const res = await fetch(`${base}/api/deliveries?handle=${encodeURIComponent(handle)}`, { headers: authHeaders() })
    if (!res.ok) return null
    return (await res.json()) as DeliveriesPayload
  } catch {
    return null
  }
}

/** Log a delivery outcome to the backend ledger. Null on failure (caller uses local). */
export async function logDelivery(input: {
  brand: string
  handle: string
  projectedViews: number
  actualViews: number
  note?: string
}): Promise<{ delivery: DeliveryRow; reliability: DeliveryReliability } | null> {
  const base = apiBase()
  if (!base) return null
  try {
    const res = await fetch(`${base}/api/deliveries`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify(input),
    })
    if (!res.ok) return null
    return (await res.json()) as { delivery: DeliveryRow; reliability: DeliveryReliability }
  } catch {
    return null
  }
}
