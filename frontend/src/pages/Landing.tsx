import { Link } from "react-router-dom"
import { motion, useInView, useReducedMotion } from "motion/react"
import { useEffect, useRef, useState } from "react"
import type { ReactNode } from "react"
import { TintPill, StatCard, StatChip, Kicker } from "../components/ui/brand"
import ccLogo from "../assets/convertcake-logo.png"
import { kols, summary } from "../data/kols"
import { compact } from "../lib/format"
import type { Kol } from "../lib/types"
import {
  ArrowRight,
  ShieldAlert,
  ShieldCheck,
  ScrollText,
  Database,
  Timer,
  Users,
  Globe,
  Layers,
  SearchCheck,
  GitBranch,
  ListChecks,
} from "lucide-react"

/* Convert Cake's measured reveal: 0.5s cubic-bezier(.215,.61,.355,1), fade-up. */
const EASE_OUT_CUBIC = [0.215, 0.61, 0.355, 1] as const

/* Reveal enhances already-visible content: it fades up when scrolled into view,
   but a fallback timer guarantees visibility even where IntersectionObserver
   never fires (headless renderers, background tabs). Never gate content. */
function Reveal({ children, delay = 0, className }: { children: ReactNode; delay?: number; className?: string }) {
  const reduce = useReducedMotion()
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: "-60px" })
  const [forced, setForced] = useState(false)
  useEffect(() => {
    const t = setTimeout(() => setForced(true), 900)
    return () => clearTimeout(t)
  }, [])
  const shown = inView || forced || !!reduce
  return (
    <motion.div
      ref={ref}
      className={className}
      initial={{ opacity: 0, y: reduce ? 0 : 24 }}
      animate={shown ? { opacity: 1, y: 0 } : undefined}
      transition={{ duration: 0.5, delay, ease: EASE_OUT_CUBIC }}
    >
      {children}
    </motion.div>
  )
}

/* ── Hero product preview: the fraud-catch moment ─────────────────────────── */

/* Every number on the landing derives from the same committed pipeline payload
   the app renders (src/data/kols.ts) — the marketing can never disagree with
   the product. The three picks mirror the shortlist story: cleanest fit,
   mid-tier anchor, and the fraud catch. */
const pick = (id: string): Kol => kols.find((k) => k.id === id) ?? kols[0]
const heroTop = pick("k1")
const heroMid = pick("k5")
const heroFraud = pick("k4")

function PreviewRow({
  initials,
  hue,
  handle,
  meta,
  fit,
  state,
}: {
  initials: string
  hue: number
  handle: string
  meta: string
  fit: number
  state: "authentic" | "fraud"
}) {
  const fraud = state === "fraud"
  return (
    <div
      className={`flex items-center gap-3 rounded-lg px-3 py-2.5 ${
        fraud ? "bg-risk-high-bg ring-1 ring-risk-high-border" : "hover:bg-surface"
      }`}
    >
      <div
        className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-[12px] font-semibold"
        style={{ background: `hsl(${hue} 62% 93%)`, color: `hsl(${hue} 48% 34%)` }}
      >
        {initials}
      </div>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13px] font-semibold text-ink">{handle}</div>
        <div className="truncate text-[11px] text-ink-500">{meta}</div>
      </div>
      <span
        className={`inline-flex items-center gap-1 rounded-full border px-2 py-[3px] text-[11px] font-medium ${
          fraud
            ? "border-risk-high-border bg-white text-risk-high-fg"
            : "border-verified-border bg-verified-bg text-verified-fg"
        }`}
      >
        {fraud ? <ShieldAlert size={12} /> : <ShieldCheck size={12} />}
        {fraud ? "Comment pod" : "Authentic"}
      </span>
      <div className="flex w-16 items-center gap-2">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-border">
          <div className={`h-full rounded-full ${fraud ? "bg-risk-high" : "bg-brand"}`} style={{ width: `${fit}%` }} />
        </div>
        <span className="tnum w-6 text-right text-[12px] font-bold text-ink">{fit}</span>
      </div>
    </div>
  )
}

