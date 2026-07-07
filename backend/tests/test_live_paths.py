"""Live-path seams, tested with fakes: the Apify actor loop (budget-capped), the
Brand DNA degradation chain, and the citation-validated LLM rerank. No network,
no SDKs — the fakes mirror the real client surfaces exactly."""

from __future__ import annotations

import json

import pytest

from app.ingest.brand_dna import extract_brand_dna
from app.matching.rerank import apply_llm_rerank, datapoints_for_kol
from app.matching.topic import keyword_topic_score
from app.pipeline import build_shortlist
from app.schemas import ClientBrief
from app.sources.apify import (
    ApifyAdapter,
    TIKTOK_COMMENTS_ACTOR,
    TIKTOK_SCRAPER_ACTOR,
    infer_tier,
    infer_vertical,
    search_queries_from_brief,
)
from app.sources.seed import SeedDatasetSource

BRIEF = ClientBrief(
    brand="Glow Lab", brand_th="โกลว์ แล็บ", category="Skincare / gentle actives (DTC)",
    audience="Thai women 22–34", pillars=["Ingredient education", "Sensitive-skin friendly"],
    region="Nationwide", website="glowlab.co.th",
)


# ── fake Apify client (mirrors apify_client's call surface) ─────────────────
class _FakeDataset:
    def __init__(self, items):
        self._items = items

    def iterate_items(self):
        return iter(self._items)


class _FakeActor:
    def __init__(self, client, actor_id):
        self._client, self._actor_id = client, actor_id

    def call(self, run_input):
        self._client.calls.append((self._actor_id, run_input))
        items = self._client.responses[self._actor_id](run_input)
        ds_id = f"ds{len(self._client.calls)}"
        self._client.datasets[ds_id] = items
        return {"defaultDatasetId": ds_id}


class FakeApifyClient:
    def __init__(self, responses):
        self.responses = responses  # actor_id -> callable(run_input) -> [items]
        self.datasets: dict[str, list] = {}
        self.calls: list = []

    def actor(self, actor_id):
        return _FakeActor(self, actor_id)

    def dataset(self, ds_id):
        return _FakeDataset(self.datasets[ds_id])


def _video_item(author_id: str, fans: int, i: int, plays: int = 50_000) -> dict:
    return {
        "id": f"{author_id}_v{i}",
        "authorMeta": {"id": author_id, "name": f"creator_{author_id}",
                       "nickName": f"Creator {author_id}", "fans": fans,
                       "signature": "skincare reviews", "region": "TH"},
        "stats": {"playCount": plays, "diggCount": int(plays * 0.05),
                  "commentCount": 40, "shareCount": 12},
        "createTimeISO": f"2026-06-{10 + i:02d}T00:00:00Z",
        "text": "skincare ingredient routine",
        "hashtags": [{"name": "skincare"}],
        "webVideoUrl": f"https://www.tiktok.com/@{author_id}/video/{i}",
    }


def _comment_item(i: int, url: str = "https://www.tiktok.com/@a/video/1") -> dict:
    return {"cid": f"c{i}", "uid": f"u{i}", "uniqueId": f"user{i}", "text": f"ดีมากค่ะ {i}",
            "diggCount": 2, "replyCommentTotal": 0,
            "createTimeISO": "2026-06-20T01:00:00Z",
            "videoWebUrl": url}


def _comments_response(run_input) -> list[dict]:
    """Batched comments actor: return comments tagged with each requested post URL
    (10 per post), mirroring the real actor's videoWebUrl echo so the adapter can
    map each comment back to its creator."""
    urls = run_input.get("postURLs", [])
    return [_comment_item(i, url=u) for u in urls for i in range(10)]


def _search_response(run_input) -> list[dict]:
    items = []
    for author, fans in (("a1", 45_000), ("a2", 250_000)):
        items += [_video_item(author, fans, i) for i in range(6)]
    return items


# ── the actor loop ───────────────────────────────────────────────────────────
def test_apify_loop_assembles_budgeted_kols():
    fake = FakeApifyClient({
        TIKTOK_SCRAPER_ACTOR: _search_response,
        TIKTOK_COMMENTS_ACTOR: _comments_response,
    })
    adapter = ApifyAdapter(client=fake, budget_usd=5.0, results_per_query=50)
    kols = adapter.fetch_candidates(BRIEF)

    assert len(kols) == 2
    tiers = {k.profile.author_id: k.tier for k in kols}
    assert tiers == {"a1": "micro", "a2": "mid"}
    assert all(k.vertical == "beauty" for k in kols)
    # each creator's 3 posts x 10 comments, mapped back from the single batch by url
    assert all(len(k.videos) == 6 and len(k.comments) == 30 for k in kols)
    assert adapter.last_run["creators"] == 2
    assert adapter.last_run["spent_usd"] <= 5.0
    # comments are pulled in ONE batched actor call for all creators' posts
    comment_calls = [c for c in fake.calls if c[0] == TIKTOK_COMMENTS_ACTOR]
    assert len(comment_calls) == 1
    assert len(comment_calls[0][1]["postURLs"]) == 6  # 3 posts x 2 creators
    # topic score on the live path is the lexical fallback with a grounded rationale
    pres = adapter.presentation(kols[0])
    assert pres.topic_score > 0 and "overlap" in (pres.topic_rationale or "")


