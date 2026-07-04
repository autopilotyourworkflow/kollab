"""Authenticity / fraud vetting — the hero differentiator.

Design principle (from PLAN.md): STRUCTURAL detectors lead and are the durable
part; the Thai phrase lexicon is only a tiebreaker/explainability aid that pod
farms rotate monthly. Every fired signal is grounded (names the triggered pattern)
and cohort-anchored (states the distribution + n it was measured against). Outlier
signals fire only at n >= min_cohort_n; below that the signal is withheld, never
guessed. What the tool CANNOT detect (true demographics, bot-at-scale, private
analytics) is stated explicitly as a trust signal.
"""

from app.fraud.cohort import CohortStats, build_cohorts, engagement_rate
from app.fraud.vet import vet_cohort, vet_kol

__all__ = [
    "CohortStats",
    "build_cohorts",
    "engagement_rate",
    "vet_kol",
    "vet_cohort",
]
