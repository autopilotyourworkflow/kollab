"""Delivery ledger: durable CRUD against a hermetic SQLite DB, honest reliability, and a
clean degrade (503 / empty map) when no database is configured."""

from __future__ import annotations

import pytest

from app.db import reset_db_cache


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'ledger.db').as_posix()}")
    reset_db_cache()
    from app.db import init_db
    init_db()
    yield
    reset_db_cache()


def test_record_and_read_delivery(db):
    from app.ledger import deliveries_for, record_delivery
    row = record_delivery("Glow Lab", "@ploy.skinnote", projected_views=50_000, actual_views=35_000)
    assert row["ratio"] == round(35_000 / 50_000, 3)
    rows = deliveries_for("@ploy.skinnote")
    assert len(rows) == 1 and rows[0]["handle"] == "ploy.skinnote"


def test_reliability_aggregates_and_labels(db):
    from app.ledger import record_delivery, reliability
    record_delivery("B", "@earn.honestreview", 100_000, 70_000)   # 0.70
    record_delivery("B", "@earn.honestreview", 100_000, 90_000)   # 0.90
    rel = reliability("@earn.honestreview")
    assert rel["n"] == 2
    assert rel["meanRatio"] == 0.8
    assert rel["adjustment"] < 0                 # under-delivery -> downward nudge
    assert "2 logged deliveries" in rel["note"]


def test_ratios_map_groups_by_handle(db):
    from app.ledger import ratios_map, record_delivery
    record_delivery("B", "@a", 100, 120)
    record_delivery("B", "@a", 100, 80)
    record_delivery("B", "@b", 100, 100)
    m = ratios_map()
    assert sorted(m["a"]) == [0.8, 1.2]
    assert m["b"] == [1.0]


def test_ratios_map_empty_without_db(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    reset_db_cache()
    from app.ledger import ratios_map
    assert ratios_map() == {}


def test_endpoints_503_without_db(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    reset_db_cache()
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    assert client.post("/api/deliveries", json={"handle": "@x", "projectedViews": 1, "actualViews": 1}).status_code == 503
    assert client.get("/api/deliveries", params={"handle": "@x"}).status_code == 503


def _auth_header(client):
    """Sign up and return an Authorization header (the ledger requires a signed-in user)."""
    tok = client.post("/api/auth/signup",
                      json={"email": "ledger@x.com", "password": "supersecret"}).json()["token"]
    return {"Authorization": f"Bearer {tok}"}


def test_endpoint_roundtrip_with_db(db):
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    h = _auth_header(client)
    res = client.post("/api/deliveries", json={
        "brand": "Glow Lab", "handle": "@ploy.skinnote",
        "projectedViews": 50_000, "actualViews": 60_000,
    }, headers=h)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["delivery"]["ratio"] == 1.2
    assert body["reliability"]["n"] == 1
    listed = client.get("/api/deliveries", params={"handle": "@ploy.skinnote"}, headers=h).json()
    assert len(listed["deliveries"]) == 1


def test_delivery_endpoints_require_auth(db):
    """With a DB but no bearer token, the ledger is not writable/readable anonymously — an
    anonymous caller must not be able to inject a fabricated 'delivered N×' outcome that
    would nudge everyone's fit scores."""
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    assert client.post("/api/deliveries", json={
        "handle": "@x", "projectedViews": 1, "actualViews": 1,
    }).status_code == 401
    assert client.get("/api/deliveries", params={"handle": "@x"}).status_code == 401
