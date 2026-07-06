"""Persistent cross-run commenter graph — the fraud-recall moat.

Proves the three properties that make it honest and valuable:
  1. history LIFTS recall — a pod undersampled in one run is caught after prior runs
     recorded its edges;
  2. it can only raise recall on a REAL pattern — with no store (or an empty one) the
     vet is byte-identical, so history never manufactures a pod from absence of data;
  3. it degrades honestly — no DB -> in-memory backend, and the readout leaks no uids.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.fraud.graph import (
    MemoryGraphStore,
    connected_pods,
    edges_from_corpus,
    get_graph_store,
    remember_edges,
    reset_graph_store,
)
from app.fraud.signals import POD_MIN_ACCOUNTS, REUSE_MIN_CREATORS
from app.fraud.vet import vet_cohort
from app.sources.seed import SeedDatasetSource

from tests.conftest import BASE, make_comment, make_kol

POD_UIDS = [f"pod_{i:03d}" for i in range(POD_MIN_ACCOUNTS)]  # exactly the min pod size


def _spread(i: int):
    """Timestamp spread over ~20 days so a naturally-distributed comment stream never
    trips the burst detector (which the graph feature is orthogonal to)."""
    return BASE - timedelta(hours=(i * 4) % (20 * 24))


def _creator_hit_by_pod(author_id: str, n_comments: int = 60) -> object:
    """A creator whose comments are dominated by the shared POD_UIDS (used to seed the
    graph with prior sightings)."""
    comments = [
        make_comment(i, uid=POD_UIDS[i % len(POD_UIDS)], text="สวยมากค่ะ", dt=_spread(i))
        for i in range(n_comments)
    ]
    return make_kol(author_id=author_id, comments=comments)


def _target_undersampled(author_id: str = "X") -> object:
    """A creator where the SAME pod accounts are 20% of comments, but in THIS run they
    appear on only this one creator — so in-run reuse alone can't see the pod."""
    pod = [make_comment(i, uid=POD_UIDS[i], text="ปังมาก", dt=_spread(i)) for i in range(len(POD_UIDS))]
    organic = [make_comment(100 + i, uid=f"org_{author_id}_{i}", dt=_spread(i + 3)) for i in range(80)]
    return make_kol(author_id=author_id, comments=pod + organic)


@pytest.fixture(autouse=True)
def _isolate_graph():
    reset_graph_store()
    yield
    reset_graph_store()


# ── pure helpers ─────────────────────────────────────────────────────────────
def test_edges_from_corpus_yields_uid_creator_pairs():
    k = make_kol(author_id="A", comments=[make_comment(0, uid="u1"), make_comment(1, uid="u2")])
    assert set(edges_from_corpus([k])) == {("u1", "A"), ("u2", "A")}


def test_connected_pods_clusters_reused_accounts():
    # 20 accounts each seen on the same 3 creators -> one pod of 20 across 3 creators.
    index = {uid: {"A", "B", "C"} for uid in POD_UIDS}
    index["loner"] = {"A"}  # single-creator commenter: not reused, not a pod member
    pods = connected_pods(index)
    assert len(pods) == 1
    assert pods[0]["accounts"] == POD_MIN_ACCOUNTS
    assert pods[0]["creators"] == 3


def test_connected_pods_ignores_below_min_accounts():
    index = {f"u{i}": {"A", "B", "C"} for i in range(REUSE_MIN_CREATORS + 2)}  # reused but few
    assert connected_pods(index) == []


# ── memory store roundtrip + dedup ───────────────────────────────────────────
def test_memory_store_records_and_dedups():
    store = MemoryGraphStore()
    corpus = [_creator_hit_by_pod("A"), _creator_hit_by_pod("B")]
    first = store.record_edges(corpus, source="seed")
    assert first == 2 * len(POD_UIDS)          # A + B, one edge per distinct pod uid
    assert store.record_edges(corpus) == 0     # idempotent: nothing new the second time
    s = store.stats()
    assert s["backend"] == "memory" and s["durable"] is False
    assert s["creators"] == 2 and s["commenters"] == len(POD_UIDS)


