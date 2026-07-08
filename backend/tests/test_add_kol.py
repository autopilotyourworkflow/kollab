"""Adding a creator to a shortlist must actually LAND the creator in the list — verified for
BOTH a logged-in account and the non-login guest path, since the reviewer checks both. Covers
create-with-kols, append, dedup-by-handle, and per-user isolation of the added creator."""

from __future__ import annotations

import pytest

from app.db import reset_db_cache


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'addkol.db').as_posix()}")
    monkeypatch.setenv("KOLLAB_AUTH_SECRET", "test-secret")
    reset_db_cache()
    from app.db import init_db
    init_db()
    import app.main as main_mod
    main_mod._rl_buckets.clear()
    from fastapi.testclient import TestClient
    yield TestClient(main_mod.app)
    reset_db_cache()


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def _account_token(client, email="acct@example.com"):
    return client.post("/api/auth/signup", json={"email": email, "password": "supersecret"}).json()["token"]


def _guest_token(client):
    return client.post("/api/auth/guest").json()["token"]


def _kol(handle, kid=None):
    return {"id": kid or handle.lstrip("@"), "handle": handle, "name": handle, "hitl": "pending"}


def _handles(client, sid, h):
    entry = client.get(f"/api/shortlists/{sid}", headers=h).json()["shortlist"]
    return {k["handle"] for k in entry["kols"]}


# ── the KOL lands in the list — LOGIN (account) method ───────────────────────
def test_added_kol_lands_in_list_for_account(client):
    h = _auth(_account_token(client))
    sid = client.post("/api/shortlists", headers=h,
                      json={"brief": {"brand": "B"}, "kols": [_kol("@one")]}).json()["shortlist"]["id"]
    assert _handles(client, sid, h) == {"@one"}

    res = client.post(f"/api/shortlists/{sid}/kols", headers=h, json={"kols": [_kol("@two")]})
    assert res.status_code == 200 and res.json()["added"] == 1
    # the added creator is now IN the list
    assert _handles(client, sid, h) == {"@one", "@two"}


# ── the KOL lands in the list — NON-LOGIN (guest) method ─────────────────────
def test_added_kol_lands_in_list_for_guest(client):
    h = _auth(_guest_token(client))
    # a guest starts seeded with the demo shortlist; create a fresh one to add into
    sid = client.post("/api/shortlists", headers=h,
                      json={"brief": {"brand": "G"}, "kols": [_kol("@g1")]}).json()["shortlist"]["id"]
    res = client.post(f"/api/shortlists/{sid}/kols", headers=h, json={"kols": [_kol("@g2")]})
    assert res.status_code == 200 and res.json()["added"] == 1
    assert _handles(client, sid, h) == {"@g1", "@g2"}


# ── dedup: adding the same handle twice never duplicates ──────────────────────
def test_added_kol_dedups_by_handle(client):
    h = _auth(_account_token(client))
    sid = client.post("/api/shortlists", headers=h,
                      json={"brief": {}, "kols": [_kol("@dup")]}).json()["shortlist"]["id"]
    # same handle (different case / different id) must not create a second row
    res = client.post(f"/api/shortlists/{sid}/kols", headers=h,
                      json={"kols": [_kol("@DUP", kid="other"), _kol("@fresh")]})
    added = res.json()["added"]
    handles = _handles(client, sid, h)
    assert "@fresh" in handles
    assert len([x for x in handles if x.lower() == "@dup"]) == 1  # not duplicated
    assert added == 1  # only the genuinely-new creator counted


# ── the added creator is private to its owner (guest add not visible to others) ─
def test_added_kol_is_isolated_per_user(client):
    guest = _auth(_guest_token(client))
    other = _auth(_account_token(client, "other@example.com"))
    sid = client.post("/api/shortlists", headers=guest,
                      json={"brief": {}, "kols": [_kol("@secret")]}).json()["shortlist"]["id"]
    client.post(f"/api/shortlists/{sid}/kols", headers=guest, json={"kols": [_kol("@secret2")]})
    # the other user cannot see the guest's shortlist or its added creators
    assert client.get(f"/api/shortlists/{sid}", headers=other).status_code == 404
