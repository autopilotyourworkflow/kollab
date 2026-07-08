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
import { Server, Zap } from "lucide-react"
import { Button } from "../components/ui/Button"
import { GraphCard } from "../components/app/GraphCard"
import { loadKeys, saveKeys, clearKeys, type ByoKeys } from "../lib/credentials"
import {
  apiBase,
  fetchCredit,
  getApifyAccounts,
  selectApifyAccount,
  type CreditInfo,
  type ApifyAccount,
  type ApifyAccountsPayload,
} from "../lib/credit"
import { cn } from "../lib/cn"

/** One row in the Apify-accounts pool: env label + masked hint + live balance + status,
 *  acting as a radio to make it the account runs start on. */
function AccountRow({
  account,
  selectedFp,
  onSelect,
  busy,
}: {
  account: ApifyAccount
  selectedFp: string | null
  onSelect: (fp: string) => void
  busy: boolean
}) {
  const a = account
  const chosen = selectedFp === a.fingerprint
  const hasNums = typeof a.remainingUsd === "number" && typeof a.limitUsd === "number" && (a.limitUsd as number) > 0
  const frac = hasNums ? Math.max(0, Math.min(1, (a.remainingUsd as number) / (a.limitUsd as number))) : 0
  const low = hasNums && (a.remainingUsd as number) < (a.limitUsd as number) * 0.2
  const empty = hasNums && (a.remainingUsd as number) <= 0
  const barColor = empty || !a.healthy ? "bg-risk-high" : low ? "bg-risk-med-fg" : "bg-verified"

  return (
    <button
      type="button"
      role="radio"
      aria-checked={chosen}
      disabled={busy}
      onClick={() => onSelect(a.fingerprint)}
      className={cn(
        "w-full rounded-xl border p-3.5 text-left transition-colors duration-200 disabled:opacity-60",
        chosen ? "border-brand-300 bg-brand-50/50 ring-1 ring-brand-300" : "border-border bg-white hover:border-brand-300",
      )}
    >
      <div className="flex items-center gap-2.5">
        {/* radio dot */}
        <span
          className={cn(
            "grid h-4 w-4 shrink-0 place-items-center rounded-full border",
            chosen ? "border-brand bg-brand" : "border-border-strong bg-white",
          )}
        >
          {chosen && <span className="h-1.5 w-1.5 rounded-full bg-white" />}
        </span>
        <span className="font-mono text-[12px] font-semibold text-ink">{a.hint}</span>
        <span className="rounded-full bg-panel px-1.5 py-px text-[10px] font-medium uppercase tracking-wide text-ink-500">
          {a.label}
        </span>
        <span className="ml-auto flex items-center gap-1.5">
          {a.active && (
            <span className="inline-flex items-center gap-1 rounded-full bg-verified-bg px-2 py-0.5 text-[10px] font-semibold text-verified-fg">
              <Zap size={10} /> Active
            </span>
          )}
          {!a.healthy && (
            <span className="inline-flex items-center gap-1 rounded-full bg-risk-high-bg px-2 py-0.5 text-[10px] font-semibold text-risk-high-fg">
              <AlertTriangle size={10} /> {a.note || "unavailable"}
            </span>
          )}
          {a.healthy && low && !empty && (
            <span className="rounded-full bg-risk-med-bg px-2 py-0.5 text-[10px] font-semibold text-risk-med-fg">Low</span>
          )}
        </span>
      </div>

      <div className="mt-2.5 pl-6.5">
        {a.checked && hasNums ? (
          <>
            <div className="flex items-baseline justify-between text-[12px]">
              <span className="text-ink-500">Apify credit</span>
              <span className="tnum font-semibold text-ink">
                ${(a.remainingUsd as number).toFixed(2)}
                <span className="font-normal text-ink-500"> of ${(a.limitUsd as number).toFixed(2)}</span>
              </span>
            </div>
            <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-panel">
              <div className={cn("h-full rounded-full transition-all", barColor)} style={{ width: `${frac * 100}%` }} />
            </div>
            {a.cycleEndAt && (
              <div className="mt-1 text-[10.5px] text-ink-400">resets {new Date(a.cycleEndAt).toLocaleDateString()}</div>
            )}
          </>
        ) : (
          <div className="text-[11px] text-ink-400">
            {a.balanceNote || "balance unreported"}
          </div>
        )}
      </div>
    </button>
  )
}

const AUTO = "__auto__"

/** The operator's Apify account pool — see every account (masked), their live balances, and
 *  manually pick which one runs start on. Runs auto-switch to the next healthy account when
 *  the chosen one runs low. Shown only when a backend + a pool are configured. */
