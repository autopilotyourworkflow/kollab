import { useEffect, useRef, useState } from "react"
import { Check, ChevronDown, Plus, Gauge, Search, Menu, Rows3, Rows2, X } from "lucide-react"
import { Link, useNavigate } from "react-router-dom"
import { AnimatePresence, motion } from "motion/react"
import { Button } from "../ui/Button"
import { useShortlist } from "../../lib/api"
import { cn } from "../../lib/cn"
import type { Density } from "./AppShell"

/** Per-run cost + latency — Kollab's cost-discipline, always visible. The number
    is the pipeline's own projection for pulling this cohort live (never invented). */
function CostMeter() {
  const { cost } = useShortlist()
  return (
    <div
      className="hidden items-center gap-2 rounded-full bg-brand-50 px-3 py-1.5 md:flex"
      title="Projected cost + wall-clock of pulling this shortlist live through the data adapter"
    >
      <Gauge size={14} className="text-brand" />
      <span className="tnum text-[12px] text-ink-700">
        <span className="font-bold text-brand">${cost.usd.toFixed(2)}</span>
        <span className="mx-1.5 text-brand-100">·</span>
        {cost.seconds.toFixed(1)}s
        <span className="mx-1.5 text-brand-100">·</span>
        <span className="font-medium text-ink-500">
          {cost.cacheHitRate > 0 ? `${Math.round(cost.cacheHitRate * 100)}% cached` : "per live run"}
        </span>
      </span>
    </div>
  )
}

/** Comfortable ↔ Spacious view toggle (persisted). */
function DensityToggle({ density, onDensity }: { density: Density; onDensity: (d: Density) => void }) {
  const opts = [
    { key: "comfortable" as const, icon: Rows3, label: "Comfortable" },
    { key: "spacious" as const, icon: Rows2, label: "Spacious" },
  ]
  return (
    <div className="hidden items-center rounded-full border border-border bg-white p-0.5 shadow-xs sm:flex" role="group" aria-label="Row density">
      {opts.map(({ key, icon: Icon, label }) => (
        <button
          key={key}
          onClick={() => onDensity(key)}
          aria-pressed={density === key}
          title={`${label} view`}
          className={cn(
            "relative grid h-8 w-9 place-items-center rounded-full transition-colors duration-300",
            density === key ? "text-white" : "text-ink-400 hover:text-ink",
          )}
        >
          {density === key && (
            <motion.span
              layoutId="density-thumb"
              className="absolute inset-0 rounded-full bg-brand"
              transition={{ duration: 0.25, ease: [0.25, 1, 0.5, 1] }}
            />
          )}
          <Icon size={15} className="relative" />
          <span className="sr-only">{label}</span>
        </button>
      ))}
    </div>
  )
}

/** Client switcher. One client in the fixtures demo; the menu shows where
    multi-client goes and routes "new client" into the brief flow. Implements
    the ARIA menu keyboard contract: focus moves in on open, arrows rove,
    Escape/Tab close and restore focus to the trigger. */
