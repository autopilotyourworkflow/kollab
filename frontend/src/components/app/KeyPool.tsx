import { useEffect, useState } from "react"
import {
  AlertTriangle,
  Check,
  Layers,
  Loader2,
  Lock,
  Plus,
  RefreshCw,
  ShieldCheck,
  Trash2,
  Unlock,
} from "lucide-react"
import { Button } from "../ui/Button"
import { apiBase } from "../../lib/credit"
import { cn } from "../../lib/cn"
import {
  addKey,
  deleteKey,
  forgetAdminSecret,
  hasAdminSecret,
  listKeys,
  refreshKeys,
  saveAdminSecret,
  type PoolKey,
  type PoolState,
  type PoolStatus,
} from "../../lib/keypool"

/** Colour + copy for each pool-key status — mirrors the CreditMeter's risk tokens. */
const STATUS_META: Record<PoolStatus, { label: string; dot: string; pill: string }> = {
  active: { label: "ready", dot: "bg-verified", pill: "bg-verified-bg text-verified-fg" },
  low: { label: "running low", dot: "bg-risk-med-fg", pill: "bg-risk-med-bg text-risk-med-fg" },
  exhausted: { label: "used up", dot: "bg-risk-high", pill: "bg-risk-high-bg text-risk-high-fg" },
  invalid: { label: "invalid key", dot: "bg-risk-high", pill: "bg-risk-high-bg text-risk-high-fg" },
  disabled: { label: "off", dot: "bg-ink-400", pill: "bg-panel text-ink-500" },
}

function StatusPill({ status }: { status: PoolStatus }) {
  const m = STATUS_META[status] ?? STATUS_META.disabled
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium", m.pill)}>
      <span className={cn("h-1.5 w-1.5 rounded-full", m.dot)} />
      {m.label}
    </span>
  )
}

function KeyRow({ k, onDelete, busy }: { k: PoolKey; onDelete: (id: string) => void; busy: boolean }) {
  const dollars =
    typeof k.remainingUsd === "number"
      ? `$${k.remainingUsd.toFixed(2)} left`
      : "balance unreported"
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface px-3.5 py-2.5">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="truncate text-[13px] font-medium text-ink">{k.label}</span>
          <StatusPill status={k.status} />
        </div>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-ink-500">
          <span className="font-mono">{k.hint}</span>
          <span aria-hidden>·</span>
          <span className="tnum">{dollars}</span>
          {k.cycleEndAt && (
            <>
              <span aria-hidden>·</span>
              <span>resets {new Date(k.cycleEndAt).toLocaleDateString()}</span>
            </>
          )}
        </div>
        {k.lastError && k.status !== "active" && (
          <p className="mt-1 truncate text-[11px] text-risk-med-fg" title={k.lastError}>
            {k.lastError}
          </p>
        )}
      </div>
      <button
        type="button"
        onClick={() => onDelete(k.id)}
        disabled={busy}
        aria-label={`Remove ${k.label}`}
        className="grid h-8 w-8 shrink-0 place-items-center rounded-md text-ink-400 hover:bg-panel hover:text-risk-high-fg disabled:opacity-40"
      >
        {busy ? <Loader2 size={15} className="animate-spin" /> : <Trash2 size={15} />}
      </button>
    </div>
  )
}

/** The operator's Apify account pool. Locked behind the admin password until unlocked;
 *  once unlocked, paste tokens and the backend spends + rotates them automatically. */
