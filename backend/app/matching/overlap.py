"""Commenter-overlap dedup — two creators who share a large fraction of the SAME
commenters reach the same people, so booking both double-serves that slice of budget.

HONESTY: this is COMMENTER overlap, not "audience overlap". Commenters are a MEASURED
proxy for audience (the subset who actually engaged), never a demographic claim — the
shared count and the Jaccard are real arithmetic on real commenter ids, and the leap to
"same audience" is inferred and labelled as such. Low overlap is never presented as proof
two creators are independent (we simply didn't observe shared commenters in the sample).
"""

from __future__ import annotations

from itertools import combinations

from app.raw import RawKOL
from app.schemas import OverlapPair

OVERLAP_MIN_COMMENTERS = 20   # both sides need a real commenter sample before comparing
OVERLAP_SURFACE_MIN = 0.15    # only surface pairs sharing >= 15% (Jaccard) — worth acting on


def _commenters(kol: RawKOL) -> set[str]:
    return {c.uid for c in kol.comments if c.uid}


def pairwise_overlap(candidates: list[RawKOL], max_pairs: int = 20) -> list[OverlapPair]:
    """Surface shortlist pairs with meaningful shared-commenter overlap, most-overlapping
    first. Pairs below the sample floor or the surface threshold are omitted (not asserted
    as independent)."""
    sets = [(k, _commenters(k)) for k in candidates]
    sets = [(k, s) for k, s in sets if len(s) >= OVERLAP_MIN_COMMENTERS]

    pairs: list[OverlapPair] = []
    for (ka, sa), (kb, sb) in combinations(sets, 2):
        shared = len(sa & sb)
        if shared == 0:
            continue
        union = len(sa | sb)
        jaccard = shared / union if union else 0.0
        if jaccard < OVERLAP_SURFACE_MIN:
            continue
        pairs.append(OverlapPair(
            a_id=ka.profile.author_id, a_handle=ka.profile.unique_id,
            b_id=kb.profile.author_id, b_handle=kb.profile.unique_id,
            shared=shared, jaccard=round(jaccard, 3),
            a_share=round(shared / len(sa), 3), b_share=round(shared / len(sb), 3),
            note="Shared commenters are measured; overlapping audience is an inferred proxy, "
                 "not a demographic match.",
        ))
    pairs.sort(key=lambda p: -p.jaccard)
    return pairs[:max_pairs]
