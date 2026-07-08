"""Apify key rotation from environment variables: token discovery/order, selection,
reactive mid-run swap, and the proactive low-balance refresh. No DB, no network — the
Apify balance call is monkeypatched, env is set per-test, and the in-memory drained set
is reset around each test."""

from __future__ import annotations

import os
import re

import pytest


@pytest.fixture
def pool(monkeypatch):
    """A hermetic env pool: strip any real APIFY_TOKEN* from the environment and clear
    the in-memory drained set before and after the test."""
    from app import keypool

    for name in list(os.environ):
        if name == "APIFY_TOKEN" or re.fullmatch(r"APIFY_TOKEN_\d+", name):
            monkeypatch.delenv(name, raising=False)
    keypool._drained.clear()
    keypool._preferred = None
    yield keypool
    keypool._drained.clear()
    keypool._preferred = None


# ── token discovery + ordering ──────────────────────────────────────────────
def test_env_tokens_order_and_dedup(pool, monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "tok-legacy")
    monkeypatch.setenv("APIFY_TOKEN_2", "tok-2")
    monkeypatch.setenv("APIFY_TOKEN_10", "tok-10")
    monkeypatch.setenv("APIFY_TOKEN_1", "tok-1")
    monkeypatch.setenv("APIFY_TOKEN_3", "tok-legacy")  # duplicate token value -> dropped

    tokens = pool.env_tokens()
    labels = [lbl for lbl, _ in tokens]
    values = [val for _, val in tokens]
    # legacy first, then numeric order 1,2,10 — and the duplicate value is removed
    assert labels == ["APIFY_TOKEN", "APIFY_TOKEN_1", "APIFY_TOKEN_2", "APIFY_TOKEN_10"]
    assert values == ["tok-legacy", "tok-1", "tok-2", "tok-10"]
    assert pool.available() is True


def test_available_false_when_no_tokens(pool):
    assert pool.available() is False
    assert pool.acquire() is None


