"""The KOLSource adapter interface. Every candidate source (seed fixtures, Apify
public sampling, a licensed feed in production) implements this, so the pipeline
never depends on where the data came from."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.raw import RawKOL
from app.schemas import ClientBrief


@dataclass
class Presentation:
    """Presentational + precomputed-relevance fields the pipeline needs to render a
    Kol but that aren't raw metrics. In fixtures mode these come from the curated
    descriptor; with embeddings/LLM enabled, topic/audience scores come live."""

    id: str
    name: str
    category: str
    category_th: str
    avatar_initials: str
    avatar_hue: int
    topic_score: int          # 0-100 brand-topic relevance (retrieval, precomputed in demo)
    audience_score: int       # 0-100 inferred audience affinity — ADVISORY, non-ranking
    brand_safety_status: str  # "clear" | "flag"
    brand_safety_note: str | None = None
    conflict_status: str = "clear"
    conflict_note: str | None = None
    hitl: str = "pending"
    # Curated grounded copy (seed mode). With the LLM path enabled these come from
    # the citation-validated rerank instead; None -> deterministic fallback text.
    topic_rationale: str | None = None
    audience_rationale: str | None = None
    why_en: str | None = None
    why_th: str | None = None


class KOLSource(ABC):
    """A source of candidate creators for a brief."""

    name: str = "base"

    @abstractmethod
    def fetch_candidates(self, brief: ClientBrief) -> list[RawKOL]:
        """Return the creators to be vetted + matched for this brief."""

    def reuse_corpus(self) -> list[RawKOL]:
        """Extra creators (beyond the candidates) used only to build the
        shared-commenter graph + reference cohorts. Production: the wider feed.
        Default: none."""
        return []

    @abstractmethod
    def presentation(self, kol: RawKOL) -> Presentation:
        """Presentational + precomputed-relevance fields for one creator."""
