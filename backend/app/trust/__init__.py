"""Trust layer: provenance tags + DETERMINISTIC confidence (computed, not vibed).
Confidence is derived from sample size / data completeness / cohort-n — never an
LLM's self-reported number for objective fields."""

from app.trust.confidence import (
    audience_confidence,
    authenticity_confidence,
    outlier_confidence,
)
from app.trust.provenance import PROVENANCE_BY_FACTOR, advisory_tag

__all__ = [
    "authenticity_confidence",
    "audience_confidence",
    "outlier_confidence",
    "PROVENANCE_BY_FACTOR",
    "advisory_tag",
]