# ── selection + reactive marking ────────────────────────────────────────────
def test_acquire_first_then_swap_on_mark(pool, monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN_1", "tok-1")
    monkeypatch.setenv("APIFY_TOKEN_2", "tok-2")

    first = pool.acquire()
    assert first.token == "tok-1" and first.label == "APIFY_TOKEN_1"

    pool.mark(first.key_id, "exhausted", error="402")
    second = pool.acquire()
    assert second.token == "tok-2"

    pool.mark(second.key_id, "invalid", error="401")
    assert pool.acquire() is None                      # both drained -> nothing left

    # a recovered key becomes selectable again
    pool.mark(first.key_id, "active")
    assert pool.acquire().token == "tok-1"


def test_acquire_excludes_tried_keys(pool, monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN_1", "tok-1")
    monkeypatch.setenv("APIFY_TOKEN_2", "tok-2")
    first = pool.acquire()
    nxt = pool.acquire(exclude_ids={first.key_id})
    assert nxt.token == "tok-2"


# ── proactive refresh ───────────────────────────────────────────────────────
def test_refresh_drains_low_and_recovers(pool, monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN_1", "tok-1")

    monkeypatch.setattr(pool, "fetch_apify_credit",
                        lambda t: {"remainingUsd": 0.2, "checked": True})   # <= $0.50 min
    pool.refresh_all()
    assert pool.status()["healthy"] == 0
    assert pool.acquire() is None                      # skipped because low

    monkeypatch.setattr(pool, "fetch_apify_credit",
                        lambda t: {"remainingUsd": 4.0, "checked": True})   # refilled
    pool.refresh_all()
    assert pool.status()["healthy"] == 1
    assert pool.acquire().token == "tok-1"


def test_refresh_transient_failure_does_not_drain(pool, monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN_1", "tok-1")
    monkeypatch.setattr(pool, "fetch_apify_credit", lambda t: {"checked": False, "note": "blip"})
    pool.refresh_all()
    assert pool.status()["healthy"] == 1               # a flaky poll never sidelines a key


# ── status never leaks a token ──────────────────────────────────────────────
def test_status_masks_tokens(pool, monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN_1", "apify_api_SUPERSECRETVALUE")
    st = pool.status()
    assert st["count"] == 1 and st["healthy"] == 1
    hint = st["keys"][0]["hint"]
    assert "SUPERSECRETVALUE" not in str(st)           # the token is never exposed
    assert hint.endswith("ALUE") and hint.startswith("apify_api_")


# ── error classification (pure) ─────────────────────────────────────────────
def test_quota_and_invalid_classification():
    from app.sources.apify import _is_invalid_token, _is_quota_error

    class E(Exception):
        def __init__(self, **kw):
            self.__dict__.update(kw)

    assert _is_quota_error(E(status_code=402))
    assert _is_quota_error(E(status_code=403))
    assert _is_quota_error(E(type="not-enough-usage-to-run-paid-actor"))
    assert _is_quota_error(E(message="Monthly usage hard limit reached"))
    assert not _is_quota_error(E(status_code=500))
    assert _is_invalid_token(E(status_code=401))
    assert _is_invalid_token(E(type="invalid-token"))
    assert not _is_invalid_token(E(status_code=402))


# ── reactive mid-run rotation (fake pool + fake client) ─────────────────────
class _FakeQuotaError(Exception):
    def __init__(self, msg="Payment Required", status_code=402):
        super().__init__(msg)
        self.status_code = status_code
        self.message = msg


class _FakeActor:
    def __init__(self, client):
        self.client = client

    def call(self, run_input=None):
        self.client.calls += 1
        if self.client.calls <= self.client.fail_n:
            raise _FakeQuotaError()
        return {"defaultDatasetId": "ds1"}


class _FakeDataset:
    def __init__(self, items):
        self.items = items

    def iterate_items(self):
        return iter(self.items)


class _FakeClient:
    def __init__(self, items, fail_n=1):
        self.calls = 0
        self.fail_n = fail_n
        self.items = items

    def actor(self, actor_id):
        return _FakeActor(self)

    def dataset(self, ds):
        return _FakeDataset(self.items)


class _FakePool:
    def __init__(self, leases):
        self._leases = list(leases)
        self.marked: list[tuple[str, str]] = []

    def mark(self, key_id, status, error=None):
        self.marked.append((key_id, status))

    def acquire(self, exclude_ids=None):
        return self._leases.pop(0) if self._leases else None


def test_reactive_rotation_swaps_on_quota_error():
    from app.keypool import Lease
    from app.sources.apify import TIKTOK_SCRAPER_ACTOR, ApifyAdapter

    pool = _FakePool([Lease(key_id="k2", label="APIFY_TOKEN_2", token="tok2")])
    fake = _FakeClient(items=[{"id": "v1"}], fail_n=1)
    adapter = ApifyAdapter(token="tok1", client=fake, pool=pool, initial_key_id="k1")

    out = adapter._run_actor(fake, TIKTOK_SCRAPER_ACTOR, {"searchQueries": ["x"]})

    assert out == [{"id": "v1"}]                 # the run still succeeded, on the next key
    assert pool.marked == [("k1", "exhausted")]  # the drained key was flagged
    assert adapter._current_key_id == "k2" and adapter.token == "tok2"


def test_rotation_raises_when_all_keys_drained():
    from app.sources.apify import TIKTOK_SCRAPER_ACTOR, ApifyAdapter

    pool = _FakePool([])                          # no replacement keys
    fake = _FakeClient(items=[{"id": "v1"}], fail_n=1)
    adapter = ApifyAdapter(token="tok1", client=fake, pool=pool, initial_key_id="k1")

    with pytest.raises(RuntimeError, match="exhausted or invalid"):
        adapter._run_actor(fake, TIKTOK_SCRAPER_ACTOR, {"searchQueries": ["x"]})
    assert pool.marked == [("k1", "exhausted")]


def test_no_pool_keeps_legacy_behavior():
    """With pool=None the adapter must NOT swallow errors — legacy single-key path."""
    from app.sources.apify import TIKTOK_SCRAPER_ACTOR, ApifyAdapter

    fake = _FakeClient(items=[{"id": "v1"}], fail_n=1)
    adapter = ApifyAdapter(token="tok1", client=fake)   # no pool
    with pytest.raises(_FakeQuotaError):
        adapter._run_actor(fake, TIKTOK_SCRAPER_ACTOR, {"searchQueries": ["x"]})


# ── manual account selection + auto-switch off a low account ─────────────────
def test_set_preferred_makes_it_the_active_account(pool, monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN_1", "tok-1")
    monkeypatch.setenv("APIFY_TOKEN_2", "tok-2")
    monkeypatch.setenv("APIFY_TOKEN_3", "tok-3")
    fps = {a["label"]: a["fingerprint"] for a in pool.accounts(with_balance=False)}

    assert pool.acquire().label == "APIFY_TOKEN_1"        # default = first in order
    assert pool.set_preferred(fps["APIFY_TOKEN_2"]) is True
    assert pool.get_preferred() == fps["APIFY_TOKEN_2"]
    assert pool.acquire().label == "APIFY_TOKEN_2"        # now runs start on the chosen one


def test_preferred_auto_switches_when_low_and_returns_on_recovery(pool, monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN_1", "tok-1")
    monkeypatch.setenv("APIFY_TOKEN_2", "tok-2")
    fps = {a["label"]: a["fingerprint"] for a in pool.accounts(with_balance=False)}
    pool.set_preferred(fps["APIFY_TOKEN_2"])
    assert pool.acquire().label == "APIFY_TOKEN_2"

    pool.mark(fps["APIFY_TOKEN_2"], "exhausted", "low balance")   # the low-credit sweep drains it
    assert pool.acquire().label == "APIFY_TOKEN_1"                # AUTO-SWITCH to the next healthy

    pool.mark(fps["APIFY_TOKEN_2"], "active")                     # monthly refill recovers it
    assert pool.acquire().label == "APIFY_TOKEN_2"               # back to the preferred account


def test_set_preferred_rejects_unknown_and_clears_on_auto(pool, monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN_1", "tok-1")
    assert pool.set_preferred("not-a-real-fingerprint") is False
    assert pool.get_preferred() is None
    fp = pool.accounts(with_balance=False)[0]["fingerprint"]
    pool.set_preferred(fp)
    assert pool.set_preferred(None) is True                       # 'auto'
    assert pool.get_preferred() is None


def test_accounts_never_leak_the_token(pool, monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN_1", "apify_api_secretvalue1234")
    rows = pool.accounts(with_balance=False)
    assert len(rows) == 1
    row = rows[0]
    assert "token" not in row
    assert row["hint"] == "apify_api_…1234"                       # masked, last 4 only
    assert "secretvalue" not in str(row)                          # the raw token never appears