function ApifyAccountsPanel() {
  const [data, setData] = useState<ApifyAccountsPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<string | null>(null) // fingerprint being selected

  const load = () => {
    if (!apiBase()) {
      setLoading(false)
      return
    }
    // Only the very first load blanks the panel to a spinner (loading starts true). A
    // re-fetch after a switch keeps the list visible and updates it in place — no flash.
    getApifyAccounts()
      .then((d) => {
        if (d) setData(d)
      })
      .finally(() => setLoading(false))
  }
  useEffect(load, [])

  const selectedFp = data?.preferred ?? AUTO

  const choose = (fp: string) => {
    if (busy) return
    setBusy(fp)
    // optimistic: mark the chosen one preferred immediately
    setData((d) =>
      d ? { ...d, preferred: fp === AUTO ? null : fp, accounts: d.accounts.map((a) => ({ ...a, preferred: a.fingerprint === fp })) } : d,
    )
    selectApifyAccount(fp === AUTO ? null : fp)
      .then(() => load()) // re-read balances + the recomputed "active" account
      .finally(() => setBusy(null))
  }

  if (!apiBase()) {
    return (
      <div className="flex items-start gap-2.5 rounded-lg border border-border bg-surface px-3.5 py-3 text-[12px] leading-relaxed text-ink-700">
        <Lock size={15} className="mt-0.5 shrink-0 text-ink-400" />
        <span>
          <span className="font-semibold text-ink">Offline preview.</span> Connect to a Kollab backend to view and switch
          between the operator's Apify accounts.
        </span>
      </div>
    )
  }
  if (loading) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3.5 py-3 text-[12px] text-ink-500">
        <Loader2 size={14} className="animate-spin" /> Loading accounts…
      </div>
    )
  }
  if (!data || !data.poolEnabled || data.accounts.length === 0) {
    return (
      <p className="text-[12px] leading-relaxed text-ink-500">
        No shared Apify accounts are configured on the server. The operator sets{" "}
        <code className="rounded bg-panel px-1 py-px font-mono text-[11px]">APIFY_TOKEN_1</code>,{" "}
        <code className="rounded bg-panel px-1 py-px font-mono text-[11px]">APIFY_TOKEN_2</code>, … in the deploy
        environment — or add your own key above to run on your account.
      </p>
    )
  }

  return (
    <div className="space-y-3">
      <p className="text-[12px] leading-relaxed text-ink-500">
        Runs start on the selected account and <span className="font-medium text-ink-700">automatically switch</span> to
        the next healthy one if it runs low or hits its monthly wall. Tokens live in the server environment — for safety
        each account shows a masked hint, never the full token.
      </p>

      <div role="radiogroup" aria-label="Apify account for runs" className="space-y-2">
        {/* Auto option */}
        <button
          type="button"
          role="radio"
          aria-checked={selectedFp === AUTO}
          disabled={!!busy}
          onClick={() => choose(AUTO)}
          className={cn(
            "flex w-full items-center gap-2.5 rounded-xl border p-3 text-left transition-colors duration-200 disabled:opacity-60",
            selectedFp === AUTO ? "border-brand-300 bg-brand-50/50 ring-1 ring-brand-300" : "border-border bg-white hover:border-brand-300",
          )}
        >
          <span
            className={cn(
              "grid h-4 w-4 shrink-0 place-items-center rounded-full border",
              selectedFp === AUTO ? "border-brand bg-brand" : "border-border-strong bg-white",
            )}
          >
            {selectedFp === AUTO && <span className="h-1.5 w-1.5 rounded-full bg-white" />}
          </span>
          <Server size={14} className="text-ink-400" />
          <span className="text-[13px] font-semibold text-ink">Auto</span>
          <span className="text-[12px] text-ink-500">— use accounts in order, skipping any that are low</span>
        </button>

        {data.accounts.map((a) => (
          <AccountRow key={a.fingerprint} account={a} selectedFp={selectedFp} onSelect={choose} busy={!!busy} />
        ))}
      </div>

      <button onClick={load} className="inline-flex items-center gap-1 text-[11px] font-medium text-ink-500 hover:text-brand">
        <RefreshCw size={12} /> Refresh balances
      </button>
    </div>
  )
}

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
          <span className="font-semibold text-ink">Offline preview.</span> This build isn't connected to a Kollab
          backend, so there's no live credit to show. Your keys are saved in this browser and are sent to the Kollab
          API automatically once it's connected.
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

      {/* ── Apify accounts (operator pool): view + manual switch + auto-switch ── */}
      <div className="mt-5 rounded-2xl border border-border bg-white p-6 shadow-sm">
        <div className="mb-3 flex items-center gap-2">
          <Server size={16} className="text-ink-400" />
          <h2 className="text-[16px] font-semibold text-ink">Apify accounts</h2>
        </div>
        <ApifyAccountsPanel />
      </div>

      {/* ── Fraud-recall moat: the persistent commenter graph ── */}
      <div className="mt-5 rounded-2xl border border-border bg-white p-6 shadow-sm">
        <h2 className="mb-3 text-[16px] font-semibold text-ink">Fraud graph</h2>
        <GraphCard />
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
