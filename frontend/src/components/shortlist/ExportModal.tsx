import { useEffect, useRef, useState } from "react"
import { X, Link2, Printer, Check } from "lucide-react"
import { motion } from "motion/react"
import type { ClientBrief, Kol } from "../../lib/types"
import { Avatar } from "../ui/Avatar"
import { Button } from "../ui/Button"
import { compact } from "../../lib/format"
import { cn } from "../../lib/cn"

function statusStyle(status: string): string {
  if (status === "fired") return "bg-risk-high-bg text-risk-high-fg"
  if (status === "withheld") return "bg-panel text-ink-500"
  return "bg-verified-bg text-verified-fg"
}

/** The INTERNAL vetting report — the opposite of the client view: every check for every
    creator, including the honestly WITHHELD ones. The honesty story as a deliverable. */
function InternalReport({ kols, brief }: { kols: Kol[]; brief: ClientBrief }) {
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-baseline gap-2">
        <span className="text-[16px] font-bold text-ink">{brief.brand}</span>
        <span className="font-thai text-[13px] text-ink-400">· {brief.brandTh}</span>
        <span className="ml-auto text-[12px] text-ink-500">Internal vetting report · {kols.length} creators</span>
      </div>
      {kols.map((k) => (
        <div key={k.id} className="mb-3.5 break-inside-avoid border-b border-border pb-3 last:border-b-0">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
            <span className="text-[14px] font-bold text-ink">{k.handle}</span>
            <span className="text-[12px] text-ink-500">
              {k.tier} · {compact(k.followers)} followers · ER {k.engagementRate}%
            </span>
            <span
              className={cn(
                "ml-auto rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase",
                k.risk.level === "clear"
                  ? "bg-verified-bg text-verified-fg"
                  : k.risk.level === "high"
                    ? "bg-risk-high-bg text-risk-high-fg"
                    : "bg-risk-med-bg text-risk-med-fg",
              )}
            >
              {k.risk.level === "clear" ? "clear" : `${k.risk.level} risk`}
            </span>
          </div>
          <div className="mt-1.5 space-y-1">
            {(k.checks ?? []).map((c) => (
              <div key={c.name} className="flex items-baseline gap-2 text-[12px]">
                <span
                  className={cn(
                    "w-16 shrink-0 rounded px-1.5 py-px text-center text-[10px] font-semibold uppercase",
                    statusStyle(c.status),
                  )}
                >
                  {c.status}
                </span>
                <span className="min-w-0">
                  <span className="font-medium text-ink-700">{c.label}</span>{" "}
                  <span className="text-ink-500">— {c.detail}</span>
                </span>
              </div>
            ))}
          </div>
          {k.brandSafety.status === "flag" && (
            <div className="mt-1.5 text-[12px] text-risk-med-fg">
              <span className="font-semibold">Brand-safety review:</span> {k.brandSafety.note}
            </div>
          )}
          {k.estRateThb && k.estRateThb.high > 0 && (
            <div className="mt-1.5 text-[12px] text-ink-600">
              <span className="font-semibold">Est. rate:</span> ฿{k.estRateThb.low.toLocaleString()}–฿
              {k.estRateThb.high.toLocaleString()}/post{" "}
              <span className="text-ink-400">(estimate at your default CPM — not a market rate)</span>
            </div>
          )}
        </div>
      ))}
      <p className="mt-2 text-[11px] leading-relaxed text-ink-500">
        Withheld checks show where the peer baseline was too thin to judge (the n≥15 rule) — surfaced, not hidden. That
        limit is the honesty.
      </p>
    </div>
  )
}

