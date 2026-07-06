"""Commenter-overlap dedup: real Jaccard on shared commenter sets, withheld when thin,
symmetric, and — the key invariant — the seed overlap pool never trips a false pod flag."""

from __future__ import annotations

from app.matching.overlap import (
    OVERLAP_MIN_COMMENTERS,
    OVERLAP_SURFACE_MIN,
    pairwise_overlap,
)
from app.pipeline import build_shortlist
from app.sources.seed import SeedDatasetSource

from tests.conftest import make_comment, make_kol


def _kol_with_commenters(author_id: str, uids: list[str]):
    return make_kol(author_id=author_id,
                    comments=[make_comment(i, uid=u) for i, u in enumerate(uids)])


def test_jaccard_math_is_correct():
    a = _kol_with_commenters("A", [f"s{i}" for i in range(50)] + [f"a{i}" for i in range(50)])
    b = _kol_with_commenters("B", [f"s{i}" for i in range(50)] + [f"b{i}" for i in range(50)])
    pairs = pairwise_overlap([a, b])
    assert len(pairs) == 1
    p = pairs[0]
    assert p.shared == 50
    assert p.jaccard == round(50 / 150, 3)   # |A∩B|=50, |A∪B|=150
    assert p.a_share == round(50 / 100, 3)


def test_disjoint_creators_do_not_surface():
    a = _kol_with_commenters("A", [f"a{i}" for i in range(40)])
    b = _kol_with_commenters("B", [f"b{i}" for i in range(40)])
    assert pairwise_overlap([a, b]) == []


def test_below_sample_floor_is_withheld():
    few = OVERLAP_MIN_COMMENTERS - 1
    a = _kol_with_commenters("A", [f"s{i}" for i in range(few)])
    b = _kol_with_commenters("B", [f"s{i}" for i in range(few)])
    assert pairwise_overlap([a, b]) == []  # not enough sample to compare — not asserted


def test_below_surface_threshold_is_omitted():
    # 10 shared out of large disjoint sets -> jaccard well under OVERLAP_SURFACE_MIN
    a = _kol_with_commenters("A", [f"s{i}" for i in range(10)] + [f"a{i}" for i in range(90)])
    b = _kol_with_commenters("B", [f"s{i}" for i in range(10)] + [f"b{i}" for i in range(90)])
    assert 10 / 190 < OVERLAP_SURFACE_MIN
    assert pairwise_overlap([a, b]) == []


def test_note_frames_commenters_as_proxy():
    a = _kol_with_commenters("A", [f"s{i}" for i in range(50)] + [f"a{i}" for i in range(50)])
    b = _kol_with_commenters("B", [f"s{i}" for i in range(50)] + [f"b{i}" for i in range(50)])
    note = pairwise_overlap([a, b])[0].note.lower()
    assert "measured" in note and "inferred" in note


# ── seed integration: fires, but never as a pod ──────────────────────────────
def test_seed_overlap_surfaces_the_injected_pair():
    resp = build_shortlist(SeedDatasetSource())
    handles = {(p.a_handle, p.b_handle) for p in resp.commenter_overlap}
    flat = {h for pair in handles for h in pair}
    assert "@ploy.skinnote" in flat and "@bua.cleanbeauty" in flat


def test_seed_overlap_pool_never_trips_a_false_pod():
    resp = build_shortlist(SeedDatasetSource())
    for handle in ("@ploy.skinnote", "@bua.cleanbeauty"):
        k = next(x for x in resp.kols if x.handle == handle)
        assert k.risk.level == "clear"  # shared over only 2 creators (< REUSE_MIN_CREATORS)
        assert not any(s.label == "Comment pod" for s in k.risk.signals)


def test_overlap_serializes_camelcase():
    resp = build_shortlist(SeedDatasetSource())
    dumped = resp.model_dump(by_alias=True)
    assert "commenterOverlap" in dumped
    if dumped["commenterOverlap"]:
        assert {"aHandle", "bHandle", "jaccard", "aShare"} <= set(dumped["commenterOverlap"][0])
