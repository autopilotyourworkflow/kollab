"""Persistent cross-run commenter graph — the fraud-recall MOAT.

`build_commenter_index()` (app.fraud.signals) already computes the durable part of a
pod signature: which creators each commenter account has been seen on. Within ONE run
that graph is limited to the corpus that run happened to pull, so a pod that only
touched 2 of this run's creators looks innocent even though it hits 9 across the whole
book of business. This module PERSISTS those `commenter uid -> {creator id}` edges so
the graph ACCUMULATES across every run and every brand: fraud recall provably improves
each campaign, and that proprietary graph is the part a competitor can't fork.

Honesty guarantees (the graph can only *raise recall*, never invent fraud):
  - Every edge is `RawComment.uid` — data DIRECTLY OBSERVED in the comment payload, the
    same field the pure detector reads. Nothing is inferred at ingest.
  - Augmentation only UNIONS historical creators into the in-run index; the SAME gated
    detector (`REUSE_MIN_CREATORS`, `POD_MIN_ACCOUNTS`, `POD_MIN_SHARE`, and the n>=15
    cohort withhold) then runs unchanged. History can push a real-but-undersampled pod
    over an honest threshold; it can NEVER manufacture a pod from absence of data.
  - Two backends: a durable `NeonGraphStore` (production) and an in-memory
    `MemoryGraphStore` (the credential-free demo + tests). Both degrade honestly — a
    missing/broken DB never raises into the pipeline; the readout says which backend and
    whether it is `durable` or an `ephemeral demo graph`.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Iterator, Protocol

from app.fraud.signals import POD_MIN_ACCOUNTS, REUSE_MIN_CREATORS
from app.raw import RawKOL

# Max edges a stats/pod scan will materialize on the durable backend before it reports
# counts only (keeps a large production graph from being fully loaded for a readout).
_STATS_SCAN_LIMIT = 200_000


# ── pure helpers ─────────────────────────────────────────────────────────────
def edges_from_corpus(corpus: Iterable[RawKOL]) -> Iterator[tuple[str, str]]:
    """Yield (commenter_uid, creator_id) for every comment in the corpus. Dedup is
    the store's job (composite key), so this stays a flat, order-independent stream."""
    for kol in corpus:
        cid = kol.profile.author_id
        if not cid:
            continue
        for c in kol.comments:
            if c.uid:
                yield c.uid, cid


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:  # path compression
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def connected_pods(
    index: dict[str, set[str]],
    min_creators: int = REUSE_MIN_CREATORS,
    min_accounts: int = POD_MIN_ACCOUNTS,
) -> list[dict]:
    """Cluster REUSED commenter accounts (each seen on >= min_creators creators) by
    shared creators (co-occurrence union-find), and return clusters of >= min_accounts.

    This is the graph-wide analogue of `commenter_reuse_across_creators`: it names the
    pods that exist across ALL accumulated runs, not just the ones a single shortlist
    surfaced. Efficient (O(edges)): commenters are unioned per creator, not pairwise."""
    reused = {uid: creators for uid, creators in index.items() if len(creators) >= min_creators}
    if not reused:
        return []
    uf = _UnionFind()
    by_creator: dict[str, list[str]] = defaultdict(list)
    for uid, creators in reused.items():
        uf.find(uid)  # ensure singletons are represented
        for c in creators:
            by_creator[c].append(uid)
    for uids in by_creator.values():
        for u in uids[1:]:
            uf.union(uids[0], u)

    clusters: dict[str, list[str]] = defaultdict(list)
    for uid in reused:
        clusters[uf.find(uid)].append(uid)

    pods: list[dict] = []
    for members in clusters.values():
        if len(members) < min_accounts:
            continue
        creators: set[str] = set()
        for uid in members:
            creators |= reused[uid]
        pods.append({"accounts": len(members), "creators": len(creators)})
    pods.sort(key=lambda p: (-p["accounts"], -p["creators"]))
    return pods


