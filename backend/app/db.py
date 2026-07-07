"""Optional Postgres (Neon) connectivity.

Kollab runs fully without a database (seed data + the browser workspace). When
DATABASE_URL is set, this is the engine behind the durable server-side store. All
SQLAlchemy/driver imports are lazy, so the credential-free install needs none of
them, and every entry point degrades honestly instead of crashing when the DB is
absent or unreachable — `db_status()` is what lets us confirm a Neon setup
end-to-end from /api/db-status."""

from __future__ import annotations

import os
from functools import lru_cache


def database_url() -> str | None:
    """The configured DB URL, normalized to SQLAlchemy's psycopg3 driver. Neon (and
    most providers) hand out a bare `postgresql://…` string; SQLAlchemy needs the
    explicit `postgresql+psycopg://` so it doesn't reach for psycopg2."""
    url = os.getenv("DATABASE_URL") or None
    if not url:
        return None
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


@lru_cache(maxsize=1)
def get_engine():
    """A pooled Engine, or None when DATABASE_URL is unset. Cached so we build it
    once. pool_pre_ping survives Neon's scale-to-zero idle disconnects."""
    url = database_url()
    if not url:
        return None
    from sqlalchemy import create_engine  # lazy: optional dep

    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)


@lru_cache(maxsize=1)
def get_sessionmaker():
    """A configured sessionmaker, or None when no DB is set. Cached alongside the
    engine. Tests that swap DATABASE_URL call `reset_db_cache()` first."""
    engine = get_engine()
    if engine is None:
        return None
    from sqlalchemy.orm import sessionmaker  # lazy

    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> bool:
    """Create tables if a DB is configured (idempotent). Returns True when the DB is
    ready to use, False when DATABASE_URL is unset. Never raises on a bad URL — logs
    via the return of db_status elsewhere; startup stays up so the seed demo works."""
    engine = get_engine()
    if engine is None:
        return False
    from app.models import Base  # lazy: pulls SQLAlchemy models only when DB is used

    Base.metadata.create_all(engine)
    return True


def reset_db_cache() -> None:
    """Drop cached engine + sessionmaker (so a changed DATABASE_URL is picked up).
    Test-only in practice. Also drops the auth signing-secret cache, which is derived
    from DATABASE_URL."""
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    from app.auth import reset_auth_cache  # local import: avoid an import cycle
    reset_auth_cache()


def db_status() -> dict:
    """{configured, connected, note} — never raises. `configured` reflects whether
    DATABASE_URL is set; `connected` runs a real `SELECT 1` so a green result proves
    the credentials, network, and SSL all work from this host."""
    if not database_url():
        return {"configured": False, "connected": False, "note": "DATABASE_URL not set"}
    try:
        from sqlalchemy import text  # lazy

        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"configured": True, "connected": True, "note": ""}
    except Exception as e:  # driver missing / auth / network / SSL — report, don't crash
        return {"configured": True, "connected": False, "note": f"{type(e).__name__}: {str(e)[:140]}"}
