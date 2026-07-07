"""Authentication primitives — password hashing + signed session tokens, pure stdlib.

Deliberately framework-free (no FastAPI import) and dependency-free: hashing is
`hashlib.scrypt` (a memory-hard KDF in the standard library) and the session token is
an HMAC-SHA256-signed blob, not a JWT library — the payload is two fields verified by a
single MAC, so a JWT lib would only add `alg`-confusion surface for no benefit.

The signing secret is derived from an ALREADY-configured secret (DATABASE_URL) when
KOLLAB_AUTH_SECRET isn't set, so auth goes live on a code-only deploy with no new env var
(and no Render Blueprint sync). With neither, `auth_available()` is False and every auth
path answers an honest 503 — exactly like the rest of the DB-backed surface.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from functools import lru_cache

# ── password hashing (scrypt) ────────────────────────────────────────────────
# n=2**14 (CPU/memory cost), r=8, p=1, 32-byte output, 16-byte salt. maxmem is set
# explicitly (64 MiB) because the ~16 MiB this needs sits near OpenSSL's 32 MiB default.
_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
_SCRYPT_MAXMEM = 64 * 1024 * 1024


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def hash_password(password: str) -> str:
    """Return a self-describing scrypt hash string `scrypt$n$r$p$salt$hash` (base64url).
    Params are embedded per-hash so a future cost bump still verifies old hashes."""
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R,
                        p=_SCRYPT_P, dklen=_SCRYPT_DKLEN, maxmem=_SCRYPT_MAXMEM)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str | None) -> bool:
    """Constant-time verify against a stored scrypt string. Returns False on any malformed
    or empty hash — never raises."""
    try:
        scheme, n, r, p, salt_b64, hash_b64 = (stored or "").split("$")
        if scheme != "scrypt":
            return False
        dk = hashlib.scrypt(password.encode("utf-8"), salt=_unb64(salt_b64),
                            n=int(n), r=int(r), p=int(p), dklen=len(_unb64(hash_b64)),
                            maxmem=_SCRYPT_MAXMEM)
        return hmac.compare_digest(dk, _unb64(hash_b64))
    except Exception:
        return False


# A fixed dummy hash so the login path can spend the same scrypt cost on an unknown
# email as on a real one — no user-enumeration timing gap.
_DUMMY_HASH = hash_password("kollab-dummy-invariant")


def normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


# ── signed session tokens (HMAC-SHA256) ──────────────────────────────────────
TOKEN_TTL_SECONDS = 30 * 24 * 3600  # 30 days


@lru_cache(maxsize=1)
def _signing_secret() -> bytes | None:
    """KOLLAB_AUTH_SECRET if set, else derived from the raw DATABASE_URL (an already-
    configured secret), else None. Uses the raw env value — NOT db.database_url()'s
    driver-normalized form — so a prefix rewrite can never shift the secret."""
    override = os.getenv("KOLLAB_AUTH_SECRET")
    if override:
        return override.encode("utf-8")
    db = os.getenv("DATABASE_URL")
    if db:
        return hashlib.sha256(b"kollab-auth:v1:" + db.encode("utf-8")).digest()
    return None


def auth_available() -> bool:
    """True when accounts can actually work: a signing secret AND a database. Requiring the
    DB too keeps the 'no DB -> honest 503' contract — a secret alone (e.g. KOLLAB_AUTH_SECRET
    set without DATABASE_URL) would otherwise pass the guard and then 500 in the DB layer."""
    return _signing_secret() is not None and os.getenv("DATABASE_URL") is not None


def reset_auth_cache() -> None:
    """Drop the cached signing secret (tests that swap env). Called from reset_db_cache."""
    _signing_secret.cache_clear()


def issue_token(uid: str, ttl: int = TOKEN_TTL_SECONDS) -> str:
    secret = _signing_secret()
    if secret is None:
        raise RuntimeError("No auth signing secret available.")
    payload = _b64(json.dumps({"uid": uid, "exp": int(time.time()) + ttl},
                              separators=(",", ":")).encode("utf-8"))
    sig = _b64(hmac.new(secret, payload.encode("ascii"), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def verify_token(token: str | None) -> str | None:
    """Return the uid for a valid, unexpired, correctly-signed token, else None. Never
    raises. Constant-time signature comparison."""
    secret = _signing_secret()
    if secret is None or not token or "." not in token:
        return None
    try:
        payload, sig = token.split(".", 1)
        expected = _b64(hmac.new(secret, payload.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(_unb64(payload))
        if int(data.get("exp", 0)) < int(time.time()):
            return None
        uid = data.get("uid")
        return uid if isinstance(uid, str) and uid else None
    except Exception:
        return None
