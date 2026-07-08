import { Link } from "react-router-dom"
import {
  ArrowRight,
  ChevronRight,
  ChevronDown,
  Layers,
  ShieldCheck,
  SearchCheck,
  Database,
  Lock,
  FlaskConical,
  Cloud,
  ListChecks,
  GitBranch,
  ExternalLink,
  LifeBuoy,
  Scale,
  Boxes,
} from "lucide-react"
import { Button } from "../components/ui/Button"
import { TintPill } from "../components/ui/brand"
import ccLogo from "../assets/convertcake-logo.png"

/** /tech — the engineering & architecture reference, written for a technical
 *  reviewer. It complements the in-app operating Guide (/app/guide, copy-as-
 *  Markdown): the Guide is the deep product reference; this page is the system
 *  view — stack, data flow, the honesty-by-construction decisions, and the
 *  fraud engine's auditable thresholds. The numbers here trace directly to the
 *  shipping code (backend/app/fraud/signals.py, matching/score.py, the test suite)
 *  and are checked against it at each release. */

const LIVE_URL = "https://kollab-64c.pages.dev"

/* ── The pipeline, as the architecture diagram (Convert Cake's outlined-box +
      connector "flow" signature, mapped Brand → pipeline → shortlist). ─────── */
interface Stage {
  label: string
  sub: string
  note?: string
  tone?: "in" | "out"
  hero?: boolean
}
const STAGES: Stage[] = [
  { label: "Client website", sub: "URL in", tone: "in" },
  { label: "Brand DNA", sub: "Claude → Gemini → rules", note: "keys optional" },
  { label: "Sourcing", sub: "KOLSource adapter", note: "Seed · Apify · licensed" },
  { label: "Enrich", sub: "profile · videos · comments" },
  { label: "Fraud vet", sub: "cohorts · structural signals", note: "n ≥ 15 gate", hero: true },
  { label: "Match", sub: "deterministic → LLM rerank", note: "citation-validated" },
  { label: "Rank", sub: "fit-sorted", note: "camelCase contract", tone: "out" },
]