# ── store interface ──────────────────────────────────────────────────────────
class GraphStore(Protocol):
    backend: str  # "memory" | "neon" | "none"

    def augment(self, index: dict[str, set[str]]) -> int:
        """Union each commenter's accumulated historical creators into the in-run index
        (mutated in place). Returns how many creator links history ADDED — the recall
        lift for this run. Never raises."""

    def record_edges(self, corpus: Iterable[RawKOL], source: str = "") -> int:
        """Persist this run's observed commenter->creator edges (idempotent). Returns
        edges newly written. Never raises."""

    def stats(self) -> dict:
        """A safe readout: {backend, durable, commenters, creators, edges, pods, topPod,
        note}. No uids/handles beyond aggregate counts. Never raises."""


def _empty_stats(backend: str, durable: bool, note: str) -> dict:
    return {"backend": backend, "durable": durable, "commenters": 0, "creators": 0,
            "edges": 0, "pods": 0, "topPod": None, "note": note}


def _stats_from_index(index: dict[str, set[str]], backend: str, durable: bool, note: str) -> dict:
    creators: set[str] = set()
    edges = 0
    for cs in index.values():
        creators |= cs
        edges += len(cs)
    pods = connected_pods(index)
    return {"backend": backend, "durable": durable, "commenters": len(index),
            "creators": len(creators), "edges": edges, "pods": len(pods),
            "topPod": pods[0] if pods else None, "note": note}


class MemoryGraphStore:
    """Process-local, ephemeral graph. Powers the credential-free demo + tests: the
    mechanism runs identically to the durable path, it just resets on restart (honestly
    labelled 'ephemeral demo graph')."""

    backend = "memory"

    def __init__(self) -> None:
        self._index: dict[str, set[str]] = defaultdict(set)

    def augment(self, index: dict[str, set[str]]) -> int:
        added = 0
        for uid in list(index.keys()):
            hist = self._index.get(uid)
            if hist:
                before = len(index[uid])
                index[uid] |= hist
                added += len(index[uid]) - before
        return added

    def record_edges(self, corpus: Iterable[RawKOL], source: str = "") -> int:
        n = 0
        for uid, cid in edges_from_corpus(corpus):
            bucket = self._index[uid]
            if cid not in bucket:
                bucket.add(cid)
                n += 1
        return n

    def stats(self) -> dict:
        return _stats_from_index(
            self._index, "memory", durable=False,
            note="Ephemeral demo graph (in-memory) — resets on restart. A live/licensed "
                 "run accumulates real creators here durably.",
        )


