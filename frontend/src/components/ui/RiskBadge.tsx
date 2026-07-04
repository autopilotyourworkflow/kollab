import { ShieldCheck, ShieldAlert, TriangleAlert } from "lucide-react"
import { cn } from "../../lib/cn"

export type RiskLevel = "high" | "medium" | "clear"

interface RiskBadgeProps {
  level: RiskLevel
  /** The specific triggered signal, e.g. "Comment pod: 41 shared accounts". Falls back to a generic label. */
  signal?: string
  className?: string
}

const config = {
  high: {
    cls: "bg-risk-high-bg text-risk-high-fg border-risk-high-border",
    Icon: ShieldAlert,
    label: "Fraud risk",
  },
  medium: {
    cls: "bg-risk-med-bg text-risk-med-fg border-risk-med-border",
    Icon: TriangleAlert,
    label: "Caution",
  },
  clear: {
    cls: "bg-verified-bg text-verified-fg border-verified-border",
    Icon: ShieldCheck,
    label: "Authentic",
  },
} as const

/** Trust badge — never signals by color alone: always icon + label text. */
export function RiskBadge({ level, signal, className }: RiskBadgeProps) {
  const c = config[level]
  const Icon = c.Icon
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-[3px] text-xs font-medium leading-none",
        c.cls,
        className,
      )}
    >
      <Icon size={13} strokeWidth={2.25} aria-hidden />
      <span>{signal ?? c.label}</span>
    </span>
  )
}
