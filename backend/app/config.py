"""Runtime configuration. Fixtures mode is the default so the deployed demo and
the test suite run with zero credentials. Env is read when get_settings() is
called (default_factory), not at import — so tests and process managers that set
env late see what they set."""

from __future__ import annotations

import contextvars
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Load backend/.env into the environment on import (local dev convenience). Does
# nothing on hosts that inject real env vars (no .env present, e.g. Render), and
# never overrides an already-set variable. Optional dep: the credential-free
# minimal install without python-dotenv simply skips it.
def _load_local_dotenv() -> None:
    # Never read the developer's real .env during tests — the suite must be
    # hermetic (each test sets its own env via monkeypatch).
    if "pytest" in sys.modules:
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


_load_local_dotenv()

# Apify actor prices, verified in the pre-flight spike (2026-07-02). Used both to
# project the cost meter and to enforce the live-run budget cap.
PRICE_PER_1K_COMMENTS = 0.50   # clockworks/tiktok-comments-scraper
PRICE_PER_1K_RESULTS = 1.70    # clockworks/tiktok-scraper

# Fair-rate estimator: placeholder CPM (THB per 1,000 organic views). This is an operator
# ASSUMPTION, editable per-creator in the UI — deliberately NOT a market rate card and NOT
# tier/vertical-varied (that would be a fabricated benchmark; the locked scope forbids it).
# The estimate is only ever this number applied to the creator's OWN measured organic reach,
# discounted by authenticity. Override the default with KOLLAB_DEFAULT_CPM_THB.
DEFAULT_CPM_THB = float(os.getenv("KOLLAB_DEFAULT_CPM_THB") or 150.0)


# ── Bring-your-own-key: per-request credential override ──────────────────────
# The reviewer can paste their OWN Apify / Anthropic key in the frontend Settings
# page; those keys ride each API call as headers and are set here for the duration
# of the request only — never written to disk, never logged, never returned. A
# request without them falls back to the operator's env keys ONLY while sharing is
# on (KOLLAB_SHARED_KEY). This ContextVar is per-asyncio-task, so requests never
# see each other's keys.
_request_credentials: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "kollab_request_credentials", default=None
)


def set_request_credentials(apify_token: str | None, anthropic_api_key: str | None):
    """Install per-request key overrides; returns a reset token for the finally block.
    Empty/whitespace values are treated as absent (no override for that key)."""
    override = {
        "apify_token": (apify_token or "").strip() or None,
        "anthropic_api_key": (anthropic_api_key or "").strip() or None,
    }
    if not override["apify_token"] and not override["anthropic_api_key"]:
        override = None  # nothing supplied -> pure operator/env resolution
    return _request_credentials.set(override)


def reset_request_credentials(token) -> None:
    _request_credentials.reset(token)


def _resolve_key(override_key: str, owner_value: str | None, shared: bool) -> str | None:
    """Effective key = the request's own key if supplied, else the operator's env
    key while sharing is on, else nothing (the honest 'bring your own key' path)."""
    ov = _request_credentials.get()
    if ov and ov.get(override_key):
        return ov[override_key]
    return owner_value if shared else None


def request_override_present(override_key: str) -> bool:
    """True when THIS request supplied its own value for override_key (used to label
    the credit meter 'your key' vs 'shared key')."""
    ov = _request_credentials.get()
    return bool(ov and ov.get(override_key))


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as e:
        raise RuntimeError(f"{name} must be an integer, got {raw!r}") from e


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as e:
        raise RuntimeError(f"{name} must be a number, got {raw!r}") from e


