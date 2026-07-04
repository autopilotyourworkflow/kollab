# Kollab — the judgment layer for Thai TikTok KOL matching

**Not a scraper, not a database — the brand-fit and vetting brain that turns a licensed KOL feed into a shortlist an account manager can defend to a client.**

🟢 **Live demo:** https://kollab-64c.pages.dev &nbsp;·&nbsp; served by the pipeline's own output over HTTP (`/api/shortlist`), zero rate-limit risk, a real result in <60s.

> Built for Convert Cake's influencer team as an AI-Engineer take-home. `KOL + Collab = Kollab`.

| | |
|---|---|
| ![Landing](docs/screenshots/landing.png) | ![Shortlist](docs/screenshots/shortlist.png) |
| ![Fraud evidence](docs/screenshots/evidence-mimin.png) | ![Design system](docs/screenshots/design-system.png) |

---

## The problem

Agencies don't lack KOL *data* — licensed Thai platforms (Tellscore, AnyMind, TikTok Creator Marketplace) already hold tens of thousands of vetted profiles with demographics scraping can't get. They lack the **judgment layer**: turning a client's brand into a defensible, fraud-screened, ROI-justified shortlist an account manager can screen-share to a client unedited.

A follower-count tool recommends the 486K-follower creator with 9.1% engagement. Kollab catches that her engagement is a **41-account comment pod** and a **6.2× view spike over her own baseline** — *before* the client's budget bleeds into her.

## What it does

A 7-step pipeline, each output tagged with provenance and grounded to a real data point:

1. **Brand DNA** — ingest the client website → structured `BrandProfile` (category, audience, tone, content pillars, brand-safety no-go list). Degrades gracefully on a new brand: Claude → Gemini → rules-based skeleton, badged *"degraded extraction."*
2. **Candidate sourcing** — via a swappable `KOLSource` adapter. `SeedDatasetSource` (curated, always-on demo) or `ApifyAdapter` (public-data sampling, prototyping only). Production target = a licensed feed behind the same interface.
3. **Enrichment** — profile + recent videos + captions → content DNA, every derived field carrying provenance + a *deterministically-computed* confidence.
4. **Authenticity / fraud vetting (the hero)** — structural-first signals, graded against a pre-computed reference cohort, each badge naming the triggered signal and the distribution (with *n*) it was measured against. See below.
5. **Two-stage explainable match** — embedding retrieve (recall) → citation-grounded LLM rerank (precision) with a post-hoc validator that rejects any claim citing a data point not in the payload.
6. **Brand-safety + commercial-conflict gate** — two named checks, flag-for-human (never silent auto-exclude), each trigger routed to review with the offending term shown.
7. **Client-ready output** — interactive shortlist with live filter/re-rank and HITL approve/reject/override.

## The hero: fraud / authenticity vetting

