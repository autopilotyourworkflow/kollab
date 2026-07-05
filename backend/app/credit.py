"""Credit meter for the bring-your-own-key flow.

Answers one question honestly: how much Apify credit does the key THIS request will
run on have left this billing cycle? The authoritative source is Apify's
`/v2/users/me/limits` — it returns the monthly cap AND current usage (the plain
`/v2/users/me` plan block reports usage as null on the free tier, so we don't use it).

Anthropic exposes no public balance endpoint, so for Claude we report only whether a
key is present and point at the console — never a fabricated number.

The parser is pure (tested with fakes); the fetch is lazy + resilient (any network or
dependency failure degrades to `checked=False` with the reason, never a crash).
"""

from __future__ import annotations

APIFY_LIMITS_URL = "https://api.apify.com/v2/users/me/limits"


def parse_apify_limits(payload: dict) -> dict:
    """Map Apify's /v2/users/me/limits response to the meter fields.

    Returns limit / used / remaining in USD (remaining only when both numbers are
    present) plus the cycle end. Missing/typeless values become None rather than 0,
    so the UI can say 'unreported' instead of implying a false balance."""
    data = payload.get("data", payload) if isinstance(payload, dict) else {}
    limits = data.get("limits") or {}
    current = data.get("current") or {}
    cycle = data.get("monthlyUsageCycle") or {}

    def _num(v):
        return round(float(v), 2) if isinstance(v, (int, float)) else None

    limit = _num(limits.get("maxMonthlyUsageUsd"))
    used = _num(current.get("monthlyUsageUsd"))
    remaining = round(max(0.0, limit - used), 2) if (limit is not None and used is not None) else None
    return {
        "limitUsd": limit,
        "usedUsd": used,
        "remainingUsd": remaining,
        "cycleEndAt": cycle.get("endAt") or None,
    }


def fetch_apify_credit(token: str | None, timeout: float = 12.0) -> dict:
    """Live Apify credit for `token`. Never raises: returns {checked: False, note}
    on any missing-key / missing-dep / network / parse failure. Never echoes the
    token."""
    empty = {"limitUsd": None, "usedUsd": None, "remainingUsd": None, "cycleEndAt": None}
    if not token:
        return {**empty, "checked": False, "note": "no Apify key on this request"}
    try:
        import httpx  # lazy: live-path dependency only
    except ImportError:
        return {**empty, "checked": False, "note": "httpx not installed (credit check needs .[live])"}
    try:
        r = httpx.get(APIFY_LIMITS_URL, params={"token": token}, timeout=timeout)
        r.raise_for_status()
        parsed = parse_apify_limits(r.json())
        return {**parsed, "checked": True, "note": ""}
    except Exception as e:  # network, auth, shape — all degrade honestly
        return {**empty, "checked": False, "note": f"Apify credit check failed: {type(e).__name__}"}
