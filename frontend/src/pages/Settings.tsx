import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import {
  ArrowLeft,
  Key,
  Eye,
  EyeOff,
  ShieldCheck,
  RefreshCw,
  ExternalLink,
  AlertTriangle,
  Check,
  Trash2,
  ChevronDown,
  Loader2,
  Lock,
} from "lucide-react"
import { Button } from "../components/ui/Button"
import { KeyPool } from "../components/app/KeyPool"
import { loadKeys, saveKeys, clearKeys, type ByoKeys } from "../lib/credentials"
import { apiBase, fetchCredit, type CreditInfo } from "../lib/credit"
import { cn } from "../lib/cn"

/** One masked API-key input with a show/hide toggle. */
function KeyField({
  label,
  provider,
  placeholder,
  value,
  onChange,
}: {
  label: string
  provider: string
  placeholder: string
  value: string
  onChange: (v: string) => void
}) {
  const [shown, setShown] = useState(false)
  return (
    <div>
      <label className="mb-1.5 flex items-center gap-2 text-[13px] font-medium text-ink">
        <Key size={14} className="text-ink-400" />
        {label}
        <span className="rounded-full bg-panel px-1.5 py-px text-[10px] font-medium uppercase tracking-wide text-ink-500">
          {provider}
        </span>
      </label>
      <div className="relative">
        <input
          type={shown ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          autoComplete="off"
          spellCheck={false}
          className="h-11 w-full rounded-lg border border-border-strong bg-white pl-3 pr-11 font-mono text-[13px] text-ink shadow-xs placeholder:font-sans placeholder:text-ink-500 focus:border-brand-300"
        />
        {value && (
          <button
            type="button"
            onClick={() => setShown((s) => !s)}
            aria-label={shown ? "Hide key" : "Show key"}
            className="absolute right-2 top-1/2 grid h-7 w-7 -translate-y-1/2 place-items-center rounded-md text-ink-400 hover:bg-surface hover:text-ink"
          >
            {shown ? <EyeOff size={15} /> : <Eye size={15} />}
          </button>
        )}
      </div>
    </div>
  )
}

/** Collapsible, beginner-friendly steps for getting one provider's key. */
function HowTo({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="rounded-lg border border-border bg-surface">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3.5 py-2.5 text-left text-[12px] font-semibold text-ink-700"
      >
        <ChevronDown size={14} className={cn("shrink-0 text-ink-400 transition-transform", open && "rotate-180")} />
        {title}
      </button>
      {open && <div className="border-t border-border px-3.5 py-3 text-[12px] leading-relaxed text-ink-700">{children}</div>}
    </div>
  )
}

function ExtLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-0.5 font-medium text-brand hover:underline"
    >
      {children}
      <ExternalLink size={11} />
    </a>
  )
}

