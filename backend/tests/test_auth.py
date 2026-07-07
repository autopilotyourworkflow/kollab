"""Auth primitives: scrypt hashing, HMAC-signed tokens, and the DATABASE_URL-derived
signing secret — all pure stdlib and hermetic."""

from __future__ import annotations

import pytest

from app.auth import (
    _DUMMY_HASH,
    auth_available,
    hash_password,
    issue_token,
    normalize_email,
    verify_password,
    verify_token,
)
from app.db import reset_db_cache


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    # a deterministic signing secret for token tests; reset caches around each test
    monkeypatch.setenv("KOLLAB_AUTH_SECRET", "test-secret-key")
    reset_db_cache()
    yield
    reset_db_cache()


# ── password hashing ─────────────────────────────────────────────────────────
def test_hash_roundtrip():
    h = hash_password("correct horse battery staple")
    assert h.startswith("scrypt$")
    assert verify_password("correct horse battery staple", h) is True
    assert verify_password("wrong", h) is False


def test_hash_is_salted():
    assert hash_password("same") != hash_password("same")  # random salt per hash


def test_verify_rejects_malformed_without_raising():
    for bad in (None, "", "notascrypthash", "scrypt$only$three", "bcrypt$x$y$z$w$v"):
        assert verify_password("x", bad) is False


def test_dummy_hash_is_valid_scrypt():
    assert _DUMMY_HASH.startswith("scrypt$")
    assert verify_password("kollab-dummy-invariant", _DUMMY_HASH) is True


# ── tokens ───────────────────────────────────────────────────────────────────
def test_token_roundtrip():
    t = issue_token("user-123")
    assert verify_token(t) == "user-123"


def test_token_rejects_tampering():
    t = issue_token("user-123")
    payload, sig = t.split(".", 1)
    assert verify_token(payload + "." + sig[:-2] + "xx") is None  # bad signature
    forged = payload[:-2] + "xx" + "." + sig
    assert verify_token(forged) is None                            # tampered payload


def test_token_rejects_expired():
    assert verify_token(issue_token("u", ttl=-1)) is None


def test_token_rejects_garbage():
    for bad in (None, "", "no-dot", "a.b.c.d"):
        assert verify_token(bad) is None


def test_token_bound_to_secret(monkeypatch):
    t = issue_token("u")
    monkeypatch.setenv("KOLLAB_AUTH_SECRET", "a-different-secret")
    reset_db_cache()
    assert verify_token(t) is None  # signed with the old secret -> rejected


# ── secret derivation + availability ─────────────────────────────────────────
def test_auth_needs_both_a_secret_and_a_database(monkeypatch):
    # a secret alone must NOT enable auth (else the DB layer 500s) — it needs a DB too
    monkeypatch.delenv("DATABASE_URL", raising=False)
    reset_db_cache()
    assert auth_available() is False
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db")
    reset_db_cache()
    assert auth_available() is True


def test_secret_derives_from_database_url(monkeypatch):
    monkeypatch.delenv("KOLLAB_AUTH_SECRET", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db")
    reset_db_cache()
    assert auth_available() is True
    assert verify_token(issue_token("u")) == "u"  # works end to end off the derived secret


def test_no_secret_no_auth(monkeypatch):
    monkeypatch.delenv("KOLLAB_AUTH_SECRET", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    reset_db_cache()
    assert auth_available() is False


def test_normalize_email():
    assert normalize_email("  Beam@Example.COM ") == "beam@example.com"
    assert normalize_email(None) == ""
