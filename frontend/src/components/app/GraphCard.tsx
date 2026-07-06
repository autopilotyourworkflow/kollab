import { useEffect, useState } from "react"
import { Network, Loader2, Lock } from "lucide-react"
import { getGraph, type GraphStats } from "../../lib/api"
import { apiBase } from "../../lib/credit"
import { cn } from "../../lib/cn"

/** The persistent cross-run commenter graph — the fraud-recall moat, made inspectable.
 *  Aggregate counts only; labels the backend durable (Neon) vs the ephemeral demo graph. */
export function GraphCard() {
  const [stats, setStats] = useState<GraphStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    getGraph()
      .then((s) => alive && setStats(s))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [])

  if (!apiBase()) {
    return (
      <div className="flex items-start gap-2.5 rounded-lg border border-border bg-surface px-3.5 py-3 text-[12px] leading-relaxed text-ink-700">
        <Lock size={15} className="mt-0.5 shrink-0 text-ink-400" />
        <span>
          <span className="font-semibold text-ink">Demo mode.</span> The persistent commenter graph runs on the live
          backend, where every run's shared-commenter edges accumulate so fraud recall improves each campaign.
        </span>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3.5 py-3 text-[12px] text-ink-500">
        <Loader2 size={14} className="animate-spin" /> Reading the graph…
      </div>
    )
  }

  if (!stats) {
    return (
      <div className="rounded-lg border border-border bg-surface px-3.5 py-3 text-[12px] text-ink-500">
        Couldn't reach the graph API.
      </div>
    )
  }

  const Stat = ({ v, l }: { v: number | null; l: string }) => (
    <div className="rounded-lg border border-border bg-white px-3 py-2">
      <div className="tnum text-[17px] font-bold text-ink">{v === null ? "—" : v.toLocaleString()}</div>
      <div className="text-[11px] text-ink-500">{l}</div>
    </div>
  )

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1.5 text-[13px] font-semibold text-ink">
          <Network size={15} className="text-brand" /> Cross-run commenter graph
        </span>
        <span
          className={cn(
            "rounded-full px-2 py-0.5 text-[11px] font-medium",
            stats.durable ? "bg-verified-bg text-verified-fg" : "bg-panel text-ink-600",
          )}
        >
          {stats.durable ? "durable · Neon" : "ephemeral demo graph"}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat v={stats.edges} l="edges" />
        <Stat v={stats.creators} l="creators" />
        <Stat v={stats.commenters} l="commenters" />
        <Stat v={stats.pods} l="pods known" />
      </div>
      {stats.topPod && (
        <p className="text-[12px] text-ink-600">
          Largest pod cluster: <span className="font-semibold text-ink">{stats.topPod.accounts} accounts</span> across{" "}
          <span className="font-semibold text-ink">{stats.topPod.creators} creators</span>.
        </p>
      )}
      <p className="text-[11px] leading-relaxed text-ink-500">{stats.note}</p>
    </div>
  )
}
