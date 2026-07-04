# Eval

A small, honest harness that scores the pipeline's ranking against human include/exclude
labels. It is **directional, not a benchmark** — 11 KOLs, one brief, provisional labels —
and the doc says so everywhere the numbers appear, because a take-home eval that
pretends to be MLPerf is worse than no eval.

## Method

`backend/eval/run_eval.py` runs the real pipeline offline (`SeedDatasetSource`, zero
API keys), takes the fit-score ranking exactly as the product emits it (nothing
excluded, ties keep fixture order), and compares it to the labels in
`backend/eval/labels.glow-lab.json`:

- **precision@k** for k ∈ {3, 5, 7} — of the top-k, how many a human labeled include;
- **recall@7** — of all labeled-include KOLs, how many made the top 7;
- **the wrong case** — the single worst label/ranking disagreement: the labeled-exclude
  KOL ranked highest or the labeled-include KOL ranked lowest, whichever causes more
  inversions. When there are no inversions at all, the harness deliberately degrades to
  reporting the thinnest margin at the include/exclude boundary instead of declaring
  victory.

Results are written to `backend/eval/results.json` and printed as text.

## The rubric, in one paragraph

`backend/eval/rubric.md` defines include/exclude per **(brief, KOL) pair** — "include"
means "belongs on the shortlist we'd hand this brand," not "good creator." Applied in
order: high-risk authenticity signals are a hard exclude (the engagement being paid for
doesn't exist); brand-safety and conflict gates exclude until a human clears them; topic
fit distinguishes core / adjacent-with-real-overlap (include-leaning) from diluted
broad-lifestyle relevance (exclude for a topic-authority brief, whatever the reach);
dormancy excludes, a slowing cadence is only a noted knock; and audience skew is
**advisory only** — it is inferred, not measured, so it never decides a label, mirroring
its literal 0.0 ranking weight in the pipeline. Every label carries a reason citing the
driving data point, and judgment calls must name their flip condition.

## Numbers (as of this commit)

Run on the 11 glow-lab fixtures, 7 labeled include / 4 exclude:

| metric      | value |
| ----------- | ----- |
| precision@3 | 1.0   |
| precision@5 | 1.0   |
| precision@7 | 1.0   |
| recall@7    | 1.0   |

Read those 1.0s with the suspicion they deserve. The seed fixtures were engineered so
the detectors reproduce the curated demo story, and the current labels were drafted
from **that same story** — so agreement is partly circular. What the run genuinely
demonstrates is narrower: the wiring works, the fraud-flagged KOLs (k4 comment pod, k6
bought followers) land at the bottom of the ranking despite having the biggest follower
counts in the set, and the harness will catch a regression if a scoring change reorders
the boundary. It does not demonstrate real-world precision. Also: with n=11, one label
flip moves precision@3 by 33 points — every number here is a step function.

## The wrong case: k8 (@gigi.beautypro)

There is no ranking inversion in this run — every labeled include outranks every
labeled exclude — so the harness reports the closest call instead: **k8, labeled
exclude, ranked 8 with fit 76/100**, only 10 points below the last include (k11, fit
86).

The disagreement is structural, and worth understanding because it will recur on live
data:

- The **label** excludes k8 under the rubric: a medium "possible boosted post" signal
  (2 posts at 2.1× her own median) stacked on an unresolved conflict flag (paid promo
  for a competing skincare brand 18 days ago), on adjacent-not-core topic fit. Two open
  caveats, exclude until a human clears them.
- The **score** gives her 76 because `fit_score` is a soft ranking over
  topic/authenticity/recency, and the conflict gate is deliberately **not** a ranking
  factor — gates route to human review; they are not penalties (see
  `docs/ARCHITECTURE.md`). A medium signal only moderately dents authenticity.

So the score answers "how good a fit, fraud-adjusted?" while the label answers "would
we hand this to the brand today?" — two different questions that happen to agree on
ordering here, by 10 points. k8 is also exactly where a second independent rater would
most plausibly flip a label (a rater who trusts the exclusivity check to clear would
include her), which is why she's the case to watch when the labels are re-drawn.

## Honesty notes

- **Labeled solo, and worse.** The labels file says it plainly: *"provisional —
  auto-drafted from the curated fixture story, TO BE RE-LABELED by Beam."* One rater, no
  inter-rater agreement measured yet. The rubric describes the upgrade path: independent
  double-labeling, percent agreement + Cohen's kappa, adjudicate, fold the winning
  rationale back into the rubric as a named rule.
- **Circularity is baked into this first run.** Fixtures engineered to tell a story,
  labels drafted from the story. The harness is built so the *next* run is the one that
  counts.
- **The next run:** re-run on the live seed pull (**2 brands × 20 KOLs**) with labels
  drawn independently — from the raw profiles and the rubric, before looking at
  pipeline scores. That is the first number worth quoting.

## How to re-run

Offline, zero API keys, deterministic (seeded RNG + dataset `as_of` date):

```bash
cd backend && ./.venv/Scripts/python.exe eval/run_eval.py     # Windows
cd backend && .venv/bin/python eval/run_eval.py               # macOS / Linux
```

Prints the ranking-vs-labels table, the metrics, and the wrong case; rewrites
`backend/eval/results.json`. To evaluate a different brief, add a
`labels.<brand>.json` following the same shape and point `LABELS_PATH` at it. After any
rubric change, re-run and commit the new `results.json` with the rubric diff so metric
movement stays attributable.
