"""Structural fraud detectors — pure functions, each independently testable.

Ordered by durability (PLAN.md): the structural signals below are the durable
part; a Thai phrase lexicon (see thai_lexicon) is only a tiebreaker/explainability
aid because pod farms rotate wording monthly. Every detector returns a SignalResult
that names the triggered pattern and the baseline it was measured against.

Thresholds are named constants with a cited rationale rather than hand-picked in
line — so a reviewer can audit and a Thai account manager can retune them.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from app.fraud.cohort import (
    CohortStats,
    engagement_rate,
    median_excluding_outliers,
    median_views,
    view_to_follower,
)
from app.raw import RawComment, RawKOL, parse_iso

# ── Calibrated thresholds (documented, retunable) ───────────────────────────
# Reuse: a "pod" is a cluster of accounts that comment across many *unrelated*
# creators. Commercial audits (HypeAuditor/Modash-style) treat cross-account
# reuse as the hardest-to-fake authenticity signal.
REUSE_MIN_CREATORS = 3       # commenter must hit >= this many creators to count as reused
POD_MIN_ACCOUNTS = 20        # cluster size that constitutes a pod
POD_MIN_SHARE = 0.15         # pod accounts must be >= this share of the KOL's comments

# Burst: bot drops post many comments in a tight window, then go silent.
BURST_WINDOW_S = 120
BURST_MIN_COMMENTS = 25

# Duplicate text: templated pod comments repeat near-identical strings.
DUP_MIN_REPEATS = 3
DUP_MIN_SHARE = 0.30

# Thin commenters: bought audiences are empty/low-history accounts.
THIN_MIN_SAMPLE = 20
THIN_MIN_SHARE = 0.50
THIN_MAX_POSTS = 5

# View-to-follower: a bought follower base makes reach collapse vs the count.
VTF_ABS_FLOOR = 0.05         # <5% of followers ever view = pathological
VTF_COLLAPSE_FRAC = 0.25     # or <25% of the peer-median ratio = a real collapse
                             # (merely below p10 is NOT fraud — 10% of clean peers are)

# Self-baseline boost: a post far above the creator's own trailing median.
BOOST_MED_MULT = 2.0         # possible boosted post (verify organic baseline)
BOOST_HIGH_MULT = 4.0        # view spike (bought/atypical reach)
BOOST_RECENT_N = 5

# Dormancy.
DORMANT_DAYS = 14


@dataclass(frozen=True)
class SignalResult:
    name: str                # internal id
    fired: bool
    level: str               # "high" | "medium" | "clear"
    label: str               # UI-facing, e.g. "Comment pod"
    detail: str
    measured_against: str
    penalty: float = 0.0     # 0..1 authenticity penalty when fired
    withheld: bool = False   # cohort too thin: signal deliberately not asserted
    family: str = ""         # groups related structural signals (e.g. "pod")
    metrics: dict = field(default_factory=dict)


def _clear(name: str) -> SignalResult:
    return SignalResult(name=name, fired=False, level="clear", label="", detail="", measured_against="")


# ── Cross-creator commenter reuse (LEAD structural signal) ──────────────────
def build_commenter_index(corpus: list[RawKOL]) -> dict[str, set[str]]:
    """Map commenter uid -> set of creator ids they've commented on."""
    index: dict[str, set[str]] = defaultdict(set)
    for kol in corpus:
        cid = kol.profile.author_id
        for c in kol.comments:
            index[c.uid].add(cid)
    return index


def commenter_reuse_across_creators(
    kol: RawKOL, commenter_index: dict[str, set[str]]
) -> SignalResult:
    """Pod signature: a cluster of accounts that comment across many unrelated
    creators and make up a meaningful share of THIS creator's comments."""
    comments = kol.comments
    if not comments:
        return _clear("commenter_reuse")

    pod_accounts = {
        c.uid
        for c in comments
        if len(commenter_index.get(c.uid, set())) >= REUSE_MIN_CREATORS
    }
    pod_comments = [c for c in comments if c.uid in pod_accounts]
    share = len(pod_comments) / len(comments)

    if len(pod_accounts) >= POD_MIN_ACCOUNTS and share >= POD_MIN_SHARE:
        max_creators = max(len(commenter_index[u]) for u in pod_accounts)
        window_days = _span_days(pod_comments)
        return SignalResult(
            name="commenter_reuse",
            fired=True,
            level="high",
            label="Comment pod",
            detail=(
                f"{len(pod_accounts)} accounts post near-identical comments across "
                f"{max_creators} unrelated creators within {window_days} days"
            ),
            measured_against=f"shared-commenter graph over {len(comments)} sampled comments",
            penalty=0.85,
            family="pod",
            metrics={"pod_accounts": len(pod_accounts), "share": round(share, 3)},
        )
    return _clear("commenter_reuse")


