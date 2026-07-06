"""SQLAlchemy models for the durable store (Neon Postgres in production, SQLite for
local dev). Imported only when a database is in use — the credential-free demo path
never touches SQLAlchemy."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, String, Text
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
