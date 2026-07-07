import { useState } from "react"
import { Link } from "react-router-dom"
import { ArrowLeft, ClipboardCopy, Check, LifeBuoy, BookOpen } from "lucide-react"
import { Button } from "../components/ui/Button"

/** In-app operating + technical reference. One typed source of truth renders to the
    screen AND to a one-click Markdown export, deep enough to paste into an LLM and ask
    questions back and forth — so the guide and the doc can never drift. */

interface GuideSection {
  id: string
  title: string
  intro?: string
  points: string[]
}

const PREAMBLE =
  "This is the complete operating and technical reference for Kollab, an AI-powered TikTok KOL (influencer) matcher and fraud-vetting decision layer for the Thai market. It is written to be read by a human operator AND to be pasted into an LLM as context: use it to answer questions about how Kollab works, what it can and cannot do, its honesty guarantees, its architecture, its fraud detectors and their thresholds, its data model, and how to operate it. Where a number or threshold is given, it is the value the shipping code uses."

const OVERVIEW =
  "Kollab (the name = KOL + Collab) turns a client's brand into a fraud-screened, ROI-justified shortlist of Thai TikTok creators an account manager can defend to a client, unedited. It is not a scraper and not a database — it is the judgment layer that sits on top of KOL data and decides who is a real, on-brand, fraud-free fit. Its one hard differentiator is authenticity vetting: catching bought engagement (comment pods, bought followers, boosted posts) before a client's budget is spent on it. Everything is built to degrade honestly: an unavailable path answers a clear error or a clearly-labelled fallback, never a fabricated result."

