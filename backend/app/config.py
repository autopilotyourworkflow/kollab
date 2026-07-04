"""Runtime configuration. Fixtures mode is the default so the deployed demo and
the test suite run with zero credentials. Real adapters activate only when their
keys are present in the environment (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # Candidate source: "seed" (fixtures) or "apify" (live public-data sampling).
    source: str = os.getenv("KOLLAB_SOURCE", "seed")

    # Optional credentials. Absent -> the corresponding live path stays disabled
    # and the pipeline transparently degrades to the fixtures/deterministic path.
    apify_token: str | None = os.getenv("APIFY_TOKEN") or None
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY") or None
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY") or None

    # Minimum cohort size before an outlier signal is allowed to fire. Below this
    # the badge reads "insufficient baseline — signal withheld" (see fraud.cohort).
    min_cohort_n: int = int(os.getenv("KOLLAB_MIN_COHORT_N", "15"))

    @property
    def apify_enabled(self) -> bool:
        return bool(self.apify_token)

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key or self.gemini_api_key)


def get_settings() -> Settings:
    return Settings()
