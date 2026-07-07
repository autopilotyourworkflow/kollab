"""Output contract — mirrors `frontend/src/lib/types.ts` exactly.

The frontend already renders this shape (deployed at kollab-64c.pages.dev), and
its types.ts says plainly: "Mirrors what the Python pipeline will emit." These
Pydantic models ARE that contract. Fields are snake_case in Python and serialized
to the camelCase JSON the frontend expects via a camel alias generator.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
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


class VetCheck(CamelModel):
    """One line of the full vetting ledger for the internal report: every detector that
    ran, whether it fired, stayed clear, or was WITHHELD (min-cohort rule) — so the
    report shows exactly what Kollab could and could NOT judge, and why."""

    name: str  # internal id, e.g. "commenter_reuse"
    label: str  # human label, e.g. "Cross-creator commenter reuse"
    status: Literal["fired", "clear", "withheld"]
    level: RiskLevel
    detail: str
    measured_against: str


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


class RateBasis(CamelModel):
    """The full, transparent arithmetic behind a fair-rate ESTIMATE — so a band is never
    a bare number a reviewer could mistake for a market rate card. It is the creator's OWN
    measured organic reach × the operator's editable CPM assumption × the authenticity
    discount. The UI rescales `band` live from these inputs as the CPM changes; every value
    is provenance 'estimated'. Withheld (null) when the video sample is too thin to price."""

    median_organic_views: int  # measured, boosted/outlier posts excluded
    cpm_thb: float             # the OPERATOR's assumption (default; editable in the UI)
    authenticity: int          # 0-100 discount applied to reach (bought reach isn't paid)
    videos_sampled: int
    band: RateBand             # the computed estimate at the current CPM
    method: str                # human-readable arithmetic, incl. "not a market rate"


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
    # Estimated fair-rate band — the creator's OWN measured organic reach × an editable
    # CPM assumption × authenticity (see rate_basis for the arithmetic). NOT a market rate
    # card. Null (withheld) when the video sample is too thin to price.
    est_rate_thb: RateBand | None = None
    rate_basis: RateBasis | None = None
    hitl: HitlStatus = "pending"
    # Full vetting ledger (every check + withheld ones) for the internal report.
    checks: list[VetCheck] = []
    # When logged deliveries nudged the fit, the label explaining the adjustment (so the
    # displayed fit reconciles with the factor math). None when no outcomes are logged.
    delivery_note: str | None = None


class OverlapPair(CamelModel):
    """Two shortlisted creators who share a meaningful fraction of the SAME commenters —
    booking both double-serves that slice of the budget. Deliberately COMMENTER overlap,
    not "audience overlap": the shared count + Jaccard are measured on real commenter ids;
    the leap to "same audience" is an inferred proxy (the engaged subset), never a
    demographic claim. Low overlap is not proof of independence."""

    a_id: str
    a_handle: str
    b_id: str
    b_handle: str
    shared: int      # raw count of shared commenter accounts (measured)
    jaccard: float   # |A∩B| / |A∪B| over commenter sets (measured), 0-1
    a_share: float   # shared / A's commenters — how much of A overlaps B
    b_share: float
    note: str        # honest framing: commenters are a proxy for audience


class ClientBrief(CamelModel):
    brand: str
    brand_th: str
    category: str
    audience: str
    pillars: list[str]
    region: str
    website: str
    tone: str = ""  # brand voice, inferred from the site copy (advisory; may be "")


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
    # Pairs of shortlisted creators who share a meaningful commenter set (dedup helper).
    commenter_overlap: list[OverlapPair] = []


class DeliveredPostRequest(CamelModel):
    """Re-audit a creator's actual DELIVERED (paid) post — catches a creator who vetted
    clean but bought engagement for the sponsored content. Empty videos/comments -> the
    demo loads a fixture for this handle; production passes freshly-scraped post data."""

    handle: str
    pre_authenticity: int | None = None  # the pre-booking score to diff against
    videos: list[dict] = []              # Apify-shaped delivered-post items (optional)
    comments: list[dict] = []
    followers: int = 0


class DeliveryAudit(CamelModel):
    """The re-audit result: the delivered post run through the SAME structural detectors
    as the pre-booking vet, diffed against it."""

    handle: str
    pre_authenticity: int | None = None
    post_authenticity: int
    verdict: Literal["consistent", "degraded", "cleared", "inconclusive"]
    new_signals: list[FraudSignal] = []  # signals that fired on the delivered post
    checks: list[VetCheck] = []          # full ledger on the delivered post
    note: str


class DeliveryLogRequest(CamelModel):
    """Log a campaign outcome: what a booked creator's paid post actually delivered vs the
    reach Kollab projected at booking. The one input the closed loop learns from."""

    brand: str = ""
    handle: str
    projected_views: int
    actual_views: int
    note: str | None = None


class OutreachRequest(CamelModel):
    kol: Kol
    brief: ClientBrief


class OutreachDraft(CamelModel):
    """A first-contact message to a creator, grounded ONLY in safe (non-fraud, non-rate)
    data points. `grounded` is True when the LLM draft passed the citation validator; False
    for the deterministic template (no key / validation failed)."""

    en: str
    th: str
    grounded: bool
    source: Literal["llm", "template"]
    note: str


class SignupRequest(CamelModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=1024)  # cap before hashing (scrypt DoS)


class LoginRequest(CamelModel):
    email: str = Field(max_length=254)
    # No min_length here: a too-short password must still take the normal 401 path (not a
    # distinct 422), so it can't be used to probe. max_length caps the pre-hash work.
    password: str = Field(max_length=1024)


class BrandDnaRequest(CamelModel):
    website: str
    # Optional pre-read page text (the paste box / the browser bookmarklet — a real
    # browser reads sites a datacenter fetch can't). When present, extraction reads this
    # directly and skips the server-side fetch.
    text: str | None = None


class BrandDnaResponse(CamelModel):
    brief: ClientBrief
    degraded: bool  # True when extraction fell back to the rules skeleton
    source: str     # "claude" | "gemini" | "rules"
    note: str = ""