const GUIDE: GuideSection[] = [
  {
    id: "positioning",
    title: "1. What Kollab is (and is not)",
    intro: "The positioning that keeps it credible and defensible.",
    points: [
      "It is a decision/judgment layer, not a data source. KOL data (profiles, videos, comments) comes from a swappable adapter; Kollab's value is the vetting, matching, and ranking on top.",
      "The scraping adapter (Apify) is clearly labelled prototyping / public-data sampling only. The production target is a LICENSED feed (e.g. Tellscore, AnyMind, TikTok Creator Marketplace) behind the exact same interface — swapping it is a new adapter, not a rewrite.",
      "It flags for a human; it never auto-clears or auto-kills a creator. Every risk is routed to review with the evidence attached.",
      "It is built as a production, SaaS-grade internal tool, not a throwaway demo — real persistence, honest error handling, health checks, and a 254-test backend suite.",
    ],
  },
  {
    id: "problem",
    title: "2. The problem it solves",
    points: [
      "Agencies don't lack KOL data — they lack the judgment layer that turns a brand into a defensible shortlist.",
      "A follower-count tool recommends the 486K-follower creator with 9.1% engagement. Kollab catches that her engagement is a 41-account comment pod and a 6.2x view spike over her own baseline — before the client's budget bleeds into her.",
      "The headline value is workflow ROI: a shortlist that takes hours of manual research becomes ~15 minutes and is more defensible. A secondary line is avoided fake-KOL bookings.",
    ],
  },
  {
    id: "workflow",
    title: "3. The end-to-end workflow",
    intro: "What an operator actually does, start to finish.",
    points: [
      "Start a shortlist: paste the client's website. Kollab reads it into a structured brief (audience, content pillars, tone, brand-safety no-go list) — the Brand DNA step.",
      "Review and edit the brief (human-in-the-loop on the brief itself), then pick a run depth (Scan / Standard / Deep) with a live cost estimate and an editable hard cap.",
      "Sourcing runs in the background (a real scrape takes minutes); the run dock tracks it and survives a refresh or closing the tab.",
      "Each candidate is enriched, vetted for fraud, matched against the brief, scored, and ranked into a shortlist.",
      "Review each creator's evidence, approve or reject (with a reason when overriding a flag), then export a client-ready shortlist or an internal vetting report.",
      "After booking: re-audit the delivered post, log the outcome to the ledger, and generate a grounded outreach message.",
    ],
  },
  {
    id: "architecture",
    title: "4. Architecture & tech stack",
    points: [
      "Frontend: Vite + React 19 + TypeScript + Tailwind v4, deployed on Cloudflare Pages. Single-page app.",
      "Backend: Python + FastAPI + Pydantic v2, deployed on Render. Pure-stdlib statistics (no numpy) so the install stays light. LLM-optional by design: deterministic, citation-grounded scoring runs with zero keys.",
      "Database: Neon Postgres (via SQLAlchemy), backing durable server-side state. All DB imports are lazy so the credential-free demo needs none of them.",
      "Data contract: a single Pydantic model serialized to camelCase JSON, mirrored exactly by the frontend TypeScript types — one source of truth for both ends.",
      "The deployed demo's shortlist renders from a committed pipeline-output payload (the bundled fallback), while the live tools (graph, re-audit, ledger, outreach) call the FastAPI backend.",
      "LLM providers: Claude (primary) with a Gemini fallback, used for Brand DNA extraction and a citation-validated rerank; both are optional and every path degrades to a labelled deterministic result without a key.",
    ],
  },
  {
    id: "adapters",
    title: "5. The data-source adapter model",
    intro: "Why the source is swappable, and the ethics stance.",
    points: [
      "Every source implements one KOLSource interface (fetch candidates + presentation). The fraud and matching layers depend on Kollab's own boundary model, never on a provider's JSON.",
      "SeedDatasetSource: curated, deterministic fixtures that power the always-on demo with zero credentials. Handles are fictional on purpose — we never label a real creator 'fake' in a public repo.",
      "ApifyAdapter: live public-data sampling via TikTok scraper actors, clearly labelled prototyping-only, with a budget-capped run loop that stops before crossing the cap.",
      "Ethics/PDPA stance: public data only, minimised, lawful-basis; scraping is one swappable adapter, and the production path is a licensed feed. Fraud-flagged handles are anonymised in a live run.",
    ],
  },
  {
    id: "fraud",
    title: "6. Fraud / authenticity vetting — the hero",
    intro: "The differentiator is depth here, not breadth everywhere.",
    points: [
      "Structural signals LEAD (they are the durable part); statistics corroborate. A Thai comment-phrase lexicon never fires a flag on its own — it only annotates an already-fired pod badge as corroboration, because pod farms rotate wording monthly.",
      "Every badge names the triggered signal and the exact baseline (with n) it was measured against. It never asserts absence-of-data as fraud.",
      "Signals fold into a per-creator authenticity score (0-100) that feeds the match, and into a Risk level (clear / medium / high). The pod family (reuse + burst + templated) collapses into a single 'Comment pod' badge led by the strongest structural signal.",
      "Every threshold is a named, documented, retunable constant in the code — a checkable invariant a reviewer or a Thai account manager can audit, not a black box.",
    ],
  },
  {
    id: "detectors",
    title: "7. The fraud detectors, one by one",
    intro: "Each detector, what it catches, its grounding, and the shipping threshold.",
    points: [
      "Cross-creator commenter reuse (LEAD signal): a cluster of accounts commenting across many unrelated creators. Fires when >= 20 pod accounts each hit >= 3 creators AND make up >= 15% of this creator's comments. Grounded in the shared-commenter graph.",
      "Comment-burst timing: a bot drop of many comments in a tight window. Fires at >= 25 comments within a 120-second window on one video.",
      "Templated comment text: copy-paste pod comments. Fires when near-duplicate strings (repeated >= 3x) make up >= 30% of the sample.",
      "Thin commenter profiles: bought audiences of empty / no-Thai-history accounts. Needs a sampled sub-set of >= 20 commenter profiles; fires when >= 50% look thin (< 5 posts or no Thai history).",
      "View-to-follower collapse (bought followers): reach far below what the follower count implies. Fires below an absolute 5% floor, or below 25% of the peer-cohort median. Withheld below 5 sampled videos (absence of data, not fraud).",
      "Self-baseline view spike (boosted posts): a recent post a large multiple of the creator's OWN trailing median (self-outliers excluded). 'View spike' at >= 4x, 'possible boosted post' at >= 2x — so ad-lifted reach isn't priced as organic.",
      "Engagement-rate vs cohort outlier: suspiciously hot engagement above the peer distribution (Tukey p75 + 1.5*IQR). WITHHELD below n=15 peers — it reads 'insufficient baseline' rather than false-flagging.",
      "Cadence / dormancy: a stalled creator. Fires when the last post is > 14 days old. Treated as a cadence concern, not engagement fraud.",
    ],
  },
  {
    id: "mincohort",
    title: "8. The minimum-cohort rule (why Kollab withholds)",
    points: [
      "An outlier signal (ER-vs-cohort, view-to-follower vs peers) is only valid against a peer distribution with enough members. The gate is n >= 15.",
      "Below the gate, the badge reads 'insufficient baseline — signal withheld' rather than a false-confident flag. The internal report shows these withheld checks explicitly.",
      "This is the core honesty mechanism: it is why the tool flags for a human rather than clearing or killing anything autonomously. Stating the limit is itself a trust signal.",
    ],
  },
  {
    id: "provenance",
    title: "9. Provenance & confidence",
    points: [
      "Every derived field is tagged measured, inferred, or estimated. Inferred fields (e.g. audience) carry an inline advisory that travels with the data: 'do not quote to client as fact.'",
      "The audience factor is inferred and strictly non-ranking (weight 0.0) — it is advisory only, because true audience demographics need licensed data.",
      "Deterministic confidence functions (computed from the data, not emitted by an LLM) scale with sample size — e.g. fraud-verdict confidence scales with how many comments were sampled.",
    ],
  },
  {
    id: "graph",
    title: "10. The persistent commenter graph (the moat)",
    intro: "The proprietary data that makes shortlists provably improve every campaign.",
    points: [
      "Every run records its observed commenter -> creator edges to a persistent store. Within one run, the reuse graph is limited to the creators that run happened to pull; across runs it accumulates.",
      "At vet time the accumulated graph is unioned into the in-run index BEFORE the unchanged, gated detector runs — so a pod that only touched a couple of this run's creators but hits many across history is caught. Fraud recall improves every run.",
      "Honesty guarantee: the graph can only RAISE recall on a real pattern. The detector's gates (>= 20 accounts, >= 3 creators, >= 15% share, and the n>=15 withhold) are unchanged, so history can never manufacture a pod from absence of data. Every edge is an observed comment, nothing inferred.",
      "Two backends: a durable Neon store (production) and an in-memory store (the credential-free demo + tests). The readout labels which — 'durable · Neon' vs 'ephemeral demo graph'. On a fresh deployment the durable graph is empty until the first run records edges (this is honest, not a bug).",
      "A pod cluster in the readout is a connected component of reused commenters (accounts seen on >= 3 creators) of >= 20 accounts, reported as accounts x creators.",
    ],
  },
  {
    id: "reaudit",
    title: "11. Delivered-post re-audit",
    points: [
      "After a booked creator posts the paid content, Kollab re-runs the SAME structural detectors on that actual delivered post and diffs the result against the pre-booking authenticity.",
      "It catches a creator who vetted clean but bought engagement for the sponsored post — zero new judgment logic, so it is exactly as trustworthy as the vetting the client already saw.",
      "It withholds ('inconclusive') when the delivered post has too few comments (< 15) — absence of evidence is never reported as a clean verdict. When the persistent graph knows the accounts, cross-creator reuse is caught even from a single post.",
      "Verdicts: consistent, degraded, cleared, or inconclusive. It lives in the 'After booking' tab, which unlocks only after you approve the creator.",
    ],
  },
  {
    id: "ledger",
    title: "12. Delivery ledger & the closed loop",
    points: [
      "You log a campaign outcome: the reach Kollab projected at booking vs what the paid post actually delivered. This is the only source of outcome truth — public data carries none.",
      "With nothing logged it shows an explicit learning state and a strictly neutral (zero) fit adjustment — never a fabricated number.",
      "Once outcomes exist, the average delivered/projection ratio nudges the creator's fit score, HARD-CLAMPED to +/-6 so a couple of data points can never dominate the measured factors, and always labelled 'estimated, from your N deliveries'.",
      "The 'ML' is deliberately a transparent clamped average, not a hidden model; a genuinely learned rate/outcome model is roadmap and labelled as such.",
      "The ledger is durable in Neon; the fit nudge is a no-op when nothing is logged, so the shortlist is byte-identical to the no-data case.",
    ],
  },
  {
    id: "rate",
    title: "13. The fraud-adjusted fair-rate estimator",
    intro: "Honest by construction — never a market rate card.",
    points: [
      "The estimate is exactly three things multiplied: the creator's OWN outlier-excluded median ORGANIC views (boosted posts already excluded) x a CPM the OPERATOR sets x the authenticity score.",
      "The CPM (Thai baht per 1,000 organic views) is the ONE assumption the user provides — editable per creator, defaulting to a neutral placeholder (150 THB) with NO tier or vertical variation. Double the CPM and the band visibly doubles; it is linear in the user's number by construction.",
      "Authenticity discounts inauthentic reach: a pod or bought-follower creator's inflated reach is discounted, not paid for. A fully-flagged creator reads 'not reach-priceable' (a zero band) because Kollab assesses the reach as non-organic — the fraud finding flows straight into the price.",
      "The band is WITHHELD when fewer than 5 videos were sampled (too thin to price). Every value is tagged 'estimated' and the full arithmetic is shown. It is never presented as the market rate for a tier — inventing tier benchmarks is explicitly out of scope.",
      "A learned rate model from accumulated agency deal history is roadmap.",
    ],
  },
  {
    id: "overlap",
    title: "14. Commenter-overlap dedup",
    points: [
      "Two shortlisted creators who share a large fraction of the same commenters reach the same people — booking both double-serves that slice of budget.",
      "Kollab computes a pairwise Jaccard over shared commenter-id sets across the shortlist and surfaces pairs above a meaningful threshold (>= 15% overlap, with >= 20 commenters sampled on both sides).",
      "Honesty: it is COMMENTER overlap, not 'audience overlap'. The shared count and Jaccard are measured on real commenter ids; the leap to 'same audience' is an inferred proxy (the engaged subset), labelled as such. Low overlap is never presented as proof two creators are independent.",
    ],
  },
  {
    id: "brandsafety",
    title: "15. Brand-safety scan",
    points: [
      "A transparent scan of the creator's OWN captions, bio, and hashtags against a documented, retunable taboo lexicon (unverified medical claims, gambling, counterfeit goods, adult content, regulated substances).",
      "It is a SEPARATE axis from fraud risk — a flag here routes to human review and never changes the risk level or the recommended/flagged counts. It always names the offending term.",
      "It never auto-excludes. Culturally-normal cosmetic language (e.g. generic skin-whitening) is a deliberate, documented omission — a brand that won't touch it lists it in its own no-go brief, which is a separate mechanism.",
    ],
  },
  {
    id: "outreach",
    title: "16. Grounded outreach draft",
    points: [
      "Generates a bilingual (English + Thai) first-contact message to a creator, grounded only in that creator's public metrics and reusing the same citation-validator as the match rerank.",
      "A SAFE ALLOWLIST excludes every fraud, risk, conflict, brand-safety, and score data point, so the model literally cannot cite an internal verdict into a message meant for the creator. The prompt also forbids any price.",
      "No LLM key, a failed citation check, or any provider error falls back to a labelled deterministic template. It never fails to produce a sendable draft.",
    ],
  },
  {
    id: "matching",
    title: "17. Match scoring & the fit score",
    points: [
      "The fit score is a normalized weighted sum of soft factors: topic fit 45%, engagement authenticity 35%, recency & cadence 20%. The audience factor carries weight 0.0 (advisory, non-ranking).",
      "Scoring is deterministic and citation-grounded always. With an LLM key, a rerank rewrites the top-of-list 'why this match' copy — but it may only cite enumerated data points and must pass a post-hoc validator; uncited claims are rejected and the deterministic copy stays.",
      "Recommended = clear risk AND fit >= 70. Flagged = any risk level above clear.",
    ],
  },
  {
    id: "branddna",
    title: "18. Brand DNA extraction",
    points: [
      "Turns a client website into a structured brief via a Claude -> Gemini -> rules-based-skeleton chain. Every response names its source and flags degraded extraction.",
      "With no LLM key it returns the honestly-labelled rules skeleton; the account manager can edit every field before sourcing.",
    ],
  },
  {
    id: "rundepth",
    title: "19. Run depth, budget & the cost model",
    points: [
      "Users pick a DEPTH (creators x videos x comments), not a raw dollar figure — the same spend allocated differently produces very different detection quality.",
      "Each preset (Scan / Standard / Deep, plus custom volumes) shows a computed cost estimate from the verified actor prices ($1.70 per 1,000 scraper results, $0.50 per 1,000 comments), a hard cap the loop stops before crossing, and an honest note on which signals can fire at that depth.",
      "A too-tight cap yields a labelled partial pull, never a surprise bill. The deeper the run, the closer cohort cells get to n>=15 and the stronger the reuse graph.",
    ],
  },
  {
    id: "byok",
    title: "20. Bring your own key & credit",
    points: [
      "In Settings, paste your own Apify / Claude key. Keys live only in your browser's local storage and ride each request as headers; they are never stored on the server, written to logs, or returned.",
      "A live credit meter shows the remaining balance for whichever key you're running on. The operator can flip a kill switch to stop sharing their own credit.",
      "The operator can also configure a pool of Apify tokens on the server that auto-rotate when one runs low.",
    ],
  },
  {
    id: "hitl",
    title: "21. Human-in-the-loop decisions",
    points: [
      "Approve or reject any creator. Overriding a flag requires a reason, which is recorded.",
      "Approving a creator unlocks the 'After booking' toolkit (re-audit, delivery ledger, outreach) — so cold discovery never shows post-decision numbers.",
      "Decisions persist with the shortlist.",
    ],
  },
  {
    id: "exports",
    title: "22. Exports — client view & internal report",
    points: [
      "Client shortlist: a clean, presentable view of the recommended creators with all fraud internals hidden — safe to screen-share to a client.",
      "Internal vetting report: the full per-creator dossier — every check that ran, including the ones honestly WITHHELD — plus brand-safety and the rate estimate. Both print to PDF from the browser.",
      "Surfacing the withheld checks is the point: the report shows exactly what Kollab could and could not judge, and why.",
    ],
  },
  {
    id: "api",
    title: "23. The API surface",
    intro: "The backend endpoints, all answering the honest-precondition contract.",
    points: [
      "GET /health — status, version, and feature flags. GET /api/db-status — a live SELECT 1.",
      "POST /api/auth/signup · login · guest · GET /api/auth/me · POST /api/auth/logout — accounts + one-click guest (stdlib scrypt password hashing + HMAC session tokens). GET/POST /api/shortlists (+ per-id kols / decisions / source-live / DELETE) — the per-user workspace, current-user-gated (an honest 503 without a database).",
      "GET /api/shortlist — the demo shortlist (seed). POST /api/shortlist — run the pipeline for a brief. POST /api/runs + GET /api/runs/{id} + cancel — async background sourcing.",
      "POST /api/brand-dna — website to brief. GET /api/credit — the live credit meter. GET /api/run-plans — run-depth presets with costs.",
      "GET /api/graph — the persistent commenter-graph readout (aggregate counts + pods, no ids). POST /api/re-audit — delivered-post re-audit. GET/POST /api/deliveries — the delivery ledger. POST /api/outreach — the grounded outreach draft.",
      "Live paths answer honest codes: a missing token or brief is a 4xx/503 with the reason; the ledger is 503 without a database; outreach never fails (it falls back to the template).",
    ],
  },
  {
    id: "persistence",
    title: "24. What's durable vs what's in your browser",
    intro: "An honest map of where each piece of state lives.",
    points: [
      "Durable in Neon Postgres: your account and — in API mode — your shortlists workspace (campaigns, their creators, and your approve/reject HITL decisions, user-scoped to your account), async sourcing runs (so a run survives a refresh or the free instance sleeping), the persistent commenter graph (commenter_edges), and the delivery ledger (deliveries).",
      "In your browser's local storage: the saved brief, the selected run depth, your CPM assumption, and your pasted API keys — plus the whole shortlists workspace ONLY in the no-backend local mode, where it falls back to browser storage so the static demo never dead-ends.",
      "Two modes, honestly: with a backend configured (the live demo), the workspace and your HITL decisions are Neon-durable and user-scoped — sign in, or take a private seeded workspace with one-click guest. With no backend, the same workspace transparently falls back to browser storage.",
      "Losing browser state is safe: the worst case is re-running a shortlist, never a wrong result.",
    ],
  },
  {
    id: "honesty",
    title: "25. Honesty principles & what Kollab cannot detect",
    points: [
      "No fabricated numbers. Anything that depends on data the user hasn't logged (outcomes, prices) shows an explicit learning state until they log it.",
      "No invented rate cards or tier benchmarks. Any domain number is grounded in a cited source or in the creator's own measured data.",
      "What Kollab cannot detect is stated plainly: true audience demographics, sophisticated bot-at-scale that mimics organic timing, and private analytics. The limit is why it flags for a human.",
      "Measured beats impressive: a visible 'withheld' or 'roadmap' label is always preferred over a confident guess.",
    ],
  },
  {
    id: "roadmap",
    title: "26. What's built vs roadmap",
    points: [
      "Built: the full fraud-vetting engine, the persistent commenter graph, delivered-post re-audit, the closed delivery ledger, the fair-rate estimator, commenter-overlap dedup, the brand-safety scan, grounded outreach, the internal vetting report, the run-depth selector, the Brand DNA chain, the citation-validated rerank, bring-your-own-key, the authenticated Neon-backed workspace (accounts + per-user shortlists and HITL decisions), and this guide — all deployed live.",
      "Roadmap: a first live calibration run against the real actors + a recorded live-extraction demo; embeddings/pgvector retrieval for recall at licensed-feed scale; a native deal-pipeline board; a learned rate model from agency deal history; Thai-native validation of the taboo and pod lexicons.",
    ],
  },
  {
    id: "quality",
    title: "27. Testing & quality",
    points: [
      "254 hermetic backend tests (pytest) on synthetic data and fake clients cover every detector in both firing and silent cases, the withhold paths, the graph's cross-run recall lift, the rate math, the overlap invariants, the ledger, the auth + workspace routes, the scheduled re-vet diff, and the outreach allowlist.",
      "Each feature was designed against its failure modes up front, then reviewed and re-tested before shipping.",
      "The frontend typechecks and builds clean; the committed pipeline payload keeps the demo, the API, and every on-screen number byte-identical by construction.",
    ],
  },
  {
    id: "glossary",
    title: "28. Glossary",
    points: [
      "KOL — Key Opinion Leader; an influencer/creator.",
      "Comment pod — a ring of accounts that comment on each other's (and clients') posts to fake engagement.",
      "Engagement rate (ER) — (likes + comments + shares) / views, taken as a per-video median so a view-spiked post doesn't distort it.",
      "View-to-follower ratio (VTF) — median views / followers; collapses when a follower base is bought.",
      "CPM — cost per 1,000 (here, per 1,000 organic views); the user's editable rate assumption.",
      "Jaccard — |A intersection B| / |A union B|; used on shared commenter sets to measure overlap.",
      "Cohort — a peer cell (vertical x tier, e.g. beauty-micro) that outlier signals are measured against.",
      "HITL — human-in-the-loop; a person makes the final approve/reject call.",
      "Provenance — the measured / inferred / estimated tag on every derived value.",
    ],
  },
  {
    id: "faq",
    title: "29. Anticipated questions",
    points: [
      "Is the data real? The demo cohort is curated fixtures with fictional handles (we never label a real creator 'fake' in a public repo), but the numbers are the pipeline's real computation on Apify-shaped data. A live run pulls real public data.",
      "Why is the fraud graph empty on the live site? It only accumulates from real runs; showing fabricated history would violate the whole thesis. Run one live scan to populate it, or read the mechanism above.",
      "Why does a flagged creator show a 0 rate? Its authenticity is near zero, so Kollab assesses the reach as non-organic and won't price it on reach — the fraud finding is the economics.",
      "Can Kollab guarantee a creator is clean? No. It surfaces structural evidence and withholds where the sample is too thin; a human makes the call. That honesty is the product.",
      "Does it need API keys? No — the full demo runs credential-free. Keys unlock live sourcing, live Brand DNA, the LLM rerank, and the live post-match tools.",
    ],
  },
]

