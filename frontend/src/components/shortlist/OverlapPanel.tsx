import { useState } from "react"
import { Users, ChevronDown } from "lucide-react"
import type { OverlapPair } from "../../lib/types"
import { cn } from "../../lib/cn"

/** Commenter-overlap dedup — pairs of shortlisted creators who share a meaningful
 *  commenter set. Honest by construction: commenters are measured, "audience" is a proxy;
 *  we show the raw shared count, never a demographic claim. */
export function OverlapPanel({ pairs }: { pairs: OverlapPair[] }) {
  const [open, setOpen] = useState(true)
  if (!pairs.length) return null

  return (
    <div className="mb-[var(--d-block-gap)] overflow-hidden rounded-2xl border border-border bg-white shadow-sm">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2.5 px-5 py-3 text-left"
        aria-expanded={open}
      >
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-brand-50 text-brand">
          <Users size={16} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-[13px] font-semibold text-ink">
            Commenter overlap · {pairs.length} pair{pairs.length === 1 ? "" : "s"}
          </div>
          <div className="text-[12px] text-ink-500">
            Creators sharing a slice of the same commenters — booking both double-serves that audience.
          </div>
        </div>
        <ChevronDown size={18} className={cn("shrink-0 text-ink-400 transition-transform", !open && "-rotate-90")} />
      </button>

      {open && (
        <div className="border-t border-border">
          <ul className="divide-y divide-border">
            {pairs.map((p) => (
              <li key={`${p.aId}-${p.bId}`} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-5 py-3">
                <span className="text-[13px] font-semibold text-ink">{p.aHandle}</span>
                <span className="text-ink-300">↔</span>
                <span className="text-[13px] font-semibold text-ink">{p.bHandle}</span>
                <span className="tnum ml-auto rounded-full bg-brand-50 px-2.5 py-1 text-[12px] font-medium text-brand">
                  {p.shared} shared · ~{Math.round(p.jaccard * 100)}% overlap
                </span>
              </li>
            ))}
          </ul>
          <p className="px-5 py-2.5 text-[11px] leading-relaxed text-ink-500">
            <span className="font-medium text-ink-700">Shared commenters are measured</span>; overlapping audience is an
            inferred proxy (the engaged subset), not a demographic match. Low overlap is not proof two creators are
            independent.
          </p>
        </div>
      )}
    </div>
  )
}
