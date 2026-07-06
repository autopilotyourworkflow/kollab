import { useState, useRef, useEffect } from "react"
import { AnimatePresence, motion } from "motion/react"
import {
  ChevronRight,
  CheckCircle2,
  ShieldAlert,
  ShieldQuestion,
  TriangleAlert,
  Ban,
  Check,
  ExternalLink,
  RotateCcw,
  FileText,
  Coins,
  Rocket,
  Lock,
  Network,
} from "lucide-react"
import type { ClientBrief, Kol, HitlStatus } from "../../lib/types"
import { cn } from "../../lib/cn"
import { compact } from "../../lib/format"
import { Avatar } from "../ui/Avatar"
import { Button } from "../ui/Button"
import { RiskBadge } from "../ui/RiskBadge"
import { ProvenanceChip } from "../ui/ProvenanceChip"
import { ScoreBar } from "../ui/ScoreBar"
import { TierChip } from "../ui/TierChip"
import { RateEstimate } from "./RateEstimate"
import { AfterBooking } from "./AfterBooking"

/** Shared column template so header + rows stay aligned. */
export const COLS =
  "grid grid-cols-[minmax(240px,1.6fr)_84px_92px_96px_60px_210px_150px_34px] items-center gap-3"

type Decision = { status: HitlStatus; reason?: string }

type PanelTab = "evidence" | "economics" | "after"
const TABS: { key: PanelTab; label: string; Icon: typeof FileText }[] = [
  { key: "evidence", label: "Evidence", Icon: FileText },
  { key: "economics", label: "Economics", Icon: Coins },
  { key: "after", label: "After booking", Icon: Rocket },
]

const reasonChips: Record<"approved" | "rejected", string[]> = {
  approved: ["Verified manually", "Client requested", "False-positive signal"],
  rejected: ["Confirmed fake", "Off-brand fit", "Over budget"],
}

function Metric({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div>
      <div className="text-[10px] font-medium uppercase tracking-wide text-ink-500">{label}</div>
      <div className="tnum mt-0.5 text-sm font-semibold text-ink">{value}</div>
      {sub && <div className="text-[11px] text-ink-500">{sub}</div>}
    </div>
  )
}

function FactorRow({
  label,
  score,
  weight,
  rationale,
  provenance,
}: {
  label: string
  score: number
  weight: number
  rationale: string
  provenance: "measured" | "inferred" | "estimated"
}) {
  const advisory = weight === 0
  const barColor = advisory
    ? "bg-ink-400"
    : score < 40
      ? "bg-risk-high"
      : score < 70
        ? "bg-risk-med"
        : "bg-brand"
  return (
    <div className="py-2.5">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-[13px] font-medium text-ink">{label}</span>
          <span
            className={cn(
              "rounded px-1.5 py-px text-[10px] font-medium",
              advisory ? "bg-panel text-ink-500" : "bg-brand-50 text-brand",
            )}
          >
            {advisory ? "advisory · not scored" : `${Math.round(weight * 100)}% weight`}
          </span>
        </div>
        <span className="tnum text-[13px] font-semibold text-ink">{score}</span>
      </div>
      <div className="mt-1.5">
        <div className="relative h-1 w-full overflow-hidden rounded-full bg-border">
          <div
            className={cn("absolute inset-y-0 left-0 rounded-full", barColor)}
            style={{ width: `${score}%` }}
          />
        </div>
      </div>
      <p className="mt-1.5 flex items-start gap-1.5 text-[12px] leading-relaxed text-ink-500">
        <span className="flex-1">{rationale}</span>
        <ProvenanceChip kind={provenance} className="mt-px shrink-0" />
      </p>
    </div>
  )
}