/** Client-ready export — a clean, presentable view (fraud internals hidden) with copy-link + print-to-PDF. */
export function ExportModal({
  kols,
  brief,
  onClose,
}: {
  kols: Kol[]
  brief: ClientBrief
  onClose: () => void
}) {
  const [copied, setCopied] = useState<"idle" | "copied" | "failed">("idle")
  const [mode, setMode] = useState<"client" | "internal">("client")
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const trigger = document.activeElement as HTMLElement | null
    const el = ref.current
    el?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose()
        return
      }
      if (e.key === "Tab" && el) {
        const f = el.querySelectorAll<HTMLElement>(
          'button, a[href], input, [tabindex]:not([tabindex="-1"])',
        )
        if (f.length === 0) return
        const first = f[0]
        const last = f[f.length - 1]
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }
    window.addEventListener("keydown", onKey)
    return () => {
      window.removeEventListener("keydown", onKey)
      trigger?.focus?.() // restore focus to the trigger on close
    }
  }, [onClose])

  const recommended = [...kols]
    .filter((k) => k.risk.level === "clear" && k.fitScore >= 70)
    .sort((a, b) => b.fitScore - a.fitScore)

  const copyLink = async () => {
    // a REAL link (this deployment's shortlist); "Copied" only when the write succeeded
    try {
      await navigator.clipboard.writeText(`${window.location.origin}/app`)
      setCopied("copied")
    } catch {
      setCopied("failed")
    }
    window.setTimeout(() => setCopied("idle"), 1800)
  }

  return (
    <div className="fixed inset-0 z-[50] flex items-center justify-center p-4">
      {/* backdrop fades; panel rises + settles (exit faster than enter) */}
      <motion.div
        className="absolute inset-0 bg-ink-900/50 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0, transition: { duration: 0.15 } }}
        transition={{ duration: 0.2 }}
      />
      <motion.div
        ref={ref}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label="Share client shortlist"
        className="relative z-[51] flex max-h-[85svh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-border bg-white shadow-lg outline-none"
        initial={{ opacity: 0, y: 12, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 8, scale: 0.98, transition: { duration: 0.15 } }}
        transition={{ duration: 0.25, ease: [0.25, 1, 0.5, 1] }}
      >
        {/* header + tabs */}
        <div className="no-print border-b border-border px-5 pt-3.5">
          <div className="flex items-start justify-between">
            <div className="min-w-0">
              <div className="text-[15px] font-semibold text-ink">
                {mode === "client" ? "Share client shortlist" : "Internal vetting report"}
              </div>
              <div className="text-[12px] text-ink-500">
                {mode === "client"
                  ? "A clean view for the client — internal fraud signals stay in Kollab."
                  : "The full evidence dossier — every check, including what we couldn't judge."}
              </div>
            </div>
            <button
              onClick={onClose}
              className="grid h-8 w-8 shrink-0 place-items-center rounded-md text-ink-400 transition-colors hover:bg-panel hover:text-ink"
              aria-label="Close"
            >
              <X size={18} />
            </button>
          </div>
          <div className="mt-2.5 flex items-center gap-1">
            {(["client", "internal"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                aria-pressed={mode === m}
                className={cn(
                  "relative -mb-px px-3 py-2 text-[13px] font-medium transition-colors",
                  mode === m ? "text-brand" : "text-ink-500 hover:text-ink",
                )}
              >
                {m === "client" ? "Client shortlist" : "Internal report"}
                {mode === m && <span className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-brand" />}
              </button>
            ))}
          </div>
        </div>

        {/* print area — client-ready OR the internal report */}
        <div className="print-area overflow-y-auto px-5 py-4">
          {mode === "client" ? (
            <>
              <div className="mb-3 flex items-baseline gap-2">
                <span className="text-[18px] font-bold text-ink">{brief.brand}</span>
                <span className="font-thai text-[14px] text-ink-400">· {brief.brandTh}</span>
                <span className="ml-auto text-[12px] font-medium text-ink-500">
                  {recommended.length} recommended creators
                </span>
              </div>
              <div className="divide-y divide-border">
                {recommended.map((k, i) => (
                  <div key={k.id} className="flex items-center gap-3 py-2.5">
                    <span className="tnum w-4 shrink-0 text-[12px] font-medium text-ink-400">{i + 1}</span>
                    <Avatar initials={k.avatar.initials} hue={k.avatar.hue} size={34} />
                    <div className="min-w-0 flex-1">
                      <div className="text-[13px] font-semibold text-ink">{k.handle}</div>
                      <div className="truncate text-[12px] text-ink-500">
                        {k.category} · {k.tier} · {compact(k.followers)} followers
                      </div>
                    </div>
                    <div className="tnum shrink-0 text-[13px] font-bold text-brand">{k.fitScore}</div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <InternalReport kols={kols} brief={brief} />
          )}
        </div>

        {/* actions */}
        <div className="no-print flex items-center justify-between gap-2 border-t border-border px-5 py-3">
          <span className="text-[11px] text-ink-400">Generated by Kollab</span>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              leadingIcon={copied === "copied" ? <Check size={15} /> : <Link2 size={15} />}
              onClick={copyLink}
            >
              {copied === "copied" ? "Copied" : copied === "failed" ? "Copy failed" : "Copy link"}
            </Button>
            <Button size="sm" leadingIcon={<Printer size={15} />} onClick={() => window.print()}>
              Save as PDF
            </Button>
          </div>
        </div>
      </motion.div>
    </div>
  )
}
