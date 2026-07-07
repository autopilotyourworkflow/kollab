"""Accounts + shortlists persistence (Neon). Mirrors app.runs / app.ledger: a thin
_session() over the shared engine, honest failure with no DATABASE_URL, and the workspace
CRUD scoped to the owning user.

Mutations to the single JSON `data` blob (append kols, set a decision, mark live) fetch the
row `with_for_update()` and reassign a FRESH dict (SQLAlchemy doesn't track in-place JSON
mutation), so a RunDock merge and a decision click on the same shortlist can't lose an
update — matching today's per-field last-write-wins with no torn write.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.auth import hash_password, normalize_email
from app.db import get_sessionmaker
from app.models import Shortlist, User


def _session():
    factory = get_sessionmaker()
    if factory is None:
        raise RuntimeError("No database configured — set DATABASE_URL to enable accounts.")
    return factory()


def _aware(dt: datetime | None) -> datetime | None:
    """Normalize a DB datetime to aware-UTC. SQLite (tests) returns tz-naive values for a
    timezone=True column; Postgres returns aware. This makes comparisons work on both."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


# ── users ────────────────────────────────────────────────────────────────────
def create_user(email: str, password: str) -> dict:
    """Insert a real account. A duplicate email raises (caller maps to 409)."""
    with _session() as s:
        row = User(id=uuid.uuid4().hex, email=normalize_email(email),
                   password_hash=hash_password(password), is_guest=False)
        s.add(row)
        s.commit()
        return row.to_dict()


def create_guest() -> dict:
    with _session() as s:
        row = User(id=uuid.uuid4().hex, email=None, password_hash=None, is_guest=True)
        s.add(row)
        s.commit()
        return row.to_dict()


def get_user(uid: str) -> dict | None:
    from datetime import timedelta
    with _session() as s:
        row = s.get(User, uid)
        if row is None:
            return None
        # throttled liveness bump (guest reaping reads last_seen_at) — at most daily
        now = datetime.now(timezone.utc)
        last = _aware(row.last_seen_at)
        if last is None or last < now - timedelta(hours=24):
            row.last_seen_at = now
            s.commit()
        return row.to_dict()


def find_by_email(email: str) -> dict | None:
    """Login lookup: {id, password_hash} or None. Email is normalized."""
    with _session() as s:
        row = s.query(User).filter(User.email == normalize_email(email)).one_or_none()
        return {"id": row.id, "password_hash": row.password_hash} if row else None


# ── shortlists (user-scoped) ─────────────────────────────────────────────────
def _entry_data(payload: dict) -> dict:
    """Build the stored `data` blob from a create request. Server owns id/runs; decisions
    default from each kol's hitl status when absent."""
    kols = payload.get("kols") or []
    decisions = payload.get("decisions")
    if not isinstance(decisions, dict):
        decisions = {k["id"]: {"status": k.get("hitl", "pending")} for k in kols if k.get("id")}
    return {
        "brief": payload.get("brief"),
        "kols": kols,
        "decisions": decisions,
        "screened": int(payload.get("screened") or len(kols)),
        "runs": int(payload.get("runs") or 1),
        "source": payload.get("source") or "fixtures",
        "cost": payload.get("cost") or {"usd": 0, "seconds": 0, "cacheHitRate": 0},
        "commenterOverlap": payload.get("commenterOverlap") or [],
    }


def list_shortlists(uid: str) -> list[dict]:
    with _session() as s:
        rows = (s.query(Shortlist).filter(Shortlist.user_id == uid)
                .order_by(Shortlist.updated_at.desc()).all())
        return [r.to_entry() for r in rows]


def get_shortlist(uid: str, sid: str) -> dict | None:
    with _session() as s:
        row = (s.query(Shortlist)
               .filter(Shortlist.id == sid, Shortlist.user_id == uid).one_or_none())
        return row.to_entry() if row else None


