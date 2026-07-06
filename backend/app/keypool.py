"""Apify API-key POOL with automatic rotation.

The operator pastes several Apify account tokens (each free account carries $5/cycle).
This module is the single authority that (a) picks the fattest healthy key for a run,
(b) marks a key exhausted the instant it hits Apify's usage wall so the next run — and
the current run, mid-flight — transparently swaps to another, and (c) is refreshed on a
schedule so keys flip active -> low -> exhausted BEFORE a run reaches the wall.

Design ties into the existing seams:
  - selection replaces `settings.effective_apify_token` inside service.make_source
  - reactive swap wraps the one actor call site (ApifyAdapter._run_actor)
  - proactive refresh reuses credit.fetch_apify_credit (GET /v2/users/me/limits)

Tokens are stored encrypted (app.crypto) and NEVER returned over HTTP. Everything here
degrades honestly: if the DB is absent, the enc secret is unset, or `cryptography` is
missing, `available()` is False and the whole system falls back to the env/BYOK key —
exactly today's behavior.

The 'single source of truth' is the Neon row `status`, mutated only via `mark()`. A key
flipped to 'exhausted' is invisible to the very next `acquire()` in any thread/instance
(Postgres read-committed), so concurrent runs never grab a dead key.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from app.credit import fetch_apify_credit
from app.crypto import decrypt_token, enc_secret_present, encrypt_token, fingerprint, mask
from app.db import database_url, get_sessionmaker

APIFY_ME_URL = "https://api.apify.com/v2/users/me"

# USD thresholds (env-tunable). A key at/under MIN is exhausted; at/under LOW it is
# 'low' (still usable, but deprioritized behind any 'active' key).
LOW_USD = float(os.getenv("KOLLAB_KEY_LOW_USD", "1.0"))
MIN_USD = float(os.getenv("KOLLAB_KEY_MIN_USD", "0.25"))


def _low_usd() -> float:
    return float(os.getenv("KOLLAB_KEY_LOW_USD", "1.0"))


def _min_usd() -> float:
    return float(os.getenv("KOLLAB_KEY_MIN_USD", "0.25"))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Lease:
    """A key handed to one run. `token` is decrypted and in-memory only."""
    key_id: str
    label: str
    token: str


def available() -> bool:
    """True when the pool can operate: a DB is configured AND an encryption secret is
    set. When False, callers fall back to the env/BYOK token path (no regression)."""
    return bool(database_url()) and enc_secret_present() and get_sessionmaker() is not None


def _sm():
    sm = get_sessionmaker()
    if sm is None:
        raise RuntimeError("Key pool needs a database — set DATABASE_URL.")
    return sm


def _status_for(remaining) -> str | None:
    """Map a remaining-USD reading to a status, or None to leave status unchanged
    (e.g. balance unreported)."""
    if remaining is None:
        return None
    if remaining <= _min_usd():
        return "exhausted"
    if remaining <= _low_usd():
        return "low"
    return "active"


# ── selection (the run path) ────────────────────────────────────────────────
def acquire(exclude_ids: set[str] | None = None) -> Lease | None:
    """Pick the fattest usable key. Prefers active > low, then most credits_remaining
    (unchecked/None sorts last), then priority, then oldest. `exclude_ids` are keys the
    current run already burned, so a mid-run swap never re-hands the same dead key.
    Returns None when nothing usable remains."""
    from app.models import ApifyKey

    exclude = set(exclude_ids or ())
    with _sm()() as s:
        rows = [r for r in s.query(ApifyKey).filter(ApifyKey.status.in_(("active", "low"))).all()
                if r.id not in exclude]
        if not rows:
            return None

        def sort_key(r):
            credit = r.credits_remaining if r.credits_remaining is not None else float("-inf")
            return (
                0 if r.status == "active" else 1,   # active before low
                -credit,                            # more credit first; None last
                r.priority,
                r.added_at or _utcnow(),
            )

        best = min(rows, key=sort_key)
        best.last_used_at = _utcnow()
        s.commit()
        return Lease(key_id=best.id, label=best.label, token=decrypt_token(best.token_encrypted))


def mark(key_id: str, status: str, error: str | None = None) -> None:
    """Atomically flip a key's status — the swap primitive. Once 'exhausted'/'invalid',
    the next acquire() in any thread/instance stops selecting it."""
    from app.models import ApifyKey

    with _sm()() as s:
        row = s.get(ApifyKey, key_id)
        if row is None:
            return
        row.status = status
        if error is not None:
            row.last_error = error[:500]
        s.commit()


# ── management (operator, admin-gated at the HTTP layer) ─────────────────────
def _validate_token(token: str) -> tuple[bool, int, str]:
    """Live liveness check: GET /v2/users/me. (True, 200, '') when the token is valid;
    otherwise (False, http_status_to_return, message). Never raises."""
    try:
        import httpx  # lazy: live-path dep
    except ImportError:
        # Can't reach out offline — accept, but the first real run/refresh will catch a
        # bad key reactively (401 -> invalid).
        return (True, 200, "")
    try:
        r = httpx.get(APIFY_ME_URL, params={"token": token}, timeout=12.0)
    except Exception as e:
        return (False, 502, f"Could not reach Apify to validate the key: {type(e).__name__}")
    if r.status_code == 401:
        return (False, 400, "Apify rejected this token (invalid or revoked).")
    if r.status_code != 200:
        return (False, 400, f"Apify returned HTTP {r.status_code} validating this token.")
    return (True, 200, "")


def add_key(token: str, label: str = "") -> dict:
    """Validate a pasted token live, seed its balance, and insert it as a pool key.
    Dedups on fingerprint (adding the same key twice is a 409, not a duplicate).
    Returns {ok: True, key: <public dict>} or {ok: False, status, error}."""
    from app.models import ApifyKey

    token = (token or "").strip()
    if not token:
        return {"ok": False, "status": 400, "error": "Paste an Apify token first."}
    if not available():
        return {"ok": False, "status": 503,
                "error": "Key pool is disabled — set DATABASE_URL and KOLLAB_KEY_ENC_SECRET on the server."}

    ok, status, err = _validate_token(token)
    if not ok:
        return {"ok": False, "status": status, "error": err}

    bal = fetch_apify_credit(token)
    remaining = bal.get("remainingUsd")
    init_status = _status_for(remaining) or "active"
    fp = fingerprint(token)

    with _sm()() as s:
        if s.query(ApifyKey).filter(ApifyKey.token_fingerprint == fp).first():
            return {"ok": False, "status": 409, "error": "This key is already in the pool."}
        row = ApifyKey(
            id=uuid.uuid4().hex,
            label=(label or "").strip() or f"account-{fp[:6]}",
            token_encrypted=encrypt_token(token),
            token_fingerprint=fp,
            token_hint=mask(token),
            status=init_status,
            credits_remaining=remaining,
            credits_limit=bal.get("limitUsd"),
            credits_checked_at=_utcnow(),
            cycle_end_at=_parse_ts(bal.get("cycleEndAt")),
            priority=100,
            added_at=_utcnow(),
        )
        s.add(row)
        s.commit()
        return {"ok": True, "key": row.to_public_dict()}


def refresh_all() -> dict:
    """Poll Apify balance for every non-disabled key and flip status accordingly. A
    transient/unreachable poll never yanks a key — it only records the check time; status
    changes only on a real balance read (or reactively on a run's 402/401). Exhausted
    keys auto-reactivate once the billing cycle refills. Never raises."""
    from app.models import ApifyKey

    if not available():
        return {"checked": 0, "note": "pool disabled"}
    with _sm()() as s:
        ids = [r.id for r in s.query(ApifyKey).filter(ApifyKey.status != "disabled").all()]

    checked = 0
    for kid in ids:
        with _sm()() as s:
            row = s.get(ApifyKey, kid)
            if row is None:
                continue
            info = fetch_apify_credit(decrypt_token(row.token_encrypted))
            row.credits_checked_at = _utcnow()
            if not info.get("checked"):
                row.last_error = info.get("note") or row.last_error
            else:
                row.credits_remaining = info.get("remainingUsd")
                row.credits_limit = info.get("limitUsd")
                row.cycle_end_at = _parse_ts(info.get("cycleEndAt")) or row.cycle_end_at
                row.last_error = None
                new_status = _status_for(info.get("remainingUsd"))
                if new_status and row.status in ("active", "low", "exhausted"):
                    row.status = new_status  # incl. auto-reactivate after cycle reset
            s.commit()
            checked += 1
    return {"checked": checked}


def list_public() -> list[dict]:
    from app.models import ApifyKey

    if not available():
        return []
    with _sm()() as s:
        rows = s.query(ApifyKey).order_by(ApifyKey.added_at.asc()).all()
        return [r.to_public_dict() for r in rows]


def summary() -> dict:
    from app.models import ApifyKey

    if not available():
        return {"enabled": False, "active": 0, "low": 0, "exhausted": 0, "invalid": 0,
                "total": 0, "totalRemainingUsd": None}
    with _sm()() as s:
        rows = s.query(ApifyKey).all()
    counts = {"active": 0, "low": 0, "exhausted": 0, "invalid": 0, "disabled": 0}
    total_rem = 0.0
    have_rem = False
    for r in rows:
        counts[r.status] = counts.get(r.status, 0) + 1
        if r.credits_remaining is not None:
            total_rem += r.credits_remaining
            have_rem = True
    return {
        "enabled": True,
        "active": counts["active"],
        "low": counts["low"],
        "exhausted": counts["exhausted"],
        "invalid": counts["invalid"],
        "total": len(rows),
        "totalRemainingUsd": round(total_rem, 2) if have_rem else None,
    }


def remove(key_id: str) -> bool:
    from app.models import ApifyKey

    if not available():
        return False
    with _sm()() as s:
        row = s.get(ApifyKey, key_id)
        if row is None:
            return False
        s.delete(row)
        s.commit()
        return True


def _parse_ts(value) -> datetime | None:
    """Best-effort ISO -> aware datetime; None on anything unusable."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
