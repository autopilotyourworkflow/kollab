"""FastAPI surface: health + the shortlist endpoint serialize the camelCase contract."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["source"] == "seed"


def test_get_shortlist_contract():
    r = client.get("/api/shortlist")
    assert r.status_code == 200
    body = r.json()
    assert len(body["kols"]) == 11
    k = body["kols"][0]
    assert "medianViews" in k and "engagementRate" in k and "fitScore" in k
    assert body["cost"]["usd"] > 0


def test_post_shortlist_with_brief():
    brief = {
        "brand": "Test", "brandTh": "เทสต์", "category": "Skincare",
        "audience": "Thai women", "pillars": ["a"], "region": "BKK", "website": "x.co",
    }
    r = client.post("/api/shortlist", json=brief)
    assert r.status_code == 200
    assert r.json()["brief"]["brand"] == "Test"


def test_flagged_kol_present():
    body = client.get("/api/shortlist").json()
    flagged = [k for k in body["kols"] if k["risk"]["level"] != "clear"]
    assert len(flagged) >= 3
    labels = {s["label"] for k in flagged for s in k["risk"]["signals"]}
    assert "Comment pod" in labels and "Bought followers" in labels


def test_apify_source_answers_503_not_a_crash(monkeypatch):
    # The Apify actor-run loop is roadmap: selecting it must yield an honest 503
    # with the reason, never an unhandled 500 or a silently faked result.
    monkeypatch.setenv("KOLLAB_SOURCE", "apify")
    monkeypatch.setenv("APIFY_TOKEN", "dummy")
    r = client.get("/api/shortlist")
    assert r.status_code == 503
    assert "not wired" in r.json()["detail"]


def test_settings_read_env_at_call_time(monkeypatch):
    monkeypatch.setenv("KOLLAB_MIN_COHORT_N", "21")
    r = client.get("/health")
    assert r.json()["min_cohort_n"] == 21
