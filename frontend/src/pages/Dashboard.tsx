import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { motion } from "motion/react"
import { Plus, ShieldAlert, Users, Trash2, Layers, Clock, ArrowRight, Loader2 } from "lucide-react"
import { Button } from "../components/ui/Button"
import { GraphCard } from "../components/app/GraphCard"
import { listShortlists, deleteEntry, counts, type ShortlistEntry } from "../lib/workspace"
import { WORKSPACE_UPDATED } from "../lib/runsStore"
import { cn } from "../lib/cn"

function relTime(ts: number): string {
  const s = Math.max(0, Math.round((Date.now() - ts) / 1000))
  if (s < 60) return "just now"
  const m = Math.round(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.round(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.round(h / 24)
  if (d < 30) return `${d}d ago`
  return new Date(ts).toLocaleDateString()
}

function Chip({ value, label, tone }: { value: number; label: string; tone: "ink" | "good" | "risk" }) {
  const cls =
    tone === "good"
      ? "bg-verified-bg text-verified-fg"
      : tone === "risk"
        ? "bg-risk-high-bg text-risk-high-fg"
        : "bg-panel text-ink-700"
  return (
    <span className={cn("inline-flex items-baseline gap-1 rounded-full px-2.5 py-1 text-[12px] font-medium", cls)}>
      <span className="tnum font-bold">{value}</span>
      {label}
    </span>
  )
}

function ShortlistCard({ entry, onDelete }: { entry: ShortlistEntry; onDelete: (id: string) => void }) {
  const navigate = useNavigate()
  const [confirming, setConfirming] = useState(false)
  const c = counts(entry.kols)

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: [0.25, 1, 0.5, 1] }}
      onClick={() => navigate(`/app/s/${entry.id}`)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault()
          navigate(`/app/s/${entry.id}`)
        }
      }}
      className="group cursor-pointer rounded-2xl border border-border bg-white p-5 shadow-sm transition-shadow duration-200 hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300"
    >
      <div className="flex items-start gap-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand-50 text-[15px] font-bold text-brand">
          {entry.brief.brand.slice(0, 1).toUpperCase()}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="truncate text-[15px] font-bold text-ink">{entry.brief.brand}</span>
            {entry.brief.brandTh && (
              <span className="font-thai truncate text-[12px] text-ink-400">· {entry.brief.brandTh}</span>
            )}
          </div>
          <div className="truncate text-[12px] text-ink-500">{entry.brief.category}</div>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide",
            entry.source === "api" ? "bg-verified-bg text-verified-fg" : "bg-panel text-ink-500",
          )}
          title={entry.source === "api" ? "Includes live-sourced creators" : "Demo fixtures"}
        >
          {entry.source === "api" ? "live" : "demo"}
        </span>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        <Chip value={entry.kols.length} label="creators" tone="ink" />
        <Chip value={c.recommended} label="recommended" tone="good" />
        <Chip value={c.flagged} label="flagged" tone="risk" />
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-border pt-3 text-[11px] text-ink-500">
        <span className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1" title="Runs">
            <Layers size={12} /> {entry.runs} {entry.runs === 1 ? "run" : "runs"}
          </span>
          <span className="inline-flex items-center gap-1">
            <Clock size={12} /> {relTime(entry.updatedAt)}
          </span>
        </span>

        {confirming ? (
          <span className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
            <span className="text-risk-high-fg">Delete?</span>
            <button
              onClick={() => onDelete(entry.id)}
              className="rounded px-1.5 py-0.5 font-semibold text-risk-high-fg hover:bg-risk-high-bg"
            >
              Yes
            </button>
            <button onClick={() => setConfirming(false)} className="rounded px-1.5 py-0.5 font-medium text-ink-500 hover:bg-surface">
              No
            </button>
          </span>
        ) : (
          <button
            onClick={(e) => {
              e.stopPropagation()
              setConfirming(true)
            }}
            aria-label={`Delete ${entry.brief.brand} shortlist`}
            className="grid h-7 w-7 place-items-center rounded-md text-ink-400 opacity-0 transition-opacity hover:bg-surface hover:text-risk-high-fg group-hover:opacity-100 focus-visible:opacity-100"
          >
            <Trash2 size={14} />
          </button>
        )}
      </div>
    </motion.div>
  )
}

