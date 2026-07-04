"""Deterministic factor scoring + fit score.

Factors mirror frontend/src/lib/types.ts:
  - topic         weight 0.45  (retrieval relevance; precomputed in fixtures mode)
  - authenticity  weight 0.35  (from the fraud layer)
  - recency       weight 0.20  (cadence/dormancy)
  - audience      weight 0.00  (inferred, ADVISORY, strictly non-ranking)

Final fit = normalized weighted sum of the soft factors. Audience carries weight
literally 0.0 and renders as advisory only — so the "what we cannot detect" limit
and the score tell exactly one story.
"""

from __future__ import annotations

from app.fraud.cohort import engagement_rate
from app.fraud.vet import VetResult
from app.raw import RawKOL
from app.schemas import MatchFactor
from app.sources.base import Presentation

WEIGHTS = {"topic": 0.45, "authenticity": 0.35, "recency": 0.20, "audience": 0.0}


def _recency_score(last_posted_days_ago: int) -> int:
    return max(30, min(100, 100 - 5 * last_posted_days_ago))


def _auth_rationale(kol: RawKOL, vet: VetResult) -> str:
    er = engagement_rate(kol)
    fired = [r for r in vet.raw_signals if r.fired]
    if not fired:
        return f"ER {er}% sits in the healthy band for peers; no pod signatures, comment authenticity looks organic."
    lead = fired[0]
    return f"ER {er}% is not what it looks like — {lead.label.lower()}: {lead.detail}. Real engagement is lower."


def build_factors(
    kol: RawKOL, pres: Presentation, vet: VetResult, last_posted_days_ago: int
) -> list[MatchFactor]:
    topic = int(pres.topic_score)
    auth = int(vet.authenticity_score)
    recency = _recency_score(last_posted_days_ago)
    audience = int(pres.audience_score)
    return [
        MatchFactor(key="topic", label="Topic fit", score=topic, weight=WEIGHTS["topic"],
                    provenance="measured",
                    rationale=pres.topic_rationale
                    or f"{pres.category} content aligns with the brand's education/authenticity pillars."),
        MatchFactor(key="authenticity", label="Engagement authenticity", score=auth,
                    weight=WEIGHTS["authenticity"], provenance="measured",
                    rationale=_auth_rationale(kol, vet)),
        MatchFactor(key="recency", label="Recency & cadence", score=recency,
                    weight=WEIGHTS["recency"], provenance="measured",
                    rationale=f"Last post {last_posted_days_ago} day(s) ago."),
        MatchFactor(key="audience", label="Audience (advisory)", score=audience,
                    weight=WEIGHTS["audience"], provenance="inferred",
                    rationale=pres.audience_rationale
                    or "Inferred from comment-language + content skew — not measured; advisory only."),
    ]


def fit_score(factors: list[MatchFactor]) -> int:
    """Normalized weighted sum of the soft (ranking) factors. Audience is excluded
    because its weight is 0.0."""
    total_w = sum(f.weight for f in factors)
    if total_w <= 0:
        return 0
    return round(sum(f.score * f.weight for f in factors) / total_w)
