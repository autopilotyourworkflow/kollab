"""Run-history store: which creators each brand has already pulled.

Powers Expand runs — "get me MORE" never re-buys evidence the brand already
holds: known handles are excluded from the next pull's comment sampling (the
dominant cost) and the creator slots fill with NEW creators instead.

Single-tenant, stdlib sqlite3, one table. `KOLLAB_DB` points elsewhere for a
persistent volume; the default lives next to the app (gitignored). Honesty
note for free-tier hosts with ephemeral disks (e.g. Render free): the history
resets on redeploy — set KOLLAB_DB to a mounted disk or managed DB for
durability. Losing it is safe: the worst case is re-buying data, never wrong
results.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _db_path() -> Path:
    return Path(os.getenv("KOLLAB_DB") or Path(__file__).resolve().parents[1] / "kollab.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.execute(
        "CREATE TABLE IF NOT EXISTS run_creators ("
        "  brand TEXT NOT NULL,"
        "  handle TEXT NOT NULL,"
        "  first_seen TEXT NOT NULL,"
        "  PRIMARY KEY (brand, handle))"
    )
    return conn


def norm_handle(handle: str) -> str:
    return handle.strip().lstrip("@").lower()


def _norm_brand(brand: str) -> str:
    return brand.strip().lower()


def known_handles(brand: str) -> set[str]:
    """Normalized handles this brand has already pulled (empty set if none)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT handle FROM run_creators WHERE brand = ?", (_norm_brand(brand),)
        ).fetchall()
    return {r[0] for r in rows}


def record_run(brand: str, handles: list[str]) -> int:
    """Remember this run's creators; returns how many were new to the brand."""
    now = datetime.now(timezone.utc).isoformat()
    rows = [(_norm_brand(brand), norm_handle(h), now) for h in handles if h.strip()]
    if not rows:
        return 0
    with _connect() as conn:
        before = conn.total_changes
        conn.executemany(
            "INSERT OR IGNORE INTO run_creators (brand, handle, first_seen) VALUES (?, ?, ?)",
            rows,
        )
        return conn.total_changes - before
