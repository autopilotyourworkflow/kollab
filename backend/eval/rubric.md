# Labeling rubric — include / exclude for a brand brief

This rubric defines how a human labels each (brief, KOL) pair as **include** (belongs on
the shortlist we'd hand the brand) or **exclude** (does not). The labels are the ground
truth `run_eval.py` scores the pipeline's ranking against.

Honest framing up front: this is a **directional harness, not a benchmark**. The current
label set was drafted solo, from the same curated fixture story the seed data encodes, so
agreement between labels and pipeline is partly baked in. The harness exists so that when
the labels are re-drawn independently (and on live data), the numbers mean something and
regressions are visible.

## The unit of labeling

One label per KOL **per brief**. "Include" is not "good creator" — it is "right for this
brand's brief." The same KOL can be include for an awareness-volume brief and exclude for
a topic-authority brief (k10 is exactly this case).

## Decision procedure (apply in order)

### 1. Authenticity — hard gate

- **High-risk fraud signals** (comment pod, bought followers, thin commenters at scale):
  **exclude**. The engagement the brand would be paying for does not exist. No amount of
  topic fit buys this back.
- **Medium signals** (e.g. a possible boosted-post pattern): judgment call, not an
  auto-exclude. Ask: is the underlying organic baseline still adequate for the brief, and
  is there a second caveat stacked on top? One medium signal alone → lean include with a
  note; a medium signal **plus** another open caveat (conflict, off-core topic) → exclude
  until a human clears it.

Note the deliberate asymmetry with the product: the pipeline *flags and routes to human
review* — it never auto-excludes. The label, by contrast, records the decision that human
review should reach. That gap is the point of the eval.

### 2. Gates — brand safety and conflict

- **Brand-safety flag**: exclude.
- **Conflict flag** (recent competing-brand promo): **exclude until cleared**. If the
  exclusivity check would plausibly clear it, say so in the reason — that's the flip
  condition a second rater might disagree on.

### 3. Topic fit — core / adjacent / diluted

- **Core** (the brief's pillars are the creator's main content): include-leaning.
- **Adjacent with real overlap** (e.g. GRWM with skincare woven in, clean-beauty next to
  gentle-actives): include-leaning — the overlap must be visible in recent content, not
  claimed in the bio.
- **Diluted** (broad lifestyle where the category appears occasionally): exclude for a
  topic-authority brief, however large the reach. Include only if the brief explicitly
  prioritizes awareness volume — and say so in the reason.

### 4. Recency — active or not

- Dormant or clearly winding down: exclude.
- A slowing cadence (a few extra days between posts) is a knock recorded in the reason,
  not a kill.

### 5. Audience — advisory only

Audience skew is **inferred, not measured** (see `docs/ETHICS.md`), so it never decides a
label on its own. It may appear in the reason as color ("skews older than target") but an
otherwise-include KOL is not excluded on inferred demographics, and vice versa. This
mirrors the pipeline, where audience carries ranking weight 0.0.

## Writing the reason field

Every label carries a `reason` that must:

- cite the concrete data point that drove the call (a signal, a gate, a content pattern);
- for judgment calls, name the **flip condition** — what fact or brief change would
  reverse the label. Borderline cases without a flip condition are under-specified.

## Solo now — how this scales to multiple raters

Current state: one labeler (and worse, labels auto-drafted from the fixture story —
marked provisional in `labels.glow-lab.json`, to be re-labeled by Beam by hand).

To make the labels defensible:

1. **Independent double-labeling.** A second rater labels the same KOLs from the raw
   profiles + this rubric, without seeing the first rater's labels or the pipeline's
   scores.
2. **Measure agreement.** With n this small, report raw percent agreement per brief and
   Cohen's kappa across briefs; kappa below ~0.6 means the rubric, not the raters, is the
   problem.
3. **Adjudicate and fold back.** Disagreements are discussed, the winning rationale is
   written into this rubric as a named rule (the way §1 and §3 already encode k8 and
   k10), and the label is updated. Disagreement cases become the rubric's regression
   examples.
4. **Re-baseline.** After any rubric change, re-run `run_eval.py` and commit the new
   `results.json` alongside the rubric diff, so metric movement is attributable.

## Known limits

- 11 KOLs, one brief, one vertical, one market. Precision@k on n=11 moves in steps of
  1/k — a single label flip swings P@3 by 33 points. Treat every number as directional.
- The fixture data was engineered to make the pipeline's detectors fire correctly, and
  these labels were drafted from that same story. The real test is the planned re-run on
  the live seed pull (2 brands × 20 KOLs) with labels drawn independently first.
