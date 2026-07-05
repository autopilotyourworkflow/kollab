import { useEffect, useMemo, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { motion } from "motion/react"
import { Check, Loader2, ShieldAlert, Gauge, ArrowRight, Sparkles, XCircle, RotateCcw, Layers } from "lucide-react"
import { Button } from "../components/ui/Button"
import { client, summary, cost as demoCost } from "../data/kols"
import { getEntry, counts } from "../lib/workspace"
import { loadRunPlan } from "../lib/runPlan"
import { cn } from "../lib/cn"

interface Step {
  key: string
  label: string
  running: string
  done: string
  ms: number
  hero?: boolean
}

/** Step results interpolate from the same payload the shortlist renders — the
    simulation can never announce numbers the next screen contradicts. */
function buildSteps(screened: number, flagged: number, recommended: number, pillars: number): Step[] {
  return [
    { key: "brand", label: "Brand DNA", running: "Reading the brand brief", done: `${pillars} pillars · audience · no-go list`, ms: 700 },
    { key: "source", label: "Source candidates", running: "Querying Thai TikTok by category & hashtag", done: `${screened} creators found`, ms: 1300 },
    { key: "enrich", label: "Enrich profiles", running: "Reading recent videos, captions & engagement", done: `${screened} / ${screened} enriched`, ms: 1400 },
    { key: "vet", label: "Vet authenticity", running: "Comment pods · bought followers · view spikes", done: `${flagged} flagged for review`, ms: 1650, hero: true },
    { key: "match", label: "Match & score", running: "Embedding retrieve → LLM rerank on brand fit", done: "weighted · normalized", ms: 1300 },
    { key: "rank", label: "Rank & explain", running: "Writing grounded rationales (TH / EN)", done: `${recommended} recommended`, ms: 1150 },
  ]
}

function StatusDot({ status, hero }: { status: "pending" | "active" | "done" | "error"; hero?: boolean }) {
  // key={status} remounts on state change → each transition pops in (scale 0.6→1)
  const pop = {
    initial: { scale: 0.6, opacity: 0.6 },
    animate: { scale: 1, opacity: 1 },
    transition: { duration: 0.2, ease: [0.25, 1, 0.5, 1] as const },
  }
  if (status === "error")
    return (
      <motion.span key={status} {...pop} className="grid h-7 w-7 place-items-center rounded-full bg-risk-high text-white">
        <XCircle size={15} strokeWidth={2.5} />
      </motion.span>
    )
  if (status === "done")
    return (
      <motion.span
        key={status}
        {...pop}
        className={cn(
          "grid h-7 w-7 place-items-center rounded-full text-white",
          hero ? "bg-risk-high" : "bg-verified",
        )}
      >
        {hero ? <ShieldAlert size={15} strokeWidth={2.5} /> : <Check size={15} strokeWidth={3} />}
      </motion.span>
    )
  if (status === "active")
    return (
      <motion.span key={status} {...pop} className="grid h-7 w-7 place-items-center rounded-full border-2 border-brand bg-brand-50">
        <Loader2 size={14} className="animate-spin text-brand" />
      </motion.span>
    )
  return <span className="grid h-7 w-7 place-items-center rounded-full border-2 border-border bg-white" />
}

export function PipelineRun() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const id = searchParams.get("id") ?? ""
  const entry = getEntry(id)
  const c = entry ? counts(entry.kols) : { recommended: summary.recommended, flagged: summary.flagged }
  const brand = entry?.brief.brand ?? client.brand
  const screened = entry?.screened ?? summary.screened
  const recommended = c.recommended
  const flagged = c.flagged
  const pillarCount = (entry?.brief.pillars ?? client.pillars).length
  const steps = useMemo(
    () => buildSteps(screened, flagged, recommended, pillarCount),
    [screened, flagged, recommended, pillarCount],
  )
  const failMode = searchParams.get("fail") === "1"
  const failAt = 3 // the vet step
  const [index, setIndex] = useState(0)
  const [elapsed, setElapsed] = useState(0)
  const [errored, setErrored] = useState(false)
  const finished = index >= steps.length
  const totalSeconds = entry?.cost.seconds || demoCost.seconds || 1
  const plan = useMemo(loadRunPlan, []) // the depth chosen on the review step

  // advance steps
  useEffect(() => {
    if (errored) return
    if (finished) {
      const t = window.setTimeout(() => navigate(id ? `/app/s/${id}` : "/app"), 2600)
      return () => window.clearTimeout(t)
    }
    if (failMode && index === failAt) {
      const t = window.setTimeout(() => setErrored(true), steps[index].ms)
      return () => window.clearTimeout(t)
    }
    const t = window.setTimeout(() => setIndex((i) => i + 1), steps[index].ms)
    return () => window.clearTimeout(t)
  }, [index, finished, errored, failMode, navigate, steps, id])

  // live meter — tracks toward the pipeline's own projected cost/latency
  useEffect(() => {
    if (finished) {
      setElapsed(totalSeconds)
      return
    }
    if (errored) return
    const iv = window.setInterval(
      () => setElapsed((e) => +Math.min(e + 0.1, totalSeconds - 0.1).toFixed(1)),
      100,
    )
    return () => window.clearInterval(iv)
  }, [finished, errored, totalSeconds])

  const retry = () => {
    // the demo failure is triggered by ?fail=1 — clear it so the retry can succeed
    setSearchParams({}, { replace: true })
    setErrored(false)
    setIndex(0)
    setElapsed(0)
  }

  const cost = ((elapsed / totalSeconds) * (entry?.cost.usd ?? demoCost.usd)).toFixed(2)

  // announce progress to screen readers (visual state alone is not enough)
  const liveMessage = errored
    ? "The vetting step failed. You can retry or go back to the shortlist."
    : finished
      ? `Shortlist ready: ${recommended} recommended, ${flagged} flagged. Opening the shortlist.`
      : `${steps[index].label}: ${steps[index].running}`

  return (
    <div className="mx-auto max-w-2xl px-6 py-12">
      <div aria-live="polite" className="sr-only">
        {liveMessage}
      </div>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-[24px] font-bold tracking-[-0.02em] text-ink">
            Finding KOLs for {brand}
          </h1>
          <p className="mt-1.5 text-[14px] text-ink-500">
            Sourcing, vetting for fraud, and ranking Thai TikTok creators on brand fit.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2 rounded-full bg-brand-50 px-3 py-1.5">
          <Gauge size={14} className="text-brand" />
          <span className="tnum text-[12px] text-ink-700">
            <span className="font-bold text-brand">${cost}</span>
            <span className="mx-1.5 text-brand-100">·</span>
            {elapsed.toFixed(1)}s
          </span>
        </div>
      </div>

      {/* the depth the AM chose on the review step — what a LIVE run would buy */}
      <div className="mt-3 inline-flex flex-wrap items-center gap-x-2 gap-y-1 rounded-full bg-panel px-3 py-1.5 text-[12px] text-ink-700">
        <Layers size={13} className="shrink-0 text-ink-500" />
        <span>
          Planned live depth: <span className="font-semibold text-ink">{plan.label}</span>
          <span className="tnum"> · est ${plan.estUsd.toFixed(2)} · cap ${plan.capUsd.toFixed(2)}</span>
        </span>
        <span className="text-ink-400">— this demo run spends $0 (fixtures)</span>
      </div>

      <ol className="mt-9 rounded-2xl border border-border bg-white p-6 shadow-sm">
        {steps.map((s, i) => {
          const status = i < index ? "done" : i === index ? (errored ? "error" : "active") : "pending"
          const last = i === steps.length - 1
          return (
            <li key={s.key} className="flex gap-4">
              <div className="flex flex-col items-center">
                <StatusDot status={status} hero={s.hero} />
                {!last && (
                  <div
                    className={cn(
                      "my-1 w-0.5 flex-1 rounded-full transition-colors",
                      i < index ? "bg-verified/40" : "bg-border",
                    )}
                  />
                )}
              </div>
              <div className={cn("flex-1 pb-6", last && "pb-0")}>
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      "text-[15px] font-semibold",
                      status === "pending" ? "text-ink-500" : "text-ink",
                    )}
                  >
                    {s.label}
                  </span>
                  {status === "done" && s.hero && (
                    <span className="inline-flex items-center gap-1 rounded-full border border-risk-high-border bg-risk-high-bg px-2 py-0.5 text-[11px] font-medium text-risk-high-fg">
                      {flagged} flagged
                    </span>
                  )}
                </div>
                <p
                  className={cn(
                    "mt-0.5 text-[13px]",
                    status === "active" ? "text-brand" : "text-ink-500",
                  )}
                >
                  {status === "done" ? s.done : s.running}
                </p>
              </div>
            </li>
          )
        })}
      </ol>

      {/* escape hatch while the run is in flight — never trap the user */}
      {!finished && !errored && (
        <div className="mt-4 text-center">
          <Link
            to="/app"
            className="inline-flex min-h-[32px] items-center text-[12px] font-medium text-ink-500 transition-colors duration-200 hover:text-ink"
          >
            Cancel run and go back
          </Link>
        </div>
      )}

      {errored ? (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25, ease: [0.25, 1, 0.5, 1] }}
          className="mt-5 flex items-center justify-between gap-3 rounded-2xl border border-risk-high-border bg-risk-high-bg px-5 py-4">
          <div className="flex items-center gap-3">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-risk-high text-white">
              <XCircle size={17} />
            </span>
            <div>
              <div className="text-[14px] font-semibold text-ink">Vetting step failed</div>
              <div className="text-[12px] text-ink-700">
                The KOL data source timed out while checking authenticity. Nothing was charged for the incomplete run.
              </div>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Button variant="ghost" onClick={() => navigate("/app")}>
              Back
            </Button>
            <Button variant="secondary" onClick={retry} leadingIcon={<RotateCcw size={16} />}>
              Retry
            </Button>
          </div>
        </motion.div>
      ) : (
        finished && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, ease: [0.25, 1, 0.5, 1] }}
            className="mt-5 flex items-center justify-between rounded-2xl border border-verified-border bg-verified-bg px-5 py-4">
            <div className="flex items-center gap-3">
              <span className="grid h-9 w-9 place-items-center rounded-lg bg-verified text-white">
                <Sparkles size={17} />
              </span>
              <div>
                <div className="text-[14px] font-semibold text-ink">Shortlist ready</div>
                <div className="text-[12px] text-ink-700">
                  {recommended} recommended · {flagged} flagged · {elapsed.toFixed(1)}s · ${cost}
                </div>
              </div>
            </div>
            <Button onClick={() => navigate(id ? `/app/s/${id}` : "/app")} trailingIcon={<ArrowRight size={16} />}>
              View shortlist
            </Button>
          </motion.div>
        )
      )}
    </div>
  )
}
