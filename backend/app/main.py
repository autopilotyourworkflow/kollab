"""FastAPI app — the judgment layer as an API.

The deployed frontend can point at this to replace its bundled fixtures with a live
call; both render the identical ShortlistResponse contract. Runs credential-free on
SeedDatasetSource. CORS is open to the Pages demo + localhost dev.
"""

from __future__ import annotations

from contextlib import contextmanager

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import (
    get_settings,
    request_override_present,
    reset_request_credentials,
    set_request_credentials,
)
from app.credit import fetch_apify_credit
from app.ingest import extract_brand_dna
from app.matching.rerank import apply_llm_rerank
from app.pipeline import build_shortlist
from app.schemas import BrandDnaRequest, BrandDnaResponse, ClientBrief, ShortlistResponse
from app.sources.apify import ApifyAdapter
from app.sources.plans import public_payload, resolve_plan
from app.sources.seed import SeedDatasetSource
from app.store import known_handles, record_run


@contextmanager
def _request_keys(x_apify_token: str | None, x_anthropic_key: str | None):
    """Bring-your-own-key: a visitor who pasted their own Apify/Claude key in
    Settings sends it per-request as a header. We install it for the body of THIS
    request only (contextvar) and always reset it — the key is never persisted,
    never logged, never returned. Absent header -> the operator's shared key (if
    sharing is on). Set/read/reset all run in the endpoint's own thread, so the deep
    callers (Apify loop, LLM callers, credit check) transparently see the right key
    with no cross-request leakage."""
    token = set_request_credentials(x_apify_token, x_anthropic_key)
    try:
        yield
    finally:
        reset_request_credentials(token)


app = FastAPI(
    title="Kollab API",
    version=__version__,
    description="Brand-fit + fraud-vetting judgment layer for Thai TikTok KOLs.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://kollab.autopilotyourworkflow.com",  # production custom domain
        "https://kollab-64c.pages.dev",               # Pages project domain
        "http://localhost:5178",
        "http://localhost:5173",
    ],
    # Cloudflare Pages preview deploys get a per-commit subdomain
    # (<hash>.kollab-64c.pages.dev) — allow those too so preview links run live.
    allow_origin_regex=r"https://[a-z0-9-]+\.kollab-64c\.pages\.dev",
    allow_methods=["*"],
    allow_headers=["*"],
)


def _make_source(preset: str | None = None, creators: int | None = None,
                 comments: int | None = None, cap_usd: float | None = None):
    settings = get_settings()
    if settings.source == "apify":
        if not settings.effective_apify_enabled:
            # Honest fail-fast: never a silent fallback that pretends to be live.
            # With sharing off (or no operator key), the visitor must bring their own.
            raise HTTPException(
                status_code=503,
                detail="No Apify credit available for this run. Add your own Apify key in "
                       "Settings (it stays in your browser), or the operator can set "
                       "APIFY_TOKEN / KOLLAB_SHARED_KEY=1. The demo dataset always runs free.",
            )
        try:
            plan = resolve_plan(preset, creators, comments)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        # The user's cap can never exceed the server operator's ceiling.
        cap = min(cap_usd if cap_usd is not None else plan.cap_usd, settings.run_budget_usd)
        return ApifyAdapter(
            settings.effective_apify_token, budget_usd=cap,
            max_creators=plan.max_creators,
            videos_per_creator=plan.videos_per_creator,
            comments_per_creator=plan.comments_per_creator,
            results_per_query=plan.results_per_query,
            region=settings.region,
        )
    return SeedDatasetSource()


@app.get("/health")
def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "version": __version__,
        "source": s.source,
        "apify_enabled": s.apify_enabled,
        "llm_enabled": s.llm_enabled,
        "llm_rerank": s.llm_rerank and s.llm_enabled,
        "min_cohort_n": s.min_cohort_n,
        "run_budget_usd": s.run_budget_usd,
        # Whether the operator shares their own keys as the fallback (kill switch).
        "shared_key": s.shared_key,
    }


