/** Live credit meter — reads GET /api/credit for the key THIS browser will run on
 *  (the stored key, or the operator's shared key). Powers the Settings meter and the
 *  pre-run low-credit warning. Returns null in demo mode (no backend configured) or
 *  on any failure, so callers just fall back to "not shown". */

import { authHeaders } from "./credentials"

type KeySource = "user" | "shared" | "none"

export interface ApifyCredit {
  hasKey: boolean
  source: KeySource
  limitUsd: number | null
  usedUsd: number | null
  remainingUsd: number | null
  cycleEndAt: string | null
  checked: boolean
  note: string
}

export interface CreditInfo {
  sharedKey: boolean
  apify: ApifyCredit
  anthropic: { hasKey: boolean; source: KeySource; note: string }
}

/** The configured backend base, or null when the app is running as the static demo
 *  (no VITE_API_URL) — in which case there is no live credit to show. */
export function apiBase(): string | null {
  const base = import.meta.env.VITE_API_URL as string | undefined
  return base && base.length > 0 ? base : null
}

export async function fetchCredit(): Promise<CreditInfo | null> {
  const base = apiBase()
  if (!base) return null
  try {
    const ctrl = new AbortController()
    const t = window.setTimeout(() => ctrl.abort(), 12_000)
    const res = await fetch(`${base}/api/credit`, { headers: authHeaders(), signal: ctrl.signal })
    window.clearTimeout(t)
    if (!res.ok) return null
    return (await res.json()) as CreditInfo
  } catch {
    return null
  }
}

/** True when we have a real remaining figure and the run estimate would exceed it —
 *  the trigger for the pre-run warning. Unknown remaining -> false (never cry wolf). */
export function runExceedsCredit(credit: CreditInfo | null, estUsd: number): boolean {
  const r = credit?.apify.remainingUsd
  return typeof r === "number" && estUsd > r
}
