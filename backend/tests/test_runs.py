"""Async run store + job runner, against a temp SQLite DB (no Postgres, no network).
The job runs the SEED source, so it's deterministic and free — the runner logic is
what's under test, not Apify."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db import init_db, reset_db_cache

_BRIEF = {
    "brand": "Glow Lab", "brandTh": "เทสต์", "category": "Skincare",
    "audience": "Thai women", "pillars": ["a"], "region": "BKK", "website": "x.co",
}


@pytest.fixture
def sqlite_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path.as_posix()}/runs.db")
    reset_db_cache()
    assert init_db() is True
    yield
    reset_db_cache()


def test_run_lifecycle_on_seed(sqlite_db, monkeypatch):
    monkeypatch.setenv("KOLLAB_SOURCE", "seed")
    from app.runs import create_run, get_run, run_job

    create_run("r1", brand="Glow Lab", preset="scan", brief=None)
    assert get_run("r1")["status"] == "queued"

    # run synchronously (no thread) — seed source is deterministic and offline
    run_job("r1", brief_dict=None, preset="scan", expand=False, exclude=[],
            apify_token=None, anthropic_key=None)

    done = get_run("r1")
    assert done["status"] == "done" and done["error"] is None
    kols = done["result"]["kols"]
    assert kols and isinstance(kols[0]["fitScore"], int)  # camelCase contract persisted


def test_run_records_error_without_leaving_it_running(sqlite_db, monkeypatch):
    # apify source, no token, sharing off -> LiveRunError -> status=error (not stuck)
    monkeypatch.setenv("KOLLAB_SOURCE", "apify")
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    monkeypatch.setenv("KOLLAB_SHARED_KEY", "0")
    from app.runs import create_run, get_run, run_job

    create_run("r2", brand="X", preset="scan", brief=_BRIEF)
    run_job("r2", brief_dict=_BRIEF, preset="scan", expand=True, exclude=[],
            apify_token=None, anthropic_key=None)

    r = get_run("r2")
    assert r["status"] == "error"
    assert "Apify" in (r["error"] or "")


def test_request_cancel_marks_cancelled(sqlite_db):
    from app.runs import create_run, get_run, request_cancel

    create_run("rc", brand="X", preset="scan", brief=None)
    out = request_cancel("rc")  # no token -> no Apify abort, no network
    assert out["status"] == "cancelled"
    assert get_run("rc")["status"] == "cancelled"


def test_cancel_on_terminal_run_is_noop(sqlite_db):
    from app.runs import _update, create_run, request_cancel

    create_run("rd", brand="X", preset="scan", brief=None)
    _update("rd", status="done")
    assert request_cancel("rd")["status"] == "done"  # already finished — unchanged


def test_cancel_unknown_run_returns_none(sqlite_db):
    from app.runs import request_cancel

    assert request_cancel("does-not-exist") is None


def test_start_run_endpoint_requires_a_database(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    reset_db_cache()
    client = TestClient(app_ref())
    r = client.post("/api/runs", json=_BRIEF)
    assert r.status_code == 503 and "database" in r.json()["detail"].lower()


def app_ref():
    from app.main import app
    return app
