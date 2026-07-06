"""SQLAlchemy models for the durable store (Neon Postgres in production, SQLite for
local dev). Imported only when a database is in use — the credential-free demo path
never touches SQLAlchemy."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Run(Base):
    """An async sourcing run: started by POST /api/runs, executed in a background
    thread, polled via GET /api/runs/{id}. The result is the camelCase
    ShortlistResponse the frontend merges into its shortlist."""

    __tablename__ = "runs"

    id = Column(String, primary_key=True)
    brand = Column(String, nullable=False, default="")
    preset = Column(String, nullable=False, default="standard")
    status = Column(String, nullable=False, default="queued", index=True)  # queued|running|done|error
    brief = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)  # ShortlistResponse (by alias / camelCase)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "brand": self.brand,
            "preset": self.preset,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class ApifyKey(Base):
    """One operator-owned Apify account in the rotation pool. The token is stored
    ENCRYPTED (never plaintext); the row otherwise carries only balance + status so
    the selector can pick the fattest healthy key and swap off exhausted ones.

    `status`: active (usable) | low (below the soft threshold, deprioritized) |
    exhausted (hit the wall / near-zero, not selected until the cycle resets) |
    invalid (token rejected by Apify) | disabled (parked by the operator).

    Auto-created by init_db() alongside `runs` — it subclasses the same Base."""

    __tablename__ = "apify_keys"

    id = Column(String, primary_key=True)
    label = Column(String, nullable=False, default="")
    token_encrypted = Column(Text, nullable=False)          # Fernet ciphertext — never the raw token
    token_fingerprint = Column(String, nullable=False, unique=True, index=True)  # sha256[:12]
    token_hint = Column(String, nullable=False, default="")  # masked display hint, e.g. apify_api_…a1b2
    status = Column(String, nullable=False, default="active", index=True)
    credits_remaining = Column(Float, nullable=True)         # USD, null = unreported
    credits_limit = Column(Float, nullable=True)             # maxMonthlyUsageUsd
    credits_checked_at = Column(DateTime(timezone=True), nullable=True)
    cycle_end_at = Column(DateTime(timezone=True), nullable=True)
    priority = Column(Integer, nullable=False, default=100)  # tie-break; lower = preferred
    added_at = Column(DateTime(timezone=True), default=_utcnow)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)

    def to_public_dict(self) -> dict:
        """Everything the UI/logs may see — NEVER the token or its ciphertext."""
        return {
            "id": self.id,
            "label": self.label,
            "hint": self.token_hint,
            "fingerprint": self.token_fingerprint,
            "status": self.status,
            "remainingUsd": self.credits_remaining,
            "limitUsd": self.credits_limit,
            "checkedAt": self.credits_checked_at.isoformat() if self.credits_checked_at else None,
            "cycleEndAt": self.cycle_end_at.isoformat() if self.cycle_end_at else None,
            "lastError": self.last_error,
        }
