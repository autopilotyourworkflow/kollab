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


# ── Absence of evidence must WITHHOLD, never report "clear" ─────────────────
# Regression guard for the honesty rule the module states in its own constants
# block (VTF_MIN_VIDEOS) and in vet.to_checks(): a detector that could not run
# must say so. Reporting "No signal — checked and clear." for a sample that was
# never judged is the exact failure this module exists to prevent. Every case
# below returned withheld=False before the fix, and none of the 273 tests caught
# it — the suite only ever asserted fired/not-fired, never "did the check run?".

def test_commenter_reuse_withholds_when_no_comments():
    kol = _kol_with_comments([])
    r = commenter_reuse_across_creators(kol, build_commenter_index([kol]))
    assert r.withheld is True and r.fired is False
    assert r.measured_against  # must name what was (not) sampled


def test_comment_burst_withholds_when_no_comments():
    r = comment_burst_timing(_kol_with_comments([]))
    assert r.withheld is True and r.fired is False


def test_duplicate_text_withholds_when_no_comments():
    r = duplicate_comment_text(_kol_with_comments([]))
    assert r.withheld is True and r.fired is False


def test_duplicate_text_withholds_when_sample_has_no_text():
    # make_comment() always appends an index, so build blank-text comments directly.
    blank = [RawComment(cid=f"c{i}", uid=f"u{i}", unique_id=f"@u{i}", text="   ",
                        digg_count=0, reply_comment_total=0, create_time_iso=iso(BASE),
                        video_web_url="https://v/1") for i in range(5)]
    r = duplicate_comment_text(_kol_with_comments(blank))
    assert r.withheld is True and r.fired is False


def test_thin_commenters_withholds_when_profiles_absent():
    """The LIVE case: the Apify comment payload carries no commenter profile fields,
    so `sampled` is empty and the bought-audience check cannot run at all."""
    kol = _kol_with_comments([make_comment(i, posts=None) for i in range(40)])
    r = thin_commenter_profiles(kol)
    assert r.withheld is True and r.fired is False
    assert "withheld" in r.detail.lower()


def test_boosted_post_withholds_below_self_baseline_minimum():
    """The LIVE case: a search feed surfaces only a few videos per creator, so there
    is no trailing baseline to compare recent reach against."""
    r = boosted_post(make_kol(n_videos=4))
    assert r.withheld is True and r.fired is False


def test_boosted_post_withholds_when_no_view_baseline():
    r = boosted_post(make_kol(n_videos=12, median_views=0))
    assert r.withheld is True and r.fired is False


def test_dormancy_withholds_when_no_videos():
    kol = make_kol(n_videos=0)
    r = cadence_dormancy(kol, BASE)
    assert r.withheld is True and r.fired is False


def test_sufficient_sample_still_reports_clear_not_withheld():
    """The fix must not turn every clean result into a withhold — a check that RAN
    and found nothing is still an honest 'clear'."""
    kol = make_kol(n_videos=20)
    assert boosted_post(kol).withheld is False
    assert cadence_dormancy(kol, BASE).withheld is False
    clean = _kol_with_comments([make_comment(i, uid=f"real{i}", posts=50, thai=True)
                                for i in range(30)])
    assert duplicate_comment_text(clean).withheld is False
    assert comment_burst_timing(clean).withheld is False
    assert thin_commenter_profiles(clean).withheld is False
