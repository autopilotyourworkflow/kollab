import { useMemo, useState, useEffect } from "react"
import { useOutletContext } from "react-router-dom"
import { AnimatePresence, motion } from "motion/react"
import { ShieldAlert, Globe, ArrowUpDown, SearchX, Share2, Search as SearchIcon } from "lucide-react"
import type { HitlStatus, Kol } from "../lib/types"
import { cn } from "../lib/cn"
import { useShortlist, loadSavedBrief } from "../lib/api"
import { KolRow, COLS } from "../components/shortlist/KolRow"
import { ExportModal } from "../components/shortlist/ExportModal"
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
  const { search, setSearch } = useOutletContext<AppContext>()
  const data = useShortlist()
  // the AM's edited brief from /app/new (persisted HITL) overrides the fixture brief
  const savedBrief = useMemo(loadSavedBrief, [])
  const audience = savedBrief?.audience ?? data.brief.audience
  const pillars = savedBrief?.pillars ?? data.brief.pillars
  const [filter, setFilter] = useState<Filter>("all")
  const [sort, setSort] = useState<SortKey>("fit")
  const [showExport, setShowExport] = useState(false)
  const isMobile = useIsMobile()
  const [statuses, setStatuses] = useState<Record<string, { status: HitlStatus; reason?: string }>>(
    () => Object.fromEntries(data.kols.map((k) => [k.id, { status: k.hitl }])),
  )
  // keep HITL decisions when the payload swaps from fixtures to the live API
  useEffect(() => {
    setStatuses((s) => Object.fromEntries(data.kols.map((k) => [k.id, s[k.id] ?? { status: k.hitl }])))
  }, [data.kols])

  const setDecision = (id: string, status: HitlStatus, reason?: string) =>
    setStatuses((s) => ({ ...s, [id]: status === "pending" ? { status: "pending" } : { status, reason } }))

  const q = search.trim().toLowerCase()
  const rows = useMemo(() => {
    const sorted = [...data.kols].sort((a, b) => {
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
  }, [filter, sort, q, data.kols])

  // tab counts respect the active search, so the numbers never lie
  const searchedAll = useMemo(
    () => (q ? data.kols.filter((k) => matchesSearch(k, q)) : data.kols),
    [q, data.kols],
  )
  const counts: Record<Filter, number> = {
    all: searchedAll.length,
    recommended: searchedAll.filter((k) => k.risk.level === "clear" && k.fitScore >= 70).length,
    flagged: searchedAll.filter((k) => k.risk.level !== "clear").length,
  }
  // headline totals (search-independent) — all derived from the active payload
  const totals = {
    recommended: data.kols.filter((k) => k.risk.level === "clear" && k.fitScore >= 70).length,
    flagged: data.kols.filter((k) => k.risk.level !== "clear").length,
    failed: data.kols.filter((k) => k.risk.level === "high").length,
  }

  return (
    <div className="px-[var(--d-page-px)] py-[var(--d-page-py)]">
      {/* Header */}
      <div className="mb-[var(--d-block-gap)]">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-[26px] font-bold tracking-[-0.02em] text-ink">
              {data.brief.brand}{" "}
              <span className="font-thai font-semibold text-ink-400">· {data.brief.brandTh}</span>
            </h1>
            <p className="mt-1 max-w-2xl text-[13px] font-medium text-ink-500">{audience}</p>
          </div>
          <div className="flex items-center gap-2">
            {/* fictional demo brand — deliberately NOT a link (no live site to 404 on) */}
            <span
              title="Fictional demo brand — no live website"
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-white px-3 py-1.5 text-[12px] font-medium text-ink-700 shadow-xs"
            >
              <Globe size={14} className="text-ink-400" />
              {data.brief.website}
            </span>
            <Button size="sm" leadingIcon={<Share2 size={15} />} onClick={() => setShowExport(true)}>
              Export
            </Button>
          </div>
        </div>

        {/* pillars + stat chips — their tint language; all numbers derive from the payload */}
        <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-3">
          <div className="flex flex-wrap items-center gap-1.5">
            {pillars.map((p) => (
              <span
                key={p}
                className="rounded-full bg-brand-50 px-3 py-1 text-[12px] font-medium text-brand"
              >
                {p}
              </span>
            ))}
            {savedBrief && (
              <span
                title="This brief was edited on the New-shortlist step"
                className="rounded-full border border-dashed border-border-strong px-2.5 py-1 text-[11px] font-medium text-ink-500"
              >
                brief edited
              </span>
            )}
          </div>
          <div className="ml-auto flex flex-wrap items-center gap-2.5">
            <StatChip value={data.screened} label="screened" tone="ink" className="bg-panel" />
            <StatChip value={totals.recommended} label="recommended" />
            <StatChip value={totals.flagged} label="flagged" tone="risk" className="bg-risk-high-bg" />
          </div>
        </div>
      </div>

      {/* Flagged banner — the hero framing; every number derives from the data */}
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

      {/* Mobile/tablet search — the topbar field only exists ≥lg */}
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
              {/* active pill slides between tabs */}
              {filter === f.key && (
                <motion.span
                  layoutId="filter-pill"
                  className="absolute inset-0 rounded-full bg-brand"
                  transition={{ duration: 0.25, ease: [0.25, 1, 0.5, 1] }}
                />
              )}
              <span className="relative">{f.label}</span>
              <span className={cn("tnum relative ml-1.5", filter === f.key ? "text-white/70" : "text-ink-400")}>
                {counts[f.key]}
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
                : "No creators match the current filter. Try “All screened”, or adjust the brand brief and re-run."}
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
                    rank={i + 1}
                    decision={statuses[kol.id]}
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
              {/* rows fade in/out on filter+search and glide on re-sort */}
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
                      rank={i + 1}
                      decision={statuses[kol.id]}
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
            data.source === "api" ? "bg-verified-bg text-verified-fg" : "bg-panel text-ink-700",
          )}
        >
          <span aria-hidden className={cn("h-1.5 w-1.5 rounded-full", data.source === "api" ? "bg-verified" : "bg-ink-400")} />
          {data.source === "api" ? "served by the pipeline API · /api/shortlist" : "bundled fixtures (API unavailable)"}
        </span>
        Demo cohort is curated public-data fixtures. Every metric is tagged{" "}
        <span className="font-medium text-ink-700">measured / inferred / estimated</span>; production points the data
        adapter at a licensed KOL feed. Fraud-flagged handles are anonymised in the live run.
      </p>

      <AnimatePresence>
        {showExport && (
          <ExportModal kols={data.kols} brief={data.brief} onClose={() => setShowExport(false)} />
        )}
      </AnimatePresence>
    </div>
  )
}