class NeonGraphStore:
    """Durable, cross-run, cross-brand graph in Postgres (Neon). No-ops honestly when no
    DATABASE_URL is configured, exactly like app.runs / app.db."""

    backend = "neon"

    def _session(self):
        from app.db import get_sessionmaker
        factory = get_sessionmaker()
        return factory() if factory is not None else None

    def augment(self, index: dict[str, set[str]]) -> int:
        uids = list(index.keys())
        if not uids:
            return 0
        try:
            from app.models import CommenterEdge
            s = self._session()
            if s is None:
                return 0
            added = 0
            with s:
                # Bounded IN() lookups so a huge graph stays a few indexed queries.
                for i in range(0, len(uids), 800):
                    chunk = uids[i:i + 800]
                    rows = (s.query(CommenterEdge.commenter_uid, CommenterEdge.creator_id)
                            .filter(CommenterEdge.commenter_uid.in_(chunk)).all())
                    for uid, cid in rows:
                        bucket = index[uid]
                        if cid not in bucket:
                            bucket.add(cid)
                            added += 1
            return added
        except Exception:
            return 0  # a DB hiccup must never weaken vetting — degrade to in-run only

    def record_edges(self, corpus: Iterable[RawKOL], source: str = "") -> int:
        edges = {(uid, cid) for uid, cid in edges_from_corpus(corpus)}
        if not edges:
            return 0
        try:
            from datetime import datetime, timezone
            from app.models import CommenterEdge
            s = self._session()
            if s is None:
                return 0
            now = datetime.now(timezone.utc)
            written = 0
            with s:
                have = set()
                keys = list(edges)
                for i in range(0, len(keys), 800):
                    chunk = keys[i:i + 800]
                    uids = [u for u, _ in chunk]
                    rows = (s.query(CommenterEdge.commenter_uid, CommenterEdge.creator_id)
                            .filter(CommenterEdge.commenter_uid.in_(uids)).all())
                    have |= {(u, c) for u, c in rows}
                for uid, cid in edges:
                    if (uid, cid) in have:
                        continue
                    s.add(CommenterEdge(commenter_uid=uid, creator_id=cid,
                                        first_seen=now, last_seen=now, source=source or ""))
                    written += 1
                s.commit()
            return written
        except Exception:
            return 0

    def stats(self) -> dict:
        try:
            from app.models import CommenterEdge
            s = self._session()
            if s is None:
                return _empty_stats("none", durable=False, note="DATABASE_URL not set")
            with s:
                total = s.query(CommenterEdge).count()
                if total == 0:
                    return _empty_stats("neon", durable=True,
                                        note="Durable graph (Neon) — empty until the first run records edges.")
                if total > _STATS_SCAN_LIMIT:
                    creators = s.query(CommenterEdge.creator_id).distinct().count()
                    commenters = s.query(CommenterEdge.commenter_uid).distinct().count()
                    return {"backend": "neon", "durable": True, "commenters": commenters,
                            "creators": creators, "edges": total, "pods": None, "topPod": None,
                            "note": "Durable graph (Neon). Pod clustering skipped at this scale."}
                index: dict[str, set[str]] = defaultdict(set)
                for uid, cid in s.query(CommenterEdge.commenter_uid, CommenterEdge.creator_id).all():
                    index[uid].add(cid)
            return _stats_from_index(index, "neon", durable=True,
                                     note="Durable graph (Neon) — accumulates across every run and brand.")
        except Exception as e:
            return _empty_stats("neon", durable=False, note=f"{type(e).__name__}: {str(e)[:120]}")


# ── module singleton + factory (mirrors db.py laziness) ──────────────────────
_memory_singleton: MemoryGraphStore | None = None
_recorded_signatures: set[str] = set()


def get_graph_store() -> GraphStore:
    """The durable Neon store when a DB is configured, else a process-local in-memory
    store (created once). Chosen per call so a late-configured DATABASE_URL is honored."""
    from app.db import database_url
    if database_url():
        return NeonGraphStore()
    global _memory_singleton
    if _memory_singleton is None:
        _memory_singleton = MemoryGraphStore()
    return _memory_singleton


def _corpus_signature(corpus: Iterable[RawKOL]) -> str:
    # Key on the actual edge set, not just the creator ids — a re-scrape of the SAME
    # creators that surfaced new commenters must still record (record_edges is idempotent,
    # so the seed's fixed edge set still no-ops after the first run).
    edges = sorted(set(edges_from_corpus(corpus)))
    return f"{len(edges)}:{hash(tuple(edges)) & 0xFFFFFFFF}"


def remember_edges(corpus: Iterable[RawKOL], source: str = "") -> int:
    """Pipeline hook: persist this run's edges, best-effort, at most ONCE per identical
    corpus per process. The seed cohort is byte-identical every GET, so it records once
    then no-ops (no write amplification on the hot demo path); a live run has a fresh
    signature and always records. Never raises into the pipeline."""
    corpus = list(corpus)
    sig = _corpus_signature(corpus)
    if sig in _recorded_signatures:
        return 0
    _recorded_signatures.add(sig)
    try:
        return get_graph_store().record_edges(corpus, source=source)
    except Exception:
        return 0


def reset_graph_store() -> None:
    """Test-only: drop the in-memory singleton + the per-process record guard."""
    global _memory_singleton
    _memory_singleton = None
    _recorded_signatures.clear()
