import { useEffect, useMemo, useState } from "react"
import {
  ShieldCheck,
  ShieldAlert,
  Loader2,
  Check,
  Copy,
  TrendingDown,
  TrendingUp,
  Send,
  AlertTriangle,
  RefreshCw,
  ClipboardCheck,
} from "lucide-react"
import type { ClientBrief, DeliveryAudit, Kol, OutreachDraft } from "../../lib/types"
import { generateOutreach, reauditPost } from "../../lib/api"
import { addDelivery, loadDeliveries, type LedgerState } from "../../lib/ledger"
import { apiBase } from "../../lib/credit"
import { compact } from "../../lib/format"
import { Button } from "../ui/Button"
import { cn } from "../../lib/cn"

function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-white p-4">
      <div className="mb-2.5 flex items-center gap-1.5 text-[13px] font-semibold text-ink">
        {icon}
        {title}
      </div>
      {children}
    </div>
  )
}

// ── Re-audit ─────────────────────────────────────────────────────────────────
function ReAudit({ kol }: { kol: Kol }) {
  const [loading, setLoading] = useState(false)
  const [audit, setAudit] = useState<DeliveryAudit | null>(null)
  const [tried, setTried] = useState(false)
  const preAuth = useMemo(() => kol.factors.find((f) => f.key === "authenticity")?.score ?? null, [kol])

  const run = async () => {
    setLoading(true)
    setTried(true)
    const res = await reauditPost(kol.handle, preAuth)
    setAudit(res)
    setLoading(false)
  }

  const tone =
    audit?.verdict === "degraded"
      ? { cls: "border-risk-high-border bg-risk-high-bg text-risk-high-fg", Icon: ShieldAlert }
      : { cls: "border-verified-border bg-verified-bg text-verified-fg", Icon: ShieldCheck }

  return (
    <Section title="Delivered-post re-audit" icon={<ShieldCheck size={15} className="text-brand" />}>
      <p className="mb-2.5 text-[12px] leading-relaxed text-ink-500">
        Re-run the same structural detectors on the creator's actual paid post — catches a creator who vetted clean but
        bought engagement for the sponsored content.
      </p>
      {!audit && (
        <Button size="sm" variant="secondary" onClick={run} disabled={loading}
          leadingIcon={loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}>
          {loading ? "Re-auditing…" : "Re-audit delivered post"}
        </Button>
      )}
      {tried && !loading && !audit && (
        <p className="text-[12px] text-ink-500">
          Live re-audit runs on the backend. {apiBase() ? "No delivered-post data for this creator yet." : "Connect the API to try it."}
        </p>
      )}
      {audit && (
        <div className={cn("rounded-lg border p-3", tone.cls)}>
          <div className="flex items-center gap-1.5 text-[13px] font-semibold">
            <tone.Icon size={15} />
            {audit.verdict === "degraded" ? "Degraded on the delivered post" : audit.verdict === "consistent" ? "Consistent with pre-booking" : audit.verdict}
          </div>
          <div className="mt-1.5 flex items-center gap-2 text-[12px] text-ink-700">
            <span>Authenticity</span>
            <span className="tnum font-semibold">{audit.preAuthenticity ?? "—"}</span>
            <span className="text-ink-400">→</span>
            <span className="tnum font-semibold">{audit.postAuthenticity}</span>
          </div>
          {audit.newSignals.length > 0 && (
            <ul className="mt-2 space-y-1">
              {audit.newSignals.map((s) => (
                <li key={s.label} className="text-[12px] text-ink-700">
                  <span className="font-semibold">{s.label}:</span> {s.detail}
                </li>
              ))}
            </ul>
          )}
          <p className="mt-2 text-[11px] leading-relaxed text-ink-600">{audit.note}</p>
        </div>
      )}
    </Section>
  )
}

