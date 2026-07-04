"""FastAPI app — the judgment layer as an API.

The deployed frontend can point at this to replace its bundled fixtures with a live
call; both render the identical ShortlistResponse contract. Runs credential-free on
SeedDatasetSource. CORS is open to the Pages demo + localhost dev.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import get_settings
from app.pipeline import build_shortlist
from app.schemas import ClientBrief, ShortlistResponse
from app.sources.apify import ApifyAdapter
from app.sources.seed import SeedDatasetSource

app = FastAPI(
    title="Kollab API",
    version=__version__,
    description="Brand-fit + fraud-vetting judgment layer for Thai TikTok KOLs.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://kollab-64c.pages.dev",
        "http://localhost:5178",
        "http://localhost:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _make_source():
    settings = get_settings()
    if settings.source == "apify" and settings.apify_enabled:
        return ApifyAdapter(settings.apify_token)
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
        "min_cohort_n": s.min_cohort_n,
    }


@app.get("/api/shortlist", response_model=ShortlistResponse)
def get_shortlist() -> ShortlistResponse:
    """The default demo shortlist (Glow Lab) on curated fixtures."""
    source = _make_source()
    return build_shortlist(source, min_n=get_settings().min_cohort_n)


@app.post("/api/shortlist", response_model=ShortlistResponse)
def post_shortlist(brief: ClientBrief) -> ShortlistResponse:
    """Run the pipeline for a supplied brief. In fixtures mode the candidate set is
    the curated cohort; with a live source it sources against the brief."""
    source = _make_source()
    return build_shortlist(source, brief=brief, min_n=get_settings().min_cohort_n)


@app.get("/")
def root() -> dict:
    return {
        "name": "Kollab API",
        "tagline": "Not a scraper, not a database — the brand-fit and vetting brain.",
        "docs": "/docs",
        "endpoints": ["/health", "/api/shortlist"],
    }
