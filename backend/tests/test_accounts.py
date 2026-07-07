"""Accounts + workspace persistence: user CRUD, ownership scoping, dedup-on-append,
decision writes, guest seeding, and reaping — against a hermetic SQLite database."""

from __future__ import annotations

import pytest

from app.db import reset_db_cache


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'acct.db').as_posix()}")
    reset_db_cache()
    from app.db import init_db
    init_db()
    yield
    reset_db_cache()


def _kol(handle, kid=None):
    return {"id": kid or handle.strip("@"), "handle": handle, "hitl": "pending"}


# ── users ────────────────────────────────────────────────────────────────────
def test_create_and_get_user(db):
    from app.accounts import create_user, get_user
    u = create_user("Beam@Example.com", "supersecret")
    assert u["email"] == "beam@example.com" and u["isGuest"] is False
    assert get_user(u["id"])["email"] == "beam@example.com"
    assert get_user("nope") is None


def test_find_by_email_normalizes(db):
    from app.accounts import create_user, find_by_email
    u = create_user("a@b.com", "pw12345678")
    found = find_by_email("  A@B.COM ")
    assert found and found["id"] == u["id"] and found["password_hash"].startswith("scrypt$")


def test_duplicate_email_raises(db):
    from app.accounts import create_user
    create_user("dup@x.com", "pw12345678")
    with pytest.raises(Exception):
        create_user("dup@x.com", "pw12345678")


def test_guest_has_no_email(db):
    from app.accounts import create_guest, get_user
    g = create_guest()
    assert g["isGuest"] is True and g["email"] is None
    assert get_user(g["id"])["isGuest"] is True


# ── shortlists: ownership + CRUD ─────────────────────────────────────────────
def test_create_list_get_scoped_to_owner(db):
    from app.accounts import create_guest, create_shortlist, get_shortlist, list_shortlists
    a, b = create_guest()["id"], create_guest()["id"]
    sl = create_shortlist(a, {"brief": {"brand": "Glow Lab"}, "kols": [_kol("@ploy")]})
    assert sl["id"] and sl["brief"]["brand"] == "Glow Lab"
    assert len(list_shortlists(a)) == 1 and list_shortlists(b) == []
    assert get_shortlist(a, sl["id"]) is not None
    assert get_shortlist(b, sl["id"]) is None  # wrong owner -> not found (no id probing)


def test_create_defaults_decisions_from_hitl(db):
    from app.accounts import create_guest, create_shortlist
    uid = create_guest()["id"]
    sl = create_shortlist(uid, {"brief": {}, "kols": [_kol("@a"), {"id": "b", "handle": "@b", "hitl": "approved"}]})
    assert sl["decisions"]["b"]["status"] == "approved"


def test_append_dedups_by_handle(db):
    from app.accounts import append_kols, create_guest, create_shortlist
    uid = create_guest()["id"]
    sl = create_shortlist(uid, {"brief": {}, "kols": [_kol("@a")]})
    res = append_kols(uid, sl["id"], [_kol("@A", "a2"), _kol("@b", "b")])  # @A dups @a
    assert res["added"] == 1
    handles = {k["handle"].lower() for k in res["entry"]["kols"]}
    assert handles == {"@a", "@b"} and res["entry"]["runs"] == 2


def test_append_wrong_owner_is_none(db):
    from app.accounts import append_kols, create_guest, create_shortlist
    a, b = create_guest()["id"], create_guest()["id"]
    sl = create_shortlist(a, {"brief": {}, "kols": [_kol("@a")]})
    assert append_kols(b, sl["id"], [_kol("@b")]) is None


def test_set_decision_and_mark_live(db):
    from app.accounts import create_guest, create_shortlist, get_shortlist, mark_source_live, set_decision
    uid = create_guest()["id"]
    sl = create_shortlist(uid, {"brief": {}, "kols": [_kol("@a")]})
    assert set_decision(uid, sl["id"], "a", {"status": "approved", "reason": "verified"}) is True
    assert set_decision("other", sl["id"], "a", {"status": "approved"}) is False
    got = get_shortlist(uid, sl["id"])
    assert got["decisions"]["a"] == {"status": "approved", "reason": "verified"}
    mark_source_live(uid, sl["id"])
    assert get_shortlist(uid, sl["id"])["source"] == "api"


def test_delete_scoped(db):
    from app.accounts import create_guest, create_shortlist, delete_shortlist, list_shortlists
    a, b = create_guest()["id"], create_guest()["id"]
    sl = create_shortlist(a, {"brief": {}, "kols": [_kol("@a")]})
    assert delete_shortlist(b, sl["id"]) is False  # can't delete another user's row
    assert delete_shortlist(a, sl["id"]) is True
    assert list_shortlists(a) == []


# ── guest seeding + reaping ──────────────────────────────────────────────────
def test_seed_guest_workspace_is_the_demo_shortlist(db):
    from app.accounts import create_guest, list_shortlists, seed_guest_workspace
    uid = create_guest()["id"]
    entry = seed_guest_workspace(uid)
    assert entry["brief"]["brand"] == "Glow Lab"
    assert len(entry["kols"]) == 11 and entry["source"] == "fixtures"
    assert len(list_shortlists(uid)) == 1


def test_reap_guests_removes_idle_only(db):
    from datetime import datetime, timedelta, timezone
    from app.accounts import create_guest, create_shortlist, reap_guests, list_shortlists
    from app.db import get_sessionmaker
    from app.models import User
    old, fresh = create_guest()["id"], create_guest()["id"]
    create_shortlist(old, {"brief": {}, "kols": [_kol("@a")]})
    with get_sessionmaker()() as s:  # age `old` past the cutoff
        s.get(User, old).last_seen_at = datetime.now(timezone.utc) - timedelta(days=40)
        s.commit()
    assert reap_guests(30) == 1
    assert list_shortlists(old) == []       # their shortlist went too
    from app.accounts import get_user
    assert get_user(old) is None and get_user(fresh) is not None