function EvidencePanel({
  kol,
  brief,
  decision,
  onDecide,
}: {
  kol: Kol
  brief: ClientBrief
  decision: Decision
  onDecide: (status: HitlStatus, reason?: string) => void
}) {
  const [tab, setTab] = useState<PanelTab>("evidence")
  const approved = decision.status === "approved"
  const [lang, setLang] = useState<"en" | "th">("en")
  const [pending, setPending] = useState<"approved" | "rejected" | null>(null)
  const [reason, setReason] = useState("")
  const [note, setNote] = useState("")
  const flagged = kol.risk.level !== "clear" || kol.conflict.status === "flag"
  const hasFlags = kol.risk.signals.length > 0 || kol.conflict.status === "flag" || kol.brandSafety.status === "flag"

  return (
    <div className="border-t border-border bg-surface/60 px-5 py-5">
      {/* metrics strip */}
      <div className="mb-5 flex flex-wrap gap-x-10 gap-y-3 rounded-lg border border-border bg-white px-4 py-3">
        <Metric label="Followers" value={compact(kol.followers)} />
        <Metric label="Median views" value={compact(kol.medianViews)} />
        <Metric label="Engagement" value={`${kol.engagementRate}%`} />
        <Metric label="Last posted" value={`${kol.lastPostedDaysAgo}d ago`} />
        <Metric label="Region" value={kol.region} />
        <div className="ml-auto flex items-center gap-1.5 self-center">
          <ProvenanceChip kind="measured" />
          <span className="text-[11px] text-ink-400">from public data</span>
        </div>
      </div>

      {/* sub-tabs: Evidence (default) · Economics · After booking (unlocks on approve) */}
      <div className="mb-4 flex items-center gap-1 border-b border-border">
        {TABS.map((t) => {
          const locked = t.key === "after" && !approved
          const active = tab === t.key
          return (
            <button
              key={t.key}
              disabled={locked}
              onClick={() => setTab(t.key)}
              className={cn(
                "relative -mb-px flex items-center gap-1.5 px-3 py-2 text-[13px] font-medium transition-colors",
                locked ? "cursor-not-allowed text-ink-300" : active ? "text-brand" : "text-ink-500 hover:text-ink",
              )}
              title={locked ? "Approve this creator to unlock the post-booking toolkit" : undefined}
            >
              {locked ? <Lock size={13} /> : <t.Icon size={13} />} {t.label}
              {active && <span className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-brand" />}
            </button>
          )
        })}
      </div>

      {tab === "economics" && (
        <div className="max-w-xl">
          <RateEstimate kol={kol} />
        </div>
      )}
      {tab === "after" &&
        (approved ? (
          <div className="max-w-xl">
            <AfterBooking kol={kol} brief={brief} />
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-border-strong bg-surface/50 px-4 py-8 text-center text-[13px] text-ink-500">
            <Lock size={18} className="mx-auto mb-2 text-ink-400" />
            Approve this creator to unlock the post-booking toolkit — delivered-post re-audit, the delivery ledger,
            and a grounded outreach draft.
          </div>
        ))}

      {tab === "evidence" && (
      <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        {/* Signals */}
        <div>
          <h4 className="mb-1 text-[13px] font-semibold text-ink">How the fit score breaks down</h4>
          <div className="divide-y divide-border">
            {kol.factors.map((f) => (
              <FactorRow
                key={f.key}
                label={f.label}
                score={f.score}
                weight={f.weight}
                rationale={f.rationale}
                provenance={f.provenance}
              />
            ))}
          </div>
        </div>

        {/* Why + flags + HITL */}
        <div className="space-y-4">
          <div className="rounded-lg border border-border bg-white p-4">
            <div className="mb-2 flex items-center justify-between">
              <h4 className="text-[13px] font-semibold text-ink">Why this match</h4>
              <div className="flex overflow-hidden rounded-md border border-border text-[11px]">
                {(["en", "th"] as const).map((l) => (
                  <button
                    key={l}
                    onClick={() => setLang(l)}
                    aria-pressed={lang === l}
                    className={cn(
                      "px-2.5 py-1 font-medium uppercase transition-colors",
                      lang === l ? "bg-brand text-white" : "bg-white text-ink-500 hover:bg-surface",
                    )}
                  >
                    {l}
                  </button>
                ))}
              </div>
            </div>
            <p className={cn("text-[13px] leading-relaxed text-ink-700", lang === "th" && "font-thai")}>
              {lang === "en" ? kol.whyEn : kol.whyTh}
            </p>
          </div>

          {hasFlags && (
            <div className="space-y-2">
              {kol.risk.signals.map((s) => (
                <div
                  key={s.label}
                  className={cn(
                    "rounded-lg border p-3",
                    s.level === "high"
                      ? "border-risk-high-border bg-risk-high-bg"
                      : "border-risk-med-border bg-risk-med-bg",
                  )}
                >
                  <div className="flex items-center gap-1.5">
                    {s.level === "high" ? (
                      <ShieldAlert size={14} className="text-risk-high-fg" />
                    ) : (
                      <TriangleAlert size={14} className="text-risk-med-fg" />
                    )}
                    <span
                      className={cn(
                        "text-[13px] font-semibold",
                        s.level === "high" ? "text-risk-high-fg" : "text-risk-med-fg",
                      )}
                    >
                      {s.label}
                    </span>
                  </div>
                  <p className="mt-1 text-[12px] leading-relaxed text-ink-700">{s.detail}</p>
                  <p className="mt-1 text-[11px] text-ink-500">Measured against {s.measuredAgainst}.</p>
                  {s.label === "Comment pod" && (
                    <p className="mt-1.5 flex items-center gap-1 text-[11px] font-medium text-brand">
                      <Network size={11} /> Tracked in Kollab's cross-run commenter graph — recall compounds every
                      campaign.
                    </p>
                  )}
                </div>
              ))}
              {kol.brandSafety.status === "flag" && (
                <div className="rounded-lg border border-risk-med-border bg-risk-med-bg p-3">
                  <div className="flex items-center gap-1.5">
                    <ShieldQuestion size={14} className="text-risk-med-fg" />
                    <span className="text-[13px] font-semibold text-risk-med-fg">Brand-safety review</span>
                  </div>
                  <p className="mt-1 text-[12px] leading-relaxed text-ink-700">{kol.brandSafety.note}</p>
                  <p className="mt-1 text-[11px] text-ink-500">
                    A separate axis from fraud risk — routed to a human, never auto-excluded.
                  </p>
                </div>
              )}
              {kol.conflict.status === "flag" && (
                <div className="rounded-lg border border-risk-med-border bg-risk-med-bg p-3">
                  <div className="flex items-center gap-1.5">
                    <TriangleAlert size={14} className="text-risk-med-fg" />
                    <span className="text-[13px] font-semibold text-risk-med-fg">Commercial conflict</span>
                  </div>
                  <p className="mt-1 text-[12px] leading-relaxed text-ink-700">{kol.conflict.note}</p>
                </div>
              )}
            </div>
          )}

          {/* HITL */}
          <div className="rounded-lg border border-border bg-white p-3">
            {decision.status !== "pending" ? (
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <div
                    className={cn(
                      "flex items-center gap-1.5 text-[13px] font-semibold",
                      decision.status === "approved" ? "text-verified-fg" : "text-risk-high-fg",
                    )}
                  >
                    {decision.status === "approved" ? <CheckCircle2 size={15} /> : <Ban size={15} />}
                    {decision.status === "approved" ? "Approved" : "Rejected"}
                    {flagged && (
                      <span className="rounded bg-panel px-1.5 py-px text-[10px] font-medium uppercase tracking-wide text-ink-500">
                        override
                      </span>
                    )}
                  </div>
                  <div className="mt-1 truncate text-[12px] text-ink-500">
                    {decision.reason ? `${decision.reason} · ` : ""}just now · Beam
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  leadingIcon={<RotateCcw size={14} />}
                  onClick={() => onDecide("pending")}
                >
                  Undo
                </Button>
              </div>
            ) : pending ? (
              <div>
                <div className="mb-2 text-[12px] font-medium text-ink-700">
                  {flagged
                    ? `Why are you ${pending === "approved" ? "approving a flagged" : "rejecting this"} KOL?`
                    : "Add a note (optional)"}
                </div>
                <div className="mb-2 flex flex-wrap gap-1.5">
                  {reasonChips[pending].map((r) => (
                    <button
                      key={r}
                      onClick={() => setReason(r)}
                      aria-pressed={reason === r}
                      className={cn(
                        "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[12px] font-medium transition-colors",
                        reason === r
                          ? "border-brand bg-brand-50 text-brand"
                          : "border-border bg-white text-ink-700 hover:bg-surface",
                      )}
                    >
                      {reason === r && <Check size={12} aria-hidden />}
                      {r}
                    </button>
                  ))}
                </div>
                <input
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="Optional note for the record…"
                  className="mb-2 h-9 w-full rounded-md border border-border bg-surface px-2.5 text-[12px] text-ink placeholder:text-ink-400 focus:border-brand-300 focus:bg-white"
                />
                <div className="flex items-center gap-2">
                  <Button
                    variant={pending === "approved" ? "primary" : "danger"}
                    size="sm"
                    disabled={flagged && !reason}
                    onClick={() => {
                      onDecide(pending, [reason, note].filter(Boolean).join(" — ") || undefined)
                      setPending(null)
                      setReason("")
                      setNote("")
                    }}
                    className="flex-1"
                  >
                    Confirm {pending === "approved" ? "approve" : "reject"}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setPending(null)
                      setReason("")
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <>
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-[12px] font-medium text-ink-700">Your call</span>
                  {flagged && (
                    <span className="text-[11px] font-medium text-risk-high-fg">overriding a flag needs a reason</span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    leadingIcon={<Check size={15} />}
                    onClick={() => (flagged ? setPending("approved") : onDecide("approved"))}
                    className="flex-1"
                  >
                    Approve
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    leadingIcon={<Ban size={15} />}
                    onClick={() => (flagged ? setPending("rejected") : onDecide("rejected"))}
                    className="flex-1"
                  >
                    Reject
                  </Button>
                  {/* fixture profiles have no live TikTok account — say so instead of 404ing */}
                  <span
                    className="grid h-8 w-8 cursor-help place-items-center rounded-md border border-dashed border-border-strong text-ink-400"
                    title="Fixture profile — no live TikTok account in the demo. The live run links real profiles."
                    aria-label="Fixture profile — no live TikTok account in the demo"
                  >
                    <ExternalLink size={15} />
                  </span>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
      )}
    </div>
  )
}

export function KolRow({
  kol,
  brief,
  rank,
  decision,
  onDecide,
  variant = "row",
}: {
  kol: Kol
  brief: ClientBrief
  rank: number
  decision: Decision
  onDecide: (status: HitlStatus, reason?: string) => void
  variant?: "row" | "card"
}) {
  const [open, setOpen] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (open) panelRef.current?.focus()
  }, [open])
  const rejected = decision.status === "rejected"
  const topSignal = kol.risk.signals[0]

  return (
    <div className={cn(variant === "row" && "border-b border-border last:border-b-0", rejected && "opacity-60")}>
      <div
        role="button"
        tabIndex={0}
        aria-expanded={open}
        aria-controls={`evidence-${kol.id}`}
        onClick={() => setOpen((o) => !o)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault()
            setOpen((o) => !o)
          }
        }}
        className={cn(
          "density-anim cursor-pointer transition-colors duration-300 hover:bg-brand-50/40",
          open && "bg-brand-50/50",
          // row height follows the Comfortable/Spacious density toggle
          variant === "row" ? cn(COLS, "px-5 py-[var(--d-row-py)]") : "px-4 py-[var(--d-row-py)]",
        )}
      >
        {variant === "row" ? (
          <>
        {/* KOL */}
        <div className="flex min-w-0 items-center gap-3">
          <span className="tnum w-4 shrink-0 text-right text-[12px] font-medium text-ink-500">{rank}</span>
          <Avatar initials={kol.avatar.initials} hue={kol.avatar.hue} size={38} />
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="truncate text-[13px] font-semibold text-ink">{kol.handle}</span>
              {decision.status === "approved" && (
                <>
                  <CheckCircle2 size={14} className="shrink-0 text-verified" aria-hidden />
                  <span className="sr-only">Approved</span>
                </>
              )}
              {rejected && (
                <span className="shrink-0 rounded-full bg-panel px-1.5 py-px text-[10px] font-medium uppercase tracking-wide text-ink-700">
                  Rejected
                </span>
              )}
            </div>
            <div className="truncate text-[12px] text-ink-500">{kol.name}</div>
          </div>
        </div>

        {/* Tier */}
        <div className="min-w-0">
          <TierChip tier={kol.tier} />
          <div className="mt-1 truncate text-[11px] text-ink-500">{kol.category}</div>
        </div>

        {/* Metrics — type scales with the density toggle */}
        <div className="tnum text-right text-[length:var(--d-cell-text)] font-medium text-ink">{compact(kol.followers)}</div>
        <div className="tnum text-right text-[length:var(--d-cell-text)] font-medium text-ink">{compact(kol.medianViews)}</div>
        <div className="tnum text-right text-[length:var(--d-cell-text)] font-medium text-ink">{kol.engagementRate}%</div>

        {/* Trust */}
        <div className="min-w-0">
          {kol.risk.level === "clear" ? (
            <RiskBadge level="clear" />
          ) : (
            <RiskBadge level={kol.risk.level} signal={topSignal?.label} />
          )}
        </div>

        {/* Fit */}
        <ScoreBar
          value={kol.fitScore}
          tone={kol.risk.level === "high" ? "risk-high" : kol.risk.level === "medium" ? "risk-med" : "brand"}
          label={`Fit score ${kol.fitScore} of 100 for ${kol.handle}`}
        />

        {/* Chevron */}
        <ChevronRight
          size={18}
          className={cn("justify-self-end text-ink-400 transition-transform duration-200", open && "rotate-90")}
        />
          </>
        ) : (
          <div className="flex items-center gap-3">
            <span className="tnum w-4 shrink-0 text-right text-[12px] font-medium text-ink-500">{rank}</span>
            <Avatar initials={kol.avatar.initials} hue={kol.avatar.hue} size={40} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5">
                <span className="truncate text-[13px] font-semibold text-ink">{kol.handle}</span>
                {decision.status === "approved" && (
                  <>
                    <CheckCircle2 size={14} className="shrink-0 text-verified" aria-hidden />
                    <span className="sr-only">Approved</span>
                  </>
                )}
                {rejected && (
                  <span className="shrink-0 rounded-full bg-panel px-1.5 py-px text-[10px] font-medium uppercase tracking-wide text-ink-700">
                    Rejected
                  </span>
                )}
              </div>
              <div className="truncate text-[12px] text-ink-500">
                {kol.name} · {kol.category}
              </div>
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                <TierChip tier={kol.tier} />
                {kol.risk.level === "clear" ? (
                  <RiskBadge level="clear" />
                ) : (
                  <RiskBadge level={kol.risk.level} signal={topSignal?.label} />
                )}
              </div>
              <div className="mt-2 max-w-[240px]">
                <ScoreBar
                  value={kol.fitScore}
                  tone={kol.risk.level === "high" ? "risk-high" : kol.risk.level === "medium" ? "risk-med" : "brand"}
                  label={`Fit score ${kol.fitScore} of 100 for ${kol.handle}`}
                />
              </div>
            </div>
            <ChevronRight
              size={18}
              className={cn(
                "shrink-0 self-start text-ink-400 transition-transform duration-200",
                open && "rotate-90",
              )}
            />
          </div>
        )}
      </div>

      {/* Expandable evidence — symmetric open/close: height animates both ways
          with the content visible during collapse (bounded to this panel). */}
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="evidence"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0, transition: { duration: 0.2, ease: [0.25, 1, 0.5, 1] } }}
            transition={{ duration: 0.25, ease: [0.25, 1, 0.5, 1] }}
            className="overflow-hidden"
          >
            <div
              ref={panelRef}
              id={`evidence-${kol.id}`}
              tabIndex={-1}
              aria-label={`Evidence for ${kol.handle}`}
              className="animate-evidence-in outline-none"
            >
              <EvidencePanel kol={kol} brief={brief} decision={decision} onDecide={onDecide} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
