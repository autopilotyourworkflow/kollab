"""DB connectivity helpers — hermetic (no real database). Verifies URL normalization
and that an unconfigured/absent DB degrades honestly instead of crashing."""

from __future__ import annotations

from app.db import database_url, db_status


def test_database_url_normalizes_to_psycopg_driver(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@ep-x-pooler.neon.tech/neondb?sslmode=require")
    url = database_url()
    assert url is not None and url.startswith("postgresql+psycopg://")
    assert "sslmode=require" in url  # query preserved


def test_database_url_handles_postgres_scheme(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@host/db")
    assert database_url() == "postgresql+psycopg://u:p@host/db"


def test_database_url_none_when_unset(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert database_url() is None


def test_db_status_unconfigured_is_honest(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    s = db_status()
    assert s["configured"] is False and s["connected"] is False
    assert "not set" in s["note"]
