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


_BRIEF = {
    "brand": "Glow Lab", "brandTh": "", "category": "Skincare",
    "audience": "Thai women", "pillars": ["Ingredient education"],
    "region": "Nationwide", "website": "glowlab.co.th",
}


def test_apify_live_path_without_token_answers_503(monkeypatch):
    # Selecting the live source without any credential must yield an honest 503 on the
    # LIVE path (POST a brief), never an unhandled 500 or a silently faked result.
    monkeypatch.setenv("KOLLAB_SOURCE", "apify")
    monkeypatch.setenv("KOLLAB_SHARED_KEY", "0")  # sharing off + no BYOK -> no key -> honest 503
    r = client.post("/api/shortlist", json=_BRIEF)
    assert r.status_code == 503
    assert "APIFY_TOKEN" in r.json()["detail"]


def test_get_shortlist_is_seed_backed_even_under_apify(monkeypatch):
    # GET /api/shortlist is the always-on demo (Glow Lab, curated fixtures): it must stay
    # seed-backed and 200 even when the live source is selected — it never depends on a
    # brief or a live token. (Real runs go through POST / the async /api/runs path.)
    monkeypatch.setenv("KOLLAB_SOURCE", "apify")
    monkeypatch.setenv("APIFY_TOKEN", "dummy")
    r = client.get("/api/shortlist")
    assert r.status_code == 200
    assert r.json()["kols"], "demo shortlist should carry creators"


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
        lambda url, text=None: real_extract(url, text=text, fetch_text=lambda u: (_ for _ in ()).throw(ConnectionError("offline"))),
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
