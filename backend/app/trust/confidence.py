"""Deterministic confidence — computed from the data, not emitted by an LLM.

Each function returns a 0-1 confidence for a specific derived field, with the input
that drives it named in its docstring so one doc line can explain every number.
LLM-emitted confidence is reserved only for genuinely subjective fields elsewhere
and is clearly marked as such.
"""

from __future__ import annotations


def authenticity_confidence(comment_sample_size: int, target: int = 200) -> float:
    """Confidence in the fraud verdict scales with how many comments we sampled.
    Full confidence at `target` sampled comments; linear below."""
    if comment_sample_size <= 0:
        return 0.0
    return round(min(1.0, comment_sample_size / target), 2)


def audience_confidence(fields_present: int, fields_total: int) -> float:
    """Confidence in inferred audience scales with data completeness. Kept low by
    design — audience is advisory/non-ranking and must not be quoted as fact."""
    if fields_total <= 0:
        return 0.0
    return round(0.6 * (fields_present / fields_total), 2)  # capped at 0.6: inferred


def outlier_confidence(cohort_n: int, min_n: int = 15) -> float:
    """Confidence in a cohort-outlier signal scales with peer count; 0 below min_n
    (the signal is withheld there anyway)."""
    if cohort_n < min_n:
        return 0.0
    return round(min(1.0, cohort_n / (2 * min_n)), 2)
