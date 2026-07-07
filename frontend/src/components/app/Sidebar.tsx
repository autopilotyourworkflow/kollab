import { useEffect, useRef, useState } from "react"
import { Sparkles, Settings, LifeBuoy, Code2, LogOut, X } from "lucide-react"
import { Link } from "react-router-dom"
import { cn } from "../../lib/cn"
import { useAuth } from "../../context/AuthContext"
import ccLogo from "../../assets/convertcake-logo.png"

/** The signed-in identity + sign-out (only in API mode; local/offline has no account). */
function UserCard({ onNavigate }: { onNavigate: () => void }) {
  const { user, mode, logout } = useAuth()
  const isGuest = !!user?.isGuest
  const title = mode === "local" ? "Offline demo" : isGuest ? "Guest workspace" : "Signed in"
  const sub = mode === "local" ? "no account needed" : isGuest ? "Explore the demo" : user?.email ?? "your account"
  const initial = (user?.email?.[0] ?? (isGuest ? "G" : "K")).toUpperCase()
  return (
    <div className="flex items-center gap-2.5 rounded-xl bg-surface px-2.5 py-2">
      <div className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-brand-100 text-[11px] font-bold text-brand">
        {initial}
      </div>
      <div className="min-w-0 flex-1 leading-tight">
        <div className="truncate text-[12px] font-semibold text-ink">{title}</div>
        <div className="truncate text-[10px] text-ink-500">{sub}</div>
      </div>
      {mode === "api" && (
        <button
          onClick={() => {
            onNavigate()
            void logout()
          }}
          title="Sign out"
          aria-label="Sign out"
          className="grid h-7 w-7 shrink-0 place-items-center rounded-md text-ink-400 transition-colors hover:bg-panel hover:text-ink"
        >
          <LogOut size={14} />
        </button>
      )}
    </div>
  )
}

interface Tool {
  name: string
  sub: string
  icon: typeof Sparkles
  active?: boolean
  soon?: boolean
}

const tools: Tool[] = [
  { name: "Kollab", sub: "KOL matcher & vetting", icon: Sparkles, active: true },
]

function ToolItem({ tool, onNavigate }: { tool: Tool; onNavigate: () => void }) {
  const Icon = tool.icon
  const inner = (
    <>
      <span
        className={cn(
          "grid h-8 w-8 shrink-0 place-items-center rounded-lg",
          tool.active ? "bg-brand text-white" : "bg-panel text-ink-500",
        )}
      >
        <Icon size={16} strokeWidth={2} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2">
          <span className={cn("truncate text-[13px] font-semibold", tool.active ? "text-brand" : "text-ink")}>
            {tool.name}
          </span>
          {tool.soon && (
            <span className="rounded-full bg-panel px-1.5 py-px text-[10px] font-medium uppercase tracking-wide text-ink-500">
              Soon
            </span>
          )}
        </span>
        <span className="mt-0.5 block truncate text-[11px] text-ink-500">{tool.sub}</span>
      </span>
    </>
  )
  if (tool.soon) {
    return (
      <div className="flex w-full cursor-default items-center gap-3 rounded-xl px-2.5 py-2 opacity-50">
        {inner}
      </div>
    )
  }
  // the active tool is a real link — clicking it always returns to its home view
  return (
    <Link
      to="/app"
      aria-current={tool.active ? "page" : undefined}
      onClick={onNavigate}
      className={cn(
        "flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-left transition-colors duration-300",
        tool.active ? "bg-brand-50" : "hover:bg-surface",
      )}
    >
      {inner}
    </Link>
  )
}

