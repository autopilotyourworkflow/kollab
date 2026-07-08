/** Auth primitives — the session token + the account API. Framework-free.
 *
 * The token is a credential (an HMAC-signed blob from the backend), not shortlist data —
 * it lives in localStorage and rides every request as `Authorization: Bearer` (added in
 * credentials.ts). Shortlist data itself is never the browser's primary store. */

import { apiBase } from "./credit"

export interface AuthUser {
  id: string
  email: string | null
  isGuest: boolean
}

export interface AuthResult {
  token: string
  user: AuthUser
}

/** Thrown with a human-readable message (the backend's `detail`) so the gate can show it. */
export class AuthError extends Error {}

const TOKEN_KEY = "kollab-auth"
const USER_KEY = "kollab-user"

export function getAuthToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setAuthToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token)
  } catch {
    /* storage unavailable */
  }
}

export function clearAuthToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  } catch {
    /* nothing to clear */
  }
}

/** The last-known user, cached alongside the token, so a returning visitor renders the app
 *  INSTANTLY (optimistically) while the token is validated in the background — instead of
 *  staring at a spinner while the (possibly asleep) backend answers /api/auth/me. */
export function getCachedUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(USER_KEY)
    if (!raw) return null
    const u = JSON.parse(raw) as AuthUser
    return typeof u?.id === "string" ? u : null
  } catch {
    return null
  }
}

export function setCachedUser(user: AuthUser): void {
  try {
    localStorage.setItem(USER_KEY, JSON.stringify(user))
  } catch {
    /* storage unavailable */
  }
}

/** Outcome of validating the stored token. `unauthorized` (a real 401) means the token is
 *  dead — sign out. `unreachable` (network / 5xx / cold-start blip) means we simply couldn't
 *  check — KEEP the session (never log a valid user out just because the server was waking). */
export type MeResult =
  | { status: "ok"; user: AuthUser }
  | { status: "unauthorized" }
  | { status: "unreachable" }

/** Validate the stored token against the backend. */
export async function apiMe(): Promise<MeResult> {
  const base = apiBase()
  const token = getAuthToken()
  if (!base || !token) return { status: "unauthorized" }
  try {
    const res = await fetch(`${base}/api/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
    if (res.status === 401) return { status: "unauthorized" }
    if (!res.ok) return { status: "unreachable" } // 5xx / gateway blip while waking — keep session
    return { status: "ok", user: (await res.json()) as AuthUser }
  } catch {
    return { status: "unreachable" } // network / timeout — keep session, don't log out
  }
}

/** Fire-and-forget backend wake-up so the instance (which sleeps on the free tier) starts
 *  cold-starting as early as possible, overlapping with the app's own first data fetches. */
export function prewarmBackend(): void {
  const base = apiBase()
  if (!base) return
  try {
    void fetch(`${base}/health`, { method: "GET", mode: "cors", keepalive: true }).catch(() => {})
  } catch {
    /* ignore */
  }
}

async function authPost(path: string, body: unknown): Promise<AuthResult> {
  const base = apiBase()
  if (!base) throw new AuthError("Accounts aren't available in offline mode.")
  let res: Response
  try {
    res = await fetch(`${base}${path}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    })
  } catch {
    throw new AuthError("Couldn't reach the server. Check your connection and try again.")
  }
  if (!res.ok) {
    let detail = "Something went wrong. Please try again."
    try {
      detail = ((await res.json()) as { detail?: string }).detail || detail
    } catch {
      /* non-JSON error */
    }
    throw new AuthError(detail)
  }
  return (await res.json()) as AuthResult
}

export const apiLogin = (email: string, password: string) => authPost("/api/auth/login", { email, password })
export const apiSignup = (email: string, password: string) => authPost("/api/auth/signup", { email, password })
export const apiGuest = () => authPost("/api/auth/guest", {})

export async function apiLogout(): Promise<void> {
  const base = apiBase()
  const token = getAuthToken()
  if (!base || !token) return
  try {
    await fetch(`${base}/api/auth/logout`, { method: "POST", headers: { Authorization: `Bearer ${token}` } })
  } catch {
    /* best-effort — the client drops the token regardless */
  }
}
