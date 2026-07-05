# Architecture

Kollab is a **judgment layer**: everything downstream of sourcing depends on our own
boundary model (`RawKOL`), never on a vendor's JSON. Swapping the public-data scraper
for a licensed feed is a new adapter, not a rewrite.

## Data flow

```
ClientBrief ──▶ KOLSource.fetch_candidates ──▶ [RawKOL]  ┐
               KOLSource.reuse_corpus ──────▶ [RawKOL]  ┘─▶ corpus
                                                          │
                          build_cohorts(corpus) ─────────┤  (vertical × tier) cells, n≥15 gate
                          build_commenter_index(corpus) ─┤  uid → {creators}
                                                          ▼
                    vet_cohort ─▶ per-candidate VetResult { Risk, authenticity_score }
                                                          │
                    build_factors + fit_score ───────────┤  topic·0.45 auth·0.35 recency·0.20 audience·0.0
                                                          ▼
                              Kol[]  ──sort by fit──▶  ShortlistResponse (camelCase)
```

## Modules

### `app/raw.py` — ingestion boundary
Apify-shaped models (`RawProfile`, `RawVideo`, `RawComment`, `RawKOL`) traced 1:1 to the
verified clockworks actor payloads. `parse_iso` normalizes actor `createTimeISO` (handles
trailing `Z`) to aware UTC. This is the ONLY place vendor field names appear.

### `app/schemas.py` — output contract
Pydantic v2 models mirroring `frontend/src/lib/types.ts`. A `to_camel` alias generator
means Python stays snake_case while the wire is the camelCase the frontend consumes
(`median_views` → `medianViews`). FastAPI serializes by alias, so the API response drops
straight into the frontend with no adapter.

### `app/fraud/` — the hero
- **`cohort.py`** — `engagement_rate` (median of per-video ratios, so a view-spiked post
  doesn't distort it), `median_views` / `view_to_follower` (self-outliers excluded via
  `median_excluding_outliers`), and `CohortStats` with the **`sufficient` (n≥15)** gate and a
  stdlib type-7 `_quantile`. `build_cohorts` groups creators into (vertical × tier) cells.
- **`signals.py`** — one pure function per detector, each returning a `SignalResult`
  (`fired`, `level`, `label`, grounded `detail`, `measured_against`, `penalty`, `withheld`,
  `family`). Thresholds are named module constants with a rationale comment — auditable and
  retunable. Structural detectors lead; `thai_lexicon_hits` never fires on its own — `vet.py`
  appends it to an already-fired pod badge as corroboration, labeled *"pattern heuristic,
  human-review recommended."* Detectors that lack evidence **withhold** instead of flagging:
  the ER outlier below cohort n≥15, and view-to-follower below a minimum video sample
  (absence of data is never asserted as fraud).
- **`vet.py`** — `vet_cohort` orchestrates: builds cohorts + the shared-commenter graph over
  the corpus, then per candidate folds fired signals into the frontend's `Risk` shape.
  Badge policy: the pod family (reuse + burst + templated text) collapses into a single
  **"Comment pod"** badge led by the strongest structural signal; the ER-outlier is shown as
  its own badge only when nothing structural already explains the inflation (structure leads,
  statistics corroborate); badges are ordered structural-first, most-severe-first.

Why structural-first: cross-account reuse and burst timing are expensive for a pod farm to
fake and cheap for us to measure; a phrase lexicon is trivially rotated. The README table
lists each signal and its grounding.

### `app/sources/` — swappable candidate sourcing
- **`base.py`** — `KOLSource` ABC: `fetch_candidates`, optional `reuse_corpus` (the wider
  set the reuse graph + cohorts are built from), and `presentation` (presentational +
  precomputed-relevance fields). `Presentation.audience_score` is advisory/non-ranking.
- **`seed.py`** — expands compact descriptors (`fixtures/seed_cohort.json`) into full raw data
  with a **per-handle seeded RNG**, so every run is byte-reproducible (no `Date.now`, no live
  RNG). Engineered so the structural detectors reproduce the exact demo story; adds clean
  cohort fillers to the corpus (never the shortlist) so hero cells reach n≥15, and pod-decoy
  creators so cross-creator reuse validly fires.
- **`apify.py`** — pure `parse_profile_item` / `parse_video_item` / `parse_comment_item`
  mappers (unit-tested; numeric `createTime` epochs are converted to ISO, and items without
  a usable timestamp are dropped by `assemble_kol` because every detector is time-based),
  plus the **budget-capped actor-run loop**: brief → search queries → tiktok-scraper video
  items (author profile embedded) → group by author → per-creator comment sample, with a
  `BudgetMeter` that pre-checks every fetch and stops *before* the projected spend crosses
  the cap (`KOLLAB_RUN_BUDGET_USD`, default $5) — a partial-but-honest pull, never a
  surprise bill. The client is injectable, so the whole loop is tested against a fake;
  the first run against the real actors is a calibration run. Commenter-profile second-pass
  enrichment is deliberately not pulled (cost) — without it the thin-commenter detector
  withholds rather than guesses. Missing preconditions (no token, no `apify-client`)
  surface as an honest `503` with the reason. Clearly labeled prototyping/public-data only.

### `app/matching/`
- **`score.py`** — deterministic `build_factors` (topic / authenticity / recency / audience)
  and `fit_score` = normalized weighted sum of the soft factors. Audience carries weight
  **literally 0.0** and is excluded from the sum, so the "advisory only" label and the score
  tell one story.