function ProductPreview() {
  return (
    <div className="relative pb-16">
      {/* faint outlined wireframe backdrop — their collage motif */}
      <div aria-hidden className="pointer-events-none absolute -inset-x-8 -top-8 bottom-4 -z-10">
        <div className="absolute right-0 top-0 h-56 w-72 rounded-2xl border border-brand-100" />
        <div className="absolute bottom-10 left-0 h-48 w-64 rounded-2xl border border-brand-100" />
        <div className="absolute left-24 top-16 h-px w-40 bg-brand-100" />
        <div className="absolute bottom-24 right-28 h-24 w-px bg-brand-100" />
      </div>

      <div className="w-full max-w-md rounded-2xl border border-border bg-white p-4 shadow-lg">
        <div className="mb-3 flex items-center justify-between px-1">
          <div className="flex items-center gap-2">
            <span className="grid h-6 w-6 place-items-center rounded bg-brand-50 text-[11px] font-bold text-brand">
              GL
            </span>
            <span className="text-[13px] font-semibold text-ink">Glow Lab · shortlist</span>
          </div>
          <span className="tnum rounded-full bg-panel px-2 py-0.5 text-[11px] font-medium text-ink-500">
            {summary.screened} screened
          </span>
        </div>
        <div className="space-y-1">
          {[heroTop, heroMid, heroFraud].map((k) => (
            <PreviewRow
              key={k.id}
              initials={k.avatar.initials}
              hue={k.avatar.hue}
              handle={k.handle}
              meta={`${k.tier} · ${compact(k.followers)} · ER ${k.engagementRate}%`}
              fit={k.fitScore}
              state={k.risk.level === "clear" ? "authentic" : "fraud"}
            />
          ))}
        </div>
      </div>

      {/* floating stat chips — their hero motif (never covering card text) */}
      <StatChip value={String(summary.flagged)} label="flagged for review" className="absolute left-1 top-[55%] hidden -translate-x-full shadow-md sm:inline-flex" />
      <StatChip value="≈15" label="min to shortlist" className="absolute -right-5 -top-5 hidden shadow-md sm:inline-flex" />

      {/* floating fraud callout */}
      <div className="absolute -bottom-2 left-1/2 flex w-[300px] -translate-x-1/2 items-start gap-2.5 rounded-xl border border-risk-high-border bg-white px-3.5 py-2.5 shadow-lg">
        <ShieldAlert size={16} className="mt-0.5 shrink-0 text-risk-high" />
        <p className="text-[12px] leading-snug text-ink-700">
          <span className="font-semibold text-ink">
            {compact(heroFraud.followers)} followers, {heroFraud.engagementRate}% engagement — and fake.
          </span>{" "}
          A follower-count tool would have recommended her. Kollab caught the comment pod.
        </p>
      </div>
    </div>
  )
}

/* ── Landing ──────────────────────────────────────────────────────────────── */

const features = [
  {
    icon: ShieldAlert,
    title: "Fraud, not followers",
    body: "Comment pods, bought followers, and view spikes — each flagged with the exact signal and the peer cohort it was measured against. The vanity metric never reaches the client.",
  },
  {
    icon: ScrollText,
    title: "Defensible by default",
    body: "Every rank cites a real data point, in Thai and English. Measured, inferred, and estimated are always labelled — so an account manager can screen-share the shortlist unedited.",
  },
  {
    icon: Database,
    title: "Native to your data",
    body: "The judgment layer on top of your licensed KOL feed, not another scraper. n8n keeps it re-vetting on a schedule, and it deploys in your own cloud.",
  },
]

const pipelineSteps = [
  { icon: Globe, label: "Brand DNA" },
  { icon: Layers, label: "Source" },
  { icon: Database, label: "Enrich" },
  { icon: SearchCheck, label: "Vet", hot: true },
  { icon: GitBranch, label: "Match" },
  { icon: ListChecks, label: "Rank" },
]

