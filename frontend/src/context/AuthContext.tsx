import { createContext, useContext, useEffect, useState, type ReactNode } from "react"
import { apiBase } from "../lib/credit"
import {
  apiGuest,
  apiLogin,
  apiLogout,
  apiMe,
  apiSignup,
  clearAuthToken,
  getAuthToken,
  getCachedUser,
  prewarmBackend,
  setAuthToken,
  setCachedUser,
  type AuthResult,
  type AuthUser,
} from "../lib/auth"

/** Two modes:
 *  - "api"   → a backend is configured; the workspace is Neon-backed and gated behind auth.
 *  - "local" → no backend (pure static / bundled fallback); the app runs in the offline
 *    demo the way it always did, so it never dead-ends. */
type Mode = "api" | "local"

interface AuthContextValue {
  user: AuthUser | null
  loading: boolean
  mode: Mode
  login: (email: string, password: string) => Promise<void>
  signup: (email: string, password: string) => Promise<void>
  guest: () => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>")
  return ctx
}

const LOCAL_USER: AuthUser = { id: "local", email: null, isGuest: false }

export function AuthProvider({ children }: { children: ReactNode }) {
  const mode: Mode = apiBase() ? "api" : "local"
  // Optimistic hydration: a returning visitor with a cached user renders the app IMMEDIATELY
  // (no spinner, no wait on the possibly-asleep backend); the token is validated in the
  // background below. Only when there's a token but no cached user do we block on the check.
  const initialUser = mode === "local" ? LOCAL_USER : getAuthToken() ? getCachedUser() : null
  const [user, setUser] = useState<AuthUser | null>(initialUser)
  const [loading, setLoading] = useState(mode === "api" && !!getAuthToken() && !getCachedUser())

  // Wake the sleeping free-tier backend as early as possible, so its cold start overlaps
  // with the app's first render/data fetches instead of stacking on top of them.
  useEffect(() => {
    if (mode === "api") prewarmBackend()
  }, [mode])

  // Validate the stored token. A cached user is already shown, so this runs in the
  // background: a real 401 signs out; a network/cold-start failure keeps the session
  // (never log a valid user out because the server was waking).
  useEffect(() => {
    if (mode !== "api") return
    if (!getAuthToken()) {
      setLoading(false)
      return
    }
    let alive = true
    ;(async () => {
      const r = await apiMe()
      if (!alive) return
      if (r.status === "ok") {
        setUser(r.user)
        setCachedUser(r.user)
      } else if (r.status === "unauthorized") {
        clearAuthToken()
        setUser(null)
      }
      // "unreachable": keep whatever we have (the cached user stays signed in)
      if (alive) setLoading(false)
    })()
    return () => {
      alive = false
    }
  }, [mode])

  // A workspace request that 401s (expired / reaped token) re-gates the app live, so a
  // write is never silently lost against a dead session.
  useEffect(() => {
    if (mode !== "api") return
    const onExpired = () => {
      clearAuthToken()
      setUser(null)
    }
    window.addEventListener("kollab-auth-expired", onExpired)
    return () => window.removeEventListener("kollab-auth-expired", onExpired)
  }, [mode])

  const adopt = (r: AuthResult) => {
    setAuthToken(r.token)
    setCachedUser(r.user) // so the next load renders instantly from cache
    setUser(r.user)
  }

  const login = async (email: string, password: string) => adopt(await apiLogin(email, password))
  const signup = async (email: string, password: string) => adopt(await apiSignup(email, password))
  const guest = async () => adopt(await apiGuest())
  const logout = async () => {
    await apiLogout()
    clearAuthToken()
    setUser(null)
    // The browser must hold no workspace/run data at rest once signed out.
    try {
      localStorage.removeItem("kollab-runs")
    } catch {
      /* ignore */
    }
  }

  return (
    <AuthContext.Provider value={{ user, loading, mode, login, signup, guest, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
