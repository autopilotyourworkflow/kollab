import { useMemo, useState, useEffect } from "react"
import { useOutletContext, useParams, Navigate, Link } from "react-router-dom"
import { AnimatePresence, motion } from "motion/react"
import {
  ShieldAlert,
  Gauge,
  ArrowUpDown,
  SearchX,
  Share2,
  Search as SearchIcon,
  Plus,
  Loader2,
  ArrowLeft,
} from "lucide-react"
import type { HitlStatus, Kol } from "../lib/types"
import { cn } from "../lib/cn"
import { startRun } from "../lib/api"
import { apiBase } from "../lib/credit"
import { plans, loadRunPlan, saveRunPlan, fromPreset } from "../lib/runPlan"
import { addRun, WORKSPACE_UPDATED } from "../lib/runsStore"
import {
  getEntry,
  setDecision as persistDecision,
  appendDemoBatch,
  demoRemaining,
  counts,
  type ShortlistEntry,
} from "../lib/workspace"
import { KolRow, COLS } from "../components/shortlist/KolRow"
import { ExportModal } from "../components/shortlist/ExportModal"
import { OverlapPanel } from "../components/shortlist/OverlapPanel"
import { Button } from "../components/ui/Button"
import { StatChip } from "../components/ui/brand"
import type { AppContext } from "../components/app/AppShell"

/** Topbar search matches handle, name, category, tier, and fraud-signal labels. */
function matchesSearch(k: Kol, q: string): boolean {
  const hay = [k.handle, k.name, k.category, k.categoryTh, k.tier, k.region,
    ...k.risk.signals.map((s) => s.label)].join(" ").toLowerCase()
  return hay.includes(q)
}

type Filter = "all" | "recommended" | "flagged"

const filters: { key: Filter; label: string }[] = [
  { key: "all", label: "Shortlist" },
  { key: "recommended", label: "Recommended" },
  { key: "flagged", label: "Flagged" },
]

type SortKey = "fit" | "followers" | "engagement" | "risk"
const sortOptions: { key: SortKey; label: string }[] = [
  { key: "fit", label: "Fit score" },
  { key: "followers", label: "Followers" },
  { key: "engagement", label: "Engagement" },
  { key: "risk", label: "Risk first" },
]
const riskRank = { high: 2, medium: 1, clear: 0 } as const

function useIsMobile() {
  const [m, setM] = useState(() => window.matchMedia("(max-width: 639px)").matches)
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 639px)")
    const on = () => setM(mq.matches)
    mq.addEventListener("change", on)
    return () => mq.removeEventListener("change", on)
  }, [])
  return m
}