# ── Comment-burst timing (within-creator temporal) ──────────────────────────
def comment_burst_timing(kol: RawKOL) -> SignalResult:
    """Bot drop: many comments inside a short window on a single video."""
    by_video: dict[str, list[datetime]] = defaultdict(list)
    for c in kol.comments:
        by_video[c.video_web_url].append(parse_iso(c.create_time_iso))

    worst = 0
    for times in by_video.values():
        worst = max(worst, _max_in_window(sorted(times), BURST_WINDOW_S))

    if worst >= BURST_MIN_COMMENTS:
        return SignalResult(
            name="comment_burst",
            fired=True,
            level="high",
            label="Comment burst",
            detail=f"{worst} comments within {BURST_WINDOW_S}s on one video, then silence",
            measured_against="comment timestamps on the spiking video",
            penalty=0.6,
            family="pod",
            metrics={"burst": worst},
        )
    return _clear("comment_burst")


# ── Duplicate comment text (within-creator content) ─────────────────────────
_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS.sub(" ", text.strip().lower())


def duplicate_comment_text(kol: RawKOL) -> SignalResult:
    """Templated pod comments repeat the same normalized string many times."""
    if not kol.comments:
        return _clear("duplicate_text")
    counts = Counter(_norm(c.text) for c in kol.comments if c.text.strip())
    if not counts:
        return _clear("duplicate_text")
    duped = sum(n for n in counts.values() if n >= DUP_MIN_REPEATS)
    share = duped / len(kol.comments)
    if share >= DUP_MIN_SHARE:
        top_text, top_n = counts.most_common(1)[0]
        return SignalResult(
            name="duplicate_text",
            fired=True,
            level="medium",
            label="Templated comments",
            detail=f'"{top_text[:40]}" and near-duplicates repeat {top_n}x ({share:.0%} of sample)',
            measured_against=f"{len(kol.comments)} sampled comments",
            penalty=0.4,
            family="pod",
            metrics={"dup_share": round(share, 3)},
        )
    return _clear("duplicate_text")


# ── Thin commenter profiles (sampled second-pass) ───────────────────────────
def thin_commenter_profiles(kol: RawKOL) -> SignalResult:
    """Bought audiences: sampled commenters are empty / no Thai history."""
    sampled = [c for c in kol.comments if c.commenter_post_count is not None]
    if len(sampled) < THIN_MIN_SAMPLE:
        return _clear("thin_commenters")
    thin = [c for c in sampled if _is_thin(c)]
    share = len(thin) / len(sampled)
    if share >= THIN_MIN_SHARE:
        return SignalResult(
            name="thin_commenters",
            fired=True,
            level="high",
            label="Thin commenters",
            detail=f"{share:.0%} of sampled commenters have no Thai profile history / <{THIN_MAX_POSTS} posts",
            measured_against=f"commenter profile sample (n={len(sampled)})",
            penalty=0.7,
            metrics={"thin_share": round(share, 3)},
        )
    return _clear("thin_commenters")


def _is_thin(c: RawComment) -> bool:
    posts = c.commenter_post_count if c.commenter_post_count is not None else 99
    return posts < THIN_MAX_POSTS or c.commenter_has_thai_history is False


# ── Engagement-rate vs cohort outlier (statistical, n>=15 gate) ─────────────
def er_vs_cohort_outlier(kol: RawKOL, cohort: CohortStats) -> SignalResult:
    """ER far above the peer distribution — suspiciously hot. Withheld below n>=15."""
    er = engagement_rate(kol)
    if not cohort.sufficient:
        return SignalResult(
            name="er_outlier",
            fired=False,
            level="clear",
            label="",
            detail="insufficient baseline — signal withheld",
            measured_against=cohort.label,
            withheld=True,
        )
    if cohort.er_is_high_outlier(er):
        very = er > cohort.er_p75 + 3 * cohort.er_iqr
        return SignalResult(
            name="er_outlier",
            fired=True,
            level="high" if very else "medium",
            label="Engagement outlier",
            detail=(
                f"ER {er}% vs cohort median {cohort.er_median}% "
                f"(p75 {cohort.er_p75}%, IQR {cohort.er_iqr})"
            ),
            measured_against=cohort.label,
            penalty=0.5 if very else 0.3,
            metrics={"er": er},
        )
    return _clear("er_outlier")


