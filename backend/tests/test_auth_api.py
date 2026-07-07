"""Auth + workspace HTTP surface: signup/login/guest, enumeration parity, token handling,
owner-scoped CRUD, and the honest 503 with no database."""

from __future__ import annotations

import pytest

from app.db import reset_db_cache


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'api.db').as_posix()}")
    monkeypatch.setenv("KOLLAB_AUTH_SECRET", "test-secret")
    reset_db_cache()
    from app.db import init_db
    init_db()
    from fastapi.testclient import TestClient
    from app.main import app
    yield TestClient(app)
    reset_db_cache()


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def _signup(client, email="beam@example.com", pw="supersecret"):
    r = client.post("/api/auth/signup", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()["token"]


# ── signup / login ───────────────────────────────────────────────────────────
def test_signup_returns_token_and_user(client):
    body = client.post("/api/auth/signup", json={"email": "a@b.com", "password": "supersecret"}).json()
    assert body["token"] and body["user"]["email"] == "a@b.com" and body["user"]["isGuest"] is False


def test_signup_validation(client):
    assert client.post("/api/auth/signup", json={"email": "notanemail", "password": "supersecret"}).status_code == 400
    assert client.post("/api/auth/signup", json={"email": "a@b.com", "password": "short"}).status_code == 400


def test_signup_duplicate_is_409(client):
    client.post("/api/auth/signup", json={"email": "dup@x.com", "password": "supersecret"})
    assert client.post("/api/auth/signup", json={"email": "dup@x.com", "password": "supersecret"}).status_code == 409


def test_login_happy(client):
    client.post("/api/auth/signup", json={"email": "a@b.com", "password": "supersecret"})
    r = client.post("/api/auth/login", json={"email": "A@B.com", "password": "supersecret"})  # case-insensitive
    assert r.status_code == 200 and r.json()["token"]


def test_login_unknown_and_wrong_password_are_indistinguishable(client):
    client.post("/api/auth/signup", json={"email": "a@b.com", "password": "supersecret"})
    unknown = client.post("/api/auth/login", json={"email": "nobody@x.com", "password": "supersecret"})
    wrong = client.post("/api/auth/login", json={"email": "a@b.com", "password": "wrongpass"})
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"]  # no user enumeration


# ── guest + me ───────────────────────────────────────────────────────────────
def test_guest_is_seeded_with_the_demo(client):
    tok = client.post("/api/auth/guest").json()["token"]
    lists = client.get("/api/shortlists", headers=_auth(tok)).json()["shortlists"]
    assert len(lists) == 1 and lists[0]["brief"]["brand"] == "Glow Lab"


def test_me_requires_a_valid_token(client):
    tok = _signup(client)
    assert client.get("/api/auth/me", headers=_auth(tok)).json()["email"] == "beam@example.com"
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers=_auth("garbage.token")).status_code == 401


# ── workspace CRUD ───────────────────────────────────────────────────────────
def test_full_workspace_lifecycle(client):
    tok = _signup(client)
    h = _auth(tok)
    created = client.post("/api/shortlists", headers=h, json={
        "brief": {"brand": "Glow Lab"}, "kols": [{"id": "a", "handle": "@a", "hitl": "pending"}],
    })
    assert created.status_code == 201
    sid = created.json()["shortlist"]["id"]

    assert len(client.get("/api/shortlists", headers=h).json()["shortlists"]) == 1
    assert client.get(f"/api/shortlists/{sid}", headers=h).json()["shortlist"]["id"] == sid

    app_res = client.post(f"/api/shortlists/{sid}/kols", headers=h,
                          json={"kols": [{"id": "b", "handle": "@b", "hitl": "pending"}]})
    assert app_res.json()["added"] == 1

    assert client.put(f"/api/shortlists/{sid}/decisions/a", headers=h,
                      json={"status": "approved", "reason": "verified"}).status_code == 204
    got = client.get(f"/api/shortlists/{sid}", headers=h).json()["shortlist"]
    assert got["decisions"]["a"]["status"] == "approved"

    assert client.post(f"/api/shortlists/{sid}/source-live", headers=h).json()["shortlist"]["source"] == "api"
    assert client.delete(f"/api/shortlists/{sid}", headers=h).status_code == 204
    assert client.get("/api/shortlists", headers=h).json()["shortlists"] == []


def test_shortlists_are_isolated_per_user(client):
    a = _signup(client, "a@x.com")
    b = _signup(client, "b@x.com")
    sid = client.post("/api/shortlists", headers=_auth(a),
                      json={"brief": {}, "kols": [{"id": "k", "handle": "@k"}]}).json()["shortlist"]["id"]
    assert client.get("/api/shortlists", headers=_auth(b)).json()["shortlists"] == []
    assert client.get(f"/api/shortlists/{sid}", headers=_auth(b)).status_code == 404  # can't read another's
    assert client.delete(f"/api/shortlists/{sid}", headers=_auth(b)).status_code == 404  # or delete it


def test_workspace_requires_auth(client):
    assert client.get("/api/shortlists").status_code == 401
    assert client.post("/api/shortlists", json={"kols": []}).status_code == 401


# ── honest 503 with no database ──────────────────────────────────────────────
def test_auth_503_without_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("KOLLAB_AUTH_SECRET", raising=False)
    reset_db_cache()
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    assert c.post("/api/auth/guest").status_code == 503
    assert c.post("/api/auth/login", json={"email": "a@b.com", "password": "x"}).status_code == 503
    assert c.get("/api/shortlists").status_code == 503
    assert c.get("/health").json()["auth"] is False
    reset_db_cache()
