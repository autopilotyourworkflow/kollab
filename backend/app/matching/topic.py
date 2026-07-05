"""Deterministic lexical topic scoring for live sources (no curated descriptor).

Transparent by design: the rationale names the exact overlapping terms. The LLM
rerank path refines the copy; it never replaces this auditability. Kept free of
source/pipeline imports so adapters can use it without cycles.
"""

from __future__ import annotations

import re

from app.raw import RawKOL
from app.schemas import ClientBrief

TOPIC_NO_OVERLAP = 10
TOPIC_BASE = 40
TOPIC_MAX = 95
_LATIN_WORD = re.compile(r"[a-z0-9]+")
_THAI_RUN = re.compile("[฀-๿]{3,}")  # Thai block; no word spaces, keep whole runs


def _brief_terms(brief: ClientBrief) -> set[str]:
    terms: set[str] = set()
    for chunk in (brief.category, *brief.pillars):
        low = chunk.lower()
        terms.update(w for w in _LATIN_WORD.findall(low) if len(w) > 3)
        terms.update(_THAI_RUN.findall(low))
    return terms


def keyword_topic_score(brief: ClientBrief, kol: RawKOL) -> tuple[int, str]:
    """Score 0-100 from caption/hashtag/bio overlap with the brief's category +
    pillars, with a rationale naming the matched terms (grounded, auditable)."""
    terms = _brief_terms(brief)
    if not terms:
        return TOPIC_NO_OVERLAP, "Brief carries no usable topic terms — verify topical fit manually."
    hay = " ".join(
        [kol.profile.signature,
         *(v.text for v in kol.videos),
         *(h for v in kol.videos for h in v.hashtags)]
    ).lower()
    hits = sorted(t for t in terms if t in hay)
    if not hits:
        return TOPIC_NO_OVERLAP, ("No caption/hashtag overlap with the brief's category or "
                                  "pillars — verify topical fit before outreach.")
    score = min(TOPIC_MAX, TOPIC_BASE + round(55 * len(hits) / len(terms)))
    shown = ", ".join(hits[:5])
    return score, (f"Captions/hashtags overlap {len(hits)}/{len(terms)} brief terms ({shown}) — "
                   f"deterministic lexical measure; the LLM rerank refines it.")
