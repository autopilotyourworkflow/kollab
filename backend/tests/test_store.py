"""Run-history store + Expand-run dedup: a re-run buys NEW evidence, never the
same creators twice."""

from __future__ import annotations

from app.store import known_handles, norm_handle, record_run
from tests.test_live_paths import (
    BRIEF,
    FakeApifyClient,
    TIKTOK_COMMENTS_ACTOR,
    TIKTOK_SCRAPER_ACTOR,
    _comment_item,
    _search_response,
)
from app.sources.apify import ApifyAdapter


def _use_tmp_db(monkeypatch, tmp_path):
    monkeypatch.setenv("KOLLAB_DB", str(tmp_path / "test.db"))


def test_store_roundtrip_and_normalization(monkeypatch, tmp_path):
    _use_tmp_db(monkeypatch, tmp_path)
    assert known_handles("Glow Lab") == set()
    assert record_run("Glow Lab", ["@Ploy.SkinNote", "@nune.skinscience"]) == 2
    # re-recording the same creators adds nothing (INSERT OR IGNORE)
    assert record_run("glow lab", ["@ploy.skinnote"]) == 0
    assert known_handles("GLOW LAB") == {"ploy.skinnote", "nune.skinscience"}
    # other brands keep their own history
    assert known_handles("Other Brand") == set()
    assert norm_handle("  @Mimin.GlowySkin ") == "mimin.glowyskin"


def test_expand_run_skips_known_creators_before_spending():
    fake = FakeApifyClient({
        TIKTOK_SCRAPER_ACTOR: _search_response,
        TIKTOK_COMMENTS_ACTOR: lambda run_input: [_comment_item(i) for i in range(30)],
    })
    adapter = ApifyAdapter(client=fake, budget_usd=5.0, results_per_query=50,
                           exclude_handles={"@Creator_a1"})
    kols = adapter.fetch_candidates(BRIEF)

    # a1 is known: skipped before any comment spend; the slot goes to a2 only
    assert [k.profile.author_id for k in kols] == ["a2"]
    assert adapter.last_run["excluded_known"] == 1
    comment_calls = [c for c in fake.calls if c[0] == TIKTOK_COMMENTS_ACTOR]
    assert len(comment_calls) == 1  # no comment dollars spent on the known creator


def test_fresh_run_excludes_nothing():
    fake = FakeApifyClient({
        TIKTOK_SCRAPER_ACTOR: _search_response,
        TIKTOK_COMMENTS_ACTOR: lambda run_input: [_comment_item(i) for i in range(30)],
    })
    adapter = ApifyAdapter(client=fake, budget_usd=5.0, results_per_query=50)
    kols = adapter.fetch_candidates(BRIEF)
    assert len(kols) == 2 and adapter.last_run["excluded_known"] == 0