function ClientMenu() {
  const navigate = useNavigate()
  const data = useShortlist()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    // focus the first menu item on open
    menuRef.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus()
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false)
        triggerRef.current?.focus()
        return
      }
      if (e.key === "Tab") {
        setOpen(false) // menus close on Tab; focus proceeds naturally
        return
      }
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault()
        const items = Array.from(
          menuRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [],
        )
        if (!items.length) return
        const i = items.indexOf(document.activeElement as HTMLElement)
        const next = e.key === "ArrowDown" ? (i + 1) % items.length : (i - 1 + items.length) % items.length
        items[next]?.focus()
      }
    }
    document.addEventListener("mousedown", onDown)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onDown)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  return (
    <div ref={ref} className="relative">
      <button
        ref={triggerRef}
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className={cn(
          "flex items-center gap-2 rounded-full border py-1.5 pl-2 pr-2.5 text-left shadow-xs transition-colors duration-300",
          open ? "border-brand-300 bg-brand-50/50" : "border-border bg-white hover:border-brand-300",
        )}
      >
        <span className="grid h-6 w-6 place-items-center rounded-full bg-brand-50 text-[11px] font-bold text-brand">
          GL
        </span>
        <span className="leading-tight">
          <span className="block text-[13px] font-semibold text-ink">{data.brief.brand}</span>
        </span>
        <span className="ml-1 rounded-full bg-panel px-2 py-0.5 text-[10px] font-medium text-ink-500">
          Skincare
        </span>
        <ChevronDown
          size={14}
          className={cn("text-ink-400 transition-transform duration-200", open && "rotate-180")}
        />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            ref={menuRef}
            role="menu"
            initial={{ opacity: 0, y: -4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98, transition: { duration: 0.12 } }}
            transition={{ duration: 0.18, ease: [0.25, 1, 0.5, 1] }}
            className="absolute left-0 top-full z-[20] mt-2 w-64 origin-top-left overflow-hidden rounded-xl border border-border bg-white p-1.5 shadow-lg"
          >
            <div className="px-2.5 pb-1 pt-1.5 text-[10px] font-semibold uppercase tracking-wider text-ink-500">
              Clients
            </div>
            <button
              role="menuitem"
              onClick={() => {
                setOpen(false)
                triggerRef.current?.focus()
              }}
              className="flex w-full items-center gap-2.5 rounded-lg bg-brand-50/60 px-2.5 py-2 text-left"
            >
              <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-brand-100 text-[11px] font-bold text-brand">
                GL
              </span>
              <span className="min-w-0 flex-1 leading-tight">
                <span className="block truncate text-[13px] font-semibold text-ink">{data.brief.brand}</span>
                <span className="block text-[11px] text-ink-500">Skincare · {data.screened} screened</span>
              </span>
              <Check size={15} className="shrink-0 text-brand" />
            </button>
            <div className="mx-2 my-1.5 h-px bg-border" />
            <button
              role="menuitem"
              onClick={() => {
                setOpen(false)
                navigate("/app/new")
              }}
              className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors duration-200 hover:bg-surface"
            >
              <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-panel text-ink-500">
                <Plus size={15} />
              </span>
              <span className="text-[13px] font-medium text-ink-700">New client shortlist…</span>
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export function Topbar({
  onMenu,
  density,
  onDensity,
  search,
  onSearch,
}: {
  onMenu: () => void
  density: Density
  onDensity: (d: Density) => void
  search: string
  onSearch: (q: string) => void
}) {
  const navigate = useNavigate()
  return (
    <header className="sticky top-0 z-[10] flex h-14 items-center gap-3 border-b border-border bg-white/90 px-4 backdrop-blur sm:px-5">
      <button
        onClick={onMenu}
        className="grid h-11 w-11 shrink-0 place-items-center rounded-md text-ink-500 transition-colors hover:bg-surface lg:hidden"
        aria-label="Open menu"
      >
        <Menu size={18} />
      </button>
      {/* Client context */}
      <div className="flex min-w-0 items-center gap-2">
        <Link
          to="/app"
          className="hidden text-[13px] font-medium text-ink-500 transition-colors duration-200 hover:text-brand sm:inline"
        >
          Shortlists
        </Link>
        <span className="hidden text-ink-400/60 sm:inline">/</span>
        <ClientMenu />
      </div>

      <div className="flex-1" />

      {/* Actions */}
      <div className="relative hidden lg:block">
        <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
        <input
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          onKeyDown={(e) => e.key === "Escape" && onSearch("")}
          className="h-9 w-56 rounded-full border border-border bg-surface pl-8.5 pr-8 text-[13px] text-ink placeholder:text-ink-500 focus:border-brand-300 focus:bg-white"
          placeholder="Search KOLs, signals…"
          aria-label="Search KOLs and signals"
        />
        {search && (
          <button
            onClick={() => onSearch("")}
            className="absolute right-2 top-1/2 grid h-5 w-5 -translate-y-1/2 place-items-center rounded-full text-ink-400 transition-colors hover:bg-panel hover:text-ink"
            aria-label="Clear search"
          >
            <X size={13} />
          </button>
        )}
      </div>
      <DensityToggle density={density} onDensity={onDensity} />
      <CostMeter />
      <Button size="sm" leadingIcon={<Plus size={15} />} onClick={() => navigate("/app/new")}>
        New shortlist
      </Button>
    </header>
  )
}