function useIsDesktop() {
  const [desktop, setDesktop] = useState(() => window.matchMedia("(min-width: 1024px)").matches)
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 1024px)")
    const on = () => setDesktop(mq.matches)
    mq.addEventListener("change", on)
    return () => mq.removeEventListener("change", on)
  }, [])
  return desktop
}

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const isDesktop = useIsDesktop()
  const closeRef = useRef<HTMLButtonElement>(null)

  // Drawer a11y (mobile): move focus in on open, close on Escape, restore focus
  // to the opener on close. When closed off-screen, `inert` removes it from the
  // tab order entirely (desktop keeps it interactive — it's statically visible).
  useEffect(() => {
    if (!open || isDesktop) return
    const opener = document.activeElement as HTMLElement | null
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose()
    }
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("keydown", onKey)
      opener?.focus?.()
    }
  }, [open, isDesktop, onClose])

  return (
    <>
      {/* Mobile backdrop */}
      <div
        className={cn(
          "fixed inset-0 z-[40] bg-ink-900/40 backdrop-blur-sm transition-opacity duration-200 lg:hidden",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={onClose}
        aria-hidden
      />

      <aside
        inert={!open && !isDesktop}
        className={cn(
          "fixed inset-y-0 left-0 z-[50] flex w-[248px] shrink-0 flex-col overflow-hidden border-r border-border bg-white transition-transform duration-200 ease-out",
          // Desktop: pin to the viewport (sticky, one screen tall, self-start so it
          // never stretches with the page) — the rail stays put no matter how many
          // shortlists the content grows to, and never scrolls with the page.
          "lg:sticky lg:top-0 lg:z-auto lg:h-svh lg:translate-x-0 lg:self-start",
          open ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
        )}
      >
        {/* Brand — real Convert Cake logo, links back to the landing */}
        <div className="flex items-center gap-2.5 px-4 py-4">
          <Link
            to="/"
            title="Back to the Kollab landing page"
            className="min-w-0 rounded-md transition-opacity duration-300 hover:opacity-80"
          >
            <img src={ccLogo} alt="Convert Cake — back to home" className="h-6 w-auto" />
            <span className="mt-1 block text-[10px] font-semibold uppercase tracking-wider text-ink-500">
              Internal Tools
            </span>
          </Link>
          <button
            ref={closeRef}
            onClick={onClose}
            className="ml-auto grid h-8 w-8 place-items-center rounded-md text-ink-400 transition-colors hover:bg-surface hover:text-ink lg:hidden"
            aria-label="Close menu"
          >
            <X size={18} />
          </button>
        </div>

        {/* Tools */}
        <nav className="flex-1 px-3 py-2">
          <div className="px-2.5 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-ink-500">
            Tools
          </div>
          <div className="space-y-1">
            {tools.map((t) => (
              <ToolItem key={t.name} tool={t} onNavigate={onClose} />
            ))}
          </div>
        </nav>

        {/* Footer — Settings (bring-your-own-key) + the operating guide */}
        <div className="border-t border-border px-3 py-3">
          <div className="flex items-center gap-1 px-1 pb-3">
            <Link
              to="/app/settings"
              onClick={onClose}
              className="flex flex-1 items-center gap-2 rounded-md px-1.5 py-1 text-ink-700 transition-colors hover:bg-surface hover:text-brand"
              title="Settings — bring your own API keys"
            >
              <Settings size={15} />
              <span className="text-[12px] font-medium">Settings</span>
            </Link>
            <Link
              to="/app/guide"
              onClick={onClose}
              className="flex flex-1 items-center gap-2 rounded-md px-1.5 py-1 text-ink-700 transition-colors hover:bg-surface hover:text-brand"
              title="Operating guide"
            >
              <LifeBuoy size={15} />
              <span className="text-[12px] font-medium">Guide</span>
            </Link>
            <Link
              to="/tech"
              onClick={onClose}
              className="flex flex-1 items-center gap-2 rounded-md px-1.5 py-1 text-ink-700 transition-colors hover:bg-surface hover:text-brand"
              title="Engineering & architecture"
            >
              <Code2 size={15} />
              <span className="text-[12px] font-medium">Tech</span>
            </Link>
          </div>
          <UserCard onNavigate={onClose} />
        </div>
      </aside>
    </>
  )
}
