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


def test_apify_source_without_token_answers_503(monkeypatch):
    # Selecting the live source without its credential must yield an honest 503
    # with the reason, never an unhandled 500 or a silently faked result.
    monkeypatch.setenv("KOLLAB_SOURCE", "apify")
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    r = client.get("/api/shortlist")
    assert r.status_code == 503
    assert "APIFY_TOKEN" in r.json()["detail"]


def test_apify_source_without_client_lib_answers_503(monkeypatch):
    # Token present but apify-client not installed (the credential-free install):
    # still an honest 503 naming the missing piece. (POST carries the brief a
    # live source needs.)
    monkeypatch.setenv("KOLLAB_SOURCE", "apify")
    monkeypatch.setenv("APIFY_TOKEN", "dummy")
    brief = {
        "brand": "Test", "brandTh": "เทสต์", "category": "Skincare",
        "audience": "Thai women", "pillars": ["a"], "region": "BKK", "website": "x.co",
    }
    r = client.post("/api/shortlist", json=brief)
    assert r.status_code == 503
    assert "apify-client" in r.json()["detail"]


def test_apify_source_get_without_brief_answers_400(monkeypatch):
    # GET has no brief and a live source carries no default one -> honest 400.
    monkeypatch.setenv("KOLLAB_SOURCE", "apify")
    monkeypatch.setenv("APIFY_TOKEN", "dummy")
    r = client.get("/api/shortlist")
    assert r.status_code == 400
    assert "brief" in r.json()["detail"].lower()


def test_expand_params_are_a_noop_on_the_seed_source():
    # expand/exclude only affect live sourcing; fixtures mode ignores them and
    # reports zero dedup rather than erroring.
    brief = {
        "brand": "Test", "brandTh": "เทสต์", "category": "Skincare",
        "audience": "Thai women", "pillars": ["a"], "region": "BKK", "website": "x.co",
    }
    r = client.post("/api/shortlist?expand=1&exclude=@someone", json=brief)
    assert r.status_code == 200
    assert r.json()["excludedKnown"] == 0


def test_brand_dna_endpoint_degrades_honestly(monkeypatch):
    # No LLM keys + unreachable site -> rules skeleton, flagged degraded, source named.
    import app.main as main_mod
    from app.ingest.brand_dna import extract_brand_dna as real_extract

    monkeypatch.setattr(
        main_mod, "extract_brand_dna",
        lambda url: real_extract(url, fetch_text=lambda u: (_ for _ in ()).throw(ConnectionError("offline"))),
    )
    r = client.post("/api/brand-dna", json={"website": "glowlab.co.th"})
    assert r.status_code == 200
    body = r.json()
    assert body["degraded"] is True and body["source"] == "rules"
    assert body["brief"]["brand"] == "Glowlab"


def test_settings_read_env_at_call_time(monkeypatch):
    monkeypatch.setenv("KOLLAB_MIN_COHORT_N", "21")
    r = client.get("/health")
    assert r.json()["min_cohort_n"] == 21
