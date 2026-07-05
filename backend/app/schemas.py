"""Output contract — mirrors `frontend/src/lib/types.ts` exactly.

The frontend already renders this shape (deployed at kollab-64c.pages.dev), and
its types.ts says plainly: "Mirrors what the Python pipeline will emit." These
Pydantic models ARE that contract. Fields are snake_case in Python and serialized
to the camelCase JSON the frontend expects via a camel alias generator.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

Provenance = Literal["measured", "inferred", "estimated"]
RiskLevel = Literal["high", "medium", "clear"]
Tier = Literal["nano", "micro", "mid", "macro", "mega"]
HitlStatus = Literal["pending", "approved", "rejected"]
GateStatus = Literal["clear", "flag"]
FactorKey = Literal["topic", "authenticity", "recency", "audience"]


class CamelModel(BaseModel):
    """Base: snake_case in Python, camelCase on the wire (frontend contract)."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class FraudSignal(CamelModel):
    """A single triggered authenticity signal, grounded and cohort-anchored."""

    label: str  # e.g. "Comment pod"
    detail: str  # grounded, e.g. "41 accounts across 6 unrelated creators in 14 days"
    level: RiskLevel
    measured_against: str  # the baseline/n it was compared to


class Risk(CamelModel):
    level: RiskLevel
    signals: list[FraudSignal] = []


class MatchFactor(CamelModel):
    key: FactorKey
    label: str
    score: int  # 0-100
    weight: float  # audience is non-ranking: weight literally 0.0
    provenance: Provenance
    rationale: str  # one grounded line citing a real data point


class Avatar(CamelModel):
    initials: str
    hue: int


class Gate(CamelModel):
    status: GateStatus
    note: str | None = None


class RateBand(CamelModel):
    low: int
    high: int


class Kol(CamelModel):
    id: str
    handle: str
    name: str
    avatar: Avatar
    category: str
    category_th: str
    tier: Tier
    region: str
    # Core metrics (measured from public data in the demo)
    followers: int
    median_views: int
    engagement_rate: float  # %
    last_posted_days_ago: int
    # Outputs
    fit_score: int
    risk: Risk
    brand_safety: Gate
    conflict: Gate
    factors: list[MatchFactor]
    why_en: str
    why_th: str
    # Only set when grounded in >=2 cited Thai rate sources; otherwise null.
    est_rate_thb: RateBand | None = None
    hitl: HitlStatus = "pending"


class ClientBrief(CamelModel):
    brand: str
    brand_th: str
    category: str
    audience: str
    pillars: list[str]
    region: str
    website: str


class CostMeter(CamelModel):
    """Per-run transparency — real numbers on a real run, zeros in fixtures mode."""

    usd: float
    seconds: float
    cache_hit_rate: float  # 0-1


class ShortlistResponse(CamelModel):
    brief: ClientBrief
    kols: list[Kol]
    screened: int
    recommended: int
    flagged: int
    cost: CostMeter
    source: str  # "seed" | "apify" — which adapter produced the candidates
    degraded: bool = False  # True if brand ingest fell back to a lower tier
    # Expand-run dedup: known creators skipped before any spend (0 on fresh runs
    # and in fixtures mode).
    excluded_known: int = 0


class BrandDnaRequest(CamelModel):
    website: str


class BrandDnaResponse(CamelModel):
    brief: ClientBrief
    degraded: bool  # True when extraction fell back to the rules skeleton
    source: str     # "claude" | "gemini" | "rules"
    note: str = ""
