"""End-to-end: the seed pipeline reproduces the exact story the deployed UI shows,
and emits the camelCase contract the frontend consumes."""

from __future__ import annotations


CLEAN_IDS = {"k1", "k2", "k3", "k5", "k7", "k9", "k10", "k11"}


def _labels(kol):
    return {s.label for s in kol.risk.signals}


def test_shortlist_has_all_candidates(shortlist):
    assert len(shortlist.kols) == 11
    assert shortlist.source == "seed" and shortlist.degraded is False


def test_mimin_is_comment_pod_and_view_spike(by_id):
    k = by_id["k4"]
    assert k.risk.level == "high"
    assert {"Comment pod", "View spike"} <= _labels(k)


def test_bello_is_bought_followers_and_thin(by_id):
    k = by_id["k6"]
    assert k.risk.level == "high"
    assert {"Bought followers", "Thin commenters"} <= _labels(k)


def test_gigi_is_possible_boosted_with_conflict_flag(by_id):
    k = by_id["k8"]
    assert k.risk.level == "medium"
    assert "Possible boosted post" in _labels(k)
    assert k.conflict.status == "flag" and k.conflict.note


def test_clean_creators_are_clear(by_id):
    for cid in CLEAN_IDS:
        assert by_id[cid].risk.level == "clear", cid
        assert by_id[cid].risk.signals == []


def test_sorted_by_fit_descending(shortlist):
    fits = [k.fit_score for k in shortlist.kols]
    assert fits == sorted(fits, reverse=True)


def test_summary_counts(shortlist):
    assert shortlist.flagged >= 3
    assert shortlist.recommended >= 5
    assert shortlist.screened > len(shortlist.kols)


def test_cost_is_projected(shortlist):
    assert shortlist.cost.usd > 0 and shortlist.cost.seconds > 0


def test_grounded_signals_name_their_baseline(by_id):
    for s in by_id["k4"].risk.signals:
        assert s.measured_against and s.detail


def test_camelcase_contract(shortlist):
    payload = shortlist.model_dump(by_alias=True)
    k = payload["kols"][0]
    for key in ("medianViews", "engagementRate", "lastPostedDaysAgo", "fitScore",
                "brandSafety", "whyEn", "whyTh", "estRateThb"):
        assert key in k, key
    if payload["kols"]:
        flagged = next((x for x in payload["kols"] if x["risk"]["signals"]), None)
        if flagged:
            assert "measuredAgainst" in flagged["risk"]["signals"][0]


def test_reported_metrics_match_descriptor(by_id):
    # median views + last-posted echo the curated descriptor within rounding
    assert abs(by_id["k4"].median_views - 88700) < 5000
    assert by_id["k1"].last_posted_days_ago == 2
