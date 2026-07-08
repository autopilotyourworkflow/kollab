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


def test_get_and_cancel_run_endpoints_503_without_db(monkeypatch):
    # These endpoints hit the DB session; with no database they must answer an honest 503,
    # not a bare 500 (RuntimeError from the session factory).
    monkeypatch.delenv("DATABASE_URL", raising=False)
    reset_db_cache()
    client = TestClient(app_ref())
    assert client.get("/api/runs/anything").status_code == 503
    assert client.post("/api/runs/anything/cancel").status_code == 503


def test_cancel_aborts_across_pool_when_no_single_token(sqlite_db, monkeypatch):
    # Recommended pool-only deploy: numbered APIFY_TOKEN_1..N, no legacy APIFY_TOKEN, no BYOK.
    # effective_apify_token is None, so cancel must still fire the abort across the env pool
    # (each pool key is a separate account) — otherwise a cancelled run keeps billing.
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    monkeypatch.setenv("APIFY_TOKEN_1", "apify_api_pool1")
    monkeypatch.setenv("APIFY_TOKEN_2", "apify_api_pool2")
    monkeypatch.setenv("KOLLAB_SHARED_KEY", "1")

    aborted: list[str] = []
    import app.runs as runs_mod
    monkeypatch.setattr(runs_mod, "_abort_running_apify", lambda tok: aborted.append(tok))

    from app.runs import create_run
    create_run("rp", brand="X", preset="scan", brief=None)
    client = TestClient(app_ref())
    r = client.post("/api/runs/rp/cancel")
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    # both pool keys got an abort attempt (best-effort across the accounts)
    assert "apify_api_pool1" in aborted and "apify_api_pool2" in aborted


def app_ref():
    from app.main import app
    return app
