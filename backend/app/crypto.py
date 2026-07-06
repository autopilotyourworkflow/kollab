"""Token encryption for the Apify key pool.

Pool tokens are full-account credentials that can spend money, so they are NEVER
stored in the clear. Each token is encrypted with Fernet (AES-128-CBC + HMAC) keyed
by KOLLAB_KEY_ENC_SECRET — a secret held only in the server's environment (Render),
never in the database. A database dump alone therefore yields ciphertext, not usable
keys. The plaintext token exists only in memory for the duration of a run.

`fingerprint()` is a one-way sha256 prefix used for dedup and safe log/UI correlation
— it can identify a key without ever exposing it.

Imports are lazy (like httpx / apify_client elsewhere) so the credential-free demo and
the non-pool test paths never require `cryptography`.
"""

from __future__ import annotations

import base64
import hashlib
import os


class EncryptionUnavailable(RuntimeError):
    """Raised when the pool needs to encrypt/decrypt but KOLLAB_KEY_ENC_SECRET is unset
    or the `cryptography` dependency is missing. Callers degrade to 'pool disabled'
    rather than crash — the env/BYOK key path keeps working."""


def enc_secret_present() -> bool:
    return bool((os.getenv("KOLLAB_KEY_ENC_SECRET") or "").strip())


def _fernet():
    secret = (os.getenv("KOLLAB_KEY_ENC_SECRET") or "").strip()
    if not secret:
        raise EncryptionUnavailable("KOLLAB_KEY_ENC_SECRET not set — cannot store pool keys securely.")
    try:
        from cryptography.fernet import Fernet  # lazy: pool-only dependency
    except ImportError as e:
        raise EncryptionUnavailable("`cryptography` not installed — `pip install cryptography` to use the key pool.") from e
    # Accept either a real 32-byte urlsafe Fernet key, or ANY passphrase (we derive a
    # stable key from it via sha256) so the operator can set a simple secret.
    try:
        return Fernet(secret.encode())
    except Exception:
        derived = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
        return Fernet(derived)


def encrypt_token(token: str) -> str:
    return _fernet().encrypt(token.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()


def fingerprint(token: str) -> str:
    """One-way, non-reversible short id for a token — safe to store/show/log. Used for
    dedup (same key added twice) and to label a key in the UI without revealing it."""
    return hashlib.sha256(token.encode()).hexdigest()[:12]


def mask(token: str) -> str:
    """A human-friendly masked hint (e.g. 'apify_api_…a1b2') — never the full token."""
    tail = token[-4:] if len(token) >= 4 else ""
    head = token[:10] if token.startswith("apify_api_") else token[:4]
    return f"{head}…{tail}"
