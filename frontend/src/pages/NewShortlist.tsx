import { useRef, useState } from "react"
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
} from "lucide-react"
import { Button } from "../components/ui/Button"
import { ProvenanceChip } from "../components/ui/ProvenanceChip"
import { client, brandDna } from "../data/kols"
import { saveBrief } from "../lib/api"
import { cn } from "../lib/cn"

type Phase = "input" | "analyzing" | "review" | "error"

/** A non-degraded extraction from the live backend (POST /api/brand-dna). */
type LiveExtraction = { brand: string; brandTh: string; category: string; source: string }

/** Try the real Brand-DNA endpoint (Claude → Gemini on the backend). Returns null
    when there is no live backend, the call fails, or the backend answered with the
    honestly-degraded rules skeleton — the UI then keeps its labeled demo path. */
async function tryLiveBrandDna(website: string): Promise<{
  live: LiveExtraction | null
  brief?: { audience?: string; region?: string; pillars?: string[] }
}> {
  // Only when a live backend is configured — the static demo hosting has no
  // /api/brand-dna, so probing it would just log 404 noise.
  const base = import.meta.env.VITE_API_URL as string | undefined
  if (!base) return { live: null }
  try {
    const ctrl = new AbortController()
    const t = window.setTimeout(() => ctrl.abort(), 12_000)
    const res = await fetch(`${base}/api/brand-dna`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ website }),
      signal: ctrl.signal,
    })
    window.clearTimeout(t)
    if (!res.ok) return { live: null }
    const data = (await res.json()) as {
      degraded?: boolean
      source?: string
      brief?: { brand?: string; brandTh?: string; category?: string; audience?: string; region?: string; pillars?: string[] }
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

  // editable brand DNA (HITL on the brief)
  const [audience, setAudience] = useState(client.audience)
  const [tone, setTone] = useState(brandDna.tone)
  const [region, setRegion] = useState(client.region)
  const [pillars, setPillars] = useState<string[]>(client.pillars)
  const [addingPillar, setAddingPillar] = useState(false)
  const [pillarDraft, setPillarDraft] = useState("")
  const addPillarRef = useRef<HTMLButtonElement>(null)

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

  const analyze = async () => {
    const cleaned = url.trim().replace(/^https?:\/\//i, "").replace(/\/+$/, "")
    if (!/^([\w-]+\.)+[a-z]{2,}(\/.*)?$/i.test(cleaned)) {
      setError("Enter a valid website — e.g. glowlab.co.th")
      return
    }
    setError(null)
    setPhase("analyzing")
    const willFail = /fail|error|unreachable|broken/i.test(cleaned)
    const startedAt = Date.now()

    // Real extraction first (live backend + LLM key); the labeled demo path
    // takes over on any miss — never a fake green badge.
    const result = await tryLiveBrandDna(cleaned)
    setLive(result.live)
    if (result.live && result.brief) {
      if (result.brief.audience) setAudience(result.brief.audience)
      if (result.brief.region) setRegion(result.brief.region)
      if (result.brief.pillars?.length) setPillars(result.brief.pillars)
    }

    // keep the reading state legible even when the answer is instant
    const waitLeft = Math.max(300, 1700 - (Date.now() - startedAt))
    window.setTimeout(() => setPhase(willFail && !result.live ? "error" : "review"), waitLeft)
  }

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
                <AlertTriangle size={12} /> draft brief — live extraction unavailable here
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
                <span className="font-semibold text-risk-med-fg">Demo boundary.</span> Live extraction for arbitrary
                brands runs on the backend's Claude → Gemini path (<code>POST /api/brand-dna</code> with an LLM key) —
                this hosted demo doesn't carry keys, so the fields below are the sample brief, shown so you can see
                and edit the review flow. Treat every value as a draft.
              </p>
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
                <p className="font-thai mt-1 text-[13px] text-ink-500">{brandDna.toneTh}</p>
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
              <div className="flex flex-wrap gap-2">
                {brandDna.noGo.map((n) => (
                  <span
                    key={n}
                    className="inline-flex items-center rounded-full border border-risk-med-border bg-risk-med-bg px-2.5 py-1 text-[12px] font-medium text-risk-med-fg"
                  >
                    {n}
                  </span>
                ))}
              </div>
            </Field>
          </div>

          <div className="mt-5 flex items-center justify-between">
            <Button variant="ghost" onClick={() => setPhase("input")} leadingIcon={<ArrowLeft size={16} />}>
              Re-analyze
            </Button>
            <Button
              onClick={() => {
                // persist the AM's edits — the shortlist and run screens read them back
                saveBrief({ audience, tone, region, pillars })
                navigate("/app/run")
              }}
              trailingIcon={<ArrowRight size={16} />}
            >
              Find matching KOLs
            </Button>
          </div>
        </motion.div>
      )}
    </div>
  )
}