def create_shortlist(uid: str, payload: dict) -> dict:
    with _session() as s:
        row = Shortlist(id=uuid.uuid4().hex, user_id=uid, data=_entry_data(payload))
        s.add(row)
        s.commit()
        return row.to_entry()


def _locked(s, uid: str, sid: str):
    return (s.query(Shortlist)
            .filter(Shortlist.id == sid, Shortlist.user_id == uid)
            .with_for_update().one_or_none())


def append_kols(uid: str, sid: str, incoming: list[dict]) -> dict | None:
    """Merge NEW creators (dedup by handle). Returns {'added', 'entry'} or None if not owned."""
    with _session() as s:
        row = _locked(s, uid, sid)
        if row is None:
            return None
        data = dict(row.data or {})
        kols = list(data.get("kols") or [])
        have = {str(k.get("handle", "")).lower() for k in kols}
        fresh = [k for k in incoming if str(k.get("handle", "")).lower() not in have]
        if fresh:
            decisions = dict(data.get("decisions") or {})
            for k in fresh:
                if k.get("id") and k["id"] not in decisions:
                    decisions[k["id"]] = {"status": k.get("hitl", "pending")}
            data["kols"] = kols + fresh
            data["decisions"] = decisions
            data["screened"] = int(data.get("screened") or len(kols)) + len(fresh)
            data["runs"] = int(data.get("runs") or 1) + 1
            row.data = data  # reassign so SQLAlchemy tracks the JSON change
            s.commit()
        return {"added": len(fresh), "entry": row.to_entry()}


def set_decision(uid: str, sid: str, kol_id: str, decision: dict) -> bool:
    with _session() as s:
        row = _locked(s, uid, sid)
        if row is None:
            return False
        data = dict(row.data or {})
        decisions = dict(data.get("decisions") or {})
        status = decision.get("status", "pending")
        decisions[kol_id] = {"status": "pending"} if status == "pending" else {
            "status": status, **({"reason": decision["reason"]} if decision.get("reason") else {})
        }
        data["decisions"] = decisions
        row.data = data
        s.commit()
        return True


def mark_source_live(uid: str, sid: str) -> dict | None:
    with _session() as s:
        row = _locked(s, uid, sid)
        if row is None:
            return None
        data = dict(row.data or {})
        if data.get("source") != "api":
            data["source"] = "api"
            row.data = data
            s.commit()
        return row.to_entry()


def delete_shortlist(uid: str, sid: str) -> bool:
    with _session() as s:
        n = s.query(Shortlist).filter(Shortlist.id == sid, Shortlist.user_id == uid).delete()
        s.commit()
        return bool(n)


def seed_guest_workspace(uid: str) -> dict:
    """Seed a guest's workspace with the demo Glow Lab shortlist (the pipeline's own seed
    output, no LLM spend) so the Dashboard is non-empty on first click."""
    from app.pipeline import build_shortlist
    from app.sources.seed import SeedDatasetSource
    resp = build_shortlist(SeedDatasetSource()).model_dump(by_alias=True)
    payload = {
        "brief": resp["brief"],
        "kols": resp["kols"],
        "screened": resp["screened"],
        "source": "fixtures",
        "cost": resp["cost"],
        "commenterOverlap": resp.get("commenterOverlap") or [],
    }
    return create_shortlist(uid, payload)


def reap_guests(max_age_days: int = 30) -> int:
    """Best-effort cleanup: delete idle guest users + their shortlists. Returns users removed.
    Compares last_seen in Python so it's correct on both SQLite (naive) and Postgres (aware)."""
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    with _session() as s:
        stale_ids = [
            uid for uid, last in s.query(User.id, User.last_seen_at)
            .filter(User.is_guest.is_(True)).all()
            if _aware(last) is not None and _aware(last) < cutoff
        ]
        if not stale_ids:
            return 0
        s.query(Shortlist).filter(Shortlist.user_id.in_(stale_ids)).delete(synchronize_session=False)
        n = s.query(User).filter(User.id.in_(stale_ids)).delete(synchronize_session=False)
        s.commit()
        return int(n)
