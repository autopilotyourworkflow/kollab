"""Runtime configuration. Fixtures mode is the default so the deployed demo and
the test suite run with zero credentials. Env is read when get_settings() is
called (default_factory), not at import — so tests and process managers that set
env late see what they set."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as e:
        raise RuntimeError(f"{name} must be an integer, got {raw!r}") from e


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

    @property
    def apify_enabled(self) -> bool:
        return bool(self.apify_token)

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key or self.gemini_api_key)


def get_settings() -> Settings:
    return Settings()