/** The live Apify credit bar + source label. */
function CreditMeter({ credit, loading, onRefresh }: { credit: CreditInfo | null; loading: boolean; onRefresh: () => void }) {
  const base = apiBase()

  if (!base) {
    return (
      <div className="flex items-start gap-2.5 rounded-lg border border-border bg-surface px-3.5 py-3 text-[12px] leading-relaxed text-ink-700">
        <Lock size={15} className="mt-0.5 shrink-0 text-ink-400" />
        <span>
          <span className="font-semibold text-ink">Demo mode.</span> Live credit appears here once Kollab is connected to
          its backend. Your keys are still saved in this browser now and will be used automatically the moment the live
          app is deployed.
        </span>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3.5 py-3 text-[12px] text-ink-500">
        <Loader2 size={14} className="animate-spin" /> Checking credit…
      </div>
    )
  }

  if (!credit) {
    return (
      <div className="flex items-center justify-between gap-2 rounded-lg border border-risk-med-border bg-risk-med-bg px-3.5 py-3 text-[12px] text-ink-700">
        <span className="flex items-center gap-2">
          <AlertTriangle size={14} className="text-risk-med-fg" /> Couldn't reach the credit API.
        </span>
        <button onClick={onRefresh} className="inline-flex items-center gap-1 font-medium text-brand hover:underline">
          <RefreshCw size={12} /> Retry
        </button>
      </div>
    )
  }

  const a = credit.apify
  const sourceChip =
    a.source === "user"
      ? { text: "Running on your Apify key", cls: "bg-verified-bg text-verified-fg", Icon: ShieldCheck }
      : a.source === "shared"
        ? { text: "Running on the shared operator key", cls: "bg-panel text-ink-700", Icon: ShieldCheck }
        : { text: "No Apify credit available — add your key below", cls: "bg-risk-med-bg text-risk-med-fg", Icon: AlertTriangle }
  const SourceIcon = sourceChip.Icon

  const hasNums = typeof a.remainingUsd === "number" && typeof a.limitUsd === "number" && a.limitUsd > 0
  const frac = hasNums ? Math.max(0, Math.min(1, (a.remainingUsd as number) / (a.limitUsd as number))) : 0
  const low = hasNums && (a.remainingUsd as number) < (a.limitUsd as number) * 0.2
  const empty = hasNums && (a.remainingUsd as number) <= 0
  const barColor = empty ? "bg-risk-high" : low ? "bg-risk-med-fg" : "bg-verified"

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium", sourceChip.cls)}>
          <SourceIcon size={12} /> {sourceChip.text}
        </span>
        <button onClick={onRefresh} className="inline-flex items-center gap-1 text-[11px] font-medium text-ink-500 hover:text-brand">
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      {a.checked && hasNums ? (
        <>
          <div className="flex items-baseline justify-between text-[13px]">
            <span className="text-ink-700">Apify credit this cycle</span>
            <span className="tnum font-semibold text-ink">
              ${(a.remainingUsd as number).toFixed(2)}{" "}
              <span className="font-normal text-ink-500">of ${(a.limitUsd as number).toFixed(2)} left</span>
            </span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-panel">
            <div className={cn("h-full rounded-full transition-all", barColor)} style={{ width: `${frac * 100}%` }} />
          </div>
          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-[11px] text-ink-500">
            <span>{typeof a.usedUsd === "number" ? `$${a.usedUsd.toFixed(2)} used` : "usage unreported"}</span>
            {a.cycleEndAt && <span>resets {new Date(a.cycleEndAt).toLocaleDateString()}</span>}
          </div>
          {empty ? (
            <p className="flex items-start gap-1.5 text-[11px] font-medium text-risk-high-fg">
              <AlertTriangle size={12} className="mt-0.5 shrink-0" /> This month's credit is used up. Add your own key
              below to keep running live.
            </p>
          ) : low ? (
            <p className="flex items-start gap-1.5 text-[11px] font-medium text-risk-med-fg">
              <AlertTriangle size={12} className="mt-0.5 shrink-0" /> Running low. Add your own Apify key below so live
              runs don't get interrupted.
            </p>
          ) : null}
        </>
      ) : (
        <p className="text-[12px] text-ink-500">
          {a.note || "Live usage isn't reported for this key — check the Apify console for the exact balance."}
        </p>
      )}
    </div>
  )
}

