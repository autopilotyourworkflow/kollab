"""Apify key rotation — straight from environment variables. No database, no UI.

The operator sets APIFY_TOKEN_1, APIFY_TOKEN_2, APIFY_TOKEN_3, ... (and/or the legacy
APIFY_TOKEN) in the server environment (Render). Kollab uses them in order and swaps
to the next automatically when one runs low or hits Apify's usage wall:

  - reactive  — a 402/403/x402/invalid-token error on the current key marks it drained
    (in memory) and the run retries on the next key, mid-flight (see ApifyAdapter).
  - proactive — a background refresher (main._start_key_refresher) polls each key's
    Apify balance every KOLLAB_KEY_REFRESH_MINUTES and drains the low/empty ones, so
    runs skip them BEFORE hitting the wall. Drained keys auto-recover when Apify's
    monthly cycle refills, or on process restart.

State is a small in-memory set of drained fingerprints — self-healing: the refresher
re-evaluates on boot and the reactive path re-marks on error. Tokens live only in the
environment + memory; they are never written to disk, logged, or returned over HTTP.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass

from app.credit import fetch_apify_credit


def _min_usd() -> float:
    """A key with less than this many USD left is skipped (swap 'when low'). Default $0.50."""
    try:
        return float(os.getenv("KOLLAB_KEY_MIN_USD", "0.50"))
    except ValueError:
        return 0.50


def _fp(token: str) -> str:
    """Short, one-way id for a token — safe to log/show; never reveals the token."""
    return hashlib.sha256(token.encode()).hexdigest()[:12]


def _mask(token: str) -> str:
    tail = token[-4:] if len(token) >= 4 else ""
    return f"apify_api_…{tail}" if token.startswith("apify_api_") else f"…{tail}"


@dataclass
class Lease:
    key_id: str   # fingerprint
    label: str    # env var name it came from (APIFY_TOKEN_2, ...)
    token: str


# Fingerprints of keys currently considered drained/unusable -> reason (in-memory,
# per process; reset on restart, re-derived by the refresher + reactive path).
_drained: dict[str, str] = {}


def env_tokens() -> list[tuple[str, str]]:
    """Ordered [(label, token)]: APIFY_TOKEN first (legacy), then APIFY_TOKEN_1..N in
    numeric order. Blanks and duplicate tokens removed."""
    candidates: list[tuple[str, str]] = []
    base = (os.getenv("APIFY_TOKEN") or "").strip()
    if base:
        candidates.append(("APIFY_TOKEN", base))
    numbered: list[tuple[int, str, str]] = []
    for name, value in os.environ.items():
        m = re.fullmatch(r"APIFY_TOKEN_(\d+)", name)
        if m and (value or "").strip():
            numbered.append((int(m.group(1)), name, value.strip()))
    numbered.sort()
    for _, name, value in numbered:
        candidates.append((name, value))

    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for label, tok in candidates:
        if tok not in seen:
            seen.add(tok)
            out.append((label, tok))
    return out


def available() -> bool:
    """True when at least one operator token is configured in the environment."""
    return len(env_tokens()) > 0


def acquire(exclude_ids: set[str] | None = None) -> Lease | None:
    """The first env token that isn't excluded and isn't currently drained. Order is
    APIFY_TOKEN then _1.._N, so Kollab burns them predictably in sequence. `exclude_ids`
    are keys the current run already tried, so a mid-run swap never re-hands a dead one."""
    exclude = set(exclude_ids or ())
    for label, tok in env_tokens():
        fp = _fp(tok)
        if fp in exclude or fp in _drained:
            continue
        return Lease(key_id=fp, label=label, token=tok)
    return None


def mark(key_id: str, status: str, error: str | None = None) -> None:
    """Reactive swap primitive. 'exhausted'/'invalid' -> drained (skipped by acquire);
    'active' -> recovered."""
    if status in ("exhausted", "invalid"):
        _drained[key_id] = (error or status)[:200]
    elif status == "active":
        _drained.pop(key_id, None)


def refresh_all() -> dict:
    """Proactive: poll each env token's live Apify balance and drain the low/empty ones
    so runs skip them before hitting the wall; recover any that refilled. A transient /
    unreported reading never drains a key. Never raises."""
    tokens = env_tokens()
    if not tokens:
        return {"checked": 0, "keys": 0}
    minimum = _min_usd()
    checked = 0
    for _label, tok in tokens:
        fp = _fp(tok)
        info = fetch_apify_credit(tok)
        if not info.get("checked"):
            continue  # network/parse blip — leave the key as-is
        checked += 1
        rem = info.get("remainingUsd")
        if rem is None:
            continue
        if rem <= minimum:
            _drained[fp] = f"low balance (${rem:.2f})"
        else:
            _drained.pop(fp, None)  # healthy (e.g. monthly refill)
    return {"checked": checked, "keys": len(tokens)}


def status() -> dict:
    """Operator health view (NO tokens): key count, how many are healthy, and each
    key's env-var name + masked hint + drained reason. Safe to surface in /health."""
    tokens = env_tokens()
    keys = []
    healthy = 0
    for label, tok in tokens:
        fp = _fp(tok)
        drained = fp in _drained
        if not drained:
            healthy += 1
        keys.append({
            "label": label,
            "hint": _mask(tok),
            "fingerprint": fp,
            "healthy": not drained,
            "note": _drained.get(fp),
        })
    return {"enabled": bool(tokens), "count": len(tokens), "healthy": healthy, "keys": keys}