def test_dataset_id_handles_dict_and_typed_run():
    # apify-client v3 returns a typed Run object (snake_case attr), older/fake
    # clients return a dict — the adapter must read both (regression: the real
    # SDK's Run has no .get()).
    from app.sources.apify import _dataset_id

    class _Run:
        default_dataset_id = "ds_typed"

    assert _dataset_id({"defaultDatasetId": "ds_dict"}) == "ds_dict"
    assert _dataset_id(_Run()) == "ds_typed"
    assert _dataset_id(None) is None


def test_region_sets_proxy_country_on_search():
    fake = FakeApifyClient({
        TIKTOK_SCRAPER_ACTOR: _search_response,
        TIKTOK_COMMENTS_ACTOR: lambda run_input: [_comment_item(i) for i in range(10)],
    })
    ApifyAdapter(client=fake, budget_usd=5.0, results_per_query=50,
                 region="TH").fetch_candidates(BRIEF)
    search_call = next(c for c in fake.calls if c[0] == TIKTOK_SCRAPER_ACTOR)
    assert search_call[1]["proxyCountryCode"] == "TH"


def test_global_region_omits_proxy_country():
    fake = FakeApifyClient({
        TIKTOK_SCRAPER_ACTOR: _search_response,
        TIKTOK_COMMENTS_ACTOR: lambda run_input: [_comment_item(i) for i in range(10)],
    })
    ApifyAdapter(client=fake, budget_usd=5.0, results_per_query=50,
                 region="none").fetch_candidates(BRIEF)
    search_call = next(c for c in fake.calls if c[0] == TIKTOK_SCRAPER_ACTOR)
    assert "proxyCountryCode" not in search_call[1]


def test_apify_loop_stops_before_crossing_the_cap():
    fake = FakeApifyClient({
        TIKTOK_SCRAPER_ACTOR: _search_response,
        TIKTOK_COMMENTS_ACTOR: lambda run_input: [_comment_item(i) for i in range(30)],
    })
    # Cap affords the search (~12 results = $0.02) but not a 120-comment pull ($0.06).
    adapter = ApifyAdapter(client=fake, budget_usd=0.05, results_per_query=5)
    kols = adapter.fetch_candidates(BRIEF)
    assert kols == []
    assert adapter.last_run["partial"] is True
    assert adapter.budget.spent_usd <= 0.05


def test_apify_loop_refuses_search_that_alone_busts_budget():
    fake = FakeApifyClient({TIKTOK_SCRAPER_ACTOR: _search_response})
    adapter = ApifyAdapter(client=fake, budget_usd=0.01, results_per_query=100)
    with pytest.raises(RuntimeError, match="budget"):
        adapter.fetch_candidates(BRIEF)
    assert fake.calls == []  # refused BEFORE spending anything


def test_apify_loop_honors_cancel_before_comment_spend():
    from app.sources.apify import RunCancelled

    fake = FakeApifyClient({
        TIKTOK_SCRAPER_ACTOR: _search_response,
        TIKTOK_COMMENTS_ACTOR: _comments_response,
    })
    adapter = ApifyAdapter(client=fake, budget_usd=5.0, results_per_query=50,
                           cancel_check=lambda: True)
    with pytest.raises(RunCancelled):
        adapter.fetch_candidates(BRIEF)
    # stopped right after the search, before any (billed) comment call
    assert not [c for c in fake.calls if c[0] == TIKTOK_COMMENTS_ACTOR]


def test_search_queries_and_inference_helpers():
    # No explicit search_terms -> fall back to the category head + concrete pillars.
    assert search_queries_from_brief(BRIEF) == ["skincare", "ingredient education",
                                                "sensitive-skin friendly"]
    # Explicit content search-terms take precedence (brand VALUES never reach the search).
    branded = BRIEF.model_copy(update={
        "pillars": ["Social responsibility", "Innovation and value"],
        "search_terms": ["Thai Skincare", "beauty review", "thai skincare"],  # note dup + case
    })
    assert search_queries_from_brief(branded) == ["thai skincare", "beauty review"]
    assert infer_tier(45_000) == "micro"
    assert infer_tier(250_000) == "mid"
    assert infer_tier(600_000) == "macro"
    assert infer_vertical(BRIEF) == "beauty"
    lifestyle = BRIEF.model_copy(update={"category": "Travel vlogs", "pillars": []})
    assert infer_vertical(lifestyle) == "lifestyle"