@dataclass(frozen=True)
class Settings:
    # Candidate source: "seed" (fixtures) or "apify" (live public-data sampling via
    # the budget-capped ApifyAdapter actor-run loop; a run with no key is an honest 503).
    source: str = field(default_factory=lambda: os.getenv("KOLLAB_SOURCE", "seed"))

    # Optional credentials — read and surfaced in /health. The live paths they
    # unlock (Apify actor loop, LLM Brand-DNA + citation-validated rerank) are
    # implemented and token-activated — honest 4xx/503 only when a key is absent.
    apify_token: str | None = field(default_factory=lambda: os.getenv("APIFY_TOKEN") or None)
    anthropic_api_key: str | None = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY") or None)
    gemini_api_key: str | None = field(default_factory=lambda: os.getenv("GEMINI_API_KEY") or None)

    # Minimum cohort size before an outlier signal is allowed to fire. Below this
    # the badge reads "insufficient baseline — signal withheld" (see fraud.cohort).
    min_cohort_n: int = field(default_factory=lambda: _env_int("KOLLAB_MIN_COHORT_N", 15))

    # Sourcing region (ISO country) — routes the TikTok scraper through this
    # country's proxy so search returns local creators. Default Thailand (the
    # target market); "None"/"" scrapes globally.
    region: str = field(default_factory=lambda: os.getenv("KOLLAB_REGION", "TH"))

    # Hard USD cap for one live Apify sourcing run. The adapter stops fetching
    # before the projected spend crosses this line (never mid-actor surprises).
    run_budget_usd: float = field(default_factory=lambda: _env_float("KOLLAB_RUN_BUDGET_USD", 5.0))

    # LLM models (env-overridable). Claude leads; Gemini is the degradation fallback.
    claude_model: str = field(default_factory=lambda: os.getenv("KOLLAB_CLAUDE_MODEL", "claude-sonnet-5"))
    gemini_model: str = field(default_factory=lambda: os.getenv("KOLLAB_GEMINI_MODEL", "gemini-2.5-flash"))

    # LLM rerank of the top of the shortlist (citation-validated). On by default
    # when a key exists; force off with KOLLAB_LLM_RERANK=0.
    llm_rerank: bool = field(
        default_factory=lambda: os.getenv("KOLLAB_LLM_RERANK", "1").strip().lower() not in ("0", "false", "no")
    )

    # Share the operator's own keys as the fallback for visitors who haven't pasted
    # their own (KOLLAB_SHARED_KEY=1, default). Flip to 0 to STOP spending the
    # operator's credit — live runs then require the visitor's own key (seed/demo
    # mode still works free). The one-line kill switch for "I'm running low".
    shared_key: bool = field(
        default_factory=lambda: os.getenv("KOLLAB_SHARED_KEY", "1").strip().lower() not in ("0", "false", "no")
    )

    @property
    def apify_enabled(self) -> bool:
        """Operator has an Apify token configured (env). Reported in /health."""
        return bool(self.apify_token)

    @property
    def llm_enabled(self) -> bool:
        """Operator has an LLM key configured (env). Reported in /health."""
        return bool(self.anthropic_api_key or self.gemini_api_key)

    # ── Effective keys: what THIS request actually runs on (request key > shared
    #    operator key > nothing). The live paths all read these, never the raw env
    #    fields, so a reviewer's pasted key transparently takes over.
    @property
    def effective_apify_token(self) -> str | None:
        return _resolve_key("apify_token", self.apify_token, self.shared_key)

    @property
    def effective_anthropic_api_key(self) -> str | None:
        return _resolve_key("anthropic_api_key", self.anthropic_api_key, self.shared_key)

    @property
    def effective_gemini_api_key(self) -> str | None:
        # Gemini is the operator's env-only degradation fallback; withheld when
        # sharing is off (no per-request Gemini override — scope is Claude/Apify).
        return self.gemini_api_key if self.shared_key else None

    @property
    def effective_apify_enabled(self) -> bool:
        return bool(self.effective_apify_token)

    @property
    def effective_llm_enabled(self) -> bool:
        return bool(self.effective_anthropic_api_key or self.effective_gemini_api_key)


def get_settings() -> Settings:
    return Settings()
