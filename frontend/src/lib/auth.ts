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
  } catch {
    /* nothing to clear */
  }
}

/** Hydrate the current user from the stored token, or null (no backend / no or bad token). */
export async function apiMe(): Promise<AuthUser | null> {
  const base = apiBase()
  const token = getAuthToken()
  if (!base || !token) return null
  try {
    const res = await fetch(`${base}/api/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
    if (!res.ok) return null
    return (await res.json()) as AuthUser
  } catch {
    return null
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