def test_keyword_topic_score_grounds_its_rationale():
    from tests.conftest import make_kol

    kol = make_kol()  # captions are empty; signature empty
    kol.videos[0].text = "gentle skincare ingredient breakdown"
    score, rationale = keyword_topic_score(BRIEF, kol)
    assert score >= 40 and "skincare" in rationale

    off_topic = make_kol(author_id="cars")
    score2, rationale2 = keyword_topic_score(BRIEF, off_topic)
    assert score2 == 10 and "verify topical fit" in rationale2


# ── brand DNA degradation chain ──────────────────────────────────────────────
_GOOD_BRIEF_JSON = json.dumps({
    "brand": "Glow Lab", "brandTh": "โกลว์ แล็บ", "category": "Skincare",
    "audience": "Thai women 22-34", "pillars": ["Ingredient education"],
    "region": "TH", "website": "glowlab.co.th",
})


def test_brand_dna_claude_first():
    r = extract_brand_dna("glowlab.co.th", fetch_text=lambda u: "site text",
                          claude_call=lambda p: _GOOD_BRIEF_JSON)
    assert r.source == "claude" and r.degraded is False and r.brief.brand == "Glow Lab"


def test_brand_dna_falls_to_gemini_on_invalid_claude_json():
    r = extract_brand_dna("glowlab.co.th", fetch_text=lambda u: "site text",
                          claude_call=lambda p: "sorry, I cannot",
                          gemini_call=lambda p: _GOOD_BRIEF_JSON)
    assert r.source == "gemini" and r.degraded is False


def test_brand_dna_degrades_to_rules_and_says_why():
    def boom(prompt):
        raise ValueError("provider down")

    r = extract_brand_dna("https://www.glow-lab.co.th/about",
                          fetch_text=lambda u: "site text",
                          claude_call=boom, gemini_call=boom)
    assert r.source == "rules" and r.degraded is True
    assert r.brief.brand == "Glow Lab" and r.brief.pillars == []
    assert "claude" in r.note and "gemini" in r.note


def test_brand_dna_degrades_when_site_unreachable():
    def dead(url):
        raise ConnectionError("dns failure")

    r = extract_brand_dna("nonexistent.example", fetch_text=dead,
                          claude_call=lambda p: _GOOD_BRIEF_JSON)
    assert r.source == "rules" and r.degraded is True
    assert "no readable text" in r.note or "paste" in r.note


def test_brand_dna_from_supplied_text_skips_the_fetch():
    # The paste box / bookmarklet supply already-rendered text — extraction uses it
    # directly and never fetches (so it works on sites a server can't read).
    fetched = {"hit": False}

    def should_not_fetch(url):
        fetched["hit"] = True
        return ""

    r = extract_brand_dna(
        "srichand.co.th",
        text="Srichand is a Thai heritage cosmetics brand — translucent powder, herbal skincare.",
        fetch_text=should_not_fetch, claude_call=lambda p: _GOOD_BRIEF_JSON,
    )
    assert r.source == "claude" and r.degraded is False
    assert fetched["hit"] is False


# ── citation-validated rerank ────────────────────────────────────────────────
def _fresh_response():
    return build_shortlist(SeedDatasetSource()).model_copy(deep=True)


def test_rerank_replaces_copy_and_strips_validated_citations():
    response = _fresh_response()
    top = response.kols[0]
    dp_ids = list(datapoints_for_kol(top))
    fake = lambda prompt: json.dumps({  # noqa: E731
        "whyEn": f"Strong fit [[{dp_ids[0]}]] with clean engagement [[dp:er]].",
        "whyTh": "ตัวเลือกที่แข็งแรง เอนเกจสะอาด [[dp:er]]",
    })
    out = apply_llm_rerank(response, call=fake, max_kols=1)
    assert "[[" not in out.kols[0].why_en and "[[" not in out.kols[0].why_th
    assert "Strong fit" in out.kols[0].why_en


def test_rerank_rejects_uncited_claims_and_keeps_deterministic_copy():
    response = _fresh_response()
    before = response.kols[0].why_en
    fake = lambda prompt: json.dumps({  # noqa: E731
        "whyEn": "Amazing reach [[dp:made_up_number]] and rates [[dp:er]].",
        "whyTh": "ไทย [[dp:made_up_number]]",
    })
    out = apply_llm_rerank(response, call=fake, max_kols=1)
    assert out.kols[0].why_en == before  # ghost citation -> copy stays deterministic


def test_rerank_survives_provider_failure():
    response = _fresh_response()
    before = response.kols[0].why_en

    def boom(prompt):
        raise TimeoutError("llm down")

    out = apply_llm_rerank(response, call=boom, max_kols=1)
    assert out.kols[0].why_en == before
