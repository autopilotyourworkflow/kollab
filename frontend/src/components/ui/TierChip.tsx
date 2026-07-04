import { cn } from "../../lib/cn"

/** Descriptive tier label (nano / micro / mid / macro / mega). Display only — not a pricing benchmark. */
export function TierChip({ tier, className }: { tier: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full bg-panel px-2.5 py-0.5 text-[11px] font-medium text-ink-700",
        className,
      )}
    >
      {tier}
    </span>
  )
}
