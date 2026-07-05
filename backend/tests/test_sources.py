"""Seed determinism + reuse corpus, and the Apify JSON→RawKOL mappers."""

from __future__ import annotations

import pytest

from app.fraud.cohort import engagement_rate, median_views
from app.raw import parse_iso
from app.sources.apify import (
    ApifyAdapter,
    assemble_kol,
    parse_comment_item,
    parse_profile_item,
    parse_video_item,
)
from app.sources.seed import SeedDatasetSource


def test_seed_realized_er_matches_descriptor():
    # The generator median-normalizes engagement jitter, so the ER any curated
    # copy quotes (e.g. Mimin's 9.1%) IS the number the pipeline computes.
    s = SeedDatasetSource()
    k4 = next(k for k in s.fetch_candidates() if k.profile.author_id == "k4")
    assert engagement_rate(k4) == 9.1


def test_seed_is_deterministic():
    a = SeedDatasetSource().fetch_candidates()
    b = SeedDatasetSource().fetch_candidates()
    ka = next(k for k in a if k.profile.author_id == "k4")
    kb = next(k for k in b if k.profile.author_id == "k4")
    assert len(ka.comments) == len(kb.comments)
    assert engagement_rate(ka) == engagement_rate(kb)
    assert median_views(ka) == median_views(kb)


def test_seed_candidate_count_and_corpus():
    s = SeedDatasetSource()
    assert len(s.fetch_candidates()) == 11
    assert len(s.reuse_corpus()) > 0  # fillers + decoys
    assert s.presentation(s.fetch_candidates()[0]).id == "k1"


def test_seed_client_brief():
    brief = SeedDatasetSource().client_brief()
    assert brief.brand == "Glow Lab" and brief.pillars


def test_apify_profile_mapper():
    item = {"authorMeta": {"id": "123", "name": "creator", "fans": 5000, "verified": True,
                           "signature": "beauty", "region": "TH"}}
    p = parse_profile_item(item)
    assert p.author_id == "123" and p.unique_id == "@creator" and p.fans == 5000 and p.verified


def test_apify_video_and_comment_mappers():
    v = parse_video_item({"id": "v1", "stats": {"playCount": 1000, "diggCount": 50},
                          "createTimeISO": "2026-06-01T00:00:00Z", "text": "hi"})
    assert v.play_count == 1000 and v.digg_count == 50
    c = parse_comment_item({"cid": "c1", "uid": "u1", "uniqueId": "bob",
                            "text": "nice", "diggCount": 3, "replyCommentTotal": 1,
                            "createTimeISO": "2026-06-01T00:00:00Z"})
    assert c.uid == "u1" and c.unique_id == "@bob" and c.reply_comment_total == 1


def test_apify_assemble_kol():
    kol = assemble_kol(
        {"authorMeta": {"id": "1", "name": "c", "fans": 10}},
        [{"id": "v", "stats": {"playCount": 100}, "createTimeISO": "2026-06-01T00:00:00Z"}],
        [{"cid": "c", "uid": "u", "uniqueId": "x", "createTimeISO": "2026-06-01T00:00:00Z"}],
    )
    assert kol.profile.fans == 10 and len(kol.videos) == 1 and len(kol.comments) == 1


def test_apify_video_mapper_converts_epoch_create_time():
    # The tiktok-scraper actor sometimes emits only `createTime` (unix epoch seconds);
    # the mapper must yield parseable ISO, not a stringified epoch.
    v = parse_video_item({"id": "v1", "stats": {"playCount": 100}, "createTime": 1782950400})
    assert parse_iso(v.create_time_iso).year == 2026


def test_apify_assemble_drops_unstamped_items():
    # Items with no usable timestamp are dropped (every detector is time-based),
    # never passed downstream where parse_iso would crash.
    kol = assemble_kol(
        {"authorMeta": {"id": "1", "name": "c", "fans": 10}},
        [{"id": "v1", "stats": {"playCount": 100}},  # no timestamp -> dropped
         {"id": "v2", "stats": {"playCount": 100}, "createTimeISO": "2026-06-01T00:00:00Z"}],
        [{"cid": "c1", "uid": "u", "uniqueId": "x"}],  # no timestamp -> dropped
    )
    assert [v.video_id for v in kol.videos] == ["v2"]
    assert kol.comments == []




def test_apify_requires_token():
    from tests.test_live_paths import BRIEF

    with pytest.raises(RuntimeError, match="APIFY_TOKEN"):
        ApifyAdapter(token=None).fetch_candidates(brief=BRIEF)
