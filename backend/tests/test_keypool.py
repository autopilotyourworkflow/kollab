"""Apify key-pool rotation: selection, reactive swap, add/validate, refresh, and the
admin gate. DB tests run against a temp SQLite file (no Postgres, no network); the
Apify calls (validate + balance) are monkeypatched, so the suite stays offline and
deterministic. Crypto/DB deps are importorskip'd so a minimal install skips cleanly."""

from __future__ import annotations

import uuid

import pytest

from app.db import init_db, reset_db_cache


@pytest.fixture
def pool_db(tmp_path, monkeypatch):
    pytest.importorskip("sqlalchemy")
    pytest.importorskip("cryptography")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path.as_posix()}/pool.db")
    monkeypatch.setenv("KOLLAB_KEY_ENC_SECRET", "unit-test-passphrase")
    reset_db_cache()
    assert init_db() is True
    yield
    reset_db_cache()


def _insert(status: str, remaining, label: str, token: str, priority: int = 100) -> str:
    from app.crypto import encrypt_token, fingerprint, mask
    from app.db import get_sessionmaker
    from app.models import ApifyKey

    kid = uuid.uuid4().hex
    with get_sessionmaker()() as s:
        s.add(ApifyKey(
            id=kid, label=label, token_encrypted=encrypt_token(token),
            token_fingerprint=fingerprint(token), token_hint=mask(token),
            status=status, credits_remaining=remaining, priority=priority,
        ))
        s.commit()
    return kid


# ── encryption ──────────────────────────────────────────────────────────────
def test_encrypt_roundtrip_and_fingerprint(monkeypatch):
    pytest.importorskip("cryptography")
    monkeypatch.setenv("KOLLAB_KEY_ENC_SECRET", "unit-test-passphrase")
    from app.crypto import decrypt_token, encrypt_token, fingerprint

    tok = "apify_api_supersecretvalue"
    ct = encrypt_token(tok)
    assert ct != tok and tok not in ct          # ciphertext hides the token
    assert decrypt_token(ct) == tok             # roundtrips
    assert fingerprint(tok) == fingerprint(tok) and len(fingerprint(tok)) == 12


# ── selection ───────────────────────────────────────────────────────────────
def test_acquire_prefers_fattest_active(pool_db):
    from app import keypool

    _insert("active", 2.0, "a", "tokA")
    _insert("active", 4.5, "b", "tokB")
    _insert("low", 9.0, "c", "tokC")            # 'low' is deprioritized below any 'active'

    lease = keypool.acquire()
    assert lease.label == "b"                    # fattest ACTIVE, not the higher-credit 'low'
    assert lease.token == "tokB"                 # decrypted correctly

    lease2 = keypool.acquire(exclude_ids={lease.key_id})
    assert lease2.label == "a"                   # exclude the burned one -> next active


def test_mark_exhausted_removes_from_selection(pool_db):
    from app import keypool

    kid = _insert("active", 5.0, "a", "tokA")
    assert keypool.acquire().key_id == kid
    keypool.mark(kid, "exhausted", error="402")
    assert keypool.acquire() is None             # exhausted key is invisible to the next run


def test_acquire_falls_to_low_when_no_active(pool_db):
    from app import keypool

    _insert("low", 0.8, "c", "tokC")
    lease = keypool.acquire()
    assert lease is not None and lease.label == "c"   # 'low' is still usable


# ── add / validate ──────────────────────────────────────────────────────────
def test_add_key_validates_seeds_balance_and_dedups(pool_db, monkeypatch):
    from app import keypool

    monkeypatch.setattr(keypool, "_validate_token", lambda t: (True, 200, ""))
    monkeypatch.setattr(keypool, "fetch_apify_credit",
                        lambda t: {"remainingUsd": 5.0, "limitUsd": 5.0, "cycleEndAt": None, "checked": True})

    res = keypool.add_key("apify_api_abc123", "my account")
    assert res["ok"] and res["key"]["status"] == "active"
    assert res["key"]["remainingUsd"] == 5.0
    assert "apify_api_abc123" not in str(res)    # token is NEVER echoed back

    dup = keypool.add_key("apify_api_abc123", "dup")
    assert dup["ok"] is False and dup["status"] == 409


def test_add_key_rejects_invalid_token(pool_db, monkeypatch):
    from app import keypool

    monkeypatch.setattr(keypool, "_validate_token", lambda t: (False, 400, "invalid or revoked"))
    res = keypool.add_key("apify_api_bad", "x")
    assert res["ok"] is False and res["status"] == 400
    assert keypool.list_public() == []           # nothing stored on rejection