export function KeyPool() {
  const live = Boolean(apiBase())
  const [unlocked, setUnlocked] = useState(false)
  const [secretInput, setSecretInput] = useState("")
  const [unlockErr, setUnlockErr] = useState("")
  const [unlocking, setUnlocking] = useState(false)

  const [state, setState] = useState<PoolState | null>(null)
  const [loading, setLoading] = useState(false)

  const [token, setToken] = useState("")
  const [label, setLabel] = useState("")
  const [adding, setAdding] = useState(false)
  const [addErr, setAddErr] = useState("")
  const [addedFlash, setAddedFlash] = useState(false)

  const [refreshing, setRefreshing] = useState(false)
  const [busyId, setBusyId] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    const r = await listKeys()
    setLoading(false)
    if (r.ok) setState(r.data)
  }

  // If a password is already remembered in this browser, open straight to the pool.
  useEffect(() => {
    if (live && hasAdminSecret()) {
      setUnlocked(true)
      void load()
    }
  }, [live])

  const onUnlock = async () => {
    const s = secretInput.trim()
    if (!s) return
    setUnlocking(true)
    setUnlockErr("")
    const r = await listKeys(s) // validate the password by actually calling the gated endpoint
    setUnlocking(false)
    if (r.ok) {
      saveAdminSecret(s)
      setUnlocked(true)
      setSecretInput("")
      setState(r.data)
    } else if (r.status === 401) {
      setUnlockErr("That admin password is incorrect.")
    } else if (r.status === 503) {
      setUnlockErr("The pool isn't enabled on the server yet (set KOLLAB_ADMIN_SECRET).")
    } else {
      setUnlockErr(r.error)
    }
  }

  const onLock = () => {
    forgetAdminSecret()
    setUnlocked(false)
    setState(null)
  }

  const onAdd = async () => {
    const t = token.trim()
    if (!t) return
    setAdding(true)
    setAddErr("")
    const r = await addKey(t, label.trim())
    setAdding(false)
    if (r.ok) {
      setToken("")
      setLabel("")
      setAddedFlash(true)
      window.setTimeout(() => setAddedFlash(false), 1800)
      void load()
    } else {
      setAddErr(r.error)
    }
  }

  const onDelete = async (id: string) => {
    setBusyId(id)
    await deleteKey(id)
    setBusyId(null)
    void load()
  }

  const onRefresh = async () => {
    setRefreshing(true)
    await refreshKeys()
    setRefreshing(false)
    void load()
  }

  // ── Demo mode (no backend): nothing to manage, say so honestly. ──
  if (!live) {
    return (
      <Card>
        <Header />
        <div className="mt-4 flex items-start gap-2.5 rounded-lg border border-border bg-surface px-3.5 py-3 text-[12px] leading-relaxed text-ink-700">
          <Lock size={15} className="mt-0.5 shrink-0 text-ink-400" />
          <span>
            <span className="font-semibold text-ink">Demo mode.</span> The account pool appears here once Kollab is
            connected to its live backend.
          </span>
        </div>
      </Card>
    )
  }

  // ── Locked: ask for the admin password. ──
  if (!unlocked) {
    return (
      <Card>
        <Header />
        <div className="mt-4 flex items-start gap-2.5 rounded-lg border border-border bg-surface px-3.5 py-2.5">
          <ShieldCheck size={16} className="mt-0.5 shrink-0 text-ink-400" />
          <p className="text-[12px] leading-relaxed text-ink-700">
            This area is for the operator only. Enter the admin password to add and see your Apify accounts. Keys are
            stored <span className="font-semibold text-ink">encrypted</span> and are never shown to anyone.
          </p>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <input
            type="password"
            value={secretInput}
            onChange={(e) => setSecretInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && onUnlock()}
            placeholder="Admin password"
            autoComplete="off"
            className="h-11 flex-1 rounded-lg border border-border-strong bg-white px-3 text-[13px] text-ink shadow-xs placeholder:text-ink-500 focus:border-brand-300"
          />
          <Button onClick={onUnlock} disabled={!secretInput.trim() || unlocking} leadingIcon={unlocking ? <Loader2 size={16} className="animate-spin" /> : <Unlock size={16} />}>
            Unlock
          </Button>
        </div>
        {unlockErr && (
          <p className="mt-2 flex items-start gap-1.5 text-[12px] font-medium text-risk-high-fg">
            <AlertTriangle size={13} className="mt-0.5 shrink-0" /> {unlockErr}
          </p>
        )}
      </Card>
    )
  }

  // ── Unlocked: the pool manager. ──
  const keys = state?.keys ?? []
  const sum = state?.summary
  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <Header />
        <button onClick={onLock} className="mt-1 inline-flex shrink-0 items-center gap-1 text-[11px] font-medium text-ink-500 hover:text-brand">
          <Lock size={12} /> Lock
        </button>
      </div>

      {sum && (
        <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px]">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-verified-bg px-2.5 py-1 font-medium text-verified-fg">
            <span className="h-1.5 w-1.5 rounded-full bg-verified" /> {sum.active} ready
          </span>
          {sum.low > 0 && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-risk-med-bg px-2.5 py-1 font-medium text-risk-med-fg">
              {sum.low} low
            </span>
          )}
          {sum.exhausted > 0 && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-panel px-2.5 py-1 font-medium text-ink-500">
              {sum.exhausted} used up
            </span>
          )}
          {typeof sum.totalRemainingUsd === "number" && (
            <span className="tnum ml-auto font-semibold text-ink">${sum.totalRemainingUsd.toFixed(2)} total left</span>
          )}
        </div>
      )}

      {/* Paste a new key */}
      <div className="mt-4 rounded-xl border border-border bg-surface p-4">
        <label className="mb-1.5 block text-[12px] font-semibold text-ink-700">Paste a new Apify key</label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="apify_api_..."
            autoComplete="off"
            spellCheck={false}
            className="h-11 flex-1 rounded-lg border border-border-strong bg-white px-3 font-mono text-[13px] text-ink shadow-xs placeholder:font-sans placeholder:text-ink-500 focus:border-brand-300"
          />
          <input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="Name (optional)"
            className="h-11 rounded-lg border border-border-strong bg-white px-3 text-[13px] text-ink shadow-xs placeholder:text-ink-500 focus:border-brand-300 sm:w-40"
          />
          <Button
            onClick={onAdd}
            disabled={!token.trim() || adding}
            leadingIcon={adding ? <Loader2 size={16} className="animate-spin" /> : addedFlash ? <Check size={16} /> : <Plus size={16} />}
          >
            {addedFlash ? "Added" : "Add"}
          </Button>
        </div>
        {addErr && (
          <p className="mt-2 flex items-start gap-1.5 text-[12px] font-medium text-risk-high-fg">
            <AlertTriangle size={13} className="mt-0.5 shrink-0" /> {addErr}
          </p>
        )}
        <p className="mt-2 text-[11px] leading-relaxed text-ink-500">
          Free Apify accounts include $5/month. Paste as many as you like — Kollab spends the fattest one and switches
          by itself when it runs low. You never manage it after this.
        </p>
      </div>

      {/* The accounts */}
      <div className="mt-4 flex items-center justify-between">
        <h3 className="text-[13px] font-semibold text-ink-700">Your accounts</h3>
        <button
          onClick={onRefresh}
          disabled={refreshing}
          className="inline-flex items-center gap-1 text-[11px] font-medium text-ink-500 hover:text-brand disabled:opacity-40"
        >
          <RefreshCw size={12} className={cn(refreshing && "animate-spin")} /> Refresh balances
        </button>
      </div>

      <div className="mt-2 space-y-2">
        {loading && !keys.length ? (
          <div className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3.5 py-3 text-[12px] text-ink-500">
            <Loader2 size={14} className="animate-spin" /> Loading accounts…
          </div>
        ) : keys.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border-strong bg-surface px-3.5 py-4 text-center text-[12px] text-ink-500">
            No accounts yet. Paste your first Apify key above to start the rotation.
          </div>
        ) : (
          keys.map((k) => <KeyRow key={k.id} k={k} onDelete={onDelete} busy={busyId === k.id} />)
        )}
      </div>
    </Card>
  )
}

function Card({ children }: { children: React.ReactNode }) {
  return <div className="rounded-2xl border border-border bg-white p-6 shadow-sm">{children}</div>
}

function Header() {
  return (
    <div>
      <h2 className="flex items-center gap-2 text-[16px] font-semibold text-ink">
        <Layers size={17} className="text-brand" />
        Apify accounts <span className="text-[12px] font-normal text-ink-500">(auto-rotation)</span>
      </h2>
      <p className="mt-1 text-[13px] text-ink-500">
        Add several free Apify accounts. Kollab spends them one at a time and switches to the next by itself when one
        runs low — so live runs never stop.
      </p>
    </div>
  )
}
