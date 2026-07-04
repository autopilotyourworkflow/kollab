"""Shared synthetic-data builders + cached seed pipeline for the test suite."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.pipeline import build_shortlist
from app.raw import RawComment, RawKOL, RawProfile, RawVideo
from app.sources.seed import SeedDatasetSource

BASE = datetime(2026, 6, 28, 9, 0, 0, tzinfo=timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def make_comment(i=0, uid=None, text="ปกติดีมากค่ะ", dt=None, digg=3, reply=1,
                 url="https://v/1", posts=None, thai=None) -> RawComment:
    return RawComment(
        cid=f"c{i}", uid=uid or f"u{i}", unique_id=f"@{uid or ('u' + str(i))}",
        text=f"{text} {i}", digg_count=digg, reply_comment_total=reply,
        create_time_iso=iso(dt or BASE), video_web_url=url,
        commenter_post_count=posts, commenter_has_thai_history=thai,
    )


def make_kol(author_id="c", followers=40000, median_views=45000, er=6.0, n_videos=20,
             comments=None, vertical="beauty", tier="micro", newest=None) -> RawKOL:
    newest = newest or BASE
    vids = []
    for i in range(n_videos):
        plays = median_views
        eng = int(plays * er / 100)
        vids.append(RawVideo(
            video_id=f"{author_id}_v{i}", play_count=plays,
            digg_count=int(eng * 0.9), comment_count=int(eng * 0.07),
            share_count=int(eng * 0.03),
            create_time_iso=iso(newest - timedelta(days=i)),
        ))
    return RawKOL(
        profile=RawProfile(author_id=author_id, unique_id=f"@{author_id}",
                           nickname=author_id, fans=followers, region="Bangkok"),
        videos=vids, comments=comments if comments is not None else
        [make_comment(i, uid=f"{author_id}_u{i}", dt=newest - timedelta(hours=i))
         for i in range(30)],
        vertical=vertical, tier=tier,
    )


def make_cohort(n, vertical="beauty", tier="micro", er_base=6.0) -> list[RawKOL]:
    """n clean peers with slightly varied ER to form a valid distribution."""
    return [
        make_kol(author_id=f"peer{i}", followers=40000 + i * 500,
                 median_views=45000 + i * 400, er=er_base + (i % 5) * 0.3,
                 vertical=vertical, tier=tier)
        for i in range(n)
    ]


@pytest.fixture(scope="session")
def seed_source() -> SeedDatasetSource:
    return SeedDatasetSource()


@pytest.fixture(scope="session")
def shortlist(seed_source):
    return build_shortlist(seed_source)


@pytest.fixture(scope="session")
def by_id(shortlist):
    return {k.id: k for k in shortlist.kols}
