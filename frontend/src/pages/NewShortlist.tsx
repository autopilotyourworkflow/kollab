import { useEffect, useRef, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { motion } from "motion/react"
import {
  Globe,
  ArrowRight,
  ArrowLeft,
  Loader2,
  Plus,
  X,
  ShieldCheck,
  Sparkles,
  ChevronDown,
  AlertTriangle,
  RotateCcw,
  Bookmark,
} from "lucide-react"
import { Button } from "../components/ui/Button"
import { ProvenanceChip } from "../components/ui/ProvenanceChip"
import { client, brandDna, kols as demoKols, summary as demoSummary, cost as demoCost, commenterOverlap as demoOverlap } from "../data/kols"
import { authHeaders } from "../lib/credentials"
import { apiBase, fetchCredit, runExceedsCredit, type CreditInfo } from "../lib/credit"
import { createEntry } from "../lib/workspace"
import { startRun } from "../lib/api"
import { addRun } from "../lib/runsStore"
import type { ClientBrief } from "../lib/types"
import {
  defaultCap,
  defaultPlan,
  estimateCustom,
  fromPreset,
  plans,
  saveRunPlan,
  type RunPlanChoice,
} from "../lib/runPlan"
import { cn } from "../lib/cn"

type Phase = "input" | "analyzing" | "review" | "error"

/** A non-degraded extraction from the live backend (POST /api/brand-dna). */
type LiveExtraction = { brand: string; brandTh: string; category: string; source: string }

/** Try the real Brand-DNA endpoint (Claude → Gemini on the backend). Returns null
    when there is no live backend, the call fails, or the backend answered with the
    honestly-degraded rules skeleton — the UI then keeps its labeled demo path. */
async function tryLiveBrandDna(website: string, text?: string): Promise<{
  live: LiveExtraction | null
  brief?: { audience?: string; region?: string; pillars?: string[]; tone?: string; searchTerms?: string[] }
}> {
  // Only when a live backend is configured — the static demo hosting has no
  // /api/brand-dna, so probing it would just log 404 noise.
  const base = import.meta.env.VITE_API_URL as string | undefined
  if (!base) return { live: null }
  try {
    const ctrl = new AbortController()
    // Supplied text (paste box / bookmarklet) is fast; a URL may need the server's
    // reader fallback (r.jina.ai renders JS), so give that path more headroom.
    const t = window.setTimeout(() => ctrl.abort(), text ? 15_000 : 25_000)
    const res = await fetch(`${base}/api/brand-dna`, {
      method: "POST",
      headers: { "content-type": "application/json", ...authHeaders() },
      body: JSON.stringify(text ? { website, text } : { website }),
      signal: ctrl.signal,
    })
    window.clearTimeout(t)
    if (!res.ok) return { live: null }
    const data = (await res.json()) as {
      degraded?: boolean
      source?: string
      brief?: { brand?: string; brandTh?: string; category?: string; audience?: string; region?: string; pillars?: string[]; tone?: string; searchTerms?: string[] }
    }
    if (data?.degraded === false && typeof data.brief?.brand === "string" && data.brief.brand) {
      return {
        live: {
          brand: data.brief.brand,
          brandTh: data.brief.brandTh ?? "",
          category: data.brief.category ?? "",
          source: data.source ?? "llm",
        },
        brief: data.brief,
      }
    }
    return { live: null }
  } catch {
    return { live: null } // static hosting / offline: the demo path takes over
  }
}

function Field({
  label,
  provenance,
  children,
}: {
  label: string
  provenance?: "measured" | "inferred" | "estimated"
  children: React.ReactNode
}) {
  return (
    <div>
      <div className="mb-1.5 flex items-center gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-ink-400">{label}</span>
        {provenance && <ProvenanceChip kind={provenance} />}
      </div>
      {children}
    </div>
  )
}

export function NewShortlist() {
  const navigate = useNavigate()
  const [phase, setPhase] = useState<Phase>("input")
  const [url, setUrl] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [showFb, setShowFb] = useState(false)
  const [fbText, setFbText] = useState("")
  const known = url.toLowerCase().includes("glowlab")
  // Is this build pointed at a live Kollab backend (with the LLM key)? The deployed
  // product is; a keyless static build isn't. Governs the honest "why no live
  // extraction" copy below — a wired site that can't read a brand blocked our reader,
  // it did NOT run out of keys.
  const wired = !!apiBase()

  // Paste box + bookmarklet (offered when a site can't be auto-read): a real browser reads
  // sites a datacenter fetch can't. The bookmarklet grabs the rendered page text and reopens
  // this page with it in the hash; the href is built from the current origin.
  const [pasteText, setPasteText] = useState("")
  const bookmarkletHref =
    "javascript:(function(){" +
    "var t=(document.body.innerText||'').replace(/\\s+/g,' ').slice(0,12000);" +
    "var p=encodeURIComponent(JSON.stringify({url:location.href,text:t}));" +
    "location.href=" +
    JSON.stringify((typeof window !== "undefined" ? window.location.origin : "") + "/app/new#brand=") +
    "+p;})()"

  // editable brand DNA (HITL on the brief)
  const [audience, setAudience] = useState(client.audience)
  const [tone, setTone] = useState(brandDna.tone)
  const [region, setRegion] = useState(client.region)
  const [pillars, setPillars] = useState<string[]>(client.pillars)
  // TikTok content search-terms from live extraction (drives creator sourcing; distinct
  // from the display pillars). Empty unless a live brand is extracted.
  const [searchTerms, setSearchTerms] = useState<string[]>([])
  const [addingPillar, setAddingPillar] = useState(false)
  const [pillarDraft, setPillarDraft] = useState("")
  const addPillarRef = useRef<HTMLButtonElement>(null)

  // Brand-safety no-go: the AM's own exclusions, not scraped from the site. Starts at the
  // demo default for the fixtures brand; a live extraction clears it (nothing hardcoded is
  // ever shown as if it were read from the brand).
  const [noGo, setNoGo] = useState<string[]>(brandDna.noGo)
  const [addingNoGo, setAddingNoGo] = useState(false)
  const [noGoDraft, setNoGoDraft] = useState("")
  const addNoGoRef = useRef<HTMLButtonElement>(null)

  const commitNoGo = () => {
    const n = noGoDraft.trim()
    if (n && !noGo.some((x) => x.toLowerCase() === n.toLowerCase())) setNoGo((xs) => [...xs, n])
    setNoGoDraft("")
    setAddingNoGo(false)
    requestAnimationFrame(() => addNoGoRef.current?.focus())
  }

  const commitPillar = () => {
    const p = pillarDraft.trim()
    if (p && !pillars.some((x) => x.toLowerCase() === p.toLowerCase())) {
      setPillars((ps) => [...ps, p])
    }
    setPillarDraft("")
    setAddingPillar(false)
    // the input unmounts — keep keyboard focus in the pillar group
    requestAnimationFrame(() => addPillarRef.current?.focus())
  }

  const [live, setLive] = useState<LiveExtraction | null>(null)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  // Run depth & budget: preset selection (or custom volumes) + editable hard cap.
  const [planKey, setPlanKey] = useState(plans.defaultPreset)
  const [customCreators, setCustomCreators] = useState(20)
  const [customComments, setCustomComments] = useState(120)
  const [capEdited, setCapEdited] = useState<number | null>(null)

  // Live credit for the pre-run warning (only when a backend is configured — the
  // static demo skips it). Reads whatever key this browser has stored.
  const [credit, setCredit] = useState<CreditInfo | null>(null)
  useEffect(() => {
    if (apiBase()) fetchCredit().then(setCredit)
  }, [])

  const currentPlan = (): RunPlanChoice => {
    if (planKey === "custom") {
      const est = estimateCustom(customCreators, customComments)
      return {
        key: "custom", label: "Custom",
        maxCreators: customCreators, commentsPerCreator: customComments,
        estUsd: est, capUsd: capEdited ?? defaultCap(est),
      }
    }
    const preset = plans.presets.find((p) => p.key === planKey)
    const base = preset ? fromPreset(preset) : defaultPlan()
    return capEdited !== null ? { ...base, capUsd: capEdited } : base
  }
  const plan = currentPlan()
  const planNote = planKey === "custom"
    ? "Custom depth — quality follows the volumes you choose; cohort stats withhold below n=15 regardless (the rule is not configurable)."
    : plans.presets.find((p) => p.key === planKey)?.note ?? ""

  const runExtraction = async (targetUrl: string, textOverride?: string) => {
    const cleaned = targetUrl.trim().replace(/^https?:\/\//i, "").replace(/\/+$/, "")
    // Supplied text (paste / bookmarklet) doesn't need a valid URL; a plain run does.
    if (!textOverride && !/^([\w-]+\.)+[a-z]{2,}(\/.*)?$/i.test(cleaned)) {
      setError("Enter a valid website — e.g. glowlab.co.th")
      return
    }
    setError(null)
    setUrl(cleaned)
    setPhase("analyzing")
    const willFail = /fail|error|unreachable|broken/i.test(cleaned)
    const startedAt = Date.now()

    // Real extraction (live backend + LLM key): direct fetch → reader fallback, or the
    // supplied text. The labeled draft takes over on any miss — never a fake green badge.
    const result = await tryLiveBrandDna(cleaned, textOverride)
    setLive(result.live)
    if (result.live && result.brief) {
      if (result.brief.audience) setAudience(result.brief.audience)
      if (result.brief.region) setRegion(result.brief.region)
      if (result.brief.pillars?.length) setPillars(result.brief.pillars)
      setTone(result.brief.tone || "") // extracted tone (or clear the demo default on a live brand)
      setSearchTerms(result.brief.searchTerms || []) // content topics that drive creator sourcing
    }
    if (result.live) {
      setNoGo([]) // the no-go list is the AM's call, not scraped — start empty on a live brand
      setPasteText("")
    }

    // keep the reading state legible even when the answer is instant
    const waitLeft = Math.max(300, 1700 - (Date.now() - startedAt))
    window.setTimeout(() => setPhase(willFail && !result.live ? "error" : "review"), waitLeft)
  }
  const analyze = () => runExtraction(url)

  // Bookmarklet payload arrives in the hash (#brand=<{url,text}>) — a real browser read the
  // page for us. Extract from it, then clear the hash so a refresh doesn't re-fire.
  useEffect(() => {
    const m = window.location.hash.match(/[#&]brand=([^&]+)/)
    if (!m) return
    try {
      const payload = JSON.parse(decodeURIComponent(m[1])) as { url?: string; text?: string }
      history.replaceState(null, "", window.location.pathname + window.location.search)
      if (payload.text && payload.text.trim()) void runExtraction(payload.url || "", payload.text)
      else if (payload.url) setUrl(payload.url.replace(/^https?:\/\//i, "").replace(/\/+$/, ""))
    } catch {
      /* malformed hash — ignore */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="mx-auto max-w-2xl px-6 py-10">
      {/* in-UI way back — never rely on the browser button */}
      <Link
        to="/app"
        className="mb-4 inline-flex min-h-[32px] items-center gap-1.5 text-[13px] font-medium text-ink-500 transition-colors duration-200 hover:text-brand"
      >
        <ArrowLeft size={15} />
        Back to shortlist
      </Link>

      {phase !== "review" && (
        <>
          <h1 className="text-[26px] font-bold tracking-[-0.02em] text-ink">New shortlist</h1>
          <p className="mt-1.5 text-[14px] text-ink-500">
            Paste the client's website. Kollab reads their brand, then finds and vets matching Thai TikTok KOLs.
          </p>
        </>
      )}

      {/* ── Input ── */}
      {phase === "input" && (
        <div className="mt-7 rounded-2xl border border-border bg-white p-6 shadow-sm">
          <label className="mb-1.5 block text-[13px] font-medium text-ink">Client website</label>
          <div className="relative">
            <Globe size={17} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
            <input
              value={url}
              onChange={(e) => {
                setUrl(e.target.value)
                if (error) setError(null)
              }}
              onKeyDown={(e) => e.key === "Enter" && analyze()}
              placeholder="https://client-website.com"
              aria-invalid={!!error}
              aria-describedby={error ? "url-error" : undefined}
              className={cn(
                "h-11 w-full rounded-lg border bg-white pl-10 pr-3 text-[15px] text-ink shadow-xs placeholder:text-ink-500 focus:border-brand-300",
                error ? "border-risk-high" : "border-border-strong",
              )}
            />
          </div>
          {error ? (
            <p id="url-error" role="alert" className="mt-2 flex items-center gap-1.5 text-[12px] font-medium text-risk-high-fg">
              <AlertTriangle size={13} /> {error}
            </p>
          ) : (
            <button
              onClick={() => setUrl("glowlab.co.th")}
              className="mt-2 text-[12px] font-medium text-brand hover:underline"
            >
              Use example · glowlab.co.th
            </button>
          )}

          {/* optional FB */}
          <button
            onClick={() => setShowFb((v) => !v)}
            className="mt-5 flex items-center gap-1.5 text-[13px] font-medium text-ink-700"
          >
            <ChevronDown size={15} className={cn("transition-transform", showFb && "rotate-180")} />
            Add Facebook page (optional)
          </button>
          {showFb && (
            <>
              <textarea
                value={fbText}
                onChange={(e) => setFbText(e.target.value)}
                placeholder="Paste the client's Facebook page URL or an About / bio snippet…"
                rows={2}
                className="mt-2 w-full resize-none rounded-lg border border-border-strong bg-white px-3 py-2 text-[13px] text-ink shadow-xs placeholder:text-ink-500 focus:border-brand-300"
              />
              {fbText.trim() && (
                <p className="mt-1.5 text-[11px] font-medium text-verified-fg">
                  ✓ Will be read as additional brand context alongside the website.
                </p>
              )}
            </>
          )}

          <div className="mt-6 flex items-center justify-between">
            <p className="max-w-xs text-[11px] leading-relaxed text-ink-400">
              Reads public data only. No login required. PDPA-aware — creator data is used lawful-basis, minimised.
            </p>
            <Button onClick={analyze} disabled={!url} trailingIcon={<ArrowRight size={16} />}>
              Analyze brand
            </Button>
          </div>
        </div>
      )}

      {/* ── Analyzing ── */}
      {phase === "analyzing" && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25, ease: [0.25, 1, 0.5, 1] }}
          className="mt-7 grid place-items-center rounded-2xl border border-border bg-white px-6 py-16 shadow-sm"
        >
          <Loader2 size={30} className="animate-spin text-brand" />
          <p className="mt-4 text-[15px] font-medium text-ink">Reading {url || "the website"}…</p>
          <p className="mt-1 text-[13px] text-ink-500">Extracting brand pillars, audience, tone, and the no-go list.</p>
        </motion.div>
      )}

      {/* ── Error ── */}
      {phase === "error" && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25, ease: [0.25, 1, 0.5, 1] }}
          className="mt-7 rounded-2xl border border-risk-high-border bg-white p-6 shadow-sm">
          <div className="flex items-start gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-risk-high-bg text-risk-high-fg">
              <AlertTriangle size={20} />
            </span>
            <div>
              <div className="text-[15px] font-semibold text-ink">Couldn't read {url}</div>
              <p className="mt-1 text-[13px] leading-relaxed text-ink-500">
                The page was unreachable or blocked automated reading. Check the URL, or paste the brand's About
                text so Kollab can read it directly. Nothing was charged for the failed attempt.
              </p>
            </div>
          </div>
          <div className="mt-5 flex items-center gap-2">
            <Button variant="secondary" onClick={() => setPhase("input")} leadingIcon={<ArrowLeft size={16} />}>
              Back
            </Button>
            <Button onClick={analyze} leadingIcon={<RotateCcw size={16} />}>
              Try again
            </Button>
          </div>
        </motion.div>
      )}

      {/* ── Review Brand DNA ── */}
      {phase === "review" && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: [0.25, 1, 0.5, 1] }}
        >
          <div className="flex items-center gap-2">
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-brand-50 text-brand">
              <Sparkles size={15} />
            </span>
            <h1 className="text-[22px] font-bold tracking-[-0.01em] text-ink">Brand DNA</h1>
            {/* honest badge: a green "extracted" claim only when extraction actually
                ran (live LLM path, or the demo's covered brand); anything else is a
                labeled draft */}
            {live ? (
              <span className="ml-1 inline-flex items-center gap-1 rounded-full bg-verified-bg px-2 py-0.5 text-[11px] font-medium text-verified-fg">
                <ShieldCheck size={12} /> extracted live from {url} · via {live.source}
              </span>
            ) : known ? (
              <span className="ml-1 inline-flex items-center gap-1 rounded-full bg-verified-bg px-2 py-0.5 text-[11px] font-medium text-verified-fg">
                <ShieldCheck size={12} /> extracted from {url || "glowlab.co.th"}
              </span>
            ) : (
              <span className="ml-1 inline-flex items-center gap-1 rounded-full bg-risk-med-bg px-2 py-0.5 text-[11px] font-medium text-risk-med-fg">
                <AlertTriangle size={12} /> {wired ? "draft — couldn't auto-read this site" : "draft — offline preview"}
              </span>
            )}
          </div>
          <p className="mt-1.5 text-[13px] text-ink-500">
            This is what Kollab understood about the brand. Edit anything, then find matching KOLs.
          </p>

          {!live && !known && (
            <div className="mt-4 flex items-start gap-2.5 rounded-lg border border-risk-med-border bg-risk-med-bg px-3.5 py-2.5">
              <AlertTriangle size={16} className="mt-0.5 shrink-0 text-risk-med-fg" />
              <p className="text-[12px] leading-relaxed text-ink-700">
                {wired ? (
                  <>
                    <span className="font-semibold text-risk-med-fg">Couldn't auto-read {url || "this site"}.</span>{" "}
                    Live extraction ran, but the site blocked our reader or returned no usable text — many brand sites
                    block automated fetches. The fields below are a starting draft: edit them (or paste the brand
                    details), then find matching KOLs.
                  </>
                ) : (
                  <>
                    <span className="font-semibold text-risk-med-fg">Offline preview.</span> This build isn't pointed
                    at a Kollab backend, so live Brand-DNA extraction (<code>POST /api/brand-dna</code>) isn't reachable
                    here. The fields below are a sample brief, shown so you can see and edit the review flow.
                  </>
                )}
              </p>
            </div>
          )}

          {wired && !live && !known && (
            <div className="mt-3 rounded-lg border border-border bg-surface px-3.5 py-3">
              <div className="text-[12px] font-semibold text-ink">Read it another way</div>
              <p className="mt-0.5 text-[11.5px] leading-relaxed text-ink-500">
                Paste the page's text below, or grab it from your own browser with the bookmarklet — a real browser
                reads sites a server can't.
              </p>
              <textarea
                value={pasteText}
                onChange={(e) => setPasteText(e.target.value)}
                placeholder="Paste the brand page's text here…"
                rows={3}
                className="mt-2 w-full resize-none rounded-lg border border-border-strong bg-white px-3 py-2 text-[13px] text-ink shadow-xs placeholder:text-ink-500 focus:border-brand-300"
              />
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <Button
                  size="sm"
                  onClick={() => pasteText.trim() && runExtraction(url, pasteText.trim())}
                  disabled={!pasteText.trim()}
                  leadingIcon={<Sparkles size={14} />}
                >
                  Extract from pasted text
                </Button>
                <a
                  ref={(el) => {
                    if (el) el.setAttribute("href", bookmarkletHref)
                  }}
                  onClick={(e) => e.preventDefault()}
                  draggable
                  title="Drag me to your bookmarks bar, then click me while viewing a brand's website"
                  className="inline-flex cursor-grab items-center gap-1.5 rounded-md border border-dashed border-border-strong px-2.5 py-1.5 text-[12px] font-medium text-ink-700 transition-colors hover:border-brand-300 hover:text-brand"
                >
                  <Bookmark size={13} /> Kollab bookmarklet
                </a>
                <span className="text-[11px] text-ink-400">drag to bookmarks → click on the brand's site</span>
              </div>
            </div>
          )}

          <div className="mt-5 space-y-5 rounded-2xl border border-border bg-white p-6 shadow-sm">
            <div className="flex items-baseline gap-2 border-b border-border pb-4">
              <span className="text-[19px] font-bold text-ink">{live?.brand ?? client.brand}</span>
              {(live ? live.brandTh : client.brandTh) && (
                <span className="font-thai text-[15px] text-ink-400">· {live?.brandTh ?? client.brandTh}</span>
              )}
              <span className="ml-auto rounded-full bg-panel px-2.5 py-1 text-[12px] font-medium text-ink-700">
                {live?.category ?? client.category}
              </span>
            </div>

            <Field label="Target audience" provenance="inferred">
              <input
                value={audience}
                onChange={(e) => setAudience(e.target.value)}
                className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-[14px] text-ink focus:border-brand-300 focus:bg-white"
              />
            </Field>

            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Tone & voice" provenance="inferred">
                <input
                  value={tone}
                  onChange={(e) => setTone(e.target.value)}
                  className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-[14px] text-ink focus:border-brand-300 focus:bg-white"
                />
                {tone === brandDna.tone && (
                  <p className="font-thai mt-1 text-[13px] text-ink-500">{brandDna.toneTh}</p>
                )}
              </Field>
              <Field label="Region focus" provenance="measured">
                <input
                  value={region}
                  onChange={(e) => setRegion(e.target.value)}
                  className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-[14px] text-ink focus:border-brand-300 focus:bg-white"
                />
              </Field>
            </div>

            <Field label="Content pillars" provenance="measured">
              <div className="flex flex-wrap gap-2">
                {pillars.map((p) => (
                  <span
                    key={p}
                    className="group inline-flex items-center gap-1.5 rounded-full bg-brand-50 py-1 pl-3 pr-2 text-[12px] font-medium text-brand"
                  >
                    {p}
                    <button
                      onClick={() => {
                        setPillars((ps) => ps.filter((x) => x !== p))
                        // removed button unmounts — hand focus to the Add control
                        requestAnimationFrame(() => addPillarRef.current?.focus())
                      }}
                      className="-my-1 grid h-6 w-6 place-items-center rounded-full text-brand/60 hover:bg-brand-100 hover:text-brand"
                      aria-label={`Remove ${p}`}
                    >
                      <X size={12} />
                    </button>
                  </span>
                ))}
                {addingPillar ? (
                  <span className="inline-flex items-center gap-1 rounded-full border border-brand-300 bg-white py-0.5 pl-3 pr-1">
                    <input
                      autoFocus
                      value={pillarDraft}
                      onChange={(e) => setPillarDraft(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") commitPillar()
                        if (e.key === "Escape") {
                          setPillarDraft("")
                          setAddingPillar(false)
                          requestAnimationFrame(() => addPillarRef.current?.focus())
                        }
                      }}
                      onBlur={commitPillar}
                      placeholder="New pillar…"
                      className="w-32 bg-transparent text-[12px] font-medium text-ink outline-none placeholder:text-ink-500"
                      aria-label="New content pillar"
                    />
                    <button
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={commitPillar}
                      className="grid h-6 w-6 place-items-center rounded-full bg-brand-50 text-brand hover:bg-brand-100"
                      aria-label="Add pillar"
                    >
                      <Plus size={13} />
                    </button>
                  </span>
                ) : (
                  <button
                    ref={addPillarRef}
                    onClick={() => setAddingPillar(true)}
                    className="inline-flex min-h-[28px] items-center gap-1 rounded-full border border-dashed border-border-strong px-2.5 py-1 text-[12px] font-medium text-ink-500 transition-colors duration-200 hover:border-brand-300 hover:text-brand"
                  >
                    <Plus size={13} /> Add
                  </button>
                )}
              </div>
            </Field>

            <Field label="Brand-safety no-go">
              <div className="flex flex-wrap items-center gap-2">
                {noGo.map((n) => (
                  <span
                    key={n}
                    className="group inline-flex items-center gap-1.5 rounded-full border border-risk-med-border bg-risk-med-bg py-1 pl-3 pr-2 text-[12px] font-medium text-risk-med-fg"
                  >
                    {n}
                    <button
                      onClick={() => {
                        setNoGo((xs) => xs.filter((x) => x !== n))
                        requestAnimationFrame(() => addNoGoRef.current?.focus())
                      }}
                      className="-my-1 grid h-6 w-6 place-items-center rounded-full text-risk-med-fg/60 hover:bg-risk-med-border hover:text-risk-med-fg"
                      aria-label={`Remove ${n}`}
                    >
                      <X size={12} />
                    </button>
                  </span>
                ))}
                {addingNoGo ? (
                  <span className="inline-flex items-center gap-1 rounded-full border border-risk-med-border bg-white py-0.5 pl-3 pr-1">
                    <input
                      autoFocus
                      value={noGoDraft}
                      onChange={(e) => setNoGoDraft(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") commitNoGo()
                        if (e.key === "Escape") {
                          setNoGoDraft("")
                          setAddingNoGo(false)
                          requestAnimationFrame(() => addNoGoRef.current?.focus())
                        }
                      }}
                      onBlur={commitNoGo}
                      placeholder="e.g. gambling promos…"
                      className="w-40 bg-transparent text-[12px] font-medium text-ink outline-none placeholder:text-ink-500"
                      aria-label="New brand-safety exclusion"
                    />
                    <button
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={commitNoGo}
                      className="grid h-6 w-6 place-items-center rounded-full bg-risk-med-bg text-risk-med-fg hover:bg-risk-med-border"
                      aria-label="Add exclusion"
                    >
                      <Plus size={13} />
                    </button>
                  </span>
                ) : (
                  <button
                    ref={addNoGoRef}
                    onClick={() => setAddingNoGo(true)}
                    className="inline-flex min-h-[28px] items-center gap-1 rounded-full border border-dashed border-border-strong px-2.5 py-1 text-[12px] font-medium text-ink-500 transition-colors duration-200 hover:border-brand-300 hover:text-brand"
                  >
                    <Plus size={13} /> Add
                  </button>
                )}
              </div>
              {noGo.length === 0 && !addingNoGo && (
                <p className="mt-1.5 text-[11px] text-ink-400">
                  Your call — add any content, claims, or verticals this brand won't be associated with.
                </p>
              )}
            </Field>
          </div>

          {/* ── Run depth & budget ── */}
          <div className="mt-5 rounded-2xl border border-border bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="text-[11px] font-semibold uppercase tracking-wide text-ink-400">
                Run depth &amp; budget
              </span>
              <span className="text-[11px] text-ink-400">
                priced from live actor rates · this first shortlist previews on fixtures
              </span>
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4" role="radiogroup" aria-label="Run depth">
              {[...plans.presets, null].map((p) => {
                const key = p?.key ?? "custom"
                const selected = planKey === key
                return (
                  <button
                    key={key}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    onClick={() => {
                      setPlanKey(key)
                      setCapEdited(null) // new depth -> recompute the default cap
                    }}
                    className={cn(
                      "rounded-xl border p-3 text-left transition-colors duration-200",
                      selected
                        ? "border-brand-300 bg-brand-50 ring-1 ring-brand-300"
                        : "border-border bg-white hover:border-brand-300",
                    )}
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-[13px] font-semibold text-ink">{p?.label ?? "Custom"}</span>
                      <span className="tnum text-[13px] font-bold text-brand">
                        ≈${p ? p.estUsd.toFixed(2) : estimateCustom(customCreators, customComments).toFixed(2)}
                      </span>
                    </div>
                    <div className="mt-0.5 text-[11px] text-ink-500">
                      {p ? `${p.maxCreators} creators · ${p.commentsPerCreator} comments each` : "set your own volumes"}
                    </div>
                  </button>
                )
              })}
            </div>

            {planKey === "custom" && (
              <div className="mt-3 flex flex-wrap items-end gap-4">
                <label className="text-[12px] font-medium text-ink-700">
                  Creators
                  <input
                    type="number" min={3} max={100} value={customCreators}
                    onChange={(e) => {
                      setCustomCreators(Math.max(3, Math.min(100, Number(e.target.value) || 3)))
                      setCapEdited(null)
                    }}
                    className="mt-1 block w-24 rounded-lg border border-border bg-surface px-2.5 py-1.5 text-[13px] text-ink focus:border-brand-300 focus:bg-white"
                  />
                </label>
                <label className="text-[12px] font-medium text-ink-700">
                  Comments / creator
                  <input
                    type="number" min={20} max={500} step={10} value={customComments}
                    onChange={(e) => {
                      setCustomComments(Math.max(20, Math.min(500, Number(e.target.value) || 20)))
                      setCapEdited(null)
                    }}
                    className="mt-1 block w-28 rounded-lg border border-border bg-surface px-2.5 py-1.5 text-[13px] text-ink focus:border-brand-300 focus:bg-white"
                  />
                </label>
              </div>
            )}

            <p className="mt-3 text-[12px] leading-relaxed text-ink-500">{planNote}</p>

            {/* Pre-run low-credit warning — only with a live backend + a real balance */}
            {credit?.apify.source === "none" ? (
              <div className="mt-3 flex items-start gap-2.5 rounded-lg border border-risk-high-border bg-risk-high-bg px-3.5 py-2.5">
                <AlertTriangle size={16} className="mt-0.5 shrink-0 text-risk-high-fg" />
                <p className="text-[12px] leading-relaxed text-ink-700">
                  <span className="font-semibold text-risk-high-fg">No live credit available.</span> A live run needs an
                  Apify key.{" "}
                  <Link to="/app/settings" className="font-medium text-brand hover:underline">
                    Add your own key in Settings
                  </Link>{" "}
                  — it stays in your browser. The demo still runs free.
                </p>
              </div>
            ) : runExceedsCredit(credit, plan.estUsd) ? (
              <div className="mt-3 flex items-start gap-2.5 rounded-lg border border-risk-med-border bg-risk-med-bg px-3.5 py-2.5">
                <AlertTriangle size={16} className="mt-0.5 shrink-0 text-risk-med-fg" />
                <p className="text-[12px] leading-relaxed text-ink-700">
                  <span className="font-semibold text-risk-med-fg">Heads up.</span> Run live, this depth's estimate (≈$
                  {plan.estUsd.toFixed(2)}) is more than the {credit?.apify.source === "shared" ? "shared " : ""}credit
                  left (≈${credit?.apify.remainingUsd?.toFixed(2)}). It would stop at the cap with a labeled partial
                  result.{" "}
                  <Link to="/app/settings" className="font-medium text-brand hover:underline">
                    Add your own key
                  </Link>{" "}
                  or pick a smaller depth.
                </p>
              </div>
            ) : null}

            <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-border pt-3 text-[12px] text-ink-700">
              <span className="font-medium">Hard cap</span>
              <span className="tnum">$</span>
              <input
                type="number" min={plan.estUsd} step={0.25} value={plan.capUsd}
                onChange={(e) => setCapEdited(Math.max(plan.estUsd, Number(e.target.value) || plan.estUsd))}
                aria-label="Hard budget cap in USD"
                className="w-20 rounded-lg border border-border bg-surface px-2 py-1 text-[13px] tnum text-ink focus:border-brand-300 focus:bg-white"
              />
              <span className="text-ink-500">
                — the sourcing loop stops <em>before</em> crossing it: a too-tight cap yields a labeled partial
                pull, never a surprise bill.
              </span>
            </div>
          </div>

          <div className="mt-5 flex items-center justify-between">
            <Button variant="ghost" onClick={() => setPhase("input")} leadingIcon={<ArrowLeft size={16} />}>
              Re-analyze
            </Button>
            <Button
              disabled={creating}
              onClick={async () => {
                if (creating) return
                setCreateError(null)
                setCreating(true)
                const brief: ClientBrief = {
                  brand: live?.brand ?? client.brand,
                  brandTh: live?.brandTh ?? client.brandTh,
                  category: live?.category ?? client.category,
                  audience,
                  pillars,
                  region,
                  website: url.trim() || client.website,
                  // Drives live creator search (falls back to category/pillars if empty).
                  searchTerms: searchTerms.length ? searchTerms : undefined,
                }
                try {
                  saveRunPlan(plan)
                  // Live backend: create an EMPTY shortlist and auto-start a real sourcing
                  // run. Brand-scored creators merge in through the run dock (~minutes) — we
                  // never seed a new brand with another brand's demo cohort or its fit scores.
                  if (apiBase()) {
                    const entry = await createEntry(brief, [], {
                      source: "fixtures",
                      screened: 0,
                      cost: { usd: 0, seconds: 0, cacheHitRate: 0 },
                      commenterOverlap: [],
                    })
                    const runPreset = plan.key === "custom" ? plans.defaultPreset : plan.key
                    const runId = await startRun(brief, runPreset)
                    if (runId) {
                      addRun({
                        id: runId,
                        shortlistId: entry.id,
                        brand: brief.brand,
                        preset: runPreset,
                        startedAt: Date.now(),
                        status: "running",
                      })
                    }
                    // Lands on the shortlist: it shows a "sourcing…" state while the run
                    // fills it, or an empty "Source creators" state if the run couldn't start.
                    navigate(`/app/s/${entry.id}`)
                    return
                  }
                  // Offline static demo (no backend): the labeled demo cohort stands in, via
                  // the pipeline animation which lands on the new shortlist's page.
                  const entry = await createEntry(brief, demoKols, {
                    source: "fixtures",
                    screened: demoSummary.screened,
                    cost: demoCost,
                    commenterOverlap: demoOverlap,
                  })
                  navigate(`/app/run?id=${entry.id}`)
                } catch {
                  setCreateError("Couldn't save the shortlist. Check your connection and try again.")
                  setCreating(false)
                }
              }}
              trailingIcon={creating ? <Loader2 size={16} className="animate-spin" /> : <ArrowRight size={16} />}
            >
              {creating ? "Saving…" : "Find matching KOLs"}
            </Button>
          </div>
          {createError && (
            <p role="alert" className="mt-3 text-right text-[12px] font-medium text-risk-high-fg">
              {createError}
            </p>
          )}
        </motion.div>
      )}
    </div>
  )
}
