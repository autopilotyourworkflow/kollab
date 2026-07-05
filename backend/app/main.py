"""FastAPI app — the judgment layer as an API.

The deployed frontend can point at this to replace its bundled fixtures with a live
call; both render the identical ShortlistResponse contract. Runs credential-free on
SeedDatasetSource. CORS is open to the Pages demo + localhost dev.

Live sourcing is slow (minutes), so it runs asynchronously: POST /api/runs starts a
background job whose state lives in the database, and the frontend polls
GET /api/runs/{id}. POST /api/shortlist keeps the synchronous path for fixtures and
direct/API use.
"""

from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager

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
from app.db import database_url, db_status, init_db
from app.ingest import extract_brand_dna
from app.schemas import BrandDnaRequest, BrandDnaResponse, ClientBrief, ShortlistResponse
from app.service import BadRequest, LiveRunError, run_shortlist
from app.sources.plans import public_payload


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


def _serve(run):
    """Map the service's typed errors to HTTP codes (400 bad input, 503 live-path
    precondition) so every endpoint answers honestly, never an opaque 500."""
    try:
        return run()
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except LiveRunError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Create the runs table when a database is configured (idempotent). A bad/absent
    # DATABASE_URL must never stop the seed demo from serving, so this is best-effort.
    try:
        init_db()
    except Exception:
        pass
    yield


app = FastAPI(
    title="Kollab API",
    version=__version__,
    description="Brand-fit + fraud-vetting judgment layer for Thai TikTok KOLs.",
    lifespan=lifespan,
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
        # Cheap flag (no DB round-trip); /api/db-status does the live check.
        "db_configured": bool(database_url()),
    }


@app.get("/api/db-status")
def db_status_endpoint() -> dict:
    """Live database connectivity — runs a real SELECT 1. A green result confirms the
    DATABASE_URL (Neon) credentials, network, and SSL all work from this host. Never
    leaks the URL/password."""
    return db_status()


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


@app.get("/api/shortlist", response_model=ShortlistResponse)
def get_shortlist() -> ShortlistResponse:
    """The default demo shortlist (Glow Lab) on curated fixtures."""
    return _serve(lambda: run_shortlist(None))


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
    """Synchronously run the pipeline for a brief. Fixtures mode returns the curated
    cohort; a live source blocks on the scrape (use POST /api/runs for the non-blocking
    path). `?preset=scan|standard|deep`, optional creators/comments overrides, cap_usd
    never exceeding the server ceiling. A visitor's own key rides the
    X-Apify-Token / X-Anthropic-Key headers. `?expand=1` skips creators this brand
    already holds; `?exclude=@handle` adds explicit skips; `excludedKnown` reports the
    dedup count."""
    with _request_keys(x_apify_token, x_anthropic_key):
        return _serve(lambda: run_shortlist(
            brief, preset=preset, creators=creators, comments=comments,
            cap_usd=cap_usd, expand=expand, exclude=exclude,
        ))


@app.post("/api/runs")
def start_run_endpoint(
    brief: ClientBrief,
    preset: str = "standard",
    expand: bool = False,
    exclude: list[str] = Query(default=[]),
    x_apify_token: str | None = Header(default=None),
    x_anthropic_key: str | None = Header(default=None),
) -> dict:
    """Start an async sourcing run; return its id immediately (a real scrape takes
    minutes — too long to hold the request open). Poll GET /api/runs/{id} for the
    result. Requires a database (run state lives there); without one, use
    POST /api/shortlist. The visitor's own key (if supplied) is captured here and used
    for the whole run."""
    if not database_url():
        raise HTTPException(
            status_code=503,
            detail="Async runs need a database — set DATABASE_URL (Neon). "
                   "Without it, POST /api/shortlist runs synchronously.",
        )
    with _request_keys(x_apify_token, x_anthropic_key):
        s = get_settings()
        apify = s.effective_apify_token
        anthropic = s.effective_anthropic_api_key
    from app.runs import start_run

    run_id = start_run(brief.model_dump(by_alias=True), preset, expand, exclude, apify, anthropic)
    return {"id": run_id, "status": "queued"}


@app.get("/api/runs/{run_id}")
def get_run_endpoint(run_id: str) -> dict:
    """Poll a run: {status: queued|running|done|error, result?, error?}. `result` is
    the camelCase ShortlistResponse the frontend merges once status is done."""
    from app.runs import get_run

    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


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
        "endpoints": ["/health", "/api/shortlist", "/api/runs"],
    }