export function Dashboard() {
  const navigate = useNavigate()
  const [entries, setEntries] = useState<ShortlistEntry[]>([])
  const [loading, setLoading] = useState(true)

  const refresh = () => {
    listShortlists()
      .then(setEntries)
      .catch(() => {
        /* keep the last-known list on a transient error */
      })
      .finally(() => setLoading(false))
  }
  useEffect(refresh, [])
  // Re-read when a run merges creators, or when the tab regains focus (another device).
  useEffect(() => {
    const on = () => refresh()
    window.addEventListener(WORKSPACE_UPDATED, on)
    window.addEventListener("focus", on)
    return () => {
      window.removeEventListener(WORKSPACE_UPDATED, on)
      window.removeEventListener("focus", on)
    }
  }, [])

  const onDelete = (id: string) => {
    setEntries((es) => es.filter((e) => e.id !== id)) // optimistic
    deleteEntry(id).catch(refresh)
  }

  const totalFlagged = entries.reduce((n, e) => n + counts(e.kols).flagged, 0)
  const firstLoad = loading && entries.length === 0

  return (
    <div className="px-[var(--d-page-px)] py-[var(--d-page-py)]">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[26px] font-bold tracking-[-0.02em] text-ink">Shortlists</h1>
          <p className="mt-1 text-[13px] text-ink-500">
            {firstLoad ? (
              "Loading your campaigns…"
            ) : (
              <>
                {entries.length} {entries.length === 1 ? "campaign" : "campaigns"}
                {totalFlagged > 0 && <> · {totalFlagged} creators flagged across all</>} · open one to review, or start a
                new shortlist.
              </>
            )}
          </p>
        </div>
        <Button onClick={() => navigate("/app/new")} leadingIcon={<Plus size={16} />}>
          New shortlist
        </Button>
      </div>

      {firstLoad ? (
        // The header + action render immediately; only the list area waits on the backend
        // (which may be cold-starting) — the page is never a blank full-screen spinner.
        <div className="grid min-h-[40svh] place-items-center rounded-2xl border border-dashed border-border bg-white/50">
          <Loader2 size={24} className="animate-spin text-brand" />
        </div>
      ) : entries.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-border-strong bg-white px-6 py-16 text-center">
          <span className="grid h-12 w-12 place-items-center rounded-full bg-brand-50 text-brand">
            <Users size={22} />
          </span>
          <div className="text-[15px] font-semibold text-ink">No shortlists yet</div>
          <p className="max-w-sm text-[13px] text-ink-500">
            Start by pasting a client's website — Kollab reads their brand, then finds and vets matching Thai TikTok KOLs.
          </p>
          <Button onClick={() => navigate("/app/new")} leadingIcon={<Plus size={16} />} className="mt-1">
            New shortlist
          </Button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {entries.map((e) => (
            <ShortlistCard key={e.id} entry={e} onDelete={onDelete} />
          ))}
          {/* new-shortlist tile */}
          <button
            onClick={() => navigate("/app/new")}
            className="flex min-h-[168px] flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-border-strong bg-surface/40 text-ink-500 transition-colors duration-200 hover:border-brand-300 hover:text-brand"
          >
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-white shadow-xs">
              <Plus size={18} />
            </span>
            <span className="text-[13px] font-semibold">New shortlist</span>
          </button>
        </div>
      )}

      {/* Fraud-recall moat — the proprietary commenter graph that improves every run */}
      <div className="mt-8 rounded-2xl border border-border bg-white p-5 shadow-sm">
        <h2 className="mb-3 text-[14px] font-semibold text-ink">Fraud-recall moat</h2>
        <GraphCard />
      </div>

      <p className="mt-6 flex items-center gap-1.5 text-[11px] text-ink-500">
        <ShieldAlert size={12} className="text-ink-400" />
        Shortlists are saved to your Kollab workspace. Each one accumulates creators as you run again — new results are
        vetted and merged, never duplicated.
        <button onClick={() => navigate("/app/new")} className="ml-1 inline-flex items-center gap-0.5 font-medium text-brand hover:underline">
          Add one <ArrowRight size={11} />
        </button>
      </p>
    </div>
  )
}