# ── View-to-follower collapse (bought followers) ────────────────────────────
def view_to_follower_collapse(kol: RawKOL, cohort: CohortStats) -> SignalResult:
    vtf = view_to_follower(kol)
    # A real collapse = far below the peer NORM (median), not merely below p10.
    below_cohort = bool(
        cohort.sufficient and cohort.vtf_median > 0 and vtf < cohort.vtf_median * VTF_COLLAPSE_FRAC
    )
    if vtf < VTF_ABS_FLOOR or below_cohort:
        ratio = (cohort.vtf_median / vtf) if vtf > 0 else float("inf")
        ratio_txt = f"{ratio:.0f}x below the peer median" if cohort.sufficient and ratio != float("inf") else "far below the peer floor"
        return SignalResult(
            name="view_to_follower",
            fired=True,
            level="high",
            label="Bought followers",
            detail=f"Median views are {vtf * 100:.1f}% of follower count — {ratio_txt}",
            measured_against=cohort.label if cohort.sufficient else "absolute view-to-follower floor (5%)",
            penalty=0.8,
            metrics={"vtf": round(vtf, 4)},
        )
    return _clear("view_to_follower")


# ── Self-baseline boosted / view spike ──────────────────────────────────────
def boosted_post(kol: RawKOL) -> SignalResult:
    """Recent post views a large multiple of the creator's OWN trailing median
    (self-outliers excluded), so ad-lifted reach isn't priced as organic."""
    vids = sorted(kol.videos, key=lambda v: parse_iso(v.create_time_iso))
    if len(vids) < BOOST_RECENT_N + 3:
        return _clear("boosted_post")
    plays = [v.play_count for v in vids]
    baseline = median_excluding_outliers(plays)
    if baseline <= 0:
        return _clear("boosted_post")
    recent_peak = max(plays[-BOOST_RECENT_N:])
    mult = recent_peak / baseline
    if mult >= BOOST_HIGH_MULT:
        return SignalResult(
            name="boosted_post", fired=True, level="high", label="View spike",
            detail=f"Recent posts run {mult:.1f}x the account's own trailing baseline",
            measured_against="this creator's prior posts (self-baseline, outliers excluded)",
            penalty=0.55, metrics={"mult": round(mult, 1)},
        )
    if mult >= BOOST_MED_MULT:
        return SignalResult(
            name="boosted_post", fired=True, level="medium", label="Possible boosted post",
            detail=f"{_count_over(plays[-BOOST_RECENT_N:], baseline, BOOST_MED_MULT)} recent posts run "
                   f"{mult:.1f}x her trailing median — verify organic baseline before pricing reach",
            measured_against="her prior posts (self-baseline)",
            penalty=0.15, metrics={"mult": round(mult, 1)},
        )
    return _clear("boosted_post")


# ── Cadence / dormancy ──────────────────────────────────────────────────────
def cadence_dormancy(kol: RawKOL, now: datetime) -> SignalResult:
    if not kol.videos:
        return _clear("dormancy")
    last = max(parse_iso(v.create_time_iso) for v in kol.videos)
    days = (now - last).days
    if days > DORMANT_DAYS:
        return SignalResult(
            name="dormancy", fired=True, level="medium", label="Dormant",
            detail=f"Last post {days} days ago — cadence stalled",
            measured_against="posting timestamps", penalty=0.2, metrics={"days": days},
        )
    return _clear("dormancy")


# ── Thai comment-farm phrase lexicon (tiebreaker / explainability only) ─────
# EXPIRABLE by design: pod farms rotate wording monthly. Starter set only; to be
# expanded with the agency and reviewed by a Thai native. Never authoritative.
THAI_POD_LEXICON = [
    "สวย", "ปัง", "รับทรัพย์", "ตัวแม่", "แอดมินทักแชท",
    "admin ทักแชท", "สนใจทักแชท", "ของแท้", "จัดไป", "ว้าวมาก",
]


def thai_lexicon_hits(comments: list[RawComment]) -> int:
    """Count comments matching a starter Thai pod-phrase lexicon (advisory)."""
    hits = 0
    for c in comments:
        t = c.text.lower()
        if any(p in t for p in THAI_POD_LEXICON):
            hits += 1
    return hits


# ── helpers ─────────────────────────────────────────────────────────────────
def _max_in_window(sorted_times: list[datetime], window_s: int) -> int:
    if not sorted_times:
        return 0
    best = 1
    lo = 0
    for hi in range(len(sorted_times)):
        while (sorted_times[hi] - sorted_times[lo]).total_seconds() > window_s:
            lo += 1
        best = max(best, hi - lo + 1)
    return best


def _span_days(comments: list[RawComment]) -> int:
    if not comments:
        return 0
    ts = [parse_iso(c.create_time_iso) for c in comments]
    return max((max(ts) - min(ts)).days, 1)


def _count_over(values: list[int], baseline: float, mult: float) -> int:
    return sum(1 for v in values if v >= mult * baseline)
