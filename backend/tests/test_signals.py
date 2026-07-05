"""Each structural detector, on synthetic pod vs clean data."""

from __future__ import annotations

from datetime import timedelta

from app.fraud.cohort import build_cohorts
from app.fraud.signals import (
    boosted_post,
    build_commenter_index,
    cadence_dormancy,
    comment_burst_timing,
    commenter_reuse_across_creators,
    duplicate_comment_text,
    er_vs_cohort_outlier,
    thin_commenter_profiles,
    view_to_follower_collapse,
)
from app.raw import RawComment, RawKOL, RawProfile, RawVideo
from tests.conftest import BASE, iso, make_cohort, make_comment, make_kol


def _kol_with_comments(comments, author_id="t", **kw):
    k = make_kol(author_id=author_id, comments=comments, **kw)
    return k


# ── commenter reuse (LEAD signal) ───────────────────────────────────────────
def _pod_creators(n_creators=4, pool_size=25):
    pool = [f"pod{i}" for i in range(pool_size)]
    creators = []
    for c in range(n_creators):
        comments = [make_comment(i, uid=uid, dt=BASE - timedelta(days=i % 14))
                    for i, uid in enumerate(pool * 2)]
        creators.append(_kol_with_comments(comments, author_id=f"cre{c}"))
    return creators, pool


def test_commenter_reuse_fires_on_cross_creator_pod():
    creators, _ = _pod_creators(n_creators=4, pool_size=25)
    index = build_commenter_index(creators)
    res = commenter_reuse_across_creators(creators[0], index)
    assert res.fired and res.level == "high" and res.label == "Comment pod"


def test_commenter_reuse_silent_when_accounts_not_shared_widely():
    creators, _ = _pod_creators(n_creators=2, pool_size=25)  # only 2 creators (<3)
    index = build_commenter_index(creators)
    assert commenter_reuse_across_creators(creators[0], index).fired is False


# ── comment burst timing ────────────────────────────────────────────────────
def test_comment_burst_fires():
    comments = [make_comment(i, uid=f"b{i}", dt=BASE + timedelta(seconds=i * 3))
                for i in range(30)]  # 30 comments in ~90s
    assert comment_burst_timing(_kol_with_comments(comments)).fired is True


def test_comment_burst_silent_when_spread_out():
    comments = [make_comment(i, uid=f"b{i}", dt=BASE + timedelta(hours=i))
                for i in range(30)]
    assert comment_burst_timing(_kol_with_comments(comments)).fired is False


# ── duplicate text ──────────────────────────────────────────────────────────
def _raw_comment(i, text, uid=None):
    return RawComment(cid=f"c{i}", uid=uid or f"u{i}", unique_id=f"@u{i}", text=text,
                      create_time_iso=iso(BASE), video_web_url="v")


def test_duplicate_text_fires_on_templated_pod():
    comments = [_raw_comment(i, "ปังมากตัวแม่") for i in range(50)]
    assert duplicate_comment_text(_kol_with_comments(comments)).fired is True


def test_duplicate_text_silent_on_varied():
    comments = [_raw_comment(i, f"comment number {i}") for i in range(50)]
    assert duplicate_comment_text(_kol_with_comments(comments)).fired is False


# ── thin commenters ─────────────────────────────────────────────────────────
def test_thin_commenters_fires():
    comments = [make_comment(i, uid=f"x{i}", posts=1, thai=False) for i in range(21)]
    comments += [make_comment(i + 100, uid=f"y{i}", posts=50, thai=True) for i in range(9)]
    assert thin_commenter_profiles(_kol_with_comments(comments)).fired is True


def test_thin_commenters_silent_when_healthy():
    comments = [make_comment(i, uid=f"z{i}", posts=40, thai=True) for i in range(30)]
    assert thin_commenter_profiles(_kol_with_comments(comments)).fired is False


def test_thin_commenters_withheld_below_min_sample():
    comments = [make_comment(i, uid=f"z{i}", posts=1, thai=False) for i in range(10)]
    assert thin_commenter_profiles(_kol_with_comments(comments)).fired is False


# ── ER vs cohort outlier (n>=15 gate) ───────────────────────────────────────
def test_er_outlier_fires_with_valid_cohort():
    cohort = build_cohorts(make_cohort(20, er_base=6.0))["beauty:micro"]
    hot = make_kol(author_id="hot", median_views=50000, er=40.0)
    res = er_vs_cohort_outlier(hot, cohort)
    assert res.fired and res.level in ("high", "medium")


def test_er_outlier_withheld_when_cohort_thin():
    cohort = build_cohorts(make_cohort(8))["beauty:micro"]
    hot = make_kol(author_id="hot", er=40.0)
    res = er_vs_cohort_outlier(hot, cohort)
    assert res.fired is False and res.withheld is True


# ── view-to-follower collapse ───────────────────────────────────────────────
def test_view_to_follower_collapse_fires():
    cohort = build_cohorts(make_cohort(20))["beauty:micro"]
    bought = make_kol(author_id="b", followers=120000, median_views=2900)
    res = view_to_follower_collapse(bought, cohort)
    assert res.fired and res.level == "high" and res.label == "Bought followers"


def test_view_to_follower_silent_when_healthy():
    cohort = build_cohorts(make_cohort(20))["beauty:micro"]
    healthy = make_kol(author_id="h", followers=50000, median_views=45000)
    assert view_to_follower_collapse(healthy, cohort).fired is False


def test_view_to_follower_withheld_without_videos():
    # Zero videos (private account / failed scrape) is absence of evidence —
    # never assert "Bought followers" from it.
    cohort = build_cohorts(make_cohort(20))["beauty:micro"]
    empty = make_kol(author_id="e", followers=50000, n_videos=0)
    res = view_to_follower_collapse(empty, cohort)
    assert res.fired is False and res.withheld is True


def test_view_to_follower_withheld_below_min_video_sample():
    cohort = build_cohorts(make_cohort(20))["beauty:micro"]
    sparse = make_kol(author_id="s", followers=500000, median_views=100, n_videos=3)
    res = view_to_follower_collapse(sparse, cohort)
    assert res.fired is False and res.withheld is True


# ── boosted post (self-baseline) ────────────────────────────────────────────
def _kol_with_plays(plays):
    vids = [RawVideo(video_id=f"v{i}", play_count=p, create_time_iso=iso(BASE + timedelta(days=i)))
            for i, p in enumerate(plays)]
    return RawKOL(profile=RawProfile(author_id="v", unique_id="@v", nickname="v", fans=100000),
                  videos=vids)


def test_boosted_high_on_big_spike():
    plays = [50000] * 17 + [300000, 310000, 305000]  # ~6x recent spike
    res = boosted_post(_kol_with_plays(plays))
    assert res.fired and res.level == "high" and res.label == "View spike"


def test_boosted_medium_on_modest_spike():
    plays = [50000] * 18 + [110000, 105000]  # ~2.1x
    res = boosted_post(_kol_with_plays(plays))
    assert res.fired and res.level == "medium" and res.label == "Possible boosted post"


def test_boosted_silent_when_flat():
    plays = [50000 + (i % 3) * 2000 for i in range(20)]
    assert boosted_post(_kol_with_plays(plays)).fired is False


# ── cadence / dormancy ──────────────────────────────────────────────────────
def test_dormancy_fires_when_stale():
    kol = make_kol(author_id="d", newest=BASE - timedelta(days=20))
    assert cadence_dormancy(kol, now=BASE).fired is True


def test_dormancy_silent_when_active():
    kol = make_kol(author_id="d", newest=BASE - timedelta(days=2))
    assert cadence_dormancy(kol, now=BASE).fired is False