export function Settings() {
  const [keys, setKeys] = useState<ByoKeys>({ apify: "", anthropic: "" })
  const [saved, setSaved] = useState(false)
  const [credit, setCredit] = useState<CreditInfo | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setKeys(loadKeys())
  }, [])

  const refreshCredit = () => {
    if (!apiBase()) return
    setLoading(true)
    fetchCredit()
      .then(setCredit)
      .finally(() => setLoading(false))
  }
  // Load the meter once on mount (reads whatever keys are already stored).
  useEffect(refreshCredit, [])

  const onSave = () => {
    saveKeys(keys)
    setSaved(true)
    window.setTimeout(() => setSaved(false), 2000)
    refreshCredit() // re-check against the key we just stored
  }

  const onClear = () => {
    clearKeys()
    setKeys({ apify: "", anthropic: "" })
    setSaved(false)
    refreshCredit()
  }

  const dirty = (() => {
    const stored = loadKeys()
    return stored.apify !== keys.apify.trim() || stored.anthropic !== keys.anthropic.trim()
  })()

  return (
    <div className="mx-auto max-w-2xl px-6 py-10">
      <Link
        to="/app"
        className="mb-4 inline-flex min-h-[32px] items-center gap-1.5 text-[13px] font-medium text-ink-500 transition-colors duration-200 hover:text-brand"
      >
        <ArrowLeft size={15} />
        Back to shortlist
      </Link>

      <h1 className="text-[26px] font-bold tracking-[-0.02em] text-ink">Settings</h1>
      <p className="mt-1.5 text-[14px] text-ink-500">
        Run Kollab on your own API credit — useful when the shared credit runs low, or if you'd rather use your own
        account. No coding required.
      </p>

      {/* ── Operator Apify account pool (auto-rotation) ── */}
      <div className="mt-7">
        <KeyPool />
      </div>

      {/* ── Bring your own keys ── */}
      <div className="mt-7 rounded-2xl border border-border bg-white p-6 shadow-sm">
        <h2 className="text-[16px] font-semibold text-ink">Your API keys</h2>
        <div className="mt-2 flex items-start gap-2.5 rounded-lg border border-verified-border bg-verified-bg px-3.5 py-2.5">
          <ShieldCheck size={16} className="mt-0.5 shrink-0 text-verified-fg" />
          <p className="text-[12px] leading-relaxed text-ink-700">
            <span className="font-semibold text-verified-fg">These stay private to you.</span> Keys are saved only in
            this browser and sent straight to the Kollab API with each run. They are never stored on the server, never
            written to logs, and never shown to anyone else. Clear them anytime.
          </p>
        </div>

        <div className="mt-5 space-y-5">
          <KeyField
            label="Apify token"
            provider="TikTok sourcing"
            placeholder="apify_api_..."
            value={keys.apify}
            onChange={(v) => setKeys((k) => ({ ...k, apify: v }))}
          />
          <KeyField
            label="Claude (Anthropic) key"
            provider="brand reading & rationale"
            placeholder="sk-ant-..."
            value={keys.anthropic}
            onChange={(v) => setKeys((k) => ({ ...k, anthropic: v }))}
          />
        </div>

        <div className="mt-5 flex items-center gap-3">
          <Button onClick={onSave} disabled={!dirty} leadingIcon={saved ? <Check size={16} /> : undefined}>
            {saved ? "Saved" : "Save keys"}
          </Button>
          {(keys.apify || keys.anthropic) && (
            <Button variant="ghost" onClick={onClear} leadingIcon={<Trash2 size={15} />}>
              Clear
            </Button>
          )}
        </div>
      </div>

      {/* ── Credit meter ── */}
      <div className="mt-5 rounded-2xl border border-border bg-white p-6 shadow-sm">
        <h2 className="mb-3 text-[16px] font-semibold text-ink">Credit remaining</h2>
        <CreditMeter credit={credit} loading={loading} onRefresh={refreshCredit} />
        {credit && (
          <p className="mt-3 border-t border-border pt-3 text-[11px] leading-relaxed text-ink-500">
            {credit.anthropic.hasKey ? "A Claude key is set. " : "No Claude key set — brand reading falls back to the labeled draft. "}
            {credit.anthropic.note}
          </p>
        )}
      </div>

      {/* ── How to get the keys ── */}
      <div className="mt-5 rounded-2xl border border-border bg-white p-6 shadow-sm">
        <h2 className="mb-3 text-[16px] font-semibold text-ink">How to get your keys</h2>
        <div className="space-y-2.5">
          <HowTo title="Get an Apify token (free — for TikTok sourcing)">
            <ol className="list-decimal space-y-1.5 pl-4">
              <li>
                Go to <ExtLink href="https://console.apify.com/sign-up">apify.com and create a free account</ExtLink> —
                no credit card needed.
              </li>
              <li>Confirm your email and log in.</li>
              <li>
                Open <ExtLink href="https://console.apify.com/settings/integrations">Settings → Integrations</ExtLink>.
              </li>
              <li>
                Copy your <span className="font-semibold">Personal API token</span> (it starts with{" "}
                <code className="rounded bg-panel px-1 py-px font-mono text-[11px]">apify_api_</code>).
              </li>
              <li>Paste it in the Apify field above and press Save.</li>
            </ol>
            <p className="mt-2 text-ink-500">
              The free plan includes <span className="font-semibold text-ink-700">$5 of usage every month</span> — enough
              for several shortlist runs.
            </p>
          </HowTo>

          <HowTo title="Get a Claude (Anthropic) key — for brand reading & rationale">
            <ol className="list-decimal space-y-1.5 pl-4">
              <li>
                Go to <ExtLink href="https://console.anthropic.com/">console.anthropic.com</ExtLink> and sign up.
              </li>
              <li>
                Open <ExtLink href="https://console.anthropic.com/settings/keys">Settings → API Keys</ExtLink>.
              </li>
              <li>
                Click <span className="font-semibold">Create Key</span>, name it "Kollab", and copy it (it starts with{" "}
                <code className="rounded bg-panel px-1 py-px font-mono text-[11px]">sk-ant-</code>).
              </li>
              <li>Paste it in the Claude field above and press Save.</li>
            </ol>
            <p className="mt-2 text-ink-500">
              Claude is pay-as-you-go — add a small amount in{" "}
              <ExtLink href="https://console.anthropic.com/settings/billing">Billing</ExtLink>. A shortlist costs only a
              few cents. This key is optional: without it, Kollab still runs and shows a labeled draft brief.
            </p>
          </HowTo>
        </div>
      </div>
    </div>
  )
}
