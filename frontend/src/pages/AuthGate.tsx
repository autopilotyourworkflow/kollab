import { useState } from "react"
import { Link } from "react-router-dom"
import { ArrowLeft, ArrowRight, Loader2, Play, ShieldCheck } from "lucide-react"
import { Button } from "../components/ui/Button"
import { useAuth } from "../context/AuthContext"
import { AuthError } from "../lib/auth"
import ccLogo from "../assets/convertcake-logo.png"

/** Sign-in / create-account, with a dominant one-click "Explore the demo" for reviewers.
 *  Rendered only when a backend is configured and no valid session exists. */
export function AuthGate() {
  const { login, signup, guest } = useAuth()
  const [mode, setMode] = useState<"signin" | "signup">("signin")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [busy, setBusy] = useState<null | "form" | "guest">(null)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (busy) return
    setError(null)
    setBusy("form")
    try {
      await (mode === "signin" ? login(email, password) : signup(email, password))
      // success → the provider sets `user`, which unmounts this gate
    } catch (err) {
      setError(err instanceof AuthError ? err.message : "Something went wrong. Please try again.")
      setBusy(null)
    }
  }

  const exploreDemo = async () => {
    if (busy) return
    setError(null)
    setBusy("guest")
    try {
      await guest()
    } catch (err) {
      setError(err instanceof AuthError ? err.message : "Couldn't start the demo. Please try again.")
      setBusy(null)
    }
  }

  return (
    <div className="grid min-h-svh place-items-center bg-surface px-4 py-10">
      <div className="w-full max-w-sm">
        <Link
          to="/"
          className="mb-6 inline-flex items-center gap-1.5 text-[13px] font-medium text-ink-500 transition-colors hover:text-brand"
        >
          <ArrowLeft size={15} /> Back to home
        </Link>

        <div className="rounded-2xl border border-border bg-white p-7 shadow-lg">
          <img src={ccLogo} alt="Convert Cake" className="h-6 w-auto" />
          <h1 className="mt-4 text-[22px] font-bold tracking-[-0.02em] text-ink">
            {mode === "signin" ? "Sign in to Kollab" : "Create your Kollab account"}
          </h1>
          <p className="mt-1 text-[13px] text-ink-500">
            Your shortlists and decisions are saved to your account, synced across devices.
          </p>

          {/* Reviewer path — front and center */}
          <button
            onClick={exploreDemo}
            disabled={!!busy}
            className="group mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-brand px-4 py-3 text-[15px] font-semibold text-white shadow-sm transition-all duration-300 hover:bg-brand-hover hover:shadow-md active:scale-[0.99] disabled:opacity-60"
          >
            {busy === "guest" ? <Loader2 size={17} className="animate-spin" /> : <Play size={16} />}
            {busy === "guest" ? "Spinning up your demo…" : "Explore the demo"}
            {busy !== "guest" && <ArrowRight size={16} className="transition-transform group-hover:translate-x-0.5" />}
          </button>
          <p className="mt-2 flex items-start gap-1.5 text-[11.5px] leading-relaxed text-ink-500">
            <ShieldCheck size={13} className="mt-0.5 shrink-0 text-verified-fg" />
            Reviewing this? Skip the form — you get a private, seeded workspace instantly. No email required.
          </p>

          <div className="my-5 flex items-center gap-3 text-[11px] font-medium uppercase tracking-wide text-ink-400">
            <span className="h-px flex-1 bg-border" /> or {mode === "signin" ? "sign in" : "sign up"}{" "}
            <span className="h-px flex-1 bg-border" />
          </div>

          <form onSubmit={submit} className="space-y-3">
            <div>
              <label htmlFor="auth-email" className="mb-1 block text-[12px] font-medium text-ink-700">
                Email
              </label>
              <input
                id="auth-email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="h-11 w-full rounded-lg border border-border-strong bg-white px-3 text-[14px] text-ink shadow-xs placeholder:text-ink-400 focus:border-brand-300"
                placeholder="you@agency.com"
              />
            </div>
            <div>
              <label htmlFor="auth-password" className="mb-1 block text-[12px] font-medium text-ink-700">
                Password
              </label>
              <input
                id="auth-password"
                type="password"
                autoComplete={mode === "signin" ? "current-password" : "new-password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                className="h-11 w-full rounded-lg border border-border-strong bg-white px-3 text-[14px] text-ink shadow-xs placeholder:text-ink-400 focus:border-brand-300"
                placeholder={mode === "signup" ? "At least 8 characters" : "••••••••"}
              />
            </div>

            {error && (
              <p role="alert" className="rounded-md border border-risk-high-border bg-risk-high-bg px-3 py-2 text-[12px] font-medium text-risk-high-fg">
                {error}
              </p>
            )}

            <Button type="submit" disabled={busy === "form"} className="h-11 w-full"
              leadingIcon={busy === "form" ? <Loader2 size={16} className="animate-spin" /> : undefined}>
              {mode === "signin" ? "Sign in" : "Create account"}
            </Button>
          </form>

          <p className="mt-4 text-center text-[13px] text-ink-500">
            {mode === "signin" ? "New to Kollab?" : "Already have an account?"}{" "}
            <button
              onClick={() => {
                setMode(mode === "signin" ? "signup" : "signin")
                setError(null)
              }}
              className="font-semibold text-brand hover:underline"
            >
              {mode === "signin" ? "Create an account" : "Sign in"}
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}