- **`topic.py`** — deterministic lexical topic scoring for live sources (no curated
  descriptor): caption/hashtag/bio overlap with the brief's category + pillars, the
  rationale naming the exact matched terms. The LLM rerank refines the copy; it never
  replaces this auditability.
- **`rerank.py`** — a **pure, tested citation validator** (`validate_citations` flags any
  `[[dp:*]]` citation outside the allowed payload; the retry-capped
  `CitationValidator.enforce` returns a *"rationale withheld: citation check failed"* badge
  on persistent failure) plus `apply_llm_rerank`: for each top-of-list KOL it enumerates
  the citable data points from the computed payload, asks the LLM (Claude via `app/llm.py`)
  for bilingual why-copy *with* citation markers, validates, then strips the markers for
  display. Claims must cite to pass; any failure keeps the deterministic copy — the rerank
  can refine, never block or fabricate. Off by default without a key
  (`KOLLAB_LLM_RERANK=0` forces it off with one).

### `app/ingest/`
- **`brand_dna.py`** — website → `ClientBrief` with an explicit degradation chain:
  **Claude → Gemini → rules-based skeleton**, each result naming its source and carrying
  `degraded=True` when it fell to the skeleton (the UI badges it "degraded extraction").
  An LLM response that fails JSON/schema validation falls through to the next tier — the
  chain never fabricates a confident-looking brief. Fetch + both LLM callers are
  injectable; the whole chain is tested with fakes. Exposed as `POST /api/brand-dna`
  (works credential-free: you get the labeled skeleton).

### `app/trust/`
- **`provenance.py`** — the measured / inferred tag on every match factor is sourced from
  `PROVENANCE_BY_FACTOR` here, and `advisory_tag` appends the inline *"do not quote to
  client as fact"* advisory to every inferred-field rationale — it ships on the audience
  factor in the live payload today.
- **`confidence.py`** — confidence is **computed, not vibed**: from comment-sample size
  (authenticity), data completeness (audience, capped at 0.6 because inferred), and cohort-n
  (outlier). One tested function per field, each naming its driver. **Not yet surfaced in
  the API contract/UI** — that wiring is roadmap; no confidence number is shown anywhere
  until it is a computed one.

### `app/pipeline.py` + `app/main.py`
`build_shortlist` wires it end-to-end and projects a real per-run cost from actual data volume
using the verified Apify prices ($0.50/1k comments, $1.70/1k results). It prefers the dataset's
own `as_of` date as "now" for deterministic recency. `main.py` exposes `/health`,
`/api/shortlist` (GET default demo, POST with a brief; live-path preconditions answer 4xx/503
with the reason) and `/api/brand-dna`, applies the LLM rerank when enabled, with CORS open to
the Pages demo + localhost.

## Reliability & degradation

- **Brand ingest:** Claude → Gemini → rules-based skeleton, each response naming its
  source; the skeleton is flagged `degraded` and the UI badges it *"degraded extraction."*
- **Rerank:** validation-gated with a capped retry; any provider/parse/citation failure
  keeps the deterministic copy (refine-only, never block). A stale-cache fallback for live
  screen-shares (serve the last-cached adjudication with a stale badge) is roadmap.
- **Citation validator:** retry-capped, then a visible "rationale withheld" badge.
- **Sourcing budget:** every live fetch is pre-checked against the run cap; the loop stops
  before crossing it and reports a partial pull honestly.
- **Fixtures mode:** the default, so a reviewer never hits a rate limit.
- **Precondition honesty:** a live path missing its token/dependency answers a clean
  `4xx/503` with the reason; no path silently degrades to a fabricated result.

## Testing

95 tests (`backend/tests/`) on synthetic data + fake clients: run-depth plan math +
frontend-parity enforcement, every detector (pod / burst /
templated / thin / ER-outlier / view-to-follower / boosted / dormancy) in both firing and
silent cases, the withhold paths (min-cohort AND min-video-sample), vetting dedup + ordering
+ lexicon corroboration, deterministic scoring, honest-rationale rules (withheld peer check,
dormancy not fraud-templated), the citation validator AND the LLM rerank against fakes
(citation-stripping, ghost-citation rejection, provider-failure survival), the Brand DNA
degradation chain (Claude → Gemini → rules, unreachable-site case), the Apify actor loop
against a fake client (assembly, tier/vertical inference, budget stop, refuse-before-spend),
the trust layer, seed determinism incl. realized-ER == descriptor, the Apify mappers (ISO +
epoch + dropped-unstamped cases), the 503/400 precondition answers, and an end-to-end
pipeline assertion that the seed shortlist reproduces the deployed UI's exact risk story and
emits the camelCase contract.

## Design decisions worth calling out

- **No numpy.** stdlib `statistics` keeps the install light and portable; the math here
  (median, IQR, quantiles, Tukey outliers) doesn't need it.
- **One LLM on the core path.** Claude leads both LLM touchpoints (Brand DNA, rerank) with
  Gemini strictly as a degradation fallback — fewer integration surfaces; Claude-vs-Gemini
  as a quality A/B on the rerank rubric is a v1 lever, noted rather than built now.
- **Determinism everywhere in fixtures mode.** Seeded RNG + dataset `as_of` → reproducible
  output, which is what makes the test suite meaningful and the demo dependable on camera.
