import { useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { AnimatePresence, motion } from "motion/react"
import { Loader2, Check, X, Ban, Eye, TriangleAlert, ChevronDown, Layers } from "lucide-react"
import { pollRun, cancelRun } from "../../lib/api"
import {
  listRuns,
  updateRun,
  removeRun,
  announceWorkspaceUpdate,
  RUNS_CHANGED,
  type TrackedRun,
} from "../../lib/runsStore"
import { appendKols, markSourceLive } from "../../lib/workspace"
import { cn } from "../../lib/cn"

const STALE_MS = 12 * 60_000

function elapsed(startedAt: number): string {
  const s = Math.max(0, Math.floor((Date.now() - startedAt) / 1000))
  const m = Math.floor(s / 60)
  return `${m}:${String(s % 60).padStart(2, "0")}`
}

export function RunDock() {
  const navigate = useNavigate()
  const [runs, setRuns] = useState<TrackedRun[]>(listRuns)
  const [, setTick] = useState(0)
  const [open, setOpen] = useState(true)
  const polling = useRef(false)

  const active = runs.some((r) => r.status === "running")

  // Re-read when a run is added/updated anywhere (e.g. started from a shortlist).
  useEffect(() => {
    const on = () => setRuns(listRuns())
    window.addEventListener(RUNS_CHANGED, on)
    return () => window.removeEventListener(RUNS_CHANGED, on)
  }, [])

  // 1s ticker for the elapsed clock, only while something is running.
  useEffect(() => {
    if (!active) return
    const t = window.setInterval(() => setTick((x) => x + 1), 1000)
    return () => window.clearInterval(t)
  }, [active])

  // Poll running runs. Reads storage fresh each cycle so it's always current, and
  // keeps going across route changes (the dock is mounted once in the shell).
  useEffect(() => {
    if (!active) return
    const poll = async () => {
      if (polling.current) return
      polling.current = true
      try {
        for (const r of listRuns()) {
          if (r.status !== "running") continue
          if (Date.now() - r.startedAt > STALE_MS) {
            updateRun(r.id, { status: "error", error: "timed out" })
            continue
          }
          const res = await pollRun(r.id)
          if (!res) continue
          if (res.status === "done") {
            const kols = res.kols ?? []
            const added = appendKols(r.shortlistId, kols)
            if (added && kols.length) markSourceLive(r.shortlistId)
            updateRun(r.id, { status: "done", added })
            announceWorkspaceUpdate(r.shortlistId)
          } else if (res.status === "error") {
            updateRun(r.id, { status: "error", error: res.error ?? "run failed" })
          } else if (res.status === "cancelled") {
            updateRun(r.id, { status: "cancelled" })
          }
        }
      } finally {
        polling.current = false
        setRuns(listRuns())
      }
    }
    poll()
    const t = window.setInterval(poll, 4000)
    return () => window.clearInterval(t)
  }, [active])

  const stop = (id: string) => {
    updateRun(id, { status: "cancelled" })
    void cancelRun(id)
  }

  if (runs.length === 0) return null
  const runningCount = runs.filter((r) => r.status === "running").length

  return (
    <div className="fixed bottom-4 right-4 z-[60] w-80 max-w-[calc(100vw-2rem)]">
      <div className="overflow-hidden rounded-2xl border border-border bg-white shadow-lg">
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex w-full items-center gap-2 border-b border-border bg-surface px-4 py-2.5 text-left"
        >
          <Layers size={14} className="text-brand" />
          <span className="text-[13px] font-semibold text-ink">Sourcing runs</span>
          {runningCount > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-brand-50 px-2 py-0.5 text-[11px] font-medium text-brand">
              <Loader2 size={10} className="animate-spin" /> {runningCount} running
            </span>
          )}
          <ChevronDown size={16} className={cn("ml-auto text-ink-400 transition-transform", !open && "-rotate-90")} />
        </button>

        <AnimatePresence initial={false}>
          {open && (
            <motion.div
              initial={{ height: 0 }}
              animate={{ height: "auto" }}
              exit={{ height: 0 }}
              transition={{ duration: 0.2, ease: [0.25, 1, 0.5, 1] }}
              className="overflow-hidden"
            >
              <div className="max-h-[50vh] overflow-y-auto divide-y divide-border">
                {runs.map((r) => (
                  <div key={r.id} className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className="min-w-0 flex-1 truncate text-[13px] font-semibold text-ink">{r.brand || "Shortlist"}</span>
                      <span className="shrink-0 rounded-full bg-panel px-1.5 py-px text-[10px] font-medium uppercase tracking-wide text-ink-500">
                        {r.preset}
                      </span>
                    </div>

                    {r.status === "running" && (
                      <>
                        <div className="mt-2 flex items-center justify-between text-[12px]">
                          <span className="flex items-center gap-1.5 text-brand">
                            <Loader2 size={12} className="animate-spin" /> Sourcing &amp; vetting…
                          </span>
                          <span className="tnum text-ink-500">{elapsed(r.startedAt)}</span>
                        </div>
                        {/* indeterminate progress line */}
                        <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-panel">
                          <motion.div
                            className="h-full w-1/3 rounded-full bg-brand"
                            animate={{ x: ["-100%", "300%"] }}
                            transition={{ duration: 1.4, ease: "easeInOut", repeat: Infinity }}
                          />
                        </div>
                        <p className="mt-1.5 text-[11px] text-ink-500">
                          Runs in the background — you can leave this page, refresh, or close the tab.
                        </p>
                        <div className="mt-2 flex items-center gap-2">
                          <button
                            onClick={() => navigate(`/app/s/${r.shortlistId}`)}
                            className="inline-flex items-center gap-1 text-[12px] font-medium text-brand hover:underline"
                          >
                            <Eye size={13} /> View shortlist
                          </button>
                          <button
                            onClick={() => stop(r.id)}
                            className="ml-auto inline-flex items-center gap-1 text-[12px] font-medium text-risk-high-fg hover:underline"
                          >
                            <Ban size={13} /> Stop
                          </button>
                        </div>
                      </>
                    )}

                    {r.status === "done" && (
                      <div className="mt-1.5 flex items-center gap-2">
                        <span className="flex items-center gap-1.5 text-[12px] font-medium text-verified-fg">
                          <Check size={13} />
                          {r.added ? `+${r.added} new creator${r.added === 1 ? "" : "s"} merged` : "No new creators found"}
                        </span>
                        <button
                          onClick={() => {
                            navigate(`/app/s/${r.shortlistId}`)
                            removeRun(r.id)
                          }}
                          className="ml-auto inline-flex items-center gap-1 text-[12px] font-medium text-brand hover:underline"
                        >
                          <Eye size={13} /> View
                        </button>
                        <button onClick={() => removeRun(r.id)} aria-label="Dismiss" className="text-ink-400 hover:text-ink">
                          <X size={14} />
                        </button>
                      </div>
                    )}

                    {r.status === "cancelled" && (
                      <div className="mt-1.5 flex items-center gap-2 text-[12px] text-ink-500">
                        <Ban size={13} /> Stopped
                        <button onClick={() => removeRun(r.id)} aria-label="Dismiss" className="ml-auto text-ink-400 hover:text-ink">
                          <X size={14} />
                        </button>
                      </div>
                    )}

                    {r.status === "error" && (
                      <div className="mt-1.5 flex items-start gap-1.5 text-[12px] text-risk-high-fg">
                        <TriangleAlert size={13} className="mt-0.5 shrink-0" />
                        <span className="min-w-0 flex-1 break-words">{r.error || "Run failed"}</span>
                        <button onClick={() => removeRun(r.id)} aria-label="Dismiss" className="shrink-0 text-ink-400 hover:text-ink">
                          <X size={14} />
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
