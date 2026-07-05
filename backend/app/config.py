"""Runtime configuration. Fixtures mode is the default so the deployed demo and
the test suite run with zero credentials. Env is read when get_settings() is
called (default_factory), not at import — so tests and process managers that set
env late see what they set."""

from __future__ import annotations

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
    # Candidate source: "seed" (fixtures) or "apify" (live public-data sampling —
    # the adapter seam exists but the actor-run loop is roadmap; the API answers 503).
    source: str = field(default_factory=lambda: os.getenv("KOLLAB_SOURCE", "seed"))

    # Optional credentials — read and surfaced in /health. The live paths they
    # unlock (Apify actor loop, LLM Brand-DNA/rerank) are roadmap; see README.
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

    @property
    def apify_enabled(self) -> bool:
        return bool(self.apify_token)

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key or self.gemini_api_key)


def get_settings() -> Settings:
    return Settings()
