import { cn } from "../../lib/cn"

export type Provenance = "measured" | "inferred" | "estimated"

const config: Record<Provenance, { cls: string; label: string }> = {
  measured: { cls: "bg-prov-measured-bg text-prov-measured-fg", label: "Measured" },
  inferred: { cls: "bg-prov-inferred-bg text-prov-inferred-fg", label: "Inferred" },
  estimated: { cls: "bg-prov-estimated-bg text-prov-estimated-fg", label: "Estimated" },
}

/** Data-honesty tag — every derived value carries one so nothing reads as fact when it isn't. */
export function ProvenanceChip({
  kind,
  className,
}: {
  kind: Provenance
  className?: string
}) {
  const c = config[kind]
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium leading-none",
        c.cls,
        className,
      )}
    >
      {c.label}
    </span>
  )
}
