"""Run-depth plans for live sourcing: what the money buys, in evidence terms.

Users pick a DEPTH (creators × videos × comments), not a raw dollar figure — the
same spend allocated differently produces very different detection quality, so
the allocation policy is the system's job. Each preset carries:

  - a computed cost ESTIMATE from the verified actor prices ("what this intends
    to buy"), and
  - a hard CAP = estimate × CAP_HEADROOM, rounded up ("the worst case the user
    authorizes") — the sourcing loop stops BEFORE crossing it, so a too-tight
    cap yields a labeled partial pull, never a surprise bill or a silent gap,
  - an honest QUALITY NOTE: which signals can fire at that depth and which
    withhold (the min-cohort rule priced out loud).

The frontend renders the generated copy of this table
(frontend/src/data/run-plans.json); test_plans.py enforces byte-parity so the
UI's numbers can never drift from the backend's.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.config import PRICE_PER_1K_COMMENTS, PRICE_PER_1K_RESULTS

SEARCH_QUERIES = 3        # search_queries_from_brief() caps at 3
CAP_HEADROOM = 1.25       # authorized worst-case over the estimate (actor overdelivery)


@dataclass(frozen=True)
class RunPlan:
    key: str
    label: str
    max_creators: int
    videos_per_creator: int
    comments_per_creator: int
    results_per_query: int
    note: str

    @property
    def est_usd(self) -> float:
        """Projected spend: search results (videos come from the search — no extra
        fetch) + per-creator comment samples."""
        results = SEARCH_QUERIES * self.results_per_query
        comments = self.max_creators * self.comments_per_creator
        return round(results / 1000 * PRICE_PER_1K_RESULTS
                     + comments / 1000 * PRICE_PER_1K_COMMENTS, 2)

    @property
    def cap_usd(self) -> float:
        """Default authorized ceiling: estimate + headroom, rounded up to $0.25."""
        return math.ceil(self.est_usd * CAP_HEADROOM * 4) / 4


# results_per_query is deliberately modest: TikTok search-scraping is the slow,
# costly part of a run (each result is billed and the actor scrapes them serially),
# and grouping a few dozen on-query videos by author already yields more distinct
# creators than a preset selects. Bigger search pages buy diminishing candidates
# for a lot more time and money.
PRESETS: dict[str, RunPlan] = {
    "scan": RunPlan(
        key="scan", label="Scan", max_creators=8, videos_per_creator=20,
        comments_per_creator=50, results_per_query=15,
        note=("Fast triage of a niche. Structural pod signals only — peer-cohort "
              "stats withhold below n=15, and the cross-creator reuse graph is "
              "thin at 8 creators."),
    ),
    "standard": RunPlan(
        key="standard", label="Standard", max_creators=20, videos_per_creator=20,
        comments_per_creator=120, results_per_query=25,
        note=("Working shortlist. Solid pod/burst/templated detection; per-tier "
              "cohort cells usually still sit below n=15, so outlier stats may "
              "withhold — honestly labeled when they do."),
    ),
    "deep": RunPlan(
        key="deep", label="Deep", max_creators=40, videos_per_creator=20,
        comments_per_creator=150, results_per_query=40,
        note=("Shortlist-grade. The dominant vertical×tier cell approaches n≥15 "
              "so peer-band statistics can fire, and the reuse graph is at its "
              "strongest. The depth used for client-facing runs."),
    ),
}

DEFAULT_PRESET = "standard"


def resolve_plan(preset: str | None = None, creators: int | None = None,
                 comments: int | None = None) -> RunPlan:
    """Preset by name, with optional custom overrides (bounded to sane ranges).
    Unknown preset -> ValueError (the API answers 400, never a silent default)."""
    key = (preset or DEFAULT_PRESET).lower()
    if key not in PRESETS:
        raise ValueError(f"Unknown preset {preset!r} — one of {sorted(PRESETS)}.")
    plan = PRESETS[key]
    if creators is None and comments is None:
        return plan
    return RunPlan(
        key="custom", label="Custom",
        max_creators=max(3, min(int(creators or plan.max_creators), 100)),
        videos_per_creator=plan.videos_per_creator,
        comments_per_creator=max(20, min(int(comments or plan.comments_per_creator), 500)),
        results_per_query=plan.results_per_query,
        note="Custom depth — quality follows the volumes you chose; cohort stats "
             "withhold below n=15 regardless (the rule is not configurable).",
    )


def public_payload() -> dict:
    """The table the frontend renders (and the parity test enforces)."""
    return {
        "prices": {"per1kResults": PRICE_PER_1K_RESULTS, "per1kComments": PRICE_PER_1K_COMMENTS},
        "searchQueries": SEARCH_QUERIES,
        "capHeadroom": CAP_HEADROOM,
        "defaultPreset": DEFAULT_PRESET,
        "presets": [
            {
                "key": p.key, "label": p.label,
                "maxCreators": p.max_creators,
                "videosPerCreator": p.videos_per_creator,
                "commentsPerCreator": p.comments_per_creator,
                "resultsPerQuery": p.results_per_query,
                "estUsd": p.est_usd, "capUsd": p.cap_usd,
                "note": p.note,
            }
            for p in PRESETS.values()
        ],
    }
