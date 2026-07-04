import type { ReactNode } from "react"
import { cn } from "../../lib/cn"

/* Convert Cake's signature elements, extracted from convertcake.com and
   componentized — the shared brand vocabulary for landing, tool, and
   /design-system. See DESIGN.md "Signature elements". */

/** Brand pill: their measured #C8D4FB tint + cobalt text, fully rounded. */
export function TintPill({
  icon,
  className,
  children,
}: {
  icon?: ReactNode
  className?: string
  children: ReactNode
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full bg-brand-100 px-4 py-1.5 text-[14px] font-medium text-brand",
        className,
      )}
    >
      {icon}
      {children}
    </span>
  )
}

/** Outlined stat card: white, 1.5px cobalt border, huge tabular number. */
export function StatCard({
  value,
  unit,
  label,
  className,
}: {
  value: string
  unit?: string
  label: string
  className?: string
}) {
  return (
    <div className={cn("rounded-2xl border-[1.5px] border-brand bg-white px-7 py-6 shadow-sm", className)}>
      <div className="tnum text-[44px] font-bold leading-tight text-ink">
        {value}
        {unit && <span className="align-super text-[22px] font-bold text-brand">{unit}</span>}
      </div>
      <div className="mt-1 text-[14px] font-medium text-ink-500">{label}</div>
    </div>
  )
}

/** Floating stat chip: their #E6ECFD tint, big cobalt number + tiny label. */
export function StatChip({
  value,
  label,
  tone = "brand",
  className,
}: {
  value: string | number
  label: string
  tone?: "brand" | "risk" | "ink"
  className?: string
}) {
  return (
    <div className={cn("inline-flex items-baseline gap-2 rounded-xl bg-brand-50 px-3.5 py-2", className)}>
      <span
        className={cn(
          "tnum text-[20px] font-bold leading-none",
          tone === "brand" && "text-brand",
          tone === "risk" && "text-risk-high-fg",
          tone === "ink" && "text-ink",
        )}
      >
        {value}
      </span>
      <span className="max-w-[110px] text-[11px] font-medium leading-tight text-ink-700">{label}</span>
    </div>
  )
}

/** Their uppercase cobalt section kicker (marketing surfaces). */
export function Kicker({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cn("text-[13px] font-semibold uppercase tracking-[0.02em] text-brand", className)}>
      {children}
    </div>
  )
}