@app.get("/api/credit")
def credit(
    x_apify_token: str | None = Header(default=None),
    x_anthropic_key: str | None = Header(default=None),
) -> dict:
    """Live credit for the key THIS request runs on — the meter behind the run-time
    low-credit warning. `apify.source` is 'user' (visitor pasted their own key),
    'shared' (operator's key), or 'none'. Anthropic has no public balance endpoint,
    so we report presence only. Never returns any key value."""
    with _request_keys(x_apify_token, x_anthropic_key):
        s = get_settings()

        def _source(override_key: str, owner_present: bool) -> str:
            if request_override_present(override_key):
                return "user"
            return "shared" if (s.shared_key and owner_present) else "none"

        apify = fetch_apify_credit(s.effective_apify_token)
        apify["source"] = _source("apify_token", s.apify_enabled)
        apify["hasKey"] = bool(s.effective_apify_token)

        return {
            "sharedKey": s.shared_key,
            "apify": apify,
            "anthropic": {
                "hasKey": bool(s.effective_anthropic_api_key),
                "source": _source("anthropic_api_key", bool(s.anthropic_api_key)),
                "note": "Anthropic has no public balance API — usage is on console.anthropic.com.",
            },
        }


def _run_pipeline(source, brief: ClientBrief | None = None) -> ShortlistResponse:
    try:
        response = build_shortlist(source, brief=brief, min_n=get_settings().min_cohort_n)
    except RuntimeError as e:
        # Live-path preconditions (missing token/client, busted budget) surface as
        # an honest 503 with the reason — never an opaque 500 or a fake result.
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        # Live sources carry no default brief: GET has nothing to run against.
        raise HTTPException(
            status_code=400,
            detail=f"{e} POST /api/shortlist with a ClientBrief to run a live source.",
        ) from e
    return apply_llm_rerank(response)


@app.get("/api/shortlist", response_model=ShortlistResponse)
def get_shortlist() -> ShortlistResponse:
    """The default demo shortlist (Glow Lab) on curated fixtures."""
    return _run_pipeline(_make_source())


@app.post("/api/shortlist", response_model=ShortlistResponse)
def post_shortlist(
    brief: ClientBrief,
    preset: str | None = None,
    creators: int | None = None,
    comments: int | None = None,
    cap_usd: float | None = None,
    expand: bool = False,
    exclude: list[str] = Query(default=[]),
    x_apify_token: str | None = Header(default=None),
    x_anthropic_key: str | None = Header(default=None),
) -> ShortlistResponse:
    """Run the pipeline for a supplied brief. In fixtures mode the candidate set is
    the curated cohort; with a live source it sources against the brief at the
    requested run depth (?preset=scan|standard|deep, optional creators/comments
    overrides, cap_usd never exceeding the server ceiling). A visitor's own Apify /
    Claude key (from Settings) rides the X-Apify-Token / X-Anthropic-Key headers and
    runs this call on their credit instead of the operator's.

    Expand runs never buy the same data twice: `?expand=1` skips every creator
    this brand has pulled before (run-history store) and `?exclude=@handle` adds
    explicit skips — their slots fill with NEW creators, and `excludedKnown`
    reports how many were deduplicated."""
    with _request_keys(x_apify_token, x_anthropic_key):
        source = _make_source(preset, creators, comments, cap_usd)
        if isinstance(source, ApifyAdapter):
            skip = set(exclude)
            if expand:
                skip |= known_handles(brief.brand)
            source.exclude_handles = {h.strip().lstrip("@").lower() for h in skip}
        response = _run_pipeline(source, brief=brief)
        if isinstance(source, ApifyAdapter):
            record_run(brief.brand, [k.handle for k in response.kols])
            response.excluded_known = int(source.last_run.get("excluded_known", 0))
        return response


@app.get("/api/run-plans")
def run_plans() -> dict:
    """Run-depth presets with computed cost estimates, default caps, and honest
    quality notes — what each spend buys in evidence terms."""
    return public_payload()


@app.post("/api/brand-dna", response_model=BrandDnaResponse)
def brand_dna(
    req: BrandDnaRequest,
    x_apify_token: str | None = Header(default=None),
    x_anthropic_key: str | None = Header(default=None),
) -> BrandDnaResponse:
    """Website → structured brief. Claude → Gemini → rules skeleton; the response
    names its source and flags degraded extraction — the UI badges it honestly. A
    visitor's own Claude key (X-Anthropic-Key header, from Settings) runs the
    extraction on their credit; without any key it returns the labeled skeleton."""
    with _request_keys(x_apify_token, x_anthropic_key):
        result = extract_brand_dna(req.website)
        return BrandDnaResponse(
            brief=result.brief, degraded=result.degraded, source=result.source, note=result.note
        )


@app.get("/")
def root() -> dict:
    return {
        "name": "Kollab API",
        "tagline": "Not a scraper, not a database — the brand-fit and vetting brain.",
        "docs": "/docs",
        "endpoints": ["/health", "/api/shortlist"],
    }