// ── Delivery ledger ──────────────────────────────────────────────────────────
function Ledger({ kol, brief }: { kol: Kol; brief: ClientBrief }) {
  const [state, setState] = useState<LedgerState | null>(null)
  const [projected, setProjected] = useState<number>(kol.medianViews)
  const [actual, setActual] = useState<string>("")
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let alive = true
    loadDeliveries(kol.handle).then((s) => alive && setState(s))
    return () => {
      alive = false
    }
  }, [kol.handle])

  const log = async () => {
    const act = Number(actual)
    if (!Number.isFinite(act) || act < 0) return
    setSaving(true)
    const s = await addDelivery({ brand: brief.brand, handle: kol.handle, projectedViews: projected, actualViews: act })
    setState(s)
    setActual("")
    setSaving(false)
  }

  const rel = state?.reliability
  const adj = rel?.adjustment ?? 0

  return (
    <Section title="Delivery ledger" icon={<ClipboardCheck size={15} className="text-brand" />}>
      {rel && rel.n > 0 ? (
        <div className="mb-3 rounded-lg border border-border bg-surface p-3">
          <div className="flex items-center gap-2 text-[13px]">
            {adj >= 0 ? <TrendingUp size={15} className="text-verified-fg" /> : <TrendingDown size={15} className="text-risk-med-fg" />}
            <span className="font-semibold text-ink">
              Delivered {rel.meanRatio?.toFixed(2)}× projection
            </span>
            <span className={cn("tnum rounded px-1.5 py-px text-[11px] font-semibold", adj >= 0 ? "bg-verified-bg text-verified-fg" : "bg-risk-med-bg text-risk-med-fg")}>
              fit {adj >= 0 ? "+" : ""}{adj}
            </span>
          </div>
          <p className="mt-1 text-[11px] text-ink-500">{rel.note}</p>
        </div>
      ) : (
        <div className="mb-3 rounded-lg border border-dashed border-border-strong bg-surface/50 p-3 text-[12px] text-ink-500">
          No delivery outcomes logged yet — nothing is estimated until you log one. Log a delivery to start closing the loop.
        </div>
      )}
      <div className="flex flex-wrap items-end gap-2.5">
        <label className="text-[11px] font-medium text-ink-600">
          Projected views
          <input type="number" value={projected} onChange={(e) => setProjected(Math.max(1, Number(e.target.value) || 1))}
            className="tnum mt-1 block w-28 rounded-md border border-border bg-white px-2 py-1 text-[13px] text-ink focus:border-brand-300" />
        </label>
        <label className="text-[11px] font-medium text-ink-600">
          Actual views delivered
          <input type="number" value={actual} onChange={(e) => setActual(e.target.value)} placeholder={compact(kol.medianViews)}
            className="tnum mt-1 block w-28 rounded-md border border-border bg-white px-2 py-1 text-[13px] text-ink placeholder:text-ink-400 focus:border-brand-300" />
        </label>
        <Button size="sm" variant="secondary" onClick={log} disabled={saving || actual === ""}
          leadingIcon={saving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}>
          Log delivery
        </Button>
      </div>
    </Section>
  )
}

// ── Outreach ─────────────────────────────────────────────────────────────────
function Outreach({ kol, brief }: { kol: Kol; brief: ClientBrief }) {
  const [loading, setLoading] = useState(false)
  const [draft, setDraft] = useState<OutreachDraft | null>(null)
  const [lang, setLang] = useState<"en" | "th">("en")
  const [copied, setCopied] = useState(false)
  const [tried, setTried] = useState(false)

  const run = async () => {
    setLoading(true)
    setTried(true)
    setDraft(await generateOutreach(kol, brief))
    setLoading(false)
  }

  const copy = async () => {
    if (!draft) return
    try {
      await navigator.clipboard.writeText(lang === "en" ? draft.en : draft.th)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      /* ignore */
    }
  }

  return (
    <Section title="Outreach draft" icon={<Send size={15} className="text-brand" />}>
      <div className="mb-2.5 flex items-start gap-1.5 rounded-md border border-risk-med-border bg-risk-med-bg px-2.5 py-1.5 text-[11px] leading-relaxed text-ink-700">
        <AlertTriangle size={13} className="mt-0.5 shrink-0 text-risk-med-fg" />
        Internal fraud/risk signals are never included in the message — it's grounded only in the creator's public metrics. Review before sending.
      </div>
      {!draft && (
        <Button size="sm" variant="secondary" onClick={run} disabled={loading}
          leadingIcon={loading ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}>
          {loading ? "Drafting…" : "Draft outreach"}
        </Button>
      )}
      {tried && !loading && !draft && (
        <p className="text-[12px] text-ink-500">Outreach drafting runs on the backend. {apiBase() ? "Couldn't reach it just now — try again." : "Connect the API to try it."}</p>
      )}
      {draft && (
        <div>
          <div className="mb-2 flex items-center gap-2">
            <div className="flex overflow-hidden rounded-md border border-border text-[11px]">
              {(["en", "th"] as const).map((l) => (
                <button key={l} onClick={() => setLang(l)} aria-pressed={lang === l}
                  className={cn("px-2.5 py-1 font-medium uppercase", lang === l ? "bg-brand text-white" : "bg-white text-ink-500 hover:bg-surface")}>
                  {l}
                </button>
              ))}
            </div>
            <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", draft.grounded ? "bg-verified-bg text-verified-fg" : "bg-panel text-ink-600")}>
              {draft.source === "llm" ? "grounded · citation-checked" : "draft template"}
            </span>
            <button onClick={copy} className="ml-auto inline-flex items-center gap-1 text-[12px] font-medium text-brand hover:underline">
              {copied ? <Check size={13} /> : <Copy size={13} />} {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <p className={cn("rounded-lg border border-border bg-surface p-3 text-[13px] leading-relaxed text-ink-700", lang === "th" && "font-thai")}>
            {lang === "en" ? draft.en : draft.th}
          </p>
        </div>
      )}
    </Section>
  )
}

export function AfterBooking({ kol, brief }: { kol: Kol; brief: ClientBrief }) {
  return (
    <div className="space-y-4">
      <ReAudit kol={kol} />
      <Ledger kol={kol} brief={brief} />
      <Outreach kol={kol} brief={brief} />
    </div>
  )
}
