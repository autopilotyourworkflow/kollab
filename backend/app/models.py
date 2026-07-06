"""SQLAlchemy models for the durable store (Neon Postgres in production, SQLite for
local dev). Imported only when a database is in use — the credential-free demo path
never touches SQLAlchemy."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Float, Index, Integer, String, Text
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


class CommenterEdge(Base):
    """One accumulated edge of the cross-run commenter graph: a commenter account
    (`commenter_uid`, TikTok's stable id — the same field the fraud detector reads) was
    observed commenting on a creator (`creator_id`). The composite primary key makes
    re-recording the same observation a no-op, so the graph only grows.

    Deliberately GLOBAL (no brand column): a pod sighting funded by brand A protects
    brand B on the next campaign. That accumulating, cross-brand graph is the moat —
    fraud recall improves every run because a pod undersampled today is known tomorrow.
    See app.fraud.graph for the store + the honest augment/withhold rules."""

    __tablename__ = "commenter_edges"

    commenter_uid = Column(String, primary_key=True)
    creator_id = Column(String, primary_key=True)
    first_seen = Column(DateTime(timezone=True), default=_utcnow)
    last_seen = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    source = Column(String, nullable=False, default="")  # "seed" | "apify"

    __table_args__ = (Index("ix_commenter_edges_creator", "creator_id"),)


class Delivery(Base):
    """A logged campaign OUTCOME: what a booked creator's paid post actually delivered
    vs the reach Kollab projected at booking. This is the only source of outcome truth —
    Apify/public data carries none — so the ledger is empty until the user logs a
    delivery, and the re-rank nudge it feeds is bounded + labelled 'estimated, from your
    N deliveries', never fabricated. See app.ledger + app.matching.delivery."""

    __tablename__ = "deliveries"

    id = Column(String, primary_key=True)
    brand = Column(String, nullable=False, default="")
    handle = Column(String, nullable=False, index=True)  # normalized (store.norm_handle)
    projected_views = Column(Integer, nullable=False, default=0)  # measured median at booking
    actual_views = Column(Integer, nullable=False, default=0)     # user-entered outcome
    ratio = Column(Float, nullable=False, default=0.0)            # actual / projected
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "brand": self.brand,
            "handle": self.handle,
            "projectedViews": self.projected_views,
            "actualViews": self.actual_views,
            "ratio": round(self.ratio, 3),
            "note": self.note,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
