import { cn } from "../../lib/cn"

type Tone = "brand" | "risk-high" | "risk-med"

const toneClass: Record<Tone, string> = {
  brand: "bg-brand",
  "risk-high": "bg-risk-high",
  "risk-med": "bg-risk-med",
}

/** Fit-score bar (0–100). Tone reflects trust (fraud KOLs go red/amber). Tabular number so columns align. */
export function ScoreBar({
  value,
  max = 100,
  tone = "brand",
  label = "Fit score",
  className,
}: {
  value: number
  max?: number
  tone?: Tone
  label?: string
  className?: string
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100))
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <div
        className="relative h-1.5 w-full overflow-hidden rounded-full bg-border"
        role="meter"
        aria-label={label}
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuetext={`${value} of ${max}`}
      >
        <div
          className={cn(
            "absolute inset-y-0 left-0 rounded-full transition-[width] duration-500 ease-out",
            toneClass[tone],
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="tnum w-7 shrink-0 text-right text-sm font-semibold text-ink">{value}</span>
    </div>
  )
}
