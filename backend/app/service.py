"""Shortlist orchestration, shared by the synchronous endpoint and the async job
runner. Turns (brief + run depth) into a ShortlistResponse, raising typed errors the
callers map to HTTP codes (or record on a job row)."""

from __future__ import annotations

from collections.abc import Iterable

from app.config import get_settings
from app.matching.rerank import apply_llm_rerank
from app.pipeline import build_shortlist
from app.schemas import ClientBrief, ShortlistResponse
from app.sources.apify import ApifyAdapter
from app.sources.plans import resolve_plan
from app.sources.seed import SeedDatasetSource
from app.store import known_handles, record_run


class LiveRunError(RuntimeError):
    """A live path cannot run (missing token/dependency, budget too tight) -> 503."""


class BadRequest(ValueError):
    """Bad input (unknown preset, missing brief for a live source) -> 400."""


def make_source(preset: str | None = None, creators: int | None = None,
                comments: int | None = None, cap_usd: float | None = None,
                cancel_check=None):
    """Seed fixtures, or a budget-capped ApifyAdapter at the requested depth. The
    per-request effective key (visitor's own, or the shared operator key) is what the
    adapter runs on; a missing key is an honest LiveRunError, never a silent fake."""
    settings = get_settings()
    if settings.source != "apify":
        return SeedDatasetSource()
    if not settings.effective_apify_enabled:
        raise LiveRunError(
            "No Apify credit available for this run. Add your own Apify key in "
            "Settings (it stays in your browser), or the operator can set "
            "APIFY_TOKEN / KOLLAB_SHARED_KEY=1. The demo dataset always runs free."
        )
    try:
        plan = resolve_plan(preset, creators, comments)
    except ValueError as e:
        raise BadRequest(str(e)) from e
    # The user's cap can never exceed the operator's ceiling.
    cap = min(cap_usd if cap_usd is not None else plan.cap_usd, settings.run_budget_usd)
    return ApifyAdapter(
        settings.effective_apify_token, budget_usd=cap,
        max_creators=plan.max_creators,
        videos_per_creator=plan.videos_per_creator,
        comments_per_creator=plan.comments_per_creator,
        results_per_query=plan.results_per_query,
        region=settings.region,
        cancel_check=cancel_check,
    )


def run_shortlist(brief: ClientBrief | None, preset: str | None = None,
                  creators: int | None = None, comments: int | None = None,
                  cap_usd: float | None = None, expand: bool = False,
                  exclude: Iterable[str] = (), cancel_check=None) -> ShortlistResponse:
    """The full path: source -> vet -> match -> rank -> rerank. Expand runs skip the
    brand's already-held creators before any spend and report the dedup count.
    `cancel_check` (an optional () -> bool) lets a background run be stopped."""
    source = make_source(preset, creators, comments, cap_usd, cancel_check=cancel_check)
    is_live = isinstance(source, ApifyAdapter)
    if is_live:
        skip = {h.strip().lstrip("@").lower() for h in exclude}
        if expand and brief is not None:
            skip |= known_handles(brief.brand)
        source.exclude_handles = skip
    try:
        response = build_shortlist(source, brief=brief, min_n=get_settings().min_cohort_n)
    except RuntimeError as e:  # missing token/dep, busted budget
        raise LiveRunError(str(e)) from e
    except ValueError as e:  # a live source carries no default brief
        raise BadRequest(f"{e} POST a ClientBrief to run a live source.") from e
    response = apply_llm_rerank(response)
    if is_live and brief is not None:
        record_run(brief.brand, [k.handle for k in response.kols])
        response.excluded_known = int(source.last_run.get("excluded_known", 0))
    return response
