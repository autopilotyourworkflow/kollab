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

// ── Apify pool accounts (the operator's key pool: view + manual switch) ──────
export interface ApifyAccount {
  label: string // env var name, e.g. "APIFY_TOKEN_1"
  hint: string // masked, e.g. "apify_api_…gr3n" (never the raw token)
  fingerprint: string // one-way id used to select this account
  healthy: boolean
  note: string | null // why drained (low balance / invalid), if so
  preferred: boolean // the operator's chosen starting account
  active: boolean // the account a run would use right now
  checked?: boolean
  remainingUsd?: number | null
  limitUsd?: number | null
  usedUsd?: number | null
  cycleEndAt?: string | null
  balanceNote?: string
}

export interface ApifyAccountsPayload {
  poolEnabled: boolean
  preferred: string | null
  accounts: ApifyAccount[]
}

/** List the operator's Apify pool accounts (masked) with live balances + which is active.
 *  Null with no backend / on failure. Requires a signed-in session (authHeaders carries it). */
export async function getApifyAccounts(): Promise<ApifyAccountsPayload | null> {
  const base = apiBase()
  if (!base) return null
  try {
    const ctrl = new AbortController()
    const t = window.setTimeout(() => ctrl.abort(), 20_000) // balances = a fetch per key
    const res = await fetch(`${base}/api/apify-accounts`, { headers: authHeaders(), signal: ctrl.signal })
    window.clearTimeout(t)
    if (!res.ok) return null
    return (await res.json()) as ApifyAccountsPayload
  } catch {
    return null
  }
}

/** Pick which pool account runs start on (by fingerprint), or null for auto (env order).
 *  Returns the updated list (without balances) or null on failure. */
export async function selectApifyAccount(keyId: string | null): Promise<ApifyAccountsPayload | null> {
  const base = apiBase()
  if (!base) return null
  try {
    const res = await fetch(`${base}/api/apify-accounts/select`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify({ keyId }),
    })
    if (!res.ok) return null
    return (await res.json()) as ApifyAccountsPayload
  } catch {
    return null
  }
}