function FlowDiagram() {
  return (
    <div className="rounded-2xl border border-border bg-white p-5 shadow-sm sm:p-6">
      {/* Mobile: vertical stack with down-connectors. md+: horizontal, scrolls if tight. */}
      <div className="flex flex-col gap-0 md:flex-row md:items-stretch md:gap-0 md:overflow-x-auto md:pb-1">
        {STAGES.map((s, i) => (
          <div key={s.label} className="flex flex-col md:flex-row md:items-center">
            <div
              className={
                "relative flex min-w-0 flex-col justify-center rounded-xl border px-3.5 py-3 md:min-w-[132px] " +
                (s.hero
                  ? "border-[1.5px] border-brand bg-brand-50/60"
                  : s.tone
                    ? "border-border-strong bg-surface"
                    : "border-border bg-white")
              }
            >
              <div
                className={
                  "text-[13px] font-semibold leading-tight " + (s.hero ? "text-brand" : "text-ink")
                }
              >
                {s.label}
              </div>
              <div className="mt-0.5 text-[11px] leading-tight text-ink-500">{s.sub}</div>
              {s.note && (
                <div className="mt-1.5 inline-flex w-fit rounded-full bg-panel px-1.5 py-px text-[10px] font-medium text-ink-700">
                  {s.note}
                </div>
              )}
            </div>
            {i < STAGES.length - 1 && (
              <div className="flex shrink-0 items-center justify-center text-ink-400 md:px-1.5">
                <ChevronDown size={16} className="my-0.5 md:hidden" aria-hidden />
                <ChevronRight size={16} className="hidden md:block" aria-hidden />
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-border pt-3 text-[12px] text-ink-500">
        <ArrowRight size={13} className="text-brand" aria-hidden />
        <span>
          The result is a <span className="font-medium text-ink-700">ShortlistResponse</span> the React SPA
          renders verbatim — every count, badge, and rationale on screen derives from that one payload.
        </span>
      </div>
    </div>
  )
}

/* ── The stack (layer · choice · why — the "why" is where the judgment is). ── */
const STACK: { layer: string; choice: string; why: string }[] = [
  {
    layer: "Frontend",
    choice: "Vite · React 19 · TypeScript · Tailwind v4",
    why: "A single-page app on Cloudflare Pages. One design system (Convert Cake's measured CI) across landing, tool, and docs.",
  },
  {
    layer: "Backend",
    choice: "Python · FastAPI · Pydantic v2",
    why: "Typed request/response contracts that serialize straight to the wire. Async run endpoints for background sourcing.",
  },
  {
    layer: "Statistics",
    choice: "Python stdlib (no numpy)",
    why: "Median, IQR, quantiles, Tukey fences — the math here doesn't need numpy, and skipping it keeps the install light and portable.",
  },
  {
    layer: "Data contract",
    choice: "One Pydantic model → camelCase JSON",
    why: "schemas.py is mirrored 1:1 by frontend/src/lib/types.ts. Python stays snake_case; the wire is camelCase; neither end owns an adapter.",
  },
  {
    layer: "LLM",
    choice: "Claude (primary) · Gemini (fallback)",
    why: "LLM-optional by design. Brand DNA + a citation-validated rerank use it; with zero keys, deterministic scoring still runs and every path degrades to a labelled result.",
  },
  {
    layer: "Auth",
    choice: "stdlib scrypt · HMAC-signed session tokens",
    why: "No heavyweight auth dependency. Passwords hashed with scrypt; sessions are HMAC-signed tokens the server verifies statelessly.",
  },
  {
    layer: "Database",
    choice: "Neon Postgres · SQLAlchemy",
    why: "Backs the durable state (workspace, runs, commenter graph, ledger). All DB imports are lazy, so the credential-free demo needs none of them.",
  },
  {
    layer: "Deploy",
    choice: "Cloudflare Pages · Render · Neon",
    why: "Static SPA + a Pages Function on Cloudflare; the FastAPI service on Render (one-click render.yaml); Postgres on Neon.",
  },
  {
    layer: "Testing",
    choice: "pytest — 271 hermetic tests",
    why: "Synthetic data + injected fake clients. Zero network, runs in seconds, deterministic by construction.",
  },
]

/* ── Engineering principles — the decisions that show judgment, not features. ─ */
const PRINCIPLES: { icon: typeof ShieldCheck; title: string; body: string }[] = [
  {
    icon: ShieldCheck,
    title: "Degrade honestly, never fabricate",
    body: "An unavailable live path answers a clear 4xx/503 with the reason, or a clearly-labelled deterministic fallback — never an invented result. Anything that depends on data the user hasn't logged (outcomes, prices) shows an explicit learning state until they log it.",
  },
  {
    icon: FlaskConical,
    title: "Deterministic in fixtures mode",
    body: "Per-handle seeded RNG plus the dataset's own as_of date as “now” — no Date.now(), no live randomness. That's what makes the 271-test suite meaningful and the demo byte-reproducible on every run.",
  },
  {
    icon: Database,
    title: "One contract, both ends",
    body: "A single Pydantic model serialized to camelCase is mirrored exactly by the frontend TypeScript types. The bundled demo fallback imports the same committed payload the API serves, so fallback and live are byte-identical by construction.",
  },
  {
    icon: SearchCheck,
    title: "Withhold below the sample size",
    body: "An outlier signal fires only when its peer cohort has n ≥ 15; view-to-follower withholds below 5 sampled videos. Below the gate the badge reads “insufficient baseline — signal withheld”. Absence of data is never asserted as fraud.",
  },
  {
    icon: Scale,
    title: "Every threshold is an auditable constant",
    body: "No black-box score. Each fraud threshold is a named, documented, retunable module constant a reviewer or a Thai account manager can read and change — and the LLM rerank may only cite enumerated data points, checked by a post-hoc validator that rejects any uncited claim.",
  },
]

/* ── The fraud engine — thresholds read straight from app/fraud/signals.py. ─── */
const DETECTORS: { signal: string; catches: string; fires: string; sev: "high" | "medium" }[] = [
  {
    signal: "Cross-creator commenter reuse",
    catches: "Comment pods (the lead signal)",
    fires: "≥ 20 shared accounts each hitting ≥ 3 unrelated creators, and ≥ 15% of this creator's comments",
    sev: "high",
  },
  {
    signal: "Comment-burst timing",
    catches: "Bot drops",
    fires: "≥ 25 comments inside a 120-second window on one video",
    sev: "high",
  },
  {
    signal: "Templated comment text",
    catches: "Copy-paste pod comments",
    fires: "Near-duplicates (repeated ≥ 3×) make up ≥ 30% of the sample",
    sev: "medium",
  },
  {
    signal: "Thin commenter profiles",
    catches: "Bought audiences",
    fires: "≥ 50% of a ≥ 20-profile sample have < 5 posts or no Thai history",
    sev: "high",
  },
  {
    signal: "View-to-follower collapse",
    catches: "Bought followers",
    fires: "Below a 5% absolute floor, or < 25% of the peer-median ratio · withheld below 5 videos",
    sev: "high",
  },
  {
    signal: "Self-baseline view spike",
    catches: "Boosted posts priced as organic",
    fires: "≥ 4× the creator's own trailing median (self-outliers excluded); ≥ 2× flags “possible boosted”",
    sev: "high",
  },
  {
    signal: "Engagement-rate outlier",
    catches: "Suspiciously hot engagement",
    fires: "Above the cohort's Tukey fence (p75 + 1.5 × IQR) · withheld below n = 15 peers",
    sev: "medium",
  },
  {
    signal: "Cadence / dormancy",
    catches: "Stalled creators",
    fires: "Last post more than 14 days ago (a cadence concern, not fraud)",
    sev: "medium",
  },
]

/* ── What's durable vs what lives in the browser. ───────────────────────────── */
const DURABLE = [
  "The authenticated workspace — accounts, their shortlists, and approve/reject decisions (per user, in API mode)",
  "The persistent cross-run commenter graph (commenter → creator edges) — fraud recall improves every run",
  "Async sourcing runs, so a run survives a refresh or the free instance sleeping",
  "The delivery-outcome ledger that feeds the bounded re-rank nudge",
]
const BROWSER = [
  "In local mode (no backend), the whole workspace runs offline in browser storage so the demo never dead-ends",
  "The saved brief, the selected run depth, and your CPM assumption",
  "Bring-your-own API keys — kept in local storage, sent per-request as headers, never stored on the server, logged, or returned",
]

const BUILT = [
  "Structural-first fraud vetting with cohort math, the n ≥ 15 rule, and Thai-lexicon pod corroboration",
  "Persistent cross-run commenter graph (Neon-backed; in-memory for the demo)",
  "Delivered-post re-audit · closed-loop delivery ledger · fraud-adjusted fair-rate estimator",
  "Commenter-overlap dedup · transparent brand-safety scan · citation-validated outreach draft",
  "Authenticated Neon workspace (scrypt + HMAC), with a no-backend local fallback",
  "Budget-capped Apify sourcing loop · Brand DNA chain · citation-validated LLM rerank",
  "Run-depth selector with live cost estimates · internal vetting-report export · eval harness",
  "Scheduled re-vet sweep — self-contained GitHub Actions cron + manual dispatch (also importable into n8n)",
]
const ROADMAP = [
  "A first live calibration run against the real actors + a recorded live-extraction demo",
  "Embeddings / pgvector retrieval for recall at licensed-feed scale",
  "A native deal-pipeline board (outreach → booked → delivered)",
  "Surfacing the computed-confidence functions in the API contract and UI",
  "A learned rate/outcome model from accumulated agency deal history",
  "Thai-native validation of the taboo and pod lexicons",
]

/* ── Section scaffold ───────────────────────────────────────────────────────── */
interface SectionDef {
  id: string
  n: string
  title: string
  icon: typeof Layers
}
const SECTIONS: SectionDef[] = [
  { id: "flow", n: "01", title: "System at a glance", icon: GitBranch },
  { id: "stack", n: "02", title: "The stack", icon: Layers },
  { id: "principles", n: "03", title: "Engineering principles", icon: ShieldCheck },
  { id: "fraud", n: "04", title: "The fraud engine", icon: SearchCheck },
  { id: "contract", n: "05", title: "One data contract", icon: Boxes },
  { id: "persistence", n: "06", title: "Persistence, auth & security", icon: Lock },
  { id: "testing", n: "07", title: "Testing & quality", icon: FlaskConical },
  { id: "deploy", n: "08", title: "Deployment topology", icon: Cloud },
  { id: "roadmap", n: "09", title: "Built vs roadmap", icon: ListChecks },
]

function SectionHeader({ id, title, icon: Icon }: { id: string; title: string; icon: typeof Layers }) {
  return (
    <h2 id={id} className="flex scroll-mt-20 items-center gap-2.5 text-[20px] font-semibold text-ink">
      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand">
        <Icon size={17} />
      </span>
      {title}
    </h2>
  )
}

function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={"rounded-2xl border border-border bg-white p-6 shadow-sm " + (className ?? "")}>
      {children}
    </div>
  )
}

export function Tech() {
  return (
    <div className="min-h-svh bg-surface">
      {/* ── Sticky header ── */}
      <header className="sticky top-0 z-[10] border-b border-border bg-white/85 backdrop-blur-sm">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3">
          <Link
            to="/"
            title="Back to the Kollab landing page"
            className="flex items-center gap-2.5 rounded-md transition-opacity duration-300 hover:opacity-80"
          >
            <img src={ccLogo} alt="Convert Cake" className="h-6 w-auto" />
            <span className="text-[15px] font-semibold text-ink">Kollab</span>
            <span className="text-ink-400">·</span>
            <span className="text-[15px] text-ink-500">Engineering</span>
          </Link>
          <nav className="flex items-center gap-1.5">
            <Link to="/app">
              <Button size="sm" variant="ghost">
                Open the tool
              </Button>
            </Link>
            <a href={LIVE_URL} target="_blank" rel="noreferrer" className="hidden sm:block">
              <Button size="sm" variant="secondary" trailingIcon={<ExternalLink size={14} />}>
                Live demo
              </Button>
            </a>
          </nav>
        </div>
      </header>

      {/* ── Navy hero (their deep-navy dark section) ── */}
      <section className="bg-ink-900 text-white">
        <div className="mx-auto max-w-5xl px-6 py-14 sm:py-16">
          <TintPill className="bg-white/10 text-brand-300">
            <GitBranch size={14} /> Engineering & architecture
          </TintPill>
          <h1 className="mt-5 max-w-3xl text-[34px] font-bold leading-[1.1] tracking-[-0.02em] sm:text-[42px]">
            How Kollab is <span className="text-brand-300">built</span>
          </h1>
          <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-white/70">
            A judgment layer on top of KOL data — not a scraper, not a database. It computes deterministically,
            degrades honestly, and never fabricates a number. This page is the system view: the stack, the data
            flow, the engineering decisions, and the fraud engine's auditable thresholds.
          </p>
          <div className="mt-7 flex flex-wrap gap-2">
            {[
              "271 tests, all green",
              "FastAPI · React 19 · Neon",
              "LLM-optional by design",
              "Live in < 60s",
            ].map((f) => (
              <span
                key={f}
                className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-[12.5px] font-medium text-white/85"
              >
                <span className="h-1.5 w-1.5 rounded-full bg-brand-300" aria-hidden />
                {f}
              </span>
            ))}
          </div>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <a href={LIVE_URL} target="_blank" rel="noreferrer">
              <Button trailingIcon={<ExternalLink size={15} />}>Open the live demo</Button>
            </a>
            <Link to="/app/guide">
              <Button variant="secondary" leadingIcon={<LifeBuoy size={15} />}>
                Operating guide
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* ── Body ── */}
      <div className="mx-auto max-w-5xl px-6 py-12 sm:py-14">
        {/* Contents */}
        <nav aria-label="Contents" className="mb-10 rounded-2xl border border-border bg-white p-5 shadow-sm">
          <div className="mb-3 text-[12px] font-semibold uppercase tracking-wide text-ink-400">Contents</div>
          <ol className="grid gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
            {SECTIONS.map((s) => (
              <li key={s.id}>
                <a
                  href={`#${s.id}`}
                  className="group flex items-center gap-2.5 text-[13px] text-ink-700 transition-colors hover:text-brand"
                >
                  <span className="tnum text-[11px] font-semibold text-ink-400 group-hover:text-brand">
                    {s.n}
                  </span>
                  {s.title}
                </a>
              </li>
            ))}
          </ol>
        </nav>

        <div className="space-y-12">
          {/* 01 · System at a glance */}
          <section className="space-y-4">
            <SectionHeader id="flow" title="System at a glance" icon={GitBranch} />
            <p className="max-w-2xl text-[14px] leading-relaxed text-ink-600">
              A 7-step pipeline. Everything downstream of sourcing depends on Kollab's own boundary model, never
              on a vendor's JSON — so swapping the public-data scraper for a licensed feed is a new adapter, not
              a rewrite.
            </p>
            <FlowDiagram />
          </section>

          {/* 02 · The stack */}
          <section className="space-y-4">
            <SectionHeader id="stack" title="The stack" icon={Layers} />
            <Card className="!p-0">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] border-collapse text-left">
                  <thead>
                    <tr className="border-b border-border text-[11px] font-semibold uppercase tracking-wide text-ink-400">
                      <th className="px-5 py-3">Layer</th>
                      <th className="px-5 py-3">Choice</th>
                      <th className="px-5 py-3">Why</th>
                    </tr>
                  </thead>
                  <tbody>
                    {STACK.map((r) => (
                      <tr key={r.layer} className="border-b border-border/70 last:border-0 align-top">
                        <td className="whitespace-nowrap px-5 py-3.5 text-[13px] font-semibold text-ink">
                          {r.layer}
                        </td>
                        <td className="px-5 py-3.5 text-[13px] font-medium text-brand">{r.choice}</td>
                        <td className="px-5 py-3.5 text-[13px] leading-relaxed text-ink-600">{r.why}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </section>

          {/* 03 · Engineering principles */}
          <section className="space-y-4">
            <SectionHeader id="principles" title="Engineering principles" icon={ShieldCheck} />
            <p className="max-w-2xl text-[14px] leading-relaxed text-ink-600">
              The decisions worth calling out are about trust, not features. Each one is a checkable invariant a
              reviewer can hold the code to.
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              {PRINCIPLES.map((p, i) => (
                <Card
                  key={p.title}
                  className={"!p-5 " + (i === PRINCIPLES.length - 1 && PRINCIPLES.length % 2 === 1 ? "sm:col-span-2" : "")}
                >
                  <div className="flex items-center gap-2.5">
                    <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand">
                      <p.icon size={15} />
                    </span>
                    <h3 className="text-[14.5px] font-semibold text-ink">{p.title}</h3>
                  </div>
                  <p className="mt-2.5 text-[13px] leading-relaxed text-ink-600">{p.body}</p>
                </Card>
              ))}
            </div>
          </section>

          {/* 04 · The fraud engine */}
          <section className="space-y-4">
            <SectionHeader id="fraud" title="The fraud engine" icon={SearchCheck} />
            <p className="max-w-2xl text-[14px] leading-relaxed text-ink-600">
              The differentiator is depth here, not breadth everywhere. Structural detectors lead — cross-account
              reuse and burst timing are expensive for a pod farm to fake and cheap to measure; a phrase lexicon
              is trivially rotated, so it only ever corroborates an already-fired badge. Every threshold below is
              a named constant in{" "}
              <code className="rounded bg-panel px-1 py-0.5 text-[12px] text-ink-700">app/fraud/signals.py</code>.
            </p>
            <Card className="!p-0">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] border-collapse text-left">
                  <thead>
                    <tr className="border-b border-border text-[11px] font-semibold uppercase tracking-wide text-ink-400">
                      <th className="px-5 py-3">Signal</th>
                      <th className="px-5 py-3">Catches</th>
                      <th className="px-5 py-3">Fires when</th>
                      <th className="px-5 py-3 text-right">Severity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {DETECTORS.map((d) => (
                      <tr key={d.signal} className="border-b border-border/70 last:border-0 align-top">
                        <td className="whitespace-nowrap px-5 py-3.5 text-[13px] font-semibold text-ink">
                          {d.signal}
                        </td>
                        <td className="whitespace-nowrap px-5 py-3.5 text-[13px] text-ink-600">{d.catches}</td>
                        <td className="px-5 py-3.5 text-[13px] leading-relaxed text-ink-600">{d.fires}</td>
                        <td className="px-5 py-3.5 text-right">
                          <span
                            className={
                              "inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold " +
                              (d.sev === "high"
                                ? "bg-risk-high-bg text-risk-high-fg"
                                : "bg-risk-med-bg text-risk-med-fg")
                            }
                          >
                            {d.sev}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
            <div className="rounded-2xl border border-brand-100 bg-brand-50/50 p-5 text-[13px] leading-relaxed text-ink-700">
              <span className="font-semibold text-ink">It flags for a human — it never auto-clears or
              auto-kills.</span>{" "}
              Signals fold into a per-creator authenticity score (0–100) and a Risk level; the pod family (reuse
              + burst + templated text) collapses into a single “Comment pod” badge led by the strongest
              structural signal. What Kollab cannot detect — true demographics, bot-at-scale that mimics organic
              timing, private analytics — is stated plainly. That limit is why every flag routes to review.
            </div>
          </section>

          {/* 05 · One data contract */}
          <section className="space-y-4">
            <SectionHeader id="contract" title="One data contract" icon={Boxes} />
            <div className="grid gap-3 md:grid-cols-5">
              <Card className="!p-5 md:col-span-3">
                <p className="text-[13px] leading-relaxed text-ink-600">
                  The ingestion boundary (<code className="rounded bg-panel px-1 py-0.5 text-[12px] text-ink-700">RawKOL</code>)
                  is the only place a vendor's field names appear. Every downstream layer — fraud, matching,
                  pricing — depends on Kollab's own model. The output is a single Pydantic model with a{" "}
                  <code className="rounded bg-panel px-1 py-0.5 text-[12px] text-ink-700">to_camel</code> alias
                  generator, mirrored field-for-field by the frontend TypeScript types. Python stays snake_case,
                  the wire is camelCase, and neither end maintains a translation layer.
                </p>
              </Card>
              <Card className="!p-5 md:col-span-2">
                <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-ink-400">
                  One source of truth
                </div>
                <div className="space-y-1.5 font-mono text-[12px] leading-relaxed text-ink-700">
                  <div>
                    <span className="text-ink-400">py </span>
                    <span className="text-ink">median_views</span>
                  </div>
                  <div className="pl-4 text-ink-400">↓ to_camel</div>
                  <div>
                    <span className="text-ink-400">ts </span>
                    <span className="text-brand">medianViews</span>
                  </div>
                </div>
              </Card>
            </div>
          </section>

          {/* 06 · Persistence, auth & security */}
          <section className="space-y-4">
            <SectionHeader id="persistence" title="Persistence, auth & security" icon={Lock} />
            <div className="grid gap-3 md:grid-cols-2">
              <Card className="!p-5">
                <div className="mb-3 flex items-center gap-2 text-[13px] font-semibold text-ink">
                  <Database size={15} className="text-brand" /> Durable in Neon Postgres
                </div>
                <ul className="space-y-2">
                  {DURABLE.map((d) => (
                    <li key={d} className="flex gap-2.5 text-[13px] leading-relaxed text-ink-600">
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" aria-hidden />
                      <span>{d}</span>
                    </li>
                  ))}
                </ul>
              </Card>
              <Card className="!p-5">
                <div className="mb-3 flex items-center gap-2 text-[13px] font-semibold text-ink">
                  <Boxes size={15} className="text-ink-500" /> In the browser
                </div>
                <ul className="space-y-2">
                  {BROWSER.map((d) => (
                    <li key={d} className="flex gap-2.5 text-[13px] leading-relaxed text-ink-600">
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-ink-400" aria-hidden />
                      <span>{d}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            </div>
            <div className="rounded-2xl border border-brand-100 bg-brand-50/50 p-5 text-[13px] leading-relaxed text-ink-700">
              <span className="font-semibold text-ink">Auth without heavy dependencies.</span> Passwords are
              hashed with stdlib scrypt; a session is an HMAC-signed token the server verifies statelessly (no
              server-side session store). In API mode the workspace is auth-gated with a one-click guest option;
              with no backend configured it drops to the offline local demo, so the app never dead-ends.
            </div>
          </section>

          {/* 07 · Testing & quality */}
          <section className="space-y-4">
            <SectionHeader id="testing" title="Testing & quality" icon={FlaskConical} />
            <div className="grid gap-3 sm:grid-cols-3">
              {[
                { v: "271", l: "hermetic backend tests" },
                { v: "~9s", l: "full suite, zero network" },
                { v: "0", l: "fabricated numbers on screen" },
              ].map((s) => (
                <Card key={s.l} className="!p-5">
                  <div className="tnum text-[30px] font-bold leading-none text-ink">{s.v}</div>
                  <div className="mt-1.5 text-[13px] text-ink-500">{s.l}</div>
                </Card>
              ))}
            </div>
            <Card className="!p-5">
              <p className="text-[13px] leading-relaxed text-ink-600">
                Every detector is tested in both its firing and its silent case; so are the withhold paths (the
                min-cohort and min-video-sample gates), the graph's cross-run recall lift, the rate arithmetic,
                the overlap invariants, the ledger, and the outreach safe-allowlist. Sourcing runs against an
                injected fake Apify client (assembly, budget stop, refuse-before-spend); the LLM rerank against a
                fake model (citation-stripping, ghost-citation rejection, provider-failure survival). The whole
                post-match layer was pressure-tested by an up-front design review and an adversarial code review
                at the end. The frontend typechecks and builds clean, and the committed pipeline payload keeps
                the demo, the API, and every on-screen number identical by construction.
              </p>
            </Card>
          </section>

          {/* 08 · Deployment topology */}
          <section className="space-y-4">
            <SectionHeader id="deploy" title="Deployment topology" icon={Cloud} />
            <Card className="!p-5">
              <div className="grid gap-4 sm:grid-cols-3">
                {[
                  {
                    h: "Cloudflare Pages",
                    b: "The React SPA, plus a Pages Function that serves the Python pipeline's own committed output at /api/shortlist — a real result with zero rate-limit risk.",
                  },
                  {
                    h: "Render",
                    b: "The FastAPI service (one-click render.yaml). This deployment's frontend is built with VITE_API_URL pointed here, so it runs live per-request compute — Brand DNA and the citation-validated rerank are live (keys set).",
                  },
                  {
                    h: "Neon",
                    b: "Serverless Postgres for the durable state. On a fresh deploy the commenter graph is honestly empty until the first run records edges.",
                  },
                ].map((c) => (
                  <div key={c.h}>
                    <div className="flex items-center gap-2 text-[13px] font-semibold text-ink">
                      <Cloud size={14} className="text-brand" /> {c.h}
                    </div>
                    <p className="mt-2 text-[12.5px] leading-relaxed text-ink-600">{c.b}</p>
                  </div>
                ))}
              </div>
              <p className="mt-4 border-t border-border pt-3 text-[12.5px] leading-relaxed text-ink-500">
                Degradation is honest at every hop: if the API is unreachable the SPA renders the bundled
                fallback (the same committed payload the Function serves); a live path missing its token answers
                a clean 4xx/503 with the reason.
              </p>
            </Card>
          </section>

          {/* 09 · Built vs roadmap */}
          <section className="space-y-4">
            <SectionHeader id="roadmap" title="Built vs roadmap" icon={ListChecks} />
            <div className="grid gap-3 md:grid-cols-2">
              <Card className="!p-5">
                <div className="mb-3 flex items-center gap-2 text-[13px] font-semibold text-verified-fg">
                  <ShieldCheck size={15} /> Built &amp; deployed
                </div>
                <ul className="space-y-2">
                  {BUILT.map((d) => (
                    <li key={d} className="flex gap-2.5 text-[13px] leading-relaxed text-ink-600">
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-verified" aria-hidden />
                      <span>{d}</span>
                    </li>
                  ))}
                </ul>
              </Card>
              <Card className="!p-5">
                <div className="mb-3 flex items-center gap-2 text-[13px] font-semibold text-ink-700">
                  <ListChecks size={15} className="text-ink-500" /> Roadmap (honestly labelled)
                </div>
                <ul className="space-y-2">
                  {ROADMAP.map((d) => (
                    <li key={d} className="flex gap-2.5 text-[13px] leading-relaxed text-ink-600">
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-border-strong" aria-hidden />
                      <span>{d}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            </div>
          </section>
        </div>

        {/* Cross-link back to the operating guide */}
        <div className="mt-12 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-white px-5 py-4 shadow-sm">
          <p className="text-[13px] text-ink-600">
            Want the full product reference? The in-app guide is written to be read — or copied as Markdown and
            pasted into an LLM to ask questions back and forth.
          </p>
          <Link to="/app/guide">
            <Button variant="secondary" leadingIcon={<LifeBuoy size={15} />}>
              Operating guide
            </Button>
          </Link>
        </div>
      </div>

      {/* ── Footer (their deep navy) ── */}
      <footer className="bg-ink-900 text-white">
        <div className="mx-auto max-w-5xl px-6 py-12">
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
                The judgment layer for Thai TikTok KOL matching — fraud-screened, explainable, honest by design.
              </p>
              <img src={ccLogo} alt="Convert Cake" className="mt-5 h-6 w-auto opacity-80 brightness-0 invert" />
            </div>
            <div className="flex flex-col items-start gap-1 text-[13px] text-white/60 sm:items-end">
              <a
                href={LIVE_URL}
                target="_blank"
                rel="noreferrer"
                className="inline-flex min-h-[36px] items-center gap-1.5 transition-colors duration-300 hover:text-white"
              >
                Live demo <ExternalLink size={13} />
              </a>
              <Link
                to="/app/guide"
                className="inline-flex min-h-[36px] items-center transition-colors duration-300 hover:text-white"
              >
                Operating guide
              </Link>
              <Link
                to="/design-system"
                className="inline-flex min-h-[36px] items-center transition-colors duration-300 hover:text-white"
              >
                Design system
              </Link>
              <Link
                to="/app"
                className="inline-flex min-h-[36px] items-center transition-colors duration-300 hover:text-white"
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
