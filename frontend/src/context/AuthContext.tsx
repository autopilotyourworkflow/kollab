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
  setAuthToken,
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
  const [user, setUser] = useState<AuthUser | null>(mode === "local" ? LOCAL_USER : null)
  const [loading, setLoading] = useState(mode === "api")

  // Reuse-before-mint: a returning visitor with a valid token skips the gate entirely.
  useEffect(() => {
    if (mode !== "api") return
    let alive = true
    ;(async () => {
      if (getAuthToken()) {
        const u = await apiMe()
        if (!alive) return
        if (u) setUser(u)
        else clearAuthToken()
      }
      if (alive) setLoading(false)
    })()
    return () => {
      alive = false
    }
  }, [mode])

  const adopt = (r: AuthResult) => {
    setAuthToken(r.token)
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
