import { useMemo, useSyncExternalStore } from "react"
import { Coins, Info, RotateCcw } from "lucide-react"
import type { Kol } from "../../lib/types"
import { CPM_DEFAULT, computeBand, getCpm, setCpmShared, subscribeCpm } from "../../lib/rate"
import { compact } from "../../lib/format"
import { cn } from "../../lib/cn"

/** Economics tab — the fraud-adjusted fair-rate ESTIMATE.
 *  It is the creator's own measured organic reach × an editable CPM YOU set × authenticity.
 *  Never a market rate card: drag the CPM and the band rescales linearly. */
export function RateEstimate({ kol }: { kol: Kol }) {
  const cpm = useSyncExternalStore(subscribeCpm, getCpm)
  const basis = kol.rateBasis

  const band = useMemo(() => (basis ? computeBand(basis, cpm) : null), [basis, cpm])

  if (!basis || !band) {
    return (
      <div className="rounded-lg border border-border bg-white p-4 text-[13px] text-ink-600">
        <div className="mb-1 flex items-center gap-1.5 font-semibold text-ink">
          <Coins size={15} className="text-ink-400" /> Rate estimate withheld
        </div>
        <p className="text-ink-500">
          Too few videos were sampled to price this creator's organic reach. A deeper run (more
          videos) would surface an estimate — we withhold rather than guess.
        </p>
      </div>
    )
  }

  const nonOrganic = band.high <= 0 // authenticity assessed the reach as non-organic
  const update = (v: number) => setCpmShared(v)

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-border bg-white p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-[13px] font-semibold text-ink">
            <Coins size={15} className="text-brand" /> Fair-rate estimate
          </div>
          <span className="rounded bg-panel px-1.5 py-px text-[10px] font-medium uppercase tracking-wide text-ink-500">
            estimated
          </span>
        </div>

        {/* the band */}
        <div className="mt-3">
          {nonOrganic ? (
            <div className="text-[15px] font-bold text-risk-high-fg">
              Not reach-priceable
              <span className="ml-2 text-[12px] font-medium text-ink-500">
                — authenticity {basis.authenticity}%, reach assessed as non-organic
              </span>
            </div>
          ) : (
            <div className="tnum text-[22px] font-bold tracking-tight text-ink">
              ฿{band.low.toLocaleString()}
              <span className="mx-1 text-ink-400">–</span>฿{band.high.toLocaleString()}
              <span className="ml-2 text-[12px] font-medium text-ink-500">per post</span>
            </div>
          )}
        </div>

        {/* the arithmetic — every input visible */}
        <div className="mt-3 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-[12px] text-ink-600">
          <span className="tnum font-semibold text-ink">{compact(basis.medianOrganicViews)}</span>
          <span>organic views/post</span>
          <span className="text-ink-300">×</span>
          <span className="tnum font-semibold text-ink">฿{cpm}</span>
          <span>CPM</span>
          <span className="text-ink-300">×</span>
          <span className="tnum font-semibold text-ink">{basis.authenticity}%</span>
          <span>authenticity</span>
        </div>
      </div>

      {/* editable CPM — the ONE assumption you control */}
      <div className="rounded-lg border border-border bg-surface p-4">
        <div className="flex items-center justify-between">
          <label htmlFor={`cpm-${kol.id}`} className="text-[12px] font-semibold text-ink">
            Your CPM assumption <span className="font-normal text-ink-500">(฿ per 1,000 organic views)</span>
          </label>
          {cpm !== CPM_DEFAULT && (
            <button
              onClick={() => update(CPM_DEFAULT)}
              className="inline-flex items-center gap-1 text-[11px] font-medium text-ink-500 hover:text-brand"
            >
              <RotateCcw size={11} /> Reset
            </button>
          )}
        </div>
        <div className="mt-2.5 flex items-center gap-3">
          <input
            id={`cpm-${kol.id}`}
            type="range"
            min={20}
            max={500}
            step={5}
            value={cpm}
            onChange={(e) => update(Number(e.target.value))}
            className="h-1.5 flex-1 cursor-pointer accent-brand"
            aria-label="CPM in Thai baht per 1000 views"
          />
          <div className="flex items-center gap-1 rounded-md border border-border bg-white px-2 py-1">
            <span className="text-[12px] text-ink-400">฿</span>
            <input
              type="number"
              min={1}
              value={cpm}
              onChange={(e) => update(Number(e.target.value) || 1)}
              className="tnum w-14 bg-transparent text-[13px] font-semibold text-ink focus:outline-none"
              aria-label="CPM exact value"
            />
          </div>
        </div>
        <p className="mt-2.5 flex items-start gap-1.5 text-[11px] leading-relaxed text-ink-500">
          <Info size={12} className={cn("mt-px shrink-0 text-ink-400")} />
          This is <span className="font-medium text-ink-700">your assumption</span> applied to this creator's
          measured organic reach (boosted posts excluded), discounted by authenticity — <span className="font-medium text-ink-700">not a market rate card</span>. Change the CPM and the band rescales. Anchor it to your own closed-deal data.
        </p>
      </div>
    </div>
  )
}
