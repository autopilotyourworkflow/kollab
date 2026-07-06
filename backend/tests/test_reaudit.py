"""Delivered-post re-audit: the paid post run back through the same detectors, diffed
against the pre-booking authenticity — catches a clean-vetted creator who bought
engagement, and passes one who didn't."""

from __future__ import annotations

from app.fraud.reaudit import (
    load_delivered_fixture,
    reaudit_delivered_post,
)


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
