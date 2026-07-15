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
from app.trust.provenance import PROVENANCE_BY_FACTOR, advisory_tag

WEIGHTS = {"topic": 0.45, "authenticity": 0.35, "recency": 0.20, "audience": 0.0}


def _recency_score(last_posted_days_ago: int) -> int:
    return max(30, min(100, 100 - 5 * last_posted_days_ago))


#: The comment-authenticity (pod) detectors. "No pod signatures" may only be claimed when
#: these actually ran — a withheld detector checked nothing.
POD_CHECKS = ("commenter_reuse", "comment_burst", "duplicate_text")


def _auth_rationale(kol: RawKOL, vet: VetResult) -> str:
    er = engagement_rate(kol)
    fired = [r for r in vet.raw_signals if r.fired]
    if not fired:
        by_name = {r.name: r for r in vet.raw_signals}

        # ER clause — never claim a peer comparison that was withheld (min-cohort rule).
        er_check = by_name.get("er_outlier")
        if er_check is not None and er_check.withheld:
            er_clause = (f"ER {er}% measured; peer-band comparison withheld "
                         f"({er_check.measured_against} — below the minimum baseline)")
        else:
            er_clause = f"ER {er}% sits in the healthy band for peers"

        # Pod clause — same rule one level up: only assert "no pod signatures" for the
        # detectors that actually ran. Saying it when the sample was empty would report
        # absence of data as a clean result, which is what the withhold rule forbids.
        pod = [by_name[n] for n in POD_CHECKS if n in by_name]
        ran = [r for r in pod if not r.withheld]
        if pod and not ran:
            pod_clause = "comment-authenticity checks withheld — no comment sample to judge"
        elif len(ran) < len(pod):
            pod_clause = (f"no pod signatures in the {len(ran)} of {len(pod)} comment checks "
                          f"that could run; the rest withheld for lack of a sample")
        else:
            pod_clause = "no pod signatures, comment authenticity looks organic"

        # Name anything else we could not judge, rather than letting silence imply "clean".
        other = sorted(r.name for r in vet.raw_signals
                       if r.withheld and r.name not in POD_CHECKS and r.name != "er_outlier")
        tail = f". Withheld for lack of sample: {', '.join(other)}" if other else ""
        return f"{er_clause}; {pod_clause}{tail}."
    if all(r.name == "dormancy" for r in fired):
        # Dormancy is a cadence problem, not engagement inauthenticity — don't
        # wrap it in the "not what it looks like" fraud template.
        return f"No engagement-authenticity red flags; the only concern is cadence — {fired[0].detail.lower()}."
    lead = fired[0]
    return f"ER {er}% is not what it looks like — {lead.label.lower()}: {lead.detail}. Real engagement is lower."


def build_factors(
    kol: RawKOL, pres: Presentation, vet: VetResult, last_posted_days_ago: int
) -> list[MatchFactor]:
    topic = int(pres.topic_score)
    auth = int(vet.authenticity_score)
    recency = _recency_score(last_posted_days_ago)
    audience = int(pres.audience_score)
    audience_rationale = pres.audience_rationale or "Inferred from comment-language + content skew."
    advisory = advisory_tag(PROVENANCE_BY_FACTOR["audience"])
    if advisory:
        audience_rationale = f"{audience_rationale} ({advisory}.)"
    return [
        MatchFactor(key="topic", label="Topic fit", score=topic, weight=WEIGHTS["topic"],
                    provenance=PROVENANCE_BY_FACTOR["topic"],
                    rationale=pres.topic_rationale
                    or f"{pres.category} content aligns with the brand's education/authenticity pillars."),
        MatchFactor(key="authenticity", label="Engagement authenticity", score=auth,
                    weight=WEIGHTS["authenticity"], provenance=PROVENANCE_BY_FACTOR["authenticity"],
                    rationale=_auth_rationale(kol, vet)),
        MatchFactor(key="recency", label="Recency & cadence", score=recency,
                    weight=WEIGHTS["recency"], provenance=PROVENANCE_BY_FACTOR["recency"],
                    rationale=f"Last post {last_posted_days_ago} day(s) ago."),
        MatchFactor(key="audience", label="Audience (advisory)", score=audience,
                    weight=WEIGHTS["audience"], provenance=PROVENANCE_BY_FACTOR["audience"],
                    rationale=audience_rationale),
    ]


def fit_score(factors: list[MatchFactor]) -> int:
    """Normalized weighted sum of the soft (ranking) factors. Audience is excluded
    because its weight is 0.0."""
    total_w = sum(f.weight for f in factors)
    if total_w <= 0:
        return 0
    return round(sum(f.score * f.weight for f in factors) / total_w)
