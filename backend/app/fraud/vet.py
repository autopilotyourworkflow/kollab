"""Vetting orchestration: run every structural detector on a creator and fold the
fired signals into the exact Risk shape the frontend renders.

Badge policy (keeps the UI honest and uncluttered):
  - The pod family (cross-creator reuse + burst + templated text) collapses into a
    single "Comment pod" badge led by the strongest structural signal.
  - ER-vs-cohort outlier is corroboration: shown as its own badge only when nothing
    structural already explains the inflation (structural leads, statistics support).
  - Signals are ordered structural-first, most-severe-first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.fraud.cohort import CohortStats, build_cohorts, cohort_key
from app.fraud.signals import (
    SignalResult,
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
from app.raw import RawKOL, parse_iso
from app.schemas import FraudSignal, Risk

_LEVEL_RANK = {"clear": 0, "medium": 1, "high": 2}

# Fixed badge order (structural first, then bought/thin, then boost/stats).
_BADGE_ORDER = [
    "pod",
    "view_to_follower",
    "thin_commenters",
    "boosted_post",
    "er_outlier",
    "dormancy",
]


@dataclass
class VetResult:
    risk: Risk
    authenticity_score: int          # 0-100, feeds the "authenticity" match factor
    raw_signals: list[SignalResult] = field(default_factory=list)  # all, for eval/transparency


def _overall_level(signals: list[FraudSignal]) -> str:
    if not signals:
        return "clear"
    return max((s.level for s in signals), key=lambda lv: _LEVEL_RANK[lv])


def _pod_badge(fired: list[SignalResult]) -> FraudSignal | None:
    pod = [r for r in fired if r.family == "pod"]
    if not pod:
        return None
    # Lead with the most durable structural signal that actually fired.
    for pref in ("commenter_reuse", "comment_burst", "duplicate_text"):
        lead = next((r for r in pod if r.name == pref), None)
        if lead:
            break
    level = max((r.level for r in pod), key=lambda lv: _LEVEL_RANK[lv])
    return FraudSignal(
        label="Comment pod",
        detail=lead.detail,
        level=level,
        measured_against=lead.measured_against,
    )


def _badges(fired: list[SignalResult]) -> list[FraudSignal]:
    structural_fired = any(r.name in ("commenter_reuse", "comment_burst", "duplicate_text",
                                      "view_to_follower", "thin_commenters", "boosted_post")
                           for r in fired)
    badges: dict[str, FraudSignal] = {}

    pod = _pod_badge(fired)
    if pod:
        badges["pod"] = pod

    for r in fired:
        if r.family == "pod":
            continue
        if r.name == "er_outlier" and structural_fired:
            continue  # corroboration only; don't double-count as its own badge
        badges[r.name] = FraudSignal(
            label=r.label, detail=r.detail, level=r.level, measured_against=r.measured_against
        )

    ordered = [badges[k] for k in _BADGE_ORDER if k in badges]
    # stable severity sort within the fixed structural ordering
    ordered.sort(key=lambda s: -_LEVEL_RANK[s.level])
    return ordered


def vet_kol(
    kol: RawKOL,
    cohort: CohortStats,
    commenter_index: dict[str, set[str]],
    now: datetime,
) -> VetResult:
    results = [
        commenter_reuse_across_creators(kol, commenter_index),
        comment_burst_timing(kol),
        duplicate_comment_text(kol),
        thin_commenter_profiles(kol),
        view_to_follower_collapse(kol, cohort),
        boosted_post(kol),
        er_vs_cohort_outlier(kol, cohort),
        cadence_dormancy(kol, now),
    ]
    fired = [r for r in results if r.fired]
    badges = _badges(fired)
    penalty = min(1.0, sum(r.penalty for r in fired))
    authenticity = max(0, min(100, round(100 * (1 - penalty))))
    return VetResult(
        risk=Risk(level=_overall_level(badges), signals=badges),
        authenticity_score=authenticity,
        raw_signals=results,
    )


def _reference_now(corpus: list[RawKOL]) -> datetime:
    """Deterministic 'now' = the most recent activity in the corpus (fixtures carry
    timestamps relative to a fixed as-of date, so this is reproducible)."""
    stamps: list[datetime] = []
    for k in corpus:
        stamps += [parse_iso(v.create_time_iso) for v in k.videos]
        stamps += [parse_iso(c.create_time_iso) for c in k.comments]
    return max(stamps) if stamps else datetime.now(timezone.utc)


def vet_cohort(
    candidates: list[RawKOL],
    corpus: list[RawKOL] | None = None,
    now: datetime | None = None,
    min_n: int = 15,
) -> dict[str, VetResult]:
    """Vet each candidate against cohort stats + a shared-commenter graph.

    `corpus` is the wider creator set the reuse graph is built from (production:
    the whole licensed feed; demo: cohort + pod-decoy creators). Defaults to the
    candidates themselves.
    """
    corpus = corpus or candidates
    cohorts = build_cohorts(corpus, min_n=min_n)
    commenter_index = build_commenter_index(corpus)
    ref_now = now or _reference_now(corpus)

    out: dict[str, VetResult] = {}
    for kol in candidates:
        cohort = cohorts.get(
            cohort_key(kol),
            # empty/insufficient cohort -> outlier signals withhold
            CohortStats(key=cohort_key(kol), n=0, er_median=0, er_iqr=0, er_p25=0,
                        er_p75=0, vtf_median=0, vtf_p10=0, min_n=min_n),
        )
        out[kol.profile.author_id] = vet_kol(kol, cohort, commenter_index, ref_now)
    return out
