"""Cohort statistics + the minimum-cohort (n>=15) rule."""

from __future__ import annotations

from app.fraud.cohort import (
    CohortStats,
    build_cohorts,
    engagement_rate,
    view_to_follower,
    _quantile,
)
from tests.conftest import make_cohort, make_kol


def test_engagement_rate_matches_target():
    kol = make_kol(median_views=50000, er=7.0)
    assert abs(engagement_rate(kol) - 7.0) < 0.2


def test_view_to_follower():
    kol = make_kol(followers=100000, median_views=25000)
    assert abs(view_to_follower(kol) - 0.25) < 1e-6


def test_quantile_median():
    assert _quantile([1, 2, 3, 4, 5], 0.5) == 3
    assert _quantile([1, 2, 3, 4], 0.5) == 2.5


def test_build_cohorts_groups_and_counts():
    kols = make_cohort(15, vertical="beauty", tier="micro") + make_cohort(3, tier="mid")
    stats = build_cohorts(kols)
    assert stats["beauty:micro"].n == 15
    assert stats["beauty:mid"].n == 3


def test_min_cohort_rule_withholds_below_threshold():
    thin = build_cohorts(make_cohort(10))["beauty:micro"]
    assert thin.n == 10 and thin.sufficient is False
    # even a wild ER cannot be called an outlier without a valid baseline
    assert thin.er_is_high_outlier(99.0) is False


def test_sufficient_cohort_can_flag_outlier():
    stats = build_cohorts(make_cohort(20, er_base=6.0))["beauty:micro"]
    assert stats.sufficient is True
    assert stats.er_is_high_outlier(stats.er_p75 + 5 * max(stats.er_iqr, 0.1)) is True


def test_empty_cohort_is_insufficient():
    c = CohortStats(key="x", n=0, er_median=0, er_iqr=0, er_p25=0, er_p75=0,
                    vtf_median=0, vtf_p10=0)
    assert c.sufficient is False