export function Landing() {
  const reduce = useReducedMotion()
  const [scrolled, setScrolled] = useState(false)
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    onScroll()
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [])
  const rise = (delay: number) => ({
    initial: { opacity: 0, y: reduce ? 0 : 20 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.5, delay, ease: EASE_OUT_CUBIC },
  })

  return (
    <div className="min-h-svh bg-white text-ink">
      {/* ── Nav — gains elevation once the page scrolls ── */}
      <header
        className={`sticky top-0 z-[10] border-b bg-white/90 backdrop-blur transition-[box-shadow,border-color] duration-300 ${
          scrolled ? "border-border shadow-sm" : "border-border/40"
        }`}
      >
        <nav className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3.5">
          <Link
            to="/"
            className="flex items-center gap-3 rounded-md transition-opacity duration-300 hover:opacity-80"
            title="Kollab home"
          >
            <img src={ccLogo} alt="Convert Cake" className="h-7 w-auto" />
            <span aria-hidden className="h-6 w-px bg-border" />
            <div className="leading-tight">
              <div className="text-[15px] font-bold text-ink">Kollab</div>
              <div className="text-[11px] text-ink-500">Internal Tools</div>
            </div>
          </Link>
          <div className="hidden items-center gap-7 text-[15px] font-medium text-ink-700 md:flex">
            <a href="#what" className="transition-colors duration-300 hover:text-brand">
              What it does
            </a>
            <a href="#how" className="transition-colors duration-300 hover:text-brand">
              How it works
            </a>
            <Link to="/design-system" className="transition-colors duration-300 hover:text-brand">
              Design system
            </Link>
          </div>
          <Link
            to="/app"
            className="group inline-flex min-h-[44px] items-center gap-2 rounded-lg bg-brand px-4 text-[15px] font-semibold text-white transition-[background-color,transform] duration-300 hover:bg-brand-hover active:scale-[0.98]"
          >
            Enter Kollab
            <ArrowRight size={16} className="transition-transform duration-300 group-hover:translate-x-0.5" />
          </Link>
        </nav>
      </header>

      {/* ── Hero ── */}
      <section className="relative overflow-hidden">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{ background: "radial-gradient(48% 42% at 82% 30%, rgba(230,236,253,0.8), transparent 70%)" }}
        />
        <div className="relative mx-auto grid max-w-7xl items-center gap-14 px-6 py-16 lg:grid-cols-[1.05fr_1fr] lg:py-24">
          <div className="min-w-0">
            <motion.div {...rise(0)}>
              <TintPill icon={<Users size={14} />}>Built for Convert Cake's influencer team</TintPill>
            </motion.div>

            <motion.h1
              {...rise(0.06)}
              className="mt-5 text-[clamp(2.1rem,5.2vw,3.4rem)] font-bold leading-[1.15] tracking-[-0.02em] text-balance text-ink"
            >
              See the fakes <span className="text-brand">before your client does.</span>
            </motion.h1>

            <motion.p {...rise(0.12)} className="mt-5 max-w-xl text-[16px] font-medium leading-relaxed text-ink-700">
              Kollab turns a client's brand into a defensible TikTok KOL shortlist — the brand-fit and
              fraud-vetting judgment layer that sits on top of your KOL data.
            </motion.p>

            <motion.ul {...rise(0.18)} className="mt-7 space-y-3">
              {[
                { icon: ShieldAlert, text: "Comment pods, bought followers, view spikes — caught with the receipts" },
                { icon: ScrollText, text: "Every rank cites a real data point, in English and Thai" },
                { icon: Timer, text: "Six to eight hours of manual vetting becomes about fifteen minutes" },
              ].map(({ icon: Icon, text }) => (
                <li key={text} className="flex items-start gap-3 text-[15px] font-medium text-ink">
                  <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-md bg-brand-50 text-brand">
                    <Icon size={14} strokeWidth={2.2} />
                  </span>
                  {text}
                </li>
              ))}
            </motion.ul>

            <motion.div {...rise(0.24)} className="mt-9 flex flex-wrap items-center gap-3">
              <Link
                to="/app"
                className="group inline-flex items-center gap-2 rounded-lg bg-brand px-6 py-3 text-[16px] font-semibold text-white shadow-sm transition-all duration-300 hover:bg-brand-hover hover:shadow-md active:scale-[0.98]"
              >
                Enter Kollab
                <ArrowRight size={17} className="transition-transform duration-300 group-hover:translate-x-0.5" />
              </Link>
              <a
                href="#how"
                className="inline-flex items-center gap-2 rounded-lg border border-border-strong px-6 py-3 text-[16px] font-medium text-ink-700 transition-colors duration-300 hover:border-brand-300 hover:text-brand"
              >
                See how it works
              </a>
            </motion.div>
          </div>

          <motion.div
            initial={{ opacity: 0, y: reduce ? 0 : 28 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.15, ease: EASE_OUT_CUBIC }}
            className="flex min-w-0 justify-center lg:justify-end"
          >
            <ProductPreview />
          </motion.div>
        </div>
      </section>

      {/* ── Stats band — their outlined stat cards ── */}
      <section className="mx-auto max-w-7xl px-6 pb-4 pt-2">
        <div className="grid gap-5 sm:grid-cols-3">
          <Reveal>
            <StatCard value={String(summary.screened)} label="KOLs screened per brief" />
          </Reveal>
          <Reveal delay={0.08}>
            <StatCard value="8" label="structural fraud signals" />
          </Reveal>
          <Reveal delay={0.16}>
            <StatCard value="15" unit="min" label="to a client-ready shortlist" />
          </Reveal>
        </div>
      </section>

      {/* ── Value props — left-margin kicker section ── */}
      <section id="what" className="mx-auto max-w-7xl px-6 py-20">
        <div className="grid gap-8 lg:grid-cols-[200px_1fr]">
          <Reveal>
            <Kicker>What Kollab does</Kicker>
          </Reveal>
          <div>
            <Reveal>
              <h2 className="max-w-2xl text-[clamp(1.7rem,3.2vw,2.5rem)] font-bold leading-[1.25] tracking-[-0.025em] text-balance text-ink">
                A shortlist an account manager can{" "}
                <span className="text-brand">defend to the client.</span>
              </h2>
              <p className="mt-3 max-w-2xl text-[16px] font-medium text-ink-500">
                The manual version takes most of a day and still can't prove a KOL is real. Kollab does the
                research and shows its work.
              </p>
            </Reveal>

            <div className="mt-10 grid gap-6 md:grid-cols-3">
              {features.map((f, i) => {
                const Icon = f.icon
                return (
                  <Reveal key={f.title} delay={i * 0.08}>
                    <div className="h-full rounded-2xl border border-border bg-white p-6 shadow-sm transition-shadow duration-300 hover:shadow-md">
                      <div className="mb-4 grid h-11 w-11 place-items-center rounded-full bg-brand-50 text-brand">
                        <Icon size={20} strokeWidth={2} />
                      </div>
                      <h3 className="text-[18px] font-semibold text-ink">{f.title}</h3>
                      <p className="mt-2 text-[14px] leading-relaxed text-ink-500">{f.body}</p>
                    </div>
                  </Reveal>
                )
              })}
            </div>
          </div>
        </div>
      </section>

      {/* ── Flow diagram — their signature pattern ── */}
      <section id="how" className="bg-surface">
        <div className="mx-auto max-w-7xl px-6 py-20">
          <div className="grid gap-8 lg:grid-cols-[200px_1fr]">
            <Reveal>
              <Kicker>How it works</Kicker>
            </Reveal>
            <div>
              <Reveal>
                <h2 className="max-w-2xl text-[clamp(1.7rem,3.2vw,2.5rem)] font-bold leading-[1.25] tracking-[-0.025em] text-balance text-ink">
                  Brand in. <span className="text-brand">Vetted shortlist out.</span>
                </h2>
              </Reveal>

              <Reveal delay={0.1}>
                <div className="mt-10 flex flex-col items-stretch gap-6 lg:flex-row lg:items-center">
                  {/* input */}
                  <div className="flex items-center gap-3 rounded-2xl border border-border bg-white px-5 py-4 shadow-sm lg:w-52">
                    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-brand-50 text-brand">
                      <Globe size={18} />
                    </span>
                    <div className="leading-tight">
                      <div className="text-[14px] font-semibold text-ink">Your client's brand</div>
                      <div className="text-[12px] text-ink-500">website → Brand DNA</div>
                    </div>
                  </div>

                  <div aria-hidden className="hidden h-px flex-1 bg-brand-100 lg:block" />
                  <div aria-hidden className="mx-auto h-6 w-px bg-brand-100 lg:hidden" />

                  {/* pipeline */}
                  <div className="rounded-2xl border-[1.5px] border-brand bg-white p-4 shadow-sm">
                    <div className="mb-2.5 px-1 text-[11px] font-semibold uppercase tracking-wide text-ink-500">
                      The Kollab pipeline
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {pipelineSteps.map(({ icon: Icon, label, hot }) => (
                        <span
                          key={label}
                          className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[13px] font-medium ${
                            hot
                              ? "border-risk-high-border bg-risk-high-bg text-risk-high-fg"
                              : "border-border bg-white text-ink-700"
                          }`}
                        >
                          <Icon size={14} />
                          {label}
                        </span>
                      ))}
                    </div>
                    <div className="mt-2.5 px-1 text-[12px] text-ink-500">
                      Vet is the hero: 8 structural fraud signals, graded against a peer cohort.
                    </div>
                  </div>

                  <div aria-hidden className="hidden h-px flex-1 bg-brand-100 lg:block" />
                  <div aria-hidden className="mx-auto h-6 w-px bg-brand-100 lg:hidden" />

                  {/* output */}
                  <div className="rounded-2xl border border-border bg-white px-5 py-4 shadow-sm lg:w-56">
                    <div className="text-[14px] font-semibold text-ink">Client-ready shortlist</div>
                    <div className="mt-2 flex items-center gap-2">
                      <span className="tnum rounded-md bg-brand-50 px-2 py-1 text-[13px] font-bold text-brand">{heroTop.fitScore}</span>
                      <span className="tnum rounded-md bg-brand-50 px-2 py-1 text-[13px] font-bold text-brand">{heroMid.fitScore}</span>
                      <span className="tnum rounded-md bg-risk-high-bg px-2 py-1 text-[13px] font-bold text-risk-high-fg">
                        {heroFraud.fitScore} ⚑
                      </span>
                      <span className="text-[12px] text-ink-500">ranked + flagged</span>
                    </div>
                  </div>
                </div>
              </Reveal>
            </div>
          </div>
        </div>
      </section>

      {/* ── CTA band ── */}
      <section className="mx-auto max-w-7xl px-6 py-20">
        <Reveal>
          <div className="rounded-3xl bg-brand-50 px-8 py-16 text-center">
            <h2 className="mx-auto max-w-2xl text-[clamp(1.7rem,3.4vw,2.6rem)] font-bold leading-[1.25] tracking-[-0.025em] text-balance text-ink">
              Ready to build a shortlist <span className="text-brand">you can stand behind?</span>
            </h2>
            <Link
              to="/app"
              className="group mt-8 inline-flex items-center gap-2 rounded-lg bg-brand px-7 py-3.5 text-[16px] font-semibold text-white shadow-sm transition-all duration-300 hover:bg-brand-hover hover:shadow-md active:scale-[0.98]"
            >
              Enter Kollab
              <ArrowRight size={17} className="transition-transform duration-300 group-hover:translate-x-0.5" />
            </Link>
          </div>
        </Reveal>
      </section>

      {/* ── Footer — their deep navy ── */}
      <footer className="bg-ink-900 text-white">
        <div className="mx-auto max-w-7xl px-6 py-12">
          <div className="flex flex-col justify-between gap-8 sm:flex-row sm:items-start">
            <div>
              <div className="flex items-center gap-2.5">
                <div className="grid h-9 w-9 place-items-center rounded-lg bg-white text-[16px] font-extrabold text-brand">
                  K
                </div>
                <div className="leading-tight">
                  <div className="text-[15px] font-bold">Kollab</div>
                  <div className="text-[11px] text-white/50">Internal Tools</div>
                </div>
              </div>
              <p className="mt-4 max-w-xs text-[13px] leading-relaxed text-white/60">
                KOL vetting, a piece of cake — fraud-screened, brand-fit, and ready to screen-share.
              </p>
              {/* the real mark, inverted for the navy footer */}
              <img
                src={ccLogo}
                alt="Convert Cake"
                className="mt-5 h-6 w-auto opacity-80 brightness-0 invert"
              />
            </div>
            <div className="flex items-center gap-6 text-[13px] text-white/60">
              <Link
                to="/tech"
                className="inline-flex min-h-[44px] items-center transition-colors duration-300 hover:text-white"
              >
                Engineering
              </Link>
              <Link
                to="/design-system"
                className="inline-flex min-h-[44px] items-center transition-colors duration-300 hover:text-white"
              >
                Design system
              </Link>
              <Link
                to="/app"
                className="inline-flex min-h-[44px] items-center transition-colors duration-300 hover:text-white"
              >
                Open the tool
              </Link>
            </div>
          </div>
          <div className="mt-10 flex flex-col items-start justify-between gap-2 border-t border-white/10 pt-6 text-[12px] text-white/40 sm:flex-row">
            <span>An internal tool concept for Convert Cake · Kollab</span>
            <span>Built by Beam</span>
          </div>
        </div>
      </footer>
    </div>
  )
}