# ── THE MOAT: history lifts recall ───────────────────────────────────────────
def test_history_lifts_recall_on_undersampled_pod():
    """Same pod, same target — invisible without history, caught with it."""
    store = MemoryGraphStore()

    # Baseline: this run alone can't see the pod (each pod account hits only X here).
    no_history = vet_cohort([_target_undersampled()], graph_store=store)["X"]
    assert no_history.risk.level == "clear"
    assert not any(s.label == "Comment pod" for s in no_history.risk.signals)

    # Prior campaigns recorded the SAME accounts hitting 3 other creators.
    store.record_edges([_creator_hit_by_pod("A"), _creator_hit_by_pod("B"),
                        _creator_hit_by_pod("C")], source="apify")

    # Now the accumulated graph pushes the real-but-undersampled pod over the line.
    with_history = vet_cohort([_target_undersampled()], graph_store=store)["X"]
    assert with_history.risk.level != "clear"
    assert any(s.label == "Comment pod" for s in with_history.risk.signals)


def test_augment_reports_recall_lift_count():
    store = MemoryGraphStore()
    store.record_edges([_creator_hit_by_pod("A"), _creator_hit_by_pod("B")])
    index = {uid: {"X"} for uid in POD_UIDS}
    added = store.augment(index)
    assert added == 2 * len(POD_UIDS)  # A and B added to each pod account
    assert index[POD_UIDS[0]] == {"X", "A", "B"}


# ── honesty: no store / empty store is byte-identical ────────────────────────
def test_no_store_matches_empty_store():
    a = vet_cohort([_target_undersampled()], graph_store=None)["X"]
    b = vet_cohort([_target_undersampled()], graph_store=MemoryGraphStore())["X"]
    assert a.risk.level == b.risk.level == "clear"
    assert a.authenticity_score == b.authenticity_score


def test_empty_graph_never_invents_a_pod():
    # A genuinely clean creator stays clean no matter that a store is attached.
    clean = make_kol(author_id="clean",
                     comments=[make_comment(i, uid=f"clean_u{i}", dt=_spread(i)) for i in range(60)])
    res = vet_cohort([clean], graph_store=MemoryGraphStore())["clean"]
    assert res.risk.level == "clear"


# ── factory + seed pipeline integration ──────────────────────────────────────
def test_factory_returns_memory_without_db(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    store = get_graph_store()
    assert store.backend == "memory"


def test_seed_pipeline_populates_graph_and_still_flags_mimin():
    from app.pipeline import build_shortlist
    reset_graph_store()
    resp = build_shortlist(SeedDatasetSource())
    mimin = next(k for k in resp.kols if k.handle == "@mimin.glowyskin")
    assert mimin.risk.level == "high"  # the graph wiring must not weaken the hero flag
    # the run recorded the seed corpus into the demo graph
    stats = get_graph_store().stats()
    assert stats["edges"] > 0 and stats["pods"] >= 1


def test_remember_edges_records_once_per_signature():
    reset_graph_store()
    corpus = [_creator_hit_by_pod("A")]
    assert remember_edges(corpus, source="seed") > 0
    assert remember_edges(corpus, source="seed") == 0  # same signature -> skipped


# ── /api/graph readout: populated + leak-free ────────────────────────────────
def test_graph_endpoint_empty_then_populated_without_leaking_uids():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.pipeline import build_shortlist

    reset_graph_store()
    client = TestClient(app)
    empty = client.get("/api/graph").json()
    assert empty["backend"] == "memory" and empty["edges"] == 0

    build_shortlist(SeedDatasetSource())  # records the seed graph
    full = client.get("/api/graph").json()
    assert full["edges"] > 0 and full["pods"] >= 1
    # readout is aggregate-only: no uid/handle strings anywhere in it
    blob = str(full).lower()
    assert "pod_" not in blob and "@" not in blob
    assert set(full["topPod"].keys()) == {"accounts", "creators"}
