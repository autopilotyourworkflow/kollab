/** Operator Apify key-pool management (admin-gated).
 *
 * The admin password is stored only in THIS browser's localStorage and sent as the
 * X-Admin-Secret header; the server compares it to KOLLAB_ADMIN_SECRET. Only someone
 * with the password can add keys or see the list, so a visitor to the public demo
 * can run Kollab but never touch the pool. The API never returns a token — only a
 * masked hint (e.g. apify_api_…a1b2) and the balance. */

import { apiBase } from "./credit"

const ADMIN_KEY = "kollab-admin-secret"

export type PoolStatus = "active" | "low" | "exhausted" | "invalid" | "disabled"

export interface PoolKey {
  id: string
  label: string
  hint: string
  fingerprint: string
  status: PoolStatus
  remainingUsd: number | null
  limitUsd: number | null
  checkedAt: string | null
  cycleEndAt: string | null
  lastError: string | null
}

export interface PoolSummary {
  enabled: boolean
  active: number
  low: number
  exhausted: number
  invalid: number
  total: number
  totalRemainingUsd: number | null
}

export interface PoolState {
  keys: PoolKey[]
  summary: PoolSummary
}

export type Result<T> = { ok: true; data: T } | { ok: false; status: number; error: string }

export function loadAdminSecret(): string {
  try {
    return localStorage.getItem(ADMIN_KEY) ?? ""
  } catch {
    return ""
  }
}

export function saveAdminSecret(s: string): void {
  try {
    if (s) localStorage.setItem(ADMIN_KEY, s)
    else localStorage.removeItem(ADMIN_KEY)
  } catch {
    /* storage unavailable — the in-memory value the caller holds still applies */
  }
}

export function hasAdminSecret(): boolean {
  return loadAdminSecret().length > 0
}

export function forgetAdminSecret(): void {
  saveAdminSecret("")
}

function adminHeaders(secret?: string): Record<string, string> {
  const s = secret ?? loadAdminSecret()
  const h: Record<string, string> = { "Content-Type": "application/json" }
  if (s) h["X-Admin-Secret"] = s
  return h
}

async function req<T>(path: string, init: RequestInit, secret?: string): Promise<Result<T>> {
  const base = apiBase()
  if (!base) return { ok: false, status: 0, error: "Live backend not configured (demo mode)." }
  try {
    const ctrl = new AbortController()
    const t = window.setTimeout(() => ctrl.abort(), 15_000)
    const res = await fetch(`${base}${path}`, {
      ...init,
      signal: ctrl.signal,
      headers: { ...adminHeaders(secret), ...(init.headers as Record<string, string> | undefined) },
    })
    window.clearTimeout(t)
    if (!res.ok) {
      let detail = `HTTP ${res.status}`
      try {
        detail = (await res.json()).detail || detail
      } catch {
        /* non-JSON error body */
      }
      return { ok: false, status: res.status, error: detail }
    }
    return { ok: true, data: (await res.json()) as T }
  } catch {
    return { ok: false, status: 0, error: "Couldn't reach the server." }
  }
}

/** Unlock check + list. Pass the just-typed secret so we can validate before storing. */
export function listKeys(secret?: string): Promise<Result<PoolState>> {
  return req<PoolState>("/api/keys", { method: "GET" }, secret)
}

export function addKey(token: string, label: string): Promise<Result<PoolKey>> {
  return req<PoolKey>("/api/keys", { method: "POST", body: JSON.stringify({ token, label }) })
}

export function deleteKey(id: string): Promise<Result<{ deleted: boolean }>> {
  return req<{ deleted: boolean }>(`/api/keys/${id}`, { method: "DELETE" })
}

export function refreshKeys(): Promise<Result<{ checked: number }>> {
  return req<{ checked: number }>("/api/keys/refresh", { method: "POST" })
}