# ── proactive refresh ───────────────────────────────────────────────────────
def test_refresh_flips_low(pool_db, monkeypatch):
    from app import keypool

    _insert("active", 5.0, "a", "tokA")
    monkeypatch.setattr(keypool, "fetch_apify_credit",
                        lambda t: {"remainingUsd": 0.5, "limitUsd": 5.0, "cycleEndAt": None, "checked": True})
    keypool.refresh_all()
    assert keypool.list_public()[0]["status"] == "low"   # 0.25 < 0.5 <= 1.00 -> low


def test_refresh_flips_exhausted_and_reactivates(pool_db, monkeypatch):
    from app import keypool

    kid = _insert("active", 5.0, "a", "tokA")
    monkeypatch.setattr(keypool, "fetch_apify_credit",
                        lambda t: {"remainingUsd": 0.0, "limitUsd": 5.0, "cycleEndAt": None, "checked": True})
    keypool.refresh_all()
    assert keypool.list_public()[0]["status"] == "exhausted"

    # cycle refilled -> next poll auto-reactivates
    monkeypatch.setattr(keypool, "fetch_apify_credit",
                        lambda t: {"remainingUsd": 5.0, "limitUsd": 5.0, "cycleEndAt": None, "checked": True})
    keypool.refresh_all()
    assert keypool.list_public()[0]["status"] == "active"


def test_refresh_transient_failure_does_not_yank_key(pool_db, monkeypatch):
    from app import keypool

    _insert("active", 5.0, "a", "tokA")
    monkeypatch.setattr(keypool, "fetch_apify_credit",
                        lambda t: {"checked": False, "note": "network blip"})
    keypool.refresh_all()
    assert keypool.list_public()[0]["status"] == "active"   # a flaky poll never sidelines a healthy key


# ── error classification (pure, no deps) ────────────────────────────────────
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


# ── reactive mid-run rotation (fake pool + fake client, no DB) ───────────────
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

    pool = _FakePool([Lease(key_id="k2", label="acct2", token="tok2")])
    fake = _FakeClient(items=[{"id": "v1"}], fail_n=1)
    adapter = ApifyAdapter(token="tok1", client=fake, pool=pool, initial_key_id="k1")

    out = adapter._run_actor(fake, TIKTOK_SCRAPER_ACTOR, {"searchQueries": ["x"]})

    assert out == [{"id": "v1"}]                 # the run still succeeded, on the next key
    assert pool.marked == [("k1", "exhausted")]  # the drained key was flagged
    assert adapter._current_key_id == "k2"       # rotated
    assert adapter.token == "tok2"
    assert "tok2" in adapter._touched_tokens     # tracked for cancel/abort


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


# ── admin gate ──────────────────────────────────────────────────────────────
def test_key_endpoints_require_admin_password(pool_db, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.delenv("KOLLAB_ADMIN_SECRET", raising=False)
    c = TestClient(app)
    assert c.get("/api/keys").status_code == 503          # disabled until a secret is set

    monkeypatch.setenv("KOLLAB_ADMIN_SECRET", "hunter2")
    assert c.get("/api/keys").status_code == 401          # missing header
    assert c.get("/api/keys", headers={"X-Admin-Secret": "wrong"}).status_code == 401
    ok = c.get("/api/keys", headers={"X-Admin-Secret": "hunter2"})
    assert ok.status_code == 200 and ok.json()["summary"]["enabled"] is True


def test_add_key_endpoint_never_returns_token(pool_db, monkeypatch):
    from fastapi.testclient import TestClient

    from app import keypool
    from app.main import app

    monkeypatch.setenv("KOLLAB_ADMIN_SECRET", "hunter2")
    monkeypatch.setattr(keypool, "_validate_token", lambda t: (True, 200, ""))
    monkeypatch.setattr(keypool, "fetch_apify_credit",
                        lambda t: {"remainingUsd": 5.0, "limitUsd": 5.0, "cycleEndAt": None, "checked": True})
    c = TestClient(app)
    r = c.post("/api/keys", json={"token": "apify_api_SECRET123", "label": "acct"},
               headers={"X-Admin-Secret": "hunter2"})
    assert r.status_code == 200
    assert "apify_api_SECRET123" not in r.text            # the token must never come back
    assert r.json()["fingerprint"] and r.json()["status"] == "active"