function toMarkdown(): string {
  const lines: string[] = [
    "# Kollab — Operating & Technical Guide",
    "",
    `> ${PREAMBLE}`,
    "",
    OVERVIEW,
    "",
  ]
  for (const s of GUIDE) {
    lines.push(`## ${s.title}`, "")
    if (s.intro) lines.push(`_${s.intro}_`, "")
    for (const p of s.points) lines.push(`- ${p}`)
    lines.push("")
  }
  return lines.join("\n")
}

export function Guide() {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(toMarkdown())
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      /* clipboard blocked — the on-screen guide is still fully readable */
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <Link
        to="/app"
        className="mb-4 inline-flex min-h-[32px] items-center gap-1.5 text-[13px] font-medium text-ink-500 transition-colors duration-200 hover:text-brand"
      >
        <ArrowLeft size={15} /> Back to shortlist
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="flex items-center gap-2 text-[26px] font-bold tracking-[-0.02em] text-ink">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-50 text-brand">
              <LifeBuoy size={17} />
            </span>
            Operating &amp; technical guide
          </h1>
          <p className="mt-1.5 max-w-xl text-[14px] leading-relaxed text-ink-500">
            The complete reference for how Kollab works — for you to read, or to{" "}
            <span className="font-medium text-ink-700">copy as Markdown and paste into an LLM</span> to ask
            questions back and forth. It stays in sync with the product because it's generated from one source.
          </p>
        </div>
        <Button onClick={copy} leadingIcon={copied ? <Check size={16} /> : <ClipboardCopy size={16} />}>
          {copied ? "Copied" : "Copy as Markdown"}
        </Button>
      </div>

      {/* Overview callout */}
      <div className="mt-6 rounded-2xl border border-brand-100 bg-brand-50/50 p-5">
        <div className="mb-1.5 flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-wide text-brand">
          <BookOpen size={14} /> In one paragraph
        </div>
        <p className="text-[13.5px] leading-relaxed text-ink-700">{OVERVIEW}</p>
      </div>

      {/* Table of contents */}
      <nav className="mt-6 rounded-2xl border border-border bg-white p-5 shadow-sm">
        <div className="mb-2.5 text-[12px] font-semibold uppercase tracking-wide text-ink-400">Contents</div>
        <ol className="grid gap-x-6 gap-y-1.5 sm:grid-cols-2">
          {GUIDE.map((s) => (
            <li key={s.id}>
              <a href={`#${s.id}`} className="text-[13px] text-ink-700 transition-colors hover:text-brand">
                {s.title}
              </a>
            </li>
          ))}
        </ol>
      </nav>

      <div className="mt-6 space-y-4">
        {GUIDE.map((s) => (
          <section
            key={s.id}
            id={s.id}
            className="scroll-mt-6 rounded-2xl border border-border bg-white p-6 shadow-sm"
          >
            <h2 className="text-[16px] font-semibold text-ink">{s.title}</h2>
            {s.intro && <p className="mt-1 text-[13px] italic text-ink-500">{s.intro}</p>}
            <ul className="mt-3 space-y-2">
              {s.points.map((p, i) => (
                <li key={i} className="flex gap-2.5 text-[13px] leading-relaxed text-ink-700">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" aria-hidden />
                  <span>{p}</span>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>

      <div className="mt-8 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-surface px-5 py-4">
        <p className="text-[13px] text-ink-600">
          Reading this in an LLM? Copy it as Markdown and ask anything — it's the whole product in one document.
        </p>
        <Button variant="secondary" onClick={copy} leadingIcon={copied ? <Check size={15} /> : <ClipboardCopy size={15} />}>
          {copied ? "Copied" : "Copy as Markdown"}
        </Button>
      </div>
    </div>
  )
}
