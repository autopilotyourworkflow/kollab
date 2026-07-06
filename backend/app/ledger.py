"""Delivery ledger — durable campaign OUTCOMES (Neon), the input to the closed loop.

Mirrors app.runs: a thin _session() over the shared engine; the endpoints that write/read
require a DATABASE_URL (they answer 503 without one), while the PIPELINE reads through
ratios_map(), which degrades to {} with no DB so the shortlist is byte-identical. Model
imports are lazy so the credential-free install never needs SQLAlchemy.
"""

from __future__ import annotations

import uuid

from app.db import get_sessionmaker
from app.matching.delivery import delivery_adjustment
from app.store import norm_handle


def _session():
    factory = get_sessionmaker()
    if factory is None:
        raise RuntimeError("No database configured — set DATABASE_URL to enable the delivery ledger.")
    return factory()


def record_delivery(brand: str, handle: str, projected_views: int, actual_views: int,
                    note: str | None = None) -> dict:
    from app.models import Delivery
    proj = max(1, int(projected_views))
    act = max(0, int(actual_views))
    row = Delivery(id=uuid.uuid4().hex, brand=brand or "", handle=norm_handle(handle),
                   projected_views=proj, actual_views=act, ratio=act / proj, note=note)
    with _session() as s:
        s.add(row)
        s.commit()
        return row.to_dict()


def deliveries_for(handle: str) -> list[dict]:
    from app.models import Delivery
    h = norm_handle(handle)
    with _session() as s:
        rows = (s.query(Delivery).filter(Delivery.handle == h)
                .order_by(Delivery.created_at.desc()).all())
        return [r.to_dict() for r in rows]


def _ratios_for(handle: str) -> list[float]:
    from app.models import Delivery
    h = norm_handle(handle)
    with _session() as s:
        return [r[0] for r in s.query(Delivery.ratio).filter(Delivery.handle == h).all()]


def reliability(handle: str) -> dict:
    """{handle, n, meanRatio, adjustment, note} for one creator (assumes a DB is configured)."""
    ratios = _ratios_for(handle)
    adj, note = delivery_adjustment(ratios)
    mean = sum(ratios) / len(ratios) if ratios else None
    return {"handle": norm_handle(handle), "n": len(ratios),
            "meanRatio": round(mean, 3) if mean is not None else None,
            "adjustment": adj, "note": note}


def ratios_map() -> dict[str, list[float]]:
    """All deliveries grouped by normalized handle -> [ratios]. Best-effort: {} with no DB
    or on any error, so the pipeline nudge is a no-op and the seed shortlist is unchanged."""
    if get_sessionmaker() is None:
        return {}
    try:
        from app.models import Delivery
        out: dict[str, list[float]] = {}
        with _session() as s:
            for handle, ratio in s.query(Delivery.handle, Delivery.ratio).all():
                out.setdefault(handle, []).append(ratio)
        return out
    except Exception:
        return {}
