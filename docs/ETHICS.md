# Ethics, data reality & PDPA

Kollab is a **judgment layer on licensed data**, not a scraping product. This document
states the data stance plainly because "no sketchy practices" is a design constraint, not
an afterthought.

## Data sourcing & ToS

- The product is the **architecture and judgment**, not the scraper. The `KOLSource`
  interface means the Apify adapter is a **prototyping / public-data sampling** source,
  explicitly swappable for a licensed feed (Tellscore / AnyMind / TikTok Creator Marketplace)
  in production. This is stated in the README and enforced in code: the Apify network path is
  guarded and disabled by default; the deployed demo runs on curated fixtures.
- Everything is cited where a claim rests on an external fact — the Apify actor payloads, the
  fraud methodology, and (in production) any Thai brand-safety or rate/benchmark source.

## PDPA / lawful basis (Thailand PDPA + GDPR-aligned)

Two categories of personal data are in scope, and both need a lawful basis:

- **Creator (KOL) data.** KOLs are identifiable individuals. Basis: **legitimate interest** in
  processing *public professional content* for B2B matchmaking, with data minimization (only
  fields needed to vet + match), **no sensitive-category inference asserted as fact**, and a
  deletion / opt-out path. Inferred attributes (e.g. audience skew) are tagged inferred and
  carry a *"do not quote as fact"* advisory — never presented as measured demographics.
- **Client audience data.** Processed under the client's own basis; Kollab ingests the client
  *website* primarily, with a Facebook paste-in as an optional fallback — never a scrape the
  demo depends on.

## Live-run creator dignity

In the recorded live-extraction run:

- **Positive** matches are shown **named**.
- **Fraud-flagged negative** examples have their handle **blurred / anonymized** on screen.

Thailand's KOL market is small — agencies and creators know each other. Kollab will not
publicly brand a specific real creator "fake." This is why the demo's fictional fixtures use
invented handles, and why the repo never ships a real creator labeled fraudulent.

## Fraud flags are advisory and human-routed

- The vetting layer **biases toward flagging** (low threshold) and routes **every** decision —
  pass and fail — through human review. It never silently auto-excludes or auto-clears.
- Structural signals lead; the Thai comment-phrase lexicon never fires a flag on its own —
  it only **annotates an already-fired pod badge** as corroboration, labeled in the product
  as *"pattern heuristic, human-review recommended,"* not authoritative Thai judgment.
- Calibrated humility: the structural signals catch **commodity pods and bought engagement**.
  Sophisticated aged-account farms can defeat purely structural signals — which is precisely
  why a flag routes to a human and why licensed audience data is the production answer.

## What Kollab cannot detect

Stated as a trust signal, not hidden:

- **True audience demographics** (age/gender/location as fact) — requires licensed audience
  analytics; Kollab only *infers* skew from public signals, tagged inferred.
- **Bot-at-scale / sophisticated farms** — structural signals catch commodity fraud, not a
  well-aged pod with organic-looking history.
- **Private analytics** (real reach, saves, completion) — not in public data.

Because of these limits, Kollab **flags for a human; it never clears or kills sensitive
content autonomously.**

## Brand-safety taxonomy — a scaffold to be replaced

The brand-safety taboo list and the comment-farm signature set are a **starter scaffold**
authored to be replaced by the agency's tacit knowledge and a Thai-native review before
production:

- The taboo taxonomy (monarchy / lèse-majesté sensitivity, regulated verticals, scam-vertical
  promos, unsubstantiated health claims) is to be **anchored to a citable Thai source** (a
  published brand-safety / legal guideline) rather than self-authored, and validated by a Thai
  native / legal reviewer.
- The comment-farm lexicon is a starter set that pod farms rotate; it is labeled expirable and
  meant to be expanded with the agency.

Both are framed honestly as *"a scaffold I built to be replaced by your team's knowledge in
v1"* — a collaboration hook, not a claim of finished Thai-domain authority.

## Confidence is computed, not claimed

The rule: **no confidence number ships unless it is computed from data** (sample size,
completeness, cohort-n) — never an LLM's self-assessment. Today the product shows *no*
numeric confidence anywhere; the computed-confidence functions are built and tested
(`backend/app/trust/confidence.py`) and surfacing them in the contract/UI is roadmap.
What ships now instead: every match factor carries a measured/inferred provenance tag,
and every inferred field's rationale carries an inline *"do not quote to client as fact"*
advisory. This keeps the tool from over-stating certainty to a client.