export function Shortlist() {
  const { id = "" } = useParams()
  const { search, setSearch } = useOutletContext<AppContext>()
  const [entry, setEntry] = useState<ShortlistEntry | null>(() => getEntry(id))
  const refresh = () => setEntry(getEntry(id))

  // When the run dock merges a finished run's creators into THIS shortlist, re-read.
  useEffect(() => {
    const on = (e: Event) => {
      const detail = (e as CustomEvent).detail as { shortlistId?: string } | undefined
      if (detail?.shortlistId === id) setEntry(getEntry(id))
    }
    window.addEventListener(WORKSPACE_UPDATED, on)
    return () => window.removeEventListener(WORKSPACE_UPDATED, on)
  }, [id])

  const [filter, setFilter] = useState<Filter>("all")
  const [sort, setSort] = useState<SortKey>("fit")
  const [showExport, setShowExport] = useState(false)
  const [adding, setAdding] = useState(false)
  const [justAdded, setJustAdded] = useState<number | null>(null)
  const [startedHint, setStartedHint] = useState(false)
  // Run depth for the next "Add more" (expand) run — the per-run setting.
  const presets = plans.presets.filter((p) => p.key !== "custom")
  const [depthKey, setDepthKey] = useState<string>(() => {
    const k = loadRunPlan().key
    return presets.some((p) => p.key === k) ? k : plans.defaultPreset
  })
  const isMobile = useIsMobile()

  const kols = useMemo(() => entry?.kols ?? [], [entry])

  const setDecision = (kolId: string, status: HitlStatus, reason?: string) => {
    if (!entry) return
    persistDecision(entry.id, kolId, { status, reason })
    refresh()
  }

  // "Add more results": accumulate NEW creators into this same shortlist. A live
  // backend does a real expand-run (never re-buys held data); with no backend the
  // demo pool stands in so accumulation is visible either way.
  // Demo depth → how many pool creators one expand reveals (live runs use the
  // preset's real creator/comment volumes on the backend).
  const DEMO_BATCH: Record<string, number> = { scan: 2, standard: 4, deep: 8 }

  const addMore = async () => {
    if (!entry || adding) return
    // No backend -> demo pool (instant, offline).
    if (!apiBase()) {
      const n = appendDemoBatch(entry.id, DEMO_BATCH[depthKey] ?? 4)
      setJustAdded(n)
      window.setTimeout(() => setJustAdded(null), 4000)
      refresh()
      return
    }
    // Live -> start a background run and hand it to the dock (fire-and-forget). The
    // dock polls, merges on done, and the run survives refresh/close. If it can't
    // even start, fall back to the demo pool.
    setAdding(true)
    try {
      const runId = await startRun(entry.brief, depthKey)
      if (runId) {
        addRun({
          id: runId, shortlistId: entry.id, brand: entry.brief.brand,
          preset: depthKey, startedAt: Date.now(), status: "running",
        })
        setStartedHint(true)
        window.setTimeout(() => setStartedHint(false), 7000)
      } else {
        const n = appendDemoBatch(entry.id, DEMO_BATCH[depthKey] ?? 4)
        setJustAdded(n)
        window.setTimeout(() => setJustAdded(null), 4000)
        refresh()
      }
    } finally {
      setAdding(false)
    }
  }

  const q = search.trim().toLowerCase()
  const rows = useMemo(() => {
    const sorted = [...kols].sort((a, b) => {
      if (sort === "followers") return b.followers - a.followers
      if (sort === "engagement") return b.engagementRate - a.engagementRate
      if (sort === "risk") return riskRank[b.risk.level] - riskRank[a.risk.level] || b.fitScore - a.fitScore
      return b.fitScore - a.fitScore
    })
    const searched = q ? sorted.filter((k) => matchesSearch(k, q)) : sorted
    if (filter === "recommended")
      return searched.filter((k) => k.risk.level === "clear" && k.fitScore >= 70)
    if (filter === "flagged") return searched.filter((k) => k.risk.level !== "clear")
    return searched
  }, [filter, sort, q, kols])

  const searchedAll = useMemo(
    () => (q ? kols.filter((k) => matchesSearch(k, q)) : kols),
    [q, kols],
  )

  // A missing/deleted id sends the user back to the Dashboard rather than a blank page.
  if (!entry) return <Navigate to="/app" replace />

  const c = counts(kols)
  const counts_by: Record<Filter, number> = {
    all: searchedAll.length,
    recommended: searchedAll.filter((k) => k.risk.level === "clear" && k.fitScore >= 70).length,
    flagged: searchedAll.filter((k) => k.risk.level !== "clear").length,
  }
  const totals = {
    recommended: c.recommended,
    flagged: c.flagged,
    failed: kols.filter((k) => k.risk.level === "high").length,
  }
  const audience = entry.brief.audience
  const pillars = entry.brief.pillars
  const remaining = demoRemaining(entry.id)
  const canAdd = remaining > 0 || !!apiBase()

  return (
    <div className="px-[var(--d-page-px)] py-[var(--d-page-py)]">
      <Link
        to="/app"
        className="mb-3 inline-flex min-h-[28px] items-center gap-1.5 text-[12px] font-medium text-ink-500 transition-colors duration-200 hover:text-brand"
      >
        <ArrowLeft size={14} /> All shortlists
      </Link>

      {/* Header */}
      <div className="mb-[var(--d-block-gap)]">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-[26px] font-bold tracking-[-0.02em] text-ink">
              {entry.brief.brand}{" "}
              <span className="font-thai font-semibold text-ink-400">· {entry.brief.brandTh}</span>
            </h1>
            <p className="mt-1 max-w-2xl text-[13px] font-medium text-ink-500">{audience}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {/* Per-run depth: what the next "Add more" run will source & spend */}
            <label htmlFor="run-depth" className="flex items-center gap-1.5 rounded-md border border-border bg-white pl-2.5 pr-1 shadow-xs">
              <Gauge size={13} className="text-ink-400" />
              <select
                id="run-depth"
                value={depthKey}
                onChange={(e) => {
                  setDepthKey(e.target.value)
                  const p = presets.find((x) => x.key === e.target.value)
                  if (p) saveRunPlan(fromPreset(p))
                }}
                title="Depth & budget for the next Add-more run"
                className="h-8 cursor-pointer bg-transparent py-0 pr-1 text-[12px] font-medium text-ink-700 focus:outline-none"
              >
                {presets.map((p) => (
                  <option key={p.key} value={p.key}>
                    {p.label} · ≈${p.estUsd.toFixed(2)}
                  </option>
                ))}
              </select>
            </label>
            <Button
              size="sm"
              variant="secondary"
              leadingIcon={adding ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
              onClick={addMore}
              disabled={!canAdd || adding}
              title={canAdd ? "Source & vet more creators into this shortlist" : "No more demo creators — deploy the backend to source live"}
            >
              {adding ? "Starting…" : "Add more"}
            </Button>
            <Button size="sm" leadingIcon={<Share2 size={15} />} onClick={() => setShowExport(true)}>
              Export
            </Button>
          </div>
        </div>

        {/* run start + accumulation feedback (live progress lives in the run dock) */}
        {adding && (
          <p className="mt-2 flex items-center gap-1.5 text-[12px] text-ink-500">
            <Loader2 size={12} className="animate-spin" /> Starting a live run…
          </p>
        )}
        {startedHint && (
          <motion.p
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-2 text-[12px] font-medium text-brand"
          >
            Live sourcing started — follow it in the run dock (bottom-right). It keeps going even
            if you leave, refresh, or close the tab, and merges in when it's done.
          </motion.p>
        )}
        {justAdded !== null && (
          <motion.p
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className={cn("mt-2 text-[12px] font-medium", justAdded > 0 ? "text-verified-fg" : "text-ink-500")}
          >
            {justAdded > 0
              ? `+${justAdded} new creator${justAdded === 1 ? "" : "s"} sourced, vetted, and merged — no duplicates.`
              : "No new creators to add right now."}
          </motion.p>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-3">
          <div className="flex flex-wrap items-center gap-1.5">
            {pillars.map((p) => (
              <span key={p} className="rounded-full bg-brand-50 px-3 py-1 text-[12px] font-medium text-brand">
                {p}
              </span>
            ))}
            <span
              title={`${entry.runs} run${entry.runs === 1 ? "" : "s"} accumulated into this shortlist`}
              className="rounded-full border border-dashed border-border-strong px-2.5 py-1 text-[11px] font-medium text-ink-500"
            >
              {entry.runs} {entry.runs === 1 ? "run" : "runs"}
            </span>
          </div>
          <div className="ml-auto flex flex-wrap items-center gap-2.5">
            <StatChip value={kols.length} label="creators" tone="ink" className="bg-panel" />
            <StatChip value={totals.recommended} label="recommended" />
            <StatChip value={totals.flagged} label="flagged" tone="risk" className="bg-risk-high-bg" />
          </div>
        </div>
      </div>

      {/* Flagged banner */}
      {totals.failed > 0 && (
        <button
          onClick={() => setFilter("flagged")}
          className="mb-[var(--d-block-gap)] flex w-full items-center gap-3 rounded-2xl border border-risk-high-border bg-risk-high-bg px-5 py-3.5 text-left transition-colors duration-300 hover:brightness-[0.99]"
        >
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-white">
            <ShieldAlert size={17} className="text-risk-high-fg" />
          </span>
          <div className="flex-1">
            <div className="text-[13px] font-semibold text-risk-high-fg">
              {totals.failed} KOLs look strong but failed authenticity vetting
            </div>
            <div className="text-[12px] text-ink-700">
              A follower-count tool would recommend them. Kollab caught a comment pod and bought followers
              {totals.flagged > totals.failed
                ? ` — plus ${totals.flagged - totals.failed} more flagged for a lighter check. Review before they reach the client.`
                : " — review before they reach the client."}
            </div>
          </div>
          <span className="shrink-0 text-[12px] font-semibold text-risk-high-fg">Review →</span>
        </button>
      )}

      {/* Mobile/tablet search */}
      <div className="relative mb-3 lg:hidden">
        <SearchIcon size={15} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-400" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="h-10 w-full rounded-full border border-border bg-white pl-9 pr-4 text-[14px] text-ink shadow-xs placeholder:text-ink-500 focus:border-brand-300"
          placeholder="Search KOLs, signals…"
          aria-label="Search KOLs and signals"
        />
      </div>

      {/* Commenter-overlap dedup (only shows when a pair shares a meaningful audience) */}
      <OverlapPanel pairs={entry.commenterOverlap} />

      {/* Toolbar */}
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 max-w-full items-center gap-1 overflow-x-auto rounded-full border border-border bg-white p-1 shadow-xs">
          {filters.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              aria-pressed={filter === f.key}
              className={cn(
                "relative rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-colors duration-300",
                filter === f.key ? "text-white" : "text-ink-500 hover:bg-surface",
              )}
            >
              {filter === f.key && (
                <motion.span
                  layoutId="filter-pill"
                  className="absolute inset-0 rounded-full bg-brand"
                  transition={{ duration: 0.25, ease: [0.25, 1, 0.5, 1] }}
                />
              )}
              <span className="relative">{f.label}</span>
              <span className={cn("tnum relative ml-1.5", filter === f.key ? "text-white/70" : "text-ink-400")}>
                {counts_by[f.key]}
              </span>
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="sort-kol" className="flex items-center gap-1.5 text-[12px] text-ink-500">
            <ArrowUpDown size={14} /> Sort
          </label>
          <select
            id="sort-kol"
            value={sort}
            onChange={(e) => setSort(e.target.value as SortKey)}
            className="h-8 cursor-pointer rounded-full border border-border bg-white px-3 text-[12px] font-medium text-ink-700 shadow-xs focus:border-brand-300"
          >
            {sortOptions.map((o) => (
              <option key={o.key} value={o.key}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-2xl border border-border bg-white shadow-sm">
        {rows.length === 0 ? (
          <div className="flex flex-col items-center gap-2 px-5 py-16 text-center">
            <div className="grid h-11 w-11 place-items-center rounded-full bg-panel text-ink-400">
              <SearchX size={20} />
            </div>
            <div className="text-[14px] font-semibold text-ink">
              {q ? <>Nothing matches “{search.trim()}”</> : "No KOLs in this view"}
            </div>
            <div className="max-w-xs text-[12px] text-ink-500">
              {q
                ? "Try a handle, a category, or a fraud signal — e.g. “comment pod”."
                : "No creators match the current filter. Try “All screened”, or Add more to source new ones."}
            </div>
            <button
              onClick={() => (q ? setSearch("") : setFilter("all"))}
              className="mt-1 text-[12px] font-medium text-brand hover:underline"
            >
              {q ? "Clear search" : "Show full shortlist"}
            </button>
          </div>
        ) : isMobile ? (
          <div className="divide-y divide-border">
            <AnimatePresence initial={false} mode="popLayout">
              {rows.map((kol, i) => (
                <motion.div
                  key={kol.id}
                  layout="position"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, transition: { duration: 0.12 } }}
                  transition={{ duration: 0.2, ease: [0.25, 1, 0.5, 1] }}
                >
                  <KolRow
                    variant="card"
                    kol={kol}
                    brief={entry.brief}
                    rank={i + 1}
                    decision={entry.decisions[kol.id] ?? { status: kol.hitl }}
                    onDecide={(status, reason) => setDecision(kol.id, status, reason)}
                  />
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <div className="min-w-[940px]">
              <div className={cn(COLS, "border-b border-border bg-surface px-5 py-2.5")}>
                <div className="pl-8 text-[11px] font-semibold uppercase tracking-wide text-ink-500">KOL</div>
                <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-500">Tier</div>
                <div className="text-right text-[11px] font-semibold uppercase tracking-wide text-ink-500">
                  Followers
                </div>
                <div className="text-right text-[11px] font-semibold uppercase tracking-wide text-ink-500">
                  Med. views
                </div>
                <div className="text-right text-[11px] font-semibold uppercase tracking-wide text-ink-500">ER</div>
                <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-500">Authenticity</div>
                <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-500">Fit score</div>
                <div />
              </div>
              <AnimatePresence initial={false} mode="popLayout">
                {rows.map((kol, i) => (
                  <motion.div
                    key={kol.id}
                    layout="position"
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, transition: { duration: 0.12 } }}
                    transition={{ duration: 0.2, ease: [0.25, 1, 0.5, 1] }}
                  >
                    <KolRow
                      variant="row"
                      kol={kol}
                      brief={entry.brief}
                      rank={i + 1}
                      decision={entry.decisions[kol.id] ?? { status: kol.hitl }}
                      onDecide={(status, reason) => setDecision(kol.id, status, reason)}
                    />
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </div>
        )}
      </div>

      <p className="mt-3 text-[11px] text-ink-500">
        <span
          className={cn(
            "mr-2 inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 font-medium",
            entry.source === "api" ? "bg-verified-bg text-verified-fg" : "bg-panel text-ink-700",
          )}
        >
          <span aria-hidden className={cn("h-1.5 w-1.5 rounded-full", entry.source === "api" ? "bg-verified" : "bg-ink-400")} />
          {entry.source === "api" ? "includes live-sourced creators · /api/shortlist" : "bundled demo fixtures"}
        </span>
        Every metric is tagged{" "}
        <span className="font-medium text-ink-700">measured / inferred / estimated</span>; production points the data
        adapter at a licensed KOL feed. Fraud-flagged handles are anonymised in the live run. Decisions and added
        creators are saved to this shortlist automatically.
      </p>

      <AnimatePresence>
        {showExport && (
          <ExportModal kols={kols} brief={entry.brief} onClose={() => setShowExport(false)} />
        )}
      </AnimatePresence>
    </div>
  )
}