The differentiator is depth here, not breadth everywhere. Structural detectors **lead** (they're the durable part); the Thai comment-phrase lexicon is only a tiebreaker because pod farms rotate wording monthly.

| Signal | What it catches | Grounding |
|---|---|---|
| **Cross-creator commenter reuse** | Comment pods: a cluster of accounts commenting across many *unrelated* creators | shared-commenter graph over the sampled corpus |
| **Comment-burst timing** | Bot drops (many comments in a 2-min window, then silence) | comment timestamps per video |
| **Templated comment text** | Copy-paste pod comments | duplicate-rate over the sample |
| **Thin commenter profiles** | Bought audiences (empty / no-Thai-history accounts) | sampled commenter second-pass |
| **View-to-follower collapse** | Bought followers (reach far below the follower count implies) | absolute floor + peer-cohort norm |
| **Self-baseline view spike** | Boosted/atypical posts priced as organic reach | the creator's own trailing median (outliers excluded) |
| **ER-vs-cohort outlier** | Suspiciously hot engagement | peer distribution — **withheld below n≥15** |
| **Cadence / dormancy** | Stalled creators | posting timestamps |

Two rules keep it honest:

- **Minimum-cohort rule.** An outlier signal fires only when its peer cell has **n ≥ 15**; below that the badge reads *"insufficient baseline — signal withheld"* rather than a false-confident flag.
- **What we cannot detect** is stated plainly (true demographics, bot-at-scale, private analytics) — the limit is a trust signal, and it's why the tool **flags for a human** rather than clearing or killing anything autonomously.

Every threshold is a named, documented, retunable constant (`app/fraud/signals.py`) — a checkable invariant a Thai account manager can audit and retune, not a black box.

## Live vs. computed

The frontend fetches `GET /api/shortlist` over HTTP and renders whatever the pipeline computed — every count, badge, and rationale on screen derives from that payload (the footer names the active source). On the hosted demo the endpoint is a Cloudflare Pages Function serving the **Python pipeline's own output** (regeneration command documented in `frontend/functions/api/shortlist.ts`); point `VITE_API_URL` at a running FastAPI instance for live per-request compute. If the API is unreachable, bundled fixtures keep the demo alive — same contract, honestly labeled. The fraud verdicts are computed **from first principles** on Apify-shaped data (see the 56-test suite), and the same code path serves live Apify or a licensed feed when credentials exist.

## Architecture

```
                       ┌──────────────────────────────────────────┐
  client website  ──▶  │  Brand DNA (Claude → Gemini → rules)      │
                       └──────────────────────────────────────────┘
                                        │  BrandProfile
                                        ▼
   KOLSource adapter  ┌───────────┐   candidates   ┌──────────────┐
   Seed | Apify | ──▶ │  enrich   │ ─────────────▶ │  fraud vet   │  structural-first,
   licensed feed      └───────────┘                │  + cohorts   │  cohort-anchored, n≥15
                                                    └──────────────┘
                                        │  Risk + authenticity
                                        ▼
                       ┌──────────────────────────────────────────┐
                       │  match: retrieve → citation-grounded      │
                       │  rerank → validator → rank                │
                       └──────────────────────────────────────────┘
                                        │  ShortlistResponse (camelCase contract)
                                        ▼
   React SPA (Cloudflare Pages)  ◀──────┘   interactive shortlist + HITL + cost meter
```

- **Frontend:** Vite + React 19 + TypeScript + Tailwind v4, deployed on Cloudflare Pages.
- **Backend:** Python + FastAPI + Pydantic v2. Pure-stdlib statistics (no numpy) so install stays light. One LLM on the core path (Claude) with a Gemini/rules degradation fallback.
- **Data contract:** a single Pydantic → camelCase model shared by both ends.

Full detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Data ethics / PDPA / ToS stance: [docs/ETHICS.md](docs/ETHICS.md).

## Repo layout

```
frontend/          Vite + React SPA (the deployed demo)
  functions/       Cloudflare Pages Function serving /api/shortlist (pipeline output)
  src/lib/api.ts   fetch-with-fixtures-fallback + persisted brief
backend/
  app/
    schemas.py     output contract (mirrors frontend/src/lib/types.ts)
    raw.py         Apify-shaped ingestion models
    fraud/         cohort stats + structural detectors + vetting orchestration  ← the hero
    sources/       KOLSource interface + Seed (fixtures) + Apify adapter
    matching/      deterministic scoring + citation-grounded rerank + validator
    trust/         provenance + deterministic confidence
    pipeline.py    brief → enrich → vet → match → rank → ShortlistResponse
    main.py        FastAPI app (/health, /api/shortlist)
  tests/           56 unit + integration tests (synthetic data)
  eval/            labeling rubric + labels + precision@k / recall@k harness
ops/n8n/           importable re-vet + alert workflow (cron + manual webhook)
docs/              architecture + ethics + eval report + screenshots
```

## Run it locally

**Frontend**
```bash
cd frontend
npm install
npm run dev            # http://localhost:5178
npm run build          # production build
```

**Backend**
```bash
cd backend
python -m venv .venv && ./.venv/Scripts/pip install fastapi "uvicorn[standard]" pydantic pytest httpx
./.venv/Scripts/python -m pytest          # 56 tests, ~0.5s
./.venv/Scripts/python -m uvicorn app.main:app --reload   # http://127.0.0.1:8000/docs
```

`GET /api/shortlist` returns the Glow Lab demo shortlist. Zero credentials required — see `backend/.env.example` for the optional keys that enable the live Apify / LLM paths.

## Business framing (method, not fabricated numbers)

The headline is **workflow ROI**: a shortlist that takes an account manager hours of manual research becomes ~15 minutes and is more defensible. The baseline hours are shown as an **editable input**, to be anchored to a *timed real run* of the manual process (honest and cheap) rather than an invented benchmark. A secondary line links avoided fake-KOL bookings to reduced fraud-spend waste. Campaign-reach projections use pulled **organic** view medians (boosted posts excluded), labelled as historical-not-guaranteed with a wide confidence band. **Rate/tier modeling is deliberately roadmap** — it belongs to the agency's own closed-deal data + licensed feeds, never a scraped or invented number.

## What's built vs. roadmap

**Built:** deployed demo served by the pipeline API over HTTP · structural-first fraud vetting with cohort math + min-n rule · KOLSource adapter (Seed + Apify mappers) · deterministic matching + citation validator · provenance + computed confidence · pipeline-derived cost meter · 56-test suite · **eval harness** (rubric + labels + precision@k/recall@k, [docs/EVAL.md](docs/EVAL.md)) · **n8n re-vet + alert workflow** ([ops/n8n](ops/n8n/), cron + manual webhook) · editable persisted brand brief · Comfortable/Spacious density toggle · WCAG-minded a11y pass (skip link, aria-live, keyboard menu, reduced-motion).

**Roadmap:** live Brand DNA (Claude → Gemini → rules) + Apify/licensed pull · embeddings/pgvector retrieval · re-labeling the eval on the live seed cohort (2 brands × 20) · PDF deck export · Thai-native validation of the taboo list + comment lexicon · rate/tier learned from agency deal history.

## Status

Private until the submission deadline, then opened / reviewers invited. The scraper adapter is clearly labeled prototyping-only; production points the same interface at a licensed feed.
