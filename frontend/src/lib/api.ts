import { useEffect, useState } from "react"
import type { ClientBrief, Kol } from "./types"
import { kols as fixtureKols, client as fixtureClient, summary as fixtureSummary, cost as fixtureCost } from "../data/kols"

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
      const res = await fetch(`${base}/api/shortlist`, { signal: ctrl.signal })
      window.clearTimeout(t)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: unknown = await res.json()
      if (!isShortlistPayload(data)) throw new Error("unexpected payload shape")
      const cost = (data as { cost?: RunCost }).cost
      return {
        ...data,
        cost: typeof cost?.usd === "number" ? cost : fixtureData.cost,
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
