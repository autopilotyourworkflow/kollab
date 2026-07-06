"""Delivered-post re-audit: the paid post run back through the same detectors, diffed
against the pre-booking authenticity — catches a clean-vetted creator who bought
engagement, and passes one who didn't."""

from __future__ import annotations

from datetime import timedelta

from app.fraud.graph import MemoryGraphStore
from app.fraud.reaudit import (
    build_kol_from_request,
    load_delivered_fixture,
    reaudit_delivered_post,
)
from app.fraud.signals import POD_MIN_ACCOUNTS
from app.schemas import DeliveredPostRequest

from tests.conftest import BASE, iso, make_comment, make_kol

_POD = [f"rpod_{i:03d}" for i in range(POD_MIN_ACCOUNTS)]


def _spread(i: int):
    return BASE - timedelta(hours=(i * 4) % (18 * 24))


def test_pod_boosted_delivered_post_is_flagged_degraded():
    kol = load_delivered_fixture("@ploy.skinnote")  # fixture archetype = pod_boosted
    assert kol is not None
    audit = reaudit_delivered_post(kol, pre_authenticity=95)
    assert audit.verdict == "degraded"
    assert audit.post_authenticity < 95
    # a real structural signal fired on the delivered post (burst / templated pod text)
    assert any(s.label in ("Comment pod", "Comment burst", "Templated comments")
               for s in audit.new_signals)


def test_clean_delivered_post_is_consistent():
    kol = load_delivered_fixture("@jinny.dermdiary")  # fixture archetype = clean
    audit = reaudit_delivered_post(kol, pre_authenticity=90)
    assert audit.verdict == "consistent"
    assert audit.new_signals == []


def test_reaudit_full_ledger_is_present():
    kol = load_delivered_fixture("@ploy.skinnote")
    audit = reaudit_delivered_post(kol, pre_authenticity=95)
    # the single-post cohort forces the peer-comparison check to withhold — honestly shown
    withheld = [c for c in audit.checks if c.status == "withheld"]
    assert any(c.name == "er_outlier" for c in withheld)


def test_clean_delivered_post_with_low_pre_score_is_cleared():
    # pre-booking authenticity was low, the delivered post is clean -> the concern cleared
    audit = reaudit_delivered_post(load_delivered_fixture("@jinny.dermdiary"), pre_authenticity=50)
    assert audit.verdict == "cleared"
    assert audit.new_signals == []


def test_thin_delivered_sample_is_withheld_not_judged():
    # a delivered post with too few comments must WITHHOLD, never report absence as clean
    thin = make_kol(author_id="thin", comments=[make_comment(i, uid=f"u{i}") for i in range(5)])
    audit = reaudit_delivered_post(thin, pre_authenticity=90)
    assert audit.verdict == "inconclusive"
    assert "withheld" in audit.note.lower() or "thin" in audit.note.lower()


def test_none_pre_score_note_makes_no_false_comparison():
    # verdict can be "degraded" with no baseline; the note must NOT print a pre->post diff
    audit = reaudit_delivered_post(load_delivered_fixture("@ploy.skinnote"), pre_authenticity=None)
    assert audit.verdict == "degraded"
    assert "None" not in audit.note and "→" not in audit.note
    assert "no pre-booking baseline" in audit.note.lower()


def test_graph_augment_catches_a_known_pod_on_the_delivered_post():
    """A delivered post whose pod is invisible in-run is caught once the persistent graph
    knows those accounts hit other creators — the cross-run recall claim, end to end."""
    def prior(aid):
        return make_kol(author_id=aid,
                        comments=[make_comment(i, uid=_POD[i % len(_POD)], dt=_spread(i)) for i in range(60)])

    def delivered():
        pod = [make_comment(i, uid=_POD[i], dt=_spread(i)) for i in range(len(_POD))]
        organic = [make_comment(100 + i, uid=f"dlv_org_{i}", dt=_spread(i + 2)) for i in range(80)]
        return make_kol(author_id="DLV", comments=pod + organic)

    store = MemoryGraphStore()
    store.record_edges([prior("A"), prior("B"), prior("C")])
    assert reaudit_delivered_post(delivered(), pre_authenticity=95, graph_store=None).verdict == "consistent"
    with_graph = reaudit_delivered_post(delivered(), pre_authenticity=95, graph_store=store)
    assert with_graph.verdict == "degraded"
    assert any(s.label == "Comment pod" for s in with_graph.new_signals)


def test_build_kol_from_request_assembles_live_post():
    comments = [
        {"cid": f"c{i}", "uid": "bot", "uniqueId": "@bot", "text": "same spam",
         "createTimeISO": iso(BASE), "videoWebUrl": "https://v/x"}
        for i in range(30)
    ]
    videos = [{"id": "v1", "stats": {"playCount": 1000}, "createTimeISO": iso(BASE)}]
    req = DeliveredPostRequest(handle="@live", followers=10_000, videos=videos, comments=comments)
    kol = build_kol_from_request(req)
    assert kol is not None and len(kol.comments) == 30
    audit = reaudit_delivered_post(kol, pre_authenticity=None)
    assert audit.verdict == "degraded"  # a burst of identical comments fires structurally


def test_missing_fixture_returns_none():
    assert load_delivered_fixture("@nobody.here") is None


def test_verdict_without_pre_score():
    kol = load_delivered_fixture("@ploy.skinnote")
    audit = reaudit_delivered_post(kol, pre_authenticity=None)
    assert audit.verdict == "degraded"  # signals fired, no baseline to diff


# ── endpoint ─────────────────────────────────────────────────────────────────
def test_reaudit_endpoint_demo_path():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    res = client.post("/api/re-audit", json={"handle": "@ploy.skinnote", "preAuthenticity": 95})
    assert res.status_code == 200
    body = res.json()
    assert body["verdict"] == "degraded"
    assert body["postAuthenticity"] < 95


def test_reaudit_endpoint_unknown_handle_404():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    res = client.post("/api/re-audit", json={"handle": "@ghost"})
    assert res.status_code == 404
